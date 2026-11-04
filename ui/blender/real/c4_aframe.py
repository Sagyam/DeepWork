# C4, A-frame cabin: a 1960s holiday A-frame, its 60-degree roof of cedar
# shakes coming down nearly to the ground on both sides. The street gable is
# glazed from the floor to the ridge in a timber grid, with sliding doors onto
# a deck that runs out from under the roof's prow; the ridge beam pokes out
# past it. A shed dormer on the right slope gives the sleeping loft its
# headroom, two rooflights light the left slope, and a wood stove's pipe
# comes through it. The back gable is boarded, with the back door on a
# landing, the kitchen window and a woodpile under the overhang. The app
# stains the boards and tints the shakes, the trim and the door per cabin.
#
# Pieces (base at the origin):
#   body  platform, deck, landing, woodpile and the gables up to the loft floor
#   roof  the roof, the gables above the loft floor, dormer, rooflights, pipe
import math

from lib import Model, Side, Z, glazing, new_id, pane

ID = "c4"
K = math.tan(math.radians(60))  # roof pitch
FL = 0.6  # floor level, on the platform
HW = 3.9  # inner half-width of the A at floor level
ZA = FL + HW * K  # underside of the ridge
TV = 0.22 / math.cos(math.radians(60))  # roof thickness, measured vertically
ZO = ZA + TV  # the ridge, outside
ZE = 0.4  # the eaves' underside
XEI, XEO = (ZA - ZE) / K, (ZO - ZE) / K  # the eaves, inside and outside
L = 8.0  # gable to gable
CY = 0.98  # the house's centre: the deck in front and the landing behind keep the footprint centred
Y0, Y1 = CY - L / 2, CY + L / 2  # front (street) and back gables
YF, YB = Y0 - 1.0, Y1 + 0.45  # the roof's prow and back overhang
DECK, DW = 2.4, 3.2  # the deck's depth and half-width
TOP = 3.35  # the loft floor: top of the body piece
DH = FL + 2.2  # head of the sliding doors
ZT = 5.35  # the upper transom in the front glass
MW, MD = 0.1, 0.2  # mullions: width and depth
PER = 0.14  # the rafter framing the gable, measured square to the roof
XD, ZDE, KD = 2.5, 5.55, math.tan(math.radians(18))  # dormer: front wall, eaves, pitch
YD0, YD1 = CY - 1.5, CY + 1.5
PIPE = (-1.0, CY + 2.4)  # the stove pipe through the left slope


def hw(z):
    """Inner half-width of the A at height z."""
    return (ZA - z) / K


def zo(x):
    """Height of the roof's outer surface at horizontal distance x from the ridge."""
    return ZO - abs(x) * K


def build(out, bake=True):
    M = Model(ID)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    M.export(out, bake)


# ---- helpers ------------------------------------------------------------------------


def area(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def clip(poly, inset):
    """Clips a polygon of (x, z) to inside the A, `inset` in from its roof lines (measured square to them)."""
    dz = inset / math.cos(math.radians(60))
    for s in (1, -1):
        f = lambda p: ZA - dz - s * p[0] * K - p[1]  # noqa: E731
        out = []
        for a, b in zip(poly, poly[1:] + poly[:1]):
            fa, fb = f(a), f(b)
            if fa >= 0:
                out.append(a)
            if (fa >= 0) != (fb >= 0):
                t = fa / (fa - fb)
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        poly = out
        if len(poly) < 3:
            return []
    return poly


def dedupe(pts):
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > 1e-5:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1]) < 1e-5:
        out.pop()
    return out


def rafter(m, y, z0, z1, d=MD):
    """The gable's framing rafters along both roof lines from z0 to z1, just inside them."""
    for s in (1, -1):
        n = (-s * math.sin(math.radians(60)), -math.cos(math.radians(60)))  # into the A
        o = PER / 2 - 0.01
        a = (s * hw(z0) + n[0] * o, y, z0 + n[1] * o)
        b = (s * hw(z1) + n[0] * o, y, z1 + n[1] * o)
        m.strut("timber", a, b, d, PER)


def panes(m, y, xs, z0, z1, wid, box, skip=()):
    """Glass between mullions at xs from z0 to z1 in the gable at y, clipped to the A;
    UVs over the opening `box` (a, b, c, e) for the interior shader."""
    a, b, c, e = box
    edges = [-HW - 1] + list(xs) + [HW + 1]
    for i in range(len(edges) - 1):
        if i in skip:
            continue
        x0 = edges[i] + (MW / 2 if i else 0)
        x1 = edges[i + 1] - (MW / 2 if i < len(edges) - 2 else 0)
        poly = clip([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], PER - 0.02)
        if len(poly) < 3 or area(poly) < 0.01:
            continue
        uvs = [(wid + (x - a) / (b - a), (z - c) / (e - c)) for x, z in poly]
        m.poly("glass", [(x, y, z) for x, z in poly], out=(0, -1, 0), uvs=uvs)


def mullions(m, y, xs, z0, z1):
    """Timber mullions at xs from z0 up to z1 or the rafter, whichever is lower."""
    for x in xs:
        top = min(z1, ZA - (abs(x) + MW / 2) * K - PER)
        if top > z0:
            m.box("timber", (x - MW / 2, y - MD / 2, z0), (x + MW / 2, y + MD / 2, top))


def transom(m, y, z, t=0.1, d=MD):
    """A horizontal timber bar across the A at height z (its middle), `t` deep."""
    w = hw(z - t / 2)
    m.box("timber", (-w, y - d / 2, z - t / 2), (w, y + d / 2, z + t / 2))


def gable_wall(F, role, z0, z1, holes, depth=0.1, reveal="timber"):
    """A gable wall filling the A between z0 and z1 (u = 0 at the ridge) with openings
    (a, b, c, e); like Side.wall, with the outer edges along the roof lines."""
    zs = sorted({z0, z1, *[c for h in holes for c in h[2:4] if z0 < c < z1]})
    for za, zb in zip(zs, zs[1:]):
        wa, wb = hw(za), hw(zb)
        cover = sorted((h[0], h[1]) for h in holes if h[2] <= za + 1e-6 and h[3] >= zb - 1e-6)
        segs, u = [], None
        for a, b in cover:
            segs.append((u, a))
            u = b
        segs.append((u, None))
        for ua, ub in segs:
            pts = dedupe([(-wa if ua is None else ua, za), (wa if ub is None else ub, za), (wb if ub is None else ub, zb), (-wb if ua is None else ua, zb)])
            if len(pts) >= 3 and area(pts) > 1e-4:
                F.m.poly(role, [F.p(u_, z_) for u_, z_ in pts], out=F.n)
    for a, b, c, e in holes:
        d = depth
        F.m.poly(reveal, [F.p(a, c, 0), F.p(a, c, -d), F.p(a, e, -d), F.p(a, e, 0)], out=F.t)
        F.m.poly(reveal, [F.p(b, c, 0), F.p(b, c, -d), F.p(b, e, -d), F.p(b, e, 0)], out=-F.t)
        F.m.poly(reveal, [F.p(a, e, 0), F.p(b, e, 0), F.p(b, e, -d), F.p(a, e, -d)], out=-Z)
        F.m.poly(reveal, [F.p(a, c, 0), F.p(b, c, 0), F.p(b, c, -d), F.p(a, c, -d)], out=Z)


def casing(F, a, b, c, e, sill=True):
    """Flat timber casing round an opening, with a sloped sill."""
    F.box("timber", a - 0.08, a, c, e, 0, 0.025)
    F.box("timber", b, b + 0.08, c, e, 0, 0.025)
    F.box("timber", a - 0.08, b + 0.08, e, e + 0.1, 0, 0.03)
    if sill:
        F.box("timber", a - 0.1, b + 0.1, c - 0.06, c, -0.06, 0.06)


def rail_run(m, x0, y0, x1, y1, z, role="timber"):
    """A deck railing between two posts: top and bottom rails, square balusters."""
    Ln = math.hypot(x1 - x0, y1 - y0)
    tx, ty = (x1 - x0) / Ln, (y1 - y0) / Ln
    nx, ny = -ty, tx

    def bar(s0, s1, o0, o1, z0, z1):
        p0 = (x0 + tx * s0 + nx * o0, y0 + ty * s0 + ny * o0)
        p1 = (x0 + tx * s1 + nx * o1, y0 + ty * s1 + ny * o1)
        m.box(role, (p0[0], p0[1], z0), (p1[0], p1[1], z1))

    bar(0.06, Ln - 0.06, -0.07, 0.07, z + 0.9, z + 0.95)
    bar(0.06, Ln - 0.06, -0.03, 0.03, z + 0.84, z + 0.9)
    bar(0.06, Ln - 0.06, -0.03, 0.03, z + 0.06, z + 0.12)
    n = int((Ln - 0.12) / 0.12)
    for i in range(n):
        s = 0.06 + (i + 0.5) * (Ln - 0.12) / n
        bar(s - 0.02, s + 0.02, -0.02, 0.02, z + 0.12, z + 0.84)


def lantern(F, u, z, w):
    """A small wall lantern hanging under a bracket at (u, z) on a face at w: iron caps, a glowing glass."""
    F.box("iron", u - 0.03, u + 0.03, z - 0.08, z + 0.04, w, w + 0.1)
    F.box("iron", u - 0.07, u + 0.07, z - 0.11, z - 0.08, w + 0.03, w + 0.17, skip=())
    F.box("lamp", u - 0.05, u + 0.05, z - 0.3, z - 0.11, w + 0.05, w + 0.15, skip=())
    F.box("iron", u - 0.06, u + 0.06, z - 0.33, z - 0.3, w + 0.04, w + 0.16, skip=())


def post(m, x, y, z0, z1, r=0.06):
    m.box("timber", (x - r, y - r, z0), (x + r, y + r, z1))


def chair(m, x, y, z):
    """An Adirondack chair facing the street (-y): slatted seat and back, broad arms."""
    m.strut("chair", (x, y - 0.32, z + 0.4), (x, y + 0.18, z + 0.3), 0.56, 0.04)
    m.strut("chair", (x, y + 0.16, z + 0.3), (x, y + 0.5, z + 0.98), 0.5, 0.04)
    for k in (-1, 1):
        u = x + k * 0.34
        m.box("chair", (u - 0.065, y - 0.42, z + 0.6), (u + 0.065, y + 0.24, z + 0.63))
        m.box("chair", (u - 0.025, y - 0.36, z), (u + 0.025, y - 0.3, z + 0.6))
        m.strut("chair", (x + k * 0.29, y - 0.34, z + 0.02), (x + k * 0.29, y + 0.36, z + 0.24), 0.04, 0.09)
        m.box("chair", (u - 0.025, y + 0.18, z + 0.3), (u + 0.025, y + 0.24, z + 0.6))


def logs(m, x0, x1, y0, y1, rows, R):
    """A stack of split logs lying along y, cut ends to the back."""
    r = 0.085
    for j in range(rows):
        n = int((x1 - x0) / (2 * r))
        for i in range(n - (j % 2)):
            cx = x0 + r + (j % 2) * r + i * 2 * r + (R.random() - 0.5) * 0.02
            cz = 0.14 + r + j * 2 * r * 0.88
            rr = r * (0.85 + 0.25 * R.random())
            ya, yb = y0 + R.random() * 0.04, y1 - R.random() * 0.04
            ring = [(cx + math.cos(a) * rr, cz + math.sin(a) * rr) for a in (k * math.tau / 6 + 0.3 * j for k in range(6))]
            for (ax, az), (bx, bz) in zip(ring, ring[1:] + ring[:1]):
                m.poly("bark", [(ax, ya, az), (bx, ya, bz), (bx, yb, bz), (ax, yb, az)], out=((ax + bx) / 2 - cx, 0, (az + bz) / 2 - cz))
            m.poly("logend", [(px, yb, pz) for px, pz in ring], out=(0, 1, 0))


def slope_box(m, top, side, s, xa, xb, ya, yb, h):
    """A box standing h proud of the roof slope on side s: x is horizontal distance from the ridge."""
    sn = (s * math.sin(math.radians(60)), 0, math.cos(math.radians(60)))

    def P(x, y, k):
        return (s * x + sn[0] * k, y, zo(x) + sn[2] * k)

    m.poly(top, [P(xa, ya, h), P(xb, ya, h), P(xb, yb, h), P(xa, yb, h)], out=sn)
    up = (-s * math.cos(math.radians(60)), 0, math.sin(math.radians(60)))
    m.poly(side, [P(xa, ya, 0), P(xa, yb, 0), P(xa, yb, h), P(xa, ya, h)], out=up)
    m.poly(side, [P(xb, ya, 0), P(xb, yb, 0), P(xb, yb, h), P(xb, ya, h)], out=tuple(-c for c in up))
    m.poly(side, [P(xa, ya, 0), P(xb, ya, 0), P(xb, ya, h), P(xa, ya, h)], out=(0, -1, 0))
    m.poly(side, [P(xa, yb, 0), P(xb, yb, 0), P(xb, yb, h), P(xa, yb, h)], out=(0, 1, 0))


# ---- body -------------------------------------------------------------------------


def body(M):
    m = M.m
    # The platform on a concrete foundation, its rim board under the eaves.
    m.box("concrete", (-HW + 0.15, Y0, 0), (HW - 0.15, Y1, FL - 0.22), skip=("z0", "z1"))
    m.box("timber", (-HW, Y0, FL - 0.25), (HW, Y1, FL), skip=("z0",))
    front_low(m)
    back_low(m)
    deck(m)
    landing(m)
    # The woodpile under the back overhang, between two posts on sleepers.
    x0, x1 = 1.2, 2.7
    for y in (Y1 + 0.12, Y1 + 0.42):
        m.box("timber", (x0 - 0.05, y - 0.04, 0), (x1 + 0.05, y + 0.04, 0.14))
    for x in (x0 - 0.04, x1 + 0.04):
        for y in (Y1 + 0.1, Y1 + 0.44):
            post(m, x, y, 0, 1.25, 0.035)
    logs(m, x0, x1, Y1 + 0.06, Y1 + 0.5, 4, M.R)
    # Inside, under the roof: dark slopes and a ceiling, seen only when the roof is gone.
    for s in (1, -1):
        a, b = hw(FL) - 0.03, hw(TOP) - 0.03
        m.poly("dark", [(s * a, Y0, FL), (s * a, Y1, FL), (s * b, Y1, TOP), (s * b, Y0, TOP)], out=(s, 0, 0.6))
    w = hw(TOP)
    m.poly("dark", [(-w, Y0, TOP - 0.02), (w, Y0, TOP - 0.02), (w, Y1, TOP - 0.02), (-w, Y1, TOP - 0.02)], out=Z)


def front_low(m):
    """The street gable up to the loft: glass in a timber grid, sliding doors in the middle bay."""
    y = Y0
    wid = new_id()
    box = (-HW, HW, FL, TOP - 0.25)
    m.box("timber", (-HW, y - 0.12, FL - 0.06), (HW, y + 0.1, FL + 0.08))
    rafter(m, y, FL, TOP)
    xs = [-2.6, -1.3, 1.3, 2.6]
    mullions(m, y, xs, FL + 0.08, TOP - 0.25)
    mullions(m, y, [0.0], DH, TOP - 0.25)
    transom(m, y, DH)
    transom(m, y, TOP - 0.13, t=0.26, d=0.26)  # the loft floor's edge beam
    panes(m, y, xs, FL + 0.08, DH - 0.05, wid, box, skip=(2,))
    panes(m, y, [-2.6, -1.3, 0.0, 1.3, 2.6], DH + 0.05, TOP - 0.26, wid, box)
    # Sliding doors: two leaves, one in front of the other.
    F = Side(m, (0, y, 0), (1, 0, 0), (0, -1, 0))
    for a, b, w in ((-1.25, 0.03, 0.035), (-0.03, 1.25, -0.035)):
        c, e = FL + 0.08, DH - 0.05
        f, g = 0.06, 0.03
        F.box("timber", a, a + f, c, e, w - g, w + g, skip=())
        F.box("timber", b - f, b, c, e, w - g, w + g, skip=())
        F.box("timber", a + f, b - f, c, c + 0.1, w - g, w + g, skip=())
        F.box("timber", a + f, b - f, e - f, e, w - g, w + g, skip=())
        pane(F, "glass", *box, a + f, b - f, c + 0.1, e - f, w, wid)
    F.box("iron", -0.12, -0.09, FL + 0.9, FL + 1.2, 0.065, 0.085)
    F.box("iron", 0.09, 0.12, FL + 0.9, FL + 1.2, -0.005, 0.015)
    # A wall light on the mullion beside the doors.
    lantern(F, 1.3, DH - 0.4, MD / 2)


def back_low(m):
    """The back gable up to the loft, boarded: the back door, the kitchen window, a wall light."""
    B = Side(m, (0, Y1, 0), (-1, 0, 0), (0, 1, 0))  # u = -x
    door = (0.7, 1.6, FL, FL + 2.1)
    win = (-1.3, -0.4, 1.55, 2.65)
    gable_wall(B, "boards", FL, TOP, [door, win])
    rafter(m, Y1, FL, TOP)
    B.box("timber", -hw(FL), hw(FL), FL, FL + 0.14, 0, 0.03)
    a, b, c, e = door
    B.box("timber", a, b, c, e, -0.1, -0.06)
    B.quad("door", a + 0.05, b - 0.05, c, e - 0.05, -0.05)
    pane(B, "glass", *door, a + 0.25, b - 0.25, c + 1.3, c + 1.85, -0.045, new_id())
    for z0, z1 in ((c + 0.2, c + 1.15),):
        B.box("door", a + 0.15, b - 0.15, z0, z1, -0.05, -0.03)
    B.box("iron", b - 0.17, b - 0.12, c + 0.95, c + 1.05, -0.05, 0.0)
    casing(B, a, b, c, e, sill=False)
    glazing(B, *win, lights=2, D=0.08, fr="timber")
    casing(B, *win)
    lantern(B, b + 0.23, c + 2.0, 0.0)


def deck(m):
    """The deck out from under the prow: boards on a rim joist and posts, railings, steps down."""
    top, yd = FL - 0.03, Y0 - DECK
    m.box("deck", (-DW, yd, top - 0.05), (DW, Y0, top), skip=("y1",))
    m.box("timber", (-DW + 0.02, yd + 0.02, top - 0.3), (DW - 0.02, Y0, top - 0.05), skip=("y1", "z1"))
    m.poly("dark", [(-DW + 0.2, yd + 0.2, 0), (DW - 0.2, yd + 0.2, 0), (DW - 0.2, yd + 0.2, top - 0.3), (-DW + 0.2, yd + 0.2, top - 0.3)], out=(0, -1, 0))
    for x, s in ((-DW + 0.2, -1), (DW - 0.2, 1)):
        m.poly("dark", [(x, yd + 0.2, 0), (x, Y0, 0), (x, Y0, top - 0.3), (x, yd + 0.2, top - 0.3)], out=(s, 0, 0))
    for x in (-DW + 0.12, -0.9, 0.9, DW - 0.12):
        m.box("timber", (x - 0.08, yd + 0.04, 0), (x + 0.08, yd + 0.2, top - 0.3))
        m.box("concrete", (x - 0.14, yd + 0.0, 0), (x + 0.14, yd + 0.24, 0.06), skip=("z0",))
    # Railings round three sides, open over the steps.
    py = yd + 0.07
    for x in (-DW + 0.07, -0.9, 0.9, DW - 0.07):
        post(m, x, py, top - 0.2, top + 1.0)
    rail_run(m, -DW + 0.07, py, -0.9, py, top)
    rail_run(m, 0.9, py, DW - 0.07, py, top)
    for x in (-DW + 0.07, DW - 0.07):
        rail_run(m, x, py, x, Y0 - 0.1, top)
        post(m, x, Y0 - 0.1, top, top + 0.95, 0.05)
    # Steps: three risers down to the path, on stringers.
    for i, z in enumerate((top - 0.19, top - 0.38)):
        y = yd - 0.28 * (i + 1)
        m.box("deck", (-0.82, y, z - 0.05), (0.82, y + 0.3, z), skip=())
        m.box("timber", (-0.8, y + 0.02, 0), (0.8, y + 0.04, z - 0.05), skip=("z0",))
    for x in (-0.86, 0.82):
        m.poly("timber", [(x, yd, 0), (x, yd - 0.62, 0), (x, yd, top - 0.05)], out=(-1, 0, 0))
        m.poly("timber", [(x + 0.04, yd, 0), (x + 0.04, yd - 0.62, 0), (x + 0.04, yd, top - 0.05)], out=(1, 0, 0))
    chair(m, -2.3, Y0 - 1.3, top)
    chair(m, -1.0, Y0 - 1.45, top)
    m.box("chair", (-1.75, Y0 - 1.75, top + 0.4), (-1.55, Y0 - 1.55, top + 0.43))
    m.box("chair", (-1.68, Y0 - 1.68, top), (-1.62, Y0 - 1.62, top + 0.4))


def landing(m):
    """A small landing at the back door with two steps down beside it."""
    x0, x1, y1 = -2.0, -0.3, Y1 + 1.0
    top = FL - 0.03
    m.box("deck", (x0, Y1, top - 0.05), (x1, y1, top), skip=("y0",))
    m.box("timber", (x0 + 0.02, Y1, 0), (x1 - 0.02, y1 - 0.02, top - 0.05), skip=("y0", "z0", "z1"))
    for i, z in enumerate((top - 0.19, top - 0.38)):
        x = x1 + 0.28 * i
        m.box("deck", (x, Y1 + 0.1, z - 0.05), (x + 0.3, y1 - 0.05, z), skip=())
        m.box("timber", (x + 0.02, Y1 + 0.12, 0), (x + 0.28, y1 - 0.07, z - 0.05), skip=("z0", "z1"))


# ---- roof -------------------------------------------------------------------------


def roof(M):
    m = M.m
    for s in (1, -1):
        slab(m, s)
    # The ridge: a cap of shakes, and the ridge beam running out past the prow.
    for s in (1, -1):
        m.poly("shake", [(s * 0.16, YF - 0.03, zo(0.16) + 0.06), (s * 0.16, YB + 0.03, zo(0.16) + 0.06), (0, YB + 0.03, ZO + 0.07), (0, YF - 0.03, ZO + 0.07)], out=(s, 0, 1))
    for y, k in ((YF - 0.03, -1), (YB + 0.03, 1)):
        m.poly("shake", [(-0.16, y, zo(0.16) + 0.06), (0.16, y, zo(0.16) + 0.06), (0, y, ZO + 0.07)], out=(0, k, 0))
    m.box("timber", (-0.09, YF - 0.35, ZA - 0.5), (0.09, YB, ZA - 0.14))
    front_high(m)
    back_high(m)
    dormer(m)
    for ya in (CY - 2.6, CY - 0.6):
        slope_box(m, "iron", "iron", -1, 1.75, 2.6, ya, ya + 0.85, 0.11)
        slope_box(m, "skyglass", "iron", -1, 1.8, 2.55, ya + 0.05, ya + 0.8, 0.13)
    # The stove pipe, with a storm collar where it comes through and a rain cap.
    x, y = PIPE
    zr = zo(x)
    m.cyl("iron", x, y, 0.26, zr - 0.5, zr + 0.35, seg=14, r1=0.11, top=False)
    m.cyl("iron", x, y, 0.1, zr, ZO + 0.45, seg=14, top=False)
    m.cyl("iron", x, y, 0.13, ZO + 0.1, ZO + 0.16, seg=14, top=False)
    m.cyl("iron", x, y, 0.21, ZO + 0.55, ZO + 0.58, seg=14, bottom=True, top=False)
    m.cyl("iron", x, y, 0.21, ZO + 0.58, ZO + 0.7, seg=14, r1=0.03)
    for k in range(3):
        a = k * math.tau / 3
        px, py = x + math.cos(a) * 0.08, y + math.sin(a) * 0.08
        m.box("iron", (px - 0.012, py - 0.012, ZO + 0.45), (px + 0.012, py + 0.012, ZO + 0.55))


def slab(m, s):
    """One side of the A: shakes on top (around the dormer on the right), boarded underneath, timber edges."""
    def top(xa, xb, ya, yb):
        d = lambda x: (XEO - x) / math.cos(math.radians(60))  # noqa: E731
        m.poly("shake", [(s * xb, ya, zo(xb)), (s * xb, yb, zo(xb)), (s * xa, yb, zo(xa)), (s * xa, ya, zo(xa))], out=(s * K, 0, 1), uvs=[(ya, d(xb)), (yb, d(xb)), (yb, d(xa)), (ya, d(xa))])

    if s > 0:
        xr = dormer_xr()
        top(0, XEO, YF, YD0)
        top(XD, XEO, YD0, YD1)
        top(0, xr, YD0, YD1)
        top(0, XEO, YD1, YB)
    else:
        top(0, XEO, YF, YB)
    m.poly("boards", [(s * XEI, YF, ZE), (s * XEI, YB, ZE), (0, YB, ZA), (0, YF, ZA)], out=(-s, 0, -1))
    m.poly("timber", [(s * XEI, YF, ZE), (s * XEO, YF, ZE), (s * XEO, YB, ZE), (s * XEI, YB, ZE)], out=-Z)
    for y, k in ((YF, -1), (YB, 1)):
        m.poly("timber", [(s * XEI, y, ZE), (s * XEO, y, ZE), (0, y, ZO), (0, y, ZA)], out=(0, k, 0))
    # A drip edge along the eaves.
    m.box("iron", (s * XEO - 0.03, YF, ZE - 0.02), (s * XEO + 0.03, YB, ZE + 0.06))


def front_high(m):
    """The street gable above the loft floor: glass to the ridge in a timber grid."""
    y = Y0
    wid = new_id()
    box = (-hw(TOP), hw(TOP), TOP, ZA)
    rafter(m, y, TOP, ZA)
    xs = [-1.3, 0.0, 1.3]
    mullions(m, y, xs, TOP, ZA)
    transom(m, y, ZT)
    panes(m, y, xs, TOP, ZT - 0.05, wid, box)
    panes(m, y, xs, ZT + 0.05, ZA, wid, box)


def back_high(m):
    """The back gable above the loft floor, boarded: the loft window and a louvred vent."""
    B = Side(m, (0, Y1, 0), (-1, 0, 0), (0, 1, 0))
    win = (-0.6, 0.6, 4.0, 5.2)
    vent = (-0.3, 0.3, 6.0, 6.4)
    gable_wall(B, "boards", TOP, ZA, [win, vent])
    rafter(m, Y1, TOP, ZA)
    glazing(B, *win, lights=2, D=0.08, fr="timber")
    casing(B, *win)
    a, b, c, e = vent
    B.quad("dark", a, b, c, e, -0.08)
    for i in range(4):
        z = c + 0.05 + i * 0.1
        B.box("timber", a, b, z, z + 0.05, -0.08, -0.02)
    casing(B, *vent, sill=False)
    # The loft floor's edge on the outside, a belt board.
    B.box("timber", -hw(TOP), hw(TOP), TOP - 0.1, TOP + 0.06, 0, 0.03)


def dormer_xr():
    """Where the dormer's roof underside meets the main roof: horizontal distance from the ridge."""
    return (ZO - ZDE - XD * KD) / (K - KD)


def dormer(m):
    """A shed dormer on the right slope: a boarded front with two windows, boarded cheeks, a shake roof."""
    xr = dormer_xr()
    zr = zo(xr)
    zb = zo(XD)
    F = Side(m, (XD, 0, 0), (0, 1, 0), (1, 0, 0))  # u = y
    wins = [(CY - 1.15, CY - 0.15, 3.85, 5.15), (CY + 0.15, CY + 1.15, 3.85, 5.15)]
    F.wall("boards", YD0, YD1, zb, ZDE, wins, depth=0.1, reveal="timber")
    for w in wins:
        glazing(F, *w, lights=2, D=0.08, fr="timber")
        casing(F, *w)
    for u0, u1 in ((YD0, YD0 + 0.1), (YD1 - 0.1, YD1)):
        F.box("timber", u0, u1, zb, ZDE, 0, 0.03)
    # Flashing where the front wall stands on the roof.
    F.box("iron", YD0 - 0.02, YD1 + 0.02, zb - 0.02, zb + 0.08, 0, 0.05)
    for y, k in ((YD0, -1), (YD1, 1)):
        m.poly("boards", [(XD, y, zb), (XD, y, ZDE), (xr, y, zr)], out=(0, k, 0))
    # The roof: overhanging the front and sides, timber fascias.
    TD = 0.16
    xo = XD + 0.3
    ya, yb = YD0 - 0.25, YD1 + 0.25
    zu = lambda x: ZDE + (XD - x) * KD  # noqa: E731
    xt = (ZO - ZDE - TD - XD * KD) / (K - KD)
    d = lambda x: (xo - x) / math.cos(math.atan(KD))  # noqa: E731
    m.poly("shake", [(xo, ya, zu(xo) + TD), (xo, yb, zu(xo) + TD), (xt, yb, zu(xt) + TD), (xt, ya, zu(xt) + TD)], out=(KD, 0, 1), uvs=[(ya, d(xo)), (yb, d(xo)), (yb, d(xt)), (ya, d(xt))])
    m.poly("boards", [(xo, ya, zu(xo)), (xo, yb, zu(xo)), (xr, yb, zr), (xr, ya, zr)], out=(-KD, 0, -1))
    m.poly("timber", [(xo, ya, zu(xo) - 0.02), (xo, yb, zu(xo) - 0.02), (xo, yb, zu(xo) + TD), (xo, ya, zu(xo) + TD)], out=(1, 0, 0))
    for y, k in ((ya, -1), (yb, 1)):
        m.poly("timber", [(xo, y, zu(xo) - 0.02), (xr, y, zr), (xt, y, zu(xt) + TD), (xo, y, zu(xo) + TD)], out=(0, k, 0))
    m.box("iron", (xo - 0.02, ya, zu(xo) - 0.05), (xo + 0.04, yb, zu(xo) + 0.02))
