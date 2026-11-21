"""Small-displacement 1D axial bar finite-element solver (SI units).

Linear elastic, two-node elements; nodal axial forces; prescribed nodal displacements.
No buckling, plasticity, bending, thermal strain, or geometric nonlinearity.
"""
import argparse
import json
import math
from pathlib import Path


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return float(value)


def solve(model):
    elements = model["elements"]
    if not isinstance(elements, list) or not elements:
        raise ValueError("elements must be a nonempty list")
    n = len(elements) + 1
    k = [[0.0] * n for _ in range(n)]
    lengths = []
    for i, element in enumerate(elements):
        length = _positive(element["length_m"], "length_m")
        area = _positive(element["area_m2"], "area_m2")
        modulus = _positive(element["youngs_modulus_pa"], "youngs_modulus_pa")
        stiffness = modulus * area / length
        if not math.isfinite(stiffness):
            raise ValueError("nonfinite element stiffness")
        lengths.append(length)
        k[i][i] += stiffness
        k[i][i + 1] -= stiffness
        k[i + 1][i] -= stiffness
        k[i + 1][i + 1] += stiffness
    loads = model.get("nodal_forces_n", [0.0] * n)
    if len(loads) != n or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in loads):
        raise ValueError("nodal_forces_n must contain one finite force per node")
    constraints = model.get("prescribed_displacements_m", {})
    if not isinstance(constraints, dict) or not constraints:
        raise ValueError("at least one displacement constraint is required")
    fixed = {}
    for key, value in constraints.items():
        idx = int(key)
        if str(idx) != str(key) or idx < 0 or idx >= n or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("invalid displacement constraint")
        fixed[idx] = float(value)
    free = [i for i in range(n) if i not in fixed]
    u = [fixed.get(i, 0.0) for i in range(n)]
    # Partial-pivot Gaussian elimination on reduced stiffness system.
    a = [[k[i][j] for j in free] for i in free]
    b = [float(loads[i]) - sum(k[i][j] * value for j, value in fixed.items()) for i in free]
    for p in range(len(free)):
        pivot = max(range(p, len(free)), key=lambda row: abs(a[row][p]))
        if abs(a[pivot][p]) <= 1e-14 * max(abs(v) for row in a for v in row):
            raise ValueError("singular stiffness matrix: insufficient constraints or ill-conditioned model")
        a[p], a[pivot] = a[pivot], a[p]
        b[p], b[pivot] = b[pivot], b[p]
        for row in range(p + 1, len(free)):
            ratio = a[row][p] / a[p][p]
            for col in range(p, len(free)):
                a[row][col] -= ratio * a[p][col]
            b[row] -= ratio * b[p]
    for p in range(len(free) - 1, -1, -1):
        u[free[p]] = (b[p] - sum(a[p][j] * u[free[j]] for j in range(p + 1, len(free)))) / a[p][p]
    reactions = [sum(k[i][j] * u[j] for j in range(n)) - loads[i] for i in range(n)]
    element_results = []
    for i, element in enumerate(elements):
        strain = (u[i + 1] - u[i]) / lengths[i]
        stress = strain * element["youngs_modulus_pa"]
        element_results.append({"strain": strain, "stress_pa": stress, "axial_force_n": stress * element["area_m2"]})
    return {"displacements_m": u, "reactions_n": {str(i): reactions[i] for i in fixed},
            "elements": element_results, "force_balance_residual_n": sum(reactions) + sum(loads)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path, help="JSON model path")
    parser.add_argument("--output", type=Path, help="optional output JSON path")
    args = parser.parse_args(argv)
    result = solve(json.loads(args.model.read_text(encoding="utf-8")))
    payload = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
