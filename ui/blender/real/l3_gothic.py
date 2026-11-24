# L3, Gothic skyscraper: a cathedral of commerce of about 1915 on its own
# lot, 13.2 m square on a 1.65 m bay, faced in glazed cream terracotta.
# Slender piers run unbroken from the plinth to the top between recessed
# bays of windows over plain sunk spandrels; the corners are buttress
# turrets, wider than the piers. The ground storey has shop windows under
# pointed arches and in the middle a tall pointed portal of three orders
# round bronze doors and a traceried light, the name in gold over it.
# The shaft steps in once (13.2 to 9.9 m) behind a pierced parapet with a
# pinnacle on every pier. The crown is an arcade of tall lancets lit at
# night, its corners carried up as pinnacles, then a steep copper spire
# with lucarnes on its faces, a finial and the aircraft light. The app
# tints the metalwork and picks the name.
#
# Pieces (base at the origin, stacked by the app):
#   ground  7.0 m: plinth, arched shopfronts, the portal, the name
#   floor1  3.6 m: a storey of the lower tier, 8 bays a side
#   ledge1  its parapet, pinnacles and the terrace (no height)
#   floor2  3.6 m: the upper tier, 6 bays
#   crown   the upper parapet, the lancet arcade, pinnacles, the spire
import math

from lib import Model, Side, Z, fpoly, new_id, pane, sides

ID = "l3"
B = 1.65  # bay
X1, X2 = 6.6, 4.95
G = 7.0
FL = 3.6
SILL, HEAD = 0.9, 3.0
R = 0.28  # the bays' recess behind the piers
PW = 0.42  # piers
CW = 1.0  # the corner turrets, each way
ARC = 7.5  # the lancet arcade's height
SP = 13.0  # the spire's height over the arcade
GAP = 8.0  # between pieces in the bake


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M.m)
    # Pieces stand apart in the bake, so a storey's AO is its own, not the
    # shade of the ledge or crown next to it (repeated up every storey).
    z = G
    M.piece("floor1", (0, 0, z))
    storey(M.m, X1, z)
    z += FL + GAP
    M.piece("ledge1", (0, 0, z))
    parapet(M.m, X1, z, terrace_to=X2)
    z += GAP
    M.piece("floor2", (0, 0, z))
    storey(M.m, X2, z)
    z += FL + GAP
    M.piece("crown", (0, 0, z))
    crown(M.m, z)
    M.export(out, bake)


def lines(X):
    n = round(2 * X / B)
    return [-X + i * B for i in range(n + 1)]


def bays(X):
    ls = lines(X)
    n = len(ls) - 1
    return [(ls[i] + (CW if i == 0 else PW / 2), ls[i + 1] - (CW if i == n - 1 else PW / 2)) for i in range(n)]


def turrets(m, X, z0, z1, ends=("z0", "z1")):
    """The corner turrets: square, a chamfer on the outer edge."""
    k = 0.25
    for sx in (-1, 1):
        for sy in (-1, 1):
            a, b = X - CW, X + 0.1
            pts = [(a, a), (b - k, a), (b, a + k), (b, b - k), (b - k, b), (a, b)]
            pts = [(sx * x, sy * y) for x, y in pts]
            if sx * sy < 0:
                pts.reverse()
            for i in range(len(pts)):
                (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
                out = (y1 - y0, x0 - x1, 0)
                m.poly("cream", [(x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)], out=out)
            if "z1" not in ends:
                m.poly("cream", [(x, y, z1) for x, y in pts], out=Z)


def lancet(F, a, b, z0, z1, w, role, rise=None, draw=True):
    """A pointed-arched panel from z0 up to the apex at z1."""
    h = b - a
    s = z1 - (rise or h * 0.9)
    pts = [(a, z0), (b, z0), (b, s)]
    r = h  # equilateral arch: each side's centre at the other springing point
    for k in range(1, 6):
        t = k / 6 * math.radians(60)
        pts.append((a + r * math.cos(t), s + r * math.sin(t) * (z1 - s) / (r * math.sin(math.radians(60)))))
    pts.append(((a + b) / 2, z1))
    for k in range(5, 0, -1):
        t = k / 6 * math.radians(60)
        pts.append((b - r * math.cos(t), s + r * math.sin(t) * (z1 - s) / (r * math.sin(math.radians(60)))))
    pts.append((a, s))
    if draw:
        fpoly(F, role, pts, w=w)
    return pts


# ---- the shaft --------------------------------------------------------------------------


def window(F, a, b, c, e, glass="decoglass"):
    wid = new_id()
    gw = -R - 0.06
    pane(F, glass, a, b, c, e, a, b, c, e, gw, wid)
    for box in ((a, a + 0.06, c, e), (b - 0.06, b, c, e), (a, b, e - 0.07, e), (a, b, c, c + 0.08)):
        F.box("bronze", *box, gw - 0.01, -R + 0.02, skip=("back",))
    u = (a + b) / 2
    F.box("bronze", u - 0.03, u + 0.03, c, e, gw, gw + 0.04, skip=("back",))
    t = c + (e - c) * 0.72
    F.box("bronze", a, b, t - 0.03, t + 0.03, gw, gw + 0.04, skip=("back",))


def storey(m, X, z):
    for F in sides(m, 2 * X, 2 * X).values():
        for a, b in bays(X):
            F.quad("cream", a, b, z, z + SILL, -R)
            window(F, a, b, z + SILL, z + HEAD)
            F.quad("cream", a, b, z + HEAD, z + FL, -R)
            # A drip moulding over each window's head.
            F.box("cream", a, b, z + HEAD + 0.12, z + HEAD + 0.2, -R, -R + 0.06, skip=("back",))
        for u in lines(X)[1:-1]:
            F.box("cream", u - PW / 2, u + PW / 2, z, z + FL, -R, 0, skip=("back", "top", "bottom"))
            F.box("cream", u - 0.08, u + 0.08, z, z + FL, 0, 0.08, skip=("back", "top", "bottom"))
    turrets(m, X, z, z + FL)
    i = X - R
    m.poly("dark", [(-i, -i, z + FL - 0.02), (i, -i, z + FL - 0.02), (i, i, z + FL - 0.02), (-i, i, z + FL - 0.02)], out=-Z)


# ---- ground storey --------------------------------------------------------------------


def ground(m):
    S = sides(m, 2 * X1, 2 * X1)
    for name, F in S.items():
        for i, (a, b) in enumerate(bays(X1)):
            if name == "front" and i in (3, 4):
                continue
            shop_bay(F, a, b, glass="shopglass" if name != "back" else "decoglass")
        for u in lines(X1)[1:-1]:
            if name == "front" and abs(u) < 1.0:
                continue
            F.box("cream", u - PW / 2, u + PW / 2, 0.7, G, -R, 0, skip=("back", "top", "bottom"))
            F.box("granite", u - PW / 2 - 0.04, u + PW / 2 + 0.04, 0, 0.7, -R, 0.04, skip=("back", "bottom"))
        F.box("cream", -X1, X1, G - 0.35, G - 0.2, -R, 0.12, skip=("back",))
    turrets(m, X1, 0.7, G)
    turrets(m, X1 + 0.04, 0, 0.7, ends=("z0",))
    portal(m, S["front"])
    i = X1 - R
    m.poly("dark", [(-i, -i, G - 0.02), (i, -i, G - 0.02), (i, i, G - 0.02), (-i, i, G - 0.02)], out=-Z)


def shop_bay(F, a, b, glass):
    """Granite stallriser, a shop window, its head a pointed arch of traceried glass."""
    F.quad("granite", a, b, 0, 0.7, -R + 0.02)
    wid = new_id()
    pane(F, glass, a, b, 0.7, 3.6, a + 0.05, b - 0.05, 0.75, 3.6, -R - 0.06, wid)
    F.box("bronze", a, b, 0.7, 0.78, -R - 0.08, -R + 0.03, skip=("back",))
    F.box("bronze", a, b, 3.6, 3.68, -R - 0.08, -R + 0.03, skip=("back",))
    top = 5.6
    pts = lancet(F, a, b, 3.68, top, -R - 0.06, "decoglass")
    F.box("bronze", (a + b) / 2 - 0.025, (a + b) / 2 + 0.025, 3.68, top - 0.1, -R - 0.06, -R - 0.02, skip=("back",))
    # The stone round the arch: the bay's face above the head and between.
    fpoly(F, "cream", pts[2:] + [(a, G - 0.35), (b, G - 0.35)], w=-R)
    for u0, u1 in ((a, a + 0.04), (b - 0.04, b)):
        F.box("cream", u0, u1, 3.68, G - 0.35, -R, -R + 0.02, skip=("back",))


def portal(m, F):
    """The entrance: a pointed arch of three orders across the two middle bays,
    bronze doors and a traceried light in it, the name in gold over it."""
    orders = [(1.55, 5.9, 0.0), (1.35, 5.55, -0.2), (1.15, 5.2, -0.4)]
    outer = arch(F, *orders[0][:2])
    fpoly(F, "cream", outer + [(-2.15, 0), (-2.15, G - 0.35), (2.15, G - 0.35), (2.15, 0)], w=0.0)
    for (hw, top, w), (hw2, top2, w2) in zip(orders, orders[1:] + [(orders[-1][0], orders[-1][1], orders[-1][2] - 0.25)]):
        o, i = arch(F, hw, top), arch(F, hw2, top2)
        if hw2 < hw:
            fpoly(F, "cream", i + o[::-1], w=w2)
        # The soffit of this order, back to the next.
        for (u0, z0), (u1, z1) in zip(o, o[1:]):
            m.poly("cream", [F.p(u0, z0, w), F.p(u1, z1, w), F.p(u1, z1, w2), F.p(u0, z0, w2)], out=tuple(-F.t * (u0 + u1) - Z * (z0 + z1 - 2 * (top - hw * 0.9))))
    hw, top, w = orders[-1]
    D = Side(F.m, F.p(0, 0, w - 0.25), F.t, F.n)
    door = 3.0
    wid = new_id()
    lancet(D, -hw, hw, door + 0.12, top, 0.0, "decoglass")
    for a, b in ((-hw, -0.03), (0.03, hw)):
        D.quad("bronze", a, b, 0, door, 0.0)
        D.box("bronze", a + 0.12, b - 0.12, 0.3, door - 0.3, 0.0, 0.03, skip=("back",))
        pane(D, "doorglass", a, b, 0, door, a + 0.2, b - 0.2, 1.2, door - 0.4, 0.035, wid)
    D.quad("bronze", -0.03, 0.03, 0, door, 0.0)
    D.box("bronze", -hw, hw, door, door + 0.12, 0.0, 0.05, skip=("back",))
    D.box("bronze", -0.03, 0.03, door + 0.12, top - 0.2, 0.0, 0.04, skip=("back",))
    F.box("granite", -1.7, 1.7, 0, 0.15, w - 0.25, 0.3, skip=("back", "bottom"))
    # The name over the portal on a panel, pinnacled shafts either side.
    F.box("cream", -2.15, 2.15, 5.95, 6.32, 0, 0.06, skip=("back",))
    F.quad("deconame", -2.0, 2.0, 6.01, 6.26, 0.065, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    for u in (-1.85, 1.85):
        F.box("cream", u - 0.12, u + 0.12, 0, 5.95, 0.0, 0.18, skip=("back", "bottom"))
        F.box("cream", u - 0.09, u + 0.09, 6.32, 6.9, 0.03, 0.15, skip=("back",))
        p = F.p(u, 0, 0.09)
        m.cyl("copper", p.x, p.y, 0.12, 6.9, 7.5, seg=4, r1=0.0)


def arch(F, hw, top):
    """A pointed opening's outline from the right foot over the apex to the left foot."""
    pts = lancet(Side(F.m, F.o, F.t, F.n), -hw, hw, 0, top, 0, None, draw=False)
    return [(hw, 0)] + pts[2:] + [(-hw, 0)]


# ---- the setback and the crown ----------------------------------------------------------


def pinnacle(m, x, y, z, h, s=0.22, role="cream"):
    """A square pinnacle: a shaft, a crocketed cap as a slim pyramid, a copper ball."""
    m.box(role, (x - s, y - s, z), (x + s, y + s, z + h * 0.55))
    m.box(role, (x - s - 0.04, y - s - 0.04, z + h * 0.55), (x + s + 0.04, y + s + 0.04, z + h * 0.6))
    m.cyl(role, x, y, (s + 0.02) * math.sqrt(2), z + h * 0.6, z + h, seg=4, r1=0.02)
    m.cyl("copper", x, y, 0.05, z + h - 0.05, z + h + 0.1, seg=6)


def parapet(m, X, z, terrace_to=None, h=1.2):
    """A pierced parapet: a row of small pointed openings, a coping; a pinnacle on every pier and turret."""
    S = sides(m, 2 * X, 2 * X)
    for F in S.values():
        for a, b in bays(X):
            F.box("cream", a, b, z, z + 0.3, -R, -0.15, skip=("back", "left", "right"))
            F.box("cream", a, b, z + 0.3, z + h - 0.15, -R, -0.15, skip=("back", "left", "right", "bottom"))
            for k in range(2):
                u0 = a + (b - a) * k / 2 + 0.08
                u1 = a + (b - a) * (k + 1) / 2 - 0.08
                lancet(F, u0, u1, z + 0.4, z + h - 0.25, -0.13, "cream", rise=0.3)
            F.box("cream", a, b, z + h - 0.15, z + h, -R - 0.08, -0.1, skip=("left", "right"))
            F.quad("cream", a, b, z, z + h, -R - 0.02, out=-F.n)
        for u in lines(X)[1:-1]:
            F.box("cream", u - PW / 2, u + PW / 2, z, z + h + 0.2, -R, 0, skip=("back", "bottom"))
            p = F.p(u, 0, -R / 2)
            pinnacle(m, p.x, p.y, z + h + 0.2, 1.8, s=0.16)
    turrets(m, X, z, z + h + 0.5, ends=("z0",))
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = X - CW / 2 + 0.05
            pinnacle(m, sx * c, sy * c, z + h + 0.5, 3.2, s=0.3)
    if terrace_to:
        t = z + 0.1
        o = X - R
        i = terrace_to
        for x0, x1, y0, y1 in ((-o, o, -o, -i), (-o, o, i, o), (-o, -i, -i, i), (i, o, -i, i)):
            m.poly("pave", [(x0, y0, t), (x1, y0, t), (x1, y1, t), (x0, y1, t)], out=Z)


def crown(m, z):
    parapet(m, X2, z, terrace_to=XA)
    arcade(m, z + 0.1)
    spire(m, z + 0.1 + ARC)


XA = 3.3  # the arcade's half width


def arcade(m, z):
    """Tall lit lancets between slim shafts, three a side, under gables; corner pinnacles."""
    S = sides(m, 2 * XA, 2 * XA)
    w = 2 * XA / 3
    for F in S.values():
        for k in range(3):
            a, b = -XA + k * w + 0.22, -XA + (k + 1) * w - 0.22
            F.quad("cream", a, b, z, z + 0.8, -0.25)
            pts = lancet(F, a, b, z + 0.8, z + ARC - 1.0, -0.25, "crownglass")
            F.box("bronze", (a + b) / 2 - 0.025, (a + b) / 2 + 0.025, z + 0.8, z + ARC - 1.3, -0.25, -0.2, skip=("back",))
            for zz in (z + 2.6, z + 4.4):
                F.box("bronze", a, b, zz - 0.025, zz + 0.025, -0.25, -0.2, skip=("back",))
            # The wall round the arch's head, and the reveals.
            fpoly(F, "cream", pts[2:] + [(a, z + ARC), (b, z + ARC)], w=0.0)
            head = pts[2:]
            for (u0, z0), (u1, z1) in zip(head, head[1:]):
                m.poly("cream", [F.p(u0, z0, -0.25), F.p(u1, z1, -0.25), F.p(u1, z1, 0), F.p(u0, z0, 0)], out=tuple(-F.t * (u0 + u1 - a - b) - Z))
            for u0 in (a, b):
                m.poly("cream", [F.p(u0, z, -0.25), F.p(u0, z, 0), F.p(u0, pts[2][1], 0), F.p(u0, pts[2][1], -0.25)], out=tuple(F.t * (1 if u0 == a else -1)))
        for k in range(4):
            u = -XA + k * w
            u0, u1 = max(-XA, u - 0.22), min(XA, u + 0.22)
            F.quad("cream", u0, u1, z, z + ARC, 0.0)
        F.box("cream", -XA, XA, z + ARC, z + ARC + 0.25, -0.3, 0.1, skip=())
        # A gable over the middle lancet, rising into the spire.
        g = [(-w / 2, z + ARC + 0.25), (w / 2, z + ARC + 0.25), (0, z + ARC + 2.2)]
        fpoly(F, "cream", g, w=0.05)
        fpoly(F, "cream", g[::-1], w=-0.1, out=-F.n)
    for sx in (-1, 1):
        for sy in (-1, 1):
            pinnacle(m, sx * (XA + 0.1), sy * (XA + 0.1), z, ARC + 3.5, s=0.32)


def spire(m, z):
    """A steep copper spire, square, lucarnes on its faces, a finial and the aircraft light."""
    base = [(-XA, -XA), (XA, -XA), (XA, XA), (-XA, XA)]
    top = z + 0.25 + SP
    for i in range(4):
        (x0, y0), (x1, y1) = base[i], base[(i + 1) % 4]
        out = (y1 - y0, x0 - x1, XA * 2 / SP * 4)
        m.poly("copper", [(x0, y0, z + 0.25), (x1, y1, z + 0.25), (0, 0, top)], out=out)
        m.strut("copper", (x0, y0, z + 0.3), (0, 0, top), 0.12)
    # Lucarnes: small gabled openings low on each face.
    for F in sides(m, 2 * XA, 2 * XA).values():
        zz = z + 3.4
        inset = XA * (zz - z - 0.25) / SP
        L = Side(m, F.p(0, 0, -inset), F.t, F.n)
        L.box("copper", -0.5, 0.5, zz, zz + 1.2, -0.6, 0.0, skip=("back",))
        L.quad("crownglass", -0.32, 0.32, zz + 0.15, zz + 0.95, 0.005)
        for s in (-1, 1):
            m.poly("copper", [L.p(0, zz + 1.75, 0.05), L.p(s * 0.62, zz + 1.15, 0.05), L.p(s * 0.62, zz + 1.15, -0.9), L.p(0, zz + 1.75, -1.2)], out=tuple(F.t * s + Z))
        fpoly(L, "copper", [(-0.62, zz + 1.15), (0.62, zz + 1.15), (0, zz + 1.75)], w=0.05)
    m.cyl("bronze", 0, 0, 0.12, top - 0.3, top + 2.4, seg=8, r1=0.03)
    m.cyl("bronze", 0, 0, 0.22, top + 0.4, top + 0.6, seg=8, bottom=True)
    m.cyl("beacon", 0, 0, 0.07, top + 2.4, top + 2.65, seg=8)
