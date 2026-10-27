"""Isolated main-thread Gmsh/CalculiX worker for EZ-FEA's Tk window.

Gmsh/OpenCASCADE may install signal handlers and cannot safely be started
from an arbitrary Python GUI worker thread. The desktop spawns this module as
a *separate process*, where Gmsh is initialized on the child main thread.

This is the same verified native run_case engine, not a subprocess running a
toy beam or pretending to have solved uploaded CAD.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from .core import Analysis, Material
from .desktop_controller import run_desktop_case


def read_request(path):
    request=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(request,dict) or request.get("schema")!="ezfea.desktop_request.v1":
        raise ValueError("Expected the versioned native desktop request")
    if set(request)!={"schema","case","output_root"} or not isinstance(request["case"],dict):
        raise ValueError("Unexpected native desktop solver request fields")
    meta=request["case"]
    needed={"step_file","fixed_face","loaded_face","force_n",
            "mesh_size_mm","material","element_type"}
    if set(meta)!=needed or not isinstance(meta["material"],dict):
        raise ValueError("Invalid single-solid request parameters")
    if (type(meta["fixed_face"]) is not int or type(meta["loaded_face"]) is not int or
        not isinstance(meta["force_n"],list) or len(meta["force_n"])!=3):
        raise ValueError("Invalid CAD face or XYZ force fields")
    material=Material(**meta["material"])
    case=Analysis(
        meta["step_file"],meta["fixed_face"],meta["loaded_face"],
        tuple(meta["force_n"]),meta["mesh_size_mm"],
        material=material,element_type=meta["element_type"],
    )
    case.validate()
    output_root=request["output_root"]
    if not isinstance(output_root,str) or not output_root.strip():
        raise ValueError("Native results location is missing")
    return case,output_root


def main():
    parser=argparse.ArgumentParser(description="EZ-FEA native desktop 3D solver child")
    parser.add_argument("request",help="Local JSON analysis request")
    parser.add_argument("response",help="Local JSON result response")
    args=parser.parse_args()
    try:
        case,output_root=read_request(args.request)
        result=run_desktop_case(case,output_root=output_root)
        answer={
            "schema":"ezfea.desktop_response.v1",
            "folder":str(result["folder"].resolve()),
            "report":str(result["report"].resolve()),
            "summary":result["summary"],
        }
        Path(args.response).write_text(
            json.dumps(answer,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        print("EZ-FEA native case finished:",result["summary"]["status"])
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    sys.exit(main())
