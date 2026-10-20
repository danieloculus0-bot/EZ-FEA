"""Independent 1D elastic axial-bar screening of native 3D FEA stress.

The analytical references F/A and FL/(EA) are from mechanics of materials,
not from Gmsh or CalculiX. A fully clamped 3D end has near-support Poisson
effects, so these are FAR-FIELD engineering checks, not an exact 3D solution.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path

from .core import Analysis
from .demo import make_demo_step
from .mesh import inspect_step
from .workflow import run_case


def axial_nominal_stress_mpa(force_n,area_mm2):
    if not math.isfinite(force_n) or not math.isfinite(area_mm2) or area_mm2<=0:
        raise ValueError("Force/area must be finite with positive area")
    return force_n/area_mm2


def axial_nominal_elongation_mm(force_n,length_mm,area_mm2,modulus_mpa):
    if (not all(math.isfinite(x) for x in
                (force_n,length_mm,area_mm2,modulus_mpa)) or
        length_mm<=0 or area_mm2<=0 or modulus_mpa<=0):
        raise ValueError("Invalid geometry or elastic modulus for axial comparison")
    return force_n*length_mm/(area_mm2*modulus_mpa)


def run_axial_reference(output_root="runs/axial_reference", *,
                        element_types=("C3D4","C3D10"),
                        meshes_mm=(14.,10.,7.)):
    root=Path(output_root)
    root.mkdir(parents=True,exist_ok=True)
    step=make_demo_step(root/"axial_100x10x10.step")
    faces=inspect_step(str(step))
    fixture=min(faces,key=lambda f:abs(f.center_mm[0]))
    top=min(faces,key=lambda f:abs(f.center_mm[0]-100.))
    if abs(fixture.center_mm[0])>1e-6 or abs(top.center_mm[0]-100)>1e-6:
        raise ValueError("Unexpected STEP end-plane geometry in analytic reference")
    force,area,length,modulus=100.,100.,100.,200000.
    target_sigma=axial_nominal_stress_mpa(force,area)
    target_u=axial_nominal_elongation_mm(force,length,area,modulus)
    probe={"bar_core_midspan":(50.13,4.31,5.82)}
    rows=[]
    for etype in element_types:
        if etype not in ("C3D4","C3D10"):
            raise ValueError("Unsupported analytical benchmark element")
        for mesh in meshes_mm:
            case=Analysis(str(step),fixture.tag,top.tag,(force,0.,0.),mesh,
                          element_type=etype)
            output=run_case(case,root/etype/f"mesh_{mesh:g}",
                            fixed_stress_probes=probe)
            data=json.loads((output/"case.json").read_text(encoding="utf-8"))
            if data["status"]!="completed" or data["results"]["force_balance_check"]!="pass":
                raise ValueError("Real axial reference did not pass solver equilibrium")
            result=data["results"]
            original=result["fixed_coordinate_stress"]["probes"]["bar_core_midspan"]
            best=(result["fixed_coordinate_stress_affine"]["probes"]["bar_core_midspan"]
                  if etype=="C3D10" else original)
            stress=best["von_mises_mpa"]
            movement=result["max_displacement_mm"]
            if not all(math.isfinite(x) and x>0 for x in (stress,movement)):
                raise ValueError("Missing actual stress or displacement in native benchmark")
            rows.append({
                "element_type":etype,"mesh_size_mm":mesh,
                "probe_coordinate_mm":list(probe["bar_core_midspan"]),
                "nominal_axial_stress_mpa":target_sigma,
                "recovered_stress_mpa":stress,
                "relative_nominal_stress_error":abs(stress-target_sigma)/target_sigma,
                "expected_1d_elongation_mm":target_u,
                "fe_max_nodal_displacement_mm":movement,
                "relative_elongation_approximation_error":abs(movement-target_u)/target_u,
                "recovery":best["recovery"],
                "native_equilibrium_relative_error":result["force_balance_relative_error"],
                "native_case_directory":str(output.relative_to(root)),
            })
    report={
        "schema":"ezfea.axial_analytic_reference.v1",
        "model":"100 x 10 x 10 mm homogeneous linear elastic bar, end-face clamped/loaded",
        "assumptions":"Ideal 1D axial nominal stress F/A and elongation FL/(EA); 3D end restraint introduces Poisson correction locally.",
        "units":"N, mm, MPa",
        "force_n":force,"area_mm2":area,"length_mm":length,"modulus_mpa":modulus,
        "probes":probe,"rows":rows,
        "engineering_validation":"not_established",
    }
    (root/"analytical_comparison.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=["# Native axial bar versus independent F/A and FL/(EA)",
           "",
           "These formulas are ideal 1D references, not exact constrained 3D stress fields.",
           "",
           "| Formulation | Mesh (mm) | Midspan stress (MPa) | F/A = 1 MPa discrepancy | Max displacement (mm) | 1D FL/EA = 0.0005 mm discrepancy |",
           "|---|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['element_type']} | {r['mesh_size_mm']:g} | "
                     f"{r['recovered_stress_mpa']:.6g} | "
                     f"{r['relative_nominal_stress_error']*100:.3g}% | "
                     f"{r['fe_max_nodal_displacement_mm']:.6g} | "
                     f"{r['relative_elongation_approximation_error']*100:.3g}% |")
    lines += ["", "No mesh convergence or experimental correctness is implied by passing this simple reference."]
    md="\n".join(lines)+"\n"
    (root/"ANALYTICAL_REPORT.md").write_text(md,encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="runs/axial_reference")
    parser.add_argument("--meshes",nargs="+",type=float,default=(14.,10.,7.))
    args=parser.parse_args()
    data=run_axial_reference(args.out,meshes_mm=args.meshes)
    print((Path(args.out)/"ANALYTICAL_REPORT.md").read_text(encoding="utf-8"))
    if any(x["relative_nominal_stress_error"]>.02 or
           x["relative_elongation_approximation_error"]>.02 or
           x["native_equilibrium_relative_error"]>.01 for x in data["rows"]):
        raise SystemExit("Native solver differs >2% from simple 1D reference; investigate rather than mark validated.")


if __name__=="__main__":
    main()
