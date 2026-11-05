# A2, brownstone row: three Italianate row houses of the 1870s, the kind
# that line the side streets of Brooklyn and Harlem. Each is two bays wide:
# a full-height canted bay on one side and, on the other, a round-arched
# double door under a heavy hood on consoles, reached by a stoop of ten
# brownstone steps between cheek walls with cast-iron railings and newel
# lamps. The garden storey is rusticated; the parlour storey above it is
# the tallest. The bays stop under the top storey, whose French doors open
# onto their railed tops. A bracketed Italianate cornice of painted sheet
# metal runs the length of the row. Houses alternate (mirrored plans), so
# the first two stoops pair up. Sides and back are common brick; flat roof
# behind low parapets with fire walls between the houses, chimney stacks on
# the party walls, hatches, skylights. The app tints brownstone, cornice,
# frames and each house's door; the areaways and back gardens are drawn
# round it.
#
# Pieces (base at the origin, stacked by the app):
#   ground   5.6 m: garden storey (0-1.8) and parlour storey, stoops, doors
#   floor    3.3 m: a typical upper storey, the bays going on up
#   top      3.1 m: the top storey, over the railed bay tops
#   roof     the cornice, parapets, roof and what stands on it
import math

from mathutils import Vector

from lib import Model, Side, Z, aerial, french, grille, hood, new_id, offset, pane, sash, sides, sill

ID = "a2"
N, HW = 3, 5.2  # houses, each 5.2 m (17 ft) wide
W, D = N * HW, 10.2
X0, X1 = -W / 2, W / 2
STOOP = 3.43  # the stoops' reach in front of the wall
Y0 = (STOOP - D) / 2  # front wall: the footprint (stoops to back wall) is centred
Y1 = Y0 + D
CY = (Y0 + Y1) / 2
GL = 1.8  # parlour floor: top of the stoop
G = 5.6  # top of the ground piece
FL = 3.3  # typical upper storey
TF = 3.1  # top storey
MIRROR = (False, True, False)  # house plans: bay left, door right; mirrored; again
BAY = (0.35, 3.45)  # the bay's width at the wall, in a house's own u (from its left party wall)
P = 0.75  # its projection
DOOR = (3.8, 4.85)
SPRING = GL + 2.55  # the door arch's springing line
DEPTH = 0.22  # window reveals
DOORS = ("door", "door2", "door3")  # each house its own paint


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    storey(M, G, FL, top=False)
    M.piece("top", (0, 0, G + FL))
    storey(M, G + FL, TF, top=True)
    M.piece("roof", (0, 0, G + FL + TF))
    roof(M, G + FL + TF)
    M.export(out, bake)


# ---- plan --------------------------------------------------------------------------


def X(k, u):
    """x of a point u along house k's front, measured from its own left party wall (mirrored houses run the other way)."""
    return X0 + k * HW + (HW - u if MIRROR[k] else u)


def span(k, a, b):
    p, q = X(k, a), X(k, b)
    return min(p, q), max(p, q)


def flats():
    """The stretches of front wall between the bays."""
    out, u = [], X0
    for a, b in sorted(span(k, *BAY) for k in range(N)):
        out.append((u, a))
        u = b
    out.append((u, X1))
    return [(a, b) for a, b in out if b - a > 1e-6]


def front_wall(F, z0, z1, holes):
    for a, b in flats():
        F.wall("brownstone", a, b, z0, z1, [h for h in holes if a - 1e-6 <= h[0] and h[1] <= b + 1e-6], depth=DEPTH, reveal="brownstone")


def bay_poly(k, d=0.0):
    ua, ub = span(k, *BAY)
    poly = [(ua, 0.0), (ua + P, P), (ub - P, P), (ub, 0.0)]
    return [(p.x, p.y) for p in offset(poly, d)] if d else poly


def bay_faces(m, F, k):
    """The bay's three faces as Sides (origin mid-face at z 0), with their lengths."""
    poly = bay_poly(k)
    out = []
    for (ua, wa), (ub, wb) in zip(poly, poly[1:]):
        a, b = F.p(ua, 0, wa), F.p(ub, 0, wb)
        t = (b - a).normalized()
        out.append((Side(m, (a + b) / 2, t, t.cross(Z)), (b - a).length))
    return out


def bay(m, F, k, z0, z1, c, e, kind):
    """One storey of house k's bay from z0 to z1, a one-over-one sash from c to e in each face.

    kind: "garden" (rusticated, barred), "parlour" or "upper".
    """
    x = 0.03  # boxes run on past the faces' ends to close the corners
    for S, L in bay_faces(m, F, k):
        half = 0.5 if L > 1.2 else 0.3
        S.wall("brownstone", -L / 2, L / 2, z0, z1, [(-half, half, c, e)], depth=DEPTH, reveal="brownstone")
        sash(S, -half, half, c, e, D=DEPTH, lights=(1, 1))
        sill(S, -half, half, c, D=DEPTH, role="brownstone")
        if kind == "garden":
            grille(S, -half, half, c, e)
            S.box("brownstone", -L / 2 - x, L / 2 + x, 0, 0.24, 0, 0.05)
            # Rustication: courses standing proud, broken by the window.
            for i in range(4):
                za, zb = 0.27 + i * 0.36, 0.27 + i * 0.36 + 0.32
                if zb > z1 - 0.2:
                    break
                cut = za < e + 0.05 and zb > c - 0.1
                for ua, ub in ([(-L / 2 - x, -half - 0.02), (half + 0.02, L / 2 + x)] if cut else [(-L / 2 - x, L / 2 + x)]):
                    S.box("brownstone", ua, ub, za, zb, 0, 0.03)
            # The water table at the parlour floor.
            S.box("brownstone", -L / 2 - x, L / 2 + x, z1 - 0.18, z1, 0, 0.07)
            continue
        # A moulded head over the window, a sunk panel under the sill, a band at the floor above.
        S.box("brownstone", -half - 0.09, half + 0.09, e, e + 0.12, 0, 0.035)
        S.box("brownstone", -half - 0.11, half + 0.11, e + 0.12, e + 0.18, 0, 0.06)
        if c - 0.12 - (z0 + 0.22) > 0.25:
            S.box("brownstone", -half + 0.02, half - 0.02, z0 + 0.22, c - 0.14, 0, 0.012)
            S.box("brownstone", -half + 0.08, half - 0.08, z0 + 0.28, c - 0.2, 0, 0.022)
        S.box("brownstone", -L / 2 - x, L / 2 + x, z1 - 0.2, z1, 0, 0.05)
        S.box("brownstone", -L / 2 - x - 0.02, L / 2 + x + 0.02, z1 - 0.07, z1, 0, 0.08)


def ceiling(m, z):
    """A dark ceiling over a storey, seen only when what is above has gone."""
    e = 0.02
    m.poly("dark", [(X0 + e, Y0 + e, z), (X1 - e, Y0 + e, z), (X1 - e, Y1 - e, z), (X0 + e, Y1 - e, z)], out=Z)
    for k in range(N):
        pts = [Vector((u, Y0 - w + (e if w == 0 else -e), z)) for u, w in bay_poly(k)]
        m.poly("dark", pts, out=Z)


# ---- the ground piece -------------------------------------------------------------------


def ground(M):
    m, cut = M.m, M.cut
    walls = sides(m, W, D, cy=CY)
    F = walls["front"]
    doors = [span(k, *DOOR) for k in range(N)]
    top = SPRING + (DOOR[1] - DOOR[0]) / 2
    front_wall(F, 0, GL, [])
    front_wall(F, GL, G, [(a, b, GL, top, 0.45) for a, b in doors])
    for a, b in flats():
        F.box("brownstone", a, b, 0, 0.24, 0, 0.04, skip=("back", "left", "right"))
        F.box("brownstone", a, b, GL - 0.18, GL, 0, 0.07, skip=("back", "left", "right"))
    for k in range(N):
        bay(m, F, k, 0, GL, 0.5, 1.45, "garden")
        bay(m, F, k, GL, G, GL + 0.5, GL + 3.05, "parlour")
        doorway(m, F, k)
        stoop(m, F, cut, k)
    # Sides: common brick, blank (party walls the row was built to share).
    for name in ("left", "right"):
        walls[name].wall("brick", -D / 2, D / 2, 0, G, [])
    B = walls["back"]
    # One wall for both storeys at the back: the garden door rises past the parlour floor.
    back(B, 0, G, [((0.9, 1.9), (0.55, 1.6)), ((0.8, 1.9), (GL + 0.7, GL + 3.1)), ((3.3, 4.4), (GL + 0.7, GL + 3.1))], door=True)
    downpipes(m, 0.15, G)
    ceiling(m, G - 0.01)


def doorway(m, F, k):
    """The front door: a round-arched opening with a deep reveal, double doors
    under a transom and fanlight, brownstone pilasters, an archivolt with a
    keystone, and a hood on two consoles."""
    a, b = span(k, *DOOR)
    r = (b - a) / 2
    c = (a + b) / 2
    top = SPRING + r
    d = 0.45
    p = F.p
    arc = [(c - r * math.cos(math.pi * i / 12), SPRING + r * math.sin(math.pi * i / 12)) for i in range(13)]
    # Fill the rectangular hole's corners down to the arch, and line the arch.
    for i in range(12):
        corner = (a, top) if i < 6 else (b, top)
        m.poly("brownstone", [p(*corner), p(*arc[i]), p(*arc[i + 1])], out=F.n)
        (u0, z0), (u1, z1) = arc[i], arc[i + 1]
        inward = F.t * (c - (u0 + u1) / 2) + Z * (SPRING - (z0 + z1) / 2)
        m.poly("brownstone", [p(u0, z0), p(u1, z1), p(u1, z1, -d), p(u0, z0, -d)], out=inward)
    # Archivolt: a moulded band round the arch, a keystone at its crown.
    ro = r + 0.16
    ring = [(c - ro * math.cos(math.pi * i / 12), SPRING + ro * math.sin(math.pi * i / 12)) for i in range(13)]
    for i in range(12):
        (ia, za), (ib, zb) = arc[i], arc[i + 1]
        (oa, ya), (ob, yb) = ring[i], ring[i + 1]
        m.poly("brownstone", [p(ia, za, 0.05), p(ib, zb, 0.05), p(ob, yb, 0.05), p(oa, ya, 0.05)], out=F.n)
        out = F.t * ((oa + ob) / 2 - c) + Z * ((ya + yb) / 2 - SPRING)
        m.poly("brownstone", [p(oa, ya, 0), p(ob, yb, 0), p(ob, yb, 0.05), p(oa, ya, 0.05)], out=out)
    F.box("brownstone", c - 0.1, c + 0.1, top - 0.06, top + 0.3, 0, 0.09)
    for u0, u1 in ((a - 0.2, a), (b, b + 0.2)):
        F.box("brownstone", u0, u1, GL, SPRING, 0, 0.06)
        F.box("brownstone", u0 - 0.03, u1 + 0.03, SPRING - 0.12, SPRING, 0, 0.09)
        F.box("brownstone", u0 - 0.03, u1 + 0.03, GL, GL + 0.3, 0, 0.09)
    # The hood: consoles over the pilasters, a frieze, a cornice.
    zh = top + 0.3
    for u in (a - 0.3, b + 0.12):
        F.box("brownstone", u, u + 0.18, zh - 0.75, zh - 0.38, 0, 0.13)
        F.box("brownstone", u, u + 0.18, zh - 0.38, zh, 0, 0.27)
        F.box("brownstone", u + 0.03, u + 0.15, zh - 0.88, zh - 0.75, 0, 0.07)
    F.box("brownstone", a - 0.12, b + 0.12, zh - 0.26, zh, 0, 0.05)
    F.box("brownstone", a - 0.34, b + 0.34, zh, zh + 0.12, 0, 0.32)
    F.box("brownstone", a - 0.37, b + 0.37, zh + 0.12, zh + 0.2, 0, 0.36)
    # In the reveal: frame, two leaves under a transom, the fanlight.
    w = -d
    role = DOORS[k]
    tr = GL + 2.25
    F.box(role, a, a + 0.07, GL, SPRING, w, w + 0.1)
    F.box(role, b - 0.07, b, GL, SPRING, w, w + 0.1)
    F.box(role, a + 0.07, b - 0.07, tr, tr + 0.08, w, w + 0.12)
    wid = new_id()
    rf = r - 0.07
    fan = [(a + 0.07, tr + 0.08), (b - 0.07, tr + 0.08)] + [(c + rf * math.cos(math.pi * i / 12), SPRING + rf * math.sin(math.pi * i / 12)) for i in range(13)]
    m.poly("doorglass", [p(u, z, w + 0.04) for u, z in fan], out=F.n, uvs=[(wid + (u - a) / (b - a), (z - GL) / (top - GL)) for u, z in fan])
    for ang in (math.pi / 4, math.pi / 2, 3 * math.pi / 4):
        m.strut(role, p(c, tr + 0.1, w + 0.06), p(c + rf * math.cos(ang), SPRING + rf * math.sin(ang), w + 0.06), 0.025)
    mid = (a + b) / 2
    for l0, l1 in ((a + 0.07, mid - 0.004), (mid + 0.004, b - 0.07)):
        F.quad(role, l0, l1, GL, tr, w + 0.03)
        for z0, z1 in ((GL + 0.15, GL + 0.75), (GL + 0.9, tr - 0.15)):
            F.box(role, l0 + 0.07, l1 - 0.07, z0, z1, w + 0.03, w + 0.05)
            F.box(role, l0 + 0.11, l1 - 0.11, z0 + 0.04, z1 - 0.04, w + 0.05, w + 0.065)
    F.box("brass", mid - 0.1, mid - 0.04, GL + 1.0, GL + 1.07, w + 0.03, w + 0.1)
    F.box("brass", mid + 0.04, mid + 0.1, GL + 1.0, GL + 1.07, w + 0.03, w + 0.1)
    F.box("brass", mid - 0.12, mid + 0.12, GL + 0.82, GL + 0.86, w + 0.05, w + 0.07)
    # The vestibule's floor, and a house number on the transom.
    F.box("brownstone", a, b, GL - 0.02, GL, w, 0, skip=("back", "bottom", "left", "right"))
    F.box("brass", mid - 0.12, mid + 0.12, tr + 0.01, tr + 0.07, w + 0.12, w + 0.13)


def stoop(m, F, cut, k):
    """Ten brownstone steps up to the door between cheek walls, iron railings on them, lamps on the newels."""
    a, b = span(k, *DOOR)
    c = (a + b) / 2
    hw, cw = 0.65, 0.18  # half the flight's width, the cheek walls
    n, land, tread = 10, 1.0, 0.27
    rise = GL / n
    run = land + (n - 1) * tread
    p = F.p
    front = [land + (n - 1 - i) * tread for i in range(n - 1)]  # each tread's nosing, bottom up
    for i, w in enumerate(front):
        z = (i + 1) * rise
        back_ = front[i + 1] if i + 1 < len(front) else land
        F.quad("brownstone", c - hw, c + hw, z - rise, z, w)
        m.poly("brownstone", [p(c - hw, z, w), p(c + hw, z, w), p(c + hw, z, back_), p(c - hw, z, back_)], out=Z)
        F.box("brownstone", c - hw, c + hw, z - 0.05, z, w - 0.02, w + 0.03, skip=("back", "left", "right"))
    F.quad("brownstone", c - hw, c + hw, GL - rise, GL, land)
    m.poly("brownstone", [p(c - hw, GL, land), p(c + hw, GL, land), p(c + hw, GL, 0), p(c - hw, GL, 0)], out=Z)
    zb, zl = rise + 0.42, GL + 0.42  # cheek tops at the foot and at the landing

    def cheek(w):
        return zl if w <= land else zb + (run - w) * (zl - zb) / (run - land)

    for s in (-1, 1):
        ui, uo = c + s * hw, c + s * (hw + cw)
        prof = [(run, 0.0), (run, zb), (land, zl), (0.0, zl), (0.0, 0.0)]
        m.poly("brownstone", [p(uo, z, w) for w, z in prof], out=F.t * s)
        m.poly("brownstone", [p(ui, z, w) for w, z in prof], out=-F.t * s)
        m.poly("brownstone", [p(ui, zb, run), p(uo, zb, run), p(uo, zl, land), p(ui, zl, land)], out=Z + F.n)
        m.poly("brownstone", [p(ui, zl, land), p(uo, zl, land), p(uo, zl, 0), p(ui, zl, 0)], out=Z)
        F.quad("brownstone", ui, uo, 0, zb, run)
        # The newel: a pedestal with a cap, an iron lamp standard on it.
        un = (ui + uo) / 2
        w0, w1 = run - 0.36, run + 0.02
        F.box("brownstone", un - 0.17, un + 0.17, 0, 0.98, w0, w1, skip=("bottom",))
        F.box("brownstone", un - 0.21, un + 0.21, 0.98, 1.06, w0 - 0.04, w1 + 0.04, skip=("bottom",))
        F.box("brownstone", un - 0.21, un + 0.21, 0.0, 0.14, w0 - 0.04, w1 + 0.04, skip=("bottom",))
        wn = (w0 + w1) / 2
        q = p(un, 0, wn)
        m.cyl("iron", q.x, q.y, 0.07, 1.06, 1.16, seg=10, r1=0.045)
        m.cyl("iron", q.x, q.y, 0.035, 1.16, 1.7, seg=8)
        m.cyl("iron", q.x, q.y, 0.06, 1.7, 1.75, seg=10)
        m.cyl("lamp", q.x, q.y, 0.1, 1.75, 1.95, seg=12, r1=0.13)
        m.cyl("iron", q.x, q.y, 0.14, 1.95, 2.0, seg=12, r1=0.05)
        m.cyl("iron", q.x, q.y, 0.02, 2.0, 2.12, seg=6, r1=0.0)
        # The railing: a handrail along the slope and the landing, bars beneath.
        h = 0.62
        ws = [w0 - 0.01, land, 0.05]
        rail = [p(un, cheek(w) + h, w) for w in ws]
        rail[0] = p(un, 1.06 + 0.02, w0 - 0.01)
        for q0, q1 in zip(rail, rail[1:]):
            m.strut("iron", q0, q1, 0.06, 0.045)
        for wa, wb in zip(ws, ws[1:]):
            za0, za1 = cheek(wa), cheek(wb)
            ta = rail[ws.index(wa)].z - 0.03
            tb = rail[ws.index(wb)].z - 0.03
            L = abs(wa - wb)
            cut.poly("bars", [p(un, za0, wa), p(un, za1, wb), p(un, tb, wb), p(un, ta, wa)], out=F.t, uvs=[(0, 0), (L / 1.2, 0), (L / 1.2, 1), (0, 1)])
            m.strut("iron", p(un, za0 + 0.06, wa), p(un, za1 + 0.06, wb), 0.035)
        F.box("iron", un - 0.03, un + 0.03, zl, zl + h, land - 0.03, land + 0.03)


def back(B, z0, z1, wins, door=False):
    """A storey of the brick back wall: per house, windows (local u, absolute or
    storey-relative z) with stone sills and gauged brick arches; the garden door."""
    holes, sashes = [], []
    for k in range(N):
        for (ua, ub), (c, e) in wins:
            x0, x1 = span(k, ua, ub)
            holes.append((-x1, -x0, c, e))
            sashes.append((-x1, -x0, c, e))
        if door:
            x0, x1 = span(k, 3.4, 4.35)
            holes.append((-x1, -x0, 0.0, 2.05))
    B.wall("brick", -W / 2, W / 2, z0, z1, holes, depth=0.2, reveal="brick")
    for a, b, c, e in sashes:
        sash(B, a, b, c, e, D=0.2, lights=(1, 1))
        sill(B, a, b, c, D=0.2)
        B.box("brick", a - 0.06, b + 0.06, e, e + 0.23, 0, 0.018)
    if door:
        for k in range(N):
            x0, x1 = span(k, 3.4, 4.35)
            a, b = -x1, -x0
            role = DOORS[k]
            B.box(role, a, a + 0.06, 0, 2.05, -0.2, -0.1)
            B.box(role, b - 0.06, b, 0, 2.05, -0.2, -0.1)
            B.box(role, a + 0.06, b - 0.06, 1.99, 2.05, -0.2, -0.1)
            B.quad(role, a + 0.06, b - 0.06, 0, 1.99, -0.17)
            pane(B, "glass", a, b, 0, 2.05, a + 0.18, b - 0.18, 1.05, 1.86, -0.165, new_id())
            B.box(role, a + 0.16, b - 0.16, 0.2, 0.9, -0.17, -0.15)
            B.box("brass", b - 0.2, b - 0.14, 0.98, 1.04, -0.17, -0.12)
            B.box("brick", a - 0.06, b + 0.06, 2.05, 2.28, 0, 0.018)
            B.box("stone", a - 0.15, b + 0.15, 0, 0.12, 0, 0.35, skip=("back", "bottom"))


def downpipes(m, z0, z1):
    """The back wall's downpipes, one a house beside its party wall, with clips."""
    for k in range(N):
        x = X0 + k * HW + 0.35
        m.box("iron", (x - 0.04, Y1 + 0.03, z0), (x + 0.04, Y1 + 0.11, z1))
        for z in (z0 + 0.3, (z0 + z1) / 2 + 0.6):
            if z < z1 - 0.1:
                m.box("iron", (x - 0.06, Y1, z), (x + 0.06, Y1 + 0.13, z + 0.04))
        if z0 < 0.2:
            m.box("iron", (x - 0.05, Y1 + 0.03, z0), (x + 0.2, Y1 + 0.13, z0 + 0.12))


# ---- upper storeys ----------------------------------------------------------------------


def cap(F, a, b, e, role="brownstone"):
    """A plain moulded cap over a window."""
    F.box(role, a - 0.1, b + 0.1, e, e + 0.16, 0, 0.04)
    F.box(role, a - 0.14, b + 0.14, e + 0.16, e + 0.24, 0, 0.09)


def storey(M, z0, h, top):
    """A typical upper storey (the bays rising through it), or the top storey over the bays' railed tops."""
    m, cut = M.m, M.cut
    walls = sides(m, W, D, cy=CY)
    F = walls["front"]
    z1 = z0 + h
    c, e = z0 + 0.75, z0 + (2.35 if top else 2.85)
    over = [span(k, 3.88, 4.78) for k in range(N)]  # a window over each door
    if top:
        doors = [span(k, 1.35, 2.45) for k in range(N)]
        holes = [(a, b, c, e) for a, b in over] + [(a, b, z0 + 0.15, z0 + 2.45) for a, b in doors]
        F.wall("brownstone", X0, X1, z0, z1, holes, depth=DEPTH, reveal="brownstone")
        for a, b in over:
            sash(F, a, b, c, e, D=DEPTH, lights=(1, 1))
            sill(F, a, b, c, D=DEPTH, role="brownstone")
            cap(F, a, b, e)
        for a, b in doors:
            french(F, a, b, z0 + 0.15, z0 + 2.45, D=DEPTH)
            cap(F, a, b, z0 + 2.45)
        for k in range(N):
            bay_top(m, F, cut, k, z0)
    else:
        front_wall(F, z0, z1, [(a, b, c, e) for a, b in over])
        for a, b in over:
            sash(F, a, b, c, e, D=DEPTH, lights=(1, 1))
            sill(F, a, b, c, D=DEPTH, role="brownstone")
            hood(F, a, b, e, role="brownstone")
        for k in range(N):
            bay(m, F, k, z0, z1, c, e, "upper")
    for name in ("left", "right"):
        walls[name].wall("brick", -D / 2, D / 2, z0, z1, [])
    rel = (0.75, 2.35 if top else 2.75)
    back(walls["back"], z0, z1, [((0.9, 1.9), (z0 + rel[0], z0 + rel[1])), ((3.3, 4.3), (z0 + rel[0], z0 + rel[1]))])
    downpipes(m, z0, z1)
    ceiling(m, z1 - 0.01)


def bay_top(m, F, cut, k, z):
    """The top of house k's bay at z: a lead flat behind a moulded edge, a railing round it."""
    e3 = [Vector((u, Y0 - w, 0)) for u, w in bay_poly(k, 0.1)]
    zt = z + 0.15
    m.poly("lead", [q + Z * zt for q in e3], out=Z)
    m.poly("brownstone", [q + Z * (z - 0.06) for q in e3], out=-Z)
    for a, b in zip(e3, e3[1:]):
        out = (b - a).cross(Z)
        m.poly("brownstone", [a + Z * (z - 0.06), b + Z * (z - 0.06), b + Z * zt, a + Z * zt], out=out)
    # The railing, set in from the edge, posts at the corners and the wall.
    rl = [Vector((u, Y0 - w, 0)) for u, w in bay_poly(k, 0.02)]
    hgt = 0.95
    for a, b in zip(rl, rl[1:]):
        L = (b - a).length
        out = (b - a).cross(Z)
        cut.poly("bars", [a + Z * (zt + 0.05), b + Z * (zt + 0.05), b + Z * (zt + hgt - 0.04), a + Z * (zt + hgt - 0.04)], out=out, uvs=[(0, 0), (L / 1.2, 0), (L / 1.2, 1), (0, 1)])
        m.strut("iron", a + Z * (zt + hgt), b + Z * (zt + hgt), 0.06, 0.04)
        m.strut("iron", a + Z * (zt + 0.05), b + Z * (zt + 0.05), 0.04)
    for q in rl:
        m.box("iron", (q.x - 0.03, q.y - 0.03, zt), (q.x + 0.03, q.y + 0.03, zt + hgt + 0.03))
        m.cyl("iron", q.x, q.y, 0.035, zt + hgt + 0.03, zt + hgt + 0.1, seg=8, r1=0.0)


# ---- roof ---------------------------------------------------------------------------------

# The cornice's profile from the top of the wall: (projection, height), rising.
CORNICE = [(0.0, 0.0), (0.06, 0.0), (0.06, 0.12), (0.03, 0.15), (0.03, 0.86), (0.08, 0.89), (0.12, 0.94), (0.12, 1.06),
           (0.74, 1.06), (0.74, 1.24), (0.8, 1.28), (0.86, 1.36), (0.88, 1.42), (0.0, 1.42)]
CROWN = 1.42
DECK = 0.95  # the roof's surface above the top of the wall
PARAPET = 1.3


def run_front(m, role, x0, x1, y, z, prof):
    """A moulding along the front wall from x0 to x1, profile (out, up) from z, capped at both ends."""
    for (o0, h0), (o1, h1) in zip(prof, prof[1:]):
        dz, do = h1 - h0, o1 - o0
        out = Vector((0, -dz, -do))
        if out.length < 1e-6:
            continue
        m.poly(role, [(x0, y - o0, z + h0), (x1, y - o0, z + h0), (x1, y - o1, z + h1), (x0, y - o1, z + h1)], out=out)
        if dz > 1e-6:
            for x, s in ((x0, -1), (x1, 1)):
                m.poly(role, [(x, y, z + h0), (x, y - o0, z + h0), (x, y - o1, z + h1), (x, y, z + h1)], out=(s, 0, 0))


def bracket(m, x, z):
    """A scrolled console under the cornice: its face curving out to the soffit, volutes top and bottom."""
    zb, zt = z + 0.12, z + 1.06
    t = 0.08
    n = 8
    pts = []
    for i in range(n + 1):
        s = i / n
        pts.append((0.1 + 0.58 * s ** 1.8, zb + (zt - zb) * s))
    y = Y0
    for (w0, h0), (w1, h1) in zip(pts, pts[1:]):
        for sx in (-1, 1):
            xx = x + sx * t
            m.poly("cornice", [(xx, y, h0), (xx, y - w0, h0), (xx, y - w1, h1), (xx, y, h1)], out=(sx, 0, 0))
        out = Vector((0, -(h1 - h0), w1 - w0))
        m.poly("cornice", [(x - t, y - w0, h0), (x + t, y - w0, h0), (x + t, y - w1, h1), (x - t, y - w1, h1)], out=-out if out.y > 0 else out)
    m.poly("cornice", [(x - t, y, zb), (x + t, y, zb), (x + t, y - pts[0][0], zb), (x - t, y - pts[0][0], zb)], out=-Z)
    # Volutes: rolls across the console's face at the foot and under the soffit, and a drop below.
    for w, h, r in ((0.13, zb + 0.06, 0.07), (0.6, zt - 0.08, 0.085)):
        m.tube("cornice", [Vector((x - t - 0.01, y - w, h)), Vector((x + t + 0.01, y - w, h))], r, Vector((0, 1, 0)), closed=False, seg=8)
    m.box("cornice", (x - 0.05, y - 0.16, zb - 0.16), (x + 0.05, y - 0.06, zb))


def roof(M, z):
    m = M.m
    walls = sides(m, W, D, cy=CY)
    run_front(m, "cornice", X0, X1, Y0, z, CORNICE)
    # Brackets in pairs at the party walls and the ends, two between them in each house.
    xs = []
    for k in range(N):
        x = X0 + k * HW
        xs += [x + 0.2, x + HW / 3, x + 2 * HW / 3, x + HW - 0.2]
    for x in xs:
        bracket(m, x, z)
    # Frieze panels between the brackets, modillions and dentils under the soffit.
    F = walls["front"]
    for x0, x1 in zip(xs, xs[1:]):
        if x1 - x0 < 0.5:
            continue
        F.box("cornice", x0 + 0.2, x1 - 0.2, z + 0.28, z + 0.72, 0.03, 0.045, skip=("back",))
        F.box("cornice", x0 + 0.26, x1 - 0.26, z + 0.34, z + 0.66, 0.045, 0.055, skip=("back",))
        nm = max(1, int((x1 - x0 - 0.4) / 0.42))
        for i in range(nm):
            u = x0 + 0.2 + (i + 0.5) * (x1 - x0 - 0.4) / nm
            F.box("cornice", u - 0.05, u + 0.05, z + 0.98, z + 1.06, 0.12, 0.62, skip=("back", "top"))
    nd = int(W / 0.11)
    for i in range(nd):
        u = X0 + (i + 0.5) * W / nd
        F.box("cornice", u - 0.032, u + 0.032, z + 0.94, z + 1.06, 0.12, 0.19, skip=("back", "top"))
    # The front wall's top behind the cornice, and the parapets round the roof.
    zd, zp = z + DECK, z + PARAPET
    m.poly("cornice", [(X0, Y0, z + CROWN), (X1, Y0, z + CROWN), (X1, Y0 + 0.35, z + CROWN), (X0, Y0 + 0.35, z + CROWN)], out=Z)
    m.poly("brick", [(X0 + 0.3, Y0 + 0.35, zd), (X1 - 0.3, Y0 + 0.35, zd), (X1 - 0.3, Y0 + 0.35, z + CROWN), (X0 + 0.3, Y0 + 0.35, z + CROWN)], out=(0, 1, 0))
    for name in ("left", "right", "back"):
        S = walls[name]
        h = D / 2 if name != "back" else W / 2
        S.wall("brick", -h, h, z, zp, [])
        S.quad("brick", h - 0.3, -h + 0.3, zd, zp, -0.3, out=-S.n)
        S.box("stone", -h, h, zp, zp + 0.08, -0.34, 0.04, skip=())
        if name == "back":
            S.box("brick", -h, h, z + 0.1, z + 0.18, 0, 0.04, skip=("back",))
            S.box("brick", -h, h, z + 0.26, z + 0.34, 0, 0.06, skip=("back",))
    m.box("stone", (X0, Y0 + 0.3, zp), (X0 + 0.3, Y0 + 0.36, z + CROWN))
    m.box("stone", (X1 - 0.3, Y0 + 0.3, zp), (X1, Y0 + 0.36, z + CROWN))
    m.poly("roof", [(X0 + 0.3, Y0 + 0.35, zd), (X1 - 0.3, Y0 + 0.35, zd), (X1 - 0.3, Y1 - 0.3, zd), (X0 + 0.3, Y1 - 0.3, zd)], out=Z)
    # Fire walls between the houses, coped.
    for k in (1, 2):
        x = X0 + k * HW
        m.box("brick", (x - 0.15, Y0 + 0.35, zd), (x + 0.15, Y1 - 0.3, zp + 0.1), skip=("z0", "y0", "y1"))
        m.box("stone", (x - 0.19, Y0 + 0.35, zp + 0.1), (x + 0.19, Y1 - 0.3, zp + 0.17), skip=("z0", "y0", "y1"))
    # Leader heads where the roof drains through the back parapet.
    for k in range(N):
        x = X0 + k * HW + 0.35
        m.box("iron", (x - 0.15, Y1 + 0.02, z + 0.45), (x + 0.15, Y1 + 0.26, z + 0.85))
        m.box("iron", (x - 0.18, Y1 + 0.02, z + 0.85), (x + 0.18, Y1 + 0.29, z + 0.9))
        m.box("iron", (x - 0.04, Y1 + 0.03, z), (x + 0.04, Y1 + 0.11, z + 0.45))
    # Chimney stacks on the party walls (front and back) and the end walls.
    stacks = [(X0 + k * HW, y) for k in (1, 2) for y in (Y0 + 2.3, Y1 - 2.6)] + [(X0 + 0.45, CY - 0.4), (X1 - 0.45, CY + 0.6)]
    for i, (x, y) in enumerate(stacks):
        chimney(m, x, y, zd, 1.0 if abs(x) > W / 2 - 1 else 1.2, 0.7, pots=2 + i % 2)
    aerial(m, stacks[1][0] + 0.6, stacks[1][1], zd + 1.9 + 0.12)
    for k in range(N):
        x = X0 + k * HW
        hx = x + (HW - 1.4 if MIRROR[k] else 1.4)
        hatch(m, hx, CY + 1.4, zd)
        skylight(m, x + (HW - 3.2 if MIRROR[k] else 3.2), CY - 0.4, zd)
        vx = x + (HW - 4.0 if MIRROR[k] else 4.0)
        m.cyl("iron", vx, Y1 - 1.4, 0.05, zd, zd + 0.9, seg=8)
        m.cyl("iron", vx, Y1 - 1.4, 0.075, zd + 0.9, zd + 0.98, seg=8, r1=0.04)
    # A condenser on the last house's roof.
    ax, ay = X1 - 2.0, Y1 - 1.6
    m.box("ac", (ax - 0.55, ay - 0.35, zd + 0.12), (ax + 0.55, ay + 0.35, zd + 0.9))
    m.cyl("dark", ax, ay, 0.28, zd + 0.9, zd + 0.92, seg=14)
    m.box("concrete", (ax - 0.65, ay - 0.45, zd), (ax + 0.65, ay + 0.45, zd + 0.12))


def chimney(m, x, y, z, wx, wy, pots=2):
    top = z + 1.9
    xa, xb, ya, yb = x - wx / 2, x + wx / 2, y - wy / 2, y + wy / 2
    m.box("brick", (xa, ya, z), (xb, yb, top), skip=("z0",))
    m.sweep("brick", wx, wy, [(-0.01, top - 0.3), (0.06, top - 0.3), (0.06, top - 0.22), (-0.01, top - 0.22)], cx=x, cy=y)
    m.sweep("stone", wx, wy, [(-0.01, top), (0.05, top), (0.05, top + 0.08), (-0.01, top + 0.08)], cx=x, cy=y)
    m.poly("stone", [(xa, ya, top + 0.08), (xb, ya, top + 0.08), (xb, yb, top + 0.08), (xa, yb, top + 0.08)], out=Z)
    for i in range(pots):
        px = x + (i - (pots - 1) / 2) * min(0.32, (wx - 0.3) / max(1, pots - 1))
        m.cyl("terracotta", px, y, 0.11, top + 0.08, top + 0.55, seg=10, r1=0.085)
        m.cyl("terracotta", px, y, 0.11, top + 0.55, top + 0.6, seg=10)


def hatch(m, x, y, z):
    """A roof hatch over the stair: a curb and a lid."""
    m.box("lead", (x - 0.45, y - 0.45, z), (x + 0.45, y + 0.45, z + 0.45), skip=("z0",))
    m.box("lead", (x - 0.5, y - 0.5, z + 0.45), (x + 0.5, y + 0.5, z + 0.52), skip=())
    m.box("iron", (x - 0.02, y - 0.52, z + 0.32), (x + 0.02, y - 0.5, z + 0.47))


def skylight(m, x, y, z):
    """A hipped skylight over the stairwell: a curb, glass in an iron frame, a ridge."""
    a, b = 0.6, 0.45
    zc = z + 0.32
    m.box("lead", (x - a, y - b, z), (x + a, y + b, zc), skip=("z0",))
    r0, r1 = Vector((x - a + b * 0.8, y, zc + 0.36)), Vector((x + a - b * 0.8, y, zc + 0.36))
    c = [Vector((x - a, y - b, zc)), Vector((x + a, y - b, zc)), Vector((x + a, y + b, zc)), Vector((x - a, y + b, zc))]
    for pts in ([c[0], c[1], r1, r0], [c[1], c[2], r1], [c[2], c[3], r0, r1], [c[3], c[0], r0]):
        m.poly("skyglass", pts, out=Z)
    m.strut("iron", r0, r1, 0.04)
    for q, r in ((c[0], r0), (c[1], r1), (c[2], r1), (c[3], r0)):
        m.strut("iron", q, r, 0.03)
    for t in (0.33, 0.66):
        m.strut("iron", c[0].lerp(c[1], t), r0.lerp(r1, t), 0.02)
        m.strut("iron", c[3].lerp(c[2], t), r0.lerp(r1, t), 0.02)
