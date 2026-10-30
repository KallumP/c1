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


class ReadMtl(unittest.TestCase):
    MTL = """# Blender MTL File
newmtl floor
Kd 0.8 0.8 0.8
map_Kd textures/floor.png
newmtl wall
map_Kd -s 2 2 1 C:\maps\wall tiles.png
newmtl plain
Kd 1 0 0
"""

    def test_reads_each_materials_image_relative_to_the_mtl(self):
        images = blendmap.read_mtl(self.MTL, os.path.join("maps", "x"))
        self.assertEqual(os.path.join("maps", "x", "textures", "floor.png"), images["floor"])

    def test_options_before_the_image_are_skipped_and_absolute_paths_kept(self):
        images = blendmap.read_mtl(self.MTL, "maps")
        self.assertEqual("C:\maps\wall tiles.png", images["wall"])

    def test_materials_without_an_image_are_left_out(self):
        self.assertNotIn("plain", blendmap.read_mtl(self.MTL, "maps"))

    def test_obj_lists_its_material_libraries(self):
        mesh = blendmap.read_obj("mtllib level.mtl
v 0 0 0
", scale=1)
        self.assertEqual(["level.mtl"], mesh.mtllibs)


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
        self.assertEqual({"floor"}, set(cells.values()))

    def test_a_floor_off_the_grid_goes_to_the_nearest_cell_top(self):
        self.assertEqual(set(self.cells(floor(0, 0, 512, 256, y=512))),
                         set(self.cells(floor(0, 0, 512, 256, y=488))))
        self.assertEqual({(i, 4, k) for i in range(4) for k in range(2)},
                         set(self.cells(floor(0, 0, 512, 256, y=600))))

    def test_wall_is_solid_behind_its_face(self):
        # a wall at x 512 facing +x, 256 high and 256 along z
        wall = quad_mesh([(512, 0, 0), (512, 256, 0), (512, 256, 256), (512, 0, 256)])
        cells = self.cells(wall)
        self.assertEqual({(3, j, k) for j in range(2) for k in range(2)}, set(cells))
        self.assertEqual({"wall"}, set(cells.values()))

    def test_floor_wins_where_it_shares_a_cell_with_a_wall(self):
        wall = quad_mesh([(512, 0, 0), (512, 512, 0), (512, 512, 256), (512, 0, 256)])
        cells = self.cells(merged(wall, floor(0, 0, 512, 256, y=512)))
        self.assertEqual("floor", cells[(3, 3, 0)])
        self.assertEqual("wall", cells[(3, 2, 0)])

    def test_walls_hanging_in_the_air_are_left_out(self):
        # the game blocks crash at any wall cell whose top is above his feet, however
        # high it hangs (PlotNodeWalls in src/solid.c), so a lintel would close a doorway
        lintel = quad_mesh([(512, 1024, 0), (512, 1536, 0), (512, 1536, 256), (512, 1024, 256)])
        cells = self.cells(merged(floor(0, 0, 1024, 256, y=512), lintel))
        self.assertEqual({"floor"}, set(cells.values()))

    def test_walls_standing_on_a_floor_or_the_zones_bottom_are_kept(self):
        on_floor = quad_mesh([(512, 512, 0), (512, 1024, 0), (512, 1024, 256), (512, 512, 256)])
        on_bottom = quad_mesh([(768, 0, 0), (768, 512, 0), (768, 512, 256), (768, 0, 256)])
        cells = self.cells(merged(floor(0, 0, 512, 256, y=512), on_floor, on_bottom))
        self.assertEqual({(3, j, k) for j in (4, 5, 6, 7) for k in (0, 1)},
                         {key for key, kind in cells.items() if kind == "wall" and key[0] == 3})
        self.assertEqual({(5, j, k) for j in range(4) for k in (0, 1)},
                         {key for key, kind in cells.items() if kind == "wall" and key[0] == 5})

    def test_a_wall_beside_a_floors_edge_with_nothing_under_it_is_kept(self):
        # an outer wall: its cells are just past the floor's edge, so nothing is under them
        floor_ = floor(0, 0, 1024, 256, y=512)
        wall = quad_mesh([(0, 512, 256), (0, 1024, 256), (1024, 1024, 256), (1024, 512, 256)])  # facing -z
        cells = self.cells(merged(floor_, wall))
        self.assertEqual({(i, j, 2) for i in range(8) for j in (4, 5, 6, 7)},
                         {key for key, kind in cells.items() if kind == "wall"})

    def test_ceilings_are_not_solid(self):
        # the game never stops a jump at the octree (FindCeilY in src/solid.c), so
        # crash would jump through a ceiling and land on top of it
        ceiling = quad_mesh([(0, 1024, 0), (256, 1024, 0), (256, 1024, 256), (0, 1024, 256)])
        self.assertEqual({}, self.cells(ceiling))

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
        self.assertEqual("floor", cells[(2, 1, 0)])

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

    def test_polygons_are_sliced_into_pieces_along_x_and_y_too(self):
        # a texture covers a whole polygon, so a big one would stretch it; a wall
        # facing z isn't cut by the slices along z at all
        wall = quad_mesh([(0, 0, 512), (1024, 0, 512), (1024, 768, 512), (0, 768, 512)])
        [(verts, polys)] = worlds(wall)
        for p in polys:
            for axis in (0, 1):
                cs = [verts[i][axis] for i in p[:3]]
                self.assertEqual(min(cs) // 256, (max(cs) - 1) // 256, cs)
        self.assertAlmostEqual(1024 * 768, sum(area(verts, p) for p in polys))

    def test_x_and_y_can_be_sliced_less_often_than_z(self):
        # fewer polygons, as the sort list only needs the slices along z
        wall = quad_mesh([(0, 0, 512), (1024, 0, 512), (1024, 768, 512), (0, 768, 512)])
        [(verts, polys)] = blendmap.world_meshes(wall, 256, GROUND, SIDE, tile=512)
        widths = [max(verts[i][0] for i in p[:3]) - min(verts[i][0] for i in p[:3]) for p in polys]
        self.assertLessEqual(max(widths), 512)
        self.assertGreater(max(widths), 256)

    def test_slicing_leaves_no_cracks_along_shared_edges(self):
        # two triangles sharing a slanted edge (x = z / 2, so every cut along it is on
        # a multiple of 8): wherever a slice cuts it, both sides get the same vertex
        mesh = blendmap.Mesh([(0, 0, 0), (512, 0, 1024), (0, 0, 1024), (512, 0, 0)],
                             [blendmap.Tri((0, 2, 1), None, None), blendmap.Tri((0, 1, 3), None, None)])
        [(verts, polys)] = worlds(mesh)

        def on_edge(v):
            return v[2] == 2 * v[0]

        sides = [set(), set()]
        for p in polys:
            left = sum(2 * verts[i][0] for i in p[:3]) < sum(verts[i][2] for i in p[:3])  # centre left of the edge
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
            self.assertLessEqual(len(verts) + len(polys), blendmap.WGEO_ITEMS_MAX)  # fits in a page
            for p in polys:
                self.assertTrue(all(0 <= i < len(verts) for i in p[:3]))
        self.assertEqual(2 * 250 * 10, sum(len(polys) for _, polys in out))


def moved(mesh, dx, dy, dz):
    return blendmap.Mesh([(x + dx, y + dy, z + dz) for x, y, z in mesh.verts], mesh.tris)


def cube(x, y, z, r, obj):
    """a small closed cube centred on (x, y, z)"""
    m = merged(floor(-r, -r, r, r, y=r), quad_mesh([(-r, -r, -r), (r, -r, -r), (r, -r, r), (-r, -r, r)]))
    m = blendmap.Mesh(m.verts, [blendmap.Tri(t.verts, obj, None) for t in m.tris])
    return moved(m, x, y, z)


class Spawn(unittest.TestCase):
    SIZE = (2048, 2048, 4096)

    def test_spawn_object_puts_crash_on_the_ground_below_it(self):
        mesh = merged(floor(0, 0, 2048, 4096, y=512), cube(1000, 900, 3000, 32, "Spawn"))
        cells = blendmap.solid_cells(mesh, self.SIZE, 128)
        self.assertEqual((1000, 512, 3000), blendmap.spawn(mesh, cells, self.SIZE, 128))

    def test_spawn_object_is_not_drawn_or_solid(self):
        marker = cube(1000, 900, 3000, 32, "spawn")
        self.assertEqual({}, blendmap.solid_cells(marker, self.SIZE, 128))
        self.assertEqual([], worlds(marker))

    def test_without_a_spawn_object_crash_starts_on_the_ground_nearest_the_start(self):
        # the route runs along -z, so the start is the +z end; nearest the middle across
        mesh = merged(floor(0, 0, 2048, 2048, y=256), floor(1536, 2048, 2048, 2560, y=512))
        cells = blendmap.solid_cells(mesh, self.SIZE, 128)
        self.assertEqual((1536 + 64, 512, 2560 - 64), blendmap.spawn(mesh, cells, self.SIZE, 128))

    def test_middle_across_is_the_middle_of_the_floors_not_of_the_zone(self):
        mesh = floor(0, 0, 768, 2048, y=256)  # the zone is 2048 wide
        cells = blendmap.solid_cells(mesh, self.SIZE, 128)
        x, y, z = blendmap.spawn(mesh, cells, self.SIZE, 128)
        self.assertIn(x, (320, 448))  # either column next to 384

    def test_crash_starts_on_a_floor_not_on_top_of_a_wall(self):
        # a wall across the +z end, nearest the start, whose top is solid with room above
        wall = quad_mesh([(0, 0, 2048), (0, 1024, 2048), (2048, 1024, 2048), (2048, 0, 2048)])
        mesh = merged(floor(0, 0, 2048, 2048, y=256), wall)
        cells = blendmap.solid_cells(mesh, self.SIZE, 128)
        x, y, z = blendmap.spawn(mesh, cells, self.SIZE, 128)
        self.assertEqual(256, y)
        self.assertLess(z, 2048)

    def test_no_ground_is_an_error(self):
        with self.assertRaises(ValueError):
            blendmap.spawn(blendmap.Mesh([], []), {}, self.SIZE, 128)


class CameraPath(unittest.TestCase):
    SIZE = (2048, 4096, 8192)

    def path(self, mesh, start, step=256):
        cells = blendmap.solid_cells(mesh, self.SIZE, 128)
        return blendmap.camera_path(cells, self.SIZE, 128, start, step)

    def test_height_ignores_the_tops_of_walls(self):
        # a low wall running along z under crash's x: its top isn't somewhere to stand
        wall = quad_mesh([(1024, 0, 0), (1024, 1024, 0), (1024, 1024, 8192), (1024, 0, 8192)])
        points = self.path(merged(floor(0, 0, 2048, 8192, y=512), wall), (960, 512, 5000))
        self.assertEqual({512 + blendmap.CAM_OFFSET[1]}, {y for _, y, _ in points})

    def test_follows_crash_from_behind_along_minus_z(self):
        points = self.path(floor(0, 0, 2048, 8192, y=512), (1024, 512, 5000))
        lead, (dx, dy) = blendmap.CAM_LEAD, blendmap.CAM_OFFSET
        self.assertEqual((1024 + dx, 512 + dy, 5000 + lead), points[0])
        self.assertEqual([-256] * (len(points) - 1), [b[2] - a[2] for a, b in zip(points, points[1:])])
        self.assertGreater(points[-1][2], 0)
        self.assertLessEqual(points[-1][2], 256 + 200)

    def test_starts_inside_the_zone(self):
        points = self.path(floor(0, 0, 2048, 8192, y=512), (1024, 512, 8000))
        self.assertLessEqual(points[0][2], 8192 - 200)

    def test_height_follows_the_ground_ahead_of_the_camera(self):
        mesh = merged(floor(0, 4096, 2048, 8192, y=512), floor(0, 0, 2048, 4096, y=1024))
        points = self.path(mesh, (1024, 512, 6000))
        for x, y, z in points:
            ground = 1024 if z - blendmap.CAM_LEAD < 4096 else 512
            self.assertEqual(ground + blendmap.CAM_OFFSET[1], y, z)

    def test_height_is_kept_over_a_gap(self):
        mesh = merged(floor(0, 4096, 2048, 8192, y=512), floor(0, 0, 2048, 2048, y=1024))
        heights = {z: y for x, y, z in self.path(mesh, (1024, 512, 6000))}
        z = next(z for z in heights if 2048 <= z - blendmap.CAM_LEAD < 4096)
        self.assertEqual(512 + blendmap.CAM_OFFSET[1], heights[z])

    def test_picks_the_ground_nearest_the_last_height(self):
        upper = floor(0, 0, 2048, 8192, y=2048)  # an upper floor over the whole route
        points = self.path(merged(floor(0, 0, 2048, 8192, y=512), upper), (1024, 512, 5000))
        self.assertEqual({512 + blendmap.CAM_OFFSET[1]}, {y for _, y, _ in points})


if __name__ == "__main__":
    unittest.main()
