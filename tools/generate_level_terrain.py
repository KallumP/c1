"""
make a custom level from a map modelled in blender: its faces as the level's
geometry and collision, and crash, with nothing else. see
doc/custom_levels.md for the whole process; nslevel.py and blendmap.py do
the work.
"""
import os
import sys

import nslevel

USAGE = """usage:
  python tools/generate_level_terrain.py <map> [name] [--scale <units per m>] [--turn <degrees>]

  map    a map's folder, such as maps/my_map, holding its .obj, .mtl and
         images (or a .obj)
  name   the level to write, custom_levels/<name> (the folder's or file's name)
  --scale  the game's units per blender metre (%d)
  --turn   degrees to turn the map about the up axis, e.g. 90 if its route
           runs along x""" % nslevel.MAP_SCALE


def parse_args(argv):
    """(map, name or None, scale, turn) from the command line"""
    args, options = [], {"--scale": nslevel.MAP_SCALE, "--turn": 0}
    rest = iter(argv)
    for arg in rest:
        if arg in options:
            value = next(rest, None)
            if value is None:
                raise ValueError("%s needs a number" % arg)
            options[arg] = int(value)
        else:
            args.append(arg)
    if not 1 <= len(args) <= 2:
        raise ValueError("give a map, and optionally a name")
    return args[0], (args[1] if len(args) == 2 else None), options["--scale"], options["--turn"]


def main(argv):
    try:
        source, name, scale, turn = parse_args(argv)
    except ValueError as e:
        print(e)
        print(USAGE)
        return 1
    path, default_name = nslevel.map_source(source)
    name = name or default_name
    with open(path) as f:
        text = f.read()
    images = nslevel.map_images(path, text)
    level = nslevel.make_map(nslevel.read_level(nslevel.STREAMS_DIR, 9), text, scale, turn, images)
    nslevel.write_level(level, nslevel.CUSTOM_LEVELS_DIR, name)
    print("wrote %s" % os.path.join(nslevel.CUSTOM_LEVELS_DIR, name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
