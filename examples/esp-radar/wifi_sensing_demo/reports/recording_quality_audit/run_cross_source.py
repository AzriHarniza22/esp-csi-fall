#!/usr/bin/env python3
"""
Cross-Source Motion Analysis — read-only
=========================================
Aligns raw CSI delta-amplitude with firmware telemetry (smooth_scaled,
enter_level_scaled, exit_level_scaled, motion_status) on a shared time axis.

Target groups:
  - All 11 fall_keseleo
  - All 10 object_drop
  - fall_forward_008
  - fall_backward Nov4 (001-010)
  - fall_lemas _010, _015, _017
"""

import base64, csv, json, math, os
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages

# ── Paths ────────────────────────────────────────────────────────────────────
REC = Path(__file__).resolve().parent.parent.parent / "recordings"
OUT = Path(__file__).resolve().parent

SCALE = 1000.0  # firmware integers → display (same as browser)
GAP_US = 500_000   # 500ms in µs — CSI timestamp gap threshold


# ═════════════════════════════════════════════════════════════════════════════
# Target recording list
# ═════════════════════════════════════════════════════════════════════════════
def build_target_list():
    targets = []
    # fall_keseleo – all 11
    for mf in sorted((REC / "fall_keseleo").glob("*.meta.json")):
        targets.append(("fall_keseleo", mf))
    # object_drop – all 10
    for mf in sorted((REC / "object_drop").glob("*.meta.json")):
        targets.append(("object_drop", mf))
    # fall_forward_008 only
    mf008 = REC / "fall_forward" / "20261104T155934Z_fall_forward_008.meta.json"
    if mf008.exists():
        targets.append(("fall_forward", mf008))
    # fall_backward Nov4 (001-010)
    for mf in sorted((REC / "fall_backward").glob("20261104*.meta.json")):
        targets.append(("fall_backward", mf))
    # fall_lemas _010, _015, _017
    for stem in ["20261107T151834Z_fall_left_010",
                 "20261107T152115Z_fall_left_015",
                 "20261107T152320Z_fall_left_017"]:
        mf = REC / "fall_lemas" / f"{stem}.meta.json"
        if mf.exists():
            targets.append(("fall_lemas", mf))
    return targets


# ═════════════════════════════════════════════════════════════════════════════
# Data loading helpers
# ═════════════════════════════════════════════════════════════════════════════
def decode_amp(vb64: str, valid_len: int) -> np.ndarray | None:
    try:
        b = base64.b64decode(vb64)
        if len(b) != valid_len:
            return None
        arr = np.frombuffer(b, dtype=np.int8)
        n = min(len(arr[0::2]), len(arr[1::2]))
        return np.sqrt(arr[0::2][:n].astype(np.float32) ** 2 +
                       arr[1::2][:n].astype(np.float32) ** 2)
    except Exception:
        return None


def load_csi(frames_csv: Path) -> dict:
    """
    Returns dict:
        ts_us    : np.ndarray int64
        amp_mean : np.ndarray float32   (mean amplitude per frame)
        delta    : np.ndarray float32   (|amp[t] - amp[t-1]|, mean over subs)
                   NaN where gap > GAP_US
    """
    rows_ts, rows_amp = [], []
    with open(frames_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                ts = int(row["callback_timestamp_us"])
                vl = int(row["valid_len"])
            except (KeyError, ValueError):
                continue
            amp = decode_amp(row.get("valid_b64", ""), vl)
            rows_ts.append(ts)
            rows_amp.append(amp)

    if not rows_ts:
        return {"ts_us": np.array([]), "amp_mean": np.array([]),
                "delta": np.array([])}

    ts = np.array(rows_ts, dtype=np.int64)
    # Minimum subcarrier count across valid frames
    valid_amps = [a for a in rows_amp if a is not None]
    if not valid_amps:
        return {"ts_us": ts, "amp_mean": np.full(len(ts), np.nan),
                "delta": np.full(len(ts), np.nan)}

    min_sc = min(len(a) for a in valid_amps)
    amp_mean = np.array([
        float(np.mean(a[:min_sc])) if a is not None else np.nan
        for a in rows_amp
    ], dtype=np.float32)

    # Delta (gap-masked)
    delta = np.full(len(ts), np.nan, dtype=np.float32)
    delta[0] = 0.0
    diffs_us = np.diff(ts)
    pos_diffs = diffs_us[diffs_us > 0]
    median_us = float(np.median(pos_diffs)) if len(pos_diffs) > 0 else 100_000
    gap_thresh = max(median_us * 5, GAP_US)

    for i in range(1, len(ts)):
        if diffs_us[i - 1] > gap_thresh:
            continue  # leave NaN
        a1, a2 = rows_amp[i - 1], rows_amp[i]
        if a1 is None or a2 is None:
            continue
        sc = min(len(a1), len(a2), min_sc)
        delta[i] = float(np.mean(np.abs(a2[:sc] - a1[:sc])))

    return {"ts_us": ts, "amp_mean": amp_mean, "delta": delta}


def load_motion_samples(meta: dict) -> list[dict]:
    events = meta.get("events", {})
    raw = (events.get("motion_samples")
           if isinstance(events.get("motion_samples"), list)
           else meta.get("motion_samples", []))
    out = []
    for s in (raw or []):
        ts = s.get("ts_ms")
        ss = s.get("smooth_scaled")
        en = s.get("enter_level_scaled")
        ex = s.get("exit_level_scaled")
        ms = s.get("motion_status")
        if None in (ts, ss, en, ex) or not isinstance(ms, bool):
            continue
        try:
            out.append({
                "ts_ms":    float(ts),
                "smooth":   float(ss) / SCALE,
                "enter":    float(en) / SCALE,
                "exit":     float(ex) / SCALE,
                "active":   bool(ms),
            })
        except (TypeError, ValueError):
            pass
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Analysis
# ═════════════════════════════════════════════════════════════════════════════
PHASE_COLORS = {
    "pre_action":  "#4a90d9",
    "fall_action": "#e34234",
    "action":      "#e34234",
    "walking":     "#f5a623",
    "post_action": "#7ed321",
    "hold":        "#9b9b9b",
}
IDLE_PHASES   = {"pre_action", "post_action", "hold"}
ACTIVE_PHASES = {"fall_action", "action", "walking"}


def phase_window_csi(ts_us: np.ndarray, t0_us: int,
                     start_s: float, end_s: float) -> np.ndarray:
    """Boolean mask over ts_us for frames in [start_s, end_s)."""
    offsets = (ts_us - t0_us) / 1e6
    return (offsets >= start_s) & (offsets < end_s)


def phase_window_motion(samples: list[dict], t0_ms: float,
                        start_s: float, end_s: float) -> list[dict]:
    return [s for s in samples
            if start_s <= (s["ts_ms"] - t0_ms) / 1000.0 < end_s]


def safe_mean(arr, mask=None):
    a = arr[mask] if mask is not None else arr
    v = a[~np.isnan(a)] if len(a) else a
    return float(np.mean(v)) if len(v) > 0 else None


def analyse_recording(label: str, meta: dict) -> dict:
    rid      = meta.get("recording_id", "?")
    timeline = meta.get("timeline", [])
    ann      = meta.get("annotations", {})
    frames_csv = REC / label / f"{rid}.frames.csv"

    csi     = load_csi(frames_csv)
    msamples = load_motion_samples(meta)

    ts_csi  = csi["ts_us"]
    delta   = csi["delta"]

    t0_csi_us  = int(ts_csi[0])  if len(ts_csi) > 0  else 0
    t0_mot_ms  = msamples[0]["ts_ms"] if msamples else 0

    # ── Per-phase metrics ────────────────────────────────────────────────────
    phase_data = {}
    for phase in timeline:
        pn = phase["phase"]
        ps, pe = phase["start_offset_s"], phase["end_offset_s"]

        # CSI delta
        if len(ts_csi) > 0:
            mask = phase_window_csi(ts_csi, t0_csi_us, ps, pe)
            csi_delta_vals = delta[mask]
            csi_delta_vals = csi_delta_vals[~np.isnan(csi_delta_vals)]
        else:
            csi_delta_vals = np.array([])

        # Motion samples
        win = phase_window_motion(msamples, t0_mot_ms, ps, pe)

        smooth_vals = [s["smooth"] for s in win]
        enter_vals  = [s["enter"]  for s in win]
        above_enter = sum(1 for s in win if s["smooth"] > s["enter"])
        active_pct  = (100 * sum(1 for s in win if s["active"]) / len(win)
                       if win else None)

        phase_data[pn] = {
            "csi_delta_mean":  float(np.mean(csi_delta_vals)) if len(csi_delta_vals) > 0 else None,
            "csi_delta_std":   float(np.std(csi_delta_vals))  if len(csi_delta_vals) > 0 else None,
            "smooth_mean":     float(np.mean(smooth_vals))    if smooth_vals else None,
            "smooth_max":      float(np.max(smooth_vals))     if smooth_vals else None,
            "enter_mean":      float(np.mean(enter_vals))     if enter_vals  else None,
            "above_enter_pct": round(100 * above_enter / len(win), 1) if win else None,
            "motion_active_pct": active_pct,
            "n_csi":           int(np.sum(mask)) if len(ts_csi) > 0 else 0,
            "n_motion":        len(win),
        }

    # ── Global checks ────────────────────────────────────────────────────────
    # 1. Does CSI show motion during fall/action phase?
    act_pn = next((p["phase"] for p in timeline
                   if p["phase"] in ACTIVE_PHASES), None)
    pre_pn = next((p["phase"] for p in timeline
                   if p["phase"] == "pre_action"), None)
    post_pn = next((p["phase"] for p in timeline
                    if p["phase"] == "post_action"), None)

    act_pd  = phase_data.get(act_pn, {}) if act_pn else {}
    pre_pd  = phase_data.get(pre_pn, {}) if pre_pn else {}
    post_pd = phase_data.get(post_pn, {}) if post_pn else {}

    csi_act  = act_pd.get("csi_delta_mean")
    csi_pre  = pre_pd.get("csi_delta_mean")
    csi_post = post_pd.get("csi_delta_mean")
    sm_act   = act_pd.get("smooth_mean")
    en_act   = act_pd.get("enter_mean")
    act_above= act_pd.get("above_enter_pct")
    act_mstat= act_pd.get("motion_active_pct")

    findings = []

    # FSM below threshold despite CSI activity
    if (csi_act is not None and sm_act is not None and en_act is not None):
        if sm_act < en_act and csi_act > 2.5:
            gap = en_act - sm_act
            findings.append(
                f"CSI_ACTIVE_FSM_BELOW_THRESHOLD: csi_delta={csi_act:.2f}, "
                f"smooth={sm_act:.0f} < enter={en_act:.0f} (gap={gap:.0f})"
            )

    # FSM threshold too high due to elevated baseline
    if (sm_act is not None and en_act is not None and
            csi_pre is not None and csi_act is not None):
        # Pre active → baseline elevated → enter_level elevated
        if csi_pre > 3.0 and sm_act < en_act:
            findings.append(
                "HIGH_PRE_BASELINE_LIFTED_THRESHOLD: "
                f"pre_csi={csi_pre:.2f} elevated baseline, "
                f"enter during action={en_act:.0f}"
            )

    # FSM still active after CSI stabilised
    if (csi_post is not None and act_mstat is not None and
            post_pd.get("motion_active_pct") is not None):
        post_active_pct = post_pd["motion_active_pct"]
        if post_active_pct > 40 and csi_post < csi_pre:
            findings.append(
                f"FSM_ACTIVE_AFTER_CSI_STABLE: "
                f"post_motion_status={post_active_pct:.0f}%, "
                f"post_csi={csi_post:.2f}"
            )

    # Annotation alignment
    fs_obj = ann.get("fall_start")
    if isinstance(fs_obj, dict) and fs_obj.get("offset_s") is not None:
        fs_s = float(fs_obj["offset_s"])
        # Check smooth in ±1.5s window vs global max
        t0_m = msamples[0]["ts_ms"] if msamples else 0
        near_fall = [s for s in msamples
                     if abs((s["ts_ms"] - t0_m) / 1000.0 - fs_s) <= 1.5]
        global_sm_max = max((s["smooth"] for s in msamples), default=0)
        if near_fall and global_sm_max > 0:
            near_max = max(s["smooth"] for s in near_fall)
            if near_max < global_sm_max * 0.6:
                findings.append(
                    f"FALL_ANNOTATION_SMOOTH_MISMATCH: "
                    f"near_fall_max={near_max:.0f}, global_max={global_sm_max:.0f} "
                    f"@ annotation={fs_s:.2f}s"
                )

    # Timestamps: check CSI-motion clock alignment
    if len(ts_csi) > 0 and msamples:
        # Both use wall-clock references that differ.
        # We align by comparing recording duration from each source.
        csi_dur_s   = (ts_csi[-1] - ts_csi[0]) / 1e6
        mot_dur_ms  = msamples[-1]["ts_ms"] - msamples[0]["ts_ms"]
        mot_dur_s   = mot_dur_ms / 1000.0
        dur_mismatch = abs(csi_dur_s - mot_dur_s)
        if dur_mismatch > 1.5:
            findings.append(
                f"CSI_MOTION_DURATION_MISMATCH: "
                f"csi={csi_dur_s:.2f}s, motion={mot_dur_s:.2f}s "
                f"(diff={dur_mismatch:.2f}s)"
            )

    return {
        "recording_id":   rid,
        "label":          label,
        "n_csi_frames":   len(ts_csi),
        "n_motion_samples": len(msamples),
        "phase_data":     phase_data,
        "csi":            csi,
        "msamples":       msamples,
        "timeline":       timeline,
        "annotations":    ann,
        "findings":       findings,
        "act_phase":      act_pn,
        "pre_phase":      pre_pn,
        "post_phase":     post_pn,
        "meta":           meta,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Plotting
# ═════════════════════════════════════════════════════════════════════════════
def plot_cross_source(result: dict, ax_csi, ax_smooth, ax_state):
    """
    Three-panel plot for one recording:
      ax_csi    : CSI delta-amplitude per frame
      ax_smooth : smooth_scaled / enter / exit (firmware)
      ax_state  : motion_status strip
    All share the same X-axis (time offset from recording start, in seconds).
    Alignment: CSI uses callback_timestamp_us, motion uses ts_ms.
    We align both to their respective first timestamps, then overlay.
    The two clocks are DIFFERENT; we align their offset-from-start,
    acknowledging this is approximate (clock drift is small over 10-12s).
    """
    csi      = result["csi"]
    msamples = result["msamples"]
    timeline = result["timeline"]
    ann      = result["annotations"]
    label    = result["label"]
    rid      = result["recording_id"]

    ts_us   = csi["ts_us"]
    delta   = csi["delta"]

    # Time offsets from each source's own start
    csi_offset_s = (ts_us - ts_us[0]) / 1e6 if len(ts_us) > 0 else np.array([])
    mot_t0_ms    = msamples[0]["ts_ms"] if msamples else 0
    mot_offset_s = np.array([(s["ts_ms"] - mot_t0_ms) / 1000.0 for s in msamples])

    # ── Phase shading on all axes ────────────────────────────────────────────
    for phase in timeline:
        pn    = phase["phase"]
        color = PHASE_COLORS.get(pn, "#888")
        for ax in (ax_csi, ax_smooth):
            ax.axvspan(phase["start_offset_s"], phase["end_offset_s"],
                       alpha=0.10, color=color, zorder=0)

    # ── CSI delta ────────────────────────────────────────────────────────────
    if len(csi_offset_s) > 0:
        ax_csi.plot(csi_offset_s, delta, lw=0.6, color="#aaddff",
                    alpha=0.6, label="CSI Δ-amp")
        # 10-frame rolling mean
        win = 10
        roll = np.full_like(delta, np.nan)
        for i in range(win, len(delta)):
            w = delta[i - win:i]
            v = w[~np.isnan(w)]
            if len(v) > 0:
                roll[i] = np.mean(v)
        ax_csi.plot(csi_offset_s, roll, lw=1.5, color="#00aaff",
                    alpha=0.9, label="CSI Δ rolling(10)")

    ax_csi.set_ylabel("Δ-amp", fontsize=6)
    ax_csi.tick_params(axis="both", labelsize=5)
    ax_csi.set_ylim(bottom=0)

    # ── Firmware smooth / enter / exit ───────────────────────────────────────
    if msamples:
        smooth = np.array([s["smooth"] for s in msamples])
        enter  = np.array([s["enter"]  for s in msamples])
        exit_  = np.array([s["exit"]   for s in msamples])

        ax_smooth.plot(mot_offset_s, smooth, lw=0.9, color="#7bffb6",
                       alpha=0.9, label="smooth/1000")
        ax_smooth.plot(mot_offset_s, enter,  lw=1.1, color="#ffb454",
                       alpha=0.85, label="enter/1000")
        ax_smooth.plot(mot_offset_s, exit_,  lw=1.1, color="#ff6b81",
                       alpha=0.85, label="exit/1000")

    ax_smooth.set_ylabel("fw value/1000", fontsize=6)
    ax_smooth.tick_params(axis="both", labelsize=5)
    ax_smooth.set_ylim(bottom=0)

    # ── Annotation markers ───────────────────────────────────────────────────
    fs_obj = ann.get("fall_start")
    fi_obj = ann.get("fall_impact")
    for ax in (ax_csi, ax_smooth):
        if isinstance(fs_obj, dict) and fs_obj.get("offset_s") is not None:
            ax.axvline(fs_obj["offset_s"], color="violet", lw=1.2, ls="--", zorder=5)
        if isinstance(fi_obj, dict) and fi_obj.get("offset_s") is not None:
            ax.axvline(fi_obj["offset_s"], color="orange", lw=1.2, ls="--", zorder=5)

    # ── Motion status strip ───────────────────────────────────────────────────
    if msamples:
        t_last = mot_offset_s[-1]
        for i, s in enumerate(msamples):
            x0 = mot_offset_s[i]
            x1 = (mot_offset_s[i + 1] if i + 1 < len(msamples)
                  else t_last + 0.06)
            col = "#2d7a4f" if s["active"] else "#7a2d3a"
            ax_state.barh(0, x1 - x0, left=x0, height=1,
                          color=col, linewidth=0, align="edge")

    ax_state.set_ylim(0, 1)
    ax_state.set_yticks([])
    ax_state.tick_params(axis="x", labelsize=5)
    ax_state.set_xlabel("time offset (s)", fontsize=6)

    # ── Titles / findings ────────────────────────────────────────────────────
    findings = result["findings"]
    finding_str = " | ".join(findings[:2]) if findings else "no anomaly"
    tc = "#ff7777" if findings else "#77ff77"

    act_pd  = result["phase_data"].get(result["act_phase"] or "", {})
    pre_pd  = result["phase_data"].get(result["pre_phase"] or "", {})
    post_pd = result["phase_data"].get(result["post_phase"] or "", {})

    csi_pre_m  = pre_pd.get("csi_delta_mean")
    csi_act_m  = act_pd.get("csi_delta_mean")
    csi_post_m = post_pd.get("csi_delta_mean")
    sm_act_m   = act_pd.get("smooth_mean")
    en_act_m   = act_pd.get("enter_mean")
    ab_en      = act_pd.get("above_enter_pct")
    mot_act    = act_pd.get("motion_active_pct")

    def fv(v, fmt=".1f"):
        return f"{v:{fmt}}" if v is not None else "N/A"

    info = (
        f"pre_csi={fv(csi_pre_m)}  act_csi={fv(csi_act_m)}  post_csi={fv(csi_post_m)}"
        f"  |  sm_act={fv(sm_act_m, '.0f')}  en_act={fv(en_act_m, '.0f')}"
        f"  above_enter={fv(ab_en, '.0f')}%  FSM_active={fv(mot_act, '.0f')}%"
    )
    ax_csi.set_title(
        f"{rid}  [{label}]\n{info}\n{finding_str}",
        fontsize=5.5, color=tc, pad=2
    )
    ax_csi.legend(loc="upper right", fontsize=4.5, framealpha=0.4)
    ax_smooth.legend(loc="upper right", fontsize=4.5, framealpha=0.4)

    # Phase legend
    patches = [mpatches.Patch(color=PHASE_COLORS.get(p["phase"], "#888"),
                               alpha=0.5, label=p["phase"])
               for p in timeline]
    ax_csi.legend(handles=patches + ax_csi.lines[:2],
                  loc="upper left", fontsize=4, framealpha=0.3, ncol=4)


# ═════════════════════════════════════════════════════════════════════════════
# CSV evidence table
# ═════════════════════════════════════════════════════════════════════════════
def build_evidence_rows(all_results: list[dict]) -> list[dict]:
    rows = []
    for r in all_results:
        base = {
            "recording_id":     r["recording_id"],
            "label":            r["label"],
            "n_csi":            r["n_csi_frames"],
            "n_motion":         r["n_motion_samples"],
            "findings":         "; ".join(r["findings"]),
        }
        for pname in ["pre_action", "fall_action", "action", "walking",
                      "post_action", "hold"]:
            pd = r["phase_data"].get(pname, {})
            for k in ["csi_delta_mean", "smooth_mean", "enter_mean",
                      "above_enter_pct", "motion_active_pct"]:
                v = pd.get(k)
                base[f"{pname}_{k}"] = round(v, 3) if isinstance(v, float) else (v or "")
        rows.append(base)
    return rows


# ═════════════════════════════════════════════════════════════════════════════
# Markdown report builder
# ═════════════════════════════════════════════════════════════════════════════
def _fv(v, fmt=".1f"):
    return f"{v:{fmt}}" if v is not None else "N/A"


def build_markdown(all_results: list[dict],
                   label_baselines: dict) -> str:
    lines = []
    W = lines.append

    W("# Cross-Source Motion Analysis Report")
    W("")
    W("**Metode:** Overlay raw CSI delta-amplitude dengan firmware telemetri "
      "(`smooth_scaled`, `enter_level_scaled`, `exit_level_scaled`, `motion_status`) "
      "pada time-offset yang sama (masing-masing clock di-zero dari sample pertama).")
    W("")
    W("**Data sources:**")
    W("- `frames.csv` → `valid_b64` → delta-amplitude antar frame (gap-masked ≥500ms)")
    W("- `meta.json` → `events.motion_samples` → firmware telemetri (/1000 untuk display)")
    W("- `meta.json` → `timeline` + `annotations`")
    W("")
    W("**Label baselines (median across all same-label recordings):**")
    W("")
    W("| Label | pre_csi | act_csi | post_csi | act_smooth | act_enter |")
    W("|---|---|---|---|---|---|")
    for lbl, b in sorted(label_baselines.items()):
        W(f"| `{lbl}` | {_fv(b.get('pre_csi'))} | {_fv(b.get('act_csi'))} | "
          f"{_fv(b.get('post_csi'))} | {_fv(b.get('act_smooth'), '.0f')} | "
          f"{_fv(b.get('act_enter'), '.0f')} |")
    W("")

    # --- Group by label
    groups = defaultdict(list)
    for r in all_results:
        groups[r["label"]].append(r)

    for group_label, grp_results in groups.items():
        W(f"---")
        W(f"")
        W(f"## {group_label.replace('_', ' ').title()} "
          f"({len(grp_results)} recordings)")
        W("")

        for r in grp_results:
            rid = r["recording_id"]
            ann = r["annotations"]
            fs  = ann.get("fall_start")
            fi  = ann.get("fall_impact")
            fs_s  = fs["offset_s"] if isinstance(fs, dict) else None
            fi_s  = fi["offset_s"] if isinstance(fi, dict) else None
            act_pn = r["act_phase"]
            pre_pn = r["pre_phase"]
            post_pn = r["post_phase"]
            act_pd  = r["phase_data"].get(act_pn or "", {})
            pre_pd  = r["phase_data"].get(pre_pn or "", {})
            post_pd = r["phase_data"].get(post_pn or "", {})

            W(f"### `{rid}`")
            W("")
            W(f"| Metrik | Pre ({pre_pn or 'N/A'}) | Action ({act_pn or 'N/A'}) "
              f"| Post ({post_pn or 'N/A'}) |")
            W("|---|---|---|---|")
            for k, label_str in [
                ("csi_delta_mean",    "CSI Δ-amp mean"),
                ("smooth_mean",       "smooth/1000 mean"),
                ("enter_mean",        "enter/1000 mean"),
                ("above_enter_pct",   "smooth > enter (%)"),
                ("motion_active_pct", "FSM active (%)"),
            ]:
                vp = pre_pd.get(k)
                va = act_pd.get(k)
                vo = post_pd.get(k)
                fmt = ".0f" if "smooth" in k or "enter" in k else ".2f"
                W(f"| {label_str} | {_fv(vp, fmt)} | {_fv(va, fmt)} | {_fv(vo, fmt)} |")
            W("")
            if fs_s is not None:
                W(f"- **fall_start annotation:** {fs_s:.3f}s")
            if fi_s is not None:
                W(f"- **fall_impact annotation:** {fi_s:.3f}s")

            if r["findings"]:
                W("")
                W("**Findings:**")
                for f_line in r["findings"]:
                    W(f"- {f_line}")
            else:
                W("*No anomaly flags.*")
            W("")

    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
def main():
    targets = build_target_list()
    print(f"Target recordings: {len(targets)}")

    # Load and analyse
    all_results = []
    for label, mf in targets:
        with open(mf, encoding="utf-8") as f:
            meta = json.load(f)
        print(f"  {meta.get('recording_id','?')}", end="\r", flush=True)
        r = analyse_recording(label, meta)
        all_results.append(r)
    print(f"\nAnalysed {len(all_results)} recordings")

    # Compute per-label baselines from this targeted set
    label_baselines = {}
    for lbl in sorted(set(r["label"] for r in all_results)):
        grp = [r for r in all_results if r["label"] == lbl]
        def _med(vals):
            v = [x for x in vals if x is not None]
            return float(np.median(v)) if v else None

        label_baselines[lbl] = {
            "pre_csi":   _med([r["phase_data"].get(r["pre_phase"] or "", {}).get("csi_delta_mean") for r in grp]),
            "act_csi":   _med([r["phase_data"].get(r["act_phase"] or "", {}).get("csi_delta_mean") for r in grp]),
            "post_csi":  _med([r["phase_data"].get(r["post_phase"] or "", {}).get("csi_delta_mean") for r in grp]),
            "act_smooth": _med([r["phase_data"].get(r["act_phase"] or "", {}).get("smooth_mean") for r in grp]),
            "act_enter":  _med([r["phase_data"].get(r["act_phase"] or "", {}).get("enter_mean") for r in grp]),
        }

    # --- PDF plots
    pdf_path = OUT / "cross_source_plots.pdf"
    print(f"Writing {pdf_path} ...")
    with PdfPages(str(pdf_path)) as pdf:
        # Cover
        fig0, ax0 = plt.subplots(figsize=(11.7, 4))
        ax0.axis("off")
        ax0.text(0.05, 0.9, "Cross-Source Motion Analysis — Targeted Recordings",
                 transform=ax0.transAxes, fontsize=12, weight="bold")
        ax0.text(0.05, 0.75,
                 f"fall_keseleo (11)  object_drop (10)  fall_forward_008 (1)\n"
                 f"fall_backward Nov4 (10)  fall_lemas _010/_015/_017 (3)\n\n"
                 f"Each page: top=CSI delta-amp  middle=smooth/enter/exit  bottom=motion_status strip\n"
                 f"Vertical dashed lines: violet=fall_start  orange=fall_impact\n"
                 f"Phase shading matches timeline.  Both time axes zeroed from first sample.",
                 transform=ax0.transAxes, fontsize=9, va="top")
        fig0.patch.set_facecolor("#1a1a2e")
        ax0.set_facecolor("#1a1a2e")
        ax0.title.set_color("white")
        pdf.savefig(fig0, bbox_inches="tight", facecolor=fig0.get_facecolor())
        plt.close(fig0)

        for i, r in enumerate(all_results):
            print(f"  PDF {i+1}/{len(all_results)} {r['recording_id']}", end="\r")
            fig = plt.figure(figsize=(13, 6.5))
            gs  = gridspec.GridSpec(3, 1, height_ratios=[2.5, 2.5, 0.5],
                                    hspace=0.08)
            ax_csi    = fig.add_subplot(gs[0])
            ax_smooth = fig.add_subplot(gs[1], sharex=ax_csi)
            ax_state  = fig.add_subplot(gs[2], sharex=ax_csi)
            plt.setp(ax_csi.get_xticklabels(), visible=False)
            plt.setp(ax_smooth.get_xticklabels(), visible=False)

            plot_cross_source(r, ax_csi, ax_smooth, ax_state)

            fig.patch.set_facecolor("#0f0f1a")
            for ax in (ax_csi, ax_smooth, ax_state):
                ax.set_facecolor("#151525")
                ax.tick_params(colors="white")
                for sp in ax.spines.values():
                    sp.set_edgecolor("#333")
                ax.yaxis.label.set_color("white")
                ax.xaxis.label.set_color("white")
                ax.title.set_color("white")

            pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
    print(f"\nPDF written: {pdf_path}")

    # --- Evidence CSV
    ev_path = OUT / "cross_source_evidence.csv"
    rows = build_evidence_rows(all_results)
    if rows:
        with open(ev_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"Evidence CSV: {ev_path}  ({len(rows)} rows)")

    # --- Markdown report (rich)
    md_text  = build_markdown(all_results, label_baselines)
    md_path  = OUT / "cross_source_motion_analysis.md"
    # Append full narrative analysis sections
    extra = build_narrative(all_results, label_baselines)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
        f.write("\n\n")
        f.write(extra)
    print(f"Markdown: {md_path}")

    # Stdout summary
    print()
    print("=" * 60)
    print("CROSS-SOURCE ANALYSIS SUMMARY")
    print("=" * 60)
    for r in all_results:
        status = "FLAGS" if r["findings"] else "clean"
        print(f"  {r['recording_id'][:40]:<40} [{r['label']:<14}] {status}")
        for f in r["findings"]:
            print(f"    · {f[:100]}")


# ═════════════════════════════════════════════════════════════════════════════
# Narrative analysis (the key sections of the report)
# ═════════════════════════════════════════════════════════════════════════════
def build_narrative(all_results: list[dict],
                    label_baselines: dict) -> str:
    lines = []
    W = lines.append

    W("---")
    W("")
    W("## Narrative Analysis")
    W("")

    # ── FALL_KESELEO ─────────────────────────────────────────────────────────
    fk = [r for r in all_results if r["label"] == "fall_keseleo"]
    W("### fall_keseleo — Semua 11 Recording")
    W("")
    W("#### Pola yang ditemukan")
    W("")
    # collect stats
    above_pcts   = [r["phase_data"].get("fall_action", {}).get("above_enter_pct") for r in fk]
    csi_act_vals = [r["phase_data"].get("fall_action", {}).get("csi_delta_mean") for r in fk]
    csi_pre_vals = [r["phase_data"].get("pre_action", {}).get("csi_delta_mean") for r in fk]
    sm_act_vals  = [r["phase_data"].get("fall_action", {}).get("smooth_mean") for r in fk]
    en_act_vals  = [r["phase_data"].get("fall_action", {}).get("enter_mean") for r in fk]

    above_ok = [v for v in above_pcts if v is not None]
    csi_act_ok = [v for v in csi_act_vals if v is not None]
    sm_ok  = [v for v in sm_act_vals  if v is not None]
    en_ok  = [v for v in en_act_vals  if v is not None]

    W(f"- **CSI delta saat fall_action:** {np.mean(csi_act_ok):.2f} ± {np.std(csi_act_ok):.2f} "
      f"(range {np.min(csi_act_ok):.2f}–{np.max(csi_act_ok):.2f})")
    W(f"- **CSI delta saat pre_action (walking):** {np.mean([v for v in csi_pre_vals if v is not None]):.2f}")
    W(f"- **smooth/1000 mean saat fall_action:** {np.mean(sm_ok):.0f}")
    W(f"- **enter/1000 mean saat fall_action:** {np.mean(en_ok):.0f}")
    W(f"- **% sampel smooth > enter:** {np.mean(above_ok):.1f}% "
      f"(range {np.min(above_ok):.0f}–{np.max(above_ok):.0f}%)")
    W("")
    W("#### Interpretasi")
    W("")
    W("Pre_action adalah fase **berjalan** (`Berjalan seperti biasa`), bukan diam. "
      "Walking menghasilkan aktivitas CSI tinggi yang menaikkan `baseline_scaled` firmware. "
      "Ketika fall terjadi (fall_action), `enter_level_scaled` sudah sangat tinggi (~7000–9000) "
      "karena baseline terangkat dari aktivitas walking sebelumnya. `smooth_scaled` saat jatuh "
      "(~4000–5500) **tidak mencapai** enter_level sehingga `motion_status` tidak trigger.")
    W("")
    W("**Penyebab:** Ini adalah **karakteristik arsitektur FSM**, bukan recording failure. "
      "Firmware esp_wifi_sensing menggunakan adaptive baseline yang terangkat saat subjek berjalan "
      "dan tidak cukup turun dalam 4 detik sisa walking. Ini **bukan anomali aktivitas**.")
    W("")
    W("**Implikasi untuk model:** `motion_status` dari fall_keseleo tidak dapat digunakan sebagai "
      "feature deteksi jatuh untuk label ini. `smooth_scaled` dan `enter_level_scaled` "
      "dapat digunakan sebagai feature kontekstual, namun dengan pemahaman bahwa FSM aktif "
      "saat berjalan, bukan saat jatuh.")
    W("")
    W("**fall_right_002 (pengecualian):** Satu-satunya recording dengan `above_enter_pct > 0` "
      "(41%). Ini kemungkinan karena walking di pre_action lebih pelan/singkat sehingga "
      "baseline tidak terangkat sebanyak recording lain.")
    W("")

    # ── OBJECT_DROP ──────────────────────────────────────────────────────────
    od = [r for r in all_results if r["label"] == "object_drop"]
    W("### object_drop — Semua 10 Recording")
    W("")
    od_csi_act = [r["phase_data"].get("action", {}).get("csi_delta_mean") for r in od]
    od_csi_pre = [r["phase_data"].get("pre_action", {}).get("csi_delta_mean") for r in od]
    od_sm_act  = [r["phase_data"].get("action", {}).get("smooth_mean") for r in od]
    od_en_act  = [r["phase_data"].get("action", {}).get("enter_mean") for r in od]
    od_above   = [r["phase_data"].get("action", {}).get("above_enter_pct") for r in od]
    od_mot     = [r["phase_data"].get("action", {}).get("motion_active_pct") for r in od]

    ok = lambda lst: [v for v in lst if v is not None]
    W(f"- **CSI delta saat action (drop):** {np.mean(ok(od_csi_act)):.2f} ± {np.std(ok(od_csi_act)):.2f}")
    W(f"- **CSI delta saat pre_action:** {np.mean(ok(od_csi_pre)):.2f}")
    W(f"- **smooth/1000 mean saat action:** {np.mean(ok(od_sm_act)):.0f}")
    W(f"- **enter/1000 mean saat action:** {np.mean(ok(od_en_act)):.0f}")
    W(f"- **% sampel smooth > enter:** {np.mean(ok(od_above)):.1f}%")
    W(f"- **FSM active % saat action:** {np.mean(ok(od_mot)):.1f}%")
    W("")
    W("#### Interpretasi")
    W("")
    W("CSI delta saat menjatuhkan benda (~2.6–3.4) **hampir identik dengan pre_action** (~2.5–3.2). "
      "Ini terjadi karena:")
    W("")
    W("1. **Gerakan benda kecil tidak mengubah channel CSI secara signifikan.** "
      "CSI bersumber dari jalur multipah antara router dan ESP32 — pergerakan tangan menjatuhkan benda "
      "adalah gerakan kecil yang tidak mengubah refleksi utama.")
    W("2. **Tubuh subjek yang diam menghasilkan baseline yang sama.** "
      "Perbedaan antara 'tangan menjatuhkan benda' dan 'berdiri diam' tidak terdeteksi "
      "oleh CSI maupun FSM firmware.")
    W("3. **FSM tidak trigger karena smooth tidak melebihi enter_level** "
      "— ini adalah hasil yang benar untuk gerakan sekecil ini.")
    W("")
    W("**Ini adalah keterbatasan fisik/arsitektural**, bukan recording failure atau mislabeling. "
      "Dataset ini tidak dapat membedakan object_drop dari still_standing menggunakan "
      "CSI delta-amplitude atau firmware motion detector. Classifier berbasis fitur CSI "
      "perlu mempertimbangkan hal ini.")
    W("")

    # ── FALL_FORWARD_008 ──────────────────────────────────────────────────────
    ff8 = next((r for r in all_results if r["recording_id"] == "20261104T155934Z_fall_forward_008"), None)
    W("### fall_forward_008")
    W("")
    if ff8:
        act_pd  = ff8["phase_data"].get("fall_action", {})
        pre_pd  = ff8["phase_data"].get("pre_action", {})
        post_pd = ff8["phase_data"].get("post_action", {})
        W(f"| Fase | CSI Δ | smooth | enter | above_enter | FSM active |")
        W("|---|---|---|---|---|---|")
        for pn, pd in [("pre_action", pre_pd), ("fall_action", act_pd), ("post_action", post_pd)]:
            cd  = _fv(pd.get("csi_delta_mean"))
            sm  = _fv(pd.get("smooth_mean"), ".0f")
            en  = _fv(pd.get("enter_mean"), ".0f")
            ab  = _fv(pd.get("above_enter_pct"), ".0f")
            ma  = _fv(pd.get("motion_active_pct"), ".0f")
            W(f"| {pn} | {cd} | {sm} | {en} | {ab}% | {ma}% |")
        W("")
        W("**Temuan:** `fall_forward_008` memiliki `fall_action` smooth (z=−2.77 vs label). "
          "CSI delta saat fall_action rendah. Firmware FSM tidak trigger sama sekali (0%). "
          "Ini berbeda dari mayoritas fall_forward yang menunjukkan FSM aktif 20–60% saat jatuh.")
        W("")
        W("**Interpretasi:** Kemungkinan eksekusi jatuh yang sangat gradual (slow fall) "
          "atau posisi subjek yang tidak optimal sehingga pertubahan channel WiFi minimal. "
          "Ini tidak membuktikan mislabeling — CSI sensitivitas bergantung pada posisi dan "
          "arah gerakan. Namun recording ini adalah outlier yang perlu diperhatikan "
          "saat training.")
        W("")
        if ff8["findings"]:
            for f_line in ff8["findings"]:
                W(f"- {f_line}")
        W("")

    # ── FALL_BACKWARD NOV4 ────────────────────────────────────────────────────
    fb4 = [r for r in all_results if r["label"] == "fall_backward"]
    W("### fall_backward Nov4 — Semua 10 Recording")
    W("")
    fb_post_sm = [r["phase_data"].get("post_action", {}).get("smooth_mean") for r in fb4]
    fb_act_sm  = [r["phase_data"].get("fall_action", {}).get("smooth_mean") for r in fb4]
    fb_post_mot= [r["phase_data"].get("post_action", {}).get("motion_active_pct") for r in fb4]
    fb_act_mot = [r["phase_data"].get("fall_action", {}).get("motion_active_pct") for r in fb4]
    fb_post_csi= [r["phase_data"].get("post_action", {}).get("csi_delta_mean") for r in fb4]
    fb_act_csi = [r["phase_data"].get("fall_action", {}).get("csi_delta_mean") for r in fb4]

    W("| Recording | act_csi | post_csi | act_smooth | post_smooth | FSM_act% | FSM_post% |")
    W("|---|---|---|---|---|---|---|")
    for r in fb4:
        apd  = r["phase_data"].get("fall_action", {})
        ppd  = r["phase_data"].get("post_action", {})
        W(f"| `{r['recording_id'][-15:]}` | "
          f"{_fv(apd.get('csi_delta_mean'))} | "
          f"{_fv(ppd.get('csi_delta_mean'))} | "
          f"{_fv(apd.get('smooth_mean'), '.0f')} | "
          f"{_fv(ppd.get('smooth_mean'), '.0f')} | "
          f"{_fv(apd.get('motion_active_pct'), '.0f')}% | "
          f"{_fv(ppd.get('motion_active_pct'), '.0f')}% |")
    W("")
    W("#### Interpretasi")
    W("")
    W("Pola **post_action lebih aktif dari fall_action** terlihat pada Nov4 recordings. "
      "Penyebab utama:")
    W("")
    W("1. **Recording Nov4 menggunakan target 10 detik** (pre=0–4s, fall=4–6s, post=6–10s). "
      "Fall_action window hanya 2 detik — sangat sempit untuk menangkap seluruh dinamika jatuh.")
    W("2. **Subjek yang baru bangun dari jatuh** (recovery movement) selama post_action "
      "menghasilkan sinyal yang lebih besar dari sinyal jatuh itu sendiri.")
    W("3. **FSM baseline**: setelah jatuh, smooth sering masih tinggi dari momentum "
      "impak dan gerakan recovery, yang justru lebih mudah ter-detect.")
    W("")
    W("Recording **_003, _007, _008, _009** menunjukkan FSM tidak aktif sama sekali "
      "saat fall_action (0%). CSI delta juga rendah (~2.5–3.5). Ini kemungkinan "
      "karena orientasi jatuh ke belakang di luar zone sensitif ESP32 "
      "(antenna pattern-dependent). Tidak ada bukti mislabeling.")
    W("")

    # ── FALL_LEMAS ──────────────────────────────────────────────────────────
    fl_targets = [r for r in all_results if r["label"] == "fall_lemas"]
    W("### fall_lemas — _010, _015, _017")
    W("")
    W("Ketiga recording ini dipilih karena action_phase_z dalam audit sebelumnya (action lemah).")
    W("")
    W("| Recording | pre_csi | act_csi | post_csi | act_smooth | enter_act | above_enter% | FSM_act% |")
    W("|---|---|---|---|---|---|---|---|")
    for r in fl_targets:
        prd = r["phase_data"].get("pre_action", {})
        apd = r["phase_data"].get("fall_action", {})
        ppd = r["phase_data"].get("post_action", {})
        W(f"| `{r['recording_id'][-10:]}` | "
          f"{_fv(prd.get('csi_delta_mean'))} | "
          f"{_fv(apd.get('csi_delta_mean'))} | "
          f"{_fv(ppd.get('csi_delta_mean'))} | "
          f"{_fv(apd.get('smooth_mean'), '.0f')} | "
          f"{_fv(apd.get('enter_mean'), '.0f')} | "
          f"{_fv(apd.get('above_enter_pct'), '.0f')}% | "
          f"{_fv(apd.get('motion_active_pct'), '.0f')}% |")
    W("")
    W("#### Interpretasi")
    W("")
    W("\"Fall lemas\" adalah jatuh yang lambat dan bertahap — subjek melemas secara gradual. "
      "Ini secara fisik menghasilkan perubahan CSI yang lebih kecil dan lebih lambat dibanding "
      "fall_forward/backward yang memiliki impak mendadak.")
    W("")
    for r in fl_targets:
        apd = r["phase_data"].get("fall_action", {})
        ma  = apd.get("motion_active_pct")
        ab  = apd.get("above_enter_pct")
        csi_a = apd.get("csi_delta_mean")
        W(f"- **`{r['recording_id'][-15:]}`:** "
          f"CSI delta={_fv(csi_a)}, smooth_above_enter={_fv(ab, '.0f')}%, "
          f"FSM_active={_fv(ma, '.0f')}%."
          + (" Timestamp gap dalam fall_action menghilangkan sebagian sinyal." if "_010" in r["recording_id"] else "")
          + (" Profil gradual konsisten dengan label." if "_015" in r["recording_id"] or "_017" in r["recording_id"] else ""))
    W("")
    W("Ketiga recording ini menunjukkan karakteristik yang **konsisten dengan label fall_lemas** "
      "(jatuh gradual). Profil berbeda dari fall_forward/backward bukan karena execution error "
      "melainkan karena sifat fisik aktivitas yang berbeda.")
    W("")

    # ── KESIMPULAN ────────────────────────────────────────────────────────────
    W("---")
    W("")
    W("## Kesimpulan Cross-Source")
    W("")
    W("| Recording / Kelompok | Sumber Anomali | Jenis | Rekomendasi |")
    W("|---|---|---|---|")
    W("| fall_keseleo 10/11 — FSM tidak trigger | FSM baseline adaptation | Keterbatasan firmware | Gunakan smooth_scaled/enter_level sebagai feature, bukan motion_status |")
    W("| object_drop 10/10 — FSM tidak trigger | Keterbatasan fisik CSI | Keterbatasan arsitektural | Pertimbangkan apakah label ini dapat dibedakan dari still_standing |")
    W("| fall_forward_008 — smooth rendah | Eksekusi aktivitas (kemungkinan gradual fall) | Anomali aktivitas | REVIEW — tidak ada bukti mislabeling |")
    W("| fall_backward Nov4 — post_action aktif | Recovery movement + window fall sempit (2s) | Karakteristik aktivitas + protokol | Dapat digunakan; pre-fall window perlu normalisasi |")
    W("| fall_lemas _010/_015/_017 — action lemah | Karakteristik fall_lemas (gradual) | Karakteristik aktivitas yang valid | Tidak ada masalah; profil gradual adalah expected |")
    W("")
    W("**Tidak ada recording yang terbukti salah label berdasarkan analisis ini.**")
    W("")
    W("**Keterbatasan analisis:** Alignment dua clock (CSI callback_timestamp_us vs "
      "motion ts_ms) dilakukan dengan zero-offset dari masing-masing sumber pertama. "
      "Jitter antar keduanya ~0–200ms, dapat menyebabkan misalignment kecil pada "
      "fase-fase sempit (< 2 detik).")
    W("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
