"""Explicit reviewed Joint Matrix -> narrowly scoped two-STEP-solid contact.

This DOES NOT make arbitrary 'Welded'/'Bolted' labels into solver physics.
It joins the existing CAD-mate editor to the already verified two-block
C3D10 compression/opening CalculiX experiment, with STEP hash, component,
face IDs and single-joint identity checked before any solve.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .joint_matrix import validate_matrix


def reviewed_contact_plan(matrix, step_file):
    validate_matrix(matrix)
    path=Path(step_file)
    if not path.is_file() or path.suffix.lower() not in (".step",".stp"):
        raise ValueError("An existing source STEP is required")
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if matrix.get("source_sha256")!=digest:
        raise ValueError("Joint Matrix STEP hash mismatches source CAD; rescan the actual assembly")
    parts=matrix.get("components")
    rows=matrix.get("rows")
    if not isinstance(parts,list) or len(parts)!=2 or not isinstance(rows,list) or len(rows)!=1:
        raise ValueError("Experimental contact bridge needs exactly two parts and one candidate joint")
    by_id={p.get("id"):p for p in parts if isinstance(p,dict)}
    if len(by_id)!=2 or any(type(i) is not int or i<=0 for i in by_id):
        raise ValueError("CAD assembly component IDs must be unique positive integers")
    ground=matrix.get("ground_component")
    if ground not in by_id:
        raise ValueError("Joint Matrix has no grounded component")
    row=rows[0]
    if row.get("joint_type")!="Contact only" or row.get("joint_confirmation")!="explicit_user_choice":
        raise ValueError("Contact only must be an explicit reviewed human-selected joint")
    if row.get("mechanical_model")!="experimental_separable_contact":
        raise ValueError("Only the experimental separable-contact physics model is mapped")
    if row.get("candidate_kind")!="coincident_planar_faces":
        raise ValueError("Only coincident planar CAD face evidence is supported")
    overlap=row.get("overlap_area_bbox_mm2")
    if type(overlap) not in (int,float) or not math.isfinite(overlap) or overlap<=0:
        raise ValueError("A finite positive contact overlap estimate is required")
    a,b=row.get("component_a"),row.get("component_b")
    if {a,b}!=set(by_id) or a==b:
        raise ValueError("Joint must connect exactly the two source STEP solids")
    fa,fb=row.get("face_a"),row.get("face_b")
    if not all(type(f) is int and f>0 for f in (fa,fb)) or fa==fb:
        raise ValueError("Separate STEP contact requires distinct positive CAD face tags")
    centers={}
    for comp in parts:
        v=comp.get("center_mm")
        if not isinstance(v,(list,tuple)) or len(v)!=3 or not all(
            type(x) in (int,float) and math.isfinite(x) for x in v
        ):
            raise ValueError("Component centers required to orient contact")
        centers[comp["id"]]=v
    low,high=sorted(by_id,key=lambda key:centers[key][2])
    if centers[low][2]>=centers[high][2] or ground!=low:
        raise ValueError("Controlled experiment requires grounded lower solid and upper contact pad")
    faces={a:fa,b:fb}
    return {
        "schema":"ezfea.reviewed_contact_plan.v1",
        "joint_id":row["joint_id"],
        "source_step_sha256":digest,
        "base_component":low, "pad_component":high,
        "base_face":faces[low],"pad_face":faces[high],
        "model":"experimental_separable_contact",
        "review_status":"explicit_user_choice",
        "limitation":"Controlled two stacked coaxial parts with axial compression and opening; not general assemblies",
    }


def run_reviewed_contact(step_file, matrix_file, output_root, *, mesh_size_mm=7.):
    from .contact_step import run_step_contact
    matrix=json.loads(Path(matrix_file).read_text(encoding="utf-8"))
    plan=reviewed_contact_plan(matrix,step_file)
    root=Path(output_root)
    root.mkdir(parents=True,exist_ok=True)
    (root/"reviewed_joint_plan.json").write_text(json.dumps(plan,indent=2)+"\n",encoding="utf-8")
    # The actual CalculiX path checks these exact face IDs against imported CAD.
    return run_step_contact(root,mesh_size_mm=mesh_size_mm,
                            source_step=step_file,joint_plan=plan)


def main():
    p=argparse.ArgumentParser(description="Narrow verified Joint Matrix to real STEP contact")
    p.add_argument("step",help="The exact STEP file originally scanned")
    p.add_argument("joint_matrix",help="Edited joint-matrix JSON with a confirmed contact model")
    p.add_argument("--out",default="runs/reviewed_contact")
    p.add_argument("--mesh",type=float,default=7.)
    args=p.parse_args()
    report=run_reviewed_contact(args.step,args.joint_matrix,args.out,mesh_size_mm=args.mesh)
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
