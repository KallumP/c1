"""
Read and write the game's level files, and make custom levels from maps
(for tools/generate_level_terrain.py): a level is an .nsd (page table and
level header) and an .nsf (64 KB pages of entries).

The layouts mirror the structs in src/ns.h, which the game loads as is.
"""
import copy
import os
import struct

import blendmap
import tpage

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
SHARED_ITEMS_TYPE = 4  # sort lists: many of their items are the same, and none is empty

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
    if etype == SHARED_ITEMS_TYPE:  # an item ends where the next stored item starts
        ends = sorted(set(offsets))
        items = [bytes(data[off + o:off + next((e for e in ends if e > o), o)]) for o in offsets[:-1]]
    else:
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
    """an entry: header, item offsets relative to the entry, then the items.
    a sort list's identical items are stored once, their offsets pointing at
    the same data (the loader makes each offset a pointer on its own)"""
    offset = 16 + 4 * (len(entry.items) + 1)
    offsets, stored, blobs = [], {}, []
    for item in entry.items:
        if item not in stored or entry.type != SHARED_ITEMS_TYPE:
            stored[item] = offset
            blobs.append(item)
            offset += len(item)
        offsets.append(stored[item])
    offsets.append(offset)
    data = struct.pack("<IIii", MAGIC_ENTRY, entry.eid, entry.type, len(entry.items))
    return data + struct.pack("<%dI" % len(offsets), *offsets) + b"".join(blobs)


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
FLOOR_CELL_MAX = 1024  # largest solid cell (zone units): ZoneQueryOctree stores a cell's position
                       # relative to the query point as int16 (>> 4), so a bigger one is misplaced

def pad4(data):
    return data + b"\0" * (-len(data) % 4)


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
    split while it's wider than FLOOR_CELL_MAX; the
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


def zone_header_bytes(template, self_eid, worlds, path_count, entity_count, neighbors=()):
    """a zone header from a real one, with the given worlds ((wgeo eid,
    (x, y, z)) pairs), its own paths and entities, itself and then the
    neighbors (zone eids) as its neighbors, an empty load list and no music"""
    h = bytearray(template)
    struct.pack_into("<I", h, 0, len(worlds))
    for i in range(8):
        world = b"\0" * ZONE_WORLD_SIZE
        if i < len(worlds):
            eid, trans = worlds[i]
            world = struct.pack("<I3i", eid, *trans).ljust(ZONE_WORLD_SIZE, b"\0")
        h[4 + i * ZONE_WORLD_SIZE:4 + (i + 1) * ZONE_WORLD_SIZE] = world
    listed = [self_eid] + list(neighbors)
    struct.pack_into("<4I", h, ZONE_PATHS_IDX, 2, path_count, entity_count, len(listed))
    struct.pack_into("<8I", h, ZONE_NEIGHBORS, *(listed + [0] * (8 - len(listed))))
    h[ZONE_LOADLIST:ZONE_DISPLAY_FLAGS] = b"\0" * (ZONE_DISPLAY_FLAGS - ZONE_LOADLIST)
    struct.pack_into("<I", h, ZONE_DISPLAY_FLAGS, 0)
    struct.pack_into("<I", h, ZONE_MIDI, EID_NONE)
    return bytes(h)


PATH_LINKS_MAX = 4  # neighbor_paths in zone_path (src/formats/zdat.h)


def path_bytes(slst, points, cam_mode, zoom, avg_node_dist, direction=(0, 0, 0), links=()):
    """a camera path; points are (x, y, z, rot_y, rot_x, rot_z) in zone
    units, links the paths it leads on to (zone_neighbor_path: relation, 1
    before or 2 after; the zone's index in its neighbors; the path's index
    in that zone; goal, 1 its start or 2 its end)"""
    data = struct.pack("<III", slst, 0, len(links))
    data += b"".join(struct.pack("<4B", *link) for link in links).ljust(4 * PATH_LINKS_MAX, b"\0")
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


WGEO_HEADER = "<iiiIIIII"  # trans x y z, poly, vert, texinfo and tpag counts, is_backdrop


WGEO_TPAGS = 8  # texture page slots in a mesh header


def world_header_bytes(template, trans, poly_count, vert_count, tpags=(), texinfos=b""):
    """a mesh header from a real one (keeping its texture pages and
    texinfos), placed at trans (zone units) with new counts, and more
    texture pages (in its free slots) and texinfos added after its own"""
    fields = list(struct.unpack_from(WGEO_HEADER, template, 0))
    slots = list(struct.unpack_from("<%dI" % WGEO_TPAGS, template, 32))
    slots[fields[6]:fields[6] + len(tpags)] = tpags
    fields[0:5] = [trans[0], trans[1], trans[2], poly_count, vert_count]
    fields[5] += len(texinfos) // 4
    fields[6] += len(tpags)
    return (struct.pack(WGEO_HEADER, *fields) + struct.pack("<%dI" % WGEO_TPAGS, *slots[:WGEO_TPAGS])
            + template[32 + 4 * WGEO_TPAGS:] + texinfos)


# sort lists (slst, see src/formats/slst.h and src/slst.c)

def poly_id(world_idx, poly_idx):
    return (world_idx << 12) | poly_idx  # flag:1, world_idx:3, poly_idx:12


POLY_IDS_MAX = 1460  # polygons the game can list (SlstInit in src/slst.c)
SLST_FULL, SLST_DELTA = 0, 1  # item types: SlstUpdate copies an even one, applies an odd one
SLST_RUN_MAX = 16             # ids a delta node can hold
SLST_NEXT = 0x8000            # a node's id flag: this one goes one place on from the last


def slst_full(ids):
    return pad4(struct.pack("<HH%dH" % len(ids), len(ids), SLST_FULL, *ids))


def slst_delta(a, b):
    """a sort list item that turns list a into list b, going forward along
    the path, and b into a going back (SlstDecodeForward and
    SlstDecodeBackward in src/slst.c). both lists have to be in the same
    order, so it only removes and adds ids, without swaps.

    a remove node is (count - 1) << 12 | the first id's place in a, plus 1,
    then the ids, each after the first flagged as the next place on. an add
    node is (count - 1) << 12 | how many of a's kept ids come before, then
    the ids, which go in together there"""
    in_a, in_b = set(a), set(b)
    removes, adds = [], []
    gone = [i for i, x in enumerate(a) if x not in in_b]
    while gone:
        run = 1
        while run < min(len(gone), SLST_RUN_MAX) and gone[run] == gone[0] + run:
            run += 1
        removes += [((run - 1) << 12) | (gone[0] + 1)] + [a[gone[0]]] + [a[i] | SLST_NEXT for i in gone[1:run]]
        gone = gone[run:]
    kept, new = 0, []
    for x in b + [None]:
        if x is not None and x not in in_a:
            new.append(x)
            continue
        while new:
            run = new[:SLST_RUN_MAX]
            adds += [((len(run) - 1) << 12) | kept] + run
            new = new[SLST_RUN_MAX:]
        kept += 1
    split = 2 + len(removes)
    swaps = split + len(adds)
    words = [split, swaps] + removes + adds
    return pad4(struct.pack("<HH%dH" % len(words), len(words), SLST_DELTA, *words))


def slst_items(world_zmax, cam_zs, step, near, world_zmid=None):
    """a sort list for a camera path along -z (cameras at z cam_zs): for each
    point, the polygons (of each world, by their largest z, one list per
    world) that stay in front of the camera all the way to the next point,
    so none is ever drawn from behind the camera, which the renderer would
    project mirrored. a list holds at most the POLY_IDS_MAX nearest.

    the game draws a list in order with no depth test (SwTransformAndShadeWorlds
    in src/pc/gfx/soft.c), so each is farthest first by the polygons' middle
    z (world_zmid, laid out like world_zmax; their largest z if not given).

    LevelUpdate copies item 0 at the first point and item N (one past the
    last point) at the last, so those are full lists; between them, item k
    is the change from point k-1's list to point k's, which it applies
    forward going on to point k and backward going back from it. as every
    list is in the same order, a change is only what comes into view and
    what leaves it, so a long path stays small."""
    world_zmid = world_zmid or world_zmax

    def ids(cam_z):
        front = [(zmax, world_zmid[w][i], poly_id(w, i)) for w, poly_zmax in enumerate(world_zmax)
                 for i, zmax in enumerate(poly_zmax) if zmax < cam_z - step - near]
        if len(front) > POLY_IDS_MAX:  # too many to list: leave out the farthest
            front = sorted(front, key=lambda f: -f[0])[:POLY_IDS_MAX]
        return [f[2] for f in sorted(front, key=lambda f: (f[1], f[2]))]
    lists = [ids(z) for z in cam_zs]
    return ([slst_full(lists[0])] + [slst_delta(a, b) for a, b in zip(lists, lists[1:])]
            + [slst_full(lists[-1])])


# entities (zone_entity in src/formats/zdat.h): parent zone, spawn flags,
# group, id, point count, 3 init flags, type, subtype, then the points, in
# units of 4 zone units relative to the zone
def zone_slst_items(listed, cam_zs, step):
    """slst_items for a zone's path (cameras at z cam_zs) over the meshes it
    lists: (vertices, polygons, z offset into the zone's frame) each, its
    own (offset 0) and the next zone's, further along -z"""
    world_zmax = [[max(verts[a][2], verts[b][2], verts[c][2]) + dz for a, b, c, *_ in polys]
                  for verts, polys, dz in listed]
    world_zmid = [[(verts[a][2] + verts[b][2] + verts[c][2]) / 3 + dz for a, b, c, *_ in polys]
                  for verts, polys, dz in listed]
    return slst_items(world_zmax, cam_zs, step, SLST_NEAR, world_zmid)


ENTITY_TYPE = 18
ENTITY_POINTS = 20


def entity_type(item):
    """an entity's type (its exec map slot) and subtype"""
    return item[ENTITY_TYPE], item[ENTITY_TYPE + 1]


# custom levels

SLST_NEAR = 64  # how far in front of the camera a polygon has to be to be listed
MAP_CELL = 128  # collision cells

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


class ZonePlan:
    """what goes in one zone of a custom level: its z offset from the first
    zone's corner, collision blocks, world meshes (vertices (x, y, z, colour)
    and polygons (a, b, c, tinf, tpag) relative to the zone), its mesh
    headers' extra texinfos, camera path points (x, y, z) relative to the
    zone (none for zones the camera never reaches) and entities"""
    def __init__(self, dz, blocks, worlds, texinfos, points, entities=()):
        self.dz, self.blocks, self.worlds, self.texinfos = dz, blocks, worlds, texinfos
        self.points, self.entities = points, list(entities)


def zone_prefix(i):
    return "Bm%02d" % i  # a zone's entries are this and Z, S, W, 1, 2, 3


def assemble_level(level, templates, size, zones, step, spawn_zone, tpag_eids=(), texture_pages=()):
    """a custom level from a real level: a chain of zones (ZonePlan) of size
    (w, h, d), the first at the template zone's origin and the rest each
    along -z from the one before, each with a follow camera path step apart
    going along -z that leads on to the next zone's. each zone lists its own
    meshes and the next zone's, as the camera looks on into it. crash, the
    first entity of spawn_zone, starts there. keeps crash, the hud and core
    objects, and the code for the entities' types, from level. tpag_eids and
    texture_pages add texture pages for the meshes' texinfos"""
    t = templates
    x0, y0, z0 = t.origin
    zone_eids = [str_to_eid(zone_prefix(i) + "Z") for i in range(len(zones))]
    world_eids = [[str_to_eid(zone_prefix(i) + ("W" if w == 0 else str(w))) for w in range(len(z.worlds))]
                  for i, z in enumerate(zones)]
    origins = [(x0, y0, z0 + z.dz) for z in zones]
    entries = []
    for i, z in enumerate(zones):
        entries += [Entry(eid, 3, [
            world_header_bytes(t.world.items[0], origins[i], len(polys), len(verts), tpag_eids, infos),
            b"".join(world_polygon_bytes(a, b, c, tinf, tpag) for a, b, c, tinf, tpag in polys),
            b"".join(world_vertex_bytes(x, y, zz, colour) for x, y, zz, colour in verts)])
            for eid, (verts, polys), infos in zip(world_eids[i], z.worlds, z.texinfos)]
    for i, z in enumerate(zones):
        nxt = i + 1 if i + 1 < len(zones) else None
        listed = [(eid, origins[i]) for eid in world_eids[i]]
        meshes = [(verts, polys, 0) for verts, polys in z.worlds]
        if nxt is not None:
            listed += [(eid, origins[nxt]) for eid in world_eids[nxt]]
            meshes += [(verts, polys, zones[nxt].dz - z.dz) for verts, polys in zones[nxt].worlds]
        neighbors = ([zone_eids[i - 1]] if i > 0 else []) + ([zone_eids[nxt]] if nxt is not None else [])
        paths = []
        if z.points:
            slst_eid = str_to_eid(zone_prefix(i) + "S")
            links = []
            if i > 0 and zones[i - 1].points:
                links.append((1, 1, 0, 2))  # back to the end of the path before
            if nxt is not None and zones[nxt].points:
                links.append((2, neighbors.index(zone_eids[nxt]) + 1, 0, 1))  # on to the start of the next
            cam_points = [(x, y, zz, -181, 1, 0) for x, y, zz in z.points]
            paths = [path_bytes(slst_eid, cam_points, cam_mode=5, zoom=1700, avg_node_dist=step,
                                direction=(0, 0, -4096), links=links)]
            entries.append(Entry(slst_eid, 4, zone_slst_items(meshes, [p[2] for p in z.points], step)))
        entries.append(Entry(zone_eids[i], 7, [
            zone_header_bytes(t.header, zone_eids[i], listed, len(paths), len(z.entities), neighbors),
            blocks_rect_bytes(origins[i], size, z.blocks, MAP_CELL)] + paths + z.entities))
    tpags = struct.unpack_from("<8I", t.world.items[0], 32)
    exec_map = level.nsd.ldat.exec_map
    slots = set(CORE_EXEC_SLOTS) | {entity_type(e)[0] for z in zones for e in z.entities}
    keep = [exec_map[i] for i in slots] + [tp for tp in tpags if tp]
    out = cut_level(level, keep)
    out.pages = pack_entries(entries) + out.pages + list(texture_pages)
    out.nsd.ldat.lid = LID_TEST
    out.nsd.ldat.zone_spawn = zone_eids[spawn_zone]
    out.nsd.ldat.path_idx_spawn = 0
    for eid in zone_eids:
        load_texture_pages(out, eid)
    return out


# maps modelled in blender (see tools/blendmap.py)

MAP_SCALE = 400        # zone units per blender metre: crash is about 665 tall (his bound in
                       # StopAtFloor in src/solid.c), so 1.7 m
MAP_PIECE = 512        # the world meshes are sliced along z this often
MAP_TILE = 1024        # and along x and y this often, so textures don't stretch over whole faces
MAP_PATH_STEP = 128    # camera path points; doubled while the sort list doesn't fit in a page
MAP_HEADROOM = 1024    # room above the map


def cell_blocks(cells, cell):
    """blocks (see blocks_rect_bytes) for collision cells ({(i, j, k):
    "floor", "wall" or "pit"})"""
    leaves = {"floor": LEAF_FLOOR, "wall": LEAF_GROUND, "pit": LEAF_PIT}
    return [(i * cell, j * cell, k * cell, (i + 1) * cell, (j + 1) * cell, (k + 1) * cell, leaves[kind])
            for (i, j, k), kind in cells.items()]


TEXINFO_WORDS_MAX = 4096  # polygons' texinfo indices (in words) are 12 bits


def map_textures(worlds, images, template):
    """texture pages for the materials' images that the world meshes' tile
    regions (blendmap.TileRegion) use, and the meshes with each region
    turned into a texinfo index and texture page slot, for a mesh header
    from template: (worlds, (tpag eids, each mesh's texinfos, texture
    pages)). each mesh lists only the regions it uses, as the indices only
    reach TEXINFO_WORDS_MAX words into its header"""
    fields = struct.unpack_from(WGEO_HEADER, template, 0)
    used = sorted({p[3].material for _, polys in worlds for p in polys if p[4] is None})
    chunks = [used[i:i + tpage.TILES_PER_PAGE] for i in range(0, len(used), tpage.TILES_PER_PAGE)]
    if len(chunks) > WGEO_TPAGS - fields[6]:
        raise ValueError("%d textured materials, more than %d" % (
            len(used), (WGEO_TPAGS - fields[6]) * tpage.TILES_PER_PAGE))
    pages, place_of = [], {}
    for k, chunk in enumerate(chunks):
        eid = str_to_eid("BMp%dT" % k)
        data, places = tpage.texture_page(eid, [tpage.tile(images[m]) for m in chunk])
        pages.append(Page(PAGE_TEXTURE, eid=eid, data=data))
        for m, place in zip(chunk, places):
            place_of[m] = (fields[6] + k, place)
    out, all_texinfos = [], []
    for w, (verts, polys) in enumerate(worlds):
        index, texinfos = {}, b""
        new = []
        for p in polys:
            if p[4] is None:
                r = p[3]
                slot, place = place_of[r.material]
                if r not in index:
                    index[r] = fields[5] + len(texinfos) // 4
                    texinfos += tpage.texinfo_bytes(place, r.layout, (r.x, r.y, r.w, r.h))
                p = p[:3] + (index[r], slot)
            new.append(p)
        if fields[5] + len(texinfos) // 4 > TEXINFO_WORDS_MAX:
            raise ValueError("world mesh %d uses %d texture regions, more than its texinfos hold (%d)" % (
                w, len(index), (TEXINFO_WORDS_MAX - fields[5]) // 2))
        out.append((verts, new))
        all_texinfos.append(texinfos)
    return out, ([p.eid for p in pages], all_texinfos, pages)


def map_source(path):
    """the .obj to make a map's level from, and the level's name, for path:
    a map's folder (holding its one .obj, named after the folder) or a .obj
    (named after the file)"""
    path = os.path.normpath(path)
    if not os.path.isdir(path):
        return path, os.path.splitext(os.path.basename(path))[0]
    objs = sorted(f for f in os.listdir(path) if f.lower().endswith(".obj"))
    if len(objs) != 1:
        raise ValueError("%s has %d .obj files; a map's folder needs exactly one" % (path, len(objs)))
    return os.path.join(path, objs[0]), os.path.basename(path)


def map_images(obj_path, text):
    """{material: PIL image} for a .obj (its path and text): each material's
    image from the .mtl files it names, next to it. missing files are
    skipped with a warning"""
    from PIL import Image
    base = os.path.dirname(obj_path)
    images = {}
    for line in text.splitlines():
        fields = line.split()
        if not fields or fields[0] != "mtllib":
            continue
        mtl = os.path.join(base, " ".join(fields[1:]))
        if not os.path.exists(mtl):
            print("warning: %s not found, so its materials are untextured" % mtl)
            continue
        with open(mtl) as f:
            for mat, path in blendmap.read_mtl(f.read(), os.path.dirname(mtl)).items():
                if os.path.exists(path):
                    images[mat] = Image.open(path)
                    images[mat].load()
                else:
                    print("warning: %s (material %s) not found, so it is untextured" % (path, mat))
    return images


def make_map(level, text, scale=MAP_SCALE, turn=0, images=None):
    """a level from a map exported from blender as .obj (its text): its
    faces as the world meshes and collision, and crash, with nothing else;
    built from level (a real level such as N. Sanity Beach) for crash and
    the textures. faces of materials with an image in
    images ({material: PIL image}) get it, the rest the beach's textures"""
    t = Templates(level)
    fit = blendmap.fit(blendmap.read_obj(text, scale, turn), MAP_CELL, MAP_HEADROOM, margin=MAP_CELL,
                       long_z=True)
    mesh = fit.mesh
    cells = blendmap.solid_cells(mesh, fit.size, MAP_CELL)
    spans = blendmap.zone_spans(fit.size[2], MAP_CELL)
    size = (fit.size[0], fit.size[1], spans[0][1] - spans[0][0])
    texinfo_words = struct.unpack_from(WGEO_HEADER, t.world.items[0], 0)[5]  # the template's own
    worlds_max = blendmap.WORLDS_MAX if len(spans) == 1 else blendmap.WORLDS_MAX // 2  # and the next's
    zone_worlds = [blendmap.world_meshes(mesh, MAP_PIECE, t.textures[0], t.textures[1], MAP_TILE,
                                         textured=set(images or ()),
                                         regions_max=(TEXINFO_WORDS_MAX - texinfo_words) // 2,
                                         span=span, worlds_max=worlds_max) for span in spans]
    flat = [w for worlds in zone_worlds for w in worlds]
    tpag_eids, texinfos, pages = (), [b""] * len(flat), []
    if images:
        flat, (tpag_eids, texinfos, pages) = map_textures(flat, images, t.world.items[0])
    start = blendmap.spawn(mesh, cells, fit.size, MAP_CELL)
    spawn_zone = blendmap.zone_index(spans, start[2])
    crash = bytearray(t.crash)
    struct.pack_into("<3h", crash, ENTITY_POINTS, start[0] // 4, (start[1] + 100) // 4,
                     (start[2] - spans[spawn_zone][0]) // 4)
    step = MAP_PATH_STEP
    while True:
        paths = blendmap.zone_paths(blendmap.camera_path(cells, fit.size, MAP_CELL, start, step), spans)
        zones, n = [], 0
        for i, span in enumerate(spans):
            count = len(zone_worlds[i])
            zones.append(ZonePlan(span[0] - spans[0][0], cell_blocks(blendmap.zone_cells(cells, span, MAP_CELL),
                                                                     MAP_CELL),
                                  flat[n:n + count], texinfos[n:n + count], paths[i],
                                  [bytes(crash)] if i == spawn_zone else []))
            n += count
        try:
            return assemble_level(level, t, size, zones, step, spawn_zone, tpag_eids, pages)
        except EntryTooBig as e:
            if e.entry.type != 4 or step >= MAP_PIECE:  # only the sort lists shrink
                raise
            step *= 2  # fewer points, so smaller sort lists


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


