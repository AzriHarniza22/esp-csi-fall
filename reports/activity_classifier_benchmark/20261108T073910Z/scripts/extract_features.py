"""Extract canonical window features for every take once, cache as pickle.

The cache stores, per take: window feature tuples, window frame indices and
host timestamps, observer-referenced onset / action boundaries on the frame
axis, and identity metadata. Experiments read only this cache so every fold
uses the identical dataset snapshot (mandate §4).

Run:
    python3 reports/activity_classifier_benchmark/20261108T073910Z/scripts/extract_features.py
"""

from __future__ import annotations

import pickle
import time
from pathlib import Path

import bench_common as bc

OUT = Path(__file__).resolve().parents[1]


def main() -> None:
    takes = {}
    started = time.time()
    for meta_path in bc.discover_takes():
        tid = meta_path.name[: -len(".meta.json")]
        take = bc.load_take(meta_path)
        take["windows"] = [
            {k: v for k, v in window.items()} for window in take["windows"]
        ]
        takes[tid] = take
        status = "ok"
        print(f"{tid}: {take['frames']} frames, {len(take['windows'])} windows {status}")
    with (OUT / "features_cache.pkl").open("wb") as handle:
        pickle.dump(takes, handle, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"cached {len(takes)} takes in {time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
