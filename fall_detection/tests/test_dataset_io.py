#!/usr/bin/env python3
"""Tests for the model-agnostic CSI dataset reader."""

from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from fall_detection.dataset_io import (
    _FRAMES_COLUMNS,
    amplitude,
    component_pairs,
    decode_iq,
    leading_invalid_pairs,
    load_recording,
    ltf_sections,
    to_feature_matrix,
    to_observation_sequence,
    to_time_series_tensor,
)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii") if data else ""


def _row(**overrides) -> dict[str, str]:
    """A frames.csv row with every column defaulted to 'na'."""
    row = {column: "na" for column in _FRAMES_COLUMNS}
    row.update({key: str(value) for key, value in overrides.items()})
    return row


def _write_v2(
    root: Path,
    rec_id: str,
    label: str,
    rows: list[dict[str, str]],
    *,
    meta_extra: dict | None = None,
    events: dict | None = None,
) -> Path:
    folder = root / label
    folder.mkdir(parents=True, exist_ok=True)
    header = ",".join(_FRAMES_COLUMNS)
    lines = [header] + [",".join(row[col] for col in _FRAMES_COLUMNS) for row in rows]
    (folder / f"{rec_id}.frames.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {
        "id": rec_id,
        "label": label,
        "schema_version": 2,
        "frames": len(rows),
        "complete": True,
        "session_id": "batch_1",
        "trial_id": rec_id,
        "started_at_utc": "2026-10-27T05:00:00.000Z",
        "ended_at_utc": "2026-10-27T05:00:05.000Z",
    }
    meta.update(meta_extra or {})
    (folder / f"{rec_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if events is not None:
        (folder / f"{rec_id}.events.json").write_text(json.dumps(events), encoding="utf-8")
    return folder


def _write_v1(root: Path, rec_id: str, label: str, data_rows: list[list[int]]) -> Path:
    folder = root / label
    folder.mkdir(parents=True, exist_ok=True)
    header = ("type,sequence,timestamp,taget_seq,target,mac,rssi,rate,sig_mode,mcs,"
              "bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,"
              "noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,"
              "sig_len,rx_state,agc_gain,fft_gain,len,first_word,data")
    lines = [header]
    for i, values in enumerate(data_rows):
        cols = ["CSI_DATA", str(i), str(1000 + i), "1", label, "aa:bb:cc:dd:ee:ff",
                "-60", "11", "1", "7", "0", "0", "0", "0", "0", "0", "0", "-97",
                "0", "6", "0", str(900 + i), "0", "0", "0", "0", "0", str(len(values)),
                "0", '"' + ",".join(str(v) for v in values) + '"']
        lines.append(",".join(cols))
    (folder / f"{rec_id}.csi_data.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {"id": rec_id, "label": label, "frames": len(data_rows), "subcarriers": 2,
            "complete": True}
    (folder / f"{rec_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return folder


def _write_v3(
    root: Path,
    rec_id: str,
    label: str,
    rows: list[dict[str, str]],
    *,
    meta_extra: dict | None = None,
) -> Path:
    """A v3 two-file take: frames.csv + meta.json (events nested in meta)."""
    folder = root / label
    folder.mkdir(parents=True, exist_ok=True)
    header = ",".join(_FRAMES_COLUMNS)
    lines = [header] + [",".join(row[col] for col in _FRAMES_COLUMNS) for row in rows]
    (folder / f"{rec_id}.frames.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {
        "schema_version": 3,
        "recording_id": rec_id,
        "activity_label": label,
        "target_duration_s": 10,
        "status": "complete",
        "started_at_utc": "2026-10-30T00:00:00.000Z",
        "ended_at_utc": "2026-10-30T00:00:10.000Z",
        "recording": {"frames": len(rows), "dropped": 0, "complete": True},
        "batch": {"batch_id": "batch_v3"},
        "annotations": {"fall_start": None, "fall_impact": None, "annotation_complete": False},
        "events": {
            "segments": [{
                "type": "activity_segment", "label": label, "binary_label": "fall",
                "start_offset_s": 0, "end_offset_s": 10, "source": "recorder_session",
            }],
            "motion_samples": [],
        },
        "files": {"frames_csv": f"{rec_id}.frames.csv", "meta_json": f"{rec_id}.meta.json"},
    }
    meta.update(meta_extra or {})
    (folder / f"{rec_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return folder


class DecodeTests(unittest.TestCase):
    def test_int8_imag_first(self):
        # ESP-IDF v5.5.3: imaginary byte precedes real byte per sub-carrier.
        pairs = decode_iq(bytes([10, 20, 30, 40]), 0)
        self.assertEqual(pairs, [(10, 20), (30, 40)])

    def test_int8_signed(self):
        pairs = decode_iq(bytes([0xFF, 0x80]), 0)  # -1, -128
        self.assertEqual(pairs, [(-1, -128)])

    def test_int16_little_endian(self):
        payload = (1).to_bytes(2, "little", signed=True) + (-2).to_bytes(2, "little", signed=True)
        pairs = decode_iq(payload, 1)
        self.assertEqual(pairs, [(1, -2)])

    def test_partial_trailing_sample_dropped(self):
        pairs = decode_iq(bytes([1, 2, 3]), 0)
        self.assertEqual(pairs, [(1, 2)])

    def test_amplitude_uses_real_and_imag(self):
        amp = amplitude([(3, 4)])
        self.assertAlmostEqual(amp[0], 5.0)

    def test_leading_invalid_pairs_by_data_type(self):
        # ESP-IDF: first_word_invalid corrupts the first four bytes of the
        # driver buffer; the count is valid for raw_payload-derived pairs.
        self.assertEqual(leading_invalid_pairs(True, 0), 2)   # int8: 2 pairs
        self.assertEqual(leading_invalid_pairs(True, 1), 1)   # int16: 1 pair
        self.assertEqual(leading_invalid_pairs(False, 0), 0)
        self.assertEqual(leading_invalid_pairs(None, 0), 0)


class LoadV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_raw_payload_preserved_verbatim(self):
        raw = bytes(range(6))
        valid = bytes([1, 2, 3, 4])
        _write_v2(self.root, "r1", "duduk", [
            _row(recording_id="r1", frame_sequence=0, raw_len=6, valid_len=4,
                 lltf_len=4, data_type=0, callback_timestamp_us=1000,
                 raw_b64=_b64(raw), valid_b64=_b64(valid), payload_ok="true"),
        ])
        rec = load_recording(self.root, "r1")
        self.assertEqual(rec.schema_version, 2)
        self.assertEqual(rec.session_id, "batch_1")
        self.assertEqual(rec.trial_id, "r1")
        frame = rec.frames[0]
        self.assertEqual(frame.raw_payload, raw)
        self.assertEqual(frame.valid_payload, valid)
        self.assertEqual(frame.primary_payload(), raw)
        self.assertEqual(frame.callback_timestamp_us, 1000)

    def test_unavailable_fields_are_none(self):
        _write_v2(self.root, "r2", "kosong", [_row(recording_id="r2", frame_sequence=0)])
        rec = load_recording(self.root, "r2")
        frame = rec.frames[0]
        self.assertIsNone(frame.rx_seq)
        self.assertIsNone(frame.first_word_invalid)
        self.assertIsNone(frame.rssi)

    def test_ltf_sections_from_reported_lengths(self):
        valid = bytes(range(8))
        _write_v2(self.root, "r3", "berjalan", [
            _row(recording_id="r3", frame_sequence=0, valid_len=8, lltf_len=4,
                 ht_ltf_len=2, stbc_ht_ltf_len=2, data_type=0, valid_b64=_b64(valid)),
        ])
        rec = load_recording(self.root, "r3")
        frame = rec.frames[0]
        self.assertEqual(ltf_sections(frame),
                         {"lltf": (0, 4), "ht_ltf": (4, 6), "stbc_ht_ltf": (6, 8)})
        # LLTF component decodes only the first four bytes.
        self.assertEqual(component_pairs(frame, "lltf"), [(0, 1), (2, 3)])
        self.assertEqual(len(component_pairs(frame, "ht_ltf")), 1)

    def test_events_and_session_metadata(self):
        events = {
            "segments": [{"label": "jatuh", "start_offset_s": 1.0, "end_offset_s": 2.0,
                          "type": "fall", "source": "manual"}],
            "motion_samples": [{"ts_ms": 10}],
        }
        _write_v2(self.root, "r4", "jatuh", [_row(recording_id="r4", frame_sequence=0)],
                 meta_extra={"subject_id": "S01"}, events=events)
        rec = load_recording(self.root, "r4")
        self.assertEqual(rec.subject_id, "S01")
        self.assertEqual(len(rec.events), 1)
        self.assertEqual(rec.events[0].label, "jatuh")
        self.assertEqual(rec.events[0].event_type, "fall")
        self.assertEqual(rec.motion_samples, [{"ts_ms": 10}])


class LoadV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_csi_data_still_loads(self):
        _write_v1(self.root, "old1", "duduk", [[1, 2, 3, 4], [5, 6, 7, 8]])
        rec = load_recording(self.root, "old1")
        self.assertEqual(rec.schema_version, 1)
        self.assertEqual(len(rec.frames), 2)
        self.assertEqual(rec.frames[0].payload_source, "csi_data_csv")
        self.assertEqual(rec.frames[0].valid_payload, bytes([1, 2, 3, 4]))
        self.assertTrue(any("legacy" in w for w in rec.warnings))
        # No events file -> the recording label becomes a single segment.
        self.assertEqual(rec.events[0].label, "duduk")
        self.assertEqual(rec.events[0].source, "recording_label")


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # 30 LLTF-only frames of 52 complex pairs (104 bytes) each.
        rows = []
        for i in range(30):
            payload = bytes([(j + i) % 100 for j in range(104)])
            rows.append(_row(
                recording_id="big", frame_sequence=i, valid_len=104, lltf_len=104,
                data_type=0, sig_mode=0, bandwidth=0, stbc=0, secondary_channel=0,
                callback_timestamp_us=1000 + i * 10000, valid_b64=_b64(payload),
                payload_ok="true",
            ))
        _write_v2(self.root, "big", "berjalan", rows)
        self.rec = load_recording(self.root, "big")

    def tearDown(self):
        self.tmp.cleanup()

    def test_feature_matrix_baseline_shape(self):
        X, y, cfg = to_feature_matrix(self.rec)
        # 30 frames, window 24, stride 12 -> starts at 0 only -> 1 window.
        self.assertEqual(len(X), 1)
        self.assertEqual(len(X[0]), 16)
        self.assertEqual(y, ["berjalan"])
        self.assertEqual(cfg["family"],
                         ["logistic-regression", "linear-svm", "decision-tree", "random-forest"])
        self.assertEqual(cfg["window_frames"], 24)
        self.assertEqual(cfg["stride_frames"], 12)

    def test_time_series_tensor_shape(self):
        windows, labels, cfg = to_time_series_tensor(
            self.rec, representation="amplitude", window=24, stride=12)
        self.assertEqual(len(windows), 1)
        self.assertEqual(len(windows[0]), 52)   # channels
        self.assertEqual(len(windows[0][0]), 24)  # length
        self.assertEqual(cfg["shape"], [52, 24])
        self.assertIn("minirocket", cfg["family"])

    def test_time_series_tensor_iq_channels(self):
        windows, _, cfg = to_time_series_tensor(
            self.rec, representation="iq", window=24, stride=12, channels=[0, 1, 2, 3])
        self.assertEqual(len(windows[0]), 4)
        self.assertEqual(cfg["representation"], "iq")

    def test_observation_sequence_preserves_order_and_time(self):
        obs, ts, cfg = to_observation_sequence(self.rec)
        self.assertEqual(len(obs), 30)
        self.assertEqual(len(obs[0]), 52)
        self.assertEqual(ts[0], 1000)
        self.assertEqual(ts[1], 11000)
        self.assertEqual(cfg["family"], ["hmm", "dtw", "shapelet"])

    def test_adapters_do_not_mutate_frames(self):
        before = self.rec.frames[0].valid_payload
        to_feature_matrix(self.rec)
        to_time_series_tensor(self.rec)
        to_observation_sequence(self.rec)
        self.assertEqual(self.rec.frames[0].valid_payload, before)


class FirstWordInvalidTests(unittest.TestCase):
    """D: the flag is metadata; trimming is deferred until the payload
    mapping is audited. Adapters read esp-radar's compacted valid_data, whose
    leading pairs do not map onto the invalid first four bytes of buf, so no
    adapter may apply the drop."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        rows = []
        for i in range(30):
            payload = bytes([(j + i) % 100 for j in range(104)])  # 52 int8 pairs
            rows.append(_row(
                recording_id="fw", frame_sequence=i, valid_len=104, lltf_len=104,
                data_type=0, sig_mode=0, bandwidth=0, stbc=0, secondary_channel=0,
                first_word_invalid=True, callback_timestamp_us=1000 + i * 10000,
                valid_b64=_b64(payload), payload_ok="true",
            ))
        _write_v2(self.root, "fw", "berjalan", rows)
        self.rec = load_recording(self.root, "fw")

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_adapter_keeps_all_pairs(self):
        obs, _, cfg = to_observation_sequence(self.rec)
        self.assertEqual(len(obs[0]), 52)
        self.assertNotIn("drop_first_word", cfg)
        self.assertIn("first_word_invalid_handling", cfg)

    def test_adapters_reject_unverified_first_word_trim(self):
        # drop_first_word was removed from the valid-payload adapters: the
        # mapping of the invalid word into compacted valid_data is layout-
        # dependent and not yet proven, so the API must not invite it.
        with self.assertRaises(TypeError):
            to_observation_sequence(self.rec, drop_first_word=True)
        with self.assertRaises(TypeError):
            to_feature_matrix(self.rec, drop_first_word=True)
        with self.assertRaises(TypeError):
            to_time_series_tensor(self.rec, drop_first_word=True)

    def test_flagged_frames_are_not_trimmed(self):
        # first_word_invalid=true must not change extracted features: the
        # adapter output equals the untrimmed pair list, leading pairs kept.
        obs, _, _ = to_observation_sequence(self.rec)
        frame = self.rec.frames[0]
        self.assertTrue(frame.first_word_invalid)
        self.assertEqual(obs[0], amplitude(component_pairs(frame, "lltf")))
        self.assertEqual(len(obs[0]), 52)

    def test_baseline_feature_matrix_is_unchanged_by_default(self):
        X, _, cfg = to_feature_matrix(self.rec)
        self.assertEqual(len(X), 1)          # baseline still produces a window
        self.assertEqual(len(X[0]), 16)
        self.assertNotIn("drop_first_word", cfg)


class LoadV3Tests(unittest.TestCase):
    """v3 two-file takes: activity_label, embedded events, derived binary_label."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_v3_identity_and_binary_label(self):
        payload = bytes(range(104))
        _write_v3(self.root, "v3a", "fall_forward", [
            _row(recording_id="v3a", frame_sequence=0, valid_len=104, lltf_len=104,
                 data_type=0, callback_timestamp_us=1000, valid_b64=_b64(payload),
                 payload_ok="true"),
        ])
        rec = load_recording(self.root, "v3a")
        self.assertEqual(rec.schema_version, 3)
        self.assertEqual(rec.recording_id, "v3a")
        self.assertEqual(rec.label, "fall_forward")
        self.assertEqual(rec.binary_label, "fall")
        self.assertEqual(rec.status, "complete")
        self.assertEqual(rec.session_id, "batch_v3")
        self.assertEqual(rec.frames[0].payload_source, "frames_csv")

    def test_v3_events_come_from_meta_not_a_sidecar(self):
        _write_v3(self.root, "v3b", "fall_backward",
                  [_row(recording_id="v3b", frame_sequence=0)])
        rec = load_recording(self.root, "v3b")
        # No .events.json file exists; segments must come from meta.events.
        self.assertEqual(len(rec.events), 1)
        self.assertEqual(rec.events[0].label, "fall_backward")
        self.assertEqual(rec.events[0].end_offset_s, 10)
        self.assertEqual(rec.binary_label, "fall")

    def test_v3_annotations_exposed(self):
        _write_v3(self.root, "v3c", "walking", [_row(recording_id="v3c", frame_sequence=0)],
                  meta_extra={"annotations": {
                      "fall_start": None, "fall_impact": None, "annotation_complete": False}})
        rec = load_recording(self.root, "v3c")
        self.assertEqual(rec.binary_label, "non_fall")
        self.assertIsInstance(rec.annotations, dict)
        self.assertFalse(rec.annotations["annotation_complete"])


if __name__ == "__main__":
    unittest.main()
