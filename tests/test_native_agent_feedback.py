"""Synthetic contract tests for native FEA agent feedback, no solver fixtures."""
import copy
import unittest

from ezfea.native_agent_feedback import score_native_predictions


def curriculum():
    return {
        "schema": "ezfea.real_structural_curriculum.v1",
        "training_geometry_disjoint_from_holdout": True,
        "cases": [
            {
                "case_id": "train-axial-01", "split": "train",
                "geometry_key": '["axial",[80,10,9]]',
                "status": "measured",
                "test_origin": "native_step_gmsh_calculix_c3d10",
                "native_measured": 2.0, "target_metric": "midspan_abs_sigma_x_mpa",
            },
            {
                "case_id": "holdout-bending-01", "split": "holdout",
                "geometry_key": '["bending",[95,10,13]]',
                "status": "measured",
                "test_origin": "native_step_gmsh_calculix_c3d10",
                "native_measured": 0.4, "target_metric": "tip_displacement_mm",
            },
            {
                "case_id": "holdout-torsion-01", "split": "holdout",
                "geometry_key": '["torsion",[105,10.5]]',
                "status": "measured",
                "test_origin": "native_step_gmsh_calculix_c3d10",
                "native_measured": 0.002, "target_metric": "abs_tip_twist_rad",
            },
        ],
    }


def predictions():
    return [
        {"case_id": "holdout-torsion-01", "predicted_value": 0.004},
        {"case_id": "holdout-bending-01", "predicted_value": 0.4},
    ]


class NativeAgentFeedbackTests(unittest.TestCase):
    def test_real_measurements_are_independently_scored(self):
        report = score_native_predictions(curriculum(), predictions())
        self.assertEqual(report["specimens_scored"], 2)
        self.assertAlmostEqual(report["mean_score"], 0.75)
        self.assertEqual([row["case_id"] for row in report["results"]],
                         ["holdout-bending-01", "holdout-torsion-01"])
        self.assertEqual(report["results"][0]["score"], 1.0)
        self.assertAlmostEqual(report["results"][1]["relative_error"], 1.0)
        self.assertFalse(report["model_learning_verified"])

    def test_train_cannot_be_scored_as_holdout(self):
        with self.assertRaisesRegex(ValueError, "exactly cover"):
            score_native_predictions(curriculum(), [
                {"case_id": "train-axial-01", "predicted_value": 2.0},
            ])

    def test_unmeasured_or_fake_native_origin_rejected(self):
        for key, value in [("status", "needs_review"), ("test_origin", "surrogate")]:
            with self.subTest(key=key):
                data = curriculum()
                data["cases"][1][key] = value
                with self.assertRaisesRegex(ValueError, "unverified"):
                    score_native_predictions(data, predictions())

    def test_geometry_leakage_rejected_even_if_flag_is_true(self):
        data = curriculum()
        data["cases"][1]["geometry_key"] = data["cases"][0]["geometry_key"]
        with self.assertRaisesRegex(ValueError, "leakage"):
            score_native_predictions(data, predictions())

    def test_missing_duplicate_extra_or_fabricated_scores_rejected(self):
        for submitted in [
            predictions()[:1],
            predictions() + predictions()[:1],
            predictions() + [{"case_id": "unknown", "predicted_value": 1.0}],
            [{"case_id": "holdout-bending-01", "predicted_value": 0.4, "score": 999},
             predictions()[0]],
        ]:
            with self.subTest(submitted=submitted):
                with self.assertRaises(ValueError):
                    score_native_predictions(curriculum(), submitted)

    def test_nonfinite_boolean_and_negative_predictions_rejected(self):
        for value in (float("nan"), float("inf"), True, 0, -1):
            submitted = predictions()
            submitted[0]["predicted_value"] = value
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite and positive"):
                    score_native_predictions(curriculum(), submitted)

    def test_input_is_unchanged_and_replay_is_deterministic(self):
        data, submitted = curriculum(), predictions()
        original = copy.deepcopy((data, submitted))
        self.assertEqual(score_native_predictions(data, submitted),
                         score_native_predictions(data, submitted))
        self.assertEqual((data, submitted), original)


if __name__ == "__main__":
    unittest.main()
