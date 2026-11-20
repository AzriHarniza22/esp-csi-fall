from __future__ import annotations

import ctypes
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "examples/esp-radar/wifi_sensing_demo/main"


class MotionGateResult(ctypes.Structure):
    _fields_ = [
        ("output_class", ctypes.c_size_t),
        ("amplitude_vetoed", ctypes.c_bool),
        ("confident_fall", ctypes.c_bool),
    ]


class ActivityMotionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = shutil.which("gcc")
        if compiler is None:
            raise unittest.SkipTest("gcc is required for motion gate tests")
        cls.temp_dir = tempfile.TemporaryDirectory()
        library = Path(cls.temp_dir.name) / "libactivity_motion_gate.so"
        subprocess.run(
            [
                compiler,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-shared",
                "-fPIC",
                str(MAIN / "activity_motion_gate.c"),
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
        cls.lib.activity_motion_gate_apply.argtypes = [
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_uint32,
            ctypes.POINTER(MotionGateResult),
        ]
        cls.lib.activity_motion_gate_apply.restype = ctypes.c_bool

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def apply_gate(self, model_class: int, motion: int) -> MotionGateResult:
        result = MotionGateResult()
        self.assertTrue(
            self.lib.activity_motion_gate_apply(
                model_class, 2, 0, 1, motion, ctypes.byref(result)
            )
        )
        return result

    def test_motion_below_3850_vetoes_model_fall(self) -> None:
        result = self.apply_gate(0, 3_849_999)
        self.assertEqual(result.output_class, 1)
        self.assertTrue(result.amplitude_vetoed)
        self.assertFalse(result.confident_fall)

    def test_exact_3850_does_not_veto(self) -> None:
        result = self.apply_gate(0, 3_850_000)
        self.assertEqual(result.output_class, 0)
        self.assertFalse(result.amplitude_vetoed)

    def test_confident_marker_requires_model_fall_and_motion_above_5000(self) -> None:
        result = self.apply_gate(0, 5_000_001)
        self.assertTrue(result.confident_fall)

    def test_high_motion_does_not_force_model_non_fall_to_fall(self) -> None:
        result = self.apply_gate(1, 5_500_000)
        self.assertEqual(result.output_class, 1)
        self.assertFalse(result.confident_fall)

    def test_exact_5000_is_not_marked_confident(self) -> None:
        result = self.apply_gate(0, 5_000_000)
        self.assertFalse(result.confident_fall)

    def test_rejects_invalid_class_configuration(self) -> None:
        result = MotionGateResult()
        self.assertFalse(
            self.lib.activity_motion_gate_apply(
                0, 2, 0, 0, 5_500_000, ctypes.byref(result)
            )
        )


if __name__ == "__main__":
    unittest.main()
