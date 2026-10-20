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
            with patch("ezfea.workflow.build_mesh",return_value=mesh), patch(
                "ezfea.workflow.run_calculix",return_value={"solver":"ccx"}):
                folder=run_case(case,root/"runs")
            meta=json.loads((folder/"case.json").read_text())
            bean=json.loads((folder/"bean_handoff.json").read_text())
            self.assertEqual(meta["status"],"completed")
            self.assertEqual(bean["bean_review_status"],"not_requested")
            self.assertTrue((folder/"analysis.inp").exists())

if __name__=="__main__":unittest.main()
