#!/usr/bin/env python3
"""Read-only feasibility probe: separate "normal walking" (label `walking`)
from "walk-then-fall" (`fall_keseleo`) using settle + shape features of the
canonical CSI motion envelope (same construction as annotate_candidates).

Two-domain question: during the ACTION window, does a fall-and-still shape
appear for keseleo but NOT for sustained walking? We deliberately confine all
features to the action window (before the protocol's post-action still) so the
protocol-mandated stop is not mistaken for a fall.

No dataset mutation. No model training. Pure separability measurement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import annotate_candidates as ac  # noqa: E402

REC = (TOOLS.parent / "recordings").resolve()


def envelope(mp: Path):
    meta = json.loads(mp.read_text())
    params = ac.extract_timeline_params(meta)
    offs, mot = ac.load_series(mp.parent, meta["recording_id"])
    grid, sm = ac.smooth_on_grid(offs, mot)
    return meta, params, offs, mot, grid, sm


def features(mp: Path, domain: str) -> dict | None:
    meta, params, offs, mot, grid, sm = envelope(mp)
    if params["kind"] != "action":
        return None
    pre_end = params["pre_end"]
    action_end = params["action_end"]
    # still baseline = the truly-still pre-action of the FALL-domain takes;
    # walking-domain pre-action is also still (Tetap diam 0-3), so both give a
    # comparable quiet floor.
    still_floor = float(np.median(mot[offs < pre_end]))
    act = sm[(grid >= pre_end) & (grid <= action_end)]
    t_act = grid[(grid >= pre_end) & (grid <= action_end)]
    if act.size < 5:
        return None
    peak_i = int(np.argmax(act))
    peak = float(act[peak_i])
    # 1) drop_after_peak: how far motion falls in the ~1.5 s AFTER the peak,
    #    relative to the peak itself. Fall -> big drop; sustained walk -> flat.
    post = act[(t_act > t_act[peak_i]) & (t_act <= t_act[peak_i] + 1.5)]
    drop_ratio = 1.0 - (float(np.mean(post)) / peak) if post.size and peak > 0 else 0.0
    # 2) still_confirm: deepest sustained low AFTER the peak within the action
    #    window, normalised by the still floor. <1 means it returns to quiet.
    aft = act[t_act > t_act[peak_i] + 0.5]
    still_confirm = (float(np.min(aft)) / max(still_floor, 1e-9)) if aft.size else 1.0
    # 3) peak_pos_frac: where the peak sits in the action window (0=start,1=end).
    #    Fall -> early/mid peak then decay; walk -> peak anywhere, no decay.
    span = max(t_act[-1] - t_act[0], 1e-9)
    peak_pos_frac = float((t_act[peak_i] - t_act[0]) / span)
    # 4) fall_shape_score: composite that needs BOTH a strong drop and a return
    #    toward still after the peak. High only for fall-then-still.
    fall_shape = drop_ratio * (1.0 / max(still_confirm, 0.3))
    return dict(
        take=mp.name.split("_")[-1].split(".")[0],
        label=meta.get("activity_label"),
        peak=round(peak, 2),
        drop_ratio=round(drop_ratio, 3),
        still_confirm=round(still_confirm, 3),
        peak_pos_frac=round(peak_pos_frac, 2),
        fall_shape=round(fall_shape, 3),
    )


def collect(folder: str, domain: str) -> list[dict]:
    out = []
    for mp in sorted((REC / folder).glob("*.meta.json")):
        f = features(mp, domain)
        if f:
            out.append(f)
    return out


def auc(pos: list[float], neg: list[float]) -> float:
    """Probability that a random pos scores above a random neg (Mann-Whitney)."""
    p, n = np.asarray(pos), np.asarray(neg)
    gt = (p[:, None] > n[None, :]).sum()
    eq = (p[:, None] == n[None, :]).sum()
    return float((gt + 0.5 * eq) / (p.size * n.size))


def main() -> int:
    kes = collect("fall_keseleo", "fall_from_walk")
    wk = collect("walking", "normal_walk")
    print(f"Domains: fall_keseleo n={len(kes)}  walking n={len(wk)}\n")

    for name, rows in (("FALL-from-walk (keseleo)", kes), ("NORMAL walk", wk)):
        print(f"== {name} ==")
        print(f"{'take':>5} {'peak':>6} {'drop':>6} {'stillC':>7} {'pkPos':>6} {'shape':>7}")
        for r in rows:
            print(f"{r['take']:>5} {r['peak']:>6} {r['drop_ratio']:>6} "
                  f"{r['still_confirm']:>7} {r['peak_pos_frac']:>6} {r['fall_shape']:>7}")
        print()

    print("== Separability (AUC, fall-domain should score higher) ==")
    for feat in ("drop_ratio", "still_confirm", "peak_pos_frac", "fall_shape"):
        k = [r[feat] for r in kes]
        w = [r[feat] for r in wk]
        a = auc(k, w)
        print(f"{feat:>14}:  AUC(fall>walk)={a:.2f}  "
              f"keseleo med={np.median(k):.2f} rng[{min(k):.2f},{max(k):.2f}]  "
              f"walk med={np.median(w):.2f} rng[{min(w):.2f},{max(w):.2f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
