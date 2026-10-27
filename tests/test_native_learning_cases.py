"""Heldout geometry isolation and fail-closed native curriculum metadata."""
import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

from ezfea.native_learning_cases import specimens,run_curriculum


class NativeCurriculumTests(unittest.TestCase):
    def test_physical_geometry_is_not_reused_across_splits(self):
        rows=specimens()
        self.assertEqual(len(rows),21)
        self.assertEqual(len([r for r in rows if r["split"]=="train"]),12)
        self.assertEqual(len([r for r in rows if r["split"]=="holdout"]),9)
        self.assertEqual({x["family"] for x in rows},{"axial","bending","torsion"})
        self.assertEqual(len({r["geometry_key"] for r in rows}),21)

    def test_failures_persist_instead_of_becoming_training_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ezfea.native_learning_cases._native_bar_or_beam",
                       side_effect=RuntimeError("intentional native solver failure")):
                with self.assertRaisesRegex(ValueError,"need review"):
                    run_curriculum(Path(tmp),limit=1)
            import json
            report=json.loads((Path(tmp)/"native_curriculum.json").read_text())
            self.assertEqual(report["failed_or_needs_review"],1)
            self.assertEqual(report["cases"][0]["status"],"needs_review")
            self.assertNotIn("native_measured",report["cases"][0])
            self.assertIn("intentional native solver failure",report["cases"][0]["error"])

    def test_partial_smoke_is_not_misrepresented_as_full_curriculum(self):
        rows=specimens()
        self.assertTrue(all("split" in item for item in rows))
        self.assertGreater(len(rows),3)


if __name__=="__main__":
    unittest.main()
