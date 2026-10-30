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


@unittest.skipUnless(os.path.exists(os.path.join(STREAMS, "s0000009.nsd")),
                     "needs N. Sanity Beach in streams/")
class RealLevel(unittest.TestCase):
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
