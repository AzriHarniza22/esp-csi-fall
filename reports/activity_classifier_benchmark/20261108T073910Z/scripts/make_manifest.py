"""Build the dataset snapshot: manifest with SHA-256 hashes + audited counts.

Run from repository root:
    python3 reports/activity_classifier_benchmark/20261108T073910Z/scripts/make_manifest.py
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import bench_common as bc

OUT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    meta_rows = []
    for meta_path in bc.discover_takes():
        tid = meta_path.name[: -len(".meta.json")]
        take = bc.load_take(meta_path)
        frames_path = meta_path.with_name(f"{tid}.frames.csv")
        meta_rows.append(
            {
                "recording_id": tid,
                "activity_label": take["activity_label"],
                "subject_id": take["subject_id"] or "",
                "session_id": take["session_id"] or "",
                "batch_id": take["batch_id"] or "",
                "recording_date": take["recording_date"],
                "frames": take["frames"],
                "windows": len(take["windows"]),
                "duration_s": round(take["duration_s"], 3),
                "subcarrier_width": take["subcarrier_width"],
                "skipped_frames": take["skipped_no_payload"] + take["skipped_layout"],
                "meta_sha256": sha256(meta_path),
                "frames_sha256": sha256(frames_path),
            }
        )
    with (OUT / "dataset_manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(meta_rows[0]))
        writer.writeheader()
        writer.writerows(meta_rows)
    with (OUT / "dataset_snapshot_hashes.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["recording_id", "meta_sha256", "frames_sha256"])
        for row in meta_rows:
            writer.writerow([row["recording_id"], row["meta_sha256"], row["frames_sha256"]])

    summary = {
        "takes": len(meta_rows),
        "frames": sum(r["frames"] for r in meta_rows),
        "windows": sum(r["windows"] for r in meta_rows),
        "skipped_frames": sum(r["skipped_frames"] for r in meta_rows),
        "labels": {},
    }
    for row in meta_rows:
        entry = summary["labels"].setdefault(
            row["activity_label"], {"takes": 0, "windows": 0, "subjects": set(), "sessions": set()}
        )
        entry["takes"] += 1
        entry["windows"] += row["windows"]
        entry["subjects"].add(row["subject_id"] or "None")
        entry["sessions"].add(row["session_id"] or "None")
    for entry in summary["labels"].values():
        entry["subjects"] = sorted(entry["subjects"])
        entry["sessions"] = sorted(entry["sessions"])
    (OUT / "dataset_snapshot_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
