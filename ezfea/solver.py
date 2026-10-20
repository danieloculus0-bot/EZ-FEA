"""Create a CalculiX deck and run the actual ccx solver, never fake results."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess

def _rows(numbers, count=12):
    for i in range(0, len(numbers), count):
        yield ", ".join(str(n) for n in numbers[i:i+count])

def write_input(case, mesh, target):
    case.material.validate()
    if not mesh.nodes or not mesh.elements or not mesh.fixed_nodes or not mesh.force_weights:
        raise ValueError("Mesh incomplete.")
    if not set(mesh.fixed_nodes).issubset(mesh.nodes) or not set(mesh.force_weights).issubset(mesh.nodes):
        raise ValueError("Selections reference nodes not in mesh.")
    if abs(sum(mesh.force_weights.values()) - 1) > 1e-8:
        raise ValueError("Force weights must sum to one.")
    lines = ["*HEADING", "EZ-FEA experimental linear static analysis N mm MPa", "*NODE"]
    lines.extend(f"{n}, {v[0]:.10g}, {v[1]:.10g}, {v[2]:.10g}" for n,v in sorted(mesh.nodes.items()))
    lines.append("*ELEMENT, TYPE=C3D4, ELSET=PART")
    lines.extend(f"{n}, {', '.join(map(str, v))}" for n,v in sorted(mesh.elements.items()))
    lines.append("*NSET, NSET=CONNECTION")
    lines.extend(_rows(mesh.fixed_nodes))
    lines.append("*NSET, NSET=ALL_NODES")
    lines.extend(_rows(sorted(mesh.nodes)))
    lines.extend(["*MATERIAL, NAME=MAT", "*ELASTIC",
                  f"{case.material.elastic_modulus_mpa:.10g}, {case.material.poisson_ratio:.10g}",
                  "*SOLID SECTION, ELSET=PART, MATERIAL=MAT", "*STEP", "*STATIC",
                  "*BOUNDARY", "CONNECTION, 1, 3, 0", "*CLOAD"])
    for node, share in sorted(mesh.force_weights.items()):
        for axis, f in enumerate(case.force_n, 1):
            if f:
                lines.append(f"{node}, {axis}, {f*share:.12g}")
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
