"""Verification of physical XYZ Gauss-to-probe stress tensor interpolation."""
import tempfile
import unittest
from pathlib import Path

from ezfea.mesh import Mesh
from ezfea.results import read_dat
from ezfea.stress_interpolation import (
    AFFINE_RECOVERY, recover_affine_gauss_stress
)


def fixture_mesh():
    pts={
        1:(0.,0.,0.),2:(10.,0.,0.),3:(0.,10.,0.),4:(0.,0.,10.),
        5:(5.,0.,0.),6:(5.,5.,0.),7:(0.,5.,0.),8:(0.,0.,5.),
        9:(5.,0.,5.),10:(0.,5.,5.),
    }
    return Mesh(pts,{7:tuple(range(1,11))},[1,2,3],{4:1.},1.,
                element_type="C3D10")


GAUSS=((1.5,1.5,1.5),(4.5,1.5,1.5),(1.5,4.5,1.5),(1.5,1.5,4.5))


def field(p):
    x,y,z=p
    return 10. + 2*x + 3*y + z/2


def fake_native_dat(reverse=False,missing=False):
    ids=range(4,0,-1) if reverse else range(1,5)
    if missing:
        ids=range(1,4)
    stress=("stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set PART and time 0.1000000E+01\n\n")
    coords=("global coordinates (elem, integ.pnt.,x,y,z) for set PART and time 0.1000000E+01\n\n")
    for i in ids:
        p=GAUSS[i-1]
        stress+=f" 7 {i} {field(p):.7E} 0.0 0.0 0.0 0.0 0.0\n"
        coords+=f" 7 {i} {p[0]:.7E} {p[1]:.7E} {p[2]:.7E}\n"
    return stress+"\n"+coords+"\n"


class PhysicalGaussInterpolationTests(unittest.TestCase):
    def setup_file(self,source):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path=Path(folder.name)/"analysis.dat"
        path.write_text(source,encoding="utf-8")
        return path

    def test_parser_pairs_calculix_gauss_coordinates(self):
        parsed=read_dat(self.setup_file(fake_native_dat()))
        self.assertEqual(len(parsed["stress"]),4)
        self.assertEqual(len(parsed["coordinates"]),4)
        self.assertEqual(parsed["coordinates"][2][:2],[7,2])

    def test_affine_tensor_recovered_exactly_at_fixed_xyz(self):
        xyz=(2.1,2.2,1.5)
        for reverse in (False,True):
            with self.subTest(reverse=reverse):
                result=recover_affine_gauss_stress(
                    self.setup_file(fake_native_dat(reverse=reverse)),
                    fixture_mesh(),{"p":xyz})
                entry=result["probes"]["p"]
                self.assertAlmostEqual(entry["von_mises_mpa"],field(xyz),places=6)
                self.assertEqual(entry["coordinate_mm"],list(xyz))
                self.assertEqual(entry["recovery"],AFFINE_RECOVERY)
                self.assertAlmostEqual(sum(entry["gauss_interpolation_weights"]),1.)
                self.assertEqual(entry["integration_point_count"],4)

    def test_requires_matching_complete_native_gauss_rows(self):
        with self.assertRaisesRegex(ValueError,"missing matched"):
            recover_affine_gauss_stress(self.setup_file(fake_native_dat(missing=True)),
                                        fixture_mesh(),{"p":(2,2,2)})
        with self.assertRaisesRegex(ValueError,"both required|both"):
            recover_affine_gauss_stress(
                self.setup_file(fake_native_dat().split("global coordinates")[0]),
                fixture_mesh(),{"p":(2,2,2)})

    def test_refuses_curved_tetra_for_affine_material_coordinates(self):
        mesh=fixture_mesh()
        mesh.nodes[5]=(5.,0.2,0.)
        with self.assertRaisesRegex(ValueError,"Curved C3D10"):
            recover_affine_gauss_stress(
                self.setup_file(fake_native_dat()),mesh,{"p":(2,2,2)})

    def test_outside_points_not_converted_into_nearest_element(self):
        with self.assertRaisesRegex(ValueError,"outside"):
            recover_affine_gauss_stress(
                self.setup_file(fake_native_dat()),fixture_mesh(),{"p":(20.,20.,20.)})

    def test_constant_tensor_remains_constant_at_interior_probe(self):
        dat=fake_native_dat()
        for p in GAUSS:
            dat=dat.replace(f" {field(p):.7E} 0.0",f" {8.:.7E} 0.0")
        entry=recover_affine_gauss_stress(
            self.setup_file(dat),fixture_mesh(),{"p":(2,2,2)})["probes"]["p"]
        self.assertAlmostEqual(entry["von_mises_mpa"],8.)


if __name__=="__main__":
    unittest.main()
