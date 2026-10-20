"""Publishing bridge tests: no missing or failed native physics ever reaches Pages."""
from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from ezfea.frame_benchmarks import STUDIES, geometry_definition_sha256
from scripts.publish_frame_evidence import export_frame_evidence


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


class NativeResultsPublishingTests(unittest.TestCase):
    def populate(self, root):
        put(root/"suite_summary.json", {
            "schema": "ezfea.frame_suite.v1",
            "case_results": [{"key": s.key} for s in STUDIES],
        })
        for i, spec in enumerate(STUDIES):
            folder=root/spec.key
            identity=geometry_definition_sha256(spec)
            put(folder/"specimen.json", {
                "schema": "ezfea.frame_specimen.v1",
                "identity_sha256": identity,
                "geometry": asdict(spec),
                "mesh_size_mm": 14,
                "material": {"name": "nominal steel", "elastic_modulus_mpa": 200000, "yield_mpa": 250},
                "loads": [{"face": 1, "force_n": list(spec.load_n)}],
                "supports": [{"face": 2, "axes": [1,2,3]}],
            })
            put(folder/"latest_result.json", {
                "status": "completed",
                "specimen": identity,
                "mesh": {"nodes": 400, "elements": 500},
                "results": {
                    "source": "analysis.dat",
                    "force_balance_check": "pass",
                    "force_balance_relative_error": 1e-7,
                    "max_displacement_mm": 0.01 if i!=2 else 0.003,
                    "max_von_mises_mpa": 5+i,
                }
            })

    def export(self, root):
        return export_frame_evidence(
            root,root/"published.json",
            source_run="https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/123",
            source_commit="testsha",
        )

    def test_six_case_evidence_has_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.populate(root)
            artifact=self.export(root)
            self.assertEqual(len(artifact["studies"]),len(STUDIES))
            self.assertEqual(artifact["schema"],"ezfea.frame_evidence.v1")
            self.assertEqual(artifact["studies"][0]["mesh_elements"],500)
            self.assertEqual(artifact["studies"][0]["force_balance_check"],"pass")
            self.assertTrue((root/"published.json").exists())

    def test_bad_equilibrium_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.populate(root)
            target=root/STUDIES[4].key/"latest_result.json"
            data=json.loads(target.read_text())
            data["results"]["force_balance_relative_error"]=.25
            put(target,data)
            with self.assertRaises(ValueError):
                self.export(root)
            self.assertFalse((root/"published.json").exists())

    def test_missing_solve_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.populate(root)
            (root/STUDIES[-1].key/"latest_result.json").unlink()
            with self.assertRaises(FileNotFoundError):
                self.export(root)


if __name__=="__main__":
    unittest.main()
