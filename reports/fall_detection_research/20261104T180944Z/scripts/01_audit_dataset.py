#!/usr/bin/env python3
"""C3: full read-only audit of recordings/ used by the current trainer.

For every *.meta.json under recordings/ this reports: label, batch/session,
take index within batch, schema version, status, frame count, duration,
pre/post action, timeline phase boundaries, per-frame layout consistency
(lltf_len/valid_len/data_type/sig_mode/stbc/first_word_invalid), the number
of feature windows the trainer would actually produce (same maths as
train_activity_model.extract_window_features), and gap_before_s.

Output: dataset_audit.json + a per-label summary table on stdout.
Read-only: touches no recording, no source file.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from fall_detection.audit_dataset import audit_take  # noqa: E402
from fall_detection.train_activity_model import (  # noqa: E402
    WINDOW_FRAMES,
    WINDOW_STRIDE,
    read_amplitude_frames_from_frames_csv,
    extract_window_features,
)

RECORDINGS = REPO / "examples/esp-radar/wifi_sensing_demo/recordings"


def layout_stats(frames_path: Path) -> dict:
    seen = defaultdict(int)
    widths = defaultdict(int)
    with frames_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = (
                row.get("sig_mode"), row.get("bandwidth"), row.get("stbc"),
                row.get("secondary_channel"), row.get("data_type"),
                row.get("lltf_len"), row.get("ht_ltf_len"),
                row.get("stbc_ht_ltf_len"), row.get("valid_len"),
                row.get("first_word_invalid"),
            )
            seen[key] += 1
    return {
        "layouts": [
            {
                "sig_mode": k[0], "bandwidth": k[1], "stbc": k[2],
                "secondary": k[3], "data_type": k[4], "lltf_len": k[5],
                "ht_ltf_len": k[6], "stbc_ht_ltf_len": k[7],
                "valid_len": k[8], "first_word_invalid": k[9], "frames": v,
            }
            for k, v in sorted(seen.items(), key=lambda kv: -kv[1])
        ]
    }


def main() -> int:
    rows = []
    for meta_path in sorted(RECORDINGS.rglob("*.meta.json")):
        audit = audit_take(meta_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        rec_id = audit.recording_id
        frames_path = meta_path.with_name(f"{rec_id}.frames.csv")
        windows = 0
        width = None
        layout = {}
        if frames_path.is_file():
            layout = layout_stats(frames_path)
            try:
                frames = read_amplitude_frames_from_frames_csv(frames_path)
                feats = extract_window_features(frames)
                windows = len(feats)
                width = len(frames[0]) if frames else 0
            except Exception as exc:  # noqa: BLE001 - audit reports, never crashes
                layout["read_error"] = str(exc)
        batch = meta.get("batch") or {}
        activity = meta.get("activity") or {}
        timeline = meta.get("timeline") or {}
        recording_node = meta.get("recording") or {}
        phases = [
            {
                "start_s": p.get("start_s"),
                "end_s": p.get("end_s"),
                "phase_id": p.get("phase_id") or p.get("id"),
                "instruction": (p.get("instruction") or "")[:40],
            }
            for p in (timeline if isinstance(timeline, list) else (timeline.get("phases") or []))
        ]
        rows.append({
            "recording_id": rec_id,
            "label": audit.label,
            "folder": meta_path.parent.name,
            "schema_version": meta.get("schema_version"),
            "status": meta.get("status"),
            "eligible": audit.eligible,
            "reasons": audit.reasons,
            "frame_count": meta.get("frame_count"),
            "actual_duration_s": meta.get("actual_duration_s"),
            "batch_id": batch.get("batch_id"),
            "take": batch.get("take"),
            "take_count": batch.get("take_count"),
            "gap_before_s": recording_node.get("gap_before_s"),
            "subject_id": meta.get("subject_id"),
            "pre_action": activity.get("pre_action"),
            "post_action": activity.get("post_action"),
            "phases": phases,
            "annotations": meta.get("annotations"),
            "feature_windows": windows,
            "lltf_width": width,
            "layout": layout,
            "audio_cue_mode": (meta.get("audio_cues") or {}).get("mode"),
            "clock_source": (meta.get("clock_anchor") or {}).get("source"),
        })

    by_label = defaultdict(lambda: {"takes": 0, "windows": 0, "frames": 0, "batches": set(), "schema": set()})
    for r in rows:
        cell = by_label[r["label"]]
        cell["takes"] += 1
        cell["windows"] += r["feature_windows"]
        cell["frames"] += int(r["frame_count"] or 0)
        cell["batches"].add(r["batch_id"])
        cell["schema"].add(r["schema_version"])

    print(f"{'label':16s} {'takes':>5s} {'frames':>7s} {'windows':>8s} {'batches':>8s}  schema  eligible")
    total = {"takes": 0, "windows": 0}
    for label in sorted(by_label):
        cell = by_label[label]
        elig = sum(1 for r in rows if r["label"] == label and r["eligible"])
        print(
            f"{label:16s} {cell['takes']:5d} {cell['frames']:7d} {cell['windows']:8d} "
            f"{len(cell['batches']):8d}  {','.join(str(s) for s in sorted(cell['schema'])):6s}  {elig}/{cell['takes']}"
        )
        total["takes"] += cell["takes"]
        total["windows"] += cell["windows"]
    print(f"{'TOTAL':16s} {total['takes']:5d} {'':7s} {total['windows']:8d}")

    # take-numbering audit: duplicate (label, take) across batches
    per_key = defaultdict(list)
    for r in rows:
        if r["take"] is not None:
            per_key[(r["label"], r["take"])].append(r["batch_id"])
    dup = {k: v for k, v in per_key.items() if len(v) > 1}
    print("\nDuplikat (label, take) antar-batch:", json.dumps(
        {f"{k[0]}#{k[1]}": v for k, v in sorted(dup.items())}, indent=1))

    # gaps in take numbering per (batch,label)
    print("\nCek nomor take per batch:")
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["batch_id"], r["label"])].append(r["take"])
    for key, takes in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        takes = sorted(t for t in takes if t is not None)
        expected = list(range(1, max(takes) + 1)) if takes else []
        missing = sorted(set(expected) - set(takes))
        dupn = sorted({t for t in takes if takes.count(t) > 1})
        if missing or dupn:
            print(f"  {key}: takes={takes} missing={missing} dup={dupn}")

    out = Path(__file__).resolve().parents[1] / "dataset_audit.json"
    out.write_text(json.dumps({"rows": rows, "summary": {
        k: {**v, "batches": sorted(str(b) for b in v["batches"]), "schema": sorted(v["schema"])}
        for k, v in by_label.items()}}, indent=1, default=str), encoding="utf-8")
    print(f"\nJSON: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
