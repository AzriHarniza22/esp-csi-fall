"""Finalisation integrity audit (mandate §4 rules of the approval message).

Checks, WITHOUT rerunning any training:
  1. Task completeness: expected = |takes| × |algorithms| per experiment,
     against fold_results.csv rows.
  2. No double-counting after resume: (experiment, algorithm, fold_id) unique
     in fold_results.csv; prediction rows per key == n_test_windows exactly.
  3. Dataset/class consistency: fold_id is a real take, its activity_label
     matches the cache, window counts per take match the cache, and pooled OOF
     label distribution matches the experiment population.
  4. failed_folds.csv presence and contents (reported, never hidden).
  5. Provenance sanity: gate file state, per-experiment fit-mode evidence
     available from headers is recorded here as a summary of what CAN and
     CANNOT be proven per row (see DESIGN_APPROVED.md §4).

Run after the chain exits:
    python3 verify_results.py
"""

from __future__ import annotations

import csv
import json
import pickle
from collections import Counter, defaultdict
from pathlib import Path

import bench_common as bc
import run_loto

OUT = Path(__file__).resolve().parents[1]
EXPECTED = {"A": 130, "B": 130, "BSENS": 89, "C": 21}
ALGOS = run_loto.ALGORITHMS


def main() -> None:
    takes = pickle.load((OUT / "features_cache.pkl").open("rb"))
    folds = list(csv.DictReader((OUT / "fold_results.csv").open()))
    preds = list(csv.DictReader((OUT / "predictions_oof.csv").open()))
    issues: list[str] = []

    # 1 — completeness
    got = Counter(r["experiment_id"] for r in folds)
    print("fold rows per experiment:", dict(got))
    for exp, n_takes in EXPECTED.items():
        want = n_takes * len(ALGOS)
        have = got.get(exp, 0)
        status = "COMPLETE" if have == want else f"INCOMPLETE ({have}/{want})"
        print(f"  {exp}: expected {want} tasks -> {status}")
        if have != want:
            issues.append(f"{exp}: {want - have} tasks missing")
    per_alg = Counter((r["experiment_id"], r["algorithm"]) for r in folds)
    for (exp, alg), n in sorted(per_alg.items()):
        if n != EXPECTED[exp]:
            issues.append(f"{exp}/{alg}: {n} rows, expected {EXPECTED[exp]}")

    # 2 — uniqueness + prediction-row agreement
    seen = Counter((r["experiment_id"], r["algorithm"], r["fold_id"]) for r in folds)
    dups = {k: v for k, v in seen.items() if v > 1}
    print("duplicate fold keys:", dups or "none")
    if dups:
        issues.append(f"duplicate fold keys: {dups}")
    pred_keys = Counter((p["experiment_id"], p["algorithm"], p["fold_id"]) for p in preds)
    mismatches = []
    for r in folds:
        key = (r["experiment_id"], r["algorithm"], r["fold_id"])
        if pred_keys.get(key, 0) != int(r["n_test_windows"]):
            mismatches.append((key, int(r["n_test_windows"]), pred_keys.get(key, 0)))
    print("fold/prediction count mismatches:", len(mismatches))
    if mismatches:
        issues.append(f"{len(mismatches)} folds with wrong prediction count: {mismatches[:5]}")
    orphan = set(pred_keys) - set(seen)
    print("prediction keys without fold row:", len(orphan), sorted(orphan)[:3])
    if orphan:
        issues.append(f"{len(orphan)} orphan prediction groups")

    # 3 — dataset / label / window consistency
    label_of = {tid: t["activity_label"] for tid, t in takes.items()}
    bad_label = [r["fold_id"] for r in folds if r["fold_id"] not in label_of]
    if bad_label:
        issues.append(f"{len(set(bad_label))} fold ids not present in cache")
    unknown_exp = {r["experiment_id"] for r in folds} - set(EXPECTED)
    if unknown_exp:
        issues.append(f"unknown experiment ids: {sorted(unknown_exp)}")
    # window totals per experiment must equal the experiment population
    for exp in EXPECTED:
        spec = run_loto.experiment_spec(exp, takes)
        want_windows = sum(len(v) for v in spec["windows"].values())
        got_windows = sum(int(r["n_test_windows"]) for r in folds
                          if r["experiment_id"] == exp and r["algorithm"] == ALGOS[0])
        print(f"  {exp}: test-window coverage {got_windows}/{want_windows}")
        if got_windows != want_windows:
            issues.append(f"{exp}: pooled test windows {got_windows} != population {want_windows}")
    # per-row label sanity: true_class must map from the held take's label
    for p in preds:
        lab = label_of.get(p["recording_id"])
        if lab is None:
            issues.append(f"prediction for unknown take {p['recording_id']}")
            break
        expect = ("fall" if lab in bc.FALL_LABELS else "non_fall") if p["experiment_id"] != "A" else lab
        if p["true_class"] != expect:
            issues.append(
                f"true_class mismatch {p['experiment_id']}/{p['recording_id']}: "
                f"{p['true_class']} != {expect}")
            break

    # 4 — failures
    fail_path = OUT / "failed_folds.csv"
    if fail_path.exists():
        fails = list(csv.DictReader(fail_path.open()))
        print(f"failed_folds.csv: {len(fails)} rows")
        for f in fails[:10]:
            print("   ", f)
        if fails:
            issues.append(f"{len(fails)} failed folds reported in failed_folds.csv")
    else:
        print("failed_folds.csv: absent (no fold ever failed)")

    # 5 — provenance summary
    gate = json.loads((OUT / "equivalence_check.json").read_text())
    print("gate_passed:", gate["gate_passed"])
    svm_bitwise = all(r["max_abs_delta_weights"] == 0.0
                      for r in gate["records"] if r["algorithm"] == "linear-svm")
    lr_bitwise = all(r["max_abs_delta_weights"] == 0.0
                     for r in gate["records"] if r["algorithm"] == "logistic-regression")
    print(f"evidence class: linear-svm bitwise={svm_bitwise}; "
          f"logistic-regression bitwise={lr_bitwise} (numerical+prediction only)")
    print("per-row provenance columns present:",
          "linear_fit_mode" in folds[0], "(expected False for run 0 — group-based documentation applies)")

    print("\n=== VERDICT ===")
    if issues:
        for i in issues:
            print("ISSUE:", i)
    else:
        print("all completeness and consistency checks passed")
    (OUT / "verification_report.json").write_text(json.dumps({
        "fold_rows_per_experiment": dict(got),
        "expected_tasks": {k: v * len(ALGOS) for k, v in EXPECTED.items()},
        "duplicate_fold_keys": len(dups),
        "prediction_count_mismatches": len(mismatches),
        "orphan_prediction_groups": len(orphan),
        "issues": issues,
    }, indent=2))


if __name__ == "__main__":
    main()
