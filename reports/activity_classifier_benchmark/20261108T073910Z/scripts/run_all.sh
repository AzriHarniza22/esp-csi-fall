#!/usr/bin/env bash
# Full reproduction pipeline for this benchmark (mandate §23).
# Deterministic: canonical RANDOM_SEED=20261026, bootstrap seed 20261108.
set -euo pipefail
cd "$(dirname "$0")"
# Start from a clean output state: the runners APPEND fold/prediction CSVs.
rm -f ../fold_results.csv ../predictions_oof.csv ../failed_folds.csv
python3 make_manifest.py
python3 extract_features.py
python3 equivalence_check.py
python3 run_loto.py --experiment A
python3 run_loto.py --experiment B
python3 run_loto.py --experiment BSENS
python3 run_loto.py --experiment C
python3 analyze.py
