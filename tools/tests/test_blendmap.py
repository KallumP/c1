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
        fit = blendmap.fit(box_mesh(0, 0, 0, 1000, 140, 5000), cell=128, headroom=0)
        self.assertEqual((1024, 256, 8192), fit.size)

    def test_headroom_is_added_above(self):
        fit = blendmap.fit(box_mesh(0, 0, 0, 1000, 100, 1000), cell=128, headroom=1500)
        self.assertEqual(2048, fit.size[1])

    def test_triangles_are_kept(self):
        mesh = box_mesh(0, 0, 0, 1, 1, 1)
        self.assertIs(mesh.tris, blendmap.fit(mesh, cell=128, headroom=0).mesh.tris)

    def test_margin_leaves_room_around_the_mesh(self):
        fit = blendmap.fit(box_mesh(0, 0, 0, 1000, 100, 1000), cell=128, headroom=0, margin=128)
        self.assertEqual((128, 128, 128), tuple(min(v[i] for v in fit.mesh.verts) for i in range(3)))
        self.assertEqual((2048, 256, 2048), fit.size)  # 1000 + 2 margins, 100 + 1 margin below

    def test_too_big_for_a_world_mesh_is_an_error(self):
        # world mesh vertices are 13 bits of multiples of 8 (src/formats/wgeo.h)
        with self.assertRaises(ValueError):
            blendmap.fit(box_mesh(0, 0, 0, 40000, 10, 10), cell=128, headroom=0)


def quad_mesh(corners, obj=None):
    """a mesh of one quad (corners anticlockwise seen from its front)"""
    return blendmap.Mesh(list(corners), [blendmap.Tri((0, 1, 2), obj, None),
                                         blendmap.Tri((0, 2, 3), obj, None)])


def floor(x0, z0, x1, z1, y, obj=None):
    """an upward facing quad"""
    return quad_mesh([(x0, y, z0), (x0, y, z1), (x1, y, z1), (x1, y, z0)], obj)


def merged(*meshes):
    verts, tris = [], []
    for m in meshes:
        tris += [blendmap.Tri(tuple(i + len(verts) for i in t.verts), t.obj, t.mat) for t in m.tris]
        verts += m.verts
    return blendmap.Mesh(verts, tris)


class SolidCells(unittest.TestCase):
    SIZE = (1024, 2048, 1024)

    def cells(self, mesh):
        return blendmap.solid_cells(mesh, self.SIZE, cell=128)

    def test_floor_is_solid_just_below_its_top(self):
        cells = self.cells(floor(0, 0, 512, 256, y=512))
        self.assertEqual({(i, 3, k) for i in range(4) for k in range(2)}, set(cells))
        self.assertEqual({"ground"}, set(cells.values()))

    def test_a_floor_off_the_grid_goes_to_the_nearest_cell_top(self):
        self.assertEqual(set(self.cells(floor(0, 0, 512, 256, y=512))),
                         set(self.cells(floor(0, 0, 512, 256, y=488))))
        self.assertEqual({(i, 4, k) for i in range(4) for k in range(2)},
                         set(self.cells(floor(0, 0, 512, 256, y=600))))

    def test_wall_is_solid_behind_its_face(self):
        # a wall at x 512 facing +x, 256 high and 256 along z
        wall = quad_mesh([(512, 0, 0), (512, 256, 0), (512, 256, 256), (512, 0, 256)])
        self.assertEqual({(3, j, k) for j in range(2) for k in range(2)}, set(self.cells(wall)))

    def test_ceiling_is_solid_above_its_face(self):
        ceiling = quad_mesh([(0, 1024, 0), (256, 1024, 0), (256, 1024, 256), (0, 1024, 256)])
        self.assertEqual({(i, 8, k) for i in range(2) for k in range(2)}, set(self.cells(ceiling)))

    def test_slope_is_a_staircase(self):
        # rises from 256 to 512 over 512 along -z
        slope = quad_mesh([(0, 256, 512), (128, 256, 512), (128, 512, 0), (0, 512, 0)])
        cells = set(self.cells(slope))
        self.assertIn((0, 3, 0), cells)  # top step, under the high end
        self.assertIn((0, 1, 3), cells)  # bottom step
        self.assertNotIn((0, 3, 3), cells)

    def test_pit_objects_are_deadly(self):
        cells = self.cells(merged(floor(0, 0, 256, 256, y=256, obj="Pit.001"),
                                  floor(256, 0, 512, 256, y=256, obj="Ground")))
        self.assertEqual("pit", cells[(0, 1, 0)])
        self.assertEqual("ground", cells[(2, 1, 0)])

    def test_pit_wins_where_they_share_a_cell(self):
        cells = self.cells(merged(floor(0, 0, 256, 256, y=256, obj="Ground"),
                                  floor(0, 0, 256, 256, y=256, obj="pit")))
        self.assertEqual({"pit"}, set(cells.values()))

    def test_cells_outside_the_zone_are_left_out(self):
        self.assertEqual({}, self.cells(floor(0, 0, 512, 256, y=0)))

    def test_flat_triangles_are_skipped(self):
        line = blendmap.Mesh([(0, 512, 0), (256, 512, 0), (512, 512, 0)],
                             [blendmap.Tri((0, 1, 2), None, None)])
        self.assertEqual({}, self.cells(line))


GROUND, SIDE = (5, 1), (9, 2)  # (tinf, tpag)


def worlds(mesh, piece=256):
    return blendmap.world_meshes(mesh, piece, GROUND, SIDE)


def area(verts, poly):
    a, b, c = (verts[i][:3] for i in poly[:3])
    n = blendmap.cross(blendmap.sub(b, a), blendmap.sub(c, a))
    return (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5 / 2


class WorldMeshes(unittest.TestCase):
    def test_polygons_are_sliced_into_pieces_along_z(self):
        [(verts, polys)] = worlds(floor(0, 0, 512, 1024, y=256))
        for p in polys:
            zs = [verts[i][2] for i in p[:3]]
            self.assertEqual(min(zs) // 256, (max(zs) - 1) // 256, zs)  # within one piece
        self.assertAlmostEqual(512 * 1024, sum(area(verts, p) for p in polys))

    def test_slicing_leaves_no_cracks_along_shared_edges(self):
        # two triangles sharing a slanted edge: wherever a slice cuts it, both sides get the same vertex
        mesh = blendmap.Mesh([(0, 0, 0), (512, 0, 1000), (0, 0, 1000), (512, 0, 0)],
                             [blendmap.Tri((0, 2, 1), None, None), blendmap.Tri((0, 1, 3), None, None)])
        [(verts, polys)] = worlds(mesh)

        def on_edge(v):  # within the rounding to multiples of 8
            return abs(v[2] * 512 - v[0] * 1000) <= 8 * 1000

        sides = [set(), set()]
        for p in polys:
            xs = [verts[i][0] for i in p[:3]]
            left = sum(xs) * 1000 < sum(verts[i][2] for i in p[:3]) * 512  # centre left of the edge
            sides[left] |= {verts[i][:3] for i in p[:3] if on_edge(verts[i])}
        self.assertEqual(sides[0], sides[1])
        self.assertGreater(len(sides[0]), 2)

    def test_vertices_are_on_multiples_of_8(self):
        mesh = blendmap.Mesh([(0, 0, 0), (504, 96, 1000), (0, 0, 1000)],
                             [blendmap.Tri((0, 1, 2), None, None)])
        for verts, polys in worlds(mesh):
            for v in verts:
                self.assertEqual((0, 0, 0), tuple(c % 8 for c in v[:3]), v)

    def test_up_facing_polygons_use_the_ground_texture_and_the_rest_the_side(self):
        wall = quad_mesh([(512, 0, 0), (512, 256, 0), (512, 256, 256), (512, 0, 256)])
        [(verts, polys)] = worlds(merged(floor(0, 0, 256, 256, y=0), wall))
        textures = {}
        for p in polys:
            up = len({verts[i][1] for i in p[:3]}) == 1
            textures.setdefault(up, set()).add(p[3:])
        self.assertEqual({True: {GROUND}, False: {SIDE}}, textures)

    def test_down_facing_polygons_are_not_drawn(self):
        # a ceiling would hide the level from the camera above it
        ceiling = quad_mesh([(0, 1024, 0), (256, 1024, 0), (256, 1024, 256), (0, 1024, 256)])
        self.assertEqual([], worlds(ceiling))

    def test_up_facing_polygons_are_lit_brighter_than_walls(self):
        wall = quad_mesh([(512, 0, 0), (512, 256, 0), (512, 256, 256), (512, 0, 256)])
        [(verts, polys)] = worlds(merged(floor(0, 0, 256, 256, y=0), wall))
        top = {verts[i][3] for p in polys if p[3:] == GROUND for i in p[:3]}
        side = {verts[i][3] for p in polys if p[3:] == SIDE for i in p[:3]}
        self.assertEqual(1, len(top))
        self.assertGreater(min(top)[0], max(side)[0])

    def test_split_into_several_meshes_when_over_4096(self):
        floors = [floor(0, k * 256, 256, k * 256 + 256, y=(k % 7) * 8) for k in range(250)]
        mesh = merged(*[merged(*[blendmap.Mesh([(x + i * 256, y, z) for x, y, z in f.verts], f.tris)
                                 for i in range(10)]) for f in floors])
        out = worlds(mesh)
        self.assertGreater(len(out), 1)
        for verts, polys in out:
            self.assertLessEqual(len(verts), 4096)
            self.assertLessEqual(len(polys), 4096)
            for p in polys:
                self.assertTrue(all(0 <= i < len(verts) for i in p[:3]))
        self.assertEqual(2 * 250 * 10, sum(len(polys) for _, polys in out))


if __name__ == "__main__":
    unittest.main()
