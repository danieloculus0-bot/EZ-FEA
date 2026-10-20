import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ezfea.core import Analysis
from ezfea.mesh import Mesh
from ezfea.workflow import run_case

class WorkflowTests(unittest.TestCase):
    def test_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            step=root/"part.step"
            step.write_text("model")
            case=Analysis(str(step),1,2,(0,-1,0),1)
            mesh=Mesh({1:(0,0,0),2:(1,0,0),3:(0,1,0),4:(0,0,1),5:(1,1,1)},
                      {1:(1,2,3,4)},[1],{5:1},1)
            def mock_calculix(inp):
                inp.with_suffix(".dat").write_text(
                    "displacements (vx,vy,vz) for set ALL_NODES and time 1.0\n"
                    + "".join(f"{i} 0 0 0\\n" for i in range(1,6)).replace("\\n","\n")
                    + "\nforces (fx,fy,fz) for set CONNECTION and time 1.0\n"
                    + "1 0 1 0\n"
                    + "\nstresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set PART and time 1.0\n"
                    + "1 1 10 0 0 0 0 0\n"
                )
                return {"solver":"ccx"}
            with patch("ezfea.workflow.build_mesh",return_value=mesh), patch(
                "ezfea.workflow.run_calculix",side_effect=mock_calculix):
                folder=run_case(case,root/"runs")
            meta=json.loads((folder/"case.json").read_text())
            bean=json.loads((folder/"bean_handoff.json").read_text())
            # A single reaction at the origin cannot balance the eccentric
            # force's moment, even though resultant forces cancel.
            self.assertEqual(meta["status"],"needs_review")
            self.assertEqual(meta["results"]["moment_balance_check"],"review")
            self.assertEqual(bean["bean_review_status"],"not_requested")
            self.assertTrue((folder/"analysis.inp").exists())
            self.assertEqual(meta["results"]["force_balance_check"],"pass")
            self.assertAlmostEqual(meta["results"]["max_von_mises_mpa"],10)

if __name__=="__main__":unittest.main()
