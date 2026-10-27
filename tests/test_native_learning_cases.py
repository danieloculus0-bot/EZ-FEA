"""Heldout geometry isolation and fail-closed native curriculum metadata."""
import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

from ezfea.native_learning_cases import specimens,run_curriculum,cantilever_reference_y_deflection_mm


class NativeCurriculumTests(unittest.TestCase):
    def test_physical_geometry_is_not_reused_across_splits(self):
        rows=specimens()
        self.assertEqual(len(rows),42)
        self.assertEqual(len([r for r in rows if r["split"]=="train"]),12)
        self.assertEqual(len([r for r in rows if r["split"]=="holdout"]),30)
        self.assertEqual({x["family"] for x in rows},{"axial","bending","torsion"})
        self.assertEqual(len({r["geometry_key"] for r in rows}),42)

    def test_nonsquare_beam_uses_correct_Iz_for_transverse_Y_load(self):
        # Along X, width is Y=12, height is Z=6.
        # Y deflection bends about the Z axis; I_z = 6*12^3/12=864.
        # Using I_y=12*6^3/12=216 would be a fourfold mistake.
        force,length,e=100.,100.,200000.
        expected=force*length**3/(3*e*864.)
        actual=cantilever_reference_y_deflection_mm(force,length,12.,6.,e)
        self.assertAlmostEqual(actual,expected,places=12)
        swapped=cantilever_reference_y_deflection_mm(force,length,6.,12.,e)
        self.assertAlmostEqual(swapped/actual,4.)
        self.assertAlmostEqual(
            cantilever_reference_y_deflection_mm(-force,length,12.,6.,e),
            actual)
        with self.assertRaises(ValueError):
            cantilever_reference_y_deflection_mm(force,length,0.,6.,e)

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
