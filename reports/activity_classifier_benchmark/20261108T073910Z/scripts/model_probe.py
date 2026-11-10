"""Post-run diagnostics for mandate §16 (algorithm internals).

Refits each algorithm on the FULL 130-take training pool (all windows, no
holdout) purely for INTERNAL INSPECTION — these probe models are not part of
the benchmark result; every reported metric comes from the LOTO OOF CSVs.
Deterministic: same seed, same defaults, same features_cache.pkl. Cheap for
centroid/LR/tree/RF; linear-svm one fit ≈ one SVM fold.

Stability sampling (cost-bounded, all selections deterministic from seed
20261108): centroid over 15 folds (canonical, ~0.2 s/fit), decision-tree over
15 folds, LR/SVM over 5 folds. LR/SVM stability uses the gate-verified
vectorized fits (argmax-equivalent to canonical; for a stability DIAGNOSTIC
this equivalence is sufficient and one canonical SVM fit would cost ~10 min).

The features cache is a trusted local artifact built by this harness from
repo recordings (same pickle pattern as run_loto/analyze; the approved
NPZ/allow_pickle=False redesign is Fase 1 of DESIGN_APPROVED.md).

Run AFTER the A→B→BSENS chain has fully exited:
    python3 model_probe.py
"""

from __future__ import annotations

import json
import pickle
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import bench_common as bc
import run_loto

OUT = Path(__file__).resolve().parents[1]


def training_pool(spec, held=None):
    rows, labels = [], []
    for tid in spec["take_ids"]:
        if tid == held:
            continue
        label = spec["map_label"](spec["_t"][tid]["activity_label"])
        for window in spec["windows"][tid]:
            rows.append(list(window["values"]))
            labels.append(label)
    return rows, labels


def tree_stats(model) -> dict:
    nodes = model.nodes
    n = len(nodes)
    internal = [nd for nd in nodes if nd.feature >= 0]
    # actual depth via BFS over roots
    depth = 0
    frontier = list(model.tree_roots)
    while frontier:
        nxt = []
        for i in frontier:
            nd = nodes[i]
            if nd.feature >= 0:
                nxt.append(nd.left)
                nxt.append(nd.right)
        if nxt:
            depth += 1
        frontier = nxt
    return {
        "n_nodes": n,
        "n_internal": len(internal),
        "n_leaves": n - len(internal),
        "actual_depth": depth,
        "split_features": Counter(nd.feature for nd in internal),
    }


def main() -> None:
    with (OUT / "features_cache.pkl").open("rb") as handle:
        takes = pickle.load(handle)
    spec = run_loto.experiment_spec("A", takes)
    spec["_t"] = takes
    rows, labels = training_pool(spec)
    probe = {}

    for alg in run_loto.ALGORITHMS:
        model = bc.fit_classifier(alg, rows, labels, spec["class_order"])
        entry = {"n_train_rows": len(rows)}
        if alg == "nearest-centroid":
            C = np.asarray(model.centroids)
            d = np.sqrt(((C[:, None, :] - C[None, :, :]) ** 2).sum(-1))
            pairs = sorted(
                ((float(d[i, j]), spec["class_order"][i], spec["class_order"][j])
                 for i in range(len(C)) for j in range(i + 1, len(C)))
            )
            entry["centroid_distances_min3"] = pairs[:3]
            entry["centroid_distance_median"] = float(np.median([p[0] for p in pairs]))
        if alg in ("logistic-regression", "linear-svm"):
            W = np.asarray(model.weights)
            entry["weight_norm_per_class"] = {
                lab: round(float(np.linalg.norm(W[i])), 4)
                for i, lab in enumerate(spec["class_order"])
            }
            entry["biases"] = [round(float(b), 4) for b in model.biases]
            entry["mean_abs_weight"] = round(float(np.abs(W).mean()), 5)
        if alg in ("decision-tree", "random-forest"):
            entry.update({k: v for k, v in tree_stats(model).items()
                          if k != "split_features"})
            entry["top_split_features"] = tree_stats(model)["split_features"].most_common(5)
        probe[alg] = entry

    # Cross-fold stability, cost-bounded deterministic samples.
    rng = np.random.default_rng(20261108)
    n_take = len(spec["take_ids"])
    small_folds = sorted(spec["take_ids"][i] for i in
                         rng.choice(n_take, 15, replace=False))
    linear_folds = sorted(set(small_folds[:5]))
    mode = "vectorized" if run_loto.linear_mode() == "vectorized" else "canonical"
    stab: dict = defaultdict(list)
    for held in small_folds:
        r, l = training_pool(spec, held=held)
        w = spec["class_order"]
        cen = bc.fit_classifier("nearest-centroid", r, l, w)
        tr = bc.fit_classifier("decision-tree", r, l, w)
        stab["tree_root_feature"].append(tr.nodes[tr.tree_roots[0]].feature)
        stab["tree_n_nodes"].append(len(tr.nodes))
        stab["tree_top_features"].append(
            tuple(f for f, _ in Counter(
                nd.feature for nd in tr.nodes if nd.feature >= 0).most_common(3)))
        stab["centroid_norms"].append(float(np.linalg.norm(
            np.asarray(cen.centroids), axis=1).mean()))
    for held in linear_folds:
        r, l = training_pool(spec, held=held)
        w = spec["class_order"]
        stab["lr_weights"].append(np.asarray(
            bc.fit_model_np("logistic-regression", r, l, w, mode=mode).weights))
        stab["svm_weights"].append(np.asarray(
            bc.fit_model_np("linear-svm", r, l, w, mode=mode).weights))
    lr_std = svm_std = None
    if stab["lr_weights"]:
        stack = np.stack(stab["lr_weights"])
        lr_std = float(np.abs(stack.std(axis=0)).mean())
        stack = np.stack(stab["svm_weights"])
        svm_std = float(np.abs(stack.std(axis=0)).mean())
    stability = {
        "note": "centroid/tree over 15 folds, LR/SVM over 5 folds, "
                f"linear fits via mode={mode} (gate-equivalent)",
        "centroid_folds": len(stab["centroid_norms"]),
        "centroid_mean_norm_spread": [
            round(float(min(stab["centroid_norms"])), 4),
            round(float(max(stab["centroid_norms"])), 4)],
        "tree_folds": len(stab["tree_root_feature"]),
        "tree_root_feature_mode": Counter(stab["tree_root_feature"]).most_common(3),
        "tree_n_nodes_min_max": [min(stab["tree_n_nodes"]), max(stab["tree_n_nodes"])],
        "tree_top3_feature_sets_distinct": len(set(stab["tree_top_features"])),
        "lr_mean_weight_std_across5folds": lr_std,
        "svm_mean_weight_std_across5folds": svm_std,
        "svm_folds_probed": len(stab["svm_weights"]),
    }

    (OUT / "model_probe.json").write_text(json.dumps(
        {"probe_full_pool": probe, "cross_fold_stability": stability},
        indent=2, default=str))
    print(json.dumps({"probe_full_pool": probe,
                      "cross_fold_stability": stability}, indent=2, default=str))


if __name__ == "__main__":
    main()
