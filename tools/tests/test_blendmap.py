"""
tests for tools/blendmap.py

run from the project root: python -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TOOLS)
import blendmap  # noqa: E402


QUAD_OBJ = """# a comment
mtllib level.mtl
o Floor
v 0 0 0
v 1 0 0
v 1 0 1
v 0 0 1
vt 0 0
vn 0 1 0
usemtl floor
s off
f 1/1/1 2/1/1 3/1/1 4/1/1
o Wall
v 0 0 0
v 0 1 0
v 1 1 0
usemtl wall
f -3 -2 -1
"""


class ReadObj(unittest.TestCase):
    def test_reads_vertices_scaled_to_zone_units(self):
        mesh = blendmap.read_obj(QUAD_OBJ, scale=256)
        self.assertEqual((0, 0, 0), mesh.verts[0])
        self.assertEqual((256, 0, 256), mesh.verts[2])
        self.assertEqual((256, 256, 0), mesh.verts[6])
        self.assertEqual(7, len(mesh.verts))

    def test_polygons_are_fanned_into_triangles(self):
        mesh = blendmap.read_obj(QUAD_OBJ, scale=256)
        floor = [t for t in mesh.tris if t.obj == "Floor"]
        self.assertEqual([(0, 1, 2), (0, 2, 3)], [t.verts for t in floor])

    def test_negative_indices_count_back_from_the_last_vertex(self):
        mesh = blendmap.read_obj(QUAD_OBJ, scale=256)
        wall = [t for t in mesh.tris if t.obj == "Wall"]
        self.assertEqual([(4, 5, 6)], [t.verts for t in wall])

    def test_triangles_know_their_object_and_material(self):
        mesh = blendmap.read_obj(QUAD_OBJ, scale=256)
        self.assertEqual([("Floor", "floor")] * 2 + [("Wall", "wall")],
                         [(t.obj, t.mat) for t in mesh.tris])

    def test_turn_rotates_about_the_up_axis(self):
        # a quarter turn takes +x to -z (seen from above, anticlockwise), up stays up
        mesh = blendmap.read_obj("v 1 2 0\n", scale=1, turn=90)
        self.assertEqual((0, 2, -1), mesh.verts[0])
        mesh = blendmap.read_obj("v 1 2 0\n", scale=1, turn=180)
        self.assertEqual((-1, 2, 0), mesh.verts[0])

    def test_turn_has_to_be_a_multiple_of_90(self):
        with self.assertRaises(ValueError):
            blendmap.read_obj("v 1 2 0\n", scale=1, turn=45)

    def test_face_with_a_missing_vertex_is_an_error(self):
        with self.assertRaises(ValueError):
            blendmap.read_obj("v 0 0 0\nv 1 0 0\nf 1 2 3\n", scale=1)


def box_mesh(x0, y0, z0, x1, y1, z1):
    """a mesh of two triangles spanning the box's corners"""
    verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z1)]
    return blendmap.Mesh(verts, [blendmap.Tri((0, 1, 2), None, None)])


class Fit(unittest.TestCase):
    def test_moves_the_mesh_to_the_zones_corner(self):
        fit = blendmap.fit(box_mesh(-1000, -500, 300, 1000, 500, 900), cell=128, headroom=0)
        self.assertEqual((0, 0, 0), tuple(min(v[i] for v in fit.mesh.verts) for i in range(3)))
        self.assertEqual((2000, 1000, 600), tuple(max(v[i] for v in fit.mesh.verts) for i in range(3)))
        self.assertEqual((-1000, -500, 300), fit.offset)

    def test_vertices_are_on_multiples_of_8(self):
        fit = blendmap.fit(box_mesh(0.4, 3, 13, 1001, 20.2, 30), cell=128, headroom=0)
        for v in fit.mesh.verts:
            for c in v:
                self.assertIsInstance(c, int)
                self.assertEqual(0, c % 8, v)
        self.assertEqual((1000, 16, 16), fit.mesh.verts[2])

    def test_each_side_is_a_power_of_two_cells(self):
        fit = blendmap.fit(box_mesh(0, 0, 0, 1000, 129, 5000), cell=128, headroom=0)
        self.assertEqual((1024, 256, 8192), fit.size)

    def test_headroom_is_added_above(self):
        fit = blendmap.fit(box_mesh(0, 0, 0, 1000, 100, 1000), cell=128, headroom=1500)
        self.assertEqual(2048, fit.size[1])

    def test_triangles_are_kept(self):
        mesh = box_mesh(0, 0, 0, 1, 1, 1)
        self.assertIs(mesh.tris, blendmap.fit(mesh, cell=128, headroom=0).mesh.tris)

    def test_too_big_for_a_world_mesh_is_an_error(self):
        # world mesh vertices are 13 bits of multiples of 8 (src/formats/wgeo.h)
        with self.assertRaises(ValueError):
            blendmap.fit(box_mesh(0, 0, 0, 40000, 10, 10), cell=128, headroom=0)


if __name__ == "__main__":
    unittest.main()
