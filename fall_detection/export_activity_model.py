#!/usr/bin/env python3
"""Export the approved Experiment B artifact as deterministic firmware C data."""

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
    "final_model_experiment_B.json"
)
DEFAULT_HEADER = (
    REPOSITORY_ROOT
    / "examples/esp-radar/wifi_sensing_demo/main/activity_model_data.h"
)
DEFAULT_SOURCE = (
    REPOSITORY_ROOT
    / "examples/esp-radar/wifi_sensing_demo/main/activity_model_data.c"
)
EXPECTED_ARTIFACT_SHA256 = (
    "0b5662acf36c72d1c502c6f0e9169eacfc4dd3a73b33899eb239c5e25590b5cb"
)
EXPECTED_CACHE_SHA256 = (
    "e4fcbf79bcaf43685bcf4077b34ad50549a684f821786b8d042593480101495e"
)
EXPECTED_MANIFEST_SHA256 = (
    "e9842d6fd961199e29b7cd7825a160ca409e35127ab3e6e4d2027c272bbe2269"
)
EXPECTED_CLASS_ORDER = ("fall", "non_fall")
EXPECTED_FEATURE_ORDER = tuple(
    f"band_{index:02d}_log1p_mean_abs_delta" for index in range(16)
)
EXPECTED_FORMULA = (
    "For each 24-frame window, take 23 adjacent-frame differences in amplitude; "
    "within each frequency band calculate mean absolute amplitude difference "
    "over frame transitions and subcarriers, then apply natural log1p."
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite_vector(values: Any, length: int, name: str) -> list[float]:
    _require(isinstance(values, list) and len(values) == length,
             f"{name} must contain exactly {length} values")
    vector = [float(value) for value in values]
    _require(all(math.isfinite(value) for value in vector),
             f"{name} contains a non-finite value")
    return vector


def validate_artifact(artifact: dict[str, Any]) -> None:
    _require(artifact.get("artifact_type") == "final_full_fit_model",
             "Artifact is not a final full-fit model")
    _require(artifact.get("experiment_id") == "B",
             "Artifact is not Experiment B")
    model = artifact.get("model")
    _require(isinstance(model, dict), "Artifact is missing model data")
    _require(model.get("algorithm") == "linear-svm",
             "Artifact algorithm must be linear-svm")
    _require(tuple(model.get("class_order", ())) == EXPECTED_CLASS_ORDER,
             "Artifact class order must be fall, non_fall")
    _require(model.get("feature_count") == 16,
             "Artifact must contain 16 features")

    weights = model.get("weights")
    _require(isinstance(weights, list) and len(weights) == 2,
             "Artifact weights must have two class rows")
    for row_index, row in enumerate(weights):
        _finite_vector(row, 16, f"weights[{row_index}]")
    _finite_vector(model.get("intercepts"), 2, "intercepts")
    _finite_vector(model.get("means"), 16, "means")
    scales = _finite_vector(model.get("scales"), 16, "scales")
    _require(all(scale > 0.0 for scale in scales),
             "All standardization scales must be positive")

    provenance = artifact.get("provenance")
    _require(isinstance(provenance, dict), "Artifact is missing provenance")
    dataset = provenance.get("dataset")
    _require(isinstance(dataset, dict), "Artifact is missing dataset provenance")
    _require(dataset.get("feature_cache_sha256") == EXPECTED_CACHE_SHA256,
             "Artifact feature-cache hash does not match the approved snapshot")
    _require(dataset.get("manifest_sha256") == EXPECTED_MANIFEST_SHA256,
             "Artifact manifest hash does not match the approved snapshot")
    _require(dataset.get("feature_window_count") == 3088,
             "Artifact window count does not match Experiment B")
    _require(dataset.get("subcarrier_width_distribution") == {"51": 130},
             "Artifact must be fit only on 51-pair LLTF takes")

    preprocessing = provenance.get("preprocessing")
    _require(isinstance(preprocessing, dict),
             "Artifact is missing preprocessing provenance")
    _require(preprocessing.get("subcarrier_width") == 51,
             "Artifact subcarrier width must be 51")
    _require(preprocessing.get("feature_count") == 16,
             "Artifact preprocessing must produce 16 features")
    _require(preprocessing.get("window_frames") == 24,
             "Artifact window length must be 24 frames")
    _require(preprocessing.get("window_stride_frames") == 12,
             "Artifact window stride must be 12 frames")
    _require(preprocessing.get("amplitude_formula") == "sqrt(I*I + Q*Q)",
             "Artifact amplitude formula is not the approved magnitude")
    _require(preprocessing.get("band_assignment") == "band = floor(subcarrier_index * 16 / 51)",
             "Artifact band assignment is not the approved 51-pair formula")
    _require(preprocessing.get("feature_formula") == EXPECTED_FORMULA,
             "Artifact feature formula is not the approved Experiment B formula")
    feature_order = preprocessing.get("feature_order")
    _require(isinstance(feature_order, list) and len(feature_order) == 16,
             "Artifact feature order must contain 16 bands")
    _require(
        tuple(item.get("name") for item in feature_order) == EXPECTED_FEATURE_ORDER,
        "Artifact feature names/order do not match the approved band order",
    )
    for band, item in enumerate(feature_order):
        start = (band * 51 + 15) // 16
        end = ((band + 1) * 51 + 15) // 16
        _require(item.get("index") == band and
                 item.get("subcarrier_start_inclusive") == start and
                 item.get("subcarrier_end_exclusive") == end,
                 f"Artifact feature band {band} has inconsistent bounds")

    training = provenance.get("training")
    _require(isinstance(training, dict), "Artifact is missing training provenance")
    _require(training.get("implementation") == "fall_detection.classifier_models.fit_classifier",
             "Artifact was not produced by the canonical Python trainer")
    _require(training.get("algorithm") == "one_vs_rest_hinge_sgd",
             "Artifact score semantics are not one-vs-rest hinge margins")
    _require(training.get("decision_rule") ==
             "argmax score in class_order; ties select the first class.",
             "Artifact decision rule is unsupported")
    _require(training.get("score_semantics") ==
             "One-vs-rest hinge margins; score_c = dot(weights[c], standardized_features) + intercept[c].",
             "Artifact score semantics are unsupported")
    _require(provenance.get("uses_oof_fold_model") is False,
             "An OOF fold model cannot be exported as the final model")
    _require(provenance.get("uses_oof_predictions_as_training_input") is False,
             "OOF predictions cannot be exported as training input")


def _c_float(value: float) -> str:
    text = f"{value:.9g}"
    if "." not in text and "e" not in text:
        text += ".0"
    return f"{text}f"


def _c_vector(values: list[float]) -> str:
    return "{ " + ", ".join(_c_float(value) for value in values) + " }"


def render_files(artifact: dict[str, Any], artifact_sha256: str) -> tuple[str, str]:
    validate_artifact(artifact)
    model = artifact["model"]
    source = f"""/* Generated by fall_detection/export_activity_model.py; do not edit.
 * Experiment B final full-fit artifact SHA-256: {artifact_sha256}
 * Feature cache SHA-256: {EXPECTED_CACHE_SHA256}
 * Manifest SHA-256: {EXPECTED_MANIFEST_SHA256}
 * Input: ESP32 LLTF int8 pairs, physical order -26..-1,+2..+26.
 * Layout: 51 pairs / 102 bytes; first_word_invalid=true.
 * Features: 16 log1p mean absolute amplitude-delta bands; 24 frames, stride 12.
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
    header = f"""/* Generated by fall_detection/export_activity_model.py; do not edit.
 * Experiment B final full-fit artifact SHA-256: {artifact_sha256}
 */
#pragma once

#include <stdint.h>

#define ACTIVITY_MODEL_ALGORITHM_NEAREST_CENTROID 1
#define ACTIVITY_MODEL_ALGORITHM_LOGISTIC_REGRESSION 2
#define ACTIVITY_MODEL_ALGORITHM_LINEAR_SVM 3
#define ACTIVITY_MODEL_ALGORITHM_DECISION_TREE 4
#define ACTIVITY_MODEL_ALGORITHM_RANDOM_FOREST 5
#define ACTIVITY_MODEL_ALGORITHM ACTIVITY_MODEL_ALGORITHM_LINEAR_SVM
#define ACTIVITY_MODEL_NAME "linear-svm-fall-vs-non-fall-experiment-B"
#define ACTIVITY_MODEL_CLASS_COUNT 2
#define ACTIVITY_MODEL_FEATURE_COUNT 16
#define ACTIVITY_MODEL_WINDOW_FRAMES 24
#define ACTIVITY_MODEL_WINDOW_STRIDE 12
#define ACTIVITY_MODEL_SUBCARRIERS 51
#define ACTIVITY_MODEL_LLTF_BYTES 102
#define ACTIVITY_MODEL_FIRST_WORD_INVALID 1

extern const char *const activity_model_labels[ACTIVITY_MODEL_CLASS_COUNT];
extern const float activity_model_means[ACTIVITY_MODEL_FEATURE_COUNT];
extern const float activity_model_scales[ACTIVITY_MODEL_FEATURE_COUNT];
extern const float activity_model_weights[ACTIVITY_MODEL_CLASS_COUNT][ACTIVITY_MODEL_FEATURE_COUNT];
extern const float activity_model_biases[ACTIVITY_MODEL_CLASS_COUNT];
"""
    return header, source


def export(artifact_path: Path, header_path: Path, source_path: Path, check: bool) -> None:
    raw = artifact_path.read_bytes()
    artifact_sha256 = hashlib.sha256(raw).hexdigest()
    if artifact_sha256 != EXPECTED_ARTIFACT_SHA256:
        raise ValueError(
            "Refusing to export unapproved artifact hash "
            f"{artifact_sha256}; expected {EXPECTED_ARTIFACT_SHA256}"
        )
    artifact = json.loads(raw)
    if not isinstance(artifact, dict):
        raise ValueError("Artifact root must be a JSON object")
    header, source = render_files(artifact, artifact_sha256)
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
    parser.add_argument("--check", action="store_true",
                        help="fail if generated C files differ; do not write")
    args = parser.parse_args()
    try:
        export(args.artifact, args.header, args.source, args.check)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print("Model C files are current." if args.check else "Model C files exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
