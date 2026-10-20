"""Create a CalculiX deck and run the actual ccx solver, never fake results."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess

def _rows(numbers, count=12):
    for i in range(0, len(numbers), count):
        yield ", ".join(str(n) for n in numbers[i:i+count])

def _rigid_body_rank(nodes, supports):
    """Rank of six infinitesimal rigid-body modes restrained by face DOFs.

    This is a necessary stability test, not proof of correct fixture physics,
    local mesh connectivity, or physical joint fidelity.
    """
    used = [nodes[n] for ids, _ in supports for n in ids]
    if not used:
        return 0
    center = tuple(sum(p[i] for p in used) / len(used) for i in range(3))
    scale = max(max(p[i] for p in used) - min(p[i] for p in used)
                for i in range(3))
    scale = max(scale, 1e-12)
    basis = []
    for ids, axes in supports:
        for n in ids:
            x, y, z = ((nodes[n][i]-center[i])/scale for i in range(3))
            choices = {
                1: (1, 0, 0, 0, z, -y),
                2: (0, 1, 0, -z, 0, x),
                3: (0, 0, 1, y, -x, 0),
            }
            for axis in axes:
                row = [float(v) for v in choices[axis]]
                for vector in basis:
                    dot = sum(a*b for a, b in zip(row, vector))
                    row = [a-dot*b for a, b in zip(row, vector)]
                length = sum(v*v for v in row)**0.5
                if length > 1e-9:
                    basis.append([v/length for v in row])
                    if len(basis) == 6:
                        return 6
    return len(basis)


def write_input(case, mesh, target):
    case.validate()
    if not mesh.nodes or not mesh.elements or not mesh.fixed_nodes or not mesh.force_weights:
        raise ValueError("Mesh incomplete.")
    if not set(mesh.fixed_nodes).issubset(mesh.nodes):
        raise ValueError("Connection nodes not present in mesh.")
    extended = bool(case.connections)
    lines = ["*HEADING", "EZ-FEA experimental linear static analysis N mm MPa", "*NODE"]
    lines.extend(f"{n}, {v[0]:.10g}, {v[1]:.10g}, {v[2]:.10g}"
                 for n, v in sorted(mesh.nodes.items()))
    lines.append("*ELEMENT, TYPE=C3D4, ELSET=PART")
    lines.extend(f"{n}, {', '.join(map(str, v))}" for n, v in sorted(mesh.elements.items()))
    lines.append("*NSET, NSET=CONNECTION")
    lines.extend(_rows(mesh.fixed_nodes))
    if extended:
        supports = []
        for i, c in enumerate(case.connections, 1):
            ids = mesh.constraint_nodes.get(c.face)
            if not ids or not set(ids).issubset(mesh.nodes):
                raise ValueError(f"Connection face {c.face} has no valid mesh nodes.")
            supports.append((ids, c.axes))
            lines.append(f"*NSET, NSET=FIX_{i}")
            lines.extend(_rows(ids))
        rank = _rigid_body_rank(mesh.nodes, supports)
        if rank != 6:
            raise ValueError(f"Underconstrained setup: only {rank}/6 rigid-body modes restrained. "
                             "Add physically justified connections; do not invent clamps.")
    lines.append("*NSET, NSET=ALL_NODES")
    lines.extend(_rows(sorted(mesh.nodes)))
    lines.extend(["*MATERIAL, NAME=MAT", "*ELASTIC",
                  f"{case.material.elastic_modulus_mpa:.10g}, {case.material.poisson_ratio:.10g}",
                  "*SOLID SECTION, ELSET=PART, MATERIAL=MAT",
                  "*STEP", "*STATIC", "*BOUNDARY"])
    if extended:
        for i, c in enumerate(case.connections, 1):
            for axis in c.axes:
                lines.append(f"FIX_{i}, {axis}, {axis}, 0")
    else:
        lines.append("CONNECTION, 1, 3, 0")
    lines.append("*CLOAD")
    combined = {}
    if extended:
        for load in case.loads:
            weights = mesh.load_weights_by_face.get(load.face)
            if not weights or not set(weights).issubset(mesh.nodes):
                raise ValueError(f"Load face {load.face} has no valid surface mesh.")
            if abs(sum(weights.values()) - 1) > 1e-8:
                raise ValueError(f"Load face {load.face} weights must sum to one.")
            for node, share in weights.items():
                for axis, component in enumerate(load.force_n, 1):
                    combined[node, axis] = combined.get((node, axis), 0.) + component*share
    else:
        if not set(mesh.force_weights).issubset(mesh.nodes):
            raise ValueError("Load selection references nodes not in mesh.")
        if abs(sum(mesh.force_weights.values()) - 1) > 1e-8:
            raise ValueError("Force weights must sum to one.")
        for node, share in mesh.force_weights.items():
            for axis, component in enumerate(case.force_n, 1):
                combined[node, axis] = component*share
    for (node, axis), force in sorted(combined.items()):
        if force:
            lines.append(f"{node}, {axis}, {force:.12g}")
    lines.extend([
        "*NODE PRINT, NSET=ALL_NODES", "U",
        "*NODE PRINT, NSET=CONNECTION", "RF",
        "*EL PRINT, ELSET=PART", "S",
        "*NODE FILE", "U", "*EL FILE", "S", "*END STEP"
    ])
    target.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return target


def run_calculix(inp: Path, timeout_seconds=300):
    executable = os.environ.get("EZFEA_CCX") or shutil.which("ccx") or shutil.which("ccx.exe")
    if not executable:
        raise RuntimeError("CalculiX ccx not found. Add ccx to PATH or set EZFEA_CCX.")
    result = subprocess.run([executable, "-i", inp.stem], cwd=inp.parent,
                            capture_output=True, text=True, timeout=timeout_seconds)
    (inp.parent/"solver.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    sta, frd = inp.with_suffix(".sta"), inp.with_suffix(".frd")
    if result.returncode != 0 or not frd.is_file():
        raise RuntimeError(f"ccx failed (exit {result.returncode}); see solver.log. {result.stderr[-900:]}")
    # CalculiX completion is reported in stdout as "Job finished".
    # Do not apply an Abaqus-style completion-message check to the .sta file.
    if "job finished" not in result.stdout.lower():
        raise RuntimeError("CalculiX did not confirm Job finished; review solver.log, .sta and .dat.")
    return {"solver":Path(executable).name, "result_frd":frd.name, "solver_log":"solver.log"}
