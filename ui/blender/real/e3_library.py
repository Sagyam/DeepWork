# E3, library: the City's free public library of 1908, the kind a steel
# fortune paid for in a thousand towns. One lofty storey of red brick over
# a raised basement of rusticated stone, limestone dressings. On the axis
# a Doric portico of four columns under a pediment, PUBLIC LIBRARY on the
# frieze, reached by a broad flight of steps between two stone lions
# lying on plinths; long cloth banners hang from iron poles either side.
# Tall round-headed windows between brick piers, the arches in rubbed
# brick with stone keys; a stone entablature round the top and a low
# parapet. Over the reading room in the middle, an octagonal drum with
# windows and a shallow ribbed copper dome with a lantern.
#
# Pieces (base at the origin):
#   ground  the basement and the main storey (to 7.3 m), the portico's
#           columns and steps, the lions and banners
#   roof    entablature, parapet, the pediment, the drum and dome
import math

from mathutils import Vector

from civic import _ellipsoid, _limb, lathe
from lib import Model, Side, Z, fpoly, letters, new_id, pane, sash, sides, sill
from s4_factory import arch

ID = "e3"
W, D = 14.0, 10.0
HW, HD = W / 2, D / 2
B = 1.3  # the basement
MAIN = 6.0
TOP = B + MAIN
PORT = (-3.3, 3.3)
DEEP = 2.4
STEPS = 6
TREAD = 0.3
SHIFT = (DEEP + STEPS * TREAD + 0.4) / 2 - 0.25  # centre the footprint, steps to back
COLS = [-2.55, -0.85, 0.85, 2.55]
CR = 0.34
ENT = 1.1


def build(out, bake=True):
    M = Model(ID, seed=37)
    M.sharp = math.radians(40)
    M.piece("ground")
    ground(M)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    for mesh in (M.m, M.cut, M.decal):
        for v in mesh.bm.verts:
            v.co.y += SHIFT
    M.export(out, bake)


# ---- the walls ------------------------------------------------------------------------


def round_window(F, a, b, c, e, D_=0.34):
    """A tall window with a round head: a sash to the springing, a fanlight in the arch."""
    half = (b - a) / 2
    spring = e - half
    sash(F, a, b, c, spring, D=D_, lights=(2, 3))
    wid = new_id()
    pane(F, "glass", a, b, spring, e, a + 0.05, b - 0.05, spring, e, -D_ + 0.08, wid)
    F.box("frame", a, b, spring - 0.04, spring + 0.04, -D_, -D_ + 0.11)
    m = (a + b) / 2
    for k in range(1, 4):
        t = math.pi * k / 4
        F.m.strut("frame", F.p(m, spring, -D_ + 0.1), F.p(m - math.cos(t) * half * 0.98, spring + math.sin(t) * half * 0.98, -D_ + 0.1), 0.03)
    arch(F, a, b, e, rise=half, ring=0.3, D=D_)
    sill(F, a, b, c, D=D_)


def ground(M):
    m = M.m
    walls = sides(m, W, D)
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        # The basement: rusticated stone, small windows, a moulded cap.
        if name == "front":
            us = [-5.6, -4.2, 4.2, 5.6]
        elif name == "back":
            us = [-4.5, -1.5, 1.5, 4.5]
        else:
            us = [-3.0, 0.0, 3.0]
        lows = [(u - 0.4, u + 0.4, 0.35, 0.95) for u in us]
        F.wall("ashlar", -h, h, 0.0, B, lows, depth=0.3)
        for a, b, c, e in lows:
            F.quad("dark", a, b, c, e, -0.25)
            for k in range(5):
                u = a + 0.08 + k * (b - a - 0.16) / 4
                F.box("iron", u - 0.012, u + 0.012, c, e, -0.12, -0.09)
        F.box("granite", -h - 0.06, h + 0.06, 0.0, 0.3, 0, 0.08)
        F.box("stone", -h - 0.08, h + 0.08, B - 0.15, B, 0, 0.14)
        # The main storey: brick, tall round-headed windows.
        if name == "front":
            ws = [(-5.0, 0.6), (5.0, 0.6)]
        elif name == "back":
            ws = [(-4.5, 0.55), (-1.5, 0.55), (1.5, 0.55), (4.5, 0.55)]
        else:
            ws = [(-3.0, 0.6), (0.0, 0.6), (3.0, 0.6)]
        c, e = B + 1.0, B + 5.0
        holes = [(u - hw, u + hw, c, e) for u, hw in ws]
        F.wall("brick", -h, h, B, TOP, holes, depth=0.34, reveal="stone")
        for a, b, c_, e_ in holes:
            round_window(F, a, b, c_, e_)
            # Stone aprons under the sills.
            F.box("stone", a - 0.05, b + 0.05, c_ - 0.5, c_ - 0.1, 0, 0.03)
        # A stone impost band at the springing, and corner piers.
        F.box("stone", -h - 0.02, h + 0.02, e - 0.65, e - 0.5, 0, 0.05)
        for u in (-h, h - 0.6):
            F.box("stone", u, u + 0.6, B, TOP, 0, 0.06)
    portico(M)
    m.poly("dark", [(-HW, -HD, TOP - 0.02), (HW, -HD, TOP - 0.02), (HW, HD, TOP - 0.02), (-HW, HD, TOP - 0.02)], out=-Z)


def doric(m, x, y, z0, z1):
    """A fluted-looking Doric column: a sixteen-sided shaft with entasis, an echinus and abacus."""
    zc = z1 - 0.45
    zs = [z0 + (zc - z0) * k / 4 for k in range(5)]
    rz = lambda z: CR * (1 - 0.14 * ((z - z0) / (zc - z0)) ** 1.5)  # noqa: E731
    lathe(m, "stone", [(rz(z), z) for z in zs], seg=16, c=(x, y), uv=False, smooth=False)
    m.cyl("stone", x, y, rz(zc) + 0.02, zc, zc + 0.06, seg=16, top=False)
    lathe(m, "stone", [(rz(zc) + 0.02, zc + 0.06), (CR + 0.06, zc + 0.22), (CR + 0.1, zc + 0.27)], seg=16, c=(x, y), uv=False)
    m.box("stone", (x - CR - 0.12, y - CR - 0.12, zc + 0.27), (x + CR + 0.12, y + CR + 0.12, z1))
    m.box("stone", (x - CR - 0.06, y - CR - 0.06, z0 - 0.08), (x + CR + 0.06, y + CR + 0.06, z0))


def portico(M):
    m = M.m
    a, b = PORT
    y0 = -HD - DEEP
    # The platform at the main floor's level, its stone face, the steps.
    m.box("ashlar", (a, y0, 0.0), (b, -HD, B), skip=("z0", "y1"))
    m.box("stone", (a - 0.05, y0 - 0.05, B - 0.15), (b + 0.05, -HD, B), skip=("y1",))
    m.poly("granite", [(a, y0, B + 0.001), (b, y0, B + 0.001), (b, -HD, B + 0.001), (a, -HD, B + 0.001)], out=Z)
    sw = (a - 1.2, b + 1.2)
    for i in range(STEPS):
        zz = B - (i + 1) * B / STEPS
        m.box("stone", (a + 0.4, y0 - (i + 1) * TREAD, 0.0), (b - 0.4, y0, zz + B / STEPS), skip=("z0",))
    # Cheek walls carrying the lions.
    for x0, x1 in ((a - 0.6, a + 0.4), (b - 0.4, b + 0.6)):
        m.box("ashlar", (x0, y0 - STEPS * TREAD, 0.0), (x1, y0 + 0.4, B - 0.3), skip=("z0",))
        m.box("stone", (x0 - 0.05, y0 - STEPS * TREAD - 0.05, B - 0.3), (x1 + 0.05, y0 + 0.45, B - 0.15))
        lion(m, (x0 + x1) / 2, y0 - STEPS * TREAD / 2 + 0.2, B - 0.15, 1 if x0 > 0 else -1)
    for x in COLS:
        doric(m, x, y0 + 0.5, B + 0.08, TOP)
    # Antae on the wall answering the outer columns.
    F = sides(m, W, D)["front"]
    for u in (a + 0.2, b - 0.75):
        F.box("stone", u, u + 0.55, B, TOP, 0, 0.12)
    # The doorway: bronze doors in an eared stone surround, a lunette over it.
    da, db = -0.8, 0.8
    de = B + 3.3
    F.box("stone", da - 0.3, db + 0.3, B, de + 0.3, 0, 0.1)
    F.box("stone", da - 0.4, db + 0.4, de, de + 0.3, 0, 0.12)
    F.quad("bronze", da, db, B, de, 0.11)
    for u0, u1 in ((da + 0.08, -0.04), (0.04, db - 0.08)):
        for k in range(3):
            F.box("bronze", u0, u1, B + 0.2 + k * 1.0, B + 1.0 + k * 1.0, 0.11, 0.14)
    F.box("stone", da - 0.4, db + 0.4, de + 0.3, de + 0.45, 0, 0.2)
    letters(m, "fireletter", F, 0, de + 0.75, 0.04, "FREE TO ALL", 0.2, depth=0.015, spacing=1.2)
    # Banners on iron poles, two each side of the portico.
    for u in (-6.2, 6.2):
        banner(m, F, u)
    # Two lamp standards on the platform.
    for x in (a + 0.25, b - 0.25):
        y = y0 + 0.2
        m.cyl("bronze", x, y, 0.1, B, B + 0.3, seg=10)
        m.cyl("bronze", x, y, 0.04, B + 0.3, B + 2.4, seg=8)
        m.cyl("lamp", x, y, 0.17, B + 2.4, B + 2.8, seg=10, bottom=True, r1=0.14)
        m.cyl("bronze", x, y, 0.16, B + 2.8, B + 2.88, seg=10, r1=0.02)


def banner(m, F, u):
    """A long cloth banner hanging from an iron arm, with a weighted foot rail."""
    z1, z0 = TOP - 0.6, B + 1.8
    hw = 0.42
    F.box("iron", u - 0.04, u + 0.04, z1 - 0.08, z1 + 0.04, 0, 0.6)
    F.box("iron", u - hw - 0.03, u + hw + 0.03, z1 - 0.06, z1, 0.5, 0.56)
    F.box("iron", u - hw - 0.02, u + hw + 0.02, z0, z0 + 0.04, 0.5, 0.54)
    pts = [(u - hw, z0 + 0.04), (u + hw, z0 + 0.04), (u + hw, z1 - 0.06), (u - hw, z1 - 0.06)]
    fpoly(F, "banner", pts, 0.53)
    fpoly(F, "banner", pts, 0.525, out=-F.n)
    fpoly(F, "fireletter", [(u - hw + 0.08, z1 - 0.55), (u + hw - 0.08, z1 - 0.55), (u + hw - 0.08, z1 - 0.5), (u - hw + 0.08, z1 - 0.5)], 0.535)
    fpoly(F, "fireletter", [(u - hw + 0.08, z0 + 0.4), (u + hw - 0.08, z0 + 0.4), (u + hw - 0.08, z0 + 0.45), (u - hw + 0.08, z0 + 0.45)], 0.535)
    # An open book in the middle of the banner, in gold.
    zb = (z0 + z1) / 2 + 0.3
    for s in (-1, 1):
        fpoly(F, "fireletter", [(u, zb - 0.12), (u + s * 0.25, zb - 0.06), (u + s * 0.25, zb + 0.16), (u, zb + 0.1)], 0.535, out=F.n)


def lion(m, x, y, z, side):
    """A couchant lion facing the street, about 1.5 m long on its plinth."""
    c = Vector((x, y, z))
    f = Vector((0, -1, 0))  # facing
    # The body and haunches.
    _ellipsoid(m, "stone", c + Vector((0, 0.2, 0.32)), 0.3, 0.6, 0.3, seg=12, rings=8)
    _ellipsoid(m, "stone", c + Vector((0, 0.55, 0.3)), 0.32, 0.3, 0.3, seg=12, rings=8)
    # The mane and head, raised and looking out.
    _ellipsoid(m, "stone", c + Vector((0, -0.35, 0.58)), 0.33, 0.26, 0.36, seg=12, rings=8)
    _ellipsoid(m, "stone", c + Vector((0, -0.55, 0.62)), 0.19, 0.2, 0.2, seg=10, rings=6)
    _ellipsoid(m, "stone", c + Vector((0, -0.72, 0.56)), 0.11, 0.12, 0.09, seg=8, rings=5)
    # Forelegs stretched out in front, paws.
    for dx in (-0.15, 0.15):
        _limb(m, "stone", [c + Vector((dx, -0.25, 0.3)), c + Vector((dx, -0.6, 0.1)), c + Vector((dx, -0.85, 0.07))], [0.1, 0.08, 0.07], seg=8)
        _ellipsoid(m, "stone", c + Vector((dx, -0.92, 0.06)), 0.08, 0.1, 0.06, seg=8, rings=4)
    # The tail curled round the haunch.
    s = side
    _limb(m, "stone", [c + Vector((s * 0.2, 0.8, 0.2)), c + Vector((s * 0.33, 0.55, 0.05)), c + Vector((s * 0.33, 0.1, 0.04))], [0.05, 0.045, 0.04], seg=6)
    _ellipsoid(m, "stone", c + Vector((s * 0.33, 0.05, 0.05)), 0.06, 0.08, 0.05, seg=6, rings=4)
    del f


# ---- roof -----------------------------------------------------------------------------


def roof(M):
    m = M.m
    walls = sides(m, W, D)
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.wall("stone", -h, h, TOP, TOP + ENT, [])
        F.box("stone", -h - 0.02, h + 0.02, TOP, TOP + 0.3, 0, 0.05)
        # Triglyphs along the frieze.
        for i in range(int(2 * h / 0.9)):
            u = -h + 0.45 + i * 0.9
            F.box("stone", u - 0.15, u + 0.15, TOP + 0.35, TOP + ENT - 0.25, 0, 0.03)
            for du in (-0.07, 0.07):
                F.box("dark", u + du - 0.015, u + du + 0.015, TOP + 0.4, TOP + ENT - 0.3, 0.03, 0.032)
        F.box("stone", -h - 0.06, h + 0.06, TOP + ENT - 0.2, TOP + ENT, 0, 0.4)
        # A plain parapet with a coping.
        F.box("brick", -h, h, TOP + ENT, TOP + ENT + 0.7, -0.3, 0.0, skip=())
        F.box("stone", -h - 0.05, h + 0.05, TOP + ENT + 0.7, TOP + ENT + 0.82, -0.35, 0.05)
    zr = TOP + ENT
    m.poly("roof", [(-HW + 0.3, -HD + 0.3, zr - 0.1), (HW - 0.3, -HD + 0.3, zr - 0.1), (HW - 0.3, HD - 0.3, zr - 0.1), (-HW + 0.3, HD - 0.3, zr - 0.1)], out=Z)
    pediment(m, zr)
    dome(m, zr - 0.1)


def pediment(m, zr):
    a, b = PORT
    y0 = -HD - DEEP
    pw = (b - a) + 0.2
    hw = pw / 2
    P = sides(m, pw, DEEP + 0.4, 0, y0 + (DEEP + 0.4) / 2)
    F = P["front"]
    m.box("stone", (-hw, y0, TOP), (hw, y0 + DEEP + 0.4, TOP + ENT), skip=("z0",))
    m.poly("stone", [(-hw, y0, TOP), (hw, y0, TOP), (hw, -HD, TOP), (-hw, -HD, TOP)], out=-Z)
    F.box("stone", -hw, hw, TOP, TOP + 0.3, 0, 0.04)
    F.box("stone", -hw - 0.05, hw + 0.05, TOP + ENT - 0.2, TOP + ENT, 0, 0.35)
    letters(m, "fireletter", F, 0, TOP + 0.63, 0.0, "PUBLIC LIBRARY", 0.36, depth=0.02, spacing=1.3)
    peak = zr + 1.7
    fpoly(F, "stone", [(-hw, zr), (hw, zr), (0, peak)], 0.0)
    fpoly(P["back"], "stone", [(-hw, zr), (hw, zr), (0, peak)], 0.0)
    for s in (-1, 1):
        A = (s * (hw + 0.3), zr - 0.02)
        Bp = (0, peak + 0.3)
        m.poly("stone", [F.p(A[0], A[1], 0.35), F.p(Bp[0], Bp[1], 0.35), F.p(Bp[0], Bp[1], -(DEEP + 0.4)), F.p(A[0], A[1], -(DEEP + 0.4))], out=(s * 0.7, 0, 1))
        m.poly("stone", [F.p(A[0], A[1] - 0.25, 0.35), F.p(Bp[0], Bp[1] - 0.25, 0.35), F.p(Bp[0], Bp[1], 0.35), F.p(A[0], A[1], 0.35)], out=(0, -1, 0))
        m.poly("stone", [F.p(A[0], A[1] - 0.25, 0.35), F.p(Bp[0], Bp[1] - 0.25, 0.35), F.p(Bp[0], Bp[1] - 0.25, 0.0), F.p(A[0], A[1] - 0.25, 0.0)], out=(-s * 0.3, 0, -1))
        m.poly("stone", [F.p(A[0], A[1] - 0.25, 0.35), F.p(A[0], A[1], 0.35), F.p(A[0], A[1], -(DEEP + 0.4)), F.p(A[0], A[1] - 0.25, -(DEEP + 0.4))], out=(s, 0, 0))
    # A wreathed lamp of learning in the tympanum.
    seg = 16
    fpoly(F, "stone", [(math.cos(i / seg * math.tau) * 0.45, zr + 0.7 + math.sin(i / seg * math.tau) * 0.45) for i in range(seg)], 0.05)
    fpoly(F, "bronze", [(-0.28, zr + 0.55), (0.28, zr + 0.55), (0.12, zr + 0.75), (0.0, zr + 1.0), (-0.12, zr + 0.75)], 0.07)


def dome(m, z):
    """An octagonal drum with eight windows and a shallow ribbed copper dome with a lantern."""
    R = 3.0
    H = 2.9
    cy = 0.6
    n = 8
    pts = [(math.cos((i + 0.5) / n * math.tau) * R, cy + math.sin((i + 0.5) / n * math.tau) * R) for i in range(n)]
    for i in range(n):
        p, q = Vector((*pts[i], z)), Vector((*pts[(i + 1) % n], z))
        t = (q - p).normalized()
        mid = (p + q) / 2
        S = Side(m, (mid.x, mid.y, z), t, t.cross(Z))
        L = (q - p).length / 2
        S.wall("brick", -L, L, 0.0, H, [(-0.5, 0.5, 1.1, 2.4)], depth=0.25, reveal="stone")
        wid = new_id()
        pane(S, "glass", -0.5, 0.5, 1.1, 2.4, -0.5, 0.5, 1.1, 2.4, -0.2, wid)
        S.box("frame", -0.02, 0.02, 1.1, 2.4, -0.2, -0.17)
        S.box("stone", -0.62, 0.62, 2.4, 2.55, 0, 0.05)
        S.box("stone", -0.6, 0.6, 1.02, 1.1, 0, 0.08)
        S.box("stone", -L - 0.02, L + 0.02, H - 0.25, H, 0, 0.15)
        S.box("stone", -L - 0.02, L + 0.02, 0.0, 0.2, 0, 0.06)
    zb = z + H
    prof = [(R + 0.2, zb)] + [(math.cos(t) * (R + 0.2), zb + math.sin(t) * 1.5) for t in [i / 8 * math.pi / 2 for i in range(1, 8)]] + [(0.6, zb + 1.5)]
    lathe(m, "copper", prof, seg=8, c=(0, cy), uv=False, smooth=False)
    for i in range(n):
        a = (i + 0.5) / n * math.tau
        rib = [Vector((math.cos(a) * (r + 0.05), cy + math.sin(a) * (r + 0.05), zz)) for r, zz in prof]
        for p_, q_ in zip(rib, rib[1:]):
            m.strut("copper", p_, q_, 0.09)
    lz = zb + 1.5
    for i in range(6):
        a = i / 6 * math.tau
        m.cyl("stone", math.cos(a) * 0.5, cy + math.sin(a) * 0.5, 0.06, lz, lz + 0.9, seg=6)
    m.cyl("dark", 0, cy, 0.4, lz, lz + 0.9, seg=8)
    lathe(m, "copper", [(0.7, lz + 0.9), (0.7, lz + 1.0), (0.35, lz + 1.3), (0.05, lz + 1.6)], seg=12, c=(0, cy), uv=False)
    m.cyl("brass", 0, cy, 0.08, lz + 1.6, lz + 1.8, seg=10, r1=0.02)
