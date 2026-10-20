"""One traceable directory per solve, BEAN handoff without false intelligence claims."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from .core import Analysis
from .mesh import build_mesh
from .solver import run_calculix, write_input
from .results import max_displacement_mm
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
        mesh = build_mesh(str(input_path),case.fixed_face,case.loaded_face,case.mesh_size_mm)
        meta["mesh"] = {"nodes":len(mesh.nodes),"elements":len(mesh.elements),
                        "loaded_area_mm2":mesh.loaded_area_mm2,"element_type":"C3D4"}
        inp = write_input(case,mesh,out/"analysis.inp")
        meta.update(run_calculix(inp))
        maximum = max_displacement_mm(out/"analysis.dat")
        if maximum is not None:
            meta["max_displacement_mm"] = maximum
        meta["status"] = "completed"
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
