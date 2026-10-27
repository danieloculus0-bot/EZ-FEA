"""Verify the exact native STEP-surface artifact used on EZ-FEA Pages."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path


def verify(metadata,stl,run_id=None):
    record=json.loads(Path(metadata).read_text(encoding="utf-8"))
    if record.get("schema")!="ezfea.truss_browser_evidence.v1" or record.get("status")!="archived_real_solver_result_not_live_browser_solve":
        raise ValueError("Truss data isn't a native archived run")
    run=record.get("source_run","")
    if not run.startswith("https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/"):
        raise ValueError("Source run missing")
    if run_id and run!=f"https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/{run_id}":
        raise ValueError("Truss source run doesn't match downloaded artifact")
    g=record["geometry"];n=record["native"]
    if (g.get("type")!="fused_one_solid" or g.get("member_count")!=10 or
        len(g.get("members",[]))!=10 or g["span_mm"]!=600 or g["rise_mm"]!=180 or
        g["support_pads"]["left"]["axes"]!="XYZ" or
        g["support_pads"]["right"]["axes"]!="YZ" or
        g["load_pad"]["force_n"]!=[0,-1000,0]):
        raise ValueError("Truss layout/fixture not the actual Warren reference")
    if (n.get("mesh_type")!="C3D10" or n.get("elements",0)<100 or
        n.get("force_balance_check")!="pass" or
        n.get("moment_balance_check")!="pass" or
        not all(math.isfinite(n.get(k,0)) and n.get(k,0)>0 for k in
                ("max_displacement_mm","peak_von_mises_mpa"))):
        raise ValueError("Source run did not pass physical evidence review")
    b=Path(stl).read_bytes()
    if len(b)<1000 or hashlib.sha256(b).hexdigest()!=g.get("stl_sha256"):
        raise ValueError("STL does not match original fused STEP export")
    if g.get("stl_surface_triangle_count",0)<100:
        raise ValueError("Missing actual STEP surface tessellation")
    if not isinstance(record.get("source_step_sha256"),str) or len(record["source_step_sha256"])!=64:
        raise ValueError("Source STEP provenance missing")
    return record


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("json");p.add_argument("stl");p.add_argument("--run-id")
    a=p.parse_args()
    verified=verify(a.json,a.stl,a.run_id)
    print("Verified native truss website archive:",verified["source_run"],
          "| elements:",verified["native"]["elements"])
