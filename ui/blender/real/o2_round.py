# O2, round glass tower: a drum of an office tower on a twenty-sided plan,
# 12 m across. A stick-system curtain wall of tinted vision glass between
# spandrel bands, a mullion fin on every facet joint, and at every storey's
# head a thin aluminium sunshade ring standing out 0.65 m, so the tower
# reads as a stack of discs with a shadow line under each. The ground
# storey stands on a ring of ten granite columns round a double-height
# glass lobby drum, set back under the first floor's soffit; in front, a
# cantilevered steel canopy on tie rods carries the name, over a revolving
# door between swing doors. The back of the drum is granite with the
# service door. Tall towers have a plant storey part way up: louvres
# behind a deeper ring. On top a crown: the fins carry on up past the roof
# to a ring with a lit band, round a louvred plant drum, the stair head
# and a mast with an aircraft warning light. The app tints the glass and
# metalwork and picks the name, per building.
#
# The tower's centre is YC behind the footprint's: the canopy is in front.
#
# Pieces (base at the origin, stacked by the app):
#   ground   6.0 m: columns, lobby drum, canopy with the name, revolving door
#   floor    3.7 m: a typical storey
#   plant    3.7 m: the plant storey, louvres behind a deep ring
#   crown    parapet, the fins' crown ring, the plant drum, stair head, mast
import math

from lib import Side, Model, Z, new_id, pane

ID = "o2"
N = 20  # facets
R = 6.0  # the curtain wall's corner radius
YC = 0.4  # the tower's centre, behind the footprint's
RL = 4.6  # the lobby drum
RC = 5.45  # the columns' centre line
G = 6.0  # ground storey
SOFFIT = G - 0.4  # under the first floor's edge band
FL = 3.7  # typical storeys
SILL, HEAD = 0.6, 3.2  # vision glass between, spandrel bands below and above
SHADE = 0.65  # how far the sunshade rings stand out
GLASS_W = -0.03  # the glass plane, just inside the facet line
PAR = 1.2  # parapet
CROWN = 5.0  # the crown ring's top above the roof slab
DOOR = 2.7  # the lobby doors' head
YF = -6.4  # the canopy's front, the footprint's front
CX = 4.0  # the canopy's half width
CZ0, CZ1 = 3.3, 3.85  # the canopy's underside and top


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M.m)
    M.piece("floor", (0, 0, G))
    storey(M.m, G)
    # Each piece at its own height, as stacked, so none shares a vertex with another.
    M.piece("plant", (0, 0, G + FL))
    storey(M.m, G + FL, plant=True)
    M.piece("crown", (0, 0, G + 2 * FL))
    crown(M.m, G + 2 * FL)
    M.export(out, bake)


# ---- the twenty-sided plan ------------------------------------------------------------


def ang(i):
    """Joint i's angle: joint 0 is at the front (-y), counting anticlockwise."""
    return -math.pi / 2 + i * math.tau / N


def at(r, a, z):
    return (r * math.cos(a), YC + r * math.sin(a), z)


def facet(m, i, r):
    """Facet i (joint i to joint i + 1) of the polygon with corner radius r,
    as a facade: u runs from -h at joint i to h at joint i + 1."""
    a = ang(i) + math.pi / N
    ap = r * math.cos(math.pi / N)
    F = Side(m, (ap * math.cos(a), YC + ap * math.sin(a), 0), (-math.sin(a), math.cos(a), 0), (math.cos(a), math.sin(a), 0))
    return F, r * math.sin(math.pi / N)


def joint(m, i, r):
    """A frame at joint i facing straight out, for mullions and fins."""
    a = ang(i)
    x, y, _ = at(r, a, 0)
    return Side(m, (x, y, 0), (-math.sin(a), math.cos(a), 0), (math.cos(a), math.sin(a), 0))


def mid(i):
    """Facet i's middle angle in degrees, -180..180."""
    d = math.degrees(ang(i) + math.pi / N)
    return (d + 180) % 360 - 180


def disc(m, role, r, z, out):
    m.poly(role, [at(r, ang(i), z) for i in range(N)], out=(0, 0, out))


def ring(m, role, r0, r1, z0, z1, edge=None, inner=False):
    """A flat ring between corner radii r0 and r1, z0 to z1 thick: top,
    underside, the outer edge (in `edge`'s role if given), the inner if asked."""
    for i in range(N):
        a, b = ang(i), ang(i + 1)
        c = ang(i) + math.pi / N
        out = (math.cos(c), math.sin(c), 0)
        m.poly(role, [at(r0, a, z1), at(r0, b, z1), at(r1, b, z1), at(r1, a, z1)], out=Z)
        m.poly(role, [at(r0, a, z0), at(r0, b, z0), at(r1, b, z0), at(r1, a, z0)], out=-Z)
        m.poly(edge or role, [at(r1, a, z0), at(r1, b, z0), at(r1, b, z1), at(r1, a, z1)], out=out)
        if inner:
            m.poly(role, [at(r0, a, z0), at(r0, b, z0), at(r0, b, z1), at(r0, a, z1)], out=(-out[0], -out[1], 0))


# ---- storeys -----------------------------------------------------------------------------


def mullion(m, i, z0, z1, fin=0.22):
    J = joint(m, i, R)
    J.box("mullion", -0.04, 0.04, z0, z1, GLASS_W - 0.05, 0.05)
    J.box("mullion", -0.02, 0.02, z0, z1, 0.05, fin)


def storey(m, z, plant=False):
    """A typical storey: spandrel at the slab, vision glass, spandrel to the
    next slab, mullion fins, the sunshade ring at the head. The plant storey
    has louvres instead of vision glass and a deep ring."""
    for i in range(N):
        F, h = facet(m, i, R)
        ga, gb = -h + 0.04, h - 0.04
        F.quad("spandrel", ga, gb, z, z + SILL - 0.03, GLASS_W)
        F.quad("spandrel", ga, gb, z + HEAD + 0.03, z + FL, GLASS_W)
        if plant:
            # Louvres in a recess, the reveals in the mullions' metal.
            F.quad("blades", ga, gb, z + SILL, z + HEAD, -0.25, uvs=[(0, 0), (gb - ga, 0), (gb - ga, HEAD - SILL), (0, HEAD - SILL)])
            F.box("mullion", ga, gb, z + SILL - 0.03, z + SILL, -0.25, GLASS_W, skip=("back", "bottom"))
            F.box("mullion", ga, gb, z + HEAD, z + HEAD + 0.03, -0.25, GLASS_W, skip=("back", "top"))
        else:
            pane(F, "officeglass", ga, gb, z + SILL, z + HEAD, ga, gb, z + SILL + 0.03, z + HEAD - 0.03, GLASS_W - 0.01, new_id())
            for hh in (SILL, HEAD):
                F.box("mullion", ga, gb, z + hh - 0.03, z + hh + 0.03, GLASS_W, 0.04)
        # The stack joint at the slab, where one storey's units meet the next.
        F.box("mullion", ga, gb, z, z + 0.025, GLASS_W, 0.02)
        mullion(m, i, z, z + FL)
    if plant:
        ring(m, "mullion", R - 0.1, R + 1.1, z + HEAD - 0.05, z + HEAD + 0.25, edge="blades")
    else:
        ring(m, "mullion", R - 0.05, R + SHADE, z + HEAD, z + HEAD + 0.05)
    # The slab's underside, seen only when the storey above is gone.
    disc(m, "dark", R, z + FL - 0.02, -1)


# ---- ground storey -----------------------------------------------------------------


def swing_door(F, a, b, c, e, wid):
    """A frameless glass door with a stainless rail at the foot and a long pull."""
    pane(F, "doorglass", a, b, c, e, a + 0.02, b - 0.02, c + 0.12, e - 0.02, -0.03, wid)
    F.box("stainless", a, b, c, c + 0.12, -0.05, 0.0)
    u = b - 0.15 if a < 0 else a + 0.15
    F.box("stainless", u - 0.02, u + 0.02, c + 0.7, c + 2.0, 0.0, 0.06, skip=())


def steel_door(F, a, b, c, e, d):
    """A flush steel door in a frame, with a push bar."""
    F.quad("ac", a + 0.05, b - 0.05, c, e - 0.05, -d + 0.03)
    F.box("mullion", a, a + 0.05, c, e, -d, -d + 0.06)
    F.box("mullion", b - 0.05, b, c, e, -d, -d + 0.06)
    F.box("mullion", a, b, e - 0.05, e, -d, -d + 0.06)
    F.box("dark", a + 0.15, b - 0.15, c + 0.95, c + 1.0, -d + 0.03, -d + 0.07)


def ground(m):
    c = 0.15
    # A granite podium a step up from the plaza.
    disc(m, "granite", R + 0.4, c, 1)
    for i in range(N):
        F, h = facet(m, i, R + 0.4)
        F.quad("granite", -h, h, 0, c)
    # The columns, under every second joint, on stainless shoes.
    for i in range(1, N, 2):
        x, y, _ = at(RC, ang(i), 0)
        m.cyl("granite", x, y, 0.32, c, SOFFIT, seg=12, top=False)
        m.cyl("stainless", x, y, 0.335, c, c + 0.3, seg=12)
    lobby(m, c)
    # The soffit under the first floor, with downlights, and the floor's
    # edge band round the outside.
    for i in range(N):
        a, b = ang(i), ang(i + 1)
        m.poly("panel", [at(RL, a, SOFFIT), at(RL, b, SOFFIT), at(R, b, SOFFIT), at(R, a, SOFFIT)], out=-Z)
        F, h = facet(m, i, R)
        F.quad("mullion", -h, h, SOFFIT, G)
        x, y, _ = at((RL + R) / 2 * math.cos(math.pi / N), ang(i) + math.pi / N, 0)
        m.cyl("lamp", x, y, 0.08, SOFFIT - 0.02, SOFFIT, seg=10, top=False, bottom=True)
    canopy(m)
    revolving(m, 0, YC - RL - 1.1, c, DOOR)
    disc(m, "dark", R, G - 0.02, -1)


def lobby(m, c):
    """The lobby drum: tall glass between slim posts round the front and
    sides, swing doors either side of the revolving door, granite round the
    back with the service door and an intake louvre."""
    solid = [i for i in range(N) if 35 < mid(i) < 145]
    for i in range(N):
        F, h = facet(m, i, RL)
        if i in solid:
            if round(mid(i)) == 81:
                F.wall("granite", -h, h, c, SOFFIT, [(-0.6, 0.6, c, c + 2.3)], depth=0.2)
                steel_door(F, -0.6, 0.6, c, c + 2.3, 0.2)
                F.box("lamp", -0.15, 0.15, c + 2.5, c + 2.62, 0, 0.12)
            elif round(mid(i)) == 99:
                F.wall("granite", -h, h, c, SOFFIT, [(-0.5, 0.5, 2.8, 4.0)], depth=0.12)
                F.quad("blades", -0.5, 0.5, 2.8, 4.0, -0.12, uvs=[(0, 0), (1, 0), (1, 1.2), (0, 1.2)])
            else:
                F.quad("granite", -h, h, c, SOFFIT)
            F.box("granite", -h, h, c, c + 0.3, 0, 0.03, skip=("back", "left", "right"))
            continue
        wid = new_id()
        if i in (1, N - 2):
            # Swing doors under a transom light.
            pane(F, "doorglass", -h, h, c, SOFFIT, -h + 0.03, h - 0.03, DOOR + 0.06, SOFFIT, -0.02, wid)
            F.box("mullion", -h, h, DOOR, DOOR + 0.08, -0.04, 0.06)
            swing_door(F, -h + 0.03, -0.01, c, DOOR, wid)
            swing_door(F, 0.01, h - 0.03, c, DOOR, wid)
        else:
            pane(F, "doorglass", -h, h, c, SOFFIT, -h + 0.02, h - 0.02, c, SOFFIT, -0.02, wid)
            F.box("mullion", -h, h, DOOR + 0.2, DOOR + 0.26, -0.03, 0.03, skip=())
        F.box("mullion", -h, h, c, c + 0.08, -0.02, 0.05)
    for i in range(N):
        if i in solid and (i - 1) % N in solid:
            continue
        J = joint(m, i, RL)
        J.box("mullion", -0.03, 0.03, c, SOFFIT, -0.06, 0.06)


def canopy(m):
    """A steel canopy over the entrance, cantilevered from the drum and hung
    from the first floor on two tie rods; the name on its fascia."""
    xs = [-CX + k * CX / 4 for k in range(9)]
    back = lambda x: YC - math.sqrt(RL * RL - x * x) + 0.1  # noqa: E731
    for x0, x1 in zip(xs, xs[1:]):
        m.poly("mullion", [(x0, YF, CZ1), (x1, YF, CZ1), (x1, back(x1), CZ1), (x0, back(x0), CZ1)], out=Z)
        m.poly("panel", [(x0, YF, CZ0), (x1, YF, CZ0), (x1, back(x1), CZ0), (x0, back(x0), CZ0)], out=-Z)
    for x, out in ((-CX, (-1, 0, 0)), (CX, (1, 0, 0))):
        m.poly("mullion", [(x, YF, CZ0), (x, back(x), CZ0), (x, back(x), CZ1), (x, YF, CZ1)], out=out)
    F = Side(m, (0, YF, 0), (1, 0, 0), (0, -1, 0))
    F.quad("mullion", -CX, CX, CZ0, CZ1)
    F.quad("towername", -CX + 0.2, CX - 0.2, CZ0 + 0.05, CZ1 - 0.05, 0.005, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    for x in (-2.4, -0.8, 0.8, 2.4):
        m.cyl("lamp", x, YF + 1.0, 0.07, CZ0 - 0.02, CZ0, seg=10, top=False, bottom=True)
    # The tie rods, from the canopy's front corners up to the first floor's edge.
    for sx in (-1, 1):
        x = sx * 2.6
        m.strut("stainless", (sx * (CX - 0.3), YF + 0.15, CZ1), (x, YC - math.sqrt(R * R - x * x) + 0.3, SOFFIT), 0.05)


def revolving(m, cx, cy, c, e):
    """A four-wing revolving door in a glass drum, open to the street and the lobby."""
    r, seg = 1.05, 20
    for side in (0.0, math.pi):
        pts = [side + (k / 6 - 0.5) * math.radians(110) for k in range(7)]
        p = lambda a, z: (cx + math.cos(a) * r, cy + math.sin(a) * r, z)  # noqa: E731
        for a0, a1 in zip(pts, pts[1:]):
            m.poly("canopy", [p(a0, c), p(a1, c), p(a1, e), p(a0, e)], out=(math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0))
        for a in (pts[0], pts[-1]):
            x, y, _ = p(a, 0)
            m.box("stainless", (x - 0.03, y - 0.03, c), (x + 0.03, y + 0.03, e))
    m.cyl("stainless", cx, cy, r + 0.05, e, e + 0.3, seg=seg, bottom=True)
    m.cyl("stainless", cx, cy, r + 0.05, c, c + 0.03, seg=seg)
    m.cyl("stainless", cx, cy, 0.06, c, e, seg=8, top=False)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = (math.cos(a), math.sin(a), 0)
        n = (-math.sin(a), math.cos(a), 0)
        W = Side(m, (cx, cy, 0), d, n)
        W.quad("canopy", 0.08, r - 0.06, c + 0.12, e - 0.08, 0.0, out=n)
        W.quad("canopy", 0.08, r - 0.06, c + 0.12, e - 0.08, 0.0, out=(-n[0], -n[1], 0))
        W.box("stainless", r - 0.06, r - 0.02, c + 0.02, e - 0.02, -0.02, 0.02, skip=())
        W.box("stainless", 0.06, r - 0.02, c + 0.02, c + 0.12, -0.02, 0.02, skip=())
        W.box("stainless", 0.06, r - 0.02, e - 0.08, e - 0.02, -0.02, 0.02, skip=())


# ---- the crown ------------------------------------------------------------------------


def crown(m, z):
    for i in range(N):
        F, h = facet(m, i, R)
        ga, gb = -h + 0.04, h - 0.04
        # The parapet: spandrel glass carried on up, a panelled inside face, a coping.
        F.quad("spandrel", ga, gb, z, z + PAR, GLASS_W)
        F.quad("panel", -h, h, z + 0.12, z + PAR, -0.3, out=-F.n)
        F.box("mullion", -h, h, z + PAR, z + PAR + 0.06, -0.32, 0.06, skip=("back",))
        # The fins carry on up to the crown ring.
        J = joint(m, i, R)
        J.box("mullion", -0.04, 0.04, z, z + PAR, GLASS_W - 0.05, 0.05)
        J.box("mullion", -0.03, 0.03, z, z + CROWN - 0.4, 0.05, 0.3)
        J.box("mullion", -0.03, 0.03, z + PAR + 0.06, z + CROWN - 0.4, -0.3, 0.05)
    ring(m, "mullion", R - 0.35, R + 0.36, z + CROWN - 0.55, z + CROWN, edge="halo", inner=True)
    ring(m, "mullion", R - 0.35, R + 0.36, z + PAR + 1.6, z + PAR + 1.7, inner=True)
    disc(m, "roof", R - 0.3, z + 0.12, 1)
    base = z + 0.12
    # The plant drum: louvres round the lift motor room and the air handlers, a metal lid.
    py, pr, ph = YC + 0.8, 2.4, 4.2
    m.cyl("blades", 0, py, pr, base, base + ph, seg=N, top=False, uv=True)
    m.cyl("mullion", 0, py, pr + 0.12, base + ph, base + ph + 0.2, seg=N, bottom=True)
    # The stair head on its front, a door onto the roof and a lamp over it.
    y0, y1 = py - pr - 0.9, py - pr + 0.6
    m.box("panel", (-0.95, y0, base), (0.95, y1, base + 2.7), skip=("z0",))
    S = Side(m, (0, y0, 0), (1, 0, 0), (0, -1, 0))
    steel_door(S, -0.5, 0.5, base, base + 2.2, -0.02)
    m.box("lamp", (-0.15, y0 - 0.12, base + 2.35), (0.15, y0, base + 2.47))
    # Condensers either side, on steel frames.
    for sx in (-1, 1):
        x, y = sx * 3.3, YC - 1.3
        m.box("iron", (x - 0.8, y - 0.5, base), (x + 0.8, y + 0.5, base + 0.25), skip=("z0",))
        m.box("ac", (x - 0.75, y - 0.45, base + 0.25), (x + 0.75, y + 0.45, base + 1.05), skip=("z0",))
        m.cyl("dark", x, y, 0.3, base + 1.05, base + 1.06, seg=14)
    # The mast on the plant drum's lid, with panel antennas and the warning light.
    mz = base + ph + 0.2
    m.cyl("ac", 0, py + 0.6, 0.08, mz, mz + 7.0, seg=8)
    for k in range(3):
        a = k * math.tau / 3
        px, pq = math.cos(a) * 0.17, py + 0.6 + math.sin(a) * 0.17
        m.box("ac", (px - 0.09, pq - 0.09, mz + 4.2), (px + 0.09, pq + 0.09, mz + 5.6))
    m.cyl("beacon", 0, py + 0.6, 0.09, mz + 7.0, mz + 7.22, seg=8)
