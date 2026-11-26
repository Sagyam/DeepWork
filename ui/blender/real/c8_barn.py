# C8, barn house: a contemporary house on a barn's lines, gable end to the
# street. A long 45-degree roof of standing-seam metal with no overhang to
# speak of, walls in dark vertical battens. The street gable is set back
# 1.3 m inside a frame wrapped in the roof's metal, the recess lined in
# light timber, and glazed from the deck to the apex: sliding doors below,
# a fixed band, and the gable's glass above in a grid. A weathering-steel
# box frames the dining room's picture window on the left; tall slot
# windows light the stairs. On the right a timber carport with a flat
# metal roof, a slatted screen and a store at its back. The back gable
# has the kitchen's sliders onto a small deck, the back door and a loft
# window in a steel box. Two rooflights and a black stove flue on the
# roof. The app stains the battens and tints the roof per house.
#
# Pieces (base at the origin):
#   body  plinth, walls to the eaves, the recess, its glass to the eaves, carport, decks
#   roof  the roof, the gables above the eaves, the gable glass, rooflights, flue
import math

from lib import Model, Side, Z, fpoly, glazing, new_id

ID = "c8"
XA, XB = -5.4, 1.6  # the barn's walls, left and right
XC = (XA + XB) / 2  # the ridge
HW = (XB - XA) / 2
Y0, Y1 = -5.2, 5.2  # front (street) and back gables
REC = 1.3  # depth of the glazed recess in the street gable
YG = Y0 + REC  # the glass wall
FL = 0.35  # floor level, on the plinth
ZE = 3.0  # the eaves: top of the long walls, the roof's underside there
T = 0.28  # roof build-up, measured vertically
OV = 0.12  # the roof's overhang, eaves and gables
FT = 0.35  # the frame round the recess, its width
S2 = math.sqrt(2)
Z2 = 2.5  # head of the sliding doors
ZT = ZE + 1.4  # the transom across the gable glass
XP = 5.2  # the carport's outer edge
CY0, CY1 = -2.8, 2.6  # the carport, front and back
CR = 2.6  # its roof's underside
STORE = 1.3  # depth of the store at the carport's back
FLUE = (XC + 1.7, 3.1)


def zu(x):
    """The roof's underside over the barn (the wall line on the gables)."""
    return ZE + HW - abs(x - XC)


def zo(x):
    """The roof's outer surface."""
    return zu(x) + T


def zi(x):
    """The top of the recess's opening: the underside brought in by the frame."""
    return zu(x) - FT * S2


XI0, XI1 = XA + FT, XB - FT  # the opening's sides
ZI = zi(XI0)  # where the opening's top meets its sides
APEX = zi(XC)


def build(out, bake=True):
    M = Model(ID)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, ZE))
    roof(M)
    M.export(out, bake)


# Facades with u along a world axis, so openings are given in plan coordinates.
def front(m, y=Y0):
    return Side(m, (0, y, 0), (1, 0, 0), (0, -1, 0))  # u = x


def back(m, y=Y1):
    return Side(m, (0, y, 0), (-1, 0, 0), (0, 1, 0))  # u = -x


def left(m, x=XA):
    return Side(m, (x, 0, 0), (0, -1, 0), (-1, 0, 0))  # u = -y


def right(m, x=XB):
    return Side(m, (x, 0, 0), (0, 1, 0), (1, 0, 0))  # u = y


def flat(m, role, x0, x1, y0, y1, z, out=Z):
    m.poly(role, [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], out=out)


def reveal(F, role, a, b, c, e, d):
    """The four reveal faces of an opening (a..b, c..e) d deep."""
    F.wall(role, a, b, c, c, [(a, b, c, e)], depth=d)


def clip(poly, lines):
    """Clips a polygon of (x, z) to below each line z = z0 + k (x - x0), given as (x0, z0, k)."""
    for x0, z0, k in lines:
        f = lambda p: z0 + k * (p[0] - x0) - p[1]  # noqa: E731
        out = []
        for a, b in zip(poly, poly[1:] + poly[:1]):
            fa, fb = f(a), f(b)
            if fa >= -1e-9:
                out.append(a)
            if (fa > 1e-9 and fb < -1e-9) or (fa < -1e-9 and fb > 1e-9):
                t = fa / (fa - fb)
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        poly = out
        if len(poly) < 3:
            return []
    return poly


# ---- parts ------------------------------------------------------------------------


def flush_door(F, a, b, c, e, D=0.1):
    """A plain door in a slim frame with a long pull."""
    F.box("alu", a, b, e - 0.05, e, -D - 0.02, -D + 0.08)
    F.box("alu", a, a + 0.05, c, e, -D - 0.02, -D + 0.08)
    F.box("alu", b - 0.05, b, c, e, -D - 0.02, -D + 0.08)
    F.quad("door", a + 0.05, b - 0.05, c, e - 0.05, -D + 0.02)
    u = b - 0.2
    F.box("ac", u, u + 0.03, c + 0.6, c + 1.6, -D + 0.02, -D + 0.07, skip=())


def steel_box(F, a, b, c, e, out=0.45, t=0.1):
    """A weathering-steel box round a window, standing `out` proud of the wall."""
    F.box("corten", a - t, a, c - t, e + t, 0, out, skip=())
    F.box("corten", b, b + t, c - t, e + t, 0, out, skip=())
    F.box("corten", a, b, e, e + t, 0, out, skip=("left", "right"))
    F.box("corten", a, b, c - t, c, 0, out, skip=("left", "right"))
    # The box's inside, carried back to the glass.
    for u0, u1, z0, z1, n in ((a, a, c, e, F.t), (b, b, c, e, -F.t)):
        F.m.poly("corten", [F.p(u0, z0, 0), F.p(u0, z0, out), F.p(u1, z1, out), F.p(u1, z1, 0)], out=n)
    F.m.poly("corten", [F.p(a, e, 0), F.p(b, e, 0), F.p(b, e, out), F.p(a, e, out)], out=-Z)
    F.m.poly("corten", [F.p(a, c, 0), F.p(b, c, 0), F.p(b, c, out), F.p(a, c, out)], out=Z)


def gable_glass(m, z0, z1, cols, transom):
    """The gable's glass between z0 and z1 under the opening's slopes, in
    `cols` columns with a transom: panes, mullions and the sloped frame."""
    F = front(m, YG)
    wid = new_id()
    us = [XI0 + i * (XI1 - XI0) / cols for i in range(cols + 1)]
    zs = [z0, transom, z1 + 1.0]
    uv = lambda u, z: (wid + (u - XI0) / (XI1 - XI0), (z - z0) / (APEX - z0))  # noqa: E731
    for i in range(cols):
        for j in range(2):
            poly = clip([(us[i] + 0.025, zs[j] + 0.025), (us[i + 1] - 0.025, zs[j] + 0.025), (us[i + 1] - 0.025, zs[j + 1] - 0.025), (us[i] + 0.025, zs[j + 1] - 0.025)], ((XI0, ZI - 0.06, 1.0), (XI1, ZI - 0.06, -1.0)))
            if poly:
                m.poly("glass", [F.p(u, z, 0) for u, z in poly], out=F.n, uvs=[uv(u, z) for u, z in poly])
    for u in us[1:-1]:
        top = ZI + min(u - XI0, XI1 - u)
        F.box("alu", u - 0.035, u + 0.035, z0, top, -0.08, 0.04)
        F.box("dark", u - 0.025, u + 0.025, z0, top - 0.02, 0.04, 0.1, skip=("back",))
    # The transom, as far as the slopes let it.
    d = transom - ZI
    F.box("alu", XI0 + d, XI1 - d, transom - 0.04, transom + 0.04, -0.08, 0.04)
    F.box("dark", XI0 + d, XI1 - d, transom - 0.025, transom + 0.025, 0.04, 0.1, skip=("back",))
    # The sloped frame along the opening's top.
    for x0, x1 in ((XI0, XC), (XI1, XC)):
        m.strut("alu", (x0, YG + 0.005, ZI - 0.03), (x1, YG + 0.005, APEX - 0.03), 0.08)


# ---- cladding -------------------------------------------------------------------

MG = 0.06  # battens stop this far short of an opening's frame


def battens(F, u0, u1, z0, top, holes, step=0.4, w=0.055, d=0.03):
    """Board-and-batten: a batten over every joint between the boards,
    `step` apart, stopped round `holes` (u0, u1, z0, z1 with their margin);
    `top(u)` is the wall's top at u (a gable's slope)."""
    n = max(1, round((u1 - u0) / step))
    for i in range(1, n):
        u = u0 + i * (u1 - u0) / n
        a, b = u - w / 2, u + w / 2
        segs = [(z0, min(top(a), top(b)) - 0.01)]
        for ha, hb, hc, he in holes:
            if b > ha and a < hb:
                segs = [q for s0, s1 in segs for q in ((s0, min(s1, hc)), (max(s0, he), s1))]
        for s0, s1 in segs:
            if s1 - s0 > 0.06:
                F.box("cladding", a, b, s0, s1, 0, d)


def grown(h, mg=MG):
    a, b, c, e = h[:4]
    return (a - mg, b + mg, c - mg, e + mg)


def clad(F, u0, u1, z0, z1, holes, boxed=(), step=0.4, corners=(True, True)):
    """A wall of boards with battens over them, its openings revealed in
    aluminium, a drip flashing at its foot and corner boards at its ends."""
    F.wall("barnboard", u0, u1, z0, z1, holes, depth=0.12, reveal="alu")
    battens(F, u0 + 0.06, u1 - 0.06, z0 + 0.04, lambda u: z1, [grown(h) for h in holes] + [grown(h, 0.14) for h in boxed], step)
    F.box("alu", u0, u1, z0 - 0.02, z0 + 0.04, 0, 0.05, skip=("back",))
    for u, k in ((u0, corners[0]), (u1, corners[1])):
        if k:
            F.box("cladding", min(u, u + (0.14 if u == u0 else -0.14)), max(u, u + (0.14 if u == u0 else -0.14)), z0 + 0.04, z1 - 0.01, 0, 0.04)


def sill(F, a, b, c):
    """A folded aluminium sill with drips at its ends."""
    F.box("alu", a - 0.04, b + 0.04, c - 0.05, c + 0.005, -0.04, 0.07)
    for u in (a - 0.04, b + 0.03):
        F.box("alu", u, u + 0.01, c, c + 0.05, 0, 0.07)


def log(m, x0, x1, y, z, r, seg=7, ends=(False, True)):
    """A split log lying along x: bark round it, the sawn ends."""
    pts = [(y + math.cos(k / seg * math.tau) * r, z + math.sin(k / seg * math.tau) * r) for k in range(seg)]
    for k in range(seg):
        (ya, za), (yb, zb) = pts[k], pts[(k + 1) % seg]
        mid = (k + 0.5) / seg * math.tau
        m.poly("bark", [(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)], out=(0, math.cos(mid), math.sin(mid)))
    for x, e, n in ((x0, ends[0], -1), (x1, ends[1], 1)):
        if e:
            m.poly("logend", [(x, yy, zz) for yy, zz in pts], out=(n, 0, 0))


# ---- body -----------------------------------------------------------------------


def body(M):
    m = M.m
    # A board-marked concrete plinth, a shadow gap under the boards.
    m.sweep("boardform", XB - XA, Y1 - Y0, [(-0.03, 0.0), (-0.03, FL - 0.02), (0.0, FL - 0.02)], cx=XC, cy=0)

    # The frame round the recess: jambs below the eaves, in the roof's metal,
    # with an edge trim where it meets the timber.
    for x0, x1 in ((XA, XI0), (XI1, XB)):
        m.poly("zincseam", [(x0, Y0, FL), (x1, Y0, FL), (x1, Y0, ZI if x0 == XA else ZE), (x0, Y0, ZE if x0 == XA else ZI)], out=(0, -1, 0))
    for x in (XI0, XI1):
        m.box("alu", (x - 0.03, Y0 - 0.03, FL), (x + 0.03, Y0 + 0.04, ZI))
    # The recess: slatted timber linings, a boarded deck, lamps, a bench, the glass wall.
    for x, n in ((XI0, 1), (XI1, -1)):
        m.poly("dark", [(x, Y0, FL), (x, YG, FL), (x, YG, ZI), (x, Y0, ZI)], out=(n, 0, 0))
        z = FL + 0.02
        while z + 0.07 < ZI:
            m.box("wood", (x, Y0 + 0.02, z), (x + n * 0.025, YG, z + 0.07), skip=("x0" if n > 0 else "x1",))
            z += 0.095
        m.box("lamp", (x + n * 0.025 - 0.06 * (n < 0), (Y0 + YG) / 2 - 0.08, 2.05), (x + n * 0.025 + 0.06 * (n > 0), (Y0 + YG) / 2 + 0.08, 2.4))
    flat(m, "dark", XI0, XI1, Y0, YG, FL - 0.03)
    y = Y0 + 0.01
    while y + 0.13 < YG:
        m.box("deck", (XI0, y, FL - 0.03), (XI1, y + 0.135, FL), skip=("z0",))
        y += 0.145
    # A slatted bench against the left lining.
    bx = XI0 + 0.03
    for yy in (Y0 + 0.25, YG - 0.35):
        m.box("dark", (bx, yy, FL), (bx + 0.42, yy + 0.06, FL + 0.42), skip=("z0",))
    for k in range(4):
        m.box("oak", (bx + 0.02 + k * 0.1, Y0 + 0.15, FL + 0.42), (bx + 0.1 + k * 0.1, YG - 0.15, FL + 0.46), skip=())
    G = front(m, YG)
    glazing(G, XI0, XI1, FL, Z2, lights=4, D=0.0, slide=True)
    glazing(G, XI0, XI1, Z2, ZI, lights=4, D=0.0)
    # A step down from the deck: boards on a steel frame.
    m.box("dark", (XC - 1.3, Y0 - 0.55, 0), (XC + 1.3, Y0 - 0.03, 0.14), skip=("z0", "y1"))
    for k in range(3):
        y = Y0 - 0.54 + k * 0.17
        m.box("deck", (XC - 1.32, y, 0.14), (XC + 1.32, y + 0.16, 0.18), skip=("z0",))

    # Left: the steel-boxed picture window, slots for the stairs and the hall.
    L = left(m)
    pic = (-1.4, 1.4, 0.85, 2.55)
    slots = [(-4.1, -3.6, FL + 0.1, 2.75), (2.9, 3.35, FL + 0.6, 2.75), (3.75, 4.2, FL + 0.6, 2.75)]
    clad(L, -Y1, -Y0, FL, ZE, [pic, *slots], boxed=[pic], corners=(True, False))
    glazing(L, *pic, lights=2)
    steel_box(L, *pic)
    for s in slots:
        glazing(L, *s)
        if s[2] > FL + 0.2:
            sill(L, s[0], s[1], s[2])
    # The frame's metal wraps round the front corner.
    L.box("zincseam", -Y0 - 0.12, -Y0, FL, ZE, 0, 0.035, skip=("back",))

    # Right: the kitchen window, the door to the carport, the utility window behind it.
    R = right(m)
    kitchen = (-3.4, -1.9, 1.15, 2.45)
    door = (0.4, 1.35, FL, FL + 2.15)
    util = (3.3, 4.1, 1.4, 2.4)
    clad(R, Y0, Y1, FL, ZE, [kitchen, door, util], corners=(False, True))
    R.box("zincseam", Y0, Y0 + 0.12, FL, ZE, 0, 0.035, skip=("back",))
    glazing(R, *kitchen, lights=2)
    sill(R, kitchen[0], kitchen[1], kitchen[2])
    flush_door(R, *door)
    glazing(R, *util)
    sill(R, util[0], util[1], util[2])
    # The meter box and an outside tap by the door.
    R.box("ac", 1.7, 2.15, 1.3, 1.85, 0, 0.16, skip=("back",))
    R.box("dark", 1.75, 2.1, 1.36, 1.79, 0.16, 0.165, skip=("back",))
    R.box("alu", 2.4, 2.46, 0.55, 0.62, 0, 0.12, skip=("back",))

    # Back: sliders onto the deck, the back door, a window between.
    B = back(m)
    slider = (2.4, 5.0, FL, Z2)
    bdoor = (-1.2, -0.3, FL, FL + 2.15)
    bwin = (0.3, 1.5, 1.2, 2.4)
    clad(B, -XB, -XA, FL, ZE, [slider, bdoor, bwin])
    glazing(B, *slider, lights=2, slide=True)
    flush_door(B, *bdoor)
    glazing(B, *bwin)
    sill(B, bwin[0], bwin[1], bwin[2])
    # The back deck in boards on a dark frame, a step at the door.
    m.box("dark", (-5.2, Y1, 0), (-2.2, Y1 + 1.0, FL - 0.08), skip=("z0", "y0"))
    x = -5.2
    while x + 0.13 < -2.2:
        m.box("deck", (x, Y1, FL - 0.08), (x + 0.135, Y1 + 1.0, FL - 0.05), skip=("z0", "y0"))
        x += 0.145
    m.box("concrete", (0.2, Y1, 0), (1.3, Y1 + 0.5, 0.17), skip=("z0", "y0"))
    # Wall lights by the doors.
    m.box("lamp", (1.45, Y1, 2.3), (1.6, Y1 + 0.08, 2.6))
    m.box("lamp", (XB, 1.55, 2.3), (XB + 0.08, 1.7, 2.6))
    # Downpipes from the gutters at the back corners, shoes at their feet.
    for x in (XA - OV - 0.06, XB + OV + 0.06):
        m.cyl("dark", x, Y1 - 0.25, 0.045, 0.08, ZE - 0.05, seg=10, top=False)
        m.box("dark", (x - 0.045, Y1 - 0.3, 0.02), (x + 0.045, Y1 - 0.2, 0.08))
        for z in (0.9, 2.0):
            m.box("dark", (x - 0.06, Y1 - 0.3, z), (x + 0.06, Y1 - 0.2, z + 0.04))

    carport(M)
    # A ceiling, seen only when the roof is gone.
    flat(m, "dark", XA, XB, YG, Y1, ZE - 0.02, out=Z)


def carport(M):
    """Timber posts on steel shoes, exposed joists under a flat metal roof,
    a slatted screen, the store behind, and a log store against the house."""
    m = M.m
    m.box("concrete", (XB, CY0, 0), (XP, CY1, 0.05), skip=("z0", "x0"))
    for y in (CY0 + 0.1, (CY0 + CY1 - STORE) / 2, CY1 - STORE):
        m.box("wood", (XP - 0.22, y - 0.08, 0.2), (XP - 0.06, y + 0.08, CR), skip=("z1",))
        m.box("dark", (XP - 0.2, y - 0.06, 0.05), (XP - 0.08, y + 0.06, 0.2), skip=("z0",))
    # Roof: the beam on the posts, joists across, boards over them.
    m.box("wood", (XP - 0.24, CY0, CR), (XP - 0.04, CY1, CR + 0.22), skip=("z1",))
    y = CY0 + 0.15
    while y < CY1 - 0.1:
        m.box("wood", (XB, y - 0.035, CR + 0.02), (XP - 0.24, y + 0.035, CR + 0.22), skip=("z1", "x0"))
        y += 0.6
    flat(m, "wood", XB, XP, CY0, CY1, CR + 0.22, out=-Z)
    m.box("alu", (XB, CY0, CR + 0.22), (XP, CY1, CR + 0.36), skip=("z0", "z1", "x0"))
    flat(m, "zincseam", XB, XP, CY0, CY1, CR + 0.36)
    m.box("alu", (XB, CY0 - 0.03, CR + 0.36), (XP + 0.03, CY0 + 0.05, CR + 0.41))
    m.box("alu", (XP - 0.05, CY0 - 0.03, CR + 0.36), (XP + 0.03, CY1 + 0.03, CR + 0.41))
    m.box("alu", (XB, CY1 - 0.05, CR + 0.36), (XP + 0.03, CY1 + 0.03, CR + 0.41))
    # The store: boards and battens to match, a door to the car.
    ys = CY1 - STORE
    S = Side(m, (0, ys, 0), (1, 0, 0), (0, -1, 0))
    sd = (XP - 1.3, XP - 0.4, 0.05, 2.2)
    clad(S, XB, XP - 0.06, 0.07, CR + 0.02, [sd], corners=(False, True))
    flush_door(S, *sd, D=0.08)
    E = Side(m, (XP - 0.06, 0, 0), (0, 1, 0), (1, 0, 0))
    clad(E, ys, CY1, 0.07, CR + 0.02, [], corners=(False, True))
    K = Side(m, (0, CY1, 0), (-1, 0, 0), (0, 1, 0))
    clad(K, -(XP - 0.06), -XB, 0.07, CR + 0.02, [], corners=(True, False))
    # The screen: vertical slats from the middle post to the store.
    y = (CY0 + CY1 - STORE) / 2 + 0.14
    while y < ys - 0.06:
        m.box("wood", (XP - 0.2, y, 0.12), (XP - 0.11, y + 0.045, CR), skip=("z1",))
        y += 0.115
    m.box("wood", (XP - 0.22, (CY0 + CY1 - STORE) / 2, 0.05), (XP - 0.09, ys, 0.12), skip=("z0",))

    # The log store: a steel rack against the house, under the kitchen window.
    y0, y1, h = -2.65, -0.45, 1.0
    x0, x1 = XB + 0.02, XB + 0.44
    m.box("dark", (x0, y0 - 0.04, 0.05), (x1, y1 + 0.04, 0.1), skip=("z0",))
    for y in (y0 - 0.04, y1):
        m.box("dark", (x0, y, 0.05), (x1, y + 0.04, h + 0.08), skip=("z0",))
    m.box("dark", (x0, y0 - 0.04, h + 0.08), (x1 + 0.04, y1 + 0.04, h + 0.11))
    R = M.R
    z = 0.1 + 0.075
    row = 0
    while z + 0.07 < h + 0.06:
        y = y0 + 0.075 + (0.04 if row % 2 else 0)
        while y + 0.075 < y1:
            r = 0.06 + R.random() * 0.025
            out = R.random() * 0.05
            log(m, x0 + 0.02, x1 - 0.02 + out, y + (R.random() - 0.5) * 0.02, z + (R.random() - 0.5) * 0.015, r, seg=7)
            y += 0.155
        z += 0.135
        row += 1


# ---- roof -----------------------------------------------------------------------


def slope(side, s, y, h=0.0):
    """A point on the roof's outer surface, s metres up the slope from its
    eave edge, at y, h above it. side -1 is the left slope, 1 the right."""
    x = XA - OV + s / S2 if side < 0 else XB + OV - s / S2
    n = (side / S2, 0, 1 / S2)
    z = zo(x)
    return (x + n[0] * h, y + n[1] * h, z + n[2] * h)


def roof(M):
    m = M.m
    ya, yb = Y0 - OV, Y1 + OV
    run = (XC - (XA - OV)) * S2  # the slope's length, eave to ridge
    for sd in (-1, 1):
        xe = XA - OV if sd < 0 else XB + OV
        top = [slope(sd, 0, ya), slope(sd, 0, yb), slope(sd, run, yb), slope(sd, run, ya)]
        m.poly("zincseam", top, out=(sd, 0, 1), uvs=[(ya, 0), (yb, 0), (yb, run), (ya, run)])
        # The eave's edge and its underside, the gables' edges.
        lo = lambda x: zu(x)  # noqa: E731
        m.poly("alu", [(xe, ya, lo(xe)), (xe, yb, lo(xe)), (xe, yb, zo(xe)), (xe, ya, zo(xe))], out=(sd, 0, 0))
        xw = XA if sd < 0 else XB
        m.poly("alu", [(xe, ya, lo(xe)), (xw, ya, lo(xw)), (xw, yb, lo(xw)), (xe, yb, lo(xe))], out=(0, 0, -1))
        for y, n in ((ya, -1), (yb, 1)):
            m.poly("alu", [(xe, y, lo(xe)), (XC, y, lo(XC)), (XC, y, zo(XC)), (xe, y, zo(xe))], out=(0, n, 0))
            # The gable's overhang underside.
            yw = Y0 if n < 0 else Y1
            m.poly("alu", [(xw, y, lo(xw)), (XC, y, lo(XC)), (XC, yw, lo(XC)), (xw, yw, lo(xw))], out=(0, 0, -1))
        # Standing seams every half metre, down the slope.
        y = ya + 0.25
        while y < yb - 0.1:
            a0, a1 = y - 0.012, y + 0.012
            q = lambda s_, yy, h: slope(sd, s_, yy, h)  # noqa: E731
            for yy, n in ((a0, -1), (a1, 1)):
                m.poly("zincseam", [q(0, yy, 0), q(run, yy, 0), q(run, yy, 0.035), q(0, yy, 0.035)], out=(0, n, 0))
            m.poly("zincseam", [q(0, a0, 0.035), q(run, a0, 0.035), q(run, a1, 0.035), q(0, a1, 0.035)], out=(sd, 0, 1))
            m.poly("zincseam", [q(0, a0, 0), q(0, a1, 0), q(0, a1, 0.035), q(0, a0, 0.035)], out=(sd, 0, -1))
            y += 0.5
        # Snow rails low on the slope, on brackets at every other seam.
        for s_ in (0.55, 0.75):
            m.tube("alu", [slope(sd, s_, ya + 0.2, 0.1), slope(sd, s_, yb - 0.2, 0.1)], 0.018, (sd, 0, 1), closed=False, seg=6)
        y = ya + 0.25
        while y < yb - 0.1:
            m.strut("alu", slope(sd, 0.5, y, 0.035), slope(sd, 0.8, y, 0.11), 0.02)
            y += 1.0
        # A box gutter along the eave.
        g0, g1 = (xe - 0.14, xe) if sd < 0 else (xe, xe + 0.14)
        zg = zo(xe) - 0.04
        m.box("dark", (g0, ya, zg - 0.13), (g1, yb, zg), skip=("z1",))
        m.poly("dark", [(g0, ya, zg - 0.02), (g1, ya, zg - 0.02), (g1, yb, zg - 0.02), (g0, yb, zg - 0.02)], out=Z)
    # A ridge cap folded over both slopes.
    rc = zo(XC)
    for sd in (-1, 1):
        m.poly("alu", [(XC, ya, rc + 0.05), (XC, yb, rc + 0.05), (XC + sd * 0.14, yb, rc - 0.09), (XC + sd * 0.14, ya, rc - 0.09)], out=(sd, 0, 1))
        m.poly("alu", [(XC + sd * 0.14, ya, rc - 0.09), (XC + sd * 0.14, yb, rc - 0.09), (XC + sd * 0.14, yb, rc - 0.14), (XC + sd * 0.14, ya, rc - 0.14)], out=(sd, 0, 0))
    for y, n in ((ya, -1), (yb, 1)):
        m.poly("alu", [(XC - 0.14, y, rc - 0.14), (XC + 0.14, y, rc - 0.14), (XC + 0.14, y, rc - 0.09), (XC, y, rc + 0.05), (XC - 0.14, y, rc - 0.09)], out=(0, n, 0))

    # The frame round the recess, above the eaves; timber soffits behind it.
    for x0, xi in ((XA, XI0), (XB, XI1)):
        m.poly("zincseam", [(x0, Y0, zu(x0)), (XC, Y0, zu(XC)), (XC, Y0, APEX), (xi, Y0, ZI)], out=(0, -1, 0))
        m.poly("dark", [(xi, Y0, ZI), (XC, Y0, APEX), (XC, YG, APEX), (xi, YG, ZI)], out=(-(x0 - XC), 0, -1))
        # Slats under it, running back to the glass, as on the linings.
        sgn = 1 if xi < XC else -1
        x = xi + sgn * 0.01
        n = (sgn / S2, -1 / S2)  # square to the slope, down and in
        while (x - XC) * sgn < -0.08:
            pa, pb = (x, zi(x)), (x + sgn * 0.075, zi(x + sgn * 0.075))
            top = [(p[0] + n[0] * 0.005, p[1] + n[1] * 0.005) for p in (pa, pb)]
            bot = [(p[0] + n[0] * 0.035, p[1] + n[1] * 0.035) for p in (pa, pb)]
            ya_, yb_ = Y0 + 0.02, YG
            m.poly("wood", [(bot[0][0], ya_, bot[0][1]), (bot[1][0], ya_, bot[1][1]), (bot[1][0], yb_, bot[1][1]), (bot[0][0], yb_, bot[0][1])], out=(n[0], 0, n[1]))
            for k, d in ((0, -sgn), (1, sgn)):
                m.poly("wood", [(top[k][0], ya_, top[k][1]), (bot[k][0], ya_, bot[k][1]), (bot[k][0], yb_, bot[k][1]), (top[k][0], yb_, top[k][1])], out=(d / S2, 0, d * sgn / S2))
            m.poly("wood", [(top[0][0], ya_, top[0][1]), (top[1][0], ya_, top[1][1]), (bot[1][0], ya_, bot[1][1]), (bot[0][0], ya_, bot[0][1])], out=(0, -1, 0))
            x += sgn * 0.1
    # The edge trim along the frame's sloped inner edge.
    for x0 in (XI0, XI1):
        m.strut("alu", (x0, Y0 + 0.005, ZI), (XC, Y0 + 0.005, APEX), 0.06)
    for t in (0.35, 0.65):
        x = XI0 + (XC - XI0) * t
        for xx in (x, 2 * XC - x):
            m.cyl("lamp", xx, (Y0 + YG) / 2, 0.06, zi(xx) - 0.05, zi(xx) - 0.04, seg=10, top=False, bottom=True)
    gable_glass(m, ZI, APEX, 4, ZT)

    # The back gable, with the loft window in a steel box.
    B = back(m)
    wx = (XC - 0.75, XC + 0.75)
    wz = (ZE + 0.55, ZE + 2.1)
    a, b = -wx[1], -wx[0]  # in the back's u (= -x)
    u_ = lambda x: -x  # noqa: E731
    fpoly(B, "barnboard", [(u_(XB), ZE), (u_(XA), ZE), (u_(XA + wz[0] - ZE), wz[0]), (u_(XB - (wz[0] - ZE)), wz[0])])
    fpoly(B, "barnboard", [(u_(XB - (wz[0] - ZE)), wz[0]), (a, wz[0]), (a, zu(wx[1]))])
    fpoly(B, "barnboard", [(b, wz[0]), (u_(XA + wz[0] - ZE), wz[0]), (b, zu(wx[0]))])
    fpoly(B, "barnboard", [(a, wz[1]), (b, wz[1]), (b, zu(wx[0])), (u_(XC), zu(XC)), (a, zu(wx[1]))])
    battens(B, -XB + 0.06, -XA - 0.06, ZE, lambda u: zu(-u), [grown((a, b, *wz), 0.14)])
    reveal(B, "alu", a, b, *wz, 0.12)
    glazing(B, a, b, *wz, lights=1)
    steel_box(B, a, b, *wz, out=0.35)

    # Two rooflights low on the left slope.
    for y0 in (-2.4, 0.9):
        rooflight(m, -1, 1.5, 2.7, y0, y0 + 0.95)
    # The stove's flue through the right slope, black, with its cap.
    fx, fy = FLUE
    z0 = zo(fx) - 0.1
    m.box("dark", (fx - 0.22, fy - 0.22, z0), (fx + 0.22, fy + 0.22, zo(fx - 0.22) + 0.06), skip=("z0",))
    m.cyl("dark", fx, fy, 0.1, z0, zo(XC) + 0.75, seg=16, top=False)
    m.cyl("dark", fx, fy, 0.15, zo(fx - 0.22) + 0.06, zo(fx - 0.22) + 0.2, seg=16, r1=0.1)
    for k in range(3):
        zb = zo(XC) - 0.4 + k * 0.45
        m.cyl("alu", fx, fy, 0.108, zb, zb + 0.03, seg=16, bottom=True)
    m.cyl("dark", fx, fy, 0.17, zo(XC) + 0.83, zo(XC) + 0.86, seg=12, bottom=True)
    m.cyl("dark", fx, fy, 0.17, zo(XC) + 0.86, zo(XC) + 0.98, seg=12, r1=0.03)
    for k in range(3):
        ang = k * math.tau / 3
        x, y = fx + math.cos(ang) * 0.11, fy + math.sin(ang) * 0.11
        m.box("dark", (x - 0.012, y - 0.012, zo(XC) + 0.74), (x + 0.012, y + 0.012, zo(XC) + 0.84))


def rooflight(m, sd, s0, s1, y0, y1, h=0.12):
    """A flush rooflight: an aluminium kerb, dark glass on top."""
    lo = [slope(sd, s0, y0), slope(sd, s0, y1), slope(sd, s1, y1), slope(sd, s1, y0)]
    hi = [slope(sd, s0, y0, h), slope(sd, s0, y1, h), slope(sd, s1, y1, h), slope(sd, s1, y0, h)]
    n = (sd, 0, 1)
    for i in range(4):
        j = (i + 1) % 4
        mid = [(lo[i][k] + lo[j][k]) / 2 - sum(p[k] for p in lo) / 4 for k in range(3)]
        m.poly("alu", [lo[i], lo[j], hi[j], hi[i]], out=mid)
    m.poly("alu", hi, out=n)
    g = [slope(sd, s0 + 0.07, y0 + 0.07, h + 0.01), slope(sd, s0 + 0.07, y1 - 0.07, h + 0.01), slope(sd, s1 - 0.07, y1 - 0.07, h + 0.01), slope(sd, s1 - 0.07, y0 + 0.07, h + 0.01)]
    m.poly("skyglass", g, out=n)
