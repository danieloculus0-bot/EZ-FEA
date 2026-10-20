"""Small known-value CalculiX ASCII .dat fixtures, including force balance."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from ezfea.results import read_dat, max_displacement_mm, summarize_dat, von_mises_mpa

FIXTURE = """
 displacements (vx,vy,vz) for set ALL_NODES and time 0.1000000E+01

       1    0.000000E+00   0.000000E+00  0.000000E+00
       2    3.000000E-01   4.000000E-01  0.000000E+00

 forces (fx,fy,fz) for set CONNECTION and time 0.1000000E+01

       1  -1.000000E+02  0.000000E+00  0.000000E+00

 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set PART and time 0.1000000E+01

       1   1    1.000000E+02  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00
       2   1    0.000000E+00  0.000000E+00  0.000000E+00  5.000000E+01  0.000000E+00  0.000000E+00

"""

class CalculixResultTests(unittest.TestCase):
    def setup_file(self, contents=FIXTURE):
        tmp=tempfile.TemporaryDirectory()
        dat=Path(tmp.name)/"analysis.dat"
        dat.write_text(contents)
        self.addCleanup(tmp.cleanup)
        return dat

    def test_simple_uniaxial_equivalent_stress(self):
        self.assertAlmostEqual(von_mises_mpa(100,0,0,0,0,0),100)

    def test_pure_shear_equivalent_stress(self):
        self.assertAlmostEqual(von_mises_mpa(0,0,0,50,0,0),50*math.sqrt(3))

    def test_hydrostatic_stress_has_zero_von_mises(self):
        self.assertAlmostEqual(von_mises_mpa(100,100,100,0,0,0),0)

    def test_reads_three_real_calculix_tables(self):
        dat=self.setup_file()
        tables=read_dat(dat)
        self.assertEqual(len(tables["displacement"]),2)
        self.assertEqual(len(tables["stress"]),2)
        self.assertEqual(len(tables["reactions"]),1)
        self.assertAlmostEqual(max_displacement_mm(dat),0.5)

    def test_correct_3d_solver_metrics(self):
        dat=self.setup_file()
        result=summarize_dat(dat,(100,0,0),250,expected_nodes=2,expected_elements=2)
        self.assertAlmostEqual(result["max_von_mises_mpa"],100)
        self.assertEqual(result["max_von_mises_element_id"],1)
        self.assertAlmostEqual(result["nominal_yield_to_von_mises_ratio"],2.5)
        self.assertEqual(result["reaction_force_n"],[-100.,0.,0.])
        self.assertEqual(result["force_balance_check"],"pass")
        self.assertAlmostEqual(result["max_displacement_mm"],0.5)

    def test_direct_force_on_connection_node_is_not_double_counted(self):
        # RF is raw internal nodal force. One connected node also gets -10 N
        # directly, so the reported -110 N must be corrected to -100 N.
        dat = self.setup_file(FIXTURE.replace("-1.000000E+02", "-1.100000E+02"))
        result = summarize_dat(
            dat, (100, 0, 0), 250,
            applied_nodal_forces_n={(1, 1): -10.},
        )
        self.assertEqual(result["reaction_force_n"], [-100., 0., 0.])
        self.assertEqual(result["raw_solver_connection_forces_n"], [-110., 0., 0.])
        self.assertEqual(result["direct_applied_forces_on_connection_nodes_n"], [-10., 0., 0.])
        self.assertEqual(result["force_balance_check"], "pass")

    def test_applied_eccentric_force_and_reaction_moments_balance(self):
        result_file=self.setup_file("""
 displacements (vx,vy,vz) for set ALL_NODES and time 1.0
 1 0 0 0
 2 0 0 0
 3 0.001 0 0

 forces (fx,fy,fz) for set CONNECTION and time 1.0
 1 -50 0 0
 2 -50 0 0

 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set PART and time 1.0
 8 1 10 0 0 0 0 0
""")
        positions={1:(0.,0.,0.),2:(0.,0.,2.),3:(10.,0.,1.)}
        force={(3,1):100.}
        info=summarize_dat(result_file,(100.,0.,0.),250,
                           applied_nodal_forces_n=force,
                           node_positions_mm=positions)
        self.assertEqual(info["force_balance_check"],"pass")
        self.assertEqual(info["moment_balance_check"],"pass")
        self.assertAlmostEqual(info["applied_moment_about_origin_nmm"][1],100.)
        self.assertAlmostEqual(info["reaction_moment_about_origin_nmm"][1],-100.)
        invalid=self.setup_file("""
 displacements (vx,vy,vz) for set ALL_NODES and time 1.0
 1 0 0 0
 2 0 0 0
 3 0.001 0 0

 forces (fx,fy,fz) for set CONNECTION and time 1.0
 1 -100 0 0
 2 0 0 0

 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set PART and time 1.0
 8 1 10 0 0 0 0 0
""")
        checked=summarize_dat(invalid,(100.,0.,0.),250,
                              applied_nodal_forces_n=force,
                              node_positions_mm=positions)
        self.assertEqual(checked["force_balance_check"],"pass")
        self.assertEqual(checked["moment_balance_check"],"review")

    def test_out_of_balance_marked_for_review(self):
        dat=self.setup_file(FIXTURE.replace("-1.000000E+02","-7.000000E+01"))
        result=summarize_dat(dat,(100,0,0),250)
        self.assertEqual(result["force_balance_check"],"review")
        self.assertAlmostEqual(result["force_balance_relative_error"],.3)

    def test_d_exponents(self):
        dat=self.setup_file(FIXTURE.replace("E+", "D+").replace("E-", "D-"))
        self.assertAlmostEqual(summarize_dat(dat,(100,0,0),250)["max_von_mises_mpa"],100)

    def test_missing_stress_rejected(self):
        dat=self.setup_file(FIXTURE.split(" stresses (elem")[0])
        with self.assertRaisesRegex(ValueError,"stress"):
            summarize_dat(dat,(100,0,0),250)

    def test_missing_reactions_rejected(self):
        dat=self.setup_file(FIXTURE.replace(" forces (fx,fy,fz)", " unrelated (fx,fy,fz)"))
        with self.assertRaisesRegex(ValueError,"reactions"):
            summarize_dat(dat,(100,0,0),250)

    def test_incomplete_node_coverage_rejected(self):
        dat=self.setup_file()
        with self.assertRaisesRegex(ValueError,"every mesh node"):
            summarize_dat(dat,(100,0,0),250,expected_nodes=3)

    def test_missing_dat_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            dat=Path(folder)/"missing.dat"
            self.assertIsNone(max_displacement_mm(dat))
            with self.assertRaises(ValueError):
                summarize_dat(dat,(100,0,0),250)

if __name__=="__main__":
    unittest.main()
