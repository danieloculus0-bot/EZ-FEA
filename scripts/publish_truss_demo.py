"""Publish only source-checked REAL EZ-FEA Warren truss solver evidence.

Inputs are the outputs of ezfea.functional_pass, which invokes the same
native subprocess as the GUI. This generator exports a Gmsh tessellation of
the exact fused STEP, not a synthetic browser 'stress contour'. Browser
results always come from case.json; no interpolation or mock stress data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

SCHEMA="ezfea.truss_browser_evidence.v1"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verified_payload(functional_root,*,run_url,commit):
    root=Path(functional_root).resolve()
    ledger=_load(root/"functional_results.json")
    if ledger.get("schema")!="ezfea.functional_acceptance.v1" or ledger.get("failed")!=0:
        raise ValueError("Functional acceptance is not a passing real native run")
    rows=ledger.get("results")
    if not isinstance(rows,list) or len(rows)!=3 or any(row.get("state")!="passed" for row in rows):
        raise ValueError("Missing complete passing structural scenarios")
    row=next((entry for entry in rows if entry.get("name")=="two_support_warren_truss"),None)
    if row is None or row.get("multibody_import_rejected") is not True:
        raise ValueError("Truss experiment or multibody rejection not verified")
    base=root/"two_support_warren_truss"
    geometry=_load(base/"input"/"GEOMETRY.json")
    model_path=base/"input"/geometry["fused"]["step"]
    casepath=base/row["native_case_path"]/"case.json"
    original=_load(casepath)
    actual_hash=hashlib.sha256(model_path.read_bytes()).hexdigest()
    if (actual_hash!=geometry["fused"]["sha256"] or
        actual_hash!=row["cad_sha256"] or actual_hash!=original["input_sha256"]):
        raise ValueError("Published STEP/FEA source hashes do not agree")
    if (original["status"]!="completed" or row.get("native_status")!="completed" or
        original["mesh"]["element_type"]!="C3D10" or
        original["mesh"]["elements"]!=row["elements"] or
        original["results"]["force_balance_check"]!="pass" or
        original["results"]["moment_balance_check"]!="pass"):
        raise ValueError("Native solver record fails model/equilibrium verification")
    result=original["results"]
    for key,matching in (
        ("max_displacement_mm","maximum_displacement_mm"),
        ("max_von_mises_mpa","maximum_von_mises_mpa"),
    ):
        a,b=result[key],row[matching]
        if type(a) not in (int,float) or not math.isfinite(a) or a<=0 or a!=b:
            raise ValueError("Numerical truss result inconsistent with saved solver record")
    model=original["model"]
    if (len(model.get("connections",[]))!=2 or len(model.get("loads",[]))!=1 or
        [c["axes"] for c in model["connections"]] != [[1,2,3],[2,3]] or
        model["loads"][0]["force_n"] != [0.,-1000.,0.] or
        row["members"]!=10 or len(geometry["members"])!=10):
        raise ValueError("Truss fixture does not match physical experiment")
    if not (isinstance(run_url,str) and run_url.startswith(
        "https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/"
    ) and run_url.rsplit("/",1)[-1].isdigit()):
        raise ValueError("Provenance needs the exact successful workflow URL")
    if not isinstance(commit,str) or len(commit)<7:
        raise ValueError("Native source revision missing")
    return {
        "schema":SCHEMA,
        "title":"10-member Warren truss · actual native FEA",
        "source_run":run_url,
        "source_commit":commit,
        "source_step_sha256":actual_hash,
        "geometry":{
            "type":"fused_one_solid",
            "solid_member_section":"square solid bar; not hollow tubing",
            "member_count":10,
            "span_mm":geometry["span_mm"],
            "rise_mm":geometry["rise_mm"],
            "members":geometry["members"],
            "support_pads":{
                "left":{"position_mm":[0.,-37.,0.],"axes":"XYZ"},
                "right":{"position_mm":[600.,-37.,0.],"axes":"YZ"},
            },
            "load_pad":{"position_mm":[300.,207.,0.],"force_n":[0.,-1000.,0.]},
        },
        "native":{
            "mesh_type":"C3D10",
            "elements":row["elements"],
            "mesh_target_mm":model["mesh_size_mm"],
            "max_displacement_mm":result["max_displacement_mm"],
            "peak_von_mises_mpa":result["max_von_mises_mpa"],
            "force_balance_check":result["force_balance_check"],
            "moment_balance_check":result["moment_balance_check"],
            "force_balance_relative_error":result["force_balance_relative_error"],
            "moment_balance_relative_error":result["moment_balance_relative_error"],
        },
        "browser_preview":"tessellated original fused STEP; no native stress contour",
        "status":"archived_real_solver_result_not_live_browser_solve",
        "limits":[
            "Individual bars are idealized solid bars; not hollow RHS tubing.",
            "Fused joints are modeled as perfectly continuous steel, not real welds.",
            "Peak stress is a single mesh integration-point value, not a converged weld check.",
            "Fixture pads and prescribed translations are idealizations; not design sign-off.",
        ],
    },model_path


def export_surface_stl(step_path,target,mesh_size=13.):
    import gmsh
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.model.add("EZFEA authenticated one-solid Warren STEP surface")
        gmsh.option.setString("Geometry.OCCTargetUnit","MM")
        gmsh.model.occ.importShapes(str(step_path))
        gmsh.model.occ.synchronize()
        if len(gmsh.model.getEntities(3))!=1:
            raise ValueError("Browser STL must be sourced from the real fused one-solid STEP")
        gmsh.option.setNumber("Mesh.MeshSizeMin",mesh_size*.65)
        gmsh.option.setNumber("Mesh.MeshSizeMax",mesh_size)
        gmsh.model.mesh.generate(2)
        triangles=0
        for kind,_ in gmsh.model.getEntities(2):
            if kind!=2:continue
        for _,face in gmsh.model.getEntities(2):
            types,ids,_=gmsh.model.mesh.getElements(2,face)
            for etype,tags in zip(types,ids):
                if etype==2:triangles+=len(tags)
        if triangles<100 or triangles>200000:
            raise ValueError("Unexpected authentic CAD surface triangle budget")
        target.parent.mkdir(parents=True,exist_ok=True)
        gmsh.write(str(target))
    finally:
        gmsh.finalize()
    if not target.is_file() or target.stat().st_size<1000:
        raise ValueError("Real STEP tessellation was not generated")
    return triangles


def publish(functional_root,destination,*,run_url,commit):
    data,step=verified_payload(functional_root,run_url=run_url,commit=commit)
    output=Path(destination)
    output.mkdir(parents=True,exist_ok=True)
    triangles=export_surface_stl(step,output/"warren_truss.stl")
    data["geometry"]["stl_surface_triangle_count"]=triangles
    data["geometry"]["stl_sha256"]=hashlib.sha256(
        (output/"warren_truss.stl").read_bytes()).hexdigest()
    (output/"truss_demo.json").write_text(
        json.dumps(data,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return data


def main():
    parser=argparse.ArgumentParser(description="Publish truthful STEP tessellation and truss numerical FEA")
    parser.add_argument("functional_root")
    parser.add_argument("--out",required=True)
    parser.add_argument("--run-url",required=True)
    parser.add_argument("--commit",required=True)
    a=parser.parse_args()
    result=publish(a.functional_root,a.out,run_url=a.run_url,commit=a.commit)
    print(json.dumps({
        "source_run":result["source_run"],
        "elements":result["native"]["elements"],
        "max_displacement_mm":result["native"]["max_displacement_mm"],
        "peak_von_mises_mpa":result["native"]["peak_von_mises_mpa"],
        "cad_surface_triangles":result["geometry"]["stl_surface_triangle_count"],
    },indent=2))


if __name__=="__main__":
    main()
