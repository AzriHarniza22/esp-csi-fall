"""Benchmark harness shared library for the classifier comparison mandate.

Imports the CANONICAL production implementations (classifier_models,
train_activity_model, dataset_io) and never modifies them. The only local
re-implementations are:
  * a frame loader that returns amplitudes *paired with host timestamps*
    (verified bit-for-bit against the canonical reader on every take), and
  * numpy-vectorized fits for logistic-regression / linear-svm that mirror
    the canonical update math exactly (verified by equivalence_check.py).
Predictions always go through canonical `predict_scores`.
"""

from __future__ import annotations

import base64
import binascii
import csv
import datetime as dt
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from fall_detection.classifier_models import (  # noqa: E402
    ALGORITHMS,
    FEATURE_COUNT,
    RANDOM_SEED,
    ClassifierModel,
    TreeNode,
    _build_tree,
    _standardize,
    fit_classifier,
    predict_scores,
)
from fall_detection.train_activity_model import (  # noqa: E402
    CSI_SUBCARRIERS,
    WINDOW_FRAMES,
    WINDOW_STRIDE,
    _has_supported_lltf_layout,
    _lltf_pair_count,
    extract_window_features,
    read_amplitude_frames_from_frames_csv,
    render_c_header,
)
from fall_detection.dataset_io import amplitude, decode_iq  # noqa: E402

RECORDINGS = REPO / "examples/esp-radar/wifi_sensing_demo/recordings"

# Class order fixed once for all folds and algorithms (mandate §9).
CLASS_ORDER_11 = (
    "fall_forward",
    "fall_backward",
    "fall_lemas",
    "fall_keseleo",
    "walking",
    "bending",
    "fast_sitting",
    "object_drop",
    "empty_room",
    "still_standing",
    "still_sitting",
)
FALL_LABELS = {"fall_forward", "fall_backward", "fall_lemas", "fall_keseleo"}
BINARY_ORDER = ("fall", "non_fall")


def utc_ms(text: str) -> float:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000.0


def host_seconds(anchor, utc_millis: float) -> float:
    """Convert a UTC millisecond stamp to the host monotonic seconds axis
    (same formula as frames.csv: host_receive_monotonic_ns == performance.now * 1e6)."""
    return (anchor["performance_now_ms"] + (utc_millis - anchor["date_now_ms"])) / 1000.0


def load_take(meta_path: Path) -> dict:
    """Amplitude frames + host timestamps, mirroring the canonical reader's
    keep/skip decisions exactly, then verified against it."""
    tid = meta_path.name[: -len(".meta.json")]
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    frames_path = meta_path.with_name(f"{tid}.frames.csv")
    amps: list[list[float]] = []
    ts: list[float] = []
    skipped_no_payload = 0
    skipped_layout = 0
    with frames_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            text = (row.get("valid_b64") or "").strip()
            if not text or text == "na":
                skipped_no_payload += 1
                continue
            try:
                valid_bytes = base64.b64decode(text, validate=False)
            except (ValueError, binascii.Error):
                skipped_no_payload += 1
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
                supported = False
            if not supported:
                skipped_layout += 1
                continue
            pairs = decode_iq(valid_bytes, data_type)
            lltf_pairs = _lltf_pair_count(row.get("lltf_len"), data_type)
            if lltf_pairs is None:
                lltf_pairs = CSI_SUBCARRIERS
            if lltf_pairs <= 0 or len(pairs) < lltf_pairs:
                skipped_layout += 1
                continue
            values = amplitude(pairs[:lltf_pairs])
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"{tid}: non-finite CSI")
            stamp = row.get("host_receive_monotonic_ns")
            if not stamp or stamp == "na":
                raise ValueError(f"{tid}: kept frame without host timestamp")
            amps.append(values)
            ts.append(float(stamp) / 1e9)

    canonical = read_amplitude_frames_from_frames_csv(frames_path)
    if len(canonical) != len(amps):
        raise ValueError(
            f"{tid}: harness kept {len(amps)} frames, canonical reader kept {len(canonical)}"
        )
    for a, b in zip(canonical, amps):
        if a != b:  # exact equality: same inputs, same deterministic math
            raise ValueError(f"{tid}: harness amplitudes differ from canonical reader")

    # Recorder clock stamps are non-decreasing; identical stamps for adjacent
    # frames occur (coarse clock ticks) and are legitimate. Any backstep is a
    # stop-condition (§26 timestamp errors).
    reversals = sum(1 for i in range(len(ts) - 1) if ts[i + 1] < ts[i])
    if reversals:
        raise ValueError(f"{tid}: {reversals} host-timestamp reversals (non-monotonic)")
    duplicate_ts = sum(1 for i in range(len(ts) - 1) if ts[i + 1] == ts[i])

    features = extract_window_features(canonical)
    windows = []
    index = 0
    t0 = ts[0] if ts else 0.0
    for row in features:
        start = index
        end = start + WINDOW_FRAMES - 1
        windows.append(
            {
                "window_index": len(windows),
                "frame_start": start,
                "frame_end": end,
                # seconds relative to the take's first kept frame, the same
                # axis as onset_s / action_start_s / action_end_s below
                "ts_start": ts[start] - t0,
                "ts_end": ts[end] - t0,
                "values": tuple(row),
            }
        )
        index += WINDOW_STRIDE

    inter = np.diff(np.asarray(ts))
    anchor = meta.get("clock_anchor") or {}
    plan_host = None
    started = meta.get("started_at_utc") or meta.get("recording_started_at_utc")
    if anchor and started:
        plan_host = host_seconds(anchor, utc_ms(started))
    onset_host = None
    ann = meta.get("annotations") or {}
    if anchor and (ann.get("fall_start") or {}).get("timestamp_utc"):
        onset_host = host_seconds(anchor, utc_ms(ann["fall_start"]["timestamp_utc"]))
    action_end_host = None
    if anchor and plan_host is not None:
        for phase in meta.get("timeline") or []:
            if phase.get("phase") in ("fall_action", "walking") and phase.get("end_offset_s") is not None:
                action_end_host = plan_host + float(phase["end_offset_s"])
    action_start_host = None
    if anchor and plan_host is not None:
        for phase in meta.get("timeline") or []:
            if phase.get("phase") in ("fall_action", "walking") and phase.get("start_offset_s") is not None:
                action_start_host = plan_host + float(phase["start_offset_s"])

    return {
        "recording_id": tid,
        "folder": meta_path.parent.name,
        "activity_label": str(meta.get("activity_label") or ""),
        "subject_id": meta.get("subject_id"),
        "session_id": meta.get("session_id"),
        "batch_id": (meta.get("batch") or {}).get("batch_id") or meta.get("batch_id"),
        "recording_date": tid.split("_")[0][:8],
        "frames": len(amps),
        "subcarrier_width": len(amps[0]) if amps else 0,
        "skipped_no_payload": skipped_no_payload,
        "skipped_layout": skipped_layout,
        "duration_s": ts[-1] - ts[0] if ts else 0.0,
        "duplicate_ts_pairs": duplicate_ts,
        "inter_arrival_median_ms": float(np.median(inter) * 1e3) if len(ts) > 1 else None,
        "inter_arrival_p95_ms": float(np.percentile(inter, 95) * 1e3) if len(ts) > 1 else None,
        "inter_arrival_max_ms": float(inter.max() * 1e3) if len(ts) > 1 else None,
        "plan_offset_from_first_frame_s": (plan_host - ts[0]) if plan_host is not None else None,
        "onset_s": (onset_host - ts[0]) if onset_host is not None else None,
        "onset_offset_s_stored": (ann.get("fall_start") or {}).get("offset_s"),
        "action_start_s": (action_start_host - ts[0]) if action_start_host is not None else None,
        "action_end_s": (action_end_host - ts[0]) if action_end_host is not None else None,
        "windows": windows,
    }


def discover_takes() -> list[Path]:
    return sorted(RECORDINGS.rglob("*.meta.json"))


# ---------------------------------------------------------------------------
# Vectorized fits mirroring the canonical update math exactly (§6 mandate).
# ---------------------------------------------------------------------------

def _to_model(algorithm: str, class_order, means, scales, weights, biases) -> ClassifierModel:
    return ClassifierModel(
        algorithm,
        tuple(class_order),
        tuple(means),
        tuple(scales),
        weights=tuple(tuple(float(v) for v in row) for row in weights),
        biases=tuple(float(v) for v in biases),
    )


def fit_logistic_regression_np(rows, labels, class_order) -> ClassifierModel:
    means, scales, normalized = _standardize(rows)  # canonical standardizer
    X = np.asarray(normalized)
    n = X.shape[0]
    k = len(class_order)
    index = {label: i for i, label in enumerate(class_order)}
    Y = np.zeros((n, k))
    for row_i, label in enumerate(labels):
        Y[row_i, index[label]] = 1.0
    W = np.zeros((k, FEATURE_COUNT))
    b = np.zeros(k)
    learning_rate = 0.12
    regularization = 0.001
    for _ in range(700):
        logits = X @ W.T + b
        logits -= logits.max(axis=1, keepdims=True)
        exps = np.exp(logits)
        P = exps / exps.sum(axis=1, keepdims=True)
        err = P - Y
        b -= learning_rate * err.mean(axis=0)
        W -= learning_rate * (err.T @ X / n + regularization * W)
    return _to_model("logistic-regression", class_order, means, scales, W, b)


def fit_linear_svm_np(rows, labels, class_order) -> ClassifierModel:
    means, scales, normalized = _standardize(rows)  # canonical standardizer
    X = np.ascontiguousarray(np.asarray(normalized), dtype=float)
    n = X.shape[0]
    k = len(class_order)
    index = {label: i for i, label in enumerate(class_order)}
    y = np.asarray([index[label] for label in labels])
    W = np.zeros((k, FEATURE_COUNT))
    b = np.zeros(k)
    rng = random.Random(RANDOM_SEED)  # same seed, same shuffle sequence
    learning_rate = 0.08
    regularization = 0.002
    # signed[c, j] = +1 iff j == c else -1: exactly the canonical per-class
    # sign, precomputed (value-identical to np.where(arange == y[s], 1, -1))
    class_range = np.arange(k)
    signed_by_class = np.where(
        class_range[:, None] == class_range[None, :], 1.0, -1.0
    )
    signed_of_sample = signed_by_class[y]
    for epoch in range(500):
        order = list(range(n))
        rng.shuffle(order)
        rate = learning_rate / (1.0 + epoch * 0.01)
        decay = 1.0 - rate * regularization
        for sample_index in order:
            x = X[sample_index]
            signed = signed_of_sample[sample_index]
            margins = signed * (W @ x + b)
            W *= decay
            upd = signed * (rate * (margins < 1.0))
            W += x * upd[:, None]
            b += upd
    return _to_model("linear-svm", class_order, means, scales, W, b)


def fit_model_np(algorithm: str, rows, labels, class_order, mode: str = "vectorized") -> ClassifierModel:
    """Canonical for centroid/tree/forest; vectorized for the two linear
    iterative solvers when the equivalence gate passed (predictions still
    via canonical predict_scores). mode='canonical' forces canonical fits."""
    if mode == "vectorized" and algorithm == "logistic-regression":
        return fit_logistic_regression_np(rows, labels, class_order)
    if mode == "vectorized" and algorithm == "linear-svm":
        return fit_linear_svm_np(rows, labels, class_order)
    return fit_classifier(algorithm, rows, labels, class_order)


def predict_class(model: ClassifierModel, row) -> str:
    scores = predict_scores(model, row)  # canonical scorer
    return model.labels[max(range(len(scores)), key=lambda i: scores[i])]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def confusion(y_true: list[str], y_pred: list[str], order: tuple[str, ...]):
    index = {label: i for i, label in enumerate(order)}
    m = np.zeros((len(order), len(order)), dtype=int)
    for t, p in zip(y_true, y_pred):
        m[index[t], index[p]] += 1
    return m


def per_class_from_confusion(m: np.ndarray, order: tuple[str, ...]):
    rows = {}
    support = m.sum(axis=1)
    macro = {"precision": [], "recall": [], "f1": []}
    for i, label in enumerate(order):
        tp = m[i, i]
        fp = m[:, i].sum() - tp
        fn = support[i] - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(support[i]),
        }
        macro["precision"].append(precision)
        macro["recall"].append(recall)
        macro["f1"].append(f1)
    present = support > 0
    macro_f1 = float(np.mean([rows[l]["f1"] for l in order if rows[l]["support"]])) if present.any() else 0.0
    balanced = float(np.mean([rows[l]["recall"] for l in order if rows[l]["support"]])) if present.any() else 0.0
    weighted_f1 = float(np.sum(support * np.array([rows[l]["f1"] for l in order])) / support.sum()) if support.sum() else 0.0
    return rows, {
        "accuracy": float(np.trace(m) / m.sum()) if m.sum() else 0.0,
        "balanced_accuracy": balanced,
        "macro_precision": float(np.mean([macro["precision"][i] for i in range(len(order)) if support[i] > 0])),
        "macro_recall": float(np.mean([macro["recall"][i] for i in range(len(order)) if support[i] > 0])),
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
    }


def take_level_vote(window_preds: list[list[str]], order: tuple[str, ...]):
    """Majority vote per take with deterministic tie-break by fixed class
    order. Returns list of (predicted, was_tie)."""
    out = []
    for preds in window_preds:
        counts = {label: preds.count(label) for label in set(preds)}
        best = max(counts.values())
        winners = [label for label in order if counts.get(label, 0) == best]
        out.append((winners[0], len(winners) > 1))
    return out
