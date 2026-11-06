# P2, power station: the City's coal-fired generating station of about
# 1932, the brick "cathedral" kind. On the street the turbine hall, a tall
# brick box with five great round-headed steel windows between fluted
# piers that rise past the parapet in stepped heads; POWER STATION in
# bronze over a stepped Art Deco doorway on the axis, the year on a
# stone panel above. Behind it and taller the boiler house, plain brick
# with high louvres, a coal conveyor climbing to its side, and on its
# roof the pair of chimneys: round, tapering, banded in concrete, with
# steel caps, ladders and red aircraft lights lit at night.
#
# Pieces (base at the origin):
#   body  the turbine hall's walls (to 10.5 m) and the boiler house's
#         lower walls, the doorway, the conveyor
#   roof  the turbine hall's parapet and roof, the boiler house above
#         10.5 m, the chimneys
import math

from mathutils import Vector

from civic import ladder
from lib import Model, Z, letters, new_id, pane, sides, sill
from s4_factory import arch, steel

ID = "p2"
W = 14.0
TY0, TY1 = -7.0, 0.4  # the turbine hall, y
BY0, BY1 = 0.4, 7.0  # the boiler house, y
BW = 12.0  # the boiler house's width
HT = 10.5  # turbine hall walls, the roof piece's base
HB = 15.5  # boiler house walls
WALL = 0.45
PIERS = [-7.0, -4.3, -1.6, 1.6, 4.3, 7.0]  # pier centres along the front
STACKS = [(-3.0, 4.0), (3.0, 4.0)]
SR0, SR1 = 1.15, 0.8  # stack radius at the roof, at the top
ST = 34.0  # stack top


def build(out, bake=True):
    M = Model(ID, seed=43)
    M.sharp = math.radians(40)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, HT))
    roof(M)
    M.export(out, bake)


def tall_window(M, F, a, b, c, e, D_=WALL):
    """A great steel window with a round head: small panes to the springing, a fan above."""
    half = (b - a) / 2
    spring = e - half
    steel(M, F, a, b, c, spring, D=D_)
    wid = new_id()
    pane(F, "worksglass", a, b, spring, e, a, b, spring, e, -D_ + 0.12, wid)
    mid = (a + b) / 2
    for k in range(1, 6):
        t = math.pi * k / 6
        F.m.strut("steelframe", F.p(mid, spring, -D_ + 0.14), F.p(mid - math.cos(t) * half, spring + math.sin(t) * half, -D_ + 0.14), 0.03)
    for r in (half * 0.45,):
        pts = [F.p(mid - math.cos(math.pi * k / 10) * r, spring + math.sin(math.pi * k / 10) * r, -D_ + 0.14) for k in range(11)]
        for p, q in zip(pts, pts[1:]):
            F.m.strut("steelframe", p, q, 0.03)
    arch(F, a, b, e, rise=half, ring=0.45, D=D_)
    sill(F, a, b, c, D=D_)


# ---- body -----------------------------------------------------------------------------


def body(M):
    m = M.m
    tw, td = W, TY1 - TY0
    T = sides(m, tw, td, 0, (TY0 + TY1) / 2)
    c, e = 1.6, 9.2
    for name, F in T.items():
        h = tw / 2 if name in ("front", "back") else td / 2
        m_plinth = 0.9
        if name == "front":
            holes = [((PIERS[i] + PIERS[i + 1]) / 2 - 0.85, (PIERS[i] + PIERS[i + 1]) / 2 + 0.85, c, e) for i in range(5) if i != 2]
            holes.append((-0.9, 0.9, 0.0, 3.4, WALL))
            holes.append((-1.0, 1.0, 5.2, 9.2))
        elif name == "back":
            # Against the boiler house but for a strip each end, where the hall is wider.
            for u0, u1 in ((-h, -BW / 2), (BW / 2, h)):
                F.wall("brick", u0, u1, 0.0, HT, [])
                F.box("bluebrick", u0 - (0.05 if u0 < 0 else 0), u1 + (0.05 if u1 > 0 else 0), 0.0, 0.9, 0, 0.06)
            continue
        else:
            holes = [(u - 0.9, u + 0.9, c, e) for u in (-1.9, 1.9)]
        F.wall("brick", -h, h, 0.0, HT, holes, depth=WALL, reveal="brick")
        F.box("bluebrick", -h - 0.05, h + 0.05, 0.0, m_plinth, 0, 0.06)
        F.box("stone", -h - 0.07, h + 0.07, m_plinth, m_plinth + 0.12, 0, 0.1)
        for hole in holes:
            if len(hole) == 5:
                continue
            tall_window(M, F, *hole)
        if name == "front":
            doorway(M, F)
            for u in PIERS:
                pier(F, u)
        else:
            for u in (-h + 0.35, 0.0, h - 0.35):
                pier(F, u, w=0.7 if abs(u) > 0.1 else 0.5)
    m.poly("dark", [(-W / 2, TY0, HT - 0.02), (W / 2, TY0, HT - 0.02), (W / 2, TY1, HT - 0.02), (-W / 2, TY1, HT - 0.02)], out=-Z)
    boiler_walls(M, 0.0, HT)
    conveyor(m)


def pier(F, u, w=0.9):
    """A fluted brick pier: three ribs standing proud, the full height of the wall."""
    F.box("brick", u - w / 2, u + w / 2, 0.9, HT, 0, 0.15)
    for k in (-1, 0, 1):
        F.box("brick", u + k * w / 3 - 0.08, u + k * w / 3 + 0.08, 1.0, HT, 0.15, 0.24)
    F.box("stone", u - w / 2 - 0.05, u + w / 2 + 0.05, 0.9, 1.05, 0, 0.3)


def doorway(M, F):
    """A stepped Art Deco doorway: bronze doors, a tall window over them, POWER STATION."""
    m = M.m
    a, b = -0.9, 0.9
    F.quad("bronze", a, b, 0.0, 3.4, -WALL + 0.05)
    for u0, u1 in ((a + 0.08, -0.04), (0.04, b - 0.08)):
        for k in range(4):
            F.box("bronze", u0, u1, 0.2 + k * 0.78, 0.9 + k * 0.78, -WALL + 0.05, -WALL + 0.08)
    # Stepped stone surround, three orders, up to the window's head.
    for k, d in enumerate((0.0, 0.25, 0.5)):
        F.box("stone", a - 0.3 - d, a - d, 0.0, 9.6 - k * 0.15, 0, 0.12 + 0.1 * (2 - k))
        F.box("stone", b + d, b + 0.3 + d, 0.0, 9.6 - k * 0.15, 0, 0.12 + 0.1 * (2 - k))
    F.box("stone", a - 0.8, b + 0.8, 9.6, 10.0, 0, 0.32)
    F.box("stone", a - 0.3, b + 0.3, 3.4, 5.2, 0, 0.1)
    letters(m, "bronze", F, 0, 4.55, 0.1, "POWER", 0.32, depth=0.03, spacing=1.2)
    letters(m, "bronze", F, 0, 3.95, 0.1, "STATION", 0.26, depth=0.03, spacing=1.2)
    steel(M, F, -1.0, 1.0, 5.2, 9.2, D=WALL)
    sill(F, -1.0, 1.0, 5.2, D=WALL)
    # A canopy of stepped slabs over the doors, lamps either side.
    F.box("stone", a - 0.2, b + 0.2, 3.25, 3.4, 0, 0.9)
    for u in (a - 1.2, b + 1.2):
        F.box("bronze", u - 0.15, u + 0.15, 2.4, 3.0, 0, 0.15)
        F.box("lamp", u - 0.11, u + 0.11, 2.45, 2.95, 0.15, 0.17)


def boiler_walls(M, z0, z1):
    """The boiler house from z0 to z1: plain brick, high louvres on the sides, a stone band."""
    m = M.m
    bd = BY1 - BY0
    S = sides(m, BW, bd, 0, (BY0 + BY1) / 2)
    for name, F in S.items():
        h = BW / 2 if name in ("front", "back") else bd / 2
        if name == "front" and z0 < HT:
            # Hidden behind the turbine hall below its roof.
            continue
        holes = []
        if z1 > HT and name != "front":
            holes = [(u - 0.7, u + 0.7, 11.5, 14.0) for u in ((-3.5, 0.0, 3.5) if name == "back" else (-1.8, 1.8))]
        if z1 <= HT and name == "back":
            holes = [(-1.6, 1.6, 0.0, 4.2, WALL)]
        lo = max(z0, HT) if name == "front" else z0
        F.wall("brick", -h, h, lo, z1, holes, depth=WALL, reveal="brick")
        for hole in holes:
            a, b, c, e = hole[:4]
            if len(hole) == 5:
                F.quad("corrugated", a, b, c, e, -WALL + 0.1)
                for z in (1.0, 2.0, 3.0):
                    F.box("steelframe", a, b, z - 0.04, z + 0.04, -WALL + 0.1, -WALL + 0.15)
                F.box("steelframe", a - 0.25, b + 0.25, e, e + 0.3, -0.05, 0.02)
            else:
                F.quad("subdoor", a, b, c, e, -0.25)
                F.box("stone", a - 0.08, b + 0.08, c - 0.1, c, 0, 0.08)
                F.box("stone", a - 0.08, b + 0.08, e, e + 0.15, 0, 0.05)
        if z0 < 1.0:
            F.box("bluebrick", -h - 0.05, h + 0.05, 0.0, 0.9, 0, 0.06)
        if z1 > HT:
            F.box("stone", -h - 0.05, h + 0.05, z1 - 0.6, z1 - 0.45, 0, 0.08)
            F.box("brick", -h, h, z1, z1 + 0.6, -0.3, 0, skip=())
            F.box("stone", -h - 0.05, h + 0.05, z1 + 0.6, z1 + 0.72, -0.35, 0.05)


def conveyor(m):
    """A covered coal conveyor climbing the boiler house's right side on steel trestles."""
    x = BW / 2 + 0.9
    y0, y1 = BY1 + 0.1, BY0 + 1.0
    z0, z1 = 1.5, 13.0
    a, b = Vector((x, y0, z0)), Vector((x, y1, z1))
    t = (b - a).normalized()
    s = Vector((1, 0, 0))
    up = t.cross(s).normalized() * -1
    hw, hh = 0.55, 1.2
    corners = [s * -hw, s * hw, s * hw + up * hh, s * -hw + up * hh]
    roles = ["corrugated", "corrugated", "corrugated", "corrugated"]
    for i in range(4):
        p, q = corners[i], corners[(i + 1) % 4]
        m.poly(roles[i], [a + p, a + q, b + q, b + p], out=(p + q))
    m.poly("dark", [b + c for c in corners], out=t)
    m.poly("corrugated", [a + c for c in corners], out=-t)
    for k in range(1, 4):
        p = a + (b - a) * (k / 4)
        m.box("steelframe", (x - 0.6, p.y - 0.12, 0.0), (x - 0.45, p.y + 0.12, p.z))
        m.box("steelframe", (x + 0.45, p.y - 0.12, 0.0), (x + 0.6, p.y + 0.12, p.z))
        m.box("steelframe", (x - 0.6, p.y - 0.12, p.z - 0.2), (x + 0.6, p.y + 0.12, p.z))
        m.strut("steelframe", (x - 0.52, p.y, 0.3), (x + 0.52, p.y, p.z - 0.3), 0.08)
    # The hopper at its foot.
    m.box("steelframe", (x - 0.9, y0 - 1.2, 0.0), (x + 0.9, y0 + 0.5, 0.25))
    m.cyl("corrugated", x, y0 - 0.35, 0.95, 0.25, 1.5, seg=4, r1=0.6)


# ---- roof -----------------------------------------------------------------------------


def roof(M):
    m = M.m
    tw = W
    T = sides(m, tw, TY1 - TY0, 0, (TY0 + TY1) / 2)
    # The turbine hall's parapet, a stone band, the piers' stepped heads.
    for name, F in T.items():
        if name == "back":
            continue
        h = tw / 2 if name in ("front", "back") else (TY1 - TY0) / 2
        F.box("stone", -h - 0.05, h + 0.05, HT, HT + 0.2, 0, 0.12)
        F.box("brick", -h, h, HT + 0.2, HT + 1.2, -0.35, 0, skip=())
        F.box("stone", -h - 0.05, h + 0.05, HT + 1.2, HT + 1.35, -0.4, 0.05)
        us = PIERS if name == "front" else [-h + 0.35, h - 0.35]
        for u in us:
            w = 0.9 if name == "front" else 0.7
            for k, (dz, dw) in enumerate(((2.0, 0.0), (2.6, 0.18), (3.1, 0.36))):
                F.box("brick", u - w / 2 + dw, u + w / 2 - dw, HT + 0.2, HT + dz, 0, 0.24 - k * 0.04, skip=())
            F.box("stone", u - w / 2 + 0.3, u + w / 2 - 0.3, HT + 3.1, HT + 3.25, 0, 0.18, skip=())
        if name == "front":
            F.box("stone", -1.3, 1.3, HT + 1.35, HT + 2.6, -0.3, 0.15, skip=())
            letters(m, "bronze", F, 0, HT + 1.95, 0.15, "1932", 0.42, depth=0.03, spacing=1.2)
    # A roof of felt over a shallow north-light ridge of patent glazing.
    m.poly("roof", [(-W / 2 + 0.35, TY0 + 0.35, HT + 0.3), (W / 2 - 0.35, TY0 + 0.35, HT + 0.3), (W / 2 - 0.35, TY1, HT + 0.3), (-W / 2 + 0.35, TY1, HT + 0.3)], out=Z)
    yc = (TY0 + TY1) / 2
    for s in (-1, 1):
        m.poly("skyglass", [(-W / 2 + 1.0, yc + s * 1.6, HT + 0.3), (W / 2 - 1.0, yc + s * 1.6, HT + 0.3), (W / 2 - 1.0, yc, HT + 1.4), (-W / 2 + 1.0, yc, HT + 1.4)], out=(0, s * 0.6, 1))
    for x in [-W / 2 + 1.0 + i * (W - 2.0) / 10 for i in range(11)]:
        for s in (-1, 1):
            m.strut("galv", (x, yc + s * 1.6, HT + 0.32), (x, yc, HT + 1.42), 0.05)
    for x in (-W / 2 + 1.0, W / 2 - 1.0):
        m.poly("galv", [(x, yc - 1.6, HT + 0.3), (x, yc + 1.6, HT + 0.3), (x, yc, HT + 1.4)], out=(1 if x > 0 else -1, 0, 0))
    # The boiler house above the turbine hall's roof, its own roof.
    boiler_walls(M, HT, HB)
    bd = BY1 - BY0
    m.poly("roof", [(-BW / 2 + 0.3, BY0 + 0.3, HB + 0.2), (BW / 2 - 0.3, BY0 + 0.3, HB + 0.2), (BW / 2 - 0.3, BY1 - 0.3, HB + 0.2), (-BW / 2 + 0.3, BY1 - 0.3, HB + 0.2)], out=Z)
    del bd
    for sx, sy in STACKS:
        stack(m, sx, sy, HB + 0.2)
    # A ventilator and the conveyor's head house on the boiler roof.
    m.box("corrugated", (BW / 2 - 2.0, BY0 + 0.6, HB + 0.2), (BW / 2 - 0.3, BY0 + 2.2, HB + 2.0))
    m.box("steelframe", (BW / 2 - 2.1, BY0 + 0.5, HB + 2.0), (BW / 2 - 0.2, BY0 + 2.3, HB + 2.15))


def stack(m, x, y, z0):
    """A round chimney from the boiler roof: a square base, a tapering brick shaft banded in concrete, a steel cap."""
    m.box("brick", (x - SR0 - 0.3, y - SR0 - 0.3, z0), (x + SR0 + 0.3, y + SR0 + 0.3, z0 + 2.0))
    m.box("stone", (x - SR0 - 0.4, y - SR0 - 0.4, z0 + 2.0), (x + SR0 + 0.4, y + SR0 + 0.4, z0 + 2.2))
    zb = z0 + 2.2
    r = lambda z: SR0 + (SR1 - SR0) * (z - zb) / (ST - zb)  # noqa: E731
    bands = [zb + (ST - zb) * k / 5 for k in range(1, 5)]
    zs = [zb, *bands, ST - 1.2]
    for za, zz in zip(zs, zs[1:]):
        m.cyl("brick", x, y, r(za), za, zz, seg=20, top=False, uv=True, r1=r(zz))
    for zz in bands:
        m.cyl("concrete", x, y, r(zz) + 0.06, zz - 0.2, zz + 0.2, seg=20, top=False, bottom=True)
    # The cap: a concrete band, a steel rim, the dark mouth, and the red lights.
    rr = r(ST - 1.2)
    m.cyl("concrete", x, y, rr + 0.1, ST - 1.2, ST, seg=20, top=False, bottom=True)
    m.cyl("steelframe", x, y, rr + 0.14, ST, ST + 0.12, seg=20, top=False, bottom=True)
    for i in range(20):
        a0, a1 = i / 20 * math.tau, (i + 1) / 20 * math.tau
        p = lambda a, q: (x + math.cos(a) * q, y + math.sin(a) * q, ST + 0.12)  # noqa: E731
        m.poly("steelframe", [p(a0, rr - 0.2), p(a1, rr - 0.2), p(a1, rr + 0.14), p(a0, rr + 0.14)], out=Z)
    m.poly("dark", [(x + math.cos(i / 16 * math.tau) * (rr - 0.2), y + math.sin(i / 16 * math.tau) * (rr - 0.2), ST - 0.4) for i in range(16)], out=Z)
    for k in range(4):
        a = k / 4 * math.tau + math.pi / 4
        lx, ly = x + math.cos(a) * (rr + 0.2), y + math.sin(a) * (rr + 0.2)
        m.box("redlamp", (lx - 0.1, ly - 0.1, ST - 0.7), (lx + 0.1, ly + 0.1, ST - 0.45))
    # A ladder up the street side, caged.
    ang = -math.pi / 2 + (0.5 if x < 0 else -0.5)
    d = Vector((math.cos(ang), math.sin(ang), 0))
    foot = Vector((x, y, zb)) + d * (SR0 + 0.25)
    head = Vector((x, y, ST - 0.2)) + d * (SR1 + 0.25)
    ladder(m, tuple(foot), tuple(head), role="galv", cage=True, out=tuple(d))
