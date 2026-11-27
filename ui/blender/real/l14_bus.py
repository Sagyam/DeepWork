# L14, the bus station: an art deco terminal of the 1930s on its half block
# beside the monument. A tall waiting hall of brick with limestone dressings,
# a tall bronze-framed window each side of a stone pylon over the doors; low
# wings either side with ribbons of glass that turn their rounded corners in
# glass block, three stone speed lines wrapping round them. A marquee over
# the doors carries the station's name. The pylon rises above the hall as a
# stepped tower: BUS in neon down a channel between its fins, a clock on the
# front and the back, a mast. Behind, under a cantilevered canopy, doors out
# to the buses, and across the lane an island platform under a long
# streamline canopy on a row of columns: benches, bay flags, a departures
# board.
#
# Pieces (base at the origin, stacked by the app):
#   body   the terminal to its parapets, the pylon to the hall's, the marquee,
#          the back canopy and the platform island
#   shed   the island's canopy and what stands under it
#   tower  the pylon above the hall: the BUS channel, clock stage, crown, mast
import math

from mathutils import Vector

from civic import lathe
from l5_cityhall import clock_face
from lib import Model, Side, Z, glazing, letters, neon, new_id, pane, sides

ID = "l14"
# Laid out on the site, front (Main Street) toward -y; SHIFT centres the
# footprint, marquee to the platform canopy, on the origin.
YF = -12.0  # the wings' front
HF = -12.4  # the hall's
PF = -12.8  # the pylon's
YB = -3.0  # the back of it all
MQ = -14.8  # the marquee's front
CAN_Y = (1.0, 9.0)  # the platform canopy
SHIFT = -(MQ + CAN_Y[1]) / 2
HX = 6.0  # the hall's half width
WX = 13.0  # the wings' outer ends
R = 2.0  # the wings' rounded front corners
WING = 4.9  # top of the wings' parapets
HALL = 7.6  # top of the hall's, and the tower piece's base
PX = 2.1  # the pylon's half width
PD = 3.2  # and depth
PY = PF + PD / 2  # its centre
STAGE = 12.4  # top of the tower's first stage
CLOCK = 14.2  # top of the clock stage
CROWN = 15.2
MAST = 18.4
RIB = (1.0, 2.9)  # the wings' ribbon windows
SPEED = (3.55, 3.8, 4.05)  # the speed lines
ISLE = (3.0, 7.0)  # the platform island, y
ISLE_H = 0.2
CAN_Z = 4.4  # the canopy's soffit
CAN_T = 5.0  # its top
COLS = [-9.0, -3.0, 3.0, 9.0]


def build(out, bake=True):
    M = Model(ID, seed=53)
    M.sharp = math.radians(40)
    M.piece("body")
    hall(M)
    for s in (-1, 1):
        wing(M, s)
    pylon(M)
    marquee(M)
    back(M)
    island(M)
    M.piece("shed")
    shed(M)
    M.piece("tower", (0, 0, HALL))
    tower(M)
    for mesh in (M.m, M.cut, M.decal):
        for v in mesh.bm.verts:
            v.co.y += SHIFT
    M.export(out, bake)


# ---- helpers --------------------------------------------------------------------------


def strip(F, u0, u1, z0, z1, holes, role, w0=0.0, w1=0.03):
    """A band proud of the wall from u0 to u1, broken where an opening crosses it."""
    cuts = sorted((a, b) for a, b, c, e, *_ in holes if c < z1 and e > z0)
    u = u0
    for a, b in cuts:
        if a > u + 1e-6:
            F.box(role, u, min(a, u1), z0, z1, w0, w1)
        u = max(u, b)
    if u1 > u + 1e-6:
        F.box(role, u, u1, z0, z1, w0, w1)


def arc(cx, cy, r, a0, a1, seg):
    """(point, outward normal) round an arc, angles in degrees."""
    out = []
    for i in range(seg + 1):
        a = math.radians(a0 + (a1 - a0) * i / seg)
        n = Vector((math.cos(a), math.sin(a), 0))
        out.append((Vector((cx, cy, 0)) + n * r, n))
    return out


def facets(m, pts):
    """An arc's facets as Sides (u from 0 to their length), with their lengths."""
    out = []
    for (p0, n0), (p1, n1) in zip(pts, pts[1:]):
        t = p1 - p0
        out.append((Side(m, p0, t, (n0 + n1).normalized()), t.length))
    return out


def stadium(x0, x1, y0, y1, seg=8):
    """A plan with round ends (counter-clockwise from above), as (x, y)."""
    r = (y1 - y0) / 2
    cy = (y0 + y1) / 2
    pts = [(p.x, p.y) for p, _ in arc(x1 - r, cy, r, -90, 90, seg)]
    pts += [(p.x, p.y) for p, _ in arc(x0 + r, cy, r, 90, 270, seg)]
    return pts


def parapet(m, plan, top, roof, coping="stone"):
    """A coping round a convex plan, the parapet's inner face down to a flat roof inside it."""
    m.psweep(coping, plan, [(0.0, top - 0.22), (0.07, top - 0.22), (0.07, top), (-0.32, top)])
    m.psweep("brick", plan, [(-0.32, top), (-0.32, roof)])
    inner = inset(plan, 0.32)
    m.poly("roof", [(x, y, roof) for x, y in inner], out=Z)


def inset(plan, d):
    """A convex plan moved in by d (mitred)."""
    P = [Vector(p) for p in plan]
    n = len(P)
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        t0, t1 = (b - a).normalized(), (c - b).normalized()
        n0, n1 = Vector((t0.y, -t0.x)), Vector((t1.y, -t1.x))
        bis = (n0 + n1).normalized()
        q = b - bis * (d / bis.dot(n0))
        out.append((q.x, q.y))
    return out


# ---- the waiting hall -------------------------------------------------------------------


def hall(M):
    m = M.m
    F = Side(m, (0, HF, 0), (1, 0, 0), (0, -1, 0))
    win = [(-5.4, -2.75), (2.75, 5.4)]
    c, e = 0.9, 6.3
    for (u0, u1), (a, b) in zip(((-HX, -PX), (PX, HX)), win):
        holes = [(a, b, c, e, 0.3)]
        F.wall("brick", u0, u1, 0, HALL, holes, reveal="stone")
        strip(F, u0, u1, 0, 0.5, holes, "granite", 0, 0.04)
        tall_window(F, a, b, c, e)
        # A chevron panel over the window, a stone sill under it.
        F.box("deco", a, b, e + 0.12, e + 0.75, 0, 0.03)
        F.box("stone", a - 0.12, b + 0.12, c - 0.1, c, -0.25, 0.08)
    # Stone quoin strips at the hall's corners, rising past the parapet line.
    for u in (-HX, HX - 0.35):
        F.box("stone", u, u + 0.35, 0.5, HALL - 0.22, 0, 0.05)
    # The hall's sides: the return in front of the wings, the clerestory above them.
    for s in (-1, 1):
        # u runs along +y on the right, -y on the left (seen from outside, left to right).
        S = Side(m, (s * HX, 0, 0), (0, s, 0), (s, 0, 0))
        uf, ub = sorted((s * HF, s * YB))
        S.wall("brick", uf, ub, WING - 0.3, HALL, clerestory(s))
        for a, b, cc, ee, *_ in clerestory(s):
            glazing(S, a, b, cc, ee, lights=2, D=0.18, fr="bronze", glass="doorglass")
        ret = (s * HF, s * YF)
        S.wall("brick", min(ret), max(ret), 0, WING - 0.3, [])
        S.box("granite", min(ret), max(ret), 0, 0.5, 0, 0.04)
    # Back: the doors out to the buses, a window each side.
    B = Side(m, (0, YB, 0), (-1, 0, 0), (0, 1, 0))
    holes = [(-1.6, 1.6, 0, 3.0, 0.3), (-5.2, -2.6, 1.0, 3.2, 0.22), (2.6, 5.2, 1.0, 3.2, 0.22)]
    B.wall("brick", -HX, HX, 0, HALL, holes, reveal="stone")
    strip(B, -HX, HX, 0, 0.5, holes, "granite", 0, 0.04)
    for a, b, cc, ee, _ in holes[1:]:
        glazing(B, a, b, cc, ee, lights=3, D=0.16, fr="bronze", glass="doorglass")
    doors(B, -1.6, 1.6, 0, 3.0, 0.3)
    # High on the back, the station's clock faces the platform from the tower.
    plan = [(-HX, HF), (HX, HF), (HX, YB), (-HX, YB)]
    parapet(m, plan, HALL, HALL - 0.75)


def clerestory(s):
    """The hall's high windows on a side, as holes in its wall's u."""
    us = [(-11.2, -9.4), (-8.6, -6.8), (-6.0, -4.2)]
    if s < 0:
        us = [(-b, -a) for a, b in us]
    return [(a, b, 5.3, 6.9, 0.2) for a, b in us]


def tall_window(F, a, b, c, e):
    """A tall bronze window in three lights, with transoms."""
    glazing(F, a, b, c, e, lights=3, D=0.24, fr="bronze", glass="doorglass")
    for z in (c + 1.7, c + 3.6):
        F.box("bronze", a + 0.05, b - 0.05, z - 0.04, z + 0.04, -0.27, -0.17)


def doors(F, a, b, c, e, D):
    """Two pairs of bronze-framed glass doors under a transom light."""
    wid = new_id()
    t = e - 0.6
    fr = "bronze"
    F.box(fr, a, b, t - 0.07, t, -D, -D + 0.1)
    F.box(fr, a, b, e - 0.07, e, -D, -D + 0.1)
    pane(F, "doorglass", a, b, c, e, a, b, t, e - 0.07, -D + 0.05, wid)
    n = 4
    w = (b - a) / n
    for i in range(n):
        u0, u1 = a + i * w, a + (i + 1) * w
        F.box(fr, u0, u0 + 0.08, c, t - 0.07, -D - 0.02, -D + 0.08)
        F.box(fr, u1 - 0.08, u1, c, t - 0.07, -D - 0.02, -D + 0.08)
        F.box(fr, u0 + 0.08, u1 - 0.08, c, c + 0.3, -D - 0.02, -D + 0.08)
        F.box(fr, u0 + 0.08, u1 - 0.08, t - 0.17, t - 0.07, -D - 0.02, -D + 0.08)
        pane(F, "doorglass", a, b, c, e, u0 + 0.08, u1 - 0.08, c + 0.3, t - 0.17, -D + 0.03, wid)
        hx = u1 - 0.2 if i % 2 == 0 else u0 + 0.16
        F.box("brass", hx, hx + 0.04, c + 0.9, c + 1.4, -D + 0.08, -D + 0.12)


# ---- the wings ----------------------------------------------------------------------------


def wing(M, s):
    """A low wing to one side (s = +1 right, -1 left): ribbon glass turning a rounded
    corner in glass block, speed lines round it, a door on the end."""
    m = M.m
    x_in, x_out = s * HX, s * WX
    cx, cy = x_out - s * R, YF + R
    # The front, from the hall to the corner.
    F = Side(m, (0, YF, 0), (1, 0, 0), (0, -1, 0))
    u0, u1 = sorted((x_in, cx))
    rib = (u0 + 0.6, u1 - 0.2) if s > 0 else (u0 + 0.2, u1 - 0.6)
    holes = [(*rib, *RIB, 0.18)]
    F.wall("brick", u0, u1, 0, WING, holes, reveal="stone")
    strip(F, u0, u1, 0, 0.5, holes, "granite", 0, 0.04)
    glazing(F, *rib, *RIB, lights=4, D=0.14, fr="bronze", glass="shopglass")
    F.box("stone", rib[0] - 0.1, rib[1] + 0.1, RIB[0] - 0.08, RIB[0], -0.14, 0.07)
    for z in SPEED:
        F.box("stone", u0, u1, z, z + 0.08, 0, 0.04)
    # The corner: glass block between the ribbon's sill and head.
    a0, a1 = (-90, 0) if s > 0 else (180, 270)
    pts = arc(cx, cy, R, a0, a1, 8)
    for S, L in facets(m, pts):
        S.quad("brick", 0, L, 0.5, RIB[0])
        S.quad("brick", 0, L, RIB[1], WING)
        S.box("granite", 0, L, 0, 0.5, -0.0, 0.04, skip=("back", "left", "right"))
        S.quad("glassblock", 0, L, RIB[0], RIB[1], -0.1)
        S.box("stone", 0, L, RIB[0] - 0.08, RIB[0], -0.1, 0.07, skip=("back", "left", "right"))
        S.box("stone", 0, L, RIB[1], RIB[1] + 0.06, -0.1, 0.0, skip=("back", "left", "right", "top"))
        for z in SPEED:
            S.box("stone", 0, L, z, z + 0.08, 0, 0.04, skip=("back", "left", "right"))
    # The end wall: a door with a stone surround and a small window.
    E = Side(m, (x_out, 0, 0), (0, s, 0), (s, 0, 0))
    e0, e1 = sorted((s * (YF + R), s * YB))
    door = (-7.2, -6.1) if s > 0 else (6.1, 7.2)
    win = (-5.0, -3.6) if s > 0 else (3.6, 5.0)
    holes = [(*door, 0, 2.6, 0.2), (*win, 1.2, 2.6, 0.18)]
    E.wall("brick", e0, e1, 0, WING, holes, reveal="stone")
    strip(E, e0, e1, 0, 0.5, holes, "granite", 0, 0.04)
    for z in SPEED:
        E.box("stone", e0, e1, z, z + 0.08, 0, 0.04)
    E.box("stone", door[0] - 0.25, door[1] + 0.25, 2.6, 2.95, 0, 0.1)
    E.box("stone", door[0] - 0.25, door[0], 0, 2.6, 0, 0.08)
    E.box("stone", door[1], door[1] + 0.25, 0, 2.6, 0, 0.08)
    wid = new_id()
    E.quad("door", door[0], door[1], 0, 2.6 - 0.65, -0.2)
    pane(E, "doorglass", door[0], door[1], 0, 2.6, door[0], door[1], 2.6 - 0.65, 2.6, -0.19, wid)
    E.box("brass", door[1] - 0.15, door[1] - 0.11, 0.95, 1.1, -0.2, -0.15)
    glazing(E, *win, 1.2, 2.6, lights=2, D=0.14, fr="bronze", glass="shopglass")
    E.box("lamp", (door[0] + door[1]) / 2 - 0.12, (door[0] + door[1]) / 2 + 0.12, 3.05, 3.3, 0, 0.14)
    # The back: windows onto the platform.
    B = Side(m, (0, YB, 0), (-1, 0, 0), (0, 1, 0))
    b0, b1 = sorted((-x_in, -x_out))
    ws = [(b0 + 0.9, b0 + 3.0), (b1 - 3.0, b1 - 0.9)]
    holes = [(a, b, 1.1, 3.0, 0.16) for a, b in ws]
    B.wall("brick", b0, b1, 0, WING, holes, reveal="stone")
    strip(B, b0, b1, 0, 0.5, holes, "granite", 0, 0.04)
    for a, b, c, e, _ in holes:
        glazing(B, a, b, c, e, lights=2, D=0.14, fr="bronze", glass="shopglass")
    for z in SPEED:
        B.box("stone", b0, b1, z, z + 0.08, 0, 0.04)
    # The roof: parapet round the wing, the plant on it.
    plan = [(p.x, p.y) for p, _ in pts]
    plan = ([(x_in, YF)] + plan + [(x_out, YB), (x_in, YB)]) if s > 0 else ([(x_in, YB), (x_out, YB)] + plan + [(x_in, YF)])
    parapet(m, plan, WING, WING - 0.6)
    ax = s * 9.6
    m.box("ac", (ax - 0.8, -7.4, WING - 0.6), (ax + 0.8, -6.2, WING + 0.4))
    m.box("dark", (ax - 0.6, -7.42, WING - 0.3), (ax + 0.6, -7.4, WING + 0.2))
    m.cyl("galv", s * 11.0, -5.0, 0.22, WING - 0.6, WING + 0.5, seg=10)
    m.cyl("galv", s * 11.0, -5.0, 0.3, WING + 0.5, WING + 0.6, seg=10)


# ---- the pylon and the marquee ----------------------------------------------------------


def pylon(M):
    """The pylon's lower part: the doors under the marquee, glass block above, fins either side."""
    m = M.m
    F = Side(m, (0, PF, 0), (1, 0, 0), (0, -1, 0))
    holes = [(-1.3, 1.3, 0.15, 3.3, 0.5), (-0.75, 0.75, 4.5, HALL - 0.3, 0.12)]
    F.wall("stone", -PX, PX, 0, HALL, holes)
    F.box("granite", -PX, PX, 0, 0.15, 0, 0.3)
    doors(F, -1.3, 1.3, 0.15, 3.3, 0.5)
    F.quad("glassblock", -0.75, 0.75, 4.5, HALL - 0.3, -0.12)
    fins(F, 3.6, HALL)
    # The returns back to the hall's front.
    for s in (-1, 1):
        S = Side(m, (s * PX, 0, 0), (0, -s, 0), (s, 0, 0))
        u = sorted((s * -PF, s * -HF))
        S.quad("stone", u[0], u[1], 0, HALL)
    m.poly("stone", [(-PX, PF, HALL), (PX, PF, HALL), (PX, HF, HALL), (-PX, HF, HALL)], out=Z)


def fins(F, z0, z1):
    """Three stone fins up the pylon's front: one at each edge, one either side of the channel."""
    for u, w in ((-PX + 0.18, 0.36), (PX - 0.18, 0.36), (-1.05, 0.22), (1.05, 0.22)):
        F.box("stone", u - w / 2, u + w / 2, z0, z1, 0, 0.3 if w > 0.3 else 0.2)


def marquee(M):
    """The marquee over the doors: rounded at its front corners, the name on its fascia,
    lights in its soffit, hung on two rods from the hall."""
    m = M.m
    x0, x1, y0, y1 = -5.2, 5.2, MQ, HF
    r = 1.0
    plan = [(p.x, p.y) for p, _ in arc(x1 - r, y0 + r, r, -90, 0, 5)]
    plan = [(x0, y1)] + [(p.x, p.y) for p, _ in arc(x0 + r, y0 + r, r, 180, 270, 5)] + plan + [(x1, y1)]
    z0, z1 = 3.4, 4.25
    m.psweep("stainless", plan, [(0.0, z0), (0.0, z0 + 0.08)])
    m.psweep("cream", plan, [(0.0, z0 + 0.08), (0.0, z1 - 0.08)])
    m.psweep("stainless", plan, [(0.0, z1 - 0.08), (0.0, z1), (-0.12, z1)])
    m.poly("roof", [(x, y, z1 - 0.02) for x, y in inset(plan, 0.12)], out=Z)
    m.poly("cream", [(x, y, z0) for x, y in plan], out=-Z)
    for z in (z0 + 0.2, z1 - 0.22):
        m.psweep("band", plan, [(0.0, z), (0.02, z), (0.02, z + 0.05), (0.0, z + 0.05)])
    F = Side(m, (0, MQ, 0), (1, 0, 0), (0, -1, 0))
    F.quad("busname", -4.0, 4.0, z0 + 0.28, z1 - 0.28, 0.024, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    for x in (-4.4, -2.2, 0.0, 2.2, 4.4):
        for y in (MQ + 0.6, MQ + 1.6):
            m.cyl("lamp", x, y, 0.12, z0 - 0.03, z0, seg=8, top=False, bottom=True)
    for x in (-4.2, 4.2):
        m.strut("iron", (x, HF, 6.6), (x, MQ + 0.5, z1), 0.05)
        m.box("iron", (x - 0.1, HF - 0.05, 6.5), (x + 0.1, HF, 6.7))


# ---- the back: canopy, platform island --------------------------------------------------


def back(M):
    """A canopy cantilevered off the back of the terminal, lit underneath."""
    m = M.m
    y0, y1 = YB, YB + 2.6
    z0, z1 = 3.8, 4.15
    m.box("cream", (-WX, y0, z0), (WX, y1, z1), skip=("y0",))
    m.box("band", (-WX - 0.01, y1 - 0.01, z0 + 0.12), (WX + 0.01, y1 + 0.01, z0 + 0.17), skip=("y0",))
    for x in range(-12, 13, 3):
        m.box("lamp", (x - 0.6, y0 + 1.2, z0 - 0.04), (x + 0.6, y0 + 1.4, z0))
    # A bench against the wall each side of the doors.
    for x in (-8.5, 8.5):
        bench(m, x, YB + 0.45, 0.0, 0, back_to=-1)


def bench(m, x, y, z, ry, back_to=0, L=2.0):
    """A wooden bench along x at (x, y): slats on iron ends; `back_to` +1/-1 puts its back to +y/-y."""
    for k in range(3):
        yy = y + (k - 1) * 0.15
        m.box("wood", (x - L / 2, yy - 0.06, z + 0.44), (x + L / 2, yy + 0.06, z + 0.48))
    for xx in (x - L / 2 + 0.15, x + L / 2 - 0.15):
        m.box("iron", (xx - 0.03, y - 0.24, z), (xx + 0.03, y + 0.24, z + 0.44))
    if back_to:
        yb = y + back_to * 0.24
        for k in range(2):
            m.box("wood", (x - L / 2, yb - 0.03, z + 0.6 + k * 0.17), (x + L / 2, yb + 0.03, z + 0.72 + k * 0.17))
        for xx in (x - L / 2 + 0.15, x + L / 2 - 0.15):
            m.box("iron", (xx - 0.03, yb - 0.03, z + 0.44), (xx + 0.03, yb + 0.03, z + 0.92))


def island(M):
    """The platform island between the two lanes: granite kerbs, paving, a safety line."""
    m = M.m
    plan = stadium(-WX, WX, *ISLE)
    m.psweep("granite", plan, [(0.0, 0.0), (0.0, ISLE_H), (-0.3, ISLE_H)])
    m.psweep("marking", plan, [(-0.45, ISLE_H + 0.003), (-0.6, ISLE_H + 0.003)])
    m.poly("pave", [(x, y, ISLE_H) for x, y in inset(plan, 0.3)], out=Z)


# ---- the platform canopy ------------------------------------------------------------------


def shed(M):
    m = M.m
    cy = (ISLE[0] + ISLE[1]) / 2
    plan = stadium(-WX, WX, *CAN_Y, seg=10)
    # The slab: a rounded soffit edge, the fascia with two speed lines, an upstand.
    m.psweep("cream", plan, [(-0.25, CAN_Z), (-0.08, CAN_Z + 0.03), (0.0, CAN_Z + 0.15), (0.0, CAN_T - 0.1)])
    m.psweep("stainless", plan, [(0.0, CAN_T - 0.1), (0.0, CAN_T + 0.12), (-0.2, CAN_T + 0.12), (-0.2, CAN_T)])
    for z in (CAN_Z + 0.3, CAN_Z + 0.46):
        m.psweep("band", plan, [(0.0, z), (0.02, z), (0.02, z + 0.06), (0.0, z + 0.06)])
    m.poly("cream", [(x, y, CAN_Z) for x, y in inset(plan, 0.25)], out=-Z)
    m.poly("roof", [(x, y, CAN_T) for x, y in inset(plan, 0.2)], out=Z)
    # A rooflight down the spine.
    m.box("skyglass", (-7.0, cy - 0.6, CAN_T), (7.0, cy + 0.6, CAN_T + 0.25), skip=("z0",))
    m.box("stainless", (-7.1, cy - 0.7, CAN_T), (7.1, cy + 0.7, CAN_T + 0.08), skip=("z0",))
    # Columns: tapered, round, flaring into the soffit.
    for x in COLS:
        lathe(m, "granite", [(0.42, ISLE_H), (0.42, ISLE_H + 0.35), (0.34, ISLE_H + 0.42)], seg=16, c=(x, cy), uv=False)
        lathe(m, "cream", [(0.27, ISLE_H + 0.42), (0.22, CAN_Z - 1.1), (0.26, CAN_Z - 0.6), (0.5, CAN_Z - 0.12), (0.9, CAN_Z)], seg=16, c=(x, cy), uv=False)
    # Lamps in the soffit, two lines over the platform edges.
    for y in (ISLE[0] + 0.5, ISLE[1] - 0.5):
        for x0 in (-11.0, -6.0, -1.0, 4.0, 9.0):
            m.box("lamp", (x0 - 0.0, y - 0.07, CAN_Z - 0.06), (x0 + 2.0, y + 0.07, CAN_Z))
    # The departures board, hung over the middle.
    bx = 0.0
    m.box("dark", (bx - 1.3, cy - 0.12, CAN_Z - 1.35), (bx + 1.3, cy + 0.12, CAN_Z - 0.7))
    for s in (-1, 1):
        m.box("led", (bx - 1.2, cy + s * 0.121, CAN_Z - 1.27), (bx + 1.2, cy + s * 0.125, CAN_Z - 0.78))
        m.strut("iron", (bx + s * 1.0, cy, CAN_Z - 0.7), (bx + s * 1.0, cy, CAN_Z), 0.04)
    # Benches back to back between the columns; bins by the columns.
    for x in (-6.0, 6.0, -11.0, 11.0):
        bench(m, x, cy - 0.45, ISLE_H, 0, back_to=+1, L=2.4 if abs(x) < 10 else 1.6)
        bench(m, x, cy + 0.45, ISLE_H, 0, back_to=-1, L=2.4 if abs(x) < 10 else 1.6)
    for x in COLS:
        m.cyl("iron", x + 0.75, cy, 0.22, ISLE_H, ISLE_H + 0.85, seg=10)
        m.cyl("dark", x + 0.75, cy, 0.17, ISLE_H + 0.85, ISLE_H + 0.86, seg=10)
    # Bay flags at the head of each bay, lettered.
    for (y, n), labels in (((ISLE[0] + 0.35, (0, -1, 0)), ("A", "B")), ((ISLE[1] - 0.35, (0, 1, 0)), ("C", "D"))):
        for x, label in zip((-6.8, 6.8), labels):
            flag(m, x, y, Vector(n), label)


def flag(m, x, y, n, label):
    """A bus stop flag: a post with a green plate lettered with the bay."""
    z0 = ISLE_H
    m.cyl("galv", x, y, 0.045, z0, z0 + 2.9, seg=8)
    m.box("busflag", (x - 0.32, y - 0.03, z0 + 2.15), (x + 0.32, y + 0.03, z0 + 2.95))
    for s in (1, -1):
        nn = n * s
        F = Side(m, (x, y + nn.y * 0.03, 0), (nn.y * -1, 0, 0) if nn.y > 0 else (1, 0, 0), nn)
        letters(m, "marking", F, 0, z0 + 2.62, 0, label, 0.42, depth=0.012)
        F.box("marking", -0.26, 0.26, z0 + 2.22, z0 + 2.3, 0, 0.01)


# ---- the tower ------------------------------------------------------------------------------


def tower(M):
    m = M.m
    W_ = sides(m, 2 * PX, PD, 0, PY)
    z0 = HALL
    # The first stage: stone, the fins carrying on up the front, BUS in the channel.
    for name, F in W_.items():
        if name == "front":
            F.wall("stone", -PX, PX, z0, STAGE, [(-0.8, 0.8, z0, STAGE - 0.5, 0.16)])
            fins(F, z0, STAGE - 0.35)
            F.quad("dark", -0.8, 0.8, z0, STAGE - 0.5, -0.16)
            for i, ch in enumerate("BUS"):
                zc = STAGE - 1.25 - i * 1.3
                letters(m, "cream", F, 0, zc, -0.16, ch, 1.05, depth=0.1)
                neon(m, "neon", F, 0, zc, -0.04, ch, 1.05, r=0.02, inset=0.025)
        else:
            half = PX if name == "back" else PD / 2
            F.quad("stone", -half, half, z0, STAGE)
            # Vertical grooves up the sides and back.
            for u in (-half * 0.55, 0.0, half * 0.55):
                F.box("dark", u - 0.04, u + 0.04, z0 + 0.6, STAGE - 0.6, -0.02, 0.0)
    # A chevron band at the stage's head, a stone cornice.
    m.sweep("deco", 2 * PX, PD, [(0.0, STAGE - 0.35), (0.02, STAGE - 0.35), (0.02, STAGE), (0.0, STAGE)], cy=PY)
    m.sweep("stone", 2 * PX, PD, [(0.0, STAGE), (0.12, STAGE + 0.06), (0.12, STAGE + 0.16), (-0.3, STAGE + 0.16)], cy=PY)
    # The clock stage, set back: a clock front and back, louvres on the sides.
    i1 = 0.3
    W2 = sides(m, 2 * (PX - i1), PD - 2 * i1, 0, PY)
    for name, F in W2.items():
        half = PX - i1 if name in ("front", "back") else PD / 2 - i1
        F.quad("stone", -half, half, STAGE + 0.16, CLOCK)
        if name in ("front", "back"):
            clock_face(m, F, 0.0, (STAGE + 0.16 + CLOCK) / 2, 0.0, r=0.62)
        else:
            F.box("dark", -0.5, 0.5, STAGE + 0.5, CLOCK - 0.3, -0.05, 0.0)
            for k in range(6):
                z = STAGE + 0.55 + k * 0.22
                F.box("stone", -0.5, 0.5, z, z + 0.06, -0.04, 0.03)
    m.sweep("stone", 2 * (PX - i1), PD - 2 * i1, [(0.0, CLOCK), (0.1, CLOCK + 0.05), (0.1, CLOCK + 0.14), (-0.25, CLOCK + 0.14)], cy=PY)
    # The crown: two more steps, ribbed, then the mast.
    top = CLOCK + 0.14
    for k, (i2, h) in enumerate(((0.65, 0.6), (1.0, 0.46))):
        w2, d2 = 2 * (PX - i2), PD - 2 * i2
        m.box("stone", (-w2 / 2, PY - d2 / 2, top), (w2 / 2, PY + d2 / 2, top + h), skip=("z0",))
        for F in sides(m, w2, d2, 0, PY).values():
            span = w2 / 2 if abs(F.n.y) > 0.5 else d2 / 2
            for u in (-span * 0.6, 0.0, span * 0.6):
                F.box("stone", u - 0.06, u + 0.06, top, top + h, 0, 0.06, skip=("back", "bottom"))
        top += h
    m.cyl("stainless", 0, PY, 0.12, top, top + 0.3, seg=12)
    m.cyl("stainless", 0, PY, 0.06, top + 0.3, MAST - 0.2, seg=10, r1=0.035)
    lathe(m, "stainless", [(0.0, MAST - 0.3), (0.12, MAST - 0.22), (0.14, MAST - 0.12), (0.1, MAST - 0.04), (0.0, MAST)], seg=12, c=(0, PY), uv=False)
    m.cyl("redlamp", 0, PY, 0.07, MAST - 0.02, MAST + 0.1, seg=8)
