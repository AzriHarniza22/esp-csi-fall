#!/usr/bin/env python3
"""Sanitasi path, tulis atomik, GET/DELETE API tanpa perangkat."""

from __future__ import annotations

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


class SafeJoinTests(unittest.TestCase):
    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "duduk").mkdir()
            with self.assertRaises(ValueError):
                srv.safe_join(root, "..", "etc", "passwd")
            with self.assertRaises(ValueError):
                srv.safe_join(root, "duduk", "..", "..", "secret")


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

    def test_post_list_delete(self):
        rec_id = "20261022T014532Z_duduk_001"
        status, payload = self._json(
            "POST",
            "/api/recordings",
            {
                "id": rec_id,
                "label": "duduk",
                "csi_data_csv": "type,data\nCSI_DATA,1\n",
                "iq_csv": "timestamp_us,seq\n1,1\n",
                "meta": {"frames": 1, "complete": True, "duration_s": 10, "started_at_utc": "2026-10-22T01:45:32Z"},
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue((self.recordings / "duduk" / f"{rec_id}.csi_data.csv").is_file())
        self.assertTrue((self.recordings / "index.csv").is_file())

        status, listed = self._json("GET", "/api/recordings")
        self.assertEqual(status, 200)
        self.assertEqual(listed["recordings"][0]["id"], rec_id)

        status, one = self._json("GET", f"/api/recordings/{rec_id}")
        self.assertEqual(status, 200)
        self.assertIn("CSI_DATA", one["csi_data_csv"])

        status, deleted = self._json("DELETE", f"/api/recordings/{rec_id}")
        self.assertEqual(status, 200, deleted)
        self.assertFalse((self.recordings / "duduk" / f"{rec_id}.csi_data.csv").exists())

    def test_rejects_bad_id(self):
        status, payload = self._json(
            "POST",
            "/api/recordings",
            {
                "id": "../escape",
                "label": "duduk",
                "csi_data_csv": "x",
                "iq_csv": "x",
                "meta": {},
            },
        )
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])

    def test_delete_unknown(self):
        status, payload = self._json("DELETE", "/api/recordings/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
