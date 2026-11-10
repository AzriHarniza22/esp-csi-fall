#!/usr/bin/env python3
"""D2 complete: required per-phase amplitude statistics, subcarrier profiles,
baseline-relative persistence, plus metadata verification requested in section D.

Outputs: d2_stats_focus.json, figures/focus_phase_profiles.png,
figures/focus_subcarrier_heatmap.png
"""
from __future__ import annotations

import base64
import csv
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1]
RECORDINGS = Path("examples/esp-radar/wifi_sensing_demo/recordings")
FOCUS = "20261104T160401Z_fall_backward_010"


def load(rec_id):
    folder = next(RECORDINGS.rglob(f"*/{rec_id}.meta.json")).parent
    meta = json.loads((folder / f"{rec_id}.meta.json").read_text())
    amps, offs = [], []
    t0 = None
    with (folder / f"{rec_id}.frames.csv").open() as h:
        for row in csv.DictReader(h):
            v = base64.b64decode(row["valid_b64"])
            n = int(row["lltf_len"]) // 2
            amps.append([math.hypot(v[2 * k + 1] - 256 if v[2 * k + 1] > 127 else v[2 * k + 1],
                                    v[2 * k] - 256 if v[2 * k] > 127 else v[2 * k])
                         for k in range(n)])
            ns = int(row["host_receive_monotonic_ns"])
            t0 = t0 or ns
            offs.append(ns / 1e9 - t0 / 1e9)
    return meta, np.array(amps), np.array(offs)


def phase_mask(offs, a, b):
    return (offs >= a) & (offs < b)


def stats_block(A, mask):
    sub = A[mask]
    if len(sub) == 0:
        return None
    per_frame = {
        "mean": float(sub.mean()),
        "median": float(np.median(sub)),
        "std": float(sub.std()),
        "iqr": float(np.percentile(sub, 75) - np.percentile(sub, 25)),
        "min": float(sub.min()),
        "max": float(sub.max()),
    }
    d = np.abs(np.diff(sub, axis=0))
    first_diff = np.diff(sub, axis=0)
    temporal_energy = float(np.sum(d ** 2))
    return {
        "frames": int(mask.sum()),
        "amplitude": per_frame,
        "mean_abs_diff": float(d.mean()),
        "first_diff_mean": float(first_diff.mean()),
        "first_diff_std": float(first_diff.std()),
        "temporal_energy": temporal_energy,
        "per_subcarrier_std_mean": float(sub.std(axis=0).mean()),
    }


def main():
    meta, A, offs = load(FOCUS)
    res = {"recording": FOCUS}
    q = meta.get("quality", {})
    si = q.get("sampling_intervals_ms", {})
    res["metadata_verification"] = {
        "actual_duration_s": meta.get("actual_duration_s"),
        "frame_count": meta["recording"]["frames"],
        "dropped_on_device": meta["recording"].get("dropped_on_device"),
        "mean_interval_ms": si.get("mean_ms"),
        "median_interval_ms": si.get("median_ms"),
        "max_interval_ms": si.get("max_ms"),
        "first_word_invalid_frames": q.get("first_word_invalid_frames"),
        "stimulus": meta.get("stimulus"),
        "phases_expected": meta.get("timeline"),
    }
    pre = phase_mask(offs, 0, 4)
    act = phase_mask(offs, 4, 6)
    post = phase_mask(offs, 6, 10.01)
    post_early = phase_mask(offs, 6, 8)
    post_late = phase_mask(offs, 8, 10.01)
    res["phase_stats"] = {
        "pre": stats_block(A, pre),
        "action": stats_block(A, act),
        "post": stats_block(A, post),
        "post_early_6_8": stats_block(A, post_early),
        "post_late_8_10": stats_block(A, post_late),
    }
    # baseline-relative: window mean profile minus pre-phase mean profile
    base = A[pre].mean(axis=0)
    rel = {
        "action_mean_abs_deviation": float(np.abs(A[act].mean(axis=0) - base).mean()),
        "post_early_mean_abs_deviation": float(np.abs(A[post_early].mean(axis=0) - base).mean()),
        "post_late_mean_abs_deviation": float(np.abs(A[post_late].mean(axis=0) - base).mean()),
        "per_subcarrier_post_late_deviation": [round(float(x), 2) for x in np.abs(A[post_late].mean(axis=0) - base)],
    }
    res["baseline_relative"] = rel
    # persistence: fraction of post frames whose per-frame motion exceeds pre 95th pct
    mot = np.linalg.norm(np.diff(A, axis=0), axis=1) / max(1, len(A[0]))
    thr = float(np.percentile(mot[pre[:-1]], 95)) if pre.sum() > 2 else None
    if thr:
        res["persistence"] = {
            "pre_motion_p95": round(thr, 3),
            "post_frames_above_p95": int((mot[post[:-1]] > thr).sum()),
            "post_frames_total": int(post[1:].sum()),
        }
    (OUT / "d2_stats_focus.json").write_text(json.dumps(res, indent=1, default=str))

    # figure 1: band-mean amplitude vs time with phase shading
    bands = np.array_split(A.T, 16)
    band_mean = np.array([b.mean(axis=0) for b in bands]).T  # (frames,16)
    fig, ax = plt.subplots(figsize=(12, 6))
    for i in range(0, 16, 3):
        ax.plot(offs, band_mean[:, i], lw=1.0, label=f"band {i}")
    for x0, x1, c, n in [(0, 4, "green", "pre"), (4, 6, "red", "action"), (6, 10, "purple", "post")]:
        ax.axvspan(x0, x1, color=c, alpha=0.07)
        ax.text((x0 + x1) / 2, ax.get_ylim()[1] * 0.97, n, ha="center", color=c)
    ax.set_xlabel("t (s)"); ax.set_ylabel("mean LLTF amplitude (band)")
    ax.set_title("Focus take: band amplitude profiles across three phases")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "figures" / "focus_phase_profiles.png", dpi=140)

    # figure 2: per-subcarrier |post_late - baseline| heatmap (pre/action/post columns)
    prof = np.vstack([A[pre].mean(0), A[act].mean(0), A[post_early].mean(0), A[post_late].mean(0)])
    fig, ax = plt.subplots(figsize=(12, 3.5))
    im = ax.imshow(prof, aspect="auto", cmap="viridis")
    ax.set_yticks(range(4)); ax.set_yticklabels(["pre 0-4", "action 4-6", "post 6-8", "post 8-10"])
    ax.set_xlabel("LLTF subcarrier index (51 pairs)")
    ax.set_title("Phase-mean amplitude per subcarrier")
    fig.colorbar(im, ax=ax)
    fig.tight_layout(); fig.savefig(OUT / "figures" / "focus_subcarrier_heatmap.png", dpi=140)
    print(json.dumps(res["phase_stats"], indent=1, default=str)[:1800])
    print(json.dumps({"baseline_relative": {k: v for k, v in rel.items() if k != "per_subcarrier_post_late_deviation"},
                      "persistence": res.get("persistence")}, indent=1))


if __name__ == "__main__":
    main()
