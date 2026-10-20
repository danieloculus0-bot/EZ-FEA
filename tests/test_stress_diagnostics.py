"""Diagnostic calculations use real stress tensors, never synthesized peaks."""
import tempfile
import unittest
from pathlib import Path

from ezfea.mesh import Mesh
from ezfea.stress_diagnostics import stress_distance_bands, fixture_plane

STRESS = """
 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set PART and time 0.1000000E+01

       101   1    1.000000E+02  0  0  0  0  0
       102   1    2.000000E+01  0  0  0  0  0
       103   1    1.500000E+01  0  0  0  0  0
"""

def fixture():
    nodes={
        1:(0.,0.,0.),2:(1.,0.,0.),3:(0.,1.,0.),4:(0.,0.,4.),
        5:(0.,0.,20.),6:(1.,0.,20.),7:(0.,1.,20.),8:(0.,0.,28.),
        9:(0.,0.,40.),10:(1.,0.,40.),11:(0.,1.,40.),12:(0.,0.,48.),
    }
    return Mesh(nodes,
                {101:(1,2,3,4),102:(5,6,7,8),103:(9,10,11,12)},
                [1,2,3],{11:1.},1.)

class StressLocalizationTests(unittest.TestCase):
    def test_fixture_plane_and_source_stress(self):
        mesh=fixture()
        self.assertEqual(fixture_plane(mesh),(2,0.))
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"analysis.dat"
            file.write_text(STRESS,encoding="utf-8")
            data=stress_distance_bands(file,mesh)
        self.assertEqual(data["status"],"plane_distance_diagnostic")
        self.assertEqual(data["global_peak_mpa"],100.)
        self.assertEqual(data["global_peak_element"],101)
        self.assertAlmostEqual(data["global_peak_host_tet_centroid_distance_mm"],1.)
        self.assertEqual(data["outside_band_max_mpa"],[20.,15.])
        self.assertEqual(data["outside_band_integration_point_count"],[2,1])

    def test_nonplanar_fixture_not_misrepresented(self):
        mesh=fixture()
        mesh.fixed_nodes=[1,2,3,4]
        self.assertIsNone(fixture_plane(mesh))
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"analysis.dat"
            file.write_text(STRESS,encoding="utf-8")
            data=stress_distance_bands(file,mesh)
        self.assertEqual(data["status"],"not_applicable_nonplanar_fixture")

    def test_no_missing_output_claims(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"no.dat"
            with self.assertRaisesRegex(ValueError,"Missing native"):
                stress_distance_bands(file,fixture())

    def test_invalid_thresholds_rejected(self):
        with self.assertRaisesRegex(ValueError,"ordered"):
            stress_distance_bands(Path("not-used.dat"),fixture(),
                                  exclusions_mm=(40,20))


if __name__=="__main__":
    unittest.main()
