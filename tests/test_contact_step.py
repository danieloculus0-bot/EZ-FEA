"""Controlled separate-solid STEP contact interface/deck invariants."""
import tempfile
import unittest
from pathlib import Path

from ezfea.contact_step import write_step_contact_deck,mesh_contact_step


class TwoBodySTEPContactTests(unittest.TestCase):
    def test_deck_has_true_c3d10_contact_without_ties(self):
        model={
            "nodes":{i:(float(i),0.,0.) for i in range(1,21)},
            "elements":{1:tuple(range(1,11)),2:tuple(range(11,21))},
            "base_fixed":[1,2,3],"pad_top":[18,19,20],
            "base_contact":[[1,2]],"pad_contact":[[2,1]],
        }
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"contact.inp"
            write_step_contact_deck(model,path,compression=True,contact=True)
            content=path.read_text()
            self.assertIn("*ELEMENT, TYPE=C3D10, ELSET=ALL",content)
            self.assertIn("*CONTACT PAIR, INTERACTION=FRICTIONLESS, TYPE=SURFACE TO SURFACE",content)
            self.assertIn("PAD_CONTACT, BASE_CONTACT",content)
            self.assertIn("1, S2",content)
            self.assertIn("2, S1",content)
            self.assertNotIn("*TIE",content)
            self.assertIn("PAD_TOP, 3, 3, -0.001",content)
            write_step_contact_deck(model,path,compression=False,contact=True)
            self.assertIn("PAD_TOP, 3, 3, 0.001",path.read_text())
            write_step_contact_deck(model,path,compression=True,contact=False)
            self.assertNotIn("*CONTACT PAIR",path.read_text())

    def test_invalid_requested_mesh_rejected_before_importing_gmsh(self):
        with self.assertRaisesRegex(ValueError,"Positive finite"):
            mesh_contact_step("does-not-exist.step",mesh_size_mm=-1)


if __name__=="__main__":
    unittest.main()
