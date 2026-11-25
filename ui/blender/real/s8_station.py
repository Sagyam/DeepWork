# S8, filling station: a streamline service station of the late 1940s. A
# low building in white porcelain-enamel panels with a band of colour along
# its base and parapet: the office on the left with a ribbon of glass that
# wraps its rounded corner, a glass door, two service bays on the right (one
# door rolled up on a lift and a bench, one closed), the restrooms' doors on
# the side. A fin tower over the office's corner with speed lines and a neon
# tube up its nose. In front, a flat canopy on two stainless columns over two
# pump islands, four pumps with lit globes, the station's name on the
# canopy's fascia; a pylon sign at the corner of the lot, an air post, a rack
# of oil cans, an ice chest and tyres by the bays. The app picks the enamel
# colour, the neon and the name.
#
# Pieces (base at the origin):
#   body  the building to its wall head, the bay's insides, the canopy,
#         islands, pumps, the pylon and the forecourt's furniture
#   roof  parapet and band, the fin tower, the deck and its plant
import math

from mathutils import Vector

from lib import Model, Side, Z, letters, neon, new_id, pane, sides

ID = "s8"
XL, XR = -6.4, 6.4  # the building's ends
YF, YB = 0.0, 6.3  # its front and back walls
CY = (YF + YB) / 2
R = 1.6  # the office's rounded corner, front left
TOP = 3.8  # wall head: the roof piece's base
PL = 0.15  # the office floor above the forecourt
RIB = (0.6, 3.1)  # the office's ribbon of glass
IS = 0.2  # pump islands' top
ISL = [-2.6, 2.6]  # their x; they run back from the street
ISY = (-5.5, -1.7)
PUMPS = [-4.75, -2.45]  # pumps' y on each island; the column between them
COL = -3.6
CAN = (-5.4, 5.4, -6.3, -0.8)  # canopy plan: x0, x1, y0, y1
CZ = 4.3  # canopy soffit
CF = 5.05  # top of its fascia
DOOR = (-2.85, -1.9)  # the office door
BAYS = [(-0.95, 2.15), (2.7, 5.8)]  # service bay openings; the first stands open
BH = 3.2  # their head
PY = (6.4, -5.95)  # the pylon sign, x and y


def build(out, bake=True):
    M = Model(ID)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    M.export(out, bake)


def arc(n=8):
    """The rounded corner as (point, outward normal) pairs, from the side wall round to the front."""
    cx, cy = XL + R, YF + R
    out = []
    for i in range(n + 1):
        a = math.pi + i / n * math.pi / 2
        out.append((Vector((cx + R * math.cos(a), cy + R * math.sin(a), 0)), Vector((math.cos(a), math.sin(a), 0))))
    return out


def outline():
    """The building's plan, counter-clockwise from above: round the corner, then the square ones."""
    return [(p.x, p.y) for p, _ in arc()] + [(XR, YF), (XR, YB), (XL, YB)]


def facets(m, z=0.0):
    """The corner's facets as Sides (u from 0 to their length), with their lengths."""
    pts = arc()
    out = []
    for (p0, n0), (p1, n1) in zip(pts, pts[1:]):
        t = p1 - p0
        out.append((Side(m, p0 + Vector((0, 0, z)), t, (n0 + n1).normalized()), t.length))
    return out


def walls(m):
    """The building's straight walls as Sides; u runs left to right seen from outside."""
    return sides(m, XR - XL, YB - YF, (XL + XR) / 2, CY)


def strip(F, u0, u1, z0, z1, holes, role, w0=0.0, w1=0.02):
    """A band proud of the wall from u0 to u1, broken where an opening crosses it."""
    cuts = sorted((a, b) for a, b, c, e, *_ in holes if c < z1 and e > z0)
    u = u0
    for a, b in cuts:
        if a > u + 1e-6:
            F.box(role, u, min(a, u1), z0, z1, w0, w1)
        u = max(u, b)
    if u1 > u + 1e-6:
        F.box(role, u, u1, z0, z1, w0, w1)


# ---- body -----------------------------------------------------------------------------


def body(M):
    m = M.m
    W = walls(m)
    building(M, m, W)
    open_bay(m, W["front"])
    closed_door(W["front"], *BAYS[1])
    canopy(M, m)
    for x in ISL:
        island(m, x)
    pylon(m)
    furniture(m)


def ribbon(M, F, u0, u1, wid, at, total, ends=(False, False)):
    """The office's glass band on F from u0 to u1, set back 0.1 m; `at` is where it
    starts along the whole ribbon and `total` its length, for the window's UVs."""
    m = M.m
    c, e = RIB
    D_ = 0.1
    F.box("enamel", u0, u1, 0.0, 0.55, 0, 0.03, skip=("back",))
    F.quad("cream", u0, u1, 0.55, c)
    F.quad("cream", u0, u1, e, TOP)
    uv = lambda u, z: (wid + (at + u - u0) / total, (z - c) / (e - c))  # noqa: E731
    F.quad("shopglass", u0, u1, c, e, -D_, uvs=[uv(u0, c), uv(u1, c), uv(u1, e), uv(u0, e)])
    # Sill and head in stainless, and the reveals at a free end.
    F.box("stainless", u0, u1, c - 0.04, c, -D_, 0.05, skip=())
    m.poly("stainless", [F.p(u0, e, 0), F.p(u1, e, 0), F.p(u1, e, -D_), F.p(u0, e, -D_)], out=-Z)
    for u, s, end in ((u0, 1, ends[0]), (u1, -1, ends[1])):
        if end:
            m.poly("stainless", [F.p(u, c, 0), F.p(u, c, -D_), F.p(u, e, -D_), F.p(u, e, 0)], out=F.t * s)


def building(M, m, W):
    wid = new_id()
    # The ribbon: the side window, round the corner, along the front to the door.
    side_u = (0.0, CY - YF - R)  # left wall u, which runs towards the front
    front_u = (XL + R, DOOR[0] - 0.12)
    fac = facets(m)
    total = (side_u[1] - side_u[0]) + sum(L for _, L in fac) + (front_u[1] - front_u[0])
    at = 0.0
    ribbon(M, W["left"], *side_u, wid, at, total, ends=(True, False))
    at += side_u[1] - side_u[0]
    for i, (F, L) in enumerate(fac):
        ribbon(M, F, 0, L, wid, at, total)
        if i % 2 == 0:
            F.box("stainless", -0.025, 0.025, RIB[0], RIB[1], -0.1, -0.04, skip=())
        at += L
    ribbon(M, W["front"], *front_u, wid, at, total, ends=(False, True))
    F = W["front"]
    for u in (-4.0, front_u[1] - 0.02):
        F.box("stainless", u - 0.025, u + 0.025, RIB[0], RIB[1], -0.1, -0.04, skip=())
    W["left"].box("stainless", 0.6 - 0.025, 0.6 + 0.025, RIB[0], RIB[1], -0.1, -0.04, skip=())
    # Front: the door, two bays between enamel-capped piers.
    a, b = DOOR
    holes = [(a, b, PL, 2.75, 0.2)] + [(u0, u1, 0.0, BH, 0.25) for u0, u1 in BAYS]
    F.wall("cream", front_u[1], XR, 0, TOP, holes, reveal="stainless")
    strip(F, front_u[1], XR, 0, 0.55, holes, "enamel", 0, 0.03)
    for u0, u1 in BAYS:
        F.box("stainless", u0 - 0.06, u1 + 0.06, BH, BH + 0.06, 0, 0.05)
    door(F, a, b)
    m.box("concrete", (a - 0.3, YF - 0.6, 0), (b + 0.3, YF, PL), skip=("y1",))
    # A pinstripe of enamel under the wall head, all the way round.
    m.psweep("enamel", outline(), [(0.0, 3.32), (0.03, 3.32), (0.03, 3.42), (0.0, 3.42)])
    # Left side: the restrooms' doors, behind the office.
    S = W["left"]
    rest = [(-2.75, -1.85), (-1.45, -0.55)]
    S.wall("cream", -CY + YF, side_u[0], 0, TOP, [(u0, u1, 0, 2.2, 0.12) for u0, u1 in rest], reveal="stainless")
    strip(S, -CY + YF, side_u[0], 0, 0.55, [(u0, u1, 0, 2.2) for u0, u1 in rest], "enamel", 0, 0.03)
    for u0, u1 in rest:
        S.quad("door", u0, u1, 0, 2.2, -0.12)
        for k in range(4):
            z = 0.25 + k * 0.48
            S.box("door", u0 + 0.12, u1 - 0.12, z, z + 0.3, -0.12, -0.1)
        S.box("brass", u1 - 0.18, u1 - 0.12, 1.0, 1.06, -0.12, -0.06)
        S.box("dark", u0 + 0.2, u1 - 0.2, 2.35, 2.6, 0, 0.02)
        S.box("cream", u0 + 0.25, u1 - 0.25, 2.4, 2.55, 0.02, 0.025)
    # Right side: a window over the bench, the ladder to the roof.
    S = W["right"]
    win = (-0.8, 0.6, 1.5, 2.7)
    S.wall("cream", -CY + YF, CY - YF, 0, TOP, [(*win, 0.18)], reveal="stainless")
    strip(S, -CY + YF, CY - YF, 0, 0.55, [], "enamel", 0, 0.03)
    wid2 = new_id()
    S.box("stainless", win[0], win[1], win[2] - 0.04, win[2], -0.18, 0.06, skip=())
    pane(S, "glass", *win, *win, -0.12, wid2)
    S.box("stainless", (win[0] + win[1]) / 2 - 0.02, (win[0] + win[1]) / 2 + 0.02, win[2], win[3], -0.12, -0.08)
    for u in (1.9, 2.35):
        S.box("iron", u - 0.025, u + 0.025, 0.9, TOP + 1.1, 0.12, 0.16, skip=())
    for k in range(int((TOP + 0.9 - 1.0) / 0.3) + 1):
        z = 1.0 + k * 0.3
        S.box("iron", 1.9, 2.35, z - 0.015, z + 0.015, 0.125, 0.155, skip=())
    for z in (1.3, TOP - 0.2):
        S.box("iron", 1.88, 1.92, z - 0.02, z + 0.02, 0, 0.14)
        S.box("iron", 2.33, 2.37, z - 0.02, z + 0.02, 0, 0.14)
    # Back: the stores' door, the bays' high windows, a downpipe.
    B = W["back"]
    hi = [(-5.6, -3.4, 2.2, 3.0), (-2.8, -0.6, 2.2, 3.0)]
    holes = hi + [(3.6, 4.5, 0, 2.2, 0.12)]
    B.wall("cream", XL, XR, 0, TOP, holes, reveal="stainless")
    strip(B, XL, XR, 0, 0.55, holes, "enamel", 0, 0.03)
    for a_, b_, c, e in hi:
        g = new_id()
        B.box("stainless", a_, b_, c - 0.04, c, -0.18, 0.05, skip=())
        pane(B, "glass", a_, b_, c, e, a_, b_, c, e, -0.12, g)
        for k in (1, 2, 3):
            u = a_ + k * (b_ - a_) / 4
            B.box("stainless", u - 0.02, u + 0.02, c, e, -0.12, -0.08)
    B.quad("door", 3.6, 4.5, 0, 2.2, -0.12)
    B.box("iron", 3.65, 3.72, 1.0, 1.06, -0.12, -0.06)
    B.box("lamp", 4.65, 4.85, 2.3, 2.5, 0, 0.12)
    m.box("gutter", (XR - 0.4, YB + 0.03, 0.05), (XR - 0.3, YB + 0.13, TOP))
    # A lid over the wall head, seen while the roof is not yet on.
    m.poly("dark", [(x, y, TOP - 0.02) for x, y in outline()], out=Z)


def door(F, a, b):
    """The office door: a stainless frame round a single glass leaf, a transom, a push bar."""
    D_ = 0.2
    c, e = PL, 2.75
    wid = new_id()
    t = 2.3
    fr = "stainless"
    F.box(fr, a, a + 0.06, c, e, -D_, -D_ + 0.08)
    F.box(fr, b - 0.06, b, c, e, -D_, -D_ + 0.08)
    F.box(fr, a + 0.06, b - 0.06, e - 0.06, e, -D_, -D_ + 0.08)
    F.box(fr, a + 0.06, b - 0.06, t - 0.05, t + 0.05, -D_, -D_ + 0.08)
    F.box(fr, a + 0.06, b - 0.06, c, c + 0.22, -D_, -D_ + 0.08)
    pane(F, "doorglass", a, b, c, e, a + 0.06, b - 0.06, c + 0.22, t - 0.05, -D_ + 0.04, wid)
    pane(F, "doorglass", a, b, c, e, a + 0.06, b - 0.06, t + 0.05, e - 0.06, -D_ + 0.04, wid)
    F.box("brass", a + 0.12, b - 0.12, c + 0.95, c + 1.0, -D_ + 0.08, -D_ + 0.13)


def open_bay(m, F):
    """The first bay, its door rolled up: a lift with its arms, a bench, tyres, a tool chest, a light."""
    a, b = BAYS[0]
    y0, y1 = YF + 0.25, YB - 0.25
    x0, x1 = a - 0.5, b + 0.3
    h = 3.5
    m.poly("concrete", [(x0, y0, 0.005), (x1, y0, 0.005), (x1, y1, 0.005), (x0, y1, 0.005)], out=Z)
    m.poly("paint", [(x0, y1, 0), (x1, y1, 0), (x1, y1, h), (x0, y1, h)], out=(0, -1, 0))
    m.poly("paint", [(x0, y0, 0), (x0, y1, 0), (x0, y1, h), (x0, y0, h)], out=(1, 0, 0))
    m.poly("paint", [(x1, y0, 0), (x1, y1, 0), (x1, y1, h), (x1, y0, h)], out=(-1, 0, 0))
    m.poly("paint", [(x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h)], out=-Z)
    m.poly("paint", [(a, y0, BH), (b, y0, BH), (b, y0, h), (a, y0, h)], out=(0, 1, 0))
    # A dado of enamel round the bay's walls.
    m.poly("enamel", [(x0, y1 - 0.01, 0), (x1, y1 - 0.01, 0), (x1, y1 - 0.01, 1.0), (x0, y1 - 0.01, 1.0)], out=(0, -1, 0))
    # The door, rolled up under the ceiling on its tracks.
    m.box("paint", (a + 0.05, y0 + 0.1, h - 0.12), (b - 0.05, y0 + 3.0, h - 0.06))
    for x in (a + 0.02, b - 0.06):
        m.box("iron", (x, y0, 0.0), (x + 0.04, y0 + 0.08, BH))
        m.box("iron", (x, y0, h - 0.14), (x + 0.04, y0 + 3.1, h - 0.1))
    # Two-post lift, its arms swung in.
    for x in (a + 0.15, b - 0.45):
        m.box("enamel", (x, 2.6, 0), (x + 0.3, 3.0, 3.1))
        m.box("iron", (x - 0.05, 2.55, 0), (x + 0.35, 3.05, 0.04))
        m.box("stainless", (x + 0.02, 2.5, 0.45), (x + 0.28, 2.6, 0.6))
        for dy in (-1.1, 0.9):
            m.box("iron", (x + 0.05, 2.75, 0.48), (x + 0.25, 2.75 + dy + (0.2 if dy < 0 else 0), 0.56))
    m.box("iron", (a + 0.15, 2.7, 3.05), (b - 0.15, 2.9, 3.15))
    # Bench along the back wall, a vice; a red tool chest; tyres stacked.
    m.box("wood", (a + 0.2, y1 - 0.7, 0.88), (b - 0.2, y1, 0.93))
    for x in (a + 0.25, b - 0.3):
        m.box("iron", (x, y1 - 0.65, 0), (x + 0.05, y1 - 0.05, 0.88))
    m.box("iron", (a + 0.25, y1 - 0.6, 0.25), (b - 0.25, y1 - 0.05, 0.28))
    m.box("steel", (a + 0.6, y1 - 0.75, 0.93), (a + 0.8, y1 - 0.6, 1.08))
    m.box("enamel", (b - 0.15 - 0.7, y1 - 1.25, 0), (b - 0.15, y1 - 0.8, 1.0))
    for k in range(5):
        z = 0.1 + k * 0.18
        m.box("dark", (b - 0.82, y1 - 1.26, z), (b - 0.18, y1 - 1.25, z + 0.02))
    for k in range(3):
        m.cyl("tyre", x0 + 0.45, y1 - 0.5, 0.33, k * 0.22, k * 0.22 + 0.21, seg=16)
    m.box("dark", (a + 0.3, y1 - 0.02, 1.3), (b - 0.3, y1 - 0.01, 2.4))  # the pegboard
    m.box("lamp", ((a + b) / 2 - 0.6, 2.8, h - 0.06), ((a + b) / 2 + 0.6, 2.95, h))


def closed_door(F, a, b):
    """The second bay's sectional door: four panels, the third glazed."""
    D_ = 0.18
    n = 4
    ph = BH / n
    wid = new_id()
    for k in range(n):
        z0, z1 = k * ph, (k + 1) * ph
        F.quad("dark", a, b, z0, z1, -D_ - 0.03)
        if k == 2:
            F.box("paint", a + 0.02, b - 0.02, z0 + 0.01, z0 + 0.14, -D_ - 0.02, -D_, skip=("back",))
            F.box("paint", a + 0.02, b - 0.02, z1 - 0.14, z1 - 0.01, -D_ - 0.02, -D_, skip=("back",))
            wn = 5
            gw = (b - a - 0.04) / wn
            for i in range(wn):
                u0 = a + 0.02 + i * gw
                F.box("paint", u0, u0 + 0.1, z0 + 0.14, z1 - 0.14, -D_ - 0.02, -D_, skip=("back",))
                pane(F, "glass", a, b, z0, z1, u0 + 0.1, u0 + gw, z0 + 0.14, z1 - 0.14, -D_ - 0.01, wid)
            F.box("paint", b - 0.12, b - 0.02, z0 + 0.14, z1 - 0.14, -D_ - 0.02, -D_, skip=("back",))
        else:
            F.box("paint", a + 0.02, b - 0.02, z0 + 0.01, z1 - 0.01, -D_ - 0.02, -D_, skip=("back",))
            for i in range(4):
                u0 = a + 0.12 + i * (b - a - 0.24) / 4
                F.box("paint", u0 + 0.04, u0 + (b - a - 0.24) / 4 - 0.04, z0 + 0.15, z1 - 0.15, -D_, -D_ + 0.02, skip=("back",))
    F.box("stainless", (a + b) / 2 - 0.2, (a + b) / 2 + 0.2, 0.9, 0.96, -D_, -D_ + 0.06)


# ---- canopy, islands, pumps -----------------------------------------------------------


def canopy(M, m):
    x0, x1, y0, y1 = CAN
    # The slab, its soffit and lights, a fascia of enamel all round with a
    # cream pinstripe and a stainless coping.
    m.box("paint", (x0 + 0.05, y0 + 0.05, CZ), (x1 - 0.05, y1 - 0.05, CF - 0.05), skip=("z0", "z1"))
    m.poly("paint", [(x0, y0, CZ), (x0, y1, CZ), (x1, y1, CZ), (x1, y0, CZ)], out=-Z)
    m.sweep("enamel", x1 - x0, y1 - y0, [(0.0, CZ), (0.06, CZ), (0.06, CF), (0.0, CF)], cx=(x0 + x1) / 2, cy=(y0 + y1) / 2)
    m.sweep("cream", x1 - x0, y1 - y0, [(0.06, CZ + 0.08), (0.075, CZ + 0.08), (0.075, CZ + 0.15), (0.06, CZ + 0.15)], cx=(x0 + x1) / 2, cy=(y0 + y1) / 2)
    m.sweep("stainless", x1 - x0, y1 - y0, [(-0.02, CF), (0.08, CF), (0.08, CF + 0.05), (-0.02, CF + 0.05)], cx=(x0 + x1) / 2, cy=(y0 + y1) / 2)
    m.poly("roof", [(x0 + 0.06, y0 + 0.06, CF - 0.05), (x1 - 0.06, y0 + 0.06, CF - 0.05), (x1 - 0.06, y1 - 0.06, CF - 0.05), (x0 + 0.06, y1 - 0.06, CF - 0.05)], out=Z)
    for x in ISL:
        for y in (y0 + 1.3, (y0 + y1) / 2, y1 - 1.3):
            for dx in (-1.6, 1.6):
                m.poly("lamp", [(x + dx - 0.6, y - 0.2, CZ - 0.01), (x + dx - 0.6, y + 0.2, CZ - 0.01), (x + dx + 0.6, y + 0.2, CZ - 0.01), (x + dx + 0.6, y - 0.2, CZ - 0.01)], out=-Z)
    # The station's name on the front fascia, from the app's sheet.
    F = Side(m, (0, y0 - 0.06, 0), (1, 0, 0), (0, -1, 0))
    F.quad("stationname", -3.9, 3.9, CZ + 0.24, CZ + 0.73, 0.004, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    # The columns, stainless, on the islands.
    for x in ISL:
        m.box("stainless", (x - 0.14, COL - 0.14, IS), (x + 0.14, COL + 0.14, CZ))
        m.box("stainless", (x - 0.2, COL - 0.2, IS), (x + 0.2, COL + 0.2, IS + 0.12))


def island(m, x):
    y0, y1 = ISY
    m.sweep("concrete", 1.1, y1 - y0, [(0.0, 0.0), (0.0, IS - 0.03), (-0.03, IS), (-0.04, IS)], cx=x, cy=(y0 + y1) / 2)
    m.poly("concrete", [(x - 0.51, y0 + 0.04, IS), (x + 0.51, y0 + 0.04, IS), (x + 0.51, y1 - 0.04, IS), (x - 0.51, y1 - 0.04, IS)], out=Z)
    for y in (y0 - 0.25, y1 + 0.25):
        m.cyl("enamel", x, y, 0.09, 0, 0.95, seg=12)
        m.cyl("cream", x, y, 0.095, 0.7, 0.8, seg=12, top=False)
    for y in PUMPS:
        pump(m, x, y)
    m.cyl("iron", x, (y0 + y1) / 2 + 0.55, 0.2, IS, IS + 0.75, seg=12)  # a bin by the column


def pump(m, x, y):
    """A pump of the late forties: enamel body, a cream head with a dial each side, a lit globe; a hose each side."""
    z = IS
    m.box("iron", (x - 0.27, y - 0.33, z), (x + 0.27, y + 0.33, z + 0.08))
    m.box("enamel", (x - 0.24, y - 0.3, z + 0.08), (x + 0.24, y + 0.3, z + 1.05))
    m.box("stainless", (x - 0.26, y - 0.32, z + 1.03), (x + 0.26, y + 0.32, z + 1.09))
    m.box("cream", (x - 0.23, y - 0.29, z + 1.09), (x + 0.23, y + 0.29, z + 1.55), skip=("z1",))
    m.sweep("cream", 0.46, 0.58, [(0.0, z + 1.55), (-0.03, z + 1.61), (-0.08, z + 1.65), (-0.14, z + 1.67)], cx=x, cy=y)
    m.poly("cream", [(x - 0.09, y - 0.15, z + 1.67), (x + 0.09, y - 0.15, z + 1.67), (x + 0.09, y + 0.15, z + 1.67), (x - 0.09, y + 0.15, z + 1.67)], out=Z)
    m.cyl("stainless", x, y, 0.09, z + 1.67, z + 1.73, seg=14)
    m.cyl("lamp", x, y, 0.15, z + 1.73, z + 2.02, seg=16, r1=0.11)
    for s in (-1, 1):
        F = Side(m, (x + s * 0.23, y, 0), (0, s, 0), (s, 0, 0))
        F.box("stainless", -0.2, 0.2, z + 1.15, z + 1.47, 0, 0.015)
        F.quad("dark", -0.17, 0.17, z + 1.18, z + 1.44, 0.016)
        F.box("cream", -0.13, 0.13, z + 1.36, z + 1.41, 0.016, 0.02)
        F.box("lamp", -0.08, 0.08, z + 1.22, z + 1.28, 0.016, 0.02)
        F.box("dark", -0.18, 0.18, z + 0.55, z + 0.85, 0.01, 0.015)  # the maker's plate
        # The nozzle in its holster, the hose looping down from the head.
        F.box("stainless", -0.27, -0.17, z + 0.82, z + 1.0, 0.01, 0.1)
        F.box("iron", -0.25, -0.19, z + 0.9, z + 1.12, 0.06, 0.14)
        hose = [F.p(0.22, z + 1.0, 0.03), F.p(0.26, z + 0.7, 0.12), F.p(0.15, z + 0.3, 0.22), F.p(-0.05, z + 0.25, 0.24), F.p(-0.18, z + 0.45, 0.2), F.p(-0.22, z + 0.85, 0.1)]
        m.tube("rubber", hose, 0.018, F.n.cross(Z), closed=False, seg=5)


def pylon(m):
    """The sign at the lot's corner: two enamel posts, a lit price board, a tall box with GAS down it under a neon edge."""
    x, y = PY
    m.box("concrete", (x - 0.8, y - 0.35, 0), (x + 0.8, y + 0.35, 0.45))
    for dx in (-0.45, 0.45):
        m.box("enamel", (x + dx - 0.08, y - 0.08, 0.45), (x + dx + 0.08, y + 0.08, 3.0))
    m.box("dark", (x - 0.6, y - 0.1, 1.9), (x + 0.6, y + 0.1, 2.85))
    m.box("stainless", (x - 0.62, y - 0.12, 2.85), (x + 0.62, y + 0.12, 2.9))
    m.box("stainless", (x - 0.62, y - 0.12, 1.85), (x + 0.62, y + 0.12, 1.9))
    z0, z1 = 3.0, 6.6
    m.box("enamel", (x - 0.65, y - 0.15, z0), (x + 0.65, y + 0.15, z1))
    m.box("stainless", (x - 0.7, y - 0.2, z1), (x + 0.7, y + 0.2, z1 + 0.06))
    for s in (-1, 1):
        F = Side(m, (x, y + s * 0.15, 0), (-s, 0, 0), (0, s, 0))
        for k, zz in enumerate((2.65, 2.35, 2.05)):
            F.box("lamp", -0.5, 0.1, zz - 0.07, zz + 0.07, 0.1, 0.105)
            F.box("lamp", 0.2, 0.5, zz - 0.07, zz + 0.07, 0.1, 0.105)
        F.box("cream", -0.5, 0.5, z0 + 0.2, z1 - 0.2, 0, 0.02)
        for k, ch in enumerate("GAS"):
            letters(m, "enamel", F, 0, z1 - 0.75 - k * 1.05, 0.02, ch, 0.85, depth=0.04, offset=0.01)
        loop = [F.p(-0.58, z0 + 0.08, 0.03), F.p(0.58, z0 + 0.08, 0.03), F.p(0.58, z1 - 0.08, 0.03), F.p(-0.58, z1 - 0.08, 0.03)]
        m.tube("neon", loop, 0.02, F.n, seg=5)


def furniture(m):
    # The air and water post by the office's corner, its hose coiled on a hook.
    x, y = -5.6, -0.9
    m.box("concrete", (x - 0.25, y - 0.25, 0), (x + 0.25, y + 0.25, 0.12))
    m.cyl("enamel", x, y, 0.12, 0.12, 1.3, seg=14)
    m.cyl("cream", x, y, 0.17, 1.3, 1.5, seg=16)
    m.cyl("stainless", x, y, 0.13, 1.5, 1.56, seg=16)
    F = Side(m, (x, y - 0.17, 0), (1, 0, 0), (0, -1, 0))
    F.quad("dark", -0.1, 0.1, 1.34, 1.46, 0.002)
    ring = [Vector((x + 0.22 * math.cos(a), y - 0.14, 0.95 + 0.22 * math.sin(a))) for a in [k / 10 * math.tau for k in range(10)]]
    m.tube("rubber", ring, 0.016, (0, 1, 0), seg=5)
    # A rack of oil cans before the office window.
    x0, x1, y0 = -4.6, -3.4, YF - 0.45
    for xx in (x0, x1):
        m.box("iron", (xx - 0.02, y0 - 0.2, 0), (xx + 0.02, y0 + 0.2, 1.1))
    for k, (z, dy) in enumerate(((0.3, -0.12), (0.65, 0.0), (1.0, 0.12))):
        m.box("iron", (x0, y0 - 0.2 + dy, z - 0.02), (x1, y0 + 0.1 + dy, z))
        for i in range(6):
            cx = x0 + 0.12 + i * 0.19
            m.cyl("enamel" if (i + k) % 2 else "cream", cx, y0 - 0.05 + dy, 0.075, z, z + 0.2, seg=10)
            m.cyl("stainless", cx + 0.03, y0 - 0.05 + dy, 0.015, z + 0.2, z + 0.24, seg=6)
    # An ice chest by the door, ICE on its front.
    x, y = -1.4, YF - 0.45
    m.box("cream", (x - 0.45, y - 0.35, 0.1), (x + 0.45, y + 0.35, 1.0))
    m.box("enamel", (x - 0.47, y - 0.37, 1.0), (x + 0.47, y + 0.37, 1.08))
    for dx in (-0.4, 0.4):
        m.box("iron", (x + dx - 0.03, y - 0.3, 0), (x + dx + 0.03, y + 0.3, 0.1))
    F = Side(m, (x, y - 0.35, 0), (1, 0, 0), (0, -1, 0))
    letters(m, "enamel", F, 0, 0.6, 0, "ICE", 0.36, depth=0.03, offset=0.006)
    # Tyres for sale on a stand by the pier between the bays.
    x, y = (BAYS[0][1] + BAYS[1][0]) / 2, YF - 0.5
    m.box("iron", (x - 0.25, y - 0.3, 0), (x + 0.25, y + 0.3, 0.06))
    for k in range(4):
        m.cyl("tyre", x, y, 0.32, 0.06 + k * 0.21, 0.26 + k * 0.21, seg=18)
    m.cyl("dark", x, y, 0.16, 0.06, 0.06 + 4 * 0.21 + 0.005, seg=12)


# ---- roof -----------------------------------------------------------------------------


def roof(M):
    m = M.m
    W = walls(m)
    pz = TOP + 0.75  # parapet top
    deck = TOP + 0.2
    fac = facets(m)
    side_end = CY - YF - R
    runs = [
        (W["left"], -CY + YF, side_end),
        *[(F, 0, L) for F, L in fac],
        (W["front"], XL + R, XR),
        (W["right"], -CY + YF, CY - YF),
        (W["back"], XL, XR),
    ]
    for F, u0, u1 in runs:
        F.quad("cream", u0, u1, TOP, pz)
        F.quad("cream", u1, u0, deck, pz, -0.25, out=-F.n)
    # The band of colour and the coping, mitred round the plan.
    plan = outline()
    m.psweep("enamel", plan, [(0.0, TOP + 0.12), (0.06, TOP + 0.12), (0.06, TOP + 0.6), (0.0, TOP + 0.6)])
    m.psweep("stainless", plan, [(-0.25, pz), (0.08, pz), (0.08, pz + 0.05), (-0.25, pz + 0.05), (-0.25, pz)])
    # SERVICE over the bays, in cream on the band.
    F = W["front"]
    letters(m, "cream", F, (BAYS[0][0] + BAYS[1][1]) / 2, TOP + 0.36, 0.06, "SERVICE", 0.34, depth=0.03, offset=0.006, spacing=1.25)
    # The deck.
    inner = [(p.x - n.x * 0.25, p.y - n.y * 0.25) for p, n in arc()]
    poly = [*inner, (XR - 0.25, YF + 0.25), (XR - 0.25, YB - 0.25), (XL + 0.25, YB - 0.25)]
    m.poly("roof", [(x, y, deck) for x, y in poly], out=Z)
    fin(m, deck)
    # Plant: a vent over the bays, an extract fan, a hatch, a stub stack.
    m.box("ac", (2.0, 3.6, deck), (3.2, 4.6, deck + 0.8))
    m.cyl("dark", 2.6, 4.1, 0.35, deck + 0.8, deck + 0.82, seg=16)
    m.box("concrete", (1.9, 3.5, deck), (3.3, 4.7, deck + 0.08))
    m.cyl("ac", 0.6, 2.4, 0.25, deck, deck + 0.5, seg=12)
    m.cyl("steel", 0.6, 2.4, 0.32, deck + 0.5, deck + 0.56, seg=12)
    m.box("wood", (-1.6, 4.4, deck), (-0.8, 5.2, deck + 0.35))
    m.box("steel", (-1.65, 4.35, deck + 0.35), (-0.75, 5.25, deck + 0.4))
    m.cyl("ac", 4.8, 5.4, 0.08, deck, deck + 0.9, seg=10)
    m.cyl("ac", 4.8, 5.4, 0.12, deck + 0.9, deck + 1.0, seg=10)


def fin(m, deck):
    """The tower over the office's corner: a slab fin with round ends, three speed lines round it, a neon tube up its nose."""
    x, y0, y1 = XL + R - 0.1, YF + 0.6, YF + 2.0  # the centres of its nose and tail
    t = 0.24  # half its thickness
    z1 = TOP + 5.4

    def body(role, z0, z1_, grow=0.0):
        m.box(role, (x - t - grow, y0, z0), (x + t + grow, y1, z1_), skip=("y0", "y1"))
        for y in (y0, y1):
            m.cyl(role, x, y, t + grow, z0, z1_, seg=20)

    body("cream", deck, z1)
    # Speed lines near the top, the band at its foot, a stainless cap.
    for k in range(3):
        z = z1 - 1.1 - k * 0.38
        body("enamel", z, z + 0.16, 0.03)
    body("enamel", deck, TOP + 1.3, 0.03)
    body("stainless", z1, z1 + 0.08, 0.05)
    # The neon up the nose, from the band to the speed lines, on stand-offs.
    ny = y0 - t - 0.07
    m.tube("neon", [(x, ny, TOP + 1.45), (x, ny, z1 - 2.05)], 0.03, (1, 0, 0), closed=False, seg=6)
    for z in (TOP + 1.55, (TOP + z1) / 2, z1 - 2.15):
        m.box("stainless", (x - 0.02, ny, z), (x + 0.02, y0 - t + 0.01, z + 0.04))
