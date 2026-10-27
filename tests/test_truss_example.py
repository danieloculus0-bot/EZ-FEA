"""Real STEP Warren weldment demonstrator: no fake weld physics."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from ezfea.truss_example import (
    SCHEMA,HEIGHT,SPAN,LOAD_N,members,
    generate_example,select_faces,analysis_case,
)


class TrussExampleTests(unittest.TestCase):
    def test_members_are_ten_distinct_solid_square_bars(self):
        data=members()
        self.assertEqual(len(data),10)
        self.assertEqual(len([m for m in data if m["kind"]=="web"]),8)
        self.assertEqual(len(set(m["id"] for m in data)),10)
        self.assertEqual(data[0]["end"][0],SPAN)
        self.assertEqual(data[1]["start"][1],HEIGHT)
        self.assertTrue(all(
            math.dist(m["start"],m["end"])>0 and
            m["square_side_mm"]>0 for m in data))

    def test_actual_native_step_exports_and_selection_identity(self):
        try:
            import gmsh
        except ImportError:
            self.skipTest("Native Gmsh required")
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            manifest=generate_example(root)
            self.assertEqual(manifest["schema"],SCHEMA)
            self.assertEqual(manifest["separate"]["solids"],10)
            self.assertEqual(manifest["fused"]["solids"],1)
            self.assertEqual(manifest["member_count"],10)
            from ezfea.mesh import inspect_step
            independent=root/"separate_members.step"
            fused=root/"fused_ideal_joints.step"
            self.assertTrue(independent.is_file())
            self.assertTrue(fused.is_file())
            self.assertEqual(hashlib.sha256(fused.read_bytes()).hexdigest(),
                             manifest["fused"]["sha256"])
            selected=select_faces(fused)
            self.assertEqual(set(selected),{"left","right","load"})
            self.assertEqual(len(set(selected.values())),3)
            ids={f.tag for f in inspect_step(fused)}
            self.assertTrue(set(selected.values()).issubset(ids))
            case=analysis_case(fused,selected,16)
            case.validate()
            self.assertEqual(case.element_type,"C3D10")
            self.assertEqual(len(case.connections),2)
            self.assertEqual(case.connections[0].axes,(1,2,3))
            self.assertEqual(case.connections[1].axes,(2,3))
            self.assertEqual(case.total_force_n,(0.,-LOAD_N,0.))
            self.assertEqual(len(case.active_loads),1)

    def test_nonphysical_mesh_or_reused_part_face_cannot_pass(self):
        with self.assertRaisesRegex(ValueError,"finite and positive"):
            analysis_case("invalid.step",{"left":1,"right":2,"load":3},0)


if __name__=="__main__":
    unittest.main()
