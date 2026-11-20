#!/usr/bin/env python3
"""Development-only CSI annotation assistance; never updates recordings or policies.

Fixed, untuned correlation/DTW methods are checked against masked observer marks.
This is NOT detector CV, physical ground truth, a calibrated confidence estimator,
or permission to use these sidecars in training. Recompute with fold-owned donors
before any approved downstream experiment. Original metadata is never rewritten.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import platform
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from fall_detection.dataset_io import load_recording
from fall_detection.train_activity_model import read_timed_amplitude_frames_from_frames_csv
from fall_detection.validate_recording import validate_recording

ROOT = Path(__file__).resolve().parents[1]
BOUNDARIES = ("fall_start", "fall_impact")
METHODS = ("ncc", "dtw")
PROTOCOLS = ("profile_preferred", "other_day")


@dataclass(frozen=True)
class Config:
    grid_hz: int = 10
    smooth_radius_s: float = 0.15
    max_gap_s: float = 0.5
    max_warp_s: float = 2.5
    anchor_tolerance_s: float = 0.3
    annotation_clock_tolerance_s: float = 0.02
    donor_count: int = 3
    min_samples: int = 30
    warp_penalty: float = 0.05


@dataclass
class Take:
    recording_id: str
    meta: dict
    hashes: dict
    annotation: dict
    grid: np.ndarray = field(default_factory=lambda: np.empty(0))
    signal: np.ndarray = field(default_factory=lambda: np.empty((0, 8)))
    quality: dict = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    packet_keys: frozenset = field(default_factory=frozenset)
    lineage: frozenset = field(default_factory=frozenset)
    payload_hash: str = ""

    @property
    def complete_annotation(self):
        return all(self.annotation.get(k) is not None for k in BOUNDARIES)

    @property
    def label(self):
        return self.meta.get("activity_label")

    @property
    def profile(self):
        return (self.meta.get("stimulus") or {}).get("mode")

    @property
    def day(self):
        return str(self.meta.get("started_at_utc") or "")[:10]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_seconds(value: str) -> float:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("UTC timestamp has no timezone")
    return stamp.timestamp()


def manual_offsets(meta: dict, config: Config) -> dict:
    """Validate stored marks; never repair a conflicting observer annotation."""
    result = {}
    duration = float(meta["actual_duration_s"])
    start = utc_seconds(meta["started_at_utc"])
    for key in BOUNDARIES:
        mark = (meta.get("annotations") or {}).get(key)
        if mark is None:
            result[key] = None
            continue
        offset = float(mark["offset_s"])
        timestamp_offset = utc_seconds(mark["timestamp_utc"]) - start
        if not math.isfinite(offset) or not 0 <= offset <= duration:
            raise ValueError(f"{key}: invalid offset")
        if abs(offset - timestamp_offset) > config.annotation_clock_tolerance_s:
            raise ValueError(f"{key}: offset/UTC conflict")
        result[key] = offset
    if all(result[k] is not None for k in BOUNDARIES):
        if result["fall_start"] >= result["fall_impact"]:
            raise ValueError("observer boundaries are not increasing")
    return result


def prepare_signal(times: np.ndarray, amplitude: np.ndarray, config: Config):
    """Offline-only time resampling. Explicitly collapse host batching duplicates.

    No sorting, extrapolation, or interpolation across a gap over max_gap_s.
    Per-take normalization uses only this input, no labels or other recordings.
    """
    if amplitude.ndim != 2 or amplitude.shape != (len(times), 51):
        raise ValueError("expected canonical 51-pair LLTF amplitude")
    if len(times) < config.min_samples or not np.isfinite(times).all():
        raise ValueError("insufficient/invalid host timestamps")
    if not np.isfinite(amplitude).all() or np.any(np.diff(times) < 0):
        raise ValueError("nonfinite amplitudes or reversed host timestamps")
    unique, starts, counts = np.unique(times, return_index=True, return_counts=True)
    # np.unique does not change ordering here: negative deltas were rejected above.
    merged = np.add.reduceat(amplitude, starts, axis=0) / counts[:, None]
    dt = np.diff(unique)
    quality = {
        "source_frames": len(times), "unique_host_times": len(unique),
        "coalesced_host_duplicates": len(times) - len(unique),
        "max_host_gap_s": float(max(dt)) if len(dt) else None,
        "clock": "host_receive relative to started_at_utc via clock_anchor",
        "clock_uncertainty_s": None,
        "clock_warning": "host batching/transport delay is not independently bounded",
    }
    if len(dt) == 0 or max(dt) > config.max_gap_s:
        raise ValueError(f"host gap {quality['max_host_gap_s']}s exceeds {config.max_gap_s}s; not interpolated")
    grid = np.arange(math.ceil(unique[0] * config.grid_hz),
                     math.floor(unique[-1] * config.grid_hz) + 1) / config.grid_hz
    if len(grid) < config.min_samples:
        raise ValueError("insufficient time-grid support")
    resampled = np.column_stack([np.interp(grid, unique, merged[:, k]) for k in range(51)])
    # Difference individual carriers before pooling: preserve signed-independent motion.
    delta = np.abs(np.diff(resampled, axis=0, prepend=resampled[:1])) * config.grid_hz
    bands = np.arange(51) * 4 // 51
    levels = np.column_stack([resampled[:, bands == b].mean(axis=1) for b in range(4)])
    motion = np.column_stack([delta[:, bands == b].mean(axis=1) for b in range(4)])
    raw = np.log1p(np.column_stack((levels, motion)))
    smoothed = np.vstack([raw[np.abs(grid - t) <= config.smooth_radius_s + 1e-9].mean(axis=0)
                          for t in grid])
    scale = smoothed.std(axis=0)
    if np.max(scale) < 1e-8:
        raise ValueError("flat signal cannot establish alignment")
    normalized = (smoothed - smoothed.mean(axis=0)) / np.maximum(scale, 1e-8)
    quality.update(grid_samples=len(grid), grid_start_s=float(grid[0]), grid_end_s=float(grid[-1]))
    return grid, normalized, quality


def load_take(path: Path, recordings: Path, config: Config) -> Take:
    meta = json.loads(path.read_text())
    rid = meta["recording_id"]
    frame_path = path.with_name(f"{rid}.frames.csv")
    take = Take(rid, meta, {"meta": sha256(path), "frames": sha256(frame_path)}, {})
    take.lineage = frozenset(str(x) for x in (
        rid, meta.get("parent_recording_id"), meta.get("source_recording_id")
    ) if x)
    try:
        take.annotation = manual_offsets(meta, config)
        rec = load_recording(recordings, rid)
        report = validate_recording(rec)
        take.quality["validator"] = report
        if report["status"] == "INVALID" or rec.status != "complete":
            raise ValueError("structurally invalid or incomplete recording")
        packet_keys = []
        content = hashlib.sha256()
        for f in rec.frames:
            content.update(f.valid_payload)
            packet_keys.append((f.mac, f.callback_timestamp_us, f.rx_seq,
                                hashlib.sha256(f.valid_payload).hexdigest()))
            if f.data_type != 0 or f.lltf_len != 102 or f.first_word_invalid is not True:
                raise ValueError("unsupported flag-bound int8 51-pair layout")
        take.payload_hash = content.hexdigest()
        take.packet_keys = frozenset(packet_keys)
        if len({(f.mac, f.channel) for f in rec.frames}) != 1:
            raise ValueError("multiple source MAC/channel segments")
        amplitudes, host = read_timed_amplitude_frames_from_frames_csv(frame_path)
        if len(amplitudes) != len(rec.frames):
            raise ValueError("canonical loader omitted frames; no silent support change")
        anchor = meta["clock_anchor"]
        start_host = (float(anchor["performance_now_ms"]) +
                      utc_seconds(meta["started_at_utc"]) * 1000 - float(anchor["date_now_ms"])) / 1000
        times = np.asarray(host) - start_host
        take.grid, take.signal, quality = prepare_signal(times, np.asarray(amplitudes), config)
        take.quality.update(quality)
        for key, value in take.annotation.items():
            if value is not None and not take.grid[0] <= value <= take.grid[-1]:
                raise ValueError(f"{key} outside observed grid support")
    except (ValueError, KeyError, TypeError) as exc:
        take.blockers.append(str(exc))
    return take


def dtw_path(tx, x, ty, y, config: Config):
    """Elapsed-time band, bounded local slopes (1,1)/(1,2)/(2,1).

    Intermediate cells contribute to cost and path; skipped samples are never
    hidden. This is a constrained variant, not a call to tslearn's default DTW.
    """
    n, m = len(x), len(y)
    distance = np.mean((x[:, None, :] - y[None, :, :]) ** 2, axis=2)
    distance[np.abs(tx[:, None] - ty[None, :]) > config.max_warp_s + 1e-9] = np.inf
    costs = np.full((n + 1, m + 1), np.inf)
    moves = np.zeros((n + 1, m + 1), dtype=np.int8)
    costs[0, 0] = 0
    for i in range(1, n + 1):
        for jj in np.flatnonzero(np.isfinite(distance[i - 1])):
            j = int(jj) + 1
            best = costs[i - 1, j - 1]
            move = 1
            if i >= 2:
                other = costs[i - 2, j - 1] + distance[i - 2, j - 1] + config.warp_penalty
                if other < best:
                    best, move = other, 2
            if j >= 2:
                other = costs[i - 1, j - 2] + distance[i - 1, j - 2] + config.warp_penalty
                if other < best:
                    best, move = other, 3
            costs[i, j] = best + distance[i - 1, j - 1]
            moves[i, j] = move
    if not np.isfinite(costs[n, m]):
        raise ValueError("no bounded DTW path")
    path = []
    i, j = n, m
    while i and j:
        path.append((i - 1, j - 1))
        move = moves[i, j]
        if move == 1:
            i, j = i - 1, j - 1
        elif move == 2:
            path.append((i - 2, j - 1))
            i, j = i - 2, j - 1
        else:
            path.append((i - 1, j - 2))
            i, j = i - 1, j - 2
    if i or j:
        raise ValueError("incomplete DTW traceback")
    return list(reversed(path))


def map_boundary(path, target_grid, donor_grid, boundary: float) -> float:
    by_donor = defaultdict(list)
    for i, j in path:
        by_donor[j].append(float(target_grid[i]))
    indices = sorted(by_donor)
    times = donor_grid[indices]
    if not times[0] <= boundary <= times[-1]:
        raise ValueError("donor boundary outside alignment support")
    mapped = [np.median(by_donor[j]) for j in indices]
    return float(np.interp(boundary, times, mapped))


def align_pair(target: Take, donor: Take, method: str, known_start: float | None,
               config: Config) -> dict:
    tx, x, ty, y = target.grid, target.signal, donor.grid, donor.signal
    if method not in METHODS:
        raise ValueError(f"unknown alignment method: {method}")
    if known_start is not None and not tx[0] <= known_start <= tx[-1]:
        raise ValueError("known start outside target support")
    if method == "ncc":
        candidates = []
        limit = round(config.max_warp_s * config.grid_hz)
        for lag in range(-limit, limit + 1):
            first, last = max(0, lag), min(len(x), len(y) + lag)
            if last - first < config.min_samples:
                continue
            shift = float(tx[0] - ty[0] + lag / config.grid_hz)
            if abs(shift) > config.max_warp_s + 1e-9:
                continue
            if known_start is not None and abs(donor.annotation["fall_start"] + shift - known_start) > config.anchor_tolerance_s:
                continue
            a, b = x[first:last], y[first-lag:last-lag]
            a, b = a - a.mean(axis=0), b - b.mean(axis=0)
            norm = float(np.linalg.norm(a) * np.linalg.norm(b))
            if norm <= 1e-10:
                continue
            correlation = float(np.sum(a * b) / norm)
            candidates.append((correlation, lag, shift, first, last))
        if not candidates:
            raise ValueError("no valid normalized-correlation lag")
        candidates.sort(key=lambda c: (-c[0], abs(c[1]), c[1]))
        best = candidates[0]
        path = [(i, i-best[1]) for i in range(best[3], best[4])]
        mapped = {k: map_boundary(path, tx, ty, donor.annotation[k]) for k in BOUNDARIES}
        alternatives = [c[0] for c in candidates if abs(c[1] - best[1]) >= 3]
        components = {"correlation": best[0], "lag_s": best[2],
                      "separated_peak_margin": best[0] - max(alternatives) if alternatives else None}
        cost = 1 - best[0]
    else:
        if known_start is None:
            path = dtw_path(tx, x, ty, y, config)
        else:
            a = int(np.argmin(abs(tx - known_start)))
            b = int(np.argmin(abs(ty - donor.annotation["fall_start"])))
            left = dtw_path(tx[:a+1], x[:a+1], ty[:b+1], y[:b+1], config)
            right = dtw_path(tx[a:], x[a:], ty[b:], y[b:], config)
            path = left + [(i+a, j+b) for i, j in right[1:]]
        mapped = {k: map_boundary(path, tx, ty, donor.annotation[k]) for k in BOUNDARIES}
        cost = float(np.mean([np.mean((x[i] - y[j])**2) for i, j in path]))
        components = {"path_length": len(path), "mean_squared_path_cost": cost,
                      "max_abs_time_warp_s": max(abs(float(tx[i]-ty[j])) for i, j in path)}
    if known_start is not None:
        mapped["fall_start"] = known_start
    if not tx[0] <= mapped["fall_start"] < mapped["fall_impact"] <= tx[-1]:
        raise ValueError("mapped boundaries unordered/outside target support")
    return {"donor_id": donor.recording_id, "donor_hashes": donor.hashes,
            "donor_day": donor.day, "donor_profile": donor.profile, "cost": cost,
            "mapped": mapped, "components": components, "path": path,
            "path_axes": {"target_start_s": float(tx[0]), "donor_start_s": float(ty[0]),
                          "grid_step_s": 1 / config.grid_hz,
                          "target_samples": len(tx), "donor_samples": len(ty)},
            "donor_annotation_source": "ORIGINAL_OBSERVER_NOT_INDEPENDENTLY_VERIFIED"}


def shares_source(first: Take, second: Take) -> bool:
    """Known overlap only; this does not establish subject/session independence."""
    return (first.recording_id == second.recording_id
            or bool(first.lineage & second.lineage)
            or bool(first.payload_hash and first.payload_hash == second.payload_hash)
            or bool(first.packet_keys & second.packet_keys))


def donor_pool(target: Take, takes: list[Take], protocol: str) -> list[Take]:
    eligible = []
    target_channel = (target.meta.get("wifi") or {}).get("channel")
    for donor in takes:
        if donor.blockers or not donor.complete_annotation or donor.label != target.label:
            continue
        if shares_source(target, donor):
            continue
        channel = (donor.meta.get("wifi") or {}).get("channel")
        if target_channel is not None and channel is not None and target_channel != channel:
            continue
        if protocol == "other_day" and donor.day == target.day:
            continue
        eligible.append(donor)
    return eligible


def propose(target: Take, takes: list[Take], method: str, protocol: str,
            known_start: float | None, config: Config, cache: dict) -> dict:
    result = {"status": "ABSTAINED", "reason": None, "method": method,
              "protocol": protocol, "prediction": None, "selected_donors": [],
              "confidence_probability": None, "confidence_status": "UNCALIBRATED",
              "training_eligible": False, "verification_status": "NOT_REVIEWED"}
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown donor protocol: {protocol}")
    if target.blockers:
        result["reason"] = "; ".join(target.blockers)
        return result
    if known_start is None and target.annotation.get("fall_impact") is not None:
        result["reason"] = "impact_present_start_missing_not_supported"
        return result
    candidates, failures = [], Counter()
    for donor in donor_pool(target, takes, protocol):
        key = (target.recording_id, donor.recording_id, method, known_start)
        if key not in cache:
            try:
                cache[key] = align_pair(target, donor, method, known_start, config)
            except ValueError as exc:
                cache[key] = str(exc)
        value = cache[key]
        if isinstance(value, str):
            failures[value] += 1
        else:
            candidates.append(value)
    by_id = {t.recording_id: t for t in takes}

    def select(pool):
        selected = []
        for candidate in sorted(pool, key=lambda v: (v["cost"], v["donor_id"])):
            if any(shares_source(by_id[candidate["donor_id"]], by_id[s["donor_id"]]) for s in selected):
                continue
            selected.append(candidate)
            if len(selected) == config.donor_count:
                break
        return selected

    same = select([v for v in candidates if target.profile is not None and v["donor_profile"] == target.profile])
    prefer_same = protocol == "profile_preferred" and len(same) >= config.donor_count
    # Profile preference is a donor-selection heuristic, not a separate model.
    selected = same if prefer_same else select(candidates)
    result.update(eligible_alignments=len(candidates), donor_failures=dict(failures),
                  same_profile_preference=prefer_same)
    if len(selected) < config.donor_count:
        result["reason"] = f"fewer_than_{config.donor_count}_source_disjoint_candidate_donors"
        return result
    prediction = {k: float(np.median([s["mapped"][k] for s in selected])) for k in BOUNDARIES}
    if known_start is not None:
        prediction["fall_start"] = known_start
    result.update(status="AUTO_PROPOSED", prediction=prediction, selected_donors=selected,
                  boundary_spread_s={k: float(np.ptp([s["mapped"][k] for s in selected])) for k in BOUNDARIES},
                  donor_boundary_range_s={k: [min(s["mapped"][k] for s in selected),
                                             max(s["mapped"][k] for s in selected)] for k in BOUNDARIES},
                  median_alignment_cost=float(np.median([s["cost"] for s in selected])),
                  cross_profile_donors=sum(s["donor_profile"] != target.profile for s in selected))
    return result


def validation_row(target: Take, method: str, protocol: str, task: str, result: dict) -> dict:
    row = {"recording_id": target.recording_id, "activity": target.label,
           "profile": target.profile, "day": target.day, "method": method,
           "protocol": protocol, "task": task, "status": result["status"],
           "reason": result.get("reason"), "donor_ids": "|".join(v["donor_id"] for v in result["selected_donors"])}
    for key in BOUNDARIES:
        scored = not (task == "impact_only" and key == "fall_start")
        value = (result.get("prediction") or {}).get(key)
        row[f"{key}_truth_s"] = target.annotation.get(key)
        row[f"{key}_predicted_s"] = value
        row[f"{key}_error_s"] = value - target.annotation[key] if scored and value is not None else None
        row[f"{key}_spread_s"] = (result.get("boundary_spread_s") or {}).get(key)
    return row


def summarize_validation(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["method"], row["protocol"], row["task"], "ALL", "ALL")].append(row)
        groups[(row["method"], row["protocol"], row["task"], row["profile"], row["activity"])].append(row)
    summaries = []
    for (method, protocol, task, profile, activity), members in sorted(groups.items(), key=str):
        result = dict(method=method, protocol=protocol, task=task, profile=profile, activity=activity,
                      targets=len(members), proposed=sum(r["status"] == "AUTO_PROPOSED" for r in members))
        for boundary in BOUNDARIES:
            errors = [r[f"{boundary}_error_s"] for r in members if r[f"{boundary}_error_s"] is not None]
            absolute = np.abs(errors)
            result[boundary] = None if not errors else {
                "n": len(errors), "bias_s": float(np.mean(errors)), "mae_s": float(np.mean(absolute)),
                "median_abs_error_s": float(np.median(absolute)), "p95_abs_error_s": float(np.quantile(absolute, .95)),
                "max_abs_error_s": float(max(absolute)),
                "fraction_within_0_3s": float(np.mean(absolute <= .3)),
                "fraction_within_0_5s": float(np.mean(absolute <= .5)),
                "spread_sensitivity": [],
            }
            if errors:
                for threshold in (.25, .5, 1.0):
                    selected = [r for r in members if r[f"{boundary}_error_s"] is not None
                                and r[f"{boundary}_spread_s"] <= threshold]
                    e = [abs(r[f"{boundary}_error_s"]) for r in selected]
                    result[boundary]["spread_sensitivity"].append({
                        "max_spread_s": threshold, "n": len(e), "coverage": len(e)/len(members),
                        "mae_s": float(np.mean(e)) if e else None,
                        "p95_abs_error_s": float(np.quantile(e, .95)) if e else None})
        summaries.append(result)
    return summaries


def write_json(path: Path, value: Any):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def output_safe(recordings: Path, output: Path):
    recordings, output = recordings.resolve(), output.resolve()
    if output == recordings or recordings in output.parents or output in recordings.parents:
        raise ValueError("output must be outside recording tree and cannot contain it")
    if output.exists():
        raise ValueError("output already exists; choose a new immutable run directory")


def run(recordings: Path, output: Path, config: Config) -> dict:
    output_safe(recordings, output)
    # Hash ALL original recording files, including auxiliary files, before/after.
    source_hashes = {str(p.relative_to(recordings)): sha256(p)
                     for p in sorted(recordings.rglob("*")) if p.is_file()}
    paths = sorted(recordings.glob("*/*.meta.json"))
    if not paths:
        raise ValueError("no recording metadata found")
    takes = []
    for path in paths:
        meta = json.loads(path.read_text())
        if str(meta.get("activity_label", "")).startswith("fall_"):
            takes.append(load_take(path, recordings, config))
    if len({t.recording_id for t in takes}) != len(takes):
        raise ValueError("duplicate recording IDs")
    complete = [t for t in takes if all((t.meta.get("annotations") or {}).get(k) for k in BOUNDARIES)]
    complete_ids = {t.recording_id for t in complete}
    targets = [t for t in takes if t.recording_id not in complete_ids]
    cache, rows = {}, []
    print(f"Loaded {len(paths)} metadata records; FALL={len(takes)}, complete={len(complete)}, targets={len(targets)}", flush=True)
    for number, take in enumerate(complete, 1):
        for task in ("missing_both", "impact_only"):
            # Mask target truth BEFORE prediction, including donor eligibility.
            masked = copy.copy(take)
            masked.annotation = {"fall_start": take.annotation.get("fall_start") if task == "impact_only" else None,
                                 "fall_impact": None}
            masked.meta = copy.deepcopy(take.meta)
            masked.meta["annotations"] = {
                "fall_start": (take.meta.get("annotations") or {}).get("fall_start") if task == "impact_only" else None,
                "fall_impact": None, "annotation_complete": False,
            }
            for protocol in PROTOCOLS:
                for method in METHODS:
                    result = propose(masked, takes, method, protocol, masked.annotation["fall_start"], config, cache)
                    rows.append(validation_row(take, method, protocol, task, result))
        if number % 10 == 0 or number == len(complete):
            print(f"Masked annotation validation {number}/{len(complete)}", flush=True)
    proposals = []
    for take in targets:
        known_start = take.annotation.get("fall_start")
        methods = {method: propose(take, takes, method, "profile_preferred", known_start, config, cache)
                   for method in METHODS}
        primary = methods["dtw"]  # Fixed before outcomes, never picked by validation score.
        boundaries = {}
        for key in BOUNDARIES:
            original = (take.meta.get("annotations") or {}).get(key)
            if original is not None:
                boundaries[key] = {"source": "MANUAL_ORIGINAL", "original": copy.deepcopy(original),
                                   "status": "PRESERVED", "verified_physical_truth": False}
            else:
                value = (primary.get("prediction") or {}).get(key)
                boundaries[key] = {"source": "AUTOMATIC_ALIGNMENT", "offset_s": value,
                                   "status": primary["status"], "verified_physical_truth": False,
                                   "uncertainty": "donor range is disagreement, not a calibrated confidence interval"}
        proposals.append({
            "schema_version": 1, "recording_id": take.recording_id, "activity": take.label,
            "subject_id": take.meta.get("subject_id"), "session_id": take.meta.get("session_id"),
            "acquisition_profile": take.meta.get("acquisition_profile"), "stimulus_family": take.profile,
            "source_hashes": take.hashes, "original_annotations": copy.deepcopy(take.meta.get("annotations")),
            "scope": "DEVELOPMENT_ONLY_NOT_FOR_TRAINING_OR_GROUND_TRUTH", "training_eligible": False,
            "status": primary["status"], "manual_review_required": True,
            "boundaries": boundaries, "quality": take.quality, "blockers": take.blockers,
            "methods": methods, "primary_method": "dtw",
        })
    after_hashes = {str(p.relative_to(recordings)): sha256(p)
                    for p in sorted(recordings.rglob("*")) if p.is_file()}
    if source_hashes != after_hashes:
        raise RuntimeError("source files changed during study; no output published")
    summaries = summarize_validation(rows)
    result = {
        "status": "COMPLETE_DEVELOPMENT_STUDY", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": asdict(config), "config_status": "FIXED_UNTUNED_RESEARCH_PARAMETERS_NOT_SAFETY_LIMITS",
        "source_recordings": len(paths), "fall_takes": len(takes), "complete_observer_takes": len(complete),
        "incomplete_targets": len(targets), "target_statuses": dict(Counter(p["status"] for p in proposals)),
        "validation_rows": len(rows), "validation": summaries,
        "source_files_checked": len(source_hashes), "source_hashes_unchanged": True,
        "packages": {"python": platform.python_version(), "numpy": np.__version__},
        "code_hashes": {name: sha256(ROOT / "fall_detection" / name) for name in (
            "automatic_annotations.py", "dataset_io.py", "train_activity_model.py", "validate_recording.py")},
        "limitations": [
            "No detector splits/manifests/training or calibrated confidence model.",
            "Leave-one-target-out observer agreement is not independent physical truth.",
            "Observer-mark integrity/support is audited before masking; invalid references abstain and remain in denominators.",
            "Stimulus family is only a coarse donor heuristic; complete acquisition profiles are unavailable.",
            "Raw subject/session metadata is unverified; source overlap checks do not prove person independence.",
            "Other-day validation also changes HTTP/TCP family in this snapshot.",
            "November4 has no complete observer references; its annotation error cannot be measured directly.",
            "All outputs remain quarantined; regenerate with approved training-fold donors before future model use.",
            "Signal standardization/smoothing is offline full-take annotation assistance, not causal inference.",
            "Host batching and observer reaction delay are not independently bounded.",
            "No numeric label acceptance tolerance was approved; AUTO_PROPOSED does not mean reliable/accepted.",
        ],
    }
    output.mkdir(parents=True)
    (output / "proposals").mkdir()
    write_json(output / "summary.json", result)
    write_json(output / "source_hashes.json", source_hashes)
    write_json(output / "input_audit.json", [{"recording_id": t.recording_id, "hashes": t.hashes,
        "quality": t.quality, "blockers": t.blockers, "complete_annotation": t.complete_annotation}
        for t in takes])
    with (output / "validation.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["recording_id"])
        writer.writeheader()
        writer.writerows(rows)
    for proposal in proposals:
        write_json(output / "proposals" / f"{proposal['recording_id']}.auto.json", proposal)
    write_json(output / "proposal_index.json", [{"recording_id": p["recording_id"], "status": p["status"],
        "boundaries": p["boundaries"], "path": f"proposals/{p['recording_id']}.auto.json"} for p in proposals])
    print(json.dumps({k: result[k] for k in ("source_recordings", "complete_observer_takes", "incomplete_targets",
                                            "target_statuses", "validation_rows", "source_hashes_unchanged")}, indent=2), flush=True)
    print(f"Output: {output}", flush=True)
    for row in summaries:
        if row["profile"] == "ALL":
            print(json.dumps(row), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recordings", type=Path, default=ROOT / "examples/esp-radar/wifi_sensing_demo/recordings")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.recordings.resolve(), args.output.resolve(), Config())


if __name__ == "__main__":
    main()
