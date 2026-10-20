"""Actual C3D10 pointwise stress tensor recovery from native Gauss XYZ and S.

For a *straight-sided*, homogeneous linear-elastic C3D10 element, quadratic
displacements have an affine spatial gradient, hence the Cauchy stress tensor
is affine in physical XYZ. Four independent Gauss tensors therefore uniquely
determine that local affine field. Reconstruct each tensor COMPONENT at the
requested physical point, then calculate von Mises on the recovered tensor.

This is Gauss-field interpolation / extrapolation within a single element,
NOT nodal averaging, not a global stress smoother, not an independent proof
of accuracy. Curved isoparametric geometries are explicitly rejected.
"""
from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path

from .results import read_dat, von_mises_mpa
from .stress_probes import tetra_barycentric, BARY_TOL, BOUNDARY_WARNING_MARGIN

AFFINE_RECOVERY = "physical_xyz_linear_gauss_tensor_c3d10_v1"
CCX_C3D10_EDGE_NODES = ((0,1,4),(1,2,5),(2,0,6),
                        (0,3,7),(1,3,8),(2,3,9))


def _straight_c3d10(mesh, connectivity):
    """An affine geometric C3D10 must have each midside node at edge midpoint."""
    points=[mesh.nodes[n] for n in connectivity]
    for a,b,mid in CCX_C3D10_EDGE_NODES:
        length=math.dist(points[a],points[b])
        if length<=1e-12:
            raise ValueError("Degenerate C3D10 edge in probe host")
        expected=[(points[a][j]+points[b][j])/2. for j in range(3)]
        if math.dist(points[mid],expected)>max(1e-6,1e-5*length):
            raise ValueError("Curved C3D10 geometry: affine Gauss stress interpolation unsupported")


def recover_affine_gauss_stress(dat_file, mesh, probes):
    """Sample a piecewise-affine *C3D10* stress tensor at unchanged XYZ mm.

    Stress tensors and global Gauss coordinates must both come from *EL PRINT
    S,COORD on the same CalculiX increment. Join rows by (element, point ID),
    never by presumed integration-point order or an undocumented reference.
    """
    if mesh.element_type!="C3D10":
        raise ValueError("Affine Gauss stress reconstruction requires C3D10")
    if not isinstance(probes,dict) or not probes:
        raise ValueError("Provide a nonempty name-to-XYZ probe dictionary")
    for name,point in probes.items():
        if not isinstance(name,str) or not name or \
           not isinstance(point,(tuple,list)) or len(point)!=3 or \
           any(not isinstance(x,(int,float)) or isinstance(x,bool) or
               not math.isfinite(x) for x in point):
            raise ValueError("Probe must have a name and three finite XYZ millimeter values")

    parsed=read_dat(Path(dat_file))
    if not parsed["stress"] or not parsed.get("coordinates"):
        raise ValueError("Native CalculiX S and COORD integration-point tables are both required")
    stresses=defaultdict(dict)
    points=defaultdict(dict)
    for rows,table,n in ((parsed["stress"],stresses,6),
                          (parsed["coordinates"],points,3)):
        for row in rows:
            element,ip=int(row[0]),int(row[1])
            if element not in mesh.elements or not 1<=ip<=4:
                raise ValueError("Invalid native C3D10 integration point identity")
            key=table[element]
            if ip in key or len(row[2:])!=n:
                raise ValueError("Duplicate or malformed C3D10 integration-point table")
            key[ip]=tuple(float(x) for x in row[2:])

    result={}
    for name,xyz in probes.items():
        candidates=[]
        for element,conn in mesh.elements.items():
            if len(conn)!=10:
                raise ValueError("C3D10 mesh contains nonquadratic tetrahedral connectivity")
            corners=[mesh.nodes[n] for n in conn[:4]]
            if any(xyz[i] < min(c[i] for c in corners)-1e-7 or
                   xyz[i] > max(c[i] for c in corners)+1e-7 for i in range(3)):
                continue
            weights=tetra_barycentric(xyz,corners)
            if min(weights)>=-BARY_TOL and max(weights)<=1+BARY_TOL:
                candidates.append((min(weights),element))
        if not candidates:
            raise ValueError(f"Probe {name} outside straight-sided C3D10 mesh")
        margin,element=max(candidates,key=lambda pair:(pair[0],-pair[1]))
        _straight_c3d10(mesh,mesh.elements[element])
        if set(stresses[element])!={1,2,3,4} or set(points[element])!={1,2,3,4}:
            raise ValueError(f"Probe {name} missing matched C3D10 Gauss S/COORD data")
        location=[points[element][ip] for ip in (1,2,3,4)]
        corner_geometry=[mesh.nodes[n] for n in mesh.elements[element][:4]]
        for gp in location:
            logical=tetra_barycentric(gp,corner_geometry)
            if min(logical)<-1e-4 or max(logical)>1+1e-4:
                raise ValueError(f"Native Gauss point outside its C3D10 element {element}")

        # Affine stress tensor reproduction from the measured physical
        # integration point XYZs, not assumed Fortran Gauss-point ordering.
        gauss_weights=tetra_barycentric(xyz,location)
        if not all(math.isfinite(v) for v in gauss_weights) or \
           abs(sum(gauss_weights)-1)>1e-7:
            raise ValueError("Degenerate physical Gauss-point stress interpolation")
        tensor=[
            sum(gauss_weights[i]*stresses[element][i+1][j] for i in range(4))
            for j in range(6)
        ]
        if not all(math.isfinite(v) for v in tensor):
            raise ValueError("Nonfinite recovered physical stress tensor")
        result[name]={
            "coordinate_mm":[float(v) for v in xyz],
            "tensor_mpa":tensor,
            "von_mises_mpa":von_mises_mpa(*tensor),
            "host_element_id":element,
            "integration_point_count":4,
            "native_gauss_coordinates_mm":[list(p) for p in location],
            "gauss_interpolation_weights":list(gauss_weights),
            "inside_corner_tetra_margin":margin,
            "location_quality":("near_element_boundary" if margin < BOUNDARY_WARNING_MARGIN
                                else "inside_element"),
            "recovery":AFFINE_RECOVERY,
        }
    return {
        "schema":"ezfea.fixed_stress_probes.v1",
        "element_type":"C3D10",
        "probes":result,
        "note":"Piecewise-affine tensor field reconstructed from matching *EL PRINT S,COORD Gauss points. Exact for affine stress fields in straight-sided, homogeneous linear-elastic C3D10 elements; extrapolation beyond Gauss hull possible. No element-to-element stress continuity or independent design validation.",
    }
