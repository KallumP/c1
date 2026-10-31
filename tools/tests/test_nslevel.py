"""
tests for tools/nslevel.py

run from the project root: python -m unittest discover -s tools/tests
"""
import os
import struct
import sys
import unittest

from PIL import Image

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
        self.dir = os.path.join(TOOLS, "..", "build", "test_levels")
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


class SharedItems(unittest.TestCase):
    A, B = b"AAAA" * 3, b"BBBB"

    def test_identical_items_are_stored_once(self):
        entry = nslevel.Entry(nslevel.str_to_eid("TestS"), 4, [self.A, self.B, self.A, self.A])
        data = nslevel.entry_bytes(entry)
        self.assertEqual(16 + 4 * 5 + len(self.A) + len(self.B), len(data))

    def test_each_items_offset_points_at_its_data(self):
        # the loader makes each item offset a pointer on its own (NSPageStruct in src/ns.c)
        items = [self.A, self.B, self.A, self.B]
        data = nslevel.entry_bytes(nslevel.Entry(nslevel.str_to_eid("TestS"), 4, items))
        offsets = struct.unpack_from("<5I", data, 16)
        for item, offset in zip(items, offsets):
            self.assertEqual(item, data[offset:offset + len(item)])
        self.assertEqual(len(data), offsets[-1])

    def test_other_entries_keep_every_item_including_empty_ones(self):
        # sort lists never have empty items, but other entries might, and an empty
        # item's offset is the next item's, so only sort lists share
        items = [self.A, b"", self.A]
        data = nslevel.entry_bytes(nslevel.Entry(nslevel.str_to_eid("TestZ"), 7, items))
        self.assertEqual(16 + 4 * 4 + 2 * len(self.A), len(data))
        self.assertEqual(items, nslevel.read_entry(data, 0).items)

    def test_shared_items_read_back(self):
        items = [self.A, self.B, self.A, self.A, self.B]
        data = nslevel.entry_bytes(nslevel.Entry(nslevel.str_to_eid("TestS"), 4, items))
        self.assertEqual(items, nslevel.read_entry(data, 0).items)


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


class Zone(unittest.TestCase):
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

    def test_path_links_to_the_paths_either_side(self):
        # as on n. sanity beach: (relation, neighbor zone index, path index,
        # goal); relation 1 the path before, arriving at its end (goal 2),
        # relation 2 the path after, arriving at its start (goal 1)
        links = [(1, 1, 0, 2), (2, 2, 0, 1)]
        p = nslevel.path_bytes(0, [(0, 0, 0, 0, 0, 0)], cam_mode=5, zoom=1700, avg_node_dist=128, links=links)
        self.assertEqual(2, struct.unpack_from("<I", p, 8)[0])
        self.assertEqual(links, [struct.unpack_from("<4B", p, 12 + 4 * i) for i in range(2)])
        self.assertEqual(1, struct.unpack_from("<H", p, 30)[0])  # the rest is where it was

    def test_zone_header_lists_itself_then_its_neighbors(self):
        # as on n. sanity beach: itself, the zone before, the zone after
        self_eid, before, after = (nslevel.str_to_eid(n) for n in ("Bm01Z", "Bm00Z", "Bm02Z"))
        h = nslevel.zone_header_bytes(bytes(nslevel.ZONE_HEADER_SIZE), self_eid, [], path_count=1,
                                      entity_count=0, neighbors=[before, after])
        self.assertEqual(3, struct.unpack_from("<I", h, nslevel.ZONE_PATHS_IDX + 12)[0])
        self.assertEqual((self_eid, before, after, 0), struct.unpack_from("<4I", h, nslevel.ZONE_NEIGHBORS))

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


def entity(type, subtype, id, points):
    """an entity as stored in a zone: parent zone, spawn flags, group, id,
    point count, 3 init flags, type, subtype, then the points (units of 4)"""
    data = struct.pack("<IHHHHhhhBB", 0, 0x18, 3, id, len(points), 1, 2, 3, type, subtype)
    for p in points:
        data += struct.pack("<3h", *p)
    return nslevel.pad4(data)


class Entities(unittest.TestCase):
    def test_entity_type_and_subtype(self):
        self.assertEqual((34, 6), nslevel.entity_type(entity(34, 6, 1, [(0, 0, 0)])))

    def test_entity_id(self):
        self.assertEqual(77, nslevel.entity_id(entity(34, 6, 77, [(0, 0, 0)])))
        self.assertEqual(78, nslevel.entity_id(nslevel.with_entity_id(entity(34, 6, 77, [(0, 0, 0)]), 78)))

    def test_new_ids_skip_the_main_objects_and_ones_taken(self):
        # spawns[] in src/gool.c is indexed by id; ids 1 to 4 make the main object (crash)
        ids = nslevel.new_entity_ids(5, taken={9, 5})
        self.assertEqual([6, 7, 8, 10, 11], ids)

    def test_ids_stay_in_the_games_spawn_table(self):
        with open(os.path.join(TOOLS, "..", "src", "gool.h")) as f:
            line = next(l for l in f if l.startswith("#define GOOL_SPAWN_COUNT"))
        self.assertEqual(int(line.split()[2]) - 1, nslevel.ENTITY_IDS_MAX)

    def test_there_are_only_so_many_ids(self):
        self.assertEqual(nslevel.ENTITY_IDS_MAX, max(nslevel.new_entity_ids(nslevel.ENTITY_IDS_MAX - 4, taken=set())))
        with self.assertRaises(ValueError) as e:
            nslevel.new_entity_ids(nslevel.ENTITY_IDS_MAX - 3, taken=set())
        self.assertIn("objects", str(e.exception))


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

    def test_world_header_keeps_the_templates_textures(self):
        template = struct.pack("<iiiIIIII", 1, 2, 3, 99, 99, 2, 1, 0)
        template += struct.pack("<8I", nslevel.str_to_eid("Ju89T"), *([0] * 7)) + b"TEX!TEX?"
        header = nslevel.world_header_bytes(template, (10, 20, 30), poly_count=4, vert_count=5)
        self.assertEqual((10, 20, 30, 4, 5, 2, 1, 0), struct.unpack_from("<iiiIIIII", header, 0))
        self.assertEqual(template[32:], header[32:])


def slst_list(item):
    length, type = struct.unpack_from("<HH", item, 0)
    return type, list(struct.unpack_from("<%dH" % length, item, 4))


class _Nodes:
    """slst_context in src/slst.c, reading add or remove nodes"""
    def __init__(self, nodes, start, end):
        self.nodes, self.i, self.end = nodes, start, end
        self.idx = self.len = self.count = self.poly = 0

    def word(self):
        w = self.nodes[self.i] if self.i < len(self.nodes) else 0xFFFF
        self.i += 1
        return w

    def next(self):  # SlstRemNext / SlstAddNext
        if self.len > 0:
            self.poly = self.word()
            self.idx += self.poly >> 15
        else:
            node = self.word()
            if self.i < self.end and node != 0xFFFF:
                self.idx, self.len = node & 0xFFF, ((node & 0xF000) >> 12) + 1
            else:
                self.idx, self.len = 0xFFFF00, 0
            if self.len > 0:
                self.poly = self.word()


def slst_words(item):
    """a sort list item's 16 bit words after its length and type: a delta's
    split_idx, swaps_idx and nodes (slst_delta in src/formats/slst.h)"""
    length, type = struct.unpack_from("<HH", item, 0)
    return length, type, list(struct.unpack_from("<%dH" % length, item, 4))


def slst_decode(item, src, forward):
    """SlstUpdate (src/slst.c) on src, a list of poly ids: a full list is
    copied, a delta applied forward (SlstDecodeForward) or backward
    (SlstDecodeBackward). the deltas here have no swaps"""
    length, type, nodes = slst_words(item)
    if not type & 1:
        return nodes
    split, swaps = nodes[0], nodes[1]
    assert swaps == length, "no swaps"
    if forward:
        rem, add = _Nodes(nodes, 2, split), _Nodes(nodes, split, swaps)
    else:
        add, rem = _Nodes(nodes, 2, split), _Nodes(nodes, split, swaps)
    rem.next()
    add.next()
    isrc, dst = 0, []
    for _ in range(100000):
        if forward:
            removes = isrc < len(src) and rem.len > 0 and rem.idx - 1 - isrc == 0
            adds = add.len > 0 and add.idx + rem.count - isrc == 0
        else:
            removes = isrc < len(src) and rem.len > 0 and rem.idx + rem.count - isrc == 0
            adds = add.len > 0 and add.idx + rem.count - (add.count + 1) - isrc == 0
        if removes:
            isrc += 1
            rem.len -= 1
            rem.count += 1
            rem.next()
        elif adds:
            dst.append(add.poly & 0x7FFF)
            add.len -= 1
            add.count += 1
            add.next()
        elif isrc < len(src):
            if forward:
                n = min(add.idx + rem.count - isrc, rem.idx - (isrc + 1), len(src) - (isrc + 1))
                n = 1 if n == 0 else n
            else:
                n = min(add.idx + (rem.count - add.count) - (isrc + 1), rem.idx + rem.count - isrc,
                        len(src) - (isrc + 1))
                n = 1 if n <= 0 else n
            assert n > 0, "the game would loop forever"
            dst += src[isrc:isrc + n]
            isrc += n
        if not (isrc < len(src) or add.len > 0 or rem.len > 0):
            return dst
    raise AssertionError("the game would loop forever")


def slst_walk(items, forward=True):
    """each point's list, the way LevelUpdate gets it walking the whole path
    from its first point (forward) or its last (backward)"""
    n = len(items) - 1
    if forward:
        lists = [slst_decode(items[0], [], True)]
        for k in range(1, n):
            lists.append(slst_decode(items[k], lists[-1], True))
        return lists
    lists = [slst_decode(items[n], [], False)]
    for k in range(n - 1, 0, -1):
        lists.insert(0, slst_decode(items[k], lists[0], False))
    return lists


class SortList(unittest.TestCase):
    # three polygons whose far edges (towards +z) are at z 100, 500 and 900;
    # the camera moves along -z from 1000 to 600 in steps of 200
    POLY_ZMAX = [100, 500, 900]
    CAM_ZS = [1000, 800, 600]

    def test_full_lists_at_the_ends_and_changes_between(self):
        # LevelUpdate copies item 0 at the first point and item N at the
        # last (N points), and steps between with items 1..N-1
        items = nslevel.slst_items([self.POLY_ZMAX], self.CAM_ZS, step=200, near=50)
        self.assertEqual(len(self.CAM_ZS) + 1, len(items))
        self.assertEqual([0, 1, 1, 0], [slst_words(item)[1] & 1 for item in items])

    def test_each_point_lists_only_polygons_in_front_of_the_camera(self):
        # in front for the whole step to the next point: zmax < cam z - step - near
        items = nslevel.slst_items([self.POLY_ZMAX], self.CAM_ZS, step=200, near=50)
        ids = [nslevel.poly_id(0, i) for i in range(3)]
        expected = [ids[:2], ids[:2], ids[:1]]  # under 1000-250 and 800-250: 100 and 500; then 100
        self.assertEqual(expected, slst_walk(items))
        self.assertEqual(expected, slst_walk(items, forward=False))

    def test_walking_the_path_either_way_gives_each_points_list(self):
        # polygons coming into view and leaving it, in runs longer than a
        # node holds (16), at the start, middle and end of the lists
        zmax = [z * 10 for z in range(300)]
        zmid = [(z * 37) % 300 for z in range(300)]
        cams = list(range(3500, 600, -170))
        items = nslevel.slst_items([zmax, zmax[:40]], cams, step=170, near=50,
                                   world_zmid=[zmid, zmid[:40]])
        expected = [slst_words(nslevel.slst_items([zmax, zmax[:40]], [c], step=170, near=50,
                                                  world_zmid=[zmid, zmid[:40]])[0])[2] for c in cams]
        self.assertEqual(expected, slst_walk(items))
        self.assertEqual(expected, slst_walk(items, forward=False))

    def test_changes_go_both_ways(self):
        ids = list(range(1, 200))
        cases = [([], ids[:30]), (ids[:30], []), (ids[:50], ids[10:60]), (ids[::2], ids[::3]),
                 (ids[5:40] + ids[90:120], ids[:20] + ids[30:100] + ids[150:]), (ids, ids)]
        for a, b in cases:
            item = nslevel.slst_delta(a, b)
            self.assertEqual(b, slst_decode(item, a, True))
            self.assertEqual(a, slst_decode(item, b, False))

    def test_a_long_path_fits_in_a_page(self):
        zmax = [z * 8 for z in range(4000)]
        items = nslevel.slst_items([zmax], list(range(32000, 0, -128)), step=128, near=50)
        self.assertLess(sum(len(i) for i in items), nslevel.PAGE_SIZE // 2)

    def test_lists_polygons_of_every_world_mesh(self):
        items = nslevel.slst_items([[100, 900], [200]], [1000], step=200, near=50)
        self.assertEqual([nslevel.poly_id(0, 0), nslevel.poly_id(1, 0)], slst_list(items[0])[1])

    def test_lists_polygons_farthest_first(self):
        # the game draws a list in order, later polygons over earlier ones,
        # with no depth test, so a near wall has to come after what's behind
        # it. by their middles: a floor piece just behind a wall shares the
        # wall's largest z
        items = nslevel.slst_items([[500, 100], [500]], [1000], step=200, near=50,
                                   world_zmid=[[250, 50], [500]])
        self.assertEqual([nslevel.poly_id(0, 1), nslevel.poly_id(0, 0), nslevel.poly_id(1, 0)],
                         slst_list(items[0])[1])

    def test_keeps_the_nearest_polygons_the_game_can_list(self):
        # custom levels' lists hold at most 4095 polygons (SlstPolyIdCount in
        # src/slst.h); the farthest (smallest z, as the camera looks along -z) are left out
        items = nslevel.slst_items([[0] * 3000, [500] * 3000], [1000], step=200, near=50)
        ids = slst_list(items[0])[1]
        self.assertEqual(4095, len(ids))
        self.assertEqual(3000, sum(1 for i in ids if i >> 12 == 1))  # all of the nearer world

    def test_the_tool_lists_as_many_polygons_as_the_game_holds(self):
        with open(os.path.join(TOOLS, "..", "src", "slst.h")) as f:
            line = next(l for l in f if l.startswith("#define SLST_CUSTOM_POLY_IDS"))
        self.assertEqual(nslevel.POLY_IDS_MAX, int(line.split()[2]))

    def test_a_change_at_the_end_of_a_full_list_fits_its_node(self):
        # a remove node holds the first place + 1 in 12 bits, and the run's length above them
        full = list(range(nslevel.POLY_IDS_MAX))
        _, words = slst_list(nslevel.slst_delta(full, full[:-1]))
        node = words[2]  # the first remove node, after split and swaps
        self.assertEqual(len(full), node & 0xFFF)  # the last place + 1, whole
        self.assertEqual(0, node >> 12)  # a run of one

    def test_a_zones_list_takes_in_the_next_zones_meshes(self):
        # the next zone is further along -z, so its meshes are offset by -16384
        # in this zone's frame, and come first, being farther
        verts = [(0, 0, 1000, None), (8, 0, 1000, None), (0, 0, 1008, None)]
        listed = [(verts, [(0, 1, 2)], 0), (verts, [(0, 1, 2)], -16384)]
        items = nslevel.zone_slst_items(listed, [3000], step=200)
        self.assertEqual([nslevel.poly_id(1, 0), nslevel.poly_id(0, 0)], slst_words(items[0])[2])

    def test_poly_id_layout(self):
        self.assertEqual((2 << 12) | 7, nslevel.poly_id(2, 7))


class MapCells(unittest.TestCase):
    def test_cells_become_blocks_with_their_leaf(self):
        blocks = nslevel.cell_blocks({(1, 2, 3): "floor", (0, 0, 0): "pit", (2, 0, 0): "wall"}, 128)
        self.assertEqual(sorted([(128, 256, 384, 256, 384, 512, nslevel.LEAF_FLOOR),
                                 (0, 0, 0, 128, 128, 128, nslevel.LEAF_PIT),
                                 (256, 0, 0, 384, 128, 128, nslevel.LEAF_GROUND)]), sorted(blocks))

    def test_floor_leaf_is_a_floor_crash_can_step_up_onto(self):
        # FindFloorY in src/solid.c: type (bits 1-3) 0 is wall or scenery, which crash
        # can't step up onto; 1 is floor, as most of n. sanity beach is
        self.assertEqual(1, (nslevel.LEAF_FLOOR & 0xE) >> 1)
        self.assertEqual(1, nslevel.LEAF_FLOOR & 1)  # a leaf


# a map as blender exports it: a floor 8 m by 16 m, a wall, and a spawn marker
MAP_OBJ = """o Floor
v -4 0 -8
v -4 0 8
v 4 0 8
v 4 0 -8
f 1 2 3 4
o Wall
v 4 0 -8
v 4 2 -8
v 4 2 8
v 4 0 8
f 5 6 7 8
o Spawn
v 0 1 5
v 0.1 1 5
v 0 1.1 5
f 9 10 11
"""


@unittest.skipUnless(os.path.exists(os.path.join(STREAMS, "s0000009.nsd")),
                     "needs N. Sanity Beach in streams/")
class Map(unittest.TestCase):
    def make(self, text=MAP_OBJ, **kw):
        level = nslevel.make_map(nslevel.read_level(STREAMS, 9), text, **kw)
        entries = {e.eid: e for p in level.pages for e in p.entries}
        return level, entries, entries[level.nsd.ldat.zone_spawn]

    TEXTURED_OBJ = MAP_OBJ.replace("o Floor\n", "o Floor\nusemtl stone\n").replace("o Wall\n", "o Wall\nusemtl plain\n")

    def stone(self):
        return Image.new("RGB", (32, 32), (90, 90, 100))

    def textures(self, level):
        return [p for p in level.pages if p.type == nslevel.PAGE_TEXTURE]

    def world(self, entries, zone):
        return entries[struct.unpack_from("<I", zone.items[0], 4)[0]]

    def test_material_images_become_a_texture_page_the_zone_loads(self):
        plain, _, _ = self.make(self.TEXTURED_OBJ)
        level, entries, zone = self.make(self.TEXTURED_OBJ, images={"stone": self.stone()})
        self.assertEqual(len(self.textures(plain)) + 1, len(self.textures(level)))
        tpags = struct.unpack_from("<8I", self.world(entries, zone).items[0], 32)
        new = [p.eid for p in self.textures(level) if p.eid not in {q.eid for q in self.textures(plain)}]
        self.assertIn(new[0], tpags)
        header = zone.items[0]
        self.assertEqual(len(self.textures(level)), struct.unpack_from("<i", header, nslevel.ZONE_LOADLIST + 4)[0])

    def test_textured_polygons_use_their_materials_tile(self):
        level, entries, zone = self.make(self.TEXTURED_OBJ, images={"stone": self.stone()})
        world = self.world(entries, zone)
        header = world.items[0]
        fields = struct.unpack_from(nslevel.WGEO_HEADER, header, 0)
        tpags = struct.unpack_from("<8I", header, 32)
        page = next(p for p in self.textures(level) if p.eid == tpags[fields[6] - 1])
        stone = nslevel.blendmap.tpage.colour_5551((90, 90, 100))
        on_page = 0
        for i in range(fields[3]):
            w0 = struct.unpack_from("<I", world.items[1], 8 * i)[0]
            tinf, tpag = (w0 >> 8) & 0xFFF, (w0 >> 5) & 7
            if tpags[tpag] != page.eid:
                continue
            on_page += 1
            self.assertLess(tinf + 1, fields[5])  # within the mesh's texture infos
            rgn = struct.unpack_from("<I", header, 64 + 4 * tinf + 4)[0]
            clut_y = (rgn >> 6) & 127
            self.assertIn(stone, struct.unpack_from("<16H", page.data, clut_y * 512))
        self.assertGreater(on_page, 0)

    def test_each_mesh_holds_only_the_texture_regions_it_uses(self):
        # a mesh header's texinfos are indexed by 12 bits of words, so a map
        # whose meshes together use more regions than that still fits if each
        # mesh lists its own
        template = struct.pack(nslevel.WGEO_HEADER, 0, 0, 0, 0, 0, 2, 1, 0) + bytes(32) + b"TEX!TEX?"
        TileRegion = nslevel.blendmap.TileRegion
        a, b = TileRegion("stone", 0, 0, 32, 32, 0), TileRegion("stone", 32, 0, 32, 32, 0)
        verts = [(0, 0, 0, (128, 128, 128))] * 3
        worlds = [(verts, [(0, 1, 2, a, None), (0, 1, 2, a, None)]), (verts, [(0, 1, 2, b, None)])]
        worlds, (tpags, texinfos, pages) = nslevel.map_textures(worlds, {"stone": self.stone()}, template)
        self.assertEqual([8, 8], [len(t) for t in texinfos])  # one region (2 words) each
        self.assertEqual([2, 2], [p[3] for p in worlds[0][1]])  # after the template's 2 words
        self.assertEqual([2], [p[3] for p in worlds[1][1]])
        self.assertNotEqual(texinfos[0], texinfos[1])

    def test_materials_without_an_image_keep_n_sanity_beachs_textures(self):
        level, entries, zone = self.make(self.TEXTURED_OBJ, images={"stone": self.stone()})
        tpags = struct.unpack_from("<8I", self.world(entries, zone).items[0], 32)
        used = {tpags[(struct.unpack_from("<I", self.world(entries, zone).items[1], 8 * i)[0] >> 5) & 7]
                for i in range(len(self.world(entries, zone).items[1]) // 8)}
        self.assertEqual(2, len(used))  # the stone page, and the beach's page for the wall

    def test_map_images_are_read_from_the_mtl_next_to_the_obj(self):
        out = os.path.join(TOOLS, "..", "build", "test_map_images")
        os.makedirs(os.path.join(out, "textures"), exist_ok=True)
        self.stone().save(os.path.join(out, "textures", "stone.png"))
        with open(os.path.join(out, "level.mtl"), "w") as f:
            f.write("newmtl stone\nmap_Kd textures/stone.png\nnewmtl plain\nKd 1 1 1\n")
        images = nslevel.map_images(os.path.join(out, "level.obj"), "mtllib level.mtl\n" + self.TEXTURED_OBJ)
        self.assertEqual(["stone"], list(images))
        self.assertEqual((90, 90, 100), images["stone"].convert("RGB").getpixel((0, 0)))

    def test_a_level_sources_folder_gives_its_obj_and_the_folders_name(self):
        out = os.path.normpath(os.path.join(TOOLS, "..", "build", "test_level_source", "my_level"))
        os.makedirs(out, exist_ok=True)
        for name in os.listdir(out):
            os.remove(os.path.join(out, name))
        open(os.path.join(out, "level.obj"), "w").close()
        open(os.path.join(out, "level.mtl"), "w").close()
        self.assertEqual((os.path.join(out, "level.obj"), "my_level"), nslevel.level_source(out))
        self.assertEqual((os.path.join(out, "level.obj"), "my_level"), nslevel.level_source(out + os.sep))

    def test_a_level_sources_obj_gives_itself_and_its_name(self):
        path = os.path.join("level_src", "x", "level.obj")
        self.assertEqual((path, "level"), nslevel.level_source(path))

    def test_a_level_sources_folder_needs_one_obj(self):
        out = os.path.join(TOOLS, "..", "build", "test_level_source", "two")
        os.makedirs(out, exist_ok=True)
        for name in ("a.obj", "b.obj"):
            open(os.path.join(out, name), "w").close()
        with self.assertRaises(ValueError):
            nslevel.level_source(out)
        with self.assertRaises(ValueError):
            nslevel.level_source(os.path.join(TOOLS, "..", "build", "test_level_source"))  # none

    def test_map_is_one_zone_with_its_geometry_and_crash_only(self):
        level, entries, zone = self.make()
        self.assertEqual(nslevel.LID_TEST, level.nsd.ldat.lid)
        header = zone.items[0]
        paths_idx, path_count, entity_count, _ = struct.unpack_from("<4I", header, nslevel.ZONE_PATHS_IDX)
        self.assertEqual((1, 1), (path_count, entity_count))
        self.assertEqual((0, 0), nslevel.entity_type(zone.items[paths_idx + 1]))  # crash
        execs = [e for e in level.nsd.ldat.exec_map if e != nslevel.EID_NONE]
        self.assertEqual(len(nslevel.CORE_EXEC_SLOTS), len(execs))
        counts = nslevel.count_by_type(level.pages)
        self.assertEqual(1, counts["ZDAT"])
        self.assertEqual(1, counts["SLST"])
        self.assertEqual(struct.unpack_from("<I", header, 0)[0], counts["WGEO"])

    def test_crash_starts_on_the_ground_at_the_spawn_marker(self):
        level, entries, zone = self.make(scale=256)
        paths_idx = struct.unpack_from("<I", zone.items[0], nslevel.ZONE_PATHS_IDX)[0]
        crash = zone.items[paths_idx + 1]
        x, y, z = (c * 4 for c in struct.unpack_from("<3h", crash, nslevel.ENTITY_POINTS))
        # the floor's corner is at the zone's corner plus a cell of margin
        self.assertAlmostEqual(128 + 4 * 256, x, delta=16)  # the marker's middle, on multiples of 8
        self.assertEqual(128 + 5 * 256 + 8 * 256, z)
        self.assertGreater(y, 128)
        self.assertLessEqual(y, 128 + 128)

    def crash_at(self, zone):
        """crash's position in a zone (zone units)"""
        paths_idx, path_count = struct.unpack_from("<2I", zone.items[0], nslevel.ZONE_PATHS_IDX)
        crash = zone.items[paths_idx + path_count]
        self.assertEqual((0, 0), nslevel.entity_type(crash))
        return tuple(c * 4 for c in struct.unpack_from("<3h", crash, nslevel.ENTITY_POINTS))

    def test_a_spawn_object_puts_crash_on_the_ground_below_it(self):
        # blender (2, -3, 0) is the .obj's (2, 0, 3): over the floor, away from the marker
        spawn = nslevel.levelobjects.LevelObject("spawn", (2, -3, 0.5))
        level, entries, zone = self.make(scale=256, objects=[spawn])
        x, y, z = self.crash_at(zone)
        self.assertAlmostEqual(128 + 6 * 256, x, delta=16)
        self.assertAlmostEqual(128 + 11 * 256, z, delta=16)
        self.assertGreater(y, 128)
        self.assertLessEqual(y, 128 + 128)

    def test_a_spawn_object_needs_ground_below_it(self):
        spawn = nslevel.levelobjects.LevelObject("spawn", (20, -3, 0.5))  # off the side of the map
        with self.assertRaises(ValueError) as e:
            self.make(scale=256, objects=[spawn])
        self.assertIn("spawn", str(e.exception))

    def entities(self, zone):
        paths_idx, path_count, entity_count = struct.unpack_from("<3I", zone.items[0], nslevel.ZONE_PATHS_IDX)
        return zone.items[paths_idx + path_count:paths_idx + path_count + entity_count]

    def warp_pads(self, entries):
        """(zone, position in it) of each warp pad (WarpC) in the level"""
        return [(zone, tuple(c * 4 for c in struct.unpack_from("<3h", e, nslevel.ENTITY_POINTS)))
                for zone in entries.values() if zone.type == 7
                for e in self.entities(zone) if nslevel.entity_type(e) == nslevel.WARP_PAD]

    def test_an_end_object_puts_a_warp_pad_on_the_ground_below_it(self):
        # blender (-2, 4, 0.5) is the .obj's (-2, 0.5, -4)
        end = nslevel.levelobjects.LevelObject("end", (-2, 4, 0.5))
        level, entries, zone = self.make(scale=256, objects=[end])
        [(pad_zone, (x, y, z))] = self.warp_pads(entries)
        self.assertEqual(zone.eid, pad_zone.eid)
        self.assertAlmostEqual(128 + 2 * 256, x, delta=16)
        self.assertAlmostEqual(128 + 4 * 256, z, delta=16)
        self.assertEqual(128, y)  # on the floor's top
        self.assertEqual((0, 0), nslevel.entity_type(self.entities(zone)[0]))  # crash stays first

    def test_raise_lifts_the_warp_pad_and_its_base(self):
        end = nslevel.levelobjects.LevelObject("end", (-2, 4, 0.5), raise_by=0.25)  # 64 at scale 256
        level, entries, zone = self.make(scale=256, objects=[end])
        [(_, (x, y, z))] = self.warp_pads(entries)
        self.assertEqual(128 + 64, y)

    def test_the_warp_pads_code_comes_with_it(self):
        end = nslevel.levelobjects.LevelObject("end", (-2, 4, 0.5))
        level, entries, zone = self.make(scale=256, objects=[end])
        self.assertIn(level.nsd.ldat.exec_map[nslevel.WARP_PAD[0]], entries)

    def test_without_an_end_object_theres_no_warp_pad(self):
        level, entries, zone = self.make(scale=256)
        self.assertEqual([], self.warp_pads(entries))

    def boxes(self, zone):
        """(subtype, id, position) of each box in a zone, in order"""
        return [(nslevel.entity_type(e)[1], nslevel.entity_id(e),
                 tuple(c * 4 for c in struct.unpack_from("<3h", e, nslevel.ENTITY_POINTS)))
                for e in self.entities(zone) if nslevel.entity_type(e)[0] == nslevel.BOX_TYPE]

    def test_a_box_goes_on_the_ground_below_it(self):
        # blender (1, 2, 0.5) is the .obj's (1, 0.5, -2)
        box = nslevel.levelobjects.LevelObject("box", (1, 2, 0.5), subtype=6)
        level, entries, zone = self.make(scale=256, objects=[box])
        [(subtype, _, (x, y, z))] = self.boxes(zone)
        self.assertEqual(6, subtype)
        self.assertAlmostEqual(128 + 5 * 256, x, delta=16)
        self.assertAlmostEqual(128 + 6 * 256, z, delta=16)
        self.assertEqual(128, y)

    def test_a_stack_is_boxes_one_on_another_one_after_another(self):
        # GoolObjectSpawn in src/gool.c stacks a box on the box spawned just
        # before it when it's at the same x and z and 100 (in units of 4) higher
        box = nslevel.levelobjects.LevelObject("box", (1, 2, 0.5), subtype=2, stack=3)
        level, entries, zone = self.make(scale=256, objects=[box])
        stack = self.boxes(zone)
        self.assertEqual(3, len(stack))
        for (_, _, below), (_, _, above) in zip(stack, stack[1:]):
            self.assertEqual(below[0], above[0])
            self.assertEqual(below[2], above[2])
            self.assertEqual(below[1] + nslevel.BOX_HEIGHT, above[1])

    def test_every_object_has_its_own_id(self):
        objects = [nslevel.levelobjects.LevelObject("box", (1, 2, 0.5), subtype=2, stack=2),
                   nslevel.levelobjects.LevelObject("box", (-1, 2, 0.5), subtype=13),
                   nslevel.levelobjects.LevelObject("end", (-2, 4, 0.5))]
        level, entries, zone = self.make(scale=256, objects=objects)
        ids = [nslevel.entity_id(e) for z in entries.values() if z.type == 7 for e in self.entities(z)]
        self.assertEqual(5, len(ids))  # crash, 3 boxes and the warp pad
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i not in nslevel.ENTITY_MAIN_IDS and i <= nslevel.ENTITY_IDS_MAX
                            for i in ids if i != nslevel.entity_id(nslevel.Templates(level).crash)))

    def test_an_end_object_needs_ground_below_it(self):
        end = nslevel.levelobjects.LevelObject("end", (-20, 4, 0.5))
        with self.assertRaises(ValueError) as e:
            self.make(scale=256, objects=[end])
        self.assertIn("end", str(e.exception))

    def test_the_warp_pads_base_is_in_the_beachs_terrain_under_it(self):
        base = nslevel.warp_pad_base(nslevel.read_level(STREAMS, 9))
        self.assertGreater(len(base.polys), 20)
        xs, ys, zs = zip(*((x, y, z) for x, y, z, _ in base.verts))
        # relative to the pad: around it, and from its top down
        self.assertLessEqual(max(map(abs, xs + zs)), 700)
        self.assertLessEqual(max(ys), 16)
        self.assertGreaterEqual(min(ys), -600)
        self.assertTrue(all(len(base.texinfos[tinf]) == 8 for *_, tinf in base.polys))  # 2 words each
        self.assertIn(base.page, {p.eid for p in nslevel.read_level(STREAMS, 9).pages})

    def test_an_end_object_has_the_warp_pads_base_under_it(self):
        end = nslevel.levelobjects.LevelObject("end", (-2, 4, 0.5))
        level, entries, zone = self.make(scale=256, objects=[end])
        base = nslevel.warp_pad_base(nslevel.read_level(STREAMS, 9))
        [(_, (px, py, pz))] = self.warp_pads(entries)
        on_page = []
        for w in range(struct.unpack_from("<I", zone.items[0], 0)[0]):
            world = entries[struct.unpack_from("<I", zone.items[0], 4 + w * nslevel.ZONE_WORLD_SIZE)[0]]
            fields = struct.unpack_from(nslevel.WGEO_HEADER, world.items[0], 0)
            tpags = struct.unpack_from("<8I", world.items[0], 32)
            verts = [decode_vertex(world.items[2][8 * i:8 * i + 8]) for i in range(fields[4])]
            for i in range(fields[3]):
                a, b, c, tinf, tpag = decode_polygon(world.items[1][8 * i:8 * i + 8])
                if tpags[tpag] == base.page:
                    self.assertLess(tinf + 1, fields[5])  # within the mesh's texinfos
                    on_page += [verts[a], verts[b], verts[c]]
        self.assertEqual(len(base.polys), len(on_page) // 3)
        xs, ys, zs = zip(*(v[:3] for v in on_page))
        self.assertAlmostEqual(px, (min(xs) + max(xs)) / 2, delta=64)
        self.assertAlmostEqual(pz, (min(zs) + max(zs)) / 2, delta=64)
        self.assertAlmostEqual(py, max(ys), delta=16)  # its top on the floor, where the pad stands
        self.assertIn(base.page, {p.eid for p in level.pages if p.type == nslevel.PAGE_TEXTURE})

    def test_world_meshes_are_its_faces(self):
        level, entries, zone = self.make()
        header = zone.items[0]
        world = entries[struct.unpack_from("<I", header, 4)[0]]
        _, _, _, polys, verts = struct.unpack_from("<iiiII", world.items[0], 0)
        self.assertGreater(polys, 4)  # floor and wall, sliced
        self.assertEqual(polys * 8, len(world.items[1]))

    def test_a_bigger_map_gets_several_world_meshes(self):
        rows = []
        for k in range(60):
            for i in range(60):
                rows.append("v %d 0 %d\nv %d 0 %d\nv %d 0 %d\nf -3 -2 -1" % (
                    i, k, i, k + 1, i + 1, k + 1))
        level, entries, zone = self.make("o Floor\n" + "\n".join(rows), scale=96)
        self.assertGreater(struct.unpack_from("<I", zone.items[0], 0)[0], 1)

    def test_paths_use_the_follow_camera(self):
        # cam_mode 9 (src/pc/follow.h): along the path, and sideways after crash
        level, entries, zone = self.make()
        paths_idx = struct.unpack_from("<I", zone.items[0], nslevel.ZONE_PATHS_IDX)[0]
        self.assertEqual(nslevel.FOLLOW_CAM_MODE, struct.unpack_from("<H", zone.items[paths_idx], 32)[0])
        self.assertEqual(9, nslevel.FOLLOW_CAM_MODE)

    def test_turn_runs_the_map_along_z(self):
        # turned a quarter, the 16 m long floor runs along x
        level, entries, zone = self.make(scale=256, turn=90)
        w, h, d = struct.unpack_from("<III", zone.items[1], 12)
        self.assertGreater(w, d)

    # a floor 100 m long: 40000 units at the default scale, so 3 zones of 16384
    LONG_OBJ = "o Floor\nv -4 0 -50\nv -4 0 50\nv 4 0 50\nv 4 0 -50\nf 1 2 3 4\n"

    _long = None

    def long_zones(self):
        if Map._long is None:  # built once, as it takes a while
            level, entries, _ = self.make(self.LONG_OBJ)
            zones = sorted((e for e in entries.values() if e.type == 7),
                           key=lambda z: -struct.unpack_from("<i", z.items[1], 8)[0])  # from the start (+z)
            Map._long = level, entries, zones
        return Map._long

    def neighbors(self, zone):
        count = struct.unpack_from("<I", zone.items[0], nslevel.ZONE_PATHS_IDX + 12)[0]
        return list(struct.unpack_from("<%dI" % count, zone.items[0], nslevel.ZONE_NEIGHBORS))

    def test_an_end_object_far_along_a_long_map_is_in_the_last_zone(self):
        # blender y 45 is the .obj's z -45: 5 m from the far end, in the third zone
        end = nslevel.levelobjects.LevelObject("end", (0, 45, 0))
        level, entries, _ = self.make(self.LONG_OBJ, objects=[end])
        zones = sorted((e for e in entries.values() if e.type == 7),
                       key=lambda z: -struct.unpack_from("<i", z.items[1], 8)[0])
        [(pad_zone, (x, y, z))] = self.warp_pads(entries)
        self.assertEqual(zones[2].eid, pad_zone.eid)
        # the floor's far end is a cell (128) in from the third zone's corner,
        # and the pad 5 m (2000) on from that
        self.assertAlmostEqual(128 + 2000, z, delta=16)

    def test_a_long_map_is_a_chain_of_zones_along_the_route(self):
        level, entries, zones = self.long_zones()
        self.assertEqual(3, len(zones))
        rects = [struct.unpack_from("<iiiIII", z.items[1], 0) for z in zones]
        for (x, y, z, w, h, d), nxt in zip(rects, rects[1:]):
            self.assertEqual(16384, d)
            self.assertEqual(z - 16384, nxt[2])  # the next one along -z, touching
            self.assertEqual((x, y, w, h), nxt[:2] + nxt[3:5])

    def test_each_zone_lists_itself_then_the_zones_either_side(self):
        level, entries, zones = self.long_zones()
        a, b, c = (z.eid for z in zones)
        self.assertEqual([[a, b], [b, a, c], [c, b]], [self.neighbors(z) for z in zones])

    def test_paths_lead_on_to_the_next_zones_and_back(self):
        level, entries, zones = self.long_zones()
        links = []
        for z in zones:
            paths_idx, path_count = struct.unpack_from("<2I", z.items[0], nslevel.ZONE_PATHS_IDX)
            for p in z.items[paths_idx:paths_idx + path_count]:
                n = struct.unpack_from("<I", p, 8)[0]
                links.append(sorted(struct.unpack_from("<4B", p, 12 + 4 * i) for i in range(n)))
        # crash starts in the first zone, so all three have a path
        self.assertEqual([[(2, 1, 0, 1)], [(1, 1, 0, 2), (2, 2, 0, 1)], [(1, 1, 0, 2)]], links)

    def test_crash_is_in_the_zone_the_level_spawns_in(self):
        level, entries, zones = self.long_zones()
        spawn = entries[level.nsd.ldat.zone_spawn]
        counts = [struct.unpack_from("<I", z.items[0], nslevel.ZONE_PATHS_IDX + 8)[0] for z in zones]
        self.assertEqual(1, sum(counts))
        self.assertEqual(1, struct.unpack_from("<I", spawn.items[0], nslevel.ZONE_PATHS_IDX + 8)[0])
        paths_idx, path_count = struct.unpack_from("<2I", spawn.items[0], nslevel.ZONE_PATHS_IDX)
        crash = spawn.items[paths_idx + path_count]
        z = struct.unpack_from("<h", crash, nslevel.ENTITY_POINTS + 4)[0] * 4
        self.assertTrue(0 <= z < 16384, z)  # relative to its zone

    def test_every_zone_loads_the_texture_pages(self):
        level, entries, zones = self.long_zones()
        pages = sum(1 for p in level.pages if p.type == nslevel.PAGE_TEXTURE)
        for z in zones:
            self.assertEqual(pages, struct.unpack_from("<i", z.items[0], nslevel.ZONE_LOADLIST + 4)[0])

    def test_a_zone_draws_its_own_and_the_next_zones_meshes(self):
        level, entries, zones = self.long_zones()
        worlds = []
        for z in zones:
            count = struct.unpack_from("<I", z.items[0], 0)[0]
            worlds.append([struct.unpack_from("<I", z.items[0], 4 + i * nslevel.ZONE_WORLD_SIZE)[0]
                           for i in range(count)])
        for i in range(2):
            self.assertTrue(set(worlds[i + 1]) & set(worlds[i]), "zone %d lists the next zone's meshes" % i)
        self.assertLessEqual(max(len(w) for w in worlds), 8)


@unittest.skipUnless(os.path.exists(os.path.join(STREAMS, "s0000009.nsd")),
                     "needs N. Sanity Beach in streams/")
class RealLevel(unittest.TestCase):
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
    def test_written_n_sanity_beach_reads_back_the_same(self):
        level = nslevel.read_level(STREAMS, 9)
        out = os.path.join(TOOLS, "..", "build", "test_levels")
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
