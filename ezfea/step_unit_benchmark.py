"""Native millimeter/inch STEP import-equivalence test.

The inch test file is independently encoded as a conversion-based STEP
length unit, with numerical geometry authored in inches. Both files are
imported through the public EZ-FEA geometry/solver path. This is a controlled
CAD-translator regression, not proof of arbitrary CAD export compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from .core import Analysis
from .mesh import inspect_step
from .workflow import run_case

_INCH_MM = 25.4
_MM_DECL = re.compile(
    r"#(?P<id>\d+)\s*=\s*\(\s*LENGTH_UNIT\s*\(\s*\)\s*"
    r"NAMED_UNIT\s*\(\s*\*\s*\)\s*"
    r"SI_UNIT\s*\(\s*\.MILLI\.\s*,\s*\.METRE\.\s*\)\s*\)\s*;",
    re.I,
)
_CONTEXT = re.compile(
    r"GLOBAL_UNIT_ASSIGNED_CONTEXT\s*\(\s*\(\s*#(?P<length>\d+)\s*,",
    re.I,
)


def encode_step_in_inches(path):
    """Change the *unit context* of inch-coordinate STEP data to real inches.

    This intentionally fails if the exporter changes its schema layout. Never
    replace arbitrary STEP text or silently assume a unit from the filename.
    """
    file = Path(path)
    data = file.read_text(encoding="utf-8")
    mm = _MM_DECL.findall(data)
    if len(mm) != 1:
        raise ValueError("STEP fixture needs exactly one declared millimeter length unit")
    mm_id = mm[0]
    contexts = list(_CONTEXT.finditer(data))
    if len(contexts) != 1 or contexts[0].group("length") != mm_id:
        raise ValueError("STEP fixture needs one matching GLOBAL_UNIT_ASSIGNED_CONTEXT")
    ids = [int(x) for x in re.findall(r"#(\d+)\s*=", data)]
    if not ids:
        raise ValueError("STEP entity identifiers not found")
    base = max(ids) + 1
    # ISO 10303-41 conversion-based length unit, 25.4 mm per inch.
    declarations = (
        f"#{base}=DIMENSIONAL_EXPONENTS(1.,0.,0.,0.,0.,0.,0.);\n"
        f"#{base+1}=LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE(25.4),#{mm_id});\n"
        f"#{base+2}=(CONVERSION_BASED_UNIT('INCH',#{base+1})"
        f"LENGTH_UNIT()NAMED_UNIT(#{base}));\n"
    )
    data, n = re.subn(r"(?i)\bDATA\s*;", "DATA;\n" + declarations, data, count=1)
    if n != 1:
        raise ValueError("STEP DATA section not found")
    context_pattern = re.compile(
        r"(GLOBAL_UNIT_ASSIGNED_CONTEXT\s*\(\s*\(\s*)#" + re.escape(mm_id) + r"(?=\s*,)",
        re.I,
    )
    data, n = context_pattern.subn(lambda match: match.group(1) + f"#{base+2}", data)
    if n != 1:
        raise ValueError("STEP unit context conversion did not match once")
    file.write_text(data, encoding="utf-8")
    return {"source_unit": "INCH", "scale_to_mm": _INCH_MM, "unit_entity": base + 2}


def _make_step(path, *, unit):
    import gmsh
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("unit_equivalence_" + unit)
        s = 1.0 if unit == "mm" else 1.0 / _INCH_MM
        gmsh.model.occ.addBox(0, 0, 0, 100*s, 10*s, 10*s)
        gmsh.model.occ.synchronize()
        gmsh.write(str(dest))
    finally:
        gmsh.finalize()
    if unit == "inch":
        encode_step_in_inches(dest)
    return dest


def _faces_and_extents(path):
    faces = inspect_step(str(path))
    if len(faces) < 6:
        raise ValueError("Unexpected imported STEP face count")
    extrema = [
        (min(f.bbox_mm[i] for f in faces), max(f.bbox_mm[i+3] for f in faces))
        for i in range(3)
    ]
    dimensions = [upper - lower for lower, upper in extrema]
    if any(abs(got - expected) > 1e-3 for got, expected in zip(dimensions, (100.,10.,10.))):
        raise ValueError(f"CAD source length/unit mismatch: imported mm extents {dimensions}")
    fixed = min(faces, key=lambda f: abs(f.center_mm[0]))
    loaded = min(faces, key=lambda f: abs(f.center_mm[0]-100.))
    if abs(fixed.center_mm[0]) > 1e-4 or abs(loaded.center_mm[0]-100.) > 1e-4:
        raise ValueError("Imported STEP end faces could not be identified geometrically")
    return fixed.tag, loaded.tag, dimensions


def _relative(a, b):
    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError("Nonfinite unit-equivalence measurement")
    return abs(a-b) / max(abs(a), abs(b), 1e-15)


def verify_step_units(output_root="runs/step_unit_equivalence", *, solve=True):
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    probe = {"core_midspan": (50.13, 4.31, 5.82)}
    records = []
    for unit in ("mm", "inch"):
        step = _make_step(root/f"bar_{unit}.step", unit=unit)
        fixed, loaded, extents = _faces_and_extents(step)
        record = {
            "source_unit": unit, "step_sha256": hashlib.sha256(step.read_bytes()).hexdigest(),
            "imported_extents_mm": extents, "fixture_face": fixed, "loaded_face": loaded
        }
        if solve:
            model = Analysis(str(step), fixed, loaded, (100., 0., 0.), 7.,
                             element_type="C3D10")
            output = run_case(model, root/f"run_{unit}", fixed_stress_probes=probe)
            raw = json.loads((output/"case.json").read_text())
            if raw["status"] != "completed":
                raise ValueError(f"{unit}: native solve failed required equilibrium checks")
            metrics = raw["results"]
            stress = metrics["fixed_coordinate_stress_affine"]["probes"]["core_midspan"]["von_mises_mpa"]
            record.update({
                "max_displacement_mm": metrics["max_displacement_mm"],
                "fixed_core_stress_mpa": stress,
                "force_balance_error": metrics["force_balance_relative_error"],
                "moment_balance_error": metrics["moment_balance_relative_error"],
                "run_directory": str(output.relative_to(root)),
            })
        records.append(record)
    diffs = {}
    if solve:
        a, b = records
        diffs = {
            "max_displacement_relative_difference": _relative(
                a["max_displacement_mm"], b["max_displacement_mm"]),
            "fixed_core_stress_relative_difference": _relative(
                a["fixed_core_stress_mpa"], b["fixed_core_stress_mpa"]),
        }
    status = (
        "pass" if (not solve or
                   diffs["max_displacement_relative_difference"] <= 0.05 and
                   diffs["fixed_core_stress_relative_difference"] <= 0.10)
        else "review"
    )
    evidence = {
        "schema": "ezfea.native_step_units.v1",
        "status": status,
        "model": "100 x 10 x 10 mm physical axial bar, 100 N X force, C3D10, 7 mm",
        "reference": "Two syntactically different STEP source units, one physical geometry",
        "comparison": diffs, "runs": records,
        "engineering_validation": "not_established",
    }
    (root/"step_unit_equivalence.json").write_text(json.dumps(evidence, indent=2)+"\n")
    if status != "pass":
        raise ValueError("Independent STEP unit equivalence tolerance exceeded")
    return evidence


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out", default="runs/step_unit_equivalence")
    parser.add_argument("--geometry-only", action="store_true")
    args=parser.parse_args()
    report=verify_step_units(args.out, solve=not args.geometry_only)
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
