# L14, telecommunications tower: a late-twentieth-century concrete needle on
# one 16 m lot, not an office tower. A heavy granite and concrete podium holds
# the glazed public entrance, a cantilevered canopy with the tower's name,
# louvred plant rooms and a separate service door. Eight buttresses carry the
# sixteen-sided shaft, whose vertical ribs and ladder run through repeated
# construction collars. At the top a flared, ribbed basket opens into a broad
# antenna deck around a three-storey glazed observation and broadcast drum.
# Stainless roof walks, open guardrails, equipment louvres and sector aerials
# surround a square lattice mast, painted in red and white bands, with aircraft
# warning lights and a slender finial. The app picks the glass, metal and name.
#
# Each shaft module tapers between identical collars: the deliberate reveal at
# every four metres hides the radius reset, so the same piece stacks cleanly at
# any floor count. The deck occupies one four-metre transition storey; the
# crown, including its mast, rises 20 m above it.
#
# Pieces (base at the origin, stacked by the app):
#   ground  6.0 m: entrance podium, canopy and name, plant, shaft buttresses
#   shaft   4.0 m: repeatable tapered concrete module, ribs and access ladder
#   deck    4.0 m: flared transition, equipment skirt and observation balcony
#   crown  20.0 m: three glazed storeys, roof deck, aerials and lattice mast
import math

from lib import Model, Side, Z, new_id, pane
from o2_round import steel_door, swing_door

ID = "l14"
N = 16  # shaft, drum and deck facets
G = 6.0
FL = 4.0

POD_X = 6.3  # podium body, before its plinth
POD_FRONT = -3.9
POD_BACK = 5.9
CANOPY_FRONT = -7.2  # footprint runs from here to the plinth's back at 6.4
PLINTH_X = 6.8

SR0, SR1 = 2.58, 2.38  # shaft concrete between the 2.68 m collars
COLLAR = 2.68
DRUM = 5.15  # observation drum's corner radius
DECK = 5.95  # balcony and roof edge; 11.9 m across
STOREY = 3.0  # three storeys in the observation drum
MAST0, MAST1 = 11.5, 18.2  # local to the crown
CROWN_H = 20.0


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M.m)
    M.piece("shaft", (0, 0, G))
    shaft(M.m, G)
    M.piece("deck", (0, 0, G + FL))
    deck(M.m, G + FL)
    M.piece("crown", (0, 0, G + 2 * FL))
    crown(M.m, G + 2 * FL)
    M.export(out, bake)


# ---- the sixteen-sided plans -------------------------------------------------------


def ang(i):
    """Joint i's angle: joint zero faces front, counting anticlockwise."""
    return -math.pi / 2 + i * math.tau / N


def at(r, a, z):
    return (r * math.cos(a), r * math.sin(a), z)


def facet(m, i, r):
    """Facet i as a facade, u running from joint i to joint i + 1."""
    a = ang(i) + math.pi / N
    ap = r * math.cos(math.pi / N)
    F = Side(m, (ap * math.cos(a), ap * math.sin(a), 0), (-math.sin(a), math.cos(a), 0), (math.cos(a), math.sin(a), 0))
    return F, r * math.sin(math.pi / N)


def joint(m, i, r):
    a = ang(i)
    return Side(m, at(r, a, 0), (-math.sin(a), math.cos(a), 0), (math.cos(a), math.sin(a), 0))


def disc(m, role, r, z, up=1):
    m.poly(role, [at(r, ang(i), z) for i in range(N)], out=(0, 0, up))


def ring(m, role, r0, r1, z0, z1, edge=None, inner=False):
    """A flat annulus with thickness and an outer (and optionally inner) edge."""
    for i in range(N):
        a, b = ang(i), ang(i + 1)
        c = (a + b) / 2
        out = (math.cos(c), math.sin(c), 0)
        m.poly(role, [at(r0, a, z1), at(r0, b, z1), at(r1, b, z1), at(r1, a, z1)], out=Z)
        m.poly(role, [at(r0, a, z0), at(r0, b, z0), at(r1, b, z0), at(r1, a, z0)], out=-Z)
        m.poly(edge or role, [at(r1, a, z0), at(r1, b, z0), at(r1, b, z1), at(r1, a, z1)], out=out)
        if inner:
            m.poly(role, [at(r0, a, z0), at(r0, b, z0), at(r0, b, z1), at(r0, a, z1)], out=(-out[0], -out[1], 0))


def guardrail(m, r, z, h=1.08):
    """Open stainless rail: joint posts and two continuous round rails."""
    for i in range(N):
        a = ang(i)
        m.strut("stainless", at(r, a, z), at(r, a, z + h), 0.045)
    for zz in (z + 0.48, z + h):
        m.tube("stainless", [at(r, ang(i), zz) for i in range(N)], 0.025, Z, seg=6)


# ---- ground podium -----------------------------------------------------------------


def vent(F, a, b, z0=1.1, z1=2.75):
    F.quad("blades", a, b, z0, z1, 0.015, uvs=[(0, 0), (b - a, 0), (b - a, z1 - z0), (0, z1 - z0)])
    for u0, u1, c, e in ((a - 0.06, a, z0 - 0.06, z1 + 0.06), (b, b + 0.06, z0 - 0.06, z1 + 0.06), (a, b, z0 - 0.06, z0), (a, b, z1, z1 + 0.06)):
        F.box("mullion", u0, u1, c, e, 0, 0.07, skip=("back",))


def entrance(m):
    """A small glazed vestibule in the otherwise solid plant podium."""
    F = Side(m, (0, -5.82, 0), (1, 0, 0), (0, -1, 0))
    wid = new_id()
    # Fixed lights beside the double doors and the transom above them.
    for a, b in ((-2.9, -1.22), (1.22, 2.9)):
        pane(F, "doorglass", -3, 3, 0.25, 3.35, a, b, 0.3, 3.3, -0.02, wid)
    pane(F, "doorglass", -3, 3, 0.25, 3.35, -1.15, 1.15, 2.86, 3.3, -0.02, wid)
    for a, b in ((-1.15, -0.025), (0.025, 1.15)):
        swing_door(F, a, b, 0.25, 2.76, wid)
    for u in (-3, -1.18, 0, 1.18, 3):
        F.box("mullion", u - 0.035, u + 0.035, 0.25, 3.4, -0.06, 0.06)
    for z0, z1 in ((0.25, 0.32), (2.78, 2.86), (3.32, 3.4)):
        F.box("mullion", -3, 3, z0, z1, -0.06, 0.06)
    # Glass returns to the solid podium, one room id on each side.
    for sx in (-1, 1):
        S = Side(m, (sx * 3, -4.85, 0), (0, sx, 0), (sx, 0, 0))
        wid = new_id()
        pane(S, "doorglass", -0.95, 0.95, 0.25, 3.35, -0.9, 0.9, 0.3, 3.3, -0.02, wid)
        for u in (-0.95, 0.95):
            S.box("mullion", u - 0.035, u + 0.035, 0.25, 3.4, -0.06, 0.06)
        for z0, z1 in ((0.25, 0.32), (3.32, 3.4)):
            S.box("mullion", -0.95, 0.95, z0, z1, -0.06, 0.06)
    # Two broad granite steps, entirely inside the plinth and canopy.
    m.box("granite", (-3.35, -6.48, 0), (3.35, -5.75, 0.13), skip=("z0",))
    m.box("granite", (-3.2, -6.15, 0.13), (3.2, -5.75, 0.25), skip=("z0",))


def canopy(m):
    x0, x1 = -3.8, 3.8
    m.box("mullion", (x0, CANOPY_FRONT, 3.5), (x1, -3.82, 3.84), skip=("z0", "y1"))
    m.poly("panel", [(x0, CANOPY_FRONT, 3.49), (x1, CANOPY_FRONT, 3.49), (x1, -3.82, 3.49), (x0, -3.82, 3.49)], out=-Z)
    F = Side(m, (0, CANOPY_FRONT - 0.006, 0), (1, 0, 0), (0, -1, 0))
    F.quad("towername", -3.55, 3.55, 3.55, 3.79, 0, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    for x in (-2.6, -0.85, 0.85, 2.6):
        m.cyl("lamp", x, -6.35, 0.075, 3.47, 3.49, seg=10, top=False, bottom=True)
    for sx in (-1, 1):
        # The ties land on the shaft's spreading foot, not in mid-air.
        m.strut("stainless", (sx * 3.5, CANOPY_FRONT + 0.18, 3.84), (sx * 1.65, -2.32, 5.25), 0.055)


def ground(m):
    # A wide, low plinth and a solid service podium establish the heavy base.
    m.box("granite", (-PLINTH_X, -6.1, 0), (PLINTH_X, 6.4, 0.25), skip=("z0",))
    m.box("concrete", (-POD_X, POD_FRONT, 0.25), (POD_X, POD_BACK, 3.86), skip=("z0",))
    m.box("granite", (-POD_X - 0.02, POD_FRONT - 0.02, 0.25), (POD_X + 0.02, POD_BACK + 0.02, 0.65), skip=("z0",))
    m.box("roof", (-POD_X, POD_FRONT, 3.86), (POD_X, POD_BACK, 3.98), skip=("z0",))
    entrance(m)
    canopy(m)

    # Intake louvres between precast panel joints on both plant-room walls.
    for sx in (-1, 1):
        F = Side(m, (sx * (POD_X + 0.012), 1.0, 0), (0, sx, 0), (sx, 0, 0))
        for a, b in ((-3.55, -1.75), (-0.85, 0.95), (1.85, 3.65)):
            vent(F, a, b)
        for u in (-4.3, -1.25, 1.45, 4.35):
            F.box("dark", u - 0.012, u + 0.012, 0.68, 3.72, 0.004, 0.014, skip=("back",))
        F.box("dark", -4.65, 4.65, 3.18, 3.205, 0.004, 0.014, skip=("back",))

    # The rear service entrance and its two ventilation bays.
    B = Side(m, (0, POD_BACK + 0.012, 0), (-1, 0, 0), (0, 1, 0))
    steel_door(B, -0.65, 0.65, 0.25, 2.65, 0.0)
    B.box("lamp", -0.17, 0.17, 2.85, 2.98, 0, 0.14, skip=("back",))
    B.box("granite", -0.85, 0.85, 0.13, 0.25, 0, 0.5, skip=("back", "bottom"))
    for a, b in ((-4.85, -3.05), (2.15, 3.95)):
        vent(B, a, b)

    # Small roof plant units, down at podium scale rather than office floors.
    for sx in (-1, 1):
        x = sx * 4.55
        m.box("blades", (x - 0.7, 2.8, 3.98), (x + 0.7, 4.25, 4.55), skip=("z0",))
        m.cyl("dark", x, 3.52, 0.43, 4.55, 4.57, seg=16)
        m.box("mullion", (x - 0.74, 2.76, 4.48), (x + 0.74, 4.29, 4.58), skip=("z0",))

    # The shaft starts on a spreading foot, with eight structural buttresses.
    m.cyl("concrete", 0, 0, 3.08, 3.98, G, seg=N, top=False, uv=True, r1=COLLAR)
    m.cyl("granite", 0, 0, 3.24, 3.96, 4.1, seg=N, top=False)
    for i in range(0, N, 2):
        a = ang(i)
        m.strut("concrete", at(4.25, a, 3.99), at(2.79, a, 5.77), 0.34, 0.24)
        m.strut("concrete", at(3.13, a, 4.05), at(2.7, a, 5.96), 0.18)
    disc(m, "dark", COLLAR, G - 0.015, -1)


# ---- repeatable shaft and observation transition -----------------------------------


def shaft(m, z):
    # Identical end collars conceal the module's taper reset at every joint.
    ring(m, "concrete", 2.24, COLLAR, z, z + 0.14, inner=True)
    ring(m, "concrete", 2.18, COLLAR, z + 3.76, z + FL, inner=True)
    m.cyl("concrete", 0, 0, SR0, z + 0.12, z + 3.8, seg=N, top=False, uv=True, r1=SR1)
    for i in range(0, N, 2):
        a = ang(i)
        m.strut("concrete", at(2.63, a, z + 0.14), at(2.43, a, z + 3.78), 0.16)
    # Dark gasket lines make the repeated collars read as construction joints.
    for zz in (z + 0.14, z + 3.72):
        m.cyl("dark", 0, 0, COLLAR + 0.006, zz, zz + 0.035, seg=N, top=False)

    # A fixed-radius ladder continues exactly from one repeated piece to the next.
    for side in (-1, 1):
        x = -side * 0.23
        m.strut("stainless", (x, 2.91, z), (x, 2.91, z + FL), 0.038)
    for k in range(10):
        zz = z + 0.24 + k * 0.38
        m.strut("stainless", (0.23, 2.91, zz), (-0.23, 2.91, zz), 0.03)
    for zz in (z + 0.45, z + 2.0, z + 3.55):
        for side in (-1, 1):
            x = -side * 0.23
            m.strut("stainless", (x, 2.5, zz), (x, 2.91, zz), 0.035)
    disc(m, "dark", 2.25, z + FL - 0.015, -1)


def deck(m, z):
    ring(m, "concrete", 2.18, COLLAR, z, z + 0.16, inner=True)
    m.cyl("concrete", 0, 0, SR0, z + 0.12, z + 3.12, seg=N, top=False, uv=True, r1=4.68)
    # Sixteen ribs express the cantilever instead of a smooth office-tower cone.
    for i in range(N):
        a = ang(i)
        m.strut("concrete", at(2.73, a, z + 0.18), at(4.92, a, z + 3.35), 0.2)
        if i % 2 == 0:
            m.strut("stainless", at(2.86, a, z + 0.4), at(4.96, a, z + 3.3), 0.055)
    m.cyl("blades", 0, 0, 4.7, z + 3.1, z + 3.72, seg=N, top=False, uv=True, r1=DRUM)
    ring(m, "roof", 4.62, DECK, z + 3.7, z + 3.94, edge="stainless", inner=True)
    # Alternating red and off-white fascia panels are the first warning band.
    for i in range(N):
        F, h = facet(m, i, DECK)
        F.quad("redpanel" if i % 2 == 0 else "panel", -h + 0.03, h - 0.03, z + 3.73, z + 3.91, 0.012)
        a = ang(i) + math.pi / N
        if i % 2 == 0:
            x, y, _ = at(4.35, a, 0)
            m.cyl("lamp", x, y, 0.085, z + 3.06, z + 3.1, seg=10, top=False, bottom=True)
    # The drum stands inside this maintenance balcony in the crown piece.
    guardrail(m, DECK - 0.12, z + 3.96)


# ---- observation drum, antenna decks and mast ---------------------------------------


def drum(m, z):
    for level in range(3):
        base = z + level * STOREY
        for i in range(N):
            F, h = facet(m, i, DRUM)
            a, b = -h + 0.045, h - 0.045
            F.quad("spandrel", a, b, base + 0.06, base + 0.53, -0.045)
            F.quad("spandrel", a, b, base + 2.68, base + 2.98, -0.045)
            pane(F, "officeglass", a, b, base + 0.5, base + 2.72, a + 0.015, b - 0.015, base + 0.58, base + 2.63, -0.06, new_id())
            for zz in (base + 0.51, base + 2.69):
                F.box("mullion", a, b, zz - 0.035, zz + 0.035, -0.09, 0.035)
            F.box("mullion", -0.025, 0.025, base + 0.52, base + 2.68, -0.095, 0.025)
            J = joint(m, i, DRUM)
            J.box("mullion", -0.04, 0.04, base, base + STOREY, -0.1, 0.08)
            J.box("mullion", -0.025, 0.025, base + 0.06, base + 2.98, 0.08, 0.18)
        ring(m, "mullion", DRUM - 0.12, DRUM + 0.14, base, base + 0.12)
    disc(m, "dark", DRUM - 0.15, z + 3 * STOREY - 0.02, -1)


def sector_aerials(m, z):
    """Six cellular/broadcast panels on outriggers around the lattice."""
    for k in range(6):
        a = k * math.tau / 6
        d = (math.cos(a), math.sin(a), 0)
        F = Side(m, at(1.5, a, 0), (-math.sin(a), math.cos(a), 0), d)
        F.box("panel", -0.25, 0.25, z + 12.25, z + 14.55, -0.11, 0.11, skip=("back",))
        for u in (-0.27, 0.27):
            F.box("stainless", u - 0.025, u + 0.025, z + 12.2, z + 14.6, -0.13, 0.13)
        for zz in (12.2, 14.55):
            F.box("stainless", -0.27, 0.27, z + zz, z + zz + 0.05, -0.13, 0.13)
        F.box("dark", -0.14, 0.14, z + 12.65, z + 13.15, -0.19, -0.11)
        for zz in (12.6, 14.15):
            m.strut("stainless", at(0.62, a, z + zz), at(1.43, a, z + zz), 0.055)


def lattice(m, z):
    levels = 5
    for k in range(levels):
        z0 = z + MAST0 + (MAST1 - MAST0) * k / levels
        z1 = z + MAST0 + (MAST1 - MAST0) * (k + 1) / levels
        w0 = 0.88 + (0.28 - 0.88) * k / levels
        w1 = 0.88 + (0.28 - 0.88) * (k + 1) / levels
        lo = [(-w0, -w0, z0), (w0, -w0, z0), (w0, w0, z0), (-w0, w0, z0)]
        hi = [(-w1, -w1, z1), (w1, -w1, z1), (w1, w1, z1), (-w1, w1, z1)]
        role = "redpanel" if k % 2 == 0 else "panel"
        for i in range(4):
            j = (i + 1) % 4
            m.strut(role, lo[i], hi[i], 0.105)
            m.strut(role, lo[i], lo[j], 0.065)
            m.strut("stainless", lo[i], hi[j], 0.05)
            m.strut("stainless", lo[j], hi[i], 0.05)
            if k == levels - 1:
                m.strut(role, hi[i], hi[j], 0.06)
    # Intermediate obstruction lights and the red/white finial.
    for sx, sy in ((-1, -1), (1, 1)):
        m.cyl("beacon", sx * 0.49, sy * 0.49, 0.075, z + 14.78, z + 14.98, seg=8)
    m.cyl("panel", 0, 0, 0.13, z + MAST1, z + 18.75, seg=8, r1=0.105)
    m.cyl("redpanel", 0, 0, 0.105, z + 18.75, z + 19.3, seg=8, r1=0.075)
    m.cyl("panel", 0, 0, 0.075, z + 19.3, z + 19.76, seg=8, r1=0.045)
    m.cyl("beacon", 0, 0, 0.085, z + 19.74, z + CROWN_H, seg=10)


def crown(m, z):
    # The geometry helpers use absolute reference heights; mast constants are
    # crown-local, so the whole upper assembly is translated as one group.
    drum(m, z)
    disc(m, "roof", DECK, z + 9.12, 1)
    ring(m, "stainless", DRUM - 0.1, DECK, z + 8.98, z + 9.15, inner=True)
    guardrail(m, DECK - 0.14, z + 9.16)

    # Louvred broadcast equipment drum and its stainless antenna platform.
    m.cyl("blades", 0, 0, 2.65, z + 9.14, z + 11.32, seg=N, top=False, uv=True)
    m.cyl("mullion", 0, 0, 2.82, z + 9.12, z + 9.3, seg=N, top=False)
    ring(m, "stainless", 0.72, 2.88, z + 11.28, z + 11.5, inner=True)
    for i in range(0, N, 2):
        F, h = facet(m, i, 2.67)
        F.box("mullion", -0.035, 0.035, z + 9.28, z + 11.28, 0, 0.08)

    # Four low equipment cabinets and dark fan grilles on the outer roof.
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x, y = sx * 3.55, sy * 2.1
        m.box("panel", (x - 0.58, y - 0.42, z + 9.15), (x + 0.58, y + 0.42, z + 9.78), skip=("z0",))
        m.cyl("dark", x, y, 0.29, z + 9.78, z + 9.8, seg=14)
        m.box("mullion", (x - 0.61, y - 0.45, z + 9.72), (x + 0.61, y + 0.45, z + 9.81), skip=("z0",))

    sector_aerials(m, z)
    lattice(m, z)
