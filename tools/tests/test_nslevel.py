"""
tests for tools/nslevel.py

run from the project root: python -m unittest discover -s tools/tests
"""
import os
import struct
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TOOLS)
import nslevel  # noqa: E402

STREAMS = os.path.join(TOOLS, "..", "streams")
EID_WILLC = nslevel.str_to_eid("WillC")


def make_entry(eid, etype, items):
    """an entry: header, item offsets (relative to the entry), then the items"""
    offset = 16 + 4 * (len(items) + 1)
    offsets = []
    for item in items:
        offsets.append(offset)
        offset += len(item)
    offsets.append(offset)
    data = struct.pack("<IIii", nslevel.MAGIC_ENTRY, eid, etype, len(items))
    data += struct.pack("<%dI" % len(offsets), *offsets)
    return data + b"".join(items)


def make_page(pgid, entries):
    """a normal (type 0) page holding entries, padded to 64 KB"""
    offset = 16 + 4 * (len(entries) + 1)
    offsets = []
    for e in entries:
        offsets.append(offset)
        offset += len(e)
    offsets.append(offset)
    data = struct.pack("<HHIII", nslevel.MAGIC_PAGE, 0, pgid, len(entries), 0)
    data += struct.pack("<%dI" % len(offsets), *offsets) + b"".join(entries)
    return data.ljust(nslevel.PAGE_SIZE, b"\0")


def make_texture_page(eid):
    data = struct.pack("<HHIII", nslevel.MAGIC_PAGE, 1, eid, 5, 0)
    return data.ljust(nslevel.PAGE_SIZE, b"\x55")


def make_nsd(page_table, lid, zone_spawn, exec_map, pages_offset=0):
    """an nsd: page table (pgid, eid pairs, all in bucket 0) and the ldat"""
    data = struct.pack("<256I", *([0] * 256))
    data += struct.pack("<iIIiIIIi", 1, len(page_table), 0, 0, 0, 0, pages_offset, 0)
    data += struct.pack("<64I", *([0] * 64))
    for pgid, eid in page_table:
        data += struct.pack("<II", pgid, eid)
    exec_map = exec_map + [nslevel.EID_NONE] * (64 - len(exec_map))
    data += struct.pack("<IIIiI", 1, lid, zone_spawn, 2, 0)
    data += struct.pack("<64I", *exec_map)
    data += struct.pack("<I", 0x1400) + b"\0" * 0xF5F8
    return data


class EidNames(unittest.TestCase):
    def test_eid_name_round_trips(self):
        self.assertEqual("WillC", nslevel.eid_to_str(nslevel.str_to_eid("WillC")))

    def test_eids_are_odd(self):
        self.assertEqual(1, nslevel.str_to_eid("WillC") & 1)

    def test_none_eid_is_none_(self):
        self.assertEqual("NONE!", nslevel.eid_to_str(nslevel.EID_NONE))


class ReadNsd(unittest.TestCase):
    def test_reads_page_table_and_ldat(self):
        zone = nslevel.str_to_eid("a5_9Z")
        nsd = nslevel.read_nsd(make_nsd([(1, EID_WILLC), (3, zone)], 9, zone, [EID_WILLC]))
        self.assertEqual(1, nsd.page_count)
        self.assertEqual([(1, EID_WILLC), (3, zone)], nsd.page_table)
        self.assertEqual(9, nsd.ldat.lid)
        self.assertEqual(zone, nsd.ldat.zone_spawn)
        self.assertEqual(2, nsd.ldat.path_idx_spawn)
        self.assertEqual(EID_WILLC, nsd.ldat.exec_map[0])
        self.assertEqual(nslevel.EID_NONE, nsd.ldat.exec_map[1])


class ReadPages(unittest.TestCase):
    def test_reads_entries_and_their_items(self):
        entry = make_entry(EID_WILLC, 11, [b"head", b"code!!"])
        pages = nslevel.read_pages(make_page(1, [entry]), page_count=1)
        self.assertEqual(1, len(pages))
        self.assertEqual(0, pages[0].type)
        e = pages[0].entries[0]
        self.assertEqual(EID_WILLC, e.eid)
        self.assertEqual(11, e.type)
        self.assertEqual([b"head", b"code!!"], e.items)

    def test_reads_several_entries_in_a_page(self):
        a = make_entry(nslevel.str_to_eid("AaaaA"), 7, [b"1"])
        b = make_entry(nslevel.str_to_eid("BbbbB"), 3, [b"22", b"333"])
        page = nslevel.read_pages(make_page(1, [a, b]), page_count=1)[0]
        self.assertEqual(["AaaaA", "BbbbB"], [nslevel.eid_to_str(e.eid) for e in page.entries])
        self.assertEqual([b"22", b"333"], page.entries[1].items)

    def test_texture_page_keeps_its_eid_and_data(self):
        tpag = nslevel.str_to_eid("TexP1")
        page = nslevel.read_pages(make_texture_page(tpag), page_count=1)[0]
        self.assertEqual(1, page.type)
        self.assertEqual(tpag, page.eid)
        self.assertEqual(nslevel.PAGE_SIZE, len(page.data))
        self.assertEqual([], page.entries)

    def test_pages_start_at_pages_offset(self):
        entry = make_entry(EID_WILLC, 11, [b"x"])
        nsf = b"\xEE" * (2 * nslevel.SECTOR_SIZE) + make_page(1, [entry])
        pages = nslevel.read_pages(nsf, page_count=1, pages_offset=2)
        self.assertEqual(EID_WILLC, pages[0].entries[0].eid)


class Summary(unittest.TestCase):
    def test_counts_entries_by_type_name(self):
        pages = [
            nslevel.read_pages(make_page(1, [make_entry(EID_WILLC, 11, [b"x"]),
                                             make_entry(nslevel.str_to_eid("a5_9Z"), 7, [b"z"])]),
                               page_count=1)[0],
            nslevel.read_pages(make_texture_page(nslevel.str_to_eid("TexP1")), page_count=1)[0],
        ]
        self.assertEqual({"GOOL": 1, "ZDAT": 1, "TPAG": 1}, nslevel.count_by_type(pages))


def probe(nsd, eid):
    """find eid in the page table the way NSProbe does: scan from its bucket"""
    i = nsd.ptb_offsets[(eid >> 15) & 0xFF]
    while nsd.page_table[i][1] != eid:
        i += 1
    return nsd.page_table[i][0]


def small_level():
    zone = nslevel.str_to_eid("a5_9Z")
    tpag = nslevel.str_to_eid("TexP1")
    pages = [
        nslevel.read_pages(make_page(1, [make_entry(zone, 7, [b"zone", b"rect"]),
                                         make_entry(EID_WILLC, 11, [b"code"])]), page_count=1)[0],
        nslevel.read_pages(make_texture_page(tpag), page_count=1)[0],
    ]
    nsd = nslevel.read_nsd(make_nsd([], 9, zone, [EID_WILLC]))
    return nslevel.Level(nsd, pages)


class WriteLevel(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(TOOLS, "..", "build", "test_custom_levels")
        os.makedirs(self.dir, exist_ok=True)

    def test_written_level_reads_back_the_same(self):
        level = small_level()
        nslevel.write_level(level, self.dir, "small")
        back = nslevel.read_level_files(os.path.join(self.dir, "small"))
        self.assertEqual(2, back.nsd.page_count)
        self.assertEqual(0, back.nsd.pages_offset)
        self.assertEqual(9, back.nsd.ldat.lid)
        self.assertEqual(level.nsd.ldat.zone_spawn, back.nsd.ldat.zone_spawn)
        self.assertEqual(level.nsd.ldat.exec_map, back.nsd.ldat.exec_map)
        self.assertEqual([[(e.eid, e.type, e.items) for e in p.entries] for p in level.pages],
                         [[(e.eid, e.type, e.items) for e in p.entries] for p in back.pages])
        self.assertEqual(level.pages[1].data, back.pages[1].data)

    def test_page_table_finds_every_entry_by_bucket(self):
        level = small_level()
        nslevel.write_level(level, self.dir, "small")
        nsd = nslevel.read_level_files(os.path.join(self.dir, "small")).nsd
        self.assertEqual(0 << 1 | 1, probe(nsd, EID_WILLC))
        self.assertEqual(0 << 1 | 1, probe(nsd, nslevel.str_to_eid("a5_9Z")))
        self.assertEqual(1 << 1 | 1, probe(nsd, nslevel.str_to_eid("TexP1")))

    def test_too_many_entries_for_a_page_is_an_error(self):
        big = nslevel.Entry(EID_WILLC, 11, [b"\0" * nslevel.PAGE_SIZE])
        with self.assertRaises(ValueError):
            nslevel.entry_page_bytes([big], 0)


def entry_page(entries):
    return nslevel.Page(nslevel.PAGE_ENTRIES, entries=entries)


def words(*eids):
    return struct.pack("<%dI" % len(eids), *eids)


class CutLevel(unittest.TestCase):
    """a level where WillC uses a model, which uses a texture page; a zone
    uses its own world mesh; nothing uses the beach object"""
    def setUp(self):
        self.willc = EID_WILLC
        self.model = nslevel.str_to_eid("Mdl0G")
        self.tex = nslevel.str_to_eid("TexP1")
        self.zone = nslevel.str_to_eid("a5_9Z")
        self.world = nslevel.str_to_eid("a5_9W")
        self.beach = nslevel.str_to_eid("BeaOC")
        pages = [
            entry_page([nslevel.Entry(self.willc, 11, [b"head", words(0x10, self.model)]),
                        nslevel.Entry(self.model, 2, [words(self.tex, 7)])]),
            entry_page([nslevel.Entry(self.zone, 7, [words(self.world)]),
                        nslevel.Entry(self.world, 3, [b"mesh"]),
                        nslevel.Entry(self.beach, 11, [b"beach"])]),
            nslevel.Page(nslevel.PAGE_TEXTURE, eid=self.tex, data=make_texture_page(self.tex)),
        ]
        nsd = nslevel.read_nsd(make_nsd([], 9, self.zone, [self.willc, self.beach]))
        self.level = nslevel.Level(nsd, pages)

    def eids(self, level):
        found = {e.eid for p in level.pages for e in p.entries}
        return found | {p.eid for p in level.pages if p.type == nslevel.PAGE_TEXTURE}

    def test_references_are_eids_in_an_entrys_items(self):
        entry = nslevel.Entry(self.willc, 11, [b"head", words(0x10, self.model, self.zone)])
        self.assertEqual({self.model, self.zone},
                         nslevel.references(entry, {self.model, self.zone, self.beach}))

    def test_keeps_what_the_kept_executables_use_and_drops_the_rest(self):
        cut = nslevel.cut_level(self.level, [self.willc])
        self.assertEqual({self.willc, self.model, self.tex}, self.eids(cut))

    def test_exec_map_keeps_only_kept_executables(self):
        cut = nslevel.cut_level(self.level, [self.willc])
        self.assertEqual(self.willc, cut.nsd.ldat.exec_map[0])
        self.assertEqual(nslevel.EID_NONE, cut.nsd.ldat.exec_map[1])

    def test_kept_entries_are_packed_into_fewer_pages(self):
        cut = nslevel.cut_level(self.level, [self.willc])
        self.assertEqual(2, len(cut.pages))  # one entry page, one texture page

    def test_packed_pages_list_entries_in_bucket_order(self):
        # NSPageUpdateEntries scans the page table forward from the bucket of
        # a page's first entry to find the rest, so a page's entries have to
        # be in bucket order
        eids = [nslevel.str_to_eid(n) for n in ("zzzzZ", "aaaaA", "MMMMM", "00000")]
        pages = nslevel.pack_entries([nslevel.Entry(e, 1, [b"x"]) for e in eids])
        buckets = [nslevel.eid_bucket(e.eid) for e in pages[0].entries]
        self.assertEqual(sorted(buckets), buckets)
        self.assertEqual(set(eids), {e.eid for e in pages[0].entries})

    def test_packing_starts_a_new_page_when_one_is_full(self):
        big = [nslevel.Entry(nslevel.str_to_eid("Big%02d" % i), 1, [b"\0" * 40000])
               for i in range(3)]
        pages = nslevel.pack_entries(big)
        self.assertEqual(3, len(pages))
        self.assertEqual(big, [e for p in pages for e in p.entries])


def octree_leaves(rect):
    """(level, y offset as a fraction of the zone height, leaf value) for
    each solid leaf of a zone's octree, walked the way ZoneQueryOctreeR does"""
    root, mdx, mdy, mdz = struct.unpack_from("<4H", rect, 28)
    leaves = []

    def walk(node, level, y, height):
        if node == 0:
            return
        if node & 1:
            leaves.append((level, y, node >> 1))
            return
        fx, fy, fz = level < mdx, level < mdy, level < mdz
        children = struct.unpack_from("<%dH" % ((1 + fx) * (1 + fy) * (1 + fz)), rect, node)
        idx = 0
        for i in range(1 + fx):
            for j in range(1 + fy):
                for k in range(1 + fz):
                    sub = height / 2 if fy else height
                    walk(children[idx], level + 1, y + (sub if j else 0), sub)
                    idx += 1
    walk(root, 0, 0.0, 1.0)
    return leaves


class Zone(unittest.TestCase):
    def test_floor_octree_is_solid_ground_along_the_bottom(self):
        rect = nslevel.floor_rect_bytes(100, 200, 300, 4096, 2048, 4096, depth=3)
        self.assertEqual((100, 200, 300, 4096, 2048, 4096),
                         struct.unpack_from("<iiiIII", rect, 0))
        leaves = octree_leaves(rect)
        self.assertTrue(leaves)
        self.assertEqual({(0.0, 0)}, {(y, value) for _, y, value in leaves})  # bottom, plain ground

    def test_floor_cells_are_small_enough_to_query(self):
        # ZoneQueryOctree stores a cell's position relative to the query as
        # int16 (>> 4), so cells have to be within about 2047 zone units
        rect = nslevel.floor_rect_bytes(0, 0, 0, 4801, 3200, 6563, depth=3)
        _, mdx, mdy, mdz = struct.unpack_from("<4H", rect, 28)
        self.assertLessEqual(4801 >> mdx, nslevel.FLOOR_CELL_MAX)
        self.assertLessEqual(6563 >> mdz, nslevel.FLOOR_CELL_MAX)
        self.assertEqual(3, mdy)
        self.assertEqual(2 ** (mdx + mdz), len(octree_leaves(rect)))

    def test_floor_top_is_a_fraction_of_the_height(self):
        self.assertEqual(256, nslevel.floor_top(2048, depth=3))

    def test_zone_header_fields(self):
        template = bytearray(nslevel.ZONE_HEADER_SIZE)
        world = nslevel.str_to_eid("Flr0W")
        self_eid = nslevel.str_to_eid("Flr0Z")
        h = nslevel.zone_header_bytes(bytes(template), self_eid, [(world, (1, 2, 3))],
                                      path_count=1, entity_count=1)
        self.assertEqual(1, struct.unpack_from("<I", h, 0)[0])
        self.assertEqual((world, 1, 2, 3), struct.unpack_from("<I3i", h, 4))
        self.assertEqual((2, 1, 1, 1), struct.unpack_from("<4I", h, nslevel.ZONE_PATHS_IDX))
        self.assertEqual(self_eid, struct.unpack_from("<I", h, nslevel.ZONE_NEIGHBORS)[0])
        self.assertEqual((0, 0), struct.unpack_from("<ii", h, nslevel.ZONE_LOADLIST))
        self.assertEqual(nslevel.EID_NONE, struct.unpack_from("<I", h, nslevel.ZONE_MIDI)[0])

    def test_load_list_opens_every_texture_page(self):
        # a zone's texture pages are only put in vram when its load list
        # opens them (LevelUpdate, NSPageOpen)
        zone_eid = nslevel.str_to_eid("Flr0Z")
        zone = nslevel.Entry(zone_eid, 7, [nslevel.zone_header_bytes(
            bytes(nslevel.ZONE_HEADER_SIZE), zone_eid, [], path_count=0, entity_count=0)])
        pages = [entry_page([zone]),
                 nslevel.Page(nslevel.PAGE_TEXTURE, eid=1),
                 entry_page([]),
                 nslevel.Page(nslevel.PAGE_TEXTURE, eid=3)]
        level = nslevel.Level(None, pages)
        nslevel.load_texture_pages(level, zone_eid)
        entries, count = struct.unpack_from("<ii", zone.items[0], nslevel.ZONE_LOADLIST)
        pgids = struct.unpack_from("<2I", zone.items[0], nslevel.ZONE_LOADLIST + 8 + 32)
        self.assertEqual((0, 2), (entries, count))
        self.assertEqual((nslevel.pgid(1), nslevel.pgid(3)), pgids)

    def test_path_without_neighbors(self):
        points = [(10, 20, 30, 0, 0, 0), (40, 50, 60, 0, 0, 0)]
        slst = nslevel.str_to_eid("Flr0S")
        p = nslevel.path_bytes(slst, points, cam_mode=5, zoom=1700, avg_node_dist=400)
        self.assertEqual((slst, 0, 0), struct.unpack_from("<III", p, 0))
        self.assertEqual(2, struct.unpack_from("<H", p, 30)[0])  # length
        self.assertEqual(5, struct.unpack_from("<H", p, 32)[0])  # cam mode
        self.assertEqual(points, [struct.unpack_from("<6h", p, 50 + 12 * i) for i in range(2)])
        self.assertEqual(0, len(p) % 4)


def octree_cells(rect):
    """solid leaves of a zone's octree as (x, y, z, w, h, d, value) in zone
    units relative to the zone, walked the way ZoneQueryOctreeR does"""
    _, _, _, zw, zh, zd = struct.unpack_from("<iiiIII", rect, 0)
    root, mdx, mdy, mdz = struct.unpack_from("<4H", rect, 28)
    cells = []

    def walk(node, level, x, y, z, w, h, d):
        if node == 0:
            return
        if node & 1:
            cells.append((x, y, z, w, h, d, node >> 1))
            return
        fx, fy, fz = level < mdx, level < mdy, level < mdz
        sw, sh, sd = (w // 2 if fx else w), (h // 2 if fy else h), (d // 2 if fz else d)
        children = struct.unpack_from("<%dH" % ((1 + fx) * (1 + fy) * (1 + fz)), rect, node)
        idx = 0
        for i in range(1 + fx):
            for j in range(1 + fy):
                for k in range(1 + fz):
                    walk(children[idx], level + 1, x + i * sw, y + j * sh, z + k * sd, sw, sh, sd)
                    idx += 1
    walk(root, 0, 0, 0, 0, zw, zh, zd)
    return cells


def grid_cells(cells, cell):
    """the cell sized grid squares that solid leaves cover"""
    out = set()
    for x, y, z, w, h, d, _ in cells:
        for i in range(x, x + w, cell):
            for j in range(y, y + h, cell):
                for k in range(z, z + d, cell):
                    out.add((i, j, k))
    return out


def block_cells(blocks, cell):
    out = set()
    for x0, y0, z0, x1, y1, z1 in blocks:
        for i in range(x0, x1, cell):
            for j in range(y0, y1, cell):
                for k in range(z0, z1, cell):
                    out.add((i, j, k))
    return out


class BlockOctree(unittest.TestCase):
    SIZE = (2048, 1024, 4096)
    BLOCKS = [(0, 0, 0, 2048, 256, 1024),        # ground at the start
              (0, 0, 1536, 2048, 256, 4096),     # ground after a gap
              (512, 256, 2048, 1024, 512, 2560)]  # a step on it

    def test_solid_cells_are_exactly_the_blocks(self):
        rect = nslevel.blocks_rect_bytes((10, 20, 30), self.SIZE, self.BLOCKS, cell=128)
        self.assertEqual((10, 20, 30) + self.SIZE, struct.unpack_from("<iiiIII", rect, 0))
        cells = octree_cells(rect)
        self.assertEqual(block_cells(self.BLOCKS, 128), grid_cells(cells, 128))
        self.assertEqual({0}, {c[6] for c in cells})  # plain ground

    def test_solid_leaves_are_small_enough_to_query(self):
        rect = nslevel.blocks_rect_bytes((0, 0, 0), self.SIZE, self.BLOCKS, cell=128)
        for x, y, z, w, h, d, _ in octree_cells(rect):
            self.assertLessEqual(w, nslevel.FLOOR_CELL_MAX)
            self.assertLessEqual(d, nslevel.FLOOR_CELL_MAX)

    def test_identical_parts_are_shared_so_it_stays_small(self):
        big = (4096, 4096, 8192)
        rect = nslevel.blocks_rect_bytes((0, 0, 0), big, [(0, 0, 0, 4096, 384, 8192)], cell=128)
        self.assertLess(len(rect), 4096)

    def test_blocks_can_have_their_own_leaf_value(self):
        pit = (0, 0, 1024, 2048, 128, 1536, nslevel.LEAF_PIT)
        rect = nslevel.blocks_rect_bytes((0, 0, 0), self.SIZE, self.BLOCKS + [pit], cell=128)
        cells = octree_cells(rect)
        pit_cells = {c for c in grid_cells([c for c in cells if c[6] == nslevel.LEAF_PIT >> 1], 128)}
        self.assertEqual(block_cells([pit[:6]], 128), pit_cells)
        self.assertEqual(11, ((nslevel.LEAF_PIT & 0x3F0) >> 4))  # subtype 11: fall kill (ProcessNode)

    def test_blocks_must_be_on_the_grid(self):
        with self.assertRaises(ValueError):
            nslevel.blocks_rect_bytes((0, 0, 0), self.SIZE, [(0, 0, 0, 100, 128, 128)], cell=128)


class BlockMesh(unittest.TestCase):
    TOP, SIDE = (593, 0), (110, 2)
    BLOCK = (0, 0, 0, 512, 256, 768)

    def mesh(self):
        return nslevel.blocks_mesh([self.BLOCK], self.TOP, self.SIDE, piece=256)

    def test_top_is_split_into_pieces(self):
        verts, polys = self.mesh()
        tops = [p for p in polys if p[3:] == self.TOP]
        self.assertEqual(2 * 3 * 2, len(tops))  # 2x3 squares, 2 triangles each
        self.assertEqual({256}, {verts[i][1] for p in tops for i in p[:3]})

    def test_sides_use_the_side_texture_and_span_the_height(self):
        verts, polys = self.mesh()
        sides = [p for p in polys if p[3:] == self.SIDE]
        # x sides are 3 pieces long, z sides 2; one piece high; 2 triangles each
        self.assertEqual(2 * (3 + 3 + 2 + 2), len(sides))
        self.assertEqual({0, 256}, {verts[i][1] for p in sides for i in p[:3]})

    def test_every_vertex_is_on_the_block(self):
        verts, _ = self.mesh()
        for x, y, z in verts:
            self.assertTrue(0 <= x <= 512 and 0 <= y <= 256 and 0 <= z <= 768)

    def test_too_many_vertices_is_an_error(self):
        with self.assertRaises(ValueError):
            nslevel.blocks_mesh([(0, 0, 0, 8192, 128, 8192)], self.TOP, self.SIDE, piece=64)


def entity(type, subtype, id, points):
    """an entity as stored in a zone: parent zone, spawn flags, group, id,
    point count, 3 init flags, type, subtype, then the points (units of 4)"""
    data = struct.pack("<IHHHHhhhBB", 0, 0x18, 3, id, len(points), 1, 2, 3, type, subtype)
    for p in points:
        data += struct.pack("<3h", *p)
    return nslevel.pad4(data)


class Entities(unittest.TestCase):
    def test_placed_entity_has_the_new_id_and_first_point(self):
        crab = entity(31, 0, 14, [(100, 50, 200), (110, 50, 200), (120, 50, 210)])
        placed = nslevel.place_entity(crab, 42, (400, 128, 800))
        self.assertEqual(42, struct.unpack_from("<H", placed, 8)[0])
        points = [struct.unpack_from("<3h", placed, 20 + 6 * i) for i in range(3)]
        self.assertEqual([(100, 32, 200), (110, 32, 210), (120, 32, 220)][0], points[0])

    def test_placed_entity_keeps_its_path_shape(self):
        crab = entity(31, 0, 14, [(100, 50, 200), (110, 50, 200), (120, 50, 210)])
        placed = nslevel.place_entity(crab, 42, (400, 128, 800))
        points = [struct.unpack_from("<3h", placed, 20 + 6 * i) for i in range(3)]
        self.assertEqual([(100, 32, 200), (110, 32, 200), (120, 32, 210)], points)

    def test_placed_entity_keeps_everything_else(self):
        box = entity(34, 6, 6, [(1, 2, 3)])
        placed = nslevel.place_entity(box, 7, (0, 0, 0))
        self.assertEqual(box[:4] + box[6:8] + box[10:20], placed[:4] + placed[6:8] + placed[10:20])

    def test_placed_entity_uses_plain_lighting(self):
        # spawn_flags >> 3 picks a lighting region in the zone's octree
        # (ZoneColorsScaleSeekByEntityNode); a copy points at the plain one
        # crash uses (0x18), keeping the low 3 bits
        box = bytearray(entity(34, 6, 6, [(1, 2, 3)]))
        struct.pack_into("<H", box, 4, 0x1a19)
        placed = nslevel.place_entity(bytes(box), 7, (0, 0, 0))
        self.assertEqual(0x19, struct.unpack_from("<H", placed, 4)[0])

    def test_entity_type_and_subtype(self):
        self.assertEqual((34, 6), nslevel.entity_type(entity(34, 6, 1, [(0, 0, 0)])))


def decode_vertex(data):
    """(x, y, z, r, g, b) the way SwTransformWorlds reads a wgeo vertex"""
    def sx(v, bits):
        return v - (1 << bits) if v & (1 << (bits - 1)) else v
    r, g, b, z8, h0, h1 = struct.unpack("<BBBBHH", data)
    x = sx(h0 >> 3, 13)
    z2 = (h0 >> 1) & 3
    y = sx(h1 >> 3, 13)
    z3 = sx(h1 & 7, 3)
    return (x * 8, y * 8, (z8 + (z2 << 8) + (z3 << 10)) * 8, r, g, b)


def decode_polygon(data):
    """(a, b, c, tinf, tpag) of a wgeo polygon"""
    w0, w1 = struct.unpack("<II", data)
    return (w1 >> 20, (w1 >> 8) & 0xFFF, w0 >> 20, (w0 >> 8) & 0xFFF, (w0 >> 5) & 7)


class World(unittest.TestCase):
    def test_vertex_round_trips(self):
        for v in [(0, 0, 0), (4088, -800, 8184), (-32768, 32760, -8192)]:
            data = nslevel.world_vertex_bytes(*v, color=(1, 2, 3))
            self.assertEqual(v + (1, 2, 3), decode_vertex(data))

    def test_polygon_round_trips(self):
        data = nslevel.world_polygon_bytes(1, 2, 4095, tinf=593, tpag=3)
        self.assertEqual((1, 2, 4095, 593, 3), decode_polygon(data))

    def test_floor_grid_covers_the_area_in_two_triangles_per_cell(self):
        verts, polys = nslevel.floor_grid(1024, 2048, cell=512)
        self.assertEqual(3 * 5, len(verts))
        self.assertEqual(2 * 2 * 4, len(polys))
        self.assertEqual({0}, {v[1] for v in verts})
        self.assertEqual((0, 1024), (min(v[0] for v in verts), max(v[0] for v in verts)))
        self.assertEqual((0, 2048), (min(v[2] for v in verts), max(v[2] for v in verts)))

    def test_world_header_keeps_the_templates_textures(self):
        template = struct.pack("<iiiIIIII", 1, 2, 3, 99, 99, 2, 1, 0)
        template += struct.pack("<8I", nslevel.str_to_eid("Ju89T"), *([0] * 7)) + b"TEX!TEX?"
        header = nslevel.world_header_bytes(template, (10, 20, 30), poly_count=4, vert_count=5)
        self.assertEqual((10, 20, 30, 4, 5, 2, 1, 0), struct.unpack_from("<iiiIIIII", header, 0))
        self.assertEqual(template[32:], header[32:])


def slst_list(item):
    length, type = struct.unpack_from("<HH", item, 0)
    return type, list(struct.unpack_from("<%dH" % length, item, 4))


class SortList(unittest.TestCase):
    # three polygons whose far edges (towards +z) are at z 100, 500 and 900;
    # the camera moves along -z from 1000 to 600 in steps of 200
    POLY_ZMAX = [100, 500, 900]
    CAM_ZS = [1000, 800, 600]

    def test_one_full_list_per_point_and_one_more_for_the_last(self):
        items = nslevel.slst_items([self.POLY_ZMAX], self.CAM_ZS, step=200, near=50)
        self.assertEqual(len(self.CAM_ZS) + 1, len(items))
        self.assertEqual({0}, {slst_list(item)[0] for item in items})  # copied as is, either way

    def test_each_point_lists_only_polygons_in_front_of_the_camera(self):
        # in front for the whole step to the next point: zmax < cam z - step - near
        items = nslevel.slst_items([self.POLY_ZMAX], self.CAM_ZS, step=200, near=50)
        ids = [nslevel.poly_id(0, i) for i in range(3)]
        self.assertEqual(ids[:2], slst_list(items[0])[1])  # under 1000-250: 100 and 500
        self.assertEqual(ids[:2], slst_list(items[1])[1])  # under 800-250: 100 and 500
        self.assertEqual(ids[:1], slst_list(items[2])[1])  # under 600-250: 100
        self.assertEqual(slst_list(items[2]), slst_list(items[3]))  # last point again

    def test_lists_polygons_of_every_world_mesh(self):
        items = nslevel.slst_items([[100, 900], [200]], [1000], step=200, near=50)
        self.assertEqual([nslevel.poly_id(0, 0), nslevel.poly_id(1, 0)], slst_list(items[0])[1])

    def test_more_polygons_than_the_game_can_list_is_an_error(self):
        # the game's lists hold at most 1460 polygons (SlstInit in src/slst.c)
        with self.assertRaises(ValueError):
            nslevel.slst_items([[0] * 1461], [1000], step=200, near=50)
        nslevel.slst_items([[0] * 1460], [1000], step=200, near=50)

    def test_poly_id_layout(self):
        self.assertEqual((2 << 12) | 7, nslevel.poly_id(2, 7))


@unittest.skipUnless(os.path.exists(os.path.join(STREAMS, "s0000009.nsd")),
                     "needs N. Sanity Beach in streams/")
class RealLevel(unittest.TestCase):
    def test_course_has_its_objects_and_their_code(self):
        course = nslevel.make_course(nslevel.read_level(STREAMS, 9))
        entries = {e.eid: e for p in course.pages for e in p.entries}
        zone = entries[course.nsd.ldat.zone_spawn]
        header = zone.items[0]
        paths_idx, path_count, entity_count, _ = struct.unpack_from("<4I", header, nslevel.ZONE_PATHS_IDX)
        kinds = [nslevel.entity_type(e) for e in zone.items[paths_idx + path_count:]]
        self.assertEqual(entity_count, len(kinds))
        self.assertEqual((0, 0), kinds[0])  # crash first
        self.assertEqual(len(nslevel.COURSE_BOXES) + 1, sum(1 for k in kinds if k[0] == 34))
        self.assertEqual(len(nslevel.COURSE_CRABS), kinds.count((31, 0)))
        self.assertEqual(1, kinds.count((32, 1)))
        execs = {nslevel.eid_to_str(e) for e in course.nsd.ldat.exec_map if e != nslevel.EID_NONE}
        self.assertTrue({"WillC", "CrabC", "WarpC", "BoxsC"} <= execs, execs)
        textures = [p for p in course.pages if p.type == nslevel.PAGE_TEXTURE]
        self.assertEqual(len(textures), struct.unpack_from("<i", header, nslevel.ZONE_LOADLIST + 4)[0])

    def test_mock_level_is_one_zone_with_a_floor_and_crash(self):
        mock = nslevel.make_mock(nslevel.read_level(STREAMS, 9))
        self.assertEqual(nslevel.LID_TEST, mock.nsd.ldat.lid)
        entries = {e.eid: e for p in mock.pages for e in p.entries}
        zone = entries[mock.nsd.ldat.zone_spawn]
        self.assertEqual(4, len(zone.items))  # header, bounds, path, crash
        counts = nslevel.count_by_type(mock.pages)
        self.assertEqual(1, counts["ZDAT"])
        self.assertEqual(1, counts["WGEO"])
        self.assertEqual(1, counts["SLST"])
        self.assertNotIn("MIDI", counts)

    def test_cut_n_sanity_beach_keeps_crash_and_the_hud_only(self):
        level = nslevel.read_level(STREAMS, 9)
        cut = nslevel.cut_level(level, [level.nsd.ldat.exec_map[i] for i in nslevel.CORE_EXEC_SLOTS])
        counts = nslevel.count_by_type(cut.pages)
        for name in ("ZDAT", "WGEO", "SLST", "MIDI"):
            self.assertNotIn(name, counts)
        gools = {nslevel.eid_to_str(e.eid) for p in cut.pages for e in p.entries if e.type == 11}
        self.assertTrue({"WillC", "DispC", "FruiC", "ShadC", "BoxsC", "DoctC"} <= gools, gools)
        self.assertNotIn("BeaOC", gools)
        self.assertLess(len(cut.pages), len(level.pages))
    def test_copy_of_n_sanity_beach_has_the_same_entries(self):
        level = nslevel.read_level(STREAMS, 9)
        out = os.path.join(TOOLS, "..", "build", "test_custom_levels")
        os.makedirs(out, exist_ok=True)
        nslevel.write_level(level, out, "beach_copy")
        copy = nslevel.read_level_files(os.path.join(out, "beach_copy"))
        self.assertEqual(level.nsd.page_count, copy.nsd.page_count)
        self.assertEqual(level.nsd.ldat.image, copy.nsd.ldat.image)
        self.assertEqual(sorted(level.nsd.page_table), sorted(copy.nsd.page_table))
        for a, b in zip(level.pages, copy.pages):
            self.assertEqual([(e.eid, e.type, e.items) for e in a.entries],
                             [(e.eid, e.type, e.items) for e in b.entries])
        for _, eid in copy.nsd.page_table:
            probe(copy.nsd, eid)  # every entry can be found
    def test_reads_n_sanity_beach(self):
        level = nslevel.read_level(STREAMS, 9)
        self.assertEqual(9, level.nsd.ldat.lid)
        self.assertEqual(level.nsd.page_count, len(level.pages))
        counts = nslevel.count_by_type(level.pages)
        for name in ("ZDAT", "WGEO", "SLST", "GOOL", "TPAG"):
            self.assertGreater(counts.get(name, 0), 0, name)
        # every entry in the page table is in a page
        found = {e.eid for p in level.pages for e in p.entries}
        found |= {p.eid for p in level.pages if p.type == 1}
        missing = [nslevel.eid_to_str(eid) for _, eid in level.nsd.page_table if eid not in found]
        self.assertEqual([], missing)
        self.assertIn(EID_WILLC, found)


if __name__ == "__main__":
    unittest.main()
