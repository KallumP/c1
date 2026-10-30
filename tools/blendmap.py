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
