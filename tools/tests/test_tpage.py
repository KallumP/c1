"""
tests for tools/tpage.py

run from the project root: python -m unittest discover -s tools/tests
"""
import os
import re
import struct
import sys
import unittest

from PIL import Image

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, TOOLS)
import tpage  # noqa: E402


def checker(size, a, b):
    """a size x size image of two colours in a checkerboard of 1 pixel squares"""
    im = Image.new("RGB", (size, size))
    im.putdata([a if (x + y) % 2 else b for y in range(size) for x in range(size)])
    return im


class Colour(unittest.TestCase):
    def test_5551_layout_is_red_low_then_green_then_blue(self):
        # pixel_5551_8888 in src/pc/gfx/pixel.h
        self.assertEqual(31 | (16 << 5) | (8 << 10), tpage.colour_5551((255, 128, 64)))

    def test_black_is_not_transparent(self):
        # a colour of 0 is drawn transparent
        self.assertNotEqual(0, tpage.colour_5551((0, 0, 0)))
        self.assertNotEqual(0, tpage.colour_5551((7, 7, 7)))


class Tile(unittest.TestCase):
    def test_tile_is_64_by_64_indices_into_16_colours(self):
        pixels, palette = tpage.tile(checker(32, (255, 0, 0), (0, 0, 255)))
        self.assertEqual(64 * 64, len(pixels))
        self.assertEqual(16, len(palette))
        self.assertTrue(all(0 <= p < 16 for p in pixels))

    def test_pixels_keep_their_colours(self):
        red, blue = (248, 0, 0), (0, 0, 248)
        pixels, palette = tpage.tile(checker(64, red, blue))
        self.assertEqual(tpage.colour_5551(blue), palette[pixels[0]])  # (0, 0) is b
        self.assertEqual(tpage.colour_5551(red), palette[pixels[1]])

    def test_a_smaller_image_is_scaled_up_without_blurring(self):
        pixels, palette = tpage.tile(checker(32, (248, 0, 0), (0, 0, 248)))
        self.assertEqual(2, len(set(pixels)))
        self.assertEqual(pixels[0], pixels[1])  # each pixel is now 2x2
        self.assertNotEqual(pixels[0], pixels[2])

    def test_many_colours_are_reduced_to_16(self):
        im = Image.new("RGB", (64, 64))
        im.putdata([(x * 4, y * 4, (x + y) * 2) for y in range(64) for x in range(64)])
        pixels, palette = tpage.tile(im)
        self.assertLessEqual(len(set(pixels)), 16)

    def test_alpha_is_ignored(self):
        im = Image.new("RGBA", (8, 8), (10, 200, 30, 0))
        pixels, palette = tpage.tile(im)
        self.assertEqual(tpage.colour_5551((10, 200, 30)), palette[pixels[0]])


def pixel(page, x, y):
    """a 4 bit pixel of a page, read as TextureCopy in src/pc/gfx/tex.c does"""
    si = x + y * 1024
    return (page[si // 2] >> (4 if si % 2 else 0)) & 0xF


def palette_at(page, clut_x, clut_y):
    at = 2 * (clut_x * 16 + clut_y * 256)
    return list(struct.unpack_from("<16H", page, at))


def region_x(place):
    """the pixel x the game finds a region at: (segment * 32 + offs_x) * 8 for 4 bits"""
    return (place.segment * 32 + place.offs_x) * 8


EID = 0x12345679


class Page(unittest.TestCase):
    def tiles(self, n):
        return [([(i + k) % 16 for i in range(64 * 64)], [k * 100 + c + 1 for c in range(16)]) for k in range(n)]

    def test_page_is_64_kb_with_a_texture_page_header(self):
        page, places = tpage.texture_page(EID, self.tiles(1))
        self.assertEqual(0x10000, len(page))
        self.assertEqual((0x1234, 1, EID, 5), struct.unpack_from("<HHII", page, 0))

    def test_tiles_are_where_their_places_say(self):
        tiles = self.tiles(20)
        page, places = tpage.texture_page(EID, tiles)
        for (pixels, palette), place in zip(tiles, places):
            x, y = region_x(place), place.offs_y * 4
            for py in (0, 1, 63):
                for px in (0, 1, 62, 63):
                    self.assertEqual(pixels[px + py * 64], pixel(page, x + px, y + py))
            self.assertEqual(palette, palette_at(page, place.clut_x, place.clut_y))

    def test_tiles_and_palettes_dont_overlap_the_header_or_each_other(self):
        page, places = tpage.texture_page(EID, self.tiles(tpage.TILES_PER_PAGE))
        self.assertEqual((0x1234, 1, EID, 5), struct.unpack_from("<HHII", page, 0))
        self.assertEqual(len(places), len({(region_x(p), p.offs_y) for p in places}))
        self.assertEqual(len(places), len({(p.clut_x, p.clut_y) for p in places}))
        for p in places:
            self.assertGreater(p.clut_y, 0)  # row 0 has the header
            self.assertTrue(region_x(p) >= 64 or p.offs_y * 4 >= 64)  # not in the palettes' slot

    def test_too_many_tiles_for_a_page_is_an_error(self):
        with self.assertRaises(ValueError):
            tpage.texture_page(EID, self.tiles(tpage.TILES_PER_PAGE + 1))


def uv_map():
    """the 600 quads of uv_map in src/gfx.c, as 8 numbers each"""
    src = open(os.path.join(TOOLS, "..", "src", "gfx.c")).read()
    body = src[src.index("uv_map[600] = {"):]
    pair = r"\{\s*(\d+),\s*(\d+)\s*\}"
    quads = re.findall(r"\{\s*" + r",\s*".join([pair] * 4) + r"\s*\}", body)[:600]
    return [tuple(map(int, q)) for q in quads]


def decode_texinfo(data):
    """(colinfo fields, rgninfo fields) of an 8 byte texture info; bitfields
    are listed high bits first in src/geom.h"""
    r, g, b, flags, rgn = struct.unpack("<4BI", data)
    col = dict(type=flags >> 7, semi_trans=(flags >> 5) & 3, no_cull=(flags >> 4) & 1, clut_x=flags & 15)
    rgn = dict(uv_idx=rgn >> 22, color_mode=(rgn >> 20) & 3, segment=(rgn >> 18) & 3,
               offs_x=(rgn >> 13) & 31, clut_y=(rgn >> 6) & 127, offs_y=rgn & 31)
    return col, rgn


class TextureInfo(unittest.TestCase):
    def test_layouts_are_the_games(self):
        quads = uv_map()
        self.assertEqual(600, len(quads))
        for layout, corners in enumerate(tpage.LAYOUTS):
            q = quads[layout * 25 + 24]  # the 64x64 one
            self.assertEqual(corners, tuple((q[2 * i] // 63, q[2 * i + 1] // 63) for i in range(3)))

    def test_uv_idx_picks_the_layout_and_size(self):
        quads = uv_map()
        for layout in (0, 7, 23):
            for w, h in ((4, 4), (32, 64), (64, 8)):
                q = quads[tpage.uv_idx(layout, w, h)]
                self.assertEqual((w - 1, h - 1), (max(q[0:8:2]), max(q[1:8:2])))
                corners = tuple((q[2 * i] // (w - 1), q[2 * i + 1] // (h - 1)) for i in range(3))
                self.assertEqual(tpage.LAYOUTS[layout], corners)

    def test_texinfo_points_at_the_tiles_region_and_palette(self):
        place = tpage.Place(1, 8, 16, 0, 5)  # x (32 + 8) * 8 = 320, y 64
        col, rgn = decode_texinfo(tpage.texinfo_bytes(place, layout=3, region=(32, 16, 32, 16)))
        self.assertEqual(dict(type=1, semi_trans=3, no_cull=0, clut_x=0), col)
        self.assertEqual(tpage.uv_idx(3, 32, 16), rgn["uv_idx"])
        self.assertEqual(0, rgn["color_mode"])  # 4 bit
        self.assertEqual(320 + 32, (rgn["segment"] * 32 + rgn["offs_x"]) * 8)
        self.assertEqual(64 + 16, rgn["offs_y"] * 4)
        self.assertEqual(5, rgn["clut_y"])

    def test_region_has_to_fit_the_games_steps(self):
        place = tpage.Place(0, 8, 0, 0, 1)
        for region in ((4, 0, 32, 32), (0, 2, 32, 32), (0, 0, 24, 32), (0, 0, 32, 2), (48, 0, 32, 32)):
            with self.assertRaises(ValueError, msg=region):
                tpage.texinfo_bytes(place, 0, region)


if __name__ == "__main__":
    unittest.main()
