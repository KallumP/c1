"""
texture pages (tpag) for custom levels: images turned into 16 colour tiles
on a page the game loads into vram, and the texture infos that put a part
of a tile on a polygon. see src/pc/gfx/tex.c for how the game reads them.
"""
from PIL import Image

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
