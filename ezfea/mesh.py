"""Gmsh C3D4/C3D10 tetrahedral meshing. Geometry units are mm."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
import math
from .core import Face
from .mesh_checks import audit_tetra_mesh, audit_gmsh_signed_quality

@dataclass
class Mesh:
    nodes: dict[int, tuple[float, float, float]]
    elements: dict[int, tuple[int, ...]]
    fixed_nodes: list[int]
    force_weights: dict[int, float]
    loaded_area_mm2: float
    constraint_nodes: dict[int, list[int]] = field(default_factory=dict)
    load_weights_by_face: dict[int, dict[int, float]] = field(default_factory=dict)
    load_areas_by_face: dict[int, float] = field(default_factory=dict)
    element_type: str = "C3D4"
    surface_triangles_by_face: dict[int, list[tuple[int,...]]] = field(default_factory=dict)
    integrity: dict = field(default_factory=dict)

def _gmsh():
    try:
        import gmsh
    except ImportError as exc:
        raise RuntimeError("Install Gmsh Python API: python -m pip install gmsh") from exc
    return gmsh

def _open_step(gmsh, filename):
    gmsh.model.add("EZ-FEA")
    # Gmsh 4.x normally keeps STEP coordinates in their source units.
    # Explicitly convert imported CAD coordinates to the solver's mm basis.
    # This must be set *before* importShapes, for inspection and meshing alike.
    gmsh.option.setString("Geometry.OCCTargetUnit", "MM")
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

def inspect_step(filename, *, require_single_solid=False):
    """Read real CAD face IDs; GUI can require the supported one-solid scope.

    The default remains permissive because assembly mate detection needs to
    inspect multibody STEP files without pretending they are one connected
    FEA domain.
    """
    gmsh = _gmsh()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        _open_step(gmsh, filename)
        solids=gmsh.model.getEntities(3)
        if require_single_solid and len(solids)!=1:
            raise ValueError(
                f"Imported STEP contains {len(solids)} separate solids. "
                "The main EZ-FEA desktop solver currently supports ONE continuous "
                "solid. Open a single part, or create a physically justified fused "
                "solid for an idealized analysis; separate welds/contact are not "
                "automatically simulated."
            )
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

def distributed_quadratic_force_weights(triangles, nodes):
    """Consistent uniform traction on planar T6 faces.

    Exact quadratic triangular shape-function area integrals yield zero corner
    resultant and A/3 at each midside node. Report physical total force.
    For curved surfaces, this planar area approximation is not exact and must
    eventually be replaced by isoparametric surface quadrature.
    """
    weights=defaultdict(float)
    total=0.
    for tri in triangles:
        if len(tri)!=6:
            raise ValueError("Expected T6 triangular faces.")
        area=triangle_area(*(nodes[n] for n in tri[:3]))
        if area<=0:
            raise ValueError("Degenerate T6 load face.")
        total+=area
        for node in tri[3:]:
            weights[node]+=area/3.
    if total<=0:
        raise ValueError("No T6 load face area.")
    return {node:share/total for node,share in weights.items()},total


def gmsh_to_calculix_tet10(connectivity):
    """Reorder Gmsh edge nodes to CalculiX/Abaqus C3D10 ordering.

    Gmsh edges 5..10: 12,23,31,14,34,24.
    CalculiX C3D10: 12,23,31,14,24,34.
    """
    if len(connectivity)!=10:
        raise ValueError("Gmsh second-order tetrahedron needs exactly 10 nodes.")
    return tuple(connectivity[i] for i in (0,1,2,3,4,5,6,7,9,8))


def build_mesh(step_file, fixed_face, loaded_face, mesh_size_mm, *, constraint_faces=None, load_faces=None, element_type="C3D4"):
    if element_type not in ("C3D4", "C3D10"):
        raise ValueError("Unsupported element type: expected C3D4 or C3D10.")
    if not math.isfinite(mesh_size_mm) or mesh_size_mm <= 0:
        raise ValueError("Mesh size must be finite and positive in mm.")
    gmsh = _gmsh()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.MeshSizeMax", float(mesh_size_mm))
        gmsh.option.setNumber("Mesh.MeshSizeMin", float(mesh_size_mm)/4)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        _open_step(gmsh, step_file)
        # Disconnected solids have no contact or tie physics in this solver.
        if len(gmsh.model.getEntities(3)) != 1:
            raise ValueError("Multi-solid STEP assemblies are not supported yet; no contact/ties are defined.")
        all_faces = {f.tag for f in _faces(gmsh)}
        support_faces = tuple(dict.fromkeys(
            constraint_faces if constraint_faces is not None else (fixed_face,)))
        force_faces = tuple(dict.fromkeys(
            load_faces if load_faces is not None else (loaded_face,)))
        if not support_faces or not force_faces or (
            set(support_faces) | set(force_faces)
        ) - all_faces:
            raise ValueError("CAD face numbering changed or a selection is empty. Reinspect the part.")
        gmsh.model.mesh.generate(3)
        if element_type=="C3D10":
            # Convert the same meshed tetra topology to 10-node quadratic
            # tets; Gmsh supplies midside nodes including on CAD faces.
            gmsh.model.mesh.setOrder(2)
        ids, coords, _ = gmsh.model.mesh.getNodes()
        nodes = {int(n): tuple(float(v) for v in coords[i*3:i*3+3]) for i,n in enumerate(ids)}
        etypes, eids, enodes = gmsh.model.mesh.getElements(3)
        elems = {}
        expected_type, nodes_per_element = (4,4) if element_type=="C3D4" else (11,10)
        for etype, labels, connectivity in zip(etypes, eids, enodes):
            if int(etype)!=expected_type:
                raise RuntimeError(f"Unsupported Gmsh 3D element {etype} for {element_type}.")
            for i,label in enumerate(labels):
                conn=tuple(int(n) for n in connectivity[i*nodes_per_element:(i+1)*nodes_per_element])
                if int(label) in elems:
                    raise ValueError(f"Gmsh reused element ID {int(label)}.")
                elems[int(label)] = (conn if element_type=="C3D4"
                                     else gmsh_to_calculix_tet10(conn))
        if not elems:
            raise ValueError("No solid elements generated.")
        integrity = audit_tetra_mesh(nodes, elems, element_type)
        integrity.update(audit_gmsh_signed_quality(
            gmsh.model.mesh.getElementQualities(sorted(elems), "minSICN"), len(elems)
        ))
        support_nodes = {}
        for face in support_faces:
            ids, _, _ = gmsh.model.mesh.getNodes(2, face, True)
            support_nodes[face] = sorted(set(int(n) for n in ids))
            if not support_nodes[face]:
                raise ValueError(f"Connection face {face} has no nodes.")
        fixed_nodes = sorted({n for group in support_nodes.values() for n in group})
        surface_weights, surface_areas = {}, {}
        surface_triangles = {}
        for face in force_faces:
            ttypes, _, tnodes = gmsh.model.mesh.getElements(2, face)
            tris = []
            expected_tri, stride=(2,3) if element_type=="C3D4" else (9,6)
            for etype, connectivity in zip(ttypes, tnodes):
                if int(etype)!=expected_tri:
                    raise ValueError(f"Expected Gmsh type {expected_tri} surface triangles.")
                tris.extend(tuple(int(n) for n in connectivity[i:i+stride])
                            for i in range(0,len(connectivity),stride))
            if not tris:
                raise ValueError(f"Loaded face {face} has no surface triangles.")
            surface_triangles[face]=tris
            surface_weights[face], surface_areas[face] = (
                distributed_force_weights(tris,nodes) if element_type=="C3D4"
                else distributed_quadratic_force_weights(tris,nodes))
        weights = surface_weights[force_faces[0]]
        if constraint_faces is None and set(weights) & set(fixed_nodes):
            raise ValueError("Connection and force regions overlap at mesh nodes.")
        return Mesh(nodes, elems, fixed_nodes, weights,
                    sum(surface_areas.values()), support_nodes, surface_weights, surface_areas,
                    element_type, surface_triangles, integrity)
    finally:
        gmsh.finalize()
