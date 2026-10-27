"""Prove round-hole/topology suggestions are from actual imported STEP."""
import hashlib
import tempfile
from pathlib import Path
import unittest

from ezfea.fixture_suggestions import SCHEMA,check_hints,choose_coplanar_supports
from ezfea.desktop_preview import extract_step_faces,validate_preview
from ezfea.core import Face
from ezfea.desktop_controller import build_multi_analysis
from ezfea.desktop_worker import read_request


def defaults():
    return {
        "fx":0.,"fy":-150.,"fz":0.,"mesh":"7",
        "e":"200000","nu":"0.26","yield_mpa":"250",
        "element_type":"C3D10",
    }


class HoleRecognitionTests(unittest.TestCase):
    def test_two_real_cut_through_holes_suggest_adjacent_planar_mounting_face(self):
        try:
            import gmsh
        except ImportError:
            self.skipTest("Real OCC STEP/Gmsh dependency required")
        from ezfea.fixture_examples import drilled_plate_step
        from ezfea.mesh import inspect_step
        with tempfile.TemporaryDirectory() as tmp:
            p=drilled_plate_step(Path(tmp)/"drilled_plate.step")
            faces=inspect_step(p)
            data=extract_step_faces(p)
            sha=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(data["source_sha256"],sha)
            self.assertEqual({f.tag for f in faces},set(data["cad_face_ids"]))
            validate_preview(data,expected_sha=sha,expected_faces=[f.tag for f in faces])
            hints=data["fixture_hints"]
            self.assertEqual(hints["schema"],SCHEMA)
            self.assertGreaterEqual(hints["cylindrical_face_count"],2)
            self.assertGreaterEqual(hints["planar_face_count"],2)
            self.assertTrue(hints["suggested_support_faces"])
            selection=check_hints(hints,source_sha256=sha,
                                  face_ids=[f.tag for f in faces])
            self.assertEqual(len(selection),1)
            self.assertGreaterEqual(hints["support_candidates"][0]["round_features_nearby"],2)
            self.assertTrue(hints["must_confirm_before_solve"])
            self.assertIn("actual_bolt_presence",hints["not_inferred"])

    def test_multiple_coplanar_mounts_but_not_both_sides_of_a_plate(self):
        def plane(tag,z,nearby,x):
            return {"face":tag,"round_features_nearby":nearby,
                    "bounds_mm":[x,0.,z,x+22.,20.,z]}
        choices=[
            plane(10,0,1,0),plane(11,0,1,100),
            plane(12,10,1,0),plane(13,10,1,100),
        ]
        self.assertEqual(choose_coplanar_supports(choices),[10,11])
        self.assertEqual(choose_coplanar_supports(choices,max_faces=1),[10])
        with self.assertRaises(ValueError):
            choose_coplanar_supports(choices,max_faces=100)

    def test_hints_reject_unrelated_cad_face_or_stale_sha(self):
        good={
            "schema":SCHEMA,"source_sha256":"a"*64,
            "support_candidates":[{"face":3,"round_features_nearby":2}],
            "suggested_support_faces":[3]
        }
        self.assertEqual(check_hints(good,source_sha256="a"*64,face_ids=[3,7]),[3])
        with self.assertRaisesRegex(ValueError,"current STEP"):
            check_hints(good,source_sha256="b"*64,face_ids=[3,7])
        with self.assertRaisesRegex(ValueError,"unknown"):
            check_hints(good,source_sha256="a"*64,face_ids=[7,8])
        good["suggested_support_faces"]=[3,7]
        with self.assertRaises(ValueError):
            check_hints(good,source_sha256="a"*64,face_ids=[3,7])

    def test_multi_support_analysis_uses_real_face_ids_and_free_axes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cad=Path(tmp)/"example.step"
            cad.write_text("mock source only for input validation; NOT a solved geometry")
            faces=[
                Face(5,(0.,0.,0.),(0.,0.,0.,1.,1.,1.)),
                Face(8,(100.,0.,0.),(99.,0.,0.,100.,1.,1.)),
                Face(11,(50.,50.,0.),(49.,49.,0.,51.,51.,1.)),
            ]
            supports=[
                {"face":5,"axes":[1,2,3]},
                {"face":8,"axes":[2,3]},
            ]
            case=build_multi_analysis(cad,faces,supports,2,defaults())
            self.assertEqual(case.fixed_face,0)
            self.assertEqual(case.loaded_face,0)
            self.assertEqual([s.face for s in case.connections],[5,8])
            self.assertEqual(case.connections[1].axes,(2,3))
            self.assertEqual(case.active_loads[0].face,11)
            self.assertEqual(case.total_force_n,(0.,-150.,0.))
            import json
            from dataclasses import asdict
            worker=Path(tmp)/"req.json"
            worker.write_text(json.dumps({
                "schema":"ezfea.desktop_request.v1",
                "output_root":tmp,
                "case":{
                    "step_file":case.step_file,"fixed_face":case.fixed_face,
                    "loaded_face":case.loaded_face,"force_n":list(case.force_n),
                    "mesh_size_mm":case.mesh_size_mm,
                    "material":asdict(case.material),"element_type":case.element_type,
                    "connections":[asdict(s) for s in case.connections],
                    "loads":[asdict(l) for l in case.loads],
                }
            }))
            recovered,output=read_request(worker)
            self.assertEqual(recovered.connections,case.connections)
            self.assertEqual(recovered.loads,case.loads)
            self.assertEqual(str(output),tmp)
            # A force at a held plane must not silently become a valid solve.
            with self.assertRaisesRegex(ValueError,"cannot also"):
                build_multi_analysis(cad,faces,supports,0,defaults())
            with self.assertRaisesRegex(ValueError,"duplicated"):
                build_multi_analysis(cad,faces,supports+[supports[0]],2,defaults())


if __name__=="__main__":
    unittest.main()
