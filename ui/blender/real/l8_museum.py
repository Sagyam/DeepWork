# L8, the museum: the city's museum of art, a Greek Revival temple of the
# 1840s on its whole block north of the Canal Quarter. On a podium of
# granite and ashlar, a giant Ionic order runs the length of the front: an
# octastyle portico on the axis up a broad flight of steps, MUSEUM OF ART
# in gilt bronze on its frieze and a pediment full of figures, then a
# colonnade of four columns along each wing in front of a blind wall hung
# with exhibition banners. The wings end in pavilions that step forward,
# each with a bronze figure in a niche and a wreath on its attic. The
# galleries are top-lit: glazed lanterns run along the wings' flat roofs,
# and the central court rises behind the pediment as an attic under a
# hipped glass roof. Plain ashlar sides; the back has two rows of sash
# windows to the offices and stores.
#
# Pieces (base at the origin, stacked by the app):
#   ground  the podium, the steps and lamps, the walls and the columns to 7 m
#   upper   the walls and columns to the capitals, the banners
#   roof    entablature, pediment and its figures, the attics, the skylights
import math

from mathutils import Vector

from civic import _ellipsoid, _limb, lathe
from l5_cityhall import baluster_run
from l7_monument import wreath
from lib import Model, Side, Z, fpoly, letters, new_id, pane, sash, sides, sill

ID = "l8"
B = 1.8  # the podium (stylobate)
G = 7.0  # where the ground piece ends
TOP = 12.0  # the tops of the capitals
ENT = 2.0  # entablature
CORN = TOP + ENT
RISE = 2.9  # the pediment
YB = 7.0  # the back wall
YW = -6.4  # the wings' wall behind the colonnade
YC = -8.4  # the central block's front wall, the doors
YP = -9.6  # the pavilions' front, and the wings' podium
YS = -13.1  # the portico's podium front
STEPS = 9
TREAD = 0.42
Y0 = YS - STEPS * TREAD  # the bottom step
CX = 10.6  # the central block's (and the portico's) half width
WX = 22.4  # the wings' ends, where the pavilions start
PX = 26.6  # the pavilions' outer walls
CR = 0.55  # the columns' radius at the foot
PCOL_Y = -12.2
PCOLS = [-9.8, -7.0, -4.2, -1.4, 1.4, 4.2, 7.0, 9.8]
WCOL_Y = -8.6
WCOLS = [12.6, 15.4, 18.2, 21.0]
FLUTES = 24
DOORS = [(-1.6, 1.6, B + 4.9), (-6.0, -4.0, B + 3.9), (4.0, 6.0, B + 3.9)]  # (u0, u1, top)
NICHE = (B + 0.9, B + 5.0)
ATTIC = 17.4  # the central court's attic
GLASS = 20.2  # the ridge of its glass roof
PAV = CORN + 1.5  # the pavilions' attics
# The footprint, bottom step to back cornice, centred on the origin.
SHIFT = -(Y0 + YB + 0.35) / 2


def build(out, bake=True):
    M = Model(ID, seed=61)
    M.sharp = math.radians(40)
    M.piece("ground")
    ground(M)
    M.piece("upper", (0, 0, G))
    upper(M)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    for mesh in (M.m, M.cut, M.decal):
        for v in mesh.bm.verts:
            v.co.y += SHIFT
    M.export(out, bake)


# ---- helpers --------------------------------------------------------------------------


def face_x(m, x, s):
    """The facade at x facing s (+1 east, -1 west); u runs along s * y."""
    return Side(m, (x, 0, 0), (0, s, 0), (s, 0, 0))


def face_y(m, y, s):
    """The facade at y facing s (-1 the front, +1 the back); u runs along -s * x."""
    return Side(m, (0, y, 0), (-s, 0, 0), (0, s, 0))


def span(s, a, b):
    """x from a to b on side s (a mirrored run), as a sorted pair."""
    return tuple(sorted((s * a, s * b)))


def radius(z):
    """The shaft's radius at z: a gentle entasis from the podium to the capitals."""
    t = max(0.0, min(1.0, (z - B) / (TOP - B)))
    return CR * (1 - 0.13 * t**1.5)


def shaft(m, x, y, z0, z1, rings=3, sub=3):
    """An Ionic shaft, fluted with fillets between the flutes."""
    depth = 0.05

    def ring(z):
        r = radius(z)
        pts = []
        for i in range(FLUTES):
            for k in range(sub):
                a = (i + k / sub) / FLUTES * math.tau
                rr = r - (0.0 if k == 0 else depth * (r / CR))
                pts.append(Vector((x + math.cos(a) * rr, y + math.sin(a) * rr, z)))
        return pts

    zs = [z0 + (z1 - z0) * j / (rings - 1) for j in range(rings)]
    rs = [ring(z) for z in zs]
    n = FLUTES * sub
    for r0, r1 in zip(rs, rs[1:]):
        for i in range(n):
            j = (i + 1) % n
            mid = (r0[i] + r0[j]) / 2
            m.poly("stone", [r0[i], r0[j], r1[j], r1[i]], out=(mid.x - x, mid.y - y, 0), smooth=True)


def column_base(m, x, y):
    """A square plinth and an Attic base: torus, scotia, torus."""
    r = CR
    m.box("stone", (x - r - 0.2, y - r - 0.2, B), (x + r + 0.2, y + r + 0.2, B + 0.2), skip=("z0",))
    lathe(m, "stone", [(r + 0.17, B + 0.2), (r + 0.2, B + 0.28), (r + 0.16, B + 0.36), (r + 0.06, B + 0.42), (r + 0.04, B + 0.48), (r + 0.1, B + 0.53), (r + 0.06, B + 0.6), (r, B + 0.64)], seg=24, c=(x, y), uv=False)


def roll(m, role, x, y, z, r, h, seg=12):
    """A volute's roll: a cylinder of radius r along y, centred at (x, y, z), 2h long, its ends closed."""
    ring = lambda yy: [Vector((x + math.cos(k / seg * math.tau) * r, yy, z + math.sin(k / seg * math.tau) * r)) for k in range(seg)]  # noqa: E731
    a, b = ring(y - h), ring(y + h)
    for k in range(seg):
        j = (k + 1) % seg
        mid = (a[k] + a[j]) / 2
        m.poly(role, [a[k], a[j], b[j], b[k]], out=(mid.x - x, 0, mid.z - z), smooth=True)
    m.poly(role, a, out=(0, -1, 0))
    m.poly(role, b, out=(0, 1, 0))


def capital(m, x, y):
    """An Ionic capital over the shaft's top at TOP - 0.75: astragal, echinus, volutes, abacus."""
    z = TOP - 0.75
    r = radius(z)
    lathe(m, "stone", [(r, z), (r + 0.05, z + 0.04), (r, z + 0.08), (r + 0.02, z + 0.2), (r + 0.12, z + 0.32), (r + 0.16, z + 0.38)], seg=24, c=(x, y), uv=False)
    # The cushion between the volutes, the rolls themselves, their eyes.
    zv = z + 0.42
    m.box("stone", (x - r - 0.05, y - r - 0.05, zv - 0.04), (x + r + 0.05, y + r + 0.05, zv + 0.2))
    for s in (-1, 1):
        cx = x + s * (r + 0.1)
        roll(m, "stone", cx, y, zv, 0.24, r + 0.06)
        for e in (-1, 1):
            yy = y + e * (r + 0.06)
            m.box("stone", (cx - 0.07, yy - 0.02, zv - 0.07), (cx + 0.07, yy + 0.02, zv + 0.07))
    # The abacus: a thin moulded square.
    a = r + 0.3
    m.box("stone", (x - a, y - a, TOP - 0.16), (x + a, y + a, TOP))
    m.box("stone", (x - a + 0.05, y - a + 0.05, TOP - 0.2), (x + a - 0.05, y + a - 0.05, TOP - 0.16))


def column(m, x, y, z0, z1):
    """A column's part from z0 to z1: the base when it starts on the podium, the capital at the top."""
    if z0 <= B:
        column_base(m, x, y)
        z0 = B + 0.64
    top = z1 >= TOP - 1e-6
    shaft(m, x, y, z0, TOP - 0.75 if top else z1)
    if top:
        capital(m, x, y)


def blind(F, holes, D):
    """The backs of shallow recesses cut by F.wall: ashlar panels set D in."""
    for a, b, c, e, *_ in holes:
        F.quad("ashlar", a, b, c, e, -D)


def pilaster(F, u, z0, z1, wd=0.36, base=True):
    F.box("stone", u - wd, u + wd, z0, z1, 0, 0.12)
    if base:
        F.box("stone", u - wd - 0.06, u + wd + 0.06, z0, z0 + 0.35, 0, 0.18)


def figure(m, role, x, y, z, h, lean=0.0, seg=6):
    """A standing draped figure h tall facing -y: the robe falling to the hem,
    a shoulder lifted when it leans, the arms by its sides, the head."""
    s = h / 1.8
    sh = Vector((x + lean * 0.4 * s, y, z + 1.42 * s))
    _limb(m, role, [(x, y, z), (x, y, z + 0.55 * s), (x + lean * 0.2 * s, y, z + 1.05 * s), sh], [0.27 * s, 0.22 * s, 0.17 * s, 0.19 * s], seg)
    _ellipsoid(m, role, (sh.x + lean * 0.05 * s, y - 0.02 * s, z + 1.62 * s), 0.1 * s, 0.11 * s, 0.13 * s, seg=seg + 2, rings=5)
    for side in (-1, 1):
        lift = 0.3 * s if side * lean > 0 else 0.0
        _limb(m, role, [(sh.x + side * 0.19 * s, y, sh.z), (sh.x + side * 0.27 * s, y - 0.06 * s, sh.z - 0.3 * s + lift), (sh.x + side * 0.24 * s, y - 0.16 * s, sh.z - 0.6 * s + 2 * lift)], [0.065 * s, 0.055 * s, 0.05 * s], 5)


def reclining(m, role, x, y, z, L, s_):
    """A figure lying along x from x, its head toward the middle (s_ the way it lies), propped on an elbow."""
    h = L / 1.8
    _limb(m, role, [(x, y, z + 0.1 * h), (x + s_ * 0.55 * h, y, z + 0.12 * h), (x + s_ * 1.1 * h, y, z + 0.16 * h), (x + s_ * 1.45 * h, y, z + 0.26 * h)], [0.09 * h, 0.13 * h, 0.17 * h, 0.14 * h], 6)
    _ellipsoid(m, role, (x + s_ * 1.6 * h, y - 0.02 * h, z + 0.4 * h), 0.1 * h, 0.11 * h, 0.11 * h, seg=8, rings=5)
    _limb(m, role, [(x + s_ * 1.45 * h, y + 0.08 * h, z + 0.28 * h), (x + s_ * 1.5 * h, y + 0.08 * h, z + 0.05 * h)], [0.05 * h, 0.05 * h], 5)


def lamp(m, x, y, z):
    """A bronze candelabrum: a fluted standard with three lanterns."""
    lathe(m, "bronze", [(0.24, z), (0.24, z + 0.1), (0.14, z + 0.3), (0.1, z + 0.9), (0.07, z + 1.0)], seg=10, c=(x, y), uv=False)
    m.cyl("bronze", x, y, 0.06, z + 1.0, z + 3.0, seg=8)
    m.cyl("lamp", x, y, 0.19, z + 3.0, z + 3.55, seg=10, bottom=True, r1=0.22)
    lathe(m, "bronze", [(0.26, z + 3.55), (0.26, z + 3.6), (0.1, z + 3.8), (0.03, z + 3.95)], seg=10, c=(x, y), uv=False)
    for s in (-1, 1):
        lx = x + s * 0.55
        m.strut("bronze", (x, y, z + 2.6), (lx, y, z + 2.75), 0.05)
        m.cyl("lamp", lx, y, 0.12, z + 2.75, z + 3.1, seg=8, bottom=True, r1=0.14)
        m.cyl("bronze", lx, y, 0.15, z + 3.1, z + 3.16, seg=8, r1=0.02)


# ---- the podium, steps and the ground storey --------------------------------------------


def ground(M):
    m = M.m
    podium(m)
    steps(m)
    walls(m, B, G)
    doors(m)
    niches(m)
    for x in PCOLS:
        column(m, x, PCOL_Y, 0, G)
    for s in (-1, 1):
        for x in WCOLS:
            column(m, s * x, WCOL_Y, 0, G)
    # The floors of the portico and colonnades: granite paving.
    m.poly("granite", [(-CX, YS + 0.1, B + 0.002), (CX, YS + 0.1, B + 0.002), (CX, YC, B + 0.002), (-CX, YC, B + 0.002)], out=Z)
    for s in (-1, 1):
        x0, x1 = span(s, CX, WX)
        m.poly("granite", [(x0, YP + 0.1, B + 0.002), (x1, YP + 0.1, B + 0.002), (x1, YW, B + 0.002), (x0, YW, B + 0.002)], out=Z)


def podium(m):
    """Ashlar with channelled joints over a granite plinth, a moulded cap at the floor."""
    m.box("ashlar", (-PX, YP, 0.0), (PX, YB, B), skip=("z0",))
    m.box("ashlar", (-CX - 0.3, YS, 0.0), (CX + 0.3, YP, B), skip=("z0", "y1"))
    fronts = [
        (face_y(m, YS, -1), -CX - 0.3, CX + 0.3),
        (face_x(m, CX + 0.3, 1), YS, YP),
        (face_x(m, -CX - 0.3, -1), -YP, -YS),
        (face_y(m, YB, 1), -PX, PX),
        (face_x(m, PX, 1), YP, YB),
        (face_x(m, -PX, -1), -YB, -YP),
    ]
    for s in (-1, 1):
        a, b = span(s, CX + 0.3, PX)
        fronts.append((face_y(m, YP, -1), a, b))
    for F, u0, u1 in fronts:
        F.box("granite", u0 - 0.04, u1 + 0.04, 0.0, 0.35, 0, 0.1)
        for k in range(3):
            z = 0.75 + k * 0.4
            F.box("dark", u0, u1, z - 0.02, z + 0.02, -0.001, 0.004)
        F.box("stone", u0 - 0.08, u1 + 0.08, B - 0.18, B, 0, 0.14)


def steps(m):
    """The flight up to the portico between granite cheek blocks, each with a candelabrum."""
    hw = CX - 0.5
    for i in range(STEPS):
        z = B - i * (B / STEPS)
        m.box("granite", (-hw, YS - (i + 1) * TREAD, 0.0), (hw, YS, z), skip=("z0",))
    for s in (-1, 1):
        x0, x1 = span(s, hw, CX + 0.3)
        m.box("ashlar", (x0, Y0, 0.0), (x1, YS, B * 0.55), skip=("z0",))
        m.box("stone", (x0 - 0.05, Y0 - 0.05, B * 0.55), (x1 + 0.05, YS, B * 0.55 + 0.14))
        m.box("granite", (x0 + 0.15, Y0 + 0.2, B * 0.55 + 0.14), (x1 - 0.15, Y0 + 1.0, B * 0.55 + 0.7))
        lamp(m, (x0 + x1) / 2, Y0 + 0.6, B * 0.55 + 0.7)


def walls(m, z0, z1):
    """Every wall from z0 to z1: the central block's front, the wings behind
    the colonnades, the pavilions, the sides and the back."""
    first = z0 <= B
    # The central block's front, behind the portico: the doors are cut by doors().
    F = face_y(m, YC, -1)
    holes = [(a, b, B, e) for a, b, e in DOORS] if first else []
    F.wall("ashlar", -CX, CX, z0, z1, holes, depth=0.6)
    for u in (-8.4, 8.4):
        pilaster(F, u, z0, z1, base=first)
    for s in (-1, 1):
        # The returns from the central block back to the wings' wall.
        R = face_x(m, s * CX, s)
        R.wall("ashlar", *sorted((s * YC, s * YW)), z0, z1, [])
        # The wings' wall: blind, a tall recessed panel in each bay.
        W_ = face_y(m, YW, -1)
        a, b = span(s, CX, WX)
        bays = [((WCOLS[i] + WCOLS[i + 1]) / 2) for i in range(len(WCOLS) - 1)]
        recess = [(*span(s, x - 0.9, x + 0.9), max(z0, B + 1.2), min(z1, TOP - 0.9), 0.15) for x in bays]
        recess = [h for h in recess if h[2] < h[3]]
        W_.wall("ashlar", a, b, z0, z1, recess, depth=0.15)
        blind(W_, recess, 0.15)
        for x in WCOLS:
            pilaster(W_, s * x, z0, z1, wd=0.42, base=first)
        # The pavilion's face to the colonnade, its front, its outer side.
        I = face_x(m, s * WX, -s)
        I.wall("ashlar", *sorted((-s * YW, -s * YP)), z0, z1, [])
        P = face_y(m, YP, -1)
        pa, pb = span(s, WX, PX)
        mid = s * (WX + PX) / 2
        niche = [(mid - 1.1, mid + 1.1, *NICHE, 0.7)] if first else []
        P.wall("ashlar", pa, pb, z0, z1, niche, depth=0.7)
        blind(P, niche, 0.7)
        for u in (pa + 0.5, pb - 0.5):
            pilaster(P, u, z0, z1, wd=0.5, base=first)
        O = face_x(m, s * PX, s)
        side_wall(O, z0, z1, first)
    back(m, z0, z1)


def side_wall(F, z0, z1, first):
    """An end wall: ashlar between pilasters, a blind panel in each bay above the ground."""
    u0, u1 = sorted((F.t.y * YP, F.t.y * YB))
    us = [u0 + 0.5 + i * (u1 - u0 - 1.0) / 4 for i in range(5)]
    panels = [(us[i] + 0.9, us[i + 1] - 0.9, max(z0, B + 6.4), min(z1, TOP - 1.0), 0.1) for i in range(4)]
    panels = [p for p in panels if p[2] < p[3]]
    F.wall("ashlar", u0, u1, z0, z1, panels, depth=0.1)
    blind(F, panels, 0.1)
    for u in us:
        pilaster(F, u, z0, z1, wd=0.4, base=first)


def back(m, z0, z1):
    """The back: thirteen bays between pilasters, a sash window in each on both floors."""
    F = face_y(m, YB, 1)
    n = 13
    us = [-PX + 0.5 + i * (2 * PX - 1.0) / n for i in range(n + 1)]
    rows = [(B + 1.3, B + 4.1), (B + 6.3, TOP - 1.4)]
    holes = []
    for i in range(n):
        mid = (us[i] + us[i + 1]) / 2
        for c, e in rows:
            if c >= z0 - 1e-6 and e <= z1 + 1e-6:
                holes.append((mid - 0.75, mid + 0.75, c, e))
    if z0 <= B:
        # A service door in the middle bay of the central block.
        holes = [h for h in holes if abs((h[0] + h[1]) / 2) > 2.0 or h[2] > B + 2] + [(-1.3, 1.3, B, B + 3.6)]
    F.wall("ashlar", -PX, PX, z0, z1, holes, depth=0.3)
    for a, b, c, e in holes:
        if c <= B + 1e-6:
            F.quad("door2", a, b, c, e, -0.3)
            F.box("door2", (a + b) / 2 - 0.02, (a + b) / 2 + 0.02, c, e, -0.3, -0.26)
            F.box("stone", a - 0.18, b + 0.18, e, e + 0.3, 0, 0.1)
            continue
        sash(F, a, b, c, e, D=0.3, lights=(2, 3), glass="decoglass")
        sill(F, a, b, c, D=0.3)
        F.box("stone", a - 0.12, b + 0.12, e, e + 0.22, 0, 0.06)
    for u in us:
        pilaster(F, u, z0, z1, wd=0.32, base=z0 <= B)


def doors(m):
    """The three doorways behind the portico: bronze doors under bronze grilles, in stone architraves."""
    F = face_y(m, YC, -1)
    for a, b, e in DOORS:
        D = 0.6
        dz = B + (e - B) * 0.68
        mid = (a + b) / 2
        F.quad("bronze", a, b, B, dz, -D)
        for u0, u1 in ((a, mid), (mid, b)):
            for k in range(3):
                z = B + 0.25 + k * (dz - B - 0.3) / 3
                F.box("bronze", u0 + 0.12, u1 - 0.12, z, z + (dz - B - 0.3) / 3 - 0.12, -D, -D + 0.04)
        F.box("bronze", mid - 0.03, mid + 0.03, B, dz, -D, -D + 0.06)
        F.box("bronze", a, b, dz, dz + 0.12, -D, -D + 0.06)
        pane(F, "decoglass", a, b, dz + 0.12, e, a, b, dz + 0.12, e, -D, new_id())
        for k in range(1, 6):
            u = a + k * (b - a) / 6
            F.box("bronze", u - 0.025, u + 0.025, dz + 0.12, e, -D + 0.01, -D + 0.05)
        # The architrave and a cornice over it on consoles.
        for u0, u1 in ((a - 0.35, a), (b, b + 0.35)):
            F.box("stone", u0, u1, B, e + 0.35, 0, 0.1)
        F.box("stone", a - 0.35, b + 0.35, e, e + 0.35, 0, 0.1)
        F.box("stone", a - 0.55, b + 0.55, e + 0.45, e + 0.7, 0, 0.35)
        for u in (a - 0.45, b + 0.45):
            F.box("stone", u - 0.1, u + 0.1, e, e + 0.45, 0, 0.3)


def niches(m):
    """A bronze figure on a pedestal in each pavilion's niche, under a shell head."""
    F = face_y(m, YP, -1)
    for s in (-1, 1):
        u = s * (WX + PX) / 2
        a, b, (c, e) = u - 1.1, u + 1.1, NICHE
        F.box("stone", a - 0.2, b + 0.2, c - 0.2, c, 0, 0.12)
        F.box("stone", a - 0.25, a, c, e + 0.25, 0, 0.1)
        F.box("stone", b, b + 0.25, c, e + 0.25, 0, 0.1)
        F.box("stone", a - 0.25, b + 0.25, e, e + 0.25, 0, 0.1)
        # The pedestal, the figure, a fan of stone ribs in the head.
        y = YP + 0.3
        m.box("stone", (u - 0.45, y - 0.3, c), (u + 0.45, y + 0.3, c + 0.8))
        figure(m, "statuary", u, y, c + 0.8, 2.7, lean=0.6 * s, seg=7)
        for k in range(7):
            ang = math.pi * (k + 0.5) / 7
            p0 = F.p(u, e - 0.6, -0.62)
            p1 = F.p(u + math.cos(ang) * 0.95, e - 0.6 + math.sin(ang) * 0.55, -0.6)
            m.strut("stone", p0, p1, 0.08, 0.06)


# ---- the upper storey ------------------------------------------------------------------


def upper(M):
    m = M.m
    walls(m, G, TOP)
    for x in PCOLS:
        column(m, x, PCOL_Y, G, TOP)
    for s in (-1, 1):
        for x in WCOLS:
            column(m, s * x, WCOL_Y, G, TOP)
        # Exhibition banners in the wings' bays, red and blue by turns.
        W_ = face_y(m, YW, -1)
        for i in range(len(WCOLS) - 1):
            x = s * (WCOLS[i] + WCOLS[i + 1]) / 2
            banner(m, W_, x, "banner" if (i + (s > 0)) % 2 else "banner2")


def banner(m, F, u, role):
    """A tall cloth banner on an iron arm, a weighted rail at its foot, a white band at its head."""
    z1, z0 = TOP - 1.2, B + 2.0
    hw = 0.7
    w = 0.32
    F.box("iron", u - 0.04, u + 0.04, z1 - 0.08, z1 + 0.04, 0, w + 0.08)
    F.box("iron", u - hw - 0.04, u + hw + 0.04, z1 - 0.06, z1, w, w + 0.06)
    F.box("iron", u - hw - 0.03, u + hw + 0.03, z0, z0 + 0.05, w, w + 0.05)
    F.quad(role, u - hw, u + hw, z0 + 0.05, z1 - 0.06, w + 0.03)
    F.quad(role, u - hw, u + hw, z0 + 0.05, z1 - 0.06, w + 0.025, out=-F.n)
    F.quad("paint", u - hw, u + hw, z1 - 1.1, z1 - 0.7, w + 0.035)
    F.quad("paint", u - hw + 0.15, u + hw - 0.15, z0 + 1.0, z0 + 1.12, w + 0.035)


# ---- entablature, pediment, attics, skylights -------------------------------------------


def entablature(m, x0, x1, y0, y1, faces):
    """An Ionic entablature from TOP to CORN over a rectangle: a three-fascia
    architrave, a frieze, a dentilled cornice; `faces` names the sides that
    show ("front", "right", "back", "left")."""
    W, D = x1 - x0, y1 - y0
    m.box("stone", (x0, y0, TOP), (x1, y1, CORN - 0.6))
    S = sides(m, W, D, (x0 + x1) / 2, (y0 + y1) / 2)
    for name in faces:
        F = S[name]
        h = W / 2 if name in ("front", "back") else D / 2
        for k, (za, zb) in enumerate(((TOP, TOP + 0.22), (TOP + 0.22, TOP + 0.46), (TOP + 0.46, TOP + 0.72))):
            F.box("stone", -h, h, za, zb, 0, 0.02 + k * 0.025)
        F.box("stone", -h - 0.02, h + 0.02, TOP + 0.72, TOP + 0.8, 0, 0.1)
        n = int(2 * h / 0.32)
        for i in range(n):
            u = -h + (i + 0.5) * 2 * h / n
            F.box("stone", u - 0.08, u + 0.08, CORN - 0.6, CORN - 0.45, 0.02, 0.16)
    m.sweep("stone", W, D, [(0.0, CORN - 0.6), (0.18, CORN - 0.45), (0.22, CORN - 0.42), (0.5, CORN - 0.25), (0.55, CORN - 0.18), (0.55, CORN - 0.1), (0.48, CORN), (0.0, CORN)], (x0 + x1) / 2, (y0 + y1) / 2)
    m.poly("lead", [(x0, y0, CORN - 0.01), (x1, y0, CORN - 0.01), (x1, y1, CORN - 0.01), (x0, y1, CORN - 0.01)], out=Z)


def roof(M):
    m = M.m
    pf = PCOL_Y - 0.62  # the portico entablature's front, over the columns' necks
    ef = WCOL_Y - 0.62  # the wings'
    entablature(m, -CX, CX, pf, YC, ["front", "right", "left"])
    for s in (-1, 1):
        x0, x1 = span(s, CX, WX)
        entablature(m, x0, x1, ef, YB, ["front", "back"])
        x0, x1 = span(s, WX, PX)
        entablature(m, x0, x1, YP, YB, ["front", "right" if s > 0 else "left", "back"])
    entablature(m, -CX, CX, YC, YB, ["back"])
    # MUSEUM OF ART on the portico's frieze.
    F = face_y(m, pf, -1)
    letters(m, "fireletter", F, 0, TOP + 1.1, 0.0, "MUSEUM OF ART", 0.5, depth=0.03, spacing=1.45)
    soffits(m, pf)
    pediment(m, pf)
    attic(m)
    for s in (-1, 1):
        lantern(m, s)
        pavilion(m, s)
        # A blocking course along the wings' front over the cornice.
        x0, x1 = span(s, CX, WX)
        m.box("stone", (x0, ef + 0.3, CORN), (x1, ef + 0.75, CORN + 0.55))


def soffits(m, pf):
    """Coffers in the portico's and colonnades' ceilings, seen from below."""
    nx, ny = 7, 3
    for i in range(nx):
        for j in range(ny):
            cx = -CX + 0.8 + (i + 0.5) * (2 * CX - 1.6) / nx
            cy = pf + 0.5 + (j + 0.5) * (YC - pf - 1.0) / ny
            m.box("dark", (cx - 0.6, cy - 0.45, TOP - 0.001), (cx + 0.6, cy + 0.45, TOP), skip=("z1",))
    for s in (-1, 1):
        for i in range(len(WCOLS) - 1):
            cx = s * (WCOLS[i] + WCOLS[i + 1]) / 2
            m.box("dark", (cx - 0.9, YP + 1.0 - 0.45, TOP - 0.001), (cx + 0.9, YW - 0.6, TOP), skip=("z1",))


def pediment(m, pf):
    """The portico's pediment: tympanum, raking cornices, the figures and acroteria."""
    hw = CX
    F = face_y(m, pf + 0.35, -1)
    Bk = face_y(m, YC + 0.6, 1)
    peak = CORN + RISE
    fpoly(F, "ashlar", [(-hw + 0.4, CORN), (hw - 0.4, CORN), (0, peak - 0.25)], 0.0)
    fpoly(Bk, "stone", [(-hw, CORN), (hw, CORN), (0, peak)], 0.0)
    # The roof slopes, the raking cornice's soffit and its face.
    front, back_ = pf - 0.4, YC + 0.6
    for s in (-1, 1):
        A = Vector((s * (hw + 0.55), front, CORN - 0.05))
        Bp = Vector((0, front, peak + 0.15))
        A1 = Vector((s * (hw + 0.55), back_, CORN - 0.05))
        B1 = Vector((0, back_, peak + 0.15))
        m.poly("lead", [A, Bp, B1, A1], out=(s * 0.25, 0, 1))
        dn = Vector((0, 0, -0.42))
        m.poly("stone", [A + dn, Bp + dn, Bp, A], out=(0, -1, 0))
        deep = Vector((0, pf + 0.35 - front, 0))  # back to the tympanum
        m.poly("stone", [A + dn, Bp + dn, Bp + dn + deep, A + dn + deep], out=(s * -0.2, 0, -1))
        # The tympanum's sloping sides meet the cornice.
        fpoly(F, "stone", [(s * (hw - 0.4), CORN), (s * hw, CORN), (0, peak), (0, peak - 0.25)], 0.0)
    # The figures: a tall figure of the arts in the middle, standing
    # figures either side lessening to the corners, reclining ones in them.
    y = pf + 0.15
    figure(m, "stone", 0, y, CORN, 2.35, seg=7)
    for s in (-1, 1):
        for x, lean in ((1.7, 0.4), (3.4, 0.0), (5.0, -0.5)):
            h = (RISE - 0.25) * (1 - (x + 0.35) / (hw - 0.4)) - 0.1
            figure(m, "stone", s * x, y, CORN, h, lean=s * lean)
        reclining(m, "stone", s * (hw - 1.1), y, CORN, 2.4, -s)
    # Acroteria: a palmette at the apex, blocks with urns at the corners.
    fpoly(F, "stone", [(-0.5, peak + 0.15), (0.5, peak + 0.15), (0.35, peak + 0.9), (0, peak + 1.3), (-0.35, peak + 0.9)], 0.45)
    for k in range(5):
        a = math.pi * (k + 1) / 6
        m.strut("stone", F.p(0, peak + 0.4, 0.5), F.p(math.cos(a) * 0.75, peak + 0.4 + math.sin(a) * 0.9, 0.5), 0.1, 0.06)
    for s in (-1, 1):
        x = s * (hw + 0.2)
        m.box("stone", (x - 0.45, front + 0.1, CORN), (x + 0.45, front + 1.0, CORN + 0.5))
        lathe(m, "stone", [(0.22, CORN + 0.5), (0.3, CORN + 0.7), (0.34, CORN + 1.0), (0.2, CORN + 1.2), (0.26, CORN + 1.3), (0.08, CORN + 1.45)], seg=12, c=(x, front + 0.55), uv=False)


def attic(m):
    """The central court rising behind the pediment: an attic of ashlar with pilaster strips under a hipped glass roof."""
    x0, x1, y0, y1 = -CX + 0.4, CX - 0.4, YC + 0.8, YB - 0.4
    W, D = x1 - x0, y1 - y0
    S = sides(m, W, D, 0, (y0 + y1) / 2, CORN)
    for name, F in S.items():
        h = W / 2 if name in ("front", "back") else D / 2
        F.wall("ashlar", -h, h, 0.0, ATTIC - CORN, [])
        n = max(2, int(2 * h / 3.2))
        for i in range(n + 1):
            F.box("stone", -h + i * 2 * h / n - 0.3, -h + i * 2 * h / n + 0.3, 0.0, ATTIC - CORN, 0, 0.08)
    m.sweep("stone", W, D, [(0.0, ATTIC - 0.5), (0.1, ATTIC - 0.4), (0.3, ATTIC - 0.15), (0.3, ATTIC), (0.0, ATTIC)], 0, (y0 + y1) / 2)
    # The glass roof: four slopes to a ridge, iron bars over them.
    inset = 0.3
    ax0, ax1, ay0, ay1 = x0 + inset, x1 - inset, y0 + inset, y1 - inset
    rise = GLASS - ATTIC
    half_d = (ay1 - ay0) / 2
    cy = (ay0 + ay1) / 2
    r0, r1 = ax0 + half_d, ax1 - half_d  # the ridge's ends
    m.poly("roof", [(ax0, ay0, ATTIC), (ax1, ay0, ATTIC), (ax1, ay1, ATTIC), (ax0, ay1, ATTIC)], out=Z)
    slopes = [
        ([(ax0, ay0, ATTIC), (ax1, ay0, ATTIC), (r1, cy, GLASS), (r0, cy, GLASS)], (0, -1, 1)),
        ([(ax1, ay1, ATTIC), (ax0, ay1, ATTIC), (r0, cy, GLASS), (r1, cy, GLASS)], (0, 1, 1)),
        ([(ax1, ay0, ATTIC), (ax1, ay1, ATTIC), (r1, cy, GLASS)], (1, 0, 1)),
        ([(ax0, ay1, ATTIC), (ax0, ay0, ATTIC), (r0, cy, GLASS)], (-1, 0, 1)),
    ]
    for pts, out in slopes:
        m.poly("skyglass", [Vector(p) + Vector(out).normalized() * 0.01 for p in pts], out=out)
    n = int((ax1 - ax0) / 1.2)
    for i in range(1, n):
        x = ax0 + i * (ax1 - ax0) / n
        # Up the slope to the ridge, or in the hips' reach to the hip.
        t = min(1.0, (x - ax0) / (r0 - ax0), (ax1 - x) / (ax1 - r1))
        for yy in (ay0, ay1):
            m.strut("iron", (x, yy, ATTIC + 0.03), (x, yy + (cy - yy) * t, ATTIC + rise * t + 0.03), 0.06, 0.08)
    for e, xr in ((ax0, r0), (ax1, r1)):
        for k in range(1, 5):
            yy = ay0 + k * (ay1 - ay0) / 5
            t = 1 - abs(yy - cy) / half_d
            m.strut("iron", (e, yy, ATTIC + 0.03), (e + (xr - e) * t, yy, ATTIC + rise * t + 0.03), 0.06, 0.08)
    m.strut("iron", (r0, cy, GLASS + 0.04), (r1, cy, GLASS + 0.04), 0.14, 0.12)
    for a, b in (((ax0, ay0), (r0, cy)), ((ax1, ay0), (r1, cy)), ((ax0, ay1), (r0, cy)), ((ax1, ay1), (r1, cy))):
        m.strut("iron", (*a, ATTIC + 0.04), (*b, GLASS + 0.04), 0.12, 0.1)


def lantern(m, s):
    """A wing gallery's skylight: a glazed ridge on a low upstand along the roof."""
    x0, x1 = span(s, CX + 1.4, WX - 1.4)
    y0, y1 = -4.6, 5.0
    up = CORN + 0.45
    m.box("lead", (x0, y0, CORN), (x1, y1, up), skip=("z0",))
    rid = up + 1.6
    cy = (y0 + y1) / 2
    for ya, out in ((y0, (0, -1, 1.2)), (y1, (0, 1, 1.2))):
        m.poly("skyglass", [(x0 + 0.1, ya, up + 0.01), (x1 - 0.1, ya, up + 0.01), (x1 - 0.1, cy, rid), (x0 + 0.1, cy, rid)], out=out)
    for x in (x0 + 0.1, x1 - 0.1):
        m.poly("lead", [(x, y0, up), (x, y1, up), (x, cy, rid)], out=(1 if x > (x0 + x1) / 2 else -1, 0, 0))
    n = int((x1 - x0) / 1.1)
    for i in range(n + 1):
        x = x0 + 0.1 + i * (x1 - x0 - 0.2) / n
        for ya in (y0, y1):
            m.strut("iron", (x, ya, up + 0.02), (x, cy, rid + 0.02), 0.05, 0.07)
    m.strut("lead", (x0 + 0.05, cy, rid + 0.04), (x1 - 0.05, cy, rid + 0.04), 0.16, 0.12)


def pavilion(m, s):
    """A pavilion's attic over its cornice: a panel with a bronze wreath to the front, a cornice, a balustrade on top."""
    x0, x1 = span(s, WX + 0.25, PX - 0.25)
    y0, y1 = YP + 0.25, YB - 0.25
    W, D = x1 - x0, y1 - y0
    S = sides(m, W, D, (x0 + x1) / 2, (y0 + y1) / 2, CORN)
    for name, F in S.items():
        h = W / 2 if name in ("front", "back") else D / 2
        F.wall("ashlar", -h, h, 0.0, PAV - CORN, [])
        F.box("stone", -h, h, 0.0, 0.25, 0, 0.1)
    F = S["front"]
    F.box("stone", -1.4, 1.4, 0.3, PAV - CORN - 0.3, 0, 0.06)
    wreath(m, F, 0, (PAV - CORN) / 2, 0.42, 0.06)
    m.sweep("stone", W, D, [(0.0, PAV - 0.3), (0.12, PAV - 0.2), (0.25, PAV - 0.08), (0.25, PAV), (0.0, PAV)], (x0 + x1) / 2, (y0 + y1) / 2)
    m.poly("lead", [(x0, y0, PAV - 0.01), (x1, y0, PAV - 0.01), (x1, y1, PAV - 0.01), (x0, y1, PAV - 0.01)], out=Z)
    baluster_run(m, (x0 + 0.3, y0 + 0.3), (x1 - 0.3, y0 + 0.3), PAV, h=0.8, step=0.3)
