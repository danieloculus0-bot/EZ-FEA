"""Pure torque nodal resultant and twist estimator independent of solver."""
import math
import unittest

from ezfea.torsion_benchmarks import (
    consistent_end_torque, measured_twist_radians, write_torsion_deck,
)
from ezfea.load_footprints import resultant_force_moment


def square():
    # Four-node symmetrical planar square; two T3 triangles.
    nodes={
        1:(100.,-1.,-1.),2:(100.,1.,-1.),
        3:(100.,1.,1.),4:(100.,-1.,1.),
    }
    return nodes,[(1,2,3),(1,3,4)]


class TorsionBenchmarkTests(unittest.TestCase):
    def test_consistent_tangential_load_is_pure_1000_nmm_torque(self):
        nodes,faces=square()
        loads,audit=consistent_end_torque(nodes,faces,1000.)
        result=resultant_force_moment(loads,nodes)
        self.assertAlmostEqual(result["moment_about_origin_nmm"][0],1000.,places=6)
        self.assertAlmostEqual(result["force_n"][0],0.,places=6)
        self.assertAlmostEqual(result["force_n"][1],0.,places=6)
        self.assertAlmostEqual(result["force_n"][2],0.,places=6)
        self.assertLess(math.hypot(*result["moment_about_origin_nmm"][1:]),1e-6)
        self.assertEqual(audit["traction"],"t_y=-alpha*z, t_z=alpha*y")

    def test_reverse_torque_reverses_nodal_forces(self):
        nodes,faces=square()
        a,_=consistent_end_torque(nodes,faces,1000.)
        b,_=consistent_end_torque(nodes,faces,-1000.)
        for key in a:
            self.assertAlmostEqual(a[key],-b[key])

    def test_rotational_displacement_fit_uses_all_tip_nodes(self):
        nodes,_=square()
        theta=.003
        data={"displacement":[[n,0.,-theta*p[2],theta*p[1]] for n,p in nodes.items()]}
        model={"nodes":nodes,"tip_nodes":list(nodes)}
        self.assertAlmostEqual(measured_twist_radians(data,model),theta,places=9)
        data["displacement"].pop()
        with self.assertRaisesRegex(ValueError,"do not match"):
            measured_twist_radians(data,model)

    def test_no_usable_torque_surface_rejected(self):
        nodes,faces=square()
        for bad in (0.,float("nan")):
            with self.assertRaises(ValueError):
                consistent_end_torque(nodes,faces,bad)
        with self.assertRaisesRegex(ValueError,"surface"):
            consistent_end_torque(nodes,[],1000.)


if __name__=="__main__":
    unittest.main()
