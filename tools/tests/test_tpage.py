"""
tests for tools/tpage.py

run from the project root: python -m unittest discover -s tools/tests
"""
import os
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


if __name__ == "__main__":
    unittest.main()
