#!/usr/bin/env python3
"""Extend the settle-time methodology (script 07) to ALL non-fall labels to
answer: does any other label need a take longer than 10 s?

Read-only. For each activity take:
  thresh  = p95 of per-frame motion during its own pre phase (from meta
            timeline boundaries, not hardcoded)
  onset   = first t >= pre_end-0.5 s with smoothed motion > thresh
  peak    = argmax smoothed motion in [onset, end]
  settle  = first t after peak where motion stays below thresh until end
  tail    = end - settle (still time left inside the 10 s take)

For idle labels (single 'hold' phase) instead report stability: Spearman rho
of smoothed motion vs time and late/early p95 ratio (no action to fit).

Outputs: label_durations.json + summary print.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module
st = import_module("07_settle_times")  # reuse load_series + smooth_on_grid

RECORDINGS = REPO / "examples/esp-radar/wifi_sensing_demo/recordings"
OUT = Path(__file__).resolve().parents[1]
IDLE = ("empty_room", "still_standing", "still_sitting")


def pre_end_from_meta(meta):
    tl = meta.get("timeline")
    if isinstance(tl, list) and tl:
        # timeline entries carry boundary seconds; take the end of phase 0
        first = tl[0]
        if isinstance(first, dict):
            return float(first.get("end_offset_s", first.get("end_s", first.get("end", 4))))
    return 4.0


def analyze(label, meta, offs, motions):
    grid, sm = st.smooth_on_grid(offs, motions)
    end = float(grid[-1])
    if label in IDLE:
        early = sm[grid < end / 2]
        late = sm[grid >= end / 2]
        rho, p = spearmanr(grid, sm)
        return {"label": label, "kind": "idle",
                "late_over_early_p95": round(
                    float(np.percentile(late, 95) / max(1e-9, np.percentile(early, 95))), 2),
                "spearman_rho": round(float(rho), 3), "rho_p": round(float(p), 4)}
    pe = pre_end_from_meta(meta)
    thresh = float(np.percentile(motions[offs < pe], 95))
    onset_i = next((i for i, t in enumerate(grid) if t >= pe - 0.5 and sm[i] > thresh), None)
    if onset_i is None:
        return {"label": label, "kind": "action", "settled": None, "note": "no onset crossing"}
    peak_i = onset_i + int(np.argmax(sm[onset_i:]))
    settled_i = next((i for i in range(peak_i, len(grid)) if np.all(sm[i:] < thresh)), None)
    return {"label": label, "kind": "action", "pre_end": pe,
            "onset_s": round(float(grid[onset_i]), 2),
            "peak_s": round(float(grid[peak_i]), 2),
            "settle_s": round(float(grid[settled_i]), 2) if settled_i is not None else None,
            "tail_s": round(end - float(grid[settled_i]), 2) if settled_i is not None else 0.0}


def main():
    per_label = {}
    for meta_path in sorted(RECORDINGS.rglob("*.meta.json")):
        rec_id = meta_path.name[: -len(".meta.json")]
        meta = json.loads(meta_path.read_text())
        label = meta["activity_label"]
        offs, motions = st.load_series(meta_path.parent, rec_id)
        r = analyze(label, meta, offs, motions)
        r["rec"] = rec_id
        per_label.setdefault(label, []).append(r)

    summary = {}
    for label, rows in sorted(per_label.items()):
        if label in IDLE:
            xs = [r for r in rows if "kind" in r]
            summary[label] = {
                "n": len(xs),
                "late_over_early_p95_median": round(float(np.median([x["late_over_early_p95"] for x in xs])), 2),
                "spearman_rho_median": round(float(np.median([x["spearman_rho"] for x in xs])), 3),
                "worst_ratio_take": max(xs, key=lambda x: x["late_over_early_p95"])["rec"],
            }
        else:
            settled = [r for r in rows if r.get("settle_s") is not None]
            never = [r["rec"][-16:] for r in rows if r.get("settle_s") is None and "note" not in r]
            summary[label] = {
                "n": len(rows),
                "settle_median_s": round(float(np.median([r["settle_s"] for r in settled])), 2) if settled else None,
                "settle_max_s": round(max([r["settle_s"] for r in settled]), 2) if settled else None,
                "never_settled": never,
                "tail_median_s": round(float(np.median([r["tail_s"] for r in settled])), 2) if settled else None,
                "tail_min_s": round(min([r["tail_s"] for r in settled]), 2) if settled else None,
                "peaks": sorted([r.get("peak_s") for r in rows if r.get("peak_s") is not None]),
            }
        for r in rows:
            print(f"{label:14s} {r['rec'][-20:]:20s} " + " ".join(
                f"{k}={v}" for k, v in r.items() if k not in ("rec", "label")))
    (OUT / "label_durations.json").write_text(json.dumps(
        {"per_take": per_label, "summary": summary}, indent=1))
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
