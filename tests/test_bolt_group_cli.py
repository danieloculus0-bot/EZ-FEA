"""End-to-end JSON bolt-group CLI acceptance tests, using synthetic loads."""
import json
import subprocess
import sys
import unittest

from ezfea.bolt_group_cli import calculate, calculate_cases


class BoltGroupCliTests(unittest.TestCase):
    def test_equilibrium_and_peak(self):
        output = calculate({"positions": [[0, 0], [100, 0], [100, 50], [0, 50]],
                            "force_x": 100, "force_y": -200, "moment_z": 4000})
        bolts = output["bolts"]
        self.assertEqual(len(bolts), 4)
        self.assertAlmostEqual(sum(b["force_x"] for b in bolts), 100)
        self.assertAlmostEqual(sum(b["force_y"] for b in bolts), -200)
        cx, cy = output["centroid"]
        self.assertAlmostEqual(sum((b["x"] - cx) * b["force_y"] -
                                   (b["y"] - cy) * b["force_x"] for b in bolts), 4000)
        self.assertAlmostEqual(output["max_resultant"], max(b["resultant"] for b in bolts))

    def test_rejects_invalid_json_types(self):
        for payload in [
            {"positions": [[0, True]], "force_x": 0, "force_y": 1},
            {"positions": [[0, 0]], "force_x": "100", "force_y": 1},
            {"positions": [[0, 0]], "force_x": 1, "force_y": 1, "extra": 3},
            {"positions": [[0, 0], [0, 0]], "force_x": 0, "force_y": 0, "moment_z": 1},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                calculate(payload)

    def test_stdin_json_cli(self):
        payload = {"positions": [[0, 0], [2, 0]], "force_x": 0, "force_y": 80}
        result = subprocess.run([sys.executable, "-m", "ezfea.bolt_group_cli", "-"],
                                input=json.dumps(payload), capture_output=True,
                                text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual([b["force_y"] for b in data["bolts"]], [40, 40])

    def test_bad_input_fails_closed(self):
        result = subprocess.run([sys.executable, "-m", "ezfea.bolt_group_cli", "-"],
                                input='{"positions":[]}', capture_output=True,
                                text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(result.stdout)
        self.assertIn("input error", result.stderr)

    def test_multiple_cases_and_per_bolt_envelope(self):
        data = calculate_cases({"positions": [[0, 0], [100, 0]], "cases": [
            {"name": "direct", "force_x": 0, "force_y": 100},
            {"name": "torsion", "force_x": 0, "force_y": 0, "moment_z": 10000},
        ]})
        self.assertEqual(len(data["cases"]), 2)
        self.assertEqual(data["envelope"]["governing_case"], "torsion")
        self.assertAlmostEqual(data["envelope"]["max_resultant"], 100)
        self.assertEqual([b["governing_case"] for b in data["envelope"]["bolts"]],
                         ["torsion", "torsion"])

    def test_batch_rejects_duplicate_and_invalid_cases(self):
        for cases in [
            [{"name": "a", "force_x": 1, "force_y": 0},
             {"name": "a", "force_x": 2, "force_y": 0}],
            [{"name": "missing", "force_x": 1}],
            [{"name": "bad", "force_x": float("nan"), "force_y": 0}],
            [],
        ]:
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                calculate_cases({"positions": [[0, 0], [100, 0]], "cases": cases})

    def test_batch_stdin_cli(self):
        payload = {"positions": [[0, 0], [100, 0]], "cases": [
            {"name": "service", "force_x": 0, "force_y": 80},
            {"name": "reverse", "force_x": 0, "force_y": -120},
        ]}
        result = subprocess.run([sys.executable, "-m", "ezfea.bolt_group_cli", "-"],
                                input=json.dumps(payload), capture_output=True,
                                text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["envelope"]["governing_case"], "reverse")


if __name__ == "__main__":
    unittest.main()
