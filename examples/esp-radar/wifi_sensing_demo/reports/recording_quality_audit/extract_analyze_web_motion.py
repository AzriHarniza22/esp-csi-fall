#!/usr/bin/env python3
"""
extract_analyze_web_motion.py
=============================================================
Mengekstrak dan menganalisis data Motion Graph web untuk 130
recording Wi-Fi CSI.

Sumber data:  meta.json → events.motion_samples[]
Rumus Y:      smooth_scaled / 1000, enter_level_scaled / 1000,
              exit_level_scaled / 1000  (sama persis dengan browser)
Sumber X:     ts_ms (epoch ms dari esp_timer_get_time()/1000)

Read-only. Tidak ada data yang dimodifikasi.
Output ke reports/recording_quality_audit/
"""

import csv
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages

# ── Paths ────────────────────────────────────────────────────────────────────
BASE   = Path(__file__).resolve().parent.parent.parent   # wifi_sensing_demo/
REC    = BASE / "recordings"
OUT    = Path(__file__).resolve().parent                 # reports/recording_quality_audit/

PDF_PATH     = OUT / "web_motion_profiles.pdf"
TIMESERIES   = OUT / "web_motion_data.csv"
SUMMARY      = OUT / "web_motion_summary.csv"
ANOMALIES    = OUT / "web_motion_anomalies.csv"

# ── Constants (mirror browser) ───────────────────────────────────────────────
SCALE          = 1000.0          # browser divides every field by 1000
# Gap threshold: if ts_ms gap > this, do not compute cross-gap derivatives
GAP_THRESHOLD_MS = 500.0         # 500 ms, same logic as prior audits

# ── Idle vs active labels ─────────────────────────────────────────────────────
IDLE_LABELS   = {"empty_room", "still_standing", "still_sitting"}
ACTIVE_LABELS = {
    "fall_forward", "fall_backward", "fall_lemas", "fall_keseleo",
    "bending", "fast_sitting", "object_drop", "walking",
}


# ═════════════════════════════════════════════════════════════════════════════
# Data loading
# ═════════════════════════════════════════════════════════════════════════════

def load_recording(meta_path: Path) -> dict | None:
    """
    Load a single recording's motion_samples from meta.json.
    Returns dict with keys:
        recording_id, label, target_duration_s, actual_duration_s,
        timeline, annotations, samples (list of dicts), has_motion_samples
    """
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    # Resolve motion samples (v3: events.motion_samples; legacy: motion_samples)
    events = meta.get("events", {})
    raw_samples = (
        events.get("motion_samples")
        if isinstance(events.get("motion_samples"), list)
        else meta.get("motion_samples")
    )

    samples = []
    if isinstance(raw_samples, list):
        for s in raw_samples:
            ts    = s.get("ts_ms")
            ss    = s.get("smooth_scaled")
            enter = s.get("enter_level_scaled")
            exit_ = s.get("exit_level_scaled")
            ms    = s.get("motion_status")
            if (ts is not None and ss is not None and
                    enter is not None and exit_ is not None and
                    isinstance(ms, bool)):
                try:
                    samples.append({
                        "ts_ms":               float(ts),
                        "smooth":              float(ss)    / SCALE,
                        "enter_level":         float(enter) / SCALE,
                        "exit_level":          float(exit_) / SCALE,
                        "motion_status":       bool(ms),
                        "smooth_raw":          int(ss),
                        "enter_level_raw":     int(enter),
                        "exit_level_raw":      int(exit_),
                    })
                except (TypeError, ValueError):
                    pass

    return {
        "recording_id":      meta.get("recording_id", meta_path.stem.replace(".meta", "")),
        "label":             meta.get("activity_label", meta_path.parent.name),
        "target_duration_s": meta.get("target_duration_s"),
        "actual_duration_s": meta.get("actual_duration_s"),
        "timeline":          meta.get("timeline", []),
        "annotations":       meta.get("annotations", {}),
        "samples":           samples,
        "has_motion_samples": len(samples) > 0,
        "frames_meta":       meta.get("recording", {}).get("frames"),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Per-recording analysis
# ═════════════════════════════════════════════════════════════════════════════

def compute_smooth_derivative(samples: list[dict]) -> np.ndarray:
    """
    Compute frame-to-frame derivative of smooth_scaled/1000.
    Pairs separated by > GAP_THRESHOLD_MS are marked NaN.
    Returns array of length len(samples); index 0 is 0.0.
    """
    n = len(samples)
    deriv = np.full(n, np.nan)
    if n < 2:
        return deriv
    deriv[0] = 0.0
    for i in range(1, n):
        gap = samples[i]["ts_ms"] - samples[i - 1]["ts_ms"]
        if gap > GAP_THRESHOLD_MS:
            deriv[i] = np.nan
        else:
            deriv[i] = samples[i]["smooth"] - samples[i - 1]["smooth"]
    return deriv


def phase_window(samples: list[dict], start_s: float, end_s: float) -> list[dict]:
    """Return samples whose offset from first sample falls in [start_s, end_s)."""
    if not samples:
        return []
    t0 = samples[0]["ts_ms"]
    return [s for s in samples
            if start_s <= (s["ts_ms"] - t0) / 1000.0 < end_s]


def stats(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0, "mean": None, "median": None, "std": None,
                "min": None, "max": None, "p90": None}
    a = np.array(vals, dtype=np.float64)
    return {
        "n":      int(len(a)),
        "mean":   float(np.mean(a)),
        "median": float(np.median(a)),
        "std":    float(np.std(a)),
        "min":    float(np.min(a)),
        "max":    float(np.max(a)),
        "p90":    float(np.percentile(a, 90)),
    }


def analyze_recording(rec: dict) -> dict:
    """Compute per-phase statistics and consistency flags."""
    samples = rec["samples"]
    result = {
        "recording_id":      rec["recording_id"],
        "label":             rec["label"],
        "n_samples":         len(samples),
        "has_motion_samples": rec["has_motion_samples"],
        "phase_stats":       {},
        "flags":             [],
        "smooth_global":     {},
        "gap_artefact_count": 0,
        # Cross-gap spikes: derivative > 5× global std, masked by gap
        "spike_count":       0,
        "motion_active_pct": 0.0,
    }

    if not samples:
        result["flags"].append("NO_MOTION_SAMPLES")
        return result

    # ── Global smooth stats ──────────────────────────────────────────────────
    all_smooth = [s["smooth"] for s in samples]
    result["smooth_global"] = stats(all_smooth)

    # Derivative
    deriv = compute_smooth_derivative(samples)
    result["gap_artefact_count"] = int(np.sum(np.isnan(deriv)))

    # Motion active %
    active_count = sum(1 for s in samples if s["motion_status"])
    result["motion_active_pct"] = round(active_count / len(samples) * 100, 1)

    # Above-enter fraction (smooth > enter_level)
    above_enter = sum(1 for s in samples if s["smooth"] > s["enter_level"])
    result["above_enter_pct"] = round(above_enter / len(samples) * 100, 1)

    # ── Per-phase stats ──────────────────────────────────────────────────────
    timeline = rec["timeline"]
    for phase in timeline:
        pname = phase["phase"]
        ps, pe = phase["start_offset_s"], phase["end_offset_s"]
        win = phase_window(samples, ps, pe)
        s_vals = [s["smooth"] for s in win]
        a_vals = [float(s["motion_status"]) for s in win]
        result["phase_stats"][pname] = {
            **stats(s_vals),
            "motion_active_pct": round(100 * sum(a_vals) / len(a_vals), 1) if a_vals else None,
        }

    # ── Consistency flags ────────────────────────────────────────────────────
    idle_phases   = {"pre_action", "post_action", "hold"}
    active_phases = {"fall_action", "action", "walking"}

    pre_ps   = result["phase_stats"].get("pre_action", {})
    post_ps  = result["phase_stats"].get("post_action", {})
    act_ps   = (result["phase_stats"].get("fall_action") or
                result["phase_stats"].get("action") or
                result["phase_stats"].get("walking") or {})
    hold_ps  = result["phase_stats"].get("hold", {})

    pre_mean  = pre_ps.get("mean")
    post_mean = post_ps.get("mean")
    act_mean  = act_ps.get("mean")
    hold_mean = hold_ps.get("mean")

    result["pre_smooth_mean"]    = pre_mean
    result["action_smooth_mean"] = act_mean
    result["post_smooth_mean"]   = post_mean

    # Smooth-based ratios (for phase comparison)
    result["action_pre_ratio"]   = round(act_mean  / pre_mean,  3) if (act_mean  and pre_mean  and pre_mean  > 0.001) else None
    result["post_action_ratio"]  = round(post_mean / act_mean,  3) if (post_mean and act_mean  and act_mean  > 0.001) else None

    label = rec["label"]

    # --- Flag: active_phase motion_status almost always inactive
    if label in ACTIVE_LABELS and act_ps.get("n", 0) >= 3:
        act_active_pct = act_ps.get("motion_active_pct", 0.0) or 0.0
        if act_active_pct < 10.0:
            result["flags"].append(
                f"ACT_PHASE_MOTION_STATUS_ALWAYS_INACTIVE:{act_active_pct:.0f}%"
            )

    # --- Flag: pre/post unexpectedly high motion_status %
    for phase_name, ps_dict in [("pre_action", pre_ps), ("post_action", post_ps)]:
        active_pct = ps_dict.get("motion_active_pct")
        if active_pct is not None and active_pct > 50 and label in ACTIVE_LABELS:
            result["flags"].append(
                f"{phase_name.upper()}_HIGH_MOTION_STATUS:{active_pct:.0f}%"
            )

    # --- Flag: smooth value much higher in pre_action than action
    if label in ACTIVE_LABELS and pre_mean and act_mean:
        pre_n = pre_ps.get("n", 0)
        act_n = act_ps.get("n", 0)
        if pre_n >= 3 and act_n >= 3:
            if act_mean < pre_mean * 0.85:
                result["flags"].append(
                    f"ACT_SMOOTH_LOWER_THAN_PRE:ratio={result['action_pre_ratio']:.3f}"
                )

    # --- Flag: post much higher than action (sustained motion after activity)
    if label in ACTIVE_LABELS and post_mean and act_mean:
        post_n = post_ps.get("n", 0)
        act_n  = act_ps.get("n", 0)
        if post_n >= 3 and act_n >= 3:
            if post_mean > act_mean * 1.15:
                result["flags"].append(
                    f"POST_SMOOTH_HIGHER_THAN_ACT:ratio={result['post_action_ratio']:.3f}"
                )

    # --- Flag: idle label with elevated smooth
    # smooth_scaled/1000 is in range 50–6600 for this dataset.
    # Empirical baseline: empty_room ≈ 1583, still_standing ≈ 2640, still_sitting ≈ 2384.
    # Flag only if hold_mean > 5500 (well above all idle baselines measured).
    if label in IDLE_LABELS and hold_mean is not None:
        if hold_mean > 5500:
            result["flags"].append(f"IDLE_LABEL_HIGH_SMOOTH:hold_mean={hold_mean:.1f}")

    # --- Flag: fall_keseleo post_action (slow movement) completely flat
    if label == "fall_keseleo" and post_mean is not None:
        if post_mean < 2000:   # smooth_scaled/1000 scale; walking pre ≈ 5200
            result["flags"].append(
                f"KESELEO_POST_TOO_LOW:post_mean={post_mean:.1f}"
            )

    # --- Flag: annotation outside smooth peak
    # For annotated fall recordings, check if fall_start aligns with elevated smooth
    ann = rec.get("annotations", {})
    fs_obj = ann.get("fall_start")
    if isinstance(fs_obj, dict) and label in {"fall_forward", "fall_backward",
                                               "fall_lemas", "fall_keseleo"}:
        fs_offset = fs_obj.get("offset_s")
        if fs_offset is not None and samples:
            t0 = samples[0]["ts_ms"]
            # Window ±1.5s around fall_start
            win_fall = [s for s in samples
                        if abs((s["ts_ms"] - t0) / 1000.0 - fs_offset) <= 1.5]
            if win_fall:
                peak_in_window = max(s["smooth"] for s in win_fall)
                global_max = result["smooth_global"]["max"] or 0
                # Only flag if peak in window is < 60% of global max (smooth never rises near annotation)
                if global_max > 0 and peak_in_window < global_max * 0.6:
                    result["flags"].append(
                        f"FALL_PEAK_NOT_NEAR_ANNOTATION:annotation={fs_offset:.2f}s,"
                        f"window_peak={peak_in_window:.0f},global_max={global_max:.0f}"
                    )

    # --- Flag: very few motion samples (< 20 for a 10s recording)
    target_dur = rec.get("target_duration_s") or 10
    expected_min = max(5, target_dur * 1)   # at least ~1 sample/s
    if len(samples) < expected_min:
        result["flags"].append(f"TOO_FEW_MOTION_SAMPLES:{len(samples)}")

    return result


# ═════════════════════════════════════════════════════════════════════════════
# Cross-recording comparison
# ═════════════════════════════════════════════════════════════════════════════

def flag_cross_recording_outliers(all_analyses: list[dict]):
    """
    For each active label, compute distribution of action_smooth_mean.
    Flag z < -2.0 (suspiciously low for active label).
    Modifies analyses in-place.
    """
    by_label = defaultdict(list)
    for a in all_analyses:
        if a["action_smooth_mean"] is not None:
            by_label[a["label"]].append(a["action_smooth_mean"])

    for a in all_analyses:
        lbl = a["label"]
        if lbl not in ACTIVE_LABELS:
            continue
        mean_val = a["action_smooth_mean"]
        if mean_val is None:
            continue
        arr = np.array(by_label[lbl])
        if len(arr) < 3:
            continue
        z = (mean_val - arr.mean()) / (arr.std() + 1e-9)
        if z < -2.0:
            a["flags"].append(
                f"ACT_SMOOTH_LOW_vs_LABEL:z={z:.2f},"
                f"label_mean={arr.mean():.3f},label_std={arr.std():.3f}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# Plotting (one page per recording)
# ═════════════════════════════════════════════════════════════════════════════

PHASE_COLORS = {
    "pre_action":  "#4a90d9",
    "fall_action": "#e34234",
    "action":      "#e34234",
    "walking":     "#f5a623",
    "post_action": "#7ed321",
    "hold":        "#9b9b9b",
}


def plot_recording(rec: dict, analysis: dict, ax_top, ax_state):
    """
    Draw motion graph (smooth, enter, exit) on ax_top and
    motion_status strip on ax_state.
    Mirrors the browser rendering exactly.
    """
    samples  = rec["samples"]
    timeline = rec["timeline"]
    ann      = rec.get("annotations", {})

    if not samples:
        ax_top.text(0.5, 0.5, "No motion_samples", transform=ax_top.transAxes,
                    ha="center", va="center", fontsize=9, color="gray")
        ax_state.set_visible(False)
        return

    ts_ms  = np.array([s["ts_ms"]   for s in samples])
    smooth = np.array([s["smooth"]  for s in samples])
    enter  = np.array([s["enter_level"] for s in samples])
    exit_  = np.array([s["exit_level"]  for s in samples])

    t0_ms   = ts_ms[0]
    offset_s = (ts_ms - t0_ms) / 1000.0

    # Phase shading
    legend_patches = []
    for phase in timeline:
        pname = phase["phase"]
        color = PHASE_COLORS.get(pname, "#cccccc")
        ax_top.axvspan(phase["start_offset_s"], phase["end_offset_s"],
                       alpha=0.12, color=color, zorder=0)
        legend_patches.append(
            mpatches.Patch(color=color, alpha=0.4, label=pname)
        )

    # Curves
    ax_top.plot(offset_s, smooth, lw=0.9, color="#7bffb6", alpha=0.9, label="smooth/1000")
    ax_top.plot(offset_s, enter,  lw=1.2, color="#ffb454", alpha=0.85, label="enter/1000")
    ax_top.plot(offset_s, exit_,  lw=1.2, color="#ff6b81", alpha=0.85, label="exit/1000")

    # Annotation markers
    fs_obj = ann.get("fall_start")
    fi_obj = ann.get("fall_impact")
    if isinstance(fs_obj, dict) and fs_obj.get("offset_s") is not None:
        ax_top.axvline(fs_obj["offset_s"], color="violet", lw=1.3, ls="--",
                       label=f"fall_start {fs_obj['offset_s']:.2f}s")
    if isinstance(fi_obj, dict) and fi_obj.get("offset_s") is not None:
        ax_top.axvline(fi_obj["offset_s"], color="orange", lw=1.3, ls="--",
                       label=f"fall_impact {fi_obj['offset_s']:.2f}s")

    ax_top.set_xlim(0, offset_s[-1] + 0.1)
    ax_top.set_ylim(bottom=0)
    ax_top.set_ylabel("value / 1000", fontsize=7)
    flags = analysis.get("flags", [])
    flag_str = "; ".join(flags[:2]) if flags else "PASS"
    title_color = "red" if flags else "black"
    ax_top.set_title(
        f"{rec['recording_id']}  [{rec['label']}]  |  {flag_str}",
        fontsize=7, color=title_color, pad=3
    )

    # Legend
    all_handles = legend_patches + ax_top.lines[:3]
    ax_top.legend(handles=all_handles, loc="upper right",
                  fontsize=5, ncol=3, framealpha=0.5)

    # Motion state strip
    ax_state.set_xlim(0, offset_s[-1] + 0.1)
    ax_state.set_ylim(0, 1)
    ax_state.set_yticks([])
    ax_state.set_xlabel("time offset (s)", fontsize=7)

    for i, s in enumerate(samples):
        x0  = (s["ts_ms"] - t0_ms) / 1000.0
        x1  = (samples[i + 1]["ts_ms"] - t0_ms) / 1000.0 if i + 1 < len(samples) else offset_s[-1] + 0.05
        col = "#2d7a4f" if s["motion_status"] else "#7a2d3a"
        ax_state.barh(0, x1 - x0, left=x0, height=1,
                      color=col, linewidth=0, align="edge")


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("Loading recordings from meta.json files …")
    recordings = []
    for lbl_dir in sorted(REC.iterdir()):
        if not lbl_dir.is_dir():
            continue
        for mf in sorted(lbl_dir.glob("*.meta.json")):
            rec = load_recording(mf)
            if rec:
                recordings.append(rec)

    print(f"  {len(recordings)} recordings loaded")

    # ── Analyse ───────────────────────────────────────────────────────────────
    print("Analysing …")
    all_analyses = []
    for i, rec in enumerate(recordings):
        print(f"  [{i+1:3d}/{len(recordings)}] {rec['recording_id']}", end="\r", flush=True)
        a = analyze_recording(rec)
        all_analyses.append(a)
    print()

    flag_cross_recording_outliers(all_analyses)

    # ── Collect label-level baselines ─────────────────────────────────────────
    label_action_means = defaultdict(list)
    label_pre_means    = defaultdict(list)
    label_post_means   = defaultdict(list)
    for a in all_analyses:
        lbl = a["label"]
        if a["action_smooth_mean"] is not None:
            label_action_means[lbl].append(a["action_smooth_mean"])
        if a["pre_smooth_mean"] is not None:
            label_pre_means[lbl].append(a["pre_smooth_mean"])
        if a["post_smooth_mean"] is not None:
            label_post_means[lbl].append(a["post_smooth_mean"])

    # ── Write web_motion_data.csv ─────────────────────────────────────────────
    print(f"Writing {TIMESERIES} …")
    ts_rows = []
    for rec in recordings:
        for s in rec["samples"]:
            t0 = rec["samples"][0]["ts_ms"] if rec["samples"] else 0
            ts_rows.append({
                "recording_id":    rec["recording_id"],
                "label":           rec["label"],
                "ts_ms":           s["ts_ms"],
                "offset_s":        round((s["ts_ms"] - t0) / 1000.0, 3),
                "smooth":          round(s["smooth"],        5),
                "enter_level":     round(s["enter_level"],   5),
                "exit_level":      round(s["exit_level"],    5),
                "motion_status":   int(s["motion_status"]),
                "smooth_raw":      s["smooth_raw"],
                "enter_level_raw": s["enter_level_raw"],
                "exit_level_raw":  s["exit_level_raw"],
            })
    if ts_rows:
        with open(TIMESERIES, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(ts_rows[0].keys()))
            w.writeheader()
            w.writerows(ts_rows)
    print(f"  {len(ts_rows)} rows")

    # ── Write web_motion_summary.csv ──────────────────────────────────────────
    print(f"Writing {SUMMARY} …")
    amap = {a["recording_id"]: a for a in all_analyses}
    sum_rows = []
    for rec in recordings:
        a = amap[rec["recording_id"]]
        sg = a["smooth_global"]
        row = {
            "recording_id":        rec["recording_id"],
            "label":               rec["label"],
            "n_samples":           a["n_samples"],
            "has_motion_samples":  a["has_motion_samples"],
            "smooth_mean":         round(sg.get("mean") or 0, 4),
            "smooth_std":          round(sg.get("std")  or 0, 4),
            "smooth_min":          round(sg.get("min")  or 0, 4),
            "smooth_max":          round(sg.get("max")  or 0, 4),
            "motion_active_pct":   a["motion_active_pct"],
            "above_enter_pct":     a.get("above_enter_pct", 0),
            "gap_artefact_count":  a["gap_artefact_count"],
            "pre_smooth_mean":     round(a["pre_smooth_mean"]    or 0, 4) if a["pre_smooth_mean"]    is not None else "",
            "action_smooth_mean":  round(a["action_smooth_mean"] or 0, 4) if a["action_smooth_mean"] is not None else "",
            "post_smooth_mean":    round(a["post_smooth_mean"]   or 0, 4) if a["post_smooth_mean"]   is not None else "",
            "action_pre_ratio":    round(a["action_pre_ratio"],  3) if a["action_pre_ratio"]  is not None else "",
            "post_action_ratio":   round(a["post_action_ratio"], 3) if a["post_action_ratio"] is not None else "",
            "flags_count":         len(a["flags"]),
            "flags":               "; ".join(a["flags"]),
        }
        # Phase detail columns
        for pname in ["pre_action", "fall_action", "action", "walking", "post_action", "hold"]:
            ps = a["phase_stats"].get(pname, {})
            for stat in ["n", "mean", "std", "motion_active_pct"]:
                val = ps.get(stat, "")
                row[f"{pname}_{stat}"] = round(val, 4) if isinstance(val, float) else val
        sum_rows.append(row)

    if sum_rows:
        with open(SUMMARY, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(sum_rows[0].keys()))
            w.writeheader()
            w.writerows(sum_rows)
    print(f"  {len(sum_rows)} rows")

    # ── Write web_motion_anomalies.csv ────────────────────────────────────────
    print(f"Writing {ANOMALIES} …")
    anom_rows = []
    for a in all_analyses:
        for flag in a["flags"]:
            anom_rows.append({
                "recording_id":       a["recording_id"],
                "label":              a["label"],
                "flag":               flag,
                "pre_smooth_mean":    round(a["pre_smooth_mean"],    4) if a["pre_smooth_mean"]    is not None else "",
                "action_smooth_mean": round(a["action_smooth_mean"], 4) if a["action_smooth_mean"] is not None else "",
                "post_smooth_mean":   round(a["post_smooth_mean"],   4) if a["post_smooth_mean"]   is not None else "",
                "action_pre_ratio":   round(a["action_pre_ratio"],   3) if a["action_pre_ratio"]   is not None else "",
                "post_action_ratio":  round(a["post_action_ratio"],  3) if a["post_action_ratio"]  is not None else "",
                "motion_active_pct":  a["motion_active_pct"],
                "n_samples":          a["n_samples"],
                "smooth_global_max":  round(a["smooth_global"].get("max") or 0, 4),
            })
    with open(ANOMALIES, "w", newline="", encoding="utf-8") as f:
        if anom_rows:
            w = csv.DictWriter(f, fieldnames=list(anom_rows[0].keys()))
            w.writeheader()
            w.writerows(anom_rows)
        else:
            f.write("recording_id,label,flag,pre_smooth_mean,action_smooth_mean,"
                    "post_smooth_mean,action_pre_ratio,post_action_ratio,"
                    "motion_active_pct,n_samples,smooth_global_max\n")
    print(f"  {len(anom_rows)} anomaly rows")

    # ── Write web_motion_profiles.pdf ─────────────────────────────────────────
    print(f"Writing {PDF_PATH} …")
    rec_map = {r["recording_id"]: r for r in recordings}
    with PdfPages(str(PDF_PATH)) as pdf:
        # Cover page
        fig_cover, ax_c = plt.subplots(figsize=(11.7, 8.3))
        ax_c.axis("off")
        lines = [
            "Web Motion Graph — 130 Recording Profiles",
            "",
            f"Dataset: recordings/",
            f"Source:  meta.json → events.motion_samples",
            f"Y-axis:  smooth_scaled/1000, enter_level_scaled/1000, exit_level_scaled/1000",
            f"X-axis:  ts_ms offset from first sample",
            "",
            "Curves:  green=smooth  orange=enter_threshold  red=exit_threshold",
            "Strip:   dark-green=ACTIVE  dark-red=INACTIVE",
            "Shading: phase windows from timeline",
            "",
            f"Total recordings: {len(recordings)}",
            f"Total motion samples: {len(ts_rows):,}",
            f"Recordings with flags: {sum(1 for a in all_analyses if a['flags'])}",
        ]
        ax_c.text(0.05, 0.95, "\n".join(lines), transform=ax_c.transAxes,
                  va="top", fontsize=10, family="monospace")
        pdf.savefig(fig_cover, bbox_inches="tight")
        plt.close(fig_cover)

        # One page per recording, ordered by label then recording_id
        sorted_recs = sorted(recordings, key=lambda r: (r["label"], r["recording_id"]))
        for i, rec in enumerate(sorted_recs):
            print(f"  PDF page {i+1}/{len(sorted_recs)} {rec['recording_id']}", end="\r", flush=True)
            a = amap[rec["recording_id"]]
            fig = plt.figure(figsize=(11.7, 4.5))
            gs  = fig.add_gridspec(2, 1, height_ratios=[4, 0.5], hspace=0.08)
            ax_top   = fig.add_subplot(gs[0])
            ax_state = fig.add_subplot(gs[1], sharex=ax_top)
            plot_recording(rec, a, ax_top, ax_state)
            plt.setp(ax_top.get_xticklabels(), visible=False)
            fig.patch.set_facecolor("#1a1a2e")
            ax_top.set_facecolor("#16213e")
            ax_state.set_facecolor("#0f3460")
            for ax in (ax_top, ax_state):
                ax.tick_params(colors="white", labelsize=6)
                ax.yaxis.label.set_color("white")
                ax.xaxis.label.set_color("white")
                ax.title.set_color("white")
                for spine in ax.spines.values():
                    spine.set_edgecolor("#444")
            pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
    print(f"\n  PDF written: {PDF_PATH}")

    # ── Summary printout ──────────────────────────────────────────────────────
    total_flagged = sum(1 for a in all_analyses if a["flags"])
    print()
    print("=" * 60)
    print("WEB MOTION GRAPH ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total recordings:     {len(recordings)}")
    print(f"Total motion samples: {len(ts_rows):,}")
    print(f"Recordings with flags:{total_flagged}")
    print()

    # Per-label table
    print(f"{'Label':<22} {'N':>3}  "
          f"{'pre_sm':>8}  {'act_sm':>8}  {'post_sm':>8}  "
          f"{'act/pre':>7}  {'flags':>5}")
    for lbl in sorted(ACTIVE_LABELS | IDLE_LABELS):
        pre_arr  = np.array(label_pre_means[lbl])    if label_pre_means[lbl]    else np.array([])
        act_arr  = np.array(label_action_means[lbl]) if label_action_means[lbl] else np.array([])
        post_arr = np.array(label_post_means[lbl])   if label_post_means[lbl]   else np.array([])
        n = max(len(pre_arr), len(act_arr))
        pre_m  = pre_arr.mean()  if len(pre_arr)  > 0 else float("nan")
        act_m  = act_arr.mean()  if len(act_arr)  > 0 else float("nan")
        post_m = post_arr.mean() if len(post_arr) > 0 else float("nan")
        ratio  = act_m / pre_m if (not math.isnan(act_m) and not math.isnan(pre_m) and pre_m > 0.01) else float("nan")
        flag_n = sum(1 for a in all_analyses if a["label"] == lbl and a["flags"])
        print(f"  {lbl:<22} {n:>3}  "
              f"{pre_m:>8.3f}  {act_m:>8.3f}  {post_m:>8.3f}  "
              f"{'N/A':>7}" if math.isnan(ratio) else
              f"  {lbl:<22} {n:>3}  "
              f"{pre_m:>8.3f}  {act_m:>8.3f}  {post_m:>8.3f}  "
              f"{ratio:>7.2f}  {flag_n:>5}"
              )

    print()
    print("Flagged recordings:")
    for a in all_analyses:
        if a["flags"]:
            print(f"  {a['recording_id']} [{a['label']}]")
            for fl in a["flags"]:
                print(f"    · {fl}")

    print()
    print(f"Output files:")
    print(f"  {TIMESERIES}")
    print(f"  {SUMMARY}")
    print(f"  {ANOMALIES}")
    print(f"  {PDF_PATH}")
    print(f"  {OUT / 'motion_graph_source.md'}")


if __name__ == "__main__":
    main()
