"""Conservative CalculiX .dat displacement summary. Missing is never estimated."""
import math
import re
from pathlib import Path
_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][-+]?\d+)?"
_ROW = re.compile(rf"^\s*(\d+)\s+({_NUM})\s+({_NUM})\s+({_NUM})\s*$")

def max_displacement_mm(dat_file: Path):
    if not dat_file.exists():
        return None
    table, maximum = False, None
    for line in dat_file.read_text(errors="replace").splitlines():
        if "displacements" in line.lower() and "vx" in line.lower():
            table = True
            continue
        if not table:
            continue
        match = _ROW.fullmatch(line)
        if match:
            xyz = [float(n.replace("D","E").replace("d","e")) for n in match.groups()[1:]]
            magnitude = math.sqrt(sum(x*x for x in xyz))
            maximum = max(maximum or 0, magnitude)
        elif line.strip() and maximum is not None:
            table = False
    return maximum
