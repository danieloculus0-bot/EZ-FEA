"""Geometry fixture definitions stay stable between engine changes."""
import dataclasses
import math
import tempfile
import unittest

from ezfea.frame_benchmarks import STUDIES, FrameSpec, geometry_definition_sha256


class FrameSpecTests(unittest.TestCase):
    def test_six_distinct_named_studies(self):
        self.assertEqual(len(STUDIES),6)
        self.assertEqual(len({s.key for s in STUDIES}),6)
        self.assertEqual([s.construction for s in STUDIES],
                         ["portal","rectangle","braced","portal","rectangle","braced"])

    def test_matched_vertical_load_cases(self):
        self.assertEqual(STUDIES[4].load_n, STUDIES[5].load_n)
        self.assertEqual(STUDIES[0].load_n, STUDIES[4].load_n)
        self.assertEqual(STUDIES[4].construction, "rectangle")
        self.assertEqual(STUDIES[5].construction, "braced")

    def test_repeatable_definition_hash(self):
        a=STUDIES[1]
        self.assertEqual(geometry_definition_sha256(a),
                         geometry_definition_sha256(dataclasses.replace(a)))
        self.assertNotEqual(geometry_definition_sha256(a),
                            geometry_definition_sha256(dataclasses.replace(a, width_mm=260)))

    def test_stiffness_comparison_same_load_and_size(self):
        rectangle,braced=STUDIES[1],STUDIES[2]
        for field in ("width_mm","height_mm","depth_mm","member_mm","load_n"):
            self.assertEqual(getattr(rectangle,field),getattr(braced,field))

    def test_bad_geometry_rejected(self):
        for width in (0,40,-10,float("nan")):
            with self.subTest(width=width):
                with self.assertRaises(ValueError):
                    dataclasses.replace(STUDIES[0],width_mm=width).check()

    def test_zero_load_rejected(self):
        with self.assertRaises(ValueError):
            dataclasses.replace(STUDIES[0],load_n=(0.,0.,0.)).check()

if __name__=="__main__":
    unittest.main()
