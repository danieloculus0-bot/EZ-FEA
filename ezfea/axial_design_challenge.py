"""Synthetic, independently scored axial design decisions for external agents.

No BEAN Core connection is implied. All units SI; no employer records.
"""
import math
import sys
from copy import deepcopy

from ezfea.axial_bar import solve


def evaluate_axial_design(challenge, proposal):
    """Return solver-grounded feasibility and mass for a discrete design choice.

    The agent supplies only option_id. Any claimed score is ignored.
    """
    if not isinstance(challenge, dict) or not isinstance(proposal, dict):
        raise ValueError("challenge and proposal must be objects")
    options = challenge["area_options_m2"]
    if not isinstance(options, dict) or not options:
        raise ValueError("area_options_m2 must be a nonempty object")
    if set(proposal) - {"option_id", "claimed_score"}:
        raise ValueError("unexpected proposal fields")
    option_id = proposal.get("option_id")
    if not isinstance(option_id, str) or option_id not in options:
        raise ValueError("unknown option_id")
    if not isinstance(challenge.get("model"), dict):
        raise ValueError("model must be an object")
    model = deepcopy(challenge["model"])
    if not isinstance(model.get("elements"), list) or not model["elements"]:
        raise ValueError("model must contain elements")
    if len(model["elements"]) != 1:
        raise ValueError("v1 supports a single axial element")
    area = options[option_id]
    limit = challenge["max_abs_displacement_m"]
    density = challenge["density_kg_m3"]
    for value, name in ((area, "area"), (limit, "displacement limit"), (density, "density")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    model["elements"][0]["area_m2"] = float(area)
    result = solve(model)
    max_displacement = max(abs(v) for v in result["displacements_m"])
    mass = float(density) * float(area) * model["elements"][0]["length_m"]
    if not math.isfinite(mass) or mass <= 0:
        raise ValueError("design mass must be finite and positive")
    feasible = max_displacement <= limit
    # Keep the reciprocal-mass ordering without emitting Infinity for tiny masses.
    score = min(1.0 / mass, sys.float_info.max) if feasible and mass >= 1.0 / sys.float_info.max else (sys.float_info.max if feasible else 0.0)
    return {
        "option_id": option_id,
        "feasible": feasible,
        "mass_kg": mass,
        "max_abs_displacement_m": max_displacement,
        "displacement_limit_m": float(limit),
        "force_balance_residual_n": result["force_balance_residual_n"],
        "score": score,
        "solver": "ezfea.axial_bar.solve",
    }


def rank_axial_options(challenge):
    """Independently evaluate every option, including an optimum reference."""
    options = challenge["area_options_m2"]
    return sorted(
        (evaluate_axial_design(challenge, {"option_id": key}) for key in options),
        key=lambda item: (-item["score"], item["mass_kg"], item["option_id"]),
    )
