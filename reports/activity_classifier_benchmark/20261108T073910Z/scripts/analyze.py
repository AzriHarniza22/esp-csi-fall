"""Aggregate pooled OOF metrics, take-level votes, confusions, CI and complexity.

All metrics are computed from predictions_oof.csv (one evaluation per window
per experiment/algorithm, out-of-fold). Window-level metrics pool every OOF
window; take-level metrics use deterministic majority vote over each take's
OOF window predictions with ties broken by the fixed class order (§7).
Bootstrap CIs resample TAKES only (mandate §19).

Run from the scripts directory:
    python3 analyze.py
"""

from __future__ import annotations

import csv
import json
import pickle
from collections import defaultdict
from pathlib import Path

import numpy as np

import bench_common as bc
import run_loto

OUT = Path(__file__).resolve().parents[1]
BOOTSTRAP_SEED = 20261108
BOOTSTRAP_N = 1000
ALGORITHMS = run_loto.ALGORITHMS


def load_predictions():
    rows = list(csv.DictReader((OUT / "predictions_oof.csv").open()))
    by_key = defaultdict(list)
    for row in rows:
        by_key[(row["experiment_id"], row["algorithm"])].append(row)
    return by_key


def to_binary(label: str) -> str:
    return "fall" if label in bc.FALL_LABELS or label == "fall" else "non_fall"


def window_metrics(pred_rows, order):
    y_true = [r["true_class"] for r in pred_rows]
    y_pred = [r["predicted_class"] for r in pred_rows]
    m = bc.confusion(y_true, y_pred, order)
    per_class, overall = bc.per_class_from_confusion(m, order)
    return m, per_class, overall, y_true, y_pred


def take_votes(pred_rows, order):
    grouped = defaultdict(list)
    truth = {}
    for row in pred_rows:
        grouped[row["recording_id"]].append(row["predicted_class"])
        truth[row["recording_id"]] = row["true_class"]
    votes = {}
    ties = 0
    for rid, preds in grouped.items():
        predicted, was_tie = bc.take_level_vote([preds], order)[0]
        votes[rid] = predicted
        ties += was_tie
    return votes, truth, ties


def binary_rates(votes, truth):
    fall = [rid for rid, t in truth.items() if t == "fall"]
    non = [rid for rid, t in truth.items() if t == "non_fall"]
    tp = sum(votes[r] == "fall" for r in fall)
    fp = sum(votes[r] == "fall" for r in non)
    return {
        "n_fall_takes": len(fall),
        "n_non_fall_takes": len(non),
        "fall_recall_take": tp / len(fall) if fall else None,
        "non_fall_fpr_take": fp / len(non) if non else None,
        "missed_fall_takes": len(fall) - tp,
    }


def bootstrap_take_ci(votes, truth, rng):
    ids = sorted(truth)
    correct = np.array([float(votes[r] == truth[r]) for r in ids])
    is_fall = np.array([truth[r] == "fall" for r in ids])
    pred_fall = np.array([votes[r] == "fall" for r in ids])
    n = len(ids)
    accs, recalls, fprs = [], [], []
    for _ in range(BOOTSTRAP_N):
        # Generator.integers is high-EXCLUSIVE: range must be [0, n), otherwise
        # the last take would never be resampled.
        pick = rng.integers(0, n, n)
        accs.append(correct[pick].mean())
        f = is_fall[pick]
        nf = ~is_fall[pick]
        recalls.append(pred_fall[pick][f].mean() if f.any() else np.nan)
        fprs.append(pred_fall[pick][nf].mean() if nf.any() else np.nan)
    ci = lambda a: (float(np.nanpercentile(a, 2.5)), float(np.nanpercentile(a, 97.5)))
    return {"accuracy_ci95": ci(accs), "fall_recall_ci95": ci(recalls), "fpr_ci95": ci(fprs)}


def main() -> None:
    with (OUT / "features_cache.pkl").open("rb") as handle:
        takes = pickle.load(handle)
    by_key = load_predictions()
    rng = np.random.default_rng(BOOTSTRAP_SEED)

    results_rows = []
    per_class_rows = []
    confusion_writer_targets = {}

    def order_for(experiment):
        return bc.CLASS_ORDER_11 if experiment == "A" else bc.BINARY_ORDER

    def record(experiment, algorithm, unit, m, per_class, overall, votes=None,
               truth=None, ties=None, ci=None, note=""):
        row = {
            "experiment_id": experiment,
            "algorithm": algorithm,
            "unit": unit,
            "accuracy": round(overall["accuracy"], 4),
            "balanced_accuracy": round(overall["balanced_accuracy"], 4),
            "macro_precision": round(overall["macro_precision"], 4),
            "macro_recall": round(overall["macro_recall"], 4),
            "macro_f1": round(overall["macro_f1"], 4),
            "weighted_f1": round(overall["weighted_f1"], 4),
            "n_eval_units": m.sum(),
            "take_vote_ties": ties if ties is not None else "",
        }
        if experiment != "A" and votes is not None:
            row.update(
                {k: (round(v, 4) if isinstance(v, float) else v)
                 for k, v in binary_rates(votes, truth).items()}
            )
        if ci:
            row["accuracy_ci95_low"] = round(ci["accuracy_ci95"][0], 4)
            row["accuracy_ci95_high"] = round(ci["accuracy_ci95"][1], 4)
            if row.get("fall_recall_take") is not None:
                row["fall_recall_ci95"] = f"{ci['fall_recall_ci95'][0]:.4f}..{ci['fall_recall_ci95'][1]:.4f}"
                row["fpr_ci95"] = f"{ci['fpr_ci95'][0]:.4f}..{ci['fpr_ci95'][1]:.4f}"
        row["note"] = note
        results_rows.append(row)
        for label, stats in per_class.items():
            per_class_rows.append({
                "experiment_id": experiment, "algorithm": algorithm, "unit": unit,
                "class": label,
                "precision": round(stats["precision"], 4),
                "recall": round(stats["recall"], 4),
                "f1": round(stats["f1"], 4),
                "support": stats["support"],
            })

    # ------------------------------------------------------------------
    for (experiment, algorithm), pred_rows in sorted(by_key.items()):
        if not pred_rows:
            continue
        order = order_for(experiment)
        m, per_class, overall, _, _ = window_metrics(pred_rows, order)
        record(experiment, algorithm, "window", m, per_class, overall)
        votes, truth, ties = take_votes(pred_rows, order)
        tm = bc.confusion([truth[r] for r in truth], [votes[r] for r in truth], order)
        t_per_class, t_overall = bc.per_class_from_confusion(tm, order)
        ci = bootstrap_take_ci(votes, truth, rng) if order is bc.BINARY_ORDER else None
        record(experiment, algorithm, "take", tm, t_per_class, t_overall,
               votes=votes, truth=truth, ties=ties, ci=ci)
        subdir = {"A": "multiclass", "B": "binary", "BSENS": "binary", "C": "hardcase"}[experiment]
        np.savetxt(
            OUT / "confusion_matrices" / subdir / f"{algorithm}_{experiment}_window.csv",
            m, fmt="%d", delimiter=",", header=",".join(order), comments="",
        )
        np.savetxt(
            OUT / "confusion_matrices" / subdir / f"{algorithm}_{experiment}_take.csv",
            tm, fmt="%d", delimiter=",", header=",".join(order), comments="",
        )
        if experiment == "A":
            bm = bc.confusion(
                [to_binary(t) for t in truth.values()],
                [to_binary(votes[r]) for r in truth],
                bc.BINARY_ORDER,
            )
            b_pc, b_ov = bc.per_class_from_confusion(bm, bc.BINARY_ORDER)
            b_votes = {r: to_binary(v) for r, v in votes.items()}
            b_truth = {r: to_binary(t) for r, t in truth.items()}
            record("A_binary_comparator", algorithm, "take", bm, b_pc, b_ov,
                   votes=b_votes, truth=b_truth, ties="",
                   ci=bootstrap_take_ci(b_votes, b_truth, rng),
                   note="multiclass-to-binary mapping of experiment A OOF votes")

    # ------------------------------------------------------------------
    # missed fall takes per manner (take-level, all multiclass/binary views)
    missed = defaultdict(lambda: defaultdict(int))
    taken_counts = defaultdict(lambda: defaultdict(int))
    for (experiment, algorithm), pred_rows in by_key.items():
        order = order_for(experiment)
        votes, truth, _ = take_votes(pred_rows, order)
        label_of = {row["recording_id"]: row["activity_label"] for row in pred_rows}
        for rid, vote in votes.items():
            lab = label_of[rid]
            if lab in bc.FALL_LABELS:
                taken_counts[(experiment, algorithm)][lab] += 1
                if to_binary(vote) != "fall":
                    missed[(experiment, algorithm)][lab] += 1
    with (OUT / "missed_fall_takes.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["experiment_id", "algorithm", "fall_manner",
                         "fall_takes", "missed_takes", "take_recall"])
        for key, counts in sorted(missed.items()):
            for manner in sorted(bc.FALL_LABELS):
                if taken_counts[key][manner]:
                    writer.writerow([
                        key[0], key[1], manner, taken_counts[key][manner],
                        counts.get(manner, 0),
                        round(1 - counts.get(manner, 0) / taken_counts[key][manner], 4),
                    ])

    # ------------------------------------------------------------------
    # model complexity from fold results
    folds = list(csv.DictReader((OUT / "fold_results.csv").open()))
    comp = defaultdict(lambda: defaultdict(list))
    fit_seconds = defaultdict(list)
    for row in folds:
        key = (row["experiment_id"], row["algorithm"])
        for field in ("n_model_params", "n_tree_nodes", "header_bytes"):
            if row[field] not in ("", None):
                comp[key][field].append(float(row[field]))
        fit_seconds[key].append(float(row["fit_seconds"]))
    with (OUT / "model_complexity.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["experiment_id", "algorithm", "metric", "median", "p95", "max"])
        for key, fields in sorted(comp.items()):
            for field, values in fields.items():
                arr = np.asarray(values)
                writer.writerow([
                    key[0], key[1], field,
                    round(float(np.median(arr)), 2),
                    round(float(np.percentile(arr, 95)), 2),
                    round(float(arr.max()), 2),
                ])
            arr = np.asarray(fit_seconds[key])
            writer.writerow([
                key[0], key[1], "fit_seconds",
                round(float(np.median(arr)), 3),
                round(float(np.percentile(arr, 95)), 3),
                round(float(arr.max()), 3),
            ])

    # ------------------------------------------------------------------
    # window-duration statistics actually covered by the canonical grid
    durations = defaultdict(list)
    for take in takes.values():
        for w in take["windows"]:
            durations["all"].append(w["ts_end"] - w["ts_start"])
    spec_c = run_loto.experiment_spec("C", takes)
    for tid, wins in spec_c["windows"].items():
        for w in wins:
            durations["C"].append(w["ts_end"] - w["ts_start"])
    window_duration_rows = []
    for group, values in durations.items():
        arr = np.asarray(values)
        window_duration_rows.append({
            "group": group, "n_windows": len(arr),
            "median_s": round(float(np.median(arr)), 3),
            "p95_s": round(float(np.percentile(arr, 95)), 3),
            "max_s": round(float(arr.max()), 3),
        })
    with (OUT / "window_duration_stats.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(window_duration_rows[0]))
        writer.writeheader()
        writer.writerows(window_duration_rows)

    # ------------------------------------------------------------------
    # Experiment C descriptive: what happens AFTER action_end (8-12s band)
    # in the keseleo takes, using experiment A OOF window predictions only.
    post = defaultdict(lambda: defaultdict(int))
    for (experiment, algorithm), pred_rows in by_key.items():
        if experiment != "A":
            continue
        by_rec = defaultdict(list)
        for row in pred_rows:
            by_rec[row["recording_id"]].append(row)
        for rid, rows in by_rec.items():
            take = takes[rid]
            if take["activity_label"] != "fall_keseleo" or take.get("action_end_s") is None:
                continue
            end = take["action_end_s"]
            windows_by_index = {w["window_index"]: w for w in take["windows"]}
            for row in rows:
                w = windows_by_index[int(row["window_index"])]
                if w["ts_start"] >= end and w["ts_end"] <= end + 4.0:
                    post[algorithm]["n_windows"] += 1
                    post[algorithm][row["predicted_class"]] += 1
    with (OUT / "hardcase_post_action_descriptive.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        classes = list(bc.CLASS_ORDER_11)
        writer.writerow(["algorithm", "band", "n_windows_8_12s_after_action", *classes])
        for algorithm, counts in sorted(post.items()):
            writer.writerow([algorithm, "post_action_8_12s", counts["n_windows"],
                             *[counts.get(c, 0) for c in classes]])

    # ------------------------------------------------------------------
    # feature distribution analysis inputs (per-band magnitude stats per label)
    feats = defaultdict(list)
    for take in takes.values():
        for w in take["windows"]:
            feats[take["activity_label"]].append(np.asarray(w["values"]))
    label_order = list(bc.CLASS_ORDER_11)
    with (OUT / "feature_stats_by_label.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["activity_label", "feature_band", "n_windows",
                         "mean", "std", "p10", "p50", "p90"])
        for label in label_order:
            if label not in feats:
                continue
            arr = np.stack(feats[label])
            for band in range(arr.shape[1]):
                col = arr[:, band]
                writer.writerow([
                    label, band, len(col),
                    round(float(col.mean()), 4), round(float(col.std()), 4),
                    round(float(np.percentile(col, 10)), 4),
                    round(float(np.percentile(col, 50)), 4),
                    round(float(np.percentile(col, 90)), 4),
                ])
    # global standardizer (all windows) for reference in feature_analysis.md
    all_rows = [list(w["values"]) for t in takes.values() for w in t["windows"]]
    means, scales, _ = bc._standardize(all_rows)
    (OUT / "feature_standardizer_global.json").write_text(json.dumps(
        {"feature_count": bc.FEATURE_COUNT, "n_windows": len(all_rows),
         "means": [round(v, 6) for v in means], "scales": [round(v, 6) for v in scales]},
        indent=2))

    # ------------------------------------------------------------------
    def write_results(path, experiment_filter):
        rows = [r for r in results_rows if r["experiment_id"] == experiment_filter]
        if not rows:
            return
        fields = sorted({k for r in rows for k in r})
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    write_results(OUT / "multiclass_results.csv", "A")
    rows_b = [r for r in results_rows if r["experiment_id"] in ("B", "BSENS", "A_binary_comparator")]
    if rows_b:
        fields = sorted({k for r in rows_b for k in r})
        with (OUT / "binary_results.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows_b)
    write_results(OUT / "hardcase_results.csv", "C")
    with (OUT / "per_class_metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_class_rows[0]))
        writer.writeheader()
        writer.writerows(per_class_rows)

    print(f"analyzed {len(by_key)} experiment/algorithm pairs, "
          f"{len(results_rows)} result rows")


if __name__ == "__main__":
    main()
