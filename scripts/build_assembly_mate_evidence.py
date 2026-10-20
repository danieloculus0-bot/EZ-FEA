"""Native integration proof: two STEP solids -> mates -> editable Joint Matrix.

Human joint classifications remain UNASSIGNED and never trigger CalculiX
*TIE or fixed DOF constraints merely from face contact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ezfea.contact_step import make_two_body_step
from ezfea.assembly_mates import inspect_step_mates
from ezfea.joint_matrix import matrix_from_graph,validate_matrix,export_csv


def run(output_dir):
    folder=Path(output_dir)
    folder.mkdir(parents=True,exist_ok=True)
    step=make_two_body_step(folder/"two_distinct_parts.step")
    graph=inspect_step_mates(step)
    if len(graph["components"])!=2:
        raise ValueError("Expected two independent STEP solids")
    if len(graph["joints"])!=1:
        raise ValueError(f"Expected one planar mate from two STEP solids; got {len(graph['joints'])}")
    if graph["unreachable_components"] or graph["candidate_cycle_edges"]:
        raise ValueError("Unexpected disconnected assembly or loop")
    j=graph["joints"][0]
    if (j["candidate_kind"]!="coincident_planar_faces" or
        j["joint_type"]!="unassigned" or j["joint_confirmation"]!="not_reviewed"
        or abs(j["overlap_area_bbox_mm2"]-100)>1.e-2):
        raise ValueError("STEP mate geometry or unassigned joint status invalid")
    matrix=matrix_from_graph(graph)
    validate_matrix(matrix)
    if matrix["rows"][0]["joint_type"]!="Unassigned" or \
       matrix["rows"][0]["mechanical_model"]!="unassigned":
        raise ValueError("Geometric mate cannot automatically define a weld/bolt/contact")
    (folder/"mate_graph.json").write_text(json.dumps(graph,indent=2)+"\n")
    (folder/"joint_matrix.json").write_text(json.dumps(matrix,indent=2)+"\n")
    (folder/"joint_matrix.csv").write_text(export_csv(matrix))
    report=(
        "# Real native STEP geometric mate-detection experiment\n\n"
        "Two distinct STEP solids, adjacent at planar z=10 mm, were scanned\n"
        "using Gmsh OpenCascade geometry (not synthetic hard-coded node IDs).\n\n"
        "| Property | Result |\n|---|---|\n"
        f"| Grounded component | {graph['ground_component']} |\n"
        f"| Parts | {len(graph['components'])} |\n"
        f"| Candidate mates | {len(graph['joints'])} |\n"
        f"| Opposing planar overlap | {j['overlap_area_bbox_mm2']:.3f} mm² |\n"
        f"| Joint type inferred | {j['joint_type']} |\n"
        f"| Human confirmation | {j['joint_confirmation']} |\n"
        f"| Native mechanical model | {matrix['rows'][0]['mechanical_model']} |\n\n"
        "This detector currently recognizes opposing axis-aligned planar CAD faces.\n"
        "It is not a general constraint inference engine or bolt/cylinder detector.\n"
        "A matching face is only evidence of a possible mate, not a constraint.\n"
    )
    (folder/"MATE_DETECTION_REPORT.md").write_text(report)
    return graph,matrix


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="runs/mate_evidence")
    args=p.parse_args()
    run(args.out)
    print((Path(args.out)/"MATE_DETECTION_REPORT.md").read_text())


if __name__=="__main__":
    main()
