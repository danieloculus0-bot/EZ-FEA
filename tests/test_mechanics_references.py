"""Independent reference calculations with handwritten closed-form targets."""
import math
import unittest

from ezfea.mechanics_references import (
    isotropic_shear_modulus_mpa,
    rectangular_beam_shear_tau_mpa,
    circular_shaft_polar_moment_mm4,
    circular_shaft_torsional_stress_mpa,
    circular_shaft_twist_radians,
)


class ReferenceMechanicsTests(unittest.TestCase):
    def test_isotropic_shear_modulus(self):
        self.assertAlmostEqual(isotropic_shear_modulus_mpa(200000.,.25),80000.)

    def test_rectangular_shear_is_parabolic(self):
        self.assertAlmostEqual(rectangular_beam_shear_tau_mpa(100.,10.,10.,0.),1.5)
        self.assertAlmostEqual(rectangular_beam_shear_tau_mpa(100.,10.,10.,2.5),1.125)
        self.assertAlmostEqual(rectangular_beam_shear_tau_mpa(100.,10.,10.,5.),0.)
        self.assertAlmostEqual(rectangular_beam_shear_tau_mpa(-100.,10.,10.,0.),-1.5)

    def test_circular_polar_moment_and_torsional_stress(self):
        # r=10 mm, J=5000*pi mm^4, torque=10000 N-mm
        self.assertAlmostEqual(circular_shaft_polar_moment_mm4(10.),5000*math.pi)
        expected=20/math.pi
        self.assertAlmostEqual(circular_shaft_torsional_stress_mpa(10000.,10.,10.),expected)
        self.assertAlmostEqual(circular_shaft_torsional_stress_mpa(10000.,10.,0.),0.)
        self.assertAlmostEqual(circular_shaft_torsional_stress_mpa(-10000.,10.,10.),-expected)

    def test_torsion_angle_scales_with_length(self):
        g=isotropic_shear_modulus_mpa(200000.,.25)
        twist=circular_shaft_twist_radians(10000.,100.,g,10.)
        self.assertAlmostEqual(twist,1000000/(80000*5000*math.pi))
        self.assertAlmostEqual(circular_shaft_twist_radians(10000.,200.,g,10.),2*twist)

    def test_invalid_inputs_fail(self):
        for call in (
            lambda: isotropic_shear_modulus_mpa(200000.,0.5),
            lambda: rectangular_beam_shear_tau_mpa(100.,10.,10.,5.1),
            lambda: rectangular_beam_shear_tau_mpa(float("nan"),10.,10.,0.),
            lambda: circular_shaft_polar_moment_mm4(0),
            lambda: circular_shaft_torsional_stress_mpa(100.,10.,20.),
            lambda: circular_shaft_twist_radians(100.,100.,0.,10.),
        ):
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


if __name__=="__main__":
    unittest.main()
