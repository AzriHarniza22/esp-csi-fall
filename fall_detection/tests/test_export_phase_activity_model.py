from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from fall_detection.export_phase_activity_model import (
    export,
    render_files,
    validate_artifact,
)
from fall_detection.train_phase_activity_model import (
    PhaseWindow,
    build_final_model_artifact,
    load_policy,
)

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "fall_detection/phase_label_policy.json"


class ExportPhaseActivityModelTests(unittest.TestCase):
    def setUp(self) -> None:
        policy = load_policy(POLICY_PATH)
        samples = []
        for index in range(4):
            samples.append(
                PhaseWindow(
                    f"fall-{index}",
                    f"fall-{index}",
                    "fall_forward",
                    "fall_start",
                    0,
                    23,
                    "fall",
                    (5.0 + index * 0.1,) * 16,
                )
            )
            samples.append(
                PhaseWindow(
                    f"walk-{index}",
                    f"walk-{index}",
                    "walking",
                    "walking",
                    0,
                    23,
                    "non_fall",
                    (0.1 + index * 0.01,) * 16,
                )
            )
        self.artifact = build_final_model_artifact(
            samples, policy, POLICY_PATH, "linear-svm"
        )

    def test_validates_and_renders_phase_model_identity(self) -> None:
        validate_artifact(self.artifact)
        header, source = render_files(self.artifact, "0" * 64)
        self.assertIn("linear-svm-phase-fall-start-to-impact-v1", header)
        self.assertIn("fall_start-to-fall_impact = fall", source)

    def test_rejects_oof_artifact(self) -> None:
        altered = copy.deepcopy(self.artifact)
        altered["provenance"]["uses_oof_fold_model"] = True
        with self.assertRaisesRegex(ValueError, "OOF"):
            validate_artifact(altered)

    def test_rejects_feature_order_or_scoring_mismatch(self) -> None:
        altered = copy.deepcopy(self.artifact)
        altered["provenance"]["preprocessing"]["band_assignment"] = (
            "band = floor(subcarrier_index * 16 / 52)"
        )
        with self.assertRaisesRegex(ValueError, "band_assignment"):
            validate_artifact(altered)

        altered = copy.deepcopy(self.artifact)
        altered["provenance"]["training"]["decision_rule"] = "threshold at zero"
        with self.assertRaisesRegex(ValueError, "score or decision semantics"):
            validate_artifact(altered)

    def test_exports_deterministically_to_explicit_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact_path = Path(temporary) / "model.json"
            header_path = Path(temporary) / "activity_model_data.h"
            source_path = Path(temporary) / "activity_model_data.c"
            import json

            artifact_path.write_text(
                json.dumps(self.artifact), encoding="utf-8"
            )
            export(artifact_path, header_path, source_path, check=False)
            before = (header_path.read_bytes(), source_path.read_bytes())
            export(artifact_path, header_path, source_path, check=True)
            self.assertEqual(
                before, (header_path.read_bytes(), source_path.read_bytes())
            )


if __name__ == "__main__":
    unittest.main()
