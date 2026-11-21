"""Independent synthetic acceptance for the BEAN-facing axial design environment."""
import math
import sys

import pytest
from ezfea.axial_design_challenge import evaluate_axial_design, rank_axial_options


def challenge():
    return {
        "model": {
            "elements": [{"length_m": 2.0, "area_m2": 0.01, "youngs_modulus_pa": 200e9}],
            "nodal_forces_n": [0.0, 1000.0],
            "prescribed_displacements_m": {"0": 0.0},
        },
        "area_options_m2": {"thin": 0.001, "medium": 0.002, "thick": 0.004},
        "density_kg_m3": 7850.0,
        "max_abs_displacement_m": 6e-6,
    }


def test_solver_scored_design_and_optimum():
    c = challenge()
    ranked = rank_axial_options(c)
    assert [item["option_id"] for item in ranked] == ["medium", "thick", "thin"]
    assert ranked[0]["feasible"] is True
    assert ranked[0]["max_abs_displacement_m"] == pytest.approx(5e-6)
    assert ranked[0]["mass_kg"] == pytest.approx(31.4)
    assert ranked[-1]["feasible"] is False
    assert ranked[-1]["score"] == 0.0


def test_agent_claimed_score_cannot_override_solver():
    c = challenge()
    actual = evaluate_axial_design(c, {"option_id": "thin"})
    spoof = evaluate_axial_design(c, {"option_id": "thin", "claimed_score": 999999})
    assert actual == spoof
    assert actual["score"] == 0.0


@pytest.mark.parametrize("proposal", [
    {"option_id": "missing"},
    {"option_id": "thin", "area_m2": 1000},
    {"option_id": None},
])
def test_invalid_proposals_rejected(proposal):
    with pytest.raises(ValueError):
        evaluate_axial_design(challenge(), proposal)


def test_deterministic_and_does_not_mutate_input():
    c = challenge()
    original = c["model"]["elements"][0]["area_m2"]
    assert rank_axial_options(c) == rank_axial_options(c)
    assert c["model"]["elements"][0]["area_m2"] == original


def test_subnormal_positive_mass_has_finite_score_and_stable_ranking():
    c = challenge()
    c["density_kg_m3"] = 1e-310
    ranked = rank_axial_options(c)
    assert [item["option_id"] for item in ranked] == ["medium", "thick", "thin"]
    assert all(math.isfinite(item["score"]) for item in ranked)
    assert ranked[0]["score"] == sys.float_info.max
    assert ranked[-1]["score"] == 0.0


def test_underflowed_design_mass_rejected_not_scored():
    c = challenge()
    c["density_kg_m3"] = 5e-324
    with pytest.raises(ValueError, match="design mass"):
        evaluate_axial_design(c, {"option_id": "medium"})
