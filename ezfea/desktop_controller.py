"""A usable native STEP -> 3D solver -> human-readable result workflow.

The Tk interface is deliberately only a thin client. These functions have
headless tests and can be invoked without a desktop display or BEAN runtime.
This is single-solid linear-static FEA, NOT generic assembly/joint simulation.
"""
from __future__ import annotations

import importlib.util
from dataclasses import asdict, replace
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .core import Analysis, Material, FaceConstraint, FaceLoad
from .workflow import run_case


def preflight():
    """List missing native solver components, without running a fake solve."""
    missing=[]
    if importlib.util.find_spec("gmsh") is None:
        missing.append("Gmsh Python API missing. Install: python -m pip install -r requirements.txt")
    configured=os.environ.get("EZFEA_CCX")
    ccx=shutil.which(configured) if configured else (shutil.which("ccx") or shutil.which("ccx.exe"))
    if not ccx:
        missing.append("CalculiX 'ccx' executable missing. Install CalculiX and put ccx on PATH or set EZFEA_CCX.")
    return missing


def build_analysis(path,faces,fixed_index,loaded_index,form):
    """Validate *actual imported* CAD-face selections and user-provided values."""
    if not isinstance(form,dict):
        raise ValueError("Missing analysis settings")
    path=Path(path)
    if not path.is_file() or path.suffix.lower() not in (".step",".stp"):
        raise ValueError("Choose a real .step or .stp CAD file")
    if len(faces)<2:
        raise ValueError("Part needs at least two distinct CAD faces for this analysis")
    if type(fixed_index) is not int or type(loaded_index) is not int or not (
        0<=fixed_index<len(faces) and 0<=loaded_index<len(faces)):
        raise ValueError("Select both a fixed face and a loaded face")
    if fixed_index==loaded_index:
        raise ValueError("Fixed and loaded CAD faces must be different")
    expected=("fx","fy","fz","mesh","e","nu","yield_mpa","element_type")
    if set(form)!=set(expected):
        raise ValueError("Analysis settings have missing or unknown fields")
    data={}
    for key in expected[:-1]:
        try:
            data[key]=float(form[key])
        except (TypeError,ValueError,OverflowError) as exc:
            raise ValueError(f"{key}: enter a number in N, mm or MPa") from exc
        if not math.isfinite(data[key]):
            raise ValueError(f"{key}: finite value required")
    if form["element_type"] not in ("C3D4","C3D10"):
        raise ValueError("Choose C3D10 or C3D4 element type")
    if not any(data[x]!=0 for x in ("fx","fy","fz")):
        raise ValueError("Enter a nonzero applied force in at least one direction")
    case=Analysis(
        str(path.resolve()),faces[fixed_index].tag,faces[loaded_index].tag,
        (data["fx"],data["fy"],data["fz"]),data["mesh"],
        material=Material(
            elastic_modulus_mpa=data["e"],
            poisson_ratio=data["nu"],yield_mpa=data["yield_mpa"]),
        element_type=form["element_type"]
    )
    case.validate()
    return case


def build_multi_analysis(path, faces, supports, loaded_index, form):
    """Keep genuine multiple CAD support faces; never silently infer bolt physics.

    'supports' is a nonempty list of {"face":original_OCC_ID,"axes":[1,2,3]}
    entries. It can be seeded by planar/hole heuristics, but a human must
    verify any inferred restraint before this function is used to solve.
    """
    if not isinstance(supports,list) or not supports or len(supports)>64:
        raise ValueError("Select at least one held surface (maximum 64)")
    if type(loaded_index) is not int or not 0<=loaded_index<len(faces):
        raise ValueError("Select an actual loaded STEP face")
    tags={f.tag for f in faces}
    seen=set()
    constraints=[]
    for item in supports:
        if not isinstance(item,dict) or set(item)!={"face","axes"}:
            raise ValueError("Support requires face ID and restrained axes")
        face=item["face"]
        axes=item["axes"]
        if type(face) is not int or face not in tags or face in seen:
            raise ValueError("Support face is unknown or duplicated")
        if not isinstance(axes,(list,tuple)):
            raise ValueError("Support axis list is missing")
        candidate=FaceConstraint(face,tuple(axes))
        candidate.validate()
        seen.add(face)
        constraints.append(candidate)
    if faces[loaded_index].tag in seen:
        raise ValueError("Loaded surface cannot also be held")
    first_index=next(i for i,f in enumerate(faces) if f.tag==constraints[0].face)
    validated=build_analysis(path,faces,first_index,loaded_index,form)
    case=replace(validated,
                 fixed_face=0,loaded_face=0,force_n=(0.,0.,0.),
                 connections=tuple(constraints),
                 loads=(FaceLoad(faces[loaded_index].tag,validated.force_n),))
    case.validate()
    return case


def _measure(value,unit,digits=6):
    if value is None:
        return "not available"
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError("Numerical result is missing or not finite")
    return f"{value:.{digits}g} {unit}"


def result_summary(record):
    """Render only actual stored mesh and native CalculiX results."""
    if not isinstance(record,dict) or record.get("status") not in ("completed","needs_review"):
        raise ValueError("There is no completed native result to display")
    m=record.get("results")
    if not isinstance(m,dict):
        raise ValueError("Real CalculiX results are missing")
    required=("max_displacement_mm","max_von_mises_mpa",
              "force_balance_relative_error","moment_balance_relative_error",
              "force_balance_check","moment_balance_check")
    if any(k not in m for k in required):
        raise ValueError("Native result lacks required equilibrium or stress data")
    if m["force_balance_check"] not in ("pass","review") or m["moment_balance_check"] not in ("pass","review"):
        raise ValueError("Native balance status is missing")
    if record["status"]=="completed" and (m["force_balance_check"]!="pass" or
                                            m["moment_balance_check"]!="pass"):
        raise ValueError("A completed result cannot have unchecked equilibrium")
    for key in required[:4]:
        if type(m[key]) not in (int,float) or not math.isfinite(m[key]):
            raise ValueError(f"Native result {key} is invalid")
    count=record.get("mesh")
    if not isinstance(count,dict) or type(count.get("elements")) is not int or count["elements"]<=0:
        raise ValueError("Native mesh evidence is missing")
    ratio=m.get("nominal_yield_to_von_mises_ratio")
    if ratio is not None and (type(ratio) not in (int,float) or not math.isfinite(ratio)):
        raise ValueError("Nominal yield/stress ratio is invalid")
    status=record["status"]
    return {
        "status":status,
        "headline":"CALCULATION COMPLETED" if status=="completed" else "CHECK RESULTS — EQUILIBRIUM NEEDS REVIEW",
        "max_displacement":_measure(m["max_displacement_mm"],"mm"),
        "max_stress":_measure(m["max_von_mises_mpa"],"MPa"),
        "yield_ratio":_measure(ratio,"nominal yield/stress ratio") if ratio is not None else "not available",
        "force_balance":("PASS" if m["force_balance_check"]=="pass" else "REVIEW")+
                        f" · {100*m['force_balance_relative_error']:.3g}% residual",
        "moment_balance":("PASS" if m["moment_balance_check"]=="pass" else "REVIEW")+
                        f" · {100*m['moment_balance_relative_error']:.3g}% residual",
        "elements":str(count["elements"]),
        "element_type":count.get("element_type","unknown"),
        "engineering_notice":(
            "Peak integration-point stress can be mesh-sensitive. A yield/stress ratio is "
            "NOT an approved safety factor. Check supports, units, material and convergence."
        ),
    }


def save_readable_report(folder,record,summary):
    """Archive a plain-text report next to the original CAD and solver trace."""
    folder=Path(folder)
    if not folder.is_dir():
        raise ValueError("Analysis result folder not found")
    model=record.get("model",{})
    if not isinstance(model,dict):
        raise ValueError("Native model evidence missing")
    lines=[
        "EZ-FEA | NATIVE 3D STATIC ANALYSIS",
        "="*44,
        summary["headline"],
        "",
        "MODEL",
        f"Source STEP: {record.get('source_file','not reported')}",
        f"Source SHA256: {record.get('input_sha256','not reported')}",
        f"Units: {record.get('units','N/mm/MPa')}",
        f"Fixed CAD face: {model.get('fixed_face','not reported')}",
        f"Loaded CAD face: {model.get('loaded_face','not reported')}",
        f"Applied XYZ force (N): {model.get('force_n','not reported')}",
        f"Mesh target (mm): {model.get('mesh_size_mm','not reported')}",
        f"Elements: {summary['elements']} ({summary['element_type']})",
        f"Material: {model.get('material','not reported')}",
        "",
        "ACTUAL NATIVE CALCULIX MEASUREMENTS",
        f"Maximum displacement: {summary['max_displacement']}",
        f"Maximum von Mises integration-point stress: {summary['max_stress']}",
        f"Nominal yield/stress ratio: {summary['yield_ratio']}",
        f"Force equilibrium: {summary['force_balance']}",
        f"Moment equilibrium: {summary['moment_balance']}",
        "",
        summary["engineering_notice"],
        "NOT VALIDATED FOR ENGINEERING SIGN-OFF.",
        "Full raw source, analysis.inp, analysis.dat, analysis.frd and solver.log stay in this directory.",
        "",
    ]
    dest=folder/"RESULTS.txt"
    dest.write_text("\n".join(lines),encoding="utf-8")
    return dest


def run_desktop_case(case,output_root="runs/desktop"):
    """Do the native analysis and return a checked report, not a fake 'success'."""
    output=Path(run_case(case,output_root))
    meta_path=output/"case.json"
    if not meta_path.is_file():
        raise ValueError("Native analysis did not produce case.json")
    record=json.loads(meta_path.read_text(encoding="utf-8"))
    summary=result_summary(record)
    report=save_readable_report(output,record,summary)
    return {"folder":output,"report":report,"summary":summary,"record":record}


def run_native_child_process(case,output_root="runs/desktop"):
    """Keep Tk responsive WITHOUT initializing Gmsh in a background thread.

    The child process runs the real verified native workflow on its own main
    thread. A returned success requires a checked response and actual report.
    """
    case.validate()
    root=Path(output_root).resolve()
    request={
        "schema":"ezfea.desktop_request.v1",
        "case":{
            "step_file":str(Path(case.step_file).resolve()),
            "fixed_face":case.fixed_face,
            "loaded_face":case.loaded_face,
            "force_n":list(case.force_n),
            "mesh_size_mm":case.mesh_size_mm,
            "material":asdict(case.material),
            "element_type":case.element_type,
        },
        "output_root":str(root),
    }
    if case.connections or case.loads:
        request["case"]["connections"]=[asdict(c) for c in case.connections]
        request["case"]["loads"]=[asdict(load) for load in case.loads]
    with tempfile.TemporaryDirectory(prefix="ezfea-worker-") as tmp:
        input_path=Path(tmp)/"request.json"
        output_path=Path(tmp)/"response.json"
        input_path.write_text(json.dumps(request,allow_nan=False),encoding="utf-8")
        try:
            completed=subprocess.run(
                [sys.executable,"-m","ezfea.desktop_worker",
                 str(input_path),str(output_path)],
                cwd=str(Path(__file__).resolve().parent.parent),
                capture_output=True,text=True,timeout=480,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Native solver exceeded runtime limit; inspect generated case files.") from exc
        if completed.returncode!=0:
            details=(completed.stderr or completed.stdout or "native worker failed").strip()
            raise RuntimeError("Native solver could not finish: "+details[-1800:])
        if not output_path.is_file():
            raise ValueError("Native worker exited without a solver result response")
        reply=json.loads(output_path.read_text(encoding="utf-8"))
    if (not isinstance(reply,dict) or
        reply.get("schema")!="ezfea.desktop_response.v1"):
        raise ValueError("Native worker returned an unknown result format")
    folder=Path(reply.get("folder",""))
    report=Path(reply.get("report",""))
    if not folder.is_dir() or not report.is_file() or report.parent!=folder:
        raise ValueError("Worker claims results, but actual solver outputs are missing")
    source=folder/"case.json"
    if not source.is_file():
        raise ValueError("Native analysis evidence file is missing")
    record=json.loads(source.read_text(encoding="utf-8"))
    verified=result_summary(record)
    if reply.get("summary")!=verified:
        raise ValueError("Desktop worker summary disagrees with actual CalculiX record")
    return {"folder":folder,"report":report,"summary":verified,"record":record}


def open_result_folder(folder):
    """User-driven file manager action; no shell execution or untrusted URL."""
    folder=Path(folder).resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Result location is not a directory")
    if os.name=="nt":
        os.startfile(str(folder))
    elif sys.platform=="darwin":
        subprocess.Popen(["open",str(folder)])
    else:
        subprocess.Popen(["xdg-open",str(folder)])
