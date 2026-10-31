#!/usr/bin/env python3
"""Prove the first_word_invalid-aware esp-radar compaction on a real recording.

Fixture derived from ``20261031T012305Z_walking_001.frames.csv`` frame 0
(ESP32, HT / 20 MHz / STBC / secondary NONE, int8, first_word_invalid=true,
raw_len 384, valid_len 328). The OLD firmware recorded ``valid_b64`` with the
invalid leading int8 pair still present: valid bytes 52-53 equal raw bytes 2-3
(``5d00``) -- the second half of the invalid first word. These tests port the
PATCHED ``copy_subcarrier_data`` (see esp-radar/src/esp_radar.c) faithfully to
Python and assert the corrected payload excludes raw bytes 0..3, keeps every
other sub-range intact, reflects the actual shortened length, and never touches
the raw buffer. They also confirm the normal ``first_word_invalid=false`` path
and a non-leaking layout are unaffected.
"""

from __future__ import annotations

import base64
import csv
import tempfile
import unittest
from pathlib import Path

from fall_detection.audit_dataset import FRAMES_HEADER
from fall_detection.train_activity_model import (
    CSI_SUBCARRIERS,
    extract_window_features,
    read_amplitude_frames_from_frames_csv,
)

RAW_HEX = (
    "de655d00f81dfb17011004080a010ffc15f61af11eee21ed20ef21ef1ff01bf1"
    "16f20ff407f3fff4f7f3f1f2edeeeaebe7e8e6e8e7e700000000000000000000"
    "0000000000000000000000001c001903160712070c070604ff00f8fcf3f7f0f0"
    "ecebebe6efe3f0e1f3e2f2e3f7e8f9edfcf6fffefe06ff0efd16fb1cfb21fa26"
    "ce00fa0ef80efa0bf80cf80bf709f608f508f509f409f507f406f305f404f203"
    "f205f202f302f202f3fff2fff3fdf4fdf4fdf4fcf4fcf5fbf6f9000000000000"
    "00000000000000000c050c060c060c070c070b0a0b0a0c0b0c0c0c0c0b0d090e"
    "080e070f070e060f050f050f030f030f020f030f020f010e0010fe0efd0efd0e"
    "ce0001150215041405160515071508140a140b140b150a150c130c130c140d14"
    "0d140d160d140d150d150b140a130b130a130a12091308130613000000000000"
    "0000000000000000f709f508f509f408f407f508f408f409f309f40af40cf409"
    "f20cf30cf50bf70bf60cf60df60df70ff90ffa0ffb0ffb10fc12fe12ff13fe16"
)
# OLD (unclamped) recorded valid payload: 328 bytes, first_word_invalid=true.
VAL_HEX = (
    "1c001903160712070c070604ff00f8fcf3f7f0f0ecebebe6efe3f0e1f3e2f2e3"
    "f7e8f9edfcf6fffefe06ff0efd16fb1cfb21fa265d00f81dfb17011004080a01"
    "0ffc15f61af11eee21ed20ef21ef1ff01bf116f20ff407f3fff4f7f3f1f2edee"
    "eaebe7e8e6e8e7e70c050c060c060c070c070b0a0b0a0c0b0c0c0c0c0b0d090e"
    "080e070f070e060f050f050f030f030f020f030f020f010e0010fe0efd0efd0e"
    "fa0ef80efa0bf80cf80bf709f608f508f509f409f507f406f305f404f203f205"
    "f202f302f202f3fff2fff3fdf4fdf4fdf4fcf4fcf5fbf6f90115021504140516"
    "0515071508140a140b140b150a150c130c130c140d140d140d160d140d150d15"
    "0b140a130b130a130a12091308130613f709f508f509f408f407f508f408f409"
    "f309f40af40cf409f20cf30cf50bf70bf60cf60df60df70ff90ffa0ffb0ffb10"
    "fc12fe12ff13fe16"
)

# ESP32 sub-carrier ranges (byte offsets into the raw driver buffer) exactly as
# in csi_sub_carrier_table.c for the fixture layout and a non-leaking one.
NONE_HT_STBC = {
    "lltf": [(76, 128), (2, 54)],
    "ht_ltf": [(200, 256), (130, 186)],
    "stbc_ht_ltf": [(258, 314), (328, 384)],
}
NONE_NON_HT = {"lltf": [(76, 128), (2, 54)]}
BELOW_NON_HT = {"lltf": [(12, 64), (66, 118)]}


def _compact(src: bytes, ranges: list[tuple[int, int]], first_word_invalid: bool):
    """Port of the patched esp-radar copy_subcarrier_data (int8 branch)."""
    out = bytearray()
    src_index: list[int] = []
    for start, stop in ranges:
        if first_word_invalid and start < 4:
            start = stop if stop <= 4 else 4
        if stop <= start:
            continue
        out += src[start:stop]
        src_index.extend(range(start, stop))
    return bytes(out), src_index


def _build_valid(src: bytes, row: dict, first_word_invalid: bool):
    parts = bytearray()
    idx_all: list[int] = []
    for field in ("lltf", "ht_ltf", "stbc_ht_ltf"):
        ranges = row.get(field)
        if not ranges:
            continue
        chunk, chunk_idx = _compact(src, ranges, first_word_invalid)
        parts += chunk
        idx_all.extend(chunk_idx)
    return bytes(parts), idx_all


def _frames_csv(path: Path, *, lltf_len: int, valid_bytes: bytes) -> None:
    idx = {name: i for i, name in enumerate(FRAMES_HEADER)}
    lines = [",".join(FRAMES_HEADER)]
    for frame_sequence in range(36):
        row = ["na"] * len(FRAMES_HEADER)
        row[idx["recording_id"]] = "fixture"
        row[idx["frame_sequence"]] = str(frame_sequence)
        row[idx["sig_mode"]] = "1"
        row[idx["bandwidth"]] = "0"
        row[idx["stbc"]] = "1"
        row[idx["secondary_channel"]] = "0"
        row[idx["data_type"]] = "0"
        row[idx["first_word_invalid"]] = "true"
        row[idx["lltf_len"]] = str(lltf_len)
        row[idx["valid_len"]] = str(len(valid_bytes))
        row[idx["valid_b64"]] = base64.b64encode(valid_bytes).decode("ascii")
        lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class CompactionTrueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = bytes.fromhex(RAW_HEX)
        self.old_valid = bytes.fromhex(VAL_HEX)

    def test_fixture_matches_recorded_old_payload(self):
        # The unclamped reference (first_word_invalid=false) must reproduce the
        # OLD recorded valid payload byte-for-byte -> faithful port, real leak.
        rebuilt, _ = _build_valid(self.raw, NONE_HT_STBC, False)
        self.assertEqual(rebuilt, self.old_valid)
        self.assertEqual(len(self.old_valid), 328)
        # The documented leak: valid pair 26 (bytes 52-53) == raw pair 1 (2-3).
        self.assertEqual(self.old_valid[52:54], self.raw[2:4])

    def test_true_excludes_raw_bytes_0_to_3(self):
        _, idx_all = _build_valid(self.raw, NONE_HT_STBC, True)
        self.assertEqual(set(idx_all) & {0, 1, 2, 3}, set())
        self.assertTrue(all(offset >= 4 for offset in idx_all))

    def test_true_drops_only_the_invalid_pair(self):
        fixed, _ = _build_valid(self.raw, NONE_HT_STBC, True)
        # Corrected payload == old payload with the two invalid bytes removed.
        self.assertEqual(fixed, self.old_valid[:52] + self.old_valid[54:])

    def test_true_all_other_pairs_match_source_mapping(self):
        fixed, _ = _build_valid(self.raw, NONE_HT_STBC, True)
        expected = (
            self.raw[76:128] + self.raw[4:54]
            + self.raw[200:256] + self.raw[130:186]
            + self.raw[258:314] + self.raw[328:384]
        )
        self.assertEqual(fixed, expected)

    def test_true_valid_len_matches_actual_shortened_length(self):
        fixed, _ = _build_valid(self.raw, NONE_HT_STBC, True)
        lltf_only, _ = _compact(self.raw, NONE_HT_STBC["lltf"], True)
        self.assertEqual(len(lltf_only), 102)   # 104 - 2 (one int8 pair)
        self.assertEqual(len(fixed), 326)       # 102 + 112 + 112

    def test_raw_buffer_is_never_modified(self):
        snapshot = bytes(self.raw)
        _build_valid(self.raw, NONE_HT_STBC, True)
        _build_valid(self.raw, NONE_HT_STBC, False)
        self.assertEqual(self.raw, snapshot)


class CompactionNormalAndNonLeakingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = bytes.fromhex(RAW_HEX)

    def test_false_keeps_normal_path_unchanged(self):
        # first_word_invalid=false must NOT trim: full 52-pair LLTF retained.
        normal, idx_all = _build_valid(self.raw, NONE_HT_STBC, False)
        self.assertEqual(len(normal), 328)
        self.assertEqual(normal, bytes.fromhex(VAL_HEX))
        self.assertIn(2, idx_all)   # raw pair 1 (bytes 2-3) is valid here

    def test_non_leaking_layout_unaffected_by_flag(self):
        # BELOW/ABOVE LLTF ranges start at byte 12; clamp is a no-op even true.
        with_true, _ = _build_valid(self.raw, BELOW_NON_HT, True)
        with_false, _ = _build_valid(self.raw, BELOW_NON_HT, False)
        self.assertEqual(with_true, with_false)
        self.assertEqual(len(with_true), 104)


class ReaderFollowsLltfLenTests(unittest.TestCase):
    def test_reader_uses_lltf_len_not_fixed_52(self):
        import math
        raw = bytes.fromhex(RAW_HEX)
        fixed, _ = _build_valid(raw, NONE_HT_STBC, True)  # 326 bytes, LLTF=102

        def signed(value: int) -> int:
            return value - 256 if value > 127 else value

        expected0 = math.hypot(signed(fixed[0]), signed(fixed[1]))
        with tempfile.TemporaryDirectory() as tmp:
            frames_path = Path(tmp) / "fixture.frames.csv"
            _frames_csv(frames_path, lltf_len=102, valid_bytes=fixed)
            frames = read_amplitude_frames_from_frames_csv(frames_path)
        self.assertEqual(len(frames), 36)
        for frame in frames:
            self.assertEqual(len(frame), 51)   # 102 / 2, not 52 (no HT bleed)
            self.assertAlmostEqual(frame[0], expected0)

    def test_reader_still_handles_full_104_lltf(self):
        raw = bytes.fromhex(RAW_HEX)
        normal, _ = _build_valid(raw, NONE_HT_STBC, False)  # 328 bytes, LLTF=104
        with tempfile.TemporaryDirectory() as tmp:
            frames_path = Path(tmp) / "fixture.frames.csv"
            _frames_csv(frames_path, lltf_len=104, valid_bytes=normal)
            frames = read_amplitude_frames_from_frames_csv(frames_path)
        self.assertEqual(len(frames), 36)
        self.assertTrue(all(len(frame) == CSI_SUBCARRIERS for frame in frames))


class ExtractWindowWidthTests(unittest.TestCase):
    def test_width51_and_width52_both_yield_16_features(self):
        for width in (51, 52):
            frames = [[float(s) for s in range(width)] for _ in range(40)]
            features = extract_window_features(frames)
            self.assertTrue(features)
            self.assertTrue(all(len(row) == 16 for row in features))

    def test_mixed_width_within_recording_raises(self):
        frames = [[0.0] * 51, [0.0] * 52, [0.0] * 51]
        with self.assertRaises(ValueError):
            extract_window_features(frames)


if __name__ == "__main__":
    unittest.main()
