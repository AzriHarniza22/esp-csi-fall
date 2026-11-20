from __future__ import annotations

import ctypes
import json
import math
import pickle
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fall_detection.classifier_models import ClassifierModel, predict_scores
from fall_detection.train_activity_model import extract_window_features

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "examples/esp-radar/wifi_sensing_demo/main"
ARTIFACT = ROOT / (
    "reports/activity_classifier_benchmark/20261108T073910Z/"
    "phase_aware_run_20261114_stabilized/final_model_phase_linear_svm.json"
)
CACHE = ROOT / (
    "reports/activity_classifier_benchmark/20261108T073910Z/features_cache.pkl"
)
WINDOW_FRAMES = 24
SUBCARRIERS = 51
FEATURE_COUNT = 16
CLASS_COUNT = 2
FloatArray = ctypes.c_float * (WINDOW_FRAMES * SUBCARRIERS)
FeatureArray = ctypes.c_float * FEATURE_COUNT
ScoreArray = ctypes.c_float * CLASS_COUNT


class ActivityModelCParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = shutil.which("gcc")
        if compiler is None:
            raise unittest.SkipTest("gcc is required for C/Python parity tests")
        cls.temp_dir = tempfile.TemporaryDirectory()
        library = Path(cls.temp_dir.name) / "libactivity_model.so"
        subprocess.run(
            [
                compiler,
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-shared",
                "-fPIC",
                "-I",
                str(MAIN),
                str(MAIN / "activity_model_data.c"),
                str(MAIN / "activity_model_inference.c"),
                "-lm",
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.lib = ctypes.CDLL(str(library))
        float_pointer = ctypes.POINTER(ctypes.c_float)
        cls.lib.activity_model_extract_features.argtypes = [
            float_pointer,
            ctypes.c_size_t,
            float_pointer,
        ]
        cls.lib.activity_model_extract_features.restype = None
        cls.lib.activity_model_standardize_features.argtypes = [
            float_pointer,
            float_pointer,
        ]
        cls.lib.activity_model_standardize_features.restype = ctypes.c_bool
        cls.lib.activity_model_linear_scores.argtypes = [
            float_pointer,
            float_pointer,
        ]
        cls.lib.activity_model_linear_scores.restype = ctypes.c_bool
        cls.lib.activity_model_argmax.argtypes = [float_pointer]
        cls.lib.activity_model_argmax.restype = ctypes.c_size_t
        cls.lib.activity_model_lltf_pair_count.argtypes = [
            ctypes.c_bool,
            ctypes.c_bool,
            ctypes.c_uint16,
        ]
        cls.lib.activity_model_lltf_pair_count.restype = ctypes.c_uint8
        cls.lib.activity_model_lltf_compatible.argtypes = [
            ctypes.c_bool,
            ctypes.c_bool,
            ctypes.c_uint16,
        ]
        cls.lib.activity_model_lltf_compatible.restype = ctypes.c_bool
        cls.lib.activity_model_ltf_segments_valid.argtypes = [
            ctypes.c_bool,
            ctypes.c_bool,
            ctypes.c_bool,
            ctypes.c_uint16,
            ctypes.c_uint16,
            ctypes.c_uint16,
            ctypes.c_uint16,
        ]
        cls.lib.activity_model_ltf_segments_valid.restype = ctypes.c_bool
        cls.lib.activity_model_should_reset_history.argtypes = [
            ctypes.c_bool,
            ctypes.c_bool,
        ]
        cls.lib.activity_model_should_reset_history.restype = ctypes.c_bool
        cls.lib.activity_model_iq_to_amplitude.argtypes = [
            ctypes.POINTER(ctypes.c_int8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_float),
        ]
        cls.lib.activity_model_iq_to_amplitude.restype = ctypes.c_bool

        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        raw_model = artifact["model"]
        cls.model = ClassifierModel(
            algorithm=raw_model["algorithm"],
            labels=tuple(raw_model["class_order"]),
            means=tuple(raw_model["means"]),
            scales=tuple(raw_model["scales"]),
            weights=tuple(tuple(row) for row in raw_model["weights"]),
            biases=tuple(raw_model["intercepts"]),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def test_c_features_match_python_for_51_pair_ring_window(self) -> None:
        rng = random.Random(20261114)
        frames = [
            [rng.uniform(0.0, 100.0) for _ in range(SUBCARRIERS)]
            for _ in range(WINDOW_FRAMES)
        ]
        oldest = 7
        ordered = frames[oldest:] + frames[:oldest]
        expected = extract_window_features(ordered)[0]
        flattened = [value for frame in frames for value in frame]
        c_history = FloatArray(*flattened)
        c_features = FeatureArray()
        self.lib.activity_model_extract_features(c_history, oldest, c_features)
        for index, (want, got) in enumerate(zip(expected, c_features)):
            self.assertAlmostEqual(want, got, delta=2e-6, msg=f"feature {index}")

    def test_layout_gate_requires_matching_flag_and_length(self) -> None:
        count = self.lib.activity_model_lltf_pair_count
        compatible = self.lib.activity_model_lltf_compatible
        self.assertEqual(count(True, True, 102), 51)
        self.assertEqual(count(True, False, 104), 52)
        self.assertEqual(count(True, True, 104), 0)
        self.assertEqual(count(True, False, 102), 0)
        self.assertEqual(count(False, True, 102), 0)
        self.assertTrue(compatible(True, True, 102))
        self.assertFalse(compatible(True, False, 104))

    def test_ltf_segment_gates_reject_ht_concatenation_leaks(self) -> None:
        valid = self.lib.activity_model_ltf_segments_valid
        self.assertTrue(valid(True, False, False, 102, 102, 0, 0))
        self.assertTrue(valid(False, True, False, 214, 102, 112, 0))
        self.assertTrue(valid(False, True, True, 326, 102, 112, 112))
        self.assertFalse(valid(False, True, False, 326, 102, 112, 0))
        self.assertFalse(valid(True, False, False, 214, 102, 112, 0))
        self.assertFalse(valid(False, False, False, 102, 102, 0, 0))

    def test_rejected_frame_and_queue_drop_reset_window_history(self) -> None:
        should_reset = self.lib.activity_model_should_reset_history
        self.assertTrue(should_reset(False, False))
        self.assertTrue(should_reset(True, True))
        self.assertFalse(should_reset(False, True))

    def test_c_iq_magnitudes_match_python_signed_byte_decoding(self) -> None:
        raw = [
            ((pair * 17) % 256) - 128
            for pair in range(SUBCARRIERS * 2)
        ]
        samples = (ctypes.c_int8 * len(raw))(*raw)
        c_amplitudes = (ctypes.c_float * SUBCARRIERS)()
        self.assertTrue(self.lib.activity_model_iq_to_amplitude(
            samples, SUBCARRIERS, c_amplitudes
        ))
        for pair in range(SUBCARRIERS):
            expected = math.hypot(raw[pair * 2], raw[pair * 2 + 1])
            self.assertAlmostEqual(expected, c_amplitudes[pair], delta=2e-5)
        self.assertFalse(self.lib.activity_model_iq_to_amplitude(
            samples, 52, c_amplitudes
        ))

    def test_c_full_iq_to_features_matches_python(self) -> None:
        frames = []
        c_history_values = []
        for frame in range(WINDOW_FRAMES):
            samples = [
                ((frame * 13 + pair * 7 + component * 19) % 256) - 128
                for pair in range(SUBCARRIERS)
                for component in range(2)
            ]
            c_samples = (ctypes.c_int8 * len(samples))(*samples)
            amplitudes = (ctypes.c_float * SUBCARRIERS)()
            self.assertTrue(self.lib.activity_model_iq_to_amplitude(
                c_samples, SUBCARRIERS, amplitudes
            ))
            frames.append([
                math.hypot(samples[pair * 2], samples[pair * 2 + 1])
                for pair in range(SUBCARRIERS)
            ])
            c_history_values.extend(amplitudes)
        expected = extract_window_features(frames)[0]
        c_history = FloatArray(*c_history_values)
        c_features = FeatureArray()
        self.lib.activity_model_extract_features(c_history, 0, c_features)
        for index, (want, got) in enumerate(zip(expected, c_features)):
            self.assertAlmostEqual(want, got, delta=2e-6, msg=f"feature {index}")

    def test_linear_scores_and_predictions_match_all_cached_windows(self) -> None:
        cache = pickle.loads(CACHE.read_bytes())
        expected_windows = 0
        max_abs_error = 0.0
        for take in cache.values():
            for window in take["windows"]:
                values = tuple(window["values"])
                expected = predict_scores(self.model, values)
                c_features = FeatureArray(*values)
                c_normalized = FeatureArray()
                self.assertTrue(
                    self.lib.activity_model_standardize_features(
                        c_features, c_normalized
                    )
                )
                expected_normalized = [
                    (values[index] - self.model.means[index]) /
                    self.model.scales[index]
                    for index in range(FEATURE_COUNT)
                ]
                for want, got in zip(expected_normalized, c_normalized):
                    self.assertLessEqual(abs(want - got), 2e-5)
                c_scores = ScoreArray()
                self.assertTrue(
                    self.lib.activity_model_linear_scores(c_features, c_scores)
                )
                for want, got in zip(expected, c_scores):
                    max_abs_error = max(max_abs_error, abs(want - got))
                self.assertEqual(
                    self.lib.activity_model_argmax(c_scores),
                    max(range(CLASS_COUNT), key=lambda index: expected[index]),
                )
                expected_windows += 1
        self.assertEqual(expected_windows, 3088)
        self.assertLessEqual(max_abs_error, 2e-5)

    def test_non_finite_scores_are_rejected(self) -> None:
        values = FeatureArray(*([0.0] * (FEATURE_COUNT - 1) + [math.nan]))
        scores = ScoreArray()
        self.assertFalse(self.lib.activity_model_linear_scores(values, scores))
        tied = ScoreArray(1.0, 1.0)
        self.assertEqual(self.lib.activity_model_argmax(tied), 0)

    def test_generated_class_order_is_fall_then_non_fall(self) -> None:
        labels = (ctypes.c_char_p * CLASS_COUNT).in_dll(
            self.lib, "activity_model_labels"
        )
        self.assertEqual(tuple(label.decode("ascii") for label in labels),
                         ("fall", "non_fall"))


if __name__ == "__main__":
    unittest.main()
