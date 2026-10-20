"""Real CalculiX *DSLOAD normal pressure on exterior tetrahedral CAD faces.

Unlike a FaceLoad/FaceFootprintLoad this pressure is a scalar in N/mm^2
(MPa): CalculiX applies it normal to the current element surface. Separate
FE integration computes the expected resultant force and moment for audit.
This is a native backend prototype; it does not override the current
Analysis API until the loading controls support pressure cases explicitly.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import math

from .load_footprints import _TRI_RULE, _tri3, _tri6, _cross
from .solver import write_input

# CalculiX tetrahedral face numbering from the CCX facial distributed loading
# manual. C3D10 node order is already converted by mesh.py.
_TET_FACES = ((0,1,2),(0,3,1),(1,3,2),(2,3,0))
_OPPOSITE = (3,2,0,1)


def exterior_face_mapping(mesh,face_id):
    """Match Gmsh CAD triangles to an actual tetra face and its CCX S-label.

    The three corner-node sets must match *exactly* and uniquely. Surfaces
    are not inferred from coordinates or by choosing nearest elements.
    """
    triangles=mesh.surface_triangles_by_face.get(face_id)
    if not triangles:
        raise ValueError(f"No explicit meshed triangles on CAD face {face_id}")
    tetfaces=defaultdict(list)
    for element,conn in mesh.elements.items():
        if len(conn) not in (4,10):
            raise ValueError("Only C3D4 and C3D10 pressure faces supported")
        for side,indices in enumerate(_TET_FACES,1):
            tetfaces[frozenset(conn[i] for i in indices)].append((element,side))
    matched=[]
    seen=set()
    for tri in triangles:
        if len(tri)!=(3 if mesh.element_type=="C3D4" else 6):
            raise ValueError("CAD surface triangle order does not match tetra type")
        key=frozenset(tri[:3])
        owners=tetfaces.get(key,())
        if len(owners)!=1:
            raise ValueError("Pressure region must be an exterior face of one tetrahedron")
        el,side=owners[0]
        if (el,side) in seen:
            raise ValueError("Duplicate or overlapping exterior CAD face triangles")
        seen.add((el,side))
        matched.append((el,side,tri))
    return matched


def native_pressure_surface(mesh,face_id,pressure_mpa):
    """Integrate traction -p*n over curved or planar surface with actual T6 map.

    Produces independent expected nodal-equivalent forces for *verification*,
    but the solver deck uses *DSLOAD, not *CLOAD. Also computes true pressure
    resultant and applied bending moment about the global origin.
    """
    if not math.isfinite(pressure_mpa) or pressure_mpa<=0:
        raise ValueError("Compressive pressure must be positive and finite MPa")
    matched=exterior_face_mapping(mesh,face_id)
    loads=defaultdict(float)
    area=0.
    for el,side,tri in matched:
        points=[mesh.nodes[n] for n in tri]
        conn=mesh.elements[el]
        opposite=mesh.nodes[conn[_OPPOSITE[side-1]]]
        fn=_tri3 if len(tri)==3 else _tri6
        for bary,weight in _TRI_RULE:
            shape,du,dv=fn(bary[1],bary[2])
            xyz=[sum(shape[j]*p[i] for j,p in enumerate(points)) for i in range(3)]
            tangent_u=[sum(du[j]*p[i] for j,p in enumerate(points)) for i in range(3)]
            tangent_v=[sum(dv[j]*p[i] for j,p in enumerate(points)) for i in range(3)]
            n=list(_cross(tangent_u,tangent_v))
            jac=math.sqrt(sum(x*x for x in n))
            if not math.isfinite(jac) or jac<=0:
                raise ValueError("Degenerate native pressure surface Jacobian")
            # Select the normal that points into the tetrahedron. Positive
            # compressive DSLOAD pressure pushes toward the element interior.
            inside=sum(n[i]*(opposite[i]-xyz[i]) for i in range(3))
            if abs(inside)<1e-12:
                raise ValueError("Pressure facet orientation is degenerate")
            sign=1 if inside>0 else -1
            traction=[pressure_mpa*sign*n[i]*weight*.5 for i in range(3)]
            area+=jac*weight*.5
            for node,N in zip(tri,shape):
                for axis in range(3):
                    loads[node,axis+1]+=N*traction[axis]
    F=[0.,0.,0.]
    M=[0.,0.,0.]
    for (node,axis),v in loads.items():
        F[axis-1]+=v
        r=mesh.nodes[node]
        q=[0.,0.,0.]
        q[axis-1]=v
        moment=_cross(r,q)
        for i in range(3):
            M[i]+=moment[i]
    if math.sqrt(sum(v*v for v in F))<=0:
        raise ValueError("Integrated pressure produces zero force: inspect normals")
    return {
        "schema":"ezfea.native_pressure.v1",
        "CAD_face_id":face_id,
        "pressure_mpa":pressure_mpa,
        "integrated_area_mm2":area,
        "total_force_n":F,
        "moment_about_origin_nmm":M,
        "element_faces":[[el,side] for el,side,_ in matched],
        "quadrature":"T3/T6 isoparametric 7-point degree-five",
        "equivalent_nodal_forces_for_audit_only":dict(
            (f"{node}:{axis}",v) for (node,axis),v in loads.items()),
        "caveat":"Native normal pressure, not spatially varying pad contact or Hertzian pressure.",
    }


def write_native_pressure_input(case,mesh,destination,face_id,pressure_mpa):
    """Build actual CalculiX pressure deck without adding any CLOADs."""
    if face_id!=case.loaded_face or case.connections or case.loads:
        raise ValueError("Initial native pressure prototype expects single-face legacy Analysis")
    audit=native_pressure_surface(mesh,face_id,pressure_mpa)
    path=write_input(case,mesh,Path(destination))
    content=path.read_text(encoding="utf-8")
    before="*STEP\n*STATIC"
    if content.count(before)!=1:
        raise ValueError("Unable to locate CalculiX loading step")
    faces=["*SURFACE, NAME=EZPRES, TYPE=ELEMENT"]
    faces.extend(f"{el}, S{side}" for el,side in audit["element_faces"])
    content=content.replace(before,"\n".join(faces)+"\n"+before)
    start=content.index("*CLOAD\n")
    end=content.index("*NODE PRINT",start)
    content=content[:start]+f"*DSLOAD\nEZPRES, P, {pressure_mpa:.12g}\n"+content[end:]
    if "*CLOAD" in content:
        raise ValueError("Native pressure input may not contain a duplicate CLOAD")
    path.write_text(content,encoding="utf-8")
    return audit
