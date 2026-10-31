"""
the objects placed in a custom level (where crash starts, where the level
ends), from the objects.json in its level source: a list of objects, each a
kind and a position in blender (metres, z up), e.g.

  [{"kind": "spawn", "at": [0, 2, 0]},
   {"kind": "end", "at": [0, 48, 1.2]}]

see doc/custom_levels.md. tools/nslevel.py puts them in the level.
"""
import json
import numbers

import blendmap

KINDS = ("spawn", "end")  # each at most once
SETTINGS = ("kind", "at")


class LevelObject:
    """an object: its kind, and where it is in blender (x, y, z)"""
    def __init__(self, kind, at):
        self.kind, self.at = kind, at

    def __repr__(self):
        return "LevelObject(%r, %r)" % (self.kind, self.at)


def is_number(v):
    return isinstance(v, numbers.Real) and not isinstance(v, bool)


def read_objects(text):
    """the objects (LevelObject) in the text of an objects.json; anything
    that isn't a list of them, each a known kind (at most one of each) at
    three numbers, is a ValueError saying which object (from 1)"""
    try:
        items = json.loads(text)
    except ValueError as e:
        raise ValueError("isn't valid JSON: %s" % e)
    if not isinstance(items, list):
        raise ValueError("should be a list of objects, [{...}, ...]")
    objects = []
    for n, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError("object %d should be {\"kind\": ..., \"at\": [x, y, z]}" % n)
        unknown = [k for k in item if k not in SETTINGS]
        if unknown:
            raise ValueError("object %d: unknown setting %s (an object takes %s)"
                             % (n, unknown[0], " and ".join(SETTINGS)))
        kind = item.get("kind")
        if kind is None:
            raise ValueError("object %d has no kind" % n)
        if kind not in KINDS:
            raise ValueError("object %d: unknown kind %s (it can be %s)" % (n, kind, " or ".join(KINDS)))
        if any(o.kind == kind for o in objects):
            raise ValueError("object %d: there's already a %s (a level has one)" % (n, kind))
        at = item.get("at")
        if not (isinstance(at, list) and len(at) == 3 and all(is_number(c) for c in at)):
            raise ValueError("object %d: at should be its position in blender, [x, y, z] in metres" % n)
        objects.append(LevelObject(kind, tuple(at)))
    return objects


def to_zone(at, scale, turn, offset):
    """where at (a position in blender: x, y, z with z up, in metres) is in
    the level (zone units, (x, y up, z)), as a vertex there in the .obj is:
    the .obj has blender's (x, z, -y), which read_obj scales and turns by
    turn degrees and fit moves by offset (Fit.offset)"""
    x, y, z = at[0] * scale, at[2] * scale, -at[1] * scale
    x, z = blendmap.turned(x, z, turn)
    return (x - offset[0], y - offset[1], z - offset[2])
