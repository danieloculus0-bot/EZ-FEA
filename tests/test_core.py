import tempfile
import unittest
from pathlib import Path
from ezfea.core import Analysis, Material
from ezfea.mesh import Mesh, triangle_area, distributed_force_weights
from ezfea.solver import write_input
from ezfea.results import max_displacement_mm

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.step=Path(self.tmp.name)/"test.step"
        self.step.write_text("test")
    def tearDown(self):self.tmp.cleanup()
    def case(self,**kw):
        args=dict(step_file=str(self.step),fixed_face=1,loaded_face=2,
                  force_n=(0,-300,0),mesh_size_mm=2)
        args.update(kw)
        return Analysis(**args)
    def test_valid(self):self.case().validate()
    def test_zero_force(self):
        with self.assertRaises(ValueError):self.case(force_n=(0,0,0)).validate()
    def test_same_face(self):
        with self.assertRaises(ValueError):self.case(loaded_face=1).validate()
    def test_invalid_poisson(self):
        with self.assertRaises(ValueError):
            self.case(material=Material(poisson_ratio=0.6)).validate()
    def test_surface_weights(self):
        pts={1:(0,0,0),2:(2,0,0),3:(0,2,0),4:(2,2,0)}
        self.assertAlmostEqual(triangle_area(pts[1],pts[2],pts[3]),2)
        weights,area=distributed_force_weights([(1,2,3),(2,4,3)],pts)
        self.assertAlmostEqual(area,4)
        self.assertAlmostEqual(weights[2],1/3)
        self.assertAlmostEqual(sum(weights.values()),1)
    def test_solver_deck(self):
        mesh=Mesh({1:(0,0,0),2:(1,0,0),3:(0,1,0),4:(0,0,1),5:(2,0,0)},
                  {1:(1,2,3,4)},[1,2,3],{5:1},1)
        source=write_input(self.case(),mesh,Path(self.tmp.name)/"run.inp").read_text()
        self.assertIn("*ELEMENT, TYPE=C3D4",source)
        self.assertIn("CONNECTION, 1, 3, 0",source)
        self.assertIn("5, 2, -300",source)
        self.assertIn("*EL FILE\nS",source)
    def test_missing_displacement(self):
        self.assertIsNone(max_displacement_mm(Path(self.tmp.name)/"missing.dat"))
    def test_displacement(self):
        dat=Path(self.tmp.name)/"run.dat"
        dat.write_text("displacements (vx,vy,vz) for set NODES\n1 0.0E+00 3.0E-01 4.0E-01\n")
        self.assertAlmostEqual(max_displacement_mm(dat),.5)

if __name__=="__main__":unittest.main()
