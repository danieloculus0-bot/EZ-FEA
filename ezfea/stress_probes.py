"""Fixed physical-coordinate, element-local stress probes from native CalculiX.

A probe is the SAME (x, y, z) in millimeters on every mesh. We locate it in
the corner-linear tetrahedron and recover a piecewise constant stress TENSOR:
the component-wise average of that host element's native integration-point
stresses. This is a zeroth-order recovery, NOT exact C3D10 interpolation at
the material point. Curved quadratic cells require true inverse isoparametric
mapping for general-purpose CAD; our frame specimen cells are straight-sided.

No peak extrapolation, nearest-Gauss-coordinate substitution, or generated
physics values. Missing/outside/ambiguous input fails rather than fabricating.
"""
from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path

from .results import read_dat, von_mises_mpa

RECOVERY = "element_mean_integration_point_tensor_v1"
BARY_TOL = 1.0e-9
BOUNDARY_WARNING_MARGIN = 0.01


def _dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],
            a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])


def tetra_barycentric(point, corners):
    """Barycentric weights for a straight four-corner physical tetrahedron."""
    if len(point)!=3 or len(corners)!=4 or any(len(p)!=3 for p in corners):
        raise ValueError("Expected 3D point and four tetrahedron corners")
    a,b,c,d=corners
    u=[b[k]-a[k] for k in range(3)]
    v=[c[k]-a[k] for k in range(3)]
    w=[d[k]-a[k] for k in range(3)]
    q=[point[k]-a[k] for k in range(3)]
    det=_dot(u,_cross(v,w))
    if abs(det)<=1e-14:
        raise ValueError("Degenerate solid tetrahedron")
    x=_dot(q,_cross(v,w))/det
    y=_dot(u,_cross(q,w))/det
    z=_dot(u,_cross(v,q))/det
    return (1-x-y-z,x,y,z)


def recover_fixed_stress(dat_file, mesh, probes):
    """Recover measured tensor at fixed specimen coordinates (not global max).

    "value" is a host-element, component-mean integration-point TENSOR.
    Converting that recovered tensor to von Mises is NOT the mean of
    integration-point von Mises values. No interpolation continuity is claimed.
    """
    if mesh.element_type not in ("C3D4","C3D10"):
        raise ValueError("Only C3D4/C3D10 probe recovery is implemented")
    if not isinstance(probes,dict) or not probes:
        raise ValueError("Name at least one fixed physical-coordinate probe")
    for name,p in probes.items():
        if not isinstance(name,str) or not name or len(p)!=3 or \
           any(not isinstance(x,(float,int)) or not math.isfinite(x) for x in p):
            raise ValueError("Probes must have named finite XYZ millimeter coordinates")
    tables=read_dat(Path(dat_file))
    if not tables["stress"]:
        raise ValueError("Native CalculiX integration-point stress is missing")
    by_element=defaultdict(list)
    for row in tables["stress"]:
        element=int(row[0])
        ip=int(row[1])
        if element not in mesh.elements:
            raise ValueError(f"Unknown native stress element {element}")
        if ip in {int(r[0]) for r in by_element[element]}:
            raise ValueError(f"Repeated integration point {ip} for element {element}")
        by_element[element].append((ip,tuple(row[2:])))
    result={}
    for name,p in probes.items():
        # Take the element containing this PHYSICAL coordinate. No nearest
        # stress point or distance threshold masquerading as exact location.
        candidates=[]
        for eid,connectivity in mesh.elements.items():
            corners=[mesh.nodes[n] for n in connectivity[:4]]
            # Fast bounding rejection before tetra barycentric solve.
            if any(p[i]<min(c[i] for c in corners)-1e-7 or
                   p[i]>max(c[i] for c in corners)+1e-7 for i in range(3)):
                continue
            weights=tetra_barycentric(p,corners)
            if min(weights)>=-BARY_TOL and max(weights)<=1+BARY_TOL:
                candidates.append((min(weights),eid))
        if not candidates:
            raise ValueError(f"Stress probe {name} is outside the straight-sided mesh")
        # Highest barycentric margin picks a reproducible host if the probe is
        # on a shared facet. Warn about weakly interior solutions.
        margin,element=max(candidates,key=lambda item:(item[0],-item[1]))
        rows=by_element.get(element,[])
        expected=1 if mesh.element_type=="C3D4" else 4
        if len(rows)!=expected or {r[0] for r in rows}!=set(range(1,expected+1)):
            raise ValueError(
                f"Probe {name} host element {element} has "
                f"{len(rows)} stress points, expected numbered 1..{expected}"
            )
        tensor=[sum(row[1][j] for row in rows)/expected for j in range(6)]
        if any(not math.isfinite(x) for x in tensor):
            raise ValueError("Nonfinite averaged native stress tensor")
        result[name]={
            "coordinate_mm":[float(x) for x in p],
            "von_mises_mpa":von_mises_mpa(*tensor),
            "tensor_mpa":tensor,
            "host_element_id":element,
            "integration_point_count":expected,
            "inside_corner_tetra_margin":margin,
            "location_quality":("near_element_boundary" if margin<BOUNDARY_WARNING_MARGIN
                                else "inside_element"),
            "recovery":RECOVERY,
        }
    return {"schema":"ezfea.fixed_stress_probes.v1",
            "element_type":mesh.element_type,
            "probes":result,
            "note":"Exactly fixed XYZ coordinates; host tetra found by corner-affine barycentrics. Stress is host-element tensor-average of actual integration-point values, not true pointwise C3D10 interpolation. Boundary-adjacent probes are flagged. Not validated for curved quadratic elements."}


def frame_stress_probes(spec):
    """Millimeter coordinates fully inside all three fused frame styles.

    Probes are deliberately off surfaces and symmetry/grid lines, so they
    sample stable specimen positions instead of individual peak elements.
    """
    if spec.width_mm!=240 or spec.height_mm!=180 or spec.member_mm!=20 or spec.depth_mm!=20:
        raise ValueError("Frame probes defined only for the standard 240x180 solid specimens")
    return {
        "left_upright_mid":(9.3,9.2,93.7),
        "upper_left_joint_interior":(14.3,9.2,166.7),
        "upper_right_joint_interior":(225.3,9.2,166.7),
        "top_member_mid":(121.3,9.2,170.7),
    }
