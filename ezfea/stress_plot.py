"""Plot actual CalculiX integration-point von Mises stress without interpolation.

Only points with matching stress and coordinate (element, integration point)
records are drawn. This is a 2D XY projection, not a surface contour or a
substitute for mesh-convergence checks.
"""
from __future__ import annotations

import argparse
import html
import math
from pathlib import Path

from .results import read_dat, von_mises_mpa


def stress_points(dat_file):
    raw = read_dat(Path(dat_file))
    if raw["stress"] is None or raw["coordinates"] is None:
        raise ValueError("Both stress and integration-point coordinate tables are required")
    coordinates = {}
    for row in raw["coordinates"]:
        key = (int(row[0]), int(row[1]))
        if key in coordinates:
            raise ValueError("Duplicate integration-point coordinate")
        coordinates[key] = tuple(row[2:])
    stresses = {}
    for row in raw["stress"]:
        key = (int(row[0]), int(row[1]))
        if key in stresses:
            raise ValueError("Duplicate integration-point stress")
        stresses[key] = von_mises_mpa(*row[2:])
    if not stresses or stresses.keys() != coordinates.keys():
        raise ValueError("Stress and coordinate integration-point IDs do not match")
    points = [(key, *coordinates[key], stresses[key]) for key in sorted(stresses)]
    if not all(math.isfinite(v) for _, x, y, z, s in points for v in (x, y, z, s)):
        raise ValueError("Nonfinite stress or coordinates")
    return points


def render_svg(points, width=900, height=600):
    if not points or width < 200 or height < 200:
        raise ValueError("Invalid plot dimensions or empty results")
    xs = [p[1] for p in points]
    ys = [p[2] for p in points]
    values = [p[4] for p in points]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    span = max(xmax - xmin, ymax - ymin, 1e-9)
    scale = min((width - 120) / span, (height - 130) / span)
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    peak = max(values)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#101827"/>',
        '<text x="30" y="35" fill="white" font-size="19">CalculiX integration-point stress, XY projection</text>',
        f'<text x="30" y="{height-20}" fill="#cbd5e1" font-size="14">von Mises MPa | min {min(values):.5g} | max {peak:.5g} | {len(points)} points | no interpolation</text>',
    ]
    for (element, ip), x, y, z, stress in points:
        fraction = stress / peak if peak else 0
        red = round(50 + 205 * fraction)
        blue = round(230 - 190 * fraction)
        px = width / 2 + (x - cx) * scale
        py = height / 2 - (y - cy) * scale
        label = html.escape(f"element {element}, integration point {ip}; z={z:.6g} mm; von Mises={stress:.6g} MPa")
        lines.append(f'<circle cx="{px:.4f}" cy="{py:.4f}" r="5" fill="#{red:02x}55{blue:02x}"><title>{label}</title></circle>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dat", type=Path)
    parser.add_argument("svg", type=Path)
    args = parser.parse_args(argv)
    points = stress_points(args.dat)
    args.svg.write_text(render_svg(points), encoding="utf-8")
    print(f"Rendered {len(points)} actual integration points to {args.svg}")


if __name__ == "__main__":
    main()
