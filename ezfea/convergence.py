"""Repeat the same physics problem at successively finer mesh sizes.

This is numerical *trend evidence*, not validation against exact mechanics.
Peak stress can diverge at idealized fixed edges or point-like loads.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

from .core import Analysis
from .workflow import run_case


def relative_change(previous: float, current: float) -> float:
    """Dimensionless last-step change; zero is stable, not proof of accuracy."""
    if not all(math.isfinite(v) for v in (previous, current)):
        raise ValueError("nonfinite solver metric")
    return abs(current - previous) / max(abs(current), abs(previous), 1.0e-12)


def run_refinement(
    case: Analysis,
    output_root="runs/mesh_refinement",
    *,
    sizes_mm=(12.0, 8.0, 5.0),
    displacement_tolerance=0.05,
    analytical_displacement_mm=None,
    fixed_stress_probes=None,
):
    """Collect independent native solves with identical non-mesh inputs.

    Do not call the final displacement a converged or validated engineering
    answer solely from agreement of two coarse C3D4 meshes.
    """
    case.validate()
    sizes = tuple(float(v) for v in sizes_mm)
    if len(sizes) < 3 or any(not math.isfinite(v) or v <= 0 for v in sizes):
        raise ValueError("provide at least three finite positive mesh sizes")
    if any(a <= b for a, b in zip(sizes, sizes[1:])):
        raise ValueError("mesh sizes must be strictly decreasing")
    if not (math.isfinite(displacement_tolerance) and 0 < displacement_tolerance < 1):
        raise ValueError("displacement tolerance must be between 0 and 1")
    if analytical_displacement_mm is not None and (
        not math.isfinite(analytical_displacement_mm) or analytical_displacement_mm <= 0
    ):
        raise ValueError("analytical displacement must be positive and finite")

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    source_sha = hashlib.sha256(Path(case.step_file).read_bytes()).hexdigest()
    model = case.as_dict()
    model.pop("mesh_size_mm")
    parameters = {
        "schema": "ezfea.mesh_refinement.v1",
        "input_sha256": source_sha,
        "units": "mm, N, MPa",
        "model_except_mesh_size": model,
        "requested_mesh_sizes_mm": sizes,
        "displacement_change_threshold": displacement_tolerance,
        "analytical_displacement_mm": analytical_displacement_mm,
        "note": "Global peak stress may be mesh-sensitive; displacement stabilization is not engineering validation.",
    }
    records = []
    for index, mesh_size in enumerate(sizes):
        if hashlib.sha256(Path(case.step_file).read_bytes()).hexdigest() != source_sha:
            raise RuntimeError("STEP changed during refinement; results are not comparable")
        run_input=replace(case,mesh_size_mm=mesh_size)
        run_dir=root / f"grid_{index+1:02d}"
        run_path=(run_case(run_input,run_dir, fixed_stress_probes=fixed_stress_probes)
                  if fixed_stress_probes is not None else run_case(run_input,run_dir))
        raw = json.loads((run_path / "case.json").read_text(encoding="utf-8"))
        if (raw.get("status") != "completed" or raw.get("input_sha256") != source_sha
            or raw.get("mesh",{}).get("element_type","C3D4")!=case.element_type):
            raise RuntimeError(f"grid {index+1} failed or changed input; see {run_path}")
        physics = raw["results"]
        displacement = float(physics["max_displacement_mm"])
        stress = float(physics["max_von_mises_mpa"])
        if not all(math.isfinite(v) and v > 0 for v in (displacement, stress)):
            raise RuntimeError(f"grid {index+1} has invalid physical results")
        record = {
            "mesh_size_mm": mesh_size,
            "element_type":case.element_type,
            "node_count": raw["mesh"]["nodes"],
            "element_count": raw["mesh"]["elements"],
            "max_displacement_mm": displacement,
            "max_von_mises_mpa": stress,
            "force_balance_relative_error": physics["force_balance_relative_error"],
            "fixed_coordinate_stress": physics.get("fixed_coordinate_stress"),
            "stress_distance_bands":physics.get("stress_distance_bands"),
            "run_directory": str(run_path.relative_to(root)),
        }
        if analytical_displacement_mm is not None:
            record["nominal_analytical_relative_error"] = (
                abs(displacement - analytical_displacement_mm) / analytical_displacement_mm
            )
        records.append(record)

    deltas = []
    for older, newer in zip(records, records[1:]):
        deltas.append({
            "from_mesh_mm": older["mesh_size_mm"],
            "to_mesh_mm": newer["mesh_size_mm"],
            "displacement_relative_change": relative_change(
                older["max_displacement_mm"], newer["max_displacement_mm"]),
            "peak_stress_relative_change": relative_change(
                older["max_von_mises_mpa"], newer["max_von_mises_mpa"]),
        })
    counts_increasing = all(
        a["element_count"] < b["element_count"]
        for a, b in zip(records, records[1:])
    )
    # A coarse/fine pair alone is insufficient: require both last changes small.
    last_two_stable = all(
        d["displacement_relative_change"] <= displacement_tolerance
        for d in deltas[-2:]
    )
    summary = {
        **parameters,
        "records": records,
        "adjacent_mesh_changes": deltas,
        "element_counts_strictly_increase": counts_increasing,
        "displacement_observation": (
            "stable_at_checked_mesh_sizes"
            if counts_increasing and last_two_stable else "refinement_not_yet_stable"
        ),
        "engineering_validation": "not_established",
        "max_stress_note": "Global peak stress may shift or diverge at idealized restraints; never infer stress convergence from this report alone.",
    }
    (root / "refinement.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description="EZ-FEA native mesh refinement evidence")
    parser.add_argument("--demo", action="store_true", help="create a 100x10x10 mm cantilever STEP")
    parser.add_argument("--step", help="single-solid STEP file to analyze")
    parser.add_argument("--fixed-face", type=int)
    parser.add_argument("--loaded-face", type=int)
    parser.add_argument("--force", nargs=3, type=float, default=(0, -100, 0))
    parser.add_argument("--meshes", nargs="+", type=float, default=(12, 8, 5))
    parser.add_argument("--out", default="runs/mesh_refinement")
    parser.add_argument("--tolerance", type=float, default=0.05)
    args = parser.parse_args()

    if args.demo:
        if args.step or args.fixed_face or args.loaded_face:
            parser.error("--demo cannot be mixed with an explicit STEP or face IDs")
        from .demo import make_demo_step
        from .mesh import inspect_step
        step = make_demo_step(Path(args.out) / "input" / "cantilever.step")
        faces = inspect_step(str(step))
        fixed = min(faces, key=lambda face: abs(face.center_mm[0]))
        loaded = min(faces, key=lambda face: abs(face.center_mm[0] - 100))
        fixed_face, loaded_face = fixed.tag, loaded.tag
    else:
        if not args.step or args.fixed_face is None or args.loaded_face is None:
            parser.error("provide --demo or --step, --fixed-face and --loaded-face")
        step, fixed_face, loaded_face = args.step, args.fixed_face, args.loaded_face

    case = Analysis(str(step), fixed_face, loaded_face, tuple(args.force), args.meshes[0])
    result = run_refinement(
        case, args.out, sizes_mm=args.meshes, displacement_tolerance=args.tolerance
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
