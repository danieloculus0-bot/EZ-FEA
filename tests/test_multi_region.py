"""Multi-face restraint/load engine: input validation, stability and deck physics."""
import tempfile
import unittest
from pathlib import Path

from ezfea.core import Analysis, FaceConstraint, FaceLoad
from ezfea.mesh import Mesh
from ezfea.solver import _rigid_body_rank, write_input


class MultipleRegionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        (self.path / "part.step").write_text("fixture", encoding="utf-8")

    def case(self, connections=None, loads=None):
        return Analysis(str(self.path / "part.step"), 0, 0, (0, 0, 0), 2,
                        connections=tuple(connections or (FaceConstraint(1),)),
                        loads=tuple(loads or (FaceLoad(2, (0, -100, 0)),)))

    def mesh(self):
        nodes = {1:(0.,0.,0.), 2:(0.,1.,0.), 3:(0.,0.,1.),
                 4:(1.,0.,0.), 5:(1.,1.,0.), 6:(1.,0.,1.)}
        return Mesh(nodes, {1:(1,2,3,4)}, [1,2,3],
                    {4:.5,5:.5}, 2.,
                    {1:[1,2,3],3:[1,2,3]},
                    {2:{4:.5,5:.5},4:{5:.25,6:.75}},
                    {2:1.,4:1.})

    def test_multiple_loads_summed_and_tracked(self):
        case = self.case(loads=(FaceLoad(2,(0,-100,0)),FaceLoad(4,(0,0,40))))
        case.validate()
        self.assertEqual(case.total_force_n,(0,-100,40))
        self.assertAlmostEqual(case.force_scale_n,140)
        text = write_input(case,self.mesh(),self.path/"run.inp").read_text()
        self.assertIn("4, 2, -50",text)
        self.assertIn("5, 2, -50",text)
        self.assertIn("5, 3, 10",text)
        self.assertIn("6, 3, 30",text)
        self.assertEqual(text.count("*CLOAD"),1)

    def test_selected_axes_not_all_clamped(self):
        case=self.case(connections=(FaceConstraint(1,(1,2,3)),FaceConstraint(3,(2,))))
        text=write_input(case,self.mesh(),self.path/"run.inp").read_text()
        self.assertIn("FIX_1, 1, 1, 0",text)
        self.assertIn("FIX_2, 2, 2, 0",text)
        self.assertNotIn("FIX_2, 3, 3, 0",text)
        self.assertIn("*NODE PRINT, NSET=CONNECTION",text)

    def test_unstable_support_detected(self):
        case=self.case(connections=(FaceConstraint(1,(1,)),))
        with self.assertRaisesRegex(ValueError,"Underconstrained"):
            write_input(case,self.mesh(),self.path/"unstable.inp")

    def test_rank_six_for_plane_clamp(self):
        mesh=self.mesh()
        self.assertEqual(_rigid_body_rank(mesh.nodes,[([1,2,3],(1,2,3))]),6)

    def test_rank_one_for_single_axis(self):
        mesh=self.mesh()
        self.assertEqual(_rigid_body_rank(mesh.nodes,[([1,2,3],(1,))]),3)

    def test_invalid_direction_rejected(self):
        with self.assertRaisesRegex(ValueError,"axes"):
            self.case(connections=(FaceConstraint(1,(1,4)),)).validate()

    def test_duplicate_support_face_rejected(self):
        with self.assertRaisesRegex(ValueError,"only occur once"):
            self.case(connections=(FaceConstraint(1,(1,)),FaceConstraint(1,(2,)))).validate()

    def test_old_and_new_fields_not_combined(self):
        case=self.case()
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError,"zero legacy"):
            replace(case,fixed_face=1).validate()

    def test_equal_opposite_loads_preserve_nonzero_reference(self):
        case=self.case(loads=(FaceLoad(2,(0,-100,0)),FaceLoad(4,(0,100,0))))
        case.validate()
        self.assertEqual(case.total_force_n,(0,0,0))
        self.assertEqual(case.force_scale_n,200)
        deck=write_input(case,self.mesh(),self.path/"balanced.inp").read_text()
        self.assertIn("6, 2, 75",deck)


if __name__=="__main__":
    unittest.main()
