"""
texture pages (tpag) for custom levels: images turned into 16 colour tiles
on a page the game loads into vram, and the texture infos that put a part
of a tile on a polygon. see src/pc/gfx/tex.c for how the game reads them.
"""
import struct

TILE = 64     # tiles are TILE x TILE pixels, the largest texture region (uv_map in src/gfx.c)
COLOURS = 16  # 4 bit textures: each tile has a palette of 16 colours


def colour_5551(rgb):
    """an (r, g, b) colour (0-255) as the game's 16 bit colour: 5 bits each
    of red, green and blue from the low bits up (pixel_5551_8888 in
    src/pc/gfx/pixel.h). 0 is drawn transparent, so black is nudged off it"""
    r, g, b = (c >> 3 for c in rgb)
    return (r | (g << 5) | (b << 10)) or 1


def tile(image):
    """a PIL image as a TILE x TILE tile: (pixels, row by row, as palette
    indices; palette, COLOURS 16 bit colours). a smaller image is scaled up
    without blurring, a bigger one scaled down smoothly; more than COLOURS
    colours are reduced to COLOURS"""
    from PIL import Image  # only needed for maps with textures
    im = image.convert("RGB")
    upscale = im.width <= TILE and im.height <= TILE
    im = im.resize((TILE, TILE), Image.NEAREST if upscale else Image.LANCZOS)
    colours = im.getcolors(COLOURS)
    if colours is None:  # more than COLOURS
        im = im.quantize(COLOURS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
        colours = im.getcolors(COLOURS)
    rgbs = [rgb for _, rgb in colours]
    index = {rgb: i for i, rgb in enumerate(rgbs)}
    pixels = [index[rgb] for rgb in im.getdata()]
    palette = [colour_5551(rgb) for rgb in rgbs] + [0] * (COLOURS - len(rgbs))
    return pixels, palette


# a texture page is the whole 64 KB page (header included) read as ROWS rows
# of ROW_BYTES bytes: 1024 4 bit pixels, or 256 16 bit colours. it is split
# into TILE x TILE slots; the first holds the header in its top row, so it
# holds the tiles' palettes instead, one a row from row 1 (16 colours are
# 32 bytes, just the slot's width)
PAGE_SIZE = 0x10000
ROWS = 128
ROW_BYTES = 512
SLOTS_ACROSS = ROW_BYTES * 2 // TILE
TILES_PER_PAGE = SLOTS_ACROSS * (ROWS // TILE) - 1
MAGIC_PAGE = 0x1234
PAGE_TEXTURE = 1
ENTRY_TPAG = 5


class Place:
    """where a tile is on its page, as a texture info gives it: x in units
    of 8 pixels (4 bit) as segment * 32 + offs_x, y in units of 4 rows as
    offs_y, and its palette at 16 bit colour (clut_x * 16, clut_y)"""
    def __init__(self, segment, offs_x, offs_y, clut_x, clut_y):
        self.segment, self.offs_x, self.offs_y = segment, offs_x, offs_y
        self.clut_x, self.clut_y = clut_x, clut_y


def texture_page(eid, tiles):
    """a texture page holding tiles ((pixels, palette) from tile()): its
    bytes, and each tile's Place"""
    if len(tiles) > TILES_PER_PAGE:
        raise ValueError("%d tiles, more than a page holds (%d)" % (len(tiles), TILES_PER_PAGE))
    page = bytearray(PAGE_SIZE)
    places = []
    for k, (pixels, palette) in enumerate(tiles):
        slot = k + 1
        x0, y0 = (slot % SLOTS_ACROSS) * TILE, (slot // SLOTS_ACROSS) * TILE
        for y in range(TILE):
            row = (y0 + y) * ROW_BYTES
            for x in range(0, TILE, 2):
                a, b = pixels[y * TILE + x], pixels[y * TILE + x + 1]
                page[row + (x0 + x) // 2] = a | (b << 4)  # even pixels in the low nibble
        clut_y = 1 + k
        page[clut_y * ROW_BYTES:clut_y * ROW_BYTES + 2 * COLOURS] = struct.pack("<%dH" % COLOURS, *palette)
        unit = x0 // 8
        places.append(Place(unit // 32, unit % 32, y0 // 4, 0, clut_y))
    struct.pack_into("<HHIII", page, 0, MAGIC_PAGE, PAGE_TEXTURE, eid, ENTRY_TPAG, 0)
    return bytes(page), places


# texture infos (texinfo2 in src/geom.h, 8 bytes in a world mesh's header):
# a region of a texture page and which of its corners go on a triangle's
# three corners. LAYOUTS are uv_map's 24 orders (src/gfx.c): every ordered
# pick of 3 of the region's 4 corners, as (x, y) with 0 left/top, 1 right/bottom
LAYOUTS = [
    ((0, 0), (1, 0), (0, 1)), ((0, 0), (0, 1), (1, 0)), ((1, 0), (0, 1), (0, 0)),
    ((1, 0), (0, 0), (0, 1)), ((0, 1), (0, 0), (1, 0)), ((0, 1), (1, 0), (0, 0)),
    ((0, 0), (1, 0), (1, 1)), ((0, 0), (1, 1), (1, 0)), ((1, 0), (1, 1), (0, 0)),
    ((1, 0), (0, 0), (1, 1)), ((1, 1), (0, 0), (1, 0)), ((1, 1), (1, 0), (0, 0)),
    ((1, 0), (1, 1), (0, 1)), ((1, 0), (0, 1), (1, 1)), ((1, 1), (0, 1), (1, 0)),
    ((1, 1), (1, 0), (0, 1)), ((0, 1), (1, 0), (1, 1)), ((0, 1), (1, 1), (1, 0)),
    ((0, 0), (1, 1), (0, 1)), ((0, 0), (0, 1), (1, 1)), ((1, 1), (0, 1), (0, 0)),
    ((1, 1), (0, 0), (0, 1)), ((0, 1), (0, 0), (1, 1)), ((0, 1), (1, 1), (0, 0)),
]
SIZES = [4, 8, 16, 32, 64]  # region widths and heights
SEMI_TRANS = 3              # as n. sanity beach's world textures


def uv_idx(layout, w, h):
    """uv_map's index for a layout and a w x h region"""
    return layout * 25 + SIZES.index(h) * 5 + SIZES.index(w)


def texinfo_bytes(place, layout, region):
    """a texture info for region (x, y, w, h, in pixels of the tile at
    place) put on a triangle's corners in layout. regions are a power of
    two 4 to 64 pixels a side, at x on 8 pixels (the step for 4 bit
    textures) and y on 4"""
    x, y, w, h = region
    if (w not in SIZES or h not in SIZES or x % 8 or y % 4 or x < 0 or y < 0
            or x + w > TILE or y + h > TILE):
        raise ValueError("region %r isn't one the game can address in a tile" % (region,))
    unit = place.segment * 32 + place.offs_x + x // 8
    flags = (1 << 7) | (SEMI_TRANS << 5) | place.clut_x  # type 1 (textured), no_cull 0
    rgn = ((uv_idx(layout, w, h) << 22) | (0 << 20) | ((unit // 32) << 18) | ((unit % 32) << 13)
           | (place.clut_y << 6) | (place.offs_y + y // 4))
    return struct.pack("<4BI", 0, 0, 0, flags, rgn)
