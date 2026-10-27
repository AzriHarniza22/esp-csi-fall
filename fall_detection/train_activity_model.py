#!/usr/bin/env python3
"""Train an embedded-friendly CSI activity classifier and export it as C."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

FEATURE_COUNT = 16
WINDOW_FRAMES = 24
WINDOW_STRIDE = 12
CSI_SUBCARRIERS = 52
LLTF_BYTES = CSI_SUBCARRIERS * 2
HT_LTF_BYTES = 112
STBC_HT_LTF_BYTES = 112
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
from fall_detection.audit_dataset import audit_take  # noqa: E402
from fall_detection.classifier_models import (  # noqa: E402
    ALGORITHMS,
    ClassifierModel,
    TreeNode,
    fit_classifier,
    predict_scores,
)


DEFAULT_RECORDINGS = (
    REPOSITORY_ROOT / "examples/esp-radar/wifi_sensing_demo/recordings"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h"
)
CLASS_PATTERN = re.compile(r"^([^=,]+)=([^,]+(?:,[^,]+)*)$")
C_IDENTIFIER = re.compile(r"[^A-Za-z0-9_]")


@dataclass(frozen=True)
class FeatureWindow:
    recording_id: str
    label: str
    values: tuple[float, ...]


def parse_class_spec(spec: str) -> tuple[str, tuple[str, ...]]:
    match = CLASS_PATTERN.fullmatch(spec.strip())
    if match is None:
        raise ValueError(
            f"Invalid class specification {spec!r}; expected NAME=LABEL[,LABEL]"
        )
    class_name = match.group(1).strip()
    labels = tuple(label.strip() for label in match.group(2).split(","))
    if not class_name or any(not label for label in labels):
        raise ValueError(f"Invalid empty class or label in {spec!r}")
    return class_name, labels


def _has_supported_lltf_layout(row: dict[str, str], values: list[int]) -> bool:
    try:
        signal_mode = int(row["sig_mode"])
        bandwidth = int(row["bandwidth"])
        stbc = int(row["stbc"])
        secondary_channel = int(row["secondary_channel"])
        data_length = int(row["len"])
    except (KeyError, ValueError) as exc:
        raise ValueError("CSI_DATA row is missing valid packet metadata") from exc

    if bandwidth != 0 or secondary_channel != 0 or len(values) != data_length:
        return False
    if signal_mode == 0:
        return stbc == 0 and data_length == LLTF_BYTES
    if signal_mode == 1:
        return (stbc == 0 and data_length == LLTF_BYTES + HT_LTF_BYTES) or (
            stbc == 1
            and data_length == LLTF_BYTES + HT_LTF_BYTES + STBC_HT_LTF_BYTES
        )
    return False


def read_amplitude_frames(csi_data_path: Path) -> list[list[float]]:
    frames: list[list[float]] = []
    with csi_data_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None or "data" not in reader.fieldnames:
            raise ValueError(f"{csi_data_path}: missing CSI_DATA header")

        for frame_number, row in enumerate(reader, start=1):
            try:
                values = [int(value) for value in row["data"].split(",")]
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"{csi_data_path}: invalid CSI values in frame {frame_number}"
                ) from exc
            if not _has_supported_lltf_layout(row, values):
                continue
            if len(values) < LLTF_BYTES:
                continue

            amplitudes: list[float] = []
            for subcarrier in range(CSI_SUBCARRIERS):
                real = float(values[subcarrier * 2])
                imag = float(values[subcarrier * 2 + 1])
                amplitudes.append(math.hypot(real, imag))
            if not all(math.isfinite(value) for value in amplitudes):
                raise ValueError(
                    f"{csi_data_path}: non-finite CSI in frame {frame_number}"
                )
            frames.append(amplitudes)
    return frames


def extract_window_features(amplitude_frames: list[list[float]]) -> list[tuple[float, ...]]:
    """Mean log amplitude-change per fixed subcarrier band and time window."""
    if any(len(frame) != CSI_SUBCARRIERS for frame in amplitude_frames):
        raise ValueError(f"Every frame must contain {CSI_SUBCARRIERS} subcarriers")
    features: list[tuple[float, ...]] = []
    final_start = len(amplitude_frames) - WINDOW_FRAMES
    for start in range(0, final_start + 1, WINDOW_STRIDE):
        band_delta = [0.0] * FEATURE_COUNT
        band_counts = [0] * FEATURE_COUNT
        for frame_index in range(start + 1, start + WINDOW_FRAMES):
            previous = amplitude_frames[frame_index - 1]
            current = amplitude_frames[frame_index]
            for subcarrier in range(CSI_SUBCARRIERS):
                band = subcarrier * FEATURE_COUNT // CSI_SUBCARRIERS
                band_delta[band] += abs(current[subcarrier] - previous[subcarrier])
                band_counts[band] += 1
        features.append(
            tuple(
                math.log1p(band_delta[index] / max(1, band_counts[index]))
                for index in range(FEATURE_COUNT)
            )
        )
    return features


def train_from_recordings(
    recordings_dir: Path,
    class_specs: list[str],
    algorithm: str = "nearest-centroid",
    test_take_ids: set[str] | None = None,
) -> tuple[
    ClassifierModel,
    list[FeatureWindow],
    list[FeatureWindow],
    tuple[int, ...],
    tuple[int, ...],
]:
    parsed = [parse_class_spec(spec) for spec in class_specs]
    class_order = tuple(name for name, _ in parsed)
    if len(set(class_order)) != len(class_order):
        raise ValueError("Output class names must be unique")
    label_to_class = {
        label: class_name
        for class_name, source_labels in parsed
        for label in source_labels
    }
    if len(label_to_class) != sum(len(labels) for _, labels in parsed):
        raise ValueError("A source label may be assigned to only one output class")

    windows: list[FeatureWindow] = []
    takes_per_label: dict[str, set[str]] = defaultdict(set)
    found_labels: set[str] = set()
    for meta_path in sorted(recordings_dir.rglob("*.meta.json")):
        audit = audit_take(meta_path)
        if audit.label not in label_to_class:
            continue
        found_labels.add(audit.label)
        if not audit.eligible:
            raise ValueError(
                f"Recording {audit.recording_id} is not eligible: "
                + "; ".join(audit.reasons)
            )
        frames = read_amplitude_frames(
            meta_path.with_name(f"{audit.recording_id}.csi_data.csv")
        )
        features = extract_window_features(frames)
        if not features:
            raise ValueError(
                f"Recording {audit.recording_id} is shorter than "
                f"{WINDOW_FRAMES} frames"
            )
        class_name = label_to_class[audit.label]
        takes_per_label[class_name].add(audit.recording_id)
        windows.extend(
            FeatureWindow(audit.recording_id, class_name, feature)
            for feature in features
        )

    missing_source_labels = sorted(set(label_to_class) - found_labels)
    if missing_source_labels:
        raise ValueError(
            "No eligible recording found for source labels: "
            + ", ".join(missing_source_labels)
        )
    found_take_ids = {window.recording_id for window in windows}
    if test_take_ids:
        missing_test_takes = sorted(test_take_ids - found_take_ids)
        if missing_test_takes:
            raise ValueError(
                "Requested test take(s) were not found for the selected classes: "
                + ", ".join(missing_test_takes)
            )
        test_windows = [
            window for window in windows if window.recording_id in test_take_ids
        ]
        training_windows = [
            window for window in windows if window.recording_id not in test_take_ids
        ]
    else:
        test_windows = []
        training_windows = windows

    grouped_windows: dict[str, list[FeatureWindow]] = defaultdict(list)
    training_takes: dict[str, set[str]] = defaultdict(set)
    for window in training_windows:
        grouped_windows[window.label].append(window)
        training_takes[window.label].add(window.recording_id)
    missing = [label for label in class_order if not grouped_windows[label]]
    if missing:
        raise ValueError(
            f"No training windows for classes: {', '.join(missing)}; "
            "keep at least one complete take per class in the training split"
        )
    model = fit_classifier(
        algorithm,
        [window.values for window in training_windows],
        [window.label for window in training_windows],
        class_order,
    )
    return (
        model,
        training_windows,
        test_windows,
        tuple(len(training_takes[label]) for label in class_order),
        tuple(len(grouped_windows[label]) for label in class_order),
    )


def _c_float(value: float) -> str:
    formatted = f"{value:.9g}"
    if "." not in formatted and "e" not in formatted:
        formatted += ".0"
    return f"{formatted}f"


def _render_nodes(nodes: tuple[TreeNode, ...]) -> str:
    return ",\n".join(
        f"    {{{node.feature}, {_c_float(node.threshold)}, "
        f"{node.left}, {node.right}, {node.prediction}}}"
        for node in nodes
    )


def render_c_header(model: ClassifierModel, source_recordings: list[str]) -> str:
    labels = ", ".join(json.dumps(label) for label in model.labels)
    source_list = ", ".join(source_recordings)
    algorithm_ids = {
        "nearest-centroid": 1,
        "logistic-regression": 2,
        "linear-svm": 3,
        "decision-tree": 4,
        "random-forest": 5,
    }
    output = f"""/* Generated by fall_detection/train_activity_model.py; do not edit by hand.
 * Experimental take-level labels; overlapping windows are correlated and are
 * not independent validation samples.
 * Source take IDs: {source_list}
 */
#pragma once

#include <stdint.h>

#define ACTIVITY_MODEL_ALGORITHM_NEAREST_CENTROID 1
#define ACTIVITY_MODEL_ALGORITHM_LOGISTIC_REGRESSION 2
#define ACTIVITY_MODEL_ALGORITHM_LINEAR_SVM 3
#define ACTIVITY_MODEL_ALGORITHM_DECISION_TREE 4
#define ACTIVITY_MODEL_ALGORITHM_RANDOM_FOREST 5
#define ACTIVITY_MODEL_ALGORITHM {algorithm_ids[model.algorithm]}
#define ACTIVITY_MODEL_NAME {json.dumps(model.algorithm)}
#define ACTIVITY_MODEL_CLASS_COUNT {len(model.labels)}
#define ACTIVITY_MODEL_FEATURE_COUNT {FEATURE_COUNT}
#define ACTIVITY_MODEL_WINDOW_FRAMES {WINDOW_FRAMES}
#define ACTIVITY_MODEL_WINDOW_STRIDE {WINDOW_STRIDE}
#define ACTIVITY_MODEL_SUBCARRIERS {CSI_SUBCARRIERS}
#define ACTIVITY_MODEL_LLTF_BYTES {LLTF_BYTES}

static const char *const activity_model_labels[ACTIVITY_MODEL_CLASS_COUNT] = {{{labels}}};
static const float activity_model_means[ACTIVITY_MODEL_FEATURE_COUNT] = {{{", ".join(_c_float(value) for value in model.means)}}};
static const float activity_model_scales[ACTIVITY_MODEL_FEATURE_COUNT] = {{{", ".join(_c_float(value) for value in model.scales)}}};
"""
    if model.algorithm == "nearest-centroid":
        rows = ",\n".join(
            "    {" + ", ".join(_c_float(value) for value in row) + "}"
            for row in model.centroids
        )
        output += f"""
static const float activity_model_centroids[ACTIVITY_MODEL_CLASS_COUNT][ACTIVITY_MODEL_FEATURE_COUNT] = {{
{rows}
}};
"""
    elif model.algorithm in {"logistic-regression", "linear-svm"}:
        rows = ",\n".join(
            "    {" + ", ".join(_c_float(value) for value in row) + "}"
            for row in model.weights
        )
        output += f"""
static const float activity_model_weights[ACTIVITY_MODEL_CLASS_COUNT][ACTIVITY_MODEL_FEATURE_COUNT] = {{
{rows}
}};
static const float activity_model_biases[ACTIVITY_MODEL_CLASS_COUNT] = {{{", ".join(_c_float(value) for value in model.biases)}}};
"""
    else:
        output += f"""
#define ACTIVITY_MODEL_NODE_COUNT {len(model.nodes)}
#define ACTIVITY_MODEL_TREE_COUNT {len(model.tree_roots)}
typedef struct {{
    int16_t feature;
    float threshold;
    int16_t left;
    int16_t right;
    int16_t prediction;
}} activity_model_node_t;
static const activity_model_node_t activity_model_nodes[ACTIVITY_MODEL_NODE_COUNT] = {{
{_render_nodes(model.nodes)}
}};
static const int16_t activity_model_tree_roots[ACTIVITY_MODEL_TREE_COUNT] = {{{", ".join(str(root) for root in model.tree_roots)}}};
"""
    return output


def print_grouped_evaluation(
    model: ClassifierModel, test_windows: list[FeatureWindow]
) -> None:
    if not test_windows:
        return
    counts = {
        (actual, predicted): 0
        for actual in model.labels
        for predicted in model.labels
    }
    for window in test_windows:
        predicted = max(
            range(len(model.labels)),
            key=lambda index: predict_scores(model, window.values)[index],
        )
        counts[(window.label, model.labels[predicted])] += 1

    total = len(test_windows)
    correct = sum(counts[(label, label)] for label in model.labels)
    f1_values = []
    test_take_count = len({window.recording_id for window in test_windows})
    print(f"Grouped holdout: {total} windows from {test_take_count} take(s)")
    print(f"Accuracy: {correct / total:.3f}")
    for label in model.labels:
        true_positive = counts[(label, label)]
        false_positive = sum(
            counts[(actual, label)] for actual in model.labels if actual != label
        )
        false_negative = sum(
            counts[(label, predicted)]
            for predicted in model.labels
            if predicted != label
        )
        precision_denominator = true_positive + false_positive
        recall_denominator = true_positive + false_negative
        precision = true_positive / precision_denominator if precision_denominator else 0.0
        recall = true_positive / recall_denominator if recall_denominator else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        f1_values.append(f1)
        support = sum(counts[(label, predicted)] for predicted in model.labels)
        print(
            f"- {label}: precision={precision:.3f} recall={recall:.3f} "
            f"F1={f1:.3f} support={support}"
        )
    print(f"Macro-F1: {sum(f1_values) / len(f1_values):.3f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recordings-dir", type=Path, default=DEFAULT_RECORDINGS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--algorithm",
        choices=(*ALGORITHMS, "all"),
        default="nearest-centroid",
        help="embedded classifier to train and export, or all to compare and export variants",
    )
    parser.add_argument(
        "--test-take",
        dest="test_takes",
        action="append",
        default=[],
        help="hold out this recording ID for whole-take evaluation; repeat as needed",
    )
    parser.add_argument(
        "--class",
        dest="classes",
        action="append",
        required=True,
        metavar="NAME=LABEL[,LABEL]",
        help="map one or more recording labels to an output class; repeat per class",
    )
    args = parser.parse_args(argv)

    algorithms = ALGORITHMS if args.algorithm == "all" else (args.algorithm,)
    if args.algorithm == "all" and not args.test_takes:
        parser.error("--algorithm all requires at least one --test-take")

    try:
        for algorithm in algorithms:
            model, windows, test_windows, takes_per_label, windows_per_label = train_from_recordings(
                args.recordings_dir, args.classes, algorithm, set(args.test_takes)
            )
            if args.algorithm == "all":
                held_out_labels = {window.label for window in test_windows}
                missing_test_labels = sorted(set(model.labels) - held_out_labels)
                if missing_test_labels:
                    raise ValueError(
                        "Algorithm comparison requires held-out takes for every "
                        "class; missing: " + ", ".join(missing_test_labels)
                    )
                output_path = args.output.with_name(
                    f"{args.output.stem}_{algorithm.replace('-', '_')}{args.output.suffix}"
                )
            else:
                output_path = args.output

            source_recordings = sorted({window.recording_id for window in windows})
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                render_c_header(model, source_recordings),
                encoding="utf-8",
            )

            print(
                f"Experimental {model.algorithm} model trained; "
                "this is not a claim of validation."
            )
            print(f"Output: {output_path}")
            for index, label in enumerate(model.labels):
                print(
                    f"- {label}: {takes_per_label[index]} training take(s), "
                    f"{windows_per_label[index]} overlapping windows"
                )
            print(f"Feature vector: {FEATURE_COUNT} log amplitude-change bands")
            print(
                f"Window: {WINDOW_FRAMES} frames, stride {WINDOW_STRIDE} frames; "
                f"LLTF input: {CSI_SUBCARRIERS} complex samples "
                f"({LLTF_BYTES} bytes)"
            )
            if test_windows:
                print_grouped_evaluation(model, test_windows)
            else:
                print("WARNING: no held-out takes; these training results are not evaluation.")
            print(
                "WARNING: one recording session per class can produce "
                "take-specific overfit."
            )
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Training failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
