# L4, twisting tower: a contemporary residential tower on a chamfered
# square, each storey turned a little further than the one below. Eight
# curtain-wall facets alternate long glazed faces and stainless corner
# sails; the turning floor edges draw the helix up the whole building. The
# double-height lobby stands back behind granite columns, with a revolving
# door between swing doors and a cantilevered name canopy. One plant storey
# interrupts the glass with louvres. At the top a faceted glass lantern
# leans in to a steel drum and a slender spire, the corner sails sweeping
# up beside it. The app turns each repeated storey and the crown, tints the
# glass and metalwork, and picks the name.
#
# Pieces (base at the origin, stacked and turned by the app):
#   ground  6.0 m: plinth, columns, lobby, canopy with the name
#   floor   3.8 m: a typical chamfered-square storey
#   plant   3.8 m: the same floor with louvres behind a deep band
#   crown   parapet, the faceted lantern, sails and spire
import math

from lib import Model, Side, Z, fpoly, new_id, pane
from l2_supertall import diagonal, facets, octa, plate, reach, ring, skin
from o2_round import revolving, steel_door, swing_door

ID = "l4"
X, C = 6.4, 1.8
XL, CL = 5.15, 1.25
G = 6.0
FL = 3.8
VIS = 3.05
GW = -0.05
SOFFIT = 5.45
LANTERN = 7.0
XT, CT = 2.35, 0.65
CROWN = 12.2


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M.m)
    M.piece("floor", (0, 0, G))
    storey(M.m, G)
    M.piece("plant", (0, 0, G + FL))
    storey(M.m, G + FL, plant=True)
    M.piece("crown", (0, 0, G + 2 * FL))
    crown(M.m, G + 2 * FL)
    M.export(out, bake)


def units(h):
    n = max(1, round(2 * h / 1.35))
    return [-h + 2 * h * k / n for k in range(n + 1)]


def storey(m, z, plant=False):
    """One repeatable storey. The renderer turns it about the tower's axis."""
    for F, h, chamfer in facets(m, X, C):
        us = units(h)
        for a, b in zip(us, us[1:]):
            ga, gb = a + 0.035, b - 0.035
            F.quad("spandrel", ga, gb, z, z + 0.24, GW)
            F.quad("spandrel", ga, gb, z + VIS, z + FL - 0.12, GW)
            if plant:
                F.quad("blades", ga, gb, z + 0.24, z + VIS, -0.28, uvs=[(0, 0), (gb - ga, 0), (gb - ga, VIS - 0.24), (0, VIS - 0.24)])
            else:
                pane(F, "officeglass", ga, gb, z, z + VIS, ga, gb, z + 0.27, z + VIS - 0.03, GW - 0.01, new_id())
            for zz in (0.24, VIS):
                F.box("mullion", ga, gb, z + zz - 0.025, z + zz + 0.025, GW, 0.035)
        for u in us:
            F.box("mullion", u - 0.032, u + 0.032, z, z + FL, GW - 0.025, 0.06 if not chamfer else 0.14)
        F.box("mullion", -h, h, z, z + 0.035, GW, 0.04)
        if chamfer:
            # A broad sail at each cut corner makes the turning shaft legible.
            F.box("stainless", -0.045, 0.045, z, z + FL, 0.02, 0.48, skip=("back", "top", "bottom"))
    skin(m, "mullion", (X, C), (X, C), z + FL - 0.16, z + FL, out=0.16)
    if plant:
        skin(m, "blades", (X, C), (X, C), z + VIS - 0.05, z + VIS + 0.32, out=0.32)
    plate(m, "dark", X - 0.1, C, z + FL - 0.02, False)


def ground(m):
    c = 0.15
    plate(m, "granite", X + 0.25, C + 0.1, c, True)
    for F, h, _ in facets(m, X + 0.25, C + 0.1):
        F.quad("granite", -h, h, 0, c)
    # Granite columns just inside the turning tower's first floor edge.
    for x, y, _ in octa(X - 0.45, C):
        m.cyl("granite", x * 0.93, y * 0.93, 0.3, c, SOFFIT, seg=12, top=False)
        m.cyl("stainless", x * 0.93, y * 0.93, 0.33, c, c + 0.3, seg=12)
    lobby(m, c)
    ring(m, "panel", (X, C), (XL, CL), SOFFIT, up=False)
    skin(m, "mullion", (X, C), (X, C), SOFFIT, G)
    for x, y, _ in octa((X + XL) / 2, (C + CL) / 2):
        m.cyl("lamp", x, y, 0.075, SOFFIT - 0.02, SOFFIT, seg=10, top=False, bottom=True)
    canopy(m)
    revolving(m, 0, -XL, c, 2.75)
    plate(m, "dark", X - 0.1, C, G - 0.02, False)


def lobby(m, c):
    for i, (F, h, _) in enumerate(facets(m, XL, CL)):
        if i in (3, 4, 5):
            if i == 4:
                F.wall("granite", -h, h, c, SOFFIT, [(-0.6, 0.6, c, c + 2.35), (-2.2, -1.1, 3.0, 4.3)], depth=0.2)
                steel_door(F, -0.6, 0.6, c, c + 2.35, 0.2)
                F.box("lamp", -0.15, 0.15, c + 2.52, c + 2.64, 0, 0.12)
                F.quad("blades", -2.2, -1.1, 3.0, 4.3, -0.2, uvs=[(0, 0), (1.1, 0), (1.1, 1.3), (0, 1.3)])
            else:
                F.quad("granite", -h, h, c, SOFFIT)
            continue
        us = units(h)
        for a, b in zip(us, us[1:]):
            wid = new_id()
            if i == 0 and abs((a + b) / 2) < 2.7:
                pane(F, "doorglass", a, b, c, SOFFIT, a + 0.025, b - 0.025, 2.82, SOFFIT, -0.02, wid)
                F.box("mullion", a, b, 2.75, 2.83, -0.04, 0.05)
                if abs((a + b) / 2) > 1.0:
                    swing_door(F, a + 0.03, b - 0.03, c, 2.75, wid)
            else:
                pane(F, "doorglass", a, b, c, SOFFIT, a + 0.025, b - 0.025, c, SOFFIT, -0.02, wid)
            F.box("mullion", a, b, c, c + 0.07, -0.02, 0.05)
        for u in us:
            F.box("mullion", u - 0.03, u + 0.03, c, SOFFIT, -0.05, 0.05)


def canopy(m):
    F = Side(m, (0, -X - 0.25, 0), (1, 0, 0), (0, -1, 0))
    m.box("mullion", (-3.5, -X - 0.25, 3.65), (3.5, -XL + 0.1, 4.05), skip=("z0", "y1"))
    m.poly("panel", [(-3.5, -X - 0.25, 3.65), (3.5, -X - 0.25, 3.65), (3.5, -XL + 0.1, 3.65), (-3.5, -XL + 0.1, 3.65)], out=-Z)
    F.quad("towername", -3.25, 3.25, 3.72, 3.98, 0.005, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    for u in (-2.4, -0.8, 0.8, 2.4):
        m.cyl("lamp", u, (-X - 0.25 - XL) / 2, 0.07, 3.63, 3.65, seg=10, top=False, bottom=True)
    for sx in (-1, 1):
        m.strut("stainless", (sx * 3.15, -X - 0.1, 4.02), (sx * 2.4, -XL, SOFFIT), 0.045)


def crown(m, z):
    for F, h, chamfer in facets(m, X, C):
        F.quad("spandrel", -h, h, z, z + 1.0, GW)
        F.quad("panel", -h, h, z + 0.1, z + 1.0, -0.28, out=-F.n)
        F.box("mullion", -h, h, z + 1.0, z + 1.08, -0.3, 0.05, skip=("back",))
        if chamfer:
            F.box("stainless", -0.045, 0.045, z, z + 1.05, 0.02, 0.48, skip=("back", "top", "bottom"))
    plate(m, "roof", X - 0.25, C, z + 0.1, True)
    lantern(m, z + 1.0)


def at(k):
    return (X - 0.25 + (XT - X + 0.25) * k, C + (CT - C) * k)


def lantern(m, z):
    top = z + LANTERN
    skin(m, "spandrel", at(0), at(1), z, top)
    # Lit rings articulate the leaning glass drum without hiding its facets.
    for k in range(1, 6):
        f = k / 6
        lo, hi = at(f), at(f + 0.018)
        skin(m, "halo", lo, hi, z + LANTERN * f, z + LANTERN * f + 0.1, out=0.055)
    ring(m, "halo", (XT + 0.28, CT), (XT, CT), top)
    skin(m, "halo", (XT + 0.28, CT), (XT + 0.28, CT), top - 0.25, top)
    plate(m, "roof", XT, CT, top, True)
    # Four broad sails sweep from the roof's chamfers to the lantern's top.
    r0, r1 = reach(*at(0)) + 0.18, reach(XT, CT)
    for i in (1, 3, 5, 7):
        D = diagonal(m, i)
        pts = [(r0 - 0.04, z), (r0 + 0.5, z), (r1 + 0.38, top + 1.5), (r1 - 0.04, top + 0.75)]
        for w in (-0.035, 0.035):
            fpoly(D, "stainless", pts, w=w, out=D.n if w > 0 else -D.n)
        for (u0, z0), (u1, z1) in zip(pts[1:], pts[2:] + pts[:1]):
            nn = (z1 - z0, -(u1 - u0))
            m.poly("stainless", [D.p(u0, z0, -0.035), D.p(u1, z1, -0.035), D.p(u1, z1, 0.035), D.p(u0, z0, 0.035)], out=tuple(D.t * nn[0] + Z * nn[1]))
    m.cyl("stainless", 0, 0, 0.8, top, top + 1.7, seg=8, r1=0.5)
    m.cyl("stainless", 0, 0, 0.28, top + 1.7, top + 3.85, seg=8, r1=0.045)
    m.cyl("mullion", 0, 0, 0.38, top + 2.1, top + 2.25, seg=8, bottom=True)
    m.cyl("beacon", 0, 0, 0.075, top + 3.85, top + 4.05, seg=8)
