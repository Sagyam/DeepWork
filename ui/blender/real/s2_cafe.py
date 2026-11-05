# S2, corner café: a European corner house of the 1890s, the kind found from
# Vienna to Lyon to Trieste. Painted stucco over a ground storey of banded
# rustication; the corner cut off at 45° for the café's door, an oriel on a
# stepped corbel over it rising through the upper storeys to a copper
# helmet. The café has big round-arched windows in timber frames with
# fanlights, keystones and archivolts, its name in gilt letters on the
# frieze above them and "CAFÉ" over the door between two lanterns; the
# flats' own arched door is on the front's left. A piano nobile of French
# windows with balconettes and pedimented heads, a second storey of
# casements with louvred shutters, a frieze and a deep modillion cornice,
# and a slate hip roof cut back over the corner, with stacks on the party
# wall. The app tints the stucco, the café's paint, the shutters and the
# slate per building, picks the name, and sets out the umbrella tables.
#
# Pieces (base at the origin, stacked by the app):
#   ground  4.5 m: the café and the flats' door, the oriel's corbel
#   first   3.3 m: the piano nobile
#   second  3.2 m: the top storey (not every café has it)
#   roof    frieze, cornice, hip roof, stacks; the oriel's top and helmet
#   table   a bistro table with two chairs under a parasol, for the terrace
import math

from mathutils import Vector

from lib import Model, Side, Z, fpoly, french, letters, new_id, pane, railing, sill

ID = "s2"
W, D = 10.0, 11.5
X0, X1, Y0, Y1 = -W / 2, W / 2, -D / 2, D / 2  # front faces -y; the corner is front right
C = 2.6  # the corner cut back this far along both streets
PL = 0.15  # the café floor above the pavement
G = 4.5  # ground storey
F1 = 3.3  # piano nobile
F2 = 3.2  # top storey
RV = 0.32  # window reveals
OP = [(-1.25, 0.0), (-0.8, 0.6), (0.8, 0.6), (1.25, 0.0)]  # the oriel's plan on the corner (u, w)
FOOT = [(X0, Y0), (X1 - C, Y0), (X1, Y0 + C), (X1, Y1), (X0, Y1)]  # counter-clockwise from above
FRIEZE = 0.62  # the roof piece's walls above the top storey
PITCH = math.radians(34)
EAVE = 0.52  # the cornice's projection, where the slates start


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("first", (0, 0, G))
    first(M, G)
    M.piece("second", (0, 0, G + F1))
    second(M, G + F1)
    top = G + F1 + F2
    M.piece("roof", (0, 0, top))
    roof(M, top)
    M.piece("table", (24, 0, 0))
    table(M.m, 24)
    M.export(out, bake)


# ---- frames and helpers ------------------------------------------------------------


def facades(m, z=0.0):
    """The five faces of the block, seen from outside, with their half-lengths:
    front (-y, the corner cut off at its right), corner, right (+y beyond the corner), back, left (the party wall)."""
    s2 = math.sqrt(0.5)
    hf, hr = (W - C) / 2, (D - C) / 2
    return {
        "front": (Side(m, (X0 + hf, Y0, z), (1, 0, 0), (0, -1, 0)), hf),
        "corner": (Side(m, (X1 - C / 2, Y0 + C / 2, z), (s2, s2, 0), (s2, -s2, 0)), C * s2),
        "right": (Side(m, (X1, Y0 + C + hr, z), (0, 1, 0), (1, 0, 0)), hr),
        "back": (Side(m, (0, Y1, z), (-1, 0, 0), (0, 1, 0)), W / 2),
        "left": (Side(m, (X0, 0, z), (0, -1, 0), (-1, 0, 0)), D / 2),
    }


def offset(poly, d):
    """Offsets an open polyline of (u, w) points outward (w up) by d; the ends slide along w = 0."""
    P = [Vector(p) for p in poly]
    segs = []
    for p, q in zip(P, P[1:]):
        t = (q - p).normalized()
        segs.append((p + Vector((-t.y, t.x)) * d, t))
    p0, t0 = segs[0]
    out = [p0 - t0 * (p0.y / t0.y)]
    for (pa, ta), (pb, tb) in zip(segs, segs[1:]):
        den = ta.x * tb.y - ta.y * tb.x
        s = ((pb - pa).x * tb.y - (pb - pa).y * tb.x) / den
        out.append(pa + ta * s)
    p1, t1 = segs[-1]
    out.append(p1 - t1 * (p1.y / t1.y))
    return [(v.x, v.y) for v in out]


def prism(F, role, poly, z0, z1, bottom=False, top=False):
    """An upright prism on the open plan `poly` (u, w) off facade F, closed against the wall."""
    m = F.m
    for (ua, wa), (ub, wb) in zip(poly, poly[1:]):
        a, b = F.p(ua, z0, wa), F.p(ub, z0, wb)
        out = (b - a).cross(Z)
        m.poly(role, [a, b, F.p(ub, z1, wb), F.p(ua, z1, wa)], out=out)
    if bottom:
        m.poly(role, [F.p(u, z0, w) for u, w in poly], out=-Z)
    if top:
        m.poly(role, [F.p(u, z1, w) for u, w in poly], out=Z)


def faces(F, poly):
    """Oriented frames along the faces of an oriel's plan: (Side, half-length) each."""
    out = []
    for (ua, wa), (ub, wb) in zip(poly, poly[1:]):
        a, b = F.p(ua, 0, wa), F.p(ub, 0, wb)
        t = (b - a).normalized()
        out.append((Side(F.m, (a + b) / 2, t, t.cross(Z)), (b - a).length / 2))
    return out


def arc(mid, s, r, n=12):
    """Points along a semicircle over (mid, s), left to right."""
    return [(mid - r * math.cos(math.pi * i / n), s + r * math.sin(math.pi * i / n)) for i in range(n + 1)]


def head(F, role, a, b, e, D=RV, key=True, ring=True):
    """Fills the top corners of the opening (a..b, ..e) round a semicircular head, with its soffit;
    an archivolt standing proud round it, imposts and a keystone."""
    m = F.m
    mid, r = (a + b) / 2, (b - a) / 2
    s = e - r
    pts = arc(mid, s, r)
    for (u0, z0), (u1, z1) in zip(pts, pts[1:]):
        fpoly(F, role, [(u0, z0), (u1, z1), (u1, e), (u0, e)])
        um, zm = (u0 + u1) / 2, (z0 + z1) / 2
        m.poly(role, [F.p(u0, z0, 0), F.p(u1, z1, 0), F.p(u1, z1, -D), F.p(u0, z0, -D)], out=F.t * (mid - um) + Z * (s - zm))
    if not ring:
        return
    # The archivolt: a flat band 0.14 wide, 0.03 proud, broken by the key.
    n = 16
    gap = (n // 2 - 1, n // 2) if key else ()
    for i in range(n):
        if i in gap:
            continue
        t0, t1 = math.pi * i / n, math.pi * (i + 1) / n
        p = lambda t, rr: (mid - rr * math.cos(t), s + rr * math.sin(t))  # noqa: E731
        q = [p(t0, r), p(t1, r), p(t1, r + 0.14), p(t0, r + 0.14)]
        fpoly(F, "trim", q, 0.03)
        edges = [(q[2], q[3])]  # the extrados
        if i == 0 or (key and i == n // 2 + 1):
            edges.append((q[3], q[0]))
        if i == n - 1 or (key and i == n // 2 - 2):
            edges.append((q[1], q[2]))
        for (ua, za), (ub, zb) in edges:
            out = (F.p(ub, zb) - F.p(ua, za)).cross(F.n)
            m.poly("trim", [F.p(ua, za, 0), F.p(ub, zb, 0), F.p(ub, zb, 0.03), F.p(ua, za, 0.03)], out=out)
    for u0, u1 in ((a - 0.16, a + 0.02), (b - 0.02, b + 0.16)):
        F.box("trim", u0, u1, s - 0.1, s, 0, 0.045)
    if key:
        # A keystone: a wedge widening upward, standing out of the band.
        k0, k1 = r - 0.03, r + 0.34
        fpoly(F, "stone", [(mid - 0.1, s + k0), (mid + 0.1, s + k0), (mid + 0.15, s + k1), (mid - 0.15, s + k1)], 0.06)
        for (ua, za), (ub, zb), out in (((mid - 0.1, s + k0), (mid + 0.1, s + k0), -Z), ((mid + 0.1, s + k0), (mid + 0.15, s + k1), F.t), ((mid + 0.15, s + k1), (mid - 0.15, s + k1), Z), ((mid - 0.15, s + k1), (mid - 0.1, s + k0), -F.t)):
            m.poly("stone", [F.p(ua, za, 0), F.p(ub, zb, 0), F.p(ub, zb, 0.06), F.p(ua, za, 0.06)], out=out)


def fan(F, glass, a, b, c, e, mid, s, r, w, wid, n=12):
    """A semicircular glass pane of radius r over (mid, s) at depth w, UV'd over the opening like pane()."""
    uv = lambda u, z: (wid + (u - a) / (b - a), (z - c) / (e - c))  # noqa: E731
    pts = arc(mid, s, r, n)
    F.m.poly(glass, [F.p(u, z, w) for u, z in pts], out=F.n, uvs=[uv(u, z) for u, z in pts])


def arcframe(F, role, mid, s, r, w0, w1, fw=0.07, n=12):
    """A frame member round a semicircle: segments fw wide inside radius r, from depth w0 to w1."""
    m = F.m
    pts = arc(mid, s, r, n)
    ins = arc(mid, s, r - fw, n)
    for k in range(n):
        (ua, za), (ub, zb) = pts[k], pts[k + 1]
        (ia, ja), (ib, jb) = ins[k], ins[k + 1]
        for w in (w0, w1):
            m.poly(role, [F.p(ua, za, w), F.p(ub, zb, w), F.p(ib, jb, w), F.p(ia, ja, w)], out=F.n if w == w1 else -F.n)
        um, zm = (ua + ub) / 2, (za + zb) / 2
        m.poly(role, [F.p(ia, ja, w0), F.p(ib, jb, w0), F.p(ib, jb, w1), F.p(ia, ja, w1)], out=F.t * (mid - um) + Z * (s - zm))


def arched(F, a, b, c, e, glass="cafeglass", D=RV, door=False):
    """A timber window or pair of doors in a round-arched opening (a..b, c..e):
    a panelled stallriser (doors: panelled lower leaves), a mullion, a transom
    at the springing and a fanlight with radiating bars, all one room behind."""
    fr = "shopframe"
    wid = new_id()
    mid, r = (a + b) / 2, (b - a) / 2
    s = e - r
    fw = 0.08
    w0, w1 = -D + 0.06, -D + 0.16
    wg = -D + 0.1
    F.box(fr, a, a + fw, c, s, w0, w1)
    F.box(fr, b - fw, b, c, s, w0, w1)
    arcframe(F, fr, mid, s, r, w0, w1, fw)
    F.box(fr, a + fw, b - fw, s - 0.05, s + 0.04, w0, w1 + 0.02)
    # The fanlight: glass, a hub and five radiating bars.
    fan(F, glass, a, b, c, e, mid, s + 0.04, r - fw, wg, wid)
    hub = arc(mid, s + 0.04, 0.16, 6)
    for (u0, z0), (u1, z1) in zip(hub, hub[1:]):
        F.m.strut(fr, F.p(u0, z0, wg + 0.02), F.p(u1, z1, wg + 0.02), 0.04)
    for k in range(1, 6):
        t = math.pi * k / 6
        F.m.strut(fr, F.p(mid - 0.16 * math.cos(t), s + 0.04 + 0.16 * math.sin(t), wg + 0.02), F.p(mid - (r - fw) * math.cos(t), s + 0.04 + (r - fw) * math.sin(t), wg + 0.02), 0.035)
    ia, ib = a + fw, b - fw
    if door:
        # Two leaves: a panel below, a big light above, a brass push bar.
        F.box(fr, a + fw, b - fw, c, c + 0.08, w0, w1)
        for la, lb in ((ia, mid), (mid, ib)):
            F.box(fr, la, la + 0.08, c, s - 0.05, wg - 0.03, wg + 0.05)
            F.box(fr, lb - 0.08, lb, c, s - 0.05, wg - 0.03, wg + 0.05)
            F.box(fr, la + 0.08, lb - 0.08, c + 0.08, c + 0.8, wg - 0.02, wg + 0.04)
            F.box(fr, la + 0.15, lb - 0.15, c + 0.2, c + 0.68, wg + 0.04, wg + 0.06)
            F.box(fr, la + 0.08, lb - 0.08, s - 0.15, s - 0.05, wg - 0.03, wg + 0.05)
            pane(F, glass, a, b, c, e, la + 0.08, lb - 0.08, c + 0.8, s - 0.15, wg, wid)
            F.box("brass", la + 0.12, lb - 0.12, c + 1.0, c + 1.04, wg + 0.05, wg + 0.09)
        return
    st = c + 0.42
    F.box(fr, ia, ib, c, st, w0, w1)
    for pa, pb in ((ia + 0.08, mid - 0.06), (mid + 0.06, ib - 0.08)):
        F.box(fr, pa, pb, c + 0.08, st - 0.08, w1, w1 + 0.02)
    F.box(fr, ia, ib, st - 0.03, st + 0.05, w0, w1 + 0.04)
    F.box(fr, mid - 0.035, mid + 0.035, st, s - 0.05, w0 + 0.02, w1 - 0.02)
    pane(F, glass, a, b, c, e, ia, ib, st + 0.05, s - 0.05, wg, wid)


def lantern(F, u, z):
    """A wall lantern on a scrolled iron arm: four glass sides round a lamp, a cap and a finial."""
    m = F.m
    F.box("iron", u - 0.06, u + 0.06, z - 0.2, z + 0.12, 0, 0.03)
    m.strut("iron", F.p(u, z, 0.03), F.p(u, z, 0.3), 0.03)
    m.strut("iron", F.p(u, z - 0.15, 0.03), F.p(u, z - 0.02, 0.22), 0.02)
    c = F.p(u, 0, 0.36)
    zb, zt = z - 0.42, z - 0.04
    m.box("iron", (c.x - 0.11, c.y - 0.11, zb - 0.03), (c.x + 0.11, c.y + 0.11, zb))
    m.box("lamp", (c.x - 0.09, c.y - 0.09, zb), (c.x + 0.09, c.y + 0.09, zt))
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        m.box("iron", (c.x + dx * 0.1 - 0.012, c.y + dy * 0.1 - 0.012, zb), (c.x + dx * 0.1 + 0.012, c.y + dy * 0.1 + 0.012, zt))
    m.cyl("iron", c.x, c.y, 0.15, zt, zt + 0.1, seg=4, r1=0.03)
    m.cyl("iron", c.x, c.y, 0.02, zt + 0.1, z + 0.04, seg=6)
    m.strut("iron", F.p(u, z + 0.04, 0.3), F.p(u, z + 0.04, 0.38), 0.02)


def plinth(F, h, gaps=()):
    """A granite base course 0.4 m tall along a facade, broken at doors."""
    u = -h
    for a, b in sorted(gaps) + [(h, h)]:
        if a > u + 1e-6:
            F.box("granite", u, a, 0, 0.4, 0, 0.04)
            F.box("granite", u, a, 0.4, 0.44, 0, 0.02)
        u = b


# ---- ground storey -------------------------------------------------------------------

# Openings on each face, u along it: (a, b, sill, crown, arched, kind).
CAFE_WIN = (0.44, 3.62)


def ground(M):
    m = M.m
    fs = facades(m)
    F, hf = fs["front"]
    K, hk = fs["corner"]
    R, hr = fs["right"]
    B, hb = fs["back"]
    L, hl = fs["left"]
    c, e = CAFE_WIN
    flats = (-3.25, -2.15)
    front_win = [(-1.25, 0.55), (1.25, 3.05)]
    right_win = [(-3.75, -1.95), (-1.15, 0.65)]
    service = (2.05, 3.05)
    door = (-0.75, 0.75)
    RUS = G - 0.6  # top of the rustication

    holes = [(*flats, PL, 3.3, RV)] + [(a, b, c, e) for a, b in front_win]
    F.wall("rustic", -hf, hf, 0, RUS, holes, depth=RV, reveal="rustic")
    for a, b in front_win:
        arched(F, a, b, c, e)
        head(F, "rustic", a, b, e)
        F.box("stone", a - 0.06, b + 0.06, c - 0.08, c, -RV + 0.06, 0.07)
    # The flats' door: panelled, half glazed, under its own fanlight, a step and a number.
    a, b = flats
    arched(F, a, b, PL, 3.3, glass="doorglass", door=True)
    head(F, "rustic", a, b, 3.3)
    F.box("granite", a - 0.1, b + 0.1, 0, PL, 0, 0.3, skip=("back",))
    F.box("brass", b + 0.18, b + 0.36, 2.3, 2.46, 0, 0.015)
    F.box("brass", b + 0.18, b + 0.3, 1.25, 1.55, 0, 0.02)
    plinth(F, hf, [(a - 0.1, b + 0.1)])

    K.wall("rustic", -hk, hk, 0, RUS, [(*door, PL, 3.6, RV)], depth=RV, reveal="rustic")
    arched(K, *door, PL, 3.6, door=True)
    head(K, "rustic", *door, 3.6)
    K.box("stone", door[0] - 0.15, door[1] + 0.15, 0, PL, 0, 0.4, skip=("back",))
    plinth(K, hk, [(door[0] - 0.15, door[1] + 0.15)])
    for u in (-1.32, 1.32):
        lantern(K, u, 2.95)

    holes = [(a, b, c, e) for a, b in right_win] + [(*service, PL, 2.55, 0.2)]
    R.wall("rustic", -hr, hr, 0, RUS, holes, depth=RV, reveal="rustic")
    for a, b in right_win:
        arched(R, a, b, c, e)
        head(R, "rustic", a, b, e)
        R.box("stone", a - 0.06, b + 0.06, c - 0.08, c, -RV + 0.06, 0.07)
    a, b = service
    R.quad("door", a + 0.05, b - 0.05, PL, 2.5, -0.17)
    for u0, u1 in ((a, a + 0.05), (b - 0.05, b)):
        R.box("door", u0, u1, PL, 2.55, -0.2, -0.12)
    R.box("door", a + 0.05, b - 0.05, 2.5, 2.55, -0.2, -0.12)
    for z in (0.5, 1.4):
        R.box("door", a + 0.12, b - 0.12, z, z + 0.7, -0.17, -0.15)
    R.box("iron", b - 0.2, b - 0.14, 1.15, 1.2, -0.17, -0.12)
    R.box("granite", a - 0.1, b + 0.1, 0, PL, 0, 0.3, skip=("back",))
    R.box("stone", a - 0.12, b + 0.12, 2.55, 2.75, 0, 0.04)
    plinth(R, hr, [(a - 0.1, b + 0.1)])

    # The back: the kitchen door and two barred windows on the yard; the party wall blank.
    bd = (2.4, 3.4)
    bw = [(-3.5, -2.5), (-0.6, 0.4)]
    B.wall("rustic", -hb, hb, 0, RUS, [(*bd, PL, 2.5, 0.2)] + [(a, b, 1.5, 3.0) for a, b in bw], depth=RV, reveal="rustic")
    a, b = bd
    B.quad("door", a + 0.05, b - 0.05, PL, 2.45, -0.17)
    B.box("door", a + 0.05, b - 0.05, 1.35, 2.3, -0.17, -0.15)
    B.box("granite", a - 0.1, b + 0.1, 0, PL, 0, 0.3, skip=("back",))
    for a, b in bw:
        casement(B, a, b, 1.5, 3.0, D=RV)
        sill(B, a, b, 1.5, D=RV)
        for i in range(6):
            u = a + 0.1 + i * (b - a - 0.2) / 5
            B.box("iron", u - 0.012, u + 0.012, 1.52, 2.98, 0.02, 0.05)
    B.box("ac", 0.9, 1.5, 2.2, 2.8, 0, 0.25)
    B.box("dark", 0.95, 1.45, 2.3, 2.7, 0.25, 0.255, skip=("back",))
    plinth(B, hb, [(bd[0] - 0.1, bd[1] + 0.1)])
    L.wall("rustic", -hl, hl, 0, RUS, [])
    plinth(L, hl)

    # Above the rustication: a band, the frieze with the name, and the first floor's cornice.
    for name, (S, h) in fs.items():
        S.wall("render", -h, h, RUS, G, [])
    m.psweep("trim", FOOT, [(-0.01, RUS), (0.05, RUS), (0.05, RUS + 0.1), (-0.01, RUS + 0.1)])
    m.psweep("trim", FOOT, [(-0.01, G - 0.16), (0.05, G - 0.16), (0.09, G - 0.1), (0.14, G - 0.06), (0.14, G), (-0.01, G)])
    # The café's name in gilt letters on the frieze (the app picks it), CAFÉ over the corner door.
    z0, z1 = RUS + 0.13, G - 0.19
    F.quad("cafename", -1.7, 3.45, z0, z1, 0.004, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    R.quad("cafename", -4.0, 1.15, z0, z1, 0.004, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    letters(m, "brass", K, 0, (z0 + z1) / 2, 0.0, "CAFÉ", 0.27, depth=0.03, spacing=1.15)
    # The oriel's corbel: four courses stepping out to carry it, and a pendant boss.
    for k, (z_0, z_1, s) in enumerate(((G - 0.18, G, 1.0), (G - 0.42, G - 0.18, 0.82), (G - 0.66, G - 0.42, 0.62), (G - 0.86, G - 0.66, 0.4))):
        poly = [(u * s, w * s) for u, w in offset(OP, 0.05)]
        prism(K, "trim" if k == 0 else "stone", poly, z_0, z_1, bottom=True)
    K.box("stone", -0.12, 0.12, G - 1.08, G - 0.86, 0.02, 0.2, skip=())
    # A ceiling over the storey, seen only when the floors above are gone.
    m.poly("dark", [(x, y, G - 0.02) for x, y in FOOT], out=Z)
    downpipe(m, 0.05, G)


def downpipe(m, z0, z1):
    """The downpipe on the back wall, from the cornice's gutter."""
    x = X0 + 0.5
    m.box("iron", (x - 0.05, Y1 + 0.03, z0), (x + 0.05, Y1 + 0.13, z1))
    for z in (z0 + 1.1, z0 + 2.2):
        if z < z1 - 0.1:
            m.box("iron", (x - 0.07, Y1, z), (x + 0.07, Y1 + 0.15, z + 0.05))


# ---- upper storeys --------------------------------------------------------------------


def casement(F, a, b, c, e, D=0.25, rows=3):
    """A pair of casements with glazing bars, and a transom light over them."""
    fr, wid = "frame", new_id()
    fw = 0.07
    w0, w1 = -D + 0.02, -D + 0.12
    F.box(fr, a, a + fw, c, e, w0, w1)
    F.box(fr, b - fw, b, c, e, w0, w1)
    F.box(fr, a + fw, b - fw, e - fw, e, w0, w1)
    F.box(fr, a + fw, b - fw, c, c + 0.06, w0, w1 + 0.02)
    t = e - 0.42
    F.box(fr, a + fw, b - fw, t - 0.06, t, w0, w1)
    wg = -D + 0.07
    pane(F, "glass", a, b, c, e, a + fw, b - fw, t, e - fw, wg, wid)
    mid = (a + b) / 2
    for la, lb in ((a + fw, mid), (mid, b - fw)):
        F.box(fr, la, la + 0.05, c + 0.06, t - 0.06, wg - 0.02, wg + 0.04)
        F.box(fr, lb - 0.05, lb, c + 0.06, t - 0.06, wg - 0.02, wg + 0.04)
        F.box(fr, la + 0.05, lb - 0.05, c + 0.06, c + 0.14, wg - 0.02, wg + 0.04)
        F.box(fr, la + 0.05, lb - 0.05, t - 0.11, t - 0.06, wg - 0.02, wg + 0.04)
        pane(F, "glass", a, b, c, e, la + 0.05, lb - 0.05, c + 0.14, t - 0.11, wg - 0.01, wid)
        for j in range(1, rows):
            z = c + 0.14 + j * (t - 0.11 - c - 0.14) / rows
            F.box(fr, la + 0.05, lb - 0.05, z - 0.012, z + 0.012, wg - 0.01, wg + 0.03)


def architrave(F, a, b, c, e, w=0.13):
    """A moulded stucco surround: a band round the opening standing 0.035 proud, with ears at the head."""
    F.box("trim", a - w, a, c, e, 0, 0.035)
    F.box("trim", b, b + w, c, e, 0, 0.035)
    F.box("trim", a - w - 0.05, b + w + 0.05, e, e + w, 0, 0.035)
    F.box("trim", a - w - 0.05, a - w, e - 0.18, e, 0, 0.035)
    F.box("trim", b + w, b + w + 0.05, e - 0.18, e, 0, 0.035)


def shutters(F, a, b, c, e, h):
    """A pair of louvred shutters folded back against the wall either side of
    the opening; one that would run past the facade's end (h) is left off."""
    sw = (b - a) / 2
    for u0, u1 in ((a - 0.14 - sw, a - 0.14), (b + 0.14, b + 0.14 + sw)):
        if u0 < -h + 0.05 or u1 > h - 0.05:
            continue
        F.box("shutter", u0, u1, c + 0.02, e - 0.02, 0.035, 0.07)
        F.box("iron", u0 + 0.04 if u0 < a else u1 - 0.08, u0 + 0.08 if u0 < a else u1 - 0.04, c + 0.9, c + 0.95, 0.07, 0.1)


# Window axes on each face, u: front over the ground's openings, right likewise, back three.
AXES = {"front": [-2.7, -0.35, 2.15], "right": [-2.85, -0.25, 2.55], "back": [-3.0, -0.1, 2.9]}


def storey(M, z, H, piano):
    m = M.m
    fs = facades(m)
    for name, (S, h) in fs.items():
        if name == "corner":
            # The wall either side of the oriel; behind it, its room.
            for u0, u1 in ((-h, OP[0][0]), (OP[-1][0], h)):
                S.wall("render", u0, u1, 0 + z, z + H, [])
            continue
        if name == "left":
            S.wall("render", -h, h, z, z + H, [])
            continue
        ww = 0.95 if name == "back" else 1.1
        c = z + (0.12 if piano and name != "back" else 0.85)
        e = z + (2.6 if piano else 2.45)
        holes = [(u - ww / 2, u + ww / 2, c, e) for u in AXES[name]]
        S.wall("render", -h, h, z, z + H, holes, depth=0.25, reveal="render")
        for a, b, c_, e_ in holes:
            architrave(S, a, b, c_, e_)
            if piano and name != "back":
                french(S, a, b, c_, e_, D=0.25)
                pediment(S, a - 0.05, b + 0.05, e_ + 0.13)
                # A shallow balconette on a stone slab.
                S.box("stone", a - 0.32, b + 0.32, c_ - 0.12, c_, 0, 0.4, skip=())
                railing(S, M.cut, a - 0.26, b + 0.26, c_, 0.02, 0.36, h=0.92)
            else:
                casement(S, a, b, c_, e_, D=0.25)
                sill(S, a - 0.05, b + 0.05, c_, D=0.25, role="trim")
                if not piano and name != "back":
                    shutters(S, a, b, c_, e_, h)
                S.box("trim", a - 0.2, b + 0.2, e_ + 0.13, e_ + 0.22, 0, 0.09)
    if not piano:
        m.psweep("trim", FOOT, [(-0.01, z + 0.7), (0.04, z + 0.7), (0.04, z + 0.78), (-0.01, z + 0.78)])
    oriel(M, fs["corner"][0], z, H, piano)
    downpipe(m, z, z + H)
    m.poly("dark", [(x, y, z + H - 0.02) for x, y in FOOT], out=Z)


def oriel(M, K, z, H, piano):
    """A storey of the oriel: three faces of stucco, a window in each over a panelled apron, a cornice band."""
    m = K.m
    c = z + 0.85
    e = z + (2.55 if piano else 2.4)
    for (S, h) in faces(K, OP):
        half = 0.48 if h > 0.6 else 0.17
        S.wall("render", -h, h, z, z + H, [(-half, half, c, e)], depth=0.15, reveal="render")
        if half > 0.3:
            casement(S, -half, half, c, e, D=0.15, rows=3)
        else:
            casement_one(S, -half, half, c, e)
        sill(S, -half - 0.02, half + 0.02, c, D=0.15, role="trim")
        S.box("trim", -half + 0.04, half - 0.04, z + 0.25, c - 0.12, 0, 0.025)
        S.box("trim", -half - 0.06, half + 0.06, e, e + 0.1, 0, 0.03)
    # Bands at the floor and at the top, stepping out.
    prism(K, "trim", offset(OP, 0.04), z, z + 0.12, bottom=piano)
    prism(K, "trim", offset(OP, 0.06), z + H - 0.2, z + H - 0.08, bottom=True)
    prism(K, "trim", offset(OP, 0.03), z + H - 0.08, z + H)
    m.poly("dark", [K.p(u, z + H - 0.02, w) for u, w in OP], out=Z)


def pediment(F, a, b, e):
    """A stucco window head: a frieze, a cornice on two consoles, and a low triangular pediment."""
    m = F.m
    F.box("trim", a - 0.16, b + 0.16, e, e + 0.2, 0, 0.04)
    F.box("trim", a - 0.26, b + 0.26, e + 0.2, e + 0.28, 0, 0.16)
    for u in (a - 0.2, b + 0.08):
        F.box("trim", u, u + 0.12, e - 0.3, e + 0.2, 0, 0.12)
    # The pediment: a raking cornice over a sunk tympanum.
    u0, u1, z0, rise = a - 0.26, b + 0.26, e + 0.28, 0.22
    mid = (u0 + u1) / 2
    fpoly(F, "trim", [(u0 + 0.06, z0), (u1 - 0.06, z0), (mid, z0 + rise - 0.06)], 0.04)
    for s in (-1, 1):
        ue = u0 if s < 0 else u1
        a0, a1 = F.p(ue, z0, 0), F.p(mid, z0 + rise, 0)
        out = Z * abs(ue - mid) + F.t * (rise if s > 0 else -rise)
        m.poly("trim", [a0, a1, F.p(mid, z0 + rise, 0.16), F.p(ue, z0, 0.16)], out=out)
        m.poly("trim", [F.p(ue, z0, 0.16), F.p(mid, z0 + rise, 0.16), F.p(mid, z0 + rise - 0.07, 0.16), F.p(ue + s * -0.08, z0, 0.16)], out=F.n)
        m.poly("trim", [F.p(ue + s * -0.08, z0, 0.04), F.p(mid, z0 + rise - 0.07, 0.04), F.p(mid, z0 + rise - 0.07, 0.16), F.p(ue + s * -0.08, z0, 0.16)], out=-out)


def casement_one(F, a, b, c, e):
    """A single narrow casement for the oriel's sides."""
    fr, wid = "frame", new_id()
    D, fw = 0.15, 0.06
    w0, w1 = -D + 0.02, -D + 0.1
    F.box(fr, a, a + fw, c, e, w0, w1)
    F.box(fr, b - fw, b, c, e, w0, w1)
    F.box(fr, a + fw, b - fw, e - fw, e, w0, w1)
    F.box(fr, a + fw, b - fw, c, c + 0.06, w0, w1)
    pane(F, "glass", a, b, c, e, a + fw, b - fw, c + 0.06, e - fw, -D + 0.06, wid)
    for j in (1, 2, 3):
        zz = c + j * (e - c) / 4
        F.box(fr, a + fw, b - fw, zz - 0.012, zz + 0.012, -D + 0.06, -D + 0.09)


def first(M, z):
    storey(M, z, F1, True)


def second(M, z):
    storey(M, z, F2, False)


# ---- roof ---------------------------------------------------------------------------


def roof(M, TOP):
    m = M.m
    fs = facades(m)
    b = TOP + FRIEZE
    for name, (S, h) in fs.items():
        if name == "corner":
            for u0, u1 in ((-h, OP[0][0]), (OP[-1][0], h)):
                S.wall("render", u0, u1, TOP, b, [])
        else:
            S.wall("render", -h, h, TOP, b, [])
        # Little attic vents over the window axes.
        for u in AXES.get(name, []):
            S.box("trim", u - 0.32, u + 0.32, TOP + 0.14, TOP + 0.42, 0, 0.03)
            S.box("dark", u - 0.24, u + 0.24, TOP + 0.2, TOP + 0.36, 0.03, 0.035, skip=("back",))
            for k in range(1, 4):
                uu = u - 0.24 + k * 0.12
                S.box("trim", uu - 0.012, uu + 0.012, TOP + 0.2, TOP + 0.36, 0.03, 0.05)
    # The cornice: a bed mould, modillions under a soffit, the corona and a cymatium.
    m.psweep("trim", FOOT, [(-0.01, TOP + 0.04), (0.05, TOP + 0.04), (0.05, TOP + 0.12), (-0.01, TOP + 0.12)])
    m.psweep("trim", FOOT, [(-0.01, b), (0.06, b), (0.06, b + 0.06), (0.12, b + 0.1), (0.12, b + 0.14), (0.44, b + 0.17), (0.46, b + 0.2), (0.46, b + 0.32), (0.5, b + 0.36), (EAVE, b + 0.42), (0.0, b + 0.42)])
    for name, (S, h) in fs.items():
        n = int((2 * h - 0.3) / 0.5)
        for i in range(n + 1):
            u = -h + 0.15 + i * (2 * h - 0.3) / max(n, 1)
            if name == "corner" and abs(u) < 1.45:
                continue
            S.box("trim", u - 0.05, u + 0.05, b + 0.07, b + 0.17, 0.12, 0.42, skip=("back",))
            S.box("trim", u - 0.05, u + 0.05, b + 0.02, b + 0.07, 0.06, 0.2, skip=("back",))
    ze = b + 0.42
    hip(m, ze)
    stacks(m, ze)
    oriel_top(M, fs["corner"][0], TOP, b, ze)
    # The gutter's outlet and the downpipe's head at the back.
    x = X0 + 0.5
    m.box("iron", (x - 0.14, Y1 + 0.03, b - 0.35), (x + 0.14, Y1 + 0.3, b - 0.05))
    m.box("iron", (x - 0.05, Y1 + 0.1, b - 0.05), (x + 0.05, Y1 + 0.2, ze))
    m.box("iron", (x - 0.05, Y1 + 0.03, TOP), (x + 0.05, Y1 + 0.13, b - 0.35))


def plane(m, role, pts, a, b):
    """A roof plane through pts; UV0 u along its eave a-b, v up the slope (metres)."""
    pts = [Vector(p) for p in pts]
    a, b = Vector(a), Vector(b)
    n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if n.z < 0:
        n = -n
    tt = (b - a).normalized()
    uvs = []
    for X in pts:
        d = X - a
        u = d.dot(tt)
        uvs.append((u, (d - tt * u).length))
    m.poly(role, pts, out=n, uvs=uvs)


def hip(m, ze):
    """The hip roof over the cut-off corner: the straight skeleton of the eave's outline.

    The corner's two hips meet on the diagonal the square corner's hip would
    have taken, at P, and run on to the ridge from there."""
    K = math.tan(PITCH)
    E = EAVE
    ex0, ex1, ey0, ey1 = X0 - E, X1 + E, Y0 - E, Y1 + E
    cc = C + E * (2 - math.sqrt(2))  # the cut's legs along the eave
    half = (ex1 - ex0) / 2
    cx = (ex0 + ex1) / 2
    k = cc / (2 - math.sqrt(2))  # P's distance from both street eaves
    h = lambda d: ze + d * K  # noqa: E731
    FL, A, Bc = Vector((ex0, ey0, ze)), Vector((ex1 - cc, ey0, ze)), Vector((ex1, ey0 + cc, ze))
    BR, BL = Vector((ex1, ey1, ze)), Vector((ex0, ey1, ze))
    R0, R1 = Vector((cx, ey0 + half, h(half))), Vector((cx, ey1 - half, h(half)))
    P = Vector((ex1 - k, ey0 + k, h(k)))
    planes = [
        ([FL, A, P, R0], FL, A),
        ([A, Bc, P], A, Bc),
        ([Bc, BR, R1, R0, P], Bc, BR),
        ([BR, BL, R1], BR, BL),
        ([BL, FL, R0, R1], BL, FL),
    ]
    for pts, a, b in planes:
        plane(m, "slate", pts, a, b)
    # Zinc rolls on the ridge and hips.
    up = Z * 0.03
    for p, q in ((R0, R1), (FL, R0), (A, P), (Bc, P), (P, R0), (BR, R1), (BL, R1)):
        m.tube("lead", [p + up, q + up], 0.045, Z if abs((q - p).normalized().z) < 0.9 else Vector((1, 0, 0)), closed=False, seg=6)
    # A roof hatch on the back slope, and a vent pipe.
    hx, hy = -1.2, ey1 - 2.0
    d = ey1 - hy
    zt = h(d + 0.45) + 0.18
    m.box("lead", (hx - 0.45, hy - 0.45, h(d - 0.45) - 0.05), (hx + 0.45, hy + 0.45, zt))
    m.box("iron", (hx - 0.5, hy - 0.5, zt), (hx + 0.5, hy + 0.5, zt + 0.05))
    m.cyl("ac", 2.0, ey1 - 1.6, 0.06, h(1.6) - 0.2, h(1.6) + 0.7, seg=8)
    m.cyl("ac", 2.0, ey1 - 1.6, 0.09, h(1.6) + 0.7, h(1.6) + 0.78, seg=8)


def stacks(m, ze):
    """Two stuccoed chimney stacks on the party wall, with a cornice cap and pots."""
    K = math.tan(PITCH)
    for y in (-2.4, 2.9):
        x = X0 + 0.45
        z0 = ze + (x - (X0 - EAVE)) * K - 0.4
        top = ze + 3.2
        m.box("render", (x - 0.4, y - 0.6, z0), (x + 0.4, y + 0.6, top), skip=("z0",))
        m.sweep("trim", 0.8, 1.2, [(-0.01, top - 0.3), (0.05, top - 0.3), (0.05, top - 0.22), (-0.01, top - 0.22)], cx=x, cy=y)
        m.sweep("trim", 0.8, 1.2, [(-0.01, top), (0.08, top), (0.08, top + 0.12), (0.0, top + 0.12)], cx=x, cy=y)
        m.poly("trim", [(x - 0.4, y - 0.6, top + 0.12), (x + 0.4, y - 0.6, top + 0.12), (x + 0.4, y + 0.6, top + 0.12), (x - 0.4, y + 0.6, top + 0.12)], out=Z)
        for dy in (-0.3, 0.0, 0.3):
            m.cyl("terracotta", x, y + dy, 0.1, top + 0.12, top + 0.5, seg=10, r1=0.085)
            m.cyl("terracotta", x, y + dy, 0.105, top + 0.5, top + 0.55, seg=10)


def oriel_top(M, K, TOP, b, ze):
    """The oriel through the frieze and cornice, its own cornice, and a copper helmet with a finial."""
    m = K.m
    for (S, h) in faces(K, OP):
        S.wall("render", -h, h, TOP, ze, [])
    prism(K, "trim", offset(OP, 0.03), TOP + 0.04, TOP + 0.12)
    o = offset(OP, 0.12)
    prism(K, "trim", offset(OP, 0.06), ze - 0.18, ze - 0.06, bottom=True)
    prism(K, "trim", o, ze - 0.06, ze + 0.06, bottom=True)
    # The helmet: a bell from the cornice to a waist, a spire above, closed into the roof behind.
    z0 = ze + 0.06
    base = [*o, (o[-1][0], -0.9), (o[0][0], -0.9)]  # back into the roof, out of sight
    cen = Vector((0.0, 0.05))
    ring = lambda s, dz: [K.p(cen.x + (u - cen.x) * s, z0 + dz, cen.y + (w - cen.y) * s) for u, w in base]  # noqa: E731
    r0, r1, r2 = ring(1.0, 0.0), ring(0.78, 0.55), ring(0.38, 0.95)
    apex = K.p(cen.x, z0 + 2.3, cen.y)
    n = len(base)
    for ra, rb in ((r0, r1), (r1, r2)):
        for i in range(n):
            j = (i + 1) % n
            q = [ra[i], ra[j], rb[j], rb[i]]
            nrm = (q[1] - q[0]).cross(q[3] - q[0])
            mid = sum(q, Vector()) / 4 - K.p(cen.x, 0, cen.y)
            mid.z = 0
            m.poly("copper", q, out=nrm if nrm.dot(mid) > 0 else -nrm)
    for i in range(n):
        j = (i + 1) % n
        tri = [r2[i], r2[j], apex]
        nrm = (tri[1] - tri[0]).cross(tri[2] - tri[0])
        mid = (tri[0] + tri[1]) / 2 - K.p(cen.x, 0, cen.y)
        mid.z = 0
        m.poly("copper", tri, out=nrm if nrm.dot(mid) > 0 else -nrm)
    # Copper rolls on the helmet's arrises over the oriel, and the finial.
    for i in (1, 2):
        m.tube("copper", [r0[i] + Z * 0.02, r1[i] + Z * 0.02, r2[i] + Z * 0.02, apex], 0.025, (r1[i] - r0[i]).cross(Z), closed=False, seg=5)
    f = apex
    m.cyl("copper", f.x, f.y, 0.035, f.z - 0.05, f.z + 0.5, seg=8)
    m.cyl("brass", f.x, f.y, 0.09, f.z + 0.3, f.z + 0.42, seg=10, r1=0.09)
    m.cyl("brass", f.x, f.y, 0.09, f.z + 0.42, f.z + 0.5, seg=10, r1=0.0)
    m.cyl("brass", f.x, f.y, 0.012, f.z + 0.5, f.z + 0.85, seg=6, r1=0.0)


# ---- the terrace's table ---------------------------------------------------------------


def table(m, ox):
    """A round bistro table on a cast-iron foot, two bentwood chairs, and a parasol over them."""
    # Table: a marble top, an iron pedestal on a cross foot.
    m.cyl("trim", ox, 0, 0.33, 0.72, 0.75, seg=20)
    m.cyl("iron", ox, 0, 0.3, 0.7, 0.72, seg=16, top=False)
    m.cyl("iron", ox, 0, 0.03, 0.06, 0.7, seg=8)
    for a in (0, math.pi / 2):
        dx, dy = math.cos(a) * 0.26, math.sin(a) * 0.26
        m.strut("iron", (ox - dx, -dy, 0.03), (ox + dx, dy, 0.03), 0.04)
    for a in (math.radians(20), math.radians(200)):
        chair(m, ox + math.cos(a) * 0.62, math.sin(a) * 0.62, a + math.pi)
    # The parasol: a pole through the table, a canvas of eight panels, a valance, a cap.
    m.cyl("wood", ox, 0, 0.022, 0.0, 2.45, seg=8)
    n, R, zr, za = 8, 1.35, 2.05, 2.42
    rim = [(ox + math.cos((i + 0.5) / n * math.tau) * R, math.sin((i + 0.5) / n * math.tau) * R, zr) for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        a, b = Vector(rim[i]), Vector(rim[j])
        top = Vector((ox, 0, za))
        nrm = (b - a).cross(top - a)
        nrm = nrm if nrm.z > 0 else -nrm
        m.poly("parasol", [a, b, top], out=nrm)
        lo = -Z * 0.012
        m.poly("parasol", [a + lo, b + lo, top + lo], out=-nrm)
        out = Vector(((a.x + b.x) / 2 - ox, (a.y + b.y) / 2, 0))
        val = [a, b, b - Z * 0.18, a - Z * 0.18]
        m.poly("parasol", val, out=out)
        inn = -out.normalized() * 0.01
        m.poly("parasol", [v + inn for v in val], out=-out)
        # Ribs under the canvas.
        m.strut("wood", (ox, 0, za - 0.06), Vector(rim[i]) - Z * 0.02, 0.015)
    m.cyl("wood", ox, 0, 0.05, za - 0.02, za + 0.06, seg=8, r1=0.02)
    m.cyl("wood", ox, 0, 0.1, 1.1, 1.16, seg=8)


def chair(m, x, y, face):
    """A bentwood café chair facing `face` (radians): a round cane seat, four legs, a hooped back."""
    m.cyl("wood", x, y, 0.21, 0.44, 0.47, seg=14)
    m.cyl("cane", x, y, 0.19, 0.47, 0.475, seg=14, top=True)
    for k in range(4):
        a = face + math.pi / 4 + k * math.pi / 2
        m.strut("wood", (x + math.cos(a) * 0.17, y + math.sin(a) * 0.17, 0.44), (x + math.cos(a) * 0.22, y + math.sin(a) * 0.22, 0.0), 0.025)
    m.tube("wood", [(x + math.cos(face + math.pi + t) * 0.18, y + math.sin(face + math.pi + t) * 0.18, 0.47) for t in (-1.0, -0.5, 0, 0.5, 1.0)], 0.012, Z, closed=False, seg=5)
    back = []
    for i in range(9):
        t = -1.0 + i * 0.25
        r = 0.2
        back.append((x + math.cos(face + math.pi + t) * r, y + math.sin(face + math.pi + t) * r, 0.47 + 0.42 * math.cos(t * 0.75) ** 0.5))
    pts = [(x + math.cos(face + math.pi - 1.0) * 0.2, y + math.sin(face + math.pi - 1.0) * 0.2, 0.47)] + back + [(x + math.cos(face + math.pi + 1.0) * 0.2, y + math.sin(face + math.pi + 1.0) * 0.2, 0.47)]
    m.tube("wood", pts, 0.016, (math.cos(face), math.sin(face), 0), closed=False, seg=5)
