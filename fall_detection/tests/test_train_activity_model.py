#!/usr/bin/env python3
"""Tests for CSI model training and embedded C export."""

from __future__ import annotations

import base64
import re
import unittest
import tempfile
from pathlib import Path

from fall_detection.audit_dataset import FRAMES_HEADER
from fall_detection.train_activity_model import (
    ALGORITHMS,
    CSI_SUBCARRIERS,
    FEATURE_COUNT,
    WINDOW_FRAMES,
    FeatureWindow,
    extract_window_features,
    parse_class_spec,
    read_amplitude_frames,
    read_amplitude_frames_from_frames_csv,
    render_c_header,
)
from fall_detection.classifier_models import fit_classifier, predict


def _write_frames_csv(path: Path, rows: int, *, sig_mode=0, bandwidth=0, stbc=0) -> None:
    idx = {name: i for i, name in enumerate(FRAMES_HEADER)}
    payload = base64.b64encode(bytes([3, 4] * CSI_SUBCARRIERS)).decode("ascii")
    lines = [",".join(FRAMES_HEADER)]
    for i in range(rows):
        row = ["na"] * len(FRAMES_HEADER)
        row[idx["recording_id"]] = "r"
        row[idx["frame_sequence"]] = str(i)
        row[idx["sig_mode"]] = str(sig_mode)
        row[idx["bandwidth"]] = str(bandwidth)
        row[idx["stbc"]] = str(stbc)
        row[idx["secondary_channel"]] = "0"
        row[idx["data_type"]] = "0"
        row[idx["valid_len"]] = str(CSI_SUBCARRIERS * 2)
        row[idx["valid_b64"]] = payload
        lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TrainingModelTests(unittest.TestCase):
    def test_parses_multiple_recording_labels_into_one_class(self) -> None:
        self.assertEqual(
            parse_class_spec(
                "ayunkan tangan=ayunkan tangan sekali,ayunkan tangan dua kali"
            ),
            (
                "ayunkan tangan",
                ("ayunkan tangan sekali", "ayunkan tangan dua kali"),
            ),
        )

    def test_extracts_overlapping_fixed_length_windows(self) -> None:
        frames = [
            [float(frame + subcarrier) for subcarrier in range(CSI_SUBCARRIERS)]
            for frame in range(WINDOW_FRAMES + 12)
        ]

        features = extract_window_features(frames)

        self.assertEqual(len(features), 2)
        self.assertEqual(len(features[0]), FEATURE_COUNT)
        self.assertTrue(all(value > 0 for value in features[0]))

    def test_reads_lltf_amplitudes_from_v3_frames_csv(self) -> None:
        # 104-byte valid payload = 52 int8 pairs of (3,4) -> amplitude 5.0 each.
        with tempfile.TemporaryDirectory() as temporary_directory:
            frames_path = Path(temporary_directory) / "sample.frames.csv"
            _write_frames_csv(frames_path, 3)

            frames = read_amplitude_frames_from_frames_csv(frames_path)

        self.assertEqual(len(frames), 3)
        self.assertEqual(len(frames[0]), CSI_SUBCARRIERS)
        self.assertAlmostEqual(frames[0][0], 5.0)

    def test_frames_csv_reader_skips_unsupported_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            frames_path = Path(temporary_directory) / "sample.frames.csv"
            _write_frames_csv(frames_path, 2, bandwidth=1)  # non-20MHz -> skipped

            frames = read_amplitude_frames_from_frames_csv(frames_path)

        self.assertEqual(frames, [])

    def test_frames_csv_reader_matches_legacy_amplitude_math(self) -> None:
        # Same (3,4) LLTF pairs fed through the legacy csi_data.csv path and the
        # v3 frames.csv path must yield identical amplitudes.
        lltf_values = [value for _ in range(CSI_SUBCARRIERS) for value in (3, 4)]
        with tempfile.TemporaryDirectory() as temporary_directory:
            csi_path = Path(temporary_directory) / "sample.csi_data.csv"
            csi_path.write_text(
                "sig_mode,bandwidth,stbc,secondary_channel,len,data\n"
                f'0,0,0,0,104,"{",".join(map(str, lltf_values))}"\n',
                encoding="utf-8",
            )
            frames_path = Path(temporary_directory) / "sample.frames.csv"
            _write_frames_csv(frames_path, 1)

            legacy = read_amplitude_frames(csi_path)
            v3 = read_amplitude_frames_from_frames_csv(frames_path)

        self.assertEqual(len(legacy), 1)
        self.assertEqual(len(v3), 1)
        for a, b in zip(legacy[0], v3[0]):
            self.assertAlmostEqual(a, b)

    def test_reads_consistent_lltf_from_supported_packet_layouts(self) -> None:
        lltf_values = [value for _ in range(CSI_SUBCARRIERS) for value in (3, 4)]
        stbc_values = lltf_values + [0] * (328 - len(lltf_values))
        non_ht_values = [0, 5] * CSI_SUBCARRIERS
        with tempfile.TemporaryDirectory() as temporary_directory:
            csi_path = Path(temporary_directory) / "sample.csi_data.csv"
            csi_path.write_text(
                "sig_mode,bandwidth,stbc,secondary_channel,len,data\n"
                f'1,0,1,0,328,"{",".join(map(str, stbc_values))}"\n'
                f'0,0,0,0,104,"{",".join(map(str, non_ht_values))}"\n'
                f'1,1,1,0,328,"{",".join(map(str, stbc_values))}"\n',
                encoding="utf-8",
            )

            frames = read_amplitude_frames(csi_path)

        self.assertEqual(len(frames), 2)
        self.assertEqual(len(frames[0]), CSI_SUBCARRIERS)
        self.assertAlmostEqual(frames[0][0], 5.0)
        self.assertAlmostEqual(frames[1][0], 5.0)

    def test_fit_and_export_contains_class_parameters(self) -> None:
        windows = [
            FeatureWindow("sit-1", "duduk", (0.0,) * FEATURE_COUNT),
            FeatureWindow("wave-1", "ayunkan tangan", (1.0,) * FEATURE_COUNT),
        ]
        model = fit_classifier(
            "nearest-centroid",
            [window.values for window in windows],
            [window.label for window in windows],
            ("duduk", "ayunkan tangan"),
        )

        header = render_c_header(model, ["sit-1", "wave-1"], CSI_SUBCARRIERS)

        self.assertIn('"duduk", "ayunkan tangan"', header)
        self.assertIn("ACTIVITY_MODEL_CLASS_COUNT 2", header)
        self.assertIn("ACTIVITY_MODEL_ALGORITHM 1", header)
        self.assertIn("Source take IDs: sit-1, wave-1", header)

    def test_requires_two_classes(self) -> None:
        with self.assertRaises(ValueError):
            fit_classifier(
                "nearest-centroid",
                [(0.0,) * FEATURE_COUNT],
                ["duduk"],
                ("duduk",),
            )

    def test_all_embedded_algorithms_fit_and_predict_separable_rows(self) -> None:
        labels = ("quiet", "motion")
        rows = []
        targets = []
        for index in range(8):
            quiet_value = float(index) * 0.01
            motion_value = 4.0 + float(index) * 0.01
            quiet = (quiet_value,) * FEATURE_COUNT
            motion = (motion_value,) * FEATURE_COUNT
            rows.extend((quiet, motion))
            targets.extend(("quiet", "motion"))

        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                model = fit_classifier(algorithm, rows, targets, labels)
                self.assertEqual(predict(model, rows[0]), "quiet")
                self.assertEqual(predict(model, rows[1]), "motion")
                header = render_c_header(model, ["take-1"], CSI_SUBCARRIERS)
                self.assertIn(f"ACTIVITY_MODEL_ALGORITHM {ALGORITHMS.index(algorithm) + 1}", header)
                self.assertIn("ACTIVITY_MODEL_FEATURE_COUNT 16", header)
                if algorithm in {"decision-tree", "random-forest"}:
                    self.assertNotIn(" 0f,", header)
                    self.assertIn("0.0f", header)

    def test_classifier_rejects_missing_training_class(self) -> None:
        with self.assertRaisesRegex(ValueError, "No training rows"):
            fit_classifier(
                "nearest-centroid",
                [(0.0,) * FEATURE_COUNT, (0.1,) * FEATURE_COUNT],
                ["quiet", "quiet"],
                ("quiet", "motion"),
            )


class HeaderRendererFixtureTests(unittest.TestCase):
    """Fase 1A.2: the renderer writes the measured LLTF width and produces a
    self-consistent C header. Tested with synthetic fixtures only - never by
    exporting a previously trained model as a stand-in for a temporary header."""

    _LABELS = ("normal_still", "fall_transition", "fallen_still", "other_action", "other_still")

    def _synthetic_model(self, algorithm: str = "linear-svm"):
        rows, targets = [], []
        for index in range(6):
            base = float(index) * 0.01
            for offset, label in enumerate(self._LABELS):
                rows.append((base + offset * 3.0,) * FEATURE_COUNT)
                targets.append(label)
        return fit_classifier(algorithm, rows, targets, self._LABELS)

    def _define(self, header: str, name: str) -> int:
        match = re.search(rf"#define {name} (\d+)", header)
        self.assertIsNotNone(match, f"{name} missing from header")
        return int(match.group(1))

    def _array_values(self, header: str, name: str) -> list[list[str]]:
        """Rows of numeric values for one ``static const ... name[..] = {...};``."""
        match = re.search(rf"{name}\[[^\]]*\][^\"]*?= \{{(.*?)\}};", header, re.DOTALL)
        self.assertIsNotNone(match, f"{name} missing from header")
        body = match.group(1)
        if "{" in body:  # 2-D array: split on inner braces
            return [re.findall(r"-?\d+\.?\d*f?", inner)
                    for inner in re.findall(r"\{([^}]*)\}", body)]
        return [re.findall(r"-?\d+\.?\d*f?", body)]

    def test_measured_51_pair_layout_is_written(self) -> None:
        header = render_c_header(self._synthetic_model(), ["synth-1"], 51)
        self.assertEqual(self._define(header, "ACTIVITY_MODEL_SUBCARRIERS"), 51)
        self.assertEqual(self._define(header, "ACTIVITY_MODEL_LLTF_BYTES"), 102)

    def test_measured_52_pair_layout_is_written(self) -> None:
        header = render_c_header(self._synthetic_model(), ["synth-1"], 52)
        self.assertEqual(self._define(header, "ACTIVITY_MODEL_SUBCARRIERS"), 52)
        self.assertEqual(self._define(header, "ACTIVITY_MODEL_LLTF_BYTES"), 104)

    def test_lltf_bytes_is_twice_subcarriers(self) -> None:
        for width in (51, 52):
            header = render_c_header(self._synthetic_model(), ["synth-1"], width)
            self.assertEqual(
                self._define(header, "ACTIVITY_MODEL_LLTF_BYTES"), 2 * width)

    def test_rejects_non_positive_measured_width(self) -> None:
        model = self._synthetic_model()
        for bad in (0, -1, None, 52.0):
            with self.subTest(width=bad):
                with self.assertRaises(ValueError):
                    render_c_header(model, ["synth-1"], bad)

    def test_weight_dimensions_class_order_and_index_consistency(self) -> None:
        model = self._synthetic_model("linear-svm")
        header = render_c_header(model, ["synth-1"], 51)
        class_count = self._define(header, "ACTIVITY_MODEL_CLASS_COUNT")
        feature_count = self._define(header, "ACTIVITY_MODEL_FEATURE_COUNT")
        self.assertEqual(class_count, len(self._LABELS))
        self.assertEqual(feature_count, FEATURE_COUNT)
        # Class order + index: the labels array must match model.labels exactly.
        labels_line = re.search(
            r"activity_model_labels\[[^\]]*\]\s*=\s*\{(.*)\};", header,
            re.DOTALL).group(1)
        labels = re.findall(r'"([^"]+)"', labels_line)
        self.assertEqual(tuple(labels), model.labels)
        # Weight matrix shape = class_count rows x feature_count columns.
        weights = self._array_values(header, "activity_model_weights")
        self.assertEqual(len(weights), class_count)
        self.assertTrue(all(len(row) == feature_count for row in weights))
        biases = self._array_values(header, "activity_model_biases")[0]
        self.assertEqual(len(biases), class_count)
        means = self._array_values(header, "activity_model_means")[0]
        scales = self._array_values(header, "activity_model_scales")[0]
        self.assertEqual(len(means), feature_count)
        self.assertEqual(len(scales), feature_count)

    def test_encode_decode_roundtrip_consistency(self) -> None:
        # The header must reproduce the trained model's per-class biases, so a
        # consumer reading the C arrays recovers identical parameters.
        model = self._synthetic_model("linear-svm")
        header = render_c_header(model, ["synth-1"], 52)
        biases = [float(v.rstrip("f")) for v in
                  self._array_values(header, "activity_model_biases")[0]]
        self.assertEqual(len(biases), len(model.biases))
        for expected, got in zip(model.biases, biases):
            self.assertAlmostEqual(expected, got, places=6)


if __name__ == "__main__":
    unittest.main()
