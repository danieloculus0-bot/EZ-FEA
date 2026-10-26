"""Fail-closed pre-solve checks; run without installing Gmsh or CalculiX."""
import math
import unittest
from types import SimpleNamespace

from ezfea.mesh import _open_step
from ezfea.mesh_checks import audit_tetra_mesh, audit_gmsh_signed_quality


_NODES = {
    1: (0., 0., 0.),
    2: (1., 0., 0.),
    3: (0., 1., 0.),
    4: (0., 0., 1.),
    5: (0., 0., -1.),
    6: (1., 1., 1.),
}


class MeshCheckTests(unittest.TestCase):
    def test_valid_tet(self):
        result = audit_tetra_mesh({k: _NODES[k] for k in (1, 2, 3, 4)},
                                  {1: (1, 2, 3, 4)})
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["boundary_triangle_count"], 4)

    def test_two_tets_sharing_face_are_connected(self):
        result = audit_tetra_mesh({k: _NODES[k] for k in (1, 2, 3, 4, 5)},
                                  {1: (1, 2, 3, 4), 2: (1, 2, 3, 5)})
        self.assertEqual(result["element_count"], 2)
        self.assertEqual(result["boundary_triangle_count"], 6)

    def test_disconnected_solids_are_rejected(self):
        nodes = {**{k: _NODES[k] for k in (1, 2, 3, 4)},
                 10: (10., 0., 0.), 11: (11., 0., 0.),
                 12: (10., 1., 0.), 13: (10., 0., 1.)}
        with self.assertRaisesRegex(ValueError, "Disconnected volume mesh"):
            audit_tetra_mesh(nodes, {1: (1, 2, 3, 4),
                                     2: (10, 11, 12, 13)})

    def test_node_only_contact_is_not_a_connected_volume(self):
        nodes = {**{k: _NODES[k] for k in (1, 2, 3, 4)},
                 10: (10., 0., 0.), 11: (11., 1., 0.),
                 12: (10., 1., 1.)}
        with self.assertRaisesRegex(ValueError, "Disconnected volume mesh"):
            audit_tetra_mesh(nodes, {1: (1, 2, 3, 4), 2: (1, 10, 11, 12)})

    def test_zero_volume_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nearly zero tetrahedral volume"):
            audit_tetra_mesh({1:(0.,0.,0.), 2:(1.,0.,0.),
                              3:(0.,1.,0.), 4:(1.,1.,0.)}, {1:(1,2,3,4)})

    def test_duplicate_connectivity_and_missing_node_are_rejected(self):
        nodes = {k: _NODES[k] for k in (1, 2, 3, 4)}
        with self.assertRaisesRegex(ValueError, "repeated node IDs"):
            audit_tetra_mesh(nodes, {1:(1,1,2,3)})
        with self.assertRaisesRegex(ValueError, "absent"):
            audit_tetra_mesh(nodes, {1:(1,2,3,17)})

    def test_orphan_node_is_rejected(self):
        nodes = {k: _NODES[k] for k in (1, 2, 3, 4, 5)}
        with self.assertRaisesRegex(ValueError, "orphan nodes"):
            audit_tetra_mesh(nodes, {1:(1,2,3,4)})

    def test_nonfinite_coordinates_are_rejected(self):
        nodes = {k: _NODES[k] for k in (1, 2, 3, 4)}
        nodes[4] = (0., float("nan"), 1.)
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            audit_tetra_mesh(nodes, {1:(1,2,3,4)})

    def test_nonmanifold_face_is_rejected(self):
        nodes = {k: _NODES[k] for k in (1, 2, 3, 4, 5, 6)}
        with self.assertRaisesRegex(ValueError, "Nonmanifold"):
            audit_tetra_mesh(nodes, {1:(1,2,3,4),2:(1,2,3,5),3:(1,2,3,6)})

    def test_tet10_checks_all_ten_nodes(self):
        nodes = {1:(0.,0.,0.), 2:(1.,0.,0.),3:(0.,1.,0.),4:(0.,0.,1.),
                 5:(.5,0.,0.),6:(.5,.5,0.),7:(0.,.5,0.),
                 8:(0.,0.,.5),9:(.5,0.,.5),10:(0.,.5,.5)}
        self.assertEqual(audit_tetra_mesh(nodes,{99:tuple(range(1,11))},"C3D10")["element_count"],1)

    def test_signed_quality_rejects_inverted_and_missing(self):
        with self.assertRaisesRegex(ValueError, "Inverted/degenerate"):
            audit_gmsh_signed_quality([0.8,-0.1],2)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            audit_gmsh_signed_quality([0.8],2)
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            audit_gmsh_signed_quality([math.nan],1)
        result = audit_gmsh_signed_quality([0.04,0.6],2)
        self.assertTrue(result["low_quality_warning"])

    def test_step_import_sets_mm_before_open_cascade_import(self):
        sequence = []
        class FakeOcc:
            def importShapes(self, path):
                sequence.append(("import", path))
            def synchronize(self):
                sequence.append(("sync", None))
        fake = SimpleNamespace(
            model=SimpleNamespace(
                add=lambda label: sequence.append(("model", label)),
                occ=FakeOcc(),
                getEntities=lambda dim: [(3,1)] if dim==3 else [],
            ),
            option=SimpleNamespace(
                setString=lambda key,value: sequence.append(("unit",key,value)),
            )
        )
        _open_step(fake, "part.step")
        self.assertEqual(sequence[1], ("unit","Geometry.OCCTargetUnit","MM"))
        self.assertEqual(sequence[2], ("import","part.step"))


if __name__ == "__main__":
    unittest.main()
