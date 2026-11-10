#!/usr/bin/env python3
"""D1+D2+I2: decode the focus recording, three-phase quantitative analysis,
and a fresh recount of previously claimed window numbers.

Read-only. Produces:
  - focus_decode.json          (D1 metadata + payload verification)
  - motion_series_focus.csv    (per-frame motion timeline for figures)
  - window_phase_counts.json   (I2 recount on the CURRENT dataset)
  - figures/focus_motion_phases.png (D2)
"""
from __future__ import annotations

import base64
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from fall_detection.dataset_io import (  # noqa: E402
    amplitude, component_pairs, decode_iq, find_recording_dir, ltf_sections,
)

RECORDINGS = REPO / "examples/esp-radar/wifi_sensing_demo/recordings"
OUT = Path(__file__).resolve().parents[1]
FOCUS = "20261104T160401Z_fall_backward_010"

WINDOW_FRAMES = 24
WINDOW_STRIDE = 12
FEATURE_COUNT = 16


def load_frames(rec_id: str):
    folder = find_recording_dir(RECORDINGS, rec_id)
    meta = json.loads((folder / f"{rec_id}.meta.json").read_text())
    frames = []
    with (folder / f"{rec_id}.frames.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            frames.append(row)
    return folder, meta, frames


def d1_verify(rec_id: str) -> dict:
    folder, meta, frames = load_frames(rec_id)
    result = {"recording_id": rec_id, "checks": {}}
    f0 = frames[0]
    valid = base64.b64decode(f0["valid_b64"])
    raw = base64.b64decode(f0["raw_b64"])
    pairs = decode_iq(valid, int(f0["data_type"]))
    sections = {"lltf": (0, int(f0["lltf_len"])), "ht_ltf": (int(f0["lltf_len"]),
                int(f0["lltf_len"]) + int(f0["ht_ltf_len"]))}
    amps = amplitude(pairs[: int(f0["lltf_len"]) // 2])
    checks = result["checks"]
    checks["frame_count_matches_meta"] = len(frames) == meta["recording"]["frames"]
    checks["valid_len_matches_payload"] = int(f0["valid_len"]) == len(valid)
    checks["lltf_ht_sum_matches_valid_len"] = (
        int(f0["lltf_len"]) + int(f0["ht_ltf_len"]) + int(f0["stbc_ht_ltf_len"]) == int(f0["valid_len"]))
    checks["lltf_pairs"] = int(f0["lltf_len"]) // 2
    checks["payload_semantics_node"] = meta.get("payload_semantics")
    checks["first_word_invalid_all"] = all(r["first_word_invalid"] == "true" for r in frames)
    checks["layouts_unique"] = len({(r["sig_mode"], r["lltf_len"], r["valid_len"], r["data_type"]) for r in frames}) == 1
    checks["fw_expected_lltf_bytes"] = 104
    checks["fw_would_accept"] = int(f0["lltf_len"]) == 104
    checks["raw_len"] = int(f0["raw_len"])
    checks["raw_first4"] = list(raw[:6])
    checks["sample_amp_head"] = [round(a, 2) for a in amps[:6]]
    checks["amp_max"] = max(amps)
    checks["annotations"] = meta.get("annotations")
    checks["audio_cue_mode"] = (meta.get("audio_cues") or {}).get("mode")
    cues = (meta.get("audio_cues") or {}).get("cues") or []
    checks["fall_cue"] = [c for c in cues if c.get("phase") == "fall_action"]
    checks["timeline"] = meta.get("timeline")
    checks["quality_first_words"] = (meta.get("quality") or {}).get("first_word_invalid_frames")
    checks["rx_seq_gaps"] = (meta.get("quality") or {}).get("rx_seq_gaps")
    checks["sampling_intervals"] = (meta.get("quality") or {}).get("sampling_intervals_ms")
    return result


def frame_offsets_s(frames, meta):
    """Offset seconds per frame from host_receive_monotonic_ns + clock anchor."""
    anchor = meta["clock_anchor"]["performance_now_ms"]
    t0 = None
    out = []
    for row in frames:
        ns = row["host_receive_monotonic_ns"]
        if ns in ("", "na"):
            out.append(None)
            continue
        t = int(ns) / 1e9  # performance.now()-based seconds
        if t0 is None:
            t0 = t
        out.append(t - t0)
    return out


def per_frame_motion_and_profiles(frames):
    """(motion[i], profile16[i]) where motion[i]=mean|Δamp| for frame i vs i-1."""
    motions = [0.0]
    log_profiles = []
    prev = None
    for row in frames:
        valid = base64.b64decode(row["valid_b64"])
        n_pairs = int(row["lltf_len"]) // 2
        amps = amplitude(decode_iq(valid, int(row["data_type"]))[:n_pairs])
        width = len(amps)
        band = [0.0] * FEATURE_COUNT
        counts = [0] * FEATURE_COUNT
        if prev is not None:
            for sc in range(width):
                b = sc * FEATURE_COUNT // width
                band[b] += abs(amps[sc] - prev[sc])
                counts[b] += 1
        motions.append(float(np.mean([abs(a - p) for a, p in zip(amps, prev)])) if prev else 0.0)
        log_profiles.append([math.log1p(band[i] / max(1, counts[i])) if prev else 0.0 for i in range(FEATURE_COUNT)])
        prev = amps
    return motions, log_profiles


def smooth(values, win):
    arr = np.asarray(values, dtype=float)
    kernel = np.ones(win) / win
    return np.convolve(arr, kernel, mode="same")


def d2_analysis():
    folder, meta, frames = load_frames(FOCUS)
    offsets = frame_offsets_s(frames, meta)
    motions, profiles = per_frame_motion_and_profiles(frames)
    sm = smooth(motions, 30)
    phases = meta["timeline"]
    pre = [m for m, o in zip(motions[1:], offsets[1:]) if o is not None and o < 4]
    act = [m for m, o in zip(motions[1:], offsets[1:]) if o is not None and 4 <= o < 6]
    post = [m for m, o in zip(motions[1:], offsets[1:]) if o is not None and 6 <= o <= 10]
    pre_s = sm[:4 * 30]
    act_s = sm[4 * 30:6 * 30]
    post_s = sm[6 * 30:]
    # peak location in smoothed signal
    peak_i = int(np.argmax(sm))
    summary = {
        "recording": FOCUS,
        "frames": len(frames),
        "span_s": round(offsets[-1], 3),
        "median_fps": round(len(frames) / offsets[-1], 2),
        "per_frame_motion_median": {"pre": round(float(np.median(pre)), 3),
                                     "action": round(float(np.median(act)), 3),
                                     "post": round(float(np.median(post)), 3)},
        "smoothed_motion_mean": {"pre": round(float(np.mean(pre_s)), 3),
                                  "action": round(float(np.mean(act_s)), 3),
                                  "post": round(float(np.mean(post_s)), 3)},
        "smoothed_peak_t_s": round(offsets[peak_i], 3),
        "smoothed_peak_value": round(float(sm[peak_i]), 3),
        "post_over_pre_ratio": round(float(np.mean(post_s) / max(1e-9, np.mean(pre_s))), 2),
    }
    # motion_samples FSM onset (independent anchor)
    ms = (meta.get("events") or {}).get("motion_samples") or []
    transitions = []
    last = None
    for s in ms:
        st = s.get("motion_status")
        if st != last:
            transitions.append({"ts_ms": s.get("ts_ms"), "from": last, "to": st})
            last = st
    summary["fsm_transitions"] = transitions[:12]
    summary["fsm_first_motion_true_ts_ms"] = next(
        (s.get("ts_ms") for s in ms if s.get("motion_status")), None)
    # events segments
    summary["event_segments"] = (meta.get("events") or {}).get("segments")

    csv_path = OUT / "motion_series_focus.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(["t_s", "motion", "motion_smooth30", "band0_log", "band15_log"])
        for i in range(1, min(len(frames), len(motions), len(sm) + 1)):
            w.writerow([round(offsets[i], 4), round(motions[i], 4), round(sm[i], 4),
                        round(profiles[i][0], 4), round(profiles[i][15], 4)])

    fig, ax = plt.subplots(figsize=(11, 5))
    n_plot = min(len(offsets) - 1, len(motions) - 1, len(sm))
    t = np.array(offsets[1:1 + n_plot])
    ax.plot(t, motions[1:1 + n_plot], color="#8899bb", lw=0.6, alpha=0.7, label="per-frame mean |Δamp|")
    ax.plot(t, sm[:n_plot], color="#1a56c4", lw=1.8, label="smoothed (30 frames)")
    for x0, x1, color, name in [(0, 4, "#2a9d4a", "pre still"), (4, 6, "#d63d2e", "fall action"), (6, 10, "#7a5cc4", "post still")]:
        ax.axvspan(x0, x1, color=color, alpha=0.08)
        ax.axvline(x1, color=color, ls="--", lw=1)
        ax.text((x0 + x1) / 2, ax.get_ylim()[1] * 0.95, name, ha="center", color=color)
    fsm = summary["fsm_first_motion_true_ts_ms"]
    if fsm:
        ax.axvline(fsm / 1000.0, color="black", ls=":", lw=1.5)
        ax.text(fsm / 1000.0, ax.get_ylim()[1] * 0.85, f"FSM motion={fsm/1000:.2f}s", rotation=90, va="top")
    cue = next((c.get("fired_at_offset_s") for c in (meta.get("audio_cues") or {}).get("cues", [])
               if c.get("phase") == "fall_action"), None)
    if cue:
        ax.axvline(cue, color="orange", ls="-.", lw=1.5)
        ax.text(cue, ax.get_ylim()[1] * 0.75, f"cue={cue:.2f}s", rotation=90, va="top", color="orange")
    ax.set_xlabel("offset since take start (s)")
    ax.set_ylabel("motion")
    ax.set_title(f"Focus take {FOCUS}: three-phase motion timeline")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "focus_motion_phases.png", dpi=140)
    return summary


def phase_window_spans(folder_meta_frames):
    """Window span by frame index (trainer convention) -> phase fractions."""
    results = defaultdict(int)
    for rec_id, (meta, frames) in folder_meta_frames.items():
        n = len(frames)
        starts = range(0, n - WINDOW_FRAMES + 1, WINDOW_STRIDE)
        for s in starts:
            span = range(s, s + WINDOW_FRAMES)
            frac = defaultdict(float)
            for label, (a, b) in PHASES[meta["activity_label"]].items():
                inside = sum(1 for i in span if a <= idx_time(i, frames, meta) < b)
                frac[label] = inside / WINDOW_FRAMES
            full = [k for k, v in frac.items() if v >= 0.999]
            key = ("full_" + full[0]) if len(full) == 1 else "mixed"
            results[(meta["activity_label"], key)] += 1
    return results


def idx_time(i, frames, meta):
    """Approximate time of frame i: linear map of index to actual duration."""
    dur = meta["actual_duration_s"]
    return i * dur / max(1, len(frames) - 1)


PHASES = {
    "fall_forward": {"pre": (0, 4), "action": (4, 6), "post": (6, 10)},
    "fall_backward": {"pre": (0, 4), "action": (4, 6), "post": (6, 10)},
    "walking": {"pre": (0, 3), "action": (3, 7), "post": (7, 10)},
    "bending": {"pre": (0, 3), "action": (3, 7), "post": (7, 10)},
    "fast_sitting": {"pre": (0, 3), "action": (3, 7), "post": (7, 10)},
    "object_drop": {"pre": (0, 3), "action": (3, 7), "post": (7, 10)},
}


def i2_recount():
    counts = defaultdict(lambda: defaultdict(int))
    for meta_path in sorted(RECORDINGS.rglob("*.meta.json")):
        rec_id = meta_path.name[: -len(".meta.json")]
        meta = json.loads(meta_path.read_text())
        with (meta_path.parent / f"{rec_id}.frames.csv").open(encoding="utf-8", newline="") as handle:
            frames = list(csv.DictReader(handle))
        label = meta["activity_label"]
        n = len(frames)
        total = max(0, (n - WINDOW_FRAMES) // WINDOW_STRIDE + 1)
        counts[label]["takes"] += 1
        counts[label]["windows"] += total
        ph = PHASES.get(label)
        if ph:
            full = {"pre": 0, "action": 0, "post": 0}
            mixed = 0
            for s in range(0, n - WINDOW_FRAMES + 1, WINDOW_STRIDE):
                labels_hit = set()
                for k, (a, b) in ph.items():
                    inside = sum(1 for i in range(s, s + WINDOW_FRAMES) if a <= idx_time(i, frames, meta) < b)
                    if inside >= WINDOW_FRAMES * 0.999:
                        labels_hit.add(k)
                if len(labels_hit) == 1:
                    full[next(iter(labels_hit))] += 1
                else:
                    mixed += 1
            for k, v in full.items():
                counts[label][f"windows_fully_{k}"] += v
            counts[label]["windows_mixed"] += mixed
    return {k: dict(v) for k, v in counts.items()}


def main():
    d1 = d1_verify(FOCUS)
    (OUT / "focus_decode.json").write_text(json.dumps(d1, indent=1, default=str))
    print("=== D1 ===")
    print(json.dumps(d1["checks"], indent=1, default=str)[:2600])
    d2 = d2_analysis()
    print("\n=== D2 ===")
    print(json.dumps(d2, indent=1, default=str))
    i2 = i2_recount()
    (OUT / "window_phase_counts.json").write_text(json.dumps(i2, indent=1))
    print("\n=== I2 recount (window spans by frame index) ===")
    for label in sorted(i2):
        print(f"  {label:15s} {i2[label]}")


if __name__ == "__main__":
    main()
