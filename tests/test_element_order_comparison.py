"""Element-order comparison checks never imply independent material validation."""
import copy
import tempfile
import unittest

from scripts.compare_element_orders import compare_element_studies
from ezfea.frame_benchmarks import STUDIES
from ezfea.frame_convergence import run_frame_convergence


def study_form(element_type):
    return {
        "schema":"ezfea.frame_convergence.v1",
        "element_type":element_type,
        "mesh_sizes_mm":[14.,10.,7.],
        "studies":[{
            "key":"02_rectangle_racking",
            "specimen_definition_sha256":"a"*64,
            "step_sha256":"b"*64,
            "mesh_sizes_mm":[14.,10.,7.],
            "elements":[100,200,500],
            "nodes":[50,100,250],
            "max_displacements_mm":[.02,.023,.024],
            "peak_von_mises_mpa":[4,5,6],
            "max_force_balance_relative_error":1e-6,
            "increasing_element_counts":True,
            "fine_displacement_delta_pct":4.,
            "fine_peak_stress_delta_pct":16.6,
            "displacement_observation":"stable_at_checked_mesh_sizes",
        }]
    }


class ElementOrderComparisonTests(unittest.TestCase):
    def test_identical_step_source_accepted(self):
        result=compare_element_studies(study_form("C3D4"),study_form("C3D10"))
        self.assertEqual(len(result["cases"]),1)
        self.assertEqual(result["engineering_validation"],"not_established")

    def test_mismatched_step_bytes_rejected(self):
        other=study_form("C3D10")
        other["studies"][0]["step_sha256"]="c"*64
        with self.assertRaisesRegex(ValueError,"geometry or source"):
            compare_element_studies(study_form("C3D4"),other)

    def test_mismatched_element_type_rejected(self):
        with self.assertRaisesRegex(ValueError,"First study"):
            compare_element_studies(study_form("C3D10"),study_form("C3D4"))

    def test_missing_byte_identical_reference_fails_before_meshing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                run_frame_convergence(d+"/study",specimens=STUDIES[:1],
                                      reuse_cad_from=d+"/missing",element_type="C3D10")


if __name__=="__main__":
    unittest.main()
