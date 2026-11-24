# C7, half-timbered house: an English Tudor timber-framed house of two
# storeys. A brick plinth, square-panelled oak framing with corner braces
# below, and the upper storey jettied out over the street on carved joist
# ends, close-studded; a cross gable over the right bay jetties out again.
# Limewashed infill, leaded casements with diamond quarries, a steep
# plain-tile roof with barge boards, and a brick stack on the left gable
# with two octagonal shafts. An oak plank door under a little tiled
# canopy. The app tints infill, oak, tiles and door per house; the garden
# is drawn round it.
#
# Pieces (base at the origin):
#   ground  the ground storey: plinth, framing, windows, door, the stack's foot
#   upper   the jettied upper storey, from the first floor to the wall plate
#   roof    the roof, gables, the cross gable, the stack's top
import math

from mathutils import Vector

from lib import Model, Side, Z, fpoly, new_id, pane, sides

ID = "c7"
W, D = 8.6, 6.0  # ground storey
JET = 0.45  # the upper storey's jetty over the front
Y0 = -2.75  # ground storey's front: the canopy in front, the stack's side keep it centred
Y1 = Y0 + D
YU = Y0 - JET  # upper storey's front
G = 3.0  # first floor
PLATE = 5.6
PLINTH = 0.55
PITCH = math.radians(48)
K = math.tan(PITCH)
EAVE, RAKE = 0.32, 0.3
T = 0.16
CYU = (YU + Y1) / 2  # the ridge's line
RIDGE = PLATE + T + (Y1 - YU) / 2 * K  # roof surface at the ridge
XG, HG = 2.3, 1.6  # cross gable: centre, half width
GJ = 0.3  # its jetty
ZG = PLATE + T + HG * K  # its ridge
DOOR = (-1.05, -0.15)
DEPTH = 0.1


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("upper", (0, 0, G))
    upper(M)
    M.piece("roof", (0, 0, PLATE))
    roof(M)
    M.export(out, bake)


# ---- framing ------------------------------------------------------------------------


def cut(z0, z1, u0, u1, holes):
    """The parts of [z0, z1] a vertical timber across u0..u1 keeps, clear of the openings."""
    spans = [(z0, z1)]
    for a, b, c, e in holes:
        if u1 <= a or u0 >= b:
            continue
        out = []
        for s0, s1 in spans:
            if s1 <= c or s0 >= e:
                out.append((s0, s1))
                continue
            if s0 < c:
                out.append((s0, c))
            if s1 > e:
                out.append((e, s1))
        spans = out
    return [(s0, s1) for s0, s1 in spans if s1 - s0 > 0.06]


def hcut(u0, u1, z0, z1, holes):
    """The parts of [u0, u1] a horizontal timber across z0..z1 keeps, clear of the openings."""
    spans = [(u0, u1)]
    for a, b, c, e in holes:
        if z1 <= c or z0 >= e:
            continue
        out = []
        for s0, s1 in spans:
            if s1 <= a or s0 >= b:
                out.append((s0, s1))
                continue
            if s0 < a:
                out.append((s0, a))
            if s1 > b:
                out.append((b, s1))
        spans = out
    return [(s0, s1) for s0, s1 in spans if s1 - s0 > 0.06]


def framing(F, h, z0, z1, opens, step, rail=None, braces=False, top=None):
    """Oak framing on a wall face from -h to h, z0 to z1: plates, corner posts, studs every `step`
    (cut round the openings), a mid rail, frames round each opening and, if asked, corner braces.
    `top(u)` caps the studs under a gable's rake."""
    o = 0.035
    holes = [(a - 0.12, b + 0.12, c - 0.12, e + 0.12) for a, b, c, e in opens]
    for a, b, c, e in opens:
        for u0, u1 in ((a - 0.12, a), (b, b + 0.12)):
            for s0, s1 in cut(z0, z1 if top is None else min(top(u0), top(u1)) - 0.05, u0, u1, [(a - 0.13, b + 0.13, -9, -8)]):
                F.box("oak", u0, u1, s0, s1, 0, o)
        F.box("oak", a, b, c - 0.12, c, 0, o)
        F.box("oak", a, b, e, e + 0.12, 0, o)
    if top is None:
        F.box("oak", -h, h, z0, z0 + 0.18, 0, o + 0.01)
        F.box("oak", -h, h, z1 - 0.18, z1, 0, o + 0.01)
        for u0, u1 in ((-h, -h + 0.24), (h - 0.24, h)):
            F.box("oak", u0, u1, z0, z1, 0, o + 0.005)
    else:
        F.box("oak", -h, h, z0, z0 + 0.18, 0, o + 0.01)
    n = max(1, round((2 * h - 0.48) / step))
    for i in range(1, n):
        u = -h + 0.24 + i * (2 * h - 0.48) / n
        u0, u1 = u - 0.08, u + 0.08
        zt = z1 - 0.18 if top is None else min(top(u0), top(u1)) - 0.05
        if any(a - 0.24 < u < b + 0.24 for a, b, c, e in opens):
            if any(a - 0.12 < u1 and u0 < b + 0.12 for a, b, c, e in opens):
                for s0, s1 in cut(z0 + 0.18, zt, u0, u1, holes):
                    F.box("oak", u0, u1, s0, s1, 0, o)
                continue
        if zt > z0 + 0.3:
            F.box("oak", u0, u1, z0 + 0.18, zt, 0, o)
    if rail is not None:
        for s0, s1 in hcut(-h + 0.24, h - 0.24, rail, rail + 0.15, holes):
            F.box("oak", s0, s1, rail, rail + 0.15, 0, o + 0.004)
    if braces:
        for s in (-1, 1):
            a = F.p(s * (h - 0.24), z0 + 0.18 + 0.1, o / 2 + 0.003)
            b = F.p(s * (h - 0.24 - 1.0), (rail if rail else z1 - 0.18) - 0.02, o / 2 + 0.003)
            F.m.strut("oak", a, b, o + 0.004, 0.16)


def leaded(F, a, b, c, e, n, wid):
    """n leaded casement lights between oak mullions in (a..b, c..e): a diamond lattice of lead cames."""
    mw = 0.08
    L = (b - a - (n - 1) * mw) / n
    d = -DEPTH
    for i in range(n):
        u0 = a + i * (L + mw)
        u1 = u0 + L
        if i:
            F.box("oak", u0 - mw, u0, c, e, d - 0.04, 0.0, skip=())
        F.box("iron", u0, u0 + 0.03, c, e, d, d + 0.04)
        F.box("iron", u1 - 0.03, u1, c, e, d, d + 0.04)
        F.box("iron", u0 + 0.03, u1 - 0.03, c, c + 0.03, d, d + 0.04)
        F.box("iron", u0 + 0.03, u1 - 0.03, e - 0.03, e, d, d + 0.04)
        pane(F, "glass", a, b, c, e, u0 + 0.03, u1 - 0.03, c + 0.03, e - 0.03, d + 0.01, wid)
        # Diamonds 0.13 wide, 0.2 tall: lines u = u_k +- z * 0.65, clipped to the light.
        ga, gb, gc, ge = u0 + 0.03, u1 - 0.03, c + 0.03, e - 0.03
        k = 0.65
        for sgn in (1, -1):
            j = -int((ge - gc) * k / 0.13) - 2
            while True:
                base = ga + j * 0.13  # u at z = gc
                pts = []
                # Clip the line u = base + sgn*(z - gc)*k to the rectangle.
                for z in (gc, ge):
                    pts.append((base + sgn * (z - gc) * k, z))
                (ua, za), (ub, zb) = pts
                if min(ua, ub) > gb:
                    break
                j += 1
                if max(ua, ub) < ga:
                    continue
                # Trim both ends into [ga, gb].
                def clip(u, z, uo, zo):
                    if u < ga:
                        z = z + (ga - u) / (uo - u) * (zo - z)
                        u = ga
                    elif u > gb:
                        z = z + (gb - u) / (uo - u) * (zo - z)
                        u = gb
                    return u, z
                ua2, za2 = clip(ua, za, ub, zb)
                ub2, zb2 = clip(ub, zb, ua, za)
                if math.hypot(ub2 - ua2, zb2 - za2) < 0.05:
                    continue
                F.m.strut("lead", F.p(ua2, za2, d + 0.025), F.p(ub2, zb2, d + 0.025), 0.012, 0.012)
    F.box("oak", a - 0.04, b + 0.04, c - 0.08, c, d, 0.05)


def window(F, a, b, c, e, n):
    leaded(F, a, b, c, e, n, new_id())


# ---- ground storey ------------------------------------------------------------------


def ground(M):
    m = M.m
    walls = sides(m, W, D, cy=(Y0 + Y1) / 2)
    c, e = 1.0, 2.25
    wins = {
        "front": [(-3.4, -1.8, 3), (1.2, 3.4, 4)],
        "back": [(-3.2, -2.0, 2), (1.6, 2.8, 2)],
        "left": [(1.2, 2.0, 1)],
        "right": [(-1.4, 0.0, 2)],
    }
    doors = {"front": DOOR, "back": (-0.9, -0.05)}
    for name, F in walls.items():
        h = W / 2 if name in ("front", "back") else D / 2
        opens = [(a, b, c, e) for a, b, _ in wins[name]]
        hs = [(a, b, c, e, DEPTH) for a, b, c, e in opens]
        if name in doors:
            a, b = doors[name]
            hs.append((a, b, 0.25, 2.25, DEPTH))
            opens.append((a, b, 0.25, 2.25))
        bricks = [h_ for h_ in hs if h_[2] < PLINTH]
        F.wall("brick", -h, h, 0, PLINTH, [(a, b, 0.25, PLINTH, DEPTH) for a, b, *_ in bricks], depth=DEPTH)
        F.box("stone", -h - 0.03, h + 0.03, PLINTH - 0.04, PLINTH, 0, 0.05)
        F.wall("render", -h, h, PLINTH, G, [(a, b, max(c_, PLINTH), e_, d) for a, b, c_, e_, d in hs], depth=DEPTH, reveal="oak")
        framing(F, h, PLINTH, G, [(a, b, c_, e_) for a, b, c_, e_ in opens], 1.05, rail=1.55, braces=True)
        for a, b, n in wins[name]:
            window(F, a, b, c, e, n)
    for name, (a, b) in doors.items():
        F = walls[name]
        door(F, a, b, 0.25, 2.25)
        F.box("stone", a - 0.2, b + 0.2, 0, 0.25, 0, 0.32, skip=("back", "bottom"))
    canopy(walls["front"], DOOR[0] - 0.35, DOOR[1] + 0.35)
    stack(m, 0, G)
    m.poly("dark", [(-W / 2, Y0, G - 0.2), (W / 2, Y0, G - 0.2), (W / 2, Y1, G - 0.2), (-W / 2, Y1, G - 0.2)], out=Z)


def door(F, a, b, c, t):
    """An oak plank door with studded battens under a four-centred head, carved spandrels above."""
    d = -DEPTH
    F.quad("door", a, b, c, t - 0.18, d + 0.01)
    mid = (a + b) / 2
    # The head: two flat arcs rising to a point, as a polygon of door in the top of the opening.
    pts = [(a, t - 0.18), (b, t - 0.18), (b, t - 0.08), (mid + 0.15, t - 0.01), (mid, t), (mid - 0.15, t - 0.01), (a, t - 0.08)]
    fpoly(F, "door", pts, w=d + 0.01)
    fpoly(F, "oak", [(a, t - 0.08), (mid - 0.15, t - 0.01), (mid, t), (a, t)], w=d + 0.012)
    fpoly(F, "oak", [(b, t - 0.08), (b, t), (mid, t), (mid + 0.15, t - 0.01)], w=d + 0.012)
    for k in range(1, 5):
        u = a + k * (b - a) / 5
        F.box("dark", u - 0.006, u + 0.006, c + 0.02, t - 0.1, d + 0.01, d + 0.014)
    for z in (c + 0.35, c + 1.0, t - 0.5):
        F.box("door", a + 0.05, b - 0.05, z, z + 0.1, d + 0.01, d + 0.04)
        for i in range(5):
            u = a + 0.1 + i * (b - a - 0.2) / 4
            F.box("iron", u - 0.015, u + 0.015, z + 0.035, z + 0.065, d + 0.04, d + 0.055)
    F.box("iron", b - 0.16, b - 0.1, c + 0.95, c + 1.07, d + 0.01, d + 0.05)


def canopy(F, u0, u1):
    """A tiled pentice over the door on two oak brackets."""
    m = F.m
    zw, depth, drop = 2.95, 0.7, 0.35
    zf = zw - drop
    a, b = F.p(u0, zf, depth), F.p(u1, zf, depth)
    m.poly("plaintile", [a + Z * 0.06, b + Z * 0.06, F.p(u1, zw + 0.06, 0), F.p(u0, zw + 0.06, 0)], out=Z + F.n)
    m.poly("oak", [a, b, F.p(u1, zw, 0), F.p(u0, zw, 0)], out=-Z)
    F.box("oak", u0, u1, zf - 0.04, zf + 0.06, depth - 0.04, depth)
    for u, s in ((u0, -F.t), (u1, F.t)):
        m.poly("oak", [F.p(u, zf - 0.04, depth), F.p(u, zw - 0.04, 0), F.p(u, zw + 0.06, 0), F.p(u, zf + 0.06, depth)], out=s)
    for u in (u0 + 0.08, u1 - 0.08):
        m.strut("oak", F.p(u, zw - 0.8, 0.05), F.p(u, zf - 0.03, depth - 0.12), 0.08)


# ---- upper storey ---------------------------------------------------------------------


def upper(M):
    m = M.m
    cy = (YU + Y1) / 2
    walls = sides(m, W, Y1 - YU, cy=cy)
    c, e = G + 0.85, G + 2.05
    wins = {
        "front": [(-3.3, -1.9, 3), (-1.0, -0.1, 2), (1.5, 3.1, 4)],
        "back": [(-2.9, -1.7, 2), (1.2, 2.4, 2)],
        "left": [(1.4, 2.2, 1)],
        "right": [(-1.6, -0.2, 2)],
    }
    for name, F in walls.items():
        h = W / 2 if name in ("front", "back") else (Y1 - YU) / 2
        opens = [(a, b, c, e) for a, b, _ in wins[name]]
        F.wall("render", -h, h, G, PLATE, [(a, b, c, e, DEPTH) for a, b, c, e in opens], depth=DEPTH, reveal="oak")
        framing(F, h, G, PLATE, opens, 0.42, rail=c - 0.15 if name == "front" else None)
        for a, b, n in wins[name]:
            window(F, a, b, c, e, n)
    # The jetty: joist ends along the front under a moulded bressumer, a soffit back to the ground storey.
    F = walls["front"]
    F.box("oak", -W / 2, W / 2, G - 0.06, G + 0.18, 0, 0.06)
    n = 22
    for i in range(n):
        u = -W / 2 + 0.15 + i * (W - 0.3) / (n - 1)
        m.box("oak", (u - 0.07, YU + 0.02, G - 0.24), (u + 0.07, Y0, G - 0.06), skip=("y1",))
    m.poly("render", [(-W / 2, YU + 0.02, G - 0.24), (W / 2, YU + 0.02, G - 0.24), (W / 2, Y0, G - 0.24), (-W / 2, Y0, G - 0.24)], out=-Z)
    for x, s in ((-W / 2, -1), (W / 2, 1)):
        m.box("oak", (x - (0.04 if s < 0 else 0), YU, G - 0.26), (x + (0.04 if s > 0 else 0), Y0, G - 0.04), skip=())
        # A dragon post's bracket at each corner.
        m.strut("oak", (x - s * 0.1, Y0 - 0.02, G - 1.1), (x - s * 0.1, YU + 0.15, G - 0.26), 0.12, 0.12)
    stack(m, G, PLATE)
    m.poly("dark", [(-W / 2, YU, PLATE - 0.02), (W / 2, YU, PLATE - 0.02), (W / 2, Y1, PLATE - 0.02), (-W / 2, Y1, PLATE - 0.02)], out=Z)


def stack(m, z0, z1):
    """The brick stack on the left gable, outside the wall: a broad breast that steps in once."""
    x = -W / 2
    yc = (YU + Y1) / 2 + 0.2
    if z0 < 3.6:
        za, zb = z0, min(z1, 3.6)
        m.box("brick", (x - 0.65, yc - 0.9, za), (x, yc + 0.9, zb), skip=("x1",) + (("z0",) if za == 0 else ()))
    if z1 > 3.6:
        za = max(z0, 3.6)
        if za == 3.6:
            m.poly("plaintile", [(x - 0.65, yc - 0.9, 3.6), (x - 0.65, yc + 0.9, 3.6), (x - 0.5, yc + 0.6, 3.85), (x - 0.5, yc - 0.6, 3.85)], out=(-1, 0, 1))
            for s in (-1, 1):
                m.poly("plaintile", [(x - 0.65, yc + s * 0.9, 3.6), (x, yc + s * 0.9, 3.6), (x, yc + s * 0.6, 3.85), (x - 0.5, yc + s * 0.6, 3.85)], out=(0, s, 1))
        m.box("brick", (x - 0.5, yc - 0.6, za), (x, yc + 0.6, z1), skip=("x1", "z0"))


# ---- roof ---------------------------------------------------------------------------


def zf(y):
    return PLATE + T + (y - YU) * K


def zb(y):
    return PLATE + T + (Y1 - y) * K


def plane(m, pts, role="plaintile"):
    P = [Vector(p) for p in pts]
    a, b = P[0], P[1]
    tt = (b - a).normalized()
    n = (P[1] - P[0]).cross(P[2] - P[0])
    if n.z < 0:
        n = -n
    uvs = []
    for X in P:
        d = X - a
        u = d.dot(tt)
        uvs.append((u, (d - tt * u).length))
    m.poly(role, P, out=n, uvs=uvs)


def barge(m, pts, out, drop=0.22):
    """An oak barge board under a rake line of points, `drop` deep, two faces and its underside."""
    P = [Vector(p) for p in pts]
    o = Vector(out).normalized() * 0.04
    for a, b in zip(P, P[1:]):
        m.poly("oak", [a - Z * drop, b - Z * drop, b + Z * 0.04, a + Z * 0.04], out=out)
        m.poly("oak", [a - Z * drop - o, b - Z * drop - o, b + Z * 0.04 - o, a + Z * 0.04 - o], out=-Vector(out))
        m.poly("oak", [a - Z * drop, b - Z * drop, b - Z * drop - o, a - Z * drop - o], out=-Z)


def roof(M):
    m = M.m
    x0, x1 = -W / 2 - RAKE, W / 2 + RAKE
    ye0, ye1 = YU - EAVE, Y1 + EAVE
    xa, xb = XG - HG, XG + HG
    # Front slope: full strips beside the cross gable, above its valleys between its walls.
    yr = YU + (ZG - zf(YU)) / K
    for xs in ((x0, xa), (xb, x1)):
        plane(m, [(xs[0], ye0, zf(ye0)), (xs[1], ye0, zf(ye0)), (xs[1], CYU, RIDGE), (xs[0], CYU, RIDGE)])
        m.poly("oak", [(xs[0], ye0, zf(ye0) - T - 0.04), (xs[1], ye0, zf(ye0) - T - 0.04), (xs[1], ye0, zf(ye0)), (xs[0], ye0, zf(ye0))], out=(0, -1, 0))
        m.poly("oak", [(xs[0], ye0, zf(ye0) - T), (xs[1], ye0, zf(ye0) - T), (xs[1], YU, PLATE), (xs[0], YU, PLATE)], out=(0, 0.3, -1))
    for s in (-1, 1):
        xo = XG + s * HG
        pts = [(xo, YU, zf(YU)), (XG, yr, ZG), (XG, CYU, RIDGE), (xo, CYU, RIDGE)]
        plane(m, pts if s < 0 else pts[::-1])
    plane(m, [(x1, ye1, zb(ye1)), (x0, ye1, zb(ye1)), (x0, CYU, RIDGE), (x1, CYU, RIDGE)])
    m.poly("oak", [(x1, ye1, zb(ye1) - T - 0.04), (x0, ye1, zb(ye1) - T - 0.04), (x0, ye1, zb(ye1)), (x1, ye1, zb(ye1))], out=(0, 1, 0))
    m.poly("oak", [(x1, ye1, zb(ye1) - T), (x0, ye1, zb(ye1) - T), (x0, Y1, PLATE), (x1, Y1, PLATE)], out=(0, -0.3, -1))
    # Ridge tiles: half-round, in the roof's clay.
    m.tube("plaintile", [(x0, CYU, RIDGE + 0.02), (x1, CYU, RIDGE + 0.02)], 0.11, (0, 1, 0), closed=False, seg=8)
    # Gable ends: framed and rendered, barge boards under the rakes, a finial.
    for x, s in ((-W / 2, -1), (W / 2, 1)):
        Gs = Side(m, (x, CYU, 0), (0, -s, 0), (s, 0, 0))
        h = (Y1 - YU) / 2
        top = lambda u, h=h: PLATE + T + (h - abs(u)) * K  # noqa: E731
        fpoly(Gs, "render", [(-h, PLATE), (h, PLATE), (h, top(h)), (0, top(0)), (-h, top(-h))])
        framing(Gs, h, PLATE, RIDGE, [(-0.35, 0.35, PLATE + 1.0, PLATE + 1.9)] if s > 0 else [], 0.42, top=lambda u, top=top: top(u) - 0.02)
        if s > 0:
            leaded(Gs, -0.35, 0.35, PLATE + 1.0, PLATE + 1.9, 1, new_id())
        for ya in (ye0, ye1):
            xe = x + s * RAKE
            barge(m, [(xe, ya, (zf if ya == ye0 else zb)(ya) + 0.02), (xe, CYU, RIDGE + 0.02)], (s, 0, 0))
        # The rake's verge: the roof's edge as a face.
        for ya in (ye0, ye1):
            xe = x + s * RAKE
            z = (zf if ya == ye0 else zb)(ya)
            m.poly("plaintile", [(xe, ya, z - T), (xe, CYU, RIDGE - T), (xe, CYU, RIDGE), (xe, ya, z)], out=(s, 0, 0))
            m.poly("oak", [(xe, ya, z - T), (xe, CYU, RIDGE - T), (x, CYU, RIDGE - T), (x, ya, z - T)], out=(0, 0, -1))
        m.cyl("oak", x + s * (RAKE - 0.02), CYU, 0.06, RIDGE - 0.3, RIDGE + 0.45, seg=8, r1=0.02)
    cross_gable(m, yr)
    # The stack's top: up past the rake, two octagonal shafts on a corbelled base.
    x = -W / 2
    yc = CYU + 0.2
    zt = RIDGE + 0.5
    m.box("brick", (x - 0.5, yc - 0.6, PLATE), (x, yc + 0.6, zt), skip=("z0",))
    m.box("brick", (x + 0.0, yc - 0.6, zb(yc + 0.6)), (x + 0.35, yc + 0.6, zt), skip=("z0",))
    m.box("brick", (x - 0.56, yc - 0.66, zt), (x + 0.41, yc + 0.66, zt + 0.12), skip=())
    for dy in (-0.3, 0.3):
        cx = x - 0.07
        m.cyl("brick", cx, yc + dy, 0.24, zt + 0.12, zt + 1.4, seg=8, uv=True)
        m.cyl("brick", cx, yc + dy, 0.3, zt + 1.4, zt + 1.55, seg=8, uv=True)
        m.cyl("terracotta", cx, yc + dy, 0.13, zt + 1.55, zt + 1.75, seg=8)


def cross_gable(m, yr):
    """The cross gable over the right bay: jettied out again on two brackets, framed, a window, barge boards."""
    yf = YU - GJ
    F = Side(m, (XG, yf, 0), (1, 0, 0), (0, -1, 0))
    top = lambda u: PLATE + T + (HG - abs(u)) * K  # noqa: E731
    fpoly(F, "render", [(-HG, PLATE), (HG, PLATE), (HG, top(HG)), (0, top(0)), (-HG, top(-HG))])
    op = [(-0.55, 0.55, PLATE + 0.55, PLATE + 1.35)]
    F.wall("render", -0.6, 0.6, PLATE + 0.5, PLATE + 1.4, [(-0.55, 0.55, PLATE + 0.55, PLATE + 1.35, DEPTH)], depth=DEPTH, reveal="oak")
    framing(F, HG, PLATE, ZG, op, 0.42, top=lambda u: top(u) - 0.02)
    leaded(F, -0.55, 0.55, PLATE + 0.55, PLATE + 1.35, 2, new_id())
    # The jetty under it: a bressumer, the soffit, two brackets down to the bressumer below.
    F.box("oak", -HG - 0.05, HG + 0.05, PLATE - 0.22, PLATE + 0.02, -0.02, 0.06)
    m.poly("oak", [(XG - HG, yf, PLATE - 0.22), (XG + HG, yf, PLATE - 0.22), (XG + HG, YU, PLATE - 0.22), (XG - HG, YU, PLATE - 0.22)], out=-Z)
    for s in (-1, 1):
        m.poly("render", [(XG + s * HG, yf, PLATE - 0.22), (XG + s * HG, YU, PLATE - 0.22), (XG + s * HG, YU, top(HG)), (XG + s * HG, yf, top(HG))], out=(s, 0, 0))
        m.strut("oak", (XG + s * (HG - 0.15), YU - 0.02, PLATE - 0.9), (XG + s * (HG - 0.15), yf + 0.1, PLATE - 0.22), 0.12, 0.12)
    # Its roof: from the barge boards back to the valleys in the main front slope.
    ov = 0.25
    ye = YU + (zf(YU) - ov * K - zf(YU)) / K  # where the eave line meets the main slope
    for s in (-1, 1):
        xe = XG + s * (HG + ov)
        ze = PLATE + T - ov * K
        ys = yf - 0.2
        pts = [(xe, ys, ze), (xe, ye, ze), (XG, yr, ZG), (XG, ys, ZG)]
        plane(m, pts if s > 0 else [pts[1], pts[0], pts[3], pts[2]])
        m.poly("oak", [(xe, ys, ze - T), (xe, ye, ze - T), (XG + s * HG, ye, ze - T + ov * K), (XG + s * HG, ys, ze - T + ov * K)], out=(0, 0, -1))
        m.poly("plaintile", [(xe, ys, ze - T), (xe, ye, ze - T), (xe, ye, ze), (xe, ys, ze)], out=(s, 0, 0))
        barge(m, [(xe, ys, ze + 0.02), (XG, ys, ZG + 0.02)], (0, -1, 0))
        m.poly("plaintile", [(xe, ys, ze - T), (XG, ys, ZG - T), (XG, ys, ZG), (xe, ys, ze)], out=(0, -1, 0))
        m.poly("oak", [(xe, ys, ze - T), (XG, ys, ZG - T), (XG, yf, ZG - T), (XG + s * HG, yf, ze - T + ov * K)], out=(0, 0, -1))
    m.tube("plaintile", [(XG, ys, ZG + 0.02), (XG, yr, ZG + 0.02)], 0.1, (1, 0, 0), closed=False, seg=8)
    m.cyl("oak", XG, ys + 0.02, 0.09, ZG - 0.05, ZG + 0.55, seg=8, r1=0.025)
