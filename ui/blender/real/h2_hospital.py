# H2, hospital: the City's general hospital of about 1968. A deep podium
# of one tall storey (outpatients, casualty, the theatres) carries a slab
# of wards: bands of aluminium windows between white precast spandrels,
# blue-grey panels under each window, a glazed stair tower at one end and
# a solid service core at the other. On the street the main entrance, a
# glass screen under a canopy lettered HOSPITAL; on the right the
# emergency department behind its own deep canopy on round columns, with
# EMERGENCY in red letters lit at night and a pair of wide doors. On the
# slab's roof: the helipad, a steel deck on legs with the white ring, the
# yellow H, edge lights and a safety net, a windsock; beside it the lift
# motor room and plant, and a blue H sign over the front, lit.
#
# Pieces (base at the origin, stacked by the app):
#   ground  the podium (4.8 m) with its roof, canopies and entrances
#   ward    one ward storey of the slab (3.5 m), repeated
#   roof    the slab's roof: parapet, helipad, plant, sign
import math

from civic import _limb
from lib import Model, Z, glazing, letters, new_id, pane, sides

ID = "h2"
W, D = 14.0, 12.0  # the podium
HW, HD = W / 2, D / 2
PH = 4.8
SW, SD = 13.0, 7.6  # the slab
SY = 1.4  # the slab's centre, y (set back from the front)
FLH = 3.5
STAIR = (-SW / 2 - 1.6, -SW / 2)  # the glazed stair tower, x
EM = (2.2, HW)  # the emergency department's front, x
CAN = 3.0  # the emergency canopy's reach in front of the podium


def build(out, bake=True):
    M = Model(ID, seed=41)
    M.sharp = math.radians(40)
    M.piece("ground")
    podium(M)
    M.piece("ward", (0, 0, PH))
    ward(M, PH)
    M.piece("roof", (0, 0, PH + FLH))
    roof(M, PH + FLH)
    # Centre the footprint (the stair tower left, the emergency canopy in front).
    for mesh in (M.m, M.cut, M.decal):
        for v in mesh.bm.verts:
            v.co.x += 0.35
            v.co.y += CAN / 2
    M.export(out, bake)


# ---- the podium -----------------------------------------------------------------------


def podium(M):
    m = M.m
    walls = sides(m, W, D)
    c, e = 1.0, 3.4
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.box("concrete", -h - 0.02, h + 0.02, 0.0, 0.35, 0, 0.04)
        if name == "front":
            holes = [(-HW + 0.6, -3.2, c, e), (-2.4, 0.6, 0.2, 3.6, 0.6), (EM[0] + 0.6, EM[0] + 3.6, 0.2, 3.0, 0.3)]
            F.wall("precast", -h, h, 0.0, PH, holes, depth=0.2)
            glazing(F, -HW + 0.6, -3.2, c, e, lights=3, D=0.15)
            entrance(m, F)
            em_doors(F, EM[0] + 0.6, EM[0] + 3.6)
            # A long fascia band over the ground storey.
            F.box("hosppanel", -h, h, PH - 0.9, PH - 0.2, 0, 0.05)
        else:
            us = [(-h + 0.8 + i * 2.6, -h + 0.8 + i * 2.6 + 1.9) for i in range(int((2 * h - 1.0) / 2.6))]
            holes = [(a, b, c, e) for a, b in us]
            F.wall("precast", -h, h, 0.0, PH, holes, depth=0.2)
            for a, b, c_, e_ in holes:
                glazing(F, a, b, c_, e_, lights=2, D=0.15, glass="frosted" if name == "back" else "glass")
            F.box("hosppanel", -h, h, PH - 0.9, PH - 0.2, 0, 0.05)
    # The podium's roof round the slab: felt, a parapet, rooflights.
    z = PH
    m.poly("roof", [(-HW, -HD, z), (HW, -HD, z), (HW, HD, z), (-HW, HD, z)], out=Z)
    m.poly("dark", [(-HW, -HD, z - 0.02), (HW, -HD, z - 0.02), (HW, HD, z - 0.02), (-HW, HD, z - 0.02)], out=-Z)
    m.sweep("precast", W, D, [(0.0, z), (0.0, z + 0.6), (-0.25, z + 0.6), (-0.25, z)])
    m.sweep("alu", W, D, [(0.02, z + 0.6), (0.02, z + 0.65), (-0.27, z + 0.65)])
    for x in (-5.5, 4.0):
        m.box("concrete", (x - 0.8, -HD + 0.8, z), (x + 0.8, -HD + 2.2, z + 0.35))
        m.poly("skyglass", [(x - 0.7, -HD + 0.9, z + 0.6), (x + 0.7, -HD + 0.9, z + 0.6), (x + 0.7, -HD + 2.1, z + 0.36), (x - 0.7, -HD + 2.1, z + 0.36)], out=(0, -0.4, 1))
    canopies(M)
    # The stair tower's foot, from the ground (it runs up beside the slab).
    stair(m, 0.0, PH, ground_=True)


def entrance(m, F):
    """The main doors: a recessed glass screen with two pairs of sliding doors."""
    a, b = -2.4, 0.6
    y = -HD
    m.box("granite", (a, y, 0.0), (b, y + 0.6, 0.2), skip=("z0",))
    S = sides(m, b - a, 1.2, (a + b) / 2, y + 1.2)["front"]
    wid = new_id()
    half = (b - a) / 2
    S.box("alu", -half, half, 2.6, 2.7, -0.05, 0.05)
    pane(S, "doorglass", -half, half, 0.2, 3.6, -half + 0.05, half - 0.05, 2.7, 3.55, 0.0, wid)
    for u0, u1 in ((-half, 0.0), (0.0, half)):
        S.box("alu", u0, u0 + 0.06, 0.2, 3.6, -0.05, 0.05)
        S.box("alu", u1 - 0.06, u1, 0.2, 3.6, -0.05, 0.05)
        pane(S, "doorglass", -half, half, 0.2, 3.6, u0 + 0.06, u1 - 0.06, 0.25, 2.6, 0.0, wid)
        mid = (u0 + u1) / 2
        S.box("alu", mid - 0.03, mid + 0.03, 0.2, 2.6, -0.03, 0.03)


def em_doors(F, a, b):
    """The emergency department's wide doors: two big sliding leaves, a red band over them."""
    wid = new_id()
    mid = (a + b) / 2
    for u0, u1 in ((a, mid), (mid, b)):
        F.box("alu", u0, u0 + 0.07, 0.2, 3.0, -0.3, -0.2)
        F.box("alu", u1 - 0.07, u1, 0.2, 3.0, -0.3, -0.2)
        F.box("alu", u0, u1, 2.9, 3.0, -0.3, -0.2)
        pane(F, "doorglass", a, b, 0.2, 3.0, u0 + 0.07, u1 - 0.07, 0.25, 2.9, -0.25, wid)
    F.box("redpanel", a - 0.3, b + 0.3, 3.05, 3.35, 0, 0.06)


def canopies(M):
    m = M.m
    # The main entrance canopy: a thin slab out from the fascia, HOSPITAL on its edge.
    a, b = -3.0, 1.2
    y0 = -HD - 2.4
    z = 3.75
    m.box("paint", (a, y0, z), (b, -HD, z + 0.25))
    m.poly("panel", [(a, y0, z - 0.001), (b, y0, z - 0.001), (b, -HD, z - 0.001), (a, -HD, z - 0.001)], out=-Z)
    for x in (a + 0.3, b - 0.3):
        m.cyl("alu", x, y0 + 0.4, 0.09, 0.0, z, seg=12)
    F = sides(m, b - a, 2.4, (a + b) / 2, y0 + 1.2, z)["front"]
    letters(m, "hospname", F, 0, 0.125, 0.0, "HOSPITAL", 0.17, depth=0.015, spacing=1.3)
    for x in (a + 0.9, (a + b) / 2, b - 0.9):
        m.box("lamp", (x - 0.15, y0 + 1.0, z - 0.03), (x + 0.15, y0 + 1.3, z), skip=("z1",))
    # The emergency canopy: deep, on round columns, the drive under it; EMERGENCY in red.
    x0, x1 = EM[0] - 0.3, HW + 0.4
    y0 = -HD - CAN
    z = 4.1
    m.box("paint", (x0, y0, z), (x1, -HD, z + 0.55))
    m.poly("panel", [(x0, y0, z - 0.001), (x1, y0, z - 0.001), (x1, -HD, z - 0.001), (x0, -HD, z - 0.001)], out=-Z)
    m.box("roof", (x0 + 0.1, y0 + 0.1, z + 0.55), (x1 - 0.1, -HD, z + 0.56), skip=("z0",))
    for x in (x0 + 0.4, x1 - 0.4):
        m.cyl("paint", x, y0 + 0.45, 0.2, 0.0, z, seg=16)
        m.cyl("concrete", x, y0 + 0.45, 0.3, 0.0, 0.45, seg=16)
    F = sides(m, x1 - x0, CAN, (x0 + x1) / 2, y0 + CAN / 2, z)["front"]
    letters(m, "redlamp", F, 0, 0.27, 0.0, "EMERGENCY", 0.3, depth=0.03, spacing=1.15)
    for x in (x0 + 1.4, (x0 + x1) / 2, x1 - 1.4):
        for y in (y0 + 0.9, y0 + 2.2):
            m.box("lamp", (x - 0.2, y - 0.2, z - 0.03), (x + 0.2, y + 0.2, z), skip=("z1",))
    # Bollards along the drive's edge.
    for x in (x0 + 1.0, x0 + 2.0):
        m.cyl("danger", x, -HD - 0.4, 0.09, 0.0, 0.9, seg=10)


# ---- the ward slab --------------------------------------------------------------------


def stair(m, z0, z1, ground_=False):
    """The glazed stair tower against the slab's left end: a glass box between concrete fins."""
    a, b = STAIR
    y0, y1 = SY - 1.6, SY + 1.6
    if ground_:
        # Down to the ground, through the podium's roof it rises from.
        y0, y1 = SY - 1.6, SY + 1.6
    S = sides(m, b - a, y1 - y0, (a + b) / 2, (y0 + y1) / 2, z0)
    for name, F in S.items():
        if name == "right":
            continue
        h = (b - a) / 2 if name in ("front", "back") else (y1 - y0) / 2
        if name == "left":
            wid = glazing(F, -h + 0.2, h - 0.2, 0.0, z1 - z0, lights=3, D=0.1, glass="stairglass")
            for u in (-h, h - 0.2):
                F.box("precast", u, u + 0.2, 0.0, z1 - z0, -0.1, 0.1)
            del wid
        else:
            F.wall("precast", -h, h, 0.0, z1 - z0, [])
    m.poly("dark", [(a, y0, z1 - 0.02), (b, y0, z1 - 0.02), (b, y1, z1 - 0.02), (a, y1, z1 - 0.02)], out=-Z)


def ward(M, z):
    m = M.m
    x0, x1 = -SW / 2, SW / 2
    y0, y1 = SY - SD / 2, SY + SD / 2
    S = sides(m, SW, SD, 0, SY, z)
    for name, F in S.items():
        h = SW / 2 if name in ("front", "back") else SD / 2
        if name in ("front", "back"):
            # A band of windows the slab's length, a precast spandrel band, coloured panels.
            c, e = 1.0, 2.75
            F.wall("precast", -h, h, 0.0, FLH, [(-h + 0.5, h - 0.5, c, e)], depth=0.18)
            n = 8
            step = (2 * h - 1.0) / n
            for i in range(n):
                a = -h + 0.5 + i * step
                glazing(F, a, a + step, c, e, lights=2, D=0.14, glass="glass")
                F.box("hosppanel", a + 0.08, a + step - 0.08, 0.15, c - 0.1, 0, 0.03)
            # Projecting fins between the window groups.
            for i in range(n + 1):
                u = -h + 0.5 + i * step
                F.box("precast", u - 0.06, u + 0.06, 0.0, FLH, 0, 0.35)
            F.box("precast", -h - 0.05, h + 0.05, FLH - 0.15, FLH, 0, 0.12)
        elif name == "right":
            # The service core's blank end: board-marked concrete, a slit of glass.
            F.wall("concrete", -h, h, 0.0, FLH, [(-0.25, 0.25, 0.3, 3.2)], depth=0.15)
            wid = new_id()
            pane(F, "frosted", -0.25, 0.25, 0.3, 3.2, -0.25, 0.25, 0.3, 3.2, -0.12, wid)
            F.box("concrete", -h - 0.05, h + 0.05, FLH - 0.15, FLH, 0, 0.1)
        else:
            F.wall("precast", -h, h, 0.0, FLH, [])
    stair(m, z, z + FLH)
    m.poly("dark", [(x0, y0, z + FLH - 0.02), (x1, y0, z + FLH - 0.02), (x1, y1, z + FLH - 0.02), (x0, y1, z + FLH - 0.02)], out=-Z)
    m.poly("dark", [(x0, y0, z + 0.02), (x1, y0, z + 0.02), (x1, y1, z + 0.02), (x0, y1, z + 0.02)], out=Z)


# ---- the roof and helipad -------------------------------------------------------------


def roof(M, z):
    m = M.m
    x0, x1 = -SW / 2, SW / 2
    y0, y1 = SY - SD / 2, SY + SD / 2
    m.poly("roof", [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], out=Z)
    m.sweep("precast", SW, SD, [(0.05, z), (0.05, z + 0.9), (-0.2, z + 0.9), (-0.2, z)], 0, SY)
    m.sweep("alu", SW, SD, [(0.07, z + 0.9), (0.07, z + 0.95), (-0.22, z + 0.95)], 0, SY)
    # The stair tower's roof.
    a, b = STAIR
    m.box("precast", (a - 0.05, SY - 1.65, z), (b, SY + 1.65, z + 0.6))
    # Lift motor room and plant at the right-hand end.
    m.box("concrete", (3.2, y0 + 1.0, z), (6.0, y1 - 1.6, z + 2.6))
    m.box("concrete", (3.1, y0 + 0.9, z + 2.6), (6.1, y1 - 1.5, z + 2.75))
    F = sides(m, 2.8, SD - 2.6, 4.6, SY - 0.3, z)["front"]
    F.quad("door", -0.4, 0.4, 0.0, 2.1, 0.005)
    for x in (4.0, 5.2):
        F2 = sides(m, 1.0, 1.0, x, y1 - 0.9, z)
        m.box("ac", (x - 0.5, y1 - 1.4, z), (x + 0.5, y1 - 0.4, z + 1.1))
        m.cyl("dark", x, y1 - 0.9, 0.38, z + 1.1, z + 1.12, seg=16)
        del F2
    for x in (2.5, 6.4):
        m.cyl("galv", x, y0 + 0.6, 0.12, z, z + 1.6, seg=10)
        m.cyl("galv", x, y0 + 0.6, 0.2, z + 1.6, z + 1.65, seg=10, r1=0.05)
    helipad(m, z)
    sign(m, z)


def helipad(m, z):
    """A square steel deck on legs, 7.8 m across: the ring, the H, edge lights, a net; the windsock."""
    cx, cy = -2.5, SY
    s = 3.9
    dz = z + 1.1
    for x in (cx - s + 0.5, cx, cx + s - 0.5):
        for y in (cy - s + 0.5, cy + s - 0.5):
            m.box("steelframe", (x - 0.12, y - 0.12, z), (x + 0.12, y + 0.12, dz - 0.25))
    m.box("steelframe", (cx - s, cy - s, dz - 0.3), (cx + s, cy + s, dz - 0.05))
    m.box("helideck", (cx - s, cy - s, dz - 0.05), (cx + s, cy + s, dz), skip=("z0",))
    # The touchdown ring and the H.
    dz += 0.004
    seg = 40
    for i in range(seg):
        a0, a1 = i / seg * math.tau, (i + 1) / seg * math.tau
        r0, r1 = 2.6, 2.95
        p = lambda a, r: (cx + math.cos(a) * r, cy + math.sin(a) * r, dz)  # noqa: E731
        m.poly("marking", [p(a0, r0), p(a1, r0), p(a1, r1), p(a0, r1)], out=Z)
    for lo, hi in (((-0.95, -1.3), (-0.55, 1.3)), ((0.55, -1.3), (0.95, 1.3)), ((-0.55, -0.2), (0.55, 0.2))):
        m.poly("danger", [(cx + lo[0], cy + lo[1], dz), (cx + hi[0], cy + lo[1], dz), (cx + hi[0], cy + hi[1], dz), (cx + lo[0], cy + hi[1], dz)], out=Z)
    # A white edge line round the deck.
    for lo, hi in (((-s + 0.1, -s + 0.1), (s - 0.1, -s + 0.3)), ((-s + 0.1, s - 0.3), (s - 0.1, s - 0.1)),
                   ((-s + 0.1, -s + 0.3), (-s + 0.3, s - 0.3)), ((s - 0.3, -s + 0.3), (s - 0.1, s - 0.3))):
        m.poly("marking", [(cx + lo[0], cy + lo[1], dz), (cx + hi[0], cy + lo[1], dz), (cx + hi[0], cy + hi[1], dz), (cx + lo[0], cy + hi[1], dz)], out=Z)
    dz -= 0.004
    # Edge lights and the safety net: a tilted mesh on brackets all round.
    for i in range(8):
        t = (i + 0.5) / 8
        for x, y in ((cx - s + 2 * s * t, cy - s), (cx - s + 2 * s * t, cy + s), (cx - s, cy - s + 2 * s * t), (cx + s, cy - s + 2 * s * t)):
            m.cyl("helilight", x, y, 0.06, dz, dz + 0.12, seg=8)
    for (ax, ay), (bx, by), (ox, oy) in ((((-s, -s), (s, -s), (0, -1))), (((s, -s), (s, s), (1, 0))), (((s, s), (-s, s), (0, 1))), (((-s, s), (-s, -s), (-1, 0)))):
        p0 = (cx + ax, cy + ay, dz - 0.1)
        p1 = (cx + bx, cy + by, dz - 0.1)
        q0 = (cx + ax + ox * 1.4, cy + ay + oy * 1.4, dz + 0.05)
        q1 = (cx + bx + ox * 1.4, cy + by + oy * 1.4, dz + 0.05)
        m.poly("net", [p0, p1, q1, q0], out=(0, 0, 1))
        m.poly("net", [p0, p1, q1, q0], out=(0, 0, -1))
        m.strut("galv", q0, q1, 0.04)
        for k in range(5):
            t = k / 4
            pa = tuple(p0[i] + (p1[i] - p0[i]) * t for i in range(3))
            qa = tuple(q0[i] + (q1[i] - q0[i]) * t for i in range(3))
            m.strut("galv", pa, qa, 0.04)
    # Steps up to the deck from the roof, at the back.
    for i in range(4):
        m.box("galv", (cx + s - 1.6, cy + s + 0.05 + i * 0.0, z + i * 0.27), (cx + s - 0.6, cy + s + 1.0 - i * 0.24, z + (i + 1) * 0.27))
    # The windsock on a mast at the deck's corner.
    wx, wy = cx - s - 0.6, cy + s - 0.3
    m.cyl("galv", wx, wy, 0.05, z, z + 4.2, seg=8)
    top = z + 4.1
    _limb(m, "windsock", [(wx + 0.06, wy, top), (wx + 0.5, wy + 0.05, top - 0.1), (wx + 0.95, wy + 0.1, top - 0.25), (wx + 1.35, wy + 0.12, top - 0.45)], [0.2, 0.17, 0.14, 0.11], seg=10)
    m.tube("galv", [(wx + 0.06, wy + 0.2 * math.cos(t), top + 0.2 * math.sin(t)) for t in [i / 10 * math.tau for i in range(10)]], 0.015, (1, 0, 0))


def sign(m, z):
    """A blue H sign at the front edge of the slab's roof, lit at night."""
    x = 4.6
    y = SY - SD / 2 + 0.3
    for dx in (-0.8, 0.8):
        m.box("steelframe", (x + dx - 0.05, y - 0.05, z + 0.9), (x + dx + 0.05, y + 0.05, z + 2.3))
    m.box("hospsign", (x - 1.0, y - 0.12, z + 1.5), (x + 1.0, y + 0.08, z + 3.5))
    F = sides(m, 2.0, 0.2, x, y - 0.02, z + 1.5)["front"]
    for lo, hi in (((-0.55, 0.35), (-0.3, 1.65)), ((0.3, 0.35), (0.55, 1.65)), ((-0.3, 0.85), (0.3, 1.15))):
        F.box("panel", lo[0], hi[0], lo[1], hi[1], 0, 0.02)
