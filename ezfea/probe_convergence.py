"""Mesh-by-mesh convergence screening for stress at fixed PHYSICAL coordinates.

Unlike a mesh-global peak, the same named material coordinate must be probed
every run. A two-step stabilization flag is NOT engineering validation.
"""
from __future__ import annotations

import math


def _relative(previous, current):
    if not all(math.isfinite(x) for x in (previous, current)):
        raise ValueError("Nonfinite fixed-coordinate stress")
    return abs(current - previous) / max(abs(current), abs(previous), 1e-12)


def screen_fixed_probe_stress(records, *, element_type, tolerance=0.10):
    """Return independent per-probe evidence for >=3 increasingly dense grids."""
    if element_type not in ("C3D4", "C3D10"):
        raise ValueError("Unsupported stress probe element type")
    if not (math.isfinite(tolerance) and 0 < tolerance < 1):
        raise ValueError("Stress probe tolerance must be between zero and one")
    if len(records) < 3:
        raise ValueError("At least three physical meshes required for stress screening")

    key = ("fixed_coordinate_stress_affine" if element_type == "C3D10"
           else "fixed_coordinate_stress")
    probes = []
    expected_names = None
    for record in records:
        source = record.get(key)
        if not isinstance(source, dict) or not isinstance(source.get("probes"), dict) or not source["probes"]:
            raise ValueError(f"Fixed stress-probe evidence missing: {key}")
        names = set(source["probes"])
        if expected_names is None:
            expected_names = names
        if names != expected_names:
            raise ValueError("Probe names changed during refinement")
        probes.append(source["probes"])

    increases = all(records[i]["element_count"] < records[i+1]["element_count"]
                    for i in range(len(records)-1))
    output = {}
    for name in sorted(expected_names):
        samples = []
        coords = None
        for idx, p in enumerate(probes):
            item = p[name]
            xyz = item.get("coordinate_mm")
            if not isinstance(xyz, (tuple, list)) or len(xyz) != 3 or not all(
                isinstance(v, (float,int)) and math.isfinite(v) for v in xyz
            ):
                raise ValueError(f"Probe {name} lacks a valid coordinate")
            if coords is None:
                coords = tuple(xyz)
            if any(abs(x-y) > 1e-8 for x,y in zip(xyz, coords)):
                raise ValueError(f"Probe {name} moved between mesh grids")
            value = item.get("von_mises_mpa")
            if not isinstance(value, (float,int)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Probe {name} has invalid stress")
            samples.append({
                "mesh_size_mm": record_size(records[idx]),
                "von_mises_mpa": float(value),
                "location_quality": item.get("location_quality", "unknown"),
            })
        deltas = [_relative(a["von_mises_mpa"], b["von_mises_mpa"])
                  for a,b in zip(samples, samples[1:])]
        all_interior = all(sample["location_quality"] == "inside_element" for sample in samples)
        stable = increases and all_interior and all(d <= tolerance for d in deltas[-2:])
        output[name] = {
            "coordinate_mm": list(coords),
            "samples": samples,
            "adjacent_relative_changes": deltas,
            "observation": "stable_at_checked_mesh_sizes" if stable else "refinement_or_probe_review_required",
            "warnings": ([] if all_interior else
                         ["At least one probe is near a mesh-element boundary or has unknown location quality."]),
        }
    return {
        "schema": "ezfea.fixed_probe_convergence.v1",
        "stress_recovery": key,
        "screening_tolerance": tolerance,
        "element_counts_strictly_increase": increases,
        "probes": output,
        "all_probes_stable_at_checked_mesh_sizes": bool(output) and all(
            x["observation"] == "stable_at_checked_mesh_sizes" for x in output.values()
        ),
        "engineering_validation": "not_established",
    }


def record_size(record):
    value = record.get("mesh_size_mm")
    if not isinstance(value, (float,int)) or not math.isfinite(value) or value <= 0:
        raise ValueError("Missing/invalid mesh size for fixed-coordinate stress screening")
    return float(value)
