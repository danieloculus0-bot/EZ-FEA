"""Pre-solve checks for tetrahedral meshes used by the single-solid solver.

These checks do not establish CAD fidelity, material validity, or convergence.
Quadratic-element curvature/inversion is additionally screened using Gmsh's
native signed quality calculation at meshing time.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
import math


# A purely numerical degeneracy threshold, not a quality/convergence target.
_MIN_NORMALIZED_VOLUME = 1.0e-10


def audit_tetra_mesh(nodes, elements, element_type="C3D4"):
    """Reject disconnected/nonmanifold/degenerate solids before writing a deck.

    Connectivity is based on *shared tetrahedral faces*, not just a touching
    vertex or edge. Only one continuous volumetric solid is supported here.
    """
    if element_type not in ("C3D4", "C3D10"):
        raise ValueError("Mesh audit supports only C3D4 or C3D10 elements.")
    if not nodes or not elements:
        raise ValueError("Mesh has no nodes or volume elements.")

    for tag, point in nodes.items():
        if type(tag) is not int or tag <= 0:
            raise ValueError("Mesh node IDs must be positive integers.")
        if len(point) != 3 or not all(math.isfinite(v) for v in point):
            raise ValueError(f"Mesh node {tag} has nonfinite or invalid coordinates.")

    required_count = 4 if element_type == "C3D4" else 10
    parent = {tag: tag for tag in elements}
    if any(type(tag) is not int or tag <= 0 for tag in elements):
        raise ValueError("Element IDs must be positive integers.")

    def root(tag):
        while parent[tag] != tag:
            parent[tag] = parent[parent[tag]]
            tag = parent[tag]
        return tag

    used_nodes = set()
    face_owners = {}
    face_counts = defaultdict(int)
    min_quality = math.inf
    for tag, conn in elements.items():
        if len(conn) != required_count or len(set(conn)) != required_count:
            raise ValueError(f"Element {tag} has missing or repeated node IDs.")
        if not set(conn).issubset(nodes):
            raise ValueError(f"Element {tag} references nodes absent from its mesh.")
        used_nodes.update(conn)

        p0, p1, p2, p3 = (nodes[n] for n in conn[:4])
        a = [p1[i] - p0[i] for i in range(3)]
        b = [p2[i] - p0[i] for i in range(3)]
        c = [p3[i] - p0[i] for i in range(3)]
        six_volume = (a[0] * (b[1]*c[2] - b[2]*c[1])
                      - a[1] * (b[0]*c[2] - b[2]*c[0])
                      + a[2] * (b[0]*c[1] - b[1]*c[0]))
        lengths_sq = [
            sum((u[i] - v[i])**2 for i in range(3))
            for u, v in combinations((p0, p1, p2, p3), 2)
        ]
        longest_sq = max(lengths_sq)
        if not math.isfinite(six_volume) or not math.isfinite(longest_sq) or longest_sq <= 0:
            raise ValueError(f"Element {tag} has nonfinite or degenerate geometry.")
        # A relative check works consistently for mm and inch-sized specimens.
        normalized = abs(six_volume) / (longest_sq**1.5)
        if not math.isfinite(normalized) or normalized <= _MIN_NORMALIZED_VOLUME:
            raise ValueError(f"Element {tag} has nearly zero tetrahedral volume.")
        min_quality = min(min_quality, normalized)

        for tri in combinations(conn[:4], 3):
            facet = tuple(sorted(tri))
            face_counts[facet] += 1
            if face_counts[facet] > 2:
                raise ValueError(f"Nonmanifold mesh: face {facet} belongs to over two tetrahedra.")
            previous = face_owners.setdefault(facet, tag)
            if previous != tag:
                parent[root(tag)] = root(previous)

    # An extraneous unmeshed node is not an acceptable part of a solver deck.
    extras = set(nodes) - used_nodes
    if extras:
        raise ValueError(f"Mesh contains {len(extras)} orphan nodes.")
    components = {root(tag) for tag in elements}
    if len(components) != 1:
        raise ValueError(f"Disconnected volume mesh: {len(components)} face-connected components.")
    return {
        "status": "pass",
        "single_face_connected_volume": True,
        "node_count": len(nodes),
        "element_count": len(elements),
        "minimum_corner_volume_shape_ratio": min_quality,
        "boundary_triangle_count": sum(count == 1 for count in face_counts.values()),
    }


def audit_gmsh_signed_quality(qualities, element_count, *, minimum=1.0e-8):
    """Verify Gmsh's per-element signed curved-element quality report."""
    samples = tuple(float(v) for v in qualities)
    if len(samples) != element_count or not samples:
        raise ValueError("Gmsh signed element quality output is incomplete.")
    if any(not math.isfinite(v) for v in samples):
        raise ValueError("Gmsh signed element quality output contains nonfinite values.")
    value = min(samples)
    if value <= minimum:
        raise ValueError(
            f"Inverted/degenerate mesh element: minimum Gmsh signed quality {value:.8g}."
        )
    return {
        "minimum_signed_inverse_condition": value,
        "low_quality_warning": value < 0.05,
        "quality_name": "minSICN",
    }
