"""JSON command-line interface for the rigid in-plane bolt-group model.

Usage: python -m ezfea.bolt_group_cli input.json
       python -m ezfea.bolt_group_cli - < input.json

Input: {"positions":[[0,0],[100,0]],"force_x":0,"force_y":1000,"moment_z":0}
All units must be consistent. This is an elastic screening model, not a
connection-capacity or failure calculation.
"""
import argparse
import json
import math
import sys

from .bolt_group import distribute_in_plane_load


def calculate(payload):
    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object")
    expected = {"positions", "force_x", "force_y", "moment_z"}
    unknown = set(payload) - expected
    if unknown:
        raise ValueError("Unknown input keys: " + ", ".join(sorted(unknown)))
    if not {"positions", "force_x", "force_y"} <= set(payload):
        raise ValueError("positions, force_x and force_y are required")
    positions = payload["positions"]
    if not isinstance(positions, list) or not positions:
        raise ValueError("positions must be a nonempty array")
    if any(not isinstance(p, list) or len(p) != 2 for p in positions):
        raise ValueError("Each position must contain two numbers")
    scalars = [*sum(positions, []), payload["force_x"], payload["force_y"], payload.get("moment_z", 0)]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in scalars):
        raise ValueError("Coordinates and loads must be finite numbers")
    centroid, polar_sum, loads = distribute_in_plane_load(
        positions, payload["force_x"], payload["force_y"], payload.get("moment_z", 0)
    )
    return {
        "model": "identical-fastener rigid-plate elastic in-plane shear",
        "centroid": list(centroid),
        "polar_sum": polar_sum,
        "bolts": [
            {"x": p.x, "y": p.y, "force_x": p.fx, "force_y": p.fy, "resultant": p.resultant}
            for p in loads
        ],
        "max_resultant": max(p.resultant for p in loads),
        "limits": "Excludes preload, prying, slip, bolt capacity and joint failure.",
    }


def calculate_cases(payload):
    """Evaluate multiple independent load cases on one unchanged bolt pattern.

    All cases are validated before results are emitted; an invalid case cannot
    leave behind a misleading partial envelope.
    """
    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object")
    if set(payload) != {"positions", "cases"}:
        raise ValueError("Batch input requires exactly positions and cases")
    cases = payload["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a nonempty array")
    if len(cases) > 10000:
        raise ValueError("Too many load cases")
    seen = set()
    results = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) - {"name", "force_x", "force_y", "moment_z"}:
            raise ValueError(f"Invalid load case at index {index}")
        name = case.get("name")
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise ValueError(f"Load case at index {index} needs a unique nonempty name")
        seen.add(name)
        try:
            result = calculate({"positions": payload["positions"],
                                "force_x": case["force_x"], "force_y": case["force_y"],
                                "moment_z": case.get("moment_z", 0)})
        except KeyError as exc:
            raise ValueError(f"Missing load component in case {name}") from exc
        except ValueError as exc:
            raise ValueError(f"Invalid case {name}: {exc}") from exc
        results.append({"name": name, **result})
    per_bolt = [
        {"index": i, "max_resultant": max(r["bolts"][i]["resultant"] for r in results),
         "governing_case": max(results, key=lambda r: r["bolts"][i]["resultant"])["name"]}
        for i in range(len(results[0]["bolts"]))
    ]
    governing = max(results, key=lambda r: r["max_resultant"])
    return {"model": "independent in-plane elastic bolt-group load cases",
            "cases": results, "envelope": {"bolts": per_bolt,
            "max_resultant": governing["max_resultant"], "governing_case": governing["name"]},
            "limits": "Envelope is not a combined-load or fatigue calculation."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON input file or '-' for stdin")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            payload = json.load(sys.stdin)
        else:
            with open(args.input, encoding="utf-8") as handle:
                payload = json.load(handle)
        print(json.dumps(calculate_cases(payload) if isinstance(payload, dict) and "cases" in payload else calculate(payload), indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"bolt-group input error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
