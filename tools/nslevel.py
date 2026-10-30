"""
Read (and later write) the game's level files: a level is an .nsd (page
table and level header) and an .nsf (64 KB pages of entries).

The layouts mirror the structs in src/ns.h, which the game loads as is.
"""
import copy
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


def read_level_files(path):
    """read path.nsd and path.nsf"""
    with open(path + ".nsd", "rb") as f:
        nsd = read_nsd(f.read())
    with open(path + ".nsf", "rb") as f:
        pages = read_pages(f.read(), nsd.page_count, nsd.pages_offset)
    return Level(nsd, pages)


def pgid(index):
    """the page id the loader gives the page at index (see NSInit)"""
    return (index << 1) | 1


def entry_bytes(entry):
    """an entry: header, item offsets relative to the entry, then the items"""
    offset = 16 + 4 * (len(entry.items) + 1)
    offsets = []
    for item in entry.items:
        offsets.append(offset)
        offset += len(item)
    offsets.append(offset)
    data = struct.pack("<IIii", MAGIC_ENTRY, entry.eid, entry.type, len(entry.items))
    return data + struct.pack("<%dI" % len(offsets), *offsets) + b"".join(entry.items)


def entry_page_bytes(entries, index):
    """a 64 KB page holding entries; raises ValueError if they don't fit"""
    blobs = [entry_bytes(e) for e in entries]
    offset = 16 + 4 * (len(blobs) + 1)
    offsets = []
    for blob in blobs:
        offsets.append(offset)
        offset += len(blob)
    offsets.append(offset)
    if offset > PAGE_SIZE:
        raise ValueError("entries take %d bytes, more than a page" % offset)
    data = struct.pack("<HHIII", MAGIC_PAGE, PAGE_ENTRIES, pgid(index), len(blobs), 0)
    data += struct.pack("<%dI" % len(offsets), *offsets) + b"".join(blobs)
    return data.ljust(PAGE_SIZE, b"\0")


def page_bytes(page, index):
    if page.type == PAGE_ENTRIES:
        return entry_page_bytes(page.entries, index)
    return page.data  # texture and audio pages are kept as they are


def eid_bucket(eid):
    return (eid >> 15) & 0xFF


def page_table(pages):
    """(pgid, eid) for every entry and texture page, grouped by bucket, and
    the offset of each bucket's first entry (NSProbe scans on from there)"""
    table = []
    for index, page in enumerate(pages):
        eids = [page.eid] if page.type == PAGE_TEXTURE else [e.eid for e in page.entries]
        table += [(pgid(index), eid) for eid in eids]
    table.sort(key=lambda pte: eid_bucket(pte[1]))
    ptb_offsets = [sum(1 for _, eid in table if eid_bucket(eid) < b) for b in range(NSD_PTB_COUNT)]
    return table, ptb_offsets


def nsd_bytes(nsd, pages):
    table, ptb_offsets = page_table(pages)
    data = struct.pack("<%dI" % NSD_PTB_COUNT, *ptb_offsets)
    data += struct.pack(NSD_HEADER, len(pages), len(table), nsd.ldat_eid,
                        nsd.has_loading_image, nsd.loading_image_width,
                        nsd.loading_image_height, 0, 0)  # pages start the nsf, none compressed
    data += struct.pack("<%dI" % NSD_COMPRESSED_PAGE_COUNT, *([0] * NSD_COMPRESSED_PAGE_COUNT))
    for pte in table:
        data += struct.pack("<II", *pte)
    ldat = nsd.ldat
    data += struct.pack(LDAT_HEADER, ldat.magic, ldat.lid, ldat.zone_spawn,
                        ldat.path_idx_spawn, ldat.unk_10)
    data += struct.pack("<%dI" % NSD_EXEC_COUNT, *ldat.exec_map)
    data += struct.pack("<I", ldat.fov) + ldat.image.ljust(LDAT_IMAGE_SIZE, b"\0")
    return data


def write_level(level, out_dir, name):
    """write out_dir/name.nsd and out_dir/name.nsf"""
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, name)
    with open(base + ".nsf", "wb") as f:
        for index, page in enumerate(level.pages):
            f.write(page_bytes(page, index))
    with open(base + ".nsd", "wb") as f:
        f.write(nsd_bytes(level.nsd, level.pages))


# exec map slots CoreObjectsCreate opens for every normal level: crash,
# fruit, hud, DoctC, shadow and boxes (src/main.c)
CORE_EXEC_SLOTS = [0, 3, 4, 5, 29, 34]


def references(entry, eids):
    """the eids (of those given) that entry's items mention: any aligned
    word that equals one counts, which may keep something unneeded but never
    drops something needed"""
    found = set()
    for item in entry.items:
        count = len(item) // 4
        found.update(w for w in struct.unpack_from("<%dI" % count, item) if w in eids)
    return found


def page_size(entries):
    return 16 + 4 * (len(entries) + 1) + sum(len(entry_bytes(e)) for e in entries)


def pack_entries(entries):
    """entry pages holding entries, in order, starting a new page when one
    is full. each page lists its entries in bucket order, since the loader
    (NSPageUpdateEntries) finds them by scanning the page table forward from
    the bucket of the page's first entry"""
    pages, current = [], []
    for entry in entries:
        if current and page_size(current + [entry]) > PAGE_SIZE:
            pages.append(current)
            current = []
        current.append(entry)
    if current:
        pages.append(current)
    return [Page(PAGE_ENTRIES, entries=sorted(p, key=lambda e: eid_bucket(e.eid))) for p in pages]


def cut_level(level, keep):
    """a copy of level with only the entries reachable from the eids in keep
    (texture and audio pages are kept whole if anything in them is used),
    repacked into as few pages as they fit"""
    entries = {e.eid: e for p in level.pages for e in p.entries}
    page_of = {}
    for page in level.pages:
        if page.type == PAGE_TEXTURE:
            page_of[page.eid] = page
        elif page.type != PAGE_ENTRIES:
            for e in page.entries:
                page_of[e.eid] = page
    all_eids = set(entries) | set(page_of)
    kept, todo = set(), [eid for eid in keep if eid in all_eids]
    while todo:
        eid = todo.pop()
        if eid in kept:
            continue
        kept.add(eid)
        if eid in entries:
            todo += references(entries[eid], all_eids) - kept
    raw_pages = [p for p in level.pages if p.type != PAGE_ENTRIES
                 and (p.eid in kept if p.type == PAGE_TEXTURE else any(e.eid in kept for e in p.entries))]
    kept_entries = [e for p in level.pages if p.type == PAGE_ENTRIES
                    for e in p.entries if e.eid in kept]
    nsd = copy.deepcopy(level.nsd)
    nsd.ldat.exec_map = [e if e in kept else EID_NONE for e in nsd.ldat.exec_map]
    return Level(nsd, pack_entries(kept_entries) + raw_pages)


# zone header layout (zone_header in src/formats/zdat.h)
ZONE_WORLD_SIZE = 64        # eid, trans, 4 pointers, 8 tpages
ZONE_PATHS_IDX = 4 + 8 * ZONE_WORLD_SIZE   # then path_count, entity_count, neighbor_count
ZONE_NEIGHBORS = ZONE_PATHS_IDX + 16
ZONE_LOADLIST = ZONE_NEIGHBORS + 32
ZONE_DISPLAY_FLAGS = ZONE_LOADLIST + 168
ZONE_MIDI = ZONE_DISPLAY_FLAGS + 4 + 36
ZONE_HEADER_SIZE = 888


OCTREE_NODES = 36    # zone_rect: x y z w h d unk, then root and max depths
LEAF_GROUND = 1      # leaf (low bit) with value 0: plain solid ground
FLOOR_CELL_MAX = 1024  # largest floor cell (zone units); see floor_rect_bytes


def pad4(data):
    return data + b"\0" * (-len(data) % 4)


def split_depth(size):
    """how many times to halve size to get cells of at most FLOOR_CELL_MAX"""
    depth = 0
    while size >> depth > FLOOR_CELL_MAX:
        depth += 1
    return depth


def floor_rect_bytes(x, y, z, w, h, d, depth):
    """zone bounds (zone units) and an octree whose bottom layer of cells is
    solid ground and everything above it empty, splitting along y depth
    times, so the floor's top is floor_top(h, depth) above the zone's bottom.

    it also splits along x and z until cells are at most FLOOR_CELL_MAX
    across: ZoneQueryOctree stores a cell's position relative to the query
    point as int16 (>> 4), so a cell much bigger than that is misplaced.
    every column is the same, so each level is one child array that all the
    lower children share."""
    mx, mz = split_depth(w), split_depth(d)
    levels = max(mx, depth, mz)
    nodes = b""
    for level in range(levels):
        fx, fy, fz = level < mx, level < depth, level < mz
        child = OCTREE_NODES + len(nodes) + 2 * (1 + fx) * (1 + fy) * (1 + fz)
        child += child % 4  # keep the next array aligned
        if level == levels - 1:
            child = LEAF_GROUND
        children = []
        for i in range(1 + fx):
            for j in range(1 + fy):
                for k in range(1 + fz):
                    children.append(0 if fy and j else child)  # upper y half empty
        nodes += struct.pack("<%dH" % len(children), *children)
        nodes = pad4(nodes)
    root = OCTREE_NODES if levels else LEAF_GROUND
    data = struct.pack("<iiiIIII", x, y, z, w, h, d, 0)
    data += struct.pack("<4H", root, mx, depth, mz) + nodes
    return pad4(data)


def floor_top(h, depth):
    return h >> depth


def zone_header_bytes(template, self_eid, worlds, path_count, entity_count):
    """a zone header from a real one, with the given worlds ((wgeo eid,
    (x, y, z)) pairs), its own paths and entities, itself as its only
    neighbor, an empty load list and no music"""
    h = bytearray(template)
    struct.pack_into("<I", h, 0, len(worlds))
    for i in range(8):
        world = b"\0" * ZONE_WORLD_SIZE
        if i < len(worlds):
            eid, trans = worlds[i]
            world = struct.pack("<I3i", eid, *trans).ljust(ZONE_WORLD_SIZE, b"\0")
        h[4 + i * ZONE_WORLD_SIZE:4 + (i + 1) * ZONE_WORLD_SIZE] = world
    struct.pack_into("<4I", h, ZONE_PATHS_IDX, 2, path_count, entity_count, 1)
    struct.pack_into("<8I", h, ZONE_NEIGHBORS, self_eid, *([0] * 7))
    h[ZONE_LOADLIST:ZONE_DISPLAY_FLAGS] = b"\0" * (ZONE_DISPLAY_FLAGS - ZONE_LOADLIST)
    struct.pack_into("<I", h, ZONE_DISPLAY_FLAGS, 0)
    struct.pack_into("<I", h, ZONE_MIDI, EID_NONE)
    return bytes(h)


def path_bytes(slst, points, cam_mode, zoom, avg_node_dist, direction=(0, 0, 0)):
    """a camera path with no neighbors; points are (x, y, z, rot_y, rot_x,
    rot_z) in zone units"""
    data = struct.pack("<III", slst, 0, 0) + b"\0" * 16
    data += struct.pack("<BBHHhh", 0, 0, len(points), cam_mode, avg_node_dist, zoom)
    data += struct.pack("<3h3h", 0, 0, 0, *direction)
    for point in points:
        data += struct.pack("<6h", *point)
    return pad4(data)


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


LID_TEST = 0x1  # custom levels use the test level id (see src/common.h)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STREAMS_DIR = os.path.join(ROOT, "streams")
CUSTOM_LEVELS_DIR = os.path.join(ROOT, "custom_levels")

USAGE = """usage:
  python tools/nslevel.py list <lid>         list a level's entries by type
  python tools/nslevel.py copy <lid> <name>  copy a level to custom_levels/<name>
  (lid is the hex level id, e.g. 9 for N. Sanity Beach)"""


def main(argv):
    if len(argv) >= 2 and argv[0] == "list":
        level = read_level(STREAMS_DIR, int(argv[1], 16))
        for name, count in sorted(count_by_type(level.pages).items()):
            print("%s %d" % (name, count))
        print("exec map: %s" % " ".join(eid_to_str(e) for e in level.nsd.ldat.exec_map
                                       if e != EID_NONE))
        return 0
    if len(argv) >= 3 and argv[0] == "copy":
        level = read_level(STREAMS_DIR, int(argv[1], 16))
        level.nsd.ldat.lid = LID_TEST
        write_level(level, CUSTOM_LEVELS_DIR, argv[2])
        print("wrote %s" % os.path.join(CUSTOM_LEVELS_DIR, argv[2]))
        return 0
    print(USAGE)
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
