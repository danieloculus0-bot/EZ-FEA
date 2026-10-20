"""Consistent surface integration for finite Gaussian traction footprints.

A Gaussian footprint is an idealized contact-pad load distribution, *not*
Hertz contact, friction, a bolt preload, or an actual pressure vessel load.
Its total 3D FORCE is specified; integration normalizes its traction to that
force and preserves the discrete force AND moment of the quadrature field.

Quadratic T6 faces use true isoparametric Jacobians and 7-point degree-5
Dunavant triangle quadrature, including curved edge geometry. The computed
nodal forces are consistent FE loads (some corner nodal shares can be
negative); positivity of every individual equivalent force is not required.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math


# barycentric L1,L2,L3, integration weight summing to 1 over a triangle
_TRI_RULE = (
    ((1/3,1/3,1/3), .225),
    ((.059715871789770,.470142064105115,.470142064105115),.132394152788506),
    ((.470142064105115,.059715871789770,.470142064105115),.132394152788506),
    ((.470142064105115,.470142064105115,.059715871789770),.132394152788506),
    ((.797426985353087,.101286507323456,.101286507323456),.125939180544827),
    ((.101286507323456,.797426985353087,.101286507323456),.125939180544827),
    ((.101286507323456,.101286507323456,.797426985353087),.125939180544827),
)


def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def _norm(v):
    return math.sqrt(sum(x*x for x in v))


def _tri6(r,s):
    """Shape values and derivatives dN/dr, dN/ds in Gmsh T6 order."""
    L=(1-r-s,r,s)
    gradL=((-1.,-1.),(1.,0.),(0.,1.))
    shape=[u*(2*u-1) for u in L]
    dndr=[(4*L[i]-1)*gradL[i][0] for i in range(3)]
    dnds=[(4*L[i]-1)*gradL[i][1] for i in range(3)]
    for i,j in ((0,1),(1,2),(2,0)):
        shape.append(4*L[i]*L[j])
        dndr.append(4*(gradL[i][0]*L[j]+L[i]*gradL[j][0]))
        dnds.append(4*(gradL[i][1]*L[j]+L[i]*gradL[j][1]))
    return shape,dndr,dnds


def _tri3(r,s):
    return ([1-r-s,r,s],[-1.,1.,0.],[-1.,0.,1.])


def _integrate(triangles,nodes,center_mm,spread_mm):
    if not triangles or not math.isfinite(spread_mm) or spread_mm<=0:
        raise ValueError("Gaussian footprint requires surface triangles and positive spread")
    if len(center_mm)!=3 or not all(math.isfinite(x) for x in center_mm):
        raise ValueError("Invalid traction center coordinates")
    weighted=defaultdict(float)
    kernel_area=0.
    first=[0.,0.,0.]
    full_area=0.
    nearest=float("inf")
    for tri in triangles:
        if len(tri) not in (3,6):
            raise ValueError("Traction integration requires T3 or T6 face elements")
        points=[nodes[n] for n in tri]
        fn=_tri3 if len(tri)==3 else _tri6
        for l,w in _TRI_RULE:
            shape,ds,dt=fn(l[1],l[2])
            xyz=[sum(shape[k]*points[k][axis] for k in range(len(tri)))
                 for axis in range(3)]
            dx=[sum(ds[k]*points[k][axis] for k in range(len(tri)))
                for axis in range(3)]
            dy=[sum(dt[k]*points[k][axis] for k in range(len(tri)))
                for axis in range(3)]
            jac=_norm(_cross(dx,dy))
            if not math.isfinite(jac) or jac<=0:
                raise ValueError("Degenerate or nonfinite surface quadrature Jacobian")
            dA=.5*w*jac
            full_area+=dA
            d2=sum((xyz[k]-center_mm[k])**2 for k in range(3))
            nearest=min(nearest,math.sqrt(d2))
            intensity=math.exp(-d2/(2*spread_mm**2))
            da=dA*intensity
            kernel_area+=da
            for k in range(3):
                first[k]+=da*xyz[k]
            for idx,n in enumerate(tri):
                weighted[n]+=da*shape[idx]
    if not math.isfinite(kernel_area) or kernel_area<=1.e-14*full_area:
        raise ValueError("Gaussian footprint misses the CAD face: location/spread unsupported")
    # For a footprint restricted to the selected face, the actual net centroid
    # is computed, never silently assumed equal to its Gaussian center.
    actual=tuple(x/kernel_area for x in first)
    weights={node:amount/kernel_area for node,amount in weighted.items()
             if abs(amount)>1e-18*kernel_area}
    if abs(sum(weights.values())-1)>1e-8:
        raise ValueError("Consistent FE equivalent nodal forces do not sum to one")
    if any(not math.isfinite(v) for v in weights.values()):
        raise ValueError("Nonfinite equivalent force")
    discrete=tuple(sum(weights[n]*nodes[n][axis] for n in weights)
                   for axis in range(3))
    if math.dist(actual,discrete)>max(1e-5,1e-7*max(1.,math.dist(actual,(0.,0.,0.)))):
        raise ValueError("Surface moment consistency failed")
    return {
        "weights":weights,
        "reference_center_mm":list(center_mm),
        "resultant_center_mm":list(discrete),
        "weighted_footprint_area_mm2":kernel_area,
        "actual_face_area_mm2":full_area,
        "effective_nominal_traction_factor":full_area/kernel_area,
        "closest_quadrature_distance_to_center_mm":nearest,
        "quadrature":"Dunavant degree-5, 7-point; actual T3/T6 Jacobian",
    }


def gaussian_face_force_weights(triangles,nodes,center_mm,spread_mm):
    """Return normalized nodal weights and a moment-preserving audit record."""
    return _integrate(triangles,nodes,tuple(center_mm),float(spread_mm))


def resultant_force_moment(nodal_forces,nodes):
    """Integrated F and M about model origin; forces keyed (node, 1-based axis)."""
    force=[0.,0.,0.]
    moment=[0.,0.,0.]
    for (node,axis),value in nodal_forces.items():
        if node not in nodes or axis not in (1,2,3) or not math.isfinite(value):
            raise ValueError("Invalid applied nodal force")
        force[axis-1]+=value
        xyz=nodes[node]
        vector=[0.,0.,0.]
        vector[axis-1]=value
        torque=_cross(xyz,vector)
        for i in range(3):
            moment[i]+=torque[i]
    return {"force_n":force,"moment_about_origin_nmm":moment}
