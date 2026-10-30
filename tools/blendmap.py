"""
turn a map modelled in blender (exported as .obj) into the parts of a
custom level: collision cells, world meshes, crash's spawn and a camera
path. tools/nslevel.py puts them together (python tools/nslevel.py map).

the .obj is read as blender exports it by default: y up, so its x, y and z
are the zone's x, y (up) and z.
"""


class Tri:
    """a triangle: three vertex indices, and the object and material it
    came from"""
    def __init__(self, verts, obj, mat):
        self.verts, self.obj, self.mat = verts, obj, mat

    def __repr__(self):
        return "Tri(%r, %r, %r)" % (self.verts, self.obj, self.mat)


class Mesh:
    def __init__(self, verts, tris):
        self.verts, self.tris = verts, tris


def turned(x, z, turn):
    """(x, z) turned by turn degrees (a multiple of 90) about the up axis,
    anticlockwise seen from above"""
    for _ in range(turn // 90 % 4):
        x, z = z, -x
    return x, z


def read_obj(text, scale, turn=0):
    """a mesh from the text of a .obj: vertices in zone units (scale zone
    units per .obj unit, turned by turn degrees about the up axis) and
    triangles (polygons are fanned). texture coordinates and normals are
    ignored"""
    if turn % 90:
        raise ValueError("turn (%d) has to be a multiple of 90 degrees" % turn)
    verts, tris = [], []
    obj, mat = None, None
    for line_no, line in enumerate(text.splitlines(), 1):
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "v":
            x, y, z = (float(f) * scale for f in fields[1:4])
            x, z = turned(x, z, turn)
            verts.append((x, y, z))
        elif fields[0] == "o" or fields[0] == "g":
            obj = " ".join(fields[1:])
        elif fields[0] == "usemtl":
            mat = " ".join(fields[1:])
        elif fields[0] == "f":
            idx = []
            for f in fields[1:]:
                i = int(f.split("/")[0])
                i = i - 1 if i > 0 else len(verts) + i
                if not 0 <= i < len(verts):
                    raise ValueError("line %d: face uses vertex %s, which isn't there" % (line_no, f))
                idx.append(i)
            for k in range(1, len(idx) - 1):
                tris.append(Tri((idx[0], idx[k], idx[k + 1]), obj, mat))
    return Mesh(verts, tris)


VERTEX_MAX = 32760  # world mesh vertices are 13 bits of multiples of 8 (src/formats/wgeo.h)


class Fit:
    """a mesh moved into a zone: mesh (vertices in zone units relative to
    the zone, on multiples of 8), the zone's size (w, h, d) and the offset
    the mesh was moved by (where the zone's corner was in the mesh)"""
    def __init__(self, mesh, size, offset):
        self.mesh, self.size, self.offset = mesh, size, offset


def fit(mesh, cell, headroom, margin=0):
    """mesh moved so its lowest corner is margin (zone units) in from the
    zone's, with each side of the zone a power of two cells, margin to
    spare along x and z, and headroom above it"""
    lo = [min(v[i] for v in mesh.verts) - margin for i in range(3)]
    verts = [tuple(int(round((v[i] - lo[i]) / 8)) * 8 for i in range(3)) for v in mesh.verts]
    size = []
    for i in range(3):
        extent = max(v[i] for v in verts)
        if extent > VERTEX_MAX:
            raise ValueError("the map is %d zone units along %s, more than %d; scale it down"
                             % (extent, "xyz"[i], VERTEX_MAX))
        side = cell
        while side < extent + (headroom if i == 1 else margin):
            side *= 2
        size.append(side)
    return Fit(Mesh(verts, mesh.tris), tuple(size), tuple(lo))


# collision: the game's collision is an octree of solid cells (see
# blocks_rect_bytes in nslevel.py), so the faces are turned into cells

FACING = 0.5  # a face whose normal's y is over this faces up (under -FACING, down)

def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def normal(mesh, tri):
    """a triangle's unit normal (out of its front, which is anticlockwise),
    or None if it's flat"""
    a, b, c = (mesh.verts[i] for i in tri.verts)
    n = cross(sub(b, a), sub(c, a))
    length = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
    return None if length == 0 else (n[0] / length, n[1] / length, n[2] / length)


def is_pit(tri):
    return (tri.obj or "").lower().startswith("pit")


def is_spawn(tri):
    """faces of an object named spawn... only mark where crash starts"""
    return (tri.obj or "").lower().startswith("spawn")


def behind(mesh, tri, n, cell):
    """the cells (i, j, k) just behind a face (with unit normal n), so its
    solid side is on the cell boundary nearest to it"""
    a, b, c = (mesh.verts[i] for i in tri.verts)
    centre = [(a[i] + b[i] + c[i]) / 3 for i in range(3)]
    longest = max(max(abs(d) for d in sub(p, q)) for p, q in ((a, b), (b, c), (c, a)))
    steps = max(1, int(-(-longest // (cell / 4))))  # samples at most a quarter cell apart
    found = set()
    for u in range(steps + 1):
        for v in range(steps + 1 - u):
            s, t = u / steps, v / steps
            key = []
            for i in range(3):
                p = a[i] + (b[i] - a[i]) * s + (c[i] - a[i]) * t
                p += (centre[i] - p) / 1000  # off the triangle's edges, which can lie on cell boundaries
                key.append(int((p - n[i] * cell / 2) // cell))
            found.add(tuple(key))
    return found


def inside(key, size, cell):
    return all(0 <= key[i] < size[i] // cell for i in range(3))


def solid_cells(mesh, size, cell):
    """{(i, j, k): "ground" or "pit"}: the cells just behind each face.
    faces of objects named pit... are deadly, and win where they share a
    cell with ground. cells outside the zone (size w, h, d) are left out"""
    cells = {}
    for tri in mesh.tris:
        n = normal(mesh, tri)
        if n is None or is_spawn(tri):
            continue
        kind = "pit" if is_pit(tri) else "ground"
        for key in behind(mesh, tri, n, cell):
            if inside(key, size, cell) and cells.get(key) != "pit":
                cells[key] = kind
    return cells


def floor_cells(mesh, size, cell):
    """the cells just behind faces facing up: somewhere to stand, unlike
    the top of a wall"""
    cells = set()
    for tri in mesh.tris:
        n = normal(mesh, tri)
        if n is not None and n[1] > FACING and not is_spawn(tri):
            cells |= {key for key in behind(mesh, tri, n, cell) if inside(key, size, cell)}
    return cells


# world meshes (wgeo): the faces, sliced along z so the sort list can drop
# the pieces behind the camera a little at a time (see slst_items in
# nslevel.py), split into meshes of at most WGEO_MAX vertices and polygons

WGEO_MAX = 4096   # polygon and vertex indices are 12 bits
WGEO_ITEMS_MAX = 7500  # vertices and polygons (8 bytes each) a mesh fits in a page beside its header
WORLDS_MAX = 8    # world meshes in a zone
LIGHT = (0.3, 0.8, 0.5)  # towards the light: above, a little to the side and towards the camera
LIGHT_LEN = sum(c * c for c in LIGHT) ** 0.5


def shade(n):
    """a face's vertex colour: grey, from 70 facing away from the light to
    128 (full brightness) facing it"""
    lit = max(0.0, sum(n[i] * LIGHT[i] for i in range(3)) / LIGHT_LEN)
    level = int(round(128 * (0.55 + 0.45 * lit)))
    return (level, level, level)


def clip(points, axis, value, keep_above):
    """the part of a convex polygon on one side of the plane where axis is
    value. a cut point is worked out from the edge's ends in the same order
    whichever way round the edge is, so two faces sharing an edge get
    exactly the same point"""
    out = []
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        p_in = p[axis] >= value if keep_above else p[axis] <= value
        q_in = q[axis] >= value if keep_above else q[axis] <= value
        if p_in:
            out.append(p)
        if p_in != q_in:
            lo, hi = sorted((p, q))
            t = (value - lo[axis]) / (hi[axis] - lo[axis])
            cut = [lo[k] + (hi[k] - lo[k]) * t for k in range(3)]
            cut[axis] = value
            out.append(tuple(cut))
    return out


def slices(points, piece):
    """a convex polygon cut by the planes z = multiples of piece"""
    zs = [p[2] for p in points]
    for k in range(int(min(zs) // piece), int(max(zs) // piece) + 1):
        part = clip(clip(points, 2, k * piece, True), 2, (k + 1) * piece, False)
        if len(part) >= 3:
            yield part


def snap(p):
    return tuple(int(round(c / 8)) * 8 for c in p)


def world_meshes(mesh, piece, ground, side):
    """world meshes for a mesh's faces: a list of (vertices (x, y, z,
    colour), polygons (a, b, c, tinf, tpag)), with ground (tinf, tpag) on
    faces facing up and side on the rest. faces facing down aren't drawn,
    since the camera looks down on the level and they would hide it"""
    meshes = []
    verts, polys, index = [], [], {}

    def add(tri, texture):
        nonlocal verts, polys, index
        new = [v for v in tri if v not in index]
        if (len(verts) + len(set(new)) > WGEO_MAX or len(polys) + 1 > WGEO_MAX
                or len(verts) + len(set(new)) + len(polys) + 1 > WGEO_ITEMS_MAX):
            meshes.append((verts, polys))
            verts, polys, index = [], [], {}
        ids = []
        for v in tri:
            if v not in index:
                index[v] = len(verts)
                verts.append(v)
            ids.append(index[v])
        polys.append(tuple(ids) + texture)

    for tri in mesh.tris:
        n = normal(mesh, tri)
        if n is None or n[1] < -FACING or is_spawn(tri):
            continue
        texture = ground if n[1] > FACING else side
        colour = shade(n)
        for part in slices([mesh.verts[i] for i in tri.verts], piece):
            part = [snap(p) for p in part]
            for k in range(1, len(part) - 1):
                a, b, c = part[0], part[k], part[k + 1]
                if cross(sub(b, a), sub(c, a)) == (0, 0, 0):
                    continue
                add([v + (colour,) for v in (a, b, c)], texture)
    if polys:
        meshes.append((verts, polys))
    if len(meshes) > WORLDS_MAX:
        raise ValueError("the map needs %d world meshes, more than %d; use fewer faces"
                         % (len(meshes), WORLDS_MAX))
    return meshes


# crash's spawn and the camera path (zone units relative to the zone)

CAM_OFFSET = (101, 1316)  # follow camera from crash: x, height (as on n. sanity beach)
CAM_LEAD = 1450           # how far ahead of the camera crash is (as on the beach)
CAM_EDGE = 200            # how far in from the zone's ends the camera path stays
HEADROOM = 2              # empty cells crash needs above the ground to start on it


def ground_tops(cells, floors, i, k, cell, headroom=1):
    """the tops of the floor cells in column (i, k) with headroom empty
    cells above them, lowest first"""
    js = sorted(j for (ci, j, ck) in floors if ci == i and ck == k)
    return [(j + 1) * cell for j in js
            if not any((i, j + h, k) in cells for h in range(1, headroom + 1))]


def spawn(mesh, cells, size, cell):
    """where crash starts, (x, y, z): on the ground below the middle of an
    object named spawn..., or without one, on the ground nearest the start
    of the route (the +z end), nearest the middle across"""
    marker = {i for tri in mesh.tris if is_spawn(tri) for i in tri.verts}
    floors = floor_cells(mesh, size, cell)
    columns = {(i, k) for i, _, k in floors}
    if marker:
        x = sum(mesh.verts[i][0] for i in marker) / len(marker)
        z = sum(mesh.verts[i][2] for i in marker) / len(marker)
        bottom = min(mesh.verts[i][1] for i in marker)
        tops = [t for t in ground_tops(cells, floors, int(x // cell), int(z // cell), cell)
                if t <= bottom + cell]
        if not tops:
            raise ValueError("there's no ground below the spawn object")
        return (int(round(x)), tops[-1], int(round(z)))
    middle = size[0] / 2
    for i, k in sorted(columns, key=lambda c: (-c[1], abs((c[0] + 0.5) * cell - middle))):
        tops = ground_tops(cells, floors, i, k, cell, HEADROOM)
        if tops:
            return (i * cell + cell // 2, tops[-1], k * cell + cell // 2)
    raise ValueError("the map has no ground for crash to start on")


def camera_path(mesh, cells, size, cell, start, step):
    """camera path points (x, y, z), step apart along -z from behind crash's
    start to the far end of the zone, CAM_OFFSET above the ground CAM_LEAD
    ahead of each point (the ground nearest the last height, which is kept
    over gaps), along crash's start x"""
    x, height, z = start
    i = x // cell
    floors = floor_cells(mesh, size, cell)
    first = min(z + CAM_LEAD, size[2] - CAM_EDGE)
    points = []
    for cz in range(first, CAM_EDGE, -step):
        k = (cz - CAM_LEAD) // cell
        tops = ground_tops(cells, floors, i, k, cell) if k >= 0 else []
        if tops:
            height = min(tops, key=lambda t: abs(t - height))
        points.append((x + CAM_OFFSET[0], height + CAM_OFFSET[1], cz))
    return points
