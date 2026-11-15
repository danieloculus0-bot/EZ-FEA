import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from ezfea.stress_plot import render_svg, stress_points


class StressPlotTests(unittest.TestCase):
    def test_actual_dat_points_and_svg(self):
        data = """stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz)
1 1 100 0 0 0 0 0
2 1 0 0 0 0 0 0
global coordinates (elem, integ.pnt.,x,y,z)
1 1 0 0 0
2 1 10 5 1
"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample.dat"
            p.write_text(data)
            points = stress_points(p)
            self.assertEqual(len(points), 2)
            self.assertAlmostEqual(points[0][-1], 100)
            svg = render_svg(points)
            root = ET.fromstring(svg)
            circles = root.findall("{http://www.w3.org/2000/svg}circle")
            self.assertEqual(len(circles), 2)
            self.assertIn("no interpolation", svg)

    def test_missing_coordinate_rejected(self):
        data = """stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz)
1 1 100 0 0 0 0 0
global coordinates (elem, integ.pnt.,x,y,z)
2 1 0 0 0
"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample.dat"
            p.write_text(data)
            with self.assertRaises(ValueError):
                stress_points(p)


if __name__ == "__main__":
    unittest.main()
