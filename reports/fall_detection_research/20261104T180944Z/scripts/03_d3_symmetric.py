#!/usr/bin/env python3
"""D3: verify the post-fall channel-state hypothesis on the CURRENT dataset.

Design (symmetric, session-invariant):
  * Every take contributes windowed 16-band log-delta profiles (trainer maths).
  * Each take's baseline profile = mean of windows whose centre < 4 s.
  * "change vector" c_w = profile(w) - baseline(take).
  * Control class  "still->still": windows with centre >= 4 s from idle takes
    (empty_room, still_standing, still_sitting).
  * Test  class    "still->after-fall": windows with centre >= 6 s from fall
    takes.
  * LOO nearest-centroid on change vectors, plus magnitude comparison and a
    decay check (correlation of |c| with time since the fall).
  * Absolute-profile controls (confound demonstration):
      - fall-pre windows vs fall-post windows, WITHIN the same takes
      - fall-pre vs still_standing windows (different batches; if a raw
        absolute-profile classifier separates these perfectly, both standing,
        then absolute profiles encode session identity, not posture).

Read-only; outputs d3_results.json + figures/d3_symmetric_separation.png.
"""
from __future__ import annotations

import base64
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1]
RECORDINGS = REPO / "examples/esp-radar/wifi_sensing_demo/recordings"

WINDOW = 24
STRIDE = 12
BANDS = 16
IDLE = ("empty_room", "still_standing", "still_sitting")
FALL = ("fall_forward", "fall_backward")


def take_windows(meta_path):
    rec_id = meta_path.name[: -len(".meta.json")]
    meta = json.loads(meta_path.read_text())
    with (meta_path.parent / f"{rec_id}.frames.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    amps = []
    offs = []
    t0 = None
    for row in rows:
        valid = base64.b64decode(row["valid_b64"])
        n_pairs = int(row["lltf_len"]) // 2
        a = []
        for k in range(n_pairs):
            imag = valid[2 * k] - 256 if valid[2 * k] > 127 else valid[2 * k]
            real = valid[2 * k + 1] - 256 if valid[2 * k + 1] > 127 else valid[2 * k + 1]
            a.append(math.hypot(real, imag))
        amps.append(a)
        ns = int(row["host_receive_monotonic_ns"])
        if t0 is None:
            t0 = ns
        offs.append(ns / 1e9 - t0 / 1e9)
    width = min(len(a) for a in amps)
    wins = []
    for s in range(0, len(amps) - WINDOW + 1, STRIDE):
        band = [0.0] * BANDS
        counts = [0] * BANDS
        for i in range(s + 1, s + WINDOW):
            prev, cur = amps[i - 1], amps[i]
            for sc in range(width):
                b = sc * BANDS // width
                band[b] += abs(cur[sc] - prev[sc])
                counts[b] += 1
        prof = np.array([math.log1p(band[b] / max(1, counts[b])) for b in range(BANDS)])
        centre = offs[s + WINDOW // 2]
        wins.append((centre, prof))
    return meta["activity_label"], (meta.get("batch") or {}).get("batch_id"), wins


def loo_nearest_centroid(X, y, test_classes=None):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y)
    classes = sorted(set(y.tolist()))
    mu, sd = X.mean(0), X.std(0)
    sd[sd < 1e-9] = 1.0
    Z = (X - mu) / sd
    correct = 0
    preds = []
    for i in range(len(Z)):
        best_c, best_d = None, float("inf")
        for c in classes:
            idx = [j for j in range(len(Z)) if y[j] == c and j != i]
            if not idx:
                continue
            d = float(np.sum((Z[i] - Z[idx].mean(0)) ** 2))
            if d < best_d:
                best_d, best_c = d, c
        preds.append(best_c)
        correct += int(best_c == y[i])
    conf = defaultdict(int)
    for t, p in zip(y, preds):
        conf[(str(t), str(p))] += 1
    return correct / len(Z), dict(conf), np.array(preds)


def main():
    data = {}  # rec_id -> (label, wins); baseline must be PER TAKE
    for meta_path in sorted(RECORDINGS.rglob("*.meta.json")):
        label, batch, wins = take_windows(meta_path)
        if label in IDLE or label in FALL:
            data[meta_path.name] = (label, wins)

    # baselines and change vectors
    controls = []   # still->still change vectors
    post_fall = []  # still->after-fall change vectors
    pre_abs = []    # absolute pre windows (fall takes)
    post_abs = []   # absolute post windows (fall takes)
    standing_abs = []  # absolute windows still_standing
    decay_pairs = []   # (t_since_action6, |c|)
    for rec_name, (label, wins) in data.items():
        if not wins:
            continue
        baseline = np.mean([p for c, p in wins if c < 4], axis=0)
        for c, p in wins:
            if label in FALL:
                if c < 4:
                    pre_abs.append(p)
                elif c >= 6:
                    post_abs.append(p)
                    ch = p - baseline
                    post_fall.append(ch)
                    decay_pairs.append((c, float(np.linalg.norm(ch))))
            else:
                if c >= 4:
                    controls.append(p - baseline)
                if label == "still_standing" and c >= 4:
                    standing_abs.append(p)

    X = np.array(controls + post_fall)
    y = np.array(["still_to_still"] * len(controls) + ["still_to_after_fall"] * len(post_fall))
    acc_sym, conf_sym, preds = loo_nearest_centroid(X, y)
    mag_ctrl = float(np.mean([np.linalg.norm(v) for v in controls]))
    mag_fall = float(np.mean([np.linalg.norm(v) for v in post_fall]))

    # absolute-profile within-take separation (pre vs post, SAME takes)
    X_abs = np.array(pre_abs + post_abs)
    y_abs = np.array(["pre"] * len(pre_abs) + ["post"] * len(post_abs))
    acc_abs_within, conf_abs_within, _ = loo_nearest_centroid(X_abs, y_abs)

    # absolute-profile cross-class confound demo (fall-pre vs standing, both standing, diff batches)
    n = min(len(pre_abs), len(standing_abs))
    rng = np.random.default_rng(7)
    idx_p = rng.choice(len(pre_abs), n, replace=False)
    idx_s = rng.choice(len(standing_abs), n, replace=False)
    X_conf = np.array([pre_abs[i] for i in idx_p] + [standing_abs[i] for i in idx_s])
    y_conf = np.array(["fall_pre"] * n + ["still_standing"] * n)
    acc_confound, _, _ = loo_nearest_centroid(X_conf, y_conf)

    # decay: spearman corr between time since action and |change|
    from scipy.stats import spearmanr
    ts = np.array([t for t, _ in decay_pairs])
    ms = np.array([m for _, m in decay_pairs])
    late = ms[ts >= 8]
    early = ms[(ts >= 6) & (ts < 8)]
    rho, pval = spearmanr(ts, ms)

    results = {
        "counts": {
            "control_still_to_still_windows": len(controls),
            "after_fall_windows": len(post_fall),
            "fall_takes": sum(1 for l, _ in data.values() if l in FALL),
            "idle_takes": sum(1 for l, _ in data.values() if l in IDLE),
        },
        "symmetric_LOO_accuracy": round(acc_sym, 4),
        "symmetric_confusion": {f"{a}->{b}": v for (a, b), v in conf_sym.items()},
        "change_magnitude_mean": {"control": round(mag_ctrl, 4), "after_fall": round(mag_fall, 4),
                                   "ratio": round(mag_fall / mag_ctrl, 2)},
        "absolute_within_take_pre_vs_post_LOO": round(acc_abs_within, 4),
        "absolute_fall_pre_vs_still_standing_LOO": round(acc_confound, 4),
        "post_fall_decay": {
            "spearman_rho_time_vs_magnitude": round(float(rho), 4),
            "p_value": float(f"{pval:.3g}"),
            "mean_magnitude_6_to_8s": round(float(early.mean()), 4) if len(early) else None,
            "mean_magnitude_8_to_10s": round(float(late.mean()), 4) if len(late) else None,
        },
    }
    (OUT / "d3_results.json").write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))

    # figure: PCA of change vectors
    Xc = X - X.mean(0)
    u, s, vt = np.linalg.svd(Xc, full_matrices=False)
    pc = Xc @ vt[:2].T
    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    ax[0].scatter(pc[: len(controls), 0], pc[: len(controls), 1], s=12, alpha=0.6, label="still→still (control)")
    ax[0].scatter(pc[len(controls):, 0], pc[len(controls):, 1], s=12, alpha=0.6, color="#d63d2e", label="still→after-fall")
    ax[0].set_xlabel("PC1"); ax[0].set_ylabel("PC2")
    ax[0].set_title(f"Baseline-relative change vectors (LOO acc={acc_sym:.0%})")
    ax[0].legend()
    ax[1].scatter(ts, ms, s=12, alpha=0.6, color="#7a5cc4")
    ax[1].axvline(6, color="red", ls="--", label="action end")
    ax[1].set_xlabel("s since take start"); ax[1].set_ylabel("||change|| (16-band)")
    ax[1].set_title(f"After-fall change magnitude vs time (ρ={rho:.2f}, p={pval:.3g})")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "d3_symmetric_separation.png", dpi=140)


if __name__ == "__main__":
    main()
