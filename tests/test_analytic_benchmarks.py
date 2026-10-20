"""Independent mechanics-of-materials bar reference mathematical checks."""
import unittest
from ezfea.analytic_benchmarks import axial_nominal_stress_mpa, axial_nominal_elongation_mm

class AnalyticalReferenceTests(unittest.TestCase):
    def test_simple_axial_force_over_area(self):
        self.assertAlmostEqual(axial_nominal_stress_mpa(100,100),1.)
        self.assertAlmostEqual(axial_nominal_elongation_mm(100,100,100,200000),.0005)
    def test_formula_preserves_load_scaling(self):
        self.assertAlmostEqual(axial_nominal_stress_mpa(200,100),2.)
        self.assertAlmostEqual(axial_nominal_elongation_mm(200,100,100,200000),.001)
    def test_rejects_nonsense_inputs(self):
        with self.assertRaises(ValueError):
            axial_nominal_stress_mpa(100,0)
        with self.assertRaises(ValueError):
            axial_nominal_elongation_mm(100,100,-20,200000)

if __name__=="__main__":
    unittest.main()
