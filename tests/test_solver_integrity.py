"""Regression checks for result identity and restraint integrity.

Small deterministic solver-output fixtures; native CalculiX is covered by
the separate integration workflow.
"""
import tempfile
import unittest
from pathlib import Path

from ezfea.core import Analysis
from ezfea.mesh import Mesh
from ezfea.results import summarize_dat
from ezfea.solver import write_input


_DAT = """\
 displacements (vx,vy,vz) for set ALL_NODES and time 1.0
 1 0 0 0
 2 0.01 0 0

 forces (fx,fy,fz) for set CONNECTION and time 1.0
 1 -100 0 0

 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set PART and time 1.0
 8 1 10 0 0 0 0 0
"""


class SolverIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dat = self.root / "analysis.dat"
        self.dat.write_text(_DAT, encoding="utf-8")

    def read(self):
        return summarize_dat(
            self.dat, (100, 0, 0), 250,
            expected_nodes=2,
            expected_elements=1,
            expected_node_ids={1, 2},
            expected_element_ids={8},
            expected_reaction_node_ids={1},
        )

    def test_expected_ids_are_accepted(self):
        self.assertEqual(self.read()["force_balance_check"], "pass")

    def test_wrong_displacement_ids_rejected_even_with_correct_count(self):
        self.dat.write_text(_DAT.replace(" 2 0.01 0 0", " 3 0.01 0 0"))
        with self.assertRaisesRegex(ValueError, "Displacement node IDs"):
            self.read()

    def test_wrong_element_id_rejected_even_with_correct_count(self):
        self.dat.write_text(_DAT.replace(" 8 1 10 0 0 0 0 0", " 9 1 10 0 0 0 0 0"))
        with self.assertRaisesRegex(ValueError, "Stress element IDs"):
            self.read()

    def test_wrong_reaction_node_id_rejected_even_with_correct_count(self):
        self.dat.write_text(_DAT.replace(" 1 -100 0 0", " 2 -100 0 0"))
        with self.assertRaisesRegex(ValueError, "Reaction node IDs"):
            self.read()

    def test_duplicate_displacement_rejected(self):
        self.dat.write_text(_DAT.replace(" 2 0.01 0 0", " 2 0.01 0 0\n 2 0.02 0 0"))
        with self.assertRaisesRegex(ValueError, "duplicate node records"):
            self.read()

    def test_duplicate_stress_sample_rejected(self):
        self.dat.write_text(_DAT + " 8 1 20 0 0 0 0 0\n")
        with self.assertRaisesRegex(ValueError, "duplicate element/integration"):
            self.read()

    def test_duplicate_reaction_rejected(self):
        self.dat.write_text(_DAT.replace(" 1 -100 0 0", " 1 -100 0 0\n 1 -100 0 0"))
        with self.assertRaisesRegex(ValueError, "duplicate node records"):
            self.read()

    def test_nonfinite_derived_stress_is_rejected(self):
        self.dat.write_text(_DAT.replace(" 8 1 10 0 0 0 0 0", " 8 1 1e308 0 0 0 0 0"))
        with self.assertRaisesRegex(ValueError, "Nonfinite derived"):
            self.read()

    def test_legacy_collinear_support_rejected(self):
        part = self.root / "part.step"
        part.write_text("fixture", encoding="utf-8")
        case = Analysis(str(part), 1, 2, (0, -100, 0), 2)
        nodes = {1: (0., 0., 0.), 2: (1., 0., 0.),
                 3: (2., 0., 0.), 4: (0., 1., 0.)}
        mesh = Mesh(nodes, {1: (1, 2, 3, 4)}, [1, 2, 3], {4: 1.}, 1.)
        with self.assertRaisesRegex(ValueError, "Underconstrained legacy fixture"):
            write_input(case, mesh, self.root / "bad.inp")


if __name__ == "__main__":
    unittest.main()
