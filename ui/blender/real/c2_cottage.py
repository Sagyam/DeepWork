# C2, brick cottage: a late-Victorian single-storey villa, red brick on a
# stone-capped plinth under a tall slate hip roof, the kind found from the
# English shires to the older suburbs of American towns. A canted bay
# window on the left with its own little slate roof, the front door with a
# fanlight under a slate canopy on timber brackets, two-over-two sashes with
# stone sills and keystone lintels, stone quoins at the corners, a dentil
# course under the eaves, black cast-iron ogee gutters, and a chimney stack
# at each end of the ridge. A lean-to coal shed on the right, the back door
# and kitchen window behind, a water butt. The app tints brick, slate and
# door per house; the garden (lawn, hedge, path) is drawn round it.
#
# Pieces (base at the origin):
#   body   everything up to the wall plate: walls, bay and its roof, porch canopy, shed
#   roof   the hip roof, gutters, chimney stacks
#   gate   brick gate piers with stone caps and a low iron gate, for the gap in the hedge
import math

from mathutils import Vector

from lib import Model, Side, Z, lintel, new_id, pane, sash, sides, sill

ID = "c2"
W, D = 10.4, 8.2  # main block
CX, CY = -0.65, 0.125  # its centre: the shed on the right, the bay and steps in front keep the footprint centred
X0, X1 = CX - W / 2, CX + W / 2
Y0, Y1 = CY - D / 2, CY + D / 2  # front and back walls (front faces -y)
BASE = 0.48  # floor level: top of the plinth
PLATE = 4.0  # top of the walls
PITCH = math.radians(40)
K = math.tan(PITCH)
EAVE = 0.35
T = 0.18  # roof thickness, measured vertically
RIDGE = PLATE + D / 2 * K  # underside at the ridge
DEPTH = 0.2  # window reveals in the brick
SILL, HEAD = 1.15, 2.9  # window openings
BAY = (-4.0, -1.0, 0.75)  # canted bay on the front: u from, u to, projection
BAYTOP = 3.14
SHED = (X1, X1 + 1.5, CY + 0.2, Y1 - 0.35)  # lean-to coal shed: x0, x1, y0, y1


def build(out, bake=True):
    M = Model(ID)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, PLATE))
    roof(M)
    M.piece("gate", (20, 0, 0))
    gate(M.m, 20)
    M.export(out, bake)


# ---- helpers ------------------------------------------------------------------------


def plane(m, role, pts, a, b, up=True, uv=True):
    """A roof plane through pts; UV0 u runs along its eave edge a-b, v up the slope from it (metres)."""
    pts = [Vector(p) for p in pts]
    a, b = Vector(a), Vector(b)
    n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if (n.z > 0) != up:
        n = -n
    uvs = None
    if uv:
        tt = (b - a).normalized()
        uvs = []
        for X in pts:
            d = X - a
            u = d.dot(tt)
            uvs.append((u, (d - tt * u).length))
    m.poly(role, pts, out=n, uvs=uvs)


def strip(m, role, a, b, z0, z1, out):
    """A vertical band under the line a-b (x, y) from z0 to z1: fascias and flashings."""
    m.poly(role, [(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], out=out)


def quoins(walls):
    """Stone quoins up every corner of the main block: long and short blocks alternating, staggered round the corner."""
    for k, (name, F) in enumerate(walls.items()):
        h = W / 2 if name in ("front", "back") else D / 2
        z, i = BASE, 0
        while z + 0.3 < PLATE - 0.4:
            for end in (-1, 1):
                L = 0.46 if (i + k + (end > 0)) % 2 else 0.26
                # The right-hand end of each face wraps the corner; the next face's left end butts against it.
                u0, u1 = (h - L, h + 0.025) if end > 0 else (-h, -h + L)
                F.box("stone", u0, u1, z + 0.006, z + 0.294, 0, 0.025)
            z += 0.3
            i += 1


def door(F, a, b, c, t, e, glazed=False):
    """A four-panel door from c to t in the opening (a..b, c..e) with a fanlight above."""
    d = -DEPTH
    wid = new_id()
    F.box("trim", a, a + 0.07, c, e, d, d + 0.1)
    F.box("trim", b - 0.07, b, c, e, d, d + 0.1)
    F.box("trim", a + 0.07, b - 0.07, t, t + 0.07, d, d + 0.12)
    F.box("trim", a + 0.07, b - 0.07, e - 0.07, e, d, d + 0.1)
    # The fanlight, three lights.
    pane(F, "glass", a, b, c, e, a + 0.07, b - 0.07, t + 0.07, e - 0.07, d + 0.04, wid)
    for k in (1, 2):
        u = a + 0.07 + k * (b - a - 0.14) / 3
        F.box("trim", u - 0.015, u + 0.015, t + 0.07, e - 0.07, d + 0.03, d + 0.06)
    da, db = a + 0.07, b - 0.07
    F.quad("door", da, db, c, t, d + 0.03)
    mid = (da + db) / 2
    rows = [(c + 0.15, c + 0.85), (c + 1.0, t - 0.12)]
    if glazed:
        g0, g1 = rows[1]
        F.box("door", da + 0.1, db - 0.1, g0 - 0.02, g1 + 0.02, d + 0.03, d + 0.05, skip=("back", "front"))
        pane(F, "glass", a, b, c, e, da + 0.1, db - 0.1, g0, g1, d + 0.04, new_id())
        F.box("door", mid - 0.015, mid + 0.015, g0, g1, d + 0.04, d + 0.055)
        rows = rows[:1]
    for z0, z1 in rows:
        for u0, u1 in ((da + 0.09, mid - 0.05), (mid + 0.05, db - 0.09)):
            F.box("door", u0, u1, z0, z1, d + 0.03, d + 0.05)
            F.box("door", u0 + 0.04, u1 - 0.04, z0 + 0.04, z1 - 0.04, d + 0.05, d + 0.06)
    # Knob, letter plate, knocker.
    F.box("brass", db - 0.13, db - 0.07, c + 1.0, c + 1.06, d + 0.03, d + 0.1)
    if not glazed:
        F.box("brass", mid - 0.14, mid + 0.14, c + 0.9, c + 0.96, d + 0.05, d + 0.07)
        F.box("brass", mid - 0.03, mid + 0.03, c + 1.45, c + 1.6, d + 0.06, d + 0.09)


def window(F, a, b, lights=(2, 1)):
    sash(F, a, b, SILL, HEAD, D=DEPTH, lights=lights)
    sill(F, a, b, SILL, D=DEPTH)
    lintel(F, a, b, HEAD)


def canopy(F, u0, u1, zw, depth, drop):
    """A lean-to slate canopy over a door, wall line at zw, on two timber brackets."""
    m, p = F.m, F.p
    zf = zw - drop
    t = 0.08
    a, b = p(u0, zf, depth), p(u1, zf, depth)
    plane(m, "slate", [a + Z * t, b + Z * t, p(u1, zw + t, 0), p(u0, zw + t, 0)], a, b)
    plane(m, "trim", [a, b, p(u1, zw, 0), p(u0, zw, 0)], a, b, up=False, uv=False)
    F.box("trim", u0, u1, zf - 0.05, zf + t, depth - 0.025, depth)
    for u, s in ((u0, -F.t), (u1, F.t)):
        m.poly("trim", [p(u, zf - 0.05, depth), p(u, zw - 0.05, 0), p(u, zw + t, 0), p(u, zf + t, depth)], out=s)
    F.box("lead", u0 - 0.02, u1 + 0.02, zw + t - 0.01, zw + t + 0.05, 0, 0.012)
    for u in (u0 + 0.1, u1 - 0.1):
        # A wall post, an arm under the canopy and the curved strut between, as straight timbers.
        F.box("trim", u - 0.04, u + 0.04, zw - 1.0, zw - 0.02, 0, 0.08)
        m.strut("trim", p(u, zw - 0.9, 0.06), p(u, zf - 0.04, depth - 0.18), 0.07)
        m.strut("trim", p(u, zw - 0.06, 0.04), p(u, zf - 0.05, depth - 0.04), 0.06, 0.08)


def steps(F, u, w, n, top):
    """n stone steps up to `top` in front of a door at u, w wide."""
    r = top / n
    for i in range(n):
        F.box("stone", u - w / 2 - 0.05 * (n - i), u + w / 2 + 0.05 * (n - i), i * r, (i + 1) * r, 0, 0.3 * (n - i), skip=("back", "bottom"))


# ---- body ---------------------------------------------------------------------------


def body(M):
    m = M.m
    walls = sides(m, W, D, cx=CX, cy=CY)
    # Plinth: projecting brick with a chamfered stone cap; a dentil course under the eaves.
    m.sweep("brick", W, D, [(0.05, 0.0), (0.05, 0.38)], cx=CX, cy=CY)
    m.sweep("stone", W, D, [(0.05, 0.38), (0.07, 0.38), (0.07, 0.42), (0.0, BASE)], cx=CX, cy=CY)
    m.sweep("brick", W, D, [(-0.01, PLATE - 0.42), (0.06, PLATE - 0.42), (0.06, PLATE - 0.34), (-0.01, PLATE - 0.34)], cx=CX, cy=CY)
    m.sweep("brick", W, D, [(-0.01, PLATE - 0.26), (0.1, PLATE - 0.26), (0.1, PLATE - 0.17), (0.05, PLATE - 0.17), (0.05, PLATE - 0.06)], cx=CX, cy=CY)
    for name, F in walls.items():
        h = W / 2 if name in ("front", "back") else D / 2
        n = int(2 * h / 0.23)
        for i in range(n):
            u = -h + (i + 0.5) * 2 * h / n
            F.box("brick", u - 0.055, u + 0.055, PLATE - 0.34, PLATE - 0.26, 0.06, 0.1, skip=("back",))

    holes = {"front": [], "back": [], "right": [], "left": []}
    wins = {"front": [(2.8, 3.8)], "back": [(-4.0, -3.1), (1.7, 2.7)], "right": [(-2.6, -1.6)], "left": [(-2.6, -1.6), (1.4, 2.4)]}
    doors = {"front": (0.42, 1.38), "back": (-2.1, -1.2)}
    for name, F in walls.items():
        h = W / 2 if name in ("front", "back") else D / 2
        hs = [(a, b, SILL, HEAD) for a, b in wins[name]]
        if name in doors:
            a, b = doors[name]
            hs.append((a, b, BASE, HEAD))
        F.wall("brick", -h, h, 0, PLATE, hs, depth=DEPTH, reveal="brick")
        for a, b in wins[name]:
            window(F, a, b, lights=(2, 1) if name != "back" or a > 0 else (1, 1))
    quoins(walls)

    # Front door: fanlight, keystone lintel, steps, the canopy, a house number.
    F = walls["front"]
    a, b = doors["front"]
    door(F, a, b, BASE, BASE + 2.04, HEAD)
    lintel(F, a, b, HEAD)
    steps(F, (a + b) / 2, b - a + 0.4, 3, BASE)
    canopy(F, a - 0.45, b + 0.45, 3.45, 0.78, 0.32)
    F.box("brass", b + 0.22, b + 0.4, 2.0, 2.18, 0, 0.015)
    # Back door: half glazed, a smaller canopy and two steps.
    B = walls["back"]
    a, b = doors["back"]
    door(B, a, b, BASE, BASE + 2.04, HEAD, glazed=True)
    lintel(B, a, b, HEAD, key_=False)
    steps(B, (a + b) / 2, b - a + 0.3, 2, BASE)
    canopy(B, a - 0.3, b + 0.3, 3.4, 0.6, 0.24)
    # A water butt under the back downpipe, and an outside light by the back door.
    m.cyl("wood", X0 + 0.55, Y1 + 0.38, 0.3, 0.0, 0.92, seg=16)
    m.cyl("dark", X0 + 0.55, Y1 + 0.38, 0.31, 0.92, 0.96, seg=16)
    for z in (0.15, 0.78):
        m.cyl("iron", X0 + 0.55, Y1 + 0.38, 0.305, z, z + 0.04, seg=16, top=False)
    B.box("iron", b + 0.45, b + 0.55, 2.3, 2.38, 0, 0.12)
    B.box("lamp", b + 0.42, b + 0.58, 2.38, 2.6, 0.03, 0.19, skip=())

    bay(m, F)
    shed(m)
    # A ceiling over the top of the walls, seen only when the roof is gone.
    m.poly("dark", [(X0, Y0, PLATE - 0.02), (X1, Y0, PLATE - 0.02), (X1, Y1, PLATE - 0.02), (X0, Y1, PLATE - 0.02)], out=Z)
    # Downpipes from the roof's gutters: two on the sides near the front, two on the back wall.
    ze = PLATE - EAVE * K
    for x, s in ((X0, -1), (X1, 1)):
        y = Y0 + 0.3
        m.strut("iron", (x + s * (EAVE + 0.07), y, ze - 0.14), (x + s * 0.07, y, ze - 0.5), 0.07)
        m.box("iron", (x + s * 0.035, y - 0.035, 0.2), (x + s * 0.105, y + 0.035, ze - 0.47))
        m.box("iron", (x + s * 0.035, y - 0.04, 0.05), (x + s * 0.2, y + 0.04, 0.2))
        for z in (1.0, 2.0, 3.0):
            m.box("iron", (x, y - 0.05, z), (x + s * 0.12, y + 0.05, z + 0.05))
    for x in (X0 + 0.55, X1 - 0.3):
        m.strut("iron", (x, Y1 + EAVE + 0.07, ze - 0.14), (x, Y1 + 0.07, ze - 0.5), 0.07)
        m.box("iron", (x - 0.035, Y1 + 0.035, 0.96 if x < CX else 0.2), (x + 0.035, Y1 + 0.105, ze - 0.47))
        for z in (1.6, 2.6):
            m.box("iron", (x - 0.05, Y1, z), (x + 0.05, Y1 + 0.12, z + 0.05))


def offset(poly, d):
    """Offsets an open polyline of (u, w) points outward (to its left, w up) by d; the ends slide along w = 0."""
    P = [Vector((u, w)) for u, w in poly]
    segs = []
    for p, q in zip(P, P[1:]):
        t = (q - p).normalized()
        segs.append((p + Vector((-t.y, t.x)) * d, t))
    out = []
    first_p, first_t = segs[0]
    out.append(first_p - first_t * (first_p.y / first_t.y))
    for (p0, t0), (p1, t1) in zip(segs, segs[1:]):
        # Intersection of the two offset lines.
        den = t0.x * t1.y - t0.y * t1.x
        s = ((p1 - p0).x * t1.y - (p1 - p0).y * t1.x) / den
        out.append(p0 + t0 * s)
    last_p, last_t = segs[-1]
    out.append(last_p - last_t * (last_p.y / last_t.y))
    return out


def bay(m, F):
    """The canted bay: three sashes over brick aprons, stone sill and head bands, a slate roof up to the wall."""
    u0, u1, pr = BAY
    poly = [(u0, 0.0), (u0 + pr, pr), (u1 - pr, pr), (u1, 0.0)]
    world = lambda u, w, z=0.0: F.p(u, z, w)  # noqa: E731
    for (ua, wa), (ub, wb) in zip(poly, poly[1:]):
        a, b = world(ua, wa), world(ub, wb)
        t = (b - a).normalized()
        S = Side(m, (a + b) / 2, t, t.cross(Z))
        L = (b - a).length
        half = 0.55 if L > 1.2 else 0.3
        S.wall("brick", -L / 2, L / 2, 0, BAYTOP - 0.32, [(-half, half, SILL, HEAD)], depth=DEPTH, reveal="brick")
        sash(S, -half, half, SILL, HEAD, D=DEPTH, lights=(2, 1) if L > 1.2 else (1, 1))
        e = 0.03
        S.box("brick", -L / 2 - e, L / 2 + e, 0, 0.38, 0, 0.05)
        S.box("stone", -L / 2 - e, L / 2 + e, 0.38, 0.45, 0, 0.07)
        S.box("stone", -L / 2 - e, L / 2 + e, SILL - 0.08, SILL, -DEPTH + 0.04, 0.07)
        S.box("stone", -L / 2 - e, L / 2 + e, HEAD, BAYTOP - 0.07, 0, 0.04)
        S.box("stone", -L / 2 - e - 0.03, L / 2 + e + 0.03, BAYTOP - 0.07, BAYTOP, 0, 0.1)
        # Brick aprons under the sashes, panelled in a sunk stone frame.
        S.box("stone", -half, half, 0.6, SILL - 0.08, 0, 0.015)
        S.box("brick", -half + 0.07, half - 0.07, 0.67, SILL - 0.15, 0, 0.02)
    # The roof: an eave line 0.12 beyond the faces, planes rising to a flashing on the main wall.
    ze, zt, t = BAYTOP + 0.02, 3.55, 0.07
    E = offset(poly, 0.12)
    e3 = [world(p.x, p.y, ze) for p in E]
    top = [world(E[1].x, 0.0, zt), world(E[2].x, 0.0, zt)]
    faces = [([e3[0], e3[1], top[0]], e3[0], e3[1]), ([e3[1], e3[2], top[1], top[0]], e3[1], e3[2]), ([e3[2], e3[3], top[1]], e3[2], e3[3])]
    for pts, a, b in faces:
        plane(m, "slate", [p + Z * t for p in pts], a, b)
        plane(m, "trim", pts, a, b, up=False, uv=False)
    for a, b in zip(e3, e3[1:]):
        out = (b - a).cross(Z)
        strip(m, "trim", a, b, ze - 0.05, ze + t, out)
    # Lead rolls on the hips, and a flashing where the roof meets the wall.
    for k in (1, 2):
        m.tube("lead", [e3[k] + Z * (t + 0.01), top[k - 1] + Z * (t + 0.01)], 0.028, Z, closed=False)
    F.box("lead", E[0].x, E[3].x, zt - 0.05, zt + t + 0.06, 0, 0.012)
    # A little iron gutter round the front, with a downpipe at the right-hand corner.
    g = offset(poly, 0.2)
    g3 = [world(p.x, p.y, ze - 0.06) for p in g[1:3]]
    m.strut("iron", g3[0], g3[1], 0.09, 0.08)
    p = world(u1 - pr * 0.5 + 0.12, pr * 0.5 + 0.02)
    m.box("iron", (p.x - 0.035, p.y - 0.035, 0.2), (p.x + 0.035, p.y + 0.035, ze - 0.12))


def shed(m):
    """The lean-to coal shed on the right: brick, a ledged plank door, a slate roof down to a gutter."""
    x0, x1, y0, y1 = SHED
    hi, lo = 3.02, 2.36
    cx = (x0 + x1) / 2
    F = Side(m, (cx, y0, 0), (1, 0, 0), (0, -1, 0))
    hw = (x1 - x0) / 2
    F.wall("brick", -hw, hw, 0, lo, [(-0.55, 0.25, 0.08, 1.98)], depth=0.1, reveal="brick")
    m.poly("brick", [(x0, y0, lo), (x1, y0, lo), (x0, y0, hi)], out=(0, -1, 0))
    F.box("trim", -0.55, -0.49, 0.08, 1.98, -0.1, 0.0)
    F.box("trim", 0.19, 0.25, 0.08, 1.98, -0.1, 0.0)
    F.box("trim", -0.55, 0.25, 1.92, 1.98, -0.1, 0.0)
    F.quad("door", -0.49, 0.19, 0.08, 1.92, -0.07)
    for k in range(1, 6):
        u = -0.49 + k * 0.68 / 6
        F.box("dark", u - 0.006, u + 0.006, 0.1, 1.9, -0.071, -0.068)
    for z in (0.35, 1.0, 1.65):
        F.box("door", -0.45, 0.15, z, z + 0.12, -0.07, -0.04)
    F.box("iron", 0.05, 0.11, 1.0, 1.12, -0.04, -0.01)
    F.box("stone", -0.62, 0.32, 1.98, 2.08, 0, 0.04)
    R = Side(m, (x1, (y0 + y1) / 2, 0), (0, 1, 0), (1, 0, 0))
    hd = (y1 - y0) / 2
    R.wall("brick", -hd, hd, 0, lo, [])
    B = Side(m, (cx, y1, 0), (-1, 0, 0), (0, 1, 0))
    B.wall("brick", -hw, hw, 0, lo, [])
    m.poly("brick", [(x1, y1, lo), (x0, y1, lo), (x0, y1, hi)], out=(0, 1, 0))
    for S, h in ((F, hw), (R, hd), (B, hw)):
        S.box("brick", -h - 0.03, h + 0.03, 0, 0.3, 0, 0.04)
    # Roof, fascia and barges, and a gutter with its downpipe at the front.
    o, t = 0.18, 0.08
    k = (hi - lo) / (x1 - x0)
    xe, ze = x1 + o, lo - o * k
    ya, yb = y0 - o, y1 + o
    a, b = (xe, yb, ze), (xe, ya, ze)
    plane(m, "slate", [(xe, yb, ze + t), (xe, ya, ze + t), (x0, ya, hi + t), (x0, yb, hi + t)], a, b)
    plane(m, "trim", [(xe, yb, ze), (xe, ya, ze), (x0, ya, hi), (x0, yb, hi)], a, b, up=False, uv=False)
    strip(m, "trim", (xe, ya), (xe, yb), ze - 0.06, ze + t, (1, 0, 0))
    for y, s in ((ya, -1), (yb, 1)):
        m.poly("trim", [(xe, y, ze - 0.06), (x0, y, hi - 0.06), (x0, y, hi + t), (xe, y, ze + t)], out=(0, s, 0))
    m.box("lead", (x0, ya, hi + t - 0.01), (x0 + 0.012, yb, hi + t + 0.16))
    m.box("iron", (xe, ya + 0.02, ze - 0.16), (xe + 0.13, yb - 0.02, ze - 0.04))
    m.box("iron", (xe + 0.03, ya + 0.1, 0.15), (xe + 0.1, ya + 0.17, ze - 0.16))


# ---- roof ---------------------------------------------------------------------------


def roof(M):
    m = M.m
    ex0, ex1, ey0, ey1 = X0 - EAVE, X1 + EAVE, Y0 - EAVE, Y1 + EAVE
    ze = PLATE - EAVE * K
    r = W / 2 - D / 2  # half the ridge's length
    R0, R1 = Vector((CX - r, CY, RIDGE)), Vector((CX + r, CY, RIDGE))
    fl, fr, br, bl = Vector((ex0, ey0, ze)), Vector((ex1, ey0, ze)), Vector((ex1, ey1, ze)), Vector((ex0, ey1, ze))
    faces = [([fl, fr, R1, R0], fl, fr), ([fr, br, R1], fr, br), ([br, bl, R0, R1], br, bl), ([bl, fl, R0], bl, fl)]
    up = Z * T
    for pts, a, b in faces:
        plane(m, "slate", [p + up for p in pts], a + up, b + up)
        plane(m, "trim", pts, a, b, up=False, uv=False)
    m.sweep("trim", ex1 - ex0, ey1 - ey0, [(0.0, ze - 0.05), (0.0, ze + T)], cx=CX, cy=CY)
    # Ogee gutters round all four eaves, closed on top.
    gz = ze - 0.02
    m.sweep("iron", ex1 - ex0, ey1 - ey0, [(0.0, gz), (0.0, gz - 0.13), (0.08, gz - 0.13), (0.12, gz - 0.1), (0.11, gz - 0.06), (0.14, gz - 0.03), (0.14, gz), (0.0, gz)], cx=CX, cy=CY)
    # Clay rolls on the ridge and hips, with a little crest of terracotta at each hip foot.
    lift = Z * (T + 0.03)
    m.tube("ridge", [R0 + lift, R1 + lift], 0.075, Vector((0, 1, 0)), closed=False, seg=8)
    for e, R_ in ((fl, R0), (fr, R1), (br, R1), (bl, R0)):
        m.tube("ridge", [e + lift + (R_ - e).normalized() * 0.05, R_ + lift], 0.07, Z, closed=False, seg=8)
    for e in (fl, fr, br, bl):
        c = e + up + Vector((0.06 if e.x < CX else -0.06, 0.06 if e.y < CY else -0.06, 0.02))
        m.cyl("ridge", c.x, c.y, 0.08, c.z, c.z + 0.12, seg=8, r1=0.0)
    # Chimney stacks at the ridge's ends: oversailing courses, a cement flaunching, two pots each.
    top = RIDGE + T + 1.05
    for cx in (CX - r, CX + r):
        xa, xb, ya, yb = cx - 0.42, cx + 0.42, CY - 0.33, CY + 0.33
        m.box("brick", (xa, ya, RIDGE - 1.2), (xb, yb, top), skip=("z0",))
        m.sweep("brick", xb - xa, yb - ya, [(-0.01, top - 0.42), (0.06, top - 0.42), (0.06, top - 0.34), (-0.01, top - 0.34)], cx=cx, cy=CY)
        m.sweep("brick", xb - xa, yb - ya, [(-0.01, top - 0.22), (0.06, top - 0.22), (0.06, top - 0.14), (0.1, top - 0.14), (0.1, top - 0.05), (0.0, top - 0.05)], cx=cx, cy=CY)
        m.sweep("stone", xb - xa, yb - ya, [(0.0, top - 0.05), (0.0, top), (-0.06, top + 0.07)], cx=cx, cy=CY)
        m.poly("stone", [(xa + 0.06, ya + 0.06, top + 0.07), (xb - 0.06, ya + 0.06, top + 0.07), (xb - 0.06, yb - 0.06, top + 0.07), (xa + 0.06, yb - 0.06, top + 0.07)], out=Z)
        for dx in (-0.2, 0.2):
            m.cyl("terracotta", cx + dx, CY, 0.12, top + 0.04, top + 0.5, seg=12, r1=0.1)
            m.cyl("terracotta", cx + dx, CY, 0.125, top + 0.5, top + 0.56, seg=12)
        # Lead apron where the stack leaves the roof, front and back.
        zr = RIDGE + T - 0.33 * K
        m.box("lead", (xa - 0.05, ya - 0.012, zr - 0.04), (xb + 0.05, ya, zr + 0.16))
        m.box("lead", (xa - 0.05, yb, zr - 0.04), (xb + 0.05, yb + 0.012, zr + 0.16))
    aerial(m, CX + r + 0.42, CY, top)
    rooflight(m, CX - 1.7, CY + 1.5)


def onslope(m, role, x0, x1, s0, s1, h0, h1, y_ridge, skip=()):
    """A box lying on the back slope: x across, s down the slope from y_ridge, h out of the roof's surface."""
    c, sn = math.cos(PITCH), math.sin(PITCH)
    d, n = Vector((0, c, -sn)), Vector((0, sn, c))
    base = Vector((0, y_ridge, RIDGE + T))
    P = lambda x, s, h: base + Vector((x, 0, 0)) + d * s + n * h  # noqa: E731
    faces = {
        "top": ([P(x0, s0, h1), P(x1, s0, h1), P(x1, s1, h1), P(x0, s1, h1)], n),
        "up": ([P(x0, s0, h0), P(x1, s0, h0), P(x1, s0, h1), P(x0, s0, h1)], -d),
        "down": ([P(x0, s1, h0), P(x1, s1, h0), P(x1, s1, h1), P(x0, s1, h1)], d),
        "left": ([P(x0, s0, h0), P(x0, s1, h0), P(x0, s1, h1), P(x0, s0, h1)], Vector((-1, 0, 0))),
        "right": ([P(x1, s0, h0), P(x1, s1, h0), P(x1, s1, h1), P(x1, s0, h1)], Vector((1, 0, 0))),
    }
    for k, (pts, out) in faces.items():
        if k not in skip:
            m.poly(role, pts, out=out)


def rooflight(m, x, y):
    """A small cast-iron rooflight on the back slope, its top edge y from the ridge's line."""
    s0 = (y - CY) / math.cos(PITCH)
    w, L = 0.62, 0.82
    onslope(m, "lead", x - w / 2 - 0.08, x + w / 2 + 0.08, s0 - 0.12, s0 + L + 0.04, -0.01, 0.015, CY)
    onslope(m, "iron", x - w / 2, x + w / 2, s0, s0 + L, 0.0, 0.09, CY, skip=("top",))
    onslope(m, "skyglass", x - w / 2 + 0.05, x + w / 2 - 0.05, s0 + 0.05, s0 + L - 0.05, 0.0, 0.075, CY, skip=("up", "down", "left", "right"))
    for (a, b, s, e) in ((x - w / 2, x - w / 2 + 0.05, s0, s0 + L), (x + w / 2 - 0.05, x + w / 2, s0, s0 + L), (x - w / 2, x + w / 2, s0, s0 + 0.05), (x - w / 2, x + w / 2, s0 + L - 0.05, s0 + L), (x - 0.015, x + 0.015, s0, s0 + L)):
        onslope(m, "iron", a, b, s, e, 0.075, 0.095, CY, skip=("up",))


def aerial(m, x, y, z):
    """A TV aerial on a mast clamped to the side of a stack: a boom along y with its elements across."""
    m.box("iron", (x, y - 0.025, z - 0.9), (x + 0.05, y + 0.025, z + 1.3))
    for zc in (z - 0.7, z - 0.25):
        m.box("iron", (x - 0.02, y - 0.05, zc), (x + 0.06, y + 0.05, zc + 0.04))
    zb = z + 1.15
    m.box("iron", (x - 0.01, y - 0.65, zb), (x + 0.06, y + 0.55, zb + 0.03))
    for i in range(9):
        yy = y - 0.6 + i * 0.13
        half = 0.32 - 0.015 * i
        m.box("iron", (x + 0.025 - half, yy - 0.006, zb + 0.01), (x + 0.025 + half, yy + 0.006, zb + 0.022))
    # The reflector: a short mast at the boom's end with three rods across.
    m.box("iron", (x + 0.01, y - 0.67, zb - 0.2), (x + 0.04, y - 0.64, zb + 0.24))
    for dz in (-0.18, 0.02, 0.22):
        m.box("iron", (x + 0.025 - 0.3, y - 0.662, zb + dz), (x + 0.025 + 0.3, y - 0.65, zb + dz + 0.012))


# ---- gate ---------------------------------------------------------------------------


def gate(m, ox):
    """Two brick piers 1.5 m apart with stone caps and balls, and a low iron gate hung between them."""
    for x in (ox - 0.75, ox + 0.75):
        m.box("brick", (x - 0.2, -0.2, 0), (x + 0.2, 0.2, 1.15), skip=("z0",))
        m.box("stone", (x - 0.25, -0.25, 1.15), (x + 0.25, 0.25, 1.22), skip=("z0",))
        m.box("stone", (x - 0.15, -0.15, 1.22), (x + 0.15, 0.15, 1.28), skip=("z0",))
        m.cyl("stone", x, 0, 0.13, 1.28, 1.36, seg=12, r1=0.15)
        m.cyl("stone", x, 0, 0.15, 1.36, 1.46, seg=12, r1=0.12)
        m.cyl("stone", x, 0, 0.12, 1.46, 1.52, seg=12, r1=0.0)
    # The gate: frame, dog bars and a hooped top rail, straight runs between the piers.
    a, b = ox - 0.53, ox + 0.53
    for x in (a + 0.02, b - 0.02):
        m.box("iron", (x - 0.022, -0.015, 0.08), (x + 0.022, 0.015, 1.0))
    for z in (0.12, 0.92):
        m.box("iron", (a, -0.012, z), (b, 0.012, z + 0.035))
    n = 9
    for i in range(1, n):
        x = a + i * (b - a) / n
        hz = 0.92 + 0.12 * math.sin(math.pi * i / n)
        m.box("iron", (x - 0.008, -0.008, 0.12), (x + 0.008, 0.008, hz))
        m.cyl("iron", x, 0, 0.016, hz, hz + 0.05, seg=6, r1=0.0)
    for x in (a + 0.02, b - 0.02):
        for z in (0.25, 0.85):
            m.box("iron", (x - 0.06 if x < ox else x, -0.01, z), (x if x < ox else x + 0.06, 0.01, z + 0.04))
