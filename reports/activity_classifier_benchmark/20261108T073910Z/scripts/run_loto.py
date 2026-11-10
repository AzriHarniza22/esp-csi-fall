"""LOTO benchmark runner for experiments A, B, BSENS and C.

Isolated harness (mandate §7): never touches production training code paths;
reads only features_cache.pkl built from the canonical extractor, fits via
bench_common (canonical for centroid/tree/forest; LR/SVM per the
equivalence-check gate), and scores exclusively via canonical
predict_scores. Failed folds are written to failed_folds.csv and reported,
never hidden (§26).

Run from the scripts directory:
    python3 run_loto.py --experiment A
    python3 run_loto.py --experiment B
    python3 run_loto.py --experiment BSENS
    python3 run_loto.py --experiment C
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
import os
import pickle
import time
from collections import Counter
from pathlib import Path

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")  # tiny matrices; avoid BLAS thread noise

import bench_common as bc

OUT = Path(__file__).resolve().parents[1]
ALGORITHMS = (
    "nearest-centroid",
    "logistic-regression",
    "linear-svm",
    "decision-tree",
    "random-forest",
)
SEMANTICS = {
    "nearest-centroid": "negative_squared_euclidean_distance_standardized",
    "logistic-regression": "softmax_logits",
    "linear-svm": "one_vs_rest_hinge_margins",
    "decision-tree": "leaf_class_indicator",
    "random-forest": "tree_vote_counts",
}

FOLD_FIELDS = [
    "experiment_id", "algorithm", "fold_id", "n_train_windows", "n_test_windows",
    "window_accuracy", "take_vote_predicted", "take_vote_tie",
    "fit_seconds", "fold_seconds", "n_model_params", "n_tree_nodes", "header_bytes",
]
PRED_FIELDS = [
    "experiment_id", "algorithm", "fold_id", "recording_id", "activity_label",
    "true_class", "predicted_class", "window_index",
    "timestamp_start_s", "timestamp_end_s", "feature_validity",
    "score_semantics", "raw_scores_json", "predicted_score",
]

_CACHE: dict = {}


def _binary_label(label: str) -> str:
    return "fall" if label in bc.FALL_LABELS else "non_fall"


def select_take_windows(take, experiment: str):
    """Return the windows used by each experiment (mandate §5, §12, §13)."""
    if experiment in ("A", "B", "BSENS"):
        return list(take["windows"])
    if experiment == "C":
        if take["activity_label"] == "fall_keseleo":
            onset, end = take["onset_s"], take["action_end_s"]
            return [
                w for w in take["windows"]
                if onset is not None and end is not None
                and w["ts_start"] >= onset and w["ts_end"] <= end
            ]
        if take["activity_label"] == "walking":
            start, end = take["action_start_s"], take["action_end_s"]
            return [
                w for w in take["windows"]
                if start is not None and end is not None
                and w["ts_start"] >= start and w["ts_end"] <= end
            ]
        return []
    raise ValueError(f"unknown experiment {experiment}")


def experiment_spec(experiment: str, takes: dict):
    if experiment == "C":
        ids = sorted(
            tid for tid, t in takes.items()
            if t["activity_label"] in ("fall_keseleo", "walking")
        )
        class_order = bc.BINARY_ORDER
        map_label = _binary_label
    elif experiment in ("B", "BSENS"):
        ids = sorted(
            tid for tid, t in takes.items()
            if experiment == "B" or t["recording_date"] == "20261104"
        )
        class_order = bc.BINARY_ORDER
        map_label = _binary_label
    elif experiment == "A":
        ids = sorted(takes)
        class_order = bc.CLASS_ORDER_11
        map_label = lambda label: label  # noqa: E731
    else:
        raise ValueError(experiment)
    windows = {tid: select_take_windows(takes[tid], experiment) for tid in ids}
    return {
        "experiment": experiment,
        "take_ids": ids,
        "class_order": class_order,
        "map_label": map_label,
        "windows": windows,
    }


def linear_mode() -> str:
    path = OUT / "equivalence_check.json"
    if not path.exists():
        return "canonical"
    data = json.loads(path.read_text())
    return "vectorized" if data.get("gate_passed") else "canonical"


def _init(experiment: str):
    global _CACHE
    with (OUT / "features_cache.pkl").open("rb") as handle:
        takes = pickle.load(handle)
    _CACHE = {"takes": takes, "spec": experiment_spec(experiment, takes),
              "mode": linear_mode()}


def _model_stats(model) -> tuple[int, int, int]:
    if model.weights:
        params = len(model.weights) * len(model.weights[0]) + len(model.biases)
    elif model.centroids:
        params = len(model.centroids) * len(model.centroids[0]) + len(model.biases)
    else:
        params = len(model.nodes) * 5
    header = bc.render_c_header(model, ["harness"], 51)
    return params, len(model.nodes), len(header.encode("utf-8"))


def run_fold(task):
    algorithm, held = task
    takes, spec, mode = _CACHE["takes"], _CACHE["spec"], _CACHE["mode"]
    t0 = time.time()
    rows, labels = [], []
    for tid in spec["take_ids"]:
        if tid == held:
            continue
        take = takes[tid]
        label = spec["map_label"](take["activity_label"])
        for window in spec["windows"][tid]:
            rows.append(list(window["values"]))
            labels.append(label)
    test_take = takes[held]
    test_label = spec["map_label"](test_take["activity_label"])
    model = bc.fit_model_np(
        algorithm, rows, labels, spec["class_order"], mode=mode
    )
    fit_s = time.time() - t0

    preds = []
    correct = 0
    for window in spec["windows"][held]:
        scores = bc.predict_scores(model, list(window["values"]))
        best = max(range(len(scores)), key=lambda i: scores[i])
        predicted = spec["class_order"][best]
        correct += predicted == test_label
        preds.append(
            {
                "experiment_id": spec["experiment"],
                "algorithm": algorithm,
                "fold_id": held,
                "recording_id": held,
                "activity_label": test_take["activity_label"],
                "true_class": test_label,
                "predicted_class": predicted,
                "window_index": window["window_index"],
                "timestamp_start_s": round(window["ts_start"] - test_take["windows"][0]["ts_start"], 4),
                "timestamp_end_s": round(window["ts_end"] - test_take["windows"][0]["ts_start"], 4),
                "feature_validity": "valid",
                "score_semantics": SEMANTICS[algorithm],
                "raw_scores_json": json.dumps([round(s, 6) for s in scores]),
                "predicted_score": round(scores[best], 6),
            }
        )
    n_test = len(preds)
    window_labels = [p["predicted_class"] for p in preds]
    vote, tie = bc.take_level_vote([window_labels], spec["class_order"])[0]
    params, nodes, header_bytes = _model_stats(model)
    fold = {
        "experiment_id": spec["experiment"],
        "algorithm": algorithm,
        "fold_id": held,
        "n_train_windows": len(rows),
        "n_test_windows": n_test,
        "window_accuracy": round(correct / n_test, 6) if n_test else "",
        "take_vote_predicted": vote,
        "take_vote_tie": tie,
        "fit_seconds": round(fit_s, 3),
        "fold_seconds": round(time.time() - t0, 3),
        "n_model_params": params,
        "n_tree_nodes": nodes,
        "header_bytes": header_bytes,
    }
    return fold, preds


def resume_complete_keys():
    """Trust only folds present in fold_results.csv AND with their full
    prediction rows in predictions_oof.csv; rewrite both files dropping any
    inconsistent tail from an interrupted run (no fold is ever hidden — the
    dropped work is simply re-run)."""
    fold_path = OUT / "fold_results.csv"
    pred_path = OUT / "predictions_oof.csv"
    if not fold_path.exists() or not pred_path.exists():
        return set()
    folds = list(csv.DictReader(fold_path.open()))
    preds = list(csv.DictReader(pred_path.open()))
    counts = Counter(
        (p["experiment_id"], p["algorithm"], p["fold_id"]) for p in preds
    )
    complete = set()
    for row in folds:
        key = (row["experiment_id"], row["algorithm"], row["fold_id"])
        if counts.get(key, 0) == int(row["n_test_windows"]):
            complete.add(key)
    keep_folds = [
        r for r in folds
        if (r["experiment_id"], r["algorithm"], r["fold_id"]) in complete
    ]
    keep_preds = [
        p for p in preds
        if (p["experiment_id"], p["algorithm"], p["fold_id"]) in complete
    ]
    if len(keep_folds) != len(folds) or len(keep_preds) != len(preds):
        for path, rows, fields in (
            (fold_path, keep_folds, FOLD_FIELDS),
            (pred_path, keep_preds, PRED_FIELDS),
        ):
            tmp = path.with_suffix(path.suffix + ".tmp")
            with tmp.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(tmp, path)
        print(
            f"resume: dropped {len(folds) - len(keep_folds)} incomplete fold "
            f"rows and {len(preds) - len(keep_preds)} orphan prediction rows",
            flush=True,
        )
    return complete


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True, choices=("A", "B", "BSENS", "C"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--fresh", action="store_true",
                        help="ignore existing fold/prediction CSVs for this experiment")
    args = parser.parse_args()

    with (OUT / "features_cache.pkl").open("rb") as handle:
        takes = pickle.load(handle)
    spec = experiment_spec(args.experiment, takes)
    mode = linear_mode()
    print(
        f"experiment {args.experiment}: {len(spec['take_ids'])} takes, "
        f"{sum(len(v) for v in spec['windows'].values())} windows, "
        f"linear_mode={mode}",
        flush=True,
    )
    # Sanity: every fold's training set must retain every class (§26).
    for held in spec["take_ids"]:
        train_labels = {
            spec["map_label"](takes[tid]["activity_label"])
            for tid in spec["take_ids"]
            if tid != held and spec["windows"][tid]
        }
        missing = set(spec["class_order"]) - train_labels
        if missing:
            print(f"STOP-CONDITION: fold {held} loses training class(es) {sorted(missing)}")
            raise SystemExit(2)

    fold_path = OUT / "fold_results.csv"
    pred_path = OUT / "predictions_oof.csv"
    fail_path = OUT / "failed_folds.csv"
    new_fold = not fold_path.exists()
    new_pred = not pred_path.exists()
    new_fail = not fail_path.exists()
    fold_f = fold_path.open("a", newline="")
    pred_f = pred_path.open("a", newline="")
    fold_w = csv.DictWriter(fold_f, fieldnames=FOLD_FIELDS)
    pred_w = csv.DictWriter(pred_f, fieldnames=PRED_FIELDS)
    if new_fold:
        fold_w.writeheader()
    if new_pred:
        pred_w.writeheader()

    tasks = [(alg, held) for alg in ALGORITHMS for held in spec["take_ids"]]
    if not args.fresh:
        complete = resume_complete_keys()
        before = len(tasks)
        tasks = [
            t for t in tasks
            if (spec["experiment"], t[0], t[1]) not in complete
        ]
        if before - len(tasks):
            print(f"resume: skipping {before - len(tasks)} already-complete folds",
                  flush=True)
    done = failed = 0
    t0 = time.time()
    with multiprocessing.Pool(
        processes=args.workers, initializer=_init, initargs=(args.experiment,)
    ) as pool:
        for result in pool.imap_unordered(_fold_guarded, tasks, chunksize=1):
            kind, payload = result
            done += 1
            if kind == "ok":
                fold, preds = payload
                fold_w.writerow(fold)
                pred_w.writerows(preds)
            else:
                if new_fail and not fail_path.exists():
                    with fail_path.open("w", newline="") as f:
                        csv.writer(f).writerow(
                            ["experiment_id", "algorithm", "fold_id", "error"]
                        )
                with fail_path.open("a", newline="") as f:
                    csv.writer(f).writerow([args.experiment, *payload])
                failed += 1
            if done % 10 == 0 or done == len(tasks):
                fold_f.flush()
                pred_f.flush()
                print(
                    f"{done}/{len(tasks)} folds ({failed} failed) "
                    f"elapsed={time.time() - t0:.0f}s",
                    flush=True,
                )
    fold_f.close()
    pred_f.close()
    print(f"experiment {args.experiment} complete: {done} folds, {failed} failed")


def _fold_guarded(task):
    try:
        return "ok", run_fold(task)
    except Exception as exc:  # never hide a failed fold (§26)
        import traceback

        traceback.print_exc()
        return "fail", (task[1], task[0], f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
