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
        print(json.dumps(calculate(payload), indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"bolt-group input error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
