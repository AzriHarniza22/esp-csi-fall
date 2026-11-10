#!/usr/bin/env python3
"""Fase 2.3 — timeline-driven signal-derived candidate annotation (host-side).

This is the canonical home of the candidate-annotation algorithm referenced by
``ACTION_PLAN.md`` Fase 2.3 and ``docs/DATA_CONTRACT.md`` §4. It is a faithful
port of the methodology in the research scripts ``08_label_durations.py`` (the
canon — timeline-driven) and the ``load_series`` / ``smooth_on_grid`` helpers of
``07_settle_times.py``, generalized so that EVERY take reads its own phase
boundaries from ``meta.timeline``:

    pre_end      = timeline[0].end_offset_s
    action_start = timeline[1].start_offset_s
    action_end   = timeline[1].end_offset_s
    take_end     = timeline[2].end_offset_s

The script 07 constants (``PRE_END=4.0``, onset search ``t >= 3.5``) are valid
only for the fall protocol and are deliberately NOT reused here. A take whose
meta carries no usable timeline is a **failed-fast** error — the tool refuses to
silently fall back to 4.0 (DATA_CONTRACT §4.3).

Output is a *derived* annotation (``candidate_onset/peak/settle`` + status +
parameters). Raw frames and observer marks (``annotations.fall_start`` /
``fall_impact``) are NEVER touched. ``annotation_status`` produced here is
always ``auto_pending``; promotion to ``signal_reviewed`` / ``manual_corrected``
belongs to the human review panel (ACTION_PLAN Fase 2.5), not to this tool.

Read-only by default (preview). Writing the derived block into ``*.meta.json``
is opt-in via ``--write`` and is a dataset mutation gated behind explicit user
approval.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

# --- Canonical algorithm identity (DATA_CONTRACT §4.2) ----------------------
ALGORITHM_VERSION = "1.0"
ANNOTATION_METHOD = "csi_envelope_p95"
GRID_HZ = 20            # linear-interp grid rate for the motion envelope
SMOOTH_N = 20           # centred moving-average length (= 1.0 s at GRID_HZ)
SEARCH_OFFSET = -0.5    # onset search starts at pre_end + SEARCH_OFFSET (= pre_end - 0.5)
ANNOTATION_PARAMETERS = {
    "grid_hz": GRID_HZ,
    "smooth_n": SMOOTH_N,
    "search_offset": SEARCH_OFFSET,
}

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RECORDINGS = (
    REPOSITORY_ROOT / "examples/esp-radar/wifi_sensing_demo/recordings"
)

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


class TimelineError(ValueError):
    """Raised when a take's meta lacks a usable timeline (failed-fast, §4.3)."""


# ---------------------------------------------------------------------------
# Motion series (ported verbatim from scripts/07_settle_times.py)
# ---------------------------------------------------------------------------
def _dataset_io():
    """Lazily import the repo's CSI decoder so importing this module never
    hard-fails when ``fall_detection`` is not on the path (e.g. unit tests that
    feed synthetic series directly)."""
    from fall_detection.dataset_io import amplitude, decode_iq  # noqa: WPS433
    return amplitude, decode_iq


def load_series(rec_dir: Path, rec_id: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (offsets_s, per_frame_motion) for one take.

    Identical construction to the canon scripts: decode ``valid_b64`` to complex
    pairs, keep the first ``lltf_len // 2`` subcarrier amplitudes, and define
    motion as ``mean(|amp[k] - amp[k-1]|)`` (0.0 for the first frame). The time
    base is ``host_receive_monotonic_ns`` relative to the first frame — the
    canonical axis of DATA_CONTRACT §2.
    """
    amplitude, decode_iq = _dataset_io()
    offs: list[float] = []
    motions: list[float] = []
    with (rec_dir / f"{rec_id}.frames.csv").open(encoding="utf-8", newline="") as h:
        prev = None
        t0 = None
        for row in csv.DictReader(h):
            payload = base64.b64decode(row["valid_b64"])
            n = int(row["lltf_len"]) // 2
            amps = np.asarray(
                amplitude(decode_iq(payload, int(row["data_type"]))[:n]), dtype=float
            )
            ns = int(row["host_receive_monotonic_ns"])
            if t0 is None:
                t0 = ns
            offs.append(ns / 1e9 - t0 / 1e9)
            motions.append(0.0 if prev is None else float(np.mean(np.abs(amps - prev))))
            prev = amps
    return np.asarray(offs, dtype=float), np.asarray(motions, dtype=float)


def smooth_on_grid(offs: np.ndarray, motions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate per-frame motion onto a GRID_HZ grid, then apply a centred
    moving average of SMOOTH_N samples (edge values held, not zero-padded)."""
    if offs.size == 0:
        return np.array([]), np.array([])
    span = float(offs[-1])
    grid = np.arange(0.0, span, 1.0 / GRID_HZ)
    if grid.size == 0:
        return grid, np.array([])
    m = np.interp(grid, offs, motions)
    if m.size < SMOOTH_N:
        return grid, m
    kernel = np.ones(SMOOTH_N) / SMOOTH_N
    sm = np.convolve(m, kernel, mode="same")
    valid = sm[SMOOTH_N // 2: -SMOOTH_N // 2]
    sm[:SMOOTH_N // 2] = valid[0]
    sm[-SMOOTH_N // 2:] = valid[-1]
    return grid, sm


# ---------------------------------------------------------------------------
# Timeline parameter extraction (failed-fast, §4.3)
# ---------------------------------------------------------------------------
def _boundary(entry: dict, key: str, ctx: str) -> float:
    value = entry.get(key) if isinstance(entry, dict) else None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        raise TimelineError(f"{ctx}: timeline entry missing numeric '{key}' ({value!r})")
    if not np.isfinite(seconds):
        raise TimelineError(f"{ctx}: timeline '{key}' is not finite ({value!r})")
    return seconds


def extract_timeline_params(meta: dict, ctx: str = "take") -> dict[str, Any]:
    """Derive per-take phase boundaries from ``meta.timeline``.

    Returns a dict with ``kind`` in {``"action"``, ``"hold"``}. Action takes
    carry ``pre_end``/``action_start``/``action_end``/``take_end``; hold takes
    (single-phase idle anchors) carry only ``take_end``.

    Raises :class:`TimelineError` when the timeline is missing, empty, or has an
    unexpected number of phases — the caller must NOT substitute a default.
    """
    tl = meta.get("timeline")
    if not isinstance(tl, list) or not tl:
        raise TimelineError(
            f"{ctx}: meta.timeline is missing or empty; refusing to fall back to a "
            "default pre_end (DATA_CONTRACT §4.3 failed-fast)"
        )
    if len(tl) == 1:
        take_end = _boundary(tl[0], "end_offset_s", ctx)
        return {"kind": "hold", "take_end": take_end}
    if len(tl) != 3:
        raise TimelineError(
            f"{ctx}: expected a 1-phase (hold) or 3-phase (action) timeline, "
            f"got {len(tl)} phases"
        )
    return {
        "kind": "action",
        "pre_end": _boundary(tl[0], "end_offset_s", ctx),
        "action_start": _boundary(tl[1], "start_offset_s", ctx),
        "action_end": _boundary(tl[1], "end_offset_s", ctx),
        "take_end": _boundary(tl[2], "end_offset_s", ctx),
    }


# ---------------------------------------------------------------------------
# Candidate computation (pure math over a motion series)
# ---------------------------------------------------------------------------
def _base_block(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "annotation_method": ANNOTATION_METHOD,
        "annotation_algorithm_version": ALGORITHM_VERSION,
        "annotation_parameters": dict(ANNOTATION_PARAMETERS),
        "annotation_status": "auto_pending",
        "candidate_onset_s": None,
        "candidate_peak_s": None,
        "candidate_settle_s": None,
        "needs_manual_review": False,
        "pre_action_candidate": False,
        "timeline_parameters": {
            k: v for k, v in params.items() if k != "kind"
        },
        "notes": [],
    }


def compute_hold_candidate(
    offs: np.ndarray, motions: np.ndarray, params: dict[str, Any]
) -> dict[str, Any]:
    """Idle/hold anchors have no action to segment; report envelope stability
    (Spearman rho of smoothed motion vs time, and late/early p95 ratio) instead
    of a candidate onset (canon scripts/08 idle branch)."""
    block = _base_block(params)
    block["kind"] = "hold"
    grid, sm = smooth_on_grid(offs, motions)
    if grid.size == 0:
        block["notes"].append("no frames")
        return block
    end = float(grid[-1])
    early = sm[grid < end / 2]
    late = sm[grid >= end / 2]
    rho, p = spearmanr(grid, sm)
    early_p95 = float(np.percentile(early, 95)) if early.size else 0.0
    late_p95 = float(np.percentile(late, 95)) if late.size else 0.0
    block["stability"] = {
        "spearman_rho": round(float(rho), 3),
        "rho_p": round(float(p), 4),
        "late_over_early_p95": round(late_p95 / max(1e-9, early_p95), 2),
    }
    return block


def compute_action_candidate(
    offs: np.ndarray, motions: np.ndarray, params: dict[str, Any]
) -> dict[str, Any]:
    """Locate candidate onset / peak / settle for an action take, thresholded at
    the p95 of its own pre-action motion and searched from ``pre_end - 0.5``."""
    block = _base_block(params)
    block["kind"] = "action"
    grid, sm = smooth_on_grid(offs, motions)
    pre = motions[offs < params["pre_end"]]
    if grid.size == 0:
        block["notes"].append("no frames")
        block["needs_manual_review"] = True
        return block
    if pre.size == 0:
        block["notes"].append("no pre-action frames to build baseline threshold")
        block["needs_manual_review"] = True
        return block

    thresh = float(np.percentile(pre, 95))
    block["threshold"] = round(thresh, 6)

    search_start = params["pre_end"] + SEARCH_OFFSET
    onset_i = next(
        (i for i, t in enumerate(grid) if t >= search_start and sm[i] > thresh), None
    )
    if onset_i is None:
        block["notes"].append("no onset crossing")
        block["needs_manual_review"] = True
        return block

    peak_i = onset_i + int(np.argmax(sm[onset_i:]))
    settled_i = next(
        (i for i in range(peak_i, grid.size) if np.all(sm[i:] < thresh)), None
    )

    onset_s = round(float(grid[onset_i]), 3)
    block["candidate_onset_s"] = onset_s
    block["candidate_peak_s"] = round(float(grid[peak_i]), 3)
    block["candidate_settle_s"] = (
        round(float(grid[settled_i]), 3) if settled_i is not None else None
    )

    if onset_s < params["action_start"]:
        block["pre_action_candidate"] = True
        block["notes"].append(
            "candidate onset precedes action_start; not treated as fall onset "
            "automatically (DATA_CONTRACT §4.4)"
        )
    if settled_i is None:
        block["notes"].append("motion never returned below threshold before take end")
    block["needs_manual_review"] = bool(
        block["pre_action_candidate"] or settled_i is None
    )
    return block


def compute_candidate(
    offs: np.ndarray, motions: np.ndarray, params: dict[str, Any]
) -> dict[str, Any]:
    if params["kind"] == "hold":
        return compute_hold_candidate(offs, motions, params)
    return compute_action_candidate(offs, motions, params)


# ---------------------------------------------------------------------------
# Per-take / dataset drivers
# ---------------------------------------------------------------------------
def annotate_meta_path(meta_path: Path) -> dict[str, Any]:
    """Annotate a single take identified by its ``*.meta.json`` path."""
    rec_id = meta_path.name[: -len(".meta.json")]
    meta = json.loads(meta_path.read_text())
    label = meta.get("activity_label")
    ctx = rec_id
    try:
        params = extract_timeline_params(meta, ctx=ctx)
    except TimelineError as exc:
        return {
            "recording_id": rec_id,
            "activity_label": label,
            "kind": "error",
            "candidate_annotation": {
                "annotation_method": ANNOTATION_METHOD,
                "annotation_algorithm_version": ALGORITHM_VERSION,
                "annotation_status": "failed_fast_no_timeline",
                "needs_manual_review": True,
                "error": str(exc),
            },
        }
    offs, motions = load_series(meta_path.parent, rec_id)
    return {
        "recording_id": rec_id,
        "activity_label": label,
        "kind": params["kind"],
        "candidate_annotation": compute_candidate(offs, motions, params),
    }


def iter_meta_paths(recordings_dir: Path) -> list[Path]:
    return sorted(recordings_dir.rglob("*.meta.json"))


def annotate_recordings(
    recordings_dir: Path,
    labels: set[str] | None = None,
    rec_id_contains: str | None = None,
) -> list[dict[str, Any]]:
    if not recordings_dir.is_dir():
        raise FileNotFoundError(f"recordings directory does not exist: {recordings_dir}")
    results: list[dict[str, Any]] = []
    for meta_path in iter_meta_paths(recordings_dir):
        meta_label = None
        if labels or rec_id_contains:
            rec_id = meta_path.name[: -len(".meta.json")]
            if rec_id_contains and rec_id_contains not in rec_id:
                continue
            if labels:
                meta_label = json.loads(meta_path.read_text()).get("activity_label")
                if meta_label not in labels:
                    continue
        results.append(annotate_meta_path(meta_path))
    return results


def apply_candidate_to_meta(meta_path: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    """Attach the derived block under the new top-level ``candidate_annotation``
    key. Existing raw fields — including ``annotations`` (observer marks) — are
    left byte-for-byte intact."""
    meta = json.loads(meta_path.read_text())
    meta["candidate_annotation"] = candidate
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta


# ---------------------------------------------------------------------------
# Optional plotting (kept out of the core path so matplotlib is not required)
# ---------------------------------------------------------------------------
def plot_candidate(result: dict[str, Any], rec_dir: Path, out_dir: Path) -> Path | None:
    rec_id = result["recording_id"]
    candidate = result.get("candidate_annotation", {})
    if candidate.get("annotation_status") == "failed_fast_no_timeline":
        return None
    offs, motions = load_series(rec_dir, rec_id)
    params = {"kind": result["kind"]}
    params.update(candidate.get("timeline_parameters", {}))
    grid, sm = smooth_on_grid(offs, motions)
    if grid.size == 0:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    thresh = candidate.get("threshold")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(offs, motions, color="lightgray", lw=0.8, label="per-frame motion")
    ax.plot(grid, sm, color="#1a56c4", lw=1.2, label="smoothed envelope")
    if thresh:
        ax.axhline(thresh, color="black", ls="--", lw=1, label="pre-action p95")
    for key, color in (
        ("candidate_onset_s", "#d63d2e"),
        ("candidate_peak_s", "#e08a00"),
        ("candidate_settle_s", "#2e8b57"),
    ):
        value = candidate.get(key)
        if value is not None:
            ax.axvline(value, color=color, ls=":", lw=1, label=key.rstrip("_s"))
    ax.set_xlabel("t since take start (s)")
    ax.set_ylabel("motion")
    ax.set_title(f"{rec_id}  [{result.get('activity_label')}]")
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{rec_id}.candidate.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Cross-class characterization (ACTION_PLAN Fase 2.4) — aggregation only,
# still read-only: it never mutates the dataset, it summarizes candidate output.
# ---------------------------------------------------------------------------
def _median(xs: list[float]) -> float | None:
    return round(float(np.median(xs)), 3) if xs else None


def characterize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize candidate segmentation per activity label.

    For action takes this reports (i) how many candidates are emitted, (ii) the
    onset deviation against the class's own ``action_start`` boundary, and the
    settle/tail distribution. For hold (idle) takes it reports the envelope
    stability medians. This is the reproducible backing for the Fase 2.4
    "karakterisasi segmentasi kandidat gerakan CSI lintas kelas" write-up.
    """
    by_label: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_label.setdefault(str(r.get("activity_label")), []).append(r)

    summary: dict[str, Any] = {}
    for label, rows in sorted(by_label.items()):
        kinds = {r["kind"] for r in rows}
        entry: dict[str, Any] = {"n_takes": len(rows)}
        failed = sum(
            1 for r in rows
            if r["candidate_annotation"].get("annotation_status") == "failed_fast_no_timeline"
        )
        if failed:
            entry["failed_fast"] = failed
        if kinds == {"hold"}:
            rhos = [r["candidate_annotation"].get("stability", {}).get("spearman_rho")
                    for r in rows]
            ratios = [r["candidate_annotation"].get("stability", {}).get("late_over_early_p95")
                      for r in rows]
            entry["kind"] = "hold"
            entry["spearman_rho_median"] = _median([x for x in rhos if x is not None])
            entry["late_over_early_p95_median"] = _median([x for x in ratios if x is not None])
            summary[label] = entry
            continue

        blocks = [r["candidate_annotation"] for r in rows]
        onsets = [b["candidate_onset_s"] for b in blocks if b.get("candidate_onset_s") is not None]
        settles = [b["candidate_settle_s"] for b in blocks if b.get("candidate_settle_s") is not None]
        entry["kind"] = "action"
        entry["candidates_emitted"] = len(onsets)
        entry["no_onset"] = len(blocks) - len(onsets)
        entry["needs_manual_review"] = sum(1 for b in blocks if b.get("needs_manual_review"))
        entry["pre_action_candidate"] = sum(1 for b in blocks if b.get("pre_action_candidate"))
        entry["onset_s_median"] = _median(onsets)
        entry["onset_s_range"] = [min(onsets), max(onsets)] if onsets else None
        # deviation of onset from each take's own action_start boundary
        devs = [
            b["candidate_onset_s"] - b["timeline_parameters"]["action_start"]
            for b in blocks
            if b.get("candidate_onset_s") is not None
            and b.get("timeline_parameters", {}).get("action_start") is not None
        ]
        entry["onset_minus_action_start_median"] = _median(devs)
        entry["onset_before_action_start"] = sum(1 for d in devs if d < 0)
        entry["settle_s_median"] = _median(settles)
        entry["settle_s_max"] = round(max(settles), 3) if settles else None
        tails = [
            b["timeline_parameters"]["take_end"] - b["candidate_settle_s"]
            for b in blocks
            if b.get("candidate_settle_s") is not None
            and b.get("timeline_parameters", {}).get("take_end") is not None
        ]
        entry["tail_s_median"] = _median(tails)
        entry["tail_s_min"] = round(min(tails), 3) if tails else None
        summary[label] = entry
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _summary_lines(results: list[dict[str, Any]]) -> list[str]:
    lines = []
    for r in results:
        c = r["candidate_annotation"]
        if c.get("annotation_status") == "failed_fast_no_timeline":
            lines.append(f"{r['recording_id'][-28:]:28s} {str(r['activity_label']):14s} FAILED-FAST: {c['error']}")
            continue
        lines.append(
            f"{r['recording_id'][-28:]:28s} {str(r['activity_label']):14s} kind={r['kind']:5s} "
            f"onset={c.get('candidate_onset_s')} peak={c.get('candidate_peak_s')} "
            f"settle={c.get('candidate_settle_s')} pre_action={c.get('pre_action_candidate')} "
            f"review={c.get('needs_manual_review')}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "recordings_dir", nargs="?", type=Path, default=DEFAULT_RECORDINGS,
        help=f"recordings root (default: {DEFAULT_RECORDINGS})",
    )
    parser.add_argument("--label", action="append", default=None,
                        help="restrict to this activity_label (repeatable)")
    parser.add_argument("--rec-id", default=None,
                        help="substring filter on recording_id")
    parser.add_argument("--out", type=Path, default=None,
                        help="write full JSON results to this path")
    parser.add_argument("--write", action="store_true",
                        help="MUTATE dataset: attach candidate_annotation into each "
                             "*.meta.json (dataset-touching; requires user approval)")
    parser.add_argument("--plot", type=Path, default=None,
                        help="also render per-take candidate curves into this directory")
    parser.add_argument("--characterize", action="store_true",
                        help="print the cross-class characterization summary (Fase 2.4)")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero if any take failed-fast on a missing timeline")
    args = parser.parse_args(argv)

    labels = set(args.label) if args.label else None
    results = annotate_recordings(args.recordings_dir, labels=labels,
                                  rec_id_contains=args.rec_id)

    if args.write:
        print("WARNING: --write mutates *.meta.json (dataset-touching).", file=sys.stderr)
        for meta_path in iter_meta_paths(args.recordings_dir):
            rec_id = meta_path.name[: -len(".meta.json")]
            by_id = {r["recording_id"]: r for r in results}
            r = by_id.get(rec_id)
            if r is None or r["candidate_annotation"].get("annotation_status") == "failed_fast_no_timeline":
                continue
            apply_candidate_to_meta(meta_path, r["candidate_annotation"])

    if args.plot:
        for meta_path in iter_meta_paths(args.recordings_dir):
            rec_id = meta_path.name[: -len(".meta.json")]
            by_id = {r["recording_id"]: r for r in results}
            r = by_id.get(rec_id)
            if r is not None:
                plot_candidate(r, meta_path.parent, args.plot)

    print("\n".join(_summary_lines(results)))
    characterization = characterize(results) if args.characterize else None
    if args.out:
        payload = {"algorithm_version": ALGORITHM_VERSION, "method": ANNOTATION_METHOD,
                   "parameters": ANNOTATION_PARAMETERS, "results": results}
        if characterization is not None:
            payload["characterization"] = characterization
        args.out.write_text(json.dumps(payload, indent=1))
        print(f"\nwrote {args.out}")
    if characterization is not None:
        print("\n=== CHARACTERIZATION (Fase 2.4) ===")
        print(json.dumps(characterization, indent=1))

    failed = sum(
        1 for r in results
        if r["candidate_annotation"].get("annotation_status") == "failed_fast_no_timeline"
    )
    print(f"\n{len(results)} takes annotated; {failed} failed-fast (no timeline).")
    if args.strict and failed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
