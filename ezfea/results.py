"""Read CalculiX ASCII .dat results without inventing missing values.

Single-step, linear-static solids only. Values originate from *NODE PRINT and
*EL PRINT, not extrapolated nodal contour values from a .frd visual.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][-+]?\d+)?"
_DISPLACEMENT = re.compile(r"^\s*displacements\s*\(vx,vy,vz\)", re.I)
_STRESS = re.compile(r"^\s*stresses\s*\(elem,\s*integ\.pnt\.,\s*sxx,syy,szz,sxy,sxz,syz\)", re.I)
_REACTION = re.compile(r"^\s*forces\s*\(fx,fy,fz\)\s*for set\b", re.I)


def _values(tokens, count):
    """Parse only complete numerical records, including Fortran D exponents."""
    if len(tokens) != count:
        return None
    try:
        values = [float(token.replace("D", "E").replace("d", "e")) for token in tokens]
    except ValueError:
        return None
    return values if all(math.isfinite(value) for value in values) else None


def von_mises_mpa(sxx, syy, szz, sxy, sxz, syz):
    """3D von Mises equivalent stress from the six Cauchy tensor components."""
    result = (
        ((sxx-syy)**2 + (syy-szz)**2 + (szz-sxx)**2) / 2
        + 3 * (sxy*sxy + sxz*sxz + syz*syz)
    )
    return math.sqrt(max(0., result))


def read_dat(dat_file: Path):
    """Return the last printed data block for each requested quantity.

    A missing table is returned as None, never as a manufactured zero.
    This parser is deliberately scoped to CalculiX's documented ASCII format.
    """
    if not dat_file.is_file():
        return {"displacement": None, "stress": None, "reactions": None}
    result = {"displacement": None, "stress": None, "reactions": None}
    kind = None
    active = []
    for line in dat_file.read_text(encoding="utf-8", errors="replace").splitlines():
        lower = line.lower()
        if _DISPLACEMENT.search(line):
            if kind is not None and active:
                result[kind] = active
            kind, active = "displacement", []
            continue
        if _STRESS.search(line):
            if kind is not None and active:
                result[kind] = active
            kind, active = "stress", []
            continue
        if _REACTION.search(line):
            if kind is not None and active:
                result[kind] = active
            kind, active = "reactions", []
            continue
        if kind is None:
            continue
        if not line.strip():
            # CalculiX inserts empty lines after headers and between tables.
            continue
        tokens = line.split()
        expected = 8 if kind == "stress" else 4
        values = _values(tokens, expected)
        if values is not None and tokens[0].isdigit() and (kind != "stress" or tokens[1].isdigit()):
            active.append(values)
            continue
        if active:
            result[kind] = active
        kind, active = None, []
    if kind is not None and active:
        result[kind] = active
    return result


def max_displacement_mm(dat_file: Path):
    """Backward-compatible public helper."""
    tables = read_dat(dat_file)
    if tables["displacement"] is None:
        return None
    return max(math.sqrt(sum(x*x for x in row[1:])) for row in tables["displacement"])


def summarize_dat(dat_file: Path, applied_force_n, yield_mpa, *, expected_nodes=None,
                  expected_elements=None, applied_force_scale_n=None,
                  applied_nodal_forces_n=None, element_type="C3D4"):
    """Provenance-aware, deliberately limited static analysis summary.

    A computed ratio against a nominal yield is not a validated safety claim.
    """
    if element_type not in ("C3D4","C3D10"):
        raise ValueError("Unknown element type in CalculiX results.")
    raw = read_dat(dat_file)
    missing = [name for name in ("displacement", "stress", "reactions")
               if raw[name] is None]
    if missing:
        raise ValueError("CalculiX .dat has no valid " + ", ".join(missing) +
                         " output. Check *NODE PRINT/*EL PRINT and solver logs.")
    nodes = raw["displacement"]
    stress = raw["stress"]
    reactions = raw["reactions"]
    if expected_nodes is not None and len(set(int(row[0]) for row in nodes)) != expected_nodes:
        raise ValueError("Displacement output does not cover every mesh node.")
    if expected_elements is not None and len(set(int(row[0]) for row in stress)) != expected_elements:
        raise ValueError("Stress output does not cover every mesh element.")
    peak_u = max(nodes, key=lambda row:math.sqrt(sum(x*x for x in row[1:])))
    peak_s = max(stress, key=lambda row:von_mises_mpa(*row[2:]))
    u_mm = math.sqrt(sum(x*x for x in peak_u[1:]))
    vm_mpa = von_mises_mpa(*peak_s[2:])
    # CalculiX printed RF also includes direct applied nodal loads at reported
    # connection nodes. Deduct those inputs to recover support reaction forces.
    raw_reaction = [sum(row[index] for row in reactions) for index in (1,2,3)]
    direct_on_connections = [
        sum(applied_nodal_forces_n.get((int(row[0]), axis), 0.)
            for row in reactions)
        if applied_nodal_forces_n is not None else 0.
        for axis in (1, 2, 3)
    ]
    reaction = [raw_reaction[i] - direct_on_connections[i] for i in range(3)]
    residual = [reaction[i] + applied_force_n[i] for i in range(3)]
    applied_magnitude = math.sqrt(sum(float(x)**2 for x in applied_force_n))
    reference_magnitude = applied_force_scale_n if applied_force_scale_n is not None else applied_magnitude
    if not math.isfinite(reference_magnitude) or reference_magnitude <= 0:
        raise ValueError("Applied force reference magnitude must be positive.")
    residual_norm = math.sqrt(sum(x*x for x in residual)) / reference_magnitude
    return {
        "source": dat_file.name,
        "stress_type": "integration_point_cauchy",
        "element_type":element_type,
        "element_type_note": ("First-order C3D4 can be stiff in bending; mesh verification required."
                              if element_type=="C3D4" else
                              "Quadratic C3D10: multiple Gauss points; peaks and convergence still require validation."),
        "max_displacement_mm": u_mm,
        "max_displacement_node_id": int(peak_u[0]),
        "max_von_mises_mpa": vm_mpa,
        "max_von_mises_element_id": int(peak_s[0]),
        "max_von_mises_integration_point": int(peak_s[1]),
        "nominal_yield_mpa": yield_mpa,
        "nominal_yield_to_von_mises_ratio": (
            yield_mpa / vm_mpa if vm_mpa > 0 else None),
        "reaction_force_n": reaction,
        "raw_solver_connection_forces_n": raw_reaction,
        "direct_applied_forces_on_connection_nodes_n": direct_on_connections,
        "applied_force_n": list(applied_force_n),
        "applied_force_reference_magnitude_n": reference_magnitude,
        "force_balance_residual_n": residual,
        "force_balance_relative_error": residual_norm,
        "force_balance_check": "pass" if residual_norm <= 0.01 else "review",
        "num_displacement_nodes": len(nodes),
        "num_stress_integration_points": len(stress),
        "num_reaction_nodes": len(reactions),
        "engineering_status": "experimental_unvalidated",
    }
