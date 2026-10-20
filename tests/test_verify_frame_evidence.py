"""Exercise the solver-to-Pages publication gate without running CalculiX."""
import json
from pathlib import Path
import tempfile
import unittest

from ezfea.frame_benchmarks import STUDIES, geometry_definition_sha256
from scripts.verify_frame_evidence import verify_frame_evidence


class PublishEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"physics.json"
        self.data={
            "schema":"ezfea.frame_evidence.v1",
            "source_run":"https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/12345",
            "source_commit":"a"*40,
            "studies":[
                {"key":spec.key,"construction":spec.construction,
                 "force_n":list(spec.load_n),
                 "model_definition_sha256":geometry_definition_sha256(spec),
                 "force_balance_check":"pass",
                 "force_balance_relative_error":1e-6,
                 "max_displacement_mm":0.002 if spec.key=="03_braced_racking" else 0.013,
                 "max_von_mises_mpa":3.2,
                 "mesh_nodes":100,"mesh_elements":450,"mesh_size_mm":14}
                for spec in STUDIES
            ]
        }
    def tearDown(self):
        self.temp.cleanup()
    def verify(self):
        self.path.write_text(json.dumps(self.data),encoding="utf-8")
        return verify_frame_evidence(self.path,run_id="12345")
    def test_accepts_complete_actual_record_structure(self):
        self.assertEqual(len(self.verify()["studies"]),len(STUDIES))
    def test_rejects_wrong_run(self):
        self.data["source_run"]="https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/12346"
        with self.assertRaisesRegex(ValueError,"source run"):self.verify()
    def test_rejects_modified_load(self):
        self.data["studies"][1]["force_n"]=[-250,0,0]
        with self.assertRaisesRegex(ValueError,"model identity"):self.verify()
    def test_rejects_missing_case(self):
        self.data["studies"].pop()
        with self.assertRaisesRegex(ValueError,"case identities"):self.verify()
    def test_rejects_nonfinite_solver_output(self):
        self.data["studies"][0]["max_von_mises_mpa"]=float("inf")
        with self.assertRaisesRegex(ValueError,"nonfinite"):self.verify()
    def test_rejects_failed_equilibrium(self):
        self.data["studies"][1]["force_balance_relative_error"]=.2
        with self.assertRaisesRegex(ValueError,"invalid physical"):self.verify()
    def test_rejects_brace_stiffness_regression(self):
        self.data["studies"][2]["max_displacement_mm"]=.09
        with self.assertRaisesRegex(ValueError,"stiffness regression"):self.verify()


if __name__=="__main__":
    unittest.main()
