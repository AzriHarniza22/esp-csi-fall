#!/usr/bin/env python3
"""Integrity and quality validation for CSI recordings.

Produces a ``VALID`` / ``WARNING`` / ``INVALID`` verdict with explicit reasons,
plus the descriptive statistics the task asks for (frame counts at each stage,
timestamp anomalies, interval and duration stats, MAC and CSI-layout spread).

Guiding rules:

* The original files are never modified. ``quality_report.json`` is a derived
  report; use ``--write`` to persist it next to the recording.
* Structural breakage (missing columns, corrupt base64, count mismatch, an
  unfinished recording) is ``INVALID``.
* Timing anomalies (duplicate, backward, or unusually large gaps) and layout
  mixing are reported as ``WARNING`` together with the measured numbers. No
  arbitrary pass/fail threshold is invented: the gap test is relative to the
  recording's own median inter-arrival interval, and everything is surfaced so
  a human can audit the real data before deciding on hard thresholds.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from fall_detection.dataset_io import (  # noqa: E402
    FrameRecord,
    Recording,
    find_recording_dir,
    load_recording,
    ltf_sections,
)

VALID = "VALID"
WARNING = "WARNING"
INVALID = "INVALID"

_SEVERITY = {VALID: 0, WARNING: 1, INVALID: 2}
# A gap is "large" when it exceeds this multiple of the median interval. This is
# a relative flag, not an absolute quality bar; it only marks frames worth a
# look and never by itself invalidates a recording.
_GAP_FACTOR = 8.0


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _interval_stats(timestamps: list[int]) -> dict:
    if len(timestamps) < 2:
        return {"count": len(timestamps)}
    deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
    positive = [d for d in deltas if d > 0]
    return {
        "count": len(timestamps),
        "min_us": min(deltas),
        "max_us": max(deltas),
        "median_us": _median([float(d) for d in deltas]),
        "median_positive_us": _median([float(d) for d in positive]) if positive else None,
        "span_us": timestamps[-1] - timestamps[0],
    }


def _payload_integrity(frames: list[FrameRecord]) -> dict:
    checked = 0
    mismatches = 0
    corrupt = 0
    for frame in frames:
        if frame.payload_source != "frames_csv":
            continue
        checked += 1
        if frame.payload_ok is False:
            mismatches += 1
        if frame.raw_len is not None and frame.raw_payload and len(frame.raw_payload) != int(frame.raw_len):
            mismatches += 1
        if frame.valid_len is not None and frame.valid_payload and len(frame.valid_payload) != int(frame.valid_len):
            mismatches += 1
        if not frame.raw_payload and not frame.valid_payload:
            corrupt += 1
    return {
        "frames_checked": checked,
        "length_or_flag_mismatches": mismatches,
        "frames_without_payload": corrupt,
    }


def _timestamp_report(frames: list[FrameRecord]) -> dict:
    stamps = [
        f.callback_timestamp_us
        for f in frames
        if isinstance(f.callback_timestamp_us, int)
    ]
    duplicates = 0
    backward = 0
    for a, b in zip(stamps, stamps[1:]):
        if b == a:
            duplicates += 1
        elif b < a:
            backward += 1
    stats = _interval_stats(stamps)
    median_positive = stats.get("median_positive_us")
    large_gaps = 0
    if median_positive:
        for a, b in zip(stamps, stamps[1:]):
            if (b - a) > _GAP_FACTOR * median_positive:
                large_gaps += 1
    missing = sum(1 for f in frames if not isinstance(f.callback_timestamp_us, int))
    host_stamped = sum(1 for f in frames if isinstance(f.host_receive_monotonic_ns, int))
    # Cross-clock delta is descriptive only. callback_timestamp_us is the
    # esp_timer monotonic clock while rx_ctrl_timestamp_us is the Wi-Fi driver's
    # 32-bit local receive time (ESP-IDF esp_wifi_types_native.h: precise only
    # when modem/light sleep is off). They are different bases, so their
    # difference is a clock offset, NOT measured per-packet processing latency.
    deltas = [
        f.callback_timestamp_us - f.rx_ctrl_timestamp_us
        for f in frames
        if isinstance(f.callback_timestamp_us, int)
        and isinstance(f.rx_ctrl_timestamp_us, int)
    ]
    cross_clock = {
        "pairs": len(deltas),
        "min_us": min(deltas) if deltas else None,
        "median_us": _median([float(d) for d in deltas]) if deltas else None,
        "max_us": max(deltas) if deltas else None,
        "interpretation": (
            "callback(esp_timer monotonic) - rx_ctrl(driver 32-bit local us): a "
            "cross-clock offset, not processing latency; compare only same-clock deltas"
        ),
    }
    return {
        "stamped_frames": len(stamps),
        "frames_missing_callback_timestamp": missing,
        "frames_with_host_receive_ns": host_stamped,
        "duplicate_timestamps": duplicates,
        "backward_timestamps": backward,
        "large_gaps": large_gaps,
        "gap_factor": _GAP_FACTOR,
        "interval": stats,
        "cross_clock_delta": cross_clock,
    }


def _sequence_report(frames: list[FrameRecord]) -> dict:
    seqs = [f.seq for f in frames if isinstance(f.seq, int)]
    gaps = 0
    if len(seqs) >= 2:
        for a, b in zip(seqs, seqs[1:]):
            if b - a > 1:
                gaps += 1
    rx_seqs = [f.rx_seq for f in frames if isinstance(f.rx_seq, int)]
    return {
        "seq_present": len(seqs),
        "seq_gaps": gaps,
        "rx_seq_present": len(rx_seqs),
    }


def _distribution(frames: list[FrameRecord]) -> dict:
    macs = Counter(f.mac for f in frames if f.mac)
    layouts = Counter()
    data_types = Counter()
    first_word_invalid = 0
    for frame in frames:
        sections = tuple(sorted(ltf_sections(frame).keys())) or ("unreported",)
        layouts[",".join(sections)] += 1
        if frame.data_type is not None:
            data_types[int(frame.data_type)] += 1
        if frame.first_word_invalid:
            first_word_invalid += 1
    return {
        "macs": dict(macs),
        "ltf_layouts": {k: v for k, v in layouts.items()},
        "data_types": {str(k): v for k, v in data_types.items()},
        "first_word_invalid_frames": first_word_invalid,
    }


def validate_recording(recording: Recording) -> dict:
    reasons: list[str] = []
    warnings: list[str] = []
    frames = recording.frames
    meta = recording.meta

    if not frames:
        reasons.append("recording contains zero frames")

    # -- finalization / counts ---------------------------------------------
    # v3 nests these under meta["recording"] (spec §6.3); v1/v2 kept them at the
    # top level. Read the nested node first, then fall back for old takes.
    recording_node = meta.get("recording")
    if not isinstance(recording_node, dict):
        recording_node = {}
    reported_frames = recording_node.get("frames", meta.get("frames"))
    if isinstance(reported_frames, int) and reported_frames != len(frames):
        reasons.append(
            f"metadata reports {reported_frames} frames but {len(frames)} were parsed"
        )
    complete = recording_node.get("complete", meta.get("complete"))
    if complete is False:
        reasons.append("recording is marked incomplete (not finalized)")
    dropped_delta = recording_node.get("dropped", meta.get("dropped_delta"))
    if isinstance(dropped_delta, int) and dropped_delta > 0:
        warnings.append(f"{dropped_delta} frames were dropped on device during capture")

    # -- v3 lifecycle status (spec §10) ------------------------------------
    # A take that did not finish cleanly is still loadable but must be flagged.
    take_status = recording.status
    if take_status and take_status != "complete":
        warnings.append(f"recording status is '{take_status}' (not a clean complete take)")

    # -- label / identity ---------------------------------------------------
    if not recording.label:
        reasons.append("recording has no label")
    if not recording.session_id:
        warnings.append("no session_id/batch_id; cannot group takes from one session")

    # -- payload integrity --------------------------------------------------
    integrity = _payload_integrity(frames)
    if integrity["length_or_flag_mismatches"]:
        reasons.append(
            f"{integrity['length_or_flag_mismatches']} frames have a payload length/flag mismatch"
        )
    if integrity["frames_without_payload"]:
        warnings.append(
            f"{integrity['frames_without_payload']} frames carry no payload bytes"
        )

    # -- timestamps ---------------------------------------------------------
    ts = _timestamp_report(frames)
    if ts["frames_missing_callback_timestamp"]:
        warnings.append(
            f"{ts['frames_missing_callback_timestamp']} frames lack a callback timestamp"
        )
    if ts["backward_timestamps"]:
        warnings.append(f"{ts['backward_timestamps']} timestamps go backward")
    if ts["duplicate_timestamps"]:
        warnings.append(f"{ts['duplicate_timestamps']} duplicate callback timestamps")
    if ts["large_gaps"]:
        warnings.append(
            f"{ts['large_gaps']} inter-arrival gaps exceed {_GAP_FACTOR}x the median interval"
        )

    # -- sequence -----------------------------------------------------------
    seqrep = _sequence_report(frames)
    if seqrep["seq_gaps"]:
        warnings.append(f"{seqrep['seq_gaps']} gaps in device seq_id")

    # -- distributions (descriptive, never invalidating) --------------------
    distribution = _distribution(frames)
    if len(distribution["macs"]) > 1:
        warnings.append(
            f"frames come from {len(distribution['macs'])} MAC addresses: "
            + ", ".join(sorted(distribution["macs"]))
        )
    if len(distribution["ltf_layouts"]) > 1:
        warnings.append(
            "mixed CSI layouts present: "
            + ", ".join(sorted(distribution["ltf_layouts"]))
        )
    if distribution["first_word_invalid_frames"]:
        warnings.append(
            f"{distribution['first_word_invalid_frames']}/{len(frames)} frames have "
            "first_word_invalid (the first four bytes of the driver CSI buffer, "
            "captured in raw_data, are hardware-invalid); valid_data is esp-radar's "
            "compacted subset of that buffer and the mapping is layout-dependent - "
            "do not auto-trim leading pairs of derived features until proven"
        )

    warnings.extend(recording.warnings)

    if reasons:
        status = INVALID
    elif warnings:
        status = WARNING
    else:
        status = VALID

    return {
        "recording_id": recording.recording_id,
        "label": recording.label,
        "binary_label": recording.binary_label,
        "schema_version": recording.schema_version,
        "status": status,
        "reasons": reasons,
        "warnings": sorted(set(warnings)),
        "frames": len(frames),
        "payload_integrity": integrity,
        "timestamps": ts,
        "sequence": seqrep,
        "distribution": distribution,
        "started_at_utc": recording.started_at_utc,
        "ended_at_utc": recording.ended_at_utc,
        "session_id": recording.session_id,
    }


def _worst(statuses: list[str]) -> str:
    worst = VALID
    for status in statuses:
        if _SEVERITY.get(status, 0) > _SEVERITY.get(worst, 0):
            worst = status
    return worst


def validate_dataset(recordings_dir: Path) -> list[dict]:
    reports = []
    recordings_dir = Path(recordings_dir)
    if not recordings_dir.is_dir():
        return reports
    from fall_detection.dataset_io import iter_recordings

    for rec_id in iter_recordings(recordings_dir):
        try:
            recording = load_recording(recordings_dir, rec_id)
        except (FileNotFoundError, ValueError) as exc:
            reports.append(
                {"recording_id": rec_id, "status": INVALID, "reasons": [str(exc)], "warnings": []}
            )
            continue
        reports.append(validate_recording(recording))
    return reports


def write_reports(recordings_dir: Path, reports: list[dict]) -> list[Path]:
    written: list[Path] = []
    for report in reports:
        rec_id = report.get("recording_id")
        if not rec_id:
            continue
        folder = find_recording_dir(Path(recordings_dir), rec_id)
        if folder is None:
            continue
        path = folder / f"{rec_id}.quality_report.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "recordings_dir",
        nargs="?",
        type=Path,
        default=REPOSITORY_ROOT / "examples/esp-radar/wifi_sensing_demo/recordings",
    )
    parser.add_argument("--json", action="store_true", help="emit a JSON report")
    parser.add_argument(
        "--write",
        action="store_true",
        help="write <recording>.quality_report.json next to each recording",
    )
    args = parser.parse_args(argv)

    reports = validate_dataset(args.recordings_dir)
    if args.write:
        write_reports(args.recordings_dir, reports)

    counts = Counter(r.get("status", INVALID) for r in reports)
    if args.json:
        print(json.dumps({"recordings_dir": str(args.recordings_dir), "reports": reports}, indent=2))
    else:
        print(f"Quality validation: {args.recordings_dir}")
        print(
            f"  {len(reports)} recordings — VALID={counts.get(VALID, 0)} "
            f"WARNING={counts.get(WARNING, 0)} INVALID={counts.get(INVALID, 0)}"
        )
        for report in reports:
            print(f"- {report.get('recording_id')} [{report.get('label')}]: {report.get('status')}")
            for reason in report.get("reasons", []):
                print(f"    INVALID: {reason}")
            for warning in report.get("warnings", []):
                print(f"    WARNING: {warning}")
    # Non-zero only when something is structurally broken.
    return 1 if counts.get(INVALID, 0) else 0


if __name__ == "__main__":
    sys.exit(main())
