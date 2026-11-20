#!/usr/bin/env python3
"""Export a final phase-aware Linear SVM artifact as firmware C data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT = (
    REPOSITORY_ROOT
    / "reports/activity_classifier_benchmark/20261108T073910Z/"
    "phase_aware_run_20261114_stabilized/final_model_phase_linear_svm.json"
)
DEFAULT_HEADER = (
    REPOSITORY_ROOT
    / "examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h"
)
DEFAULT_SOURCE = (
    REPOSITORY_ROOT
    / "examples/esp-radar/wifi_sensing_demo/main/activity_model_data.c"
)
CLASS_ORDER = ("fall", "non_fall")
FEATURE_COUNT = 16
WINDOW_FRAMES = 24
WINDOW_STRIDE = 12
SUBCARRIER_WIDTH = 51
LLTF_BYTES = 102
MODEL_NAME = "linear-svm-phase-fall-start-to-impact-v1"
BAND_ASSIGNMENT = "band = floor(subcarrier_index * 16 / 51)"
FEATURE_FORMULA = (
    "For each 24-frame window, take 23 adjacent-frame differences in amplitude; "
    "within each frequency band calculate mean absolute amplitude difference "
    "over frame transitions and subcarriers, then apply natural log1p."
)
SCORE_SEMANTICS = (
    "One-vs-rest hinge margins; score_c = "
    "dot(weights[c], standardized_features) + intercept[c]."
)
DECISION_RULE = "argmax score in class_order; ties select the first class."


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite_vector(values: Any, length: int, name: str) -> list[float]:
    _require(
        isinstance(values, list) and len(values) == length,
        f"{name} must contain exactly {length} values",
    )
    vector = [float(value) for value in values]
    _require(all(math.isfinite(value) for value in vector), f"{name} is non-finite")
    return vector


def validate_artifact(artifact: dict[str, Any]) -> None:
    _require(
        artifact.get("artifact_type") == "final_full_fit_model"
        and artifact.get("experiment_id") == "PHASE",
        "Artifact is not a final phase-aware full-fit model",
    )
    model = artifact.get("model")
    _require(isinstance(model, dict), "Artifact is missing model data")
    _require(model.get("algorithm") == "linear-svm", "Algorithm must be linear-svm")
    _require(
        tuple(model.get("class_order", ())) == CLASS_ORDER,
        "Class order must be fall, non_fall",
    )
    _require(model.get("feature_count") == FEATURE_COUNT, "Feature count must be 16")
    _require(
        isinstance(model.get("weights"), list) and len(model["weights"]) == 2,
        "Weights must contain two class rows",
    )
    for row_index, row in enumerate(model["weights"]):
        _finite_vector(row, FEATURE_COUNT, f"weights[{row_index}]")
    _finite_vector(model.get("intercepts"), 2, "intercepts")
    _finite_vector(model.get("means"), FEATURE_COUNT, "means")
    scales = _finite_vector(model.get("scales"), FEATURE_COUNT, "scales")
    _require(all(scale > 0.0 for scale in scales), "Scales must be positive")

    provenance = artifact.get("provenance")
    _require(isinstance(provenance, dict), "Artifact is missing provenance")
    dataset = provenance.get("dataset")
    _require(isinstance(dataset, dict), "Artifact is missing dataset metadata")
    feature_window_count = dataset.get("feature_window_count")
    _require(
        type(feature_window_count) is int and feature_window_count > 0,
        "Artifact has no training windows",
    )
    _require(
        dataset.get("subcarrier_width_distribution")
        == {str(SUBCARRIER_WIDTH): feature_window_count},
        "Artifact must use 51-pair LLTF inputs",
    )
    preprocessing = provenance.get("preprocessing")
    _require(isinstance(preprocessing, dict), "Artifact is missing preprocessing")
    for key, expected in (
        ("subcarrier_width", SUBCARRIER_WIDTH),
        ("feature_count", FEATURE_COUNT),
        ("window_frames", WINDOW_FRAMES),
        ("window_stride_frames", WINDOW_STRIDE),
        ("amplitude_formula", "sqrt(I*I + Q*Q)"),
        ("band_assignment", BAND_ASSIGNMENT),
        ("feature_formula", FEATURE_FORMULA),
    ):
        _require(preprocessing.get(key) == expected, f"Unsupported {key}")
    training = provenance.get("training")
    _require(isinstance(training, dict), "Artifact is missing training provenance")
    _require(
        training.get("implementation")
        == "fall_detection.classifier_models.fit_classifier",
        "Model was not produced by the canonical trainer",
    )
    _require(
        training.get("algorithm") == "one_vs_rest_hinge_sgd",
        "Unsupported Linear SVM training algorithm",
    )
    _require(
        training.get("score_semantics") == SCORE_SEMANTICS
        and training.get("decision_rule") == DECISION_RULE,
        "Unsupported score or decision semantics",
    )
    _require(
        provenance.get("uses_oof_fold_model") is False
        and provenance.get("uses_oof_predictions_as_training_input") is False,
        "An OOF model or OOF predictions cannot be exported",
    )


def _c_float(value: float) -> str:
    text = f"{value:.9g}"
    if "." not in text and "e" not in text:
        text += ".0"
    return text + "f"


def _c_vector(values: list[float]) -> str:
    return "{ " + ", ".join(_c_float(value) for value in values) + " }"


def render_files(
    artifact: dict[str, Any], artifact_sha256: str
) -> tuple[str, str]:
    validate_artifact(artifact)
    model = artifact["model"]
    policy_hash = artifact["provenance"]["preprocessing"]["label_policy_sha256"]
    source = f"""/* Generated by fall_detection/export_phase_activity_model.py; do not edit.
 * Phase-aware full-fit artifact SHA-256: {artifact_sha256}
 * Label policy SHA-256: {policy_hash}
 * Input: ESP32 LLTF int8 pairs, 51 pairs / 102 bytes.
 * Features: 16 log1p mean absolute amplitude-delta bands; 24 frames, stride 12.
 * Training labels: fall_start-to-fall_impact = fall; mapped normal phases = non_fall.
 * Scores: one-vs-rest hinge margins in order fall, non_fall; ties choose fall.
 */
#include "activity_model_data.h"

const char *const activity_model_labels[ACTIVITY_MODEL_CLASS_COUNT] = {{
    "fall", "non_fall"
}};

const float activity_model_means[ACTIVITY_MODEL_FEATURE_COUNT] =
    {_c_vector(model["means"])};

const float activity_model_scales[ACTIVITY_MODEL_FEATURE_COUNT] =
    {_c_vector(model["scales"])};

const float activity_model_weights[ACTIVITY_MODEL_CLASS_COUNT][ACTIVITY_MODEL_FEATURE_COUNT] = {{
    {_c_vector(model["weights"][0])},
    {_c_vector(model["weights"][1])}
}};

const float activity_model_biases[ACTIVITY_MODEL_CLASS_COUNT] =
    {_c_vector(model["intercepts"])};
"""
    header = f"""/* Generated by fall_detection/export_phase_activity_model.py; do not edit.
 * Phase-aware full-fit artifact SHA-256: {artifact_sha256}
 */
#pragma once

#include <stdint.h>

#define ACTIVITY_MODEL_ALGORITHM_NEAREST_CENTROID 1
#define ACTIVITY_MODEL_ALGORITHM_LOGISTIC_REGRESSION 2
#define ACTIVITY_MODEL_ALGORITHM_LINEAR_SVM 3
#define ACTIVITY_MODEL_ALGORITHM_DECISION_TREE 4
#define ACTIVITY_MODEL_ALGORITHM_RANDOM_FOREST 5
#define ACTIVITY_MODEL_ALGORITHM ACTIVITY_MODEL_ALGORITHM_LINEAR_SVM
#define ACTIVITY_MODEL_NAME "{MODEL_NAME}"
#define ACTIVITY_MODEL_CLASS_COUNT 2
#define ACTIVITY_MODEL_FALL_CLASS_INDEX 0
#define ACTIVITY_MODEL_NON_FALL_CLASS_INDEX 1
#define ACTIVITY_MODEL_FEATURE_COUNT {FEATURE_COUNT}
#define ACTIVITY_MODEL_WINDOW_FRAMES {WINDOW_FRAMES}
#define ACTIVITY_MODEL_WINDOW_STRIDE {WINDOW_STRIDE}
#define ACTIVITY_MODEL_SUBCARRIERS {SUBCARRIER_WIDTH}
#define ACTIVITY_MODEL_LLTF_BYTES {LLTF_BYTES}
#define ACTIVITY_MODEL_FIRST_WORD_INVALID 1

extern const char *const activity_model_labels[ACTIVITY_MODEL_CLASS_COUNT];
extern const float activity_model_means[ACTIVITY_MODEL_FEATURE_COUNT];
extern const float activity_model_scales[ACTIVITY_MODEL_FEATURE_COUNT];
extern const float activity_model_weights[ACTIVITY_MODEL_CLASS_COUNT][ACTIVITY_MODEL_FEATURE_COUNT];
extern const float activity_model_biases[ACTIVITY_MODEL_CLASS_COUNT];
"""
    return header, source


def export(
    artifact_path: Path, header_path: Path, source_path: Path, check: bool
) -> None:
    raw = artifact_path.read_bytes()
    artifact = json.loads(raw)
    if not isinstance(artifact, dict):
        raise ValueError("Artifact root must be a JSON object")
    digest = hashlib.sha256(raw).hexdigest()
    header, source = render_files(artifact, digest)
    if check:
        stale = []
        if not header_path.is_file() or header_path.read_text(encoding="utf-8") != header:
            stale.append(str(header_path))
        if not source_path.is_file() or source_path.read_text(encoding="utf-8") != source:
            stale.append(str(source_path))
        if stale:
            raise ValueError("Generated model files are stale: " + ", ".join(stale))
        return
    header_path.write_text(header, encoding="utf-8")
    source_path.write_text(source, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--header", type=Path, default=DEFAULT_HEADER)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        export(args.artifact, args.header, args.source, args.check)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print("Phase model C files are current." if args.check else "Phase model C files exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
