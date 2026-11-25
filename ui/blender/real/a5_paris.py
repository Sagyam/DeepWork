# A5, Parisian block: a Haussmann apartment house of the 1860s, the kind
# that lines every boulevard in Paris. Cut limestone with fine joints over a
# ground storey of banded rustication: two shops either side of the
# porte-cochère, the tall carriage door to the courtyard under a carved
# keystone. Five bays of tall French windows, each with an iron garde-corps
# across its foot. The second floor is the étage noble: pedimented window
# heads and a continuous stone balcony on consoles with a wrought-iron
# railing the width of the front; the fifth has a second, lighter one.
# Above the main cornice the mansard: a steep zinc slope (the brisis) with
# a dormer over every bay, a shallow one behind (the terrasson), and the
# party-wall stacks with their rows of terracotta pots. The app tints the
# stone, the zinc, the shopfronts and the carriage door.
#
# Pieces (base at the origin, stacked by the app):
#   ground   4.6 m: shops, the porte-cochère, rustication, the entresol band
#   noble    3.5 m: the étage noble and its balcony
#   floor_a, floor_b  3.2 m: typical storeys, keyed or corniced heads, alternating
#   last     3.0 m: the fifth floor and its balcony
#   roof     the main cornice, the mansard, dormers and stacks
import math

from mathutils import Vector

from lib import Model, Side, Z, french, hood, new_id, pane, railing, sash, shopfront, sides

ID = "a5"
W, D = 15.0, 12.0
G = 4.6  # ground storey
NOBLE = 3.5
FL = 3.2
LAST = 3.0
STOREYS = (("noble", NOBLE), ("floor_a", FL), ("floor_b", FL), ("last", LAST))  # the reference stack
BAYS = {"front": [-6.0, -3.0, 0.0, 3.0, 6.0], "back": [-6.0, -3.0, 0.0, 3.0, 6.0], "right": [-3.4, 0.0, 3.4], "left": [-3.4, 0.0, 3.4]}
HALF = {"front": W / 2, "back": W / 2, "right": D / 2, "left": D / 2}
WW = 1.25  # window width
DEPTH = 0.3  # window reveals: thick stone walls
BAL = 0.85  # the continuous balconies' reach
# The mansard: (offset from the wall face, height above the cornice top).
BRISIS = 2.9
TERRASSON = 0.65
CORNICE = 1.0  # the main cornice, frieze to the top of its gutter


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    z = G
    for kind, h in STOREYS:
        M.piece(kind, (0, 0, z))
        storey(M, kind, z, h)
        z += h
    M.piece("roof", (0, 0, z))
    roof(M, z)
    M.export(out, bake)


def core(m, z0, z1):
    """A dark box inside the walls, so hairlines where faces meet show dark, not sky."""
    m.box("dark", (-W / 2 + DEPTH + 0.02, -D / 2 + DEPTH + 0.02, z0), (W / 2 - DEPTH - 0.02, D / 2 - DEPTH - 0.02, z1), skip=("z0", "z1"))


def ceiling(m, z):
    """Seen only when what is above has gone."""
    e = 0.02
    m.poly("dark", [(-W / 2 + e, -D / 2 + e, z), (W / 2 - e, -D / 2 + e, z), (W / 2 - e, D / 2 - e, z), (-W / 2 + e, D / 2 - e, z)], out=Z)


# ---- the ground storey ---------------------------------------------------------------


def ground(M):
    m = M.m
    # A plinth of hard stone, then rustication to the entresol band.
    m.sweep("granite", W, D, [(0.05, 0.0), (0.05, 0.38), (0.02, 0.42), (-0.01, 0.42)])
    band = G - 0.35
    for name, F in sides(m, W, D).items():
        h = HALF[name]
        if name == "front":
            shops = [(-7.0, -2.2), (2.2, 7.0)]
            gate = (-1.25, 1.25, 0.0, 3.75)
            holes = [(a, b, 0.42, 3.4) for a, b in shops] + [gate]
            F.wall("rustic", -h, h, 0.42, band, holes, depth=DEPTH, reveal="stone")
            F.wall("rustic", -1.6, 1.6, 0.0, 0.42, [gate], depth=DEPTH, reveal="stone")
            for i, (a, b) in enumerate(shops):
                shopfront(F, a + 0.1, b - 0.1, 0.42, 3.4, sign=i, door_left=i == 0, D_=DEPTH)
            porte(M, F, *gate)
        else:
            holes = [(u - WW / 2, u + WW / 2, 1.0, 3.5) for u in BAYS[name]]
            if name == "back":
                holes[2] = (-0.7, 0.7, 0.42, 3.0)
            F.wall("rustic", -h, h, 0.42, band, holes, depth=DEPTH, reveal="stone")
            for i, (a, b, c, e) in enumerate(holes):
                if name == "back" and i == 2:
                    F.quad("door", a, b, c, e, -DEPTH)
                    F.box("stone", a - 0.1, b + 0.1, 0.0, 0.42, 0.0, 0.5, skip=("back",))
                    continue
                french(F, a, b, c, e, D=DEPTH)
                F.box("stone", a - 0.06, b + 0.06, c - 0.08, c + 0.01, -DEPTH + 0.04, 0.06)
                for k in range(6):
                    u = a + 0.12 + k * (b - a - 0.24) / 5
                    F.box("iron", u - 0.012, u + 0.012, c + 0.02, c + 1.4, 0.02, 0.05)
                F.box("iron", a + 0.05, b - 0.05, c + 1.38, c + 1.42, 0.02, 0.06)
    # The entresol band: a plain stone course from the shop heads to the first floor.
    m.sweep("stone", W, D, [(-0.01, band), (0.04, band), (0.04, G - 0.12), (0.1, G - 0.06), (0.12, G), (-0.01, G)])
    core(m, 0.42, G)
    ceiling(m, G - 0.01)


def porte(M, F, a, b, c, e):
    """The porte-cochère: a tall pair of carriage doors with a fanlight under an arch
    of voussoirs and a carved keystone, kerb stones either side against the wheels."""
    m = M.m
    D_ = DEPTH + 0.15
    F.quad("stone", a, b, e, e, -D_)
    t = e - 1.0  # the fanlight's sill
    wid = new_id()
    # The fanlight: a half-round in iron in a square frame; its rays.
    F.box("door", a, b, t - 0.12, t, -D_, -D_ + 0.12)
    pane(F, "doorglass", a, b, c, e, a, b, t, e, -D_ + 0.02, wid)
    mid, r = (a + b) / 2, (b - a) / 2 - 0.05
    for k in range(9):
        ang = math.pi * k / 8
        p0 = F.p(mid, t, -D_ + 0.06)
        p1 = F.p(mid + math.cos(ang) * r, t + min(0.95, math.sin(ang) * r), -D_ + 0.06)
        m.strut("iron", p0, p1, 0.025)
    # The doors: two leaves in panels, a wicket in the left one.
    m0 = (a + b) / 2
    for l0, l1 in ((a, m0 - 0.01), (m0 + 0.01, b)):
        F.box("door", l0, l1, c, t - 0.12, -D_, -D_ + 0.1)
        for z0, z1 in ((c + 0.25, c + 1.15), (c + 1.35, t - 0.35)):
            F.box("door", l0 + 0.14, l1 - 0.14, z0, z1, -D_ + 0.1, -D_ + 0.14)
            F.box("door", l0 + 0.22, l1 - 0.22, z0 + 0.08, z1 - 0.08, -D_ + 0.14, -D_ + 0.16)
    F.box("brass", m0 - 0.2, m0 - 0.04, 1.35, 1.5, -D_ + 0.14, -D_ + 0.2)
    F.box("brass", m0 + 0.04, m0 + 0.2, 1.35, 1.5, -D_ + 0.14, -D_ + 0.2)
    # Reveals and the arch: dressed stone, voussoirs in a fan, the keystone.
    for u0, u1 in ((a - 0.35, a), (b, b + 0.35)):
        F.box("stone", u0, u1, 0.0, e, 0.0, 0.06)
    n = 9
    for k in range(n):
        a0, a1 = math.pi * k / n, math.pi * (k + 1) / n
        ri, ro = (b - a) / 2, (b - a) / 2 + 0.38
        pts = [(mid + math.cos(a0) * ri, e - 0.6 + math.sin(a0) * 0.6), (mid + math.cos(a0) * ro, e - 0.6 + math.sin(a0) * 0.6 + 0.38),
               (mid + math.cos(a1) * ro, e - 0.6 + math.sin(a1) * 0.6 + 0.38), (mid + math.cos(a1) * ri, e - 0.6 + math.sin(a1) * 0.6)]
        for w, out in ((0.07, F.n),):
            m.poly("stone", [F.p(u, z, w) for u, z in pts], out=out)
    F.box("stone", mid - 0.22, mid + 0.22, e - 0.1, e + 0.55, 0.0, 0.14)
    F.box("stone", mid - 0.28, mid + 0.28, e + 0.5, e + 0.58, 0.0, 0.18)
    # The infill of the arch's spandrels behind the voussoirs.
    F.box("stone", a - 0.35, b + 0.35, e - 0.6, e + 0.45, -0.02, 0.0, skip=("back",))
    for u in (a - 0.45, b + 0.45):
        q = F.p(u, 0, 0.25)
        m.cyl("granite", q.x, q.y, 0.16, 0.0, 0.55, seg=10, r1=0.11)
    # The number, enamelled blue in the Paris way, beside the door.
    F.box("iron", b + 0.5, b + 0.85, 2.6, 2.85, 0.0, 0.02)
    F.box("trim", b + 0.53, b + 0.82, 2.63, 2.82, 0.02, 0.025)


# ---- the storeys over it ------------------------------------------------------------------


def storey(M, kind, z, h):
    m, cut = M.m, M.cut
    head = {"noble": 2.75, "floor_a": 2.6, "floor_b": 2.6, "last": 2.35}[kind]
    for name, F in sides(m, W, D).items():
        hh = HALF[name]
        holes = [(u - WW / 2, u + WW / 2, z + 0.05, z + head) for u in BAYS[name]]
        F.wall("cladstone", -hh, hh, z, z + h, holes, depth=DEPTH, reveal="stone")
        for i, (a, b, c, e) in enumerate(holes):
            french(F, a, b, c, e, D=DEPTH)
            # The architrave round the window.
            for u0, u1 in ((a - 0.16, a), (b, b + 0.16)):
                F.box("stone", u0, u1, c, e, 0.0, 0.05)
            F.box("stone", a - 0.16, b + 0.16, e, e + 0.16, 0.0, 0.05)
            # The garde-corps across its foot, unless a balcony runs in front.
            if not (name == "front" and kind in ("noble", "last")):
                railing(F, cut, a + 0.02, b - 0.02, c, 0.02, 0.12, h=0.95)
                F.box("stone", a - 0.2, b + 0.2, c - 0.14, c, 0.0, 0.14)
            front = name in ("front", "back")
            if kind == "noble" and front:
                hood(F, a, b, e + 0.1)
            elif kind == "floor_a" and front:
                # A carved keystone breaking the architrave, a festoon of stone either side.
                mid = (a + b) / 2
                F.box("stone", mid - 0.15, mid + 0.15, e - 0.05, e + 0.36, 0.0, 0.1)
                F.box("stone", mid - 0.12, mid + 0.12, e + 0.36, e + 0.4, 0.0, 0.13)
                F.box("stone", a + 0.05, mid - 0.25, e + 0.2, e + 0.28, 0.0, 0.07)
                F.box("stone", mid + 0.25, b - 0.05, e + 0.2, e + 0.28, 0.0, 0.07)
            elif kind == "floor_b" and front:
                # A flat corniced head on two small consoles.
                F.box("stone", a - 0.22, b + 0.22, e + 0.16, e + 0.24, 0.0, 0.14)
                for u in (a - 0.18, b + 0.08):
                    F.box("stone", u, u + 0.1, e - 0.2, e + 0.16, 0.0, 0.1)
        # Chained quoins up the corners: smooth, a little proud.
        q = h / 5
        for k in range(5):
            z0 = z + k * q
            L = 0.55 if k % 2 == 0 else 0.35
            F.box("cladstone", -hh, -hh + L, z0 + 0.01, z0 + q - 0.01, 0.0, 0.02, skip=("back", "left"))
            F.box("cladstone", hh - L, hh, z0 + 0.01, z0 + q - 0.01, 0.0, 0.02, skip=("back", "right"))
    F = sides(m, W, D)["front"]
    if kind == "noble":
        balcony(M, F, z, heavy=True)
    elif kind == "last":
        balcony(M, F, z, heavy=False)
    # A string course at the sill line of every storey.
    m.sweep("stone", W, D, [(-0.01, z), (0.05, z), (0.05, z + 0.14), (-0.01, z + 0.14)])
    if kind == "noble":
        # The noble floor's taller course, and a frieze under the floor above.
        m.sweep("stone", W, D, [(-0.01, z + h - 0.3), (0.04, z + h - 0.3), (0.07, z + h - 0.24), (0.07, z + h - 0.1), (-0.01, z + h - 0.1)])
    core(m, z, z + h)
    ceiling(m, z + h - 0.01)


def balcony(M, F, z, heavy):
    """The continuous balcony along the front at floor z: a stone slab with a moulded edge
    on consoles, one between each pair of windows, and a wrought-iron railing."""
    m, cut = M.m, M.cut
    hh = W / 2
    u0, u1 = -hh + 0.25, hh - 0.25
    t = 0.22 if heavy else 0.16
    F.box("stone", u0, u1, z - t, z, 0.0, BAL, skip=())
    F.box("stone", u0 - 0.04, u1 + 0.04, z - t - 0.05, z - t + 0.04, 0.0, BAL + 0.04, skip=())
    F.box("stone", u0, u1, z, z + 0.04, 0.0, BAL - 0.04, skip=("back", "bottom"))
    us = [-7.0, -4.5, -1.5, 1.5, 4.5, 7.0] if heavy else [-7.0, -4.5, 4.5, 7.0]
    for u in us:
        u = max(u0 + 0.1, min(u1 - 0.1, u))
        lo = 0.75 if heavy else 0.45
        F.box("stone", u - 0.11, u + 0.11, z - t - lo, z - t, 0.0, 0.28)
        F.box("stone", u - 0.11, u + 0.11, z - t - lo * 0.45, z - t, 0.28, BAL - 0.12)
        F.box("stone", u - 0.13, u + 0.13, z - t - lo - 0.06, z - t - lo, 0.0, 0.3)
    railing(F, cut, u0 + 0.06, u1 - 0.06, z, 0.05, BAL - 0.06, h=1.0)
    # Panels of scrollwork every bay: a heavier bar frame in the railing.
    for u in [-6.0, -3.0, 0.0, 3.0, 6.0]:
        for uu in (u - 0.7, u + 0.7):
            F.box("iron", uu - 0.02, uu + 0.02, z + 0.06, z + 0.98, BAL - 0.09, BAL - 0.05)
        F.box("iron", u - 0.7, u + 0.7, z + 0.44, z + 0.48, BAL - 0.09, BAL - 0.05)
        ring = [F.p(u + math.cos(k / 10 * math.tau) * 0.22, z + 0.72 + math.sin(k / 10 * math.tau) * 0.22, BAL - 0.07) for k in range(10)]
        m.tube("iron", ring, 0.015, F.n)


# ---- the roof ---------------------------------------------------------------------------------


def slope(dz):
    """The brisis's face, as an offset from the wall, dz above its foot."""
    return -0.35 - dz / BRISIS * 1.05


def roof(M, TOP):
    m = M.m
    # The main cornice: a frieze, a deep moulded corona, a zinc gutter on top.
    cz = TOP + 0.45
    m.sweep("cladstone", W, D, [(-0.01, TOP), (0.02, TOP), (0.02, cz - 0.08)])
    m.sweep("stone", W, D, [(0.02, cz - 0.08), (0.08, cz - 0.08), (0.12, cz - 0.02), (0.15, cz), (0.48, cz + 0.06), (0.52, cz + 0.14), (0.52, cz + 0.32),
                            (0.6, cz + 0.38), (0.62, cz + 0.48), (0.5, cz + 0.52)])
    for name, F in sides(m, W, D).items():
        hh = HALF[name]
        n = int(2 * hh / 0.55)
        for i in range(n + 1):
            u = -hh + 0.25 + i * (2 * hh - 0.5) / n
            F.box("stone", u - 0.07, u + 0.07, cz - 0.05, cz + 0.08, 0.1, 0.44)
    # The zinc gutter's lip, then the brisis from behind it.
    z0 = cz + 0.52
    m.sweep("zinc", W, D, [(0.5, z0), (0.5, z0 + 0.12), (0.38, z0 + 0.12), (-0.35, z0)])
    z1 = z0 + BRISIS
    o1 = slope(BRISIS)
    o2 = o1 - 1.8
    z2 = z1 + TERRASSON
    m.sweep("zinc", W, D, [(-0.35, z0), (o1, z1)])
    m.sweep("zinc", W, D, [(o1 + 0.04, z1), (o1 + 0.04, z1 + 0.06), (o1, z1 + 0.08)])
    m.sweep("zinc", W, D, [(o1, z1 + 0.08), (o2, z2)])
    xa, xb, ya, yb = -W / 2 - o2, W / 2 + o2, -D / 2 - o2, D / 2 + o2
    m.poly("zinc", [(xa, ya, z2), (xb, ya, z2), (xb, yb, z2), (xa, yb, z2)], out=Z)
    for name, F in sides(m, W, D).items():
        # The sides lose their middle dormer to the stack.
        for u in BAYS[name] if name in ("front", "back") else (-3.4, 3.4):
            dormer(M, F, u, z0)
    # The party-wall stacks: render, a stone cap, a row of pots.
    for sx in (-1, 1):
        x = sx * (W / 2 - 0.55)
        ya_, yb_ = -1.9, 1.9
        top = z2 + 0.9
        m.box("cladstone", (x - 0.4, ya_, z0 - 0.4), (x + 0.4, yb_, top), skip=("z0",))
        m.box("stone", (x - 0.47, ya_ - 0.07, top), (x + 0.47, yb_ + 0.07, top + 0.14))
        for k in range(8):
            y = ya_ + 0.3 + k * (yb_ - ya_ - 0.6) / 7
            hgt = 0.45 + 0.1 * ((k * 7) % 3)
            m.cyl("terracotta", x, y, 0.13, top + 0.14, top + 0.14 + hgt, seg=8, r1=0.1)
            m.cyl("dark", x, y, 0.08, top + 0.14 + hgt, top + 0.141 + hgt, seg=8)
    # A middle stack on the spine wall, the kitchens' flues, a roof hatch.
    m.box("cladstone", (-0.5, -0.3, z2), (0.5, 0.3, z2 + 1.1), skip=("z0",))
    m.box("stone", (-0.56, -0.36, z2 + 1.1), (0.56, 0.36, z2 + 1.2))
    for x in (-0.25, 0.25):
        m.cyl("terracotta", x, 0.0, 0.12, z2 + 1.2, z2 + 1.65, seg=8, r1=0.09)
    for x in (-3.2, 3.2):
        m.cyl("zinc", x, 0.8, 0.09, z2, z2 + 0.9, seg=8)
        m.cyl("zinc", x, 0.8, 0.16, z2 + 0.9, z2 + 1.05, seg=8, r1=0.04)
    m.box("zinc", (2.0, -1.2, z2), (2.8, -0.5, z2 + 0.25))
    m.poly("skyglass", [(2.05, -1.15, z2 + 0.26), (2.75, -1.15, z2 + 0.26), (2.75, -0.55, z2 + 0.26), (2.05, -0.55, z2 + 0.26)], out=Z)


def dormer(M, F, u, z0):
    """A dormer in the brisis over the bay at u: a stone front with a casement and a
    segmental pediment, zinc cheeks back to the slope, a zinc roof."""
    m = M.m
    w = -0.45  # the dormer's face, behind the gutter
    a, b = u - 0.75, u + 0.75
    zb, zt = z0 + 0.1, z0 + 1.95
    D_ = Side(m, F.p(0, 0, w), F.t, F.n)
    hole = (u - 0.48, u + 0.48, zb + 0.25, zt - 0.1)
    D_.wall("stone", a, b, zb, zt, [hole], depth=0.12)
    sash(D_, *hole, D=0.12, lights=(2, 2))
    railing(D_, M.cut, hole[0] + 0.02, hole[1] - 0.02, hole[2], 0.02, 0.1, h=0.55)
    for uu in (a, b - 0.12):
        D_.box("stone", uu, uu + 0.12, zb, zt, 0.0, 0.06)
    # The pediment: a segmental arch of stone over the face, a zinc hood behind it back to the slope.
    D_.box("stone", a - 0.06, b + 0.06, zt, zt + 0.1, 0.0, 0.1)
    n = 8
    ang = [math.pi * k / n for k in range(n + 1)]
    arc = [(u + math.cos(t) * 0.81, zt + 0.1 + math.sin(t) * 0.38) for t in ang]
    m.poly("stone", [F.p(x, zz, w + 0.08) for x, zz in arc], out=F.n)
    zr = zt + 0.48
    back = slope(zr - z0) - 0.1
    for k in range(n):
        (x0, zz0), (x1, zz1) = arc[k], arc[k + 1]
        tm = (ang[k] + ang[k + 1]) / 2
        out = F.t * math.cos(tm) + Z * math.sin(tm)
        m.poly("stone", [F.p(x0, zz0, w + 0.08), F.p(x1, zz1, w + 0.08), F.p(x1, zz1, w - 0.02), F.p(x0, zz0, w - 0.02)], out=out)
        m.poly("zinc", [F.p(x0, zz0, w - 0.02), F.p(x1, zz1, w - 0.02), F.p(x1, zz1, back), F.p(x0, zz0, back)], out=out)
    # Cheeks from the face back to the slope.
    for uu, out in ((a, -F.t), (b, F.t)):
        m.poly("zinc", [F.p(uu, zb, w), F.p(uu, zt + 0.1, w), F.p(uu, zt + 0.1, back), F.p(uu, zb, slope(zb - z0))], out=out)
