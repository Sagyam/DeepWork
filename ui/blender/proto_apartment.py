# Prototype of a realistic building for the city: a six-storey pre-war brick
# apartment block over two shops, with stone trim, a bracketed cornice, sash
# windows, balconies, a fire escape and a water tank on the roof.
#
#   bun run proto   (blender -b --factory-startup -P blender/proto_apartment.py -- proto)
#
# The output goes to ui/proto/ (git-ignored, outside public/ so the app's
# build does not embed it); the dev server serves it to proto.html.
# Writes apartment.glb (geometry, materials named by role) and the textures:
# tiling PBR sets drawn with numpy (UV0 is in metres, so the viewer sets each
# texture's repeat to 1 / tile size) and ao.png, ambient occlusion baked in
# Cycles on the lightmap UVs (UV1). Window glass carries (window id + u, v)
# across its opening in UV0; the viewer draws the room behind it.
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
OUT = argv[0] if argv else "proto"
os.makedirs(OUT, exist_ok=True)
SKIP_BAKE = "--no-bake" in argv

Z = Vector((0, 0, 1))
R = random.Random(7)

# ---- textures ------------------------------------------------------------------


def lattice(n, px, py, rng):
    """Seamless value noise: px x py lattice cells over an n x n image."""
    g = rng.random((py, px))
    def axis(p):
        x = np.arange(n) * p / n
        i0 = np.floor(x).astype(int)
        f = x - i0
        return i0, (i0 + 1) % p, f * f * (3 - 2 * f)
    y0, y1, fy = axis(py)
    x0, x1, fx = axis(px)
    fy, fx = fy[:, None], fx[None, :]
    a, b = g[np.ix_(y0, x0)], g[np.ix_(y0, x1)]
    c, d = g[np.ix_(y1, x0)], g[np.ix_(y1, x1)]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(n, base, octaves, seed, gain=0.5, stretch=(1, 1)):
    rng = np.random.default_rng(seed)
    s, amp, tot, p = 0.0, 1.0, 0.0, base
    for _ in range(octaves):
        if p * max(stretch) > n:
            break
        s = s + amp * lattice(n, p * stretch[0], p * stretch[1], rng)
        tot += amp
        amp *= gain
        p *= 2
    return s / tot


def normals(h, strength):
    """Tangent-space normal map (OpenGL, green up) from a height field; row 0 is the top."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength
    dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * 0.5 * strength
    n = np.dstack([-dx, -dy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def save(name, data, alpha=None):
    """Writes an image; data is (h, w) or (h, w, 3) in 0..1 with row 0 at the top."""
    if data.ndim == 2:
        data = np.dstack([data] * 3)
    h, w = data.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = np.clip(data, 0, 1)
    if alpha is not None:
        rgba[..., 3] = np.clip(alpha, 0, 1)
    img = bpy.data.images.new(name, w, h, alpha=alpha is not None)
    img.pixels.foreach_set(np.flipud(rgba).ravel())
    img.filepath_raw = os.path.join(OUT, f"{name}.png")
    img.file_format = "PNG"
    img.save()


def srgb(*c):
    return np.array(c, np.float32) / 255.0


def brick_tex(n=1024):
    """Running bond, 8 bricks x 24 courses: tile 1.72 x 1.8 m."""
    cols, rows = 8, 24
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / rows)
    course = np.floor(cy).astype(int)
    fy = cy - course
    bx = x / (n / cols) + 0.5 * (course % 2)
    brick = np.floor(bx).astype(int) % cols
    fx = bx - np.floor(bx)
    # Distance to the brick's edge in metres (bricks 0.215 x 0.075 with joints).
    edge = np.minimum(np.minimum(fx, 1 - fx) * 0.215, np.minimum(fy, 1 - fy) * 0.075)
    mortar = edge < 0.0055
    rng = np.random.default_rng(3)
    ids = course * cols + brick
    tone = rng.random(rows * cols)[ids]
    hue = rng.random(rows * cols)[ids]
    burnt = rng.random(rows * cols)[ids] < 0.1
    base = np.stack([srgb(150, 68, 48), srgb(128, 58, 42), srgb(166, 88, 62), srgb(112, 54, 44)])
    k = (hue * 3.999).astype(int)
    f = (hue * 3.999 - k)[..., None]
    col = base[k] * (1 - f) + base[np.minimum(k + 1, 3)] * f
    col *= (0.82 + 0.3 * tone)[..., None]
    col[burnt] *= 0.55
    fine = fbm(n, 64, 4, 11)
    blotch = fbm(n, 8, 4, 12)
    col *= (0.85 + 0.3 * fine)[..., None] * (0.9 + 0.2 * blotch)[..., None]
    mcol = srgb(168, 160, 148) * (0.8 + 0.35 * fbm(n, 128, 3, 13))[..., None]
    col[mortar] = mcol[mortar]
    # Height: bricks with worn, rounded arrises; mortar recessed.
    h = np.clip((edge - 0.004) / 0.006, 0, 1) ** 0.5
    h = h * (0.85 + 0.15 * fbm(n, 64, 4, 14)) + 0.08 * fbm(n, 256, 2, 15)
    rough = np.where(mortar, 0.95, 0.78 + 0.15 * fine)
    save("brick_col", col)
    save("brick_nrm", normals(h, 6.0))
    save("brick_rgh", rough)


def stone_tex(n=1024):
    """Limestone, smooth with pitting and soft staining: tile 2 x 2 m."""
    a = fbm(n, 4, 6, 21)
    b = fbm(n, 32, 5, 22)
    pits = (fbm(n, 256, 2, 23) > 0.72).astype(np.float32)
    col = srgb(178, 168, 148) * (0.8 + 0.2 * a)[..., None] * (0.93 + 0.1 * b)[..., None]
    col *= (1 - 0.18 * pits)[..., None]
    h = 0.4 * b + 0.2 * fbm(n, 128, 3, 24) - 0.5 * pits
    save("stone_col", col)
    save("stone_nrm", normals(h, 2.5))


def ashlar_tex(n=1024):
    """Rusticated limestone blocks with V joints: 2 x 4 blocks, tile 2.4 x 1.8 m."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / 4)
    course = np.floor(cy).astype(int)
    fy = cy - course
    bx = x / (n / 2) + 0.5 * (course % 2)
    fx = bx - np.floor(bx)
    block = (np.floor(bx).astype(int) % 2) + course * 2
    ex = np.minimum(fx, 1 - fx) * 1.2
    ey = np.minimum(fy, 1 - fy) * 0.45
    h = np.clip(np.minimum(ex * 0.6, ey) / 0.03, 0, 1)
    rng = np.random.default_rng(31)
    tone = rng.random(8)[block]
    a = fbm(n, 8, 6, 32)
    col = srgb(172, 162, 142) * (0.88 + 0.12 * tone + 0.1 * (a - 0.5))[..., None]
    col *= (0.75 + 0.25 * h)[..., None]
    h = h + 0.15 * fbm(n, 64, 4, 33)
    save("ashlar_col", col)
    save("ashlar_nrm", normals(h, 3.0))


def granite_tex(n=512):
    """Speckled dark granite: tile 1 m."""
    s = fbm(n, 128, 2, 41)
    m = fbm(n, 16, 4, 42)
    col = srgb(92, 90, 88) * (0.75 + 0.35 * m)[..., None]
    col[s > 0.62] = srgb(170, 166, 160)
    col[s < 0.32] = srgb(40, 38, 38)
    save("granite_col", col)


def roof_tex(n=1024):
    """Torch-on bitumen in 1 m strips with lapped seams: tile 4 m."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    fx = (x / (n / 4)) % 1
    seam = np.exp(-((fx - 0.03) / 0.008) ** 2)
    grit = fbm(n, 256, 2, 51)
    stain = fbm(n, 4, 5, 52)
    col = srgb(78, 78, 80) * (0.75 + 0.2 * grit + 0.25 * stain)[..., None]
    col *= (1 - 0.25 * seam)[..., None]
    h = 0.3 * grit + 0.8 * seam
    save("roof_col", col)
    save("roof_nrm", normals(h, 3.0))


def wood_tex(n=512):
    """Weathered cedar staves 0.15 m wide: tile 1.2 m."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    fx = (x / (n / 8)) % 1
    stave = np.floor(x / (n / 8)).astype(int)
    rng = np.random.default_rng(61)
    tone = rng.random(8)[stave]
    grain = fbm(n, 16, 5, 62, stretch=(4, 1))
    col = srgb(120, 98, 76) * (0.7 + 0.25 * tone + 0.3 * grain)[..., None]
    gap = np.minimum(fx, 1 - fx) < 0.03
    col[gap] *= 0.35
    h = np.where(gap, 0.0, 1.0) + 0.2 * grain
    save("wood_col", col)
    save("wood_nrm", normals(h, 2.0))


def bars_tex():
    """Wrought-iron railing: square bars every 0.12 m with collars; tile 1.2 x 1 m."""
    w, hh = 1024, 256
    y, x = np.mgrid[0:hh, 0:w].astype(np.float32)
    u = (x / w * 10) % 1  # ten bars over 1.2 m
    v = y / hh
    bar = np.abs(u - 0.5) < 0.07
    collar = bar & (np.abs(v - 0.5) < 0.03) & (np.abs(u - 0.5) < 0.12)
    spear = (np.abs(u - 0.5) < 0.12 - (0.12 - v) * 0) & (v < 0.06)
    a = (bar | collar | spear).astype(np.float32)
    col = np.zeros((hh, w, 3), np.float32) + srgb(30, 30, 32)
    save("bars", col, a)


def grate_tex():
    """Fire escape slats: 0.04 m bars, 0.025 m gaps; tile 1 m."""
    n = 512
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    v = (y / n * 15) % 1
    u = (x / n * 4) % 1
    a = ((v < 0.62) | (np.abs(u - 0.5) < 0.02)).astype(np.float32)
    col = np.zeros((n, n, 3), np.float32) + srgb(34, 34, 36)
    save("grate", col, a)


def awning_tex():
    """Canvas stripes, 0.25 m: tile 1 m."""
    n = 512
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    s = np.floor(x / (n / 4)).astype(int) % 2
    weave = fbm(n, 128, 2, 71)
    col = np.where(s[..., None] == 0, srgb(38, 92, 64), srgb(232, 226, 208))
    col *= (0.9 + 0.12 * weave)[..., None]
    save("awning_col", col)


def grime_tex(n=512):
    """Grey noise the viewer samples in world space for weathering: blotches and rain streaks."""
    g = fbm(n, 4, 7, 91)
    g = (g - g.min()) / (g.max() - g.min())
    save("grime", g)


def ground_tex(n=1024):
    """Pavement slabs (0.9 m, tile 3.6 m) and asphalt (tile 6 m) for the viewer's street."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    f = (x / (n / 4)) % 1, (y / (n / 4)) % 1
    e = np.minimum(np.minimum(f[0], 1 - f[0]), np.minimum(f[1], 1 - f[1]))
    slab = (np.floor(x / (n / 4)) + 4 * np.floor(y / (n / 4))).astype(int)
    tone = np.random.default_rng(81).random(16)[slab]
    a = fbm(n, 16, 6, 82)
    col = srgb(142, 138, 132) * (0.86 + 0.1 * tone + 0.12 * (a - 0.5))[..., None]
    col[e < 0.006] *= 0.6
    save("pave_col", col)
    save("pave_nrm", normals(np.clip(e / 0.01, 0, 1) + 0.1 * fbm(n, 128, 3, 83), 3.0))
    g = fbm(n, 256, 2, 84)
    p = fbm(n, 8, 6, 85)
    col = srgb(64, 64, 66) * (0.75 + 0.3 * g + 0.3 * (p - 0.5))[..., None]
    col[g > 0.75] = srgb(120, 118, 114)
    save("asphalt_col", col)
    save("asphalt_nrm", normals(g, 1.5))


# ---- geometry ------------------------------------------------------------------

AXES = {(1, 0, 0): "x1", (-1, 0, 0): "x0", (0, 1, 0): "y1", (0, -1, 0): "y0", (0, 0, 1): "z1", (0, 0, -1): "z0"}


def key(v):
    return AXES[tuple(int(round(c)) for c in v)]


class Mesh:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.fixed = self.bm.faces.layers.int.new("fixed")
        self.roles = []

    def mi(self, role):
        if role not in self.roles:
            self.roles.append(role)
        return self.roles.index(role)

    def poly(self, role, pts, out=None, uvs=None, smooth=False):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.mi(role)
        f.smooth = smooth
        f.normal_update()
        if out is not None and f.normal.dot(Vector(out)) < 0:
            f.normal_flip()
        if uvs:
            at = {v: uv for v, uv in zip(vs, uvs)}
            for loop in f.loops:
                loop[self.uv].uv = at[loop.vert]
            f[self.fixed] = 1
        return f

    def box(self, role, lo, hi, skip=()):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        z0, z1 = min(z0, z1), max(z0, z1)
        faces = {
            "x0": ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
            "x1": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
            "y0": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
            "y1": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
            "z0": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
            "z1": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        }
        for k, (pts, out) in faces.items():
            if k not in skip:
                self.poly(role, pts, out)

    def strut(self, role, a, b, t, t2=None):
        """A square bar from a to b."""
        a, b = Vector(a), Vector(b)
        ax = (b - a).normalized()
        p1 = ax.cross(Z) if abs(ax.z) < 0.99 else Vector((1, 0, 0))
        p1.normalize()
        p2 = ax.cross(p1).normalized()
        h1, h2 = p1 * t / 2, p2 * (t2 or t) / 2
        ring = [h1 + h2, -h1 + h2, -h1 - h2, h1 - h2]
        for i in range(4):
            c0, c1 = ring[i], ring[(i + 1) % 4]
            self.poly(role, [a + c0, a + c1, b + c1, b + c0], out=(c0 + c1))
        self.poly(role, [a + c for c in ring], out=-ax)
        self.poly(role, [b + c for c in ring], out=ax)

    def cyl(self, role, x, y, r, z0, z1, seg=24, top=True, bottom=False, uv=False, r1=None):
        r1 = r if r1 is None else r1
        for i in range(seg):
            a0, a1 = i / seg * math.tau, (i + 1) / seg * math.tau
            p = lambda a, rr, z: (x + math.cos(a) * rr, y + math.sin(a) * rr, z)
            pts = [p(a0, r, z0), p(a1, r, z0), p(a1, r1, z1), p(a0, r1, z1)]
            uvs = [(a0 * r, z0), (a1 * r, z0), (a1 * r, z1), (a0 * r, z1)] if uv else None
            mid = (a0 + a1) / 2
            self.poly(role, pts, out=(math.cos(mid), math.sin(mid), 0), uvs=uvs, smooth=True)
        ring = lambda rr, z: [(x + math.cos(i / seg * math.tau) * rr, y + math.sin(i / seg * math.tau) * rr, z) for i in range(seg)]
        if top and r1 > 0:
            self.poly(role, ring(r1, z1), out=(0, 0, 1))
        if bottom:
            self.poly(role, ring(r, z0), out=(0, 0, -1))

    def sweep(self, role, W, D, profile, cx=0.0, cy=0.0):
        """Sweeps (offset, z) points round a W x D rectangle with mitred corners."""
        def ring(o, z):
            return [(cx - W / 2 - o, cy - D / 2 - o, z), (cx + W / 2 + o, cy - D / 2 - o, z),
                    (cx + W / 2 + o, cy + D / 2 + o, z), (cx - W / 2 - o, cy + D / 2 + o, z)]
        outs = [(0, -1, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0)]
        for (o0, z0), (o1, z1) in zip(profile, profile[1:]):
            r0, r1 = ring(o0, z0), ring(o1, z1)
            for i in range(4):
                j = (i + 1) % 4
                dz, do = z1 - z0, o1 - o0
                out = Vector(outs[i]) * dz - Z * do  # perpendicular to the profile segment
                if out.length < 1e-6:
                    continue
                self.poly(role, [r0[i], r0[j], r1[j], r1[i]], out=out)

    def finish(self):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.0004)
        for f in self.bm.faces:
            if f[self.fixed]:
                continue
            n = f.normal
            for loop in f.loops:
                p = loop.vert.co
                if abs(n.z) > 0.7:
                    uv = (p.x, p.y)
                elif abs(n.x) >= abs(n.y):
                    uv = (p.y * (1 if n.x > 0 else -1), p.z)
                else:
                    uv = (-p.x * (1 if n.y > 0 else -1), p.z)
                loop[self.uv].uv = uv
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        for role in self.roles:
            mat = bpy.data.materials.get(role) or bpy.data.materials.new(role)
            me.materials.append(mat)
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


class Side:
    """A facade's frame: u along it (left to right seen from outside), z up, w outward."""

    def __init__(self, m, o, t, n):
        self.m, self.o, self.t, self.n = m, Vector(o), Vector(t), Vector(n)

    def p(self, u, z, w=0.0):
        return self.o + self.t * u + Z * z + self.n * w

    def box(self, role, u0, u1, z0, z1, w0, w1, skip=("back",), m=None):
        names = {"back": key(-self.n), "front": key(self.n), "left": key(-self.t), "right": key(self.t), "top": "z1", "bottom": "z0"}
        (m or self.m).box(role, self.p(u0, z0, w0), self.p(u1, z1, w1), [names[s] for s in skip])

    def quad(self, role, u0, u1, z0, z1, w=0.0, uvs=None, out=None, m=None):
        pts = [self.p(u0, z0, w), self.p(u1, z0, w), self.p(u1, z1, w), self.p(u0, z1, w)]
        (m or self.m).poly(role, pts, out=out or self.n, uvs=uvs)

    def wall(self, role, u0, u1, z0, z1, holes, depth=0.22, reveal=None):
        zs = sorted({z0, z1, *[c for h in holes for c in h[2:4] if z0 < c < z1]})
        for za, zb in zip(zs, zs[1:]):
            cover = sorted((h[0], h[1]) for h in holes if h[2] <= za + 1e-6 and h[3] >= zb - 1e-6)
            u = u0
            for a, b in cover:
                if a > u + 1e-6:
                    self.quad(role, u, a, za, zb)
                u = max(u, b)
            if u1 > u + 1e-6:
                self.quad(role, u, u1, za, zb)
        rv = reveal or role
        for a, b, c, e, *deep in holes:
            d = deep[0] if deep else depth
            self.m.poly(rv, [self.p(a, c, 0), self.p(a, c, -d), self.p(a, e, -d), self.p(a, e, 0)], out=self.t)
            self.m.poly(rv, [self.p(b, c, 0), self.p(b, c, -d), self.p(b, e, -d), self.p(b, e, 0)], out=-self.t)
            self.m.poly(rv, [self.p(a, e, 0), self.p(b, e, 0), self.p(b, e, -d), self.p(a, e, -d)], out=-Z)
            self.m.poly(rv, [self.p(a, c, 0), self.p(b, c, 0), self.p(b, c, -d), self.p(a, c, -d)], out=Z)


WID = [0]


def pane(F, role, a, b, c, e, u0, u1, z0, z1, w, wid):
    """A glass pane inside opening (a..b, c..e): UV0 is (window id + u, v) over the opening."""
    uv = lambda u, z: (wid + (u - a) / (b - a), (z - c) / (e - c))
    F.quad(role, u0, u1, z0, z1, w, uvs=[uv(u0, z0), uv(u1, z0), uv(u1, z1), uv(u0, z1)])


def new_id():
    WID[0] += 1
    return WID[0]


def sash(F, a, b, c, e, D=0.22, lights=2):
    """A double-hung sash window in the opening (a..b, c..e) set D deep."""
    fr, wid = "frame", new_id()
    fw = 0.07
    F.box(fr, a, a + fw, c, e, -D, -D + 0.11)
    F.box(fr, b - fw, b, c, e, -D, -D + 0.11)
    F.box(fr, a + fw, b - fw, e - fw, e, -D, -D + 0.11)
    F.box(fr, a + fw, b - fw, c, c + 0.05, -D, -D + 0.13)
    ia, ib, ic, ie = a + fw, b - fw, c + 0.05, e - fw
    mid = (ic + ie) / 2 + 0.04
    st = 0.05
    for z0, z1, wa, wb in ((mid - 0.025, ie, -D + 0.07, -D + 0.11), (ic, mid + 0.025, -D + 0.025, -D + 0.065)):
        F.box(fr, ia, ia + st, z0, z1, wa, wb)
        F.box(fr, ib - st, ib, z0, z1, wa, wb)
        F.box(fr, ia + st, ib - st, z1 - st, z1, wa, wb)
        F.box(fr, ia + st, ib - st, z0, z0 + st, wa, wb)
        gw = wa + 0.015
        pane(F, "glass", a, b, c, e, ia + st, ib - st, z0 + st, z1 - st, gw, wid)
        if lights == 2:
            F.box(fr, (a + b) / 2 - 0.016, (a + b) / 2 + 0.016, z0 + st, z1 - st, gw, wb - 0.01)


def french(F, a, b, c, e, D=0.22):
    """A pair of glazed doors onto a balcony, with a transom light."""
    fr, wid = "frame", new_id()
    fw = 0.08
    F.box(fr, a, a + fw, c, e, -D, -D + 0.11)
    F.box(fr, b - fw, b, c, e, -D, -D + 0.11)
    F.box(fr, a + fw, b - fw, e - fw, e, -D, -D + 0.11)
    t = e - 0.45
    F.box(fr, a + fw, b - fw, t - 0.06, t, -D, -D + 0.11)
    pane(F, "glass", a, b, c, e, a + fw, b - fw, t, e - fw, -D + 0.04, wid)
    m = (a + b) / 2
    for l0, l1 in ((a + fw, m), (m, b - fw)):
        F.box(fr, l0, l0 + 0.06, c, t - 0.06, -D + 0.02, -D + 0.08)
        F.box(fr, l1 - 0.06, l1, c, t - 0.06, -D + 0.02, -D + 0.08)
        F.box(fr, l0 + 0.06, l1 - 0.06, c, c + 0.45, -D + 0.02, -D + 0.08)
        F.box(fr, l0 + 0.06, l1 - 0.06, t - 0.12, t - 0.06, -D + 0.02, -D + 0.08)
        F.box(fr, l0 + 0.06, l1 - 0.06, c + 0.45, c + 0.51, -D + 0.02, -D + 0.08)
        pane(F, "glass", a, b, c, e, l0 + 0.06, l1 - 0.06, c + 0.51, t - 0.12, -D + 0.04, wid)


def sill(F, a, b, c, D=0.22):
    F.box("stone", a - 0.09, b + 0.09, c - 0.07, c + 0.015, -D + 0.04, 0.06)


def lintel(F, a, b, e, key_=True):
    F.box("stone", a - 0.1, b + 0.1, e, e + 0.26, 0, 0.025)
    if key_:
        m = (a + b) / 2
        F.box("stone", m - 0.11, m + 0.11, e - 0.04, e + 0.32, 0, 0.05)


def hood(F, a, b, e):
    """The first floor's pedimented window head: a frieze, a cornice and two consoles."""
    F.box("stone", a - 0.16, b + 0.16, e, e + 0.3, 0, 0.04)
    F.box("stone", a - 0.26, b + 0.26, e + 0.3, e + 0.38, 0, 0.16)
    F.box("stone", a - 0.3, b + 0.3, e + 0.38, e + 0.44, 0, 0.2)
    for u in (a - 0.2, b + 0.08):
        F.box("stone", u, u + 0.12, e - 0.3, e + 0.3, 0, 0.12)


def ac_unit(F, u, c):
    F.box("ac", u - 0.33, u + 0.33, c + 0.04, c + 0.44, -0.12, 0.42, skip=())
    F.box("dark", u - 0.29, u + 0.29, c + 0.08, c + 0.4, 0.42, 0.425, skip=("back",))
    F.box("iron", u - 0.25, u - 0.22, c - 0.3, c + 0.05, 0.0, 0.35)
    F.box("iron", u + 0.22, u + 0.25, c - 0.3, c + 0.05, 0.0, 0.35)


def railing(F, cut, u0, u1, z, w0, w1, h=1.0):
    """Posts and rails in iron with alpha-tested bars between, round three sides."""
    for u in (u0, u1):
        F.box("iron", u - 0.025, u + 0.025, z, z + h, w1 - 0.05, w1)
        F.box("iron", u - 0.02, u + 0.02, z + h - 0.04, z + h, w0, w1)
        F.box("iron", u - 0.015, u + 0.015, z + 0.06, z + 0.1, w0, w1)
    F.box("iron", u0 - 0.03, u1 + 0.03, z + h - 0.04, z + h + 0.01, w1 - 0.06, w1 + 0.01)
    F.box("iron", u0, u1, z + 0.06, z + 0.1, w1 - 0.04, w1 - 0.01)
    L = u1 - u0
    uvs = lambda l: [(0, 0), (l / 1.2, 0), (l / 1.2, 1), (0, 1)]
    F.quad("bars", u0, u1, z + 0.1, z + h - 0.04, w1 - 0.025, uvs=uvs(L), m=cut)
    for u, out in ((u0, -F.t), (u1, F.t)):
        pts = [F.p(u, z + 0.1, w1), F.p(u, z + 0.1, w0), F.p(u, z + h - 0.04, w0), F.p(u, z + h - 0.04, w1)]
        cut.poly("bars", pts, out=out, uvs=uvs(w1 - w0))


# ---- the building ----------------------------------------------------------------

W, D = 14.0, 12.0
G = 4.5  # ground storey
FL = 3.1  # upper storeys
N = 6
TOP = G + N * FL  # 23.1, where the cornice starts
PLINTH = 0.45


def build():
    m, cut = Mesh("apartment"), Mesh("apartment_cutout")
    sides = {
        "front": Side(m, (0, -D / 2, 0), (1, 0, 0), (0, -1, 0)),
        "right": Side(m, (W / 2, 0, 0), (0, 1, 0), (1, 0, 0)),
        "back": Side(m, (0, D / 2, 0), (-1, 0, 0), (0, 1, 0)),
        "left": Side(m, (-W / 2, 0, 0), (0, -1, 0), (-1, 0, 0)),
    }
    half = {"front": W / 2, "back": W / 2, "right": D / 2, "left": D / 2}
    bays = {"front": [-5.2, -2.6, 0.0, 2.6, 5.2], "back": [-5.2, -2.6, 0.0, 2.6, 5.2], "right": [-4.2, -1.4, 1.4, 4.2], "left": [-4.2, -1.4, 1.4, 4.2]}
    ww, wh, sh = 1.3, 1.8, 0.9

    # Plinth, string course, cornice, parapet coping.
    m.sweep("granite", W, D, [(0.06, 0.0), (0.06, PLINTH - 0.04), (0.02, PLINTH), (-0.01, PLINTH)])
    m.sweep("stone", W, D, [(-0.01, G - 0.12), (0.05, G - 0.12), (0.05, G), (0.12, G + 0.06), (0.12, G + 0.2), (0.07, G + 0.24), (0.04, G + 0.3), (-0.01, G + 0.3)])
    m.sweep("stone", W, D, [(-0.01, TOP), (0.06, TOP), (0.06, TOP + 0.22), (0.03, TOP + 0.26), (-0.01, TOP + 0.26)])
    cz = TOP + 0.95  # cornice soffit
    m.sweep("stone", W, D, [(-0.01, cz - 0.2), (0.1, cz - 0.2), (0.1, cz - 0.1), (0.16, cz - 0.04), (0.18, cz), (0.62, cz), (0.66, cz + 0.06), (0.66, cz + 0.2), (0.74, cz + 0.28), (0.76, cz + 0.36), (0.6, cz + 0.4), (-0.01, cz + 0.42)])
    PT = cz + 0.42  # parapet base
    PH = 0.9
    m.sweep("stone", W, D, [(-0.31, PT + PH - 0.02), (-0.36, PT + PH - 0.02), (-0.36, PT + PH + 0.12), (0.05, PT + PH + 0.12), (0.05, PT + PH - 0.02), (-0.01, PT + PH - 0.02)])

    for name, F in sides.items():
        h = half[name]
        # Ground storey.
        holes = []
        if name == "front":
            shops = [(-6.3, -2.1), (2.1, 6.3)]
            entry = (-0.95, 0.95)
            holes = [(a, b, PLINTH, 3.45) for a, b in shops] + [(entry[0], entry[1], PLINTH, 3.3, 1.0)]
            F.wall("ashlar", -h, h, PLINTH, G, holes, depth=0.3, reveal="stone")
            for i, (a, b) in enumerate(shops):
                shopfront(F, cut, a, b, door_left=i == 1, awning=i == 0)
            entrance(F, *entry)
        else:
            gb = bays[name]
            holes = [(u - 0.6, u + 0.6, 1.4, 3.3) for u in gb]
            F.wall("ashlar", -h, h, PLINTH, G, holes, depth=0.3, reveal="stone")
            for a, b, c, e in holes:
                sash(F, a, b, c, e, D=0.3)
                F.box("stone", a - 0.08, b + 0.08, c - 0.08, c + 0.015, -0.26, 0.07)
                grille(F, a, b, c, e)
        # Upper storeys in brick, quoins at the corners.
        holes, kinds = [], []
        for f in range(N):
            z = G + f * FL
            for u in bays[name]:
                balc = name == "front" and u == 0.0 and 1 <= f <= 4
                if balc:
                    holes.append((u - 0.7, u + 0.7, z + 0.05, z + 2.5))
                else:
                    holes.append((u - ww / 2, u + ww / 2, z + sh, z + sh + wh))
                kinds.append((f, u, balc))
        F.wall("brick", -h, h, G, TOP, holes, depth=0.22)
        for (a, b, c, e), (f, u, balc) in zip(holes, kinds):
            if balc:
                french(F, a, b, c, e)
                balcony(F, cut, u, c - 0.05)
                lintel(F, a, b, e)
                continue
            sash(F, a, b, c, e)
            sill(F, a, b, c)
            if f == 0 and name != "back":
                hood(F, a, b, e)
            else:
                lintel(F, a, b, e, key_=name != "back")
            if name in ("left", "back") and R.random() < 0.22 and f < N - 1:
                ac_unit(F, u, c)
        for f in range(N * 7):
            z0 = G + 0.3 + f * 0.43
            if z0 + 0.43 > TOP:
                break
            L = 0.62 if f % 2 == 0 else 0.36
            F.box("stone", -h - 0.0, -h + L, z0 + 0.012, z0 + 0.43 - 0.012, 0, 0.025, skip=("back", "left"))
            F.box("stone", h - L, h, z0 + 0.012, z0 + 0.43 - 0.012, 0, 0.025, skip=("back", "right"))
        # Frieze: brick, with dentils under the cornice and modillions in it.
        F.wall("brick", -h, h, TOP, PT, [])
        for i in range(int((2 * h) / 0.22)):
            u = -h + 0.11 + i * 0.22
            F.box("stone", u - 0.06, u + 0.06, cz - 0.36, cz - 0.2, 0, 0.09)
        n = int((2 * h) / 0.75)
        for i in range(n + 1):
            u = -h + 0.35 + i * (2 * h - 0.7) / n
            F.box("stone", u - 0.08, u + 0.08, cz - 0.1, cz, 0.08, 0.58)
            F.box("stone", u - 0.08, u + 0.08, cz - 0.22, cz - 0.1, 0.08, 0.2)
        # Parapet: outer face flush with the frieze, inner face 0.3 m in.
        F.wall("brick", -h, h, PT, PT + PH, [])
        F.quad("brick", h - 0.3, -h + 0.3, PT, PT + PH, -0.3, out=-F.n)

    fire_escape(sides["right"], cut)
    roof(m, cut, PT)
    return m, cut


def grille(F, a, b, c, e):
    """Iron security bars over a ground-storey window."""
    for i in range(7):
        u = a + 0.08 + i * (b - a - 0.16) / 6
        F.box("iron", u - 0.012, u + 0.012, c + 0.02, e - 0.02, 0.02, 0.05)
    for z in (c + 0.12, (c + e) / 2, e - 0.12):
        F.box("iron", a + 0.04, b - 0.04, z - 0.015, z + 0.015, 0.05, 0.075)


def shopfront(F, cut, a, b, door_left, awning):
    D = 0.3
    fr = "shopframe"
    c, e = PLINTH, 3.45
    t = 2.85  # transom bar
    # Stallriser, posts, transom bar, head.
    F.box(fr, a, b, c, c + 0.4, -D, -D + 0.14)
    F.box(fr, a, a + 0.1, c, e, -D, -D + 0.16)
    F.box(fr, b - 0.1, b, c, e, -D, -D + 0.16)
    F.box(fr, a + 0.1, b - 0.1, t - 0.08, t, -D, -D + 0.16)
    F.box(fr, a + 0.1, b - 0.1, e - 0.08, e, -D, -D + 0.16)
    wid = new_id()
    dw = 1.1
    d0, d1 = (a + 0.1, a + 0.1 + dw) if door_left else (b - 0.1 - dw, b - 0.1)
    g0, g1 = (d1 + 0.06, b - 0.1) if door_left else (a + 0.1, d0 - 0.06)
    F.box(fr, d0 - 0.06 if not door_left else d1, d0 if not door_left else d1 + 0.06, c, t, -D, -D + 0.16)
    # Display window in two lights, and the door.
    mid = (g0 + g1) / 2
    F.box(fr, mid - 0.03, mid + 0.03, c + 0.4, t - 0.08, -D + 0.02, -D + 0.12)
    pane(F, "shopglass", a, b, c, e, g0, g1, c + 0.4, t - 0.08, -D + 0.06, wid)
    pane(F, "shopglass", a, b, c, e, a + 0.1, b - 0.1, t, e - 0.08, -D + 0.06, wid)
    for u in [a + 0.1 + i * (b - a - 0.2) / 4 for i in range(1, 4)]:
        F.box(fr, u - 0.025, u + 0.025, t, e - 0.08, -D + 0.02, -D + 0.12)
    F.box(fr, d0, d1, c, c + 0.1, -D - 0.05, -D + 0.04)
    F.box(fr, d0, d0 + 0.09, c, t - 0.08, -D - 0.05, -D + 0.04)
    F.box(fr, d1 - 0.09, d1, c, t - 0.08, -D - 0.05, -D + 0.04)
    F.box(fr, d0 + 0.09, d1 - 0.09, c + 0.1, c + 0.35, -D - 0.05, -D + 0.04)
    F.box(fr, d0 + 0.09, d1 - 0.09, t - 0.16, t - 0.08, -D - 0.05, -D + 0.04)
    pane(F, "shopglass", a, b, c, e, d0 + 0.09, d1 - 0.09, c + 0.35, t - 0.16, -D, wid)
    hx = d1 - 0.18 if door_left else d0 + 0.14
    F.box("brass", hx, hx + 0.04, 1.3, 1.75, -D + 0.04, -D + 0.08)
    # Fascia with the shop's sign, between console brackets.
    F.box("shopframe", a - 0.15, b + 0.15, 3.55, 4.25, 0, 0.12)
    F.box("shopframe", a - 0.2, b + 0.2, 4.25, 4.33, 0, 0.18)
    sign = 0 if awning else 1
    F.quad("sign", a + 0.1, b - 0.1, 3.62, 4.18, 0.121, uvs=[(sign, 0), (sign + 1, 0), (sign + 1, 1), (sign, 1)])
    for u in (a - 0.32, b + 0.15):
        F.box("shopframe", u, u + 0.17, 3.3, 4.33, 0, 0.2)
    if awning:
        x0, x1 = a - 0.1, b + 0.1
        top, drop, depth = 3.5, 0.75, 1.5
        m, p = F.m, F.p
        m.poly("awning", [p(x0, top, 0.05), p(x1, top, 0.05), p(x1, top - drop, depth), p(x0, top - drop, depth)], out=F.n + Z)
        m.poly("awning", [p(x0, top, 0.05), p(x1, top, 0.05), p(x1, top - drop, depth), p(x0, top - drop, depth)], out=-F.n - Z)
        m.poly("awning", [p(x0, top - drop, depth), p(x1, top - drop, depth), p(x1, top - drop - 0.28, depth), p(x0, top - drop - 0.28, depth)], out=F.n)
        m.poly("awning", [p(x0, top - drop, depth), p(x1, top - drop, depth), p(x1, top - drop - 0.28, depth), p(x0, top - drop - 0.28, depth)], out=-F.n)
        for u in (x0, x1):
            pts = [p(u, top, 0.05), p(u, top - drop, depth), p(u, top - drop - 0.12, depth)]
            m.poly("awning", pts, out=F.t)
            m.poly("awning", pts, out=-F.t)
        F.box("iron", x0, x1, top - drop - 0.03, top - drop + 0.02, depth - 0.04, depth + 0.01, skip=())
        for u in (x0 + 0.05, x1 - 0.05):
            m.strut("iron", p(u, top - 0.6, 0.0), p(u, top - drop, depth - 0.03), 0.03)


def entrance(F, a, b):
    """The residents' door: recessed, with a fanlight, a stone surround and a glass canopy."""
    D = 1.0
    c, e = PLINTH, 3.3
    # The recess's floor, step and the door at its back.
    F.box("granite", a, b, c - 0.01, c, -D, 0, skip=())
    F.box("granite", a - 0.4, b + 0.4, 0, 0.15, 0, 0.75, skip=("back",))
    F.box("granite", a - 0.3, b + 0.3, 0.15, 0.3, 0, 0.45, skip=("back",))
    F.box("granite", a - 0.2, b + 0.2, 0.3, PLINTH, 0, 0.15, skip=("back",))
    F.quad("stone", a, b, c, e, -D)
    dr = "door"
    wid = new_id()
    da, db = a + 0.12, b - 0.12
    t = 2.65
    F.box(dr, da - 0.08, db + 0.08, c, t + 0.08, -D, -D + 0.08)
    m = (da + db) / 2
    for l0, l1 in ((da, m - 0.005), (m + 0.005, db)):
        F.box(dr, l0, l1, c, t, -D, -D + 0.13)
        pane(F, "doorglass", a, b, c, e, l0 + 0.12, l1 - 0.12, c + 1.0, t - 0.15, -D + 0.135, wid)
        F.box("dark", l0 + 0.1, l1 - 0.1, c + 0.25, c + 0.8, -D + 0.13, -D + 0.14)
    F.box("brass", m - 0.12, m - 0.04, 1.4, 1.48, -D + 0.13, -D + 0.18)
    F.box("brass", m + 0.04, m + 0.12, 1.4, 1.48, -D + 0.13, -D + 0.18)
    pane(F, "doorglass", a, b, c, e, da, db, t + 0.08, e - 0.05, -D + 0.04, wid)
    for i in range(1, 6):
        u = da + i * (db - da) / 6
        F.box(dr, u - 0.015, u + 0.015, t + 0.08, e - 0.05, -D + 0.04, -D + 0.07)
    # Surround: pilasters and an entablature.
    for u0, u1 in ((a - 0.35, a), (b, b + 0.35)):
        F.box("stone", u0, u1, PLINTH, e + 0.05, 0, 0.1)
        F.box("stone", u0 - 0.04, u1 + 0.04, PLINTH, PLINTH + 0.3, 0, 0.14)
    F.box("stone", a - 0.42, b + 0.42, e + 0.05, e + 0.45, 0, 0.12)
    F.box("stone", a - 0.5, b + 0.5, e + 0.45, e + 0.55, 0, 0.22)
    # Canopy and lamps.
    F.box("iron", a - 0.6, b + 0.6, e + 0.6, e + 0.68, 0, 1.3, skip=())
    F.box("canopy", a - 0.55, b + 0.55, e + 0.68, e + 0.7, 0.05, 1.25, skip=())
    p = F.p
    for u in (a - 0.5, b + 0.5):
        F.m.strut("iron", p(u, e + 1.6, 0.0), p(u, e + 0.7, 1.25), 0.025)
    for u in (a - 0.6, b + 0.6):
        F.box("iron", u - 0.06, u + 0.06, 2.0, 2.06, 0, 0.18)
        F.box("lamp", u - 0.07, u + 0.07, 2.06, 2.32, 0.11, 0.25, skip=())
        F.box("iron", u - 0.09, u + 0.09, 2.32, 2.36, 0.09, 0.27, skip=())
    # House number plaque.
    F.box("brass", b + 0.42, b + 0.62, 2.0, 2.2, 0.0, 0.02)


def balcony(F, cut, u, z):
    """A stone balcony on two scrolled corbels with an iron railing."""
    F.box("stone", u - 1.15, u + 1.15, z - 0.18, z, 0, 0.95, skip=())
    F.box("stone", u - 1.18, u + 1.18, z - 0.24, z - 0.18, 0, 0.98, skip=())
    for k in (-0.85, 0.85):
        F.box("stone", u + k - 0.1, u + k + 0.1, z - 0.6, z - 0.24, 0, 0.35)
        F.box("stone", u + k - 0.1, u + k + 0.1, z - 0.4, z - 0.24, 0.35, 0.75)
    railing(F, cut, u - 1.1, u + 1.1, z, 0.05, 0.9)


def fire_escape(F, cut):
    """Landings at every upper storey, joined by stairs, with a drop ladder to the street."""
    u0, u1 = -2.5, 2.5
    w = 1.05
    for f in range(N):
        z = G + f * FL + 0.75
        cut.poly("grate", [F.p(u0, z, 0.02), F.p(u1, z, 0.02), F.p(u1, z, w), F.p(u0, z, w)], out=Z, uvs=[(0, 0), (5, 0), (5, w), (0, w)])
        cut.poly("grate", [F.p(u0, z, 0.02), F.p(u1, z, 0.02), F.p(u1, z, w), F.p(u0, z, w)], out=-Z, uvs=[(0, 0), (5, 0), (5, w), (0, w)])
        F.box("iron", u0, u1, z - 0.1, z, w - 0.04, w, skip=())
        F.box("iron", u0, u1, z - 0.1, z, 0.0, 0.04, skip=())
        for u in (u0, u1):
            F.box("iron", u - 0.02, u + 0.02, z - 0.1, z, 0.0, w, skip=())
            F.m.strut("iron", F.p(u, z - 0.9, 0.0), F.p(u, z - 0.05, w - 0.05), 0.04)
        railing(F, cut, u0, u1, z, 0.02, w)
        if f < N - 1:
            # Stairs up to the next landing, alternating direction.
            s0, s1 = (u0 + 0.5, u1 - 0.9) if f % 2 == 0 else (u1 - 0.5, u0 + 0.9)
            zt = z + FL
            wa, wb = 0.1, 0.65
            for wq in (wa, wb):
                F.m.strut("iron", F.p(s0, z, wq), F.p(s1, zt, wq), 0.05, 0.16)
                F.m.strut("iron", F.p(s0, z + 0.85, wq), F.p(s1, zt + 0.85, wq), 0.035)
            steps = 15
            for i in range(1, steps):
                k = i / steps
                us, zs = s0 + (s1 - s0) * k, z + (zt - z) * k
                F.box("iron", us - 0.1, us + 0.1, zs - 0.02, zs, wa + 0.02, wb - 0.02, skip=())
    # Drop ladder below the first landing.
    z = G + 0.75
    for wq in (0.35, 0.75):
        F.m.strut("iron", F.p(u1 - 0.4, z, wq), F.p(u1 - 0.4, 2.6, wq), 0.04)
    for i in range(int((z - 2.6) / 0.3)):
        zz = 2.7 + i * 0.3
        F.m.strut("iron", F.p(u1 - 0.4, zz, 0.35), F.p(u1 - 0.4, zz, 0.75), 0.025)


def roof(m, cut, PT):
    z = PT - 0.05
    m.poly("roof", [(-W / 2 + 0.3, -D / 2 + 0.3, z), (W / 2 - 0.3, -D / 2 + 0.3, z), (W / 2 - 0.3, D / 2 - 0.3, z), (-W / 2 + 0.3, D / 2 - 0.3, z)], out=Z)
    # Stair bulkhead with a door.
    bx0, bx1, by0, by1 = -5.6, -2.2, 1.6, 5.4
    h = 2.7
    for name, F in {
        "f": Side(m, ((bx0 + bx1) / 2, by0, z), (1, 0, 0), (0, -1, 0)),
        "r": Side(m, (bx1, (by0 + by1) / 2, z), (0, 1, 0), (1, 0, 0)),
        "b": Side(m, ((bx0 + bx1) / 2, by1, z), (-1, 0, 0), (0, 1, 0)),
        "l": Side(m, (bx0, (by0 + by1) / 2, z), (0, -1, 0), (-1, 0, 0)),
    }.items():
        L = (bx1 - bx0) / 2 if name in "fb" else (by1 - by0) / 2
        holes = [(-0.5, 0.5, 0.0, 2.1)] if name == "f" else []
        F.wall("brick", -L, L, 0, h, holes, depth=0.12)
        if holes:
            F.quad("door", -0.5, 0.5, 0, 2.1, -0.12)
            F.box("iron", -0.62, 0.62, 2.1, 2.2, 0, 0.6, skip=())
    m.sweep("stone", bx1 - bx0, by1 - by0, [(-0.01, z + h), (0.06, z + h), (0.06, z + h + 0.12), (-0.01, z + h + 0.12)], cx=(bx0 + bx1) / 2, cy=(by0 + by1) / 2)
    m.poly("roof", [(bx0 + 0.05, by0 + 0.05, z + h + 0.1), (bx1 - 0.05, by0 + 0.05, z + h + 0.1), (bx1 - 0.05, by1 - 0.05, z + h + 0.1), (bx0 + 0.05, by1 - 0.05, z + h + 0.1)], out=Z)
    # Water tank on a steel stand.
    tx, ty, tr = 3.4, 2.4, 1.45
    legs = 2.4
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = tx + dx * tr * 0.72, ty + dy * tr * 0.72
        m.box("steel", (x - 0.08, y - 0.08, z), (x + 0.08, y + 0.08, z + legs))
    for (dx0, dy0), (dx1, dy1) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
        a = Vector((tx + dx0 * tr * 0.72, ty + dy0 * tr * 0.72, z + 0.3))
        b = Vector((tx + dx1 * tr * 0.72, ty + dy1 * tr * 0.72, z + legs - 0.2))
        m.strut("steel", a, b, 0.04)
        m.strut("steel", Vector((a.x, a.y, b.z)), Vector((b.x, b.y, a.z)), 0.04)
    m.box("steel", (tx - tr - 0.1, ty - tr - 0.1, z + legs), (tx + tr + 0.1, ty + tr + 0.1, z + legs + 0.15))
    t0, t1 = z + legs + 0.15, z + legs + 2.75
    m.cyl("wood", tx, ty, tr, t0, t1, seg=32, top=False, uv=True)
    m.cyl("wood", tx, ty, tr, t1, t1 + 0.75, seg=32, r1=0.12, uv=True)
    m.cyl("steel", tx, ty, 0.14, t1 + 0.7, t1 + 0.95, seg=8, r1=0.0)
    for k in range(5):
        hz = t0 + 0.3 + k * 0.52
        m.cyl("steel", tx, ty, tr + 0.025, hz, hz + 0.05, seg=32, top=False)
    m.strut("steel", (tx + tr + 0.15, ty, z + 0.2), (tx + tr + 0.15, ty, t1 + 0.1), 0.04)
    # Rooftop plant: two condensers and vents.
    for x, y in ((-0.5, -3.6), (2.3, -3.6)):
        m.box("ac", (x - 0.9, y - 0.6, z), (x + 0.9, y + 0.6, z + 1.1))
        m.cyl("dark", x - 0.42, y, 0.36, z + 1.1, z + 1.13, seg=16)
        m.cyl("dark", x + 0.42, y, 0.36, z + 1.1, z + 1.13, seg=16)
        m.box("concrete", (x - 1.0, y - 0.7, z), (x + 1.0, y + 0.7, z + 0.12))
    for x, y, hh in ((0.6, 4.6, 1.2), (1.4, 4.9, 0.9), (-1.0, 0.0, 0.8), (5.6, -1.4, 1.0)):
        m.cyl("ac", x, y, 0.08, z, z + hh, seg=10)
        m.cyl("ac", x, y, 0.13, z + hh, z + hh + 0.12, seg=10)
    # Chimney stacks on the party walls.
    for x in (-3.5, 3.0):
        y = D / 2 - 0.15
        m.box("brick", (x - 0.55, y - 0.5, z), (x + 0.55, y + 0.1, z + 2.2))
        m.sweep("stone", 1.1, 0.6, [(-0.01, z + 2.2), (0.06, z + 2.2), (0.06, z + 2.32), (-0.01, z + 2.32)], cx=x, cy=y - 0.2)
        m.poly("stone", [(x - 0.56, y - 0.51, z + 2.32), (x + 0.56, y - 0.51, z + 2.32), (x + 0.56, y + 0.11, z + 2.32), (x - 0.56, y + 0.11, z + 2.32)], out=Z)
        for k in (-0.25, 0.25):
            m.cyl("terracotta", x + k, y - 0.2, 0.11, z + 2.32, z + 2.7, seg=10, r1=0.09)


# ---- bake and export ---------------------------------------------------------------


def bake(ob, size=2048):
    me = ob.data
    light = me.uv_layers.new(name="Light")
    me.uv_layers.active = light
    light.active_render = True
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.0015, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    if SKIP_BAKE:
        return
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 96
    sc.world = bpy.data.worlds.new("w")
    sc.world.light_settings.distance = 2.5
    img = bpy.data.images.new("ao", size, size, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    for mat in me.materials:
        mat.use_nodes = True
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.select = True
        mat.node_tree.nodes.active = node
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    sc.render.bake.margin = 8
    bpy.ops.object.bake(type="AO", use_clear=True)
    img.filepath_raw = os.path.join(OUT, "ao.png")
    img.file_format = "PNG"
    img.save()
    bpy.data.objects.remove(ground)
    me.uv_layers["UVMap"].active_render = True
    px = np.array(img.pixels[:]).reshape(-1, 4)[:, 0]
    print("ao mean", px.mean(), "dark", (px < 0.2).mean())
    if os.environ.get("AO_DEBUG"):
        light = me.uv_layers["Light"]
        big = sorted(me.polygons, key=lambda p: -p.area)[:12]
        for p in big:
            uv = sum((light.data[i].uv for i in p.loop_indices), Vector((0, 0))) / p.loop_total
            x, y = int(uv.x * size), int(uv.y * size)
            print("face", round(p.area, 1), tuple(round(c, 1) for c in p.normal), tuple(round(c, 1) for c in p.center), me.materials[p.material_index].name, "ao", round(img.pixels[(y * size + x) * 4], 3), "uv", round(uv.x, 3), round(uv.y, 3))
    for mat in me.materials:
        nodes = mat.node_tree.nodes
        for n in [n for n in nodes if n.type == "TEX_IMAGE"]:
            nodes.remove(n)


def main():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for f in (brick_tex, stone_tex, ashlar_tex, granite_tex, roof_tex, wood_tex, bars_tex, grate_tex, awning_tex, ground_tex, grime_tex):
        f()
        print("texture", f.__name__)
    m, cut = build()
    ob, co = m.finish(), cut.finish()
    print("faces", len(ob.data.polygons), len(co.data.polygons), "windows", WID[0])
    bake(ob)
    for o in bpy.data.objects:
        o.select_set(o in (ob, co))
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "apartment.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True, export_normals=True, export_materials="EXPORT")


main()
