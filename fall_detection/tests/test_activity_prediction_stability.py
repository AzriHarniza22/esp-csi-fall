from __future__ import annotations

import ctypes
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "examples/esp-radar/wifi_sensing_demo/main"


class StabilityState(ctypes.Structure):
    _fields_ = [
        ("history", ctypes.c_size_t * 3),
        ("stable_class", ctypes.c_size_t),
        ("history_count", ctypes.c_uint8),
        ("next_history_index", ctypes.c_uint8),
        ("consecutive_non_fall", ctypes.c_uint8),
        ("initialized", ctypes.c_bool),
    ]


class ActivityPredictionStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = shutil.which("gcc")
        if compiler is None:
            raise unittest.SkipTest("gcc is required for stability state tests")
        cls.temp_dir = tempfile.TemporaryDirectory()
        library = Path(cls.temp_dir.name) / "libactivity_stability.so"
        subprocess.run(
            [
                compiler,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-shared",
                "-fPIC",
                str(MAIN / "activity_prediction_stability.c"),
                "-I",
                str(MAIN),
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.activity_prediction_stability_reset.argtypes = [
            ctypes.POINTER(StabilityState)
        ]
        cls.lib.activity_prediction_stability_update.argtypes = [
            ctypes.POINTER(StabilityState),
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        cls.lib.activity_prediction_stability_update.restype = ctypes.c_bool

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def _update(self, state: StabilityState, raw_class: int) -> int:
        stable_class = ctypes.c_size_t()
        self.assertTrue(
            self.lib.activity_prediction_stability_update(
                ctypes.byref(state), raw_class, 2, 0, 1, ctypes.byref(stable_class)
            )
        )
        return stable_class.value

    def test_requires_two_of_three_fall_windows_and_three_non_fall_to_release(self) -> None:
        state = StabilityState()
        self.lib.activity_prediction_stability_reset(ctypes.byref(state))

        self.assertEqual(self._update(state, 1), 1)
        self.assertEqual(self._update(state, 0), 1)
        self.assertEqual(self._update(state, 1), 1)
        self.assertEqual(self._update(state, 0), 0)
        self.assertEqual(self._update(state, 1), 0)
        self.assertEqual(self._update(state, 1), 0)
        self.assertEqual(self._update(state, 1), 1)

        self.assertEqual(self._update(state, 0), 1)
        self.assertEqual(self._update(state, 0), 0)
        self.assertEqual(self._update(state, 1), 0)
        self.assertEqual(self._update(state, 1), 0)
        self.assertEqual(self._update(state, 1), 1)

    def test_reset_clears_previous_votes_and_state(self) -> None:
        state = StabilityState()
        self.lib.activity_prediction_stability_reset(ctypes.byref(state))
        self._update(state, 1)
        self._update(state, 0)
        self._update(state, 0)
        self.assertEqual(state.stable_class, 0)

        self.lib.activity_prediction_stability_reset(ctypes.byref(state))

        self.assertEqual(self._update(state, 1), 1)
        self.assertEqual(state.history_count, 1)

    def test_rejects_invalid_class_values_and_indices(self) -> None:
        state = StabilityState()
        output = ctypes.c_size_t()
        self.lib.activity_prediction_stability_reset(ctypes.byref(state))
        self.assertFalse(
            self.lib.activity_prediction_stability_update(
                ctypes.byref(state), 2, 2, 0, 1, ctypes.byref(output)
            )
        )
        self.assertFalse(
            self.lib.activity_prediction_stability_update(
                ctypes.byref(state), 0, 2, 0, 0, ctypes.byref(output)
            )
        )


if __name__ == "__main__":
    unittest.main()
