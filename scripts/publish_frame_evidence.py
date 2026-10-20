"""Publish *actual* archived native frame metrics as browser-safe JSON.

Do not run a new solve or manufacture any missing data. This fails closed if a
case is missing, failed, mismatched, or outside force-equilibrium tolerance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from ezfea.frame_benchmarks import STUDIES, geometry_definition_sha256

NAMES = {
    "01_portal_vertical": "Open portal — downward",
    "02_rectangle_racking": "Rectangle — sideways",
    "03_braced_racking": "Braced rectangle — sideways",
    "04_portal_racking": "Open portal — sideways",
    "05_rectangle_vertical": "Rectangle — downward",
    "06_braced_vertical": "Braced rectangle — downward",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def export_frame_evidence(root: Path, destination: Path, *,
                          source_run: str, source_commit: str):
    summary = load_json(root / "suite_summary.json")
    if summary.get("schema") != "ezfea.frame_suite.v1":
        raise ValueError("Unsupported frame solver suite format")
    reported = summary.get("case_results")
    if not isinstance(reported, list):
        raise ValueError("Frame suite summary is incomplete")
    if [x.get("key") for x in reported] != [spec.key for spec in STUDIES]:
        raise ValueError("Frame suite does not contain the expected study identities")
    studies = []
    for spec in STUDIES:
        folder = root / spec.key
        definition = load_json(folder / "specimen.json")
        latest = load_json(folder / "latest_result.json")
        if (definition.get("schema") != "ezfea.frame_specimen.v1" or
            definition.get("identity_sha256") != geometry_definition_sha256(spec) or
            latest.get("specimen") != geometry_definition_sha256(spec) or
            latest.get("status") != "completed"):
            raise ValueError(f"{spec.key}: failed provenance/solve-status verification")
        metrics = latest["results"]
        mesh = latest["mesh"]
        if (metrics.get("force_balance_check") != "pass" or
            not (0 <= metrics["force_balance_relative_error"] <= 0.01) or
            not (metrics["max_displacement_mm"] > 0) or
            not (metrics["max_von_mises_mpa"] > 0) or
            not mesh.get("nodes", 0) > 0 or
            not mesh.get("elements", 0) > 0):
            raise ValueError(f"{spec.key}: unusable CalculiX results")
        if (len(definition["loads"]) < 1 or len(definition["supports"]) < 1
            or definition["material"]["elastic_modulus_mpa"] <= 0):
            raise ValueError(f"{spec.key}: no actual case setup")
        entry = {
            "key": spec.key,
            "name": NAMES[spec.key],
            "construction": spec.construction,
            "model_dimensions_mm": {
                "width": spec.width_mm,
                "height": spec.height_mm,
                "depth": spec.depth_mm,
                "member": spec.member_mm,
                "brace": spec.brace_mm,
            },
            "force_n": list(spec.load_n),
            "material_name": definition["material"]["name"],
            "elastic_modulus_mpa": definition["material"]["elastic_modulus_mpa"],
            "yield_mpa": definition["material"]["yield_mpa"],
            "max_displacement_mm": metrics["max_displacement_mm"],
            "max_von_mises_mpa": metrics["max_von_mises_mpa"],
            "force_balance_relative_error": metrics["force_balance_relative_error"],
            "mesh_nodes": mesh["nodes"],
            "mesh_elements": mesh["elements"],
            "mesh_size_mm": definition["mesh_size_mm"],
            "model_definition_sha256": definition["identity_sha256"],
            "solver_source": metrics.get("source", "analysis.dat"),
            "force_balance_check": "pass",
        }
        studies.append(entry)
    if not (studies[2]["max_displacement_mm"] < studies[1]["max_displacement_mm"]):
        raise ValueError("Braced lateral stiffness regression failed")
    evidence = {
        "schema": "ezfea.frame_evidence.v1",
        "source": "Gmsh + native CalculiX, published from GitHub Actions",
        "source_run": source_run,
        "source_commit": source_commit,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_type": "Single-material linear static, C3D4 solid tets, fully restrained bottom faces",
        "units": {"length": "mm", "force": "N", "stress": "MPa"},
        "studies": studies,
        "notice": "Verified archived solver metrics for fixed examples. Not a new analysis of browser uploads. "
                  "Single mesh; no contact, nonlinear behavior or design sign-off.",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--run-url", required=True)
    p.add_argument("--commit", required=True)
    args = p.parse_args()
    out = export_frame_evidence(args.root,args.out,
                                source_run=args.run_url,source_commit=args.commit)
    print(f"Published {len(out['studies'])} verified real-solver frame cases")


if __name__ == "__main__":
    main()
