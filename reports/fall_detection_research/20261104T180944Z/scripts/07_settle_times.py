#!/usr/bin/env python3
"""Follow-up to D2: measure WHEN each fall actually ends (settle time), across
all 20 fall takes. Read-only on recordings; outputs settle_analysis.json +
figures/fall_settle_times.png.

Definitions (per take, time in s from take start):
  thresh        = p95 of per-frame motion during pre phase (t < 4 s)
  onset         = first t >= 3.5 s where smoothed motion crosses above thresh
  peak          = argmax of smoothed motion in [onset, end]
  settle        = FIRST t after peak where smoothed motion drops back below
                  thresh and STAYS below until take end (null if never)
  still_tail_s  = time from settle to take end (0 if never settled)
  overshoot_at_6/8/10 = smoothed(threshold_units) at fixed boundaries

Smoothing: linear interp of per-frame mean|Δamp| onto a 20 Hz grid, then
centred moving average of 20 samples (=1.0 s) so the window is time-exact
across takes with different fps.

FSM cross-check: meta.events.motion_samples transition true->false after
first true (device hysteresis, independent anchor).
"""
from __future__ import annotations

import base64
import csv
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from fall_detection.dataset_io import amplitude, decode_iq  # noqa: E402

RECORDINGS = REPO / "examples/esp-radar/wifi_sensing_demo/recordings"
OUT = Path(__file__).resolve().parents[1]
FALL = ("fall_forward", "fall_backward")
PRE_END = 4.0
GRID_HZ = 20
SMOOTH_N = 20


def load_series(rec_dir, rec_id):
    offs, motions = [], []
    with (rec_dir / f"{rec_id}.frames.csv").open(encoding="utf-8", newline="") as h:
        prev = None
        t0 = None
        for row in csv.DictReader(h):
            v = base64.b64decode(row["valid_b64"])
            n = int(row["lltf_len"]) // 2
            amps = np.asarray(amplitude(decode_iq(v, int(row["data_type"]))[:n]), dtype=float)
            ns = int(row["host_receive_monotonic_ns"])
            if t0 is None:
                t0 = ns
            offs.append(ns / 1e9 - t0 / 1e9)
            motions.append(0.0 if prev is None else float(np.mean(np.abs(amps - prev))))
            prev = amps
    return np.array(offs), np.array(motions)


def smooth_on_grid(offs, motions):
    span = offs[-1]
    grid = np.arange(0.0, span, 1.0 / GRID_HZ)
    m = np.interp(grid, offs, motions)
    kernel = np.ones(SMOOTH_N) / SMOOTH_N
    sm = np.convolve(m, kernel, mode="same")
    # edge fix: moving-average 'same' biases edges toward zero-padded values;
    # replace first/last SMOTH_N/2 samples with nearest valid interior value
    valid = sm[SMOOTH_N // 2: -SMOOTH_N // 2]
    sm[:SMOOTH_N // 2] = valid[0]
    sm[-SMOOTH_N // 2:] = valid[-1]
    return grid, sm


def fsm_end(meta, offs):
    ms = (meta.get("events") or {}).get("motion_samples") or []
    anchor = (meta.get("clock_anchor") or {}).get("performance_now_ms")
    if not ms or anchor is None:
        return None, None
    def t_of(s):
        return (s.get("ts_ms", 0) - anchor) / 1000.0
    first_true = None
    for i, s in enumerate(ms):
        if s.get("motion_status") and first_true is None:
            first_true = i
    if first_true is None:
        return None, None
    for s in ms[first_true + 1:]:
        if not s.get("motion_status"):
            return t_of(s), None
    # never returned: report duration since first true
    return None, t_of(ms[-1]) - t_of(ms[first_true])


def analyze(rec_id, meta, offs, motions):
    grid, sm = smooth_on_grid(offs, motions)
    thresh = float(np.percentile(motions[offs < PRE_END], 95))
    onset_i = next((i for i, t in enumerate(grid) if t >= 3.5 and sm[i] > thresh), None)
    if onset_i is None:
        return {"rec": rec_id, "label": meta["activity_label"], "settled": None,
                "note": "no onset crossing"}
    peak_i = onset_i + int(np.argmax(sm[onset_i:]))
    settled_i = None
    for i in range(peak_i, len(grid)):
        if np.all(sm[i:] < thresh):
            settled_i = i
            break
    def at(t):
        return float(sm[min(int(t * GRID_HZ), len(sm) - 1)])
    fsm_back_false, fsm_open_s = fsm_end(meta, offs)
    return {
        "rec": rec_id, "label": meta["activity_label"],
        "span_s": round(float(grid[-1]), 2),
        "thresh": round(thresh, 3),
        "onset_s": round(float(grid[onset_i]), 2),
        "peak_s": round(float(grid[peak_i]), 2),
        "settle_s": round(float(grid[settled_i]), 2) if settled_i is not None else None,
        "still_tail_s": round(float(grid[-1] - grid[settled_i]), 2) if settled_i is not None else 0.0,
        "overshoot_at": {"6": round(at(6) / thresh, 2), "8": round(at(8) / thresh, 2),
                          "10": round(at(10) / thresh, 2) if grid[-1] >= 10 else None},
        "fsm_back_false_s": round(fsm_back_false, 2) if fsm_back_false is not None else None,
        "fsm_open_s": round(fsm_open_s, 2) if fsm_open_s is not None else None,
    }


def main():
    results = []
    curves = {}
    for meta_path in sorted(RECORDINGS.rglob("*.meta.json")):
        rec_id = meta_path.name[: -len(".meta.json")]
        meta = json.loads(meta_path.read_text())
        if meta["activity_label"] not in FALL:
            continue
        offs, motions = load_series(meta_path.parent, rec_id)
        r = analyze(rec_id, meta, offs, motions)
        results.append(r)
        grid, sm = smooth_on_grid(offs, motions)
        curves[rec_id] = (grid, sm, r.get("thresh"))
        print(f"{rec_id[-24:]:24s} onset={r.get('onset_s')} peak={r.get('peak_s')} "
              f"settle={r.get('settle_s')} tail={r.get('still_tail_s')} "
              f"x@6/8/10={r.get('overshoot_at')} fsm_false={r.get('fsm_back_false_s')} "
              f"fsm_open={r.get('fsm_open_s')}")
    (OUT / "settle_analysis.json").write_text(json.dumps(results, indent=1))

    settled = [r["settle_s"] for r in results if r.get("settle_s") is not None]
    never = [r["rec"] for r in results if r.get("settle_s") is None and "note" not in r]
    summary = {
        "n_takes": len(results),
        "settled_within_take": len(settled),
        "never_settled": never,
        "settle_median_s": round(float(np.median(settled)), 2) if settled else None,
        "settle_range_s": [min(settled), max(settled)] if settled else None,
        "settle_by_label": {
            lab: [r["settle_s"] for r in results if r["label"] == lab and r.get("settle_s")]
            for lab in FALL},
    }
    for lab in FALL:
        xs = summary["settle_by_label"][lab]
        if xs:
            summary["settle_by_label"][lab] = {
                "n": len(xs), "median": round(float(np.median(xs)), 2),
                "min": round(min(xs), 2), "max": round(max(xs), 2)}
    (OUT / "settle_summary.json").write_text(json.dumps(summary, indent=1))
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=1))

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for rec_id, (grid, sm, thresh) in sorted(curves.items()):
        fwd = "forward" in rec_id
        ax.plot(grid, sm / thresh, lw=1.0,
                color="#d63d2e" if fwd else "#1a56c4", alpha=0.55,
                label="fall_forward" if rec_id == sorted(curves)[0] else None)
    ax.axhline(1.0, color="black", ls="--", lw=1)
    for x in (4, 6, 8, 10):
        ax.axvline(x, color="gray", ls=":", lw=0.8)
    ax.set_xlabel("t since take start (s)")
    ax.set_ylabel("smoothed motion / pre-phase p95 threshold")
    ax.set_title("All 20 fall takes: when does motion return below the pre-fall noise floor?")
    handles, labels = ax.get_legend_handles_labels()
    ax.plot([], [], color="#d63d2e", label="fall_forward")
    ax.plot([], [], color="#1a56c4", label="fall_backward")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "fall_settle_times.png", dpi=140)


if __name__ == "__main__":
    main()
