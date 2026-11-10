#!/usr/bin/env python3
"""Serve the web serial monitor and store CSI recordings under ../recordings/.

v3 storage contract (docs/recording-pipeline-implementation.md §3, §5):
a take is exactly two files, ``<id>.frames.csv`` and ``<id>.meta.json``.
POST payloads are validated BEFORE anything is written so a rejected take
never leaves partial files behind. Legacy v1/v2 artifacts are still listed,
served and deleted, but the server never creates them anymore.
"""

from __future__ import annotations

import argparse
import base64
import binascii
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

# Must match FRAMES_HEADER in tools/csi_recorder.js byte for byte (spec §4).
FRAMES_HEADER = [
    "recording_id", "frame_sequence", "seq", "rx_seq", "mac", "dmac", "rssi",
    "noise_floor", "channel", "secondary_channel", "sig_mode", "mcs", "rate",
    "bandwidth", "stbc", "data_type", "raw_len", "valid_len", "lltf_len",
    "ht_ltf_len", "stbc_ht_ltf_len", "first_word_invalid", "agc_gain",
    "fft_gain", "rx_gain_compensation", "callback_timestamp_us",
    "rx_ctrl_timestamp_us", "host_receive_monotonic_ns", "dropped",
    "payload_ok", "raw_b64", "valid_b64",
]

BINARY_LABELS = {
    "fall_forward": "fall",
    "fall_backward": "fall",
    "fall_lemas": "fall",
    "fall_keseleo": "fall",
    "walking": "non_fall",
    "fast_sitting": "non_fall",
    "bending": "non_fall",
    "object_drop": "non_fall",
    "empty_room": "non_fall",
    "still_standing": "non_fall",
    "still_sitting": "non_fall",
}

INDEX_HEADER = [
    "id",
    "activity_label",
    "binary_label",
    "started_at_utc",
    "target_duration_s",
    "actual_duration_s",
    "frames",
    "complete",
    "status",
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


def _meta_label(meta: dict, fallback: str) -> str:
    return str(meta.get("activity_label") or meta.get("label") or fallback)


def _meta_recording_node(meta: dict) -> dict:
    node = meta.get("recording")
    return node if isinstance(node, dict) else {}


def _index_row(meta: dict, rec_id: str, folder: str) -> dict:
    label = _meta_label(meta, folder)
    recording = _meta_recording_node(meta)
    frames = recording.get("frames", meta.get("frames", ""))
    complete = recording.get("complete", meta.get("complete", ""))
    actual = meta.get("actual_duration_s", meta.get("duration_s", ""))
    return {
        "id": rec_id,
        "activity_label": label,
        "binary_label": BINARY_LABELS.get(label, ""),
        "started_at_utc": meta.get("started_at_utc", ""),
        "target_duration_s": meta.get("target_duration_s", ""),
        "actual_duration_s": actual,
        "frames": frames,
        "complete": complete,
        "status": meta.get("status", "complete" if complete in (True, "true") else ""),
        "meta": f"{folder}/{rec_id}.meta.json",
    }


def rewrite_index(recordings_dir: Path) -> list[dict]:
    rows: list[dict] = []
    if recordings_dir.exists():
        for meta_file in sorted(recordings_dir.glob("*/*.meta.json")):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rec_id = str(
                meta.get("recording_id") or meta.get("id")
                or meta_file.name.replace(".meta.json", "")
            )
            rows.append(_index_row(meta, rec_id, meta_file.parent.name))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=INDEX_HEADER, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    atomic_write(index_path(recordings_dir), buf.getvalue())
    return rows


def recording_paths(recordings_dir: Path, rec_id: str, label: str) -> dict[str, Path]:
    folder = safe_join(recordings_dir, slug_label(label) or "unlabeled")
    paths = {
        "frames": folder / f"{rec_id}.frames.csv",
        "meta": folder / f"{rec_id}.meta.json",
    }
    # Legacy v1/v2 artifacts: never created anymore, but GET/DELETE must keep
    # working for takes recorded before the two-file contract.
    for key, suffix in (
        ("csi_data", ".csi_data.csv"),
        ("iq", ".iq.csv"),
        ("raw_iq", ".raw_iq.csv"),
        ("events", ".events.json"),
        ("quality", ".quality_report.json"),
    ):
        paths[key] = folder / f"{rec_id}{suffix}"
    return paths


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
            meta = {"recording_id": rec_id}
        label = _meta_label(meta, meta_file.parent.name)
        paths = recording_paths(recordings_dir, rec_id, label)
        return {"id": rec_id, "label": label, "meta": meta, "paths": paths}
    return None


def validate_frames_csv(frames_csv: str, meta: dict) -> list[str]:
    """Validate the frames payload against the 32-column contract (spec §16.A/B).

    Returns a list of human-readable problems; empty means valid. Checks run
    before any file is written so a bad take cannot leave partial artifacts.
    """
    errors: list[str] = []
    if not isinstance(frames_csv, str) or not frames_csv.strip():
        return ["frames_csv is empty"]
    reader = csv.reader(io.StringIO(frames_csv))
    try:
        header = next(reader)
    except StopIteration:
        return ["frames_csv has no header"]
    if header != FRAMES_HEADER:
        return [f"frames_csv header mismatch: expected {len(FRAMES_HEADER)} columns"]
    idx = {name: i for i, name in enumerate(header)}
    raw_i = idx["raw_b64"]
    valid_i = idx["valid_b64"]
    raw_len_i = idx["raw_len"]
    valid_len_i = idx["valid_len"]
    seq_i = idx["frame_sequence"]
    rows = 0
    for row in reader:
        if not row:
            continue
        if len(row) != len(FRAMES_HEADER):
            errors.append(f"row {rows}: expected {len(FRAMES_HEADER)} fields, got {len(row)}")
            break
        if row[seq_i] != str(rows):
            errors.append(f"row {rows}: frame_sequence is {row[seq_i]!r}, expected {rows!r}")
            break
        for b64_i, len_i, name in ((raw_i, raw_len_i, "raw"), (valid_i, valid_len_i, "valid")):
            cell = row[b64_i]
            declared = row[len_i]
            if not cell:
                if declared not in ("0", "na"):
                    errors.append(f"row {rows}: empty {name}_b64 but {name}_len={declared}")
                    break
                continue
            try:
                decoded_len = len(base64.b64decode(cell, validate=True))
            except (binascii.Error, ValueError):
                errors.append(f"row {rows}: {name}_b64 is not valid base64")
                break
            if declared not in ("na", "") and decoded_len != int(float(declared)):
                errors.append(
                    f"row {rows}: {name}_b64 decodes to {decoded_len} bytes but {name}_len={declared}"
                )
                break
        if errors:
            break
        rows += 1
    if errors:
        return errors
    recording = _meta_recording_node(meta)
    expected_frames = recording.get("frames", None)
    if isinstance(expected_frames, int) and expected_frames != rows:
        errors.append(f"meta.recording.frames={expected_frames} but frames.csv has {rows} rows")
    if rows == 0:
        errors.append("frames.csv has no data rows")
    return errors


def validate_meta(meta: dict, rec_id: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(meta, dict):
        return ["meta must be a JSON object"]
    if "schema_version" not in meta:
        errors.append("meta.schema_version is missing")
    recording_id = meta.get("recording_id")
    if recording_id != rec_id:
        errors.append(f"meta.recording_id={recording_id!r} does not match id={rec_id!r}")
    if not meta.get("activity_label"):
        errors.append("meta.activity_label is missing")
    target = meta.get("target_duration_s")
    # target_duration_s is derived from the last timeline boundary (fall = 12 s,
    # most others = 10 s) rather than a single fixed value; the server only
    # checks it is a positive number, never a specific one.
    if target is not None and (not isinstance(target, (int, float))
                               or isinstance(target, bool) or target <= 0):
        errors.append(f"meta.target_duration_s={target!r}, expected a positive number or null")
    files = meta.get("files")
    if not isinstance(files, dict) or not files.get("frames_csv") or not files.get("meta_json"):
        errors.append("meta.files must reference frames_csv and meta_json")
    elif files.get("frames_csv") != f"{rec_id}.frames.csv" or files.get("meta_json") != f"{rec_id}.meta.json":
        errors.append("meta.files does not match the two-file naming contract")
    for legacy in ("legacy_iq_csv", "raw_iq_rows"):
        semantics = meta.get("payload_semantics")
        if isinstance(semantics, dict) and legacy in semantics:
            errors.append(f"meta.payload_semantics still references discontinued file semantics: {legacy}")
    return errors


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
            payload["activity_label"] = found["label"]
            payload["label"] = found["label"]
            for key, name in (("frames_csv", "frames"),):
                path = found["paths"][name]
                payload[key] = path.read_text(encoding="utf-8") if path.exists() else ""
            # Legacy payloads are only served when the files actually exist so
            # old takes keep visualising; v3 takes simply omit these keys' data.
            for key, name in (("csi_data_csv", "csi_data"), ("iq_csv", "iq"),
                              ("raw_iq_csv", "raw_iq")):
                path = found["paths"][name]
                if path.exists():
                    payload[key] = path.read_text(encoding="utf-8")
            for key, name in (("events", "events"), ("quality_report", "quality")):
                path = found["paths"][name]
                if path.exists():
                    try:
                        payload[key] = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        payload[key] = None
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

        rec_id = str(body.get("id") or "").strip()
        if not ID_RE.match(rec_id):
            return self._json(400, {"ok": False, "error": "invalid id"})
        if ".." in rec_id or "/" in rec_id or "\\" in rec_id:
            return self._json(400, {"ok": False, "error": "invalid id"})
        meta = body.get("meta") if isinstance(body.get("meta"), dict) else None
        if meta is None:
            return self._json(400, {"ok": False, "error": "meta object is required"})
        meta = dict(meta)
        meta["recording_id"] = rec_id
        label = str(meta.get("activity_label") or meta.get("label") or "").strip()
        slug = slug_label(label)
        if not slug or not SLUG_RE.match(slug):
            return self._json(400, {"ok": False, "error": "invalid activity label"})
        meta["activity_label"] = label
        meta.pop("label", None)

        # Reject unknown extras from old clients: the two-file contract means
        # csi_data/iq/raw_iq/events payloads are no longer accepted or stored.
        for stale in ("csi_data_csv", "iq_csv", "raw_iq_csv", "events", "label"):
            if stale in body:
                return self._json(400, {
                    "ok": False,
                    "error": f"field {stale!r} is no longer accepted; post frames_csv + meta only",
                })

        frames_csv = body.get("frames_csv")
        errors = validate_meta(meta, rec_id) + validate_frames_csv(frames_csv, meta)
        if errors:
            return self._json(400, {"ok": False, "error": "; ".join(errors)})

        paths = recording_paths(self.recordings_dir, rec_id, slug)
        # Write frames first, then meta; meta.json is the commit point (the
        # index and all readers key off it). Remove frames if meta fails.
        atomic_write(paths["frames"], frames_csv)
        try:
            atomic_write(paths["meta"], json.dumps(meta, indent=2) + "\n")
        except Exception:
            try:
                paths["frames"].unlink()
            except OSError:
                pass
            raise
        rewrite_index(self.recordings_dir)
        return self._json(
            200,
            {
                "ok": True,
                "id": rec_id,
                "label": slug,
                "paths": {
                    "frames": str(paths["frames"].relative_to(self.recordings_dir)),
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
