"""Joint matrix labels cannot authorize physics unless explicitly reviewed."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from ezfea.assembly_physics import reviewed_contact_plan
from ezfea.joint_matrix import validate_matrix


class ReviewedAssemblyPhysicsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.step=Path(self.temp.name)/"pair.step"
        self.step.write_bytes(b"CAD fixture original")
        self.matrix={
            "schema":"ezfea.joint_matrix.v1",
            "source_sha256":hashlib.sha256(self.step.read_bytes()).hexdigest(),
            "ground_component":1,
            "components":[
                {"id":1,"center_mm":[5.,5.,5.]},
                {"id":2,"center_mm":[5.,5.,15.]},
            ],
            "rows":[{"joint_id":"J-001","component_a":1,"component_b":2,
                "face_a":11,"face_b":12,
                "joint_type":"Contact only",
                "joint_confirmation":"explicit_user_choice",
                "mechanical_model":"experimental_separable_contact",
                "candidate_kind":"coincident_planar_faces",
                "overlap_area_bbox_mm2":100.}]
        }

    def test_reviewed_contact_produces_face_identified_plan(self):
        plan=reviewed_contact_plan(self.matrix,self.step)
        self.assertEqual(plan["base_component"],1)
        self.assertEqual(plan["pad_component"],2)
        self.assertEqual(plan["base_face"],11)
        self.assertEqual(plan["pad_face"],12)
        self.assertEqual(plan["model"],"experimental_separable_contact")

    def test_same_step_hash_required(self):
        self.step.write_bytes(b"changed CAD")
        with self.assertRaisesRegex(ValueError,"hash"):
            reviewed_contact_plan(self.matrix,self.step)

    def test_label_does_not_install_contact_without_explicit_model(self):
        self.matrix["rows"][0]["mechanical_model"]="unassigned"
        with self.assertRaisesRegex(ValueError,"physics model"):
            reviewed_contact_plan(self.matrix,self.step)

    def test_geometry_does_not_auto_confirm_joint(self):
        self.matrix["rows"][0]["joint_confirmation"]="not_reviewed"
        with self.assertRaisesRegex(ValueError,"reviewed"):
            reviewed_contact_plan(self.matrix,self.step)

    def test_welded_bolted_pinned_not_contact_substitutes(self):
        for kind in ("Welded","Bolted","Pinned"):
            self.matrix["rows"][0]["joint_type"]=kind
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,"Contact only"):
                reviewed_contact_plan(self.matrix,self.step)

    def test_multi_part_not_promised_as_supported(self):
        self.matrix["components"].append({"id":3,"center_mm":[1.,1.,1.]})
        with self.assertRaisesRegex(ValueError,"exactly two parts"):
            reviewed_contact_plan(self.matrix,self.step)

    def test_inverted_ground_rejected(self):
        self.matrix["ground_component"]=2
        with self.assertRaisesRegex(ValueError,"grounded lower"):
            reviewed_contact_plan(self.matrix,self.step)

    def test_unverified_face_kind_rejected(self):
        self.matrix["rows"][0]["candidate_kind"]="coincident_cylinders"
        with self.assertRaisesRegex(ValueError,"planar CAD"):
            reviewed_contact_plan(self.matrix,self.step)


if __name__=="__main__":
    unittest.main()
