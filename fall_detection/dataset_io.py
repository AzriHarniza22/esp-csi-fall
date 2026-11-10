#!/usr/bin/env python3
"""Model-agnostic reader for Wi-Fi CSI recordings.

The recording pipeline stores the raw driver payload losslessly (see
``tools/csi_recorder.js`` -> ``frames.csv``). This module is the single place
that turns those files back into numbers so different model families can be
fed from the *same* source of truth without re-recording.

Design rules honoured here:

* The raw payload is never mutated. Amplitude, band aggregation, windowing and
  normalisation all live in the adapters below, not in the stored files.
* A missing value stays ``None`` ("not available"); it is never guessed or
  zero-filled as if it were a real CSI sample.
* Old (v1) recordings that only carry ``csi_data.csv`` / ``iq.csv`` still load,
  so existing readers and the baseline classifier keep working.
* Every adapter records the parameters it used so a transform is reproducible.

Byte order follows ESP-IDF v5.5.3 ``api-guides/wifi.rst``: each sub-carrier is
two signed bytes, imaginary part first then real part. The legacy ``iq.csv``
``scNNN_i``/``scNNN_q`` columns are swapped relative to that; this reader does
not use them for new work and keeps them only for backward compatibility.
"""

from __future__ import annotations

import base64
import csv
import json
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

NA = "na"

# Baseline pipeline constants. These mirror main/activity_classifier.c and
# fall_detection/train_activity_model.py and must not drift: 52 LLTF complex
# pairs -> 16 log-amplitude-change bands over a 24-frame window, stride 12.
BASELINE_LLTF_COMPLEX_PAIRS = 52
BASELINE_FEATURE_COUNT = 16
BASELINE_WINDOW_FRAMES = 24
BASELINE_WINDOW_STRIDE = 12
BASELINE_SUBCARRIERS = BASELINE_LLTF_COMPLEX_PAIRS

# CSI layout contract (DATA_CONTRACT.md §1). Length and ``first_word_invalid``
# are bound 1-to-1: the esp-radar source clamp (commit ``3ac4a35``) drops the
# 4 hardware-corrupt leading bytes before the ring buffer, so a flagged frame
# arrives as 102 B / 51 pairs (Layout A) and an unflagged frame as the full
# 104 B / 52 pairs (Layout B). Any other pairing is a contract violation, not a
# tolerated "X or X-2". The default model width is Layout B (52 pairs) until the
# header is regenerated against the target layout (Fase 1B/4B).
LLTF_PAIRS_FLAGGED = 51     # Layout A: first_word_invalid true, 102 B int8 LLTF
LLTF_PAIRS_UNFLAGGED = 52   # Layout B: first_word_invalid false, 104 B int8 LLTF


class DatasetError(ValueError):
    """Base for dataset-adapter data-contract failures."""


class EmptyFeatureMatrixError(DatasetError):
    """No frame in the recording passed the flag-bound layout filter."""


class MixedLayoutError(DatasetError):
    """Frames that passed the filter did not share a single LLTF width."""

SCHEMA_VERSION_V2 = 2
SCHEMA_VERSION_V3 = 3

# Binary mapping of the activity labels (spec §7 + §9.6 idle anchors). Derived
# from activity_label, never stored redundantly in v3 metadata.
BINARY_LABELS = {
    "fall_forward": "fall",
    "fall_backward": "fall",
    "fall_lemas": "fall",
    "fall_keseleo": "fall",
    "walking": "non_fall",
    "fast_sitting": "non_fall",
    "bending": "non_fall",
    "object_drop": "non_fall",
    "empty_room": "non_fall",
    "still_standing": "non_fall",
    "still_sitting": "non_fall",
}


def _to_number(value: str) -> float | int | None:
    """Parse a frames.csv numeric cell, mapping 'na'/'' to None (unavailable)."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text == NA:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _to_bool(value: str) -> bool | None:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def _decode_base64_bytes(value: str) -> bytes:
    text = str(value or "").strip()
    if not text or text == NA:
        return b""
    try:
        return base64.b64decode(text, validate=False)
    except (ValueError, base64.binascii.Error):
        return b""


def _signed8(byte: int) -> int:
    return byte - 256 if byte > 127 else byte


@dataclass
class FrameRecord:
    """One CSI frame with its metadata and both stored payloads."""

    frame_sequence: int
    recording_id: str | None = None
    seq: int | None = None
    rx_seq: int | None = None
    mac: str | None = None
    dmac: str | None = None
    rssi: int | None = None
    noise_floor: int | None = None
    channel: int | None = None
    secondary_channel: int | None = None
    sig_mode: int | None = None
    mcs: int | None = None
    rate: int | None = None
    bandwidth: int | None = None
    stbc: int | None = None
    data_type: int | None = None
    raw_len: int | None = None
    valid_len: int | None = None
    lltf_len: int | None = None
    ht_ltf_len: int | None = None
    stbc_ht_ltf_len: int | None = None
    first_word_invalid: bool | None = None
    agc_gain: int | None = None
    fft_gain: int | None = None
    rx_gain_compensation: float | None = None
    callback_timestamp_us: int | None = None
    rx_ctrl_timestamp_us: int | None = None
    host_receive_monotonic_ns: int | None = None
    dropped: int | None = None
    payload_ok: bool | None = None
    raw_payload: bytes = b""
    valid_payload: bytes = b""
    # v1 fallbacks may only carry a decoded payload; keep its origin explicit.
    payload_source: str = "frames_csv"

    def primary_payload(self) -> bytes:
        """Raw driver buffer when present, else the filtered/valid payload."""
        if self.raw_payload:
            return self.raw_payload
        return self.valid_payload


@dataclass
class EventSegment:
    """A labelled time span inside a recording (event/segment annotation)."""

    label: str
    start_offset_s: float | None = None
    end_offset_s: float | None = None
    started_at_utc: str | None = None
    ended_at_utc: str | None = None
    event_type: str | None = None
    source: str | None = None


@dataclass
class Recording:
    """A single recording: metadata, ordered frames and optional annotations."""

    recording_id: str
    label: str
    schema_version: int
    meta: dict = field(default_factory=dict)
    frames: list[FrameRecord] = field(default_factory=list)
    events: list[EventSegment] = field(default_factory=list)
    motion_samples: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # -- identity / session -------------------------------------------------
    @property
    def session_id(self) -> str | None:
        batch = self.meta.get("batch")
        if isinstance(batch, dict) and batch.get("batch_id"):
            return str(batch["batch_id"])
        return self.meta.get("session_id") or self.meta.get("batch_id")

    @property
    def trial_id(self) -> str | None:
        return self.meta.get("trial_id") or self.recording_id

    @property
    def subject_id(self) -> str | None:
        return self.meta.get("subject_id")

    @property
    def binary_label(self) -> str | None:
        """fall / non_fall derived from the activity label (spec §7)."""
        return BINARY_LABELS.get(self.label)

    @property
    def annotations(self) -> dict:
        """Manual fall annotations captured during the take (spec §11)."""
        node = self.meta.get("annotations")
        return node if isinstance(node, dict) else {}

    @property
    def status(self) -> str | None:
        return self.meta.get("status")

    @property
    def started_at_utc(self) -> str | None:
        return self.meta.get("recording_started_at_utc") or self.meta.get("started_at_utc")

    @property
    def ended_at_utc(self) -> str | None:
        return self.meta.get("recording_ended_at_utc") or self.meta.get("ended_at_utc")

    def __len__(self) -> int:
        return len(self.frames)

    def __iter__(self) -> Iterator[FrameRecord]:
        return iter(self.frames)


def decode_iq(payload: bytes, data_type: int | None) -> list[tuple[int, int]]:
    """Decode a CSI payload into ``(imaginary, real)`` pairs.

    ESP-IDF v5.5.3 stores each sub-carrier as imaginary byte then real byte.
    ``data_type == 1`` selects 16-bit little-endian samples, otherwise 8-bit.
    A trailing partial sample is dropped rather than zero-padded.
    """
    sample_bytes = 2 if int(data_type or 0) == 1 else 1
    pair_bytes = sample_bytes * 2
    pairs: list[tuple[int, int]] = []
    if not payload or len(payload) < pair_bytes:
        return pairs
    for offset in range(0, len(payload) - pair_bytes + 1, pair_bytes):
        if sample_bytes == 2:
            imag = struct.unpack_from("<h", payload, offset)[0]
            real = struct.unpack_from("<h", payload, offset + 2)[0]
        else:
            imag = _signed8(payload[offset])
            real = _signed8(payload[offset + 1])
        pairs.append((imag, real))
    return pairs


def amplitude(pairs: Iterable[Sequence[int]]) -> list[float]:
    """Per-sub-carrier amplitude (magnitude) from (imag, real) pairs."""
    return [math.hypot(float(real), float(imag)) for imag, real in pairs]


def leading_invalid_pairs(
    first_word_invalid: bool | None, data_type: int | None
) -> int:
    """Count of leading ``(imag, real)`` pairs of the *driver buffer* that the
    hardware corrupted when ``first_word_invalid`` is true.

    ESP-IDF v5.5.3 (``api-guides/wifi.rst``) scopes the flag to the first four
    bytes of the CSI data starting at ``wifi_csi_info_t.buf`` - which esp-radar
    forwards verbatim as ``raw_data`` (``esp_radar.c``: ``raw_data = info->buf``).
    A pair occupies ``2 * sample_bytes`` bytes, so that is 2 pairs for int8
    (``data_type == 0``) and 1 pair for int16 (``data_type == 1``). Returns 0
    when the flag is false or unknown, so callers never drop real samples.

    AUDIT LIMIT (2026-10-30): this count is only meaningful for a pair list
    decoded from ``FrameRecord.raw_payload`` (the original buffer). It must NOT
    be applied to ``valid_data`` or its LTF segments: esp-radar rebuilds
    ``valid_data`` by concatenating sub-carrier byte ranges of ``buf``
    (``csi_sub_carrier_table.c``), so the first pair of a segment generally is
    not ``buf``'s first pair. For the observed none/HT/20 MHz/STBC layout the
    LLTF segment starts at ``buf[76]`` and the invalid ``buf[2:4]`` lands at
    LLTF pair index 26, mid-segment. Per-layout mapping of the invalid word
    into ``valid_data`` is not yet proven; keep this helper for raw-buffer
    preprocessing only.
    """
    if not first_word_invalid:
        return 0
    sample_bytes = 2 if int(data_type or 0) == 1 else 1
    return max(0, 4 // (sample_bytes * 2))


def ltf_sections(frame: FrameRecord) -> dict[str, tuple[int, int]]:
    """Byte ranges of each LTF component inside the *valid* payload.

    Uses the per-frame component lengths reported by esp-radar so a consumer
    can select LLTF / HT-LTF / STBC-HT-LTF without re-deriving the layout.
    Components the device did not report are omitted, not zero-filled.
    """
    sections: dict[str, tuple[int, int]] = {}
    offset = 0
    for name, length in (
        ("lltf", frame.lltf_len),
        ("ht_ltf", frame.ht_ltf_len),
        ("stbc_ht_ltf", frame.stbc_ht_ltf_len),
    ):
        if length is None or length <= 0:
            continue
        sections[name] = (offset, offset + int(length))
        offset += int(length)
    return sections


def component_pairs(frame: FrameRecord, component: str = "lltf") -> list[tuple[int, int]]:
    """(imag, real) pairs for one LTF component of a frame.

    ``component`` is one of ``lltf``, ``ht_ltf``, ``stbc_ht_ltf`` or ``all``
    (the whole valid payload). Falls back to the raw buffer when the valid
    payload or component lengths are unavailable, so old recordings still work.
    """
    data_type = frame.data_type
    if not frame.valid_payload:
        return decode_iq(frame.raw_payload, data_type)
    if component == "all":
        return decode_iq(frame.valid_payload, data_type)
    sections = ltf_sections(frame)
    if component not in sections:
        # Layout lengths not reported (e.g. v1 recording): the LLTF sits at the
        # start of the valid payload, so expose what we can without inventing.
        if component == "lltf":
            return decode_iq(frame.valid_payload, data_type)
        return []
    start, stop = sections[component]
    return decode_iq(frame.valid_payload[start:stop], data_type)


def _lltf_component_bytes(frame: FrameRecord) -> int | None:
    """Reported LLTF byte length for a frame, or ``None`` when unreported.

    Uses esp-radar's per-frame ``lltf_len``; falls back to the whole valid
    payload only when the component lengths are absent (e.g. v1 recordings).
    """
    sections = ltf_sections(frame)
    if "lltf" in sections:
        start, stop = sections["lltf"]
        return stop - start
    if frame.lltf_len is None and frame.valid_payload:
        return len(frame.valid_payload)
    return None


def frame_layout_pairs(frame: FrameRecord) -> int:
    """Complex LLTF pairs of a frame's *intrinsic* layout (DATA_CONTRACT §1).

    Independent of the loaded model: ``first_word_invalid=true`` with a 102 B
    int8 LLTF is Layout A (51 pairs), ``false``/unknown with a 104 B int8 LLTF
    is Layout B (52 pairs). Any other length/flag binding is not a legal layout
    and yields 0. int16 frames (untested against the contract) yield 0 so callers
    drop them instead of guessing a width.
    """
    lltf_bytes = _lltf_component_bytes(frame)
    if not lltf_bytes or lltf_bytes <= 0:
        return 0
    if int(frame.data_type or 0) == 1:
        return 0
    flag = frame.first_word_invalid
    if flag is True:
        return LLTF_PAIRS_FLAGGED if lltf_bytes == LLTF_PAIRS_FLAGGED * 2 else 0
    if flag is False or flag is None:
        return LLTF_PAIRS_UNFLAGGED if lltf_bytes == LLTF_PAIRS_UNFLAGGED * 2 else 0
    return 0


def frame_lltf_pairs(
    frame: FrameRecord, model_pairs: int = BASELINE_SUBCARRIERS
) -> int:
    """Flag-bound pair count of a frame *only if* the loaded model can consume it.

    Mirrors the firmware gate (``main/activity_classifier.c``): 0 is returned for
    contract violations *and* for frames whose legal layout does not match the
    model width (e.g. a 51-pair frame under a 52-pair model) - those must wait
    for the header to be regenerated (Fase 1B/4B), never be silently squeezed.
    """
    layout = frame_layout_pairs(frame)
    return layout if layout == model_pairs else 0


def _uniform_lltf_pairs(frames: Sequence[FrameRecord]) -> tuple[int, int]:
    """Distinct *legitimate* layout widths and the contract-reject count.

    Counts every frame whose length/flag binding is legal (Layout A or B),
    regardless of the model, so a recording that mixes the two layouts is
    detected even when one layout happens to equal the model width.
    """
    distinct: set[int] = set()
    rejects = 0
    for frame in frames:
        layout = frame_layout_pairs(frame)
        if layout:
            distinct.add(layout)
        else:
            rejects += 1
    return len(distinct), rejects


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

_FRAMES_COLUMNS = (
    "recording_id", "frame_sequence", "seq", "rx_seq", "mac", "dmac", "rssi",
    "noise_floor", "channel", "secondary_channel", "sig_mode", "mcs", "rate",
    "bandwidth", "stbc", "data_type", "raw_len", "valid_len", "lltf_len",
    "ht_ltf_len", "stbc_ht_ltf_len", "first_word_invalid", "agc_gain",
    "fft_gain", "rx_gain_compensation", "callback_timestamp_us",
    "rx_ctrl_timestamp_us", "host_receive_monotonic_ns", "dropped",
    "payload_ok", "raw_b64", "valid_b64",
)


def _frame_from_row(row: dict[str, str]) -> FrameRecord:
    return FrameRecord(
        frame_sequence=int(_to_number(row.get("frame_sequence")) or 0),
        recording_id=row.get("recording_id") or None,
        seq=_to_number(row.get("seq")),
        rx_seq=_to_number(row.get("rx_seq")),
        mac=(row.get("mac") or None) if row.get("mac") != NA else None,
        dmac=(row.get("dmac") or None) if row.get("dmac") != NA else None,
        rssi=_to_number(row.get("rssi")),
        noise_floor=_to_number(row.get("noise_floor")),
        channel=_to_number(row.get("channel")),
        secondary_channel=_to_number(row.get("secondary_channel")),
        sig_mode=_to_number(row.get("sig_mode")),
        mcs=_to_number(row.get("mcs")),
        rate=_to_number(row.get("rate")),
        bandwidth=_to_number(row.get("bandwidth")),
        stbc=_to_number(row.get("stbc")),
        data_type=_to_number(row.get("data_type")),
        raw_len=_to_number(row.get("raw_len")),
        valid_len=_to_number(row.get("valid_len")),
        lltf_len=_to_number(row.get("lltf_len")),
        ht_ltf_len=_to_number(row.get("ht_ltf_len")),
        stbc_ht_ltf_len=_to_number(row.get("stbc_ht_ltf_len")),
        first_word_invalid=_to_bool(row.get("first_word_invalid", "")),
        agc_gain=_to_number(row.get("agc_gain")),
        fft_gain=_to_number(row.get("fft_gain")),
        rx_gain_compensation=_to_number(row.get("rx_gain_compensation")),
        callback_timestamp_us=_to_number(row.get("callback_timestamp_us")),
        rx_ctrl_timestamp_us=_to_number(row.get("rx_ctrl_timestamp_us")),
        host_receive_monotonic_ns=_to_number(row.get("host_receive_monotonic_ns")),
        dropped=_to_number(row.get("dropped")),
        payload_ok=_to_bool(row.get("payload_ok", "")),
        raw_payload=_decode_base64_bytes(row.get("raw_b64", "")),
        valid_payload=_decode_base64_bytes(row.get("valid_b64", "")),
        payload_source="frames_csv",
    )


def _load_frames_csv(path: Path) -> list[FrameRecord]:
    frames: list[FrameRecord] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return frames
        missing = [c for c in _FRAMES_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path.name}: frames.csv missing columns {missing}")
        for row in reader:
            frames.append(_frame_from_row(row))
    return frames


def _load_csi_data_csv(path: Path) -> list[FrameRecord]:
    """v1 fallback: rebuild frames from the legacy CSI_DATA csv ``data`` column.

    The legacy column stores the *valid* payload as comma-separated signed
    bytes, so it is loaded into ``valid_payload`` and flagged as such. Raw
    driver bytes were never stored in v1 and stay unavailable.
    """
    frames: list[FrameRecord] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "data" not in reader.fieldnames:
            return frames
        for index, row in enumerate(reader):
            raw = row.get("data") or ""
            payload = bytes(int(v) & 0xFF for v in raw.split(",") if v.strip() != "")
            frames.append(
                FrameRecord(
                    frame_sequence=index,
                    seq=_to_number(row.get("sequence", "")),
                    mac=row.get("mac") or None,
                    rssi=_to_number(row.get("rssi", "")),
                    noise_floor=_to_number(row.get("noise_floor", "")),
                    channel=_to_number(row.get("channel", "")),
                    secondary_channel=_to_number(row.get("secondary_channel", "")),
                    sig_mode=_to_number(row.get("sig_mode", "")),
                    mcs=_to_number(row.get("mcs", "")),
                    rate=_to_number(row.get("rate", "")),
                    bandwidth=_to_number(row.get("bandwidth", "")),
                    stbc=_to_number(row.get("stbc", "")),
                    valid_len=_to_number(row.get("len", "")),
                    first_word_invalid=_to_bool(row.get("first_word", "")),
                    agc_gain=_to_number(row.get("agc_gain", "")),
                    fft_gain=_to_number(row.get("fft_gain", "")),
                    callback_timestamp_us=_to_number(row.get("timestamp", "")),
                    rx_ctrl_timestamp_us=_to_number(row.get("local_timestamp", "")),
                    valid_payload=payload,
                    payload_source="csi_data_csv",
                )
            )
    return frames


def _load_events(path: Path) -> tuple[list[EventSegment], list[dict]]:
    if not path.is_file():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], []
    segments: list[EventSegment] = []
    for item in data.get("segments", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        segments.append(
            EventSegment(
                label=str(item.get("label", "")),
                start_offset_s=item.get("start_offset_s"),
                end_offset_s=item.get("end_offset_s"),
                started_at_utc=item.get("started_at_utc"),
                ended_at_utc=item.get("ended_at_utc"),
                event_type=item.get("type"),
                source=item.get("source"),
            )
        )
    motion = data.get("motion_samples", []) if isinstance(data, dict) else []
    return segments, motion if isinstance(motion, list) else []


def _events_from_meta(meta: dict) -> tuple[list[EventSegment], list[dict]]:
    """v3: events live inside meta.json (no separate events.json file)."""
    node = meta.get("events")
    if not isinstance(node, dict):
        return [], []
    segments: list[EventSegment] = []
    for item in node.get("segments", []):
        if not isinstance(item, dict):
            continue
        segments.append(
            EventSegment(
                label=str(item.get("label", "")),
                start_offset_s=item.get("start_offset_s"),
                end_offset_s=item.get("end_offset_s"),
                started_at_utc=item.get("started_at_utc"),
                ended_at_utc=item.get("ended_at_utc"),
                event_type=item.get("type"),
                source=item.get("source"),
            )
        )
    motion = node.get("motion_samples", [])
    return segments, motion if isinstance(motion, list) else []


def find_recording_dir(recordings_dir: Path, rec_id: str) -> Path | None:
    for meta_path in recordings_dir.glob(f"*/{rec_id}.meta.json"):
        return meta_path.parent
    return None


def load_recording(recordings_dir: Path, rec_id: str) -> Recording:
    """Load one recording, preferring the lossless frames.csv payload.

    Supports metadata v3 (activity_label, embedded events) and keeps v1/v2
    fallbacks (label/id keys, separate events.json, csi_data.csv payloads).
    """
    folder = find_recording_dir(Path(recordings_dir), rec_id)
    if folder is None:
        raise FileNotFoundError(f"no meta.json for recording {rec_id!r}")
    meta_path = folder / f"{rec_id}.meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read metadata for {rec_id!r}: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError(f"metadata root for {rec_id!r} is not a JSON object")

    schema_version = int(meta.get("schema_version") or 1)
    label = str(meta.get("activity_label") or meta.get("label") or folder.name)
    warnings: list[str] = []

    frames_path = folder / f"{rec_id}.frames.csv"
    csi_data_path = folder / f"{rec_id}.csi_data.csv"
    if frames_path.is_file():
        frames = _load_frames_csv(frames_path)
    elif csi_data_path.is_file():
        frames = _load_csi_data_csv(csi_data_path)
        warnings.append(
            "loaded from legacy csi_data.csv; raw driver payload unavailable"
        )
    else:
        frames = []
        warnings.append("no frames.csv or csi_data.csv found")

    # v3 stores events inside meta.json; v2 keeps a separate events.json.
    events, motion = _events_from_meta(meta)
    if not events:
        events_path = folder / f"{rec_id}.events.json"
        events, legacy_motion = _load_events(events_path)
        motion = motion or legacy_motion
    if not events:
        # Homogeneous-activity recordings may only carry a per-recording label.
        if label:
            events = [EventSegment(label=label, source="recording_label")]

    return Recording(
        recording_id=str(meta.get("recording_id") or meta.get("id") or rec_id),
        label=label,
        schema_version=schema_version,
        meta=meta,
        frames=frames,
        events=events,
        motion_samples=motion,
        warnings=warnings,
    )


def iter_recordings(recordings_dir: Path) -> Iterator[str]:
    """Yield every recording id under a recordings directory."""
    for meta_path in sorted(Path(recordings_dir).rglob("*.meta.json")):
        yield meta_path.name[: -len(".meta.json")]


# --------------------------------------------------------------------------
# Adapters. Each returns plain nested lists (no hard numpy dependency) plus a
# config dict so the exact transform can be reproduced. Choose the adapter
# that matches the target model family; do not force one shape on all models.
# --------------------------------------------------------------------------

RepresentationFn = Callable[[FrameRecord], list[float]]


def amplitude_representation(component: str = "lltf") -> RepresentationFn:
    """Per-frame amplitude vector for one LTF component (rule-based/feature ML).

    ``first_word_invalid`` is deliberately *not* handled here: this function
    reads esp-radar's compacted ``valid_data``, whose leading pairs do not map
    onto the invalid first four bytes of the driver buffer (see
    :func:`leading_invalid_pairs` for the audit limit). Trimming belongs in
    raw-buffer preprocessing once that mapping is proven per layout.
    """

    def _repr(frame: FrameRecord) -> list[float]:
        return amplitude(component_pairs(frame, component))

    return _repr


def iq_representation(component: str = "lltf") -> RepresentationFn:
    """Interleaved [imag, real, ...] vector, keeping phase for temporal models.

    ``first_word_invalid`` is not handled here for the same audited reason as
    in :func:`amplitude_representation`.
    """

    def _repr(frame: FrameRecord) -> list[float]:
        pairs = component_pairs(frame, component)
        out: list[float] = []
        for imag, real in pairs:
            out.append(float(imag))
            out.append(float(real))
        return out

    return _repr


REPRESENTATIONS: dict[str, Callable[..., RepresentationFn]] = {
    "amplitude": amplitude_representation,
    "iq": iq_representation,
}


def baseline_band_features(
    amplitude_frames: Sequence[Sequence[float]],
    feature_count: int = BASELINE_FEATURE_COUNT,
    window: int = BASELINE_WINDOW_FRAMES,
    stride: int = BASELINE_WINDOW_STRIDE,
    subcarriers: int = BASELINE_SUBCARRIERS,
) -> list[list[float]]:
    """Reproduce the deployed baseline: mean log amplitude-change per band.

    This is a *reader-side* re-derivation kept bit-for-bit compatible with
    ``main/activity_classifier.c`` and ``train_activity_model.py`` so the raw
    dataset can regenerate the baseline features without touching the model.
    """
    features: list[list[float]] = []
    final_start = len(amplitude_frames) - window
    for start in range(0, final_start + 1, stride):
        band_delta = [0.0] * feature_count
        band_counts = [0] * feature_count
        for frame_index in range(start + 1, start + window):
            previous = amplitude_frames[frame_index - 1]
            current = amplitude_frames[frame_index]
            for sc in range(subcarriers):
                band = sc * feature_count // subcarriers
                band_delta[band] += abs(current[sc] - previous[sc])
                band_counts[band] += 1
        features.append(
            [
                math.log1p(band_delta[i] / max(1, band_counts[i]))
                for i in range(feature_count)
            ]
        )
    return features


def _series_matrix(recording: Recording, repr_fn: RepresentationFn) -> list[list[float]]:
    return [repr_fn(frame) for frame in recording.frames]


def to_feature_matrix(
    recording: Recording,
    *,
    component: str = "lltf",
    window: int = BASELINE_WINDOW_FRAMES,
    stride: int = BASELINE_WINDOW_STRIDE,
    feature_count: int = BASELINE_FEATURE_COUNT,
    model_pairs: int = BASELINE_SUBCARRIERS,
) -> tuple[list[list[float]], list[str], dict]:
    """Adapter for LR / Linear-SVM / Decision-Tree / Random-Forest.

    Returns ``(X, y, config)``: one row per window of band features, the label
    applied to every window of the recording, and the parameters used.

    The LLTF floor is **dynamic and flag-bound** (DATA_CONTRACT §1), not a fixed
    52: a frame is kept only when its length and ``first_word_invalid`` agree -
    102 B/51 pairs when flagged (Layout A) or ``model_pairs`` when unflagged
    (Layout B). This is the reader-side mirror of the firmware gate, so 51-pair
    takes are decoded instead of silently dropped. Frames that violate the
    binding are rejected and counted. When the loaded model width differs from
    the recording's layout the model header must be regenerated to match
    (Fase 1B/4B); that is reported in ``config`` rather than guessed here.

    Raises :class:`EmptyFeatureMatrixError` when no frame passes the filter
    (previously this silently produced an empty matrix) and
    :class:`MixedLayoutError` when the kept frames do not share one width.
    """
    repr_fn = amplitude_representation(component)
    series = _series_matrix(recording, repr_fn)
    distinct_layouts, contract_rejects = _uniform_lltf_pairs(recording.frames)
    if distinct_layouts > 1:
        raise MixedLayoutError(
            f"recording {recording.recording_id!r}: mixed LLTF layouts "
            f"({distinct_layouts} distinct legal widths) in one take"
        )
    rows: list[list[float]] = []
    for frame, row in zip(recording.frames, series):
        pairs = frame_lltf_pairs(frame, model_pairs)
        if pairs and len(row) >= pairs:
            rows.append(row[:pairs])
    if not rows:
        raise EmptyFeatureMatrixError(
            f"recording {recording.recording_id!r}: 0 of {len(series)} frames "
            f"passed the flag-bound LLTF layout filter "
            f"({contract_rejects} contract violation(s)); model width "
            f"{model_pairs} pairs"
        )
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise MixedLayoutError(
            f"recording {recording.recording_id!r}: mixed LLTF widths "
            f"{sorted(widths)} pairs in one take"
        )
    width = widths.pop()
    X = baseline_band_features(
        rows, feature_count=feature_count, window=window, stride=stride,
        subcarriers=width,
    )
    y = [recording.label] * len(X)
    config = {
        "adapter": "feature_matrix",
        "family": ["logistic-regression", "linear-svm", "decision-tree", "random-forest"],
        "component": component,
        "representation": "amplitude",
        "first_word_invalid_handling": "flag-bound layout filter (DATA_CONTRACT §1); never trims compacted valid_data",
        "window_frames": window,
        "stride_frames": stride,
        "feature_count": feature_count,
        "subcarriers": width,
        "model_pairs": model_pairs,
        "layout_matches_model": width == model_pairs,
        "frames_total": len(series),
        "frames_kept": len(rows),
        "contract_rejects": contract_rejects,
        "distinct_layouts": distinct_layouts,
    }
    return X, y, config


def to_time_series_tensor(
    recording: Recording,
    *,
    component: str = "lltf",
    representation: str = "amplitude",
    window: int = BASELINE_WINDOW_FRAMES,
    stride: int = BASELINE_WINDOW_STRIDE,
    channels: Sequence[int] | None = None,
) -> tuple[list[list[list[float]]], list[str], dict]:
    """Adapter for MiniROCKET / MultiROCKET / Hydra / TCN / CNN-LSTM.

    Returns ``(windows, y, config)`` where each window is shaped
    ``[channels, length]``. ``channels`` selects sub-carrier indices (or I/Q
    slots); when omitted every available channel is kept. No resampling or
    normalisation is applied here - that stays in the training preprocessing.
    ``first_word_invalid`` is not trimmed here (unverified mapping into the
    compacted valid payload; see :func:`leading_invalid_pairs`).
    """
    if representation not in REPRESENTATIONS:
        raise ValueError(f"unknown representation {representation!r}")
    repr_fn = REPRESENTATIONS[representation](component)
    matrix = _series_matrix(recording, repr_fn)
    if not matrix:
        return [], [], {}
    width = min(len(row) for row in matrix)
    selected = list(channels) if channels else list(range(width))
    windows: list[list[list[float]]] = []
    labels: list[str] = []
    final_start = len(matrix) - window
    for start in range(0, final_start + 1, stride):
        block = matrix[start : start + window]
        window_tensor = [[row[ch] if ch < len(row) else 0.0 for row in block] for ch in selected]
        windows.append(window_tensor)
        labels.append(recording.label)
    config = {
        "adapter": "time_series_tensor",
        "family": ["minirocket", "multirocket", "hydra", "tcn", "cnn-lstm"],
        "component": component,
        "representation": representation,
        "first_word_invalid_handling": "metadata only; trimming deferred pending payload-mapping audit",
        "window_frames": window,
        "stride_frames": stride,
        "channels": selected,
        "shape": [len(selected), window],
    }
    return windows, labels, config


def to_observation_sequence(
    recording: Recording,
    *,
    component: str = "lltf",
    representation: str = "amplitude",
) -> tuple[list[list[float]], list[float | None], dict]:
    """Adapter for HMM / DTW / shapelet models.

    Returns the full ordered sequence ``(observations, timestamps_us, config)``
    with no windowing, so segment boundaries and temporal order are preserved.
    ``first_word_invalid`` is not trimmed here (unverified mapping into the
    compacted valid payload; see :func:`leading_invalid_pairs`).
    """
    if representation not in REPRESENTATIONS:
        raise ValueError(f"unknown representation {representation!r}")
    repr_fn = REPRESENTATIONS[representation](component)
    observations = _series_matrix(recording, repr_fn)
    timestamps = [frame.callback_timestamp_us for frame in recording.frames]
    config = {
        "adapter": "observation_sequence",
        "family": ["hmm", "dtw", "shapelet"],
        "component": component,
        "representation": representation,
        "first_word_invalid_handling": "metadata only; trimming deferred pending payload-mapping audit",
        "length": len(observations),
    }
    return observations, timestamps, config
