"""Native CalculiX pure torsion on an actual STEP solid round shaft.

Generates a physical circular shaft, meshes quadratic C3D10 tets in Gmsh,
integrates a tangential traction into consistent end-surface nodal forces,
and compares measured twist AND fixed-end reaction torque to independent
Saint-Venant circular-shaft equations. This is a bounded benchmark, not a
general torque load button or assembly solver.
"""
from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
import json
import math
from pathlib import Path

from .load_footprints import _TRI_RULE, _tri3, _tri6, _cross, resultant_force_moment
from .mesh import gmsh_to_calculix_tet10
from .mesh_checks import audit_tetra_mesh, audit_gmsh_signed_quality
from .mechanics_references import (
    circular_shaft_twist_radians, circular_shaft_torsional_stress_mpa,
    isotropic_shear_modulus_mpa,
)
from .results import read_dat
from .solver import run_calculix


def consistent_end_torque(nodes, triangles, torque_nmm):
    """Consistent FE nodal forces for t_y=-z and t_z=y tangential traction.

    Normalize by the *discrete* computed moment to exactly preserve specified
    torque rather than assuming the curved CAD area's analytical polar J.
    """
    if type(torque_nmm) not in (int, float) or not math.isfinite(torque_nmm) or torque_nmm == 0:
        raise ValueError("Applied X torque must be finite and nonzero")
    if not triangles:
        raise ValueError("A meshed end surface is required")
    forces=defaultdict(float)
    for tri in triangles:
        if len(tri) not in (3, 6) or len(set(tri)) != len(tri) or any(n not in nodes for n in tri):
            raise ValueError("Invalid end face surface triangle connectivity")
        p=[nodes[n] for n in tri]
        fn=_tri3 if len(tri)==3 else _tri6
        for bary,weight in _TRI_RULE:
            N,dr,ds=fn(bary[1],bary[2])
            loc=[sum(N[k]*p[k][i] for k in range(len(tri))) for i in range(3)]
            tangent1=[sum(dr[k]*p[k][i] for k in range(len(tri))) for i in range(3)]
            tangent2=[sum(ds[k]*p[k][i] for k in range(len(tri))) for i in range(3)]
            norm=_cross(tangent1,tangent2)
            dA=math.sqrt(sum(v*v for v in norm))*.5*weight
            if not math.isfinite(dA) or dA <= 0:
                raise ValueError("Invalid end-surface Jacobian")
            for n,share in zip(tri,N):
                forces[n,2]+=share*(-loc[2])*dA
                forces[n,3]+=share*loc[1]*dA
    before=resultant_force_moment(forces,nodes)
    torque=before["moment_about_origin_nmm"][0]
    if not math.isfinite(torque) or abs(torque)<1e-14:
        raise ValueError("End surface has no usable torsional moment")
    scale=torque_nmm/torque
    normalized={key:value*scale for key,value in forces.items() if abs(value*scale)>1e-13}
    after=resultant_force_moment(normalized,nodes)
    characteristic_radius=math.sqrt(sum(
        nodes[node][1]**2+nodes[node][2]**2 for node,_ in normalized
    )/max(len(normalized),1))
    force_error=math.dist(after["force_n"],(0.,0.,0.))
    if force_error>abs(torque_nmm)/max(characteristic_radius,1.)*.015:
        raise ValueError("Tangential torque traction has unbalanced transverse force")
    if abs(after["moment_about_origin_nmm"][0]-torque_nmm)>abs(torque_nmm)*1e-8:
        raise ValueError("Discrete nodal load failed exact torque audit")
    if math.hypot(*after["moment_about_origin_nmm"][1:])>abs(torque_nmm)*.02:
        raise ValueError("Unexpected bending moment in torsion load")
    return normalized, {
        "applied_force_n":after["force_n"],
        "applied_moment_nmm":after["moment_about_origin_nmm"],
        "force_error_n":force_error,
        "normalization":scale,
        "traction":"t_y=-alpha*z, t_z=alpha*y",
        "quadrature":"T6/T3 isoparametric seven-point surface quadrature",
    }


def create_cylinder_step(path, length_mm=100., radius_mm=10.):
    import gmsh
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.model.add("circular_shaft_native_torsion")
        gmsh.model.occ.addCylinder(0,0,0,length_mm,0,0,radius_mm)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    return path


def mesh_shaft(step_file, mesh_size_mm, *, length_mm=100.):
    import gmsh
    if not math.isfinite(mesh_size_mm) or mesh_size_mm<=0:
        raise ValueError("Mesh size must be positive")
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.model.add("native_torsion")
        gmsh.option.setString("Geometry.OCCTargetUnit","MM")
        gmsh.model.occ.importShapes(str(step_file))
        gmsh.model.occ.synchronize()
        bodies=gmsh.model.getEntities(3)
        if len(bodies)!=1:
            raise ValueError("Torsion reference expects one independent round solid")
        faces=[tag for _,tag in gmsh.model.getBoundary(bodies,oriented=False,recursive=False)]
        def end_at(x):
            matches=[
                tag for tag in faces
                if abs(gmsh.model.occ.getCenterOfMass(2,tag)[0]-x)<.001
                and abs(gmsh.model.getBoundingBox(2,tag)[0]-x)<.001
                and abs(gmsh.model.getBoundingBox(2,tag)[3]-x)<.001
            ]
            if len(matches)!=1:
                raise ValueError(f"No unique circular end face at x={x}")
            return matches[0]
        fixed_face=end_at(0.)
        loaded_face=end_at(length_mm)
        gmsh.option.setNumber("Mesh.MeshSizeMin",mesh_size_mm/2)
        gmsh.option.setNumber("Mesh.MeshSizeMax",mesh_size_mm)
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(2)
        ids,coords,_=gmsh.model.mesh.getNodes()
        nodes={int(tag):tuple(float(x) for x in coords[3*i:3*i+3])
               for i,tag in enumerate(ids)}
        typetags,elementtags,connectivity=gmsh.model.mesh.getElements(3)
        if set(int(t) for t in typetags)!={11}:
            raise ValueError("Only C3D10 quadratic tets supported")
        elements={}
        for ids_list,connect in zip(elementtags,connectivity):
            for i,tag in enumerate(ids_list):
                elements[int(tag)]=gmsh_to_calculix_tet10(tuple(
                    int(v) for v in connect[10*i:10*(i+1)]
                ))
        integrity=audit_tetra_mesh(nodes,elements,"C3D10")
        integrity.update(audit_gmsh_signed_quality(
            gmsh.model.mesh.getElementQualities(sorted(elements),"minSICN"),len(elements)))
        def face_nodes(face):
            tags,_,_=gmsh.model.mesh.getNodes(2,face,True)
            result=sorted(int(t) for t in tags)
            if not result or any(t not in nodes for t in result):
                raise ValueError("End face nodes missing from volume mesh")
            return result
        fixed_nodes=face_nodes(fixed_face)
        tip_nodes=face_nodes(loaded_face)
        if set(fixed_nodes)&set(tip_nodes):
            raise ValueError("Torsion fixed and loaded surfaces overlap")
        typetags,_,raw=gmsh.model.mesh.getElements(2,loaded_face)
        tris=[]
        for kind,conn in zip(typetags,raw):
            if int(kind)!=9:
                raise ValueError("C3D10 torsion requires T6 CAD face triangles")
            tris.extend(tuple(int(n) for n in conn[6*i:6*(i+1)])
                        for i in range(len(conn)//6))
        if not tris:
            raise ValueError("Torsion end face has no surface triangles")
        return {
            "nodes":nodes,"elements":elements,"fixed_nodes":fixed_nodes,
            "tip_nodes":tip_nodes,"tip_triangles":tris,"mesh_checks":integrity,
            "fixed_cad_face":fixed_face,"loaded_cad_face":loaded_face,
        }
    finally:
        gmsh.finalize()


def write_torsion_deck(model,loads,path, *, modulus_mpa=200000.,poisson=.25):
    nodes=model["nodes"]
    elems=model["elements"]
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    lines=[
        "*HEADING","EZ-FEA actual STEP round shaft / pure torque C3D10",
        "*NODE",
    ]
    lines.extend(f"{tag}, {p[0]:.12g}, {p[1]:.12g}, {p[2]:.12g}"
                 for tag,p in sorted(nodes.items()))
    lines+=["*ELEMENT, TYPE=C3D10, ELSET=ALL"]
    lines.extend(f"{tag}, {', '.join(map(str,conn))}" for tag,conn in sorted(elems.items()))
    for name,key in (("FIXED","fixed_nodes"),("TIP","tip_nodes")):
        lines.append(f"*NSET, NSET={name}")
        tags=model[key]
        lines.extend(", ".join(map(str,tags[i:i+12])) for i in range(0,len(tags),12))
    lines.extend([
        "*MATERIAL, NAME=ISOTROPIC_REFERENCE","*ELASTIC",
        f"{modulus_mpa:.12g}, {poisson:.12g}",
        "*SOLID SECTION, ELSET=ALL, MATERIAL=ISOTROPIC_REFERENCE",
        "*STEP","*STATIC","*BOUNDARY","FIXED, 1, 3, 0","*CLOAD",
    ])
    lines.extend(f"{node}, {axis}, {force:.15g}" for (node,axis),force in sorted(loads.items()))
    lines.extend([
        "*NODE PRINT, NSET=FIXED","RF",
        "*NODE PRINT, NSET=TIP","U",
        "*EL PRINT, ELSET=ALL","S",
        "*END STEP",
    ])
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return path


def measured_twist_radians(data,model):
    rows=data.get("displacement")
    if not rows:
        raise ValueError("No measured TIP displacement table in native CalculiX")
    actual={int(row[0]):row for row in rows}
    if set(actual)!=set(model["tip_nodes"]):
        raise ValueError("TIP displacement IDs do not match actual meshed end")
    numerator=denominator=0.
    for node,row in actual.items():
        _,y,z=model["nodes"][node]
        numerator+=y*row[3]-z*row[2]
        denominator+=y*y+z*z
    if denominator<=0 or not math.isfinite(numerator):
        raise ValueError("Invalid native torsion tip twist sample")
    return numerator/denominator


def run_torsion_benchmark(output="runs/native_torsion", *,
                          grids_mm=(6.,4.),
                          torque_nmm=10000.,radius_mm=10.,
                          length_mm=100.,modulus_mpa=200000.,poisson=.25):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    step=create_cylinder_step(output/"circular_shaft.step",length_mm,radius_mm)
    reference_angle=circular_shaft_twist_radians(
        torque_nmm,length_mm,isotropic_shear_modulus_mpa(modulus_mpa,poisson),radius_mm)
    reference_surface_tau=circular_shaft_torsional_stress_mpa(torque_nmm,radius_mm,radius_mm)
    records=[]
    for size in grids_mm:
        folder=output/f"mesh_{str(size).replace('.','p')}"
        model=mesh_shaft(step,size,length_mm=length_mm)
        loads,audit=consistent_end_torque(model["nodes"],model["tip_triangles"],torque_nmm)
        inp=write_torsion_deck(model,loads,folder/"analysis.inp",
                               modulus_mpa=modulus_mpa,poisson=poisson)
        run_calculix(inp,timeout_seconds=240)
        raw=read_dat(folder/"analysis.dat")
        reactions=raw["reactions"]
        if not reactions or {int(row[0]) for row in reactions}!=set(model["fixed_nodes"]):
            raise ValueError("Native torsion fixed-end reactions are incomplete")
        reaction_loads={}
        for row in reactions:
            for axis in (1,2,3):
                reaction_loads[(int(row[0]),axis)]=row[axis]
        summary=resultant_force_moment(reaction_loads,model["nodes"])
        actual_torque=summary["moment_about_origin_nmm"][0]
        relative_torque=abs(actual_torque+torque_nmm)/abs(torque_nmm)
        angle=measured_twist_radians(raw,model)
        relative_angle=abs(angle-reference_angle)/abs(reference_angle)
        records.append({
            "mesh_size_mm":size,
            "elements":len(model["elements"]),"nodes":len(model["nodes"]),
            "mesh_integrity":model["mesh_checks"],
            "applied_audit":audit,
            "native_support_resultant_n":summary["force_n"],
            "native_support_moment_nmm":summary["moment_about_origin_nmm"],
            "reaction_torque_relative_error":relative_torque,
            "measured_tip_twist_rad":angle,
            "twist_relative_error":relative_angle,
            "status": ("pass" if relative_torque<.02 and relative_angle<.15 else "review"),
        })
    report={
        "schema":"ezfea.native_circular_torsion.v1",
        "status":"pass" if all(r["status"]=="pass" for r in records) else "review",
        "model":"one solid round STEP, fixed x=0, tangential distributed torque at x=L",
        "element_type":"C3D10",
        "source_step":str(step),
        "source_step_sha256":hashlib.sha256(step.read_bytes()).hexdigest(),
        "geometry":{"radius_mm":radius_mm,"length_mm":length_mm},
        "material":{"youngs_mpa":modulus_mpa,"poisson":poisson},
        "torque_nmm":torque_nmm,
        "reference_tip_twist_rad":reference_angle,
        "reference_surface_shear_mpa":reference_surface_tau,
        "theory":"T*L/(G*J), G=E/(2*(1+nu)), J=pi*R^4/2",
        "records":records,
        "engineering_validation":"not_established",
        "external_source_verification":"not_embedded",
        "limits":"A single circular-shaft Saint-Venant verification is not general torsion or connection behavior",
    }
    (output/"TORSION_EVIDENCE.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=["# Native STEP circular-shaft torsion / real CalculiX", "",
           f"Reference twist: {reference_angle:.8g} rad; reference surface tau: {reference_surface_tau:.8g} MPa.",
           "| Mesh (mm) | Elements | Measured twist (rad) | Twist difference | Reaction torque difference |",
           "|---|---:|---:|---:|---:|"]
    for row in records:
        lines.append(
            f"| {row['mesh_size_mm']:g} | {row['elements']} | {row['measured_tip_twist_rad']:.8g} | "
            f"{100*row['twist_relative_error']:.3g}% | "
            f"{100*row['reaction_torque_relative_error']:.3g}% |"
        )
    lines.extend(["","Native results are an experimental benchmark, not a general design approval."])
    (output/"TORSION_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    if report["status"]!="pass":
        raise ValueError(f"Native twist/reaction torsion verification requires review: {report['records']}")
    return report


def main():
    p=argparse.ArgumentParser(description="Real Gmsh STEP/CalculiX circular torsion benchmark")
    p.add_argument("--out",default="runs/native_torsion")
    p.add_argument("--meshes",nargs="+",type=float,default=(6.,4.))
    args=p.parse_args()
    run_torsion_benchmark(args.out,grids_mm=args.meshes)
    print((Path(args.out)/"TORSION_REPORT.md").read_text())


if __name__=="__main__":
    main()
