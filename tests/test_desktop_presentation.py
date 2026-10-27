"""Only a single force and direction is needed for a native 3D setup."""
import unittest

from ezfea.desktop_presentation import (
    PALETTE, DIRECTIONS, force_components, brief_native_result,
)


class SimplifiedDesktopTests(unittest.TestCase):
    def test_direction_maps_to_actual_xyz_newtons(self):
        vectors={
            "Down (−Y)":(0.,-125.,0.),
            "Up (+Y)":(0.,125.,0.),
            "Right (+X)":(125.,0.,0.),
            "Left (−X)":(-125.,0.,0.),
            "Forward (+Z)":(0.,0.,125.),
            "Back (−Z)":(0.,0.,-125.),
        }
        self.assertEqual(tuple(DIRECTIONS),tuple(vectors))
        for name,expected in vectors.items():
            with self.subTest(name=name):
                self.assertEqual(force_components("125",name),expected)

    def test_invalid_force_or_direction_is_rejected(self):
        for value in ("", "garbage", "0", "-100", "nan", "inf"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                force_components(value,"Down (−Y)")
        with self.assertRaisesRegex(ValueError,"direction"):
            force_components(100,"Random force")

    def test_neutral_black_lime_palette(self):
        self.assertEqual(PALETTE["background"],"#050607")
        self.assertEqual(PALETTE["accent"],"#c5ff4a")
        self.assertNotEqual(PALETTE["panel"],PALETTE["background"])

    def test_result_status_keeps_equilibrium_review_visible(self):
        s={"status":"completed","headline":"CALCULATION COMPLETED",
           "max_displacement":"0.02 mm","max_stress":"40 MPa",
           "force_balance":"PASS","moment_balance":"PASS"}
        x=brief_native_result(s)
        self.assertEqual(x["state"],"SOLVED")
        self.assertIn("Force PASS",x["balance"])
        s["status"]="needs_review"
        s["moment_balance"]="REVIEW"
        x=brief_native_result(s)
        self.assertEqual(x["state"],"REVIEW")
        self.assertIn("Moment REVIEW",x["balance"])
        s["status"]="failed"
        with self.assertRaises(ValueError):
            brief_native_result(s)


if __name__=="__main__":
    unittest.main()
