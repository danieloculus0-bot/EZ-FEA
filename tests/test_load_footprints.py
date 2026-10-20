"""Finite traction footprints must preserve both applied force and moment."""
import math
import tempfile
import unittest
from pathlib import Path

from ezfea.core import Analysis, FaceConstraint, FaceFootprintLoad, FaceLoad
from ezfea.load_footprints import gaussian_face_force_weights, resultant_force_moment
from ezfea.mesh import Mesh
from ezfea.solver import assemble_surface_loads, write_input


def planar_patch_nodes():
    nodes={
      1:(0.,0.,0.),2:(0.,10.,0.),3:(0.,10.,10.),4:(0.,0.,10.),
      5:(0.,5.,0.),6:(0.,10.,5.),7:(0.,5.,5.),
      8:(0.,5.,10.),9:(0.,0.,5.),
    }
    t3=[(1,2,3),(1,3,4)]
    t6=[(1,2,3,5,6,7),(1,3,4,7,8,9)]
    return nodes,t3,t6


class LoadFootprintMathTests(unittest.TestCase):
    def test_symmetric_center_moment_on_linear_and_quadratic_triangles(self):
        nodes,t3,t6=planar_patch_nodes()
        for triangles in (t3,t6):
            with self.subTest(order=len(triangles[0])):
                rec=gaussian_face_force_weights(triangles,nodes,(0,5,5),2.5)
                self.assertAlmostEqual(sum(rec["weights"].values()),1.,places=9)
                cx,cy,cz=rec["resultant_center_mm"]
                self.assertAlmostEqual(cx,0.,places=10)
                self.assertAlmostEqual(cy,5.,places=8)
                self.assertAlmostEqual(cz,5.,places=8)
                nodal={(node,1):100.*share for node,share in rec["weights"].items()}
                wrench=resultant_force_moment(nodal,nodes)
                self.assertAlmostEqual(wrench["force_n"][0],100.,places=8)
                self.assertAlmostEqual(wrench["moment_about_origin_nmm"][1],500.,places=7)
                self.assertAlmostEqual(wrench["moment_about_origin_nmm"][2],-500.,places=7)

    def test_eccentric_footprint_changes_real_moment_not_net_force(self):
        nodes,t3,t6=planar_patch_nodes()
        for tris in (t3,t6):
            baseline=gaussian_face_force_weights(tris,nodes,(0,5,5),2)
            eccentric=gaussian_face_force_weights(tris,nodes,(0,5,7.5),2)
            self.assertGreater(eccentric["resultant_center_mm"][2],
                               baseline["resultant_center_mm"][2]+.3)
            self.assertAlmostEqual(sum(eccentric["weights"].values()),1.)
            self.assertGreater(eccentric["weighted_footprint_area_mm2"],0.)
            self.assertLess(eccentric["weighted_footprint_area_mm2"],
                            eccentric["actual_face_area_mm2"])

    def test_reject_invalid_or_missed_footprints(self):
        nodes,t3,_=planar_patch_nodes()
        with self.assertRaisesRegex(ValueError,"misses"):
            gaussian_face_force_weights(t3,nodes,(0,1000,0),1)
        with self.assertRaisesRegex(ValueError,"positive"):
            gaussian_face_force_weights(t3,nodes,(0,5,5),-1)
        with self.assertRaisesRegex(ValueError,"finite"):
            FaceFootprintLoad(2,(100,0,0),(float("nan"),5,5),2).validate()
        with self.assertRaisesRegex(ValueError,"positive"):
            FaceFootprintLoad(2,(100,0,0),(0,5,5),0).validate()

    def test_solver_deck_contains_real_consistent_patch_cload(self):
        nodes,tris,t6=planar_patch_nodes()
        nodes.update({
            10:(-10,0,0),11:(-10,10,0),12:(-10,10,10),13:(-10,0,10),
        })
        with tempfile.TemporaryDirectory() as tmp:
            step=Path(tmp)/"fake.step"
            step.write_text("dummy")
            loaded=FaceFootprintLoad(2,(100.,0.,0.),(0.,5.,7.5),2.)
            case=Analysis(str(step),0,0,(0,0,0),5.,
                          connections=(FaceConstraint(1),),
                          loads=(loaded,))
            # C3D4 connectivity deliberately minimal; load-face mesh
            # contains real triangles independent of the volume fixture.
            mesh=Mesh(nodes,{20:(1,2,3,10)},[10,11,12,13],
                      {1:1.},100.,
                      constraint_nodes={1:[10,11,12,13]},
                      load_weights_by_face={2:{1:1/3,2:1/3,3:1/3}},
                      load_areas_by_face={2:100.},
                      surface_triangles_by_face={2:tris})
            assembled,evidence=assemble_surface_loads(case,mesh)
            self.assertEqual(evidence[0]["mode"],"gaussian_face_traction")
            self.assertTrue(evidence[0]["moment_balance_passed"])
            self.assertAlmostEqual(sum(v for (n,axis),v in assembled.items()
                                       if axis==1),100.,places=9)
            inp=write_input(case,mesh,Path(tmp)/"analysis.inp")
            self.assertIn("*CLOAD",inp.read_text())
            self.assertNotIn("FaceFootprintLoad",inp.read_text())


if __name__=="__main__":
    unittest.main()
