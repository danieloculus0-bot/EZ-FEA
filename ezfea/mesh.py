"""Gmsh import and C3D4 tetrahedral meshing. Geometry units are mm."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from .core import Face

@dataclass
class Mesh:
    nodes: dict[int, tuple[float, float, float]]
    elements: dict[int, tuple[int, int, int, int]]
    fixed_nodes: list[int]
    force_weights: dict[int, float]
    loaded_area_mm2: float

def _gmsh():
    try:
        import gmsh
    except ImportError as exc:
        raise RuntimeError("Install Gmsh Python API: python -m pip install gmsh") from exc
    return gmsh

def _open_step(gmsh, filename):
    gmsh.model.add("EZ-FEA")
    gmsh.model.occ.importShapes(str(filename))
    gmsh.model.occ.synchronize()
    if not gmsh.model.getEntities(3):
        raise ValueError("STEP does not contain a closed solid volume.")

def _faces(gmsh):
    result = []
    for _, tag in sorted(gmsh.model.getEntities(2)):
        center = tuple(float(v) for v in gmsh.model.occ.getCenterOfMass(2, tag))
        bbox = tuple(float(v) for v in gmsh.model.getBoundingBox(2, tag))
        result.append(Face(tag, center, bbox))
    return result

def inspect_step(filename):
    gmsh = _gmsh()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        _open_step(gmsh, filename)
        return _faces(gmsh)
    finally:
        gmsh.finalize()

def triangle_area(a, b, c):
    u = [b[i]-a[i] for i in range(3)]
    v = [c[i]-a[i] for i in range(3)]
    x = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    return 0.5 * sum(t*t for t in x)**0.5

def distributed_force_weights(triangles, nodes):
    """Linear triangular face traction: nodal contributions proportional to area."""
    weights = defaultdict(float)
    total = 0.0
    for tri in triangles:
        a = triangle_area(*(nodes[n] for n in tri))
        if a <= 0:
            raise ValueError("Degenerate load face triangle.")
        total += a
        for node in tri:
            weights[node] += a / 3
    if total <= 0:
        raise ValueError("Load face has zero triangulated area.")
    return {n:w/total for n,w in weights.items()}, total

def build_mesh(step_file, fixed_face, loaded_face, mesh_size_mm):
    gmsh = _gmsh()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.MeshSizeMax", float(mesh_size_mm))
        gmsh.option.setNumber("Mesh.MeshSizeMin", float(mesh_size_mm)/4)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        _open_step(gmsh, step_file)
        all_faces = {f.tag for f in _faces(gmsh)}
        if fixed_face not in all_faces or loaded_face not in all_faces:
            raise ValueError("CAD face numbering changed. Reinspect the part.")
        gmsh.model.mesh.generate(3)
        ids, coords, _ = gmsh.model.mesh.getNodes()
        nodes = {int(n): tuple(float(v) for v in coords[i*3:i*3+3]) for i,n in enumerate(ids)}
        etypes, eids, enodes = gmsh.model.mesh.getElements(3)
        elems = {}
        for etype, labels, connectivity in zip(etypes, eids, enodes):
            if int(etype) != 4:
                raise RuntimeError(f"Unsupported solid element type {etype}. Expected C3D4.")
            for i,label in enumerate(labels):
                elems[int(label)] = tuple(int(n) for n in connectivity[i*4:i*4+4])
        if not elems:
            raise ValueError("No solid elements generated.")
        fixed_ids, _, _ = gmsh.model.mesh.getNodes(2, fixed_face, True)
        fixed_nodes = sorted(set(int(n) for n in fixed_ids))
        if not fixed_nodes:
            raise ValueError("Connection face has no nodes.")
        ttypes, _, tnodes = gmsh.model.mesh.getElements(2, loaded_face)
        tris = []
        for etype, connectivity in zip(ttypes, tnodes):
            if int(etype) != 2:
                raise ValueError("Expected T3 triangles on the load face.")
            tris.extend(tuple(int(n) for n in connectivity[i:i+3]) for i in range(0,len(connectivity),3))
        weights, area = distributed_force_weights(tris, nodes)
        if set(weights) & set(fixed_nodes):
            raise ValueError("Connection and force regions overlap at mesh nodes.")
        return Mesh(nodes, elems, fixed_nodes, weights, area)
    finally:
        gmsh.finalize()
