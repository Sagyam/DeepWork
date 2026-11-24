# L2, glass supertall: a tower of about 2005 on its own lot, a 14.4 m square
# with its corners cut back 2.2 m at 45 degrees, so the plan is a long-and-
# short octagon. A unitised curtain wall of tinted vision glass storey high
# over a spandrel band, slim mullions with shallow fins on the long faces;
# on each chamfer a stainless sail fin stands out 0.7 m and runs the full
# height, so the corners catch the sun. The shaft steps in twice (14.4,
# 12.8, 11.2 m) at sky storeys of louvres (the plant and the sky lobbies),
# behind a glass balustrade round the terrace. The ground storey is a tall
# glass lobby set back behind granite columns, a cantilevered canopy over a
# revolving door carrying the name, a granite back with the service door.
# The crown: the curtain wall carries on up as a parapet, then the faces
# lean in to a faceted glass lantern ringed with lit bands, the sail fins
# sweeping up its corners, to a stainless spire with an aircraft light. The
# app tints the glass and metalwork and picks the name.
#
# Pieces (base at the origin, stacked by the app):
#   ground  7.0 m: plinth, columns, lobby, canopy with the name, doors
#   floor1  3.8 m: a storey of the lower tier
#   sky2    3.8 m: louvres, the terrace and balustrade where the tier steps in
#   floor2  3.8 m: the middle tier
#   sky3    3.8 m: the same for the upper tier
#   floor3  3.8 m: the upper tier
#   crown   parapet, the lantern, the spire
import math

from lib import Model, Side, Z, fpoly, new_id, pane
from o2_round import revolving, steel_door, swing_door

ID = "l2"
X1, X2, X3 = 7.2, 6.4, 5.6  # the tiers' half widths
C = 2.2  # the chamfer, each way
G = 7.0  # ground storey
FL = 3.8  # typical storeys
VIS = 2.95  # vision glass from the slab; spandrel band above it
GW = -0.05  # the glass plane behind the facet line
UNIT = 1.5  # curtain wall units
XL, CL = 5.9, 1.6  # the lobby, set back behind the columns
SOFFIT = G - 0.7  # under the first floor's edge band
DOOR = 2.7
PAR = 1.4  # the parapet
LANTERN = 16.0  # the lantern's height over the parapet
XT, CT = 2.0, 0.8  # the lantern's top
SPIRE = 22.0


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M.m)
    z = G
    for name, X, Xo in (("floor1", X1, None), ("sky2", X2, X1), ("floor2", X2, None), ("sky3", X3, X2), ("floor3", X3, None)):
        # Each piece at its own height, as stacked, so none shares a vertex with another.
        M.piece(name, (0, 0, z))
        storey(M.m, X, z, sky=Xo is not None)
        if Xo:
            terrace(M.m, Xo, X, z)
        z += FL
    M.piece("crown", (0, 0, z))
    crown(M.m, z)
    M.export(out, bake)


# ---- the octagon ---------------------------------------------------------------------


def octa(X, c, z=0.0):
    """The plan's corners anticlockwise from the front's left: long faces front
    (-y), right, back, left, a chamfer after each."""
    return [(-X + c, -X, z), (X - c, -X, z), (X, -X + c, z), (X, X - c, z), (X - c, X, z), (-X + c, X, z), (-X, X - c, z), (-X, -X + c, z)]


def facets(m, X, c):
    """Each face as a facade (u from -h to h seen from outside) with its half
    length and whether it is a chamfer."""
    P = octa(X, c)
    out = []
    for i in range(8):
        (x0, y0, _), (x1, y1, _) = P[i], P[(i + 1) % 8]
        L = math.hypot(x1 - x0, y1 - y0)
        t = ((x1 - x0) / L, (y1 - y0) / L, 0)
        F = Side(m, ((x0 + x1) / 2, (y0 + y1) / 2, 0), t, (t[1], -t[0], 0))
        out.append((F, L / 2, i % 2 == 1))
    return out


def plate(m, role, X, c, z, up):
    m.poly(role, octa(X, c, z), out=(0, 0, 1 if up else -1))


def skin(m, role, A, B, z0, z1, out=0.0):
    """The faces between octagon A = (X, c) at z0 and B at z1, `out` further out."""
    lo, hi = octa(A[0] + out, A[1], z0), octa(B[0] + out, B[1], z1)
    for i in range(8):
        j = (i + 1) % 8
        (x0, y0, _), (x1, y1, _) = lo[i], lo[j]
        m.poly(role, [lo[i], lo[j], hi[j], hi[i]], out=(y1 - y0, x0 - x1, 0))


def ring(m, role, A, B, z, up=True):
    """A flat ring between octagons A (outer) and B (inner)."""
    o, n = octa(*A, z), octa(*B, z)
    for i in range(8):
        j = (i + 1) % 8
        m.poly(role, [o[i], o[j], n[j], n[i]], out=(0, 0, 1 if up else -1))


def diagonal(m, i):
    """A frame on chamfer i's diagonal: u out from the tower's axis, w across."""
    sx = 1 if i in (1, 3) else -1
    sy = 1 if i in (3, 5) else -1
    d = (sx / math.sqrt(2), sy / math.sqrt(2), 0)
    return Side(m, (0, 0, 0), d, (-d[1], d[0], 0))


def reach(X, c):
    """How far a chamfer's middle is from the axis."""
    return (X - c / 2) * math.sqrt(2)


# ---- storeys --------------------------------------------------------------------------


def units(h):
    n = max(1, round(2 * h / UNIT))
    return [-h + 2 * h * k / n for k in range(n + 1)]


def storey(m, X, z, sky=False):
    """A typical storey: vision glass to the head, a spandrel to the next slab,
    mullions with fins; a sky storey has louvres in a recess instead."""
    for i, (F, h, chamfer) in enumerate(facets(m, X, C)):
        us = units(h)
        for a, b in zip(us, us[1:]):
            ga, gb = a + 0.035, b - 0.035
            if sky:
                F.quad("blades", ga, gb, z + 0.1, z + VIS, -0.3, uvs=[(0, 0), (gb - ga, 0), (gb - ga, VIS - 0.1), (0, VIS - 0.1)])
                F.box("mullion", ga, gb, z, z + 0.1, -0.3, GW, skip=("back", "bottom"))
                F.box("mullion", ga, gb, z + VIS, z + VIS + 0.05, -0.3, GW, skip=("back", "top"))
            else:
                pane(F, "officeglass", ga, gb, z, z + VIS, ga, gb, z + 0.03, z + VIS, GW, new_id())
        F.quad("spandrel", -h, h, z + VIS, z + FL, GW)
        F.box("mullion", -h, h, z + VIS - 0.03, z + VIS + 0.03, GW, 0.03)
        F.box("mullion", -h, h, z, z + 0.03, GW, 0.02)
        for k, u in enumerate(us):
            fin = 0.03 if k in (0, len(us) - 1) or chamfer else 0.16
            F.box("mullion", u - 0.035, u + 0.035, z, z + FL, GW - 0.03, fin)
        if sky:
            # The deep band at the head that hides the plant's outlets.
            F.box("mullion", -h, h, z + VIS + 0.05, z + VIS + 0.35, GW, 0.25, skip=("back",))
        if chamfer:
            sail(m, i, X, z, z + FL)
    # The slab's underside, seen only when the storey above is gone.
    plate(m, "dark", X - 0.1, C, z + FL - 0.02, False)


def sail(m, i, X, z0, z1, out=0.7):
    """Chamfer i's stainless fin, standing straight out of its middle."""
    D = diagonal(m, i)
    r = reach(X, C)
    D.box("stainless", r - 0.05, r + out, z0, z1, -0.035, 0.035, skip=("bottom", "top"))


def terrace(m, Xo, X, z):
    """Where a tier steps in: paving round it and a glass balustrade on the edge."""
    ring(m, "roof", (Xo, C), (X, C), z + 0.02)
    for F, h, _ in facets(m, Xo, C):
        F.quad("spandrel", -h, h, z, z + 1.1, -0.04)
        F.quad("panel", -h, h, z + 0.02, z + 1.1, -0.1, out=-F.n)
        F.box("mullion", -h, h, z + 1.1, z + 1.16, -0.12, 0.02, skip=("back",))


# ---- ground storey -----------------------------------------------------------------


def ground(m):
    c = 0.15
    # A granite plinth a step up from the plaza.
    plate(m, "granite", X1 + 0.3, C + 0.12, c, True)
    for F, h, _ in facets(m, X1 + 0.3, C + 0.12):
        F.quad("granite", -h, h, 0, c)
    # Columns at the corners and the middles of the sides (not the front's,
    # where the door is), stainless shoes.
    cols = [(x * (X1 - 0.6) / X1, y * (X1 - 0.6) / X1) for x, y, _ in octa(X1, C)]
    cols += [(X1 - 0.6, 0), (0, X1 - 0.6), (-X1 + 0.6, 0)]
    for x, y in cols:
        m.cyl("granite", x, y, 0.38, c, SOFFIT, seg=14, top=False)
        m.cyl("stainless", x, y, 0.4, c, c + 0.35, seg=14)
    lobby(m, c)
    # The soffit under the first floor, downlights, the floor's edge band.
    ring(m, "panel", (X1, C), (XL, CL), SOFFIT, up=False)
    skin(m, "mullion", (X1, C), (X1, C), SOFFIT, G)
    for x, y, _ in octa((X1 + XL) / 2, (C + CL) / 2):
        m.cyl("lamp", x, y, 0.08, SOFFIT - 0.02, SOFFIT, seg=10, top=False, bottom=True)
    canopy(m)
    revolving(m, 0, -XL, c, DOOR)
    plate(m, "dark", X1 - 0.1, C, G - 0.02, False)


def lobby(m, c):
    """Glass walls between posts on the front and sides; the back and its
    chamfers granite, the service door in the back."""
    for i, (F, h, chamfer) in enumerate(facets(m, XL, CL)):
        if i in (3, 4, 5):
            if i == 4:
                F.wall("granite", -h, h, c, SOFFIT, [(-0.6, 0.6, c, c + 2.3), (-2.6, -1.4, 3.2, 4.6)], depth=0.2)
                steel_door(F, -0.6, 0.6, c, c + 2.3, 0.2)
                F.box("lamp", -0.15, 0.15, c + 2.5, c + 2.62, 0, 0.12)
                F.quad("blades", -2.6, -1.4, 3.2, 4.6, -0.2, uvs=[(0, 0), (1.2, 0), (1.2, 1.4), (0, 1.4)])
            else:
                F.quad("granite", -h, h, c, SOFFIT)
            continue
        us = units(h)
        for a, b in zip(us, us[1:]):
            if i == 0 and a < 1.1 and b > -1.1:
                continue  # the revolving door
            wid = new_id()
            if i == 0 and abs((a + b) / 2) < 3.4:
                # Swing doors under a transom light, beside the revolving door.
                pane(F, "doorglass", a, b, c, SOFFIT, a + 0.03, b - 0.03, DOOR + 0.06, SOFFIT, -0.02, wid)
                F.box("mullion", a, b, DOOR, DOOR + 0.08, -0.04, 0.06)
                swing_door(F, a + 0.03, b - 0.03, c, DOOR, wid)
            else:
                pane(F, "doorglass", a, b, c, SOFFIT, a + 0.02, b - 0.02, c, SOFFIT, -0.02, wid)
                F.box("mullion", a, b, DOOR + 0.6, DOOR + 0.66, -0.03, 0.03, skip=())
        if i == 0:
            # Round the revolving door, which stands half out, and over it, the glass carries on.
            g = next(u for u in us if u > 1.1)
            wid = new_id()
            for a, b, e in ((-g, -1.12, DOOR + 0.3), (1.12, g, DOOR + 0.3), (-g, g, SOFFIT)):
                pane(F, "doorglass", -g, g, c, SOFFIT, a, b, c if e < SOFFIT else DOOR + 0.36, e, -0.02, wid)
            F.box("mullion", -g, g, DOOR + 0.3, DOOR + 0.36, -0.04, 0.04, skip=())
        for u in us:
            F.box("mullion", u - 0.03, u + 0.03, c, SOFFIT, -0.06, 0.06)
        F.box("mullion", -h, h, c, c + 0.08, -0.02, 0.05)


def canopy(m):
    """A thin steel canopy over the doors, cantilevered from the lobby; the name on its fascia."""
    x, y0, y1, z0, z1 = 3.6, -X1 - 0.1, -XL, 4.0, 4.45
    m.box("mullion", (-x, y0, z0 + 0.05), (x, y1, z1), skip=("z0", "y1"))
    m.poly("panel", [(-x, y0, z0 + 0.05), (x, y0, z0 + 0.05), (x, y1, z0 + 0.05), (-x, y1, z0 + 0.05)], out=-Z)
    F = Side(m, (0, y0, 0), (1, 0, 0), (0, -1, 0))
    F.quad("towername", -x + 0.2, x - 0.2, z0 + 0.1, z1 - 0.05, 0.005, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    for u in (-2.4, -0.8, 0.8, 2.4):
        m.cyl("lamp", u, (y0 + y1) / 2, 0.07, z0 + 0.03, z0 + 0.05, seg=10, top=False, bottom=True)


# ---- the crown -----------------------------------------------------------------------


def crown(m, z):
    # The parapet: the curtain wall carried on up, a panelled inside face, a coping.
    for i, (F, h, chamfer) in enumerate(facets(m, X3, C)):
        F.quad("spandrel", -h, h, z, z + PAR, GW)
        F.quad("panel", -h, h, z + 0.12, z + PAR, -0.3, out=-F.n)
        for u in units(h):
            F.box("mullion", u - 0.035, u + 0.035, z, z + PAR, GW - 0.03, 0.03 if chamfer else 0.16)
        F.box("mullion", -h, h, z + PAR, z + PAR + 0.06, -0.32, 0.06, skip=("back",))
        if chamfer:
            sail(m, i, X3, z, z + PAR)
    plate(m, "roof", X3 - 0.3, C, z + 0.12, True)
    lantern(m, z + PAR)


def at(k):
    """The lantern's plan k of the way up: (X, c)."""
    return (X3 - 0.3 + (XT - X3 + 0.3) * k, C + (CT - C) * k)


def lantern(m, z):
    """Faceted glass leaning in to a small top, lit bands round it every two
    metres, the sail fins sweeping up the corners to the spire."""
    top = z + LANTERN
    skin(m, "spandrel", at(0), at(1), z, top)
    n = 7
    for k in range(1, n + 1):
        f = k / (n + 0.5)
        zb = z + LANTERN * f
        lo, hi = at(f), at(f + 0.1 / LANTERN)
        skin(m, "halo", lo, hi, zb, zb + 0.1, out=0.06)
        ring(m, "halo", (lo[0] + 0.06, lo[1]), lo, zb, up=False)
        ring(m, "halo", (hi[0] + 0.06, hi[1]), hi, zb + 0.1)
    ring(m, "halo", (XT + 0.3, CT), (XT, CT), top)
    skin(m, "halo", (XT + 0.3, CT), (XT + 0.3, CT), top - 0.3, top)
    ring(m, "halo", (XT + 0.3, CT), (XT, CT), top - 0.3, up=False)
    plate(m, "roof", XT, CT, top, True)
    # The sails: from the parapet up the chamfers, tapering to the top.
    r0, r1 = reach(*at(0)) + 0.3, reach(XT, CT)
    for i in (1, 3, 5, 7):
        D = diagonal(m, i)
        pts = [(r0 - 0.05, z), (r0 + 0.7, z), (r1 + 0.5, top + 2.5), (r1 - 0.05, top + 1.0)]
        for w in (-0.035, 0.035):
            fpoly(D, "stainless", pts, w=w, out=D.n if w > 0 else -D.n)
        for (u0, z0), (u1, z1) in zip(pts[1:], pts[2:] + pts[:1]):
            nn = (z1 - z0, -(u1 - u0))
            m.poly("stainless", [D.p(u0, z0, -0.035), D.p(u1, z1, -0.035), D.p(u1, z1, 0.035), D.p(u0, z0, 0.035)], out=tuple(D.t * nn[0] + Z * nn[1]))
    # A stainless drum and the spire, collars on it, the aircraft light.
    m.cyl("stainless", 0, 0, 1.1, top, top + 2.6, seg=8, r1=0.7)
    s0 = top + 2.6
    m.cyl("stainless", 0, 0, 0.45, s0, s0 + SPIRE, seg=8, r1=0.04)
    for hh, r in ((0.0, 0.55), (4.0, 0.46), (9.0, 0.34)):
        m.cyl("mullion", 0, 0, r, s0 + hh, s0 + hh + 0.2, seg=8, bottom=True)
    m.cyl("beacon", 0, 0, 0.08, s0 + SPIRE - 0.1, s0 + SPIRE + 0.2, seg=8)
