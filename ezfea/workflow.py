"""One traceable directory per solve, BEAN handoff without false intelligence claims."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from .core import Analysis
from .mesh import build_mesh
from .solver import run_calculix, write_input
from .results import summarize_dat
from .bean import send_to_bean_inbox

def run_case(case: Analysis, output_root="runs"):
    case.validate()
    input_path = Path(case.step_file)
    out = Path(output_root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True, exist_ok=False)
    import shutil
    source_copy = out / ("source"+input_path.suffix.lower())
    shutil.copy2(input_path, source_copy)
    meta = {"status":"preparing", "input_sha256":hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "units":"N/mm/MPa", "source_file":source_copy.name, "model":case.as_dict(),
            "disclaimer":"EXPERIMENTAL - NOT VALIDATED FOR ENGINEERING SIGN-OFF"}
    (out/"case.json").write_text(json.dumps(meta,indent=2)+"\n", encoding="utf-8")
    try:
        if case.connections:
            mesh = build_mesh(str(input_path), 0, 0, case.mesh_size_mm,
                              constraint_faces=[c.face for c in case.connections],
                              load_faces=[load.face for load in case.loads])
        else:
            mesh = build_mesh(str(input_path),case.fixed_face,case.loaded_face,case.mesh_size_mm)
        meta["mesh"] = {"nodes":len(mesh.nodes),"elements":len(mesh.elements),
                        "loaded_area_mm2":mesh.loaded_area_mm2,"element_type":"C3D4",
                        "connections":len(case.active_connections),
                        "load_regions":len(case.active_loads),
                        "loaded_areas_by_face_mm2":mesh.load_areas_by_face}
        inp = write_input(case,mesh,out/"analysis.inp")
        meta.update(run_calculix(inp))
        metrics = summarize_dat(
            out/"analysis.dat", case.total_force_n, case.material.yield_mpa,
            expected_nodes=len(mesh.nodes),
            expected_elements=len(mesh.elements),
            applied_force_scale_n=case.force_scale_n,
        )
        meta["results"] = metrics
        meta["max_displacement_mm"] = metrics["max_displacement_mm"]
        # A static solver can finish but still produce physically suspect results.
        # Do not advertise an unchecked load balance as validated.
        meta["status"] = (
            "completed" if metrics["force_balance_check"] == "pass"
            else "needs_review"
        )
    except Exception as exc:
        meta["status"], meta["error"] = "failed", str(exc)
        raise
    finally:
        (out/"case.json").write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8")
        handoff = {"schema":"ezfea.bean_handoff.v1","source":"EZ-FEA","analysis":meta,
                   "requested_review":["Check assumptions","Review run quality","Suggest next experiment"],
                   "bean_review_status":"not_requested"}
        (out/"bean_handoff.json").write_text(json.dumps(handoff,indent=2)+"\n",encoding="utf-8")
    try:
        delivered=send_to_bean_inbox(out/"bean_handoff.json")
        if delivered: meta["bean_inbox_queued"]=str(delivered)
    except Exception as exc:
        meta["bean_inbox_error"]=str(exc)
    (out/"case.json").write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8")
    return out
