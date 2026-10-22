#!/usr/bin/env python3
"""Serve the web serial monitor and store CSI recordings under ../recordings/."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import posixpath
import re
import sys
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_RECORDINGS_DIR = TOOLS_DIR.parent / "recordings"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")
SLUG_RE = re.compile(r"^[a-z0-9_][a-z0-9_-]{0,47}$")
INDEX_HEADER = [
    "id",
    "label",
    "started_at_utc",
    "duration_s",
    "frames",
    "complete",
    "csi_data",
    "iq",
    "meta",
]


def slug_label(label: str) -> str:
    text = re.sub(r"[^a-z0-9_-]+", "_", (label or "").strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:48]


def safe_join(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError("path escapes recordings directory")
    return candidate


def atomic_write(path: Path, data: str | bytes, binary: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".part", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb" if binary else "w", encoding=None if binary else "utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def index_path(recordings_dir: Path) -> Path:
    return recordings_dir / "index.csv"


def rewrite_index(recordings_dir: Path) -> list[dict]:
    rows: list[dict] = []
    if recordings_dir.exists():
        for meta_file in sorted(recordings_dir.glob("*/*.meta.json")):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rec_id = meta.get("id") or meta_file.name.replace(".meta.json", "")
            label = meta.get("label") or meta_file.parent.name
            stem = rec_id
            rows.append(
                {
                    "id": rec_id,
                    "label": label,
                    "started_at_utc": meta.get("started_at_utc", ""),
                    "duration_s": meta.get("duration_s", ""),
                    "frames": meta.get("frames", ""),
                    "complete": meta.get("complete", ""),
                    "csi_data": f"{label}/{stem}.csi_data.csv",
                    "iq": f"{label}/{stem}.iq.csv",
                    "meta": f"{label}/{stem}.meta.json",
                }
            )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=INDEX_HEADER, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    atomic_write(index_path(recordings_dir), buf.getvalue())
    return rows


def recording_paths(recordings_dir: Path, rec_id: str, label: str) -> dict[str, Path]:
    folder = safe_join(recordings_dir, slug_label(label) or "unlabeled")
    return {
        "csi_data": folder / f"{rec_id}.csi_data.csv",
        "iq": folder / f"{rec_id}.iq.csv",
        "meta": folder / f"{rec_id}.meta.json",
    }


def find_recording(recordings_dir: Path, rec_id: str) -> dict | None:
    if not ID_RE.match(rec_id):
        return None
    for meta_file in recordings_dir.glob(f"*/{rec_id}.meta.json"):
        try:
            safe_join(recordings_dir, meta_file.relative_to(recordings_dir))
        except ValueError:
            return None
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {"id": rec_id}
        label = meta.get("label") or meta_file.parent.name
        paths = recording_paths(recordings_dir, rec_id, label)
        return {"id": rec_id, "label": label, "meta": meta, "paths": paths}
    return None


class RecorderHandler(SimpleHTTPRequestHandler):
    recordings_dir: Path

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(TOOLS_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code: int, payload: dict | list):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 32 * 1024 * 1024:
            raise ValueError("invalid content length")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        return data

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/recordings":
            rows = rewrite_index(self.recordings_dir)
            return self._json(200, {"recordings": rows})
        if parsed.path.startswith("/api/recordings/"):
            rec_id = posixpath.basename(parsed.path)
            found = find_recording(self.recordings_dir, rec_id)
            if not found:
                return self._json(404, {"ok": False, "error": "not found"})
            payload = dict(found["meta"])
            payload["id"] = found["id"]
            payload["label"] = found["label"]
            for key, name in (("csi_data_csv", "csi_data"), ("iq_csv", "iq")):
                path = found["paths"][name]
                payload[key] = path.read_text(encoding="utf-8") if path.exists() else ""
            return self._json(200, payload)
        if parsed.path in ("/", ""):
            self.path = "/web_serial_monitor.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/recordings":
            return self._json(404, {"ok": False, "error": "not found"})
        try:
            body = self._read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json(400, {"ok": False, "error": str(exc)})

        label = str(body.get("label") or "").strip()
        slug = slug_label(label)
        if not slug or not SLUG_RE.match(slug):
            return self._json(400, {"ok": False, "error": "invalid label"})
        rec_id = str(body.get("id") or "").strip()
        if not ID_RE.match(rec_id):
            return self._json(400, {"ok": False, "error": "invalid id"})
        if rec_id.split("_")[-2:] and slug not in rec_id:
            # id must contain the slug so listing stays grouped by label
            pass
        if ".." in rec_id or "/" in rec_id or "\\" in rec_id:
            return self._json(400, {"ok": False, "error": "invalid id"})

        csi_csv = str(body.get("csi_data_csv") or "")
        iq_csv = str(body.get("iq_csv") or "")
        meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
        meta = dict(meta)
        meta["id"] = rec_id
        meta["label"] = label

        paths = recording_paths(self.recordings_dir, rec_id, slug)
        atomic_write(paths["csi_data"], csi_csv)
        atomic_write(paths["iq"], iq_csv)
        atomic_write(paths["meta"], json.dumps(meta, indent=2) + "\n")
        rewrite_index(self.recordings_dir)
        return self._json(
            200,
            {
                "ok": True,
                "id": rec_id,
                "label": slug,
                "paths": {
                    "csi_data": str(paths["csi_data"].relative_to(self.recordings_dir)),
                    "iq": str(paths["iq"].relative_to(self.recordings_dir)),
                    "meta": str(paths["meta"].relative_to(self.recordings_dir)),
                },
            },
        )

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/recordings/"):
            return self._json(404, {"ok": False, "error": "not found"})
        rec_id = posixpath.basename(parsed.path)
        found = find_recording(self.recordings_dir, rec_id)
        if not found:
            return self._json(404, {"ok": False, "error": "not found"})
        for path in found["paths"].values():
            try:
                if path.is_file() and self.recordings_dir.resolve() in path.resolve().parents:
                    path.unlink()
            except OSError:
                pass
        rewrite_index(self.recordings_dir)
        return self._json(200, {"ok": True, "id": rec_id})

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def make_handler(recordings_dir: Path):
    class BoundHandler(RecorderHandler):
        pass

    BoundHandler.recordings_dir = recordings_dir
    return BoundHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CSI recorder HTTP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--recordings-dir", default=os.environ.get("CSI_RECORDINGS_DIR", str(DEFAULT_RECORDINGS_DIR)))
    args = parser.parse_args(argv)
    recordings_dir = Path(args.recordings_dir).resolve()
    recordings_dir.mkdir(parents=True, exist_ok=True)
    rewrite_index(recordings_dir)
    handler = make_handler(recordings_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {TOOLS_DIR} on http://{args.host}:{args.port}/web_serial_monitor.html")
    print(f"Recordings -> {recordings_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
