"""Mate candidate graph and Excel-style classification operations stay safe."""
import unittest

from ezfea.assembly_mates import match_planar_faces,build_joint_graph
from ezfea.joint_matrix import (
    matrix_from_graph,fill_down,paste_column,export_csv,validate_matrix
)


def face(component,tag,z,center_z,*,xmin=0,xmax=10):
    return {"component_id":component,"face_id":tag,
            "surface_type":"Plane",
            "body_center_mm":[5.,5.,center_z],
            "bbox_mm":[xmin,0.,z,xmax,10.,z]}


def graph():
    bodies=[{"id":1,"label":"Base"},{"id":2,"label":"Upright"},
            {"id":3,"label":"Bracket"},{"id":4,"label":"Detached"}]
    surfaces=[face(1,11,10,5),
              face(2,12,10,15),
              face(2,13,20,15),
              face(3,14,20,25)]
    return build_joint_graph(bodies,surfaces,1)


class MateMatrixTests(unittest.TestCase):
    def test_true_opposing_planar_faces_become_unassigned_candidates(self):
        result=match_planar_faces(face(1,11,10,5),face(2,12,10,15))
        self.assertEqual(result["candidate_kind"],"coincident_planar_faces")
        self.assertEqual(result["joint_type"],"unassigned")
        self.assertEqual(result["overlap_area_bbox_mm2"],100.)
        self.assertIsNone(match_planar_faces(face(1,11,10,5),face(3,12,10,5)))
        self.assertIsNone(match_planar_faces(face(1,11,10,5),
                                            face(2,12,10.5,15)))
        curved=face(2,12,10,15)
        curved["surface_type"]="Cylinder"
        self.assertIsNone(match_planar_faces(face(1,11,10,5),curved))

    def test_grounded_graph_is_not_a_claim_of_physical_stability(self):
        g=graph()
        self.assertEqual(len(g["joints"]),2)
        self.assertEqual(g["unreachable_components"],[4])
        self.assertEqual(g["components"][2]["ground_depth"],2)
        self.assertFalse(g["joint_types_inferred"])
        self.assertEqual(g["physics_readiness"],"unassigned_mates_require_human_review")

    def test_fill_down_copies_welded_without_inventing_constraint_model(self):
        matrix=matrix_from_graph(graph())
        self.assertTrue(validate_matrix(matrix))
        original_ids=[r["joint_id"] for r in matrix["rows"]]
        edited=paste_column(matrix,"joint_type",0,"Welded")
        copied=fill_down(edited,"joint_type",0,1)
        self.assertEqual([x["joint_type"] for x in copied["rows"]],["Welded","Welded"])
        self.assertEqual([x["mechanical_model"] for x in copied["rows"]],
                         ["unassigned","unassigned"])
        self.assertEqual([x["joint_confirmation"] for x in copied["rows"]],
                         ["explicit_user_choice"]*2)
        self.assertEqual([x["joint_id"] for x in copied["rows"]],original_ids)
        self.assertEqual([x["joint_type"] for x in matrix["rows"]],
                         ["Unassigned","Unassigned"])
        self.assertIn("joint_id",export_csv(copied).splitlines()[0])

    def test_atomic_paste_rejects_bogus_joint_choice(self):
        original=matrix_from_graph(graph())
        with self.assertRaisesRegex(ValueError,"Unknown joint type"):
            paste_column(original,"joint_type",0,"Welded\nBanana")
        self.assertEqual(original["rows"][0]["joint_type"],"Unassigned")
        with self.assertRaisesRegex(ValueError,"immutable"):
            fill_down(original,"component_a",0,1)
        with self.assertRaisesRegex(ValueError,"exceeds"):
            paste_column(original,"joint_type",1,"Welded\nPinned")
        selected=paste_column(original,"joint_type",0,"Welded\nPinned")
        self.assertEqual(selected["rows"][1]["joint_type"],"Pinned")
        self.assertTrue(validate_matrix(selected))


if __name__=="__main__":
    unittest.main()
