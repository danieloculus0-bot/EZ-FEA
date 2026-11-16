"""Elastic rigid-plate in-plane bolt-group shear model; identical fasteners.

Consistent units required. Excludes preload, prying, slip and failure criteria.
"""
from dataclasses import dataclass
from math import hypot, isfinite


@dataclass(frozen=True)
class BoltLoad:
    x: float
    y: float
    fx: float
    fy: float
    resultant: float


def distribute_in_plane_load(positions, force_x, force_y, moment_z=0.0):
    """Return individual bolt loads for force and centroidal moment.

    Positive moment is counterclockwise. Returns (centroid, polar_sum, loads).
    """
    if not positions or any(len(p) != 2 for p in positions):
        raise ValueError("Nonempty (x,y) bolt positions required")
    if not all(isfinite(v) for v in (force_x, force_y, moment_z, *(v for p in positions for v in p))):
        raise ValueError("Inputs must be finite")
    n = len(positions)
    cx = sum(x for x, y in positions) / n
    cy = sum(y for x, y in positions) / n
    relative = [(x-cx, y-cy) for x, y in positions]
    j = sum(dx*dx + dy*dy for dx, dy in relative)
    if moment_z and j <= 0:
        raise ValueError("Coincident bolts cannot resist moment")
    loads = []
    for (x,y),(dx,dy) in zip(positions,relative):
        fx = force_x/n - (moment_z*dy/j if moment_z else 0.0)
        fy = force_y/n + (moment_z*dx/j if moment_z else 0.0)
        loads.append(BoltLoad(x,y,fx,fy,hypot(fx,fy)))
    return (cx,cy),j,tuple(loads)
