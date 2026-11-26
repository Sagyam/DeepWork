# S9, market hall: a Victorian covered market of the 1880s, the kind every
# English and Scottish town built on its market place. One tall hall in red
# brick with stone dressings, its gable end to the street. On the front a
# great round arch over the entrance, a cast-iron and glass screen in it
# with gates folded back; the name cut in a stone panel over the arch, and
# in the gable a lunette window with radiating iron bars under a clock,
# stone coping up the rakes to a finial. Down the sides, tall round-arched
# windows between brick pilasters under a corbelled eaves cornice. A slate
# roof carries a glazed lantern along the ridge, louvred below its glass,
# to light and air the stalls. The app tints the brick, the slate and the
# ironwork, and picks the name.
#
# Pieces (base at the origin, stacked by the app):
#   body   7.0 m: the walls to the eaves line, the arches, the entrance
#   roof   gables, coping, slate slopes, the lantern, the clock
#   stall  a trader's stall with a striped awning and crates, for the yard
import math

from lib import Model, Side, Z, fpoly, new_id, pane, sides

ID = "s9"
W, D = 13.6, 13.0
HW, HD = W / 2, D / 2
E = 7.0  # the eaves line
RISE = 4.2  # ridge above the eaves
R = E + RISE
DEPTH = 0.4  # brick walls a brick and a half thick, and the reveals
PLINTH = 0.45
LX = 1.8  # the lantern's half width
OVER = 0.45  # the eaves' overhang
SIDE_BAYS = [-5.0, -2.5, 0.0, 2.5, 5.0]
FRONT_BAYS = [-4.6, 4.6]
LUN = 2.2  # the gable lunette's radius


def build(out, bake=True):
    M = Model(ID)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, E))
    roof(M)
    M.piece("stall", (0, -HD - 8.0, 0))
    stall(M, 0.0, -HD - 8.0)
    M.export(out, bake)


def slope_z(x):
    """The roof's height over x across the hall (the slates' top face)."""
    return E + RISE * (1 - abs(x) / HW)


# ---- arches --------------------------------------------------------------------------------


def arc(mid, spring, r, n=10):
    return [(mid - math.cos(math.pi * k / n) * r, spring + math.sin(math.pi * k / n) * r) for k in range(n + 1)]


def arch_face(m, F, a, b, spring, deep, wall="brick", ring=0.36, key=True):
    """What F.wall left square round a round-arched opening: the spandrels back
    to the wall face, the intrados, a ring of stone voussoirs and a keystone."""
    mid, r = (a + b) / 2, (b - a) / 2
    top = spring + r
    pts = arc(mid, spring, r)
    n = len(pts) - 1
    for k in range(n):
        p0, p1 = pts[k], pts[k + 1]
        corner = (a, top) if p1[0] <= mid + 1e-6 else (b, top)
        m.poly(wall, [F.p(*corner, 0), F.p(*p0, 0), F.p(*p1, 0)], out=F.n)
        t = math.pi * (k + 0.5) / n
        inward = F.t * math.cos(t) - Z * math.sin(t)
        m.poly("stone", [F.p(*p0, 0), F.p(*p1, 0), F.p(*p1, -deep), F.p(*p0, -deep)], out=inward)
    k = 9
    ro = r + ring
    for i in range(k):
        t0, t1 = math.pi * i / k, math.pi * (i + 1) / k
        q = [(mid - math.cos(t0) * r, spring + math.sin(t0) * r), (mid - math.cos(t0) * ro, spring + math.sin(t0) * ro),
             (mid - math.cos(t1) * ro, spring + math.sin(t1) * ro), (mid - math.cos(t1) * r, spring + math.sin(t1) * r)]
        m.poly("stone", [F.p(u, z, 0.05) for u, z in q], out=F.n)
        tm = (t0 + t1) / 2
        m.poly("stone", [F.p(*q[1], 0.0), F.p(*q[2], 0.0), F.p(*q[2], 0.05), F.p(*q[1], 0.05)], out=F.t * (-math.cos(tm)) + Z * math.sin(tm))
        m.poly("stone", [F.p(*q[0], 0.0), F.p(*q[3], 0.0), F.p(*q[3], 0.05), F.p(*q[0], 0.05)], out=F.t * math.cos(tm) - Z * math.sin(tm))
    if key:
        F.box("stone", mid - 0.18, mid + 0.18, top - 0.1, top + ring + 0.12, 0.0, 0.12, skip=("back",))


def arch_glass(m, F, a, b, c, spring, deep, glass="shopglass", bars=2, transom=None):
    """Iron-framed glass in a round-arched opening: a square light under the
    lunette, mullions, radiating bars in the head."""
    mid, r = (a + b) / 2, (b - a) / 2
    top = spring + r
    pts = arc(mid, spring, r)
    wid = new_id()
    gw = -deep + 0.06
    uv = lambda u, z: (wid + (u - a) / (b - a), (z - c) / (top - c))  # noqa: E731
    pane(F, glass, a, b, c, top, a, b, c, spring, gw, wid)
    m.poly(glass, [F.p(u, z, gw) for u, z in pts], out=F.n, uvs=[uv(u, z) for u, z in pts])
    f = 0.06
    F.box("castiron", a, a + f, c, spring, gw - 0.03, gw + 0.06)
    F.box("castiron", b - f, b, c, spring, gw - 0.03, gw + 0.06)
    F.box("castiron", a, b, c, c + f, gw - 0.03, gw + 0.08)
    F.box("castiron", a, b, spring - 0.04, spring + 0.04, gw - 0.03, gw + 0.07)
    for i in range(1, bars):
        u = a + i * (b - a) / bars
        F.box("castiron", u - 0.03, u + 0.03, c, spring, gw - 0.02, gw + 0.05)
    for z in transom or [c + (spring - c) * 0.5]:
        F.box("castiron", a, b, z - 0.025, z + 0.025, gw - 0.02, gw + 0.05)
    for k in range(1, 6):
        t = math.pi * k / 6
        m.strut("castiron", F.p(mid, spring, gw + 0.02), F.p(mid - math.cos(t) * (r - 0.03), spring + math.sin(t) * (r - 0.03), gw + 0.02), 0.04)
    for k in range(len(pts) - 1):
        m.strut("castiron", F.p(*pts[k], gw + 0.02), F.p(*pts[k + 1], gw + 0.02), 0.05)
    return wid


# ---- the walls --------------------------------------------------------------------------------


def body(M):
    m = M.m
    S = sides(m, W, D)
    # A stone plinth round the hall, a weathered top.
    m.sweep("stone", W, D, [(0.08, 0.0), (0.08, PLINTH - 0.06), (0.02, PLINTH), (-0.01, PLINTH)])
    for name in ("right", "left"):
        side(M, S[name])
    front(M, S["front"])
    back(M, S["back"])
    # The sill band and the impost band (at the arches' springing) round the hall.
    m.sweep("stone", W, D, [(-0.01, 1.55), (0.07, 1.55), (0.07, 1.72), (-0.01, 1.72)])
    m.sweep("stone", W, D, [(-0.01, 4.85), (0.06, 4.85), (0.06, 5.0), (-0.01, 5.0)])
    # Stone quoins up the corners, long and short.
    for sx in (-1, 1):
        for sy in (-1, 1):
            z = PLINTH
            k = 0
            while z < E - 0.2:
                h = min(0.45, E - 0.05 - z)
                L = 0.62 if k % 2 == 0 else 0.38
                x0, x1 = sorted((sx * HW, sx * (HW - L)))
                y0, y1 = sorted((sy * HD, sy * (HD - 0.38 if k % 2 == 0 else HD - 0.62)))
                m.box("stone", (x0, sy * (HD + 0.04), z + 0.01), (x1, sy * HD, z + h - 0.01))
                m.box("stone", (sx * (HW + 0.04), y0, z + 0.01), (sx * HW, y1, z + h - 0.01))
                z += h
                k += 1
    # A dark hall inside, so seams show dark, not sky.
    # Its front stands back behind the entrance screen.
    e = DEPTH + 0.02
    m.box("dark", (-HW + e, -HD + DEPTH + 0.45, PLINTH), (HW - e, HD - e, E), skip=("z0",))
    m.poly("dark", [(-HW + e, -HD + e, PLINTH + 0.01), (HW - e, -HD + e, PLINTH + 0.01), (HW - e, HD - e, PLINTH + 0.01), (-HW + e, HD - e, PLINTH + 0.01)], out=Z)


def side(M, F):
    """A long side: five tall arched windows between brick pilasters, a
    corbelled brick cornice under the eaves."""
    m = M.m
    holes = [(u - 0.8, u + 0.8, 1.72, 5.0 + 0.8) for u in SIDE_BAYS]
    F.wall("brick", -HD, HD, PLINTH, E, holes, depth=DEPTH, reveal="stone")
    for u in SIDE_BAYS:
        a, b = u - 0.8, u + 0.8
        arch_face(m, F, a, b, 5.0, DEPTH)
        arch_glass(m, F, a, b, 1.72, 5.0, DEPTH, bars=3)
    for u in [(x + y) / 2 for x, y in zip(SIDE_BAYS, SIDE_BAYS[1:])]:
        F.box("brick", u - 0.22, u + 0.22, PLINTH, E - 0.55, 0.0, 0.14, skip=("back",))
        F.box("stone", u - 0.28, u + 0.28, E - 0.75, E - 0.55, 0.0, 0.2, skip=("back",))
    cornice(F, -HD, HD)


def cornice(F, u0, u1):
    """A corbel table in brick, three oversailing courses, a stone cornice."""
    z0 = E - 0.55
    n = int((u1 - u0) / 0.45)
    for i in range(n):
        u = u0 + 0.22 + i * (u1 - u0 - 0.44) / (n - 1)
        F.box("brick", u - 0.11, u + 0.11, z0, z0 + 0.22, 0.0, 0.12, skip=("back",))
    for k, w in enumerate((0.12, 0.2, 0.28)):
        z = z0 + 0.22 + k * 0.08
        F.box("brick", u0, u1, z, z + 0.08, 0.0, w, skip=("back",))
    F.box("stone", u0 - 0.05, u1 + 0.05, E - 0.09, E + 0.06, 0.0, 0.38, skip=("back",))


def front(M, F):
    """The street front: the entrance arch, a window either side, the name panel."""
    m = M.m
    ea, eb, es = -1.9, 1.9, 3.6  # the entrance arch
    holes = [(u - 0.9, u + 0.9, 1.72, 5.9) for u in FRONT_BAYS] + [(ea, eb, PLINTH, es + 1.9, DEPTH + 0.3)]
    F.wall("brick", -HW, HW, PLINTH, E, holes, depth=DEPTH, reveal="stone")
    for u in FRONT_BAYS:
        arch_face(m, F, u - 0.9, u + 0.9, 5.0, DEPTH)
        arch_glass(m, F, u - 0.9, u + 0.9, 1.72, 5.0, DEPTH, bars=3)
    deep = DEPTH + 0.3
    arch_face(m, F, ea, eb, es, deep, ring=0.45)
    # The entrance screen: a glazed fan over the transom, doors under it.
    wid = arch_glass(m, F, ea, eb, es - 1.1, es, deep, glass="shopglass", bars=4, transom=[])
    D_ = -deep + 0.06
    pane(F, "shopglass", ea, eb, PLINTH, es + 1.9, ea + 0.1, eb - 0.1, PLINTH + 0.15, es - 1.15, D_ - 0.04, wid)
    for u in (ea + 0.06, -0.95, 0.0, 0.95, eb - 0.06):
        F.box("castiron", u - 0.06, u + 0.06, PLINTH, es - 1.1, D_ - 0.05, D_ + 0.05)
    F.box("castiron", ea, eb, PLINTH, PLINTH + 0.15, D_ - 0.05, D_ + 0.06)
    F.box("castiron", ea, eb, PLINTH + 0.95, PLINTH + 1.02, D_ - 0.03, D_ + 0.05)
    F.box("brass", -0.25, -0.05, PLINTH + 1.05, PLINTH + 1.12, D_ + 0.04, D_ + 0.08)
    F.box("brass", 0.05, 0.25, PLINTH + 1.05, PLINTH + 1.12, D_ + 0.04, D_ + 0.08)
    # The gates, folded back against the reveals: iron bars with a spiked head.
    for u0, s in ((ea, 1), (eb, -1)):
        for k in range(7):
            ww = -0.08 - k * 0.07
            F.box("castiron", u0 + s * 0.03 - 0.015, u0 + s * 0.03 + 0.015, PLINTH + 0.05, es - 0.3, ww - 0.012, ww + 0.012)
            F.box("castiron", u0 + s * 0.03 - 0.02, u0 + s * 0.03 + 0.02, es - 0.3, es - 0.15, ww - 0.02, ww + 0.02)
        for z in (PLINTH + 0.2, es - 0.4):
            F.box("castiron", u0 + s * 0.01, u0 + s * 0.05, z, z + 0.05, -0.55, -0.05)
    # The floor of the arch, granite setts a step up.
    m.poly("granite", [F.p(ea, PLINTH, 0.0), F.p(eb, PLINTH, 0.0), F.p(eb, PLINTH, -deep), F.p(ea, PLINTH, -deep)], out=Z)
    F.box("granite", ea - 0.3, eb + 0.3, 0.0, PLINTH - 0.005, 0.0, 0.5, skip=("back",))
    # Dressed stone jambs to the springing, a lamp on a bracket each side.
    for u0, u1 in ((ea - 0.45, ea), (eb, eb + 0.45)):
        F.box("stone", u0, u1, PLINTH, es, 0.0, 0.06, skip=("back",))
    for u in (ea - 0.85, eb + 0.85):
        F.box("castiron", u - 0.03, u + 0.03, 3.2, 3.26, 0.0, 0.5)
        q = F.p(u, 0, 0.5)
        m.cyl("castiron", q.x, q.y, 0.16, 2.6, 2.68, seg=8)
        m.cyl("lamp", q.x, q.y, 0.14, 2.68, 3.15, seg=8, top=False, r1=0.18)
        m.cyl("castiron", q.x, q.y, 0.21, 3.15, 3.3, seg=8, r1=0.04)
    # The name, cut in a stone panel over the arch.
    F.box("stone", -3.1, 3.1, 6.1, 6.75, 0.0, 0.08, skip=("back",))
    F.box("stone", -3.2, 3.2, 6.75, 6.85, 0.0, 0.14, skip=("back",))
    F.quad("stonename", -2.9, 2.9, 6.15, 6.7, 0.084, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    # The string course at the eaves line, the gable's base.
    F.box("stone", -HW - 0.06, HW + 0.06, E - 0.12, E + 0.04, 0.0, 0.2, skip=("back",))


def back(M, F):
    """The yard side: a cart arch with boarded doors, a window either side."""
    m = M.m
    ga, gb, gs = -1.6, 1.6, 3.4
    holes = [(u - 0.9, u + 0.9, 1.72, 5.9) for u in FRONT_BAYS] + [(ga, gb, PLINTH, gs + 1.6)]
    F.wall("brick", -HW, HW, PLINTH, E, holes, depth=DEPTH, reveal="stone")
    for u in FRONT_BAYS:
        arch_face(m, F, u - 0.9, u + 0.9, 5.0, DEPTH)
        arch_glass(m, F, u - 0.9, u + 0.9, 1.72, 5.0, DEPTH, bars=3)
    arch_face(m, F, ga, gb, gs, DEPTH, key=False)
    w = -DEPTH + 0.05
    for l0, l1 in ((ga, -0.01), (0.01, gb)):
        F.quad("door", l0, l1, PLINTH, gs, w)
        for z in (PLINTH + 0.4, gs - 0.5):
            F.box("door", l0 + 0.08, l1 - 0.08, z, z + 0.14, w, w + 0.05)
        m.strut("door", F.p(l0 + 0.1, PLINTH + 0.55, w + 0.03), F.p(l1 - 0.1, gs - 0.55, w + 0.03), 0.04, 0.12)
    pts = arc(0.0, gs, gb)
    fpoly(F, "door", pts, w)
    F.box("stone", -HW - 0.06, HW + 0.06, E - 0.12, E + 0.04, 0.0, 0.2, skip=("back",))
    m.box("lamp", (-0.15, HD, gs + 2.0), (0.15, HD + 0.12, gs + 2.12))


# ---- the roof ----------------------------------------------------------------------------------


def roof(M):
    m = M.m
    S = sides(m, W, D)
    gable(M, S["front"], clock=True)
    gable(M, S["back"], clock=False)
    zl = slope_z(LX)
    y0, y1 = -HD + 0.1, HD - 0.1
    # The slate slopes from the eaves to the ridge, a board under the eaves.
    for sx in (-1, 1):
        xe = sx * (HW + OVER)
        ze = slope_z(HW + OVER)
        pts = [(xe, y0, ze), (0.0, y0, R), (0.0, y1, R), (xe, y1, ze)]
        L = math.hypot(HW + OVER, R - ze)
        uvs = [(y0, 0), (y0, L), (y1, L), (y1, 0)]
        m.poly("slate", pts, out=(sx * RISE / HW, 0, 1), uvs=uvs)
        m.poly("dark", [(xe, y0, ze - 0.02), (0.0, y0, R - 0.02), (0.0, y1, R - 0.02), (xe, y1, ze - 0.02)], out=(-sx * RISE / HW, 0, -1))
        # Fascia, soffit back to the wall, the iron gutter and downpipes.
        x0, x1 = sorted((xe, xe - sx * 0.04))
        m.box("castiron", (x0, y0, ze - 0.25), (x1, y1, ze), skip=())
        xa, xb = sorted((xe, sx * HW))
        m.poly("brick", [(xa, y0, ze - 0.25), (xb, y0, ze - 0.25), (xb, y1, ze - 0.25), (xa, y1, ze - 0.25)], out=-Z)
        gx0, gx1 = sorted((xe, xe + sx * 0.16))
        m.box("castiron", (gx0, y0, ze - 0.22), (gx1, y1, ze - 0.06))
        for yy in (-HD + 0.8, HD - 0.8):
            px0, px1 = sorted((sx * (HW + 0.06), sx * (HW + 0.16)))
            m.box("castiron", (px0, yy - 0.05, PLINTH), (px1, yy + 0.05, ze - 0.2))
    # Ridge tiles beyond the lantern.
    lan = HD - 1.6
    for ya, yb in ((y0, -lan), (lan, y1)):
        m.box("terracotta", (-0.12, ya, R - 0.05), (0.12, yb, R + 0.12))
    lantern(M, zl, lan)


def gable(M, F, clock):
    """A gable end above the eaves: brick round the lunette, stone coping up the
    rakes on kneelers, a finial; on the front the clock over the lunette."""
    m = M.m
    r = LUN
    deep = DEPTH
    pts = arc(0.0, E, r, n=16)  # from the left springing over to the right

    def edge(t):
        """Where the ray from (0, E) at angle t leaves the gable."""
        c, s = -math.cos(t), math.sin(t)
        if abs(c) < 1e-6:
            return (0.0, R)
        # Ray (c, s) * d meets the rake z - E = RISE (1 - |u| / HW).
        d = RISE / (s + RISE * abs(c) / HW)
        return (c * d, E + s * d)

    for k in range(len(pts) - 1):
        t0, t1 = math.pi * k / 16, math.pi * (k + 1) / 16
        q0, q1 = edge(t0), edge(t1)
        pa, pb = pts[k], pts[k + 1]
        # The apex is a ray's end (t = pi / 2), so each piece is a convex quad.
        m.poly("brick", [F.p(*pa, 0), F.p(*q0, 0), F.p(*q1, 0), F.p(*pb, 0)], out=F.n)
        tm = (t0 + t1) / 2
        m.poly("stone", [F.p(*pa, 0), F.p(*pb, 0), F.p(*pb, -deep), F.p(*pa, -deep)], out=F.t * math.cos(tm) - Z * math.sin(tm))
    # The lunette: glass in iron, bars radiating from a hub, voussoirs round it.
    wid = new_id()
    gw = -deep + 0.06
    uv = lambda u, z: (wid + (u + r) / (2 * r), (z - E) / r)  # noqa: E731
    m.poly("shopglass", [F.p(u, z, gw) for u, z in pts], out=F.n, uvs=[uv(u, z) for u, z in pts])
    for k in range(1, 8):
        t = math.pi * k / 8
        m.strut("castiron", F.p(0.0, E, gw + 0.02), F.p(-math.cos(t) * (r - 0.03), E + math.sin(t) * (r - 0.03), gw + 0.02), 0.05)
    hub = arc(0.0, E, 0.45, n=8)
    for k in range(len(hub) - 1):
        m.strut("castiron", F.p(*hub[k], gw + 0.03), F.p(*hub[k + 1], gw + 0.03), 0.05)
    for k in range(len(pts) - 1):
        m.strut("castiron", F.p(*pts[k], gw + 0.02), F.p(*pts[k + 1], gw + 0.02), 0.06)
    F.box("castiron", -r, r, E, E + 0.06, gw - 0.03, gw + 0.06)
    ring = 0.34
    n = 13
    for i in range(n):
        t0, t1 = math.pi * i / n, math.pi * (i + 1) / n
        q = [(-math.cos(t0) * r, E + math.sin(t0) * r), (-math.cos(t0) * (r + ring), E + math.sin(t0) * (r + ring)),
             (-math.cos(t1) * (r + ring), E + math.sin(t1) * (r + ring)), (-math.cos(t1) * r, E + math.sin(t1) * r)]
        m.poly("stone", [F.p(u, z, 0.05) for u, z in q], out=F.n)
        tm = (t0 + t1) / 2
        m.poly("stone", [F.p(*q[1], 0.0), F.p(*q[2], 0.0), F.p(*q[2], 0.05), F.p(*q[1], 0.05)], out=F.t * (-math.cos(tm)) + Z * math.sin(tm))
    # The coping: stone slabs up each rake, kneelers at the feet, a finial at the apex.
    for sx in (-1, 1):
        a = F.p(sx * (HW + 0.12), E + 0.1, -0.15)
        b = F.p(0.0, R + 0.2, -0.15)
        m.strut("stone", a, b, 0.62, 0.3)
        u0, u1 = sorted((sx * (HW + 0.14), sx * (HW - 0.5)))
        F.box("stone", u0, u1, E - 0.1, E + 0.45, -0.45, 0.16, skip=())
    F.box("stone", -0.22, 0.22, R + 0.1, R + 0.6, -0.37, 0.07, skip=())
    q = F.p(0.0, 0.0, -0.15)
    m.cyl("stone", q.x, q.y, 0.16, R + 0.6, R + 0.9, seg=10, r1=0.11)
    m.cyl("stone", q.x, q.y, 0.15, R + 0.9, R + 1.15, seg=10, r1=0.0)
    if clock:
        clock_face(m, F, 0.0, E + 3.15, 0.08, r=0.42)


def clock_face(m, F, u, z, w, r=0.5):
    """A clock dial: a stone surround, a white face, hour marks, hands at ten to two."""
    seg = 24
    fpoly(F, "stone", [(u + math.cos(i / seg * math.tau) * (r + 0.13), z + math.sin(i / seg * math.tau) * (r + 0.13)) for i in range(seg)], w)
    for i in range(seg):
        a0, a1 = i / seg * math.tau, (i + 1) / seg * math.tau
        rr = r + 0.13
        m.poly("stone", [F.p(u + math.cos(a0) * rr, z + math.sin(a0) * rr, 0.0), F.p(u + math.cos(a1) * rr, z + math.sin(a1) * rr, 0.0),
                         F.p(u + math.cos(a1) * rr, z + math.sin(a1) * rr, w), F.p(u + math.cos(a0) * rr, z + math.sin(a0) * rr, w)],
               out=F.t * math.cos((a0 + a1) / 2) + Z * math.sin((a0 + a1) / 2))
    fpoly(F, "clock", [(u + math.cos(i / seg * math.tau) * r, z + math.sin(i / seg * math.tau) * r) for i in range(seg)], w + 0.02)
    for i in range(12):
        a = i / 12 * math.tau
        c, s = math.cos(a), math.sin(a)
        F.box("iron", u + c * (r - 0.08) - 0.02, u + c * (r - 0.08) + 0.02, z + s * (r - 0.08) - 0.02, z + s * (r - 0.08) + 0.02, w + 0.02, w + 0.03)
    for ang, L, t in ((math.radians(90 - 300), r * 0.5, 0.04), (math.radians(90 - 50), r * 0.78, 0.03)):
        m.strut("iron", F.p(u, z, w + 0.035), F.p(u + math.cos(ang) * L, z + math.sin(ang) * L, w + 0.035), t, 0.01)


def lantern(M, zl, lan):
    """The ridge lantern: louvred cheeks, glass above them in iron, a glass roof
    on iron bars, closed at the ends; ventilator finials on the ridge."""
    m = M.m
    hl = R - zl + 0.45  # louvres, their top clear of the ridge
    hg = 0.55  # glass
    zt = zl + hl + hg
    zr = zt + 0.7
    for sx in (-1, 1):
        F = Side(m, (sx * LX, 0, 0), (0, sx, 0), (sx, 0, 0))
        F.quad("blades", -lan, lan, zl, zl + hl, 0.0, uvs=[(0, 0), (2 * lan, 0), (2 * lan, hl), (0, hl)])
        F.quad("skyglass", -lan, lan, zl + hl, zt, 0.0)
        n = int(2 * lan / 0.9)
        for i in range(n + 1):
            u = -lan + i * 2 * lan / n
            F.box("castiron", u - 0.04, u + 0.04, zl, zt, -0.04, 0.05, skip=())
        F.box("castiron", -lan, lan, zl + hl - 0.03, zl + hl + 0.03, -0.04, 0.06, skip=())
        F.box("castiron", -lan - 0.05, lan + 0.05, zt - 0.02, zt + 0.06, -0.06, 0.12, skip=())
        # The glass roof and its bars.
        xa, xb = sx * (LX + 0.1), 0.0
        m.poly("skyglass", [(xa, -lan, zt + 0.02), (xb, -lan, zr), (xb, lan, zr), (xa, lan, zt + 0.02)], out=(sx * 0.8, 0, LX))
        m.poly("dark", [(xa, -lan, zt), (xb, -lan, zr - 0.02), (xb, lan, zr - 0.02), (xa, lan, zt)], out=(-sx * 0.8, 0, -LX))
        for i in range(n * 2 + 1):
            y = -lan + i * lan / n
            m.strut("castiron", (xa, y, zt + 0.06), (0.0, y, zr + 0.04), 0.04, 0.05)
    m.box("castiron", (-0.1, -lan - 0.1, zr - 0.02), (0.1, lan + 0.1, zr + 0.12))
    # The ends: louvred, glass above, a little gable of glass.
    for sy in (-1, 1):
        y = sy * lan
        F = Side(m, (0, y, 0), (-sy, 0, 0), (0, sy, 0))
        fpoly(F, "blades", [(-LX, zl), (0.0, R), (0.0, zl + hl), (-LX, zl + hl)])
        fpoly(F, "blades", [(0.0, R), (LX, zl), (LX, zl + hl), (0.0, zl + hl)])
        fpoly(F, "skyglass", [(-LX, zl + hl), (LX, zl + hl), (LX, zt), (-LX, zt)])
        fpoly(F, "skyglass", [(-LX - 0.1, zt), (LX + 0.1, zt), (0.0, zr)])
        for u in (-LX, -0.6, 0.6, LX):
            F.box("castiron", u - 0.04, u + 0.04, max(zl, slope_z(u)), zt, -0.04, 0.05, skip=())
    # Ventilator finials on the lantern's ridge.
    for y in (-lan + 0.8, lan - 0.8):
        m.cyl("castiron", 0.0, y, 0.07, zr + 0.1, zr + 0.6, seg=8)
        m.cyl("castiron", 0.0, y, 0.22, zr + 0.6, zr + 0.75, seg=10, r1=0.12)
        m.cyl("castiron", 0.0, y, 0.12, zr + 0.75, zr + 1.05, seg=10, r1=0.0)


# ---- a stall for the yard -----------------------------------------------------------------------


def stall(M, x, y):
    """A trader's stall: a trestle counter under a striped canvas on poles, crates
    of produce on it and under it. Faces -y; about 2.4 x 1.2 m."""
    m = M.m
    w, d, h = 2.4, 1.2, 0.85
    x0, x1, y0, y1 = x - w / 2, x + w / 2, y - d / 2, y + d / 2
    m.box("boards", (x0, y0, h - 0.05), (x1, y1, h))
    for xx in (x0 + 0.1, x1 - 0.1):
        for yy in (y0 + 0.1, y1 - 0.1):
            m.box("castiron", (xx - 0.03, yy - 0.03, 0.0), (xx + 0.03, yy + 0.03, h - 0.05))
    # Poles and a canvas ridge awning sloping to the front.
    for xx in (x0 + 0.05, x1 - 0.05):
        m.cyl("castiron", xx, y1 - 0.05, 0.03, 0.0, 2.35, seg=6)
        m.cyl("castiron", xx, y0 - 0.15, 0.03, 0.0, 2.0, seg=6)
    for out in ((0, -0.35, 1), (0, 0.35, -1)):
        m.poly("awning", [(x0 - 0.1, y0 - 0.3, 1.95), (x1 + 0.1, y0 - 0.3, 1.95), (x1 + 0.1, y1, 2.35), (x0 - 0.1, y1, 2.35)], out=out)
    for out in ((0, -1, 0), (0, 1, 0)):
        m.poly("awning", [(x0 - 0.1, y0 - 0.3, 1.95), (x1 + 0.1, y0 - 0.3, 1.95), (x1 + 0.1, y0 - 0.3, 1.72), (x0 - 0.1, y0 - 0.3, 1.72)], out=out)
    # Crates heaped with produce: apples, oranges, greens; empties underneath.
    for i in range(4):
        cx = x0 + 0.33 + i * 0.58
        tilt = 0.08
        m.box("boards", (cx - 0.26, y0 + 0.12, h), (cx + 0.26, y0 + 0.62, h + 0.2), skip=("z1",))
        m.poly("produce%d" % (i % 3), [(cx - 0.24, y0 + 0.14, h + 0.2), (cx + 0.24, y0 + 0.14, h + 0.2), (cx + 0.24, y0 + 0.6, h + 0.2 + tilt), (cx - 0.24, y0 + 0.6, h + 0.2 + tilt)], out=Z)
        if i % 2 == 0:
            m.box("boards", (cx - 0.24, y0 + 0.66, 0.0), (cx + 0.24, y0 + 1.1, 0.32))
    # A chalked price board on a stand.
    m.box("dark", (x1 - 0.1, y0 - 0.55, 0.0), (x1 + 0.4, y0 - 0.5, 0.9))
