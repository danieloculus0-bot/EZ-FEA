"""Desktop native stress-preview acceptance using fictional CalculiX records."""
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from ezfea.desktop_controller import write_native_stress_preview


class NativeDesktopStressPreviewTests(unittest.TestCase):
    def test_real_integration_point_records_generate_svg(self):
        data = """stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz)
1 1 100 0 0 0 0 0
2 1 0 0 0 0 0 0
global coordinates (elem, integ.pnt.,x,y,z)
1 1 0 0 0
2 1 10 5 1
"""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "analysis.dat").write_text(data, encoding="utf-8")
            svg = write_native_stress_preview(folder)
            self.assertEqual(svg, folder / "STRESS_POINTS.svg")
            root = ET.fromstring(svg.read_text(encoding="utf-8"))
            self.assertEqual(len(root.findall("{http://www.w3.org/2000/svg}circle")), 2)
            self.assertIn("no interpolation", svg.read_text(encoding="utf-8"))

    def test_missing_or_unmatched_coordinates_do_not_generate_fake_plot(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.assertIsNone(write_native_stress_preview(folder))
            (folder / "analysis.dat").write_text(
                "stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz)\n"
                "1 1 100 0 0 0 0 0\n"
                "global coordinates (elem, integ.pnt.,x,y,z)\n"
                "2 1 0 0 0\n", encoding="utf-8"
            )
            self.assertIsNone(write_native_stress_preview(folder))
            self.assertFalse((folder / "STRESS_POINTS.svg").exists())


if __name__ == "__main__":
    unittest.main()
