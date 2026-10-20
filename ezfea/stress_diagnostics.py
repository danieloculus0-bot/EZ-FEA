"""Diagnose *where* native CalculiX integration-point stress concentrates.

Only single planar fixture setups are supported. A tetrahedron's four-corner
centroid approximates location of its integration points for zoning; actual
quadratic Gauss-point coordinates are NOT being reconstructed. No stress
averaging or manufactured stress values are used.
"""
from __future__ import annotations

import math
from pathlib import Path

from .results import read_dat, von_mises_mpa


def _node_plane(mesh, node_ids):
    """Identify a unique, single plane from selected face nodes."""
    if not node_ids:
        return None
    points=[mesh.nodes[n] for n in node_ids]
    all_points=list(mesh.nodes.values())
    span=max(max(p[i] for p in all_points)-min(p[i] for p in all_points)
             for i in range(3))
    tol=max(span*1e-7,1e-7)
    flats=[]
    for axis in range(3):
        vals=[p[axis] for p in points]
        if max(vals)-min(vals)<=tol:
            flats.append((axis,sum(vals)/len(vals)))
    if len(flats)!=1:
        return None
    return flats[0]


def fixture_plane(mesh):
    """Return one planar fixed support; refuse false normals for complex fixtures."""
    if not mesh.fixed_nodes:
        raise ValueError("No fixed nodes available to diagnose stress.")
    return _node_plane(mesh,mesh.fixed_nodes)


def load_plane(mesh):
    """Infer a single loaded plane only if nonzero weighted face nodes define it."""
    region_nodes=set(mesh.force_weights)
    for values in mesh.load_weights_by_face.values():
        region_nodes.update(values)
    return _node_plane(mesh,region_nodes)


def stress_distance_bands(dat_file:Path,mesh,*,exclusions_mm=(20.,40.)):
    """Locate actual peak and fixed-distance interior stress from solver .dat.

    Peaks are *integration-point stress tensors*, categorized using the
    host tetrahedron's 4-corner centroid. C3D10 integration points are not
    all at the centroid, so the distance classification is approximate.
    """
    bands=tuple(float(x) for x in exclusions_mm)
    if not bands or any(not math.isfinite(x) or x<0 for x in bands) or             any(a>=b for a,b in zip(bands,bands[1:])):
        raise ValueError("Distances must be ordered nonnegative physical millimeters.")
    plane=fixture_plane(mesh)
    if plane is None:
        return {"status":"not_applicable_nonplanar_fixture",
                "note":"Cannot define a single planar fixture distance from multiple supports."}
    axis,origin=plane
    loaded=load_plane(mesh)
    tables=read_dat(Path(dat_file))
    stresses=tables["stress"]
    if not stresses:
        raise ValueError("Missing native integration-point stress table.")
    peak=(-1.,None,None)
    remote=[(-1.,None,0) for _ in bands]
    far_load=[(-1.,None,0) for _ in bands] if loaded is not None else None
    load_peak_distance=None
    all_elements=set()
    for row in stresses:
        element=int(row[0])
        if element not in mesh.elements:
            raise ValueError(f"Stress element {element} is not in the mesh.")
        corners=mesh.elements[element][:4]
        centroid=sum(mesh.nodes[n][axis] for n in corners)/4.
        dist=abs(centroid-origin)
        load_dist=(abs(sum(mesh.nodes[n][loaded[0]] for n in corners)/4.-loaded[1])
                   if loaded is not None else None)
        stress=von_mises_mpa(*row[2:])
        if not math.isfinite(stress):
            raise ValueError("Nonfinite native stress.")
        all_elements.add(element)
        if stress>peak[0]:
            peak=(stress,element,dist)
            load_peak_distance=load_dist
        for i,limit in enumerate(bands):
            value,idx,count=remote[i]
            is_remote=dist>=limit
            if is_remote:
                if stress>value:
                    value,idx=stress,element
                count+=1
            remote[i]=(value,idx,count)
            if far_load is not None:
                val,host,n=far_load[i]
                if load_dist>=limit:
                    if stress>val:
                        val,host=stress,element
                    n+=1
                far_load[i]=(val,host,n)
    if not all_elements or peak[0]<=0:
        raise ValueError("No valid integration-point stresses.")
    return {
        "status":"plane_distance_diagnostic",
        "fixture_plane_axis":("X","Y","Z")[axis],
        "fixture_plane_coordinate_mm":origin,
        "global_peak_mpa":peak[0],
        "global_peak_element":peak[1],
        "global_peak_host_tet_centroid_distance_mm":peak[2],
        "load_plane_axis":(("X","Y","Z")[loaded[0]] if loaded is not None else None),
        "load_plane_coordinate_mm":(loaded[1] if loaded is not None else None),
        "global_peak_host_tet_centroid_distance_from_load_mm":load_peak_distance,
        "excluded_near_fixture_mm":list(bands),
        "outside_band_max_mpa":[None if r[2]==0 else r[0] for r in remote],
        "outside_band_integration_point_count":[r[2] for r in remote],
        "outside_band_max_element":[r[1] for r in remote],
        "outside_load_band_max_mpa":([None if r[2]==0 else r[0] for r in far_load]
                                     if far_load is not None else None),
        "outside_load_band_integration_point_count":([r[2] for r in far_load]
                                                     if far_load is not None else None),
        "total_stress_integration_points":len(stresses),
        "note":"Measured native Gauss-point stress; distance uses host tetra corner centroid, NOT exact Gauss coordinates. No stress smoothing or proof of singularity.",
    }
