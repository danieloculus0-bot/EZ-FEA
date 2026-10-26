"""Experimental two-solid STEP contact through actual CAD face-to-CCX pairing.

This is a constrained **two coaxial box solids** STEP proof, not generic CAD:
faces are explicitly selected by the exact z=10 material interface, with
physical volumes and boundary nodes verified disjoint. Gmsh generates real
C3D10 tetrahedral meshes in both bodies, and native CalculiX contact handles
the compressive interface, not a tie or common mesh node.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .mesh import Mesh, gmsh_to_calculix_tet10
from .native_pressure import exterior_face_mapping
from .contact_benchmarks import _base_reaction_from_native_dat
from .solver import run_calculix


def make_two_body_step(path):
    """Export independent touching solids as a real STEP assembly."""
    import gmsh
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.model.add("two_independent_contact_blocks")
        occ=gmsh.model.occ
        occ.addBox(0,0,0,10,10,10)
        occ.addBox(0,0,10,10,10,10)
        occ.synchronize()
        if len(gmsh.model.getEntities(3))!=2:
            raise ValueError("STEP fixture must contain exactly two independent volumes")
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    return path


def mesh_contact_step(step_file,mesh_size_mm=7.,*,joint_plan=None):
    """Mesh two STEP volumes independently; verify topology and boundary IDs."""
    if not (math.isfinite(mesh_size_mm) and mesh_size_mm>0):
        raise ValueError("Positive finite mesh size required")
    import gmsh
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.option.setNumber("Mesh.MeshSizeMax",mesh_size_mm)
        gmsh.option.setNumber("Mesh.MeshSizeMin",mesh_size_mm/3)
        gmsh.model.add("EZ-FEA-two-solid-STEP")
        gmsh.option.setString("Geometry.OCCTargetUnit","MM")
        gmsh.model.occ.importShapes(str(step_file))
        gmsh.model.occ.synchronize()
        bodies=sorted(tag for _,tag in gmsh.model.getEntities(3))
        if len(bodies)!=2:
            raise ValueError("Contact STEP must contain exactly 2 independent solids")
        def select_boundary(body,z):
            faces=[tag for _,tag in gmsh.model.getBoundary(
                [(3,body)],oriented=False,recursive=False) if
                abs(gmsh.model.occ.getCenterOfMass(2,tag)[2]-z)<1e-5 and
                abs(gmsh.model.getBoundingBox(2,tag)[2]-z)<1e-5 and
                abs(gmsh.model.getBoundingBox(2,tag)[5]-z)<1e-5]
            if len(faces)!=1:
                raise ValueError(f"Expected one distinct CAD face at z={z} on volume {body}")
            return faces[0]
        bottom,top=sorted(bodies,key=lambda b:gmsh.model.occ.getCenterOfMass(3,b)[2])
        base_fixed=select_boundary(bottom,0.)
        base_contact=select_boundary(bottom,10.)
        pad_contact=select_boundary(top,10.)
        pad_top=select_boundary(top,20.)
        if base_contact==pad_contact:
            raise ValueError("Assembly STEP shares a CAD contact face; independent interface required")
        if joint_plan is not None:
            if joint_plan.get("schema")!="ezfea.reviewed_contact_plan.v1":
                raise ValueError("Expected verified reviewed joint plan")
            if (joint_plan.get("base_component")!=bottom or
                joint_plan.get("pad_component")!=top or
                joint_plan.get("base_face")!=base_contact or
                joint_plan.get("pad_face")!=pad_contact):
                raise ValueError("Reviewed Joint Matrix face/component IDs do not match source STEP")
            import hashlib
            if hashlib.sha256(Path(step_file).read_bytes()).hexdigest()!=joint_plan.get("source_step_sha256"):
                raise ValueError("Reviewed STEP hash changed after mate scan")
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(2)
        tags,coords,_=gmsh.model.mesh.getNodes()
        nodes={int(n):tuple(float(v) for v in coords[i*3:i*3+3])
               for i,n in enumerate(tags)}
        elements={}
        body_element_ids={}
        body_node_ids={}
        for b in (bottom,top):
            types,eids,connections=gmsh.model.mesh.getElements(3,b)
            if set(int(t) for t in types)!={11}:
                raise ValueError("Contact STEP backend expects quadratic C3D10 only")
            ids=[]
            for labels,raw in zip(eids,connections):
                for i,tag in enumerate(labels):
                    eid=int(tag)
                    conn=tuple(int(x) for x in raw[10*i:10*(i+1)])
                    elements[eid]=gmsh_to_calculix_tet10(conn)
                    ids.append(eid)
            if not ids:
                raise ValueError("Missing contact STEP body volume mesh")
            body_element_ids[b]=ids
            body_node_ids[b]={node for eid in ids for node in elements[eid]}
        if body_node_ids[bottom] & body_node_ids[top]:
            raise ValueError("Two STEP parts have shared nodes: not a physical contact interface")
        def face_nodes(tag):
            values,_,_=gmsh.model.mesh.getNodes(2,tag,True)
            return set(int(n) for n in values)
        fixed_nodes=face_nodes(base_fixed)
        upper_nodes=face_nodes(pad_top)
        if not fixed_nodes or not upper_nodes:
            raise ValueError("Missing top or bottom boundary nodes")
        if fixed_nodes&upper_nodes:
            raise ValueError("Solid support and load face nodes overlap")
        surf={}
        for name,face_id in (("base",base_contact),("pad",pad_contact)):
            types,_,raw=gmsh.model.mesh.getElements(2,face_id)
            tri=[]
            for etype,connectivity in zip(types,raw):
                if int(etype)!=9:
                    raise ValueError("Contact faces must be quadratic T6")
                tri.extend(tuple(int(n) for n in connectivity[i:i+6])
                           for i in range(0,len(connectivity),6))
            if not tri:
                raise ValueError("Contact face has no tetra face triangles")
            surf[face_id]=tri
        mesh=Mesh(nodes,elements,sorted(fixed_nodes),{},0.,
                  element_type="C3D10",surface_triangles_by_face=surf)
        mbase=exterior_face_mapping(mesh,base_contact)
        mpad=exterior_face_mapping(mesh,pad_contact)
        if not mbase or not mpad:
            raise ValueError("No nonshared contact surfaces created")
        if any(el not in body_element_ids[bottom] for el,_,_ in mbase) or \
           any(el not in body_element_ids[top] for el,_,_ in mpad):
            raise ValueError("Contact surfaces reversed or include other body's tets")
        return {
            "nodes":nodes,"elements":elements,"base_fixed":sorted(fixed_nodes),
            "pad_top":sorted(upper_nodes),
            "base_contact":[[e,f] for e,f,_ in mbase],
            "pad_contact":[[e,f] for e,f,_ in mpad],
            "body_elements":{str(k):len(v) for k,v in body_element_ids.items()},
            "body_nodes":{str(k):len(v) for k,v in body_node_ids.items()},
            "shared_node_count":0,
            "source_step":str(step_file),
        }
    finally:
        gmsh.finalize()


def write_step_contact_deck(model,path,*,compression=True,contact=True):
    """One real C3D10 multi-body deck; contact *optional* control."""
    nodes=model["nodes"]
    lines=["*HEADING","EZ-FEA two-body STEP contact experimental C3D10",
           "*NODE"]
    lines.extend(f"{n}, {v[0]:.12g}, {v[1]:.12g}, {v[2]:.12g}"
                 for n,v in sorted(nodes.items()))
    lines.append("*ELEMENT, TYPE=C3D10, ELSET=ALL")
    for n,v in sorted(model["elements"].items()):
        lines.append(f"{n}, {', '.join(map(str,v))}")
    for label,key in (("BASE_FIXED","base_fixed"),("PAD_TOP","pad_top")):
        lines.append(f"*NSET, NSET={label}")
        ids=model[key]
        for i in range(0,len(ids),12):
            lines.append(", ".join(map(str,ids[i:i+12])))
    lines.extend(["*MATERIAL, NAME=STEEL","*ELASTIC","200000, 0.26",
                  "*SOLID SECTION, ELSET=ALL, MATERIAL=STEEL"])
    if contact:
        for label,key in (("BASE_CONTACT","base_contact"),("PAD_CONTACT","pad_contact")):
            lines.append(f"*SURFACE, NAME={label}, TYPE=ELEMENT")
            lines.extend(f"{e}, S{side}" for e,side in model[key])
        lines.extend(["*SURFACE INTERACTION, NAME=FRICTIONLESS",
                      "*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR",
                      "100000",
                      "*CONTACT PAIR, INTERACTION=FRICTIONLESS, TYPE=SURFACE TO SURFACE",
                      "PAD_CONTACT, BASE_CONTACT"])
    displacement=-.001 if compression else .001
    lines.extend(["*STEP, NLGEOM=YES, INC=200","*STATIC","0.1, 1., 1.e-8, 0.1",
                  "*BOUNDARY","BASE_FIXED, 1, 3, 0","PAD_TOP, 1, 2, 0",
                  f"PAD_TOP, 3, 3, {displacement:.10g}",
                  "*NODE PRINT, NSET=BASE_FIXED","RF",
                  "*NODE PRINT, NSET=PAD_TOP","U",
                  "*EL PRINT, ELSET=ALL","S",
                  "*NODE FILE","U","*EL FILE","S","*END STEP"])
    Path(path).write_text("\n".join(lines)+"\n",encoding="utf-8")


def _native_base_reaction(file,base_nodes):
    from .results import read_dat
    rows=read_dat(Path(file))["reactions"]
    if not rows or {int(x[0]) for x in rows}!=set(base_nodes):
        raise ValueError("Missing or incomplete STEP assembly support reactions")
    return [sum(x[i] for x in rows) for i in (1,2,3)]


def run_step_contact(root="runs/step_contact",*,mesh_size_mm=7.,source_step=None,joint_plan=None):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    if joint_plan is not None and source_step is None:
        raise ValueError("A reviewed contact plan requires its original STEP")
    cad=Path(source_step) if source_step is not None else make_two_body_step(root/"two_unmerged_steel_parts.step")
    model=mesh_contact_step(cad,mesh_size_mm,joint_plan=joint_plan)
    cases=(("compression_contact",True,True),
           ("compression_disconnected",True,False),
           ("separation_contact",False,True))
    records=[]
    for name,compress,connected in cases:
        dest=root/name
        dest.mkdir(parents=True,exist_ok=True)
        deck=dest/"analysis.inp"
        write_step_contact_deck(model,deck,compression=compress,contact=connected)
        run_calculix(deck,timeout_seconds=240)
        reaction=_native_base_reaction(dest/"analysis.dat",model["base_fixed"])
        records.append({
            "scenario":name,"contact":connected,
            "top_displacement_mm":(-.001 if compress else .001),
            "bottom_reaction_n":reaction,
            "bottom_normal_reaction_n":abs(reaction[2]),
        })
    results={x["scenario"]:x for x in records}
    comp=results["compression_contact"]["bottom_normal_reaction_n"]
    control=results["compression_disconnected"]["bottom_normal_reaction_n"]
    opening=results["separation_contact"]["bottom_normal_reaction_n"]
    if comp<1. or control>max(.05,.01*comp) or opening>max(.05,.01*comp):
        raise ValueError(f"Imported STEP contact failed compression/release checks: {records}")
    report={
        "schema":"ezfea.step_two_body_contact.v1",
        "reviewed_joint_plan":joint_plan,
        "element_type":"C3D10",
        "STEP_input_has_two_independent_solids":True,
        "shared_mesh_nodes":model["shared_node_count"],
        "volume_element_counts":model["body_elements"],
        "contact_surface_faces":{s:len(model[s]) for s in ("base_contact","pad_contact")},
        "cases":records,
        "engineering_validation":"not_established",
        "limitations":"two axis-aligned coaxial solids, prescribed displacement; not arbitrary STEP contact wizard or validated stresses",
    }
    (root/"step_contact_evidence.json").write_text(json.dumps(report,indent=2)+"\n")
    lines=["# Actual separate-solid STEP C3D10 frictionless contact experiment","",
           "Two STEP solids meshed independently with zero shared nodes.",
           "",
           "| Scenario | Contact? | Base normal reaction (N) |",
           "|---|---|---:|"]
    for row in records:
        lines.append(f"| {row['scenario']} | {'yes' if row['contact'] else 'no'} | "
                     f"{row['bottom_normal_reaction_n']:.6g} |")
    lines.extend(["","Native compression/opening/no-contact checks were executed in CalculiX.",
                  "Surface pairs were matched to real CAD and C3D10 tetra faces.",
                  "This is not a validated general CAD assembly solver."])
    (root/"STEP_CONTACT_REPORT.md").write_text("\n".join(lines)+"\n")
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="runs/step_contact")
    p.add_argument("--mesh",type=float,default=7.)
    args=p.parse_args()
    run_step_contact(args.out,mesh_size_mm=args.mesh)
    print((Path(args.out)/"STEP_CONTACT_REPORT.md").read_text())


if __name__=="__main__":
    main()
