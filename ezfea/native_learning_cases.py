"""Generate *real* CalculiX supervision for BEAN, never simulated labels.

Three constrained linear-elastic families: axial rectangular bars, bending
rectangular cantilevers and pure torque on solid circular shafts. Sources are
STEP, meshes are genuine Gmsh C3D10, outputs are actual CalculiX runs.

The predetermined held-out GEOMETRIES remain separate from calibration data.
'Exceeds example limit' is an exercise threshold, NOT a material failure or
building-code finding. Entire dataset, including reviewed/failing runs, is
written to disk. Nothing here updates BEAN's learning weights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .core import Analysis, Material
from .mesh import inspect_step
from .workflow import run_case
from .torsion_benchmarks import run_torsion_benchmark

SCHEMA="ezfea.real_structural_curriculum.v1"

# Fixed specs are intentional for reproducible source identities. Every
# holdout changes a geometry dimension, not merely the applied load.
_SPECS={
 "train":[
  ("axial",  (80,10,9,150,200000)),
  ("axial",  (110,12,10,350,190000)),
  ("axial",  (90,9,11,-220,210000)),
  ("axial",  (125,13,8,110,180000)),
  ("bending",(85,11,9,80,200000)),
  ("bending",(115,12,10,-170,190000)),
  ("bending",(100,9,12,230,210000)),
  ("bending",(130,14,11,-90,180000)),
  ("torsion",(80,9,6800,200000,.25)),
  ("torsion",(115,11,-12500,190000,.27)),
  ("torsion",(95,10,4400,210000,.24)),
  ("torsion",(125,12,-15600,180000,.26)),
 ],
 "holdout":[
  ("axial",  (100,11,8,280,195000)),
  ("axial",  (135,14,9,-175,205000)),
  ("axial",  (75,8,12,240,185000)),
  ("bending",(95,10,13,140,195000)),
  ("bending",(120,13,9,-200,205000)),
  ("bending",(105,8,10,100,185000)),
  ("torsion",(105,10.5,9400,195000,.23)),
  ("torsion",(90,8.5,-7400,205000,.28)),
  ("torsion",(135,11.5,17700,185000,.25)),
 ],
}

# Extra *unseen geometries* make a 30-specimen held-out benchmark large
# enough for BEAN Core's existing scored-checkpoint contract. These do not
# enter the training corpus; no load-only duplicates masquerade as geometry
# generalization.
_SPECS["holdout"].extend([
  ("axial",(65,8,10,170,190000)),
  ("axial",(72,9,8,-290,195000)),
  ("axial",(87,10,12,180,205000)),
  ("axial",(98,11,9,380,185000)),
  ("axial",(118,12,11,-125,215000)),
  ("axial",(132,13,10,320,175000)),
  ("axial",(145,14,12,-210,200000)),
  ("bending",(78,9,8,95,185000)),
  ("bending",(86,10,9,-145,200000)),
  ("bending",(94,11,10,210,195000)),
  ("bending",(102,12,11,-155,205000)),
  ("bending",(112,13,12,200,180000)),
  ("bending",(124,14,13,-115,210000)),
  ("bending",(140,15,14,125,190000)),
  ("torsion",(70,7.5,3900,195000,.24)),
  ("torsion",(78,8.0,-6800,185000,.27)),
  ("torsion",(86,9.0,7400,210000,.26)),
  ("torsion",(98,10.0,-11000,205000,.23)),
  ("torsion",(110,11.0,9800,195000,.25)),
  ("torsion",(120,12.0,-17800,180000,.28)),
  ("torsion",(140,13.0,19300,200000,.24)),
])


def specimens():
    seen=set()
    rows=[]
    for split,entries in _SPECS.items():
        for i,(family,parameters) in enumerate(entries,1):
            # Geometry signature includes shape and dimensions but NOT load/E.
            geometry=(family,tuple(parameters[:3] if family!="torsion"
                                   else parameters[:2]))
            if geometry in seen:
                raise ValueError("Training/holdout physical geometry leakage detected")
            seen.add(geometry)
            rows.append({"case_id":f"{split}-{family}-{i:02d}",
                         "split":split,"family":family,"parameters":parameters,
                         "geometry_key":json.dumps(geometry,separators=(",",":"))})
    return rows


def box_step(path,length,width,height):
    import gmsh
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.model.add("bean_real_FEA_curriculum_"+path.stem)
        gmsh.model.occ.addBox(0,0,0,length,width,height)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    return path


def _pick_end_faces(path,length):
    faces=inspect_step(str(path))
    fixed=[f for f in faces if abs(f.center_mm[0])<1e-5]
    tip=[f for f in faces if abs(f.center_mm[0]-length)<1e-5]
    if len(fixed)!=1 or len(tip)!=1:
        raise ValueError("Physical STEP ends not uniquely identified")
    return fixed[0].tag,tip[0].tag


def _native_bar_or_beam(root,record):
    family=record["family"]
    L,b,h,force,E=record["parameters"]
    source=box_step(root/"source.step",L,b,h)
    a,z=_pick_end_faces(source,L)
    if family=="axial":
        applied=(force,0.,0.)
        # Ideal F/A; compare actual far-field |sigma_x| in native stress.
        reference=abs(force)/(b*h)
        metric="midspan_abs_sigma_x_mpa"
        limit=2.0  # explicitly hypothetical stress-screening threshold
    else:
        applied=(0.,force,0.)
        reference=abs(force)*L**3/(3*E*(b*h**3/12))
        metric="tip_displacement_mm"
        limit=L/500  # explicitly hypothetical service deflection threshold
    point=(.513*L,.437*b,.573*h)
    material=Material(elastic_modulus_mpa=E,poisson_ratio=.26)
    case=Analysis(str(source),a,z,applied,min(b,h)*.65,
                  material=material,element_type="C3D10")
    folder=run_case(case,root/"native",fixed_stress_probes={"physical_midspan":point})
    raw=json.loads((folder/"case.json").read_text(encoding="utf-8"))
    if raw.get("status")!="completed":
        raise ValueError(f"Native analysis needs review: {record['case_id']}")
    metrics=raw["results"]
    if family=="axial":
        probe=metrics["fixed_coordinate_stress_affine"]["probes"]["physical_midspan"]
        observed=abs(probe["tensor_mpa"][0])
        if probe.get("location_quality") not in (None,"inside_element"):
            # A probe near a boundary may still be archived, but never
            # silently accepted as training-grade supervision.
            raise ValueError("Midspan stress probe location requires review")
    else:
        observed=metrics["max_displacement_mm"]
    if metrics["force_balance_check"]!="pass" or metrics["moment_balance_check"]!="pass":
        raise ValueError("Solver equilibrium is not verified")
    return {
        "target_metric":metric,"analytical_reference":reference,
        "native_measured":observed,"example_screen_limit":limit,
        "load_n":force,"youngs_mpa":E,
        "geometry_mm":{"length":L,"width":b,"height":h},
        "mesh_elements":raw["mesh"]["elements"],
        "solver_force_balance_relative_error":metrics["force_balance_relative_error"],
        "solver_moment_balance_relative_error":metrics["moment_balance_relative_error"],
        "source_step_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "native_case_path":str(folder.relative_to(root.parent)),
    }


def _native_torsion(root,record):
    L,r,torque,E,nu=record["parameters"]
    report=run_torsion_benchmark(root/"native_torsion",
        grids_mm=(min(5.,r*.6),),length_mm=L,radius_mm=r,
        torque_nmm=torque,modulus_mpa=E,poisson=nu)
    one=report["records"][0]
    return {
        "target_metric":"abs_tip_twist_rad",
        "analytical_reference":abs(report["reference_tip_twist_rad"]),
        "native_measured":abs(one["measured_tip_twist_rad"]),
        "example_screen_limit":.001,
        "torque_nmm":torque,"youngs_mpa":E,"poisson":nu,
        "geometry_mm":{"length":L,"radius":r},
        "mesh_elements":one["elements"],
        "solver_moment_balance_relative_error":one["reaction_torque_relative_error"],
        "source_step_sha256":report["source_step_sha256"],
        "native_case_path":str((root/"native_torsion").relative_to(root.parent)),
    }


def run_curriculum(destination="runs/real_fea_curriculum",*,limit=None):
    if limit is not None and (type(limit) is not int or limit<=0):
        raise ValueError("limit must be a positive count, or omitted")
    root=Path(destination)
    root.mkdir(parents=True,exist_ok=True)
    planned=specimens()
    actual=planned if limit is None else planned[:limit]
    rows=[]
    failed=0
    for record in actual:
        folder=root/record["case_id"]
        folder.mkdir(exist_ok=True)
        result={
            "case_id":record["case_id"],"split":record["split"],
            "family":record["family"],"geometry_key":record["geometry_key"],
            "status":"pending","test_origin":"native_step_gmsh_calculix_c3d10",
            "engineering_validation":"not_established",
        }
        try:
            values=(_native_torsion(folder,record) if record["family"]=="torsion"
                    else _native_bar_or_beam(folder,record))
            result.update(values)
            actual_value=result["native_measured"]
            reference=result["analytical_reference"]
            if not (math.isfinite(actual_value) and actual_value>0 and
                    math.isfinite(reference) and reference>0):
                raise ValueError("Invalid native stress/twist/displacement quantity")
            result["reference_relative_error"]=abs(actual_value-reference)/reference
            result["actual_exceeds_example_screen"]=(actual_value>result["example_screen_limit"])
            result["status"]="measured"
        except Exception as exc:
            failed+=1
            result["status"]="needs_review"
            result["error"]=str(exc)
        rows.append(result)
        # Persist the full outcome including failures immediately.
        (folder/"sample.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    payload={
        "schema":SCHEMA,
        "origin":"REAL Gmsh STEP mesh and CalculiX solver, not surrogate labels",
        "element_type":"C3D10",
        "cases_planned":len(planned),"cases_executed":len(actual),
        "training_geometry_disjoint_from_holdout":True,
        "cases":rows,
        "failed_or_needs_review":failed,
        "limits_provenance":"hypothetical example numerical screens, not material strength or code",
        "no_design_approval":True,
        "engineer_validation":"not_established",
    }
    (root/"native_curriculum.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    if failed:
        raise ValueError(f"{failed} native cases need review; inspect recorded failures")
    return payload


def main():
    p=argparse.ArgumentParser(description="Generate held-out real FEA training corpus")
    p.add_argument("--out",default="runs/real_fea_curriculum")
    p.add_argument("--limit",type=int,default=None,
                   help="Quick smoke runs only; never treat as complete dataset")
    args=p.parse_args()
    report=run_curriculum(args.out,limit=args.limit)
    print(json.dumps({
        "schema":report["schema"],"cases_executed":report["cases_executed"],
        "failed_or_needs_review":report["failed_or_needs_review"],
    },indent=2))


if __name__=="__main__":
    main()
