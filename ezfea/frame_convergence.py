"""Repeat the six *actual* frame specimens with progressively finer native meshes.

Gmsh + CalculiX provide all measured data. This is a numerical sensitivity
study, NOT solver validation, weld validation, or design certification.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from .convergence import run_refinement, relative_change
from .frame_benchmarks import STUDIES, create_step, case_from_step, geometry_definition_sha256


DEFAULT_MESHES_MM = (14., 10., 7.)


def analyze_recorded_refinements(cases, *, displacement_tolerance=.05,
                                 peak_stress_tolerance=.10):
    """Summarize *recorded* calculations without manufacturing any outputs.

    This function accepts run_refinement output and is unit-testable without
    loading the actual physics engine. It does not validate engineering truth.
    """
    if not isinstance(cases,list) or not cases:
        raise ValueError("No frame refinement records provided")
    if not (math.isfinite(displacement_tolerance) and 0 < displacement_tolerance < 1):
        raise ValueError("Invalid displacement tolerance")
    if not (math.isfinite(peak_stress_tolerance) and 0 < peak_stress_tolerance < 1):
        raise ValueError("Invalid peak stress tolerance")

    out=[]
    for entry in cases:
        raw=entry["refinement"]
        records=raw["records"]
        changes=raw["adjacent_mesh_changes"]
        if len(records)<3 or len(changes)!=len(records)-1:
            raise ValueError("Need at least three real solver meshes for every specimen")
        sizes=[float(item["mesh_size_mm"]) for item in records]
        counts=[item["element_count"] for item in records]
        if (any(not math.isfinite(x) or x<=0 for x in sizes)
            or any(a<=b for a,b in zip(sizes,sizes[1:]))
            or any(not isinstance(x,int) or x<=0 for x in counts)):
            raise ValueError("Invalid ordered mesh metadata")
        for metric in ("max_displacement_mm","max_von_mises_mpa","force_balance_relative_error"):
            if any(not isinstance(item.get(metric),(int,float))
                   or not math.isfinite(item[metric]) for item in records):
                raise ValueError(f"Incomplete solver records: {metric}")
        if any(item["max_displacement_mm"]<=0 or item["max_von_mises_mpa"]<=0
               or not 0<=item["force_balance_relative_error"]<=.01 for item in records):
            raise ValueError("Failed solver physics or force equilibrium")
        increasing=all(a<b for a,b in zip(counts,counts[1:]))
        if increasing != bool(raw["element_counts_strictly_increase"]):
            raise ValueError("Mesh count progression does not match raw data")
        for older,newer,delta in zip(records,records[1:],changes):
            for metric,label in (
                ("max_displacement_mm","displacement_relative_change"),
                ("max_von_mises_mpa","peak_stress_relative_change")
            ):
                observed=relative_change(older[metric],newer[metric])
                if (not math.isfinite(delta[label]) or
                    abs(delta[label]-observed)>1e-10):
                    raise ValueError("Recorded mesh deltas are inconsistent")
        disp_changes=[d["displacement_relative_change"] for d in changes]
        stress_changes=[d["peak_stress_relative_change"] for d in changes]
        displacement_stable=(increasing and
            all(x<=displacement_tolerance for x in disp_changes[-2:]))
        stress_stable=(increasing and
            all(x<=peak_stress_tolerance for x in stress_changes[-2:]))
        if raw["displacement_observation"] != (
                "stable_at_checked_mesh_sizes" if displacement_stable
                else "refinement_not_yet_stable"):
            # This analyzer normally uses the same displacement tolerance
            # passed into run_refinement. Mismatch indicates an invalid report.
            raise ValueError("Raw convergence assessment mismatches parameters")
        out.append({
            "key":entry["key"],
            "specimen_definition_sha256":entry["definition_sha256"],
            "step_sha256":raw["input_sha256"],
            "source_step":entry["source_step"],
            "mesh_sizes_mm":sizes,
            "elements":counts,
            "nodes":[r["node_count"] for r in records],
            "max_displacements_mm":[r["max_displacement_mm"] for r in records],
            "peak_von_mises_mpa":[r["max_von_mises_mpa"] for r in records],
            "equilibrium_relative_errors":[r["force_balance_relative_error"] for r in records],
            "displacement_adjacent_changes":disp_changes,
            "peak_stress_adjacent_changes":stress_changes,
            "fine_displacement_delta_pct":100*disp_changes[-1],
            "fine_peak_stress_delta_pct":100*stress_changes[-1],
            "max_force_balance_relative_error":max(r["force_balance_relative_error"] for r in records),
            "increasing_element_counts":increasing,
            "displacement_observation":(
                "stable_at_checked_mesh_sizes" if displacement_stable
                else "refinement_not_yet_stable"),
            "peak_stress_observation":(
                "limited_sensitivity_at_checked_mesh_sizes" if stress_stable
                else "mesh_sensitive_or_singularity_possible"),
            "raw_evidence_path":entry["raw_evidence_path"],
        })
    return out


def report_markdown(report):
    """A compact human-readable engineering report with source limitations."""
    def fmt(value): return f"{value:.5g}"
    lines=[
        "# EZ-FEA — Native frame three-grid solver refinement",
        "",
        f"Run date (UTC): {report['generated_utc']}",
        "",
        f"Element type: {report['element_type']}. These are real Gmsh + CalculiX solves, not BEAN estimates.",
        "All six cases retain the same STEP geometry, material, supports and total force",
        "within each three-grid comparison; only requested mesh size changes.",
        "",
        "| Frame / load | Tets coarse → medium → fine | Displacement coarse → medium → fine (mm) | Last Δu | Last Δ peak σ | Displacement trend | Peak stress trend |",
        "|---|---:|---|---:|---:|---|---|",
    ]
    for r in report["studies"]:
        sizes=", ".join(fmt(x) for x in r["max_displacements_mm"])
        counts=" → ".join(str(x) for x in r["elements"])
        lines.append(
            f"| \`{r['key']}\` | {counts} | {sizes} | "
            f"{fmt(r['fine_displacement_delta_pct'])}% | "
            f"{fmt(r['fine_peak_stress_delta_pct'])}% | "
            f"{r['displacement_observation']} | {r['peak_stress_observation']} |"
        )
    lines.extend([
        "",
        f"**Displacement observation:** {report['overall_displacement_observation']}. "
        f"Criterion: both successive changes ≤ {report['displacement_threshold_pct']}% "
        "and mesh element counts strictly increase.",
        f"**Peak stress observation:** {report['overall_peak_stress_observation']}. "
        f"Screening criterion: both successive changes ≤ {report['peak_stress_screen_pct']}%. "
        "This is NOT a stress-convergence guarantee.",
        "",
        "> This report is NOT solver validation, only sensitivity to meshing. Global peak",
        "> first-order C3D4 stress may change substantially at fully fixed corners,",
        "> and first-order tets can be overly stiff in bending. No physical",
        "> test, higher-order element, independent benchmark, or qualified",
        "> engineer has validated these designs. Not for engineering sign-off.",
    ])
    return "\n".join(lines)+"\n"


def run_frame_convergence(output_root="runs/frame_convergence", *,
                          sizes_mm=DEFAULT_MESHES_MM,
                          displacement_tolerance=.05,
                          peak_stress_tolerance=.10,
                          specimens=STUDIES,
                          element_type="C3D4"):
    """Generate each STEP once, run each with 3+ grids, record full provenance."""
    if element_type not in ("C3D4", "C3D10"):
        raise ValueError("Unsupported element type.")
    sizes=tuple(float(x) for x in sizes_mm)
    if len(sizes)<3 or any(not math.isfinite(v) or v<=0 for v in sizes) or \
            any(x<=y for x,y in zip(sizes,sizes[1:])):
        raise ValueError("Specify at least three strictly decreasing positive mesh sizes")
    if not specimens or len({s.key for s in specimens})!=len(specimens):
        raise ValueError("Expected unique frame specimen identities")
    root=Path(output_root)
    root.mkdir(parents=True,exist_ok=True)
    base=[]
    for spec in specimens:
        frame=root/spec.key
        step=create_step(spec,frame/"cad"/(spec.key+".step"))
        case=replace(case_from_step(spec,step,mesh_size_mm=sizes[0]),
                     element_type=element_type)
        raw=run_refinement(case,frame/"refinement",
                           sizes_mm=sizes,displacement_tolerance=displacement_tolerance)
        base.append({
            "key":spec.key,
            "definition_sha256":geometry_definition_sha256(spec),
            "source_step":str(step.relative_to(root)),
            "raw_evidence_path":str((frame/"refinement"/"refinement.json").relative_to(root)),
            "refinement":raw,
        })
    rows=analyze_recorded_refinements(base,
        displacement_tolerance=displacement_tolerance,
        peak_stress_tolerance=peak_stress_tolerance)
    report={
        "schema":"ezfea.frame_convergence.v1",
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "mesh_sizes_mm":list(sizes),
        "element_type":element_type,
        "displacement_threshold_pct":100*displacement_tolerance,
        "peak_stress_screen_pct":100*peak_stress_tolerance,
        "studies":rows,
        "overall_displacement_observation":(
            "stable_at_checked_mesh_sizes"
            if all(r["displacement_observation"]=="stable_at_checked_mesh_sizes" for r in rows)
            else "more_refinement_needed"),
        "overall_peak_stress_observation":(
            "limited_sensitivity_at_checked_mesh_sizes"
            if all(r["peak_stress_observation"]=="limited_sensitivity_at_checked_mesh_sizes" for r in rows)
            else "at_least_one_peak_remains_mesh_sensitive"),
        "physics":f"linear static, one Boolean-fused solid, {element_type}; fixed bottom faces",
        "engineering_validation":"not_established",
        "notice":"Mesh trends and equilibrated solver results are not independent model validation or a certified factor of safety."
    }
    (root/"convergence_summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    (root/"CONVERGENCE_REPORT.md").write_text(report_markdown(report),encoding="utf-8")
    with (root/"convergence_summary.csv").open("w",newline="",encoding="utf-8") as fp:
        writer=csv.writer(fp)
        writer.writerow(["case","element_type","requested_mesh_mm","nodes","tetrahedra",
                         "max_displacement_mm","peak_von_mises_mpa",
                         "force_balance_relative_error"])
        for row in rows:
            for i,size in enumerate(row["mesh_sizes_mm"]):
                writer.writerow([row["key"],element_type,size,row["nodes"][i],row["elements"][i],
                                 row["max_displacements_mm"][i],row["peak_von_mises_mpa"][i],
                                 row["equilibrium_relative_errors"][i]])
    return report


def main():
    parser=argparse.ArgumentParser(description="Real Gmsh/CalculiX frame mesh-convergence suite")
    parser.add_argument("--out",default="runs/frame_convergence")
    parser.add_argument("--element-type",choices=("C3D4","C3D10"),default="C3D4")
    parser.add_argument("--cases",nargs="+",choices=[s.key for s in STUDIES])
    parser.add_argument("--meshes",nargs="+",type=float,default=DEFAULT_MESHES_MM)
    parser.add_argument("--displacement-tolerance",type=float,default=.05)
    parser.add_argument("--peak-stress-tolerance",type=float,default=.10)
    args=parser.parse_args()
    selected=tuple(s for s in STUDIES if args.cases is None or s.key in args.cases)
    report=run_frame_convergence(args.out,sizes_mm=args.meshes,
        displacement_tolerance=args.displacement_tolerance,
        peak_stress_tolerance=args.peak_stress_tolerance,
        specimens=selected, element_type=args.element_type)
    print(report_markdown(report))
    print(f"Saved native evidence in {args.out}")


if __name__=="__main__":
    main()
