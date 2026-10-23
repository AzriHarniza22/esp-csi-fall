#!/usr/bin/env python3
"""Tests for the offline CSI dataset audit."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from fall_detection.audit_dataset import audit_dataset, audit_take


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


if __name__ == "__main__":
    unittest.main()
