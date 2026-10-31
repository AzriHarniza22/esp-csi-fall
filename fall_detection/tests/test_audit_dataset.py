#!/usr/bin/env python3
"""Tests for the offline CSI dataset audit."""

from __future__ import annotations

import base64
import csv
import json
import tempfile
import unittest
from pathlib import Path

from fall_detection.audit_dataset import FRAMES_HEADER, audit_dataset, audit_take


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii") if data else ""


def write_v3_take(
    root: Path,
    *,
    take_id: str = "fall_001",
    label: str = "fall_forward",
    rows: int = 3,
    complete: bool = True,
    status: str = "complete",
    meta_frames: int | None = None,
    write_frames: bool = True,
) -> Path:
    """A v3 two-file take: frames.csv (32 cols) + meta.json."""
    take_dir = root / label
    take_dir.mkdir(parents=True, exist_ok=True)
    idx = {name: i for i, name in enumerate(FRAMES_HEADER)}
    payload = bytes([3, 4] * 52)  # 104 bytes -> 52 int8 pairs, amplitude 5.0
    lines = [",".join(FRAMES_HEADER)]
    for i in range(rows):
        row = ["na"] * len(FRAMES_HEADER)
        row[idx["recording_id"]] = take_id
        row[idx["frame_sequence"]] = str(i)
        row[idx["sig_mode"]] = "0"
        row[idx["bandwidth"]] = "0"
        row[idx["stbc"]] = "0"
        row[idx["secondary_channel"]] = "0"
        row[idx["data_type"]] = "0"
        row[idx["valid_len"]] = "104"
        row[idx["valid_b64"]] = _b64(payload)
        row[idx["raw_b64"]] = ""  # absent payload is empty, never 'na'
        lines.append(",".join(row))
    meta_path = take_dir / f"{take_id}.meta.json"
    meta_path.write_text(
        json.dumps({
            "schema_version": 3,
            "recording_id": take_id,
            "activity_label": label,
            "status": status,
            "recording": {
                "frames": rows if meta_frames is None else meta_frames,
                "complete": complete,
            },
        }),
        encoding="utf-8",
    )
    if write_frames:
        (take_dir / f"{take_id}.frames.csv").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    return meta_path


def write_take(
    root: Path,
    *,
    take_id: str = "take_001",
    label: str = "normal",
    complete: bool = True,
    rows: int = 2,
    subcarriers: int = 2,
) -> Path:
    take_dir = root / label
    take_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "id": take_id,
        "label": label,
        "frames": rows,
        "subcarriers": subcarriers,
        "complete": complete,
    }
    meta_path = take_dir / f"{take_id}.meta.json"
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")

    header = ["timestamp_us", "seq", "mac", "rssi", "data_type", "dropped"]
    for index in range(subcarriers):
        header.extend((f"sc{index:03d}_i", f"sc{index:03d}_q"))
    with (take_dir / f"{take_id}.iq.csv").open(
        "w", encoding="utf-8", newline=""
    ) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        for frame in range(rows):
            writer.writerow(
                [100 + frame, frame + 1, "aa:bb:cc:dd:ee:ff", -60, 0, 0]
                + [frame, -frame] * subcarriers
            )
    return meta_path


class AuditTakeTests(unittest.TestCase):
    def test_accepts_complete_take_with_matching_iq_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = write_take(Path(tmp))

            result = audit_take(meta_path)

        self.assertTrue(result.eligible, result.reasons)
        self.assertEqual(result.frames, 2)
        self.assertEqual(result.subcarriers, 2)
        self.assertEqual(result.label, "normal")

    def test_excludes_incomplete_take(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = write_take(Path(tmp), complete=False)

            result = audit_take(meta_path)

        self.assertFalse(result.eligible)
        self.assertIn("Metadata does not mark this take complete.", result.reasons)

    def test_excludes_row_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = write_take(Path(tmp), rows=1)
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            metadata["frames"] = 2
            meta_path.write_text(json.dumps(metadata), encoding="utf-8")

            result = audit_take(meta_path)

        self.assertFalse(result.eligible)
        self.assertTrue(any("data rows" in reason for reason in result.reasons))

    def test_dataset_reports_only_eligible_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recordings = Path(tmp)
            write_take(recordings, take_id="normal_001", label="normal")
            write_take(
                recordings,
                take_id="fall_001",
                label="fall",
                complete=False,
            )

            takes, errors = audit_dataset(recordings)

        self.assertEqual(errors, [])
        self.assertEqual(len(takes), 2)
        self.assertEqual(
            {take.label for take in takes if take.eligible},
            {"normal"},
        )


class AuditV3Tests(unittest.TestCase):
    def test_v3_frames_take_is_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = write_v3_take(Path(tmp), rows=4)
            result = audit_take(meta_path)
        self.assertTrue(result.eligible, result.reasons)
        self.assertEqual(result.frames, 4)
        self.assertEqual(result.subcarriers, 52)
        self.assertEqual(result.label, "fall_forward")

    def test_v3_missing_frames_csv_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = write_v3_take(Path(tmp), write_frames=False)
            result = audit_take(meta_path)
        self.assertFalse(result.eligible)
        self.assertTrue(any("Missing frames CSV" in r for r in result.reasons))

    def test_v3_row_count_mismatch_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = write_v3_take(Path(tmp), rows=2, meta_frames=5)
            result = audit_take(meta_path)
        self.assertFalse(result.eligible)
        self.assertTrue(any("data rows" in r for r in result.reasons))

    def test_v3_non_complete_status_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = write_v3_take(Path(tmp), status="stopped_early")
            result = audit_take(meta_path)
        self.assertFalse(result.eligible)
        self.assertTrue(any("status" in r for r in result.reasons))

    def test_v3_dataset_groups_by_activity_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recordings = Path(tmp)
            write_v3_take(recordings, take_id="fall_001", label="fall_forward")
            write_v3_take(recordings, take_id="walk_001", label="walking")
            takes, errors = audit_dataset(recordings)
        self.assertEqual(errors, [])
        self.assertEqual({t.label for t in takes if t.eligible}, {"fall_forward", "walking"})


if __name__ == "__main__":
    unittest.main()
