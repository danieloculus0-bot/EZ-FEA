"""Probe locations are fixed XYZ and stress values come only from CalculiX .dat."""
import tempfile
import unittest
from pathlib import Path

from ezfea.mesh import Mesh
from ezfea.stress_probes import (
    RECOVERY, frame_stress_probes, recover_fixed_stress, tetra_barycentric,
)
from ezfea.frame_benchmarks import STUDIES


def source_mesh(element_type):
    corners={1:(0.,0.,0.),2:(10.,0.,0.),3:(0.,10.,0.),4:(0.,0.,10.)}
    extra={5:(5.,0.,0.),6:(5.,5.,0.),7:(0.,5.,0.),
           8:(0.,0.,5.),9:(5.,0.,5.),10:(0.,5.,5.)}
    nodes={**corners,**extra}
    conn=tuple(range(1,5 if element_type=="C3D4" else 11))
    return Mesh(nodes,{7:conn},[1,2,3],{4:1.},1.,element_type=element_type)


def dat_for(values):
    return (
        " stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set PART and time 0.1000000E+01\n"
        "\n" + "".join(
            f"      7   {i}   {v:.8E}  0.000000E+00  0.000000E+00"
            f"  0.000000E+00  0.000000E+00  0.000000E+00\n"
            for i,v in enumerate(values,1)
        )
    )


class FixedCoordinateStressTests(unittest.TestCase):
    def test_exact_barycentric_inside_and_outside(self):
        verts=[(0.,0.,0.),(10.,0.,0.),(0.,10.,0.),(0.,0.,10.)]
        a=tetra_barycentric((2.,3.,1.),verts)
        self.assertAlmostEqual(sum(a),1.)
        self.assertTrue(all(x>0 for x in a))
        b=tetra_barycentric((20.,3.,1.),verts)
        self.assertTrue(any(x<0 for x in b))

    def run_probe(self,kind,values,xyz=(2.1,2.2,1.5)):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"analysis.dat"
            file.write_text(dat_for(values),encoding="utf-8")
            return recover_fixed_stress(file,source_mesh(kind),{"target":xyz})

    def test_linear_tetra_uses_real_single_gauss_tensor(self):
        obs=self.run_probe("C3D4",[32.])
        item=obs["probes"]["target"]
        self.assertAlmostEqual(item["von_mises_mpa"],32.)
        self.assertEqual(item["coordinate_mm"],[2.1,2.2,1.5])
        self.assertEqual(item["host_element_id"],7)
        self.assertEqual(item["integration_point_count"],1)
        self.assertEqual(item["location_quality"],"inside_element")

    def test_quadratic_mean_tensor_is_not_max_gauss_stress(self):
        obs=self.run_probe("C3D10",[10.,20.,30.,40.])
        item=obs["probes"]["target"]
        self.assertAlmostEqual(item["von_mises_mpa"],25.)
        self.assertNotEqual(item["von_mises_mpa"],40.)
        self.assertEqual(item["integration_point_count"],4)
        self.assertEqual(item["recovery"],RECOVERY)

    def test_unknown_outside_probes_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"outside"):
            self.run_probe("C3D4",[12.],xyz=(50.,50.,50.))
        with self.assertRaisesRegex(ValueError,"stress points"):
            self.run_probe("C3D10",[12.])
        with self.assertRaisesRegex(ValueError,"Missing|missing"):
            with tempfile.TemporaryDirectory() as folder:
                recover_fixed_stress(Path(folder)/"missing.dat",
                                     source_mesh("C3D4"),{"p":(2,2,2)})

    def test_probes_are_fixed_in_all_six_model_definitions(self):
        cases=[frame_stress_probes(s) for s in STUDIES]
        self.assertTrue(all(p==cases[0] for p in cases))
        self.assertEqual(len(cases[0]),4)


if __name__=="__main__":
    unittest.main()
