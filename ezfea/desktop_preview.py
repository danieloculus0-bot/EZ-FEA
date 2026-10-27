"""True STEP CAD-face tessellation and minimal rotatable Tk viewer geometry.

Gmsh runs only in the independent CLI worker's MAIN thread. Every polygon
retains the same OCC CAD surface tag that Analysis uses as its boundary face.
The Tk viewer renders an orthographic illustration of these actual CAD
surfaces; it does not perform stress physics, surface fitting or ray casting
on the full solid.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

MAX_PREVIEW_TRIANGLES=9500
SCHEMA="ezfea.cad_face_preview.v1"


def extract_step_faces(source, *, triangle_limit=MAX_PREVIEW_TRIANGLES):
    """Mesh original STEP *surfaces* with Gmsh, keeping CAD face identity."""
    import gmsh
    source=Path(source)
    if not source.is_file() or source.suffix.lower() not in (".step",".stp"):
        raise ValueError("Choose an existing STEP file")
    if type(triangle_limit) is not int or triangle_limit<3:
        raise ValueError("Invalid preview triangle limit")
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.model.add("EZ-FEA actual CAD surface preview")
        gmsh.option.setString("Geometry.OCCTargetUnit","MM")
        gmsh.model.occ.importShapes(str(source))
        gmsh.model.occ.synchronize()
        if len(gmsh.model.getEntities(3))!=1:
            raise ValueError("Viewer supports one closed STEP solid; assemblies require explicit physics")
        faces=sorted(int(tag) for _,tag in gmsh.model.getEntities(2))
        if len(faces)<2:
            raise ValueError("STEP model has too few selectable CAD faces")
        bbox=gmsh.model.getBoundingBox(3,gmsh.model.getEntities(3)[0][1])
        extents=[bbox[j+3]-bbox[j] for j in range(3)]
        diagonal=math.sqrt(sum(d*d for d in extents))
        if not math.isfinite(diagonal) or diagonal<=0:
            raise ValueError("CAD has an invalid bounding box")
        mesh_size=diagonal/24.
        gmsh.option.setNumber("Mesh.MeshSizeMin",mesh_size*.70)
        gmsh.option.setNumber("Mesh.MeshSizeMax",mesh_size*1.35)
        gmsh.model.mesh.generate(2)
        all_ids,xyz,_=gmsh.model.mesh.getNodes()
        nodes={int(tag):tuple(float(v) for v in xyz[i*3:i*3+3])
               for i,tag in enumerate(all_ids)}
        triangles=[]
        for face in faces:
            types,_,blocks=gmsh.model.mesh.getElements(2,face)
            for kind,block in zip(types,blocks):
                if int(kind)!=2:
                    raise ValueError("Surface preview expects linear triangular CAD tessellation")
                for start in range(0,len(block),3):
                    if len(triangles)>=triangle_limit:
                        raise ValueError("STEP preview exceeds triangle budget; use smaller CAD or face IDs under More settings")
                    ids=[int(v) for v in block[start:start+3]]
                    if len(ids)!=3 or len(set(ids))<3 or any(i not in nodes for i in ids):
                        raise ValueError("CAD face triangle is invalid")
                    tri=[nodes[i] for i in ids]
                    if not all(math.isfinite(coord) for p in tri for coord in p):
                        raise ValueError("Nonfinite CAD triangle coordinates")
                    triangles.append({"face":face,"points":tri})
        if not triangles:
            raise ValueError("No selectable CAD surface triangles were produced")
        observed={t["face"] for t in triangles}
        if observed!=set(faces):
            raise ValueError("One or more CAD faces have no selectable triangles")
        return {
            "schema":SCHEMA,"source_sha256":sha,
            "cad_face_ids":faces,"triangles":triangles,
            "triangle_count":len(triangles),
            "basis":"source STEP imported as millimeters",
        }
    finally:
        gmsh.finalize()


def validate_preview(data,*,expected_sha,expected_faces):
    """Prevent stale/foreign rendered CAD from selecting real solver faces."""
    if not isinstance(data,dict) or data.get("schema")!=SCHEMA or data.get("source_sha256")!=expected_sha:
        raise ValueError("Preview is not from the currently opened STEP part")
    faces=data.get("cad_face_ids")
    if (not isinstance(faces,list) or sorted(faces)!=sorted(expected_faces)
            or len(faces)!=len(set(faces)) or not faces
            or any(type(f) is not int or f<=0 for f in faces)):
        raise ValueError("Preview CAD face IDs differ from the inspected STEP file")
    tris=data.get("triangles")
    if not isinstance(tris,list) or not 1<=len(tris)<=MAX_PREVIEW_TRIANGLES:
        raise ValueError("No valid bounded STEP surface preview")
    if data.get("triangle_count")!=len(tris):
        raise ValueError("Preview triangle count mismatch")
    covered=set()
    clean=[]
    for tri in tris:
        if not isinstance(tri,dict) or type(tri.get("face")) is not int or tri["face"] not in faces:
            raise ValueError("Preview triangle has unknown original STEP surface")
        pts=tri.get("points")
        if not isinstance(pts,list) or len(pts)!=3 or any(
            not isinstance(p,(list,tuple)) or len(p)!=3 or any(
                type(v) not in (int,float) or not math.isfinite(v) for v in p)
            for p in pts):
            raise ValueError("Preview has an invalid 3D CAD triangle")
        covered.add(tri["face"])
        clean.append((tri["face"],tuple(tuple(p) for p in pts)))
    if covered!=set(faces):
        raise ValueError("Preview omitted a CAD face")
    return clean


def projected_triangles(triangles,width,height,yaw=-0.55,pitch=0.40,zoom=1.0):
    """Orthographic, depth-sorted original CAD face triangles for Tk rendering."""
    if width<=0 or height<=0 or not math.isfinite(zoom) or zoom<=0:
        return []
    if not triangles:
        return []
    coordinates=[p for _,tri in triangles for p in tri]
    minimum=[min(p[i] for p in coordinates) for i in range(3)]
    maximum=[max(p[i] for p in coordinates) for i in range(3)]
    center=[(minimum[i]+maximum[i])/2 for i in range(3)]
    radius=max(math.dist(center,p) for p in coordinates)
    if not math.isfinite(radius) or radius<=0:
        return []
    cy,sy=math.cos(yaw),math.sin(yaw)
    cp,sp=math.cos(pitch),math.sin(pitch)
    scale=.42*min(width,height)/radius*zoom
    rows=[]
    for tag,points in triangles:
        coords=[]
        depths=[]
        for x,y,z in points:
            dx,dy,dz=x-center[0],y-center[1],z-center[2]
            ox=cy*dx-sy*dy
            oy=sy*dx+cy*dy
            vertical=cp*dz-sp*oy
            depth=sp*dz+cp*oy
            coords.append((width/2+scale*ox,height/2-scale*vertical))
            depths.append(depth)
        signed=(coords[1][0]-coords[0][0])*(coords[2][1]-coords[0][1])-(
            coords[1][1]-coords[0][1])*(coords[2][0]-coords[0][0])
        if abs(signed)<.08:
            continue
        rows.append((sum(depths)/3,tag,coords))
    # Largest depth faces are closest and painted last.
    rows.sort(key=lambda item:item[0])
    return rows


def _contains_triangle(pts,x,y):
    (x1,y1),(x2,y2),(x3,y3)=pts
    d=(y2-y3)*(x1-x3)+(x3-x2)*(y1-y3)
    if abs(d)<1e-9:
        return False
    a=((y2-y3)*(x-x3)+(x3-x2)*(y-y3))/d
    b=((y3-y1)*(x-x3)+(x1-x3)*(y-y3))/d
    c=1-a-b
    return min(a,b,c)>=-1e-8


def face_under_cursor(painted,x,y):
    """Pick topmost CAD triangle, respecting the same painter-order as Tk."""
    for _,tag,points in reversed(painted):
        if _contains_triangle(points,x,y):
            return tag
    return None


def main():
    parser=argparse.ArgumentParser(description="Mesh STEP surfaces to show true CAD face IDs")
    parser.add_argument("step")
    parser.add_argument("output")
    args=parser.parse_args()
    data=extract_step_faces(args.step)
    Path(args.output).write_text(json.dumps(data,separators=(",",":"),allow_nan=False),encoding="utf-8")
    print(f"STEP surface preview: {len(data['cad_face_ids'])} faces, {data['triangle_count']} triangles")


if __name__=="__main__":
    main()
