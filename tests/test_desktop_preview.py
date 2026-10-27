"""3D CAD viewer geometry and face IDs must match the *source* STEP solid."""
import json
import math
from pathlib import Path
import tempfile
import unittest

from ezfea.desktop_preview import (
    MAX_PREVIEW_TRIANGLES,SCHEMA,validate_preview,
    projected_triangles,face_under_cursor,
)


def square_fixture():
    return {
        "schema":SCHEMA,"source_sha256":"a"*64,
        "cad_face_ids":[3,7],
        "triangles":[
            {"face":3,"points":[[-1.,0.,-1.],[1.,0.,-1.],[1.,0.,1.]]},
            {"face":3,"points":[[-1.,0.,-1.],[1.,0.,1.],[-1.,0.,1.]]},
            {"face":7,"points":[[-1.,1.,-1.],[1.,1.,-1.],[1.,1.,1.]]},
            {"face":7,"points":[[-1.,1.,-1.],[1.,1.,1.],[-1.,1.,1.]]},
        ],
        "triangle_count":4,
    }


class CADDirectSelectionTests(unittest.TestCase):
    def test_original_cad_face_ids_survive_triangle_projection_and_click(self):
        data=square_fixture()
        triangles=validate_preview(data,expected_sha="a"*64,expected_faces=[3,7])
        self.assertEqual(len(triangles),4)
        painted=projected_triangles(triangles,500,380,yaw=0,pitch=0)
        self.assertEqual({r[1] for r in painted},{3,7})
        # Orthographic view from +Y: a center click must pick front face 7.
        tag=face_under_cursor(painted,250,190)
        self.assertEqual(tag,7)
        self.assertIsNone(face_under_cursor(painted,-100,-100))

    def test_stale_source_sha_and_unknown_face_fail_closed(self):
        data=square_fixture()
        with self.assertRaisesRegex(ValueError,"currently opened STEP"):
            validate_preview(data,expected_sha="b"*64,expected_faces=[3,7])
        with self.assertRaisesRegex(ValueError,"differ"):
            validate_preview(data,expected_sha="a"*64,expected_faces=[3,8])
        data["triangles"][0]["face"]=99
        with self.assertRaisesRegex(ValueError,"unknown"):
            validate_preview(data,expected_sha="a"*64,expected_faces=[3,7])

    def test_incomplete_and_nonfinite_render_mesh_rejected(self):
        data=square_fixture()
        data["triangles"]=data["triangles"][:2]
        data["triangle_count"]=2
        with self.assertRaisesRegex(ValueError,"omitted"):
            validate_preview(data,expected_sha="a"*64,expected_faces=[3,7])
        data=square_fixture()
        data["triangles"][1]["points"][0][0]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid"):
            validate_preview(data,expected_sha="a"*64,expected_faces=[3,7])

    def test_rotation_keeps_original_face_identity(self):
        triangles=validate_preview(square_fixture(),expected_sha="a"*64,
                                   expected_faces=[3,7])
        for yaw,pitch in ((-.55,.4),(0.,.2),(.8,-.4),(1.5,1.1)):
            with self.subTest(angles=(yaw,pitch)):
                painted=projected_triangles(triangles,600,400,yaw,pitch)
                self.assertTrue(painted)
                self.assertTrue(all(face in (3,7) for _,face,_ in painted))

    def test_actual_demo_step_surface_tags_are_selected(self):
        import importlib.util
        if importlib.util.find_spec("gmsh") is None:
            self.skipTest("Native Gmsh API is not installed")
        from ezfea.demo import make_demo_step
        from ezfea.mesh import inspect_step
        from ezfea.desktop_preview import extract_step_faces
        with tempfile.TemporaryDirectory() as tmp:
            source=make_demo_step(Path(tmp)/"demo.step")
            faces=inspect_step(source)
            data=extract_step_faces(source)
            tris=validate_preview(data,expected_sha=data["source_sha256"],
                                  expected_faces=[f.tag for f in faces])
            self.assertEqual({tag for tag,_ in tris},{f.tag for f in faces})
            self.assertEqual(len(data["cad_face_ids"]),6)
            self.assertGreater(len(tris),30)
            self.assertLess(len(tris),MAX_PREVIEW_TRIANGLES)


if __name__=="__main__":
    unittest.main()
