"""Independent beam-theory checks, kept separate from FE solver outputs."""
import unittest

from ezfea.bending_benchmarks import (
    rectangular_second_moment_mm4,
    cantilever_bending_displacement_mm,
    cantilever_bending_stress_mpa,
)


class BendingTheoryTests(unittest.TestCase):
    def test_euler_tip_deflection(self):
        inertia=rectangular_second_moment_mm4(10,10)
        self.assertAlmostEqual(inertia,833.3333333333334)
        self.assertAlmostEqual(cantilever_bending_displacement_mm(
            100,100,200000,inertia),.2)
        self.assertAlmostEqual(cantilever_bending_stress_mpa(
            100,100,51.1,3.3,inertia),19.3644,places=4)

    def test_linear_tension_compression_bending_gradient(self):
        inertia=rectangular_second_moment_mm4(10,10)
        self.assertEqual(cantilever_bending_stress_mpa(
            100,100,25,0,inertia),0.)
        positive=cantilever_bending_stress_mpa(100,100,25,3,inertia)
        negative=cantilever_bending_stress_mpa(100,100,25,-3,inertia)
        self.assertAlmostEqual(positive,-negative)

    def test_invalid_geometry_rejected(self):
        with self.assertRaises(ValueError):
            rectangular_second_moment_mm4(10,0)
        with self.assertRaises(ValueError):
            cantilever_bending_displacement_mm(100,100,-200000,800)


if __name__=="__main__":
    unittest.main()
