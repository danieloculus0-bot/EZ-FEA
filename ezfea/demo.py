"""Create a simple cantilever example in millimeters using Gmsh."""
from pathlib import Path
from .mesh import _gmsh

def make_demo_step(destination="examples/demo_cantilever.step"):
    target=Path(destination)
    target.parent.mkdir(parents=True,exist_ok=True)
    gmsh=_gmsh()
    gmsh.initialize()
    try:
        gmsh.model.add("EZ-FEA Demo Cantilever")
        gmsh.model.occ.addBox(0,0,0,100,10,10)
        gmsh.model.occ.synchronize()
        gmsh.write(str(target))
    finally:
        gmsh.finalize()
    return target
