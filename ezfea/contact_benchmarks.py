"""Two *separate* elastic solids with genuine separable CalculiX contact.

A tiny controlled verification specimen uses two independent C3D8 bricks:
- base and upper pad DO NOT share any node
- a real CONTACT PAIR transfers load only under compressive engagement
- separation must release normal reaction
- no-contact control MUST not transfer any normal load.

This is a narrowly scoped verified experimental contact solver, not yet a
general arbitrary STEP assembly or accurate contact pressure field.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .solver import run_calculix
from .results import read_dat


def brick_nodes():
    def brick(start,z0,z1):
        points=((0,0,z0),(10,0,z0),(10,10,z0),(0,10,z0),
                (0,0,z1),(10,0,z1),(10,10,z1),(0,10,z1))
        return {start+i:tuple(float(x) for x in p) for i,p in enumerate(points)}
    return {**brick(1,0,10),**brick(9,10,20)}


def contact_deck(*,mode="compression",enabled_contact=True,penalty_mpa_per_mm=100000.):
    """Controlled displacement test of compressive-only normal transfer."""
    if mode not in ("compression","separation"):
        raise ValueError("Unsupported contact test direction")
    if not math.isfinite(penalty_mpa_per_mm) or penalty_mpa_per_mm<=0:
        raise ValueError("Penalty stiffness must be finite and positive")
    nodes=brick_nodes()
    lines=["*HEADING","EZ-FEA controlled two-body, frictionless contact specimen",
           "*NODE"]
    lines.extend(f"{n}, {x}, {y}, {z}" for n,(x,y,z) in sorted(nodes.items()))
    lines.extend([
        "*ELEMENT, TYPE=C3D8, ELSET=BASE",
        "1, 1, 2, 3, 4, 5, 6, 7, 8",
        "*ELEMENT, TYPE=C3D8, ELSET=PAD",
        "2, 9, 10, 11, 12, 13, 14, 15, 16",
        "*ELSET, ELSET=ALL",
        "1, 2",
        "*NSET, NSET=BASE_BOTTOM",
        "1, 2, 3, 4",
        "*NSET, NSET=PAD_TOP",
        "13, 14, 15, 16",
        "*MATERIAL, NAME=STEEL",
        "*ELASTIC",
        "200000, 0.26",
        "*SOLID SECTION, ELSET=BASE, MATERIAL=STEEL",
        "*SOLID SECTION, ELSET=PAD, MATERIAL=STEEL",
    ])
    if enabled_contact:
        lines.extend([
            "*SURFACE, NAME=PAD_INTERFACE, TYPE=ELEMENT",
            "2, S1",
            "*SURFACE, NAME=BASE_INTERFACE, TYPE=ELEMENT",
            "1, S2",
            "*SURFACE INTERACTION, NAME=FRICTIONLESS_PAD",
            "*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR",
            f"{penalty_mpa_per_mm:.10g}",
            "*CONTACT PAIR, INTERACTION=FRICTIONLESS_PAD, TYPE=SURFACE TO SURFACE",
            "PAD_INTERFACE, BASE_INTERFACE",
        ])
    delta=-.001 if mode=="compression" else +.001
    lines.extend([
        "*STEP, NLGEOM=YES, INC=200",
        "*STATIC",
        "0.1, 1., 1.e-8, 0.1",
        "*BOUNDARY",
        "BASE_BOTTOM, 1, 3, 0",
        "PAD_TOP, 1, 2, 0",
        f"PAD_TOP, 3, 3, {delta:.8g}",
        "*NODE PRINT, NSET=BASE_BOTTOM",
        "RF",
        "*NODE PRINT, NSET=PAD_TOP",
        "U",
        "*EL PRINT, ELSET=ALL",
        "S",
        "*NODE FILE",
        "U",
        "*EL FILE",
        "S",
        "*END STEP",
    ])
    return "\n".join(lines)+"\n"


def _base_reaction_from_native_dat(dat_path):
    parsed=read_dat(dat_path)
    if parsed["reactions"] is None:
        raise ValueError("Missing actual bottom support reactions from contact solver")
    ids={int(row[0]) for row in parsed["reactions"]}
    if ids!={1,2,3,4}:
        raise ValueError(f"Actual base reaction node coverage invalid: {ids}")
    reaction=[sum(row[i] for row in parsed["reactions"]) for i in (1,2,3)]
    if any(not math.isfinite(x) for x in reaction):
        raise ValueError("Invalid native contact reaction")
    return reaction


def run_contact_benchmark(root="runs/native_contact"):
    """Run compression/contact, compression/no-contact, and opening/contact."""
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    scenarios=(("compression_contact","compression",True),
               ("compression_unconnected","compression",False),
               ("separation_contact","separation",True))
    outcomes=[]
    for name,mode,enabled in scenarios:
        out=root/name
        out.mkdir(parents=True,exist_ok=True)
        inp=out/"analysis.inp"
        inp.write_text(contact_deck(mode=mode,enabled_contact=enabled),
                       encoding="utf-8")
        details=run_calculix(inp,timeout_seconds=240)
        reaction=_base_reaction_from_native_dat(out/"analysis.dat")
        fz=abs(reaction[2])
        result={
            "scenario":name,"contact_enabled":enabled,
            "prescribed_top_displacement_mm":(-.001 if mode=="compression" else .001),
            "bottom_reaction_force_n":reaction,
            "bottom_normal_reaction_magnitude_n":fz,
            "solver":details["solver"],"native_files":str(out.relative_to(root)),
        }
        outcomes.append(result)
    byname={r["scenario"]:r for r in outcomes}
    compression=byname["compression_contact"]["bottom_normal_reaction_magnitude_n"]
    disconnected=byname["compression_unconnected"]["bottom_normal_reaction_magnitude_n"]
    separation=byname["separation_contact"]["bottom_normal_reaction_magnitude_n"]
    # Quantitative one-way load-transfer test with a no-interface reference;
    # a working contact interface MUST transmit compression, but NOT tension.
    if compression<1.:
        raise ValueError("Contact interface did not transmit a measurable compressive load")
    limit=max(0.05,0.01*compression)
    if disconnected>limit or separation>limit:
        raise ValueError("Frictionless contact carried load during separation/no-contact control")
    report={
        "schema":"ezfea.two_body_contact.v1",
        "model":"two geometrically touching 10x10x10 mm steel bricks, distinct node IDs, native C3D8",
        "contact_law":"CalculiX frictionless surface-to-surface LINEAR penalty, compressive-only",
        "penalty_stiffness_mpa_per_mm":100000.,
        "scenarios":outcomes,
        "compression_reference_load_n":compression,
        "unloaded_reaction_tolerance_n":limit,
        "contact_transfers_compression_only":True,
        "engineering_validation":"not_established",
        "limitations":"single flat interface C3D8 controlled displacement; not generic two-solid STEP, bolts, friction or qualified contact stress",
    }
    (root/"contact_evidence.json").write_text(json.dumps(report,indent=2)+"\n")
    lines=["# True two-body CalculiX contact transfer benchmark","",
           "Two independent elastic 10x10x10 mm solids share NO node IDs;",
           "only the native surface-to-surface contact pair can transmit normal compression.",
           "",
           "| Scenario | Top displacement (mm) | Contact pair? | Base normal reaction (N) |",
           "|---|---:|---|---:|"]
    for item in outcomes:
        lines.append(f"| {item['scenario']} | {item['prescribed_top_displacement_mm']:.6g} | "
                     f"{'yes' if item['contact_enabled'] else 'no'} | "
                     f"{item['bottom_normal_reaction_magnitude_n']:.6g} |")
    lines.extend(["",
                  "Contact must transfer compression, release during opening, and transfer",
                  "nothing with the contact pair disabled. These are genuine native RF results.",
                  "This isolated proof does not establish generic assembly contact, pressure",
                  "convergence, friction, bolt clamp physics or design-qualified behavior."])
    (root/"CONTACT_REPORT.md").write_text("\n".join(lines)+"\n")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="runs/native_contact")
    args=parser.parse_args()
    run_contact_benchmark(args.out)
    print((Path(args.out)/"CONTACT_REPORT.md").read_text())


if __name__=="__main__":
    main()
