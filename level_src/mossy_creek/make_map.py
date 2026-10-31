"""
make mossy_creek.obj, .mtl and objects.json: an organic level, made for c1x.
run it from anywhere (python level_src/mossy_creek/make_map.py); it writes
next to itself.

the ground is a heightfield on a 1 m grid, cut along the contours of smooth
fields (water, stones, boulders, terraces, the rim, painted paths), so
shores and ledges are curves rather than grid lines. each piece between the
cuts is flat or gently rolling; where neighbouring pieces have different
heights, a wall joins them. it's all one surface, so nothing overlaps (the
game has no depth test for level geometry).

blender coordinates: x across, y along the route, z up; the .obj is written
as blender's default export (x, z, -y).
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "mossy_creek"

X0, X1 = -15.0, 15.0  # across
Y0, Y1 = -4.0, 116.0  # along the route
# the game slices the map every 1.28 m along the route and 2.56 m across,
# from 0.32 m (its margin) outside the map's corner (the -x, far +y one).
# the grid's lines are on those slices, so they don't cut it up any more
SLICE_Y, SLICE_X, MARGIN = 1.28, 2.56, 0.32
YS = sorted([Y1] + [Y1 + MARGIN - SLICE_Y * m for m in range(1, int((Y1 - Y0) / SLICE_Y) + 1)])
# and twice as many rows over the creek and the pond, so the stones and lily
# pads (which are only a little bigger than a cell) keep their shape
FINE = [(18.0, 35.0), (80.0, 98.0)]
YS = sorted(YS + [(a + b) / 2 for a, b in zip(YS, YS[1:]) if any(lo < a < hi for lo, hi in FINE)])
# across: every half slice in the middle, a slice out on the hilltops nobody walks on
XS = [X0, X0 - MARGIN + SLICE_X] + [X0 - MARGIN + SLICE_X * k / 2 for k in range(4, 21)] + \
     [X0 - MARGIN + SLICE_X * 11, X1]
WL = -1.0  # water level
END = 108  # where the warp pad is


# noise

def hash2(i, j, seed):
    h = (i * 374761393 + j * 668265263 + seed * 2147483647) & 0xffffffff
    h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
    return ((h ^ (h >> 16)) & 0xffff) / 32767.5 - 1.0


def smooth(t):
    return t * t * (3 - 2 * t)


def vnoise(x, y, seed):
    i, j = math.floor(x), math.floor(y)
    fx, fy = smooth(x - i), smooth(y - j)
    a, b = hash2(i, j, seed), hash2(i + 1, j, seed)
    c, d = hash2(i, j + 1, seed), hash2(i + 1, j + 1, seed)
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy


def fbm(x, y, seed, octaves=3):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * vnoise(x, y, seed + o * 17)
        norm += amp
        x, y, amp = x * 2.03, y * 2.03, amp * 0.5
    return total / norm


def sstep(a, b, t):
    if a == b:
        return 1.0 if t >= b else 0.0
    return smooth(min(max((t - a) / (b - a), 0.0), 1.0))


def smax(a, b, k=1.5):
    h = min(max(0.5 + 0.5 * (a - b) / k, 0.0), 1.0)
    return b + (a - b) * h + k * h * (1 - h)


def lerp_keys(keys, t):
    """smoothly between (t, value) keys"""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * smooth((t - t0) / (t1 - t0))
    return keys[-1][1]


# the shape of the level

def path_x(y):
    """the middle of the trail"""
    return 3.2 * math.sin(y * 0.105) + 1.6 * math.sin(y * 0.27 + 1.3)


GROUND = [(-10, 0.0), (20, 0.0), (36, 0.0), (44, 0.35), (54, 0.2), (72, 2.2), (77, 2.2), (82, 0.0),
          (98, 0.0), (104, 1.2), (130, 1.2)]


def base_height(x, y):
    d = abs(x - path_x(y))
    hills = 0.7 * sstep(2.5, 8.0, d) * (0.6 + 0.5 * fbm(x * 0.15, y * 0.15, 3))
    hills *= sstep(14, 22, y)  # the beach is flat
    dunes = 0.18 * fbm(x * 0.3, y * 0.3, 7)
    return lerp_keys(GROUND, y) + hills + dunes


def lagoon(x, y):
    """the sea on the left of the beach"""
    shore = -4.5 + 1.8 * math.sin(y * 0.33) + 1.2 * fbm(x * 0.2, y * 0.2, 11)
    return min(shore - x, (17.5 + 2.0 * fbm(x * 0.2, 0.0, 12)) - y)


def river_y(x):
    return 25.0 + 1.4 * math.sin(x * 0.28) + 0.8 * fbm(x * 0.25, 0.0, 21)


def river(x, y):
    width = 4.5 + 0.4 * fbm(x * 0.3, 1.0, 22)
    return width - abs(y - river_y(x))


POND = (path_x(89) - 1.5, 89.0)


def pond(x, y):
    dx, dy = (x - POND[0]) / 6.5, (y - POND[1]) / 5.0
    wobble = 0.12 * fbm(x * 0.35, y * 0.35, 31)
    return (1.0 + wobble - math.sqrt(dx * dx + dy * dy)) * 4.5


def wet(x, y):
    return max(lagoon(x, y), river(x, y), pond(x, y))


def blob(cx, cy, r, seed, wobble=0.18):
    """a roundish field: r - distance, with its edge wobbling"""
    def f(x, y):
        a = math.atan2(y - cy, x - cx)
        rr = r * (1 + wobble * (0.6 * math.sin(3 * a + seed) + 0.4 * math.sin(5 * a + seed * 1.7)))
        return rr - math.hypot(x - cx, y - cy)
    return f


def on_path(y, dx=0.0):
    return path_x(y) + dx


def crossing():
    """where the trail goes into the creek and comes out of it, along y"""
    ys = [y / 20 for y in range(15 * 20, 36 * 20)]
    inside = [y for y in ys if river(path_x(y), y) > 0]
    return inside[0], inside[-1]


def stepping_stones(count=3, r=0.95, wobble=(0.3, -0.4, 0.25)):
    """stones evenly across the creek on the trail: the gaps between them,
    and to the banks, all the same"""
    y0, y1 = crossing()
    gap = (y1 - y0 - 2 * r * count) / (count + 1)
    return [(on_path(y0 + gap + r + k * (gap + 2 * r), wobble[k]), y0 + gap + r + k * (gap + 2 * r), r)
            for k in range(count)]


# stepping stones across the creek, along the trail, and some to the side
STONES = stepping_stones() + [(-7.5, 24.2, 1.0), (8.5, 26.8, 1.0), (-11.0, 26.5, 1.2)]
# lily pads across the pond
PADS = [(POND[0] - 2.2, 84.6, 1.15), (POND[0] - 3.6, 87.2, 1.1), (POND[0] - 1.9, 89.7, 1.2),
        (POND[0] - 3.4, 92.2, 1.05), (POND[0] + 1.6, 88.6, 0.9), (POND[0] + 3.4, 91.0, 0.8)]
ISLANDS = [blob(x, y, r, 3 + k, 0.1) for k, (x, y, r) in enumerate(STONES)] + \
          [blob(x, y, r, 40 + k, 0.08) for k, (x, y, r) in enumerate(PADS)]


def water(x, y):
    return min(wet(x, y), -max(f(x, y) for f in ISLANDS))


def corridor(y):
    return 9.0 + 1.6 * fbm(0.0, y * 0.07, 51)


def rim(x, y):
    """the hills either side and at the ends"""
    side = abs(x - 0.5 * path_x(y)) - corridor(y) + 1.4 * fbm(x * 0.22, y * 0.22, 52)
    ends = max(-1.0 - y, y - (END + 5.0)) + 1.5 * fbm(x * 0.2, y * 0.2, 53)
    return smax(side, ends, 1.0)


def rim_height(x, y):
    return 3.3 + 1.0 * sstep(0, 4, rim(x, y)) + 0.4 * fbm(x * 0.12, y * 0.12, 54)


# rounded mossy boulders: (x, y, radius, edge height, dome height)
BOULDERS = [(7.2, 6.5, 1.3, 0.5, 0.4), (-2.4, 15.2, 1.0, 0.4, 0.3),
            (on_path(37, 3.6), 37.0, 1.6, 0.6, 0.5), (on_path(40, -4.2), 40.0, 2.0, 0.7, 0.6),
            (on_path(45, 3.0), 45.0, 1.2, 0.5, 0.3), (on_path(48.5, -2.9), 48.5, 1.4, 0.55, 0.4),
            (on_path(78, 4.5), 78.0, 1.5, 0.6, 0.5), (on_path(97, -4.5), 97.0, 1.3, 0.5, 0.4)]
BOULDER_FIELDS = [blob(x, y, r, 60 + k) for k, (x, y, r, _, _) in enumerate(BOULDERS)]


def terrace(level):
    """terraced banks either side of the climb up the gully"""
    inner = 2.6 + 2.6 * level

    def f(x, y):
        d = abs(x - path_x(y)) - inner - 0.9 * fbm(x * 0.3, y * 0.3, 70 + level)
        span = min(y - (52.0 + 2 * level), (75.0 - 1.5 * level) - y) + 1.2 * fbm(x * 0.3, y * 0.2, 75)
        return -smax(-d, -span, 2.0)  # rounded where the terrace ends
    return f


TERRACE_UP = 0.75


def trail(x, y):
    return 1.3 + 0.35 * fbm(0.0, y * 0.3, 81) - abs(x - path_x(y))


def sand(x, y):
    return max(16.0 + 2.5 * fbm(x * 0.2, 0.0, 82) - y, lagoon(x, y) + 3.0, river(x, y) + 1.6,
               pond(x, y) + 1.4)


CLEARING = (path_x(END), float(END))
CLEARING_H = 1.35


def clearing(x, y):
    return blob(CLEARING[0], CLEARING[1], 2.4, 90, 0.06)(x, y)


# features, in the order the ground is cut by them: (name, field)
FEATURES = [("water", water), ("wet", wet), ("rim", rim)] + \
           [("boulder%d" % k, f) for k, f in enumerate(BOULDER_FIELDS)] + \
           [("terrace0", terrace(0)), ("terrace1", terrace(1)),
            ("clearing", clearing), ("sand", sand), ("trail", trail)]
NAMES = [n for n, _ in FEATURES]


def height(x, y, act):
    if "water" in act:
        return WL
    if "clearing" in act:
        return CLEARING_H
    if "wet" in act:  # a stone or a lily pad
        return WL + 0.45 + 0.06 * fbm(x * 0.8, y * 0.8, 91)
    h = base_height(x, y)
    if "rim" in act:
        h += rim_height(x, y)
    for k, (bx, by, r, edge, dome) in enumerate(BOULDERS):
        if "boulder%d" % k in act:
            h += edge + dome * sstep(0, r * 0.8, BOULDER_FIELDS[k](x, y))
    for level in (0, 1):
        if "terrace%d" % level in act:
            h += TERRACE_UP
    return h


def floor_material(act, y):
    if "water" in act:
        return "water"
    if "clearing" in act:
        return "stone"
    if "wet" in act:
        return "leaf" if y > 70 else "rock"
    if any(a.startswith("boulder") for a in act):
        return "moss"
    if "rim" in act:
        return "moss"
    if "terrace0" in act or "terrace1" in act:
        return "grass"
    if "sand" in act:
        return "sand"
    if "trail" in act:
        return "dirt"
    return "grass"


def wall_material(act, y):
    if "clearing" in act:
        return "stone"
    if "wet" in act and "water" not in act:
        return "rock" if y < 70 else "wood"  # lily pads have a stem-ish side
    if any(a.startswith("boulder") for a in act):
        return "rock"
    if "rim" in act or "terrace0" in act or "terrace1" in act:
        return "cliff"
    return "dirt"


# cutting the grid into pieces

def clip(poly, k, keep_in):
    """the part of poly (a list of (x, y, values)) where values[k] > 0
    (keep_in) or <= 0 (not keep_in)"""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ain, bin_ = (a[2][k] > 0) == keep_in, (b[2][k] > 0) == keep_in
        if ain:
            out.append(a)
        if ain != bin_:
            # interpolate from the lower-keyed end, so both sides of a shared edge cut it alike
            p, q = (a, b) if (a[0], a[1]) < (b[0], b[1]) else (b, a)
            t = p[2][k] / (p[2][k] - q[2][k])
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t,
                        tuple(pv + (qv - pv) * t for pv, qv in zip(p[2], q[2]))))
    return out if len(out) >= 3 else None


def key(p):
    return (round(p[0], 4), round(p[1], 4))


def build():
    nx, ny = len(XS) - 1, len(YS) - 1
    grid = {}
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = XS[i], YS[j]
            grid[i, j] = (x, y, tuple(f(x, y) for _, f in FEATURES))
    pieces = []  # (polygon, active names)
    for j in range(ny):
        for i in range(nx):
            a, b, c, d = grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]
            tris = [(a, b, c), (a, c, d)] if (i + j) % 2 else [(a, b, d), (b, c, d)]
            for tri in tris:
                parts = [(list(tri), ())]
                for k, name in enumerate(NAMES):
                    nxt = []
                    for poly, act in parts:
                        for keep_in in (True, False):
                            part = clip(poly, k, keep_in)
                            if part:
                                nxt.append((part, act + ((name,) if keep_in else ())))
                    parts = nxt
                pieces.extend((poly, frozenset(act)) for poly, act in parts)
    return pieces


def write(pieces):
    verts, vindex = [], {}
    faces = {}  # (object, material) -> [vertex ids]

    def vert(x, y, z):
        k = (round(x, 4), round(y, 4), round(z, 4))
        if k not in vindex:
            vindex[k] = len(verts) + 1
            verts.append(k)
        return vindex[k]

    def add(obj, mat, pts):
        # obj coordinates are (x, z, -y): anticlockwise from above in blender is anticlockwise there too
        faces.setdefault((obj, mat), []).append([vert(*p) for p in pts])

    edges = {}
    for n, (poly, act) in enumerate(pieces):
        pts = [(p[0], p[1], height(p[0], p[1], act)) for p in poly]
        area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                   for i in range(len(pts)))
        if abs(area) < 1e-6:
            continue
        if area < 0:
            pts.reverse()
        cy = sum(p[1] for p in pts) / len(pts)
        add("pit" if "water" in act else "terrain", floor_material(act, cy), pts)
        for i in range(len(pts)):
            p, q = pts[i], pts[(i + 1) % len(pts)]
            edges.setdefault(frozenset((key(p), key(q))), []).append((p, q, act))

    walls = 0
    for sides in edges.values():
        if len(sides) != 2:
            continue
        (p1, q1, act1), (p2, q2, act2) = sides
        # p1 -> q1 runs anticlockwise round piece 1, so piece 1 is on its left
        h1 = {key(p1): p1[2], key(q1): q1[2]}
        h2 = {key(p2): p2[2], key(q2): q2[2]}
        ka, kb = key(p1), key(q1)
        da, db = h1[ka] - h2[ka], h1[kb] - h2[kb]
        if abs(da) < 0.02 and abs(db) < 0.02:
            continue
        high_act = act1 if da + db > 0 else act2
        ax, ay, bx, by = p1[0], p1[1], q1[0], q1[1]
        top_a, top_b = max(h1[ka], h2[ka]), max(h1[kb], h2[kb])
        low_a, low_b = min(h1[ka], h2[ka]), min(h1[kb], h2[kb])
        quad = [(ax, ay, low_a), (bx, by, low_b), (bx, by, top_b), (ax, ay, top_a)]
        # as it is, it faces right of a -> b, piece 2: turn it to face piece 1 when piece 2 is higher
        if da + db < 0:
            quad.reverse()
        add("terrain", wall_material(high_act, (ay + by) / 2), quad)
        walls += 1

    lines = ["# %s, made for c1x by make_map.py" % NAME, "mtllib %s.mtl" % NAME]
    lines += ["v %.4f %.4f %.4f" % (x, z, -y) for x, y, z in verts]
    for obj in ("pit", "terrain"):
        lines.append("o " + obj)
        for (o, mat), fs in sorted(faces.items()):
            if o != obj:
                continue
            lines.append("usemtl " + mat)
            for f in fs:
                ids = []
                for v in f:  # drop repeated corners (a wall coming to a point)
                    if v not in ids:
                        ids.append(v)
                if len(ids) >= 3:
                    lines.append("f " + " ".join(map(str, ids)))
    with open(os.path.join(HERE, NAME + ".obj"), "w") as f:
        f.write("\n".join(lines) + "\n")
    count = sum(len(fs) for fs in faces.values())
    print("%d vertices, %d faces (%d walls)" % (len(verts), count, walls))


MATERIALS = {"cliff": "cliff.png", "dirt": "dirt.png", "grass": "grass.png", "leaf": "leaf.png",
             "moss": "moss.png", "rock": "rock.png", "sand": None, "stone": "stone.png",
             "water": "water.png", "wood": "wood.png"}


def write_mtl():
    lines = ["# materials of %s.obj (sand has no image, so it gets n. sanity beach's)" % NAME]
    for mat, image in sorted(MATERIALS.items()):
        lines += ["", "newmtl " + mat, "Kd 1.0 1.0 1.0"]
        if image:
            lines.append("map_Kd " + image)
    with open(os.path.join(HERE, NAME + ".mtl"), "w") as f:
        f.write("\n".join(lines) + "\n")


# objects

def ground(x, y):
    act = frozenset(n for n, f in FEATURES if f(x, y) > 0)
    return height(x, y, act)


def at(x, y, up=0.05):
    return [round(x, 2), round(y, 2), round(ground(x, y) + up, 2)]


def box(type_, x, y, **extra):
    o = {"kind": "box", "type": type_, "at": at(x, y)}
    o.update(extra)
    return o


def objects():
    p = path_x
    b = BOULDERS
    pads = PADS
    objs = [{"kind": "spawn", "at": at(p(4), 4.0, 0.3)}]
    # the beach
    objs += [box("aku_aku", p(8) + 1.5, 8.0), box("basic", p(11), 11.0), box("basic", p(12.5) - 0.6, 12.5),
             box("basic", p(14) - 1.4, 14.0), box("question", b[0][0], b[0][1])]
    # the creek: a box on a side stone
    objs += [box("basic", STONES[-2][0], STONES[-2][1])]
    # the hills
    objs += [box("checkpoint", p(33.5), 33.5),
             box("basic", p(36.5) - 1.0, 36.5), box("basic", p(38) + 0.8, 38.0),
             box("life", b[3][0], b[3][1]), box("arrow", b[3][0] + 2.4, b[3][1] - 1.0),
             box("basic", p(42), 42.0, stack=2), box("slatted", p(46) - 0.8, 46.0),
             box("basic", b[5][0], b[5][1]), box("basic", p(50.5) + 1.0, 50.5)]
    # the gully: boxes on the trail and up on the terraces
    objs += [box("basic", p(56), 56.0), box("basic", p(59) + 0.7, 59.0),
             box("basic", p(61) + 3.7, 61.0), box("basic", p(62) + 3.9, 62.0),
             box("question", p(64) - 6.5, 64.0), box("arrow", p(64) - 3.3, 64.0),
             box("iron", p(67) + 0.9, 67.0), box("basic", p(69) - 0.5, 69.0)]
    # the ridge: a switch, and the outline boxes it fills in, up to the boulder
    objs += [box("checkpoint", p(74), 74.0), box("switch", p(76) - 2.0, 76.0),
             box("outline", b[6][0] - 2.2, b[6][1] - 0.4), box("outline", b[6][0] - 2.2, b[6][1] - 0.4 + 1.0),
             box("aku_aku", b[6][0], b[6][1])]
    # the pond: boxes on the side pads
    objs += [box("basic", pads[4][0], pads[4][1]), box("life", pads[5][0], pads[5][1]),
             box("basic", p(83) + 3.0, 83.0)]
    # up to the clearing
    objs += [box("basic", p(99), 99.0), box("basic", p(101) + 0.8, 101.0), box("question", b[7][0], b[7][1])]
    objs.append({"kind": "end", "at": at(CLEARING[0], CLEARING[1], 0.0), "raise": 0.15})
    with open(os.path.join(HERE, "objects.json"), "w") as f:
        f.write("[\n" + ",\n".join("  " + json.dumps(o) for o in objs) + "\n]\n")


if __name__ == "__main__":
    write(build())
    write_mtl()
    objects()
