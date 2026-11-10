#!/usr/bin/env python3
"""G3/H: feature-set and algorithm comparison under whole-take group holdout.

Three feature sets per window (trainer band maths, 51-pair LLTF):
  A motion_only         : 16 log-delta bands (current deployed features)
  B profile_only        : 16 absolute log-mean-amplitude bands (session-bound,
                          shown only as a known confounded control)
  C motion + baseline-relative profile (16+16=32): relative = window profile -
                          mean of that take's windows with centre < 4 s
                          (causal: never uses data after the window's own era
                          baseline; per mandate 'baseline tanpa data masa depan')

Labels: window-level phase labels from timeline boundaries
  (fall takes: pre->non_fall_pre, action->fall_transition, post->fallen_still;
   other action takes: pre->normal_still, action->other_action, post->other_still;
   idle takes: all centre>=? -> normal_still).
Comparison targets:
  binary  fall_transition vs rest
  binary  fallen_still vs normal_still (the H2/H3 question)
  3-state normal_still / fall_transition / fallen_still (H4 question)

Evaluation: GroupShuffleSplit whole-take held out, 5 repeats, grouped by
recording id (sessions share take files; no window from a train take appears
in test). Models: logistic regression, linear SVM, RBF SVM, random forest,
ExtraTrees, KNN, gradient boosting, HistGradientBoosting, nearest centroid,
MLP (sklearn defaults, class_weight balanced where supported).

Read-only on dataset; outputs g3h_results.json.
"""
from __future__ import annotations

import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC, LinearSVC
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier, NearestCentroid
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, precision_score, recall_score
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module
d3 = import_module("03_d3_symmetric")

RECORDINGS = Path("examples/esp-radar/wifi_sensing_demo/recordings")
IDLE = d3.IDLE
FALL = d3.FALL
BOUND = {  # (pre_end, action_end) from csi_recorder.js TIMELINE_DEFS
    "fall_forward": (4, 6), "fall_backward": (4, 6),
    "walking": (3, 7), "bending": (3, 7), "fast_sitting": (3, 7), "object_drop": (3, 7),
}

def band_amplitudes(amps, width):
    """mean log amplitude per 16 bands for a list of frames (window)."""
    prof = np.mean(amps, axis=0)
    bands = np.array_split(prof[:width], 16)
    return np.array([np.log1p(b.mean()) for b in bands])

def band_delta(amps, width):
    delta = np.abs(np.diff(np.asarray(amps), axis=0))
    m = delta.mean(axis=0)
    bands = np.array_split(m[:width], 16)
    return np.array([np.log1p(b.mean()) for b in bands])

def take_feature_sets(meta_path):
    import base64, csv, math
    rec_id = meta_path.name[: -len(".meta.json")]
    meta = json.loads(meta_path.read_text())
    amps, offs = [], []
    t0 = None
    with (meta_path.parent / f"{rec_id}.frames.csv").open(encoding="utf-8", newline="") as h:
        for row in csv.DictReader(h):
            v = base64.b64decode(row["valid_b64"])
            n = int(row["lltf_len"]) // 2
            amps.append([math.hypot(v[2 * k + 1] - 256 if v[2 * k + 1] > 127 else v[2 * k + 1],
                                    v[2 * k] - 256 if v[2 * k] > 127 else v[2 * k]) for k in range(n)])
            ns = int(row["host_receive_monotonic_ns"])
            t0 = t0 or ns
            offs.append(ns / 1e9 - t0 / 1e9)
    width = min(len(a) for a in amps)
    W, S = 24, 12
    rows = []
    for s in range(0, len(amps) - W + 1, S):
        c = offs[s + W // 2]
        mot = band_delta(amps[s:s + W], width)
        prof = band_amplitudes(amps[s:s + W], width)
        rows.append((c, mot, prof))
    if not rows:
        return None
    base = np.mean([p for c, m, p in rows if c < 4], axis=0)
    return meta["activity_label"], [(c, m, p, p - base) for c, m, p in rows]

def phase_label(label, c):
    if label in IDLE:
        return "normal_still"
    pre_end, act_end = BOUND[label]
    if c < pre_end + 0.6:      # centre-based with small guard
        return "normal_still" if not label.startswith("fall") else "normal_still"
    if c < act_end + 0.6:
        return "fall_transition" if label in FALL else "other_action"
    return "fallen_still" if label in FALL else "other_still"

MODELS = {
    "logistic": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
    "linear-svm": lambda: make_pipeline(StandardScaler(), LinearSVC(class_weight="balanced", max_iter=5000)),
    "rbf-svm": lambda: make_pipeline(StandardScaler(), SVC(class_weight="balanced")),
    "random-forest": lambda: RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=0),
    "extra-trees": lambda: ExtraTreesClassifier(n_estimators=300, class_weight="balanced", random_state=0),
    "knn": lambda: make_pipeline(StandardScaler(), KNeighborsClassifier(5)),
    "grad-boosting": lambda: GradientBoostingClassifier(random_state=0),
    "hist-gb": lambda: HistGradientBoostingClassifier(random_state=0),
    "nearest-centroid": lambda: make_pipeline(StandardScaler(), NearestCentroid()),
    "mlp": lambda: make_pipeline(StandardScaler(), MLPClassifier(max_iter=1500, random_state=0)),
    "lda": lambda: make_pipeline(StandardScaler(), LinearDiscriminantAnalysis()),
}

def run_task(data, groups, feat_key, pairs, task_name):
    X, y, g = [], [], []
    for rec, label, rows in data:
        for c, mot, prof, rel in rows:
            lab = phase_label(label, c)
            mapping = pairs.get(lab)
            if mapping is None:
                continue
            if feat_key == "A":
                f = mot
            elif feat_key == "B":
                f = prof
            elif feat_key == "C":
                f = np.concatenate([mot, rel])
            elif feat_key == "D":
                f = np.concatenate([mot, rel[:8]])
            X.append(f); y.append(mapping); g.append(rec)
    X = np.array(X); y = np.array(y); g = np.array(g)
    if len(set(y)) < 2:
        return None
    res = {"task": task_name, "featset": feat_key, "n": int(len(X)),
           "class_counts": {k: int(v) for k, v in zip(*np.unique(y, return_counts=True))}}
    gss = GroupShuffleSplit(n_splits=5, test_size=0.25, random_state=0)
    per_model = {}
    splits = list(gss.split(X, y, g))
    for name, ctor in MODELS.items():
        accs, bals, f1s, precs, recs = [], [], [], [], []
        for tr, te in splits:
            if len(set(y[tr])) < 2:
                continue
            m = ctor()
            try:
                m.fit(X[tr], y[tr])
                pred = m.predict(X[te])
            except Exception as exc:  # noqa: BLE001
                per_model[name] = {"error": str(exc)[:80]}
                continue
            accs.append(accuracy_score(y[te], pred))
            bals.append(balanced_accuracy_score(y[te], pred))
            f1s.append(f1_score(y[te], pred, average="binary", pos_label="fall"))
            precs.append(precision_score(y[te], pred, average="binary", pos_label="fall", zero_division=0))
            recs.append(recall_score(y[te], pred, average="binary", pos_label="fall", zero_division=0))
        if accs:
            per_model[name] = {
                "accuracy": round(float(np.mean(accs)), 3),
                "balanced_acc": round(float(np.mean(bals)), 3),
                "fall_F1": round(float(np.mean(f1s)), 3),
                "fall_precision": round(float(np.mean(precs)), 3),
                "fall_recall": round(float(np.mean(recs)), 3),
                "folds": len(accs),
            }
    res["models"] = per_model
    return res

def main():
    warnings.filterwarnings("ignore")
    data = []
    for meta_path in sorted(RECORDINGS.rglob("*.meta.json")):
        got = take_feature_sets(meta_path)
        if got:
            data.append((meta_path.name, *got))
    tasks = [
        ("falling_vs_rest", {
            "fall_transition": "fall", "other_action": "non_fall",
            "normal_still": "non_fall", "fallen_still": "non_fall", "other_still": "non_fall"}),
        ("fallen_still_vs_normal_still", {
            "fallen_still": "fall", "normal_still": "non_fall"}),
    ]
    all_res = []
    for tname, pairs in tasks:
        for fk in ("A", "B", "C", "D"):
            r = run_task(data, None, fk, pairs, tname)
            if r:
                all_res.append(r)
                print(f"[{tname}][{fk}] n={r['n']} classes={r['class_counts']}")
                best = sorted(((v.get('balanced_acc', 0), k) for k, v in r['models'].items() if 'balanced_acc' in v), reverse=True)[:4]
                print("   top balanced_acc:", [(k, b) for b, k in best])
    (OUT / "g3h_results.json").write_text(json.dumps(all_res, indent=1))

if __name__ == "__main__":
    main()
