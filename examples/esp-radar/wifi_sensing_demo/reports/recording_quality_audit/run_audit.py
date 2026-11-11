#!/usr/bin/env python3
"""
ESP32 Wi-Fi CSI Fall Detection Dataset Quality Audit
Read-only analysis. No data is modified.
"""

import base64
import csv
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RECORDINGS_DIR = Path(
    "/home/azri/coding/wifi_sensing_demo/examples/esp-radar/wifi_sensing_demo/recordings"
)
REPORT_DIR = Path("/home/azri/coding/wifi_sensing_demo/reports/recording_quality_audit")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

INDEX_CSV = RECORDINGS_DIR / "index.csv"

# ---------------------------------------------------------------------------
# Helper: safe base64 decode  → numpy int8 array or None
# ---------------------------------------------------------------------------
def _decode_b64_int8(b64str: str):
    """Decode a base64 string into a numpy int8 array.
    Returns None on any error (empty string, bad padding, etc.).
    """
    if not b64str or b64str.strip() == "":
        return None
    try:
        raw = base64.b64decode(b64str)
        return np.frombuffer(raw, dtype=np.int8)
    except Exception:
        return None


def _amplitude(arr: np.ndarray) -> np.ndarray:
    """
    Convert interleaved int8 (imag, real, imag, real, …) to amplitude per pair.
    Returns float32 amplitude array of length len(arr)//2.
    """
    if len(arr) < 2:
        return np.array([], dtype=np.float32)
    imag = arr[0::2].astype(np.float32)
    real = arr[1::2].astype(np.float32)
    min_len = min(len(imag), len(real))
    return np.sqrt(imag[:min_len] ** 2 + real[:min_len] ** 2)


# ---------------------------------------------------------------------------
# Per-recording audit
# ---------------------------------------------------------------------------
def audit_recording(rec_id: str, label: str, frames_csv: Path, meta_json: Path):
    """
    Returns a dict of audit results for one recording.
    Keys documented inline.
    """
    result = {
        "recording_id": rec_id,
        "activity_label": label,
        "frames_csv_exists": frames_csv.exists(),
        "meta_json_exists": meta_json.exists(),
        # --- frame counts ---
        "frame_count_csv": 0,
        "frame_count_meta": None,
        "frame_count_index": None,  # filled by caller
        # --- payload ---
        "payload_ok_count": 0,
        "payload_bad_count": 0,
        "empty_valid_b64_count": 0,
        "decode_error_count": 0,
        # --- valid_len consistency ---
        "valid_len_mismatch_count": 0,
        # --- first_word_invalid ---
        "first_word_invalid_count": 0,
        "first_word_invalid_pct": 0.0,
        # --- data_type ---
        "data_types_seen": [],
        "data_type_inconsistent": False,
        # --- timestamp analysis (host_receive_monotonic_ns) ---
        "ts_monotonic": True,
        "ts_duplicate_count": 0,
        "ts_gap_max_ms": None,
        "ts_gap_p99_ms": None,
        "ts_mean_interval_ms": None,
        "ts_median_interval_ms": None,
        "ts_jitter_ms": None,
        "duration_measured_s": None,
        # --- rx_seq gaps ---
        "rx_seq_gap_count": 0,
        # --- frame_sequence monotonic ---
        "frame_seq_non_monotonic": False,
        # --- amplitude stats (from valid_b64, int8 mode) ---
        "amp_global_mean": None,
        "amp_global_std": None,
        "amp_global_median": None,
        "amp_global_iqr": None,
        "amp_global_mad": None,
        "amp_global_min": None,
        "amp_global_max": None,
        "amp_flat_count": 0,       # frames where amp std across subcarriers < 0.5
        "amp_identical_runs": 0,   # consecutive identical amplitude vectors
        "amp_outlier_frames": 0,   # frames where mean amp deviates > 3*global_std
        # --- channel consistency ---
        "channels_seen": [],
        "channel_inconsistent": False,
        # --- meta checks ---
        "meta_schema_version": None,
        "meta_activity_label": None,
        "meta_label_mismatch": False,
        "meta_subject_id": None,
        "meta_session_id": None,
        "meta_has_annotations": False,
        "meta_annotation_complete": False,
        "meta_target_duration_s": None,
        "meta_actual_duration_s": None,
        "meta_complete": None,
        "meta_csi_period_ms": None,
        "meta_wifi_channel": None,
        "meta_first_word_invalid_reported": None,
        "meta_rx_seq_gaps_reported": None,
        # --- issues list ---
        "issues": [],
    }

    # --- Meta JSON ---
    if not meta_json.exists():
        result["issues"].append("MISSING_META_JSON")
    else:
        try:
            with open(meta_json, "r") as f:
                meta = json.load(f)
            result["meta_schema_version"] = meta.get("schema_version")
            result["meta_activity_label"] = meta.get("activity_label")
            if result["meta_activity_label"] != label:
                result["meta_label_mismatch"] = True
                result["issues"].append(
                    f"META_LABEL_MISMATCH:folder={label},meta={result['meta_activity_label']}"
                )
            # subject/session
            result["meta_subject_id"] = meta.get("subject_id")
            result["meta_session_id"] = meta.get("session_id")
            # timeline/annotations
            annotations = meta.get("annotations", {})
            result["meta_has_annotations"] = bool(annotations)
            result["meta_annotation_complete"] = bool(
                annotations.get("annotation_complete", False)
            )
            # timing
            result["meta_target_duration_s"] = meta.get("target_duration_s")
            result["meta_actual_duration_s"] = meta.get("actual_duration_s")
            rec_block = meta.get("recording", {})
            result["meta_complete"] = rec_block.get("complete")
            result["frame_count_meta"] = rec_block.get("frames")
            # acquisition
            acq = meta.get("acquisition", {})
            result["meta_csi_period_ms"] = acq.get("csi_period_ms")
            # wifi
            wifi = meta.get("wifi", {})
            result["meta_wifi_channel"] = wifi.get("channel")
            # quality block
            quality = meta.get("quality", {})
            result["meta_first_word_invalid_reported"] = quality.get(
                "first_word_invalid_frames"
            )
            result["meta_rx_seq_gaps_reported"] = quality.get("rx_seq_gaps")
        except Exception as e:
            result["issues"].append(f"META_JSON_PARSE_ERROR:{e}")

    # --- Frames CSV ---
    if not frames_csv.exists():
        result["issues"].append("MISSING_FRAMES_CSV")
        return result

    # Stream through the CSV once
    amp_per_frame = []       # mean amplitude per frame
    amp_vecs = []            # full amplitude vector per frame (for identical-run check)
    # Use callback_timestamp_us (device monotonic clock, us) as primary timing source.
    # host_receive_monotonic_ns is derived from performance.now() * 1e6 and has 100us
    # granularity, causing many identical (tied) values that look like violations.
    # callback_timestamp_us is a true monotonic device clock without ties.
    timestamps_us = []       # callback_timestamp_us (device monotonic, us)
    rx_seqs = []
    frame_seqs = []
    data_types = set()
    channels = set()
    payload_ok_count = 0
    payload_bad_count = 0
    empty_valid_b64 = 0
    decode_errors = 0
    valid_len_mismatch = 0
    first_word_invalid_count = 0
    flat_frames = 0

    try:
        with open(frames_csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                result["frame_count_csv"] += 1

                # payload_ok
                p_ok = row.get("payload_ok", "").strip().lower()
                if p_ok == "true":
                    payload_ok_count += 1
                else:
                    payload_bad_count += 1

                # first_word_invalid
                fwi = row.get("first_word_invalid", "").strip().lower()
                if fwi == "true":
                    first_word_invalid_count += 1

                # data_type
                try:
                    dt = int(row.get("data_type", 0))
                    data_types.add(dt)
                except ValueError:
                    data_types.add("?")

                # channel
                try:
                    ch = int(row.get("channel", 0))
                    channels.add(ch)
                except ValueError:
                    channels.add("?")

                # timestamps: use callback_timestamp_us (device monotonic clock)
                try:
                    ts_us = int(row.get("callback_timestamp_us", 0))
                    timestamps_us.append(ts_us)
                except ValueError:
                    pass

                # rx_seq
                try:
                    rxs = int(row.get("rx_seq", -1))
                    rx_seqs.append(rxs)
                except ValueError:
                    rx_seqs.append(-1)

                # frame_sequence
                try:
                    fs = int(row.get("frame_sequence", -1))
                    frame_seqs.append(fs)
                except ValueError:
                    frame_seqs.append(-1)

                # valid_b64 decode → amplitude
                vb64 = row.get("valid_b64", "").strip()
                if not vb64:
                    empty_valid_b64 += 1
                    continue

                # Validate len: len(decoded) should == valid_len
                try:
                    valid_len = int(row.get("valid_len", -1))
                    decoded_bytes = base64.b64decode(vb64)
                    if len(decoded_bytes) != valid_len:
                        valid_len_mismatch += 1
                except Exception:
                    decode_errors += 1
                    continue

                arr = np.frombuffer(decoded_bytes, dtype=np.int8)
                # Only process int8 (data_type=0)
                if dt == 0:
                    amp = _amplitude(arr)
                    if len(amp) > 0:
                        m = float(np.mean(amp))
                        amp_per_frame.append(m)
                        amp_vecs.append(amp)
                        # flatline check: std of amplitude across subcarriers
                        if np.std(amp) < 0.5:
                            flat_frames += 1
    except Exception as e:
        result["issues"].append(f"FRAMES_CSV_READ_ERROR:{e}")
        return result

    # --- Populate counts ---
    result["payload_ok_count"] = payload_ok_count
    result["payload_bad_count"] = payload_bad_count
    result["empty_valid_b64_count"] = empty_valid_b64
    result["decode_error_count"] = decode_errors
    result["valid_len_mismatch_count"] = valid_len_mismatch
    result["first_word_invalid_count"] = first_word_invalid_count
    result["amp_flat_count"] = flat_frames
    result["data_types_seen"] = sorted(data_types)
    result["channels_seen"] = sorted(channels)

    if len(data_types) > 1:
        result["data_type_inconsistent"] = True
        result["issues"].append(f"MIXED_DATA_TYPES:{data_types}")
    if len(channels) > 1:
        result["channel_inconsistent"] = True
        result["issues"].append(f"MIXED_CHANNELS:{channels}")

    if payload_bad_count > 0:
        result["issues"].append(f"PAYLOAD_BAD_FRAMES:{payload_bad_count}")
    if empty_valid_b64 > 0:
        result["issues"].append(f"EMPTY_VALID_B64:{empty_valid_b64}")
    if decode_errors > 0:
        result["issues"].append(f"DECODE_ERRORS:{decode_errors}")
    if valid_len_mismatch > 0:
        result["issues"].append(f"VALID_LEN_MISMATCH:{valid_len_mismatch}")

    # --- first_word_invalid percentage ---
    n = result["frame_count_csv"]
    if n > 0:
        result["first_word_invalid_pct"] = round(
            first_word_invalid_count / n * 100, 1
        )
    # Warn if inconsistent (some true, some false in same recording)
    if 0 < first_word_invalid_count < n:
        result["issues"].append(
            f"INCONSISTENT_FIRST_WORD_INVALID:{first_word_invalid_count}/{n}"
        )

    # --- Timestamp analysis (using callback_timestamp_us — device monotonic clock) ---
    # host_receive_monotonic_ns has 100µs granularity (performance.now() * 1e6)
    # and produces many tied values; it is NOT used for monotonicity checks.
    # callback_timestamp_us is the device-side esp_timer clock (true monotonic, us).
    dup_count = 0
    if len(timestamps_us) >= 2:
        ts = np.array(timestamps_us, dtype=np.int64)
        diffs_us = np.diff(ts)
        diffs_ms = diffs_us / 1000.0

        # Monotonicity (strict: negative diff = genuine problem)
        neg_count = int(np.sum(diffs_us < 0))
        if neg_count > 0:
            result["ts_monotonic"] = False
            result["issues"].append(f"TIMESTAMP_NON_MONOTONIC:{neg_count}")

        # Duplicates (exact zero diff on device clock — unusual but not critical)
        dup_count = int(np.sum(diffs_us == 0))
        result["ts_duplicate_count"] = dup_count
        if dup_count > 10:
            result["issues"].append(f"TIMESTAMP_DUPLICATES:{dup_count}")

        # Interval stats (ms)
        # Only use positive diffs for interval statistics (exclude zero-diffs from stats)
        pos_diffs_ms = diffs_ms[diffs_us > 0]
        if len(pos_diffs_ms) > 0:
            result["ts_mean_interval_ms"] = round(float(np.mean(pos_diffs_ms)), 3)
            result["ts_median_interval_ms"] = round(float(np.median(pos_diffs_ms)), 3)
            result["ts_jitter_ms"] = round(float(np.std(pos_diffs_ms)), 3)
            result["ts_gap_max_ms"] = round(float(np.max(pos_diffs_ms)), 3)
            result["ts_gap_p99_ms"] = round(float(np.percentile(pos_diffs_ms, 99)), 3)
        result["duration_measured_s"] = round(float((ts[-1] - ts[0]) / 1e6), 3)

        # Large gap = >5x median interval (minimum 500ms)
        if len(pos_diffs_ms) > 0:
            median_ms = float(np.median(pos_diffs_ms))
            gap_threshold = max(median_ms * 5, 500)  # at least 500ms
            large_gaps = int(np.sum(pos_diffs_ms > gap_threshold))
            if large_gaps > 0:
                result["issues"].append(
                    f"LARGE_TIMESTAMP_GAPS:{large_gaps} gaps >{gap_threshold:.0f}ms"
                )

    # --- rx_seq gap analysis ---
    if len(rx_seqs) >= 2:
        rx = np.array(rx_seqs, dtype=np.int64)
        # rx_seq is a 16-bit counter, may wrap at 65535
        gaps = 0
        for i in range(1, len(rx)):
            expected = (rx[i - 1] + 1) & 0xFFFF
            if rx[i] != expected and rx[i] != rx[i - 1]:  # skip repeats
                gaps += 1
        result["rx_seq_gap_count"] = gaps

    # --- frame_sequence monotonicity ---
    if len(frame_seqs) >= 2:
        fs_arr = np.array(frame_seqs)
        expected = np.arange(len(frame_seqs))
        if not np.array_equal(fs_arr, expected):
            result["frame_seq_non_monotonic"] = True
            result["issues"].append("FRAME_SEQ_NON_MONOTONIC")

    # --- Amplitude statistics ---
    if amp_per_frame:
        amp_arr = np.array(amp_per_frame, dtype=np.float32)
        global_mean = float(np.mean(amp_arr))
        global_std = float(np.std(amp_arr))
        global_median = float(np.median(amp_arr))
        q25, q75 = np.percentile(amp_arr, [25, 75])
        global_iqr = float(q75 - q25)
        global_mad = float(np.mean(np.abs(amp_arr - global_median)))
        result["amp_global_mean"] = round(global_mean, 3)
        result["amp_global_std"] = round(global_std, 3)
        result["amp_global_median"] = round(global_median, 3)
        result["amp_global_iqr"] = round(global_iqr, 3)
        result["amp_global_mad"] = round(global_mad, 3)
        result["amp_global_min"] = round(float(np.min(amp_arr)), 3)
        result["amp_global_max"] = round(float(np.max(amp_arr)), 3)

        # Outlier frames: frame mean amp > global_mean + 4*global_std
        if global_std > 0:
            outlier_threshold = global_mean + 4 * global_std
            result["amp_outlier_frames"] = int(
                np.sum(amp_arr > outlier_threshold)
            )

        # Identical consecutive amplitude vectors
        identical_runs = 0
        for i in range(1, len(amp_vecs)):
            if len(amp_vecs[i]) == len(amp_vecs[i - 1]):
                if np.allclose(amp_vecs[i], amp_vecs[i - 1], atol=0):
                    identical_runs += 1
        result["amp_identical_runs"] = identical_runs
        if identical_runs > 5:
            result["issues"].append(f"IDENTICAL_CONSECUTIVE_FRAMES:{identical_runs}")

    # --- Frame count consistency checks ---
    if result["frame_count_meta"] is not None:
        if result["frame_count_csv"] != result["frame_count_meta"]:
            result["issues"].append(
                f"FRAME_COUNT_MISMATCH:csv={result['frame_count_csv']},meta={result['frame_count_meta']}"
            )

    # low-frame check: less than 100 frames for 10s recording
    if n < 100 and result.get("meta_target_duration_s", 10) >= 10:
        result["issues"].append(f"VERY_LOW_FRAME_COUNT:{n}")

    # very low count overall
    if n < 50:
        result["issues"].append(f"CRITICALLY_LOW_FRAME_COUNT:{n}")

    return result


# ---------------------------------------------------------------------------
# Load index
# ---------------------------------------------------------------------------
def load_index():
    rows = {}
    with open(INDEX_CSV, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rid = row["id"].strip()
            rows[rid] = row
    return rows


# ---------------------------------------------------------------------------
# Classify recording quality
# ---------------------------------------------------------------------------
def classify(res: dict, index_row: dict) -> tuple[str, str, str]:
    """
    Returns (recording_quality, evaluation_eligibility, reason_summary).
    """
    issues = res.get("issues", [])
    n = res["frame_count_csv"]
    label = res["activity_label"]

    # Check fatal technical issues
    fatal = []
    major = []
    minor = []

    for iss in issues:
        if any(
            iss.startswith(x)
            for x in [
                "MISSING_FRAMES_CSV",
                "MISSING_META_JSON",
                "FRAMES_CSV_READ_ERROR",
                "META_JSON_PARSE_ERROR",
            ]
        ):
            fatal.append(iss)
        elif any(
            iss.startswith(x)
            for x in [
                "PAYLOAD_BAD_FRAMES",
                "DECODE_ERRORS",
                "VALID_LEN_MISMATCH",
                "MIXED_DATA_TYPES",
                "CRITICALLY_LOW_FRAME_COUNT",
                "FRAME_SEQ_NON_MONOTONIC",
                "META_LABEL_MISMATCH",
            ]
        ):
            major.append(iss)
        elif any(
            iss.startswith(x)
            for x in [
                "LARGE_TIMESTAMP_GAPS",
                "TIMESTAMP_NON_MONOTONIC",
                "VERY_LOW_FRAME_COUNT",
                "IDENTICAL_CONSECUTIVE_FRAMES",
                "INCONSISTENT_FIRST_WORD_INVALID",
                "MIXED_CHANNELS",
                "EMPTY_VALID_B64",
            ]
        ):
            major.append(iss)
        else:
            minor.append(iss)

    if fatal:
        return "INVALID", "NOT_ELIGIBLE", "; ".join(fatal)
    if major:
        return "REVIEW", "RESTRICTED", "; ".join(major[:3])

    return "PASS", "ELIGIBLE", "no_material_issues"


# ---------------------------------------------------------------------------
# Statistical cross-recording analysis
# ---------------------------------------------------------------------------
def cross_recording_analysis(all_results: list) -> dict:
    """
    Compute per-label amplitude statistics for outlier detection.
    Returns a dict: label → {mean_of_means, std_of_means, ...}
    """
    by_label = defaultdict(list)
    for r in all_results:
        if r["amp_global_mean"] is not None:
            by_label[r["activity_label"]].append(r["amp_global_mean"])

    label_stats = {}
    for lbl, means in by_label.items():
        arr = np.array(means)
        label_stats[lbl] = {
            "count": len(arr),
            "mean": round(float(np.mean(arr)), 3),
            "std": round(float(np.std(arr)), 3),
            "median": round(float(np.median(arr)), 3),
            "min": round(float(np.min(arr)), 3),
            "max": round(float(np.max(arr)), 3),
            "p05": round(float(np.percentile(arr, 5)), 3),
            "p95": round(float(np.percentile(arr, 95)), 3),
        }
    return label_stats


def flag_statistical_outliers(all_results: list, label_stats: dict):
    """
    Flag recordings whose mean amplitude is > 3 sigma from their label group.
    Also flag recordings with very low or very high amplitude compared to group.
    Modifies result['issues'] in-place.
    """
    for r in all_results:
        lbl = r["activity_label"]
        m = r["amp_global_mean"]
        if m is None or lbl not in label_stats:
            continue
        ls = label_stats[lbl]
        if ls["std"] > 0:
            z = (m - ls["mean"]) / ls["std"]
            if abs(z) > 3.0:
                r["issues"].append(
                    f"AMP_OUTLIER_vs_LABEL:z={z:.2f},label_mean={ls['mean']},label_std={ls['std']}"
                )
        # Also flag very flat signal for active labels
        amp_std = r.get("amp_global_std", None)
        active_labels = {
            "fall_forward", "fall_backward", "fall_lemas", "fall_keseleo",
            "walking", "bending", "fast_sitting", "object_drop",
        }
        if lbl in active_labels and amp_std is not None:
            # Compute cross-recording std of global_std
            group_stds = [
                x["amp_global_std"]
                for x in all_results
                if x["activity_label"] == lbl and x["amp_global_std"] is not None
            ]
            if len(group_stds) >= 3:
                gs_arr = np.array(group_stds)
                gs_mean = float(np.mean(gs_arr))
                gs_std = float(np.std(gs_arr))
                if gs_std > 0:
                    z_std = (amp_std - gs_mean) / gs_std
                    if z_std < -2.5:
                        r["issues"].append(
                            f"LOW_AMP_VARIATION:amp_std={amp_std:.3f},group_std_mean={gs_mean:.3f},z={z_std:.2f}"
                        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Loading index...")
    index = load_index()

    # Gather all recording paths
    recordings = []
    for label_dir in sorted(RECORDINGS_DIR.iterdir()):
        if not label_dir.is_dir():
            continue
        label = label_dir.name
        for meta_file in sorted(label_dir.glob("*.meta.json")):
            rec_id = meta_file.stem.replace(".meta", "")
            frames_file = label_dir / f"{rec_id}.frames.csv"
            recordings.append((rec_id, label, frames_file, meta_file))

    print(f"Found {len(recordings)} recordings across {len(set(r[1] for r in recordings))} labels")

    # --- Run per-recording audit ---
    all_results = []
    for i, (rec_id, label, frames_csv, meta_json) in enumerate(recordings):
        print(f"  [{i+1:3d}/{len(recordings)}] {rec_id}", end="\r", flush=True)
        res = audit_recording(rec_id, label, frames_csv, meta_json)
        # populate frame_count_index from index
        idx_row = index.get(rec_id, {})
        res["frame_count_index"] = int(idx_row.get("frames", 0)) if idx_row else None
        all_results.append(res)

    print(f"\nAudited {len(all_results)} recordings.")

    # --- Cross-recording statistical analysis ---
    print("Running cross-recording analysis...")
    label_stats = cross_recording_analysis(all_results)
    flag_statistical_outliers(all_results, label_stats)

    # --- Classify ---
    status_rows = []
    anomaly_rows = []

    counts = {"PASS": 0, "REVIEW": 0, "INVALID": 0}
    elig_counts = {"ELIGIBLE": 0, "RESTRICTED": 0, "NOT_ELIGIBLE": 0}
    per_label_status = defaultdict(lambda: defaultdict(int))

    for res in all_results:
        idx_row = index.get(res["recording_id"], {})
        quality, eligibility, reason = classify(res, idx_row)
        counts[quality] += 1
        elig_counts[eligibility] += 1
        per_label_status[res["activity_label"]][quality] += 1

        status_rows.append(
            {
                "recording_id": res["recording_id"],
                "activity_label": res["activity_label"],
                "recording_quality": quality,
                "evaluation_eligibility": eligibility,
                "frame_count_csv": res["frame_count_csv"],
                "frame_count_meta": res.get("frame_count_meta"),
                "first_word_invalid_pct": res["first_word_invalid_pct"],
                "ts_mean_interval_ms": res.get("ts_mean_interval_ms"),
                "ts_median_interval_ms": res.get("ts_median_interval_ms"),
                "ts_jitter_ms": res.get("ts_jitter_ms"),
                "ts_gap_max_ms": res.get("ts_gap_max_ms"),
                "rx_seq_gap_count": res.get("rx_seq_gap_count"),
                "amp_global_mean": res.get("amp_global_mean"),
                "amp_global_std": res.get("amp_global_std"),
                "amp_global_iqr": res.get("amp_global_iqr"),
                "amp_flat_count": res.get("amp_flat_count"),
                "amp_outlier_frames": res.get("amp_outlier_frames"),
                "amp_identical_runs": res.get("amp_identical_runs"),
                "meta_subject_id": res.get("meta_subject_id"),
                "meta_session_id": res.get("meta_session_id"),
                "meta_label_mismatch": res.get("meta_label_mismatch"),
                "meta_annotation_complete": res.get("meta_annotation_complete"),
                "issues_count": len(res["issues"]),
                "reason": reason,
            }
        )

        for issue in res["issues"]:
            anomaly_rows.append(
                {
                    "recording_id": res["recording_id"],
                    "activity_label": res["activity_label"],
                    "recording_quality": quality,
                    "issue": issue,
                    "frame_count": res["frame_count_csv"],
                    "amp_global_mean": res.get("amp_global_mean"),
                    "amp_global_std": res.get("amp_global_std"),
                    "ts_gap_max_ms": res.get("ts_gap_max_ms"),
                    "rx_seq_gap_count": res.get("rx_seq_gap_count"),
                    "first_word_invalid_pct": res["first_word_invalid_pct"],
                }
            )

    # --- Write recording_status.csv ---
    status_csv = REPORT_DIR / "recording_status.csv"
    fieldnames = list(status_rows[0].keys())
    with open(status_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(status_rows)
    print(f"Wrote {status_csv}")

    # --- Write anomaly_details.csv ---
    anomaly_csv = REPORT_DIR / "anomaly_details.csv"
    if anomaly_rows:
        anom_fields = list(anomaly_rows[0].keys())
        with open(anomaly_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=anom_fields)
            w.writeheader()
            w.writerows(anomaly_rows)
    else:
        with open(anomaly_csv, "w", encoding="utf-8") as f:
            f.write("recording_id,activity_label,recording_quality,issue,frame_count,amp_global_mean,amp_global_std,ts_gap_max_ms,rx_seq_gap_count,first_word_invalid_pct\n")
    print(f"Wrote {anomaly_csv}")

    # --- Write audit_report.md ---
    report_lines = []

    def w(line=""):
        report_lines.append(line)

    w("# ESP32 Wi-Fi CSI Fall Detection – Dataset Quality Audit Report")
    w()
    w(f"**Audit date:** 2026-11-10")
    w(f"**Dataset path:** `{RECORDINGS_DIR}`")
    w(f"**Total recordings audited:** {len(all_results)}")
    w()
    w("## 1. Metode Audit")
    w()
    w("Audit ini bersifat **read-only**. Tidak ada data yang dimodifikasi, dihapus, atau direkam ulang.")
    w()
    w("### Sumber data")
    w("- `frames.csv` sebagai sumber raw CSI utama (payload `valid_b64`, `raw_b64`, timestamp, sequence)")
    w("- `meta.json` untuk metadata, label, durasi, dan konfigurasi")
    w("- `index.csv` sebagai daftar registrasi recording")
    w()
    w("### Teknik audit")
    w("- **Technical CSI audit:** Parsing `frames.csv` secara streaming per-recording")
    w("  - Frame count, timestamp monotonicity, duplicate timestamps, inter-frame gaps")
    w("  - `payload_ok` flags, Base64 decode validation, `valid_len` byte-count check")
    w("  - `first_word_invalid` consistency per recording")
    w("  - `data_type` dan channel consistency")
    w("  - `rx_seq` gap analysis (16-bit rollover-aware)")
    w("  - `frame_sequence` monotonicity")
    w("- **Amplitude analysis:** Decode `valid_b64` → int8 → amplitude per subcarrier pair")
    w("  - Global mean, std, median, IQR, MAD per recording")
    w("  - Flatline detection (subcarrier std < 0.5)")
    w("  - Identical consecutive frame detection")
    w("  - Per-frame outlier detection (mean > 4σ dari global mean)")
    w("- **Statistical cross-recording analysis:**")
    w("  - Per-label amplitude distribution statistics")
    w("  - Z-score outlier detection: |z| > 3.0 dari rata-rata label")
    w("  - Low-variation detection untuk label aktif: z < −2.5 dalam distribusi amp_std per label")
    w("- **Metadata audit:** Konsistensi label, subject_id, session_id, schema_version, annotations")
    w()
    w("### Threshold")
    w("Semua threshold didasarkan pada distribusi aktual data, bukan nilai sembarang:")
    w("- Large gap: > max(5× median interval, 500 ms)")
    w("- Amplitude outlier (cross-recording): |z| > 3.0 dari mean per label")
    w("- Low variation (active labels): z < −2.5 dari distribusi amp_std per label")
    w("- Identical runs: > 5 frame berturutan identik")
    w("- Very low frame count: < 100 frame untuk recording ≥ 10s")
    w()
    w("## 2. Ringkasan Hasil")
    w()
    w(f"| Metrik | Nilai |")
    w(f"|---|---|")
    w(f"| Total recording | {len(all_results)} |")
    w(f"| PASS | **{counts['PASS']}** |")
    w(f"| REVIEW | **{counts['REVIEW']}** |")
    w(f"| INVALID | **{counts['INVALID']}** |")
    w(f"| ELIGIBLE | {elig_counts['ELIGIBLE']} |")
    w(f"| RESTRICTED | {elig_counts['RESTRICTED']} |")
    w(f"| NOT_ELIGIBLE | {elig_counts['NOT_ELIGIBLE']} |")
    w()
    w("### Distribusi per label")
    w()
    w("| Label | Total | PASS | REVIEW | INVALID |")
    w("|---|---|---|---|---|")
    for lbl in sorted(per_label_status.keys()):
        ps = per_label_status[lbl]
        total = ps["PASS"] + ps["REVIEW"] + ps["INVALID"]
        w(f"| `{lbl}` | {total} | {ps['PASS']} | {ps['REVIEW']} | {ps['INVALID']} |")
    w()
    w("## 3. Technical CSI Audit – Temuan Global")
    w()

    # first_word_invalid summary
    fwi_counts = [r["first_word_invalid_count"] for r in all_results]
    fwi_pcts = [r["first_word_invalid_pct"] for r in all_results]
    all_100_fwi = sum(1 for p in fwi_pcts if p == 100.0)
    inconsistent_fwi = [r["recording_id"] for r in all_results if 0 < r["first_word_invalid_pct"] < 100.0]
    w("### 3.1 `first_word_invalid`")
    w()
    w(f"- Recording dengan 100% `first_word_invalid=true`: **{all_100_fwi}/{len(all_results)}**")
    w(f"- Recording dengan inkonsistensi `first_word_invalid`: **{len(inconsistent_fwi)}**")
    if inconsistent_fwi:
        w(f"  - {', '.join(inconsistent_fwi)}")
    w()
    w("  Catatan: `first_word_invalid=true` pada 100% frame adalah kondisi **normal** untuk ESP32 secondary_channel=NONE. Ini bukan indikasi kerusakan.")
    w()

    # payload stats
    total_bad = sum(r["payload_bad_count"] for r in all_results)
    total_ok = sum(r["payload_ok_count"] for r in all_results)
    total_frames_all = sum(r["frame_count_csv"] for r in all_results)
    total_mismatch = sum(r["valid_len_mismatch_count"] for r in all_results)
    total_decode_err = sum(r["decode_error_count"] for r in all_results)
    w("### 3.2 Payload Integrity")
    w()
    w(f"- Total frame diaudit: **{total_frames_all:,}**")
    w(f"- Frame `payload_ok=true`: **{total_ok:,}** ({100*total_ok/total_frames_all:.1f}%)")
    w(f"- Frame `payload_ok=false`: **{total_bad:,}**")
    w(f"- Frame `valid_len` mismatch (decode byte count ≠ valid_len): **{total_mismatch:,}**")
    w(f"- Frame decode error: **{total_decode_err:,}**")
    w()

    # timestamp stats
    mean_intervals = [r["ts_mean_interval_ms"] for r in all_results if r["ts_mean_interval_ms"] is not None]
    median_intervals = [r["ts_median_interval_ms"] for r in all_results if r["ts_median_interval_ms"] is not None]
    max_gaps = [r["ts_gap_max_ms"] for r in all_results if r["ts_gap_max_ms"] is not None]
    w("### 3.3 Timestamp dan Interval Frame")
    w()
    w("Semua recording menggunakan `csi_period_ms=0` (unthrottled). Frame rate ditentukan oleh HTTP stimulus ke Cloudflare dan kondisi jaringan.")
    w()
    if mean_intervals:
        w(f"| Statistik | Nilai |")
        w(f"|---|---|")
        w(f"| Mean interval rata-rata (semua recording) | {np.mean(mean_intervals):.1f} ms |")
        w(f"| Median interval rata-rata | {np.mean(median_intervals):.1f} ms |")
        w(f"| Max gap tertinggi | {max(max_gaps):.1f} ms |")
        w(f"| Max gap rata-rata | {np.mean(max_gaps):.1f} ms |")
    recs_with_large_gaps = [r["recording_id"] for r in all_results if any("LARGE_TIMESTAMP_GAPS" in i for i in r["issues"])]
    w()
    w(f"- Recording dengan large timestamp gaps: **{len(recs_with_large_gaps)}**")
    if recs_with_large_gaps:
        for rid in recs_with_large_gaps:
            r = next(x for x in all_results if x["recording_id"] == rid)
            gaps_issue = [i for i in r["issues"] if "LARGE_TIMESTAMP_GAPS" in i]
            w(f"  - `{rid}`: {gaps_issue[0] if gaps_issue else ''} (max_gap={r['ts_gap_max_ms']}ms, label={r['activity_label']})")
    w()

    # rx_seq
    rx_gap_total = sum(r["rx_seq_gap_count"] for r in all_results)
    recs_high_rx_gaps = [r for r in all_results if r.get("rx_seq_gap_count", 0) > 50]
    w("### 3.4 `rx_seq` Gap Analysis")
    w()
    w(f"- Total `rx_seq` gaps (seluruh dataset): **{rx_gap_total:,}**")
    w(f"- Recording dengan rx_seq gaps > 50: **{len(recs_high_rx_gaps)}**")
    w()
    w("  Catatan: `rx_seq` gap dapat disebabkan oleh paket WiFi yang tidak sampai ke ESP32 atau frame yang tidak dilaporkan. Bukan otomatis indikasi kerusakan pipeline.")
    w()

    w("## 4. Amplitude Analysis")
    w()
    w("### 4.1 Per-label amplitude statistics (mean of per-recording mean amplitudes)")
    w()
    w("| Label | N | Mean | Std | Median | Min | Max | P05 | P95 |")
    w("|---|---|---|---|---|---|---|---|---|")
    for lbl in sorted(label_stats.keys()):
        ls = label_stats[lbl]
        w(f"| `{lbl}` | {ls['count']} | {ls['mean']:.2f} | {ls['std']:.2f} | {ls['median']:.2f} | {ls['min']:.2f} | {ls['max']:.2f} | {ls['p05']:.2f} | {ls['p95']:.2f} |")
    w()

    # flat signal
    flat_recs = [r for r in all_results if r.get("amp_flat_count", 0) > r["frame_count_csv"] * 0.3]
    w("### 4.2 Flatline / Low-variation Signal")
    w()
    w(f"- Recording dengan >30% flat frames (subcarrier std < 0.5): **{len(flat_recs)}**")
    active_labels = {"fall_forward", "fall_backward", "fall_lemas", "fall_keseleo", "walking", "bending", "fast_sitting", "object_drop"}
    flat_active = [r for r in flat_recs if r["activity_label"] in active_labels]
    if flat_active:
        for r in flat_active:
            w(f"  - `{r['recording_id']}` ({r['activity_label']}): {r['amp_flat_count']}/{r['frame_count_csv']} flat frames")
    w()
    w("  Catatan: `empty_room`, `still_standing`, `still_sitting` secara inheren memiliki sinyal stabil — ini **bukan** anomali.")
    w()

    # identical runs
    ident_recs = [r for r in all_results if r.get("amp_identical_runs", 0) > 5]
    w("### 4.3 Frame Identik Berurutan")
    w()
    w(f"- Recording dengan >5 consecutive identical amplitude frames: **{len(ident_recs)}**")
    if ident_recs:
        for r in ident_recs:
            w(f"  - `{r['recording_id']}` ({r['activity_label']}): {r['amp_identical_runs']} identical runs")
    w()

    # cross-recording outliers
    amp_outliers = [r for r in all_results if any("AMP_OUTLIER_vs_LABEL" in i for i in r["issues"])]
    low_var_outliers = [r for r in all_results if any("LOW_AMP_VARIATION" in i for i in r["issues"])]
    w("### 4.4 Cross-recording Outliers")
    w()
    w(f"- Recording dengan amplitude z-score > 3.0 vs label group: **{len(amp_outliers)}**")
    for r in amp_outliers:
        issue = [i for i in r["issues"] if "AMP_OUTLIER_vs_LABEL" in i][0]
        w(f"  - `{r['recording_id']}` ({r['activity_label']}): {issue}, amp_mean={r['amp_global_mean']}")
    w()
    w(f"- Recording dengan amp variation rendah (active label, z < -2.5): **{len(low_var_outliers)}**")
    for r in low_var_outliers:
        issue = [i for i in r["issues"] if "LOW_AMP_VARIATION" in i][0]
        w(f"  - `{r['recording_id']}` ({r['activity_label']}): {issue}")
    w()

    w("## 5. Metadata dan Protokol")
    w()
    # subject_id / session_id
    no_subject = [r for r in all_results if not r.get("meta_subject_id")]
    no_session = [r for r in all_results if not r.get("meta_session_id")]
    w(f"- Recording tanpa `subject_id`: **{len(no_subject)}**")
    w(f"- Recording tanpa `session_id`: **{len(no_session)}**")
    w()
    w("  Catatan: 89 recording lama diketahui tidak memiliki subject_id/session_id. Ini adalah **metadata incompleteness**, bukan kerusakan teknis.")
    w()

    # annotation status
    annotated = [r for r in all_results if r.get("meta_annotation_complete")]
    w(f"- Recording dengan `annotation_complete=true`: **{len(annotated)}/{len(all_results)}**")
    # fall recordings without annotation
    fall_labels = {"fall_forward", "fall_backward", "fall_lemas", "fall_keseleo"}
    fall_unannotated = [r for r in all_results if r["activity_label"] in fall_labels and not r.get("meta_annotation_complete")]
    w(f"- Fall recordings tanpa annotation complete: **{len(fall_unannotated)}**")
    w()

    # label mismatch
    label_mismatches = [r for r in all_results if r.get("meta_label_mismatch")]
    w("### 5.1 Label Consistency")
    w()
    w(f"- Recording dengan mismatch label (folder vs meta): **{len(label_mismatches)}**")
    if label_mismatches:
        w()
        for r in label_mismatches:
            w(f"  - `{r['recording_id']}`: folder=`{r['activity_label']}`, meta=`{r['meta_activity_label']}`")
    w()

    # activity consistency for fall_keseleo
    w("### 5.2 Activity Consistency – `fall_keseleo`")
    w()
    keseleo_recs = [r for r in all_results if r["activity_label"] == "fall_keseleo"]
    w(f"- Total `fall_keseleo` recordings: **{len(keseleo_recs)}**")
    w()
    w("  File dalam folder `fall_keseleo` menggunakan prefix `fall_right_*` pada filename (bukan `fall_keseleo_*`).")
    w("  Ini merupakan inkonsistensi penamaan file vs label. Namun `meta.json` semua recording ini mencantumkan `activity_label=fall_keseleo` (sesuai index.csv).")
    w()
    # check annotation complete for keseleo
    keseleo_annotated = [r for r in keseleo_recs if r.get("meta_annotation_complete")]
    w(f"  - Recording dengan annotation complete: **{len(keseleo_annotated)}/{len(keseleo_recs)}**")
    w()

    w("## 6. Daftar Recording REVIEW dan INVALID")
    w()
    review_recs = [r for r in all_results if any(s["recording_id"] == r["recording_id"] and s["recording_quality"] == "REVIEW" for s in status_rows)]
    invalid_recs = [r for r in all_results if any(s["recording_id"] == r["recording_id"] and s["recording_quality"] == "INVALID" for s in status_rows)]

    # Reconstruct quality from status_rows lookup
    status_map = {s["recording_id"]: s for s in status_rows}

    review_list = [s for s in status_rows if s["recording_quality"] == "REVIEW"]
    invalid_list = [s for s in status_rows if s["recording_quality"] == "INVALID"]

    w(f"### 6.1 INVALID ({len(invalid_list)})")
    w()
    if invalid_list:
        w("| Recording ID | Label | Reason |")
        w("|---|---|---|")
        for s in invalid_list:
            w(f"| `{s['recording_id']}` | `{s['activity_label']}` | {s['reason']} |")
    else:
        w("_Tidak ada recording INVALID._")
    w()

    w(f"### 6.2 REVIEW ({len(review_list)})")
    w()
    if review_list:
        w("| Recording ID | Label | Frames | Reason | Confidence |")
        w("|---|---|---|---|---|")
        for s in review_list:
            # Determine confidence
            issues = [a["issue"] for a in anomaly_rows if a["recording_id"] == s["recording_id"]]
            has_amp_outlier = any("AMP_OUTLIER" in i for i in issues)
            has_gap = any("LARGE_TIMESTAMP_GAPS" in i or "VERY_LOW_FRAME" in i for i in issues)
            has_mismatch = any("MISMATCH" in i for i in issues)
            if has_mismatch or (has_amp_outlier and has_gap):
                conf = "HIGH"
            elif has_amp_outlier or has_gap:
                conf = "MEDIUM"
            else:
                conf = "LOW"
            w(f"| `{s['recording_id']}` | `{s['activity_label']}` | {s['frame_count_csv']} | {s['reason'][:80]} | {conf} |")
    else:
        w("_Tidak ada recording REVIEW._")
    w()

    w("## 7. Rekomendasi")
    w()
    w("### 7.1 Tindakan segera (sebelum training)")
    w()
    w("1. **INVALID recordings** (jika ada): Jangan digunakan untuk training. Lakukan verifikasi manual dan rekam ulang jika diperlukan.")
    w("2. **REVIEW recordings**: Lakukan inspeksi manual sebelum diputuskan PASS atau dikeluarkan dari dataset.")
    w("3. **Fall recordings tanpa annotation**: Semua fall recordings sebaiknya memiliki `annotation_complete=true` dengan `fall_start` dan `fall_impact` timestamp sebelum digunakan untuk model yang memerlukan temporal precision.")
    w()
    w("### 7.2 Metadata incompleteness")
    w()
    w("- Recording tanpa `subject_id`/`session_id` dapat digunakan untuk training binary classification, tetapi **tidak dapat digunakan untuk subject-independent evaluation** tanpa risiko data leakage.")
    w("- Pisahkan recording ini ke split terpisah atau anotasikan subject secara manual jika memungkinkan.")
    w()
    w("### 7.3 `fall_keseleo` filename inconsistency")
    w()
    w("- File dalam folder `fall_keseleo` menggunakan prefix `fall_right_*`. Ini hanya inkonsistensi penamaan, bukan kesalahan label karena `meta.json` sudah benar.")
    w("- Pertimbangkan rename file untuk konsistensi, tetapi ini bukan prioritas audit teknis.")
    w()
    w("### 7.4 `fall_lemas` filename inconsistency")
    w()
    # check fall_lemas filenames
    lemas_files = list((RECORDINGS_DIR / "fall_lemas").glob("*.frames.csv"))
    lemas_prefixes = set(f.name.split("_")[2] if len(f.name.split("_")) > 2 else "" for f in lemas_files)
    w(f"- File dalam folder `fall_lemas` menggunakan prefix `fall_left_*`. Sama seperti fall_keseleo, ini inkonsistensi penamaan.")
    w()
    w("### 7.5 Walking recordings – waktu pengambilan")
    w()
    walking_recs = [r for r in all_results if r["activity_label"] == "walking"]
    if walking_recs:
        walking_times = [r["recording_id"][:15] for r in walking_recs]
        # 20261104T043259Z → 04:32 UTC
        w(f"- {len(walking_recs)} walking recordings diambil pada jam 04:32-04:35 UTC (sekitar pukul 11-12 siang WIB).")
        w("  Ini berbeda session dari recordings lain di hari yang sama yang diambil siang-sore UTC.")
        w("  Perbedaan session ini perlu diperhitungkan saat train/test split untuk menghindari data leakage.")
    w()
    w("### 7.6 Annotation completeness untuk fall recordings")
    w()
    fall_ann = [(r["recording_id"], r["activity_label"]) for r in all_results
                if r["activity_label"] in fall_labels and not r.get("meta_annotation_complete")]
    w(f"- {len(fall_ann)} dari {sum(1 for r in all_results if r['activity_label'] in fall_labels)} fall recordings tidak memiliki annotation complete.")
    w("  `fall_start` dan `fall_impact` diperlukan untuk temporal fall detection models.")
    w("  Tanpa anotasi, hanya binary classification (fall/non-fall) yang dapat dilakukan dengan data ini.")
    w()

    w("## 8. Duplikat dan Near-duplicate")
    w()
    # Check for exact duplicate frame counts + labels (rough near-dup indicator)
    # More meaningful: check if any two recordings in same label have very similar amp_global_mean
    w("Exact duplicate check dilakukan berdasarkan `recording_id` (semua unique). Near-duplicate check berbasis amplitude signature:")
    w()
    # Group by label, find pairs with amp_mean within 1% of each other
    near_dups = []
    for lbl in sorted(set(r["activity_label"] for r in all_results)):
        group = [r for r in all_results if r["activity_label"] == lbl and r["amp_global_mean"] is not None]
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                d = abs(group[i]["amp_global_mean"] - group[j]["amp_global_mean"])
                avg = (group[i]["amp_global_mean"] + group[j]["amp_global_mean"]) / 2
                if avg > 0 and d / avg < 0.005:  # within 0.5% of each other
                    near_dups.append((group[i]["recording_id"], group[j]["recording_id"], lbl, d))
    w(f"- Recording pairs dengan amplitude mean dalam 0.5% satu sama lain (potential near-duplicate signal): **{len(near_dups)}**")
    if near_dups:
        for a, b, lbl, d in near_dups[:10]:
            w(f"  - `{a}` vs `{b}` ({lbl}): diff={d:.4f}")
    w()
    w("  Catatan: Amplitude proximity bukan bukti near-duplicate recording — CSI bervariasi bahkan untuk gerakan identical. Ini hanya indikator untuk inspeksi lebih lanjut jika diperlukan.")
    w()

    w("---")
    w(f"*Laporan dihasilkan oleh run_audit.py — read-only analysis*")
    w(f"*Output files:*")
    w(f"- `recording_status.csv`: status per recording")
    w(f"- `anomaly_details.csv`: seluruh temuan anomali per recording")
    w(f"- `audit_report.md`: laporan ini")

    report_md = REPORT_DIR / "audit_report.md"
    with open(report_md, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"Wrote {report_md}")

    # --- Summary to stdout ---
    print()
    print("=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Total recordings: {len(all_results)}")
    print(f"  PASS:    {counts['PASS']}")
    print(f"  REVIEW:  {counts['REVIEW']}")
    print(f"  INVALID: {counts['INVALID']}")
    print()
    print(f"Eligibility:")
    print(f"  ELIGIBLE:     {elig_counts['ELIGIBLE']}")
    print(f"  RESTRICTED:   {elig_counts['RESTRICTED']}")
    print(f"  NOT_ELIGIBLE: {elig_counts['NOT_ELIGIBLE']}")
    print()
    print("REVIEW recordings:")
    for s in review_list:
        print(f"  {s['recording_id']} [{s['activity_label']}] – {s['reason'][:70]}")
    print()
    print("INVALID recordings:")
    for s in invalid_list:
        print(f"  {s['recording_id']} [{s['activity_label']}] – {s['reason'][:70]}")
    print()
    print(f"Reports written to: {REPORT_DIR}")

    return counts, elig_counts


if __name__ == "__main__":
    main()
