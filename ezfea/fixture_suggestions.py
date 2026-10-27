"""Bounded CAD attachment clues, not inferred engineering boundary conditions.

A cylindrical STEP surface is *evidence* of a manufactured round feature,
not automatically a bolt. We find planar surfaces sharing its CAD edges and
offer plausible support-face suggestions. The operator must confirm which
surfaces actually connect to the fixture before numerical solving.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

SCHEMA="ezfea.fixture_hints.v1"

def choose_coplanar_supports(candidates,max_faces=4):
    """Propose distinct attachment pads on ONE plane, never opposite faces.

    A hole cut through a plate typically touches its front and back planar
    faces. Restraining both would be a fabricated boundary condition.
    Independent same-plane mounting pads can be represented separately,
    subject to explicit review of the real joints.
    """
    if not isinstance(candidates,list):
        raise ValueError("Candidate list required")
    if type(max_faces) is not int or not 1<=max_faces<=8:
        raise ValueError("Bounded support face limit required")
    groups={}
    for row in candidates:
        if not isinstance(row,dict) or "bounds_mm" not in row:
            continue
        bounds=row["bounds_mm"]
        if not isinstance(bounds,(list,tuple)) or len(bounds)!=6 or not all(
            type(v) in (int,float) and math.isfinite(v) for v in bounds):
            continue
        extents=[bounds[i+3]-bounds[i] for i in range(3)]
        flat_axes=[i for i,v in enumerate(extents) if abs(v)<1e-5]
        if not flat_axes:continue
        axis=flat_axes[0]
        # Micron-granularity grouping in the required mm coordinate system.
        key=(axis,round(bounds[axis],3))
        groups.setdefault(key,[]).append(row)
    if not groups:return []
    selected=max(groups.values(),key=lambda rows:(
        sum(int(row.get("round_features_nearby",0)) for row in rows),
        len(rows),-min(row["face"] for row in rows)))
    return [
        row["face"] for row in sorted(
            selected,key=lambda row:(-row.get("round_features_nearby",0),row["face"])
        )[:max_faces]
    ]


def analyze_open_model(gmsh,source_sha256):
    """Read face topology in the already-imported OCCTargetUnit=MM Gmsh model."""
    if not isinstance(source_sha256,str) or len(source_sha256)!=64:
        raise ValueError("Source CAD SHA256 is required")
    faces=[int(tag) for dim,tag in gmsh.model.getEntities(2)]
    face_types={tag:gmsh.model.getType(2,tag).strip().lower() for tag in faces}
    planar=[tag for tag in faces if "plane" in face_types[tag]]
    round_faces=[tag for tag in faces if "cylind" in face_types[tag]]
    edges={}
    for tag in faces:
        edges[tag]={int(t) for dim,t in gmsh.model.getBoundary(
            [(2,tag)],combined=False,oriented=False,recursive=False) if dim==1}
    round_features=[]
    attachment_evidence={}
    for tag in round_faces:
        box=[float(x) for x in gmsh.model.getBoundingBox(2,tag)]
        if not all(math.isfinite(v) for v in box):
            continue
        planes=[]
        for plane in planar:
            shared=edges[tag] & edges[plane]
            if shared:
                planes.append(plane)
                attachment_evidence[plane]=attachment_evidence.get(plane,0)+1
        round_features.append({
            "cylindrical_face":tag,
            "adjacent_planar_faces":sorted(planes),
            "bounds_mm":box,
            "interpretation":"round_attachment_clue_not_a_verified_hole_or_fastener",
        })
    scored=[]
    for tag in planar:
        count=attachment_evidence.get(tag,0)
        if not count:continue
        bounds=[float(x) for x in gmsh.model.getBoundingBox(2,tag)]
        spans=[bounds[i+3]-bounds[i] for i in range(3)]
        flat=sum(abs(s)<1e-5 for s in spans)
        if flat<1:continue
        scored.append({
            "face":tag,"round_features_nearby":count,
            "bounds_mm":bounds,"basis":"plane_with_cylindrical_CAD_edge",
            "constraint_axes_suggested":[1,2,3],
            "assumption":"ideal_fully_restrained_planar_face_not_verified_bolted_joint",
            "confidence":"candidate_not_verified",
        })
    scored.sort(key=lambda row:(-row["round_features_nearby"],row["face"]))
    # Propose distinct mounting pads only when on the same actual plane.
    # Do NOT treat the opposite sides of a drilled plate as two fixtures.
    suggested=choose_coplanar_supports(scored)
    return {
        "schema":SCHEMA,"source_sha256":source_sha256,
        "planar_face_count":len(planar),
        "cylindrical_face_count":len(round_faces),
        "round_features":round_features[:200],
        "support_candidates":scored[:20],
        "suggested_support_faces":suggested,
        "reason":"Round surfaces adjoining planar CAD can indicate fastener locations; check purpose and real fixture",
        "must_confirm_before_solve":True,
        "not_inferred":["actual_bolt_presence","bolt_preload","bearing_contact",
                        "welded_connection","true_pin_or_roller","load_magnitude"],
    }


def check_hints(hints,*,source_sha256,face_ids):
    if not isinstance(hints,dict) or hints.get("schema")!=SCHEMA or hints.get("source_sha256")!=source_sha256:
        raise ValueError("Fixture hints do not match the current STEP file")
    known=set(face_ids)
    if len(known)!=len(face_ids):raise ValueError("Duplicate actual CAD face IDs")
    suggestions=hints.get("suggested_support_faces")
    candidates=hints.get("support_candidates")
    if not isinstance(suggestions,list) or not isinstance(candidates,list):
        raise ValueError("Fixture hint support lists missing")
    if len(suggestions)>4 or len(set(suggestions))!=len(suggestions) or any(type(t) is not int or t not in known for t in suggestions):
        raise ValueError("Hints include unknown/too many fixture faces")
    candidate_ids={row["face"] for row in candidates if isinstance(row,dict) and type(row.get("face")) is int}
    if not set(suggestions)<=candidate_ids or not candidate_ids<=known:
        raise ValueError("Support hint is not grounded in inspected planar STEP surfaces")
    return list(suggestions)
