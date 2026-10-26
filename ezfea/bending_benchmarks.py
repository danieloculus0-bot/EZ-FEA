"""Independent Euler-Bernoulli/Timoshenko cantilever bending reference.

This analytical reference applies to a slender uniform, straight prismatic
beam away from load/fixture stress boundary layers. A clamped 3D solid with
a discretized surface tip load is NOT the same exact boundary value problem.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .core import Analysis, Material
from .demo import make_demo_step
from .mesh import inspect_step
from .workflow import run_case
from .probe_convergence import screen_fixed_probe_stress
from .mechanics_references import (isotropic_shear_modulus_mpa,
                                   rectangular_beam_shear_tau_mpa)


def rectangular_second_moment_mm4(b_mm,h_mm):
    if min(b_mm,h_mm)<=0 or not all(math.isfinite(x) for x in (b_mm,h_mm)):
        raise ValueError("Positive finite rectangle dimensions required")
    return b_mm*h_mm**3/12.


def cantilever_bending_displacement_mm(force_n,length_mm,modulus_mpa,moment_mm4):
    if (length_mm<=0 or modulus_mpa<=0 or moment_mm4<=0 or
        not all(math.isfinite(v) for v in (force_n,length_mm,modulus_mpa,moment_mm4))):
        raise ValueError("Invalid independent Euler Bernoulli bending input")
    return force_n*length_mm**3/(3.*modulus_mpa*moment_mm4)


def cantilever_bending_stress_mpa(force_n,length_mm,x_mm,y_from_neutral_mm,moment_mm4):
    if not (0<=x_mm<=length_mm and moment_mm4>0):
        raise ValueError("Stress evaluation must be within beam span")
    if not all(math.isfinite(v) for v in (force_n,length_mm,x_mm,y_from_neutral_mm,moment_mm4)):
        raise ValueError("Nonfinite bending stress reference")
    return force_n*(length_mm-x_mm)*y_from_neutral_mm/moment_mm4


def run_bending_reference(output_root="runs/bending_reference", *,
                          element_types=("C3D4","C3D10"),
                          meshes_mm=(14.,10.,7.)):
    root=Path(output_root)
    root.mkdir(parents=True,exist_ok=True)
    step=make_demo_step(root/"cantilever_100x10x10.step")
    faces=inspect_step(str(step))
    fixture=min(faces,key=lambda f:abs(f.center_mm[0]))
    loaded=min(faces,key=lambda f:abs(f.center_mm[0]-100))
    if abs(fixture.center_mm[0])>1e-6 or abs(loaded.center_mm[0]-100)>1e-6:
        raise ValueError("Unexpected cantilever fixture/load geometry")
    force,length,width,height=100.,100.,10.,10.
    modulus=Material().elastic_modulus_mpa
    poisson=Material().poisson_ratio
    I=rectangular_second_moment_mm4(width,height)
    reference=cantilever_bending_displacement_mm(force,length,modulus,I)
    G=isotropic_shear_modulus_mpa(modulus,poisson)
    shear=force*length/((5./6.)*G*(width*height))
    probe_xyz=(51.1,8.3,4.3)
    shear_probe_xyz=(50.91,4.83,5.17)
    probe={"outer_fiber_at_midspan":probe_xyz,
           "midspan_neutral_axis_shear":shear_probe_xyz}
    reference_tau=abs(rectangular_beam_shear_tau_mpa(
        force,width,height,shear_probe_xyz[1]-height/2))
    sigma=abs(cantilever_bending_stress_mpa(
        force,length,probe_xyz[0],probe_xyz[1]-height/2,I))
    rows=[]
    probe_series={etype:[] for etype in element_types}
    for element_type in element_types:
        for mesh in meshes_mm:
            case=Analysis(str(step),fixture.tag,loaded.tag,(0,-force,0),
                          mesh,element_type=element_type)
            out=run_case(case,root/element_type/f"mesh_{mesh:g}",
                         fixed_stress_probes=probe)
            record=json.loads((out/"case.json").read_text(encoding="utf-8"))
            if record["status"]!="completed":
                raise ValueError(f"Failed native cantilever solve: {out}")
            metrics=record["results"]
            actual_disp=metrics["max_displacement_mm"]
            recovery_key=("fixed_coordinate_stress_affine" if element_type=="C3D10"
                          else "fixed_coordinate_stress")
            measured=metrics[recovery_key]["probes"]["outer_fiber_at_midspan"]
            axial_sigma=abs(measured["tensor_mpa"][0])
            shear_measured=abs(metrics[recovery_key]["probes"]["midspan_neutral_axis_shear"]["tensor_mpa"][3])
            probe_series[element_type].append({
                "mesh_size_mm":mesh,
                "element_count":record["mesh"]["elements"],
                "fixed_coordinate_stress":metrics.get("fixed_coordinate_stress"),
                "fixed_coordinate_stress_affine":metrics.get("fixed_coordinate_stress_affine"),
            })
            rows.append({
                "element_type":element_type,
                "mesh_size_mm":mesh,
                "analytical_euler_tip_displacement_mm":reference,
                "analytical_timoshenko_tip_displacement_mm":reference+shear,
                "actual_max_displacement_mm":actual_disp,
                "relative_tip_displacement_error_against_EB":abs(actual_disp-reference)/reference,
                "analytical_outer_fiber_abs_sigma_x_mpa":sigma,
                "actual_fixed_probe_abs_sigma_x_mpa":axial_sigma,
                "analytical_midspan_abs_tau_xy_mpa":reference_tau,
                "actual_fixed_probe_abs_tau_xy_mpa":shear_measured,
                "relative_nominal_shear_error":abs(shear_measured-reference_tau)/reference_tau,
                "relative_outer_fiber_stress_error":abs(axial_sigma-sigma)/sigma,
                "native_force_balance_relative_error":metrics["force_balance_relative_error"],
                "probe_coordinate_mm":list(probe_xyz),
                "recovery":measured["recovery"],
                "native_run_path":str(out.relative_to(root)),
            })
    stress_screens={
        etype: (screen_fixed_probe_stress(series,element_type=etype)
                if len(series)>=3 else {"status":"not_run_need_three_grids"})
        for etype,series in probe_series.items()
    }
    report={"schema":"ezfea.cantilever_analytic_reference.v1",
            "model":"100 x 10 x 10 mm homogeneous steel, 100 N transverse tip force",
            "assumptions":"Euler Bernoulli bending, small shear correction; free-end surface loading and fixed face differ from ideal beam BC.",
            "I_mm4":I,"youngs_modulus_mpa":modulus,
            "poisson_ratio":poisson,"force_n":force,
            "probe":probe,"rows":rows,
            "reference_neutral_axis_shear_mpa":reference_tau,
            "fixed_probe_stress_convergence":stress_screens,
            "engineering_validation":"not_established"}
    (root/"bending_analytical_comparison.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=["# 3D solid FEA cantilever versus independent beam theory","","| Element | Mesh (mm) | 3D max disp (mm) | EB theory (mm) | Δ deflection | 3D probe |σxx| (MPa) | EB nominal |σxx| (MPa) | Δ stress |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['element_type']} | {r['mesh_size_mm']:g} | "
                     f"{r['actual_max_displacement_mm']:.6g} | "
                     f"{reference:.6g} | "
                     f"{r['relative_tip_displacement_error_against_EB']*100:.3g}% | "
                     f"{r['actual_fixed_probe_abs_sigma_x_mpa']:.6g} | "
                     f"{sigma:.6g} | {r['relative_outer_fiber_stress_error']*100:.3g}% |")
    lines+=["", "Native shear stress at fixed neutral-axis-adjacent location versus textbook rectangular section:"]
    for r in rows:
        lines.append(f"- {r['element_type']}, {r['mesh_size_mm']:g} mm: "
                     f"|tau_xy| = {r['actual_fixed_probe_abs_tau_xy_mpa']:.5g} MPa; "
                     f"reference = {reference_tau:.5g} MPa; "
                     f"approximate discrepancy = {100*r['relative_nominal_shear_error']:.3g}%.")
    lines+=["", "Fixed physical-coordinate stress convergence screening (not validation):"]
    for etype,screen in stress_screens.items():
        lines.append(f"- {etype}: " + (
            "stable at checked grids" if screen.get("all_probes_stable_at_checked_mesh_sizes") else
            "review / further refinement required"
        ))
    lines+=[
        f"Timoshenko 1D shear-corrected tip approximation: {reference+shear:.8g} mm.",
        "3D boundary layers, end-face load application and probe recovery remain independent limitations.",
        "No code is considered design-certified by agreement with this textbook beam case."]
    md="\n".join(lines)+"\n"
    (root/"BENDING_REPORT.md").write_text(md,encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="runs/bending_reference")
    p.add_argument("--meshes",nargs="+",type=float,default=(14.,10.,7.))
    args=p.parse_args()
    data=run_bending_reference(args.out,meshes_mm=args.meshes)
    print((Path(args.out)/"BENDING_REPORT.md").read_text(encoding="utf-8"))
    quadratic=[r for r in data["rows"] if r["element_type"]=="C3D10"]
    fine=sorted(quadratic,key=lambda row:row["mesh_size_mm"])[0]
    if any(r["native_force_balance_relative_error"]>.01 for r in data["rows"]):
        raise SystemExit("Analytical benchmark failed native force equilibrium")
    if (fine["relative_tip_displacement_error_against_EB"]>.05 or
        fine["relative_outer_fiber_stress_error"]>.05 or
        fine["native_force_balance_relative_error"]>.01):
        raise SystemExit("Fine-grid C3D10 cantilever differs more than 5% from classical bending; investigate before accepting.")


if __name__=="__main__":
    main()
