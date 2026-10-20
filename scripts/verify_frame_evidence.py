"""Validate a published native EZ-FEA frame artifact before displaying it.

This is a record/provenance validation layer, not engineering V&V.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import re

from ezfea.frame_benchmarks import STUDIES, geometry_definition_sha256

_RUN_URL = re.compile(r"^https://github\.com/danieloculus0-bot/EZ-FEA/actions/runs/(\d+)$")


def verify_frame_evidence(source: str | Path, *, run_id: str | None = None) -> dict:
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    if data.get("schema") != "ezfea.frame_evidence.v1":
        raise ValueError("Frame evidence schema mismatch")
    match = _RUN_URL.fullmatch(data.get("source_run", ""))
    if match is None or (run_id is not None and match.group(1) != str(run_id)):
        raise ValueError("Frame evidence source run does not match its published artifact")
    if not re.fullmatch(r"[0-9a-f]{40}", str(data.get("source_commit", ""))):
        raise ValueError("Frame evidence source commit is missing")
    studies = data.get("studies")
    if not isinstance(studies, list) or [r.get("key") for r in studies] != [s.key for s in STUDIES]:
        raise ValueError("Frame evidence case identities do not match the solver suite")
    for specimen, row in zip(STUDIES, studies):
        if row.get("force_balance_check") != "pass":
            raise ValueError(f"{specimen.key}: equilibrium did not pass")
        numeric = ("max_displacement_mm", "max_von_mises_mpa",
                   "force_balance_relative_error", "mesh_nodes", "mesh_elements", "mesh_size_mm")
        if any(not isinstance(row.get(k), (int,float)) or not math.isfinite(row[k]) for k in numeric):
            raise ValueError(f"{specimen.key}: numeric result is missing or nonfinite")
        if (row["max_displacement_mm"] <= 0 or row["max_von_mises_mpa"] <= 0 or
            row["mesh_nodes"] < 1 or row["mesh_elements"] < 1 or
            row["mesh_size_mm"] <= 0 or
            not 0 <= row["force_balance_relative_error"] <= 0.01):
            raise ValueError(f"{specimen.key}: invalid physical metrics")
        if (row.get("model_definition_sha256") != geometry_definition_sha256(specimen)
            or row.get("construction") != specimen.construction
            or row.get("force_n") != list(specimen.load_n)):
            raise ValueError(f"{specimen.key}: model identity/load mismatch")
    if not studies[2]["max_displacement_mm"] < studies[1]["max_displacement_mm"]:
        raise ValueError("Braced frame stiffness regression failed")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify an EZ-FEA frame solver publication")
    parser.add_argument("source", type=Path)
    parser.add_argument("--run-id", required=True, help="GitHub Actions source run")
    args = parser.parse_args()
    data = verify_frame_evidence(args.source, run_id=args.run_id)
    print(f"Verified {len(data['studies'])} real solver records from {data['source_run']}")


if __name__ == "__main__":
    main()
