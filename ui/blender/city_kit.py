# Builds the city kit: modular building pieces and trees with baked ambient
# occlusion, exported as one glTF binary for the 3D city (ui/src/city/kit.ts).
#
#   blender -b --factory-startup -P ui/blender/city_kit.py -- ui/public/city-kit.glb [--preview out.png]
#
# Conventions the app relies on:
# - One object per piece, at the origin. Blender +Z is up and the front faces
#   -Y; in glTF / three.js that is +Y up and the front facing +Z.
# - Buildings are stacks: a ground piece, floor pieces (one storey each, open
#   top and bottom but for a dark cap) and a roof piece. Footprints are the
#   nominal sizes below; the app scales x / z to each building's lot.
# - Material names are roles (wall, trim, window, ...). The app picks the real
#   material per building and damage, so colours here only serve the preview.
# - Each window pane maps to one cell of a CELLS x CELLS window atlas
#   (TEXCOORD_0); the app shifts cells per floor so lit windows differ.
# - COLOR_0 is the baked ambient occlusion (linear, multiplied in).
# - Custom properties (glTF extras) are anchors in three.js coordinates.
import math
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
OUT = argv[0] if argv else "city-kit.glb"
PREVIEW = argv[argv.index("--preview") + 1] if "--preview" in argv else None

CELLS = 32
Z = Vector((0, 0, 1))

# Nominal footprints (W along x, D along y) and storey heights; keep in step
# with NOMINAL in kit.ts and shape() in plan.ts.
COTTAGE = (6.75, 6.25, 3.2)
SHOP = (8.75, 8.0, 3.4)
APT = (9.15, 9.15, 3.1)
OFFICE = (9.6, 9.6, 3.5)
LANDMARK = (10.4, 3.5)
LM_TIERS = (1.0, 0.78, 0.56)

PREVIEW_COLORS = {
    "wall": (0.82, 0.74, 0.62), "trim": (0.86, 0.84, 0.79), "stone": (0.6, 0.58, 0.54),
    "window": (0.1, 0.14, 0.2), "glass": (0.16, 0.24, 0.32), "frame": (0.93, 0.93, 0.9),
    "roof": (0.5, 0.2, 0.15), "deck": (0.3, 0.3, 0.31), "accent": (0.6, 0.14, 0.11),
    "canvas": (0.92, 0.9, 0.84), "sign": (1.0, 0.75, 0.35), "board": (0.08, 0.08, 0.1),
    "shopfront": (0.85, 0.7, 0.45), "lobby": (0.85, 0.78, 0.6), "crownlight": (1.0, 0.8, 0.45),
    "door": (0.28, 0.16, 0.09), "metal": (0.5, 0.52, 0.55), "dark": (0.16, 0.15, 0.14),
    "spandrel": (0.1, 0.12, 0.15), "gold": (0.85, 0.6, 0.2), "brick": (0.48, 0.22, 0.15),
    "wood": (0.42, 0.27, 0.17), "leaf": (0.22, 0.42, 0.16), "bark": (0.28, 0.18, 0.11),
    "paint": (0.95, 0.95, 0.9), "railglass": (0.28, 0.36, 0.42),
}
CELL_ROLES = {"window", "glass"}


class Mod:
    """One kit piece under construction."""

    def __init__(self, name, ground=False, ao=3.0):
        self.name = name
        self.ground = ground  # occlusion sees a ground plane at z = 0
        self.ao = ao  # occlusion ray length
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.verify()
        self.roles = []
        self.extras = {}
        self.r = random.Random(name)
        MODS.append(self)

    def mi(self, role):
        if role not in self.roles:
            self.roles.append(role)
        return self.roles.index(role)

    def anchor(self, key, p):
        """A point for the app, converted to three.js axes."""
        self.extras[key] = [round(p[0], 3), round(p[2], 3), round(-p[1], 3)]

    def face(self, role, pts, out=None, cell=False, smooth=False):
        f = self.bm.faces.new([self.bm.verts.new(p) for p in pts])
        f.material_index = self.mi(role)
        f.smooth = smooth
        f.normal_update()
        if out is not None and f.normal.dot(Vector(out)) < 0:
            f.normal_flip()
        if cell:
            self.cell(f)
        return f

    def cell(self, f):
        """Maps a pane onto a random cell of the window atlas, upright."""
        n = f.normal
        right = Z.cross(n)
        if right.length < 1e-6:
            right = Vector((1, 0, 0))
        right.normalize()
        up = n.cross(right)
        us = [v.co.dot(right) for v in f.verts]
        vs = [v.co.dot(up) for v in f.verts]
        u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
        i, j = self.r.randrange(CELLS), self.r.randrange(CELLS)
        for loop in f.loops:
            a = (loop.vert.co.dot(right) - u0) / max(u1 - u0, 1e-6)
            b = (loop.vert.co.dot(up) - v0) / max(v1 - v0, 1e-6)
            loop[self.uv].uv = ((i + 0.04 + 0.92 * a) / CELLS, (j + 0.04 + 0.92 * b) / CELLS)

    def hexa(self, role, corner, skip="", bevel=0.0, smooth=False, cell=False):
        """A six-sided solid from corner(xi, yi, zi). Faces: w/e (x), n/s (y), b/t (z)."""
        vs = {}
        for xi in (0, 1):
            for yi in (0, 1):
                for zi in (0, 1):
                    vs[xi, yi, zi] = self.bm.verts.new(corner(xi, yi, zi))
        c = sum((v.co for v in vs.values()), Vector()) / 8
        sides = {
            "w": [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)],
            "e": [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
            "n": [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
            "s": [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)],
            "b": [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
            "t": [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
        }
        faces = []
        for k, idx in sides.items():
            if k in skip:
                continue
            f = self.bm.faces.new([vs[i] for i in idx])
            f.material_index = self.mi(role)
            f.smooth = smooth
            f.normal_update()
            if f.normal.dot(f.calc_center_median() - c) < 0:
                f.normal_flip()
            faces.append(f)
        for v in vs.values():
            if not v.link_faces:
                self.bm.verts.remove(v)
        if bevel > 0:
            edges = [e for e in {e for f in faces for e in f.edges} if len(e.link_faces) == 2]
            bmesh.ops.bevel(self.bm, geom=edges, offset=bevel, segments=1, affect="EDGES", profile=0.5, clamp_overlap=True)
        if cell:
            for f in faces:
                self.cell(f)
        return faces

    def box(self, role, x0, y0, z0, x1, y1, z1, **kw):
        return self.hexa(role, lambda a, b, c: ((x0, x1)[a], (y0, y1)[b], (z0, z1)[c]), **kw)

    def mbox(self, role, M, sx, sy, sz, **kw):
        """A box of size sx, sy, sz centred on the origin, transformed by M."""
        return self.hexa(role, lambda a, b, c: M @ Vector(((a - 0.5) * sx, (b - 0.5) * sy, (c - 0.5) * sz)), **kw)

    def _faces_of(self, verts, role, smooth):
        faces = {f for v in verts for f in v.link_faces}
        for f in faces:
            f.material_index = self.mi(role)
            side = abs(f.normal.z) < 0.7
            f.smooth = smooth and side
        if smooth:
            for f in faces:
                for e in f.edges:
                    if len(e.link_faces) == 2 and e.link_faces[0].smooth != e.link_faces[1].smooth:
                        e.smooth = False
        return faces

    def cyl(self, role, x, y, z0, r0, r1, h, seg=10, smooth=True, M=None):
        M = (M or Matrix()) @ Matrix.Translation((x, y, z0 + h / 2))
        verts = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r0, radius2=r1, depth=h, matrix=M)["verts"]
        return self._faces_of(verts, role, smooth)

    def blob(self, role, c, s, sub=1, jitter=0.0):
        M = Matrix.Translation(c) @ Matrix.Diagonal((*s, 1))
        verts = bmesh.ops.create_icosphere(self.bm, subdivisions=sub, radius=1.0, matrix=M)["verts"]
        for v in verts:
            v.co += Vector((self.r.uniform(-1, 1), self.r.uniform(-1, 1), self.r.uniform(-1, 1))) * jitter
        faces = self._faces_of(verts, role, False)
        for f in faces:
            f.normal_update()
        return faces


class Side:
    """One side of a W x D footprint: u runs left to right seen from outside,
    v up from z0, k outwards (negative is into the wall)."""

    def __init__(self, m, side, W, D, z0=0.0):
        self.m = m
        o, self.u, self.n, self.L = {
            "n": (Vector((-W / 2, -D / 2, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)), W),
            "e": (Vector((W / 2, -D / 2, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)), D),
            "s": (Vector((W / 2, D / 2, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), W),
            "w": (Vector((-W / 2, D / 2, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0)), D),
        }[side]
        self.o = o + Z * z0

    def P(self, u, v, k=0.0):
        return self.o + self.u * u + Z * v + self.n * k

    def box(self, role, u0, u1, v0, v1, k0, k1, skip="", bevel=0.0):
        """Skip letters: w/e the u ends, n the face against the wall, s the front, b/t."""
        return self.m.hexa(role, lambda a, b, c: self.P((u0, u1)[a], (v0, v1)[c], (k0, k1)[b]), skip, bevel)

    def quad(self, role, u0, u1, v0, v1, k=0.0, cell=False):
        return self.m.face(role, [self.P(u0, v0, k), self.P(u1, v0, k), self.P(u1, v1, k), self.P(u0, v1, k)], out=self.n, cell=cell)

    def wall(self, role, v0, v1, holes=(), u0=0.0, u1=None, k=0.0):
        """A flat wall with rectangular holes (u0, u1, v0, v1, ...)."""
        u1 = self.L if u1 is None else u1
        us = sorted({u0, u1, *[h[0] for h in holes], *[h[1] for h in holes]})
        vs = sorted({v0, v1, *[h[2] for h in holes], *[h[3] for h in holes]})
        for a, b in zip(us, us[1:]):
            for c, d in zip(vs, vs[1:]):
                uc, vc = (a + b) / 2, (c + d) / 2
                if any(h[0] < uc < h[1] and h[2] < vc < h[3] for h in holes):
                    continue
                self.quad(role, a, b, c, d, k)

    def opening(self, h, depth, pane="window", reveal="wall"):
        """Reveals into a hole and the pane at its back."""
        u0, u1, v0, v1 = h[:4]
        P, d, m = self.P, -depth, self.m
        m.face(reveal, [P(u0, v0), P(u1, v0), P(u1, v0, d), P(u0, v0, d)], out=Z)
        m.face(reveal, [P(u0, v1), P(u1, v1), P(u1, v1, d), P(u0, v1, d)], out=-Z)
        m.face(reveal, [P(u0, v0), P(u0, v1), P(u0, v1, d), P(u0, v0, d)], out=self.u)
        m.face(reveal, [P(u1, v0), P(u1, v1), P(u1, v1, d), P(u1, v0, d)], out=-self.u)
        if pane:
            self.quad(pane, u0, u1, v0, v1, d, cell=pane in CELL_ROLES)


def spaced(L, n, w, margin=0.0):
    step = (L - 2 * margin) / n
    return [(margin + step * (i + 0.5) - w / 2, margin + step * (i + 0.5) + w / 2) for i in range(n)]


def punched(m, W, D, z0, H, layout, role="wall", depth=0.16, reveal="wall", sill="trim", lintel="trim", pane="window"):
    """Four walls with punched openings: layout maps side -> holes
    (u0, u1, v0, v1[, pane role])."""
    sides = {}
    for side, holes in layout.items():
        sd = sides[side] = Side(m, side, W, D, z0)
        sd.wall(role, 0, H, holes)
        for h in holes:
            p = h[4] if len(h) > 4 else pane
            sd.opening(h, depth, pane=p, reveal=reveal)
            if p not in CELL_ROLES:
                continue
            if sill and h[2] > 0.1:
                sd.box(sill, h[0] - 0.1, h[1] + 0.1, h[2] - 0.09, h[2], 0, 0.13, skip="n")
            if lintel:
                sd.box(lintel, h[0] - 0.12, h[1] + 0.12, h[3], h[3] + 0.17, 0, 0.05, skip="n")
    return sides


def band(m, W, D, z0, z1, out, role="trim", bevel=0.03):
    m.box(role, -W / 2 - out, -D / 2 - out, z0, W / 2 + out, D / 2 + out, z1, bevel=bevel)


def ring(m, W, D, z0, z1, t, role="wall", out=0.0, bevel=0.0):
    """A parapet: four walls t thick whose outer faces sit `out` past the footprint."""
    x, y = W / 2 + out, D / 2 + out
    m.box(role, -x, -y, z0, x, -y + t, z1, bevel=bevel)
    m.box(role, -x, y - t, z0, x, y, z1, bevel=bevel)
    m.box(role, -x, -y + t, z0, -x + t, y - t, z1, bevel=bevel)
    m.box(role, x - t, -y + t, z0, x, y - t, z1, bevel=bevel)


def cap(m, W, D, z):
    """Dark top of a storey: seen only when a broken building ends there."""
    m.face("deck", [(-W / 2, -D / 2, z), (W / 2, -D / 2, z), (W / 2, D / 2, z), (-W / 2, D / 2, z)], out=Z)


def roof_deck(m, W, D, z, t=0.3):
    m.box("deck", -W / 2 + t, -D / 2 + t, z - 0.1, W / 2 - t, D / 2 - t, z, skip="b")


def ac_unit(m, x, y, z, s=1.0):
    m.box("metal", x - 0.7 * s, y - 0.55 * s, z, x + 0.7 * s, y + 0.55 * s, z + 0.9 * s, bevel=0.03)
    m.cyl("dark", x, y, z + 0.9 * s, 0.38 * s, 0.38 * s, 0.06, seg=12, smooth=False)


def vent(m, x, y, z, h=0.9):
    m.cyl("metal", x, y, z, 0.12, 0.12, h, seg=8)
    m.cyl("metal", x, y, z + h, 0.2, 0.05, 0.18, seg=8)


# ---- cottages ---------------------------------------------------------------


def gable(m, W, D, rise, oe=0.4, og=0.3, t=0.16, axis="x", wall="wall", role="roof"):
    """A gable roof on a W x D top at z = 0, ridge along `axis`."""
    if axis == "y":
        W, D = D, W
        sw = lambda x, y, z: Vector((y, x, z))  # noqa: E731
    else:
        sw = lambda x, y, z: Vector((x, y, z))  # noqa: E731
    hd = D / 2
    slope = rise / hd
    ze = -oe * slope
    for s in (-1, 1):
        n = Vector((0, s * slope, 1)).normalized()

        def corner(a, b, c, s=s, n=n):
            x = (-W / 2 - og, W / 2 + og)[a]
            p = Vector((x, s * (hd + oe), ze)) if b == 0 else Vector((x, 0, rise))
            if c == 0:
                p = p - n * t
            return sw(*p)

        m.hexa(role, corner)
    for x in (-W / 2, W / 2):
        m.face(wall, [sw(x, -hd, 0), sw(x, hd, 0), sw(x, 0, rise - 0.12)], out=sw(x, 0, 0))
    m.hexa("trim", lambda a, b, c: sw((-W / 2 - og - 0.02, W / 2 + og + 0.02)[a], (-0.16, 0.16)[b], (rise - 0.05, rise + 0.1)[c]))
    # Barge boards along the gable edges.
    for x in (-W / 2 - og, W / 2 + og):
        for s in (-1, 1):
            m.hexa(
                "trim",
                lambda a, b, c, x=x, s=s: sw(
                    x + (a - 0.5) * 0.08,
                    s * (hd + oe) * (1 - b),
                    (ze + (rise - ze) * b) - 0.28 + c * 0.3,
                ),
            )


def hip(m, W, D, rise, o=0.38, t=0.18, role="roof"):
    """A hipped roof (W >= D) on a top at z = 0."""
    hw, hd = W / 2 + o, D / 2 + o
    slope = rise / (D / 2)
    ze = -o * slope
    r = max(0.0, W / 2 - D / 2)
    E = [Vector(p) for p in [(-hw, -hd, ze), (hw, -hd, ze), (hw, hd, ze), (-hw, hd, ze)]]
    R0, R1 = Vector((-r, 0, rise)), Vector((r, 0, rise))
    below = Vector((0, 0, ze - 2))
    for pts in ([E[0], E[1], R1, R0], [E[1], E[2], R1], [E[2], E[3], R0, R1], [E[3], E[0], R0]):
        c = sum(pts, Vector()) / len(pts)
        m.face(role, pts, out=c - below)
    lo = [e - Z * t for e in E]
    for i in range(4):
        a, b = E[i], E[(i + 1) % 4]
        mid = (a + b) / 2
        m.face("trim", [a, b, lo[(i + 1) % 4], lo[i]], out=Vector((mid.x, mid.y, 0)))
    m.face("trim", lo, out=-Z)
    m.box("trim", -r - 0.12, -0.12, rise - 0.06, r + 0.12, 0.12, rise + 0.08)


def chimney(m, x, y, top):
    m.box("brick", x - 0.36, y - 0.36, 0.2, x + 0.36, y + 0.36, top, skip="b")
    m.box("trim", x - 0.46, y - 0.46, top, x + 0.46, y + 0.46, top + 0.14, bevel=0.02)
    m.cyl("dark", x - 0.12, y, top + 0.14, 0.1, 0.1, 0.3, seg=8)
    m.cyl("dark", x + 0.14, y, top + 0.14, 0.1, 0.1, 0.22, seg=8)
    m.anchor("smoke", (x, y, top + 0.6))


def cottage_body(v):
    W, D, H = COTTAGE
    m = Mod(f"cottage_body_{v}", ground=True)
    m.box("stone", -W / 2 - 0.06, -D / 2 - 0.06, 0, W / 2 + 0.06, D / 2 + 0.06, 0.5, skip="b", bevel=0.02)
    win = lambda c, w=1.05: (c - w / 2, c + w / 2, 1.05, 2.4)  # noqa: E731
    dc = {"a": W / 2, "b": W * 0.68, "c": W / 2}[v]
    door = (dc - 0.5, dc + 0.5, 0.5, 2.6, "door")
    front = {
        "a": [win(W * 0.2), door, win(W * 0.8)],
        "b": [win(W * 0.17), win(W * 0.4), door, win(W * 0.88, 0.75)],
        "c": [win(W * 0.18, 1.3), door, win(W * 0.82, 1.3)],
    }[v]
    side = [win(D / 2)] if v != "b" else [win(D * 0.3), win(D * 0.7)]
    back = [win(W * 0.25), win(W * 0.75)]
    sides = punched(m, W, D, 0, H, {"n": front, "e": side, "s": back, "w": side}, depth=0.14, reveal="frame", lintel=None)
    n = sides["n"]
    for h in front:
        if len(h) > 4:
            continue
        if v == "a":  # shutters
            n.box("accent", h[0] - 0.42, h[0] - 0.05, h[2], h[3], 0, 0.05, skip="n")
            n.box("accent", h[1] + 0.05, h[1] + 0.42, h[2], h[3], 0, 0.05, skip="n")
        if v == "b":  # flower boxes
            n.box("wood", h[0] - 0.05, h[1] + 0.05, h[2] - 0.38, h[2] - 0.09, 0, 0.3, skip="n")
            for i in range(3):
                u = h[0] + (h[1] - h[0]) * (i + 0.5) / 3
                m.blob("leaf", n.P(u, h[2] - 0.02, 0.16), (0.2, 0.16, 0.14), sub=1, jitter=0.03)
    # Door: steps, a fanlight frame, a canopy (a, b) or a porch (c).
    n.box("stone", dc - 0.75, dc + 0.75, 0, 0.25, 0, 0.95, skip="n")
    n.box("stone", dc - 0.75, dc + 0.75, 0.25, 0.5, 0, 0.5, skip="n")
    n.box("frame", dc - 0.62, dc + 0.62, 2.6, 2.75, 0, 0.08, skip="n")
    if v == "c":
        u0, u1 = W * 0.22, W * 0.78
        n.box("wood", u0, u1, 0.38, 0.5, 0, 1.9, skip="n")
        for u in (u0 + 0.1, u1 - 0.1):
            n.box("frame", u - 0.09, u + 0.09, 0.5, 2.85, 1.7, 1.88)
        n.box("frame", u0, u1, 2.85, 2.95, 1.7, 1.9, skip="n")
        n.m.hexa("roof", lambda a, b, c: n.P((u0 - 0.2, u1 + 0.2)[a], (3.15, 2.85)[b] + c * 0.12, (0, 2.1)[b]))
    else:
        n.box("trim", dc - 0.85, dc + 0.85, 2.82, 2.94, 0, 0.75, skip="n", bevel=0.02)
        for u in (dc - 0.7, dc + 0.7):
            n.box("trim", u - 0.05, u + 0.05, 2.45, 2.82, 0, 0.5, skip="n")
    band(m, W, D, H - 0.34, H - 0.12, 0.06, "trim", bevel=0.0)
    cap(m, W, D, H)


def cottage_roof(v):
    W, D, _ = COTTAGE
    m = Mod(f"cottage_roof_{v}")
    if v == "a":
        gable(m, W, D, 2.5, axis="x")
        chimney(m, W * 0.24, D * 0.16, 2.9)
    elif v == "b":
        hip(m, W, D, 2.2)
        chimney(m, -W * 0.22, -D * 0.12, 2.6)
    else:
        gable(m, W, D, 2.7, oe=0.35, og=0.45, axis="y")
        # A round-ish attic window in the front gable.
        sd = Side(m, "n", W, D)
        c = W / 2
        sd.box("frame", c - 0.45, c + 0.45, 0.75, 1.65, 0, 0.06)
        sd.quad("window", c - 0.33, c + 0.33, 0.87, 1.53, 0.065, cell=True)
        chimney(m, -W * 0.28, D * 0.2, 3.0)
    return m


# ---- shops ------------------------------------------------------------------

GLYPHS = [
    "111101111101101", "110101110101110", "111100100100111", "110101101101110", "111100110100111",
    "111100110100100", "111100101101111", "101101111101101", "111010010010111", "100100100100111",
    "101111111101101", "111101101101111", "111101111100100", "111101111110101", "111100111001111",
    "111010010010010", "101101101101111", "101101101101010", "101101111111101", "101101010101101",
]


def lettering(m, sd, uc, vc, k, n, px=0.075):
    """A row of n block letters centred on (uc, vc), glowing at night."""
    width = n * 4 * px - px
    for i in range(n):
        g = GLYPHS[m.r.randrange(len(GLYPHS))]
        u0 = uc - width / 2 + i * 4 * px
        for row in range(5):
            bits = g[row * 3 : row * 3 + 3]
            col = 0
            while col < 3:
                if bits[col] == "1":
                    end = col
                    while end + 1 < 3 and bits[end + 1] == "1":
                        end += 1
                    v1 = vc + 2.5 * px - row * px
                    sd.box("sign", u0 + col * px, u0 + (end + 1) * px, v1 - px, v1, k, k + 0.05, skip="n")
                    col = end + 1
                else:
                    col += 1


def awning(m, sd, u0, u1, top, drop, depth, stripes=True):
    n = max(2, round((u1 - u0) / 0.45))
    for i in range(n):
        a = u0 + (u1 - u0) * i / n
        b = u0 + (u1 - u0) * (i + 1) / n
        role = "accent" if i % 2 == 0 or not stripes else "canvas"
        m.face(role, [sd.P(a, top), sd.P(b, top), sd.P(b, top - drop, depth), sd.P(a, top - drop, depth)], out=sd.n + Z)
        sd.quad(role, a, b, top - drop - 0.28, top - drop, depth)
    for u, s in ((u0, -1), (u1, 1)):
        m.face("accent", [sd.P(u, top), sd.P(u, top - drop, depth), sd.P(u, top - drop - 0.28, depth)], out=sd.u * s)


def shop_ground(v):
    W, D, H = SHOP
    m = Mod(f"shop_ground_{v}", ground=True)
    n = Side(m, "n", W, D)
    if v == "a":
        dc = W * 0.72
        holes = [(0.6, dc - 0.8, 0.55, 2.55, "shopfront"), (dc - 0.6, dc + 0.6, 0.0, 2.55, "door"), (dc + 0.8, W - 0.6, 0.55, 2.55, "shopfront")]
    else:
        dc = W / 2
        holes = [
            (0.6, dc - 1.3, 0.5, 2.55, "shopfront"), (dc - 1.1, dc - 0.2, 0, 2.55, "door"),
            (dc + 0.2, dc + 1.1, 0, 2.55, "door"), (dc + 1.3, W - 0.6, 0.5, 2.55, "shopfront"),
        ]
    n.wall("wall", 0, H, holes)
    for h in holes:
        n.opening(h, 0.3, pane=h[4], reveal="metal")
        if h[4] == "shopfront":
            k = max(1, round((h[1] - h[0]) / 1.3))
            for i in range(1, k):
                u = h[0] + (h[1] - h[0]) * i / k
                n.box("metal", u - 0.04, u + 0.04, h[2], h[3], -0.3, -0.25, skip="n")
            n.box("metal", h[0], h[1], 2.05, 2.11, -0.3, -0.25, skip="n")
            n.box("stone", h[0] - 0.08, h[1] + 0.08, 0, h[2], 0, 0.06, skip="n")
        else:
            n.box("metal", h[0], h[1], 2.05, 2.11, -0.3, -0.25, skip="n")
    for u0, u1 in ((0, 0.42), (W - 0.42, W)):
        n.box("trim", u0, u1, 0, H, 0, 0.14, skip="n", bevel=0.02)
    if v == "b":
        n.box("trim", dc - 0.18, dc + 0.18, 2.55, H, 0, 0.14, skip="n")
    # Fascia sign with lettering; awnings below it.
    n.box("board", 0.45, W - 0.45, 2.72, 3.28, 0, 0.1, skip="n")
    if v == "a":
        lettering(m, n, W / 2, 3.0, 0.1, 6)
        awning(m, n, 0.6, W - 0.6, 2.68, 0.55, 1.5)
    else:
        lettering(m, n, W * 0.27, 3.0, 0.1, 4)
        lettering(m, n, W * 0.73, 3.0, 0.1, 4)
        awning(m, n, 0.6, dc - 1.25, 2.68, 0.5, 1.3)
        awning(m, n, dc + 1.25, W - 0.6, 2.68, 0.5, 1.3, stripes=False)
        # A blade sign on the corner.
        n.box("board", W - 0.3, W - 0.22, 1.6, 2.6, 0.15, 1.0)
        n.box("sign", W - 0.33, W - 0.19, 1.75, 2.45, 0.3, 0.85)
    sides = punched(
        m, W, D, 0, H,
        {"e": [(D * 0.6 - 0.5, D * 0.6 + 0.5, 1.4, 2.5)], "s": [(W * 0.3 - 0.5, W * 0.3 + 0.5, 0, 2.2, "door"), (W * 0.7 - 0.6, W * 0.7 + 0.6, 1.2, 2.5)], "w": [(D * 0.4 - 0.5, D * 0.4 + 0.5, 1.4, 2.5)]},
        depth=0.15,
    )
    sides["s"].box("metal", W * 0.3 - 0.7, W * 0.3 + 0.7, 2.35, 2.45, 0, 0.7, skip="n")
    m.box("stone", -W / 2 - 0.04, -D / 2 + 0.01, 0, W / 2 + 0.04, D / 2 + 0.04, 0.35, skip="bn")
    cap(m, W, D, H)


def quoins(m, W, D, z0, H, role="trim", t=0.05):
    """Alternating corner stones, wrapping each corner."""
    n = max(1, round(H / 0.8))
    h = H / n
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * W / 2, sy * D / 2
            for i in range(n):
                a, b = (0.6, 0.32) if i % 2 == 0 else (0.32, 0.6)
                z1, z2 = z0 + i * h, z0 + (i + 1) * h - 0.05
                xs, ys = sorted((x - sx * a, x + sx * t)), sorted((y, y + sy * t))
                m.box(role, xs[0], ys[0], z1, xs[1], ys[1], z2)
                xs, ys = sorted((x, x + sx * t)), sorted((y - sy * b, y))
                m.box(role, xs[0], ys[0], z1, xs[1], ys[1], z2)


def shop_floor(v):
    W, D, H = SHOP
    m = Mod(f"shop_floor_{v}")
    if v == "a":
        front = [(a, b, 0.75, 2.65) for a, b in spaced(W, 3, 1.2)]
    else:
        front = []
        for a, b in spaced(W, 2, 2.6):
            front += [(a, a + 1.05, 0.75, 2.65), (b - 1.05, b, 0.75, 2.65)]
    side = [(a, b, 0.8, 2.6) for a, b in spaced(D, 2, 1.1)]
    back = [(a, b, 0.8, 2.6) for a, b in spaced(W, 3, 1.0)]
    sides = punched(m, W, D, 0, H, {"n": front, "e": side, "s": back, "w": side}, depth=0.2)
    band(m, W, D, 0, 0.2, 0.08)
    if v == "a":
        quoins(m, W, D, 0.2, H - 0.2)
    else:
        n = sides["n"]
        for u in (0.2, W / 2, W - 0.2):
            n.box("trim", u - 0.2, u + 0.2, 0.2, H, 0, 0.12, skip="nbt")
        for h in front:  # keystones
            c = (h[0] + h[1]) / 2
            n.box("trim", c - 0.12, c + 0.12, h[3] + 0.05, h[3] + 0.32, 0, 0.09, skip="n")
    cap(m, W, D, H)


def shop_roof(v):
    W, D, _ = SHOP
    m = Mod(f"shop_roof_{v}")
    band(m, W, D, 0, 0.28, 0.12)
    band(m, W, D, 0.28, 0.5, 0.34, bevel=0.05)
    for side, L in (("n", W), ("e", D), ("s", W), ("w", D)):
        sd = Side(m, side, W, D)
        k = round(L / 0.7)
        for i in range(k):
            u = L * (i + 0.5) / k
            sd.box("trim", u - 0.07, u + 0.07, 0.06, 0.28, 0.12, 0.3, skip="nt")
    ring(m, W, D, 0.5, 1.2, 0.25, "wall")
    ring(m, W, D, 1.2, 1.32, 0.36, "trim", out=0.06, bevel=0.02)
    roof_deck(m, W, D, 0.62)
    if v == "b":
        sd = Side(m, "n", W, D)
        c = W / 2
        sd.box("wall", c - 2.2, c + 2.2, 1.2, 2.0, -0.25, 0)
        sd.box("trim", c - 2.3, c + 2.3, 2.0, 2.12, -0.3, 0.06, bevel=0.02)
        tri = [sd.P(c - 2.3, 2.12, 0.04), sd.P(c + 2.3, 2.12, 0.04), sd.P(c, 2.9, 0.04)]
        back = [p - sd.n * 0.3 for p in tri]
        m.face("trim", tri, out=sd.n)
        m.face("trim", back, out=-sd.n)
        for a, b in ((0, 2), (2, 1)):
            m.face("trim", [tri[a], tri[b], back[b], back[a]], out=Z + sd.u * (1 if a == 2 else -1))
        sd.box("board", c - 1.0, c + 1.0, 1.35, 1.85, 0, 0.04, skip="n")
        ac_unit(m, W * 0.18, D * 0.2, 0.62)
        vent(m, -W * 0.3, D * 0.25, 0.62)
    else:
        ac_unit(m, -W * 0.2, D * 0.1, 0.62)
        ac_unit(m, W * 0.15, D * 0.22, 0.62, 0.8)
        vent(m, W * 0.3, -D * 0.2, 0.62)
        vent(m, W * 0.36, -D * 0.1, 0.62, 0.6)
        m.box("metal", -W * 0.1, -D * 0.3, 0.62, W * 0.12, -D * 0.12, 0.85)
        m.hexa("glass", lambda a, b, c: (-W * 0.08 + a * W * 0.18, -D * 0.28 + b * D * 0.14, 0.85 + c * (0.12 + 0.25 * b)), cell=False)


# ---- apartments -------------------------------------------------------------


def apt_ground():
    W, D, H = APT
    m = Mod("apt_ground", ground=True)
    dc = W / 2
    door = (dc - 0.85, dc + 0.85, 0, 2.45, "door")
    win = lambda c: (c - 0.55, c + 0.55, 1.0, 2.4)  # noqa: E731
    front = [win(W * 0.12), win(W * 0.3), door, win(W * 0.7), win(W * 0.88)]
    sides = punched(
        m, W, D, 0, H,
        {"n": front, "e": [win(a + 0.55) for a, _ in spaced(D, 3, 1.1)], "s": [win(a + 0.55) for a, _ in spaced(W, 4, 1.1)], "w": [win(a + 0.55) for a, _ in spaced(D, 3, 1.1)]},
        depth=0.18, lintel=None,
    )
    n = sides["n"]
    # Recessed entrance: deeper reveal in stone, glass door with a transom.
    n.opening(door, 0.0, pane=None, reveal="stone")
    n.box("stone", door[0] - 0.25, door[1] + 0.25, 0, 2.7, 0, 0.12, skip="n")
    n.box("metal", door[0], door[1], 2.0, 2.06, -0.17, -0.12, skip="n")
    n.box("metal", dc - 0.03, dc + 0.03, 0, 2.0, -0.17, -0.12, skip="n")
    n.box("trim", dc - 1.5, dc + 1.5, 2.7, 2.9, 0, 1.6, skip="n", bevel=0.03)
    n.box("shopfront", dc - 0.15, dc + 0.15, 2.55, 2.7, 1.2, 1.5)
    n.box("stone", door[0] - 0.4, door[1] + 0.4, 0, 0.15, 0, 1.2, skip="n")
    for side, sd in sides.items():
        if side == "n":
            sd.box("stone", 0, door[0] - 0.25, 0, 0.75, 0, 0.06, skip="n")
            sd.box("stone", door[1] + 0.25, sd.L, 0, 0.75, 0, 0.06, skip="n")
        else:
            sd.box("stone", 0, sd.L, 0, 0.75, 0, 0.06, skip="n")
    band(m, W, D, H - 0.2, H, 0.07)
    cap(m, W, D, H)


def balcony(sd, uc, w=2.6, depth=1.25, glass=False):
    sd.box("trim", uc - w / 2, uc + w / 2, -0.02, 0.16, 0, depth, skip="n", bevel=0.03)
    panel = "railglass" if glass else "trim"
    t = 0.04 if glass else 0.1
    sd.box(panel, uc - w / 2, uc + w / 2, 0.16, 1.05, depth - t, depth, skip="b")
    for u in (uc - w / 2, uc + w / 2 - t):
        sd.box(panel, u, u + t, 0.16, 1.05, 0, depth - t, skip="bn")
    if glass:
        sd.box("metal", uc - w / 2 - 0.02, uc + w / 2 + 0.02, 1.05, 1.1, depth - 0.07, depth + 0.02, skip="")


def apt_floor(v):
    W, D, H = APT
    m = Mod(f"apt_floor_{v}")
    win = lambda c, w=1.1: (c - w / 2, c + w / 2, 0.8, 2.4)  # noqa: E731
    fr = lambda c: (c - 0.5, c + 0.5, 0.0, 2.4)  # noqa: E731
    if v == "a":
        front = [win(W * 0.1), fr(W * 0.33), fr(W * 0.67), win(W * 0.9)]
    else:
        front = [win(W * 0.12), (W * 0.36 - 0.5, W * 0.36 + 0.5, 0.25, 2.4), (W * 0.64 - 0.5, W * 0.64 + 0.5, 0.25, 2.4), win(W * 0.88)]
    side = [win(a + 0.55) for a, _ in spaced(D, 3, 1.1)]
    back = [win(a + 0.5, 1.0) for a, _ in spaced(W, 4, 1.0)]
    sides = punched(m, W, D, 0, H, {"n": front, "e": side, "s": back, "w": side}, depth=0.16, lintel=None)
    band(m, W, D, 0, 0.18, 0.05)
    n = sides["n"]
    if v == "a":
        balcony(n, W * 0.3, w=2.8)
        balcony(n, W * 0.7, w=2.8, glass=True)
    else:
        for h in front[1:3]:  # Juliet balconies
            n.box("metal", h[0] - 0.08, h[1] + 0.08, 1.0, 1.06, 0, 0.3, skip="n")
            n.box("metal", h[0] - 0.08, h[1] + 0.08, 0.2, 0.26, 0, 0.3, skip="n")
            for u in (h[0] - 0.08, h[1] + 0.02):
                n.box("metal", u, u + 0.06, 0.2, 1.06, 0, 0.3, skip="nbt")
        for u in (W * 0.22, W * 0.5, W * 0.78):
            n.box("trim", u - 0.15, u + 0.15, 0.18, H, 0, 0.1, skip="nbt")
    cap(m, W, D, H)


def stair_house(m, x, y, z, w=2.4, d=2.6, h=2.6):
    m.box("wall", x - w / 2, y - d / 2, z, x + w / 2, y + d / 2, z + h, skip="b")
    m.box("trim", x - w / 2 - 0.15, y - d / 2 - 0.15, z + h, x + w / 2 + 0.15, y + d / 2 + 0.15, z + h + 0.18, bevel=0.03)
    sd = Side(m, "n", w, d, z)
    sd.o = sd.o + Vector((x, y, 0))
    sd.quad("door", w / 2 - 0.45, w / 2 + 0.45, 0, 2.05, 0.01)


def apt_roof(v):
    W, D, _ = APT
    m = Mod(f"apt_roof_{v}")
    ring(m, W, D, 0, 0.9, 0.22, "wall")
    ring(m, W, D, 0.9, 1.02, 0.32, "trim", out=0.05, bevel=0.02)
    roof_deck(m, W, D, 0.12)
    if v == "a":
        x, y = W * 0.2, D * 0.12
        for lx, ly in ((-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
            m.box("dark", x + lx - 0.07, y + ly - 0.07, 0.12, x + lx + 0.07, y + ly + 0.07, 1.4)
        m.box("dark", x - 0.85, y - 0.85, 1.3, x + 0.85, y + 0.85, 1.42)
        m.cyl("wood", x, y, 1.42, 1.1, 1.1, 1.9, seg=14)
        for z in (1.8, 2.5, 3.1):
            m.cyl("dark", x, y, z, 1.13, 1.13, 0.06, seg=14)
        m.cyl("roof", x, y, 3.32, 1.2, 0.08, 0.75, seg=14, smooth=False)
        stair_house(m, -W * 0.22, -D * 0.12, 0.12)
        ac_unit(m, -W * 0.25, D * 0.28, 0.12, 0.8)
    else:
        stair_house(m, W * 0.24, D * 0.2, 0.12, w=2.2, d=2.4)
        # Roof garden: planters with shrubs and a pergola.
        for i, (x, y) in enumerate(((-W * 0.3, -D * 0.3), (-W * 0.05, -D * 0.3), (W * 0.2, -D * 0.3))):
            m.box("wood", x - 0.9, y - 0.4, 0.12, x + 0.9, y + 0.4, 0.6, bevel=0.02)
            for j in range(3):
                m.blob("leaf", (x - 0.55 + j * 0.55, y, 0.75), (0.38, 0.34, 0.32), sub=1, jitter=0.06)
        for x in (-W * 0.35, -W * 0.05):
            for y in (D * 0.05, D * 0.3):
                m.box("wood", x - 0.07, y - 0.07, 0.12, x + 0.07, y + 0.07, 2.3)
        for i in range(6):
            y = D * 0.02 + i * 0.4
            m.box("wood", -W * 0.38, y - 0.04, 2.3, -W * 0.02, y + 0.04, 2.42)
        vent(m, W * 0.3, -D * 0.25, 0.12)


# ---- offices ----------------------------------------------------------------


def curtain(sd, H, sill=0.65, cells=None):
    L = sd.L
    n = cells or max(2, round(L / 1.6))
    sd.quad("spandrel", 0, L, 0, sill)
    for i in range(n):
        sd.quad("glass", L * i / n, L * (i + 1) / n, sill, H, cell=True)
    for i in range(n + 1):
        u = L * i / n
        w = 0.14 if i in (0, n) else 0.07
        sd.box("metal", max(0, u - w), min(L, u + w), 0, H, 0, 0.18, skip="nbt")
    sd.box("metal", 0, L, sill - 0.05, sill + 0.03, 0, 0.1, skip="n")


def office_ground():
    W, D, H = OFFICE
    m = Mod("office_ground", ground=True)
    n = Side(m, "n", W, D)
    hole = (0.7, W - 0.7, 0, H - 0.45)
    n.wall("stone", 0, H, [hole])
    n.opening(hole, 0.45, pane=None, reveal="stone")
    k = 6
    for i in range(k):
        a = hole[0] + (hole[1] - hole[0]) * i / k
        b = hole[0] + (hole[1] - hole[0]) * (i + 1) / k
        n.quad("lobby", a, b, 0, hole[3], -0.45)
        n.box("metal", a - 0.04, a + 0.04, 0, hole[3], -0.45, -0.38, skip="n")
    n.box("metal", hole[0], hole[1], 2.4, 2.46, -0.45, -0.38, skip="n")
    m.cyl("railglass", 0, -D / 2 + 0.45 - 0.5, 0, 0.95, 0.95, 2.4, seg=16)
    m.cyl("metal", 0, -D / 2 + 0.45 - 0.5, 2.4, 1.0, 1.0, 0.15, seg=16)
    n.box("metal", W / 2 - 2.4, W / 2 + 2.4, 2.75, 2.95, 0, 2.4, skip="n", bevel=0.03)
    n.box("shopfront", W / 2 - 2.2, W / 2 + 2.2, 2.7, 2.75, 0.2, 2.2)
    for side in ("e", "s", "w"):
        sd = Side(m, side, W, D)
        holes = [(a, b, 0.4, H - 0.6) for a, b in spaced(sd.L, 4, 1.1)]
        sd.wall("stone", 0, H, holes)
        for h in holes:
            sd.opening(h, 0.25, pane="glass", reveal="stone")
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.box("stone", sx * W / 2 - 0.45, sy * D / 2 - 0.45, 0, sx * W / 2 + 0.45, sy * D / 2 + 0.45, H, skip="b", bevel=0.03)
    band(m, W, D, H - 0.3, H, 0.1, "metal")
    cap(m, W, D, H)


def office_floor(v):
    W, D, H = OFFICE
    m = Mod(f"office_floor_{v}")
    for side in "nesw":
        sd = Side(m, side, W, D)
        if v == "a":
            curtain(sd, H)
        else:
            L = sd.L
            sd.box("wall", 0, L, 0, 1.0, 0, 0.12, skip="n")
            sd.quad("wall", 0, L, H - 0.12, H, 0.0)
            n = 4
            for i in range(n):
                sd.quad("glass", L * i / n, L * (i + 1) / n, 1.0, H - 0.12, -0.12, cell=True)
            sd.m.face("wall", [sd.P(0, H - 0.12), sd.P(L, H - 0.12), sd.P(L, H - 0.12, -0.12), sd.P(0, H - 0.12, -0.12)], out=-Z)
            for i in range(n + 1):
                u = L * i / n
                sd.box("metal", max(0, u - 0.05), min(L, u + 0.05), 1.0, H - 0.12, -0.12, 0.0, skip="nbt")
            for i in range(1, 2 * n):
                u = L * i / (2 * n)
                sd.box("metal", u - 0.04, u + 0.04, 1.0, H, 0.0, 0.5, skip="nb")
    cap(m, W, D, H)


def office_setback():
    W, D, _ = OFFICE
    m = Mod("office_setback")
    m.box("metal", -W / 2 - 0.15, -D / 2 - 0.15, 0, W / 2 + 0.15, D / 2 + 0.15, 0.5, bevel=0.05)
    ring(m, W, D, 0.5, 1.4, 0.05, "railglass", out=0.05)
    ring(m, W, D, 1.4, 1.47, 0.09, "metal", out=0.07)
    for x, y in ((-W * 0.4, -D * 0.4), (W * 0.4, -D * 0.4), (-W * 0.4, D * 0.4), (W * 0.4, D * 0.4)):
        m.box("stone", x - 0.35, y - 0.35, 0.5, x + 0.35, y + 0.35, 0.95, bevel=0.02)
        m.blob("leaf", (x, y, 1.25), (0.45, 0.45, 0.5), sub=1, jitter=0.06)


def office_roof(v):
    W, D, _ = OFFICE
    m = Mod(f"office_roof_{v}")
    ring(m, W, D, 0, 1.0, 0.18, "metal")
    roof_deck(m, W, D, 0.1, 0.18)
    if v == "a":
        # Plant room with louvres, an antenna and a dish.
        w, d, h = W * 0.55, D * 0.5, 2.6
        m.box("wall", -w / 2, -d / 2, 0.1, w / 2, d / 2, 0.1 + h, skip="b")
        for side in "nesw":
            sd = Side(m, side, w, d, 0.1)
            for i in range(6):
                v0 = 0.6 + i * 0.28
                sd.box("dark", 0.3, sd.L - 0.3, v0, v0 + 0.16, 0, 0.06, skip="n")
        m.box("metal", -w / 2 - 0.1, -d / 2 - 0.1, 0.1 + h, w / 2 + 0.1, d / 2 + 0.1, 0.3 + h, bevel=0.03)
        x = w * 0.3
        m.cyl("metal", x, 0, 0.3 + h, 0.16, 0.06, 9, seg=8)
        for z in (3.0, 5.5):
            m.box("metal", x - 0.5, -0.04, 0.3 + h + z, x + 0.5, 0.04, 0.38 + h + z)
        m.anchor("beacon", (x, 0, 0.3 + h + 9.2))
        dish = Matrix.Translation((-W * 0.3, D * 0.3, 1.0)) @ Matrix.Rotation(-0.7, 4, "X")
        m.cyl("trim", 0, 0, 0, 0.75, 0.15, 0.4, seg=12, M=dish)
        m.box("metal", -W * 0.3 - 0.06, D * 0.3 - 0.06, 0.1, -W * 0.3 + 0.06, D * 0.3 + 0.06, 1.0)
        ac_unit(m, -W * 0.28, -D * 0.32, 0.1, 0.8)
    else:
        # Helipad on a raised deck, plant room behind.
        m.box("metal", -W * 0.35, -D * 0.38, 0.1, W * 0.35, D * 0.18, 0.9)
        m.cyl("deck", 0, -D * 0.1, 0.9, 3.0, 3.0, 0.12, seg=24, smooth=False)
        m.cyl("paint", 0, -D * 0.1, 1.02, 2.75, 2.75, 0.02, seg=24, smooth=False)
        m.cyl("deck", 0, -D * 0.1, 1.04, 2.55, 2.55, 0.02, seg=24, smooth=False)
        for x0, x1, y0, y1 in ((-0.9, -0.6, -1.0, 1.0), (0.6, 0.9, -1.0, 1.0), (-0.6, 0.6, -0.15, 0.15)):
            m.box("paint", x0, -D * 0.1 + y0, 1.06, x1, -D * 0.1 + y1, 1.08)
        m.box("wall", -W * 0.3, D * 0.22, 0.1, W * 0.3, D * 0.45, 2.4, skip="b")
        m.box("metal", -W * 0.32, D * 0.2, 2.4, W * 0.32, D * 0.47, 2.55)
        m.anchor("beacon", (W * 0.3, D * 0.45, 2.85))
        for x in (-W * 0.15, W * 0.12):
            ac_unit(m, x, D * 0.33, 2.55, 0.7)


# ---- landmark ---------------------------------------------------------------


def lm_bays(sd, H, n, cw=0.7, pw=0.32, sill=0.95, pane="glass"):
    """Art deco bays: deep windows between piers, dark spandrels below."""
    L = sd.L
    bay = (L - 2 * cw) / n
    holes = [(cw + i * bay + pw / 2, cw + (i + 1) * bay - pw / 2, 0.0, H - 0.35) for i in range(n)]
    sd.wall("wall", 0, H, holes)
    for h in holes:
        sd.opening(h, 0.28, pane=None, reveal="wall")
        sd.quad("spandrel", h[0], h[1], 0, sill, -0.28)
        sd.quad(pane, h[0], h[1], sill, h[3], -0.28, cell=True)
    for i in range(1, n):
        u = cw + i * bay
        sd.box("trim", u - pw / 2, u + pw / 2, 0, H, 0, 0.2, skip="nbt")
    sd.box("trim", 0, cw, 0, H, 0, 0.3, skip="nbt")
    sd.box("trim", L - cw, L, 0, H, 0, 0.3, skip="nbt")


def lm_ground():
    S, H = LANDMARK
    m = Mod("lm_ground", ground=True)
    n = Side(m, "n", S, S)
    portal = (S / 2 - 1.6, S / 2 + 1.6, 0, H - 0.25)
    n.wall("stone", 0, H, [portal])
    n.opening(portal, 0.6, pane=None, reveal="gold")
    n.quad("lobby", portal[0], portal[1], 0, portal[3], -0.6)
    for i in range(1, 4):
        u = portal[0] + (portal[1] - portal[0]) * i / 4
        n.box("gold", u - 0.05, u + 0.05, 0, portal[3], -0.6, -0.52, skip="n")
    n.box("gold", portal[0] - 0.3, portal[1] + 0.3, portal[3], portal[3] + 0.25, 0, 0.12, skip="n")
    for u in (portal[0] - 0.3, portal[1]):
        n.box("gold", u, u + 0.3, 0, portal[3], 0, 0.12, skip="n")
    for u in (1.2, S - 1.2):
        n.box("stone", u - 0.6, u + 0.6, 0, 0.45, 0, 0.3, skip="n", bevel=0.03)
        m.cyl("dark", 0, 0, 0, 0.05, 0.05, 1.0, seg=6, M=Matrix.Translation(n.P(u, 0.45, 0.15)))
        n.box("shopfront", u - 0.18, u + 0.18, 1.45, 1.8, 0.0, 0.3)
    for side in ("e", "s", "w"):
        lm_bays(Side(m, side, S, S), H, 5, pane="glass")
    for side in "nesw":
        sd = Side(m, side, S, S)
        sd.box("stone", 0, sd.L, 0, 1.0, 0, 0.12, skip="n")
    band(m, S, S, H - 0.3, H, 0.18, "stone")
    cap(m, S, S, H)


def lm_floor(t):
    S0, H = LANDMARK
    S = S0 * LM_TIERS[t - 1]
    m = Mod(f"lm_floor_{t}")
    for side in "nesw":
        lm_bays(Side(m, side, S, S), H, (5, 4, 3)[t - 1])
    cap(m, S, S, H)


def finial(m, x, y, z, h=1.3, r=0.25):
    m.box("gold", x - r, y - r, z, x + r, y + r, z + 0.25)
    m.cyl("gold", x, y, z + 0.25, r * 0.9, 0.0, h, seg=4, smooth=False, M=Matrix.Translation((x, y, 0)) @ Matrix.Rotation(math.pi / 4, 4, "Z") @ Matrix.Translation((-x, -y, 0)))


def lm_ledge(t):
    S0, _ = LANDMARK
    S = S0 * LM_TIERS[t - 1]
    m = Mod(f"lm_ledge_{t}")
    band(m, S, S, -0.1, 0.35, 0.28, "trim", bevel=0.05)
    band(m, S, S, 0.35, 0.55, 0.14, "gold", bevel=0.02)
    ring(m, S, S, 0.55, 1.1, 0.3, "wall")
    ring(m, S, S, 1.1, 1.22, 0.4, "trim", out=0.05, bevel=0.02)
    roof_deck(m, S, S, 0.65)
    for sx in (-1, 1):
        for sy in (-1, 1):
            finial(m, sx * (S / 2 - 0.15), sy * (S / 2 - 0.15), 1.22)


def lm_crown():
    S0, _ = LANDMARK
    S = S0 * LM_TIERS[2]
    m = Mod("lm_crown")
    band(m, S, S, -0.1, 0.35, 0.25, "trim", bevel=0.05)
    band(m, S, S, 0.35, 0.55, 0.12, "gold", bevel=0.02)
    # Lantern storey: tall lit windows framed in gold.
    a = S * 0.86
    for side in "nesw":
        sd = Side(m, side, a, a, 0.55)
        holes = [(u0, u1, 0.4, 2.9) for u0, u1 in spaced(a, 3, 0.8)]
        sd.wall("wall", 0, 3.3, holes)
        for h in holes:
            sd.opening(h, 0.2, pane="crownlight", reveal="gold")
            c = (h[0] + h[1]) / 2
            tri = [sd.P(h[0] - 0.1, h[3], 0.02), sd.P(h[1] + 0.1, h[3], 0.02), sd.P(c, h[3] + 0.32, 0.02)]
            m.face("gold", tri, out=sd.n)
    band(m, a, a, 3.85, 4.1, 0.12, "gold", bevel=0.02)
    for sx in (-1, 1):
        for sy in (-1, 1):
            finial(m, sx * (a / 2 - 0.05), sy * (a / 2 - 0.05), 4.1, h=1.0, r=0.2)
    # Stepped crown with sunburst chevrons.
    b = a * 0.74
    m.box("wall", -b / 2, -b / 2, 4.1, b / 2, b / 2, 6.6, skip="b")
    for side in "nesw":
        sd = Side(m, side, b, b, 4.1)
        c = b / 2
        for i, (w, h, role) in enumerate(((b * 0.48, 2.3, "gold"), (b * 0.34, 1.75, "board"), (b * 0.22, 1.2, "gold"), (b * 0.1, 0.7, "crownlight"))):
            k = 0.02 + i * 0.015
            m.face(role, [sd.P(c - w, 0.05, k), sd.P(c + w, 0.05, k), sd.P(c, h + 0.05, k)], out=sd.n)
    band(m, b, b, 6.6, 6.8, 0.1, "gold", bevel=0.02)
    c3 = b * 0.66
    m.box("gold", -c3 / 2, -c3 / 2, 6.8, c3 / 2, c3 / 2, 8.2, skip="b", bevel=0.04)
    rot = Matrix.Rotation(math.pi / 4, 4, "Z")
    m.cyl("gold", 0, 0, 8.2, c3 * 0.62, 0.12, 6.5, seg=8, smooth=False, M=rot)
    m.cyl("metal", 0, 0, 14.5, 0.14, 0.04, 9.0, seg=8)
    m.blob("gold", (0, 0, 14.4), (0.3, 0.3, 0.3), sub=1)
    m.anchor("beacon", (0, 0, 23.7))


# ---- trees ------------------------------------------------------------------


def trunk(m, h, r=0.17):
    m.cyl("bark", 0, 0, 0, r, r * 0.6, h, seg=7)


def tree_round():
    m = Mod("tree_a", ground=True, ao=2.0)
    trunk(m, 2.4)
    for M in (Matrix.Translation((0, 0, 1.4)) @ Matrix.Rotation(0.7, 4, "Y"), Matrix.Translation((0, 0, 1.6)) @ Matrix.Rotation(-0.6, 4, "X")):
        m.cyl("bark", 0, 0, 0, 0.08, 0.05, 1.0, seg=5, M=M)
    blobs = [((0, 0, 3.2), 1.35), ((0.75, 0.3, 2.7), 0.95), ((-0.7, 0.25, 2.8), 1.0), ((0.1, -0.75, 2.75), 0.95), ((0.2, 0.7, 3.6), 0.85), ((-0.3, -0.2, 4.0), 0.8)]
    for c, r in blobs:
        m.blob("leaf", c, (r, r, r * 0.9), sub=1, jitter=0.1)


def tree_conifer():
    m = Mod("tree_b", ground=True, ao=2.0)
    trunk(m, 1.2, 0.15)
    for i, (r, z) in enumerate(((1.5, 0.8), (1.18, 1.95), (0.85, 3.0), (0.5, 3.9))):
        m.cyl("leaf", 0, 0, z, r, 0.0, 1.75 - i * 0.15, seg=9, smooth=False, M=Matrix.Rotation(i * 0.7, 4, "Z"))


def tree_poplar():
    m = Mod("tree_c", ground=True, ao=2.0)
    trunk(m, 1.6, 0.14)
    m.blob("leaf", (0, 0, 3.4), (0.95, 0.95, 2.4), sub=2, jitter=0.12)
    m.blob("leaf", (0.25, 0.1, 2.2), (0.7, 0.7, 1.1), sub=1, jitter=0.08)


def tree_bush():
    m = Mod("tree_d", ground=True, ao=2.0)
    trunk(m, 1.6, 0.2)
    for c, s in (((0, 0, 2.5), (1.6, 1.5, 1.0)), ((0.9, 0.4, 2.2), (1.0, 0.9, 0.75)), ((-0.8, -0.5, 2.3), (1.1, 1.0, 0.8)), ((0.1, 0.2, 3.1), (1.0, 1.0, 0.7))):
        m.blob("leaf", c, s, sub=1, jitter=0.1)


# ---- ambient occlusion and export --------------------------------------------


def hemisphere(n):
    """Cosine-weighted directions about +Z (Hammersley points)."""
    out = []
    for i in range(n):
        u = (i + 0.5) / n
        bits, x, f = i, 0.0, 0.5
        while bits:
            x += f * (bits & 1)
            bits >>= 1
            f *= 0.5
        r, a = math.sqrt(u), 2 * math.pi * x
        out.append(Vector((r * math.cos(a), r * math.sin(a), math.sqrt(max(0.0, 1 - u)))))
    return out


DIRS = hemisphere(64)


def bake_ao(m):
    bm = m.bm
    bm.normal_update()
    probe = bm.copy()
    if m.ground:
        g = [probe.verts.new(p) for p in [(-80, -80, -0.002), (80, -80, -0.002), (80, 80, -0.002), (-80, 80, -0.002)]]
        probe.faces.new(g)
    tree = BVHTree.FromBMesh(probe)
    probe.free()
    layer = bm.loops.layers.float_color.new("Color")
    R = m.ao
    for f in bm.faces:
        n = f.normal
        c = f.calc_center_median()
        t = n.orthogonal().normalized()
        b = n.cross(t)
        for loop in f.loops:
            p = loop.vert.co.lerp(c, 0.03) + n * 0.003
            occ = 0.0
            for d in DIRS:
                hit = tree.ray_cast(p, t * d.x + b * d.y + n * d.z, R)
                if hit[0] is not None:
                    occ += 1.0 - hit[3] / R
            ao = 1.0 - 1.1 * occ / len(DIRS)
            ao = max(0.25, min(1.0, ao)) ** 1.3
            loop[layer] = (ao, ao, ao, 1.0)


def material(role):
    mt = bpy.data.materials.get(role)
    if mt:
        return mt
    mt = bpy.data.materials.new(role)
    nt = mt.node_tree
    if nt is None:
        mt.use_nodes = True
        nt = mt.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    col = nt.nodes.new("ShaderNodeVertexColor")
    col.layer_name = "Color"
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    mul.inputs[0].default_value = PREVIEW_COLORS.get(role, (0.8, 0.8, 0.8))
    nt.links.new(col.outputs["Color"], mul.inputs[1])
    nt.links.new(mul.outputs[0], bsdf.inputs["Base Color"])
    if role in ("window", "glass", "railglass", "metal", "gold"):
        bsdf.inputs["Roughness"].default_value = 0.15 if role != "gold" else 0.3
        bsdf.inputs["Metallic"].default_value = 0.6
    if role in ("sign", "shopfront", "lobby", "crownlight"):
        bsdf.inputs["Emission Color"].default_value = (*PREVIEW_COLORS[role], 1)
        bsdf.inputs["Emission Strength"].default_value = 1.5
    return mt


def finish(m):
    bmesh.ops.dissolve_degenerate(m.bm, dist=1e-5, edges=m.bm.edges[:])
    bake_ao(m)
    me = bpy.data.meshes.new(m.name)
    m.bm.to_mesh(me)
    m.bm.free()
    for r in m.roles:
        me.materials.append(material(r))
    ob = bpy.data.objects.new(m.name, me)
    bpy.context.scene.collection.objects.link(ob)
    for k, v in m.extras.items():
        ob[k] = v
    attr = me.color_attributes.get("Color")
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.active_color_index
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    print(f"  {m.name:18s} {tris:6d} tris  {', '.join(m.roles)}")
    return ob


MODS = []


def build():
    for v in "abc":
        cottage_body(v)
        cottage_roof(v)
    for v in "ab":
        shop_ground(v)
        shop_floor(v)
        shop_roof(v)
        apt_floor(v)
        apt_roof(v)
        office_floor(v)
        office_roof(v)
    apt_ground()
    office_ground()
    office_setback()
    lm_ground()
    for t in (1, 2, 3):
        lm_floor(t)
    lm_ledge(1)
    lm_ledge(2)
    lm_crown()
    tree_round()
    tree_conifer()
    tree_poplar()
    tree_bush()


def preview(objs, path):
    """A Cycles render of assembled buildings, to check the kit by eye."""
    scene = bpy.context.scene
    col = bpy.data.collections.new("preview")
    scene.collection.children.link(col)

    def put(name, x, y, z, sx=1.0, sy=1.0):
        o = bpy.data.objects.new(name + "_p", objs[name].data)
        o.location = (x, y, z)
        o.scale = (sx, sy, 1)
        col.objects.link(o)

    def tower(x, ground, floor, roof, n, fh):
        put(ground, x, 0, 0)
        for f in range(1, n):
            put(floor[f % len(floor)], x, 0, f * fh)
        put(roof, x, 0, n * fh)

    put("cottage_body_a", -40, 0, 0)
    put("cottage_roof_a", -40, 0, COTTAGE[2])
    put("cottage_body_c", -40, 12, 0)
    put("cottage_roof_c", -40, 12, COTTAGE[2])
    put("cottage_body_b", -40, -12, 0)
    put("cottage_roof_b", -40, -12, COTTAGE[2])
    tower(-28, "shop_ground_a", ["shop_floor_a"], "shop_roof_a", 3, SHOP[2])
    put("shop_ground_b", -28, -12, 0)
    put("shop_floor_b", -28, -12, SHOP[2])
    put("shop_roof_b", -28, -12, 2 * SHOP[2])
    tower(-16, "apt_ground", ["apt_floor_a"], "apt_roof_a", 6, APT[2])
    put("apt_ground", -16, -12, 0)
    for f in range(1, 5):
        put("apt_floor_b", -16, -12, f * APT[2])
    put("apt_roof_b", -16, -12, 5 * APT[2])
    fh = OFFICE[2]
    put("office_ground", -3, 0, 0)
    for f in range(1, 9):
        put("office_floor_a", -3, 0, f * fh)
    put("office_setback", -3, 0, 9 * fh)
    for f in range(9, 13):
        put("office_floor_a", -3, 0, f * fh, 0.78, 0.78)
    put("office_roof_a", -3, 0, 13 * fh, 0.78, 0.78)
    put("office_ground", -3, -12, 0)
    for f in range(1, 7):
        put("office_floor_b", -3, -12, f * fh)
    put("office_roof_b", -3, -12, 7 * fh)
    S, fh = LANDMARK
    put("lm_ground", 12, 0, 0)
    z = fh
    for t, n in ((1, 9), (2, 6), (3, 4)):
        for _ in range(n - (1 if t == 1 else 0)):
            put(f"lm_floor_{t}", 12, 0, z)
            z += fh
        if t < 3:
            put(f"lm_ledge_{t}", 12, 0, z)
    put("lm_crown", 12, 0, z)
    for i, name in enumerate(["tree_a", "tree_b", "tree_c", "tree_d"]):
        put(name, -46 + i * 4, -24, 0)

    bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 0, 0))
    ground = bpy.context.object
    gm = bpy.data.materials.new("ground_p")
    gb = next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    gb.inputs["Base Color"].default_value = (0.3, 0.42, 0.22, 1)
    ground.data.materials.append(gm)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 4
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    col.objects.link(sun)
    world = bpy.data.worlds.new("w")
    scene.world = world
    bg = world.node_tree.nodes.get("Background") if world.node_tree else None
    if bg is None:
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.55, 0.65, 0.8, 1)
    bg.inputs["Strength"].default_value = 0.8
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    col.objects.link(cam)
    aim = bpy.data.objects.new("aim", None)
    col.objects.link(aim)
    track = cam.constraints.new("TRACK_TO")
    track.target = aim
    scene.camera = cam
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = 1400, 900
    stem = path.rsplit(".", 1)[0]
    for tag, loc, target, lens in (
        ("wide", (-75, -80, 55), (-8, 0, 18), 32),
        ("near", (-52, -34, 14), (-30, -4, 5), 35),
        ("top", (0, -40, 70), (3, 0, 45), 40),
    ):
        cam.location, aim.location, cam.data.lens = loc, target, lens
        scene.render.filepath = f"{stem}-{tag}.png"
        bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build()
    print(f"city kit: {len(MODS)} pieces")
    objs = {m.name: finish(m) for m in MODS}
    bpy.ops.export_scene.gltf(
        filepath=OUT,
        export_format="GLB",
        export_extras=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_vertex_color="ACTIVE",
        export_all_vertex_colors=False,
        export_materials="EXPORT",
        export_image_format="NONE",
    )
    print(f"wrote {OUT}")
    if PREVIEW:
        preview(objs, PREVIEW)


main()
