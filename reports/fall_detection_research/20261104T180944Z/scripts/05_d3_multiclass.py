#!/usr/bin/env python3
"""D3 extension: multi-class symmetric test.

Can baseline-relative change vectors distinguish
  still_to_still (idle controls), still_to_after_fall, and
  still_to_after_other_action (walking/bending/fast_sitting/object_drop post
  phases)? "Intentionally lying down" and "kneeling" do not exist in the
dataset and are reported as impossible to test.

Also same-session standing control: fall-pre vs fall-post absolute windows
(within fall takes) versus cross-session equivalents.

Read-only; outputs d3_multiclass.json +
figures/d3_change_magnitude_by_class.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module
d3 = import_module("03_d3_symmetric")  # reuse take_windows + LOO

IDLE = d3.IDLE
FALL = d3.FALL
OTHER = ("walking", "bending", "fast_sitting", "object_drop")
OTHER_POST = {"walking": 7.0, "bending": 7.0, "fast_sitting": 7.0, "object_drop": 7.0}
OTHER_WINDOW_START = {"walking": 3.0, "bending": 3.0, "fast_sitting": 3.0, "object_drop": 3.0}

RECORDINGS = Path("examples/esp-radar/wifi_sensing_demo/recordings")


def main():
    groups = {"still": [], "fall": [], "other": []}
    per_class_mag = {"still": [], "fall": [], "other": []}
    for meta_path in sorted(RECORDINGS.rglob("*.meta.json")):
        label, batch, wins = d3.take_windows(meta_path)
        if label not in IDLE + FALL + OTHER or not wins:
            continue
        baseline = np.mean([p for c, p in wins if c < 4], axis=0)
        for c, p in wins:
            ch = p - baseline
            if label in IDLE and c >= 4:
                groups["still"].append(ch)
                per_class_mag["still"].append(float(np.linalg.norm(ch)))
            elif label in FALL and c >= 6:
                groups["fall"].append(ch)
                per_class_mag["fall"].append(float(np.linalg.norm(ch)))
            elif label in OTHER and c >= OTHER_POST[label]:
                groups["other"].append(ch)
                per_class_mag["other"].append(float(np.linalg.norm(ch)))

    X = np.array(groups["still"] + groups["fall"] + groups["other"])
    y = np.array(["still"] * len(groups["still"]) + ["fall"] * len(groups["fall"])
                  + ["other_action"] * len(groups["other"]))
    acc, conf, preds = d3.loo_nearest_centroid(X, y)
    fall_idx = slice(len(groups["still"]), len(groups["still"]) + len(groups["fall"]))
    fall_preds = preds[fall_idx]
    fall_as_other = float(np.mean([p == "other_action" for p in fall_preds]))
    fall_as_still = float(np.mean([p == "still" for p in fall_preds]))

    res = {
        "n_windows": {k: len(v) for k, v in groups.items()},
        "three_class_LOO_accuracy": round(acc, 4),
        "confusion": {f"{a}->{b}": v for (a, b), v in conf.items()},
        "fall_post_pred_as_other_action": round(fall_as_other, 4),
        "fall_post_pred_as_still": round(fall_as_still, 4),
        "change_magnitude_mean": {k: round(float(np.mean(v)), 4) for k, v in per_class_mag.items()},
        "change_magnitude_median": {k: round(float(np.median(v)), 4) for k, v in per_class_mag.items()},
        "untestable_contrasts": [
            "Normal still -> intentionally lying down: no lying-down class in dataset",
            "Normal still -> kneeling: no kneeling class in dataset",
            "fall_left/fall_right: zero takes recorded",
        ],
    }
    (OUT / "d3_multiclass.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.boxplot([per_class_mag["still"], per_class_mag["fall"], per_class_mag["other"]],
               tick_labels=["still→still", "still→after-fall", "still→after-other"])
    ax.set_ylabel("||profile change|| (16-band, vs own <4 s baseline)")
    ax.set_title("Baseline-relative change magnitude by contrast class")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "d3_change_magnitude_by_class.png", dpi=140)


if __name__ == "__main__":
    main()
