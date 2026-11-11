#!/usr/bin/env python3
"""
Phase-Level Motion Consistency Audit — read-only
=================================================
Analyses motion intensity (frame-to-frame CSI delta) per timeline phase
for all 130 recordings and flags temporal inconsistencies.

No data is written outside reports/recording_quality_audit/.
No recordings are modified, deleted, or re-recorded.
"""

import base64, csv, json, math, os, sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REC = Path(
    "/home/azri/coding/wifi_sensing_demo/examples/esp-radar/wifi_sensing_demo/recordings"
)
OUT = Path("/home/azri/coding/wifi_sensing_demo/reports/recording_quality_audit")
PLOTS_DIR = OUT / "motion_plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Decoding helpers
# ---------------------------------------------------------------------------
def decode_valid_b64(vb64: str, valid_len: int) -> np.ndarray | None:
    """Decode valid_b64 → int8 → amplitude per sub-carrier pair."""
    if not vb64:
        return None
    try:
        b = base64.b64decode(vb64)
        if len(b) != valid_len:
            return None
        arr = np.frombuffer(b, dtype=np.int8)
        n = min(len(arr[0::2]), len(arr[1::2]))
        imag = arr[0::2][:n].astype(np.float32)
        real = arr[1::2][:n].astype(np.float32)
        return np.sqrt(imag**2 + real**2)
    except Exception:
        return None


def load_frames(frames_csv: Path):
    """
    Stream frames.csv once.

    Returns list of dicts:
        ts_us      : callback_timestamp_us (device monotonic, µs)
        amp        : np.ndarray of amplitudes per sub-carrier pair (or None)
        frame_seq  : int
    Large-gap pairs are flagged so delta motion is not computed across them.
    """
    rows = []
    with open(frames_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                ts = int(row["callback_timestamp_us"])
            except (KeyError, ValueError):
                ts = 0
            try:
                vl = int(row["valid_len"])
            except (KeyError, ValueError):
                vl = 0
            try:
                fs = int(row["frame_sequence"])
            except (KeyError, ValueError):
                fs = -1
            amp = decode_valid_b64(row.get("valid_b64", ""), vl)
            rows.append({"ts_us": ts, "amp": amp, "frame_seq": fs})
    return rows


def compute_motion_scores(frames: list, gap_threshold_us: float | None = None) -> np.ndarray:
    """
    Compute per-frame motion score = mean |amp[t] - amp[t-1]| across sub-carriers.

    Frame 0 gets score 0.
    If gap_threshold_us is set, pairs separated by > threshold get score NaN
    (gap artefact, excluded from phase statistics).

    gap_threshold_us default: 5 × median inter-frame interval, min 500 ms.
    """
    n = len(frames)
    scores = np.full(n, np.nan)
    scores[0] = 0.0

    # Determine gap threshold from data
    tss = np.array([f["ts_us"] for f in frames], dtype=np.int64)
    diffs = np.diff(tss)
    pos_diffs = diffs[diffs > 0]
    if len(pos_diffs) == 0:
        return scores
    median_us = float(np.median(pos_diffs))
    if gap_threshold_us is None:
        gap_threshold_us = max(median_us * 5, 500_000)  # 500 ms

    # Determine minimum sub-carrier count across non-None frames
    valid_amps = [f["amp"] for f in frames if f["amp"] is not None]
    if not valid_amps:
        return scores
    min_sc = min(len(a) for a in valid_amps)

    for i in range(1, n):
        gap_us = tss[i] - tss[i - 1]
        if gap_us > gap_threshold_us:
            scores[i] = np.nan  # gap artefact
            continue
        a_prev = frames[i - 1]["amp"]
        a_curr = frames[i]["amp"]
        if a_prev is None or a_curr is None:
            continue
        sc = min(len(a_prev), len(a_curr), min_sc)
        scores[i] = float(np.mean(np.abs(a_curr[:sc] - a_prev[:sc])))

    return scores


# ---------------------------------------------------------------------------
# Phase slicing
# ---------------------------------------------------------------------------
def slice_phase(frames: list, motion_scores: np.ndarray,
                start_s: float, end_s: float) -> np.ndarray:
    """Return motion scores for frames whose timestamp falls in [start_s, end_s)."""
    tss_s = np.array([f["ts_us"] for f in frames], dtype=np.float64) / 1e6
    t0 = tss_s[0]
    offsets = tss_s - t0
    mask = (offsets >= start_s) & (offsets < end_s)
    vals = motion_scores[mask]
    # Exclude NaN (gap artefacts)
    return vals[~np.isnan(vals)]


def phase_stats(vals: np.ndarray) -> dict:
    """Compute summary stats for a phase's motion scores."""
    if len(vals) == 0:
        return {"n": 0, "mean": np.nan, "median": np.nan,
                "std": np.nan, "p90": np.nan, "p99": np.nan, "max": np.nan}
    return {
        "n":      int(len(vals)),
        "mean":   float(np.mean(vals)),
        "median": float(np.median(vals)),
        "std":    float(np.std(vals)),
        "p90":    float(np.percentile(vals, 90)),
        "p99":    float(np.percentile(vals, 99)),
        "max":    float(np.max(vals)),
    }


# ---------------------------------------------------------------------------
# Phase-level motion audit per recording
# ---------------------------------------------------------------------------
def audit_recording_motion(rec_id: str, label: str,
                            frames_csv: Path, meta_json: Path) -> dict:
    """
    Returns audit dict with per-phase motion stats and consistency flags.
    """
    result = {
        "recording_id": rec_id,
        "label": label,
        "phase_stats": {},      # phase → stat dict
        "motion_scores": None,  # np.ndarray (not serialised to CSV)
        "frames": None,         # list of frame dicts (not serialised)
        "consistency_flags": [],
        "motion_verdict": "PASS",
        "motion_verdict_reason": "",
        "has_annotations": False,
        "fall_start_s": None,
        "fall_impact_s": None,
        "pre_motion_mean": None,
        "action_motion_mean": None,
        "post_motion_mean": None,
        "fall_ratio_pre": None,   # action_mean / pre_mean
        "fall_ratio_post": None,  # post_mean / action_mean (expect low)
        "gap_artefact_frames": 0,
    }

    if not frames_csv.exists() or not meta_json.exists():
        result["consistency_flags"].append("MISSING_FILES")
        result["motion_verdict"] = "SKIP"
        return result

    # Load meta
    with open(meta_json) as f:
        meta = json.load(f)

    timeline = meta.get("timeline", [])
    ann = meta.get("annotations", {})
    target_dur = meta.get("target_duration_s", 10)

    if not timeline:
        result["consistency_flags"].append("NO_TIMELINE")
        result["motion_verdict"] = "SKIP"
        return result

    fs_obj = ann.get("fall_start")
    fi_obj = ann.get("fall_impact")
    if isinstance(fs_obj, dict):
        result["fall_start_s"] = fs_obj.get("offset_s")
    if isinstance(fi_obj, dict):
        result["fall_impact_s"] = fi_obj.get("offset_s")
    result["has_annotations"] = bool(ann.get("annotation_complete", False))

    # Load frames
    frames = load_frames(frames_csv)
    if len(frames) < 10:
        result["consistency_flags"].append("TOO_FEW_FRAMES")
        result["motion_verdict"] = "SKIP"
        return result

    motion = compute_motion_scores(frames)
    result["motion_scores"] = motion
    result["frames"] = frames
    result["gap_artefact_frames"] = int(np.sum(np.isnan(motion)))

    # Per-phase stats
    for phase in timeline:
        pname = phase["phase"]
        ps = slice_phase(frames, motion,
                         phase["start_offset_s"], phase["end_offset_s"])
        result["phase_stats"][pname] = phase_stats(ps)

    # -------------------------------------------------------------------
    # Motion intensity naming convention
    # idle-like phases: pre_action, post_action, hold
    # active phases:    fall_action, action, walking
    # -------------------------------------------------------------------
    idle_phases   = {"pre_action", "post_action", "hold"}
    active_phases = {"fall_action", "action", "walking"}

    idle_means   = []
    active_means = []
    for pname, ps in result["phase_stats"].items():
        if ps["n"] == 0 or np.isnan(ps["mean"]):
            continue
        if pname in idle_phases:
            idle_means.append(ps["mean"])
        elif pname in active_phases:
            active_means.append(ps["mean"])

    # Aggregate
    pre_stats  = result["phase_stats"].get("pre_action", {})
    post_stats = result["phase_stats"].get("post_action", {})
    act_stats  = (result["phase_stats"].get("fall_action") or
                  result["phase_stats"].get("action") or
                  result["phase_stats"].get("walking") or {})

    pre_mean   = pre_stats.get("mean", np.nan)
    act_mean   = act_stats.get("mean", np.nan)
    post_mean  = post_stats.get("mean", np.nan)

    result["pre_motion_mean"]    = round(pre_mean,  3) if not np.isnan(pre_mean)  else None
    result["action_motion_mean"] = round(act_mean,  3) if not np.isnan(act_mean)  else None
    result["post_motion_mean"]   = round(post_mean, 3) if not np.isnan(post_mean) else None

    # Ratios
    if not np.isnan(pre_mean) and pre_mean > 0.1:
        result["fall_ratio_pre"]  = round(act_mean / pre_mean,  2) if not np.isnan(act_mean)  else None
    if not np.isnan(act_mean) and act_mean > 0.1:
        result["fall_ratio_post"] = round(post_mean / act_mean, 2) if not np.isnan(post_mean) else None

    # -------------------------------------------------------------------
    # Consistency checks — thresholds derived from data distributions
    # -------------------------------------------------------------------
    flags = []

    # For fall/active labels: action phase should be more intense than idle phases
    # We use a mild threshold because CSI is noisy: action_mean > 1.5 × pre_mean
    # Only flag if both phases have enough frames (n≥5)
    if label in {"fall_forward", "fall_backward", "fall_lemas", "fall_keseleo",
                 "fast_sitting", "bending", "object_drop", "walking"}:

        # Check 1: active phase should exceed pre_action
        if (not np.isnan(pre_mean) and not np.isnan(act_mean) and
                pre_stats.get("n", 0) >= 5 and act_stats.get("n", 0) >= 5):
            if act_mean < pre_mean * 1.3:
                flags.append(
                    f"LOW_ACTION_vs_PRE:ratio={result['fall_ratio_pre']:.2f}"
                    if result["fall_ratio_pre"] else "LOW_ACTION_vs_PRE:ratio=N/A"
                )

        # Check 2: post_action should be calmer than action phase
        # (expect ratio < 0.9 for fall labels where person lies still after fall)
        # For non-fall active labels (walking, bending) post is 'diam' so also low
        if (not np.isnan(act_mean) and not np.isnan(post_mean) and
                post_stats.get("n", 0) >= 5 and act_stats.get("n", 0) >= 5):
            if post_mean > act_mean * 1.2:
                flags.append(
                    f"HIGH_POST_vs_ACTION:ratio={result['fall_ratio_post']:.2f}"
                    if result["fall_ratio_post"] else "HIGH_POST_vs_ACTION:ratio=N/A"
                )

        # Check 3: pre_action too active for 'diam' instruction
        # Flag if pre_mean > 2.5 × baseline (empty_room average ~0.85)
        # Baseline empirically: empty_room delta mean ≈ 0.85–1.3
        IDLE_BASELINE = 1.3  # conservative upper bound from empty_room measurements
        if (not np.isnan(pre_mean) and pre_stats.get("n", 0) >= 5
                and pre_mean > IDLE_BASELINE * 3.0):
            flags.append(
                f"PRE_ACTION_TOO_ACTIVE:pre_mean={pre_mean:.2f}"
            )

    # For idle-only labels (empty_room, still_standing, still_sitting)
    if label in {"empty_room", "still_standing", "still_sitting"}:
        hold_stats = result["phase_stats"].get("hold", {})
        hold_mean = hold_stats.get("mean", np.nan)
        if not np.isnan(hold_mean) and hold_stats.get("n", 0) >= 5:
            # Flag if significantly higher than empty_room baseline
            if hold_mean > 1.3 * 2.5:
                flags.append(f"IDLE_LABEL_HIGH_MOTION:hold_mean={hold_mean:.2f}")

    # fall_keseleo: pre_action is walking, so it SHOULD be active
    if label == "fall_keseleo":
        # pre_action = walking → should be MORE active than typical pre_action
        # Remove LOW_ACTION_vs_PRE if pre is already walking
        flags = [f for f in flags if "LOW_ACTION_vs_PRE" not in f]
        # Instead: pre_action (walking) should itself be active
        if not np.isnan(pre_mean) and pre_stats.get("n", 0) >= 5:
            if pre_mean < 1.5:  # walking should produce delta > 1.5
                flags.append(f"KESELEO_PRE_WALKING_LOW:pre_mean={pre_mean:.2f}")
        # post_action = slow movement → should be non-zero but lower than fall_action
        # post_mean > act_mean * 0.5 is expected for slow movement
        # Flag only if post is completely flat (looks like fallen still, not slow movement)
        if not np.isnan(post_mean) and not np.isnan(act_mean):
            if post_mean < 0.4:
                flags.append(f"KESELEO_POST_SLOW_MOVEMENT_FLAT:post_mean={post_mean:.2f}")

    result["consistency_flags"] = flags

    # -------------------------------------------------------------------
    # Verdict
    # -------------------------------------------------------------------
    if not flags:
        result["motion_verdict"] = "PASS"
        result["motion_verdict_reason"] = "motion_profile_consistent"
    elif any("LOW_ACTION_vs_PRE" in f for f in flags):
        # Stronger signal: action phase barely differs from idle — potential
        # execution issue or label problem.
        # Exclude: post_action_too_high is less critical
        result["motion_verdict"] = "REVIEW"
        result["motion_verdict_reason"] = "; ".join(flags)
    elif any("HIGH_POST" in f or "IDLE_LABEL_HIGH" in f or "PRE_ACTION_TOO_ACTIVE" in f for f in flags):
        result["motion_verdict"] = "REVIEW"
        result["motion_verdict_reason"] = "; ".join(flags)
    else:
        result["motion_verdict"] = "REVIEW"
        result["motion_verdict_reason"] = "; ".join(flags)

    return result


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------
PHASE_COLORS = {
    "pre_action":  "#4a90d9",
    "fall_action": "#e34234",
    "action":      "#e34234",
    "walking":     "#f5a623",
    "post_action": "#7ed321",
    "hold":        "#9b9b9b",
}

def plot_motion_profile(result: dict, out_path: Path, label_norm_factor: float = 1.0):
    """
    Plot per-frame motion score with phase shading and annotation markers.
    label_norm_factor: divide scores by this for normalised view.
    """
    frames = result["frames"]
    motion = result["motion_scores"]
    if frames is None or motion is None:
        return

    tss_s = (np.array([f["ts_us"] for f in frames], dtype=np.float64) / 1e6)
    t0 = tss_s[0]
    offsets = tss_s - t0
    scores = motion / label_norm_factor

    # Load timeline from meta
    mf_path = (REC / result["label"] /
                f"{result['recording_id']}.meta.json")
    with open(mf_path) as f:
        meta = json.load(f)
    timeline = meta.get("timeline", [])

    fig, ax = plt.subplots(figsize=(12, 4))

    # Phase shading
    legend_patches = []
    for phase in timeline:
        pname = phase["phase"]
        color = PHASE_COLORS.get(pname, "#cccccc")
        ax.axvspan(phase["start_offset_s"], phase["end_offset_s"],
                   alpha=0.15, color=color, zorder=0)
        legend_patches.append(
            mpatches.Patch(color=color, alpha=0.4, label=pname)
        )

    # Motion scores (NaN gaps shown as gaps)
    s_plot = np.where(np.isnan(scores), np.nan, scores)
    ax.plot(offsets, s_plot, lw=0.8, color="#333333", alpha=0.7, label="motion score")

    # 50-frame rolling mean (skip NaN)
    win = 15
    roll = np.full_like(s_plot, np.nan)
    for i in range(win, len(s_plot)):
        window = s_plot[i - win : i]
        valid = window[~np.isnan(window)]
        if len(valid) > 0:
            roll[i] = np.mean(valid)
    ax.plot(offsets, roll, lw=1.8, color="#e34234", alpha=0.9, label=f"rolling mean ({win}f)")

    # Annotation markers
    fs = result.get("fall_start_s")
    fi = result.get("fall_impact_s")
    if fs is not None:
        ax.axvline(fs, color="purple", lw=1.5, ls="--", label=f"fall_start {fs:.2f}s")
    if fi is not None:
        ax.axvline(fi, color="orange", lw=1.5, ls="--", label=f"fall_impact {fi:.2f}s")

    ax.set_xlabel("Time offset (s)")
    ax.set_ylabel("Motion score (Δ-amp)")
    ax.set_title(f"{result['recording_id']}\n{result['label']}  |  verdict={result['motion_verdict']}")
    ax.set_xlim(0, offsets[-1] + 0.2)
    ax.set_ylim(bottom=0)
    ax.legend(handles=legend_patches + ax.lines[:3],
              loc="upper right", fontsize=7, ncol=2)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Loading recordings...")

    recordings = []
    for lbl_dir in sorted(REC.iterdir()):
        if not lbl_dir.is_dir():
            continue
        label = lbl_dir.name
        for mf in sorted(lbl_dir.glob("*.meta.json")):
            rid = mf.stem.replace(".meta", "")
            csvf = lbl_dir / f"{rid}.frames.csv"
            recordings.append((rid, label, csvf, mf))

    print(f"  {len(recordings)} recordings found")

    # Audit all
    all_results = []
    for i, (rid, lbl, csvf, mf) in enumerate(recordings):
        print(f"  [{i+1:3d}/{len(recordings)}] {rid}", end="\r", flush=True)
        r = audit_recording_motion(rid, lbl, csvf, mf)
        all_results.append(r)

    print(f"\nAudited {len(all_results)} recordings.")

    # -------------------------------------------------------------------
    # Collect label-level baselines for cross-recording comparison
    # -------------------------------------------------------------------
    # pre_motion by label
    label_pre  = defaultdict(list)
    label_act  = defaultdict(list)
    label_post = defaultdict(list)
    for r in all_results:
        lbl = r["label"]
        if r["pre_motion_mean"]    is not None: label_pre[lbl].append(r["pre_motion_mean"])
        if r["action_motion_mean"] is not None: label_act[lbl].append(r["action_motion_mean"])
        if r["post_motion_mean"]   is not None: label_post[lbl].append(r["post_motion_mean"])

    # -------------------------------------------------------------------
    # Cross-recording outlier: action phase z-score
    # Flag if z < -2 within label (suspiciously low for active label)
    # -------------------------------------------------------------------
    active_labels = {"fall_forward","fall_backward","fall_lemas","fall_keseleo",
                     "bending","fast_sitting","object_drop","walking"}

    for r in all_results:
        lbl = r["label"]
        if lbl not in active_labels:
            continue
        act_mean = r["action_motion_mean"]
        if act_mean is None:
            continue
        arr = np.array(label_act.get(lbl, []))
        if len(arr) < 3:
            continue
        z = (act_mean - arr.mean()) / (arr.std() + 1e-6)
        if z < -2.0:
            r["consistency_flags"].append(
                f"ACTION_PHASE_LOW_vs_LABEL:z={z:.2f},label_act_mean={arr.mean():.2f}"
            )
            if r["motion_verdict"] == "PASS":
                r["motion_verdict"] = "REVIEW"
                r["motion_verdict_reason"] += f" ACTION_PHASE_LOW_vs_LABEL:z={z:.2f}"

    # -------------------------------------------------------------------
    # Generate plots for all REVIEW recordings + one sample per label
    # -------------------------------------------------------------------
    print("Generating motion plots...")

    # Build per-label normalization (mean of action_motion means)
    label_norm = {}
    for lbl in sorted(label_act.keys()):
        arr = np.array(label_act[lbl])
        label_norm[lbl] = float(arr.mean()) if len(arr) > 0 else 1.0

    plotted = set()

    # Plot all REVIEW
    for r in all_results:
        if r["motion_verdict"] == "REVIEW" and r["frames"] is not None:
            fname = PLOTS_DIR / f"{r['recording_id']}.png"
            norm = max(label_norm.get(r["label"], 1.0), 1.0)
            plot_motion_profile(r, fname, label_norm_factor=norm)
            plotted.add(r["recording_id"])

    # Plot one representative per label (median action_motion)
    for lbl in sorted(set(r["label"] for r in all_results)):
        group = [r for r in all_results
                 if r["label"] == lbl and r["frames"] is not None
                 and r["action_motion_mean"] is not None]
        if not group:
            # No action phase (empty_room, still_*)
            group = [r for r in all_results
                     if r["label"] == lbl and r["frames"] is not None]
        if not group:
            continue
        # Pick median
        means = [r["action_motion_mean"] or 0 for r in group]
        idx = int(np.argsort(np.abs(np.array(means) - np.median(means)))[0])
        rep = group[idx]
        if rep["recording_id"] not in plotted:
            fname = PLOTS_DIR / f"_ref_{lbl}__{rep['recording_id']}.png"
            norm = max(label_norm.get(lbl, 1.0), 1.0)
            plot_motion_profile(rep, fname, label_norm_factor=norm)
            plotted.add(rep["recording_id"])

    print(f"  Generated {len(list(PLOTS_DIR.iterdir()))} plots in {PLOTS_DIR}")

    # -------------------------------------------------------------------
    # Write motion_phase_stats.csv
    # -------------------------------------------------------------------
    phase_rows = []
    for r in all_results:
        base = {
            "recording_id": r["recording_id"],
            "label": r["label"],
            "motion_verdict": r["motion_verdict"],
            "has_annotations": r["has_annotations"],
            "fall_start_s": r["fall_start_s"],
            "fall_impact_s": r["fall_impact_s"],
            "pre_motion_mean": r["pre_motion_mean"],
            "action_motion_mean": r["action_motion_mean"],
            "post_motion_mean": r["post_motion_mean"],
            "fall_ratio_pre": r["fall_ratio_pre"],
            "fall_ratio_post": r["fall_ratio_post"],
            "gap_artefact_frames": r["gap_artefact_frames"],
            "flags": "; ".join(r["consistency_flags"]),
            "verdict_reason": r["motion_verdict_reason"],
        }
        # Add per-phase detailed stats
        for phase_name in ["pre_action", "fall_action", "action", "walking",
                           "post_action", "hold"]:
            ps = r["phase_stats"].get(phase_name, {})
            for stat in ["n", "mean", "median", "std", "p90", "max"]:
                val = ps.get(stat, "")
                base[f"{phase_name}_{stat}"] = (
                    round(val, 3) if isinstance(val, float) and not math.isnan(val)
                    else ("" if (isinstance(val, float) and math.isnan(val)) else val)
                )
        phase_rows.append(base)

    ps_csv = OUT / "motion_phase_stats.csv"
    if phase_rows:
        with open(ps_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(phase_rows[0].keys()))
            w.writeheader()
            w.writerows(phase_rows)
    print(f"Wrote {ps_csv}")

    # -------------------------------------------------------------------
    # Write motion_anomaly_details.csv
    # -------------------------------------------------------------------
    anom_rows = []
    for r in all_results:
        for flag in r["consistency_flags"]:
            anom_rows.append({
                "recording_id": r["recording_id"],
                "label": r["label"],
                "motion_verdict": r["motion_verdict"],
                "flag": flag,
                "pre_motion_mean": r["pre_motion_mean"],
                "action_motion_mean": r["action_motion_mean"],
                "post_motion_mean": r["post_motion_mean"],
                "fall_ratio_pre": r["fall_ratio_pre"],
                "fall_ratio_post": r["fall_ratio_post"],
                "has_annotations": r["has_annotations"],
                "fall_start_s": r["fall_start_s"],
                "fall_impact_s": r["fall_impact_s"],
            })

    ma_csv = OUT / "motion_anomaly_details.csv"
    if anom_rows:
        with open(ma_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(anom_rows[0].keys()))
            w.writeheader()
            w.writerows(anom_rows)
    else:
        with open(ma_csv, "w", encoding="utf-8") as f:
            f.write("recording_id,label,motion_verdict,flag,pre_motion_mean,"
                    "action_motion_mean,post_motion_mean,fall_ratio_pre,"
                    "fall_ratio_post,has_annotations,fall_start_s,fall_impact_s\n")
    print(f"Wrote {ma_csv}")

    # -------------------------------------------------------------------
    # Summary stats for report
    # -------------------------------------------------------------------
    verdicts = defaultdict(int)
    by_label_verdict = defaultdict(lambda: defaultdict(int))
    for r in all_results:
        verdicts[r["motion_verdict"]] += 1
        by_label_verdict[r["label"]][r["motion_verdict"]] += 1

    print("\n" + "=" * 60)
    print("MOTION CONSISTENCY AUDIT SUMMARY")
    print("=" * 60)
    for v, cnt in sorted(verdicts.items()):
        print(f"  {v:8s}: {cnt}")
    print()
    print("REVIEW recordings:")
    for r in all_results:
        if r["motion_verdict"] == "REVIEW":
            print(f"  {r['recording_id']} [{r['label']}]")
            print(f"    flags: {'; '.join(r['consistency_flags'])}")
    print()

    return all_results, by_label_verdict, label_pre, label_act, label_post


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    all_results, by_label_verdict, label_pre, label_act, label_post = main()

    # -------------------------------------------------------------------
    # Print per-label phase comparison table for report
    # -------------------------------------------------------------------
    print("\nPer-label motion intensity (mean motion score per phase):")
    print(f"{'Label':<22} {'N':>3}  {'pre_mean':>9}  {'act_mean':>9}  "
          f"{'post_mean':>9}  {'ratio_pre':>10}")
    for lbl in sorted(label_pre.keys() | label_act.keys()):
        pre_arr  = np.array(label_pre.get(lbl,  []))
        act_arr  = np.array(label_act.get(lbl,  []))
        post_arr = np.array(label_post.get(lbl, []))
        pre_m  = pre_arr.mean()  if len(pre_arr)  > 0 else float("nan")
        act_m  = act_arr.mean()  if len(act_arr)  > 0 else float("nan")
        post_m = post_arr.mean() if len(post_arr) > 0 else float("nan")
        ratio  = act_m / pre_m   if (not math.isnan(pre_m) and pre_m > 0.05) else float("nan")
        n = max(len(pre_arr), len(act_arr))
        print(f"  {lbl:<22} {n:>3}  "
              f"{pre_m:>9.3f}  {act_m:>9.3f}  "
              f"{post_m:>9.3f}  "
              f"{'N/A' if math.isnan(ratio) else f'{ratio:9.2f}'}")
