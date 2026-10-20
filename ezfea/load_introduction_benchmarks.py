"""Native experiment: uniform end traction vs Gaussian centered/eccentric pads.

The same 100x10x10 steel bar, fixed plane and 100 N axial applied force are
used throughout. Changing the Gaussian load introduction changes the actual
force-resultant location and therefore the applied bending moment. Solves must
pass independent force AND reaction moment equilibrium. This is NOT physical
contact, finite bearing law, bolt clamping, or true pressure-contact FEA.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .core import Analysis, FaceConstraint, FaceLoad, FaceFootprintLoad
from .demo import make_demo_step
from .mesh import inspect_step
from .workflow import run_case


def run_footprint_experiment(output_root="runs/footprint_experiment",
                             *, meshes_mm=(10.,7.),
                             element_types=("C3D4","C3D10")):
    root=Path(output_root)
    root.mkdir(parents=True,exist_ok=True)
    step=make_demo_step(root/"source_axial_bar.step")
    faces=inspect_step(str(step))
    fixed=min(faces,key=lambda face:abs(face.center_mm[0]))
    loaded=min(faces,key=lambda face:abs(face.center_mm[0]-100.))
    if abs(fixed.center_mm[0])>1e-6 or abs(loaded.center_mm[0]-100.)>1e-6:
        raise ValueError("Unexpected bar end-face selection in fixture")

    samples=(
        ("whole_end_face",None),
        ("centered_pad",(100.,5.,5.)),
        ("eccentric_pad",(100.,5.,7.5)),
    )
    records=[]
    for kind in element_types:
        if kind not in ("C3D4","C3D10"):
            raise ValueError("Unsupported native footprint experiment element type")
        for mesh_size in meshes_mm:
            if not math.isfinite(mesh_size) or mesh_size<=0:
                raise ValueError("Positive finite mesh size required")
            per_case={}
            for label,center in samples:
                force=(100.,0.,0.)
                load=(FaceLoad(loaded.tag,force) if center is None else
                      FaceFootprintLoad(loaded.tag,force,center,2.5))
                case=Analysis(str(step),0,0,(0.,0.,0.),mesh_size,
                              connections=(FaceConstraint(fixed.tag),),
                              loads=(load,),element_type=kind)
                out=run_case(case,root/kind/f"mesh_{mesh_size:g}"/label,
                             fixed_stress_probes={"bar_midspan":(50.13,4.31,5.82)})
                data=json.loads((out/"case.json").read_text(encoding="utf-8"))
                if data["status"]!="completed":
                    raise ValueError(f"Load model failed native physics: {kind} {label}: {data.get('error',data['status'])}")
                result=data["results"]
                load_audit=data["load_introduction"]["distributions"][0]
                observed_force=load_audit["resultant_force_n"]
                observed_moment=load_audit["resultant_moment_about_origin_nmm"]
                if (math.dist(observed_force,force)>1e-6 or
                    result["force_balance_relative_error"]>.01 or
                    result["moment_balance_relative_error"]>.01):
                    raise ValueError(f"Native force/wrench conservation failed: {kind} {label}")
                record={
                    "element_type":kind,"mesh_mm":mesh_size,"load_type":label,
                    "load_center_request_mm":center,
                    "actual_resultant_center_mm":load_audit["resultant_center_mm"],
                    "applied_force_n":observed_force,
                    "applied_moment_origin_nmm":observed_moment,
                    "reaction_moment_origin_nmm":result["reaction_moment_about_origin_nmm"],
                    "force_equilibrium_relative_error":result["force_balance_relative_error"],
                    "moment_equilibrium_relative_error":result["moment_balance_relative_error"],
                    "max_displacement_mm":result["max_displacement_mm"],
                    "max_native_gauss_von_mises_mpa":result["max_von_mises_mpa"],
                    "sampled_midspan_von_mises_mpa":(
                        result["fixed_coordinate_stress_affine"]["probes"]["bar_midspan"]["von_mises_mpa"]
                        if kind=="C3D10" else
                        result["fixed_coordinate_stress"]["probes"]["bar_midspan"]["von_mises_mpa"]),
                    "source_directory":str(out.relative_to(root)),
                    "surface_quadrature":load_audit.get("quadrature","uniform_face_consistent_force"),
                    "load_audit":load_audit,
                }
                per_case[label]=record
                records.append(record)
            # Eccentric Gaussian footprint must create a larger bending moment
            # than centered pad despite identical total axial 100 N.
            whole=per_case["whole_end_face"]
            symmetric=per_case["centered_pad"]
            offset=per_case["eccentric_pad"]
            if (abs(symmetric["applied_moment_origin_nmm"][1]-
                    whole["applied_moment_origin_nmm"][1])>4. or
                offset["applied_moment_origin_nmm"][1] <=
                    symmetric["applied_moment_origin_nmm"][1]+25.):
                raise ValueError("Eccentric traction did not produce the expected extra bending moment")
    report={
        "schema":"ezfea.load_introduction_native.v1",
        "model":"100x10x10 mm A36 nominal bar, left face fully fixed, 100N axial force",
        "mesh_sizes_mm":list(meshes_mm),
        "element_types":list(element_types),
        "test_conditions":"uniform full end face vs centered Gaussian pad vs z-eccentric Gaussian pad, sigma 2.5 mm",
        "engineering_validation":"not_established",
        "records":records,
        "notice":"Prescribed Gaussian force density, not Hertzian pressure or nonlinear structural contact."
    }
    (root/"load_introduction_evidence.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=[
      "# Actual CalculiX load-introduction experiment",
      "",
      "All cases use 100 N total X force and the SAME geometry, material and restraint.",
      "The pad is a prescribed Gaussian face traction envelope, NOT a contact law.",
      "Its resultant moves when the pad is offset and the support reacts to the changed moment.",
      "",
      "| Elements | Mesh mm | Load introduction | Actual resultant z (mm) | Applied moment My (N·mm) | Max disp (mm) | Peak native stress (MPa) | Moment residual |",
      "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for entry in records:
        lines.append(
            f"| {entry['element_type']} | {entry['mesh_mm']:g} | "
            f"{entry['load_type']} | {entry['actual_resultant_center_mm'][2]:.4f} | "
            f"{entry['applied_moment_origin_nmm'][1]:.4f} | "
            f"{entry['max_displacement_mm']:.7g} | "
            f"{entry['max_native_gauss_von_mises_mpa']:.5g} | "
            f"{100*entry['moment_equilibrium_relative_error']:.4g}% |"
        )
    lines+=["",
            "All source meshes, input decks, solver logs and results are archived.",
            "A lower stress or better convergence is not automatically physically valid;",
            "the Gaussian envelope approximates a finite loading pad, with no",
            "friction/contact/deformation-dependent traction calculation."]
    (root/"LOAD_INTRODUCTION_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="runs/footprint_experiment")
    p.add_argument("--meshes",nargs="+",type=float,default=(10.,7.))
    args=p.parse_args()
    run_footprint_experiment(args.out,meshes_mm=args.meshes)
    print((Path(args.out)/"LOAD_INTRODUCTION_REPORT.md").read_text(encoding="utf-8"))


if __name__=="__main__":
    main()
