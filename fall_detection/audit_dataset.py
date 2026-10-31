#!/usr/bin/env python3
"""Audit CSI recording takes before using them in a labeled dataset."""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDINGS = (
    REPOSITORY_ROOT / "examples/esp-radar/wifi_sensing_demo/recordings"
)
BASE_IQ_COLUMNS = (
    "timestamp_us",
    "seq",
    "mac",
    "rssi",
    "data_type",
    "dropped",
)
SUBCARRIER_COLUMN = re.compile(r"sc(\d+)_([iq])")

# The 32-column frames.csv contract (spec §4). Must match FRAMES_HEADER in
# tools/csi_recorder.js and tools/csi_recorder_server.py byte for byte.
FRAMES_HEADER = (
    "recording_id", "frame_sequence", "seq", "rx_seq", "mac", "dmac", "rssi",
    "noise_floor", "channel", "secondary_channel", "sig_mode", "mcs", "rate",
    "bandwidth", "stbc", "data_type", "raw_len", "valid_len", "lltf_len",
    "ht_ltf_len", "stbc_ht_ltf_len", "first_word_invalid", "agc_gain",
    "fft_gain", "rx_gain_compensation", "callback_timestamp_us",
    "rx_ctrl_timestamp_us", "host_receive_monotonic_ns", "dropped",
    "payload_ok", "raw_b64", "valid_b64",
)


@dataclass(frozen=True)
class TakeAudit:
    recording_id: str
    label: str
    eligible: bool
    frames: int
    subcarriers: int
    reasons: tuple[str, ...]


def _as_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _recording_node(metadata: dict) -> dict:
    node = metadata.get("recording")
    return node if isinstance(node, dict) else {}


def _is_v3(metadata: dict, take_id: str, meta_path: Path) -> bool:
    """A v3 take carries schema_version 3 or a sibling frames.csv."""
    if metadata.get("schema_version") == 3:
        return True
    return meta_path.with_name(f"{take_id}.frames.csv").is_file()


def _subcarriers_from_row(row: list[str], idx: dict[str, int]) -> int:
    """Complex sub-carrier pairs implied by one frame's valid payload."""
    try:
        data_type = int(row[idx["data_type"]])
    except (ValueError, TypeError):
        data_type = 0
    valid_cell = row[idx["valid_b64"]]
    if not valid_cell:
        return 0
    try:
        valid_bytes = len(base64.b64decode(valid_cell, validate=True))
    except (binascii.Error, ValueError):
        return 0
    sample_bytes = 2 if data_type == 1 else 1
    pair_bytes = sample_bytes * 2
    return valid_bytes // pair_bytes if pair_bytes else 0


def _audit_frames_take(meta_path: Path, metadata: dict, take_id: str) -> TakeAudit:
    """Audit a v3 two-file take: meta.json + frames.csv (spec §4, §5, §14)."""
    reasons: list[str] = []
    label = ""

    recording_id = metadata.get("recording_id") or metadata.get("id")
    if not isinstance(recording_id, str) or not recording_id.strip():
        reasons.append("Metadata is missing a non-empty string recording_id.")
    elif recording_id != take_id:
        reasons.append(
            f"Metadata recording_id {recording_id!r} does not match filename id {take_id!r}."
        )

    label_value = metadata.get("activity_label") or metadata.get("label")
    if not isinstance(label_value, str) or not label_value.strip():
        reasons.append("Metadata is missing a non-empty string activity_label.")
    else:
        label = label_value.strip()

    node = _recording_node(metadata)
    frames_value = _as_nonnegative_int(node.get("frames", metadata.get("frames")))
    frame_count = 0 if frames_value is None else frames_value
    if frames_value is None:
        reasons.append("Metadata frames must be a non-negative integer.")

    complete = node.get("complete", metadata.get("complete"))
    if complete is not True:
        reasons.append("Metadata does not mark this take complete.")
    status = metadata.get("status")
    if isinstance(status, str) and status not in ("", "complete"):
        reasons.append(f"Metadata status is {status!r}, expected 'complete'.")
    if frame_count == 0:
        reasons.append("Metadata reports zero frames.")

    frames_path = meta_path.with_name(f"{take_id}.frames.csv")
    if not frames_path.is_file():
        reasons.append(f"Missing frames CSV: {frames_path.name}.")
        return TakeAudit(
            take_id, label, False, frame_count, 0, tuple(dict.fromkeys(reasons))
        )

    idx = {name: i for i, name in enumerate(FRAMES_HEADER)}
    actual_frames = 0
    subcarrier_count = 0
    try:
        with frames_path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.reader(csv_file)
            header = next(reader, None)
            if header is None:
                reasons.append("frames CSV is empty.")
            elif tuple(header) != FRAMES_HEADER:
                reasons.append(
                    f"frames CSV header does not match the {len(FRAMES_HEADER)}-column contract."
                )
            else:
                for line_number, row in enumerate(reader, start=2):
                    if not row:
                        continue
                    if len(row) != len(FRAMES_HEADER):
                        reasons.append(
                            f"Row {line_number} has {len(row)} columns; expected {len(FRAMES_HEADER)}."
                        )
                        break
                    seq_cell = row[idx["frame_sequence"]]
                    if seq_cell != str(actual_frames):
                        reasons.append(
                            f"Row {line_number} frame_sequence is {seq_cell!r}, expected {actual_frames!r}."
                        )
                        break
                    actual_frames += 1
                    for b64_name, len_name in (("raw_b64", "raw_len"), ("valid_b64", "valid_len")):
                        cell = row[idx[b64_name]]
                        declared = row[idx[len_name]]
                        if not cell:
                            if declared not in ("0", "na", ""):
                                reasons.append(
                                    f"Row {line_number}: empty {b64_name} but {len_name}={declared!r}."
                                )
                            continue
                        try:
                            decoded_len = len(base64.b64decode(cell, validate=True))
                        except (binascii.Error, ValueError):
                            reasons.append(f"Row {line_number}: {b64_name} is not valid base64.")
                            break
                        if declared not in ("na", "") and decoded_len != int(float(declared)):
                            reasons.append(
                                f"Row {line_number}: {b64_name} decodes to {decoded_len} bytes but {len_name}={declared}."
                            )
                            break
                    if subcarrier_count == 0:
                        subcarrier_count = _subcarriers_from_row(row, idx)
    except (OSError, UnicodeError, csv.Error) as exc:
        reasons.append(f"Cannot read frames CSV: {exc}")

    if actual_frames != frame_count:
        reasons.append(
            f"frames CSV contains {actual_frames} data rows; metadata reports {frame_count}."
        )

    return TakeAudit(
        recording_id=take_id,
        label=label,
        eligible=not reasons,
        frames=actual_frames,
        subcarriers=subcarrier_count,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def audit_take(meta_path: Path) -> TakeAudit:
    """Check a metadata file and its sibling I/Q CSV without loading it all."""
    take_id = meta_path.name[: -len(".meta.json")]
    reasons: list[str] = []
    label = ""
    frame_count = 0
    subcarrier_count = 0

    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return TakeAudit(
            take_id, label, False, frame_count, subcarrier_count,
            (f"Cannot read metadata: {exc}",),
        )

    if not isinstance(metadata, dict):
        return TakeAudit(
            take_id, label, False, frame_count, subcarrier_count,
            ("Metadata root must be a JSON object.",),
        )

    # v3 takes store exactly two files (frames.csv + meta.json); audit those.
    # Legacy v1/v2 takes keep the iq.csv schema path below.
    if _is_v3(metadata, take_id, meta_path):
        return _audit_frames_take(meta_path, metadata, take_id)

    metadata_id = metadata.get("id")
    label_value = metadata.get("label")
    if not isinstance(metadata_id, str) or not metadata_id.strip():
        reasons.append("Metadata is missing a non-empty string id.")
    elif metadata_id != take_id:
        reasons.append(
            f"Metadata id {metadata_id!r} does not match filename id {take_id!r}."
        )

    if not isinstance(label_value, str) or not label_value.strip():
        reasons.append("Metadata is missing a non-empty string label.")
    else:
        label = label_value.strip()

    frames_value = _as_nonnegative_int(metadata.get("frames"))
    if frames_value is None:
        reasons.append("Metadata frames must be a non-negative integer.")
    else:
        frame_count = frames_value

    subcarriers_value = _as_nonnegative_int(metadata.get("subcarriers"))
    if subcarriers_value is None:
        reasons.append("Metadata subcarriers must be a non-negative integer.")
    else:
        subcarrier_count = subcarriers_value

    if metadata.get("complete") is not True:
        reasons.append("Metadata does not mark this take complete.")
    if frame_count == 0:
        reasons.append("Metadata reports zero frames.")
    if subcarrier_count == 0:
        reasons.append("Metadata reports zero subcarriers.")

    iq_path = meta_path.with_name(f"{take_id}.iq.csv")
    if not iq_path.is_file():
        reasons.append(f"Missing I/Q CSV: {iq_path.name}.")
        return TakeAudit(
            take_id, label, False, frame_count, subcarrier_count, tuple(reasons)
        )

    actual_frames = 0
    try:
        with iq_path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.reader(csv_file)
            header = next(reader, None)
            if header is None:
                reasons.append("I/Q CSV is empty.")
            else:
                if tuple(header[: len(BASE_IQ_COLUMNS)]) != BASE_IQ_COLUMNS:
                    reasons.append("I/Q CSV metadata columns do not match the expected schema.")
                subcarrier_columns: dict[int, set[str]] = {}
                for column in header[len(BASE_IQ_COLUMNS) :]:
                    match = SUBCARRIER_COLUMN.fullmatch(column)
                    if match is None:
                        reasons.append(f"Unexpected I/Q CSV column: {column!r}.")
                        continue
                    index, component = int(match.group(1)), match.group(2)
                    subcarrier_columns.setdefault(index, set()).add(component)

                indices = sorted(subcarrier_columns)
                if indices != list(range(subcarrier_count)):
                    reasons.append(
                        "I/Q CSV subcarrier columns do not match metadata "
                        f"(expected {subcarrier_count}, found indices {indices[:5]}...)."
                    )
                if any(components != {"i", "q"} for components in subcarrier_columns.values()):
                    reasons.append("Each subcarrier must have one _i and one _q column.")
                expected_columns = len(BASE_IQ_COLUMNS) + 2 * subcarrier_count
                if len(header) != expected_columns:
                    reasons.append(
                        f"I/Q CSV has {len(header)} columns; expected {expected_columns}."
                    )

                for line_number, row in enumerate(reader, start=2):
                    actual_frames += 1
                    if len(row) != len(header):
                        reasons.append(
                            f"Row {line_number} has {len(row)} columns; expected {len(header)}."
                        )
                        continue
                    for column_index, value in enumerate(row):
                        if column_index == 2:
                            continue
                        try:
                            numeric_value = float(value)
                        except ValueError:
                            reasons.append(
                                f"Row {line_number}, column {header[column_index]!r} "
                                "is not numeric."
                            )
                            break
                        if not math.isfinite(numeric_value):
                            reasons.append(
                                f"Row {line_number}, column {header[column_index]!r} "
                                "is not finite."
                            )
                            break
    except (OSError, UnicodeError, csv.Error) as exc:
        reasons.append(f"Cannot read I/Q CSV: {exc}")

    if actual_frames != frame_count:
        reasons.append(
            f"I/Q CSV contains {actual_frames} data rows; metadata reports {frame_count}."
        )

    return TakeAudit(
        recording_id=take_id,
        label=label,
        eligible=not reasons,
        frames=actual_frames,
        subcarriers=subcarrier_count,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def audit_dataset(recordings_dir: Path) -> tuple[list[TakeAudit], list[str]]:
    """Audit all takes in a recordings directory."""
    if not recordings_dir.is_dir():
        return [], [f"Recordings directory does not exist: {recordings_dir}"]

    metadata_files = sorted(recordings_dir.rglob("*.meta.json"))
    if not metadata_files:
        return [], [f"No *.meta.json files found under {recordings_dir}."]

    return [audit_take(path) for path in metadata_files], []


def render_report(
    recordings_dir: Path, takes: list[TakeAudit], scan_errors: list[str]
) -> str:
    eligible = [take for take in takes if take.eligible]
    label_counts = Counter(take.label for take in eligible)
    enough_classes = len(label_counts) >= 2

    lines = [
        f"CSI dataset audit: {recordings_dir}",
        f"Takes found: {len(takes)}",
        f"Eligible takes: {len(eligible)}",
        f"Excluded takes: {len(takes) - len(eligible)}",
        "Eligible label counts: "
        + (", ".join(f"{label}={count}" for label, count in sorted(label_counts.items()))
           if label_counts else "none"),
        "Supervised training gate: "
        + ("at least two labels found; sample sufficiency still needs review"
           if enough_classes else "BLOCKED (need at least two eligible labels)"),
    ]

    for error in scan_errors:
        lines.append(f"ERROR: {error}")

    for take in takes:
        status = "eligible" if take.eligible else "excluded"
        lines.append(
            f"- {take.recording_id} [{take.label or 'unlabeled'}]: {status}; "
            f"{take.frames} frames, {take.subcarriers} subcarriers"
        )
        lines.extend(f"    - {reason}" for reason in take.reasons)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "recordings_dir",
        nargs="?",
        type=Path,
        default=DEFAULT_RECORDINGS,
        help=f"recordings root (default: {DEFAULT_RECORDINGS})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="write a machine-readable JSON report",
    )
    args = parser.parse_args(argv)

    takes, scan_errors = audit_dataset(args.recordings_dir)
    if args.json:
        print(
            json.dumps(
                {
                    "recordings_dir": str(args.recordings_dir),
                    "takes": [asdict(take) for take in takes],
                    "scan_errors": scan_errors,
                    "eligible_labels": dict(
                        Counter(take.label for take in takes if take.eligible)
                    ),
                },
                indent=2,
            )
        )
    else:
        print(render_report(args.recordings_dir, takes, scan_errors))

    return 2 if scan_errors else 0


if __name__ == "__main__":
    sys.exit(main())
