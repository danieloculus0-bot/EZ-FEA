"""Real native functional acceptance: STEP in -> checked CalculiX reports out.

Unlike mock-only tests, every positive case executes the SAME native child
worker as EZ-FEA desktop SOLVE. It exercises a cantilever, actual drilled
mounting plate with topology evidence, and two-support Warren truss, plus a
multibody input that MUST be rejected rather than secretly fused.

No example establishes engineering certification, true bolt/weld behavior or
mesh convergence. Failing scenarios remain archived; suite exits nonzero.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import traceback

from .core import Face
from .demo import make_demo_step
from .desktop_controller import (
    build_analysis,build_multi_analysis,run_native_child_process,
)
from .desktop_preview import extract_step_faces,validate_preview
from .fixture_examples import drilled_plate_step
from .fixture_suggestions import check_hints
from .mesh import inspect_step
from .truss_example import generate_example,select_faces,analysis_case

SCHEMA="ezfea.functional_acceptance.v1"


def _form(force,mesh=7.):
    return {
        "fx":force[0],"fy":force[1],"fz":force[2],
        "mesh":str(mesh),"e":"200000","nu":"0.26",
        "yield_mpa":"250","element_type":"C3D10",
    }


def _verified_run(case,output):
    result=run_native_child_process(case,output)
    record=result["record"]
    reported=result["summary"]
    source=Path(case.step_file)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if record["input_sha256"]!=digest:
        raise ValueError("Native solver source digest does not match generated STEP")
    if (record["status"]!="completed" or
        reported["force_balance"].split()[0]!="PASS" or
        reported["moment_balance"].split()[0]!="PASS"):
        raise ValueError("Native solution lacks force or moment equilibrium")
    measured=record["results"]
    for key in ("max_displacement_mm","max_von_mises_mpa"):
        value=measured[key]
        if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
            raise ValueError(f"Native {key} is not finite and positive")
    if record["mesh"]["element_type"]!="C3D10" or record["mesh"]["elements"]<80:
        raise ValueError("Real C3D10 mesh absent or implausibly small")
    folder=result["folder"]
    for name in ("analysis.inp","analysis.dat","analysis.frd","solver.log","case.json","RESULTS.txt"):
        if not (folder/name).is_file():
            raise ValueError(f"Missing actual solver deliverable: {name}")
    actual_report=result["report"].read_text(encoding="utf-8")
    if "NOT VALIDATED FOR ENGINEERING SIGN-OFF" not in actual_report:
        raise ValueError("Human-readable report lacks engineering scope warning")
    return {
        "native_status":record["status"],
        "cad_sha256":digest,
        "element_type":"C3D10","elements":record["mesh"]["elements"],
        "maximum_displacement_mm":measured["max_displacement_mm"],
        "maximum_von_mises_mpa":measured["max_von_mises_mpa"],
        "force_equilibrium":measured["force_balance_check"],
        "moment_equilibrium":measured["moment_balance_check"],
        "native_report":str(result["report"].relative_to(output.parent)),
        "native_case_path":str(folder.relative_to(output.parent)),
    }


def _cantilever(root):
    source=make_demo_step(root/"input"/"cantilever.step")
    faces=inspect_step(source,require_single_solid=True)
    i=min(range(len(faces)),key=lambda n:faces[n].center_mm[0])
    j=max(range(len(faces)),key=lambda n:faces[n].center_mm[0])
    if i==j:
        raise ValueError("Could not find distinct cantilever end faces")
    case=build_analysis(source,faces,i,j,_form((0.,-100.,0.)))
    solved=_verified_run(case,root/"native")
    return {**solved,"support_face":faces[i].tag,
            "load_face":faces[j].tag,"total_load_n":[0.,-100.,0.]}


def _hole_plate(root):
    source=drilled_plate_step(root/"input"/"two_through_holes.step")
    faces=inspect_step(source,require_single_solid=True)
    preview=extract_step_faces(source)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    validate_preview(preview,expected_sha=digest,expected_faces=[f.tag for f in faces])
    hints=preview["fixture_hints"]
    suggested=check_hints(hints,source_sha256=digest,face_ids=[f.tag for f in faces])
    if not suggested or hints["cylindrical_face_count"]<2:
        raise ValueError("Actual drilled attachment holes were not detected")
    # The two through-holes meet opposite planar plate faces. Confirm ONE
    # suggestion for this test; automatically fixing both would be wrong.
    support=suggested[0]
    fhold=next(face for face in faces if face.tag==support)
    if len(suggested)!=1 or not math.isclose(
        abs(fhold.center_mm[2]-5),5.,abs_tol=.01):
        raise ValueError("A two-hole plate should suggest exactly one original outer mounting plane")
    opposites=[
        (n,face) for n,face in enumerate(faces)
        if face.tag!=support
        and abs(face.bbox_mm[5]-face.bbox_mm[2])<.001
        and abs(face.center_mm[2]-fhold.center_mm[2])>8.
    ]
    if len(opposites)!=1:
        raise ValueError("Opposite loaded plate face is not uniquely identifiable")
    load_index,loaded=opposites[0]
    direction=-1. if loaded.center_mm[2]>fhold.center_mm[2] else 1.
    load=[0.,0.,direction*150.]
    case=build_multi_analysis(source,faces,
        [{"face":support,"axes":[1,2,3]}],load_index,_form(load,mesh=7.))
    solved=_verified_run(case,root/"native")
    return {**solved,
        "cylindrical_feature_count":hints["cylindrical_face_count"],
        "suggested_mounting_faces":suggested,
        "suggestion_reviewed_for_test":True,
        "actual_bolt_and_contact_physics":False,
        "loaded_face":loaded.tag,
        "total_load_n":load,
    }


def _warren_truss(root):
    fixture=generate_example(root/"input")
    separate=root/"input"/fixture["separate"]["step"]
    try:
        inspect_step(separate,require_single_solid=True)
    except ValueError as exc:
        if "separate solids" not in str(exc):
            raise
        rejects_multiple_solids=True
    else:
        raise ValueError("Danger: unconnected multibody weldment was accepted as one solid")
    source=root/"input"/fixture["fused"]["step"]
    faces=select_faces(source)
    case=analysis_case(source,faces,mesh_size_mm=16.)
    solved=_verified_run(case,root/"native")
    report=Path(root/solved["native_report"]).read_text(encoding="utf-8")
    for wanted in (
        f"CAD face {faces['left']}: restrained global directions X,Y,Z",
        f"CAD face {faces['right']}: restrained global directions Y,Z",
        f"CAD face {faces['load']}: total XYZ force",
        "Total prescribed XYZ force (N): [0.0, -1000.0, 0.0]",
    ):
        if wanted not in report:
            raise ValueError("The actual multi-face human report omitted "+wanted)
    return {**solved,
        "members":fixture["member_count"],"multibody_import_rejected":rejects_multiple_solids,
        "separate_members_sha256":fixture["separate"]["sha256"],
        "fused_idealized_sha256":fixture["fused"]["sha256"],
        "support_face_axes":{
            str(faces["left"]):"XYZ",str(faces["right"]):"YZ",
        },
        "loaded_face":faces["load"],"total_load_n":[0.,-1000.,0.],
        "weld_strength_verified":False,
    }


def run_functional_pass(output="runs/functional_pass"):
    root=Path(output).resolve()
    root.mkdir(parents=True,exist_ok=True)
    results=[]
    failed=0
    for name,fn in (
        ("cantilever_direct_step",_cantilever),
        ("drilled_plate_mounting_evidence",_hole_plate),
        ("two_support_warren_truss",_warren_truss),
    ):
        folder=root/name
        folder.mkdir(exist_ok=True)
        item={"name":name,"state":"pending"}
        try:
            item.update(fn(folder))
            item["state"]="passed"
        except Exception as exc:
            failed+=1
            item["state"]="failed"
            item["reason"]=str(exc)
            (folder/"failure_trace.txt").write_text(
                traceback.format_exc(),encoding="utf-8")
        (folder/"functional_result.json").write_text(
            json.dumps(item,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        results.append(item)
    ledger={
        "schema":SCHEMA,"executed":len(results),"passed":len(results)-failed,
        "failed":failed,"origin":"actual STEP Gmsh C3D10 CalculiX child-process solves",
        "results":results,"general_multibody_weld_physics":False,
        "actual_fastener_contact_validated":False,
        "engineer_design_approval":False,
    }
    (root/"functional_results.json").write_text(
        json.dumps(ledger,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    if failed:
        raise RuntimeError(f"{failed}/{len(results)} real native scenarios failed; inspect functional_results.json")
    return ledger


def main():
    p=argparse.ArgumentParser(description="Real EZ-FEA functional acceptance, preserves raw CAD/solver evidence")
    p.add_argument("--out",default="runs/functional_pass")
    a=p.parse_args()
    answer=run_functional_pass(a.out)
    print(json.dumps({
        "passed":answer["passed"],"failed":answer["failed"],
        "evidence":str(Path(a.out).resolve()/"functional_results.json"),
    },indent=2))


if __name__=="__main__":
    main()
