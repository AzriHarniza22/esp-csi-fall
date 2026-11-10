#!/usr/bin/env python3
"""Unit tests for the Fase 2.3 candidate-annotation tool (host, no device).

Covers the two guarantees ACTION_PLAN 2.3 / DATA_CONTRACT §4 make:
  * timeline parameters are read per take (never a silent 4.0 fallback), and
  * the derived p95 candidate marks + ``pre_action_candidate`` behave correctly.

These exercise the pure math over synthetic motion series and the timeline
extractor; no recordings or CSI decoder are required.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import annotate_candidates as ac  # noqa: E402


def action_series(pre_end=4.0, spike=(5.0, 7.0), base=0.1, peak=5.0, tail=0.05,
                  span=12.0, dt=0.02, noise=0.02, seed=1):
    rng = np.random.default_rng(seed)
    offs = np.arange(0.0, span, dt)
    motions = base + rng.normal(0.0, noise, offs.size)
    lo, hi = spike
    motions[(offs >= lo) & (offs < hi)] = peak
    motions[offs >= hi] = tail
    return offs, motions


class ExtractTimelineParamsTests(unittest.TestCase):
    def test_action_timeline_reads_own_boundaries(self):
        meta = {"timeline": [
            {"phase": "pre_action", "start_offset_s": 0, "end_offset_s": 4},
            {"phase": "fall_action", "start_offset_s": 4, "end_offset_s": 8},
            {"phase": "post_action", "start_offset_s": 8, "end_offset_s": 12},
        ]}
        p = ac.extract_timeline_params(meta)
        self.assertEqual(p["kind"], "action")
        self.assertEqual((p["pre_end"], p["action_start"], p["action_end"], p["take_end"]),
                         (4.0, 4.0, 8.0, 12.0))

    def test_single_phase_is_hold(self):
        meta = {"timeline": [{"phase": "hold", "start_offset_s": 0, "end_offset_s": 10}]}
        p = ac.extract_timeline_params(meta)
        self.assertEqual(p["kind"], "hold")
        self.assertEqual(p["take_end"], 10.0)

    def test_missing_timeline_fails_fast_no_fallback(self):
        with self.assertRaises(ac.TimelineError):
            ac.extract_timeline_params({}, ctx="t")

    def test_empty_timeline_fails_fast(self):
        with self.assertRaises(ac.TimelineError):
            ac.extract_timeline_params({"timeline": []}, ctx="t")

    def test_two_phase_timeline_is_rejected(self):
        meta = {"timeline": [{"end_offset_s": 4}, {"end_offset_s": 8}]}
        with self.assertRaises(ac.TimelineError):
            ac.extract_timeline_params(meta, ctx="t")

    def test_non_numeric_boundary_fails_fast(self):
        meta = {"timeline": [
            {"end_offset_s": None}, {"start_offset_s": 4, "end_offset_s": 8},
            {"end_offset_s": 12},
        ]}
        with self.assertRaises(ac.TimelineError):
            ac.extract_timeline_params(meta, ctx="t")


class ComputeActionCandidateTests(unittest.TestCase):
    def params(self, **over):
        p = {"kind": "action", "pre_end": 4.0, "action_start": 4.0,
             "action_end": 8.0, "take_end": 12.0}
        p.update(over)
        return p

    def test_clean_fall_onset_after_action_start(self):
        offs, motions = action_series(spike=(5.0, 7.0))
        block = ac.compute_action_candidate(offs, motions, self.params())
        self.assertEqual(block["kind"], "action")
        self.assertEqual(block["annotation_status"], "auto_pending")
        self.assertIsNotNone(block["candidate_onset_s"])
        self.assertGreaterEqual(block["candidate_onset_s"], 4.0)
        self.assertLess(block["candidate_onset_s"], block["candidate_peak_s"])
        self.assertIsNotNone(block["candidate_settle_s"])
        self.assertGreater(block["candidate_settle_s"], block["candidate_peak_s"])
        self.assertFalse(block["pre_action_candidate"])
        self.assertFalse(block["needs_manual_review"])

    def test_candidate_before_action_start_is_flagged(self):
        # Spike rises at 4.2 but action_start is declared at 5.0 -> pre-action.
        offs, motions = action_series(spike=(4.2, 7.0))
        block = ac.compute_action_candidate(offs, motions, self.params(action_start=5.0))
        self.assertIsNotNone(block["candidate_onset_s"])
        self.assertLess(block["candidate_onset_s"], 5.0)
        self.assertTrue(block["pre_action_candidate"])
        self.assertTrue(block["needs_manual_review"])

    def test_no_crossing_needs_review(self):
        rng = np.random.default_rng(2)
        offs = np.arange(0.0, 12.0, 0.02)
        motions = 0.1 + rng.normal(0.0, 0.02, offs.size)
        block = ac.compute_action_candidate(offs, motions, self.params())
        self.assertIsNone(block["candidate_onset_s"])
        self.assertTrue(block["needs_manual_review"])
        self.assertIn("no onset crossing", " ".join(block["notes"]))

    def test_never_settled_needs_review(self):
        # Motion jumps and stays high until take end -> no settle point.
        offs, motions = action_series(spike=(5.0, 12.0), tail=5.0)
        motions[offs >= 5.0] = 5.0
        block = ac.compute_action_candidate(offs, motions, self.params())
        self.assertIsNotNone(block["candidate_onset_s"])
        self.assertIsNone(block["candidate_settle_s"])
        self.assertTrue(block["needs_manual_review"])

    def test_algorithm_identity_fields_present(self):
        offs, motions = action_series()
        block = ac.compute_action_candidate(offs, motions, self.params())
        self.assertEqual(block["annotation_method"], "csi_envelope_p95")
        self.assertEqual(block["annotation_algorithm_version"], "1.0")
        self.assertEqual(block["annotation_parameters"],
                         {"grid_hz": 20, "smooth_n": 20, "search_offset": -0.5})

    def test_no_pre_action_frames_needs_review(self):
        offs = np.arange(4.5, 12.0, 0.02)  # nothing before pre_end
        motions = np.full(offs.shape, 1.0)
        block = ac.compute_action_candidate(offs, motions, self.params())
        self.assertTrue(block["needs_manual_review"])
        self.assertIn("no pre-action frames", " ".join(block["notes"]))


class ComputeHoldCandidateTests(unittest.TestCase):
    def test_hold_reports_stability_not_onset(self):
        offs = np.arange(0.0, 10.0, 0.02)
        rng = np.random.default_rng(0)
        motions = 0.1 + rng.normal(0, 0.01, offs.size)
        block = ac.compute_hold_candidate(offs, motions, {"kind": "hold", "take_end": 10.0})
        self.assertEqual(block["kind"], "hold")
        self.assertIsNone(block["candidate_onset_s"])
        self.assertFalse(block["needs_manual_review"])
        self.assertIn("spearman_rho", block["stability"])
        self.assertIn("late_over_early_p95", block["stability"])


if __name__ == "__main__":
    unittest.main()
