"""Consumer-facing invariants for the Visualizer export."""

import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ANALYZER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYZER_ROOT))
from visualizer_export import export_analysis, json_value, table, validate_export


class SerializationTests(unittest.TestCase):
    def test_missing_values_are_null_and_zero_is_preserved(self):
        value = json_value({"missing": [float("nan"), pd.NA, float("inf")], "zero": 0, "flag": False})
        self.assertEqual(value, {"missing": [None, None, None], "zero": 0, "flag": False})
        json.dumps(value, allow_nan=False)

    def test_table_preserves_identity_index_and_nested_values(self):
        frame = pd.DataFrame({"versions": [["1", "2"]], "ratio": [math.nan]}, index=pd.Index(["org/repo"], name="repository"))
        exported = table(frame, "Repository")
        self.assertEqual(exported["rows"], [{"repository": "org/repo", "versions": ["1", "2"], "ratio": None}])
        self.assertEqual(exported["row_count"], 1)

    def test_failed_export_keeps_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            output.write_text("previous export", encoding="utf-8")
            with patch("visualizer_export.build_export", side_effect=ValueError("bad input")):
                with self.assertRaises(ValueError):
                    export_analysis({}, Path("notebook.ipynb"), output)
            self.assertEqual(output.read_text(encoding="utf-8"), "previous export")


class PublishedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ANALYZER_ROOT / "outputs/django/clone-x269596i/analysis.json").read_text(encoding="utf-8"))

    def test_all_questions_have_consistent_tables_and_observations(self):
        validate_export(self.payload)
        self.assertEqual(len(self.payload["questions"]), 10)

    def test_ci_without_analysis_is_not_exported_as_zero_findings(self):
        ci = self.payload["questions"][9]
        self.assertEqual(ci["status"], "insufficient_evidence")
        self.assertTrue(all(row["hallazgos_ci_observados"] is None for row in ci["tables"]["cobertura_ci"]["rows"]))

    def test_export_contains_relationship_and_concentration_not_just_counts(self):
        correlation = self.payload["questions"][4]
        self.assertEqual(correlation["metrics"]["sample_size"], 19)
        self.assertAlmostEqual(correlation["metrics"]["rho_spearman"], 0.5134471310049109)
        self.assertIsNone(correlation["metrics"]["p_value"])
        self.assertIn("proporcion", self.payload["questions"][0]["tables"]["concentracion"]["columns"])
        self.assertTrue(correlation["observations"][0]["evidence_tables"])

    def test_evidence_hashes_match_available_inputs(self):
        root = ANALYZER_ROOT.parent
        for record in self.payload["provenance"]["evidence"]:
            if record["available"]:
                self.assertEqual(hashlib.sha256((root / record["path"]).read_bytes()).hexdigest(), record["sha256"])

    def test_consumer_rejects_broken_observation_reference(self):
        invalid = copy.deepcopy(self.payload)
        invalid["questions"][0]["observations"][0]["evidence_tables"] = ["missing_table"]
        with self.assertRaises(ValueError):
            validate_export(invalid)


if __name__ == "__main__":
    unittest.main()
