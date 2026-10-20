"""Optional real Gmsh+CalculiX cantilever smoke test."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from ezfea.core import Analysis
from ezfea.mesh import inspect_step
from ezfea.workflow import run_case

@unittest.skipUnless(os.environ.get("EZFEA_RUN_INTEGRATION")=="1","Needs real Gmsh and ccx")
class SolverSmokeTest(unittest.TestCase):
    def test_beam(self):
        import gmsh
        if not (os.environ.get("EZFEA_CCX") or shutil.which("ccx")):
            self.skipTest("ccx missing")
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            step=root/"beam.step"
            gmsh.initialize()
            try:
                gmsh.model.add("beam")
                gmsh.model.occ.addBox(0,0,0,100,10,10)
                gmsh.model.occ.synchronize()
                gmsh.write(str(step))
            finally:
                gmsh.finalize()
            faces=inspect_step(str(step))
            fixed=min(faces,key=lambda f:abs(f.center_mm[0]))
            loaded=min(faces,key=lambda f:abs(f.center_mm[0]-100))
            output=run_case(Analysis(str(step),fixed.tag,loaded.tag,(0,-100,0),7),root/"runs")
            self.assertTrue((output/"analysis.frd").exists())

if __name__=="__main__":unittest.main()
