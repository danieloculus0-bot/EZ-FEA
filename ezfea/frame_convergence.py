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
import shutil

from .convergence import run_refinement, relative_change
from .frame_benchmarks import STUDIES, create_step, case_from_step, geometry_definition_sha256
from .stress_probes import frame_stress_probes, RECOVERY


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
        probe_data=[r.get("fixed_coordinate_stress") for r in records]
        fixed_probe_trends=None
        if any(p is not None for p in probe_data):
            if any(not isinstance(p,dict) or p.get("schema")!="ezfea.fixed_stress_probes.v1"
                   for p in probe_data):
                raise ValueError("Fixed-coordinate stress evidence missing on one or more meshes")
            names=list(probe_data[0]["probes"])
            if not names or any(set(p["probes"])!=set(names) for p in probe_data):
                raise ValueError("Fixed stress probe names changed across mesh sizes")
            fixed_probe_trends=[]
            for name in names:
                readings=[item["probes"][name] for item in probe_data]
                positions=[reading["coordinate_mm"] for reading in readings]
                if any(x!=positions[0] for x in positions):
                    raise ValueError(f"{name}: physical XYZ probe moved between refinements")
                if any(reading.get("recovery")!=RECOVERY or
                       not isinstance(reading.get("von_mises_mpa"),(int,float)) or
                       not math.isfinite(reading["von_mises_mpa"]) or
                       reading["von_mises_mpa"]<0 for reading in readings):
                    raise ValueError(f"{name}: unavailable native probe tensor")
                recovered=[reading["von_mises_mpa"] for reading in readings]
                changes=[relative_change(a,b) for a,b in zip(recovered,recovered[1:])]
                quality=[reading.get("location_quality") for reading in readings]
                healthy=all(q=="inside_element" for q in quality)
                fixed_probe_trends.append({
                    "name":name,
                    "coordinate_mm":positions[0],
                    "recovery":RECOVERY,
                    "von_mises_mpa":recovered,
                    "adjacent_relative_changes":changes,
                    "last_change_pct":100*changes[-1],
                    "host_element_ids":[r["host_element_id"] for r in readings],
                    "location_quality":quality,
                    "min_barycentric_margins":[r["inside_corner_tetra_margin"] for r in readings],
                    "observation":(
                        "near_element_boundary_check_probe" if not healthy
                        else "limited_sensitivity_at_checked_mesh_sizes"
                        if increasing and all(v<=peak_stress_tolerance for v in changes[-2:])
                        else "mesh_sensitive_at_checked_mesh_sizes"
                    ),
                })
        diagnostics=[r.get("stress_distance_bands") for r in records]
        band_trends=None
        peak_distances=None
        if all(isinstance(d,dict) and d.get("status")=="plane_distance_diagnostic"
               for d in diagnostics):
            limits=diagnostics[0]["excluded_near_fixture_mm"]
            for d in diagnostics:
                if (d["excluded_near_fixture_mm"] != limits or
                    d["fixture_plane_axis"] != diagnostics[0]["fixture_plane_axis"] or
                    abs(d["fixture_plane_coordinate_mm"] -
                        diagnostics[0]["fixture_plane_coordinate_mm"]) > 1e-6):
                    raise ValueError("Support stress reference zone changed across meshes")
            peak_distances=[d["global_peak_host_tet_centroid_distance_mm"] for d in diagnostics]
            band_trends=[]
            for i,limit in enumerate(limits):
                values=[d["outside_band_max_mpa"][i] for d in diagnostics]
                if any(x is None or not isinstance(x,(int,float)) or
                       not math.isfinite(x) or x<=0 for x in values):
                    band_trends.append({"min_distance_mm":limit,
                                        "observation":"insufficient_interior_gauss_points"})
                    continue
                shifts=[relative_change(a,b) for a,b in zip(values,values[1:])]
                band_trends.append({
                    "min_distance_mm":limit,
                    "max_stress_mpa":values,
                    "adjacent_relative_changes":shifts,
                    "last_change_pct":100*shifts[-1],
                    "observation":("limited_sensitivity_at_checked_mesh_sizes"
                                   if increasing and all(v<=peak_stress_tolerance
                                                         for v in shifts[-2:])
                                   else "mesh_sensitive_at_checked_mesh_sizes"),
                })
        load_band_trends=None
        peak_load_distances=None
        if (band_trends is not None and
            all(d.get("outside_load_band_max_mpa") is not None for d in diagnostics)):
            ref_axis=diagnostics[0]["load_plane_axis"]
            ref_position=diagnostics[0]["load_plane_coordinate_mm"]
            if any(d["load_plane_axis"]!=ref_axis or
                   abs(d["load_plane_coordinate_mm"]-ref_position)>1e-6
                   for d in diagnostics):
                raise ValueError("Load plane changed across mesh refinements")
            peak_load_distances=[
                d["global_peak_host_tet_centroid_distance_from_load_mm"]
                for d in diagnostics]
            load_band_trends=[]
            for i,limit in enumerate(limits):
                values=[d["outside_load_band_max_mpa"][i] for d in diagnostics]
                if any(v is None or not isinstance(v,(int,float)) or
                       not math.isfinite(v) or v<=0 for v in values):
                    load_band_trends.append({"min_distance_mm":limit,
                                             "observation":"insufficient_interior_gauss_points"})
                    continue
                changes=[relative_change(a,b) for a,b in zip(values,values[1:])]
                load_band_trends.append({
                    "min_distance_mm":limit,
                    "max_stress_mpa":values,
                    "adjacent_relative_changes":changes,
                    "last_change_pct":100*changes[-1],
                    "observation":("limited_sensitivity_at_checked_mesh_sizes"
                                   if increasing and all(v<=peak_stress_tolerance
                                                         for v in changes[-2:])
                                   else "mesh_sensitive_at_checked_mesh_sizes"),
                })
        out.append({
            "fixed_coordinate_stress_trends":fixed_probe_trends,
            "load_stress_band_trends":load_band_trends,
            "peak_host_tet_centroid_distance_from_load_mm":peak_load_distances,
            "stress_band_trends":band_trends,
            "peak_host_tet_centroid_distance_mm":peak_distances,
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
        f"Element type: {report.get('element_type','C3D4')}. These are real Gmsh + CalculiX solves, not BEAN estimates.",
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
    if any(r.get("fixed_coordinate_stress_trends") for r in report["studies"]):
        lines.extend([
            "",
            "### Fixed XYZ stress probes across successive meshes",
            "",
            "Each XYZ is held constant in physical millimeters, NOT a changing",
            "location of the mesh-global stress maximum. Measured native",
            "integration-point *tensors* are averaged within the host tetrahedron.",
            "This gives a piecewise-constant element recovery, NOT exact",
            "pointwise C3D10 Gauss interpolation; boundaries are flagged.",
            "",
            "| Case | Probe | X,Y,Z (mm) | Last Δ von Mises | Location / trend |",
            "|---|---|---|---:|---|",
        ])
        for row in report["studies"]:
            for pr in row.get("fixed_coordinate_stress_trends") or []:
                xyz=", ".join(f"{x:.2f}" for x in pr["coordinate_mm"])
                lines.append(
                    f"| {row['key']} | {pr['name']} | {xyz} | "
                    f"{pr['last_change_pct']:.3g}% | {pr['observation']} |"
                )
        lines.extend([
            "",
            "A low last-step change is not independent material validation;",
            "stress at a fixed point remains approximate and can be affected",
            "by local mesh topology or nearby stress discontinuities.",
        ])
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
        "> stress may change substantially at fully fixed corners. First-order C3D4",
        "> tetrahedra may be overly stiff in bending; quadratic C3D10 does not",
        "> eliminate stress singularities. No physical test, independent benchmark,",
        "> or qualified engineer has validated these designs. Not for engineering sign-off.",
    ])
    return "\n".join(lines)+"\n"


def run_frame_convergence(output_root="runs/frame_convergence", *,
                          sizes_mm=DEFAULT_MESHES_MM,
                          displacement_tolerance=.05,
                          peak_stress_tolerance=.10,
                          specimens=STUDIES,
                          element_type="C3D4",
                          reuse_cad_from=None):
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
        destination=frame/"cad"/(spec.key+".step")
        if reuse_cad_from is not None:
            source=Path(reuse_cad_from)/spec.key/"cad"/(spec.key+".step")
            if not source.is_file():
                raise FileNotFoundError(f"Matched CAD reference missing: {source}")
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,destination)
            step=destination
        else:
            step=create_step(spec,destination)
        case=replace(case_from_step(spec,step,mesh_size_mm=sizes[0]),
                     element_type=element_type)
        raw=run_refinement(case,frame/"refinement",
                           sizes_mm=sizes,displacement_tolerance=displacement_tolerance,
                           fixed_stress_probes=frame_stress_probes(spec))
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
    parser.add_argument("--reuse-cad-from",default=None,
                        help="Load exact same STEP bytes generated by a prior element-order suite")
    parser.add_argument("--meshes",nargs="+",type=float,default=DEFAULT_MESHES_MM)
    parser.add_argument("--displacement-tolerance",type=float,default=.05)
    parser.add_argument("--peak-stress-tolerance",type=float,default=.10)
    args=parser.parse_args()
    selected=tuple(s for s in STUDIES if args.cases is None or s.key in args.cases)
    report=run_frame_convergence(args.out,sizes_mm=args.meshes,
        displacement_tolerance=args.displacement_tolerance,
        peak_stress_tolerance=args.peak_stress_tolerance,
        specimens=selected, element_type=args.element_type,
        reuse_cad_from=args.reuse_cad_from)
    print(report_markdown(report))
    print(f"Saved native evidence in {args.out}")


if __name__=="__main__":
    main()
