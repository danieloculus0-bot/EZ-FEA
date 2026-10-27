"""Tiny true STEP part for testing common mounting-hole recognition.

A flat steel plate with two drilled through-holes, not an assembly and not
an assertion that holes are actually bolted in service.
"""
from pathlib import Path


def drilled_plate_step(filename):
    import gmsh
    path=Path(filename)
    path.parent.mkdir(parents=True,exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal",0)
        gmsh.model.add("mounting_plate_with_two_round_through_holes")
        occ=gmsh.model.occ
        plate=occ.addBox(0,0,0,120,65,10)
        holes=[
            occ.addCylinder(25,24,-2,0,0,14,5),
            occ.addCylinder(95,24,-2,0,0,14,5),
        ]
        parts,_=occ.cut([(3,plate)],[(3,tag) for tag in holes],
                        removeObject=True,removeTool=True)
        occ.synchronize()
        if len(parts)!=1 or len(gmsh.model.getEntities(3))!=1:
            raise ValueError("Drilled plate must remain a single closed STEP solid")
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    return path
