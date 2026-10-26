"""Conservative candidate face mates and grounded joint graph for STEP assemblies.

Initial detection intentionally supports *axis-aligned planar* faces with
positive overlapping area and tiny plane separation. No inference of welds,
bolts, pins, friction or stiffness from geometry alone. Unrecognized
curved/concentric/fastener mates remain unassigned for later detectors.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
import json
import math
import hashlib
from pathlib import Path

SCHEMA="ezfea.assembly_joint_graph.v1"


def _face_plane(bbox,tol):
    """Find unique constant coordinate of an axis-aligned planar bbox."""
    if len(bbox)!=6 or not all(math.isfinite(v) for v in bbox):
        raise ValueError("Invalid CAD face bounds")
    axes=[i for i in range(3) if abs(bbox[i+3]-bbox[i])<=tol]
    if len(axes)!=1:
        return None
    axis=axes[0]
    return axis,(bbox[axis]+bbox[axis+3])/2.


def match_planar_faces(a,b,*,tolerance_mm=.001,min_overlap_mm2=.01):
    """Geometric mate candidate only; never invent a physical joint type.

    Requires independent component IDs, planar OCC tags, aligned plane,
    in-plane overlap of finite area, and facing-away-from-body orientation.
    """
    if a["component_id"]==b["component_id"]:
        return None
    if not (math.isfinite(tolerance_mm) and tolerance_mm>0 and
            math.isfinite(min_overlap_mm2) and min_overlap_mm2>0):
        raise ValueError("Positive geometric tolerances required")
    if a.get("surface_type")!="Plane" or b.get("surface_type")!="Plane":
        return None
    box1=a["bbox_mm"]
    box2=b["bbox_mm"]
    p=_face_plane(box1,tolerance_mm)
    q=_face_plane(box2,tolerance_mm)
    if p is None or q is None or p[0]!=q[0]:
        return None
    axis=p[0]
    gap=abs(p[1]-q[1])
    if gap>tolerance_mm:
        return None
    directions=[k for k in range(3) if k!=axis]
    widths=[]
    for dim in directions:
        width=min(box1[dim+3],box2[dim+3])-max(box1[dim],box2[dim])
        if width<=tolerance_mm:
            return None
        widths.append(width)
    area=widths[0]*widths[1]
    if area<min_overlap_mm2:
        return None
    normal_a=1 if p[1]>a["body_center_mm"][axis] else -1
    normal_b=1 if q[1]>b["body_center_mm"][axis] else -1
    if normal_a==normal_b:
        return None
    return {
        "face_a":a["face_id"],
        "face_b":b["face_id"],
        "component_a":a["component_id"],
        "component_b":b["component_id"],
        "axis":"XYZ"[axis],
        "gap_mm":gap,
        "overlap_area_bbox_mm2":area,
        "candidate_kind":"coincident_planar_faces",
        "geometric_evidence":"Axis-aligned planar CAD faces; positive bounding-rectangle overlap; facing body centers.",
        "confidence":"high_geometric_only",
        "joint_type":"unassigned",
        "joint_confirmation":"not_reviewed",
    }


def build_joint_graph(components,faces,ground_component,*,tolerance_mm=.001):
    """Compute candidate links, branches, cycles and grounded reachability."""
    ids=[int(c["id"]) for c in components]
    if not ids or len(set(ids))!=len(ids):
        raise ValueError("Assembly needs unique component IDs")
    if type(ground_component)!=int or ground_component not in ids:
        raise ValueError("Ground must identify a real assembly component")
    for face in faces:
        if face["component_id"] not in ids:
            raise ValueError("CAD face references missing assembly component")
    found=[]
    for i,a in enumerate(faces):
        for b in faces[i+1:]:
            candidate=match_planar_faces(a,b,tolerance_mm=tolerance_mm)
            if candidate:
                found.append(candidate)
    found.sort(key=lambda e:(min(e["component_a"],e["component_b"]),
                             max(e["component_a"],e["component_b"]),
                             e["face_a"],e["face_b"]))
    for i,joint in enumerate(found,1):
        joint["joint_id"]=f"J-{i:03d}"
    adj=defaultdict(list)
    for j in found:
        a,b=j["component_a"],j["component_b"]
        adj[a].append((b,j["joint_id"]))
        adj[b].append((a,j["joint_id"]))
    # BFS over parts with a separate visited-edge set, preserving multiple
    # face-level mates and possible mechanical closed loops.
    depth={ground_component:0}
    todo=deque([ground_component])
    while todo:
        node=todo.popleft()
        for nxt,_ in adj[node]:
            if nxt not in depth:
                depth[nxt]=depth[node]+1
                todo.append(nxt)
    # Count cycles in an undirected multigraph; multiple paired faces may
    # form loops but should not be silently condensed to a single rigid link.
    parent={x:x for x in ids}
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    cycles=[]
    for joint in found:
        a,b=joint["component_a"],joint["component_b"]
        aa,bb=find(a),find(b)
        if aa==bb:
            cycles.append(joint["joint_id"])
        else:
            parent[bb]=aa
    return {
        "schema":SCHEMA,
        "ground_component":ground_component,
        "components":[{**c,"grounded":c["id"]==ground_component,
                        "ground_depth":depth.get(c["id"]),
                        "reachable_from_ground":c["id"] in depth}
                       for c in components],
        "joints":found,
        "unreachable_components":[x for x in ids if x not in depth],
        "candidate_cycle_edges":cycles,
        "joint_types_inferred":False,
        "physics_readiness":"unassigned_mates_require_human_review",
        "warning":"Coincident CAD faces indicate possible contact, NOT physical weld, bolt, pin, rigid link or load path. Ground reachability is topological, not kinematic stability.",
    }


def inspect_step_mates(path,*,ground_component=None,tolerance_mm=.001):
    """Inspect Gmsh OCC STEP without meshing, limited to planar bbox matches."""
    import gmsh
    path=Path(path)
    if not path.is_file() or path.suffix.lower() not in (".step",".stp"):
        raise ValueError("Existing STEP file required")
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.model.add("EZ-FEA-mate-scanner")
        gmsh.option.setString("Geometry.OCCTargetUnit","MM")
        gmsh.model.occ.importShapes(str(path))
        gmsh.model.occ.synchronize()
        bodies=sorted(tag for dim,tag in gmsh.model.getEntities(3) if dim==3)
        if not bodies:
            raise ValueError("No STEP solids found")
        comps=[{
            "id":body,
            "label":f"Part {body}",
            "center_mm":list(gmsh.model.occ.getCenterOfMass(3,body)),
            "bbox_mm":list(gmsh.model.getBoundingBox(3,body)),
        } for body in bodies]
        faces=[]
        for comp in comps:
            for dim,tag in gmsh.model.getBoundary(
                [(3,comp["id"])],oriented=False,recursive=False):
                if dim!=2:
                    continue
                faces.append({
                    "face_id":tag,
                    "component_id":comp["id"],
                    "body_center_mm":comp["center_mm"],
                    "surface_type":gmsh.model.getType(2,tag),
                    "bbox_mm":list(gmsh.model.getBoundingBox(2,tag)),
                })
        report=build_joint_graph(comps,faces,
            ground_component if ground_component is not None else bodies[0],
            tolerance_mm=tolerance_mm)
        report["source_step"]=str(path)
        report["source_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
        report["face_count_scanned"]=len(faces)
        return report
    finally:
        gmsh.finalize()


def main():
    p=argparse.ArgumentParser(description="Conservative two-/multi-solid assembly mate candidate detection")
    p.add_argument("step")
    p.add_argument("--ground",type=int,default=None)
    p.add_argument("--out",default=None)
    p.add_argument("--tolerance-mm",type=float,default=.001)
    a=p.parse_args()
    result=inspect_step_mates(a.step,ground_component=a.ground,
                              tolerance_mm=a.tolerance_mm)
    pretty=json.dumps(result,indent=2)
    if a.out:
        Path(a.out).write_text(pretty+"\n",encoding="utf-8")
    print(pretty)


if __name__=="__main__":
    main()
