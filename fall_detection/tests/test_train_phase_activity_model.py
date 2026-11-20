from __future__ import annotations

import base64
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from fall_detection.audit_dataset import FRAMES_HEADER
from fall_detection.train_phase_activity_model import (
    PhaseWindow,
    evaluate_grouped,
    extract_phase_windows,
    load_policy,
    run_experiment,
    stabilize_oof_predictions,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "fall_detection/phase_label_policy.json"
RUNTIME_SUBCARRIERS = 51


def _iso_at(epoch_ms: int) -> str:
    return dt.datetime.fromtimestamp(epoch_ms / 1000, tz=dt.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _write_take(
    directory: Path,
    recording_id: str,
    activity: str,
    start_epoch_ms: int,
    *,
    frames: int = 72,
    session_id: str = "session-a",
    annotations: bool = False,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    meta_path = directory / f"{recording_id}.meta.json"
    frame_path = directory / f"{recording_id}.frames.csv"
    is_fall = activity.startswith("fall_")
    action_phase = "fall_action" if is_fall else (
        "walking" if activity == "walking" else "action"
    )
    meta = {
        "recording_id": recording_id,
        "activity_label": activity,
        "status": "complete",
        "started_at_utc": _iso_at(start_epoch_ms),
        "clock_anchor": {
            "performance_now_ms": 1000.0,
            "date_now_ms": float(start_epoch_ms),
        },
        "session_id": session_id,
        "subject_id": "subject-a",
        "timeline": (
            [
                {"phase": "pre_action", "start_offset_s": 0, "end_offset_s": 4},
                {"phase": action_phase, "start_offset_s": 4, "end_offset_s": 6},
                {"phase": "post_action", "start_offset_s": 6, "end_offset_s": 10},
            ]
            if is_fall
            else [
                {"phase": "pre_action", "start_offset_s": 0, "end_offset_s": 0.6},
                {"phase": action_phase, "start_offset_s": 0.6, "end_offset_s": 1.6},
                {"phase": "post_action", "start_offset_s": 1.6, "end_offset_s": 2.2},
            ]
        ),
        "annotations": {
            "fall_start": {
                "timestamp_utc": _iso_at(start_epoch_ms + 4200),
                "offset_s": 4.2,
            },
            "fall_impact": {
                "timestamp_utc": _iso_at(start_epoch_ms + 5000),
                "offset_s": 5.0,
            },
        } if annotations and is_fall else {},
    }
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    indexes = {name: index for index, name in enumerate(FRAMES_HEADER)}
    payload = base64.b64encode(bytes([3, 4] * RUNTIME_SUBCARRIERS)).decode("ascii")
    rows = [",".join(FRAMES_HEADER)]
    for frame_index in range(frames):
        row = ["na"] * len(FRAMES_HEADER)
        row[indexes["recording_id"]] = recording_id
        row[indexes["frame_sequence"]] = str(frame_index)
        row[indexes["host_receive_monotonic_ns"]] = str(
            int((1000.0 + frame_index * 30.0) * 1e6)
        )
        row[indexes["sig_mode"]] = "0"
        row[indexes["bandwidth"]] = "0"
        row[indexes["stbc"]] = "0"
        row[indexes["secondary_channel"]] = "0"
        row[indexes["data_type"]] = "0"
        row[indexes["lltf_len"]] = str(RUNTIME_SUBCARRIERS * 2)
        row[indexes["valid_len"]] = str(RUNTIME_SUBCARRIERS * 2)
        row[indexes["valid_b64"]] = payload
        rows.append(",".join(row))
    frame_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return meta_path


class PhaseTrainingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy(POLICY_PATH)

    def test_selects_only_whole_windows_inside_mapped_phase_or_annotation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = _write_take(
                Path(temporary),
                "fall_take",
                "fall_forward",
                1767225600000,
                frames=400,
                annotations=True,
            )
            samples = extract_phase_windows(meta_path, self.policy)

        fall_samples = [sample for sample in samples if sample.label == "fall"]
        non_fall_samples = [
            sample for sample in samples if sample.label == "non_fall"
        ]
        self.assertTrue(fall_samples)
        self.assertTrue(non_fall_samples)
        self.assertTrue(
            all(
                sample.frame_start * 0.03 >= 4
                and sample.phase == "recording_tail_from_4s"
                for sample in fall_samples
            )
        )
        self.assertTrue(
            all(
                sample.frame_end * 0.03 < 4
                and sample.phase == "pre_action"
                for sample in non_fall_samples
            )
        )
        self.assertTrue(all(sample.frame_end - sample.frame_start == 23 for sample in samples))

    def test_activity_window_labels_come_from_phase_map_not_take_label(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meta_path = _write_take(
                Path(temporary),
                "bending_take",
                "bending",
                1767225600000,
            )
            samples = extract_phase_windows(meta_path, self.policy)

        self.assertTrue(samples)
        self.assertEqual({sample.label for sample in samples}, {"non_fall"})
        self.assertIn("action", {sample.phase for sample in samples})

    def test_grouped_oof_keeps_all_windows_from_a_take_in_one_fold(self) -> None:
        values = lambda value: (value,) * 16
        samples = [
            PhaseWindow(f"fall-{i}", f"fall-{i}", "fall_forward", "fall_start", 0, 23, "fall", values(5.0))
            for i in range(3)
        ] + [
            PhaseWindow(f"normal-{i}", f"normal-{i}", "walking", "walking", 0, 23, "non_fall", values(0.0))
            for i in range(3)
        ]

        predictions, metrics = evaluate_grouped(
            samples, ("fall", "non_fall"), "linear-svm", fold_count=3
        )

        self.assertEqual(len(predictions), len(samples))
        self.assertEqual(metrics["window_count"], len(samples))
        for prediction in predictions:
            self.assertEqual(prediction["group_id"], prediction["recording_id"])
        for group in {sample.group_id for sample in samples}:
            self.assertEqual(
                len({
                    row["fold_id"]
                    for row in predictions
                    if row["group_id"] == group
                }),
                1,
            )

    def test_rejects_group_fold_without_training_class(self) -> None:
        values = (0.0,) * 16
        samples = [
            PhaseWindow("fall-1", "same", "fall_forward", "fall_start", 0, 23, "fall", values),
            PhaseWindow("normal-1", "same", "walking", "walking", 0, 23, "non_fall", values),
            PhaseWindow("normal-2", "normal-2", "walking", "walking", 0, 23, "non_fall", values),
        ]
        with self.assertRaisesRegex(ValueError, "no training windows for classes"):
            evaluate_grouped(
                samples, ("fall", "non_fall"), "linear-svm", fold_count=2
            )

    def test_temporal_stabilization_reduces_class_transitions(self) -> None:
        raw_labels = [
            "non_fall", "fall", "non_fall", "fall",
            "non_fall", "non_fall", "non_fall",
        ]
        rows = [
            {
                "fold_id": 0,
                "recording_id": "take-1",
                "group_id": "take-1",
                "frame_start": index * 12,
                "true_label": label,
                "predicted_label": raw,
            }
            for index, (label, raw) in enumerate(
                zip(["non_fall"] * len(raw_labels), raw_labels)
            )
        ]

        stable_rows, transitions = stabilize_oof_predictions(
            rows, ("fall", "non_fall")
        )

        self.assertEqual(
            [row["stable_predicted_label"] for row in stable_rows],
            ["non_fall", "non_fall", "non_fall", "fall", "fall", "fall", "non_fall"],
        )
        self.assertEqual(transitions, {"raw_transitions": 4, "stabilized_transitions": 2})

    def test_writes_oof_predictions_and_summary_without_final_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for i in range(3):
                _write_take(
                    root / "fall_forward",
                    f"fall-{i}",
                    "fall_forward",
                    1767225600000 + i * 10000,
                    frames=400,
                    annotations=True,
                )
                _write_take(
                    root / "walking",
                    f"walk-{i}",
                    "walking",
                    1767225600000 + (i + 10) * 10000,
                )
            output = root / "out"

            summary = run_experiment(
                root,
                self.policy,
                "linear-svm",
                "take",
                output,
                fold_count=3,
                fit_final=True,
            )

            self.assertTrue(summary["final_model_fit"])
            self.assertFalse(summary["final_model_exported"])
            self.assertIn("stabilized", summary["oof_metrics"])
            self.assertEqual(
                summary["temporal_stability"]["fall_activation"],
                "at least 2 fall predictions in the last 3 windows",
            )
            self.assertTrue((output / "predictions.csv").is_file())
            self.assertTrue((output / "summary.json").is_file())
            artifact = json.loads(
                Path(summary["final_model_artifact"]).read_text(encoding="utf-8")
            )
            self.assertEqual(artifact["artifact_type"], "final_full_fit_model")
            self.assertFalse(artifact["provenance"]["uses_oof_fold_model"])


if __name__ == "__main__":
    unittest.main()
