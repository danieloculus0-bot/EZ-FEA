"""Native DSLOAD pressure must use real tetra faces and conserve the wrench."""
import math
import tempfile
import unittest
from pathlib import Path

from ezfea.core import Analysis
from ezfea.mesh import Mesh
from ezfea.native_pressure import exterior_face_mapping,native_pressure_surface,write_native_pressure_input


def one_tet(kind):
    nodes={1:(0.,0.,0.),2:(10.,0.,0.),3:(0.,10.,0.),4:(0.,0.,10.)}
    if kind=="C3D10":
        nodes.update({5:(5.,0.,0.),6:(5.,5.,0.),7:(0.,5.,0.),
                      8:(0.,0.,5.),9:(5.,0.,5.),10:(0.,5.,5.)})
    conn=tuple(range(1,11 if kind=="C3D10" else 5))
    tri=(1,2,3,5,6,7) if kind=="C3D10" else (1,2,3)
    return Mesh(nodes,{22:conn},[2,3,4],{1:1/3,2:1/3,3:1/3},50.,
                constraint_nodes={1:[2,3,4]},
                load_weights_by_face={2:{1:1/3,2:1/3,3:1/3}},
                load_areas_by_face={2:50.},
                element_type=kind,
                surface_triangles_by_face={2:[tri]})


class NativePressureTests(unittest.TestCase):
    def test_accurate_element_face_mapping(self):
        for k in ("C3D4","C3D10"):
            with self.subTest(kind=k):
                m=one_tet(k)
                a=exterior_face_mapping(m,2)
                self.assertEqual([(el,side) for el,side,_ in a],[(22,1)])

    def test_pressure_load_is_inward_and_has_predictable_torque(self):
        for kind in ("C3D4","C3D10"):
            a=native_pressure_surface(one_tet(kind),2,2.)
            self.assertAlmostEqual(a["integrated_area_mm2"],50.,places=8)
            self.assertAlmostEqual(a["total_force_n"][2],100.,places=7)
            self.assertAlmostEqual(a["total_force_n"][0],0.,places=7)
            # Triangle centroid x=y=10/3; r x F has torque about X,Y.
            self.assertAlmostEqual(a["moment_about_origin_nmm"][0],(10/3)*100,places=6)
            self.assertAlmostEqual(a["moment_about_origin_nmm"][1],-(10/3)*100,places=6)

    def test_writes_dsload_and_rejects_legacy_cload(self):
        with tempfile.TemporaryDirectory() as tmp:
            step=Path(tmp)/"sample.step"
            step.write_text("dummy")
            mesh=one_tet("C3D4")
            case=Analysis(str(step),1,2,(0,0,100),8.)
            p=Path(tmp)/"analysis.inp"
            audit=write_native_pressure_input(case,mesh,p,2,2.)
            inp=p.read_text()
            self.assertIn("*SURFACE, NAME=EZPRES, TYPE=ELEMENT",inp)
            self.assertIn("22, S1",inp)
            self.assertIn("*DSLOAD\nEZPRES, P, 2",inp)
            self.assertNotIn("*CLOAD",inp)
            self.assertEqual(audit["pressure_mpa"],2.)

    def test_interior_faces_and_unknown_cad_faces_fail(self):
        m=one_tet("C3D4")
        with self.assertRaisesRegex(ValueError,"No explicit"):
            native_pressure_surface(m,900,1)
        with self.assertRaisesRegex(ValueError,"positive"):
            native_pressure_surface(m,2,-1)
        m.elements[99]=(1,2,3,4)
        with self.assertRaisesRegex(ValueError,"exterior"):
            native_pressure_surface(m,2,1)


if __name__=="__main__":
    unittest.main()
