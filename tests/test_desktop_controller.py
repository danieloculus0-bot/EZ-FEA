"""Desktop controllers are headless, deterministic and never invent FEA data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ezfea.core import Face
from ezfea.desktop_controller import (
    build_analysis,preflight,result_summary,save_readable_report,run_desktop_case,
)


def inputs():
    return {"fx":"0","fy":"-100","fz":"0","mesh":"7",
            "e":"200000","nu":"0.26","yield_mpa":"250",
            "element_type":"C3D10"}


def actual_record(status="completed"):
    return {
        "status":status,"source_file":"source.step",
        "input_sha256":"a"*64,"units":"N/mm/MPa",
        "model":{"fixed_face":4,"loaded_face":7,"force_n":[0,-100,0],
                 "mesh_size_mm":7,"material":{"name":"steel"}},
        "mesh":{"elements":421,"element_type":"C3D10"},
        "results":{
            "max_displacement_mm":.015,
            "max_von_mises_mpa":41.,
            "nominal_yield_to_von_mises_ratio":250/41,
            "force_balance_check":"pass","moment_balance_check":"pass",
            "force_balance_relative_error":.000001,
            "moment_balance_relative_error":.00003,
        }
    }


class DesktopControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.step=Path(self.tmp.name)/"beam.step"
        self.step.write_text("test fixture")
        self.faces=[
            Face(4,(0.,5.,5.),(0.,0.,0.,0.,10.,10.)),
            Face(7,(100.,5.,5.),(100.,0.,0.,100.,10.,10.))
        ]

    def test_real_face_ids_and_quadratic_default(self):
        case=build_analysis(self.step,self.faces,0,1,inputs())
        self.assertEqual(case.fixed_face,4)
        self.assertEqual(case.loaded_face,7)
        self.assertEqual(case.element_type,"C3D10")
        self.assertEqual(case.force_n,(0.,-100.,0.))

    def test_wrong_face_and_zero_load_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"different"):
            build_analysis(self.step,self.faces,0,0,inputs())
        with self.assertRaisesRegex(ValueError,"Select"):
            build_analysis(self.step,self.faces,-1,1,inputs())
        data=inputs()
        data["fy"]="0"
        with self.assertRaisesRegex(ValueError,"nonzero"):
            build_analysis(self.step,self.faces,0,1,data)

    def test_reject_nonfinite_and_unsupported_settings(self):
        for key,value in (
            ("mesh","0"),("mesh","NaN"),("fy","inf"),
            ("e","-1"),("nu","0.5"),("yield_mpa","0"),
            ("element_type","C3D8")
        ):
            with self.subTest(key=key,value=value):
                data=inputs()
                data[key]=value
                with self.assertRaises(ValueError):
                    build_analysis(self.step,self.faces,0,1,data)

    def test_result_report_from_solver_values(self):
        result=result_summary(actual_record())
        self.assertEqual(result["status"],"completed")
        self.assertIn("41",result["max_stress"])
        self.assertIn("PASS",result["moment_balance"])
        with tempfile.TemporaryDirectory() as tmp:
            report=save_readable_report(tmp,actual_record(),result)
            text=report.read_text()
            self.assertIn("Maximum von Mises integration-point stress: 41 MPa",text)
            self.assertIn("NOT VALIDATED",text)
            self.assertIn("source.step",text)

    def test_failed_balance_must_not_be_called_completed(self):
        record=actual_record("needs_review")
        record["results"]["moment_balance_check"]="review"
        result=result_summary(record)
        self.assertIn("NEEDS REVIEW",result["headline"])
        record["status"]="completed"
        with self.assertRaisesRegex(ValueError,"unchecked"):
            result_summary(record)

    def test_cannot_present_missing_real_solver_numbers(self):
        record=actual_record()
        del record["results"]["max_von_mises_mpa"]
        with self.assertRaisesRegex(ValueError,"lacks"):
            result_summary(record)
        record=actual_record()
        record["results"]["max_displacement_mm"]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid"):
            result_summary(record)
        record=actual_record()
        del record["mesh"]["elements"]
        with self.assertRaisesRegex(ValueError,"mesh evidence"):
            result_summary(record)

    def test_desktop_run_uses_real_workflow_contract(self):
        case=build_analysis(self.step,self.faces,0,1,inputs())
        folder=Path(self.tmp.name)/"native"
        folder.mkdir()
        (folder/"case.json").write_text(json.dumps(actual_record()))
        with patch("ezfea.desktop_controller.run_case",return_value=folder) as solver:
            value=run_desktop_case(case,Path(self.tmp.name)/"runs")
        self.assertEqual(value["summary"]["status"],"completed")
        self.assertTrue((folder/"RESULTS.txt").is_file())
        solver.assert_called_once()

    def test_missing_dependencies_are_communicated(self):
        with patch("ezfea.desktop_controller.importlib.util.find_spec",return_value=None),patch(
            "ezfea.desktop_controller.shutil.which",return_value=None):
            issues=preflight()
        self.assertEqual(len(issues),2)
        self.assertIn("Gmsh",issues[0])
        self.assertIn("CalculiX",issues[1])


if __name__=="__main__":
    unittest.main()
