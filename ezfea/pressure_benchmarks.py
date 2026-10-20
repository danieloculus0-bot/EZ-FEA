"""Run actual CalculiX normal DSLOAD pressure versus equivalent end force.

N/mm2 (MPa) pressure is applied by CalculiX on a real exterior tetra
surface; the benchmark separately integrates a pressure wrench and verifies
the supports' reaction force and moment, from native .dat reaction output.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from .core import Analysis
from .demo import make_demo_step
from .mesh import inspect_step,build_mesh
from .native_pressure import write_native_pressure_input
from .results import read_dat,summarize_dat
from .solver import run_calculix


def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])


def run_pressure_benchmark(root="runs/native_pressure", *, element_types=("C3D4","C3D10"),
                           mesh_sizes=(10.,7.)):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    step=make_demo_step(root/"pressure_bar_100x10x10.step")
    faces=inspect_step(step)
    left=min(faces,key=lambda f:abs(f.center_mm[0]))
    end=min(faces,key=lambda f:abs(f.center_mm[0]-100.))
    if abs(left.center_mm[0])>1e-5 or abs(end.center_mm[0]-100)>1e-5:
        raise ValueError("Unexpected axial pressure benchmark face selection")
    data=[]
    for etype in element_types:
        for size in mesh_sizes:
            out=root/etype/f"grid_{size:g}"
            out.mkdir(parents=True,exist_ok=True)
            case=Analysis(str(step),left.tag,end.tag,(-100.,0.,0.),size,element_type=etype)
            mesh=build_mesh(str(step),left.tag,end.tag,size,element_type=etype)
            audit=write_native_pressure_input(case,mesh,out/"analysis.inp",end.tag,1.)
            if math.dist(audit["total_force_n"],(-100.,0.,0.))>1e-5:
                raise ValueError("Positive pressure did not point inward or force magnitude is wrong")
            run_calculix(out/"analysis.inp")
            result=summarize_dat(out/"analysis.dat",audit["total_force_n"],case.material.yield_mpa,
                                 expected_nodes=len(mesh.nodes),expected_elements=len(mesh.elements),
                                 applied_nodal_forces_n={},element_type=etype)
            raw=read_dat(out/"analysis.dat")
            support=[0.,0.,0.]
            moment=[0.,0.,0.]
            for row in raw["reactions"]:
                n=int(row[0])
                if n not in mesh.fixed_nodes:
                    raise ValueError("Unrecognized support reaction")
                p=mesh.nodes[n]
                reaction=row[1:4]
                for i in range(3):
                    support[i]+=reaction[i]
                m=_cross(p,reaction)
                for i in range(3):
                    moment[i]+=m[i]
            actual_force_error=math.dist(audit["total_force_n"],tuple(-x for x in support))
            actual_moment_error=math.dist(audit["moment_about_origin_nmm"],tuple(-x for x in moment))
            scale=math.sqrt(sum(v*v for v in audit["total_force_n"]))
            length=math.sqrt(100**2+10**2+10**2)
            force_error=actual_force_error/scale
            moment_error=actual_moment_error/(scale*length)
            row={
                "element_type":etype,"requested_mesh_mm":size,
                "native_dsload_pressure_mpa":1.,
                "integrated_pressure":audit,
                "solver_max_displacement_mm":result["max_displacement_mm"],
                "solver_peak_stress_mpa":result["max_von_mises_mpa"],
                "resultant_reaction_force_n":support,
                "resultant_reaction_moment_nmm":moment,
                "force_equilibrium_relative_error":force_error,
                "moment_equilibrium_relative_error":moment_error,
                "solver_output_dir":str(out.relative_to(root)),
            }
            (out/"pressure_audit.json").write_text(json.dumps(row,indent=2)+"\n")
            data.append(row)
            if force_error>.01 or moment_error>.01:
                raise ValueError(f"Real DSLOAD force/moment check failed: {row}")
    report={"schema":"ezfea.native_pressure_benchmark.v1",
            "description":"Real CalculiX DSLOAD P=1 MPa on 100 mm2 end face; F=100N.",
            "samples":data,"engineering_validation":"experimental_only"}
    (root/"pressure_benchmark.json").write_text(json.dumps(report,indent=2)+"\n")
    lines=["# Actual native CalculiX normal pressure benchmark","",
           "Positive normal pressure P=1 MPa on the x=100 mm end face;",
           "the integrated inward normal resultant is -100 N in X.",
           "",
           "| Element | Mesh (mm) | Applied pressure force (N) | Max displacement (mm) | Peak stress (MPa) | Reaction force residual | Reaction moment residual |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for s in data:
        lines.append(f"| {s['element_type']} | {s['requested_mesh_mm']} | "
                     f"{s['integrated_pressure']['total_force_n'][0]:.7g} | "
                     f"{s['solver_max_displacement_mm']:.8g} | "
                     f"{s['solver_peak_stress_mpa']:.7g} | "
                     f"{s['force_equilibrium_relative_error']*100:.6g}% | "
                     f"{s['moment_equilibrium_relative_error']*100:.6g}% |")
    lines += ["","Native P pressure was not pre-converted into CLOAD.",
              "A positive pressure follows the inward deformed surface normal in CalculiX.",
              "Not a nonlinear mechanical-contact or physically measured boundary model."]
    (root/"PRESSURE_REPORT.md").write_text("\n".join(lines)+"\n")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="runs/native_pressure")
    args=parser.parse_args()
    run_pressure_benchmark(args.out)
    print((Path(args.out)/"PRESSURE_REPORT.md").read_text())


if __name__=="__main__":
    main()
