"""Small reproducible Warren truss STEP weldment demonstrator.

This fixture creates TWO explicitly different STEP interpretations:

1) separate_members.step: ten overlapping individually constructed solids.
   This illustrates multibody-weldment import, not coped production cuts,
   joined structural physics, or a usable contact/weld model.
2) fused_ideal_joints.step: all members and three fixture/load pads are
   BOOLEAN-FUSED into exactly one CAD volume, assuming perfectly continuous
   material at every intersection. This CAN use EZ-FEA's real native C3D10
   single-solid solver, but it does NOT calculate an actual fillet weld.

Dimensions mm, forces N, stress MPa. Artificial material E=200000 MPa,
nu=.26, nominal Fy=250 MPa. NOT a certified truss or weld specification.

Truss lies in XY, with thickness along Z. Two lower bearing pads use
left XYZ fixed and right YZ fixed; one upper pad receives a vertical load.
The restraint faces have finite area; this is a bounded demonstration rather
than an ideal mathematical pin/roller or a real foundation detail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .core import Analysis, FaceConstraint, FaceLoad, Material
from .mesh import inspect_step

SCHEMA="ezfea.warren_truss_example.v1"
SPAN=600.
HEIGHT=180.
BOTTOM_STATIONS=(0.,150.,300.,450.,600.)
TOP_STATIONS=(75.,225.,375.,525.)
CHORD_SIDE_MM=24.
WEB_SIDE_MM=18.
LOAD_N=1000.

def members():
    """Ten CAD solid members, all straight 3D solid square-section bars."""
    data=[
       {"id":"BOTTOM","kind":"chord","start":[0.,0.,0.],
        "end":[SPAN,0.,0.],"square_side_mm":CHORD_SIDE_MM},
       {"id":"TOP","kind":"chord","start":[TOP_STATIONS[0],HEIGHT,0.],
        "end":[TOP_STATIONS[-1],HEIGHT,0.],"square_side_mm":CHORD_SIDE_MM},
    ]
    chain=[]
    for i,t in enumerate(TOP_STATIONS):
        chain.extend((("B",i),("T",i)))
    chain.append(("B",4))
    def node(label):
        typ,i=label
        return (BOTTOM_STATIONS[i],0.,0.) if typ=="B" else (
            TOP_STATIONS[i],HEIGHT,0.)
    for index,(a,b) in enumerate(zip(chain,chain[1:]),1):
        data.append({"id":f"W{index:02d}","kind":"web",
                     "start":list(node(a)),"end":list(node(b)),
                     "square_side_mm":WEB_SIDE_MM})
    if len(data)!=10:
        raise AssertionError("Warren example should contain two chords and eight webs")
    return data


def _add_member(occ,member):
    a,b=member["start"],member["end"]
    dx=b[0]-a[0];dy=b[1]-a[1]
    length=math.hypot(dx,dy)
    if length<=0 or abs(a[2]-b[2])>1e-9:
        raise ValueError("Example members must be planar, nonzero segments")
    size=member["square_side_mm"]
    # Short overlap at each intersection models fused continuity only,
    # not precisely mitered or welded tube ends.
    ext=7. if member["kind"]=="web" else 0.
    tag=occ.addBox(-ext,-size/2,-size/2,length+2*ext,size,size)
    theta=math.atan2(dy,dx)
    occ.rotate([(3,tag)],0,0,0,0,0,1,theta)
    occ.translate([(3,tag)],a[0],a[1],a[2])
    return tag


def _build(step,*,fused):
    import gmsh
    step=Path(step)
    step.parent.mkdir(parents=True,exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.model.add("EZ-FEA_Warren_idealized_"+("fused" if fused else "separate"))
        occ=gmsh.model.occ
        parts=[(3,_add_member(occ,m)) for m in members()]
        if fused:
            # Distinct bearing faces on two physically separated lower pads
            # and a top load pad provide real selectable STEP CAD surfaces.
            parts.extend([
                (3,occ.addBox(-18,-37,-15,36,29,30)),
                (3,occ.addBox(SPAN-18,-37,-15,36,29,30)),
                (3,occ.addBox(SPAN/2-20,188,-15,40,19,30)),
            ])
            united,_=occ.fuse(parts[:1],parts[1:],removeObject=True,removeTool=True)
            occ.synchronize()
            if len(gmsh.model.getEntities(3))!=1 or len(united)!=1:
                raise ValueError("CAD union is not ONE continuous truss: cannot claim welded physics")
        else:
            occ.synchronize()
            if len(gmsh.model.getEntities(3))!=len(parts):
                raise ValueError("Independent weldment solids unexpectedly merged")
        gmsh.write(str(step))
    finally:
        gmsh.finalize()
    return step


def generate_example(root="runs/truss_example"):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    separate=_build(root/"separate_members.step",fused=False)
    fused=_build(root/"fused_ideal_joints.step",fused=True)
    manifest={
        "schema":SCHEMA,
        "steel_geometry":"solid square-section bars, not hollow RHS/HSS tubing",
        "span_mm":SPAN,"rise_mm":HEIGHT,
        "members":members(),"member_count":len(members()),
        "separate":{
            "step":separate.name,"sha256":hashlib.sha256(separate.read_bytes()).hexdigest(),
            "solids":10,"analysis":"not_supported_by_single_solid_backend",
            "warning":"Individual overlapping CAD members; no actual weld, tie, miter or load transfer defined",
        },
        "fused":{
            "step":fused.name,"sha256":hashlib.sha256(fused.read_bytes()).hexdigest(),
            "solids":1,"analysis":"supported_as_idealized_continuous_solid",
            "extra_geometry":"two lower bearing pads plus central top load pad",
            "warning":"Mathematical union; locally assumes perfect weld continuity, does not verify weld throat/connection strength",
        },
        "nominal_material":{
            "elastic_modulus_mpa":200000.,
            "poisson_ratio":.26,
            "nominal_yield_mpa":250.,
        },
        "applied_force_n":[0.,-LOAD_N,0.],
        "design_approved":False,
    }
    (root/"GEOMETRY.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def select_faces(source):
    """Select the three UNIQUE original CAD faces by ground-truth pads.

    The first two have horizontal bottom planes at Y=-37 near each support.
    The loaded top plane is at Y=207 near the span's midpoint.
    """
    faces=inspect_step(source)
    def plane_at(y,x):
        valid=[
            face for face in faces
            if abs(face.bbox_mm[1]-y)<.005
            and abs(face.bbox_mm[4]-y)<.005
            and abs(face.center_mm[0]-x)<5.
            and abs(face.center_mm[2])<3.
        ]
        if len(valid)!=1:
            raise ValueError(f"Cannot identify unique original CAD pad face at (x={x}, y={y})")
        return valid[0].tag
    left=plane_at(-37.,0.)
    right=plane_at(-37.,SPAN)
    loaded=plane_at(207.,SPAN/2)
    if len({left,right,loaded})!=3:
        raise ValueError("Support/load CAD face IDs are not distinct")
    return {"left":left,"right":right,"load":loaded}


def analysis_case(source,faces,mesh_size_mm=16.):
    if not math.isfinite(mesh_size_mm) or mesh_size_mm<=0:
        raise ValueError("Mesh size must be finite and positive")
    return Analysis(
        str(Path(source).resolve()),0,0,(0.,0.,0.),mesh_size_mm,
        material=Material(name="A36 illustrative isotropic elastic steel",
                          elastic_modulus_mpa=200000.,
                          poisson_ratio=.26,yield_mpa=250.),
        connections=(
            FaceConstraint(faces["left"],(1,2,3)),
            FaceConstraint(faces["right"],(2,3)),
        ),
        loads=(FaceLoad(faces["load"],(0.,-LOAD_N,0.)),),
        element_type="C3D10",
    )


def solve_example(root="runs/truss_example",*,mesh_size_mm=16.):
    from .workflow import run_case
    root=Path(root)
    manifest=generate_example(root)
    source=root/manifest["fused"]["step"]
    faces=select_faces(source)
    (root/"FACE_SELECTION.json").write_text(json.dumps(
        {"schema":"ezfea.truss_face_selection.v1","source_step_sha256":manifest["fused"]["sha256"],
         "support_left_cad_face":faces["left"],"support_right_cad_face":faces["right"],
         "loaded_cad_face":faces["load"],
         "left_support_axes":"XYZ","right_support_axes":"YZ",
         "applied_force_n":[0.,-LOAD_N,0.]},indent=2)+"\n",encoding="utf-8")
    case=analysis_case(source,faces,mesh_size_mm)
    result_folder=run_case(case,root/"native_results")
    record=json.loads((result_folder/"case.json").read_text(encoding="utf-8"))
    results=record.get("results") or {}
    outcome={
        "schema":"ezfea.warren_truss_example_result.v1",
        "case_status":record["status"],
        "original_fused_source_sha256":manifest["fused"]["sha256"],
        "native_case_dir":str(result_folder.relative_to(root)),
        "mesh_size_mm":mesh_size_mm,
        "element_count":record.get("mesh",{}).get("elements"),
        "maximum_displacement_mm":results.get("max_displacement_mm"),
        "peak_integration_point_von_mises_mpa":results.get("max_von_mises_mpa"),
        "force_balance_check":results.get("force_balance_check"),
        "moment_balance_check":results.get("moment_balance_check"),
        "force_balance_relative_error":results.get("force_balance_relative_error"),
        "moment_balance_relative_error":results.get("moment_balance_relative_error"),
        "scope":"continuous-fused-solid linear static only; NOT a weld validation or member buckling check",
    }
    (root/"TRUSS_RESULT.json").write_text(json.dumps(outcome,indent=2)+"\n",encoding="utf-8")
    summary=[
        "# EZ-FEA Warren truss weldment example","",
        "A real CAD-and-solver experiment for an illustrative square-solid steel truss.",
        "A 10-member multibody STEP illustrates current import limits. A separate",
        "fused continuous-solid STEP demonstrates today's existing real C3D10 solver.",
        "",
        f"- Span/rise: {SPAN:g} / {HEIGHT:g} mm; nominal downward top load {LOAD_N:g} N",
        f"- Member sections: {CHORD_SIDE_MM:g} mm square chords, {WEB_SIDE_MM:g} mm square webs (solid bars, not HSS)",
        "- Left pad restrained XYZ; right pad restrained YZ, both are finite-area restraints",
        f"- CAD support/load faces: {faces['left']} / {faces['right']} / {faces['load']}",
        f"- Mesh elements: {outcome['element_count']}",
        f"- Native solve status: {outcome['case_status']}",
        f"- Maximum displacement: {outcome['maximum_displacement_mm']} mm",
        f"- Peak integration-point von Mises: {outcome['peak_integration_point_von_mises_mpa']} MPa",
        f"- Force/moment balance: {outcome['force_balance_check']} / {outcome['moment_balance_check']}",
        "",
        "**Important:** Fusion means joints are mathematically continuous. It does not",
        "model weld throat, weld defects, actual RHS tube walls, joint failure,",
        "local buckling, fabrication cuts, or a professionally verified design.",
        "Read native_results/*/case.json and analysis.frd/.dat for actual source evidence.",
    ]
    (root/"RESULTS.md").write_text("\n".join(summary)+"\n",encoding="utf-8")
    if record["status"]!="completed":
        raise ValueError("Native truss solve requires force/moment balance review")
    return outcome


def main():
    parser=argparse.ArgumentParser(description="Create and optionally solve an illustrative welded truss")
    parser.add_argument("--out",default="runs/truss_example")
    parser.add_argument("--solve",action="store_true")
    parser.add_argument("--mesh",type=float,default=16.)
    args=parser.parse_args()
    if args.solve:
        print(json.dumps(solve_example(args.out,mesh_size_mm=args.mesh),indent=2))
    else:
        print(json.dumps(generate_example(args.out),indent=2))


if __name__=="__main__":
    main()
