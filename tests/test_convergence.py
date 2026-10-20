"""Mesh refinement math and provenance without replacing actual solver tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ezfea.convergence import relative_change, run_refinement
from ezfea.core import Analysis


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.step = self.root / "part.step"
        self.step.write_text("placeholder STEP bytes")
        self.case = Analysis(str(self.step), 1, 2, (0, -100, 0), 12)

    def fake_runner(self, displacements, stresses=None, elements=None):
        calls = []
        stresses = stresses or [10, 12, 13]
        elements = elements or [30, 60, 120]
        def execute(case, folder):
            position = len(calls)
            target = Path(folder) / "actual_solve"
            target.mkdir(parents=True, exist_ok=False)
            import hashlib
            digest = hashlib.sha256(self.step.read_bytes()).hexdigest()
            record = {
                "status": "completed",
                "input_sha256": digest,
                "mesh": {"nodes": elements[position], "elements": elements[position]},
                "results": {
                    "max_displacement_mm": displacements[position],
                    "max_von_mises_mpa": stresses[position],
                    "force_balance_relative_error": 0.001
                },
            }
            (target / "case.json").write_text(json.dumps(record))
            calls.append(case.mesh_size_mm)
            return target
        return execute, calls

    def test_three_grids_and_last_two_changes(self):
        fake, calls = self.fake_runner([1.02, 1.01, 1.005])
        with patch("ezfea.convergence.run_case", side_effect=fake):
            result = run_refinement(self.case, self.root / "runs", sizes_mm=[12,8,5])
        self.assertEqual(calls, [12.,8.,5.])
        self.assertEqual(result["displacement_observation"], "stable_at_checked_mesh_sizes")
        self.assertEqual(result["engineering_validation"], "not_established")
        self.assertEqual(len(result["records"]), 3)
        self.assertEqual(len(result["adjacent_mesh_changes"]), 2)
        self.assertTrue((self.root / "runs/refinement.json").exists())

    def test_nonstabilized_or_nonmonotonic_mesh_marked_for_refinement(self):
        for displacements, counts in [([1.4, 1.1, 0.8], [30, 60, 120]),
                                      ([1.02, 1.01, 1.005], [30, 30, 120])]:
            with self.subTest(displacements=displacements, elements=counts):
                fake, _ = self.fake_runner(displacements, elements=counts)
                with patch("ezfea.convergence.run_case", side_effect=fake):
                    result = run_refinement(self.case, self.root / f"check_{counts[1]}_{displacements[0]}")
                self.assertEqual(result["displacement_observation"], "refinement_not_yet_stable")

    def test_bad_input_rejected_before_solver(self):
        for sizes in ([5, 8, 12], [12, 12, 5], [12, 5],
                      [12, float("nan"), 5], [12, 0, 5]):
            with self.subTest(sizes=sizes):
                with self.assertRaises(ValueError):
                    run_refinement(self.case, self.root / "bad", sizes_mm=sizes)
        with self.assertRaises(ValueError):
            run_refinement(self.case, self.root / "bad", displacement_tolerance=-1)

    def test_source_changes_between_grids_are_rejected(self):
        fake, _ = self.fake_runner([1.02, 1.01, 1.005])
        def changed_source(case, root):
            out = fake(case, root)
            self.step.write_text("different STEP during analysis")
            return out
        with patch("ezfea.convergence.run_case", side_effect=changed_source):
            with self.assertRaises(RuntimeError):
                run_refinement(self.case, self.root / "changed")

    def test_relative_change(self):
        self.assertAlmostEqual(relative_change(1., 1.1), 0.1 / 1.1)
        self.assertEqual(relative_change(0., 0.), 0.)
        with self.assertRaises(ValueError):
            relative_change(float("nan"), 1.)


if __name__ == "__main__":
    unittest.main()
