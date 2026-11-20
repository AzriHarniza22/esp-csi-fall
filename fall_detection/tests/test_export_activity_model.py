from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from fall_detection.export_activity_model import (
    DEFAULT_ARTIFACT,
    export,
    validate_artifact,
)


class ExportActivityModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact = json.loads(DEFAULT_ARTIFACT.read_text(encoding="utf-8"))

    def test_approved_artifact_exports_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            header = Path(temporary) / "activity_model_data.h"
            source = Path(temporary) / "activity_model_data.c"
            export(DEFAULT_ARTIFACT, header, source, check=False)
            export(DEFAULT_ARTIFACT, header, source, check=True)

    def test_rejects_wrong_class_order(self) -> None:
        altered = copy.deepcopy(self.artifact)
        altered["model"]["class_order"] = ["non_fall", "fall"]
        with self.assertRaisesRegex(ValueError, "class order"):
            validate_artifact(altered)

    def test_rejects_wrong_feature_width(self) -> None:
        altered = copy.deepcopy(self.artifact)
        altered["model"]["weights"][0].pop()
        with self.assertRaisesRegex(ValueError, "weights\\[0\\]"):
            validate_artifact(altered)

    def test_rejects_wrong_subcarrier_layout(self) -> None:
        altered = copy.deepcopy(self.artifact)
        altered["provenance"]["preprocessing"]["subcarrier_width"] = 52
        with self.assertRaisesRegex(ValueError, "subcarrier width"):
            validate_artifact(altered)


if __name__ == "__main__":
    unittest.main()
