# C5, stone cottage: a Cotswold-style cottage of coursed rubble, one and a
# half storeys under a steep stone-slate roof. The gables rise as parapets
# with dressed copings, kneelers at the eaves and a stack on each apex; two
# wall dormers break the front eave, gabled and coped like the ends. Stone
# mullioned windows with hood moulds, a ledged plank door under a little
# gabled stone porch, a half-round iron gutter in runs between the dormers.
# Behind, the back door under a stone hood, a rooflight and a water butt.
# The app tints the rubble, the roof and the door per house; the garden
# (lawn, path, the dry-stone wall) is drawn round it.
#
# Pieces (base at the origin):
#   body   the walls to the wall plate, windows, door, porch
#   roof   the roof, gables and copings, dormers, stacks, gutters
#   wall   2.4 m of dry-stone wall with a cock-and-hen top, centred, for the garden's front
import math
import random

from mathutils import Vector

from lib import Side, Model, Z, fpoly, new_id, pane, sides

ID = "c5"
W, D = 9.6, 6.2  # main block
CY = 0.35  # its centre: the porch in front keeps the footprint centred
X0, X1 = -W / 2, W / 2
Y0, Y1 = CY - D / 2, CY + D / 2
BASE = 0.25  # floor level
PLATE = 3.6  # top of the walls
PITCH = math.radians(50)
K = math.tan(PITCH)
TT = 0.16  # roof surface above the wall plate at the wall's face
EAVE = 0.22
PAR = 0.42  # gable wall thickness: the roof runs inside it
DEPTH = 0.3  # window reveals: thick stone walls
APEX = PLATE + TT + D / 2 * K  # roof surface at the ridge
DORMERS = (-2.6, 2.6)  # dormer centres, x
DHW = 0.95  # dormer half width
DE = PLATE + 1.5  # dormer eave height (its roof at the cheeks)
DR = DE + DHW * K  # dormer ridge
DOOR = (-0.5, 0.5)


def zf(y):
    """Height of the front roof surface over y."""
    return PLATE + TT + (y - Y0) * K


def zb(y):
    return PLATE + TT + (Y1 - y) * K


def build(out, bake=True):
    M = Model(ID)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, PLATE))
    roof(M)
    M.piece("wall", (24, 0, 0))
    drywall(M.m, 24)
    M.export(out, bake)


# ---- parts --------------------------------------------------------------------------


def casement(F, a, b, c, e, wid, d):
    """One casement light in a stone opening: a frame, a glazing bar across, glass."""
    fw = 0.055
    F.box("frame", a, a + fw, c, e, -d, -d + 0.08)
    F.box("frame", b - fw, b, c, e, -d, -d + 0.08)
    F.box("frame", a + fw, b - fw, e - fw, e, -d, -d + 0.08)
    F.box("frame", a + fw, b - fw, c, c + fw, -d, -d + 0.09)
    F.box("frame", a + fw, b - fw, (c + e) / 2 - 0.015, (c + e) / 2 + 0.015, -d + 0.02, -d + 0.07)
    F.box("frame", (a + b) / 2 - 0.012, (a + b) / 2 + 0.012, c + fw, e - fw, -d + 0.02, -d + 0.065)
    return a + fw, b - fw, c + fw, e - fw


def mullioned(F, a, b, c, e, n, hood=True):
    """n casement lights between stone mullions in the opening (a..b, c..e), its surround dressed stone."""
    wid = new_id()
    mw = 0.11
    L = (b - a - (n - 1) * mw) / n
    for i in range(n):
        u0 = a + i * (L + mw)
        ga, gb, gc, ge = casement(F, u0, u0 + L, c, e, wid, DEPTH - 0.06)
        pane(F, "glass", a, b, c, e, ga, gb, gc, ge, -DEPTH + 0.1, wid)
        if i:
            F.box("stone", u0 - mw, u0, c, e, -DEPTH, 0.0, skip=())
    # Chamfered jambs and head flush with the rubble, a projecting sill, the hood mould.
    F.box("stone", a - 0.14, a, c - 0.06, e + 0.16, 0, 0.02)
    F.box("stone", b, b + 0.14, c - 0.06, e + 0.16, 0, 0.02)
    F.box("stone", a, b, e, e + 0.16, 0, 0.02)
    F.box("stone", a - 0.18, b + 0.18, c - 0.1, c, -DEPTH + 0.06, 0.07)
    if hood:
        F.box("stone", a - 0.24, b + 0.24, e + 0.16, e + 0.27, 0, 0.11)
        for u in (a - 0.24, b + 0.12):
            F.box("stone", u, u + 0.12, e - 0.1, e + 0.16, 0, 0.11)


def plank_door(F, a, b, c, t, d):
    """A ledged plank door with strap hinges and a ring latch, in a stone surround with a flat head."""
    F.quad("door", a, b, c, t, -d)
    n = 6
    for k in range(1, n):
        u = a + k * (b - a) / n
        F.box("dark", u - 0.007, u + 0.007, c + 0.02, t - 0.02, -d, -d + 0.004)
    for z in (c + 0.3, t - 0.35):
        F.box("iron", a + 0.04, a + 0.62, z, z + 0.05, -d, -d + 0.015)
    F.box("iron", b - 0.18, b - 0.12, c + 1.0, c + 1.12, -d, -d + 0.04)
    F.box("stone", a - 0.16, a, c, t + 0.22, 0, 0.02)
    F.box("stone", b, b + 0.16, c, t + 0.22, 0, 0.02)
    F.box("stone", a - 0.16, b + 0.16, t, t + 0.22, 0, 0.03)


def coping(m, a, b, w):
    """A dressed coping stone along a gable's rake from a to b, w wide, its top 0.14 above the line."""
    a, b = Vector(a), Vector(b)
    up = Z * 0.07
    m.strut("stone", a + up, b + up, w, 0.14)


def stack(m, x, y, z0, top, wx=0.62, wy=0.95):
    """A dressed-stone chimney stack with a projecting cap and two pots."""
    m.box("stone", (x - wx / 2, y - wy / 2, z0), (x + wx / 2, y + wy / 2, top - 0.2), skip=("z0",))
    m.box("stone", (x - wx / 2 - 0.07, y - wy / 2 - 0.07, top - 0.2), (x + wx / 2 + 0.07, y + wy / 2 + 0.07, top), skip=())
    for dy in (-wy / 4, wy / 4):
        m.cyl("terracotta", x, y + dy, 0.12, top, top + 0.45, seg=10, r1=0.1)
        m.cyl("terracotta", x, y + dy, 0.125, top + 0.45, top + 0.5, seg=10)


# ---- body ---------------------------------------------------------------------------


def body(M):
    m = M.m
    walls = sides(m, W, D, cy=CY)
    wins = {
        "front": [(-3.45, -1.75, 3), (1.75, 3.45, 3)],
        "back": [(-3.6, -2.5, 2), (1.3, 2.4, 2)],
        "left": [(-0.55, 0.55, 2)],
        "right": [],
    }
    doors = {"front": DOOR, "back": (-1.0, -0.1)}
    c, e = 0.95, 2.1
    for name, F in walls.items():
        h = W / 2 if name in ("front", "back") else D / 2
        hs = [(a, b, c, e, DEPTH) for a, b, _ in wins[name]]
        if name in doors:
            a, b = doors[name]
            hs.append((a, b, BASE, BASE + 2.0, DEPTH))
        F.wall("fieldstone", -h, h, 0, PLATE, hs, depth=DEPTH)
        for a, b, n in wins[name]:
            mullioned(F, a, b, c, e, n)
        # Long-and-short quoins at the corners, dressed stone.
        z, i = 0.0, 0
        while z + 0.28 < PLATE:
            for end in (-1, 1):
                L = 0.42 if (i + (end > 0)) % 2 else 0.24
                u0, u1 = (h - L, h + 0.02) if end > 0 else (-h, -h + L)
                F.box("stone", u0, u1, z + 0.004, z + 0.276, 0, 0.02)
            z += 0.28
            i += 1
    for name in doors:
        F = walls[name]
        a, b = doors[name]
        plank_door(F, a, b, BASE, BASE + 2.0, DEPTH - 0.05)
        F.box("stone", a - 0.25, b + 0.25, 0, BASE, 0, 0.35, skip=("back", "bottom"))
    porch(m, walls["front"])
    # The back door's stone hood on two brackets.
    B = walls["back"]
    a, b = doors["back"]
    B.box("stone", a - 0.3, b + 0.3, BASE + 2.4, BASE + 2.52, 0, 0.5)
    for u in (a - 0.22, b + 0.12):
        B.box("stone", u, u + 0.1, BASE + 2.1, BASE + 2.4, 0, 0.4)
    # A water butt by the back door, and a lamp.
    m.cyl("wood", X0 + 1.1, Y1 + 0.42, 0.3, 0.0, 0.92, seg=16)
    m.cyl("dark", X0 + 1.1, Y1 + 0.42, 0.31, 0.92, 0.96, seg=16)
    for z in (0.15, 0.78):
        m.cyl("iron", X0 + 1.1, Y1 + 0.42, 0.305, z, z + 0.04, seg=16, top=False)
    B.box("iron", b + 0.35, b + 0.45, 2.2, 2.28, 0, 0.12)
    B.box("lamp", b + 0.32, b + 0.48, 2.28, 2.5, 0.03, 0.19, skip=())
    # A ceiling over the top of the walls, seen only when the roof is gone.
    m.poly("dark", [(X0, Y0, PLATE - 0.02), (X1, Y0, PLATE - 0.02), (X1, Y1, PLATE - 0.02), (X0, Y1, PLATE - 0.02)], out=Z)


def porch(m, F):
    """A gabled stone porch: rubble cheeks, a stone lintel, a coped gable and a stone-slate roof."""
    a, b = DOOR
    u0, u1 = a - 0.6, b + 0.6
    dep = 1.15
    top = 2.3
    for ua, ub in ((u0, a - 0.28), (b + 0.28, u1)):
        F.box("fieldstone", ua, ub, 0, top, 0, dep, skip=("back",))
        F.box("stone", ua - 0.03, ub + 0.03, 0.85, 0.93, 0, dep + 0.03, skip=("back",))
    F.box("stone", u0, u1, top, top + 0.22, 0, dep, skip=("back",))
    # The gable over the lintel, its roof back to the wall under the main eave.
    hw = (u1 - u0) / 2 + 0.08
    pk = math.tan(math.radians(32))
    mid = (u0 + u1) / 2
    z0 = top + 0.22
    apex = z0 + (hw - 0.08) * pk
    fpoly(F, "fieldstone", [(u0, z0), (u1, z0), (mid, apex)], w=dep)
    fpoly(F, "fieldstone", [(u0, z0), (mid, apex), (u1, z0)], w=dep - 0.01, out=-F.n)
    for s in (-1, 1):
        ue = mid + s * hw
        # Roof plane: eave edge from the front to the wall, up to the ridge.
        pts = [F.p(ue, z0 - 0.06, dep + 0.06), F.p(ue, z0 - 0.06, 0), F.p(mid, apex + 0.05, 0), F.p(mid, apex + 0.05, dep + 0.06)]
        m.poly("stoneslate", pts, out=Z + F.t * s * 0.5)
        m.poly("stone", [F.p(ue, z0 - 0.06, dep + 0.06), F.p(ue, z0 - 0.06, 0), F.p(ue, z0 - 0.14, 0), F.p(ue, z0 - 0.14, dep + 0.06)], out=F.t * s)
        coping(m, F.p(mid + s * (hw - 0.02), z0 - 0.05, dep - 0.12), F.p(mid, apex + 0.02, dep - 0.12), 0.34)
    m.poly("stone", [F.p(mid - hw, z0 - 0.14, dep + 0.06), F.p(mid + hw, z0 - 0.14, dep + 0.06), F.p(mid + hw, z0 - 0.14, 0), F.p(mid - hw, z0 - 0.14, 0)], out=-Z)
    p = F.p(mid, apex + 0.2, dep - 0.12)
    m.cyl("stone", p.x, p.y, 0.09, p.z - 0.02, p.z + 0.18, seg=8, r1=0.0)
    # A flagstone floor.
    F.box("stone", u0, u1, 0, 0.06, 0, dep, skip=("back",))


# ---- roof ---------------------------------------------------------------------------


def roof(M):
    m = M.m
    xa, xb = X0 + PAR, X1 - PAR  # the roof runs between the gable parapets
    ye0, ye1 = Y0 - EAVE, Y1 + EAVE
    # Front slope: full strips beside the dormers, above the valleys between their cheeks.
    xs = [xa]
    for xc in DORMERS:
        xs += [xc - DHW, xc + DHW]
    xs.append(xb)
    yr = Y0 + (DR - zf(Y0)) / K  # where a dormer's ridge meets the main roof
    ye = Y0 + (DE - zf(Y0)) / K  # where its eaves do
    ym = CY
    for i in range(0, len(xs), 2):
        plane(m, [(xs[i], ye0, zf(ye0)), (xs[i + 1], ye0, zf(ye0)), (xs[i + 1], ym, APEX), (xs[i], ym, APEX)])
        eave(m, xs[i], xs[i + 1], ye0, -1)
    for xc in DORMERS:
        for s in (-1, 1):
            xo = xc + s * DHW
            pts = [(xo, ye, zf(ye)), (xc, yr, zf(yr)), (xc, ym, APEX), (xo, ym, APEX)]
            plane(m, pts if s < 0 else pts[::-1])
        dormer(m, xc, ye, yr)
    plane(m, [(xb, ye1, zb(ye1)), (xa, ye1, zb(ye1)), (xa, ym, APEX), (xb, ym, APEX)])
    eave(m, xa, xb, ye1, 1)
    # Ridge: half-round stone ridge tiles.
    m.tube("stone", [(xa, ym, APEX + 0.02), (xb, ym, APEX + 0.02)], 0.1, (0, 1, 0), closed=False, seg=8)
    # Gables: rubble up past the roof surface, the copings, kneelers, the stacks.
    for x, s in ((X0, -1), (X1, 1)):
        G = Side(m, (x, CY, 0), (0, -s, 0), (s, 0, 0))
        h = D / 2
        top = lambda u: PLATE + TT + (h - abs(u)) * K + 0.06  # noqa: E731
        fpoly(G, "fieldstone", [(-h, PLATE), (h, PLATE), (h, top(h)), (0, top(0)), (-h, top(-h))])
        # The parapet's inner face, above the roof.
        I = Side(m, (x - s * PAR, CY, 0), (0, s, 0), (-s, 0, 0))
        for u0, u1 in ((-h, 0), (0, h)):
            fpoly(I, "fieldstone", [(u0, PLATE + TT + (h - abs(u0)) * K - 0.02), (u1, PLATE + TT + (h - abs(u1)) * K - 0.02), (u1, top(u1)), (u0, top(u0))])
        for y0 in (Y0, Y1):
            coping(m, (x - s * (PAR / 2 - 0.04), y0, zf(Y0) + 0.06), (x - s * (PAR / 2 - 0.04), CY, APEX + 0.06), PAR + 0.16)
            # Kneeler: a corbelled block at the parapet's foot.
            ya, yb_ = (y0 - 0.12, y0 + 0.5) if y0 == Y0 else (y0 - 0.5, y0 + 0.12)
            m.box("stone", (x - s * (PAR + 0.06) if s > 0 else x - 0.06, ya, PLATE - 0.05), (x + 0.06 if s > 0 else x + PAR + 0.06, yb_, PLATE + 0.42), skip=("z0",))
        stack(m, x - s * PAR / 2, CY, APEX - 0.6, APEX + 1.25)
    # A small loft light in the left gable, and a dove hole in the right.
    G = Side(m, (X0, CY, 0), (0, -1, 0), (-1, 0, 0))
    G.quad("dark", -0.3, 0.3, PLATE + 1.6, PLATE + 2.2, 0.005)
    G.box("stone", -0.42, 0.42, PLATE + 1.48, PLATE + 1.6, 0, 0.06)
    G.box("stone", -0.42, 0.42, PLATE + 2.2, PLATE + 2.32, 0, 0.04)
    for u in (-0.42, 0.3):
        G.box("stone", u, u + 0.12, PLATE + 1.6, PLATE + 2.2, 0, 0.02)
    R = Side(m, (X1, CY, 0), (0, 1, 0), (1, 0, 0))
    R.quad("dark", -0.12, 0.12, PLATE + 2.3, PLATE + 2.5, 0.005)
    R.box("stone", -0.2, 0.2, PLATE + 2.22, PLATE + 2.3, 0, 0.1)
    rooflight(m, 1.8, Y1 - 1.6)
    # Downpipes at the ends of the gutter runs.
    for x, y, s in ((xa + 0.25, ye0, -1), (1.45, ye0, -1), (xb - 0.25, ye0, -1), (xa + 0.25, ye1, 1), (xb - 0.25, ye1, 1)):
        wy = Y0 if s < 0 else Y1
        top = zf(ye0) - 0.12
        m.strut("iron", (x, y + s * 0.07, top), (x, wy + s * 0.06, top - 0.35), 0.075)
        m.cyl("iron", x, wy + s * 0.06, 0.04, 0.15, top - 0.33, seg=8)
        m.box("iron", (x - 0.06, wy, 0.05), (x + 0.06, wy + s * 0.2, 0.15))


def plane(m, pts):
    """A stone-slate roof plane through pts (its first edge the eave), with UV0 along the eave and up the slope."""
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
    m.poly("stoneslate", P, out=n, uvs=uvs)


def eave(m, x0, x1, y, s):
    """The stone eaves course under a run of roof, the slates' edge, and a half-round gutter."""
    z = zf(Y0 - EAVE)
    wy = Y0 if s < 0 else Y1
    m.box("stone", (x0, min(y, wy), z - 0.2), (x1, max(y, wy), z), skip=("z1",))
    m.box("stoneslate", (x0, y - 0.015, z - 0.03), (x1, y + 0.015, z + 0.02), skip=("z0", "z1"))
    m.tube("iron", [(x0 + 0.05, y + s * 0.07, z - 0.14), (x1 - 0.05, y + s * 0.07, z - 0.14)], 0.07, (0, s, 0), closed=False, seg=6)


def dormer(m, xc, ye, yr):
    """A wall dormer: the front wall carried up into a coped gable, two-light window, cheeks, its own roof."""
    F = Side(m, (xc, Y0, 0), (1, 0, 0), (0, -1, 0))
    c, e = PLATE + 0.12, PLATE + 1.2
    F.wall("fieldstone", -DHW, DHW, PLATE, DE, [(-0.55, 0.55, c, e, DEPTH)], depth=DEPTH)
    mullioned(F, -0.55, 0.55, c, e, 2)
    fpoly(F, "fieldstone", [(-DHW, DE), (DHW, DE), (0, DR + 0.06)])
    # The gable's inside face, behind its coping, above the dormer roof.
    fpoly(F, "fieldstone", [(-DHW, DE), (0, DR + 0.06), (DHW, DE)], w=-0.36, out=-F.n)
    for s in (-1, 1):
        coping(m, F.p(s * (DHW + 0.04), DE - 0.02, -0.16), F.p(0, DR + 0.06, -0.16), 0.44)
        u0, u1 = sorted((s * (DHW + 0.06), s * (DHW - 0.24)))
        F.box("stone", u0, u1, DE - 0.2, DE + 0.12, -0.42, 0.06, skip=())
        # Cheek: a triangle of rubble between the main roof and the dormer's eave.
        x = xc + s * DHW
        m.poly("fieldstone", [(x, Y0, PLATE), (x, Y0, DE), (x, ye, DE)], out=(s, 0, 0))
        # The dormer's roof plane, eave at the cheek, back to the valley.
        y0 = Y0 + 0.05
        plane(m, [(x, y0, DE), (x, ye, DE), (xc, yr, DR), (xc, y0, DR)] if s > 0 else [(x, ye, DE), (x, y0, DE), (xc, y0, DR), (xc, yr, DR)])
        m.box("stone", (min(x, x + s * 0.05), y0, DE - 0.16), (max(x, x + s * 0.05), ye, DE), skip=("z1",))
    m.tube("stone", [(xc, Y0 + 0.3, DR + 0.03), (xc, yr, DR + 0.03)], 0.08, (1, 0, 0), closed=False, seg=8)
    p = F.p(0, DR + 0.26, -0.16)
    m.cyl("stone", p.x, p.y, 0.1, p.z - 0.06, p.z + 0.18, seg=8, r1=0.0)


def rooflight(m, x, y):
    """A small cast-iron rooflight on the back slope at (x, y)."""
    c, s = math.cos(PITCH), math.sin(PITCH)
    d, n = Vector((0, c, -s)), Vector((0, s, c))  # down the back slope, out of it
    base = Vector((x, y, zb(y)))
    w, L = 0.6, 0.8
    P = lambda u, v, h: base + Vector((u, 0, 0)) + d * v + n * h  # noqa: E731
    m.poly("lead", [P(-w / 2 - 0.08, -0.12, 0.01), P(w / 2 + 0.08, -0.12, 0.01), P(w / 2 + 0.08, L + 0.06, 0.01), P(-w / 2 - 0.08, L + 0.06, 0.01)], out=n)
    for (u0, u1, v0, v1) in ((-w / 2, w / 2, 0, 0.05), (-w / 2, w / 2, L - 0.05, L), (-w / 2, -w / 2 + 0.05, 0, L), (w / 2 - 0.05, w / 2, 0, L)):
        q = [P(u0, v0, 0.09), P(u1, v0, 0.09), P(u1, v1, 0.09), P(u0, v1, 0.09)]
        m.poly("iron", q, out=n)
    m.poly("skyglass", [P(-w / 2 + 0.05, 0.05, 0.075), P(w / 2 - 0.05, 0.05, 0.075), P(w / 2 - 0.05, L - 0.05, 0.075), P(-w / 2 + 0.05, L - 0.05, 0.075)], out=n)
    for u0, v0, u1, v1, o in ((-w / 2, 0, w / 2, 0, -d), (-w / 2, L, w / 2, L, d)):
        m.poly("iron", [P(u0, v0, 0.0), P(u1, v1, 0.0), P(u1, v1, 0.09), P(u0, v0, 0.09)], out=o)
    for u in (-w / 2, w / 2):
        m.poly("iron", [P(u, 0, 0.0), P(u, L, 0.0), P(u, L, 0.09), P(u, 0, 0.09)], out=Vector((1 if u > 0 else -1, 0, 0)))


# ---- garden wall --------------------------------------------------------------------


def drywall(m, ox):
    """2.4 m of dry-stone wall, battered from 0.55 m at the foot to 0.4 m, under a row of upright stones."""
    L, h = 2.4, 0.72
    x0, x1 = ox - L / 2, ox + L / 2
    # In 0.3 m bays, so the lightmap has the texels to shade under the uprights.
    n = 8
    for i in range(n):
        a, b = x0 + i * L / n, x0 + (i + 1) * L / n
        for s in (-1, 1):
            m.poly("fieldstone", [(a, s * 0.275, 0), (b, s * 0.275, 0), (b, s * 0.2, h), (a, s * 0.2, h)], out=(0, s, 0.15))
        m.poly("fieldstone", [(a, -0.2, h), (b, -0.2, h), (b, 0.2, h), (a, 0.2, h)], out=Z)
    # Cock and hen: thin uprights packed tight, of uneven heights, a few leaning.
    R = random.Random(5)
    u = x0
    while u < x1 - 0.03:
        t = min(R.uniform(0.05, 0.1), x1 - u)
        top = h + R.uniform(0.12, 0.24)
        lean = R.uniform(-0.03, 0.03)
        m.poly("fieldstone", [(u, -0.19, h), (u + t, -0.19, h), (u + t + lean, -0.17, top), (u + lean, -0.17, top)], out=(0, -1, 0))
        m.poly("fieldstone", [(u + t, 0.19, h), (u, 0.19, h), (u + lean, 0.17, top), (u + t + lean, 0.17, top)], out=(0, 1, 0))
        m.poly("fieldstone", [(u + lean, -0.17, top), (u + t + lean, -0.17, top), (u + t + lean, 0.17, top), (u + lean, 0.17, top)], out=Z)
        for e, sgn in ((u, -1), (u + t, 1)):
            m.poly("fieldstone", [(e, -0.19, h), (e, 0.19, h), (e + lean, 0.17, top), (e + lean, -0.17, top)], out=(sgn, 0, 0))
        u += t + 0.008
