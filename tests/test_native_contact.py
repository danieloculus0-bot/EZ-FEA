"""Native pressure and two-body contact keyword/control regression tests."""
import unittest

from ezfea.contact_benchmarks import brick_nodes,contact_deck


class ContactDeckTests(unittest.TestCase):
    def test_two_solids_have_disjoint_nodes_and_touch_geometrically(self):
        nodes=brick_nodes()
        self.assertEqual(len(nodes),16)
        self.assertEqual(set(range(1,9)).intersection(range(9,17)),set())
        self.assertEqual(nodes[5],nodes[9])
        self.assertEqual(nodes[8],nodes[12])

    def test_contact_deck_disables_and_enables_real_interface(self):
        withcontact=contact_deck(mode="compression",enabled_contact=True)
        nocontact=contact_deck(mode="compression",enabled_contact=False)
        separated=contact_deck(mode="separation",enabled_contact=True)
        self.assertIn("*CONTACT PAIR, INTERACTION=FRICTIONLESS_PAD",withcontact)
        self.assertIn("*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR",withcontact)
        self.assertIn("PAD_INTERFACE, BASE_INTERFACE",withcontact)
        self.assertNotIn("*CONTACT PAIR",nocontact)
        self.assertIn("PAD_TOP, 3, 3, -0.001",withcontact)
        self.assertIn("PAD_TOP, 3, 3, 0.001",separated)
        self.assertIn("*NODE PRINT, NSET=BASE_BOTTOM",withcontact)

    def test_invalid_test_conditions_rejected(self):
        with self.assertRaises(ValueError):
            contact_deck(mode="shear")
        with self.assertRaises(ValueError):
            contact_deck(penalty_mpa_per_mm=0)


if __name__=="__main__":
    unittest.main()
