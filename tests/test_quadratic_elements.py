"""C3D10 formulation invariants; separate native solver smoke test runs in CI."""
import math
import tempfile
import unittest
from pathlib import Path

from ezfea.core import Analysis
from ezfea.mesh import Mesh, distributed_quadratic_force_weights, gmsh_to_calculix_tet10
from ezfea.solver import write_input, nodal_force_components


class QuadraticElementTests(unittest.TestCase):
    def test_gmsh_to_calculix_last_two_midside_edges(self):
        self.assertEqual(gmsh_to_calculix_tet10(tuple(range(1,11))),
                         (1,2,3,4,5,6,7,8,10,9))
        with self.assertRaises(ValueError):
            gmsh_to_calculix_tet10(tuple(range(4)))

    def test_t6_consistent_traction(self):
        nodes={1:(0,0,0),2:(2,0,0),3:(0,2,0),
               4:(1,0,0),5:(1,1,0),6:(0,1,0)}
        weights,area=distributed_quadratic_force_weights(
            [(1,2,3,4,5,6)],nodes)
        self.assertAlmostEqual(area,2.)
        self.assertEqual(set(weights),{4,5,6})
        self.assertAlmostEqual(sum(weights.values()),1.)
        for midside in (4,5,6):
            self.assertAlmostEqual(weights[midside],1/3)

    def test_actual_calculix_input_specifies_ten_nodes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            cad=root/"part.step"
            cad.write_text("unit fake STEP")
            case=Analysis(str(cad),1,2,(0,0,-90),10,element_type="C3D10")
            # Use a physically three-dimensional reference tetrahedron:
            # an all-collinear synthetic fixture must fail the support check.
            nodes={1:(0.,0.,0.),2:(1.,0.,0.),3:(0.,1.,0.),4:(0.,0.,1.),
                   5:(.5,0.,0.),6:(.5,.5,0.),7:(0.,.5,0.),
                   8:(0.,0.,.5),9:(.5,0.,.5),10:(0.,.5,.5)}
            mesh=Mesh(nodes,{99:tuple(range(1,11))},
                      [1,2,3,4],{8:1/3,9:1/3,10:1/3},2.,
                      element_type="C3D10")
            dest=write_input(case,mesh,root/"analysis.inp")
            deck=dest.read_text()
            self.assertIn("*ELEMENT, TYPE=C3D10, ELSET=PART",deck)
            self.assertIn("99, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10",deck)
            self.assertIn("8, 3, -30",deck)
            self.assertEqual(sum(v for (n,a),v in nodal_force_components(case,mesh).items()
                                 if a==3),-90)
            with self.assertRaisesRegex(ValueError,"differs"):
                write_input(Analysis(str(cad),1,2,(0,0,-90),10),
                            mesh,root/"wrong.inp")

    def test_invalid_element_option_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"part.step"
            file.write_text("test")
            with self.assertRaisesRegex(ValueError,"Element type"):
                Analysis(str(file),1,2,(0,0,-50),10,element_type="C3D8").validate()


if __name__=="__main__":
    unittest.main()
