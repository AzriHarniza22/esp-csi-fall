#!/usr/bin/env python3
"""Train an embedded-friendly CSI activity classifier and export it as C."""

from __future__ import annotations

import argparse
import base64
import binascii
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
from fall_detection.dataset_io import (  # noqa: E402
    LLTF_PAIRS_FLAGGED,
    LLTF_PAIRS_UNFLAGGED,
    amplitude,
    decode_iq,
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
    # The patched esp-radar drops the invalid leading int8 pair (raw bytes 2-3)
    # when first_word_invalid is true, shortening the valid payload by 2 bytes
    # for these secondary-NONE layouts. Accept both the full and the reduced
    # (2 bytes shorter) length so re-recorded takes are not silently skipped.
    if signal_mode == 0:
        return stbc == 0 and data_length in (LLTF_BYTES, LLTF_BYTES - 2)
    if signal_mode == 1:
        ht_total = LLTF_BYTES + HT_LTF_BYTES
        stbc_total = LLTF_BYTES + HT_LTF_BYTES + STBC_HT_LTF_BYTES
        if stbc == 0:
            return data_length in (ht_total, ht_total - 2)
        if stbc == 1:
            return data_length in (stbc_total, stbc_total - 2)
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


def _decode_payload(cell: str | None) -> bytes:
    text = (cell or "").strip()
    if not text or text == "na":
        return b""
    try:
        return base64.b64decode(text, validate=False)
    except (ValueError, binascii.Error):
        return b""


def _lltf_pair_count(lltf_len_cell: object, data_type: int) -> int | None:
    """Complex LLTF pairs described by the frame's ``lltf_len`` column.

    int8 stores one byte per I/Q component (2 bytes/pair); int16 stores two
    (4 bytes/pair). Returns ``None`` when the column is absent or unparseable
    so the caller can fall back to the legacy fixed width. Because the
    vendored esp-radar patch now drops the invalid leading pair when
    ``first_word_invalid`` is set, ``lltf_len`` can legitimately be 102 (51
    int8 pairs) instead of 104, so the LLTF slice must follow this value and
    never a hard-coded 52 that would bleed into the following HT-LTF segment.
    """
    text = (str(lltf_len_cell).strip() if lltf_len_cell is not None else "")
    if not text or text == "na":
        return None
    try:
        length = int(text)
    except ValueError:
        return None
    if length <= 0:
        return None
    bytes_per_pair = 4 if data_type == 1 else 2
    return length // bytes_per_pair


def read_amplitude_frames_from_frames_csv(frames_path: Path) -> list[list[float]]:
    """Amplitude frames from a v3 ``frames.csv`` (spec §4), mirroring the legacy
    ``read_amplitude_frames`` math.

    The LLTF segment is the leading ``lltf_len`` bytes of each frame's
    ``valid`` payload (``lltf_len``/2 pairs for int8, ``lltf_len``/4 for
    int16), mirroring the legacy ``read_amplitude_frames`` math. Amplitude
    (magnitude) is invariant to the imaginary/real byte order, so these
    magnitudes match the csi_data.csv path for the same supported packet
    layouts. Frames whose layout is not one of the supported LLTF/HT/STBC
    shapes are skipped, never zero-filled.
    """
    frames: list[list[float]] = []
    with frames_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None or "valid_b64" not in reader.fieldnames:
            raise ValueError(f"{frames_path}: missing frames.csv header")

        for frame_number, row in enumerate(reader, start=1):
            valid_bytes = _decode_payload(row.get("valid_b64"))
            if not valid_bytes:
                continue
            try:
                data_type = int(row.get("data_type") or 0)
            except ValueError:
                data_type = 0
            shim = {
                "sig_mode": row.get("sig_mode", ""),
                "bandwidth": row.get("bandwidth", ""),
                "stbc": row.get("stbc", ""),
                "secondary_channel": row.get("secondary_channel", ""),
                "len": row.get("valid_len", ""),
            }
            try:
                supported = _has_supported_lltf_layout(shim, list(valid_bytes))
            except ValueError:
                continue
            if not supported:
                continue
            pairs = decode_iq(valid_bytes, data_type)
            lltf_pairs = _lltf_pair_count(row.get("lltf_len"), data_type)
            if lltf_pairs is None:
                lltf_pairs = CSI_SUBCARRIERS
            if lltf_pairs <= 0 or len(pairs) < lltf_pairs:
                continue
            amplitudes = amplitude(pairs[:lltf_pairs])
            if not all(math.isfinite(value) for value in amplitudes):
                raise ValueError(
                    f"{frames_path}: non-finite CSI in frame {frame_number}"
                )
            frames.append(amplitudes)
    return frames


def extract_window_features(amplitude_frames: list[list[float]]) -> list[tuple[float, ...]]:
    """Mean log amplitude-change per fixed subcarrier band and time window.

    The subcarrier width is taken from the frames themselves rather than a
    module constant, so a recording whose LLTF was compacted to 51 pairs (a
    ``first_word_invalid`` frame under the patched esp-radar) trains alongside
    legacy 52-pair recordings. Both paths still emit ``FEATURE_COUNT`` bands.
    """
    if not amplitude_frames:
        return []
    width = len(amplitude_frames[0])
    if width <= 0:
        raise ValueError("Amplitude frames must contain at least one subcarrier")
    if any(len(frame) != width for frame in amplitude_frames):
        raise ValueError(
            "Every frame in a recording must share the same subcarrier count"
        )
    features: list[tuple[float, ...]] = []
    final_start = len(amplitude_frames) - WINDOW_FRAMES
    for start in range(0, final_start + 1, WINDOW_STRIDE):
        band_delta = [0.0] * FEATURE_COUNT
        band_counts = [0] * FEATURE_COUNT
        for frame_index in range(start + 1, start + WINDOW_FRAMES):
            previous = amplitude_frames[frame_index - 1]
            current = amplitude_frames[frame_index]
            for subcarrier in range(width):
                band = subcarrier * FEATURE_COUNT // width
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
    int,
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
    measured_widths: set[int] = set()
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
        frames_path = meta_path.with_name(f"{audit.recording_id}.frames.csv")
        csi_path = meta_path.with_name(f"{audit.recording_id}.csi_data.csv")
        if frames_path.is_file():
            frames = read_amplitude_frames_from_frames_csv(frames_path)
        elif csi_path.is_file():
            frames = read_amplitude_frames(csi_path)
        else:
            raise ValueError(
                f"Recording {audit.recording_id} has neither frames.csv nor csi_data.csv"
            )
        features = extract_window_features(frames)
        if not features:
            raise ValueError(
                f"Recording {audit.recording_id} is shorter than "
                f"{WINDOW_FRAMES} frames"
            )
        if frames:
            measured_widths.add(len(frames[0]))
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
    if len(measured_widths) > 1:
        raise ValueError(
            "Run mixes two LLTF layouts "
            f"{sorted(measured_widths)} pairs; a single exported model must "
            "be built from one layout width"
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
        measured_widths.pop() if measured_widths else CSI_SUBCARRIERS,
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


def render_c_header(
    model: ClassifierModel, source_recordings: list[str], subcarriers: int
) -> str:
    if not isinstance(subcarriers, int) or subcarriers <= 0:
        raise ValueError(
            f"render_c_header requires a positive measured subcarrier count, "
            f"got {subcarriers!r}"
        )
    lltf_bytes = subcarriers * 2
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
#define ACTIVITY_MODEL_SUBCARRIERS {subcarriers}
#define ACTIVITY_MODEL_LLTF_BYTES {lltf_bytes}

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
            model, windows, test_windows, takes_per_label, windows_per_label, measured_subcarriers = train_from_recordings(
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
                render_c_header(model, source_recordings, measured_subcarriers),
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
                f"LLTF input: {measured_subcarriers} complex samples "
                f"({measured_subcarriers * 2} bytes)"
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
