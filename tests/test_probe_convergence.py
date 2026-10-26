"""Stress convergence must be evaluated at identical physical coordinates."""
import copy
import unittest

from ezfea.probe_convergence import screen_fixed_probe_stress


def series(stresses=(10., 10.4, 10.42), *, quality="inside_element",
           count=(60, 130, 300)):
    rows=[]
    for i, stress in enumerate(stresses):
        probe={"coordinate_mm":[50.13,4.31,5.82], "von_mises_mpa":stress,
               "location_quality":quality}
        rows.append({
            "mesh_size_mm":(14.,10.,7.)[i],
            "element_count":count[i],
            "fixed_coordinate_stress_affine":{"probes":{"midspan":probe}},
            "fixed_coordinate_stress":{"probes":{"midspan":probe}},
        })
    return rows


class FixedProbeConvergenceTests(unittest.TestCase):
    def test_stable_c3d10_interior_probe(self):
        report=screen_fixed_probe_stress(series(),element_type="C3D10")
        self.assertTrue(report["all_probes_stable_at_checked_mesh_sizes"])
        self.assertEqual(report["engineering_validation"],"not_established")
        self.assertEqual(len(report["probes"]["midspan"]["adjacent_relative_changes"]),2)

    def test_unstable_stress_not_called_stable(self):
        report=screen_fixed_probe_stress(series([10.,13.,17.]),element_type="C3D10")
        self.assertFalse(report["all_probes_stable_at_checked_mesh_sizes"])

    def test_fixed_probe_near_element_boundary_flags_review(self):
        report=screen_fixed_probe_stress(series(quality="near_element_boundary"),element_type="C3D10")
        self.assertFalse(report["all_probes_stable_at_checked_mesh_sizes"])
        self.assertTrue(report["probes"]["midspan"]["warnings"])

    def test_mesh_counts_must_increase(self):
        report=screen_fixed_probe_stress(series(count=[60,60,300]),element_type="C3D4")
        self.assertFalse(report["all_probes_stable_at_checked_mesh_sizes"])

    def test_moved_probe_is_rejected(self):
        rows=series()
        rows[2]["fixed_coordinate_stress_affine"]["probes"]["midspan"]["coordinate_mm"][0]+=0.1
        with self.assertRaisesRegex(ValueError,"moved"):
            screen_fixed_probe_stress(rows,element_type="C3D10")

    def test_probe_name_or_missing_data_is_rejected(self):
        rows=series()
        del rows[1]["fixed_coordinate_stress_affine"]["probes"]["midspan"]
        with self.assertRaisesRegex(ValueError,"missing"):
            screen_fixed_probe_stress(rows,element_type="C3D10")
        rows=series()
        rows[1]["fixed_coordinate_stress_affine"]["probes"]={"other": rows[1]["fixed_coordinate_stress_affine"]["probes"].pop("midspan")}
        with self.assertRaisesRegex(ValueError,"names changed"):
            screen_fixed_probe_stress(rows,element_type="C3D10")

    def test_nonfinite_stress_rejected(self):
        rows=series()
        rows[1]["fixed_coordinate_stress_affine"]["probes"]["midspan"]["von_mises_mpa"]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid stress"):
            screen_fixed_probe_stress(rows,element_type="C3D10")

    def test_distinct_c3d4_and_c3d10_recovery(self):
        rows=series()
        del rows[0]["fixed_coordinate_stress_affine"]
        self.assertTrue(screen_fixed_probe_stress(rows,element_type="C3D4")["all_probes_stable_at_checked_mesh_sizes"])


if __name__=="__main__":
    unittest.main()
