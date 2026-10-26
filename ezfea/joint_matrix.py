"""Joint Matrix editing model, independent of FEA solver-specific constraints.

Supports Excel-style column validation, range fill, multi-row paste, and
copy without equating labels like "welded" with a specific mechanical
model. All user edits are explicit; automatic mate detection leaves joints
UNASSIGNED until the user selects a physical classification.
"""
from __future__ import annotations
import csv
import io
import json

JOINT_TYPES=("Unassigned","Welded","Bolted","Pinned","Bearing",
             "Bonded","Sliding","Contact only")
FIELDS=("joint_id","component_a","component_b","face_a","face_b",
        "joint_type","joint_confirmation","mechanical_model")
EDITABLE=("joint_type","joint_confirmation","mechanical_model")
PHYSICS_MODELS=("unassigned","ideal_bonded","frictionless_contact",
                "experimental_separable_contact")


def display_type(value):
    if not isinstance(value,str):
        raise ValueError("Joint type must be text")
    for kind in JOINT_TYPES:
        if kind.casefold()==value.strip().casefold() or \
           kind.lower().replace(" ","_")==value.strip().lower():
            return kind
    raise ValueError(f"Unknown joint type {value!r}")


def matrix_from_graph(graph):
    if graph.get("schema")!="ezfea.assembly_joint_graph.v1":
        raise ValueError("Expected a verified geometric joint graph")
    rows=[]
    for joint in graph["joints"]:
        rows.append({
            "joint_id":joint["joint_id"],
            "component_a":joint["component_a"],
            "component_b":joint["component_b"],
            "face_a":joint["face_a"],
            "face_b":joint["face_b"],
            "joint_type":"Unassigned",
            "joint_confirmation":"not_reviewed",
            "mechanical_model":"unassigned",
            "candidate_kind":joint["candidate_kind"],
            "overlap_area_bbox_mm2":joint["overlap_area_bbox_mm2"],
        })
    return {"schema":"ezfea.joint_matrix.v1",
            "source_step":graph.get("source_step"),
            "source_sha256":graph.get("source_sha256"),
            "ground_component":graph["ground_component"],
            "components":graph["components"],
            "rows":rows,
            "joint_type_options":list(JOINT_TYPES),
            "physical_connection_status":"all_mates_require_review"}


def _change(row,field,value):
    if field not in EDITABLE:
        raise ValueError("Only editable Joint Matrix cells can change")
    result=dict(row)
    if field=="joint_type":
        result[field]=display_type(value)
        result["joint_confirmation"]="explicit_user_choice"
        # Never silently transfer previous solver physics to a newly chosen
        # joint label. The user must separately assign a proven model.
        result["mechanical_model"]="unassigned"
    elif field=="mechanical_model":
        if value not in PHYSICS_MODELS:
            raise ValueError("Unknown or unsupported solver connection model")
        result[field]=value
    else:
        if value not in ("not_reviewed","explicit_user_choice"):
            raise ValueError("Invalid review status")
        result[field]=value
    return result


def fill_down(matrix,field,from_row,to_row):
    """Fill a contiguous spreadsheet range from its first selected row."""
    if not isinstance(from_row,int) or not isinstance(to_row,int) or \
       not 0<=from_row<=to_row<len(matrix["rows"]):
        raise ValueError("Invalid spreadsheet range")
    if field not in EDITABLE:
        raise ValueError("Cannot fill immutable CAD geometry or joint identity")
    source=matrix["rows"][from_row][field]
    updated={**matrix,"rows":[dict(x) for x in matrix["rows"]]}
    for i in range(from_row+1,to_row+1):
        updated["rows"][i]=_change(updated["rows"][i],field,source)
    return updated


def paste_column(matrix,field,start_row,tsv):
    """Paste multi-line values into a single editable column.

    Atomic operation: no changes are returned if any cell is invalid.
    """
    if field not in EDITABLE:
        raise ValueError("Cannot paste over immutable CAD/assembly fields")
    if not isinstance(tsv,str) or not tsv.strip():
        raise ValueError("Paste requires nonempty text")
    vals=[v.strip() for v in tsv.strip().splitlines()]
    if any("\t" in v for v in vals):
        raise ValueError("Single-column paste accepts one field per line")
    if type(start_row)!=int or start_row<0 or start_row+len(vals)>len(matrix["rows"]):
        raise ValueError("Paste exceeds matrix rows")
    updated={**matrix,"rows":[dict(x) for x in matrix["rows"]]}
    for offset,value in enumerate(vals):
        updated["rows"][start_row+offset]=_change(updated["rows"][start_row+offset],field,value)
    return updated


def export_csv(matrix):
    """Plain CSV for spreadsheet import, including non-editable CAD IDs."""
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=FIELDS,extrasaction="ignore")
    writer.writeheader()
    for row in matrix["rows"]:
        writer.writerow(row)
    return output.getvalue()


def validate_matrix(matrix):
    if matrix.get("schema")!="ezfea.joint_matrix.v1":
        raise ValueError("Wrong Joint Matrix schema")
    ids=set()
    for row in matrix["rows"]:
        if row["joint_id"] in ids:
            raise ValueError("Joint ID must be unique")
        ids.add(row["joint_id"])
        display_type(row["joint_type"])
        if row["mechanical_model"] not in PHYSICS_MODELS:
            raise ValueError("Invalid assigned connection model")
        if (row["joint_type"]=="Unassigned" and
            row["mechanical_model"]!="unassigned"):
            raise ValueError("Unassigned joint cannot silently have solver physics")
    return True
