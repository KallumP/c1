"""
Read (and later write) the game's level files: a level is an .nsd (page
table and level header) and an .nsf (64 KB pages of entries).

The layouts mirror the structs in src/ns.h, which the game loads as is.
"""
import copy
import os
import struct

import blendmap

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


class EntryTooBig(ValueError):
    def __init__(self, entry):
        super().__init__("%s takes %d bytes, more than a page" % (eid_to_str(entry.eid), page_size([entry])))
        self.entry = entry


def pack_entries(entries):
    """entry pages holding entries, in order, starting a new page when one
    is full. each page lists its entries in bucket order, since the loader
    (NSPageUpdateEntries) finds them by scanning the page table forward from
    the bucket of the page's first entry"""
    pages, current = [], []
    for entry in entries:
        if page_size([entry]) > PAGE_SIZE:
            raise EntryTooBig(entry)
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


ZONE_LOADLIST_PAGES_MAX = 32


def load_texture_pages(level, zone_eid):
    """make the zone's load list open every texture page in level: LevelUpdate
    opens the pages in it (NSPageOpen), which is what puts a texture page in
    vram, so a texture page nothing opens leaves the models using it blank.
    page ids depend on where pages are, so this is done once they're laid out"""
    pgids = [pgid(i) for i, page in enumerate(level.pages) if page.type == PAGE_TEXTURE]
    if len(pgids) > ZONE_LOADLIST_PAGES_MAX:
        raise ValueError("%d texture pages, more than a load list holds" % len(pgids))
    zone = next(e for p in level.pages for e in p.entries if e.eid == zone_eid)
    header = bytearray(zone.items[0])
    struct.pack_into("<ii", header, ZONE_LOADLIST, 0, len(pgids))
    struct.pack_into("<%dI" % ZONE_LOADLIST_PAGES_MAX, header, ZONE_LOADLIST + 8 + 32,
                     *(pgids + [0] * (ZONE_LOADLIST_PAGES_MAX - len(pgids))))
    zone.items[0] = bytes(header)


OCTREE_NODES = 36    # zone_rect: x y z w h d unk, then root and max depths
LEAF_GROUND = 1      # leaf (low bit) with value 0: plain solid ground
LEAF_FLOOR = 3       # leaf of type 1, floor: crash can step up onto it (by up to land_offset in
                     # src/solid.c, about 244), unlike ground (FindFloorY counts that as a wall)
LEAF_PIT = (11 << 4) | 1  # leaf with subtype 11: kills what falls on it (ProcessNode in src/solid.c)
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


def log2_exact(n, what):
    depth = n.bit_length() - 1
    if n <= 0 or 1 << depth != n:
        raise ValueError("%s (%d) has to be a power of two times the cell size" % (what, n))
    return depth


def blocks_rect_bytes(origin, size, blocks, cell):
    """zone bounds and a collision octree where the given blocks are solid
    and the rest is empty. size (w, h, d) and the blocks ((x0, y0, z0, x1,
    y1, z1), zone units relative to origin, optionally followed by the leaf
    to use, LEAF_GROUND by default; later blocks win where they overlap)
    have to be on a grid of cell sized cells, and each side of size a power
    of two times cell.

    a region is split where its cells differ, and a solid region is also
    split while it's wider than FLOOR_CELL_MAX (see floor_rect_bytes); the
    same subtree is only stored once, so large regions cost nothing"""
    w, h, d = size
    nx, ny, nz = w // cell, h // cell, d // cell
    mx, my, mz = log2_exact(nx, "w"), log2_exact(ny, "h"), log2_exact(nz, "d")
    if (nx * cell, ny * cell, nz * cell) != (w, h, d):
        raise ValueError("size has to be a multiple of the cell size")
    grid = [[[0] * nz for _ in range(ny)] for _ in range(nx)]
    for block in blocks:
        box, leaf = block[:6], (block[6] if len(block) > 6 else LEAF_GROUND)
        if any(v % cell for v in box) or not (0 <= box[0] < box[3] <= w and
                                              0 <= box[1] < box[4] <= h and
                                              0 <= box[2] < box[5] <= d):
            raise ValueError("block %r isn't on the %d grid inside the zone" % (block, cell))
        for i in range(box[0] // cell, box[3] // cell):
            for j in range(box[1] // cell, box[4] // cell):
                for k in range(box[2] // cell, box[5] // cell):
                    grid[i][j][k] = leaf

    # prefix sums of each leaf's cells, so a region's makeup is a lookup
    def prefix_sums(leaf):
        sums = [[[0] * (nz + 1) for _ in range(ny + 1)] for _ in range(nx + 1)]
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    sums[i + 1][j + 1][k + 1] = ((grid[i][j][k] == leaf) + sums[i][j + 1][k + 1]
                                                 + sums[i + 1][j][k + 1] + sums[i + 1][j + 1][k]
                                                 - sums[i][j][k + 1] - sums[i][j + 1][k]
                                                 - sums[i + 1][j][k] + sums[i][j][k])
        return sums
    leaves = {leaf: prefix_sums(leaf) for leaf in {b[6] if len(b) > 6 else LEAF_GROUND for b in blocks}}

    def count(sums, i0, j0, k0, i1, j1, k1):
        return (sums[i1][j1][k1] - sums[i0][j1][k1] - sums[i1][j0][k1] - sums[i1][j1][k0]
                + sums[i0][j0][k1] + sums[i0][j1][k0] + sums[i1][j0][k0] - sums[i0][j0][k0])

    nodes = bytearray()
    shared = {}

    def build(level, i0, j0, k0, ni, nj, nk):
        total = ni * nj * nk
        counts = {leaf: count(sums, i0, j0, k0, i0 + ni, j0 + nj, k0 + nk)
                  for leaf, sums in leaves.items()}
        if not any(counts.values()):
            return 0
        uniform = [leaf for leaf, n in counts.items() if n == total]
        if uniform and ni * cell <= FLOOR_CELL_MAX and nk * cell <= FLOOR_CELL_MAX:
            return uniform[0]
        fx, fy, fz = level < mx, level < my, level < mz
        si, sj, sk = (ni // 2 if fx else ni), (nj // 2 if fy else nj), (nk // 2 if fz else nk)
        children = tuple(build(level + 1, i0 + i * si, j0 + j * sj, k0 + k * sk, si, sj, sk)
                         for i in range(1 + fx) for j in range(1 + fy) for k in range(1 + fz))
        if children not in shared:
            shared[children] = OCTREE_NODES + len(nodes)
            nodes.extend(pad4(struct.pack("<%dH" % len(children), *children)))
            if shared[children] > 0xFFFF:
                raise ValueError("octree is too big for 16 bit node offsets")
        return shared[children]

    root = build(0, 0, 0, 0, nx, ny, nz)
    data = struct.pack("<iiiIIII", origin[0], origin[1], origin[2], w, h, d, 0)
    return pad4(data + struct.pack("<4H", root, mx, my, mz) + bytes(nodes))


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


# world meshes (wgeo, see src/formats/wgeo.h; its bitfield macros list fields
# high bits first)

def world_vertex_bytes(x, y, z, color):
    """a vertex at (x, y, z) relative to its mesh, in zone units (multiples
    of 8, within -32768..32760), and its colour"""
    x, y, z = x // 8, y // 8, z // 8
    h0 = ((x & 0x1FFF) << 3) | (((z >> 8) & 3) << 1)   # x:13, z2:2, fx:1
    h1 = ((y & 0x1FFF) << 3) | ((z >> 10) & 7)          # y:13, z3:3
    return struct.pack("<BBBBHH", color[0], color[1], color[2], z & 0xFF, h0, h1)


def world_polygon_bytes(a, b, c, tinf, tpag):
    """a triangle of vertex indices a, b, c with texture info tinf (a word
    index into the mesh's texinfos) on texture page tpag, not animated"""
    w0 = (c << 20) | (tinf << 8) | (tpag << 5)   # c, tinf, tpag, anim_phase
    w1 = (a << 20) | (b << 8)                    # a, b, anim_period, anim_mask
    return struct.pack("<II", w0, w1)


def floor_grid(w, d, cell):
    """a flat w by d grid of cell sized squares at y 0: vertices (x, y, z)
    and triangles (a, b, c), two per square"""
    nx, nz = w // cell, d // cell
    verts = [(i * cell, 0, k * cell) for k in range(nz + 1) for i in range(nx + 1)]
    polys = []
    for k in range(nz):
        for i in range(nx):
            v = k * (nx + 1) + i
            polys += [(v, v + 1, v + nx + 1), (v + 1, v + nx + 2, v + nx + 1)]
    return verts, polys


WGEO_MAX = 4096  # polygon and vertex indices are 12 bits


def pieces(start, end, piece):
    """split start..end into pieces at most piece long"""
    edges = list(range(start, end, piece)) + [end]
    return list(zip(edges, edges[1:]))


def blocks_mesh(blocks, top_texture, side_texture, piece):
    """a world mesh for blocks ((x0, y0, z0, x1, y1, z1), zone units): each
    block's top and four sides, split into squares at most piece across so
    the sort list can drop the ones behind the camera a little at a time.
    returns vertices (x, y, z) and triangles (a, b, c, tinf, tpag), with
    top_texture and side_texture as (tinf, tpag)"""
    verts, polys = [], []

    def quad(corners, texture):
        # corners in order a, b, c, d around the square: triangles abd, bcd
        base = len(verts)
        verts.extend(corners)
        polys.append((base, base + 1, base + 3) + texture)
        polys.append((base + 1, base + 2, base + 3) + texture)

    for x0, y0, z0, x1, y1, z1 in blocks:
        for xa, xb in pieces(x0, x1, piece):
            for za, zb in pieces(z0, z1, piece):
                quad([(xa, y1, za), (xb, y1, za), (xb, y1, zb), (xa, y1, zb)], top_texture)
        for ya, yb in pieces(y0, y1, piece):
            for za, zb in pieces(z0, z1, piece):  # the two sides along z
                for x in (x0, x1):
                    quad([(x, ya, za), (x, ya, zb), (x, yb, zb), (x, yb, za)], side_texture)
            for xa, xb in pieces(x0, x1, piece):  # the two ends
                for z in (z0, z1):
                    quad([(xa, ya, z), (xb, ya, z), (xb, yb, z), (xa, yb, z)], side_texture)
    if len(verts) > WGEO_MAX or len(polys) > WGEO_MAX:
        raise ValueError("mesh has %d vertices and %d polygons, more than %d"
                         % (len(verts), len(polys), WGEO_MAX))
    return verts, polys


WGEO_HEADER = "<iiiIIIII"  # trans x y z, poly, vert, texinfo and tpag counts, is_backdrop


def world_header_bytes(template, trans, poly_count, vert_count):
    """a mesh header from a real one (keeping its texture pages and
    texinfos), placed at trans (zone units) with new counts"""
    fields = list(struct.unpack_from(WGEO_HEADER, template, 0))
    fields[0:5] = [trans[0], trans[1], trans[2], poly_count, vert_count]
    return struct.pack(WGEO_HEADER, *fields) + template[struct.calcsize(WGEO_HEADER):]


# sort lists (slst, see src/formats/slst.h and src/slst.c)

def poly_id(world_idx, poly_idx):
    return (world_idx << 12) | poly_idx  # flag:1, world_idx:3, poly_idx:12


POLY_IDS_MAX = 1460  # polygons the game can list (SlstInit in src/slst.c)


def slst_items(world_zmax, cam_zs, step, near):
    """a sort list for a camera path along -z (cameras at z cam_zs): for each
    point, the polygons (of each world, by their largest z, one list per
    world) that stay in front of the camera all the way to the next point,
    so none is ever drawn from behind the camera, which the renderer would
    project mirrored. a list holds at most the POLY_IDS_MAX nearest.

    every item is a full list rather than a delta (the game copies an even
    type item as is, whichever way the camera moves). LevelUpdate reads
    item k on reaching point k, and item N (one past the last point) when
    starting in the second half of the path, so that repeats the last."""
    def full_list(cam_z):
        front = [(zmax, poly_id(w, i)) for w, poly_zmax in enumerate(world_zmax)
                 for i, zmax in enumerate(poly_zmax) if zmax < cam_z - step - near]
        if len(front) > POLY_IDS_MAX:  # too many to list: leave out the farthest
            front = sorted(front, key=lambda f: -f[0])[:POLY_IDS_MAX]
        ids = sorted(f[1] for f in front)
        return pad4(struct.pack("<HH%dH" % len(ids), len(ids), 0, *ids))
    items = [full_list(z) for z in cam_zs]
    return items + [items[-1]]


# entities (zone_entity in src/formats/zdat.h): parent zone, spawn flags,
# group, id, point count, 3 init flags, type, subtype, then the points, in
# units of 4 zone units relative to the zone
ENTITY_SPAWN_FLAGS = 4
ENTITY_ID = 8
ENTITY_POINT_COUNT = 10
ENTITY_TYPE = 18
ENTITY_POINTS = 20
ENTITY_ID_MAX = 303  # ids index the spawn table (GOOL_SPAWN_COUNT in src/gool.h)
ENTITY_PLAIN_LIGHT = 0x18  # spawn_flags >> 3 is a lighting region in the zone's octree
                           # (ZoneColorsScaleSeekByEntityNode); crash's points at plain light


def entity_type(item):
    """an entity's type (its exec map slot) and subtype"""
    return item[ENTITY_TYPE], item[ENTITY_TYPE + 1]


def place_entity(item, entity_id, pos):
    """a copy of a real entity with a new id, moved so its first point is at
    pos (zone units relative to the zone); a path (such as a crab's patrol)
    keeps its shape. it is lit plainly, like crash, since the lighting
    region it pointed at in its own zone isn't in this one"""
    if not 0 < entity_id <= ENTITY_ID_MAX:
        raise ValueError("entity id %d is outside 1..%d" % (entity_id, ENTITY_ID_MAX))
    data = bytearray(item)
    count = struct.unpack_from("<H", data, ENTITY_POINT_COUNT)[0]
    points = [struct.unpack_from("<3h", data, ENTITY_POINTS + 6 * i) for i in range(count)]
    offset = [pos[i] // 4 - points[0][i] for i in range(3)]
    for i, point in enumerate(points):
        struct.pack_into("<3h", data, ENTITY_POINTS + 6 * i, *(point[a] + offset[a] for a in range(3)))
    struct.pack_into("<H", data, ENTITY_ID, entity_id)
    flags = struct.unpack_from("<H", data, ENTITY_SPAWN_FLAGS)[0]
    struct.pack_into("<H", data, ENTITY_SPAWN_FLAGS, (flags & 7) | ENTITY_PLAIN_LIGHT)
    return bytes(data)


# the mock level

MOCK_SIZE = (4096, 3200, 8192)   # zone w, h, d (zone units)
MOCK_FLOOR_DEPTH = 3             # floor top at h >> 3 = 400
MOCK_CELL = 512                  # floor grid squares
MOCK_CAM = (101, 1316)           # follow camera offset from crash: x, height (as on the beach)
MOCK_PATH_STEP = 80              # distance between camera path points (the sort list
                                 # has a list per point, and has to fit in a page)
MOCK_NEAR = 64                   # how far in front of the camera a polygon has to be


def most_used_texture(world):
    """(tinf, tpag) that most of a mesh's polygons use"""
    counts = {}
    for i in range(len(world.items[1]) // 8):
        w0 = struct.unpack_from("<I", world.items[1], 8 * i)[0]
        key = ((w0 >> 8) & 0xFFF, (w0 >> 5) & 7)
        counts[key] = counts.get(key, 0) + 1
    return max(counts, key=counts.get)


def make_mock(level):
    """a level from scratch: one zone with a flat floor, a straight follow
    camera path, and crash; with crash, the hud and core objects (and the
    floor's texture) taken from level, a real level such as N. Sanity Beach"""
    entries = {e.eid: e for p in level.pages for e in p.entries}
    template = entries[level.nsd.ldat.zone_spawn]
    header = template.items[0]
    paths_idx, path_count, _, _ = struct.unpack_from("<4I", header, ZONE_PATHS_IDX)
    crash = next(item for item in template.items[paths_idx + path_count:]
                 if item[18] == 0)  # entity type 0, crash (exec map slot 0)
    worlds = [entries[struct.unpack_from("<I", header, 4 + i * ZONE_WORLD_SIZE)[0]]
              for i in range(struct.unpack_from("<I", header, 0)[0])]
    floor_template = max((w for w in worlds if not struct.unpack_from("<I", w.items[0], 28)[0]),
                         key=lambda w: len(w.items[1]))  # biggest non-backdrop mesh
    tinf, tpag = most_used_texture(floor_template)

    zone_eid, world_eid, slst_eid = str_to_eid("MockZ"), str_to_eid("MockW"), str_to_eid("MockS")
    x0, y0, z0 = struct.unpack_from("<iii", template.items[1], 0)
    w, h, d = MOCK_SIZE
    top = floor_top(h, MOCK_FLOOR_DEPTH)

    verts, polys = floor_grid(w, d, MOCK_CELL)
    world = Entry(world_eid, 3, [
        world_header_bytes(floor_template.items[0], (x0, y0 + top, z0), len(polys), len(verts)),
        b"".join(world_polygon_bytes(a, b, c, tinf, tpag) for a, b, c in polys),
        b"".join(world_vertex_bytes(x, y, z, (128, 128, 128)) for x, y, z in verts)])

    crash_x, crash_z = w // 2, d - 1700
    cam_x, cam_y = crash_x + MOCK_CAM[0], top + MOCK_CAM[1]
    points = [(cam_x, cam_y, z, -181, 1, 0) for z in range(d - 200, 200, -MOCK_PATH_STEP)]
    path = path_bytes(slst_eid, points, cam_mode=5, zoom=1700, avg_node_dist=MOCK_PATH_STEP,
                      direction=(0, 0, -4096))
    poly_zmax = [max(verts[a][2], verts[b][2], verts[c][2]) for a, b, c in polys]
    slst = Entry(slst_eid, 4, slst_items([poly_zmax], [p[2] for p in points], MOCK_PATH_STEP, MOCK_NEAR))

    crash = bytearray(crash)  # entity location is in units of 4 zone units
    struct.pack_into("<3h", crash, 20, crash_x // 4, (top + 100) // 4, crash_z // 4)
    zone = Entry(zone_eid, 7, [
        zone_header_bytes(header, zone_eid, [(world_eid, (x0, y0 + top, z0))], 1, 1),
        floor_rect_bytes(x0, y0, z0, w, h, d, MOCK_FLOOR_DEPTH),
        path,
        bytes(crash)])

    tpags = struct.unpack_from("<8I", floor_template.items[0], 32)
    keep = [level.nsd.ldat.exec_map[i] for i in CORE_EXEC_SLOTS] + [t for t in tpags if t]
    mock = cut_level(level, keep)
    mock.pages = pack_entries([zone, world, slst]) + mock.pages
    mock.nsd.ldat.lid = LID_TEST
    mock.nsd.ldat.zone_spawn = zone_eid
    mock.nsd.ldat.path_idx_spawn = 0
    load_texture_pages(mock, zone_eid)
    return mock


# shared by the custom levels

def used_textures(world):
    """(tinf, tpag) pairs a mesh's polygons use, most used first"""
    counts = {}
    for i in range(len(world.items[1]) // 8):
        w0 = struct.unpack_from("<I", world.items[1], 8 * i)[0]
        key = ((w0 >> 8) & 0xFFF, (w0 >> 5) & 7)
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts, key=counts.get, reverse=True)


class Templates:
    """what custom levels take from a real level: its spawn zone (header
    settings, origin), crash's entity, its biggest world mesh (for textures),
    and an example of each kind of entity (by type and subtype)"""
    def __init__(self, level):
        entries = {e.eid: e for p in level.pages for e in p.entries}
        zone = entries[level.nsd.ldat.zone_spawn]
        self.header = zone.items[0]
        self.origin = struct.unpack_from("<iii", zone.items[1], 0)
        worlds = [entries[struct.unpack_from("<I", self.header, 4 + i * ZONE_WORLD_SIZE)[0]]
                  for i in range(struct.unpack_from("<I", self.header, 0)[0])]
        self.world = max((w for w in worlds if not struct.unpack_from("<I", w.items[0], 28)[0]),
                         key=lambda w: len(w.items[1]))  # biggest non-backdrop mesh
        self.textures = used_textures(self.world)
        self.entities = {}
        for e in entries.values():
            if e.type != 7:  # zones
                continue
            paths_idx, path_count, entity_count, _ = struct.unpack_from("<4I", e.items[0], ZONE_PATHS_IDX)
            for item in e.items[paths_idx + path_count:paths_idx + path_count + entity_count]:
                self.entities.setdefault(entity_type(item), item)
        self.crash = self.entities[(0, 0)]


GREY = (128, 128, 128)  # unshaded vertex colour


def assemble_level(level, templates, prefix, size, blocks, worlds, points, step, entities):
    """a custom level from a real level: one zone of size (w, h, d) at the
    template zone's origin, with collision from blocks, world meshes (each
    vertices (x, y, z, colour) and polygons (a, b, c, tinf, tpag) relative
    to the zone), one follow camera path through points (x, y, z) step
    apart going along -z, and entities (crash first). keeps crash, the hud
    and core objects, and the code for the entities' types, from level"""
    t = templates
    zone_eid, slst_eid = str_to_eid(prefix + "Z"), str_to_eid(prefix + "S")
    world_eids = [str_to_eid(prefix + ("W" if i == 0 else str(i))) for i in range(len(worlds))]
    x0, y0, z0 = t.origin
    world_entries = [Entry(eid, 3, [
        world_header_bytes(t.world.items[0], (x0, y0, z0), len(polys), len(verts)),
        b"".join(world_polygon_bytes(a, b, c, tinf, tpag) for a, b, c, tinf, tpag in polys),
        b"".join(world_vertex_bytes(x, y, z, colour) for x, y, z, colour in verts)])
        for eid, (verts, polys) in zip(world_eids, worlds)]
    cam_points = [(x, y, z, -181, 1, 0) for x, y, z in points]
    path = path_bytes(slst_eid, cam_points, cam_mode=5, zoom=1700,
                      avg_node_dist=step, direction=(0, 0, -4096))
    world_zmax = [[max(verts[a][2], verts[b][2], verts[c][2]) for a, b, c, _, _ in polys]
                  for verts, polys in worlds]
    slst = Entry(slst_eid, 4, slst_items(world_zmax, [p[2] for p in points], step, MOCK_NEAR))
    zone = Entry(zone_eid, 7, [
        zone_header_bytes(t.header, zone_eid, [(eid, (x0, y0, z0)) for eid in world_eids],
                          1, len(entities)),
        blocks_rect_bytes(t.origin, size, blocks, COURSE_CELL),
        path] + list(entities))
    tpags = struct.unpack_from("<8I", t.world.items[0], 32)
    exec_map = level.nsd.ldat.exec_map
    slots = set(CORE_EXEC_SLOTS) | {entity_type(e)[0] for e in entities}
    keep = [exec_map[i] for i in slots] + [tp for tp in tpags if tp]
    out = cut_level(level, keep)
    out.pages = pack_entries([zone, slst] + world_entries) + out.pages
    out.nsd.ldat.lid = LID_TEST
    out.nsd.ldat.zone_spawn = zone_eid
    out.nsd.ldat.path_idx_spawn = 0
    load_texture_pages(out, zone_eid)
    return out


# the course level: an obstacle course along -z (zone units, on a 128 grid)

COURSE_SIZE = (4096, 4096, 8192)
COURSE_CELL = 128
COURSE_PIECE = 512       # mesh squares
COURSE_PATH_STEP = 128   # camera path points; with the pieces, keeps the sort list in a page
COURSE_GROUND = 512      # height of the ground's top
COURSE_LEAD = 1450       # how far ahead of the camera crash is (as on the beach)

# (x0, x1, z0, z1, top): platforms, from the start (high z) to the end
# crash starts COURSE_LEAD in front of the camera path's start, so the start
# platform reaches back to the end of the zone
COURSE_PLATFORMS = [
    (1024, 3072, 5760, 8192, 512),    # start
    (1024, 3072, 4096, 5120, 512),    # after gap 1: a row of boxes
    (1024, 3072, 3712, 4096, 768),    # step up
    (1024, 3072, 3328, 3712, 1024),   # and up again
    (1024, 3072, 2432, 2816, 1024),   # ledge, after gap 2
    (512, 3584, 1408, 2432, 512),     # down to a wide stretch with crabs
    (1024, 3072, 0, 896, 512),        # end, after gap 3: the warp pad
]
COURSE_GAPS = [(1024, 3072, 5120, 5760), (1024, 3072, 2816, 3328), (1024, 3072, 896, 1408)]
COURSE_PIT = 128         # height of the deadly floor under each gap

# BoxsC (exec slot 34) subtypes: 2 plain, 3 arrow (bounce), 4 checkpoint, 5 steel,
# 6 slatted, 7 '!', 8 life, 9 aku aku, 10 '?', 13 outline (appears after a '!' box)
COURSE_BOXES = [(34, 2), (34, 10), (34, 3), (34, 9), (34, 8)]  # in a row
COURSE_BOX_Z = 4480
COURSE_CHECKPOINT = (2048, 3456)              # x, z of a checkpoint box on the top step
COURSE_CRABS = [(2048, 2100), (2048, 1700)]   # centre x, z of each crab's patrol
COURSE_WARP = (2048, 448)                     # x, z of the warp pad
COURSE_CRASH = (2048, 6500)


def course_top(z):
    """the ground's top at z along the middle of the course, or None over a gap"""
    for x0, x1, z0, z1, top in COURSE_PLATFORMS:
        if z0 <= z < z1:
            return top
    return None


def make_course(level):
    """an obstacle course: gaps to jump (with a deadly floor below), steps
    and a ledge, a row of boxes, a checkpoint, crabs, and the warp pad at the end; built
    the same way as make_mock, from level (a real level such as N. Sanity
    Beach) for crash, the objects and the textures"""
    t = Templates(level)
    w, h, d = COURSE_SIZE
    blocks = [(x0, 0, z0, x1, top, z1) for x0, x1, z0, z1, top in COURSE_PLATFORMS]
    blocks += [(x0, 0, z0, x1, COURSE_PIT, z1, LEAF_PIT) for x0, x1, z0, z1 in COURSE_GAPS]
    top_texture, side_texture = t.textures[0], t.textures[1]
    verts, polys = blocks_mesh([b[:6] for b in blocks], top_texture, side_texture, COURSE_PIECE)

    points, height = [], COURSE_GROUND
    for z in range(d - 200, 200, -COURSE_PATH_STEP):
        top = course_top(z - COURSE_LEAD)
        height = top if top is not None else height  # keep the height over gaps
        points.append((COURSE_CRASH[0] + MOCK_CAM[0], height + MOCK_CAM[1], z))

    crash = bytearray(t.crash)
    struct.pack_into("<3h", crash, ENTITY_POINTS, COURSE_CRASH[0] // 4,
                     (course_top(COURSE_CRASH[1]) + 100) // 4, COURSE_CRASH[1] // 4)
    entities, next_id = [bytes(crash)], 20
    for i, kind in enumerate(COURSE_BOXES):
        x = 2048 + (i - len(COURSE_BOXES) // 2) * 448
        entities.append(place_entity(t.entities[kind], next_id, (x, course_top(COURSE_BOX_Z), COURSE_BOX_Z)))
        next_id += 1
    x, z = COURSE_CHECKPOINT
    entities.append(place_entity(t.entities[(34, 4)], next_id, (x, course_top(z), z)))
    next_id += 1
    crab = t.entities[(31, 0)]
    count = struct.unpack_from("<H", crab, ENTITY_POINT_COUNT)[0]
    xs = [struct.unpack_from("<h", crab, ENTITY_POINTS + 6 * i)[0] * 4 for i in range(count)]
    first_from_middle = xs[0] - (min(xs) + max(xs)) // 2   # so the patrol is centred
    for x, z in COURSE_CRABS:
        entities.append(place_entity(crab, next_id, (x + first_from_middle, course_top(z), z)))
        next_id += 1
    x, z = COURSE_WARP
    entities.append(place_entity(t.entities[(32, 1)], next_id, (x, course_top(z), z)))
    worlds = [([v + (GREY,) for v in verts], polys)]
    return assemble_level(level, t, "Cour", COURSE_SIZE, blocks, worlds, points,
                          COURSE_PATH_STEP, entities)


# maps modelled in blender (see tools/blendmap.py)

MAP_SCALE = 400        # zone units per blender metre: crash is a little over 2 m tall
MAP_PIECE = 512        # the world meshes are sliced along z this often
MAP_PATH_STEP = 128    # camera path points; doubled while the sort list doesn't fit in a page
MAP_HEADROOM = 1024    # room above the map


def cell_blocks(cells, cell):
    """blocks (see blocks_rect_bytes) for collision cells ({(i, j, k):
    "ground" or "pit"})"""
    leaves = {"ground": LEAF_FLOOR, "pit": LEAF_PIT}
    return [(i * cell, j * cell, k * cell, (i + 1) * cell, (j + 1) * cell, (k + 1) * cell, leaves[kind])
            for (i, j, k), kind in cells.items()]


def make_map(level, text, scale=MAP_SCALE, turn=0):
    """a level from a map exported from blender as .obj (its text): its
    faces as the world meshes and collision, and crash, with nothing else;
    built like make_course from level (a real level such as N. Sanity
    Beach) for crash and the textures"""
    t = Templates(level)
    fit = blendmap.fit(blendmap.read_obj(text, scale, turn), COURSE_CELL, MAP_HEADROOM, margin=COURSE_CELL)
    mesh = fit.mesh
    cells = blendmap.solid_cells(mesh, fit.size, COURSE_CELL)
    worlds = blendmap.world_meshes(mesh, MAP_PIECE, t.textures[0], t.textures[1])
    start = blendmap.spawn(mesh, cells, fit.size, COURSE_CELL)
    crash = bytearray(t.crash)
    struct.pack_into("<3h", crash, ENTITY_POINTS, start[0] // 4, (start[1] + 100) // 4, start[2] // 4)
    step = MAP_PATH_STEP
    while True:
        points = blendmap.camera_path(mesh, cells, fit.size, COURSE_CELL, start, step)
        try:
            return assemble_level(level, t, "BMap", fit.size, cell_blocks(cells, COURSE_CELL), worlds,
                                  points, step, [bytes(crash)])
        except EntryTooBig as e:
            if e.entry.type != 4 or step >= MAP_PIECE:  # only the sort list shrinks
                raise
            step *= 2  # fewer points, so a smaller sort list


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
  python tools/nslevel.py map <file.obj> [name] [--scale <units per m>] [--turn <degrees>]
                                             make a level from a map exported from blender
                                             as custom_levels/<name> (the file's name)
  python tools/nslevel.py course [name]      make an obstacle course as custom_levels/<name> (course)
  python tools/nslevel.py mock [name]        make a level from scratch (a flat floor
                                             and crash) as custom_levels/<name> (mock)
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
    if len(argv) >= 2 and argv[0] == "map":
        args, options = [], {"--scale": MAP_SCALE, "--turn": 0}
        rest = iter(argv[1:])
        for arg in rest:
            if arg in options:
                options[arg] = int(next(rest, "x"))
            else:
                args.append(arg)
        path = args[0]
        name = args[1] if len(args) >= 2 else os.path.splitext(os.path.basename(path))[0]
        with open(path) as f:
            text = f.read()
        level = make_map(read_level(STREAMS_DIR, 9), text, options["--scale"], options["--turn"])
        write_level(level, CUSTOM_LEVELS_DIR, name)
        print("wrote %s" % os.path.join(CUSTOM_LEVELS_DIR, name))
        return 0
    if len(argv) >= 1 and argv[0] == "course":
        name = argv[1] if len(argv) >= 2 else "course"
        write_level(make_course(read_level(STREAMS_DIR, 9)), CUSTOM_LEVELS_DIR, name)
        print("wrote %s" % os.path.join(CUSTOM_LEVELS_DIR, name))
        return 0
    if len(argv) >= 1 and argv[0] == "mock":
        name = argv[1] if len(argv) >= 2 else "mock"
        write_level(make_mock(read_level(STREAMS_DIR, 9)), CUSTOM_LEVELS_DIR, name)
        print("wrote %s" % os.path.join(CUSTOM_LEVELS_DIR, name))
        return 0
    print(USAGE)
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
