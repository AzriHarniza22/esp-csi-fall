#!/usr/bin/env python3
"""Path sanitisation, atomic two-file write, GET/DELETE API without a device.

Covers the v3 storage contract (docs/recording-pipeline-implementation.md §3,
§5, §16): a POST stores exactly ``<id>.frames.csv`` + ``<id>.meta.json``, is
validated before anything is written, and rejects the discontinued v1/v2
payload fields.
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import csi_recorder_server as srv  # noqa: E402

LEGACY_SUFFIXES = (".csi_data.csv", ".iq.csv", ".raw_iq.csv", ".events.json")


def _b64(n: int, seed: int) -> str:
    return base64.b64encode(bytes((seed + i) & 0xFF for i in range(n))).decode()


def make_frames_csv(rec_id: str, n_frames: int, raw_len: int = 128, valid_len: int = 104) -> str:
    lines = [",".join(srv.FRAMES_HEADER)]
    for i in range(n_frames):
        row = {
            "recording_id": rec_id,
            "frame_sequence": str(i),
            "seq": str(i),
            "rx_seq": str(i),
            "mac": "aa:bb:cc:dd:ee:ff",
            "dmac": "11:22:33:44:55:66",
            "rssi": "-60",
            "noise_floor": "-90",
            "channel": "1",
            "secondary_channel": "0",
            "sig_mode": "0",
            "mcs": "0",
            "rate": "0",
            "bandwidth": "0",
            "stbc": "0",
            "data_type": "0",
            "raw_len": str(raw_len),
            "valid_len": str(valid_len),
            "lltf_len": str(valid_len),
            "ht_ltf_len": "0",
            "stbc_ht_ltf_len": "0",
            "first_word_invalid": "false",
            "agc_gain": "0",
            "fft_gain": "0",
            "rx_gain_compensation": "0",
            "callback_timestamp_us": str(1000 + i * 1000),
            "rx_ctrl_timestamp_us": str(900 + i * 1000),
            "host_receive_monotonic_ns": str(5_000_000 + i * 1_000_000),
            "dropped": "0",
            "payload_ok": "true",
            "raw_b64": _b64(raw_len, i),
            "valid_b64": _b64(valid_len, i),
        }
        lines.append(",".join(row[col] for col in srv.FRAMES_HEADER))
    return "\n".join(lines) + "\n"


def make_meta(rec_id: str, label: str, n_frames: int, **over) -> dict:
    meta = {
        "schema_version": 3,
        "recording_id": rec_id,
        "activity_label": label,
        "started_at_utc": "2026-10-30T00:00:00Z",
        "target_duration_s": 10,
        "actual_duration_s": 10.0,
        "status": "complete",
        "recording": {"frames": n_frames, "dropped": 0, "complete": True},
        "files": {
            "frames_csv": f"{rec_id}.frames.csv",
            "meta_json": f"{rec_id}.meta.json",
        },
    }
    meta.update(over)
    return meta


class SafeJoinTests(unittest.TestCase):
    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fall_forward").mkdir()
            with self.assertRaises(ValueError):
                srv.safe_join(root, "..", "etc", "passwd")
            with self.assertRaises(ValueError):
                srv.safe_join(root, "fall_forward", "..", "..", "secret")


class ValidateTests(unittest.TestCase):
    def test_frames_header_is_32_columns(self):
        self.assertEqual(len(srv.FRAMES_HEADER), 32)

    def test_valid_frames_and_meta_pass(self):
        rec_id = "20261030T000000Z_fall_forward_001"
        frames = make_frames_csv(rec_id, 3)
        meta = make_meta(rec_id, "fall_forward", 3)
        self.assertEqual(srv.validate_frames_csv(frames, meta), [])
        self.assertEqual(srv.validate_meta(meta, rec_id), [])

    def test_meta_rejects_legacy_payload_semantics(self):
        rec_id = "20261030T000000Z_walking_001"
        meta = make_meta(
            rec_id, "walking", 1,
            payload_semantics={"legacy_iq_csv": "x"},
        )
        errors = srv.validate_meta(meta, rec_id)
        self.assertTrue(any("legacy_iq_csv" in e for e in errors))


class HttpApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.recordings = Path(self.tmp.name)
        handler = srv.make_handler(self.recordings)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def _json(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read().decode("utf-8"))
            return exc.code, payload

    def test_post_writes_exactly_two_files(self):
        rec_id = "20261030T000000Z_fall_forward_001"
        status, payload = self._json(
            "POST",
            "/api/recordings",
            {
                "id": rec_id,
                "frames_csv": make_frames_csv(rec_id, 4),
                "meta": make_meta(rec_id, "fall_forward", 4),
            },
        )
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["ok"])
        folder = self.recordings / "fall_forward"
        self.assertTrue((folder / f"{rec_id}.frames.csv").is_file())
        self.assertTrue((folder / f"{rec_id}.meta.json").is_file())
        for suffix in LEGACY_SUFFIXES:
            self.assertFalse(
                (folder / f"{rec_id}{suffix}").exists(),
                f"v3 must not create {suffix}",
            )
        # index.csv carries the binary mapping derived from activity_label.
        index = (self.recordings / "index.csv").read_text(encoding="utf-8")
        self.assertIn("fall_forward", index)
        self.assertIn("fall", index)

    def test_post_persists_diagnostic_events_in_meta(self):
        """Prioritas 1: meta.events.ping/csi_diag + session_stats + boundary
        round-trip through the server while the take still stores exactly two
        files (frames.csv + meta.json)."""
        rec_id = "20261101T000000Z_walking_001"
        diag_meta = make_meta(
            rec_id, "walking", 3,
            events={
                "segments": [],
                "motion_samples": [],
                "ping": {
                    "columns": ["type", "ds", "ts_delta_us", "seqno", "seqno_valid",
                                "timegap_ms", "ttl", "recv_size", "transmitted", "received"],
                    "ts_base_us": 1000, "ts_unit": "us", "ts_monotonic": "esp_timer",
                    "type_enum": {"success": 1, "timeout": 2},
                    "rows": [[1, 7001, 0, 7, 1, 3, 64, 29, 1, 1],
                             [2, 7002, 10000, 8, 1, None, None, None, 1, 0]],
                },
                "csi_diag": {
                    "columns": ["cb", "ds", "ts_delta_us", "mac", "dmac", "rx_seq",
                                "sig_mode", "mcs", "rssi", "bandwidth", "stbc",
                                "payload_len", "firmware_seq", "drop_reason"],
                    "ts_base_us": 1000, "mac_format": "12-hex lowercase, no colons",
                    "drop_reason_enum": {"throttle": 0, "tx_lock_timeout": 1,
                                         "oversized": 2, "base64_fail": 3,
                                         "uart_write_fail": 4},
                    "rows": [[1, 7101, 0, "f8731a5923f4", "3c22fbe1a2b4", 512, 0, 7,
                              -59, 0, 0, 128, None, 0],
                             [1, 7102, 900, "f8731a5923f4", "3c22fbe1a2b4", 513, 0, 7,
                              -60, 0, 0, 128, 55, 2]],
                },
            },
            session_stats={"success_callback_count": 1, "timeout_callback_count": 1,
                           "truncated": False},
            boundary={"epoch": 5, "flush_generation": 1, "confirmed": True,
                      "status": "confirmed"},
        )
        status, payload = self._json(
            "POST", "/api/recordings",
            {"id": rec_id, "frames_csv": make_frames_csv(rec_id, 3), "meta": diag_meta},
        )
        self.assertEqual(status, 200, payload)
        folder = self.recordings / "walking"
        self.assertTrue((folder / f"{rec_id}.frames.csv").is_file())
        self.assertTrue((folder / f"{rec_id}.meta.json").is_file())
        for suffix in LEGACY_SUFFIXES:
            self.assertFalse((folder / f"{rec_id}{suffix}").exists())
        status, one = self._json("GET", f"/api/recordings/{rec_id}")
        self.assertEqual(status, 200)
        self.assertEqual(one["events"]["ping"]["rows"][1][0], 2)  # timeout enum preserved
        self.assertIsNone(one["events"]["ping"]["rows"][1][5])    # null preserved on round-trip
        # Fallback csi_diag rows keep firmware_seq/drop_reason through the server.
        self.assertEqual(one["events"]["csi_diag"]["rows"][1][12], 55)
        self.assertEqual(one["events"]["csi_diag"]["rows"][1][13], 2)
        self.assertEqual(one["events"]["csi_diag"]["drop_reason_enum"]["uart_write_fail"], 4)
        self.assertEqual(one["boundary"]["status"], "confirmed")
        self.assertEqual(one["session_stats"]["timeout_callback_count"], 1)

    def test_post_persists_degraded_and_staged_meta(self):
        """Final audit: degraded diagnostics (streams null, reason kept) and
        the staged loss_accounting round-trip; null must never be rewritten
        as 0 by the server."""
        rec_id = "20261101T000100Z_walking_002"
        degraded_meta = make_meta(
            rec_id, "walking", 2,
            events={"segments": [], "motion_samples": [], "ping": None, "csi_diag": None},
            session_stats={
                "diagnostics_unavailable": True,
                "diagnostics_unavailable_reason": "queue_alloc_failed",
                "success_callback_count": None,
                "diagnostic_event_loss_count": None,
                "loss_accounting": None,
                "truncated": False,
            },
            boundary={"epoch": 6, "flush_generation": 1, "confirmed": True,
                      "status": "confirmed", "diagnostics_enabled": False,
                      "diagnostics_unavailable_reason": "queue_alloc_failed"},
        )
        status, payload = self._json(
            "POST", "/api/recordings",
            {"id": rec_id, "frames_csv": make_frames_csv(rec_id, 2), "meta": degraded_meta},
        )
        self.assertEqual(status, 200, payload)
        status, one = self._json("GET", f"/api/recordings/{rec_id}")
        self.assertEqual(status, 200)
        self.assertIsNone(one["events"]["ping"])
        self.assertIsNone(one["events"]["csi_diag"])
        self.assertTrue(one["session_stats"]["diagnostics_unavailable"])
        self.assertEqual(
            one["session_stats"]["diagnostics_unavailable_reason"], "queue_alloc_failed")
        self.assertIsNone(one["session_stats"]["success_callback_count"])
        self.assertIsNone(one["session_stats"]["diagnostic_event_loss_count"])
        self.assertFalse(one["boundary"]["diagnostics_enabled"])

        staged_id = "20261101T000200Z_walking_003"
        staged_meta = make_meta(
            staged_id, "walking", 2,
            session_stats={
                "diagnostic_event_loss_count": 6,
                "diag_tx_failure_count": 1,
                "loss_accounting": {"counter_inconsistent": False, "stages": {
                    "diag_assigned_count": 8, "diag_queue_overflow_count": 2, "diag_queue_enqueued_count": 6,
                    "diag_tx_failure_count": 1, "diag_pending_at_close_count": 0, "transport_unaccounted_count": 3,
                    "browser_received_unique_count": 2, "browser_persisted_count": 2,
                    "diag_unaccounted_stage1_count": 0,
                }},
            },
            boundary={"epoch": 7, "flush_generation": 1, "confirmed": False,
                      "status": "boundary_unconfirmed"},
        )
        status, payload = self._json(
            "POST", "/api/recordings",
            {"id": staged_id, "frames_csv": make_frames_csv(staged_id, 2), "meta": staged_meta},
        )
        self.assertEqual(status, 200, payload)
        status, one = self._json("GET", f"/api/recordings/{staged_id}")
        stages = one["session_stats"]["loss_accounting"]["stages"]
        self.assertEqual(stages["diag_queue_overflow_count"], 2)
        self.assertEqual(stages["diag_tx_failure_count"], 1)
        self.assertEqual(stages["transport_unaccounted_count"], 3)
        self.assertEqual(one["session_stats"]["diagnostic_event_loss_count"], 6)
        self.assertEqual(one["boundary"]["status"], "boundary_unconfirmed")

    def test_get_and_delete_two_files(self):
        rec_id = "20261030T000100Z_walking_001"
        self._json(
            "POST",
            "/api/recordings",
            {
                "id": rec_id,
                "frames_csv": make_frames_csv(rec_id, 2),
                "meta": make_meta(rec_id, "walking", 2),
            },
        )
        status, listed = self._json("GET", "/api/recordings")
        self.assertEqual(status, 200)
        row = next(r for r in listed["recordings"] if r["id"] == rec_id)
        self.assertEqual(row["activity_label"], "walking")
        self.assertEqual(row["binary_label"], "non_fall")

        status, one = self._json("GET", f"/api/recordings/{rec_id}")
        self.assertEqual(status, 200)
        self.assertIn("frame_sequence", one["frames_csv"])
        self.assertEqual(one["activity_label"], "walking")

        folder = self.recordings / "walking"
        status, deleted = self._json("DELETE", f"/api/recordings/{rec_id}")
        self.assertEqual(status, 200, deleted)
        self.assertFalse((folder / f"{rec_id}.frames.csv").exists())
        self.assertFalse((folder / f"{rec_id}.meta.json").exists())

    def test_rejects_stale_v2_fields(self):
        rec_id = "20261030T000200Z_bending_001"
        for stale in ("csi_data_csv", "iq_csv", "raw_iq_csv", "events", "label"):
            with self.subTest(field=stale):
                status, payload = self._json(
                    "POST",
                    "/api/recordings",
                    {
                        "id": rec_id,
                        "frames_csv": make_frames_csv(rec_id, 1),
                        "meta": make_meta(rec_id, "bending", 1),
                        stale: "x",
                    },
                )
                self.assertEqual(status, 400)
                self.assertFalse(payload["ok"])
                self.assertFalse((self.recordings / "bending" / f"{rec_id}.frames.csv").exists())

    def test_rejects_frame_count_mismatch_without_partial_write(self):
        rec_id = "20261030T000300Z_object_drop_001"
        meta = make_meta(rec_id, "object_drop", 5)  # claims 5, csv has 3
        status, payload = self._json(
            "POST",
            "/api/recordings",
            {"id": rec_id, "frames_csv": make_frames_csv(rec_id, 3), "meta": meta},
        )
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        folder = self.recordings / "object_drop"
        self.assertFalse((folder / f"{rec_id}.frames.csv").exists())
        self.assertFalse((folder / f"{rec_id}.meta.json").exists())

    def test_rejects_corrupt_base64(self):
        rec_id = "20261030T000400Z_fast_sitting_001"
        frames = make_frames_csv(rec_id, 1).replace(_b64(128, 0), "!!!not-base64!!!")
        status, payload = self._json(
            "POST",
            "/api/recordings",
            {"id": rec_id, "frames_csv": frames, "meta": make_meta(rec_id, "fast_sitting", 1)},
        )
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])

    def test_rejects_bad_id(self):
        status, payload = self._json(
            "POST",
            "/api/recordings",
            {"id": "../escape", "frames_csv": "x", "meta": {"schema_version": 3}},
        )
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])

    def test_delete_unknown(self):
        status, payload = self._json("DELETE", "/api/recordings/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
