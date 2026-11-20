#!/usr/bin/env python3
"""Train and evaluate a window classifier from explicitly labeled take phases."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
from fall_detection.classifier_models import (  # noqa: E402
    ALGORITHMS,
    fit_classifier,
    predict_scores,
)
from fall_detection.train_activity_model import (  # noqa: E402
    FEATURE_COUNT,
    WINDOW_FRAMES,
    WINDOW_STRIDE,
    extract_window_features,
    read_timed_amplitude_frames_from_frames_csv,
)

DEFAULT_RECORDINGS = (
    REPOSITORY_ROOT / "examples/esp-radar/wifi_sensing_demo/recordings"
)
DEFAULT_POLICY = REPOSITORY_ROOT / "fall_detection/phase_label_policy.json"
MODEL_SUBCARRIER_WIDTH = 51


@dataclass(frozen=True)
class PhaseWindow:
    recording_id: str
    group_id: str
    activity_label: str
    phase: str
    frame_start: int
    frame_end: int
    label: str
    values: tuple[float, ...]


def _utc_ms(value: str) -> float:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value!r}")
    return parsed.timestamp() * 1000.0


def _host_seconds(anchor: dict[str, Any], utc_millis: float) -> float:
    try:
        performance_ms = float(anchor["performance_now_ms"])
        date_ms = float(anchor["date_now_ms"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("clock_anchor must contain numeric clock-pair fields") from exc
    if not math.isfinite(performance_ms) or not math.isfinite(date_ms):
        raise ValueError("clock_anchor values must be finite")
    return (performance_ms + utc_millis - date_ms) / 1000.0


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    class_order = policy.get("class_order")
    phase_labels = policy.get("phase_labels")
    annotation_intervals = policy.get("annotation_intervals", {})
    recording_tail_labels = policy.get("recording_tail_labels", {})
    if (
        not isinstance(class_order, list)
        or len(class_order) < 2
        or any(not isinstance(label, str) or not label for label in class_order)
        or len(set(class_order)) != len(class_order)
    ):
        raise ValueError("Policy class_order must contain at least two unique labels")
    if (
        not isinstance(phase_labels, dict)
        or not isinstance(annotation_intervals, dict)
        or not isinstance(recording_tail_labels, dict)
    ):
        raise ValueError(
            "Policy phase_labels, annotation_intervals, and "
            "recording_tail_labels must be objects"
        )
    preprocessing = policy.get("preprocessing")
    if not isinstance(preprocessing, dict) or preprocessing != {
        "subcarrier_width": MODEL_SUBCARRIER_WIDTH,
        "feature_count": FEATURE_COUNT,
        "window_frames": WINDOW_FRAMES,
        "window_stride_frames": WINDOW_STRIDE,
    }:
        raise ValueError("Policy preprocessing does not match the ESP32 model input")
    for activity, labels_by_phase in phase_labels.items():
        if not isinstance(activity, str) or not isinstance(labels_by_phase, dict):
            raise ValueError("Each phase_labels entry must map an activity to phases")
        for phase, label in labels_by_phase.items():
            if not isinstance(phase, str) or label not in class_order:
                raise ValueError(f"Invalid phase label mapping for {activity!r}/{phase!r}")
    for activity, intervals in annotation_intervals.items():
        if not isinstance(activity, str) or not isinstance(intervals, list):
            raise ValueError("Each annotation_intervals entry must be a list")
        for interval in intervals:
            if (
                not isinstance(interval, dict)
                or not isinstance(interval.get("start"), str)
                or not isinstance(interval.get("end"), str)
                or interval.get("label") not in class_order
            ):
                raise ValueError(f"Invalid annotation interval for {activity!r}")
    for activity, spec in recording_tail_labels.items():
        if (
            not isinstance(activity, str)
            or not isinstance(spec, dict)
            or spec.get("label") not in class_order
        ):
            raise ValueError(f"Invalid recording-tail label for {activity!r}")
        try:
            start_offset_s = float(spec["start_offset_s"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid recording-tail start for {activity!r}"
            ) from exc
        if not math.isfinite(start_offset_s) or start_offset_s < 0:
            raise ValueError(
                f"Recording-tail start for {activity!r} must be finite and non-negative"
            )
    return policy


def _take_group(meta: dict[str, Any], recording_id: str, group_by: str) -> str:
    if group_by == "take":
        return recording_id
    value = meta.get(f"{group_by}_id")
    if value is None or not str(value).strip():
        raise ValueError(f"missing {group_by}_id required by --group-by {group_by}")
    return str(value)


def _phase_intervals(
    meta: dict[str, Any], first_frame_s: float
) -> list[tuple[str, float, float]]:
    anchor = meta.get("clock_anchor")
    started = meta.get("started_at_utc")
    timeline = meta.get("timeline")
    if not isinstance(anchor, dict) or not started or not isinstance(timeline, list):
        raise ValueError("missing clock_anchor, started_at_utc, or phase timeline")
    plan_start_s = _host_seconds(anchor, _utc_ms(str(started)))
    result: list[tuple[str, float, float]] = []
    for item in timeline:
        if not isinstance(item, dict):
            raise ValueError("timeline entries must be objects")
        try:
            phase = str(item["phase"])
            start = plan_start_s + float(item["start_offset_s"]) - first_frame_s
            end = plan_start_s + float(item["end_offset_s"]) - first_frame_s
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("timeline entry has invalid phase boundaries") from exc
        if not phase or not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError("timeline phase boundaries must be finite and increasing")
        result.append((phase, start, end))
    return result


def _annotation_intervals(
    meta: dict[str, Any], policy_intervals: list[dict[str, str]], first_frame_s: float
) -> list[tuple[str, float, float, str]]:
    if not policy_intervals:
        return []
    anchor = meta.get("clock_anchor")
    annotations = meta.get("annotations")
    if not isinstance(anchor, dict) or not isinstance(annotations, dict):
        return []
    result = []
    for spec in policy_intervals:
        start_event = annotations.get(spec["start"])
        end_event = annotations.get(spec["end"])
        if not isinstance(start_event, dict) or not isinstance(end_event, dict):
            continue
        start_utc = start_event.get("timestamp_utc")
        end_utc = end_event.get("timestamp_utc")
        if not start_utc or not end_utc:
            continue
        start = _host_seconds(anchor, _utc_ms(str(start_utc))) - first_frame_s
        end = _host_seconds(anchor, _utc_ms(str(end_utc))) - first_frame_s
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError(
                f"invalid annotation interval {spec['start']} -> {spec['end']}"
            )
        result.append((spec["start"], start, end, spec["label"]))
    return result


def extract_phase_windows(
    meta_path: Path, policy: dict[str, Any], group_by: str = "take"
) -> list[PhaseWindow]:
    recording_id = meta_path.name.removesuffix(".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("status") != "complete":
        raise ValueError("recording status is not complete")
    activity = str(meta.get("activity_label") or "")
    phase_labels = policy["phase_labels"].get(activity, {})
    annotation_specs = policy.get("annotation_intervals", {}).get(activity, [])
    if not phase_labels and not annotation_specs:
        return []

    frames_path = meta_path.with_name(f"{recording_id}.frames.csv")
    amplitude_frames, timestamps = read_timed_amplitude_frames_from_frames_csv(
        frames_path
    )
    if len(amplitude_frames) < WINDOW_FRAMES:
        raise ValueError(f"only {len(amplitude_frames)} valid frames")
    if any(len(frame) != MODEL_SUBCARRIER_WIDTH for frame in amplitude_frames):
        raise ValueError(
            f"runtime model requires {MODEL_SUBCARRIER_WIDTH}-pair LLTF frames"
        )
    if len(timestamps) != len(amplitude_frames):
        raise ValueError("canonical frame/timestamp counts do not match")
    if any(
        not math.isfinite(timestamp) or timestamps[i + 1] < timestamp
        for i, timestamp in enumerate(timestamps[:-1])
    ):
        raise ValueError("host frame timestamps are non-finite or reversed")

    first_frame_s = timestamps[0]
    phases = _phase_intervals(meta, first_frame_s)
    annotations = _annotation_intervals(meta, annotation_specs, first_frame_s)
    recording_tail = policy.get("recording_tail_labels", {}).get(activity)
    recording_tail_start_s = None
    if recording_tail is not None:
        anchor = meta["clock_anchor"]
        plan_start_s = _host_seconds(anchor, _utc_ms(str(meta["started_at_utc"])))
        recording_tail_start_s = (
            plan_start_s + float(recording_tail["start_offset_s"]) - first_frame_s
        )
    recording_end_s = timestamps[-1] - first_frame_s
    features = extract_window_features(amplitude_frames)
    samples = []
    for index, values in enumerate(features):
        start_index = index * WINDOW_STRIDE
        end_index = start_index + WINDOW_FRAMES - 1
        window_start = timestamps[start_index] - first_frame_s
        window_end = timestamps[end_index] - first_frame_s
        matches: list[tuple[str, str]] = []
        for phase, phase_start, phase_end in phases:
            label = phase_labels.get(phase)
            if (
                label is not None
                and window_start >= phase_start
                and window_end < phase_end
            ):
                matches.append((phase, label))
        for phase, phase_start, phase_end, label in annotations:
            if window_start >= phase_start and window_end < phase_end:
                matches.append((phase, label))
        if (
            recording_tail is not None
            and recording_tail_start_s is not None
            and window_start >= recording_tail_start_s
            and window_end <= recording_end_s
        ):
            matches.append(
                ("recording_tail_from_4s", recording_tail["label"])
            )
        labels = {label for _, label in matches}
        if len(labels) > 1:
            raise ValueError(
                f"{recording_id} window {index} matches conflicting labels "
                f"{sorted(labels)}"
            )
        if not matches:
            continue
        phase_names = sorted({phase for phase, _ in matches})
        samples.append(
            PhaseWindow(
                recording_id=recording_id,
                group_id=_take_group(meta, recording_id, group_by),
                activity_label=activity,
                phase="+".join(phase_names),
                frame_start=start_index,
                frame_end=end_index,
                label=next(iter(labels)),
                values=values,
            )
        )
    return samples


def collect_phase_windows(
    recordings_dir: Path,
    policy: dict[str, Any],
    group_by: str,
) -> tuple[list[PhaseWindow], dict[str, int]]:
    samples: list[PhaseWindow] = []
    skipped: Counter[str] = Counter()
    for meta_path in sorted(recordings_dir.rglob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if str(meta.get("session_id") or "") in policy.get(
            "excluded_session_ids", []
        ):
            skipped["excluded session by label policy"] += 1
            continue
        if str(meta.get("subject_id") or "") in policy.get(
            "excluded_subject_ids", []
        ):
            skipped["excluded subject by label policy"] += 1
            continue
        try:
            take_samples = extract_phase_windows(meta_path, policy, group_by)
        except ValueError as exc:
            skipped[str(exc)] += 1
            continue
        if not take_samples:
            skipped["no mapped phase windows"] += 1
            continue
        samples.extend(take_samples)
    if not samples:
        raise ValueError("No labeled phase windows were found")
    return samples, dict(sorted(skipped.items()))


def _metrics(
    actual: list[str], predicted: list[str], class_order: tuple[str, ...]
) -> dict[str, Any]:
    per_class = {}
    f1_values = []
    correct = 0
    for label in class_order:
        tp = sum(a == label and p == label for a, p in zip(actual, predicted))
        fp = sum(a != label and p == label for a, p in zip(actual, predicted))
        fn = sum(a == label and p != label for a, p in zip(actual, predicted))
        support = sum(a == label for a in actual)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        per_class[label] = {
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        f1_values.append(f1)
    correct = sum(a == p for a, p in zip(actual, predicted))
    return {
        "window_count": len(actual),
        "accuracy": correct / len(actual) if actual else 0.0,
        "macro_f1": sum(f1_values) / len(f1_values) if f1_values else 0.0,
        "per_class": per_class,
    }


def stabilize_oof_predictions(
    prediction_rows: list[dict[str, Any]],
    class_order: tuple[str, ...],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    fall_class = "fall"
    non_fall_class = "non_fall"
    if class_order != (fall_class, non_fall_class):
        raise ValueError("Temporal stabilization requires fall, non_fall class order")

    by_recording: dict[str, list[dict[str, Any]]] = {}
    for row in prediction_rows:
        by_recording.setdefault(row["recording_id"], []).append(row)

    raw_transitions = 0
    stable_transitions = 0
    result: list[dict[str, Any]] = []
    for rows in by_recording.values():
        rows.sort(key=lambda row: row["frame_start"])
        history: list[str] = []
        stable_class: str | None = None
        non_fall_streak = 0
        previous_raw: str | None = None
        previous_stable: str | None = None
        previous_start: int | None = None
        for row in rows:
            raw_class = row["predicted_label"]
            start = row["frame_start"]
            if previous_start is not None and start - previous_start != WINDOW_STRIDE:
                history = []
                stable_class = None
                non_fall_streak = 0
                previous_raw = None
                previous_stable = None
            history = (history + [raw_class])[-3:]
            if stable_class is None:
                stable_class = raw_class
            elif stable_class == non_fall_class:
                if history.count(fall_class) >= 2:
                    stable_class = fall_class
                    non_fall_streak = 0
            elif raw_class == non_fall_class:
                non_fall_streak += 1
                if non_fall_streak >= 3:
                    stable_class = non_fall_class
                    non_fall_streak = 0
            else:
                non_fall_streak = 0

            if previous_raw is not None:
                raw_transitions += raw_class != previous_raw
                stable_transitions += stable_class != previous_stable
            result.append({**row, "stable_predicted_label": stable_class})
            previous_raw = raw_class
            previous_stable = stable_class
            previous_start = start
    result.sort(key=lambda row: (row["fold_id"], row["recording_id"], row["frame_start"]))
    return result, {
        "raw_transitions": raw_transitions,
        "stabilized_transitions": stable_transitions,
    }


def evaluate_grouped(
    samples: list[PhaseWindow],
    class_order: tuple[str, ...],
    algorithm: str,
    fold_count: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups = sorted({sample.group_id for sample in samples})
    if fold_count < 2 or fold_count > len(groups):
        raise ValueError(
            f"fold_count must be between 2 and the group count ({len(groups)})"
        )
    group_counts: dict[str, Counter[str]] = {
        group: Counter(sample.label for sample in samples if sample.group_id == group)
        for group in groups
    }
    fold_groups: list[list[str]] = [[] for _ in range(fold_count)]
    fold_counts: list[Counter[str]] = [Counter() for _ in range(fold_count)]
    fold_sizes = [0] * fold_count
    assigned: set[str] = set()
    class_group_counts = {
        label: sum(group_counts[group][label] > 0 for group in groups)
        for label in class_order
    }
    for label in sorted(class_order, key=lambda item: (class_group_counts[item], item)):
        candidates = sorted(
            (group for group in groups if group not in assigned and group_counts[group][label]),
            key=lambda group: (-group_counts[group][label], group),
        )
        for group in candidates:
            fold_index = min(
                range(fold_count),
                key=lambda index: (fold_counts[index][label], fold_sizes[index], index),
            )
            fold_groups[fold_index].append(group)
            fold_counts[fold_index].update(group_counts[group])
            fold_sizes[fold_index] += sum(group_counts[group].values())
            assigned.add(group)
    for group in sorted(
        (group for group in groups if group not in assigned),
        key=lambda item: (-sum(group_counts[item].values()), item),
    ):
        fold_index = min(range(fold_count), key=lambda index: (fold_sizes[index], index))
        fold_groups[fold_index].append(group)
        fold_counts[fold_index].update(group_counts[group])
        fold_sizes[fold_index] += sum(group_counts[group].values())

    actual_all: list[str] = []
    predicted_all: list[str] = []
    prediction_rows: list[dict[str, Any]] = []
    for fold_id, held_groups in enumerate(fold_groups):
        held_group_set = set(held_groups)
        training = [sample for sample in samples if sample.group_id not in held_group_set]
        testing = [sample for sample in samples if sample.group_id in held_group_set]
        if not testing:
            raise ValueError(f"OOF fold {fold_id} has no test windows")
        training_labels = {sample.label for sample in training}
        missing = sorted(set(class_order) - training_labels)
        if missing:
            raise ValueError(
                f"OOF fold {fold_id} leaves no training windows for classes: "
                + ", ".join(missing)
            )
        model = fit_classifier(
            algorithm,
            [sample.values for sample in training],
            [sample.label for sample in training],
            class_order,
        )
        for sample in testing:
            scores = predict_scores(model, sample.values)
            predicted = class_order[max(range(len(scores)), key=scores.__getitem__)]
            actual_all.append(sample.label)
            predicted_all.append(predicted)
            prediction_rows.append(
                {
                    "fold_id": fold_id,
                    "group_id": sample.group_id,
                    "recording_id": sample.recording_id,
                    "activity_label": sample.activity_label,
                    "phase": sample.phase,
                    "frame_start": sample.frame_start,
                    "frame_end": sample.frame_end,
                    "true_label": sample.label,
                    "predicted_label": predicted,
                    "scores": list(scores),
                }
            )
    stabilized_rows, transition_counts = stabilize_oof_predictions(
        prediction_rows, class_order
    )
    stabilized_actual = [row["true_label"] for row in stabilized_rows]
    stable_predictions = [row["stable_predicted_label"] for row in stabilized_rows]
    metrics = _metrics(actual_all, predicted_all, class_order)
    metrics["temporal_stability"] = transition_counts
    metrics["stabilized"] = _metrics(stabilized_actual, stable_predictions, class_order)
    return stabilized_rows, metrics


def build_final_model_artifact(
    samples: list[PhaseWindow],
    policy: dict[str, Any],
    policy_path: Path,
    algorithm: str,
) -> dict[str, Any]:
    if algorithm != "linear-svm":
        raise ValueError("ESP32 phase-model export currently supports linear-svm only")
    if not samples:
        raise ValueError("Cannot fit a final model without labeled windows")
    class_order = tuple(policy["class_order"])
    counts = Counter(sample.label for sample in samples)
    missing = sorted(set(class_order) - counts.keys())
    if missing:
        raise ValueError("No labeled windows for classes: " + ", ".join(missing))

    model = fit_classifier(
        algorithm,
        [sample.values for sample in samples],
        [sample.label for sample in samples],
        class_order,
    )
    policy_sha256 = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    return {
        "artifact_type": "final_full_fit_model",
        "experiment_id": "PHASE",
        "model": {
            "algorithm": model.algorithm,
            "class_order": list(model.labels),
            "feature_count": FEATURE_COUNT,
            "means": list(model.means),
            "scales": list(model.scales),
            "weights": [list(row) for row in model.weights],
            "intercepts": list(model.biases),
        },
        "provenance": {
            "dataset": {
                "take_count": len({sample.recording_id for sample in samples}),
                "group_count": len({sample.group_id for sample in samples}),
                "feature_window_count": len(samples),
                "class_window_counts": {
                    label: counts[label] for label in class_order
                },
                "source_recording_ids": sorted(
                    {sample.recording_id for sample in samples}
                ),
                "subcarrier_width_distribution": {
                    str(MODEL_SUBCARRIER_WIDTH): len(samples)
                },
            },
            "preprocessing": {
                "subcarrier_width": MODEL_SUBCARRIER_WIDTH,
                "feature_count": FEATURE_COUNT,
                "window_frames": WINDOW_FRAMES,
                "window_stride_frames": WINDOW_STRIDE,
                "amplitude_formula": "sqrt(I*I + Q*Q)",
                "band_assignment": (
                    "band = floor(subcarrier_index * 16 / 51)"
                ),
                "feature_formula": (
                    "For each 24-frame window, take 23 adjacent-frame differences "
                    "in amplitude; within each frequency band calculate mean "
                    "absolute amplitude difference over frame transitions and "
                    "subcarriers, then apply natural log1p."
                ),
                "phase_window_rule": (
                    "Keep only windows whose first and last kept frame timestamps "
                    "are inside one mapped timeline phase or annotation interval."
                ),
                "label_policy_sha256": policy_sha256,
                "label_policy": policy,
            },
            "training": {
                "implementation": "fall_detection.classifier_models.fit_classifier",
                "algorithm": "one_vs_rest_hinge_sgd",
                "optimizer": "canonical deterministic Linear SVM",
                "score_semantics": (
                    "One-vs-rest hinge margins; score_c = "
                    "dot(weights[c], standardized_features) + intercept[c]."
                ),
                "decision_rule": (
                    "argmax score in class_order; ties select the first class."
                ),
            },
            "uses_oof_fold_model": False,
            "uses_oof_predictions_as_training_input": False,
        },
    }


def run_experiment(
    recordings_dir: Path,
    policy: dict[str, Any],
    algorithm: str,
    group_by: str,
    output_dir: Path,
    fold_count: int = 5,
    fit_final: bool = False,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    class_order = tuple(policy["class_order"])
    samples, skipped = collect_phase_windows(recordings_dir, policy, group_by)
    counts = Counter(sample.label for sample in samples)
    missing = sorted(set(class_order) - counts.keys())
    if missing:
        raise ValueError("No labeled windows for classes: " + ", ".join(missing))
    predictions, metrics = evaluate_grouped(
        samples, class_order, algorithm, fold_count=fold_count
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = (
            "fold_id", "group_id", "recording_id", "activity_label", "phase",
            "frame_start", "frame_end", "true_label", "predicted_label",
            "stable_predicted_label", "scores",
        )
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in predictions:
            serialized = dict(row)
            serialized["scores"] = json.dumps(row["scores"], separators=(",", ":"))
            writer.writerow(serialized)
    summary = {
        "experiment": "phase_annotated_window_oof",
        "algorithm": algorithm,
        "group_by": group_by,
        "fold_count": fold_count,
        "class_order": list(class_order),
        "window_frames": WINDOW_FRAMES,
        "window_stride_frames": WINDOW_STRIDE,
        "window_label_rule": (
            "A window is labeled only when its first and last kept frame timestamps "
            "are inside one mapped phase or annotation interval, or inside a "
            "configured recording-tail interval through the last valid frame."
        ),
        "feature_definition": "Canonical train_activity_model.extract_window_features",
        "group_count": len({sample.group_id for sample in samples}),
        "take_count": len({sample.recording_id for sample in samples}),
        "window_counts_by_class": {label: counts[label] for label in class_order},
        "oof_metrics": metrics,
        "oof_stabilized_metrics": metrics["stabilized"],
        "temporal_stability": {
            "fall_activation": "at least 2 fall predictions in the last 3 windows",
            "fall_release": "3 consecutive non_fall predictions",
            "state_reset": "reset on a gap in labeled window indices",
            **metrics["temporal_stability"],
        },
        "skipped_take_reasons": skipped,
        "final_model_fit": fit_final,
        "final_model_exported": False,
    }
    if fit_final:
        artifact = build_final_model_artifact(
            samples, policy, policy_path, algorithm
        )
        artifact_path = output_dir / "final_model_phase_linear_svm.json"
        artifact_path.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        summary["final_model_artifact"] = str(artifact_path)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recordings", type=Path, default=DEFAULT_RECORDINGS)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--algorithm", choices=ALGORITHMS, default="linear-svm")
    parser.add_argument("--group-by", choices=("take", "session", "subject"), default="take")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--fit-final",
        action="store_true",
        help="fit and save a full-data final-model artifact after grouped OOF",
    )
    args = parser.parse_args(argv)
    try:
        summary = run_experiment(
            args.recordings,
            load_policy(args.policy),
            args.algorithm,
            args.group_by,
            args.output,
            args.folds,
            args.fit_final,
            args.policy,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
