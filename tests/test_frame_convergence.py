"""Unit tests for result interpretation; not replacements for the native solves."""
import copy
import math
import unittest

from ezfea.convergence import relative_change
from ezfea.frame_convergence import (
    DEFAULT_MESHES_MM, analyze_recorded_refinements, report_markdown,
)


def synthetic_case(*, disps=(1.0,1.03,1.04), stresses=(4.,4.8,5.8),
                   counts=(100,230,650)):
    records=[
        {"mesh_size_mm":size,"element_count":count,"node_count":count//3,
         "max_displacement_mm":u,"max_von_mises_mpa":s,
         "force_balance_relative_error":1e-8}
        for size,count,u,s in zip(DEFAULT_MESHES_MM,counts,disps,stresses)
    ]
    changes=[
        {"displacement_relative_change":relative_change(a["max_displacement_mm"],b["max_displacement_mm"]),
         "peak_stress_relative_change":relative_change(a["max_von_mises_mpa"],b["max_von_mises_mpa"])}
        for a,b in zip(records,records[1:])
    ]
    stable=all(d["displacement_relative_change"]<=.05 for d in changes[-2:]) and \
            all(a<b for a,b in zip(counts,counts[1:]))
    return {"key":"rectangle_racking","definition_sha256":"a"*64,
            "source_step":"rectangle_racking/cad/rectangle_racking.step",
            "raw_evidence_path":"rectangle_racking/refinement/refinement.json",
            "refinement":{
                "input_sha256":"b"*64,"records":records,
                "adjacent_mesh_changes":changes,
                "element_counts_strictly_increase":all(a<b for a,b in zip(counts,counts[1:])),
                "displacement_observation":"stable_at_checked_mesh_sizes" if stable else "refinement_not_yet_stable",
            }}


class FrameConvergenceTests(unittest.TestCase):
    def test_stable_movement_does_not_hide_sensitive_peak_stress(self):
        a=analyze_recorded_refinements([synthetic_case()])[0]
        self.assertEqual(a["displacement_observation"],"stable_at_checked_mesh_sizes")
        self.assertEqual(a["peak_stress_observation"],"mesh_sensitive_or_singularity_possible")
        self.assertGreater(a["fine_peak_stress_delta_pct"],10)
        self.assertAlmostEqual(a["fine_displacement_delta_pct"],
                               100*.01/1.04)

    def test_stable_both_observations_not_a_safety_approval(self):
        a=analyze_recorded_refinements([synthetic_case(stresses=(4.0,4.2,4.3))])[0]
        self.assertEqual(a["peak_stress_observation"],"limited_sensitivity_at_checked_mesh_sizes")
        sample={"studies":[a],"generated_utc":"2026-10-20",
                "overall_displacement_observation":a["displacement_observation"],
                "overall_peak_stress_observation":a["peak_stress_observation"],
                "displacement_threshold_pct":5.0,"peak_stress_screen_pct":10.0}
        report=report_markdown(sample)
        self.assertIn("NOT solver validation",report)
        self.assertIn("Not for engineering sign-off",report)

    def test_identical_xyz_stress_probes_across_meshes(self):
        from ezfea.stress_probes import RECOVERY
        case=synthetic_case()
        for i,record in enumerate(case["refinement"]["records"]):
            record["fixed_coordinate_stress"]={
                "schema":"ezfea.fixed_stress_probes.v1",
                "probes":{"joint":{
                    "coordinate_mm":[14.3,9.2,166.7],
                    "von_mises_mpa":[4.0,4.3,4.35][i],
                    "host_element_id":[15,30,51][i],
                    "inside_corner_tetra_margin":.12,
                    "location_quality":"inside_element",
                    "recovery":RECOVERY,
                }},
            }
        observed=analyze_recorded_refinements([case])[0]
        probe=observed["fixed_coordinate_stress_trends"][0]
        self.assertEqual(probe["coordinate_mm"],[14.3,9.2,166.7])
        self.assertEqual(probe["observation"],"limited_sensitivity_at_checked_mesh_sizes")
        self.assertEqual(probe["host_element_ids"],[15,30,51])
        self.assertIn("4.35",str(probe["von_mises_mpa"]))
        sample={"studies":[observed],"generated_utc":"2026-10-20",
                "overall_displacement_observation":"stable_at_checked_mesh_sizes",
                "overall_peak_stress_observation":"mesh_sensitive",
                "displacement_threshold_pct":5.,"peak_stress_screen_pct":10.}
        self.assertIn("Fixed XYZ stress probes",report_markdown(sample))
        broken=copy.deepcopy(case)
        broken["refinement"]["records"][2]["fixed_coordinate_stress"]["probes"]["joint"]["coordinate_mm"][0]+=1
        with self.assertRaisesRegex(ValueError,"moved"):
            analyze_recorded_refinements([broken])
        poor=copy.deepcopy(case)
        poor["refinement"]["records"][0]["fixed_coordinate_stress"]["probes"]["joint"]["location_quality"]="near_element_boundary"
        flagged=analyze_recorded_refinements([poor])[0]["fixed_coordinate_stress_trends"][0]
        self.assertEqual(flagged["observation"],"near_element_boundary_check_probe")

    def test_refinement_flag_not_exaggerated(self):
        case=synthetic_case(disps=(1,1.18,1.30))
        actual=analyze_recorded_refinements([case])[0]
        self.assertEqual(actual["displacement_observation"],"refinement_not_yet_stable")

    def test_rejects_bad_source_metrics_and_fake_deltas(self):
        case=synthetic_case()
        for name,change in [
            ("nonfinite",lambda c:c["refinement"]["records"][2].update(
                max_von_mises_mpa=float("nan"))),
            ("force_balance",lambda c:c["refinement"]["records"][0].update(
                force_balance_relative_error=.1)),
            ("delta_mismatch",lambda c:c["refinement"]["adjacent_mesh_changes"][1].update(
                displacement_relative_change=0)),
            ("wrong_mesh_order",lambda c:c["refinement"]["records"][2].update(
                mesh_size_mm=13)),
        ]:
            with self.subTest(name=name):
                cloned=copy.deepcopy(case)
                change(cloned)
                with self.assertRaises(ValueError):
                    analyze_recorded_refinements([cloned])

    def test_rejects_inconsistent_raw_stability_flag(self):
        case=synthetic_case()
        case["refinement"]["displacement_observation"]="refinement_not_yet_stable"
        with self.assertRaises(ValueError):
            analyze_recorded_refinements([case])


if __name__=="__main__":
    unittest.main()
