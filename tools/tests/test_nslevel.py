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

    def test_packing_starts_a_new_page_when_one_is_full(self):
        big = [nslevel.Entry(nslevel.str_to_eid("Big%02d" % i), 1, [b"\0" * 40000])
               for i in range(3)]
        pages = nslevel.pack_entries(big)
        self.assertEqual(3, len(pages))
        self.assertEqual(big, [e for p in pages for e in p.entries])


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
