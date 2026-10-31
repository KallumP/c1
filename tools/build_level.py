"""
build a level from its source, a map modelled in blender: its faces as the level's
geometry and collision, and crash, with nothing else. see
doc/custom_levels.md for the whole process; nslevel.py and blendmap.py do
the work.
"""
import os
import sys

import blendmap
import nslevel

USAGE = """usage:
  python tools/build_level.py <source> [name] [--scale <units per m>] [--turn <degrees>]

  source a level source's folder, such as level_src/tide_ruins, holding its
         .obj, .mtl and images (or a .obj)
  name   the level to write, build/levels/<name> (the folder's or file's name)
  --scale  the game's units per blender metre (%d)
  --turn   degrees to turn the level about the up axis, e.g. 90 if its route
           runs along x

  a level.cfg next to the .obj can set scale and turn for the level (one
  "key = value" a line); --scale and --turn override it""" % nslevel.MAP_SCALE

LEVEL_CFG = "level.cfg"


def parse_args(argv):
    """(source, name or None, scale or None, turn or None) from the command
    line; scale and turn are None when not given"""
    args, options = [], {"--scale": None, "--turn": None}
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
        raise ValueError("give a level source, and optionally a name")
    return args[0], (args[1] if len(args) == 2 else None), options["--scale"], options["--turn"]


def read_level_cfg(folder):
    """{"scale": n, "turn": n} for the settings the level.cfg in folder gives
    (none without one). blank lines and lines starting with # are skipped;
    anything else that isn't scale or turn set to a whole number is a
    ValueError"""
    path = os.path.join(folder, LEVEL_CFG)
    if not os.path.exists(path):
        return {}
    settings = {}
    with open(path) as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, equals, value = (part.strip() for part in line.partition("="))
            if not equals:
                raise ValueError("%s, line %d: expected key = value" % (path, line_no))
            if key not in ("scale", "turn"):
                raise ValueError("%s, line %d: unknown setting %s (it takes scale and turn)" % (path, line_no, key))
            try:
                settings[key] = int(value)
            except ValueError:
                raise ValueError("%s, line %d: %s has to be a whole number, not %s"
                                 % (path, line_no, key, value or "nothing"))
    return settings


def level_options(folder, scale, turn):
    """(scale, turn) for the level source in folder: scale and turn from the command
    line if given, else from its level.cfg, else the defaults"""
    settings = read_level_cfg(folder)
    if scale is None:
        scale = settings.get("scale", nslevel.MAP_SCALE)
    if turn is None:
        turn = settings.get("turn", 0)
    return scale, turn


def fitting_scale(scale, too_big):
    """the largest scale (rounded down to a 10) at which a map that was
    too_big (blendmap.TooBig) at scale fits"""
    e = too_big
    return int(scale * (e.side_max - e.fixed) / (e.extent - e.fixed)) // 10 * 10


def main(argv):
    try:
        source, name, scale, turn = parse_args(argv)
    except ValueError as e:
        print(e)
        print(USAGE)
        return 1
    path, default_name = nslevel.level_source(source)
    name = name or default_name
    try:
        scale, turn = level_options(os.path.dirname(path), scale, turn)
    except ValueError as e:
        print(e)
        return 1
    with open(path) as f:
        text = f.read()
    images = nslevel.map_images(path, text)
    try:
        level = nslevel.make_map(nslevel.read_level(nslevel.STREAMS_DIR, 9), text, scale, turn, images)
    except blendmap.TooBig as e:
        print("%s: at --scale %d it's %d units along %s, and the game's collision only reaches %d. "
              "use --scale %d or less" % (source, scale, e.extent, "xyz"[e.axis], e.side_max,
                                          fitting_scale(scale, e)))
        return 1
    nslevel.write_level(level, nslevel.LEVELS_DIR, name)
    print("wrote %s" % os.path.join(nslevel.LEVELS_DIR, name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
