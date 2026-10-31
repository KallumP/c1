"""
the objects placed in a custom level (where crash starts, where the level
ends, boxes), from the objects.json in its level source: a list of objects,
each a kind and a position in blender (metres, z up), e.g.

  [{"kind": "spawn", "at": [0, 2, 0]},
   {"kind": "box", "subtype": 2, "at": [1, 10, 0], "stack": 2},
   {"kind": "end", "at": [0, 48, 1.2]}]

see doc/custom_levels.md. tools/nslevel.py puts them in the level.
"""
import json
import numbers

import blendmap

KINDS = ("spawn", "end", "box")
ONCE = ("spawn", "end")  # a level has at most one of these
SETTINGS = ("kind", "at", "raise")  # every kind takes these
BOX_SETTINGS = ("subtype", "stack")  # and a box these
BOX_SUBTYPES = (2, 3, 4, 5, 6, 7, 8, 9, 10, 13)  # the box subtypes n. sanity beach has, to copy


class LevelObject:
    """an object: its kind, where it is in blender (x, y, z), how far
    (metres) to raise it off the ground it goes on, and for a box, its
    subtype and how many high its stack is"""
    def __init__(self, kind, at, raise_by=0, subtype=None, stack=1):
        self.kind, self.at, self.raise_by = kind, at, raise_by
        self.subtype, self.stack = subtype, stack

    def __repr__(self):
        return "LevelObject(%r, %r, %r, %r, %r)" % (self.kind, self.at, self.raise_by, self.subtype, self.stack)


def is_number(v):
    return isinstance(v, numbers.Real) and not isinstance(v, bool)


def is_whole(v):
    return isinstance(v, numbers.Integral) and not isinstance(v, bool)


def read_objects(text):
    """the objects (LevelObject) in the text of an objects.json; anything
    that isn't a list of them, each a known kind (at most one spawn and one
    end) at three numbers, is a ValueError saying which object (from 1)"""
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
        kind = item.get("kind")
        if kind is None:
            raise ValueError("object %d has no kind" % n)
        if kind not in KINDS:
            raise ValueError("object %d: unknown kind %s (it can be %s)" % (n, kind, ", ".join(KINDS)))
        settings = SETTINGS + (BOX_SETTINGS if kind == "box" else ())
        unknown = [k for k in item if k not in settings]
        if unknown:
            raise ValueError("object %d: unknown setting %s (a %s takes %s)"
                             % (n, unknown[0], kind, ", ".join(settings)))
        if kind in ONCE and any(o.kind == kind for o in objects):
            raise ValueError("object %d: there's already a %s (a level has one)" % (n, kind))
        at = item.get("at")
        if not (isinstance(at, list) and len(at) == 3 and all(is_number(c) for c in at)):
            raise ValueError("object %d: at should be its position in blender, [x, y, z] in metres" % n)
        raise_by = item.get("raise", 0)
        if not is_number(raise_by):
            raise ValueError("object %d: raise should be how far to raise it off the ground, in metres" % n)
        subtype, stack = None, 1
        if kind == "box":
            subtype = item.get("subtype")
            if subtype not in BOX_SUBTYPES or not is_whole(subtype):
                raise ValueError("object %d: a box's subtype should be one of %s"
                                 % (n, ", ".join(map(str, BOX_SUBTYPES))))
            stack = item.get("stack", 1)
            if not is_whole(stack) or stack < 1:
                raise ValueError("object %d: stack should be how many boxes high it is, 1 or more" % n)
        objects.append(LevelObject(kind, tuple(at), raise_by, subtype, stack))
    return objects


def to_zone(at, scale, turn, offset):
    """where at (a position in blender: x, y, z with z up, in metres) is in
    the level (zone units, (x, y up, z)), as a vertex there in the .obj is:
    the .obj has blender's (x, z, -y), which read_obj scales and turns by
    turn degrees and fit moves by offset (Fit.offset)"""
    x, y, z = at[0] * scale, at[2] * scale, -at[1] * scale
    x, z = blendmap.turned(x, z, turn)
    return (x - offset[0], y - offset[1], z - offset[2])
