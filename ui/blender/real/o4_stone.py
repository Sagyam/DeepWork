# O4, stone office: a Beaux-Arts commercial block of about 1910, the kind
# a bank or an insurance company put up on the main street downtown.
# A base of rusticated limestone on a granite plinth: tall round-arched
# windows lighting the banking hall, voussoirs and a keystone over each,
# and on the axis the entrance, a deeper arch with bronze doors under a
# bronze-barred fanlight, up two granite steps between bronze lanterns.
# Over it a smooth limestone shaft: pilaster strips run up between the
# bays, each bay a Chicago pair of one-over-one sashes on a stone mullion
# above a sunk spandrel panel; the first storey's windows wear pediments.
# At the top an attic storey of square windows, an entablature with the
# firm's name cut in the frieze, a deep cornice on modillions and dentils,
# a panelled parapet. On the roof the lift's brick penthouse and a timber
# water tank on its steel stand. The app tints the stone, the bronze and
# the sash paint, and picks the name, per building.
#
# Pieces (base at the origin, stacked by the app):
#   ground  6.0 m: plinth, rustication, arched windows, the entrance
#   first   3.7 m: the first storey, pedimented windows over a belt course
#   floor   3.7 m: a typical storey
#   roof    attic storey, entablature, cornice, parapet, penthouse, tank
import math

from lib import Model, Side, Z, hood, new_id, pane, sash, sides

ID = "o4"
W, D = 14.4, 12.0
HW, HD = W / 2, D / 2
G = 6.0  # ground storey
FL = 3.7  # the storeys over it
DEPTH = 0.34  # window reveals: stone walls on a steel frame
PIER = 0.12  # how far the pilaster strips stand out
CP = 0.18  # how far the corner piers stand out
CW = 0.6  # the corner piers' width on each face
PW = 0.62  # the pilaster strips' width
PLINTH = 0.75
BAND = 0.55  # the string course over the base
SILL, HEAD = 0.9, 3.1  # window sill and head above a storey's floor
ATTIC = 2.6  # the attic storey
ENT = 1.65  # architrave, frieze and cornice over the attic
PARAPET = 0.95
# Bay centres per facade (u left to right seen from outside) and window widths.
BAYS = {"front": [-5.5, -2.75, 0.0, 2.75, 5.5], "back": [-5.5, -2.75, 0.0, 2.75, 5.5], "right": [-4.2, -1.4, 1.4, 4.2], "left": [-4.2, -1.4, 1.4, 4.2]}
WW = {"front": 1.8, "back": 1.8, "right": 1.7, "left": 1.7}
HALF = {"front": HW, "back": HW, "right": HD, "left": HD}


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("first", (0, 0, G))
    storey(M, G, first=True)
    M.piece("floor", (0, 0, G + FL))
    storey(M, G + FL)
    M.piece("roof", (0, 0, G + 2 * FL))
    roof(M, G + 2 * FL)
    M.export(out, bake)


def core(m, z0, z1, front=DEPTH + 0.02):
    """A dark box inside the walls, so hairlines where faces meet show dark, not
    sky; `front` sets its front face further back behind a deep entrance."""
    e = DEPTH + 0.02
    m.box("dark", (-HW + e, -HD + front, z0), (HW - e, HD - e, z1), skip=("z0", "z1"))


def ceiling(m, z):
    """Seen only when what is above has gone."""
    e = 0.02
    m.poly("dark", [(-HW + e, -HD + e, z), (HW - e, -HD + e, z), (HW - e, HD - e, z), (-HW + e, HD - e, z)], out=Z)


def piers(F, name, z0, z1, role="cladstone"):
    """The pilaster strips between a facade's bays, and its two corner piers."""
    us = BAYS[name]
    for a, b in zip(us, us[1:]):
        mid = (a + b) / 2
        F.box(role, mid - PW / 2, mid + PW / 2, z0, z1, 0.0, PIER, skip=("back", "top", "bottom"))


def corners(m, z0, z1, role="cladstone"):
    """The corner piers, proud of both faces: one box per corner."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, x1 = sorted((sx * (HW - CW), sx * (HW + CP)))
            y0, y1 = sorted((sy * (HD - CW), sy * (HD + CP)))
            m.box(role, (x0, y0, z0), (x1, y1, z1), skip=("z0", "z1"))


# ---- arches --------------------------------------------------------------------------------


def arc(mid, spring, r, n=10):
    """Points round a semicircle from the left springing to the right."""
    return [(mid - math.cos(math.pi * k / n) * r, spring + math.sin(math.pi * k / n) * r) for k in range(n + 1)]


def arched(M, F, a, b, c, spring, deep, wall, glass, bars=2, wid=None):
    """Everything in a round-arched opening (a..b, c..crown) that F.wall left
    square: the spandrels filled back to the wall face, the intrados, the
    glass (a square light under a half-round one) in a bronze frame, and a
    fan of voussoirs with a keystone round the head."""
    m = M.m
    mid, r = (a + b) / 2, (b - a) / 2
    top = spring + r
    pts = arc(mid, spring, r)
    # Spandrels, fanned from the opening's top corners, and the intrados.
    for k in range(len(pts) - 1):
        p0, p1 = pts[k], pts[k + 1]
        corner = (a, top) if p1[0] <= mid + 1e-6 else (b, top)
        m.poly(wall, [F.p(*corner, 0), F.p(*p0, 0), F.p(*p1, 0)], out=F.n)
        ang = math.pi * (k + 0.5) / (len(pts) - 1)
        inward = -F.t * (-math.cos(ang)) - Z * math.sin(ang)
        m.poly("stone", [F.p(*p0, 0), F.p(*p1, 0), F.p(*p1, -deep), F.p(*p0, -deep)], out=inward)
    # The glass: one window id over the square light and the lunette.
    wid = wid or new_id()
    gw = -deep + 0.05
    uv = lambda u, z: (wid + (u - a) / (b - a), (z - c) / (top - c))  # noqa: E731
    pane(F, glass, a, b, c, top, a, b, c, spring, gw, wid)
    m.poly(glass, [F.p(u, z, gw) for u, z in pts], out=F.n, uvs=[uv(u, z) for u, z in pts])
    # The frame: jambs, sill, transom at the springing, mullions, radial bars.
    f = 0.07
    F.box("bronze", a, a + f, c, spring, gw - 0.03, gw + 0.07)
    F.box("bronze", b - f, b, c, spring, gw - 0.03, gw + 0.07)
    F.box("bronze", a, b, c, c + f, gw - 0.03, gw + 0.09)
    F.box("bronze", a, b, spring - 0.05, spring + 0.05, gw - 0.03, gw + 0.08)
    for i in range(1, bars):
        u = a + i * (b - a) / bars
        F.box("bronze", u - 0.035, u + 0.035, c, spring, gw - 0.02, gw + 0.06)
    for k in range(1, 4):
        t = math.pi * k / 4
        p0 = F.p(mid, spring, gw + 0.02)
        p1 = F.p(mid - math.cos(t) * (r - 0.04), spring + math.sin(t) * (r - 0.04), gw + 0.02)
        m.strut("bronze", p0, p1, 0.05)
    for k in range(len(pts) - 1):
        (u0, z0), (u1, z1) = pts[k], pts[k + 1]
        m.strut("bronze", F.p(u0, z0, gw + 0.02), F.p(u1, z1, gw + 0.02), 0.06)
    # Voussoirs, proud of the rustication, and the keystone.
    n = 9
    ro = r + 0.36
    for k in range(n):
        t0, t1 = math.pi * k / n, math.pi * (k + 1) / n
        q = [(mid - math.cos(t0) * r, spring + math.sin(t0) * r), (mid - math.cos(t0) * ro, spring + math.sin(t0) * ro),
             (mid - math.cos(t1) * ro, spring + math.sin(t1) * ro), (mid - math.cos(t1) * r, spring + math.sin(t1) * r)]
        m.poly("stone", [F.p(u, z, 0.07) for u, z in q], out=F.n)
        # The voussoir's soffit edge and its outer edge.
        tm = (t0 + t1) / 2
        m.poly("stone", [F.p(*q[0], 0.0), F.p(*q[3], 0.0), F.p(*q[3], 0.07), F.p(*q[0], 0.07)], out=F.t * math.cos(tm) - Z * math.sin(tm))
        m.poly("stone", [F.p(*q[1], 0.0), F.p(*q[2], 0.0), F.p(*q[2], 0.07), F.p(*q[1], 0.07)], out=F.t * (-math.cos(tm)) + Z * math.sin(tm))
    F.box("stone", mid - 0.2, mid + 0.2, top - 0.12, top + 0.5, 0.0, 0.16, skip=("back",))


# ---- the base --------------------------------------------------------------------------------


def ground(M):
    m = M.m
    S = sides(m, W, D)
    top = G - BAND
    for name, F in S.items():
        h = HALF[name]
        if name == "back":
            back(M, F, top)
            continue
        holes, arches = [], []
        for u in BAYS[name]:
            if name == "front" and abs(u) < 1e-6:
                continue
            a, b = u - 0.75, u + 0.75
            spring = 3.85
            holes.append((a, b, 1.15, spring + (b - a) / 2))
            arches.append((a, b, 1.15, spring))
        door = None
        if name == "front":
            door = (-1.1, 1.1, 0.3, 3.6 + 1.1)
            holes.append(door)
        F.wall("ashlar", -h, h, PLINTH, top, [x for x in holes if x is not door] + ([(door[0], door[1], PLINTH, door[3])] if door else []), depth=DEPTH, reveal="stone")
        for a, b, c, spring in arches:
            arched(M, F, a, b, c, spring, DEPTH, "ashlar", "glass", bars=2)
            # A sill on two blocks, a bronze grille over the lower light.
            F.box("stone", a - 0.12, b + 0.12, c - 0.12, c + 0.02, -DEPTH + 0.05, 0.12)
            for k in range(7):
                uu = a + 0.15 + k * (b - a - 0.3) / 6
                F.box("bronze", uu - 0.014, uu + 0.014, c + 0.03, c + 1.1, -DEPTH + 0.02, -DEPTH + 0.05)
            F.box("bronze", a + 0.08, b - 0.08, c + 1.08, c + 1.13, -DEPTH + 0.02, -DEPTH + 0.05)
        if door:
            entrance(M, F, *door)
        plinth(F, h, name, (door[0] - 0.45, door[1] + 0.45) if door else None)
    corners(m, 0.0, top, "ashlar")
    # The string course over the base, with a slim cornice at its head.
    m.sweep("stone", W, D, [(-0.01, top), (0.2, top), (0.2, top + 0.08), (0.24, top + 0.14), (0.24, G - 0.12), (0.3, G - 0.06), (0.3, G), (-0.01, G)])
    core(m, PLINTH, G, front=DEPTH + 0.6)
    ceiling(m, G - 0.01)


def plinth(F, h, name, cut):
    """Granite to PLINTH, proud of the wall, a weathered top; split round the door.
    The front and back run past the corners, the sides stop at them."""
    o = 0.14
    full = name in ("front", "back")
    u0, u1 = (-h - CP - o, h + CP + o) if full else (-h, h)
    runs = [(u0, cut[0]), (cut[1], u1)] if cut else [(u0, u1)]
    skip = ("back",) if full else ("back", "left", "right")
    w1 = CP + o
    for a, b in runs:
        F.box("granite", a, b, 0.0, PLINTH - 0.08, 0.0, w1, skip=skip)
        p = F.p
        F.m.poly("granite", [p(a, PLINTH - 0.08, w1), p(b, PLINTH - 0.08, w1), p(b, PLINTH, w1 - 0.1), p(a, PLINTH, w1 - 0.1)], out=F.n + Z)
        F.m.poly("granite", [p(a, PLINTH, w1 - 0.1), p(b, PLINTH, w1 - 0.1), p(b, PLINTH, 0.0), p(a, PLINTH, 0.0)], out=Z)


def entrance(M, F, a, b, c, e):
    """The entrance: a deep arch over a pair of bronze-and-glass doors, a
    transom, a fanlight behind a bronze grille; granite steps out to the
    pavement, a bronze lantern each side on the plinth's ends."""
    m = M.m
    r = (b - a) / 2
    spring = e - r
    deep = DEPTH + 0.5
    mid = 0.0
    # Reveals from the ground: the rustication's returns are dressed stone.
    for u0, u1, out in ((a, a, F.t), (b, b, -F.t)):
        m.poly("stone", [F.p(u0, 0.0, 0), F.p(u0, 0.0, -deep), F.p(u0, PLINTH, -deep), F.p(u0, PLINTH, 0)], out=out)
        m.poly("stone", [F.p(u0, PLINTH, -DEPTH), F.p(u0, PLINTH, -deep), F.p(u0, spring, -deep), F.p(u0, spring, -DEPTH)], out=out)
    wid = new_id()
    arched(M, Side(m, F.p(0, 0, -DEPTH), F.t, F.n), a, b, spring - 0.01, spring, 0.5, "stone", "doorglass", bars=1, wid=wid)
    # Re-face the arch at the wall plane: spandrels and voussoirs on the rustication.
    arched_face(M, F, a, b, spring, DEPTH)
    # The doors and their frame, under a transom at 3.0.
    w = -deep + 0.06
    tr = 3.0
    pane(F, "doorglass", a, b, c, e, a + 0.1, b - 0.1, tr + 0.08, spring, w, wid)
    F.box("bronze", a, a + 0.1, c, spring, w - 0.04, w + 0.06)
    F.box("bronze", b - 0.1, b, c, spring, w - 0.04, w + 0.06)
    F.box("bronze", a, b, tr, tr + 0.08, w - 0.04, w + 0.08)
    for k in range(1, 5):
        uu = a + k * (b - a) / 5
        F.box("bronze", uu - 0.02, uu + 0.02, tr + 0.08, spring, w, w + 0.05)
    m0 = mid
    for l0, l1 in ((a + 0.1, m0 - 0.01), (m0 + 0.01, b - 0.1)):
        pane(F, "doorglass", a, b, c, e, l0 + 0.12, l1 - 0.12, c + 0.45, tr - 0.12, w - 0.01, wid)
        F.box("bronze", l0, l0 + 0.12, c, tr, w - 0.03, w + 0.03)
        F.box("bronze", l1 - 0.12, l1, c, tr, w - 0.03, w + 0.03)
        F.box("bronze", l0 + 0.12, l1 - 0.12, c, c + 0.45, w - 0.03, w + 0.03)
        F.box("bronze", l0 + 0.12, l1 - 0.12, tr - 0.12, tr, w - 0.03, w + 0.03)
        F.box("brass", l0 + 0.15, l1 - 0.15, c + 1.0, c + 1.06, w + 0.03, w + 0.08)
    # Two granite steps out of the opening, the lower one wider.
    for k, (hw, out, z) in enumerate(((b + 0.9, 0.85, 0.15), (b + 0.45, 0.45, 0.3))):
        F.box("granite", -hw, hw, 0.0, z, -deep if k else -0.2, out + CP, skip=("back", "bottom"))
    # The lanterns: bronze cages on brackets either side of the arch.
    for u in (a - 0.3, b + 0.3):
        q = F.p(u, 0, 0.42)
        F.box("bronze", u - 0.04, u + 0.04, 2.75, 2.83, 0.09, 0.42)
        m.cyl("bronze", q.x, q.y, 0.13, 2.4, 2.48, seg=8)
        m.cyl("lamp", q.x, q.y, 0.11, 2.48, 2.95, seg=8, top=False)
        m.cyl("bronze", q.x, q.y, 0.17, 2.95, 3.02, seg=8, r1=0.15)
        m.cyl("bronze", q.x, q.y, 0.15, 3.02, 3.2, seg=8, r1=0.02)
    # A bronze plate with the street number on the left jamb's face.
    F.box("bronze", a - 0.42, a - 0.12, 1.5, 1.85, 0.09, 0.11)


def arched_face(M, F, a, b, spring, deep):
    """The entrance arch's face on the rustication: spandrels, intrados and
    voussoirs, without the glass."""
    m = M.m
    mid, r = (a + b) / 2, (b - a) / 2
    top = spring + r
    pts = arc(mid, spring, r)
    for k in range(len(pts) - 1):
        p0, p1 = pts[k], pts[k + 1]
        corner = (a, top) if p1[0] <= mid + 1e-6 else (b, top)
        m.poly("ashlar", [F.p(*corner, 0), F.p(*p0, 0), F.p(*p1, 0)], out=F.n)
        ang = math.pi * (k + 0.5) / (len(pts) - 1)
        m.poly("stone", [F.p(*p0, 0), F.p(*p1, 0), F.p(*p1, -deep), F.p(*p0, -deep)], out=-F.t * (-math.cos(ang)) - Z * math.sin(ang))
    n = 11
    ro = r + 0.45
    for k in range(n):
        t0, t1 = math.pi * k / n, math.pi * (k + 1) / n
        q = [(mid - math.cos(t0) * r, spring + math.sin(t0) * r), (mid - math.cos(t0) * ro, spring + math.sin(t0) * ro),
             (mid - math.cos(t1) * ro, spring + math.sin(t1) * ro), (mid - math.cos(t1) * r, spring + math.sin(t1) * r)]
        m.poly("stone", [F.p(u, z, 0.09) for u, z in q], out=F.n)
        tm = (t0 + t1) / 2
        m.poly("stone", [F.p(*q[1], 0.0), F.p(*q[2], 0.0), F.p(*q[2], 0.09), F.p(*q[1], 0.09)], out=F.t * (-math.cos(tm)) + Z * math.sin(tm))
    F.box("stone", mid - 0.26, mid + 0.26, top - 0.15, top + 0.62, 0.0, 0.2, skip=("back",))
    # Plain dressed jambs from the plinth to the springing.
    for u0, u1 in ((a - 0.45, a), (b, b + 0.45)):
        F.box("stone", u0, u1, 0.0, spring, 0.0, 0.09, skip=("back", "bottom"))


def back(M, F, top):
    """The service side: square windows in the rustication, a goods door."""
    holes = [(u - 0.8, u + 0.8, 1.4, 4.2) for u in BAYS["back"] if abs(u) > 1e-6]
    door = (-1.0, 1.0, 0.0, 3.0)
    F.wall("ashlar", -HW, HW, PLINTH, top, holes + [(door[0], door[1], PLINTH, door[3])], depth=DEPTH, reveal="stone")
    for a, b, c, e in holes:
        sash(F, a, b, c, e, D=DEPTH, lights=(1, 1), fr="frame")
        F.box("stone", a - 0.1, b + 0.1, c - 0.1, c + 0.02, -DEPTH + 0.05, 0.1)
        F.box("stone", a - 0.15, b + 0.15, e, e + 0.32, 0.0, 0.06)
    a, b, c, e = door
    F.quad("door", a, b, 0.0, e, -DEPTH)
    for u0, u1 in ((a, a), (b, b)):
        out = F.t if u0 == a else -F.t
        F.m.poly("stone", [F.p(u0, 0.0, 0), F.p(u0, 0.0, -DEPTH), F.p(u0, PLINTH, -DEPTH), F.p(u0, PLINTH, 0)], out=out)
    F.box("stone", a - 0.2, b + 0.2, e, e + 0.4, 0.0, 0.08)
    F.m.poly("granite", [F.p(a, 0.0, 0), F.p(b, 0.0, 0), F.p(b, 0.0, -DEPTH), F.p(a, 0.0, -DEPTH)], out=Z)
    F.box("lamp", -0.15, 0.15, e + 0.5, e + 0.62, 0.0, 0.12)
    plinth(F, HW, "back", (a, b))


# ---- the shaft --------------------------------------------------------------------------------


def storey(M, z, first=False):
    m = M.m
    for name, F in sides(m, W, D).items():
        h = HALF[name]
        holes = [(u - WW[name] / 2, u + WW[name] / 2, z + SILL, z + HEAD) for u in BAYS[name]]
        panels = [(a + 0.05, b - 0.05, z + 0.18, c - 0.2, 0.05) for a, b, c, e in holes]
        F.wall("cladstone", -h, h, z, z + FL, holes + panels, depth=DEPTH, reveal="stone")
        for a, b, c, e in holes:
            mid = (a + b) / 2
            # A Chicago pair: two sashes either side of a stone mullion.
            sash(F, a, mid - 0.08, c, e, D=DEPTH, lights=(1, 1), fr="frame")
            sash(F, mid + 0.08, b, c, e, D=DEPTH, lights=(1, 1), fr="frame")
            F.box("stone", mid - 0.08, mid + 0.08, c, e, -DEPTH, -0.04, skip=("back",))
            F.box("stone", a - 0.1, b + 0.1, c - 0.09, c + 0.02, -DEPTH + 0.05, 0.09)
            # The spandrel under it: a sunk panel in a flat frame.
            F.quad("cladstone", a + 0.05, b - 0.05, z + 0.18, c - 0.2, -0.05)
            if first and name != "back":
                hood(F, a, b, e)
            else:
                F.box("stone", a - 0.08, b + 0.08, e, e + 0.22, 0.0, 0.03)
                F.box("stone", mid - 0.13, mid + 0.13, e - 0.05, e + 0.3, 0.0, 0.07)
        piers(F, name, z, z + FL)
    corners(m, z, z + FL)
    if first:
        # A belt course at the first storey's sill line.
        m.sweep("stone", W, D, [(-0.01, z + SILL - 0.24), (0.16, z + SILL - 0.24), (0.2, z + SILL - 0.16), (0.2, z + SILL - 0.1), (-0.01, z + SILL - 0.1)])
    core(m, z, z + FL)
    ceiling(m, z + FL - 0.01)


# ---- the top --------------------------------------------------------------------------------


def roof(M, z):
    m = M.m
    za = z + ATTIC
    # A course under the attic, the pilaster strips' caps on it.
    m.sweep("stone", W + 2 * CP, D + 2 * CP, [(-0.01, z), (0.06, z), (0.06, z + 0.22), (0.1, z + 0.28), (-0.01, z + 0.28)])
    for name, F in sides(m, W, D).items():
        h = HALF[name]
        holes = [(u - 0.65, u + 0.65, z + 0.75, z + 2.0) for u in BAYS[name]]
        F.wall("cladstone", -h, h, z, za, holes, depth=DEPTH, reveal="stone")
        for a, b, c, e in holes:
            sash(F, a, b, c, e, D=DEPTH, lights=(2, 1), fr="frame")
            F.box("stone", a - 0.08, b + 0.08, c - 0.08, c + 0.02, -DEPTH + 0.05, 0.08)
            # An eared architrave round the square window.
            for u0, u1 in ((a - 0.14, a), (b, b + 0.14)):
                F.box("stone", u0, u1, c, e, 0.0, 0.04)
            F.box("stone", a - 0.24, b + 0.24, e, e + 0.16, 0.0, 0.04)
        # The pilaster strips carry on as short pilasters with a capital.
        us = BAYS[name]
        for a, b in zip(us, us[1:]):
            mid = (a + b) / 2
            F.box("cladstone", mid - PW / 2, mid + PW / 2, z + 0.28, za - 0.3, 0.0, PIER, skip=("back", "bottom"))
            F.box("stone", mid - PW / 2 - 0.06, mid + PW / 2 + 0.06, za - 0.3, za, 0.0, PIER + 0.06, skip=("back",))
    corners(m, z + 0.28, za)
    entablature(M, za)


def entablature(M, za):
    """Architrave, frieze (the name cut in it on the front), the cornice on
    modillions over a row of dentils, the parapet, then the roof's plant."""
    m = M.m
    W2, D2 = W + 2 * CP, D + 2 * CP
    a0 = za
    a1 = a0 + 0.36  # architrave
    f1 = a1 + 0.62  # frieze
    m.sweep("stone", W2, D2, [(-0.01, a0), (0.02, a0), (0.02, a0 + 0.16), (0.05, a0 + 0.18), (0.05, a1 - 0.06), (0.09, a1), (0.0, a1)])
    m.sweep("cladstone", W2, D2, [(0.0, a1), (0.0, f1)])
    # The name, a decal so the bake leaves the frieze alone.
    F = sides(m, W2, D2)["front"]
    F.quad("stonename", -3.7, 3.7, a1 + 0.08, f1 - 0.08, 0.004, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    # The bed moulding, the dentils, the modillions under the soffit, the corona.
    d0 = f1 + 0.18  # the dentils' foot
    m.sweep("stone", W2, D2, [(0.0, f1), (0.06, f1), (0.1, f1 + 0.06), (0.12, f1 + 0.14), (0.12, d0)])
    sof = d0 + 0.24  # the soffit
    reach = 0.95
    for name, S in sides(m, W2, D2).items():
        hh = (W2 if name in ("front", "back") else D2) / 2
        n = int((2 * hh - 0.2) / 0.2)
        for i in range(n):
            u = -hh + 0.15 + i * (2 * hh - 0.3) / (n - 1)
            S.box("stone", u - 0.055, u + 0.055, d0, sof - 0.04, 0.12, 0.26, skip=("back", "top"))
        n = int((2 * hh - 0.4) / 0.62)
        for i in range(n):
            u = -hh + 0.4 + i * (2 * hh - 0.8) / (n - 1)
            # A modillion: a scrolled bracket, here a block and a deeper head.
            S.box("stone", u - 0.1, u + 0.1, sof - 0.2, sof, 0.12, reach - 0.08, skip=("back", "top"))
            S.box("stone", u - 0.11, u + 0.11, sof - 0.3, sof, 0.12, 0.42, skip=("back", "top"))
    m.sweep("stone", W2, D2, [(0.12, d0), (0.18, d0), (0.18, sof), (reach, sof), (reach, sof + 0.22), (reach + 0.05, sof + 0.26), (reach + 0.05, sof + 0.3),
                             (reach + 0.12, sof + 0.38), (reach + 0.12, sof + 0.44), (0.3, sof + 0.48)])
    top = sof + 0.48
    # The parapet: set back over the cornice, panelled, a coping on top.
    p0, p1 = top, top + PARAPET
    pw = 0.25
    m.sweep("stone", W2, D2, [(0.3, p0), (0.3, p0 + 0.12), (0.24, p0 + 0.18), (0.24, p1 - 0.14), (0.32, p1 - 0.08), (0.32, p1), (0.24 - pw, p1),
                             (0.24 - pw, p0 + 0.05)])
    for name, S in sides(m, W2, D2).items():
        hh = (W2 if name in ("front", "back") else D2) / 2
        n = round((2 * hh - 1.2) / 1.6)
        step = (2 * hh - 1.2) / n
        for i in range(n):
            u0 = -hh + 0.6 + i * step + 0.12
            S.box("cladstone", u0, u0 + step - 0.24, p0 + 0.3, p1 - 0.3, 0.24, 0.27, skip=("back",))
    deck = p0 + 0.05
    x0, y0 = -W2 / 2 - 0.24 + pw, -D2 / 2 - 0.24 + pw
    m.poly("roof", [(x0, y0, deck), (-x0, y0, deck), (-x0, -y0, deck), (x0, -y0, deck)], out=Z)
    penthouse(m, deck)
    tank(m, -3.6, 2.6, deck)
    # Vents and a skylight over the light well.
    for x in (-0.8, 0.8):
        m.cyl("ac", x, -2.6, 0.12, deck, deck + 1.1, seg=8)
        m.cyl("ac", x, -2.6, 0.2, deck + 1.1, deck + 1.25, seg=8, r1=0.05)
    m.box("ac", (-2.0, -1.2, deck), (2.0, 1.0, deck + 0.45), skip=("z0",))
    for k in range(2):
        xa, xb = -1.9 + k * 1.95, -0.05 + k * 1.95
        m.poly("skyglass", [(xa, -1.1, deck + 0.46), (xb, -1.1, deck + 0.46), (xb, -0.1, deck + 0.95), (xa, -0.1, deck + 0.95)], out=(0, -1, 1))
        m.poly("skyglass", [(xa, 0.9, deck + 0.46), (xb, 0.9, deck + 0.46), (xb, -0.1, deck + 0.95), (xa, -0.1, deck + 0.95)], out=(0, 1, 1))


def penthouse(m, deck):
    """The lift motor room: brick, a stone coping, a steel door to the roof."""
    x0, x1, y0, y1 = 2.2, 5.6, 1.6, 5.2
    h = 3.4
    m.box("brick", (x0, y0, deck), (x1, y1, deck + h), skip=("z0",))
    m.box("stone", (x0 - 0.1, y0 - 0.1, deck + h), (x1 + 0.1, y1 + 0.1, deck + h + 0.22))
    F = Side(m, ((x0 + x1) / 2, y0, 0), (1, 0, 0), (0, -1, 0))
    F.quad("door", -0.9, 0.1, deck, deck + 2.15, 0.01)
    F.box("stone", -1.0, 0.2, deck + 2.15, deck + 2.3, 0.0, 0.05)
    F.box("lamp", -0.55, -0.25, deck + 2.45, deck + 2.57, 0.0, 0.1)
    L = Side(m, (x0, (y0 + y1) / 2, 0), (0, -1, 0), (-1, 0, 0))
    L.quad("blades", -0.6, 0.6, deck + 1.6, deck + 2.6, 0.01, uvs=[(0, 0), (1.2, 0), (1.2, 1.0), (0, 1.0)])


def tank(m, x, y, deck):
    """A timber water tank on a steel stand: staves held by iron hoops, a
    conical roof with a hatch, a ladder up the side."""
    r, legs = 1.55, 3.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.box("iron", (x + sx * 1.0 - 0.08, y + sy * 1.0 - 0.08, deck), (x + sx * 1.0 + 0.08, y + sy * 1.0 + 0.08, deck + legs), skip=("z0",))
            m.box("concrete", (x + sx * 1.0 - 0.22, y + sy * 1.0 - 0.22, deck), (x + sx * 1.0 + 0.22, y + sy * 1.0 + 0.22, deck + 0.2), skip=("z0",))
    for sx in (-1, 1):
        m.strut("iron", (x + sx * 1.0, y - 1.0, deck + 0.4), (x - sx * 1.0, y - 1.0, deck + legs - 0.2), 0.05)
        m.strut("iron", (x - 1.0, y + sx * 1.0, deck + 0.4), (x - 1.0, y - sx * 1.0, deck + legs - 0.2), 0.05)
    m.box("iron", (x - 1.3, y - 1.3, deck + legs - 0.2), (x + 1.3, y + 1.3, deck + legs))
    z0, z1 = deck + legs, deck + legs + 3.2
    m.cyl("wood", x, y, r, z0, z1, seg=24, top=False, bottom=True, uv=True)
    for k in range(5):
        zz = z0 + 0.25 + k * 0.68
        m.cyl("iron", x, y, r + 0.025, zz, zz + 0.05, seg=24, top=False)
    m.cyl("wood", x, y, r + 0.08, z1, z1 + 0.9, seg=24, r1=0.12, uv=True)
    m.cyl("iron", x, y, 0.14, z1 + 0.9, z1 + 1.05, seg=8, r1=0.0)
    # The ladder up the stand and the tank, facing the penthouse.
    for dy in (-0.22, 0.22):
        m.box("iron", (x + r + 0.12, y + dy - 0.025, deck), (x + r + 0.17, y + dy + 0.025, z1 + 0.2))
    for k in range(int((z1 - deck) / 0.35)):
        zz = deck + 0.3 + k * 0.35
        m.box("iron", (x + r + 0.12, y - 0.22, zz), (x + r + 0.16, y + 0.22, zz + 0.03))
    for k in range(3):
        m.box("iron", (x + r * 0.7 + k * 0.0, y - 0.22, z0 - 0.05), (x + r + 0.15, y - 0.18, z0))
