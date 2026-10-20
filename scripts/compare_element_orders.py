"""Compare *measured* C3D4 and C3D10 frame refinement evidence.

This is an apples-to-apples element study, not proof of engineering accuracy.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def compare_element_studies(linear, quadratic):
    if linear.get("schema")!="ezfea.frame_convergence.v1" or \
       quadratic.get("schema")!="ezfea.frame_convergence.v1":
        raise ValueError("Expected actual native convergence datasets")
    if linear.get("element_type")!="C3D4" or quadratic.get("element_type")!="C3D10":
        raise ValueError("First study must be C3D4; second must be C3D10")
    if linear.get("mesh_sizes_mm")!=quadratic.get("mesh_sizes_mm"):
        raise ValueError("Mesh refinements must use identical requested sizes")
    a={x["key"]:x for x in linear["studies"]}
    b={x["key"]:x for x in quadratic["studies"]}
    if set(a)!=set(b) or not a:
        raise ValueError("Specimen identities do not match")
    rows=[]
    for name in sorted(a):
        old,new=a[name],b[name]
        if old["specimen_definition_sha256"]!=new["specimen_definition_sha256"] or \
           old["step_sha256"]!=new["step_sha256"]:
            raise ValueError(name+": geometry or source STEP differs")
        for item in (old,new):
            if len(item["mesh_sizes_mm"])<3 or not item["increasing_element_counts"]:
                raise ValueError(name+": incomplete mesh progression")
            if item["max_force_balance_relative_error"] > .01:
                raise ValueError(name+": force equilibrium failed")
            if not all(math.isfinite(v) and v>0 for v in item["max_displacements_mm"]):
                raise ValueError(name+": invalid displacement")
        rows.append({
            "key":name,
            "C3D4_fine_max_displacement_mm":old["max_displacements_mm"][-1],
            "C3D10_fine_max_displacement_mm":new["max_displacements_mm"][-1],
            "C3D4_fine_displacement_change_pct":old["fine_displacement_delta_pct"],
            "C3D10_fine_displacement_change_pct":new["fine_displacement_delta_pct"],
            "C3D4_fine_peak_stress_change_pct":old["fine_peak_stress_delta_pct"],
            "C3D10_fine_peak_stress_change_pct":new["fine_peak_stress_delta_pct"],
            "C3D4_displacement_observation":old["displacement_observation"],
            "C3D10_displacement_observation":new["displacement_observation"],
            "C3D4_tetrahedra":old["elements"],
            "C3D10_tetrahedra":new["elements"],
            "C3D4_nodes":old["nodes"],
            "C3D10_nodes":new["nodes"],
            "fine_displacement_step_improved":(
                new["fine_displacement_delta_pct"] < old["fine_displacement_delta_pct"]
            ),
        })
    return {"schema":"ezfea.element_order_comparison.v1",
            "meshes_mm":linear["mesh_sizes_mm"],
            "cases":rows,
            "engineering_validation":"not_established",
            "disclaimer":"C3D10 may improve bending fidelity, but comparing element refinement is NOT proof of physical accuracy. Peak stresses near clamped corners can be singular."}


def to_markdown(result):
    lines=[
        "# C3D4 versus C3D10 — genuine CalculiX element-order comparison",
        "",
        "Identical CAD source hashes, fixture conditions, loads, and mesh sizes.",
        "All entries originate in independent native Gmsh/CalculiX calculations.",
        "",
        "| Case | C3D4 finest u (mm) | C3D10 finest u (mm) | C3D4 10→7 Δu | C3D10 10→7 Δu | C3D10 improved last step? |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in result["cases"]:
        lines.append(
            f"| {r['key']} | {r['C3D4_fine_max_displacement_mm']:.6g} | "
            f"{r['C3D10_fine_max_displacement_mm']:.6g} | "
            f"{r['C3D4_fine_displacement_change_pct']:.3f}% | "
            f"{r['C3D10_fine_displacement_change_pct']:.3f}% | "
            f"{'Yes' if r['fine_displacement_step_improved'] else 'No'} |"
        )
    lines.extend([
        "",
        "**Interpretation:** Element orders are distinct physics discretizations;",
        "do not treat either fine-grid solution as the known exact answer.",
        "Fine-step stability alone is not an independent analytical/experimental",
        "validation. Peak von Mises stresses at idealized clamps may diverge.",
        "",
        "**Engineering validation: NOT ESTABLISHED.**",
    ])
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--linear",required=True,type=Path)
    p.add_argument("--quadratic",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    linear=json.loads(a.linear.read_text(encoding="utf-8"))
    quadratic=json.loads(a.quadratic.read_text(encoding="utf-8"))
    result=compare_element_studies(linear,quadratic)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"comparison.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    md=to_markdown(result)
    (a.out/"COMPARISON.md").write_text(md,encoding="utf-8")
    print(md)


if __name__=="__main__":
    main()
