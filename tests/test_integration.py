"""Optional real Gmsh+CalculiX cantilever smoke test."""
import json
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
            record=json.loads((output/"case.json").read_text())
            metrics=record["results"]
            self.assertEqual(record["status"],"completed",record)
            self.assertEqual(metrics["force_balance_check"],"pass")
            self.assertGreater(metrics["max_von_mises_mpa"],0)
            self.assertGreater(metrics["max_displacement_mm"],0)
            self.assertLess(metrics["force_balance_relative_error"],.01)


    def test_multi_region_actual_calculix_solve(self):
        """Real native solve with two support regions and two non-collinear force loads."""
        from ezfea.core import FaceConstraint, FaceLoad
        import gmsh
        if not (os.environ.get("EZFEA_CCX") or shutil.which("ccx")):
            self.skipTest("ccx missing")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            step = root / "multi.step"
            gmsh.initialize()
            try:
                gmsh.model.add("multi-region-beam")
                gmsh.model.occ.addBox(0, 0, 0, 100, 10, 10)
                gmsh.model.occ.synchronize()
                gmsh.write(str(step))
            finally:
                gmsh.finalize()
            faces = inspect_step(str(step))
            fixed = min(faces, key=lambda f: abs(f.center_mm[0]))
            end = min(faces, key=lambda f: abs(f.center_mm[0] - 100))
            bottom = min(faces, key=lambda f: abs(f.center_mm[2]))
            top = min(faces, key=lambda f: abs(f.center_mm[2] - 10))
            case = Analysis(
                str(step), 0, 0, (0, 0, 0), 7,
                connections=(FaceConstraint(fixed.tag), FaceConstraint(bottom.tag, (3,))),
                loads=(FaceLoad(end.tag, (0, -80, 0)), FaceLoad(top.tag, (0, 0, -20))),
            )
            folder_out = run_case(case, root / "runs")
            record = json.loads((folder_out / "case.json").read_text())
            self.assertEqual(record["status"], "completed", record)
            self.assertEqual(record["mesh"]["connections"], 2)
            self.assertEqual(record["mesh"]["load_regions"], 2)
            self.assertEqual(record["results"]["force_balance_check"], "pass")
            self.assertEqual(record["results"]["applied_force_n"], [0, -80, -20])
            self.assertLess(record["results"]["force_balance_relative_error"], .01)
            self.assertTrue((folder_out / "analysis.frd").exists())

if __name__=="__main__":unittest.main()
