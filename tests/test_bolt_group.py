import math
import unittest
from ezfea.bolt_group import distribute_in_plane_load


class BoltGroupTests(unittest.TestCase):
    def test_direct_shear(self):
        centroid, j, loads = distribute_in_plane_load([(0,0),(4,0),(4,2),(0,2)],120,-80)
        self.assertEqual(centroid,(2,1))
        self.assertTrue(all((p.fx,p.fy)==(30,-20) for p in loads))
        self.assertAlmostEqual(max(p.resultant for p in loads),math.hypot(30,20))

    def test_equilibrium(self):
        centroid,j,loads=distribute_in_plane_load([(-2,-1),(2,-1),(2,1),(-2,1)],80,40,200)
        self.assertAlmostEqual(sum(p.fx for p in loads),80)
        self.assertAlmostEqual(sum(p.fy for p in loads),40)
        self.assertAlmostEqual(sum((p.x-centroid[0])*p.fy-(p.y-centroid[1])*p.fx for p in loads),200)

    def test_invalid(self):
        for positions,fx,fy,mz in [([],0,0,0), ([(0,0),(0,0)],0,0,1), ([(0,0)],float("nan"),0,0)]:
            with self.assertRaises(ValueError):
                distribute_in_plane_load(positions,fx,fy,mz)


if __name__=="__main__":
    unittest.main()
