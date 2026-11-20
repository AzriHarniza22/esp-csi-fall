"""Synthetic correctness and non-destructive execution tests; no classifier fits."""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np

from fall_detection import automatic_annotations as aa


def take(rid, *, profile="http", day="2026-11-07", complete=True):
    grid = np.arange(100) / 10
    rng = np.random.default_rng(17)
    signal = rng.normal(size=(100, 8))
    annotation = {"fall_start": 4.0 if complete else None,
                  "fall_impact": 5.0 if complete else None}
    raw = {k: {"offset_s": v, "timestamp_utc": f"{day}T00:00:0{int(v)}Z"}
           if v is not None else None for k, v in annotation.items()}
    meta = {"recording_id": rid, "activity_label": "fall_backward",
            "started_at_utc": f"{day}T00:00:00Z", "actual_duration_s": 10.0,
            "subject_id": None, "session_id": None, "stimulus": {"mode": profile},
            "wifi": {"channel": 1}, "annotations": raw}
    return aa.Take(rid, meta, {"meta": rid, "frames": rid}, annotation,
                   grid=grid, signal=signal, lineage=frozenset([rid]), payload_hash=rid)


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.config = aa.Config()
        self.times = np.arange(101) / 20
        self.amplitude = 20 + np.sin(self.times[:, None] * np.linspace(1, 4, 51))

    def test_duplicate_coalescing_is_explicit_and_does_not_modify_input(self):
        times = np.repeat(self.times, 2)
        amplitude = np.repeat(self.amplitude, 2, axis=0)
        saved = amplitude.copy()
        grid, signal, quality = aa.prepare_signal(times, amplitude, self.config)
        original_grid, original_signal, _ = aa.prepare_signal(self.times, self.amplitude, self.config)
        np.testing.assert_array_equal(amplitude, saved)
        np.testing.assert_array_equal(grid, original_grid)
        np.testing.assert_allclose(signal, original_signal)
        self.assertEqual(quality["coalesced_host_duplicates"], len(self.times))
        self.assertGreaterEqual(grid[0], times[0])
        self.assertLessEqual(grid[-1], times[-1])
        self.assertIsNone(quality["clock_uncertainty_s"])

    def test_reversed_timestamps_rejected(self):
        times = self.times.copy()
        times[40] = times[38]
        with self.assertRaisesRegex(ValueError, "reversed"):
            aa.prepare_signal(times, self.amplitude, self.config)

    def test_gap_is_not_interpolated(self):
        times = self.times.copy()
        times[40:] += 1
        with self.assertRaisesRegex(ValueError, "not interpolated"):
            aa.prepare_signal(times, self.amplitude, self.config)

    def test_flat_signal_rejected(self):
        with self.assertRaisesRegex(ValueError, "flat"):
            aa.prepare_signal(self.times, np.ones_like(self.amplitude), self.config)

    def test_nonfinite_signal_rejected(self):
        self.amplitude[10, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            aa.prepare_signal(self.times, self.amplitude, self.config)

    def test_layout_and_short_support_rejected(self):
        with self.assertRaisesRegex(ValueError, "51-pair"):
            aa.prepare_signal(self.times, self.amplitude[:, :50], self.config)
        with self.assertRaisesRegex(ValueError, "insufficient"):
            aa.prepare_signal(self.times[:10], self.amplitude[:10], self.config)

    def test_manual_clock_conflict_is_not_repaired(self):
        target = take("target")
        self.assertEqual(aa.manual_offsets(target.meta, self.config), target.annotation)
        target.meta["annotations"]["fall_impact"]["offset_s"] = 6.0
        with self.assertRaisesRegex(ValueError, "offset/UTC conflict"):
            aa.manual_offsets(target.meta, self.config)


class AlignmentTests(unittest.TestCase):
    def setUp(self):
        self.config = aa.Config()
        self.donor = take("donor")
        self.target = take("target", complete=False)

    def test_ncc_positive_and_negative_lag(self):
        for lag in (-8, 8):
            with self.subTest(lag=lag):
                self.target.signal = np.roll(self.donor.signal, lag, axis=0)
                result = aa.align_pair(self.target, self.donor, "ncc", None, self.config)
                self.assertAlmostEqual(result["components"]["lag_s"], lag / 10)
                self.assertAlmostEqual(result["components"]["correlation"], 1)
                self.assertAlmostEqual(result["mapped"]["fall_start"], 4 + lag / 10)
                self.assertAlmostEqual(result["mapped"]["fall_impact"], 5 + lag / 10)

    def test_ncc_grid_origins_are_part_of_physical_lag(self):
        self.target.grid = self.target.grid + 0.2
        result = aa.align_pair(self.target, self.donor, "ncc", None, self.config)
        self.assertAlmostEqual(result["mapped"]["fall_start"], 4.2)

    def test_no_donor_boundary_extrapolation(self):
        self.target.signal = np.roll(self.donor.signal, 8, axis=0)
        self.donor.annotation["fall_impact"] = 9.8
        with self.assertRaisesRegex(ValueError, "outside alignment support"):
            aa.align_pair(self.target, self.donor, "ncc", None, self.config)
        with self.assertRaisesRegex(ValueError, "outside alignment support"):
            aa.map_boundary([(0, 0), (1, 1)], self.target.grid, self.donor.grid, 4)

    def test_identity_dtw_path(self):
        result = aa.align_pair(self.target, self.donor, "dtw", None, self.config)
        self.assertEqual(result["path"], [(i, i) for i in range(100)])
        self.assertEqual(result["mapped"], self.donor.annotation)
        self.assertEqual(result["cost"], 0)

    def test_variable_speed_and_unequal_length_dtw(self):
        indices = np.concatenate((np.arange(30), np.repeat(np.arange(30, 50), 2), np.arange(50, 100)))
        self.target.signal = self.donor.signal[indices]
        self.target.grid = np.arange(len(indices)) / 10
        result = aa.align_pair(self.target, self.donor, "dtw", None, self.config)
        self.assertAlmostEqual(result["mapped"]["fall_start"], 5.05)
        self.assertAlmostEqual(result["mapped"]["fall_impact"], 7.0)
        path = np.asarray(result["path"])
        self.assertEqual(tuple(path[0]), (0, 0))
        self.assertEqual(tuple(path[-1]), (119, 99))
        self.assertEqual(set(path[:, 0]), set(range(120)))
        self.assertEqual(set(path[:, 1]), set(range(100)))
        delta = np.diff(path, axis=0)
        self.assertTrue(np.all((delta >= 0) & (delta <= 1)))
        self.assertTrue(np.all(delta.sum(axis=1) >= 1))
        self.assertLessEqual(result["components"]["max_abs_time_warp_s"], self.config.max_warp_s)

    def test_unreachable_time_band_and_slope_rejected(self):
        with self.assertRaisesRegex(ValueError, "no bounded DTW path"):
            aa.dtw_path(self.target.grid + 10, self.target.signal,
                        self.donor.grid, self.donor.signal, self.config)
        with self.assertRaisesRegex(ValueError, "no bounded DTW path"):
            aa.dtw_path(np.arange(30) / 10, self.target.signal[:30],
                        np.arange(5) / 10, self.donor.signal[:5], self.config)

    def test_partial_manual_start_preserved_exactly(self):
        for method in aa.METHODS:
            result = aa.align_pair(self.target, self.donor, method, 4.029, self.config)
            self.assertEqual(result["mapped"]["fall_start"], 4.029)
            self.assertGreater(result["mapped"]["fall_impact"], 4.029)

    def test_hidden_target_marks_do_not_change_prediction(self):
        donors = [take(f"donor{i}") for i in range(3)]
        for method in aa.METHODS:
            first = aa.propose(self.target, donors, method, "profile_preferred", None, self.config, {})
            self.target.meta["annotations"] = {"fall_start": {"offset_s": -999},
                                               "fall_impact": {"offset_s": 999}}
            second = aa.propose(self.target, donors, method, "profile_preferred", None, self.config, {})
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "AUTO_PROPOSED")
            self.assertFalse(first["training_eligible"])
            self.assertIsNone(first["confidence_probability"])


class DonorTests(unittest.TestCase):
    def test_unknown_identities_remain_eligible_but_same_source_is_excluded(self):
        target = take("target")
        eligible = take("unknown_identity")
        overlap = take("overlap")
        overlap.lineage = target.lineage
        duplicate = take("duplicate")
        duplicate.payload_hash = target.payload_hash
        packet = take("packet")
        target.packet_keys = packet.packet_keys = frozenset([("mac", 1, 1, "hash")])
        wrong_channel = take("channel")
        wrong_channel.meta["wifi"]["channel"] = 11
        donors = aa.donor_pool(target, [target, eligible, overlap, duplicate, packet, wrong_channel], "profile_preferred")
        self.assertEqual([d.recording_id for d in donors], [eligible.recording_id])
        self.assertIsNone(eligible.meta["subject_id"])
        self.assertIsNone(eligible.meta["session_id"])

    def test_other_day_excludes_same_day(self):
        target = take("target")
        other = take("other", day="2026-11-19")
        donors = aa.donor_pool(target, [take("same"), other], "other_day")
        self.assertEqual([d.recording_id for d in donors], ["other"])

    def test_consensus_cannot_count_duplicate_donors(self):
        target = take("target", complete=False)
        donors = [take(f"donor{i}") for i in range(3)]
        donors[0].payload_hash = donors[1].payload_hash
        result = aa.propose(target, donors, "dtw", "profile_preferred", None, aa.Config(), {})
        self.assertEqual(result["status"], "ABSTAINED")
        self.assertIn("source_disjoint", result["reason"])

    def test_profile_preference_and_cross_profile_fallback(self):
        target = take("target", complete=False)
        donors = [take(f"donor{i}") for i in range(3)] + [take("tcp", profile="tcp")]
        result = aa.propose(target, donors, "ncc", "profile_preferred", None, aa.Config(), {})
        self.assertTrue(result["same_profile_preference"])
        self.assertEqual(result["cross_profile_donors"], 0)
        donors.pop(0)
        result = aa.propose(target, donors, "ncc", "profile_preferred", None, aa.Config(), {})
        self.assertFalse(result["same_profile_preference"])
        self.assertEqual(result["cross_profile_donors"], 1)

    def test_blocked_target_and_insufficient_donors_abstain(self):
        target = take("target", complete=False)
        result = aa.propose(target, [], "ncc", "profile_preferred", None, aa.Config(), {})
        self.assertEqual(result["status"], "ABSTAINED")
        target.blockers = ["invalid source"]
        result = aa.propose(target, [], "dtw", "profile_preferred", None, aa.Config(), {})
        self.assertEqual(result["reason"], "invalid source")


class ExecutionTests(unittest.TestCase):
    def test_output_tree_and_existing_directory_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recordings = root / "recordings"
            recordings.mkdir()
            for output in (root, recordings, recordings / "nested"):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    aa.output_safe(recordings, output)
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"):
                aa.output_safe(recordings, existing)
            aa.output_safe(recordings, root / "new")

    def test_run_preserves_files_and_manual_mark_and_masks_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recordings = root / "recordings"
            folder = recordings / "fall_backward"
            folder.mkdir(parents=True)
            takes = [take(f"donor{i}") for i in range(4)]
            partial = take("partial", complete=False)
            original = {"offset_s": 4.029, "timestamp_utc": "2026-11-07T00:00:04.029Z"}
            partial.meta["annotations"]["fall_start"] = original
            partial.annotation["fall_start"] = 4.029
            takes.append(partial)
            for item in takes:
                (folder / f"{item.recording_id}.meta.json").write_text(json.dumps(item.meta))
            (recordings / "auxiliary.bin").write_bytes(b"must remain unchanged")
            before = {p: p.read_bytes() for p in recordings.rglob("*") if p.is_file()}
            by_id = {t.recording_id: t for t in takes}
            original_propose = aa.propose
            calls = []

            def checked(target, *args):
                calls.append(target.recording_id)
                self.assertIsNone(target.annotation["fall_impact"])
                self.assertIsNone(target.meta["annotations"]["fall_impact"])
                return original_propose(target, *args)

            output = root / "output"
            with patch.object(aa, "load_take", side_effect=lambda p, *_: by_id[p.name.removesuffix(".meta.json")]), \
                    patch.object(aa, "propose", side_effect=checked), redirect_stdout(io.StringIO()):
                summary = aa.run(recordings, output, aa.Config())
            self.assertEqual(before, {p: p.read_bytes() for p in recordings.rglob("*") if p.is_file()})
            self.assertEqual(summary["validation_rows"], 32)
            self.assertEqual(summary["target_statuses"], {"AUTO_PROPOSED": 1})
            self.assertEqual(len(calls), 34)
            proposal = json.loads((output / "proposals/partial.auto.json").read_text())
            self.assertEqual(proposal["boundaries"]["fall_start"]["original"], original)
            self.assertFalse(proposal["training_eligible"])
            self.assertTrue(proposal["manual_review_required"])
            self.assertEqual(proposal["methods"]["dtw"]["prediction"]["fall_start"], 4.029)
            with (output / "validation.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 32)
            self.assertTrue(all(r["recording_id"] not in r["donor_ids"].split("|") for r in rows))
            self.assertTrue(all(r["fall_start_error_s"] == "" for r in rows if r["task"] == "impact_only"))

    def test_empty_input_does_not_publish_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "no recording metadata"):
                aa.run(root / "missing", root / "output", aa.Config())
            self.assertFalse((root / "output").exists())


@unittest.skipUnless(os.environ.get("ANNOTATION_STUDY_OUTPUT"), "saved-study verification is opt-in")
class SavedStudyTests(unittest.TestCase):
    def test_published_provenance_boundaries_metrics_and_source_immutability(self):
        output = Path(os.environ["ANNOTATION_STUDY_OUTPUT"])
        recordings = aa.ROOT / "examples/esp-radar/wifi_sensing_demo/recordings"
        summary = json.loads((output / "summary.json").read_text())
        source_hashes = json.loads((output / "source_hashes.json").read_text())
        self.assertEqual(source_hashes, {str(p.relative_to(recordings)): aa.sha256(p)
                                      for p in recordings.rglob("*") if p.is_file()})
        for name, digest in summary["code_hashes"].items():
            self.assertEqual(aa.sha256(aa.ROOT / "fall_detection" / name), digest)
        metadata = {p.name.removesuffix(".meta.json"): json.loads(p.read_text())
                    for p in recordings.glob("*/*.meta.json")}
        self.assertEqual(len(metadata), summary["source_recordings"])
        index = json.loads((output / "proposal_index.json").read_text())
        self.assertEqual(len(index), summary["incomplete_targets"])
        proposed = 0
        for entry in index:
            proposal = json.loads((output / entry["path"]).read_text())
            original = metadata[entry["recording_id"]]
            self.assertEqual(proposal["original_annotations"], original.get("annotations"))
            self.assertEqual(proposal["subject_id"], original.get("subject_id"))
            self.assertEqual(proposal["session_id"], original.get("session_id"))
            self.assertFalse(proposal["training_eligible"])
            self.assertTrue(proposal["manual_review_required"])
            self.assertIn("DEVELOPMENT_ONLY", proposal["scope"])
            for boundary, value in proposal["boundaries"].items():
                self.assertFalse(value["verified_physical_truth"])
                mark = (original.get("annotations") or {}).get(boundary)
                if mark is not None:
                    self.assertEqual(value["original"], mark)
                    self.assertEqual(value["status"], "PRESERVED")
                else:
                    self.assertEqual(value["status"], proposal["status"])
            for method, result in proposal["methods"].items():
                self.assertIsNone(result["confidence_probability"])
                self.assertEqual(result["confidence_status"], "UNCALIBRATED")
                if result["status"] != "AUTO_PROPOSED":
                    self.assertIsNone(result["prediction"])
                    continue
                prediction = result["prediction"]
                self.assertLess(prediction["fall_start"], prediction["fall_impact"])
                donors = result["selected_donors"]
                self.assertEqual(len({d["donor_id"] for d in donors}), summary["config"]["donor_count"])
                for donor in donors:
                    self.assertNotEqual(donor["donor_id"], proposal["recording_id"])
                    donor_meta = metadata[donor["donor_id"]]
                    self.assertEqual(donor_meta["activity_label"], original["activity_label"])
                    for suffix, key in (("meta.json", "meta"), ("frames.csv", "frames")):
                        relative = f"{donor_meta['activity_label']}/{donor['donor_id']}.{suffix}"
                        self.assertEqual(donor["donor_hashes"][key], source_hashes[relative])
                    axes = donor["path_axes"]
                    tx = axes["target_start_s"] + np.arange(axes["target_samples"]) * axes["grid_step_s"]
                    ty = axes["donor_start_s"] + np.arange(axes["donor_samples"]) * axes["grid_step_s"]
                    for boundary in aa.BOUNDARIES:
                        mark = (original.get("annotations") or {}).get(boundary)
                        expected = mark["offset_s"] if mark else aa.map_boundary(
                            donor["path"], tx, ty, donor_meta["annotations"][boundary]["offset_s"])
                        self.assertAlmostEqual(donor["mapped"][boundary], expected)
                for boundary in aa.BOUNDARIES:
                    self.assertAlmostEqual(prediction[boundary], np.median([d["mapped"][boundary] for d in donors]))
            proposed += proposal["status"] == "AUTO_PROPOSED"
        self.assertEqual(proposed, summary["target_statuses"].get("AUTO_PROPOSED", 0))
        with (output / "validation.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), summary["validation_rows"])
        self.assertEqual(len(rows), summary["complete_observer_takes"] * 8)
        for row in rows:
            self.assertNotIn(row["recording_id"], row["donor_ids"].split("|"))
            if row["protocol"] == "other_day":
                self.assertTrue(all(metadata[d]["started_at_utc"][:10] != row["day"]
                                    for d in row["donor_ids"].split("|") if d))
        for group in summary["validation"]:
            if group["profile"] != "ALL":
                continue
            members = [r for r in rows if all(r[k] == group[k] for k in ("method", "protocol", "task"))]
            self.assertEqual(len(members), group["targets"])
            for boundary in aa.BOUNDARIES:
                errors = [abs(float(r[f"{boundary}_error_s"])) for r in members if r[f"{boundary}_error_s"]]
                if errors:
                    self.assertAlmostEqual(float(np.mean(errors)), group[boundary]["mae_s"])
                    self.assertAlmostEqual(float(np.quantile(errors, .95)), group[boundary]["p95_abs_error_s"])


if __name__ == "__main__":
    unittest.main()
