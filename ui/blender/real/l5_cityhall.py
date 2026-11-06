# L5, city hall: the council's seat, a Beaux-Arts civic building of about
# 1910 at lot size until the master plan reserves its half block. Limestone
# ashlar over a rusticated podium; a giant-order portico of four columns
# on the axis carrying an entablature lettered CITY HALL and a pediment, up
# a broad flight of steps between plinths with bronze lamps. Each side of
# the portico, two bays of tall windows between pilasters: pedimented on
# the main floor, eared above. A balustrade round the flat roof, and on
# the axis a clock tower: a square stage with a clock on each face, an
# open colonnaded drum, a copper dome, a lantern and a flagpole.
#
# Pieces (base at the origin, stacked by the app):
#   ground  6.2 m: the podium and the main floor, the steps, the columns' lower half
#   floor   4.4 m: the upper floor, the columns' upper half
#   roof    entablature, pediment, balustrade, the clock tower and dome
import math

from mathutils import Vector

from civic import lathe
from lib import Model, Z, fpoly, hood, letters, new_id, pane, sash, sides, sill

ID = "l5"
W, D = 14.4, 10.0
HW, HD = W / 2, D / 2
P = 1.4  # the podium
G = 4.8  # the main floor (above the podium)
FL = 4.4
TOP = P + G + FL
PORT = (-4.2, 4.2)  # the portico, x
DEEP = 2.2  # how far it stands out
STEPS = 5
TREAD = 0.32
# The steps reach 1.6 m out before the portico: the whole model moves back
# by SHIFT so its footprint, steps to back cornice, is centred on the origin.
SHIFT = ((HD + DEEP + STEPS * TREAD) - (HD + 0.45)) / 2
COLS = [-3.3, -1.1, 1.1, 3.3]
CR = 0.38  # column radius
WIN = [-5.55, 5.55]  # the window bays either side of the portico (front)
ENT = 1.05  # entablature height
TW = 4.0  # clock stage width


def build(out, bake=True):
    M = Model(ID, seed=29)
    M.sharp = math.radians(40)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, P + G))
    upper(M)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    for mesh in (M.m, M.cut, M.decal):
        for v in mesh.bm.verts:
            v.co.y += SHIFT
    M.export(out, bake)


# ---- helpers --------------------------------------------------------------------------


def column(m, x, y, z0, z1, base=False, cap=False):
    """A shaft from z0 to z1 with a slight entasis; an Attic base and an Ionic-ish capital."""
    if base:
        m.box("stone", (x - CR - 0.12, y - CR - 0.12, z0), (x + CR + 0.12, y + CR + 0.12, z0 + 0.12))
        lathe(m, "stone", [(CR + 0.1, z0 + 0.12), (CR + 0.1, z0 + 0.2), (CR + 0.03, z0 + 0.26), (CR + 0.06, z0 + 0.32), (CR, z0 + 0.38)], seg=16, c=(x, y), uv=False)
        z0 += 0.38
    if cap:
        z1 -= 0.55
    # Entasis over the whole shaft (P to TOP), so the two pieces meet without a step.
    rz = lambda z: CR * (1 - 0.1 * max(0.0, (z - P) / (TOP - P)) ** 1.6)  # noqa: E731
    zs = [z0 + (z1 - z0) * k / 4 for k in range(5)]
    lathe(m, "stone", [(rz(z), z) for z in zs], seg=16, c=(x, y), uv=False)
    if cap:
        lathe(m, "stone", [(CR * 0.9, z1), (CR * 0.95, z1 + 0.08), (CR * 1.05, z1 + 0.16), (CR * 0.92, z1 + 0.2)], seg=16, c=(x, y), uv=False)
        # Volutes as rolled boxes front and back, the abacus over them.
        for s in (-1, 1):
            m.cyl("stone", x + s * (CR + 0.08), y, 0.12, z1 + 0.12, z1 + 0.13, seg=10, bottom=True)
            m.strut("stone", (x + s * (CR + 0.08), y - CR - 0.05, z1 + 0.28), (x + s * (CR + 0.08), y + CR + 0.05, z1 + 0.28), 0.24)
        m.box("stone", (x - CR - 0.2, y - CR - 0.2, z1 + 0.4), (x + CR + 0.2, y + CR + 0.2, z1 + 0.55))
        m.box("stone", (x - CR - 0.08, y - CR - 0.08, z1 + 0.2), (x + CR + 0.08, y + CR + 0.08, z1 + 0.4))


def baluster_run(m, a, b, z, h=0.95, step=0.28):
    """A balustrade from a to b (x, y): plinth, turned balusters, a moulded rail; dies at the ends."""
    a, b = Vector((*a, z)), Vector((*b, z))
    L = (b - a).length
    t = (b - a) / L
    n = Vector((-t.y, t.x, 0))
    def bar(u0, u1, z0, z1, w):
        p0 = a + t * u0 - n * w + Z * z0
        p1 = a + t * u1 + n * w + Z * z1
        m.box("stone", tuple(min(p0[i], p1[i]) for i in range(3)), tuple(max(p0[i], p1[i]) for i in range(3)))
    bar(0, L, 0, 0.18, 0.2)
    bar(0, L, h - 0.14, h, 0.2)
    bar(-0.02, L + 0.02, h, h + 0.04, 0.23)
    for u in (0.2, L - 0.2):
        bar(u - 0.2, u + 0.2, 0.18, h - 0.14, 0.22)
    k = int((L - 0.6) / step)
    for i in range(k):
        u = 0.4 + (i + 0.5) * (L - 0.8) / k
        c = a + t * u
        lathe(m, "stone", [(0.07, z + 0.18), (0.09, z + 0.3), (0.06, z + 0.45), (0.04, z + 0.6), (0.07, z + h - 0.14)], seg=6, c=(c.x, c.y), uv=False)


def clock_face(m, F, u, z, w, r=0.8):
    """A clock dial on facade F: a stone surround, a white face, hour marks and two hands at ten past ten."""
    seg = 24
    fpoly(F, "stone", [(u + math.cos(i / seg * math.tau) * (r + 0.15), z + math.sin(i / seg * math.tau) * (r + 0.15)) for i in range(seg)], w)
    fpoly(F, "clock", [(u + math.cos(i / seg * math.tau) * r, z + math.sin(i / seg * math.tau) * r) for i in range(seg)], w + 0.02)
    for i in range(12):
        a = i / 12 * math.tau
        c, s = math.cos(a), math.sin(a)
        F.box("iron", u + c * (r - 0.14) - 0.025, u + c * (r - 0.14) + 0.025, z + s * (r - 0.14) - 0.025, z + s * (r - 0.14) + 0.025, w + 0.02, w + 0.03)
    for ang, L, t in ((math.radians(90 - 300), r * 0.5, 0.05), (math.radians(90 - 60), r * 0.75, 0.035)):
        p0 = F.p(u, z, w + 0.035)
        p1 = F.p(u + math.cos(ang) * L, z + math.sin(ang) * L, w + 0.035)
        m.strut("iron", p0, p1, t, 0.01)


# ---- the podium and main floor --------------------------------------------------------


def ground(M):
    m = M.m
    walls = sides(m, W, D)
    # The podium: rusticated, a plinth course and a cap; small windows.
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.wall("ashlar", -h, h, 0.0, P, [], depth=0.2)
        for i in range(3):
            F.box("ashlar", -h, h, 0.15 + i * 0.42, 0.17 + i * 0.42, 0, 0.02)
        F.box("granite", -h - 0.05, h + 0.05, 0.0, 0.25, 0, 0.08)
        F.box("stone", -h - 0.08, h + 0.08, P - 0.12, P, 0, 0.14)
    # The main floor: the windows on all four sides.
    c, e = P + 0.9, P + G - 1.1
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        us = WIN if name == "front" else ([-4.4, -1.5, 1.5, 4.4] if name == "back" else [-3.6, 0.0, 3.6])
        holes = [(u - 0.6, u + 0.6, c, e) for u in us]
        F.wall("stone", -h, h, P, P + G, holes, depth=0.35)
        for a, b, c_, e_ in holes:
            sash(F, a, b, c_, e_, D=0.35, lights=(2, 3), glass="decoglass")
            sill(F, a, b, c_, D=0.35)
            hood(F, a, b, e_ + 0.05)
            F.box("stone", a - 0.12, b + 0.12, c_ - 0.45, c_ - 0.08, 0, 0.04)
        pilasters(F, h, P, P + G, name)
        F.box("stone", -h - 0.04, h + 0.04, P + G - 0.25, P + G, 0, 0.1)
    portico(M, 0, P + G)
    m.poly("dark", [(-HW, -HD, P + G - 0.02), (HW, -HD, P + G - 0.02), (HW, HD, P + G - 0.02), (-HW, HD, P + G - 0.02)], out=-Z)


def pilasters(F, h, z0, z1, name):
    us = [-h + 0.35, h - 0.35]
    if name == "front":
        us += [PORT[0] - 0.35, PORT[1] + 0.35]
    for u in us:
        F.box("stone", u - 0.3, u + 0.3, z0, z1, 0, 0.1)


def portico(M, z0, z1):
    """The portico from z0 to z1: in the ground piece its floor, steps and doors, the columns' lower part."""
    m = M.m
    a, b = PORT
    y0 = -HD - DEEP
    if z0 == 0:
        # The platform at podium height, and the steps down to the forecourt.
        m.box("ashlar", (a - 0.3, y0, 0.0), (b + 0.3, -HD, P), skip=("z0", "y1"))
        m.box("stone", (a - 0.35, y0 - 0.05, P - 0.12), (b + 0.35, -HD, P), skip=("y1",))
        n = STEPS
        for i in range(n):
            zz = P - (i + 1) * P / n
            m.box("stone", (a + 0.3, y0 - (i + 1) * TREAD, 0.0), (b - 0.3, y0, zz + P / n), skip=("z0",))
        for x in (a + 0.05, b - 0.55):
            m.box("ashlar", (x, y0 - n * TREAD, 0.0), (x + 0.5, y0, P * 0.6), skip=("z0",))
            m.box("stone", (x - 0.04, y0 - n * TREAD - 0.04, P * 0.6), (x + 0.54, y0 + 0.04, P * 0.6 + 0.12))
            px, py = x + 0.25, y0 - n * TREAD + 0.4
            m.cyl("bronze", px, py, 0.12, P * 0.6 + 0.12, P * 0.6 + 0.4, seg=10)
            m.cyl("bronze", px, py, 0.05, P * 0.6 + 0.4, P * 0.6 + 2.2, seg=8)
            m.cyl("lamp", px, py, 0.18, P * 0.6 + 2.2, P * 0.6 + 2.65, seg=10, bottom=True, r1=0.15)
            m.cyl("bronze", px, py, 0.17, P * 0.6 + 2.65, P * 0.6 + 2.75, seg=10, r1=0.03)
        # The doors in the wall behind the columns: three, bronze, under fanlights.
        F = sides(m, W, D)["front"]
        for u in (-2.2, 0.0, 2.2):
            da, db, de = u - 0.7, u + 0.7, P + 3.2
            F.quad("bronze", da, db, P, de, 0.01)
            for k in range(3):
                F.box("bronze", da + 0.08, db - 0.08, P + 0.2 + k * 1.0, P + 1.0 + k * 1.0, 0.01, 0.04)
            F.box("bronze", u - 0.02, u + 0.02, P, de, 0.01, 0.05)
            wid = new_id()
            pane(F, "decoglass", da, db, de + 0.1, de + 1.0, da + 0.08, db - 0.08, de + 0.15, de + 0.95, 0.02, wid)
            F.box("stone", da - 0.2, db + 0.2, de, de + 0.1, 0, 0.12)
            F.box("stone", da - 0.2, db + 0.2, de + 1.0, de + 1.3, 0, 0.12)
            for x_ in (da - 0.2, db):
                F.box("stone", x_, x_ + 0.2, P, de + 1.3, 0, 0.12)
        # Coffered portico ceiling is in the roof piece; the floor here is paving.
        m.poly("granite", [(a - 0.3, y0, P + 0.001), (b + 0.3, y0, P + 0.001), (b + 0.3, -HD, P + 0.001), (a - 0.3, -HD, P + 0.001)], out=Z)
    for x in COLS:
        for yy in (y0 + 0.6,):
            column(m, x, yy, max(z0, P), z1, base=z0 == 0, cap=z1 >= TOP - 0.01)
    # Pilasters on the wall answering the columns.
    F = sides(m, W, D)["front"]
    for x in (a + 0.3, b - 0.3):
        F.box("stone", x - 0.35, x + 0.35, max(z0, P), z1, 0, 0.12)


# ---- the upper floor ------------------------------------------------------------------


def upper(M):
    m = M.m
    z = P + G
    walls = sides(m, W, D)
    c, e = z + 0.75, z + FL - 0.8
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        us = WIN if name == "front" else ([-4.4, -1.5, 1.5, 4.4] if name == "back" else [-3.6, 0.0, 3.6])
        holes = [(u - 0.55, u + 0.55, c, e) for u in us]
        if name == "front":
            holes += [(u - 0.5, u + 0.5, c, e) for u in (-2.2, 0.0, 2.2)]
        F.wall("stone", -h, h, z, z + FL, holes, depth=0.35)
        for a, b, c_, e_ in holes:
            sash(F, a, b, c_, e_, D=0.35, lights=(2, 2), glass="decoglass")
            sill(F, a, b, c_, D=0.35)
            # Eared architraves.
            F.box("stone", a - 0.14, b + 0.14, e_, e_ + 0.14, 0, 0.05)
            for u in (a - 0.14, b):
                F.box("stone", u, u + 0.14, c_, e_ + 0.14, 0, 0.05)
            F.box("stone", a - 0.24, a - 0.14, e_ - 0.2, e_ + 0.14, 0, 0.05)
            F.box("stone", b + 0.14, b + 0.24, e_ - 0.2, e_ + 0.14, 0, 0.05)
        pilasters(F, h, z, z + FL, name)
    portico(M, z, TOP)
    m.poly("dark", [(-HW, -HD, TOP - 0.02), (HW, -HD, TOP - 0.02), (HW, HD, TOP - 0.02), (-HW, HD, TOP - 0.02)], out=-Z)


# ---- entablature, roof and the clock tower ---------------------------------------------


def roof(M):
    m = M.m
    walls = sides(m, W, D)
    # Entablature round the main block: architrave, frieze, a modillioned cornice.
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.wall("stone", -h, h, TOP, TOP + ENT, [])
        F.box("stone", -h - 0.02, h + 0.02, TOP, TOP + 0.35, 0, 0.06)
        F.box("stone", -h - 0.05, h + 0.05, TOP + ENT - 0.3, TOP + ENT - 0.18, 0, 0.18)
        F.box("stone", -h - 0.05, h + 0.05, TOP + ENT - 0.18, TOP + ENT, 0, 0.45)
        for i in range(int(2 * h / 0.6)):
            u = -h + 0.3 + i * 0.6
            F.box("stone", u - 0.08, u + 0.08, TOP + ENT - 0.3, TOP + ENT - 0.18, 0.18, 0.4)
    zr = TOP + ENT
    m.poly("roof", [(-HW + 0.2, -HD + 0.2, zr - 0.2), (HW - 0.2, -HD + 0.2, zr - 0.2), (HW - 0.2, HD - 0.2, zr - 0.2), (-HW + 0.2, HD - 0.2, zr - 0.2)], out=Z)
    # The balustrade round the roof, broken by the portico's pediment at the front.
    a, b = PORT
    runs = [((-HW + 0.1, -HD + 0.1), (a, -HD + 0.1)), ((b, -HD + 0.1), (HW - 0.1, -HD + 0.1)), ((HW - 0.1, -HD + 0.1), (HW - 0.1, HD - 0.1)),
            ((HW - 0.1, HD - 0.1), (-HW + 0.1, HD - 0.1)), ((-HW + 0.1, HD - 0.1), (-HW + 0.1, -HD + 0.1))]
    for p, q in runs:
        baluster_run(m, p, q, zr)
    # The portico's entablature and pediment.
    y0 = -HD - DEEP
    pw = (b - a) + 0.4
    Pf = sides(m, pw, DEEP + 0.3, 0, y0 + (DEEP + 0.3) / 2)
    F = Pf["front"]
    hw = pw / 2
    m.box("stone", (-hw, y0, TOP), (hw, y0 + DEEP + 0.3, TOP + ENT), skip=("z0",))
    m.poly("stone", [(-hw, y0, TOP), (hw, y0, TOP), (hw, -HD, TOP), (-hw, -HD, TOP)], out=-Z)
    # Coffers on the portico ceiling.
    for i in range(4):
        for j in range(2):
            cx = -hw + 0.6 + i * (pw - 1.2) / 3
            cy = y0 + 0.7 + j * 1.0
            m.box("dark", (cx - 0.35, cy - 0.3, TOP - 0.001), (cx + 0.35, cy + 0.3, TOP), skip=("z1",))
    F.box("stone", -hw, hw, TOP + ENT - 0.18, TOP + ENT, 0, 0.3)
    F.box("stone", -hw, hw, TOP, TOP + 0.35, 0, 0.04)
    letters(m, "fireletter", F, 0, TOP + 0.58, 0.0, "CITY HALL", 0.42, depth=0.025, spacing=1.35)
    peak = zr + 2.0
    fpoly(F, "stone", [(-hw, zr), (hw, zr), (0, peak)], 0.0)
    fpoly(Pf["back"], "stone", [(-hw, zr), (hw, zr), (0, peak)], 0.0)
    for s in (-1, 1):
        A = (s * (hw + 0.3), zr - 0.02)
        B = (0, peak + 0.3)
        m.poly("stone", [F.p(A[0], A[1], 0.3), F.p(B[0], B[1], 0.3), F.p(B[0], B[1], -(DEEP + 0.3)), F.p(A[0], A[1], -(DEEP + 0.3))], out=(s * 0.7, 0, 1))
        m.poly("stone", [F.p(A[0], A[1] - 0.25, 0.3), F.p(B[0], B[1] - 0.25, 0.3), F.p(B[0], B[1], 0.3), F.p(A[0], A[1], 0.3)], out=(0, -1, 0))
    # A roundel with the city's arms in the tympanum: a bronze shield.
    seg = 16
    fpoly(F, "stone", [(math.cos(i / seg * math.tau) * 0.55, zr + 0.85 + math.sin(i / seg * math.tau) * 0.55) for i in range(seg)], 0.05)
    fpoly(F, "bronze", [(-0.25, zr + 1.15), (0.25, zr + 1.15), (0.25, zr + 0.85), (0.0, zr + 0.5), (-0.25, zr + 0.85)], 0.07)
    tower(m, zr)


def tower(m, zr):
    """The clock tower on the axis: a stage with four clocks, an open drum of columns, a dome, a lantern."""
    cy = 0.6
    z0 = zr - 0.2
    stage = z0 + 3.6
    T = sides(m, TW, TW, 0, cy, z0)
    for name, F in T.items():
        F.wall("stone", -TW / 2, TW / 2, 0.0, stage - z0, [])
        for u in (-TW / 2 + 0.25, TW / 2 - 0.25):
            F.box("stone", u - 0.25, u + 0.25, 0.0, stage - z0, 0, 0.1)
        F.box("stone", -TW / 2 - 0.1, TW / 2 + 0.1, stage - z0 - 0.3, stage - z0, 0, 0.2)
        clock_face(m, F, 0.0, 1.9, 0.1)
    m.box("stone", (-TW / 2 - 0.1, cy - TW / 2 - 0.1, stage), (TW / 2 + 0.1, cy + TW / 2 + 0.1, stage + 0.12))
    # The drum: a ring of eight columns round a dark core, an entablature.
    R = 1.55
    dz0, dz1 = stage + 0.12, stage + 2.7
    lathe(m, "dark", [(R - 0.5, dz0), (R - 0.5, dz1)], seg=16, c=(0, cy), uv=False)
    for i in range(8):
        a = i / 8 * math.tau
        x, y = math.cos(a) * R, cy + math.sin(a) * R
        m.cyl("stone", x, y, 0.13, dz0, dz1, seg=10)
        m.box("stone", (x - 0.18, y - 0.18, dz1 - 0.18), (x + 0.18, y + 0.18, dz1))
    lathe(m, "stone", [(R + 0.25, dz1), (R + 0.25, dz1 + 0.45), (R + 0.35, dz1 + 0.5), (R + 0.35, dz1 + 0.6), (0.0, dz1 + 0.6)], seg=24, c=(0, cy), uv=False)
    # The copper dome, ribbed, the lantern and a flagpole.
    db = dz1 + 0.6
    prof = [(R + 0.1, db)] + [(math.cos(t) * (R + 0.1), db + math.sin(t) * 1.9) for t in [i / 10 * math.pi / 2 for i in range(1, 10)]] + [(0.35, db + 1.9)]
    lathe(m, "copper", prof, seg=24, c=(0, cy), uv=False)
    for i in range(8):
        a = i / 8 * math.tau
        pts = [Vector((math.cos(a) * (r + 0.03), cy + math.sin(a) * (r + 0.03), z)) for r, z in prof]
        for p_, q_ in zip(pts, pts[1:]):
            m.strut("copper", p_, q_, 0.07)
    lz = db + 1.9
    for i in range(6):
        a = i / 6 * math.tau
        m.cyl("stone", math.cos(a) * 0.32, cy + math.sin(a) * 0.32, 0.05, lz, lz + 0.9, seg=6)
    m.cyl("dark", 0, cy, 0.22, lz, lz + 0.9, seg=8)
    lathe(m, "copper", [(0.45, lz + 0.9), (0.45, lz + 1.0), (0.25, lz + 1.3), (0.06, lz + 1.5)], seg=12, c=(0, cy), uv=False)
    m.cyl("brass", 0, cy, 0.1, lz + 1.5, lz + 1.65, seg=10)
    m.cyl("paint", 0, cy, 0.04, lz + 1.65, lz + 5.0, seg=8, r1=0.025)
