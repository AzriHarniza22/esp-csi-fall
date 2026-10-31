#!/usr/bin/env python3
"""Tests for CSI recording quality/integrity validation."""

from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from fall_detection.dataset_io import _FRAMES_COLUMNS
from fall_detection.validate_recording import (
    INVALID,
    VALID,
    WARNING,
    load_recording,
    validate_recording,
)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii") if data else ""


def _row(**overrides) -> dict[str, str]:
    row = {column: "na" for column in _FRAMES_COLUMNS}
    row.update({key: str(value) for key, value in overrides.items()})
    return row


def _write(root: Path, rec_id: str, label: str, rows: list[dict[str, str]], meta_extra: dict) -> None:
    folder = root / label
    folder.mkdir(parents=True, exist_ok=True)
    header = ",".join(_FRAMES_COLUMNS)
    lines = [header] + [",".join(r[c] for c in _FRAMES_COLUMNS) for r in rows]
    (folder / f"{rec_id}.frames.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {"id": rec_id, "label": label, "schema_version": 2, "frames": len(rows),
            "complete": True, "session_id": "batch_1"}
    meta.update(meta_extra)
    (folder / f"{rec_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _good_rows(n: int, start_us: int = 1000, step_us: int = 10000) -> list[dict[str, str]]:
    payload = bytes(range(104))
    return [
        _row(recording_id="r", frame_sequence=i, valid_len=104, lltf_len=104, data_type=0,
             mac="aa:bb:cc:dd:ee:ff", callback_timestamp_us=start_us + i * step_us,
             seq=i, valid_b64=_b64(payload), payload_ok="true")
        for i in range(n)
    ]


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, rec_id: str) -> dict:
        return validate_recording(load_recording(self.root, rec_id))

    def test_clean_recording_is_valid(self):
        _write(self.root, "r", "duduk", _good_rows(10), {})
        report = self._report("r")
        self.assertEqual(report["status"], VALID)
        self.assertEqual(report["frames"], 10)
        self.assertEqual(report["timestamps"]["stamped_frames"], 10)

    def test_cross_clock_delta_reported_not_as_latency(self):
        rows = _good_rows(10)
        for r in rows:
            r["rx_ctrl_timestamp_us"] = str(int(r["callback_timestamp_us"]) - 160_000)
        _write(self.root, "r", "duduk", rows, {})
        report = self._report("r")
        cc = report["timestamps"]["cross_clock_delta"]
        self.assertEqual(cc["pairs"], 10)
        self.assertAlmostEqual(cc["median_us"], 160_000)
        self.assertIn("not processing latency", cc["interpretation"])

    def test_first_word_invalid_warns(self):
        rows = _good_rows(4)
        for r in rows:
            r["first_word_invalid"] = "true"
        _write(self.root, "r", "duduk", rows, {})
        report = self._report("r")
        self.assertEqual(report["status"], WARNING)
        self.assertEqual(report["distribution"]["first_word_invalid_frames"], 4)
        self.assertTrue(any("first_word_invalid" in w for w in report["warnings"]))

    def test_frame_count_mismatch_is_invalid(self):
        _write(self.root, "r", "duduk", _good_rows(5), {"frames": 9})
        report = self._report("r")
        self.assertEqual(report["status"], INVALID)
        self.assertTrue(any("frames" in r for r in report["reasons"]))

    def test_incomplete_recording_is_invalid(self):
        _write(self.root, "r", "duduk", _good_rows(5), {"complete": False})
        report = self._report("r")
        self.assertEqual(report["status"], INVALID)
        self.assertTrue(any("incomplete" in r for r in report["reasons"]))

    def test_payload_length_mismatch_is_invalid(self):
        rows = _good_rows(3)
        rows[1]["valid_len"] = "999"          # disagrees with decoded bytes
        rows[1]["payload_ok"] = "false"
        _write(self.root, "r", "duduk", rows, {})
        report = self._report("r")
        self.assertEqual(report["status"], INVALID)
        self.assertGreaterEqual(report["payload_integrity"]["length_or_flag_mismatches"], 1)

    def test_backward_and_duplicate_timestamps_warn(self):
        rows = _good_rows(4)
        rows[2]["callback_timestamp_us"] = "500"   # backward
        rows[3]["callback_timestamp_us"] = "500"   # duplicate
        _write(self.root, "r", "duduk", rows, {})
        report = self._report("r")
        self.assertEqual(report["status"], WARNING)
        self.assertEqual(report["timestamps"]["backward_timestamps"], 1)
        self.assertEqual(report["timestamps"]["duplicate_timestamps"], 1)

    def test_large_gap_warns_with_relative_threshold(self):
        rows = _good_rows(4)
        rows[3]["callback_timestamp_us"] = str(1000 + 3 * 10000 + 10_000_000)
        _write(self.root, "r", "duduk", rows, {})
        report = self._report("r")
        self.assertEqual(report["status"], WARNING)
        self.assertGreaterEqual(report["timestamps"]["large_gaps"], 1)

    def test_dropped_frames_warn(self):
        _write(self.root, "r", "duduk", _good_rows(4), {"dropped_delta": 3})
        report = self._report("r")
        self.assertEqual(report["status"], WARNING)
        self.assertTrue(any("dropped" in w for w in report["warnings"]))

    def test_mixed_mac_warns(self):
        rows = _good_rows(4)
        rows[2]["mac"] = "11:22:33:44:55:66"
        _write(self.root, "r", "duduk", rows, {})
        report = self._report("r")
        self.assertEqual(report["status"], WARNING)
        self.assertEqual(len(report["distribution"]["macs"]), 2)

    def test_missing_session_warns(self):
        rows = _good_rows(3)
        _write(self.root, "r", "duduk", rows, {"session_id": None})
        # session_id None is dropped by dict.update -> meta lacks the key.
        report = self._report("r")
        self.assertIn(report["status"], (WARNING, VALID))
        self.assertTrue(any("session" in w for w in report["warnings"]))

    def test_v3_reads_recording_node_and_flags_status(self):
        # v3 nests counts under meta["recording"], derives binary_label from
        # activity_label, groups by batch.batch_id, and adds a lifecycle status.
        _write(self.root, "r", "fall_forward", _good_rows(6), {
            "schema_version": 3,
            "activity_label": "fall_forward",
            "recording": {"frames": 6, "dropped": 0, "complete": True},
            "status": "stopped_early",
            "frames": None,       # nested node must win over the top level
            "complete": None,
            "session_id": None,
            "batch": {"batch_id": "batch_v3"},
        })
        report = self._report("r")
        self.assertEqual(report["binary_label"], "fall")
        self.assertEqual(report["session_id"], "batch_v3")
        self.assertEqual(report["frames"], 6)
        # A non-complete lifecycle status is surfaced as a warning, not silent.
        self.assertTrue(any("stopped_early" in w for w in report["warnings"]))
        # Nested complete=True means no "incomplete" INVALID reason is raised.
        self.assertFalse(any("incomplete" in r for r in report["reasons"]))


if __name__ == "__main__":
    unittest.main()
