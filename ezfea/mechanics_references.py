"""Independent closed-form mechanics references (not a substitute for native FEA).

SI-consistent engineering units: force N, length mm, stress MPa, moment N*mm.
Circular torsion equations assume a uniform homogeneous round prismatic shaft
with Saint-Venant torsion and no material plasticity. Rectangular transverse
shear distribution is a classical beam approximation, not an exact 3D field.
"""
from __future__ import annotations
import math


def _positive(*values):
    if not all(isinstance(x, (float, int)) and math.isfinite(x) and x > 0 for x in values):
        raise ValueError("Geometry and moduli must be finite and positive")


def isotropic_shear_modulus_mpa(youngs_mpa, poisson):
    _positive(youngs_mpa)
    if not math.isfinite(poisson) or not -1 < poisson < 0.5:
        raise ValueError("Poisson ratio must satisfy -1 < nu < 0.5")
    return youngs_mpa / (2 * (1 + poisson))


def rectangular_beam_shear_tau_mpa(shear_force_n, width_mm, height_mm, y_mm):
    """Parabolic transverse shear stress tau_xy, y relative to neutral axis.

    tau_xy(y) = (3/2) V/(b*h) * (1 - (2*y/h)^2).
    """
    _positive(width_mm, height_mm)
    if not math.isfinite(shear_force_n) or not math.isfinite(y_mm):
        raise ValueError("Shear loading or sample coordinate is nonfinite")
    if abs(y_mm) > height_mm/2:
        raise ValueError("Shear evaluation is outside beam depth")
    return 1.5 * shear_force_n / (width_mm * height_mm) * (
        1 - (2*y_mm/height_mm)**2
    )


def circular_shaft_polar_moment_mm4(radius_mm):
    _positive(radius_mm)
    return math.pi * radius_mm**4 / 2


def circular_shaft_torsional_stress_mpa(torque_nmm, radius_mm, sample_radius_mm):
    _positive(radius_mm)
    if not math.isfinite(torque_nmm) or not math.isfinite(sample_radius_mm) or not 0 <= sample_radius_mm <= radius_mm:
        raise ValueError("Invalid torque or sample radius")
    return torque_nmm * sample_radius_mm / circular_shaft_polar_moment_mm4(radius_mm)


def circular_shaft_twist_radians(torque_nmm, length_mm, shear_modulus_mpa, radius_mm):
    _positive(length_mm, shear_modulus_mpa, radius_mm)
    if not math.isfinite(torque_nmm):
        raise ValueError("Nonfinite torque")
    return torque_nmm * length_mm / (shear_modulus_mpa * circular_shaft_polar_moment_mm4(radius_mm))
