"""Equivalence gate: vectorized LR/SVM fits vs the canonical pure-Python fits.

The LOTO benchmark needs ~130 fits per algorithm. The canonical iterative
fits are pure Python and too slow for that many folds, so bench_common
provides numpy mirrors of the identical update math (per-class updates are
independent within a sample, so simultaneous vectorization == sequential
canonical loops; the SVM shuffle sequence is reproduced with the same
random.Random(RANDOM_SEED) stream).

This script is the gate: for logistic-regression and linear-svm it fits both
implementations on several training sizes and compares weights and canonical
predictions. The benchmark may use the vectorized fits ONLY if this gate
passes; otherwise those algorithms must fall back to canonical fits and the
reduced scope must be reported (mandate §26 stop-conditions / honesty rules).

Run (background recommended; the full-size canonical fits take minutes):
    python3 equivalence_check.py
"""

from __future__ import annotations

import json
import pickle
import time
from pathlib import Path

import bench_common as bc

OUT = Path(__file__).resolve().parents[1]


def dataset_from(takes, holdout: str, limit_takes: int | None = None):
    rows, labels = [], []
    used = 0
    for tid in sorted(takes):
        if tid == holdout:
            continue
        if limit_takes is not None and used >= limit_takes:
            continue
        take = takes[tid]
        used += 1
        for window in take["windows"]:
            rows.append(list(window["values"]))
            labels.append(take["activity_label"])
    return rows, labels


def compare(alg: str, takes, holdout: str, limit_takes: int | None):
    rows, labels = dataset_from(takes, holdout, limit_takes)
    class_order = bc.CLASS_ORDER_11
    t0 = time.time()
    canonical = bc.fit_classifier(alg, rows, labels, class_order)
    canonical_s = time.time() - t0
    t0 = time.time()
    fast = (
        bc.fit_logistic_regression_np
        if alg == "logistic-regression"
        else bc.fit_linear_svm_np
    )(rows, labels, class_order)
    vectorized_s = time.time() - t0

    max_dw = max(
        abs(a - b)
        for ra, rb in zip(canonical.weights, fast.weights)
        for a, b in zip(ra, rb)
    )
    max_db = max(abs(a - b) for a, b in zip(canonical.biases, fast.biases))
    max_dm = max(abs(a - b) for a, b in zip(canonical.means, fast.means))
    max_ds = max(abs(a - b) for a, b in zip(canonical.scales, fast.scales))

    agree = total = 0
    holdout_agree = holdout_total = 0
    mismatches = []
    for tid, take in takes.items():
        for window in take["windows"]:
            pc = bc.predict_class(canonical, window["values"])
            pf = bc.predict_class(fast, window["values"])
            total += 1
            if pc == pf:
                agree += 1
            else:
                mismatches.append((tid, window["window_index"], pc, pf))
            if tid == holdout:
                holdout_total += 1
                holdout_agree += pc == pf

    return {
        "algorithm": alg,
        "train_rows": len(rows),
        "holdout": holdout,
        "canonical_fit_seconds": round(canonical_s, 2),
        "vectorized_fit_seconds": round(vectorized_s, 2),
        "max_abs_delta_weights": max_dw,
        "max_abs_delta_biases": max_db,
        "max_abs_delta_means": max_dm,
        "max_abs_delta_scales": max_ds,
        "holdout_windows": holdout_total,
        "holdout_argmax_agreement": holdout_agree / holdout_total if holdout_total else None,
        "all_windows": total,
        "all_argmax_agreement": agree / total if total else None,
        "example_mismatches": mismatches[:10],
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--algorithms", default="logistic-regression,linear-svm",
        help="comma-separated subset to (re)validate; records for other "
             "algorithms are merged from an existing equivalence_check.json",
    )
    args = parser.parse_args()
    wanted = [a.strip() for a in args.algorithms.split(",") if a.strip()]

    with (OUT / "features_cache.pkl").open("rb") as handle:
        takes = pickle.load(handle)

    old_records = []
    if (OUT / "equivalence_check.json").exists():
        old_records = json.loads(
            (OUT / "equivalence_check.json").read_text()).get("records", [])

    holdout = "20261107T101217Z_fall_keseleo_006"
    if holdout not in takes:
        holdout = sorted(takes)[0]
    records = []
    for alg in ("logistic-regression", "linear-svm"):
        if alg not in wanted:
            records.extend(r for r in old_records if r["algorithm"] == alg)
            continue
        for limit, tag in ((8, "subset8"), (32, "subset32"), (None, "full_fold")):
            print(f"{alg} {tag} ...", flush=True)
            rec = compare(alg, takes, holdout, limit)
            rec["scale"] = tag
            records.append(rec)
            print(json.dumps(rec, indent=2), flush=True)

    gate = records and all(
        r["holdout_argmax_agreement"] == 1.0 and r["all_argmax_agreement"] >= 0.995
        for r in records
    )
    summary = {"records": records, "gate_passed": gate}
    (OUT / "equivalence_check.json").write_text(json.dumps(summary, indent=2))
    print("GATE PASSED" if gate else "GATE FAILED - fall back to canonical fits")


if __name__ == "__main__":
    main()
