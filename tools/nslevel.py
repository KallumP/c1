"""
Read (and later write) the game's level files: a level is an .nsd (page
table and level header) and an .nsf (64 KB pages of entries).

The layouts mirror the structs in src/ns.h, which the game loads as is.
"""
import os
import struct

MAGIC_PAGE = 0x1234
MAGIC_ENTRY = 0x100FFFF
PAGE_SIZE = 0x10000
SECTOR_SIZE = 0x800
EID_NONE = 0x6396347F

ALPHA = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_!"

# entry type names, by the type number (the subsystem table in src/main.c)
TYPE_NAMES = {
    1: "SVTX", 2: "TGEO", 3: "WGEO", 4: "SLST", 5: "TPAG", 6: "LDAT",
    7: "ZDAT", 8: "CPAT", 9: "BINF", 10: "OPAT", 11: "GOOL", 12: "ADIO",
    13: "MIDI", 14: "INST", 15: "IMAG", 16: "LINK", 17: "MDAT", 18: "IPAL",
    19: "PBAK", 20: "CVTX",
}

# page types
PAGE_ENTRIES = 0
PAGE_TEXTURE = 1

NSD_PTB_COUNT = 256
NSD_COMPRESSED_PAGE_COUNT = 64
NSD_EXEC_COUNT = 64
NSD_HEADER = "<iIIiIIIi"  # page_count .. compressed_page_count
LDAT_HEADER = "<IIIiI"    # magic, lid, zone_spawn, path_idx_spawn, unk_10
LDAT_IMAGE_SIZE = 0xF5F8


def eid_to_str(eid):
    """an entry id as its 5 character name, as NSEIDToString does"""
    if not eid & 1:
        return "[%X]" % eid
    eid >>= 1
    name = ""
    for _ in range(5):
        name = ALPHA[eid & 0x3F] + name
        eid >>= 6
    return name


def str_to_eid(name):
    """the entry id for a 5 character name"""
    eid = 0
    for c in name:
        eid = (eid << 6) | ALPHA.index(c)
    return (eid << 1) | 1


class Ldat:
    """the level header at the end of the nsd"""
    def __init__(self, magic, lid, zone_spawn, path_idx_spawn, unk_10, exec_map, fov, image):
        self.magic = magic
        self.lid = lid
        self.zone_spawn = zone_spawn
        self.path_idx_spawn = path_idx_spawn
        self.unk_10 = unk_10
        self.exec_map = exec_map
        self.fov = fov
        self.image = image


class Nsd:
    def __init__(self):
        self.ptb_offsets = []
        self.page_count = 0
        self.ldat_eid = 0
        self.has_loading_image = 0
        self.loading_image_width = 0
        self.loading_image_height = 0
        self.pages_offset = 0
        self.page_table = []  # (pgid, eid) pairs, grouped by eid hash
        self.ldat = None


def read_nsd(data):
    nsd = Nsd()
    nsd.ptb_offsets = list(struct.unpack_from("<%dI" % NSD_PTB_COUNT, data, 0))
    off = 4 * NSD_PTB_COUNT
    (nsd.page_count, table_size, nsd.ldat_eid, nsd.has_loading_image,
     nsd.loading_image_width, nsd.loading_image_height, nsd.pages_offset,
     _compressed_count) = struct.unpack_from(NSD_HEADER, data, off)
    off += struct.calcsize(NSD_HEADER) + 4 * NSD_COMPRESSED_PAGE_COUNT
    for i in range(table_size):
        nsd.page_table.append(struct.unpack_from("<II", data, off + 8 * i))
    off += 8 * table_size
    header = struct.unpack_from(LDAT_HEADER, data, off)
    off += struct.calcsize(LDAT_HEADER)
    exec_map = list(struct.unpack_from("<%dI" % NSD_EXEC_COUNT, data, off))
    off += 4 * NSD_EXEC_COUNT
    fov = struct.unpack_from("<I", data, off)[0]
    image = data[off + 4:off + 4 + LDAT_IMAGE_SIZE]
    nsd.ldat = Ldat(*header, exec_map, fov, image)
    return nsd


class Entry:
    def __init__(self, eid, type, items):
        self.eid = eid
        self.type = type
        self.items = items  # list of bytes


class Page:
    def __init__(self, type, pgid=0, eid=0, entries=None, data=b""):
        self.type = type
        self.pgid = pgid        # for entry pages
        self.eid = eid          # for texture pages
        self.entries = entries or []
        self.data = data        # whole page, for pages that aren't entry pages


def read_entry(data, off):
    magic, eid, etype, item_count = struct.unpack_from("<IIii", data, off)
    if magic != MAGIC_ENTRY:
        raise ValueError("bad entry magic %x at %x" % (magic, off))
    offsets = struct.unpack_from("<%dI" % (item_count + 1), data, off + 16)
    items = [bytes(data[off + offsets[i]:off + offsets[i + 1]]) for i in range(item_count)]
    return Entry(eid, etype, items)


def read_page(data):
    magic, ptype = struct.unpack_from("<HH", data, 0)
    if magic != MAGIC_PAGE:
        raise ValueError("bad page magic %x" % magic)
    if ptype == PAGE_TEXTURE:  # one texture, named by its own eid
        eid = struct.unpack_from("<I", data, 4)[0]
        return Page(ptype, eid=eid, data=bytes(data))
    # entry pages (0) and audio pages (3, 4) hold entries the same way
    pgid, count = struct.unpack_from("<II", data, 4)
    offsets = struct.unpack_from("<%dI" % (count + 1), data, 16)
    entries = [read_entry(data, offsets[i]) for i in range(count)]
    return Page(ptype, pgid=pgid, entries=entries, data=bytes(data))


def read_pages(nsf, page_count, pages_offset=0):
    """the uncompressed pages, which start pages_offset sectors into the nsf"""
    start = pages_offset * SECTOR_SIZE
    return [read_page(nsf[start + i * PAGE_SIZE:start + (i + 1) * PAGE_SIZE])
            for i in range(page_count)]


class Level:
    def __init__(self, nsd, pages):
        self.nsd = nsd
        self.pages = pages


def stream_name(lid, ext):
    return "s%07x.%s" % (lid, ext)


def read_level(streams_dir, lid):
    with open(os.path.join(streams_dir, stream_name(lid, "nsd")), "rb") as f:
        nsd = read_nsd(f.read())
    with open(os.path.join(streams_dir, stream_name(lid, "nsf")), "rb") as f:
        pages = read_pages(f.read(), nsd.page_count, nsd.pages_offset)
    return Level(nsd, pages)


def type_name(etype):
    return TYPE_NAMES.get(etype, str(etype))


def count_by_type(pages):
    """number of entries of each type; texture pages count as TPAG"""
    counts = {}
    for page in pages:
        names = ["TPAG"] if page.type == PAGE_TEXTURE else [type_name(e.type) for e in page.entries]
        for name in names:
            counts[name] = counts.get(name, 0) + 1
    return counts
