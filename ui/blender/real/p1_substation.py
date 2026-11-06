# P1, electrical substation: what a hamlet gets when the line comes over the
# hill. A fenced gravel compound behind steel palisade: the incoming line
# lands on a wooden H-pole at the back, spans to a lattice gantry and drops
# through disc insulators onto the bushings of a pole-mounted-size
# distribution transformer (a tank with radiator banks either side, a
# conservator on brackets, three porcelain bushings, a cable box) standing
# on a plinth in an oil bund. Cable trench covers run to a brick switch
# house with louvred steel doors, barred vents and a bulkhead lamp; the low
# voltage side rises up a riser pipe on a wooden pole by the gate and goes
# out along the street on a crossarm. Danger signs on the fence and gates.
#
# Pieces (base at the origin):
#   body  the compound, fence, transformer, gantry, poles, the switch
#         house's walls to the eaves (3.0 m)
#   roof  the switch house's concrete roof slab, coping and vent
import math

from mathutils import Vector

from civic import chamfer_box, rod
from lib import Model, Z, grille, sides

ID = "p1"
W, D = 14.0, 12.0  # the fence line
HW, HD = W / 2, D / 2
KERB = 0.15  # the fence's concrete kerb above the yard
YARD = 0.06  # gravel over the ground
FENCE = 2.2  # palisade height
GATE = (0.6, 4.6)  # the gate opening in the front fence, x
# Switch house, back left.
SH = (-6.4, -2.2, 1.6, 5.4)  # x0, x1, y0, y1
EAVES = 3.0
# Transformer, centre.
TX, TY = 1.9, 0.4
PLINTH = 0.35
TANK = (2.4, 1.3, 2.1)  # x, y, height above the plinth
GANTRY_Y = 3.9
GANTRY_X = (-0.6, 4.4)
GANTRY_H = 7.0
PHASES = [TX - 1.0, TX, TX + 1.0]
H_POLE_Y = 5.35  # the incoming line's H-pole, just inside the back fence
LV_POLE = (6.25, -5.25)  # the outgoing pole, inside the front right corner


def build(out, bake=True):
    M = Model(ID, seed=13)
    M.sharp = math.radians(40)
    M.piece("body")
    yard(M)
    fence(M)
    switch_house(M)
    transformer(M)
    gantry(M)
    poles(M)
    M.piece("roof", (0, 0, EAVES))
    roof(M)
    M.export(out, bake)


# ---- the compound ---------------------------------------------------------------------


def yard(M):
    m = M.m
    # Gravel inside the kerb, a concrete apron inside the gate.
    m.poly("gravel", [(-HW + 0.15, -HD + 0.15, YARD), (HW - 0.15, -HD + 0.15, YARD), (HW - 0.15, HD - 0.15, YARD), (-HW + 0.15, HD - 0.15, YARD)], out=Z)
    m.box("concrete", (GATE[0] - 0.2, -HD + 0.15, YARD), (GATE[1] + 0.2, -HD + 2.6, YARD + 0.04), skip=("z0",))
    # The fence's kerb, all round.
    for lo, hi in (((-HW, -HD, 0), (HW, -HD + 0.3, KERB)), ((-HW, HD - 0.3, 0), (HW, HD, KERB)),
                   ((-HW, -HD + 0.3, 0), (-HW + 0.3, HD - 0.3, KERB)), ((HW - 0.3, -HD + 0.3, 0), (HW, HD - 0.3, KERB))):
        if lo[1] == -HD:
            # Broken at the gate, where the apron runs out to the street.
            m.box("concrete", lo, (GATE[0], hi[1], hi[2]), skip=("z0",))
            m.box("concrete", (GATE[1], lo[1], lo[2]), hi, skip=("z0",))
        else:
            m.box("concrete", lo, hi, skip=("z0",))
    # Cable trench covers: transformer to switch house, and out to the low voltage pole.
    trench(m, (TX - TANK[0] / 2 - 0.9, TY + 0.2), (SH[1] + 0.1, TY + 0.2))
    trench(m, (SH[1] - 0.6, TY + 0.2), (SH[1] - 0.6, SH[2] - 0.1))
    trench(m, (TX + TANK[0] / 2 + 0.9, TY - 0.3), (LV_POLE[0] - 0.3, TY - 0.3))
    trench(m, (LV_POLE[0] - 0.3, TY - 0.3), (LV_POLE[0] - 0.3, LV_POLE[1] + 0.5))


def trench(m, a, b):
    """Precast covers 0.6 m wide from a to b along x or y, in slabs with a gap between."""
    (x0, y0), (x1, y1) = a, b
    along_x = abs(x1 - x0) > abs(y1 - y0)
    L = abs(x1 - x0) if along_x else abs(y1 - y0)
    n = max(1, round(L / 0.9))
    step = L / n
    for i in range(n):
        s0, s1 = i * step + 0.02, (i + 1) * step - 0.02
        if along_x:
            u0, u1 = min(x0, x1) + s0, min(x0, x1) + s1
            m.box("concrete", (u0, y0 - 0.3, YARD), (u1, y0 + 0.3, YARD + 0.07), skip=("z0",))
            m.box("iron", ((u0 + u1) / 2 - 0.1, y0 - 0.02, YARD + 0.07), ((u0 + u1) / 2 + 0.1, y0 + 0.02, YARD + 0.085), skip=("z0",))
        else:
            v0, v1 = min(y0, y1) + s0, min(y0, y1) + s1
            m.box("concrete", (x0 - 0.3, v0, YARD), (x0 + 0.3, v1, YARD + 0.07), skip=("z0",))
            m.box("iron", (x0 - 0.02, (v0 + v1) / 2 - 0.1, YARD + 0.07), (x0 + 0.02, (v0 + v1) / 2 + 0.1, YARD + 0.085), skip=("z0",))


# ---- the palisade ---------------------------------------------------------------------


def palisade(m, a, b, out, z0=KERB, h=FENCE, posts=True):
    """Steel palisade from a to b (x, y): W-section pales with triple-pointed
    heads on two angle rails, a post every 2.75 m. `out` is the outside."""
    a, b = Vector((*a, 0)), Vector((*b, 0))
    t = (b - a).normalized()
    n = Vector((*out, 0)).normalized()
    L = (b - a).length
    p = lambda u, z, w: a + t * u + Z * z + n * w  # noqa: E731

    def bar(role, u0, u1, z0_, z1_, w0, w1):
        lo, hi = p(u0, z0_, w0), p(u1, z1_, w1)
        m.box(role, tuple(min(lo[i], hi[i]) for i in range(3)), tuple(max(lo[i], hi[i]) for i in range(3)))

    # Rails on the inside of the pales.
    for zr in (z0 + 0.35, z0 + h - 0.45):
        bar("galv", 0, L, zr, zr + 0.06, -0.09, -0.03)
    if posts:
        k = max(1, round(L / 2.75))
        for i in range(k + 1):
            u = min(L - 0.05, max(0.05, i * L / k))
            bar("galv", u - 0.05, u + 0.05, 0, z0 + h - 0.15, -0.15, -0.05)
    k = int(L / 0.2)
    pitch = L / k
    for i in range(k):
        u = (i + 0.5) * pitch
        u0, u1 = u - 0.03, u + 0.03
        top = z0 + h - 0.12
        bar("galv", u0, u1, z0, top, -0.03, 0.0)
        # The head: a point in the middle and one at each edge.
        for c in (u0, u, u1):
            s = 0.022
            m.poly("galv", [p(c - s, top, 0.0), p(c + s, top, 0.0), p(c, top + 0.12, 0.0)], out=n)
            m.poly("galv", [p(c - s, top, -0.03), p(c + s, top, -0.03), p(c, top + 0.12, -0.03)], out=-n)


def fence(M):
    m = M.m
    i = 0.05  # the pales' face, in from the kerb's edge
    palisade(m, (-HW + i, -HD + i), (GATE[0], -HD + i), (0, -1))
    palisade(m, (GATE[1], -HD + i), (HW - i, -HD + i), (0, -1))
    palisade(m, (HW - i, -HD + i), (HW - i, HD - i), (1, 0))
    palisade(m, (HW - i, HD - i), (-HW + i, HD - i), (0, 1))
    palisade(m, (-HW + i, HD - i), (-HW + i, -HD + i), (-1, 0))
    # Double gates, shut, on heavy posts; the padlocked chain and a sign on each leaf.
    mid = (GATE[0] + GATE[1]) / 2
    for x0, x1 in ((GATE[0] + 0.12, mid - 0.02), (mid + 0.02, GATE[1] - 0.12)):
        palisade(m, (x0, -HD + i), (x1, -HD + i), (0, -1), z0=YARD + 0.04, h=FENCE + KERB - 0.1, posts=False)
        for zz in (0.5, FENCE - 0.4):
            m.box("galv", (x0, -HD + i + 0.03, zz), (x1, -HD + i + 0.09, zz + 0.07))
        m.strut("galv", (x0 + 0.05, -HD + i + 0.06, 0.55), (x1 - 0.05, -HD + i + 0.06, FENCE - 0.4), 0.05)
        danger(m, (x0 + x1) / 2, -HD + i - 0.01, 1.45, (0, -1))
    for x in (GATE[0], GATE[1]):
        m.box("galv", (x - 0.12, -HD - 0.07, 0), (x + 0.12, -HD + 0.17, FENCE + KERB + 0.05))
        m.box("galv", (x - 0.14, -HD - 0.09, FENCE + KERB + 0.05), (x + 0.14, -HD + 0.19, FENCE + KERB + 0.09))
    m.box("iron", (mid - 0.09, -HD - 0.03, 1.15), (mid + 0.09, -HD + 0.0, 1.3))
    # Signs on the other three sides.
    danger(m, HW + 0.01, 0.0, 1.5, (1, 0))
    danger(m, -HW - 0.01, -2.0, 1.5, (-1, 0))
    danger(m, 2.0, HD + 0.01, 1.5, (0, 1))
    danger(m, -4.0, -HD - 0.01, 1.5, (0, -1))


def danger(m, x, y, z, out):
    """A yellow enamel sign, 0.4 x 0.5 m: a black triangle with a lightning flash."""
    n = Vector((*out, 0))
    t = Vector((-n.y, n.x, 0))
    c = Vector((x, y, z))
    p = lambda u, v, w=0.0: c + t * u + Z * v + n * w  # noqa: E731
    m.poly("danger", [p(-0.2, -0.25, 0.005), p(0.2, -0.25, 0.005), p(0.2, 0.25, 0.005), p(-0.2, 0.25, 0.005)], out=n)
    m.poly("danger", [p(-0.2, -0.25, -0.005), p(0.2, -0.25, -0.005), p(0.2, 0.25, -0.005), p(-0.2, 0.25, -0.005)], out=-n)
    w = 0.008
    m.poly("iron", [p(-0.15, -0.02, w), p(0.15, -0.02, w), p(0.0, 0.22, w)], out=n)
    m.poly("danger", [p(-0.11, 0.0, w + 0.001), p(0.11, 0.0, w + 0.001), p(0.0, 0.175, w + 0.001)], out=n)
    m.poly("iron", [p(0.02, 0.16, w + 0.002), p(-0.04, 0.07, w + 0.002), p(0.0, 0.07, w + 0.002)], out=n)
    m.poly("iron", [p(0.0, 0.07, w + 0.002), p(0.03, 0.07, w + 0.002), p(-0.02, 0.015, w + 0.002)], out=n)
    # The black band beneath, where DANGER would be lettered.
    m.poly("iron", [p(-0.17, -0.2, w), p(0.17, -0.2, w), p(0.17, -0.08, w), p(-0.17, -0.08, w)], out=n)


# ---- the switch house -----------------------------------------------------------------


def switch_house(M):
    m = M.m
    x0, x1, y0, y1 = SH
    w, d = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    m.sweep("concrete", w, d, [(0.06, 0.0), (0.06, 0.3), (0.0, 0.3)], cx=cx, cy=cy)
    walls = sides(m, w, d, cx, cy)
    hw, hd = w / 2, d / 2
    # Front: a pair of louvred steel doors under a concrete lintel; a bulkhead lamp.
    F = walls["front"]
    da, db, de = -0.95, 0.95, 2.35
    F.wall("brick", -hw, hw, 0.3, EAVES, [(da, db, 0.3, de)], depth=0.25, reveal="concrete")
    for a, b in ((da + 0.04, -0.01), (0.01, db - 0.04)):
        F.quad("subdoor", a, b, 0.32, de - 0.04, -0.18)
        F.box("subframe", a, b, 0.32, 0.4, -0.18, -0.16)
        F.box("subframe", a, b, de - 0.12, de - 0.04, -0.18, -0.16)
    F.box("subframe", da, db, de - 0.04, de, -0.25, -0.16)
    F.box("iron", -0.08, -0.02, 1.0, 1.3, -0.16, -0.12)
    F.box("iron", 0.02, 0.08, 1.0, 1.3, -0.16, -0.12)
    F.box("concrete", da - 0.2, db + 0.2, de, de + 0.22, 0, 0.04)
    F.box("concrete", da - 0.1, db + 0.1, 0.0, 0.32, 0, 0.5, skip=("back",))
    F.box("iron", db + 0.3, db + 0.48, 2.45, 2.7, 0, 0.12)
    F.box("lamp", db + 0.32, db + 0.46, 2.47, 2.68, 0.12, 0.15, skip=("back",))
    danger(m, cx + da - 0.55, y0 - 0.01, 1.6, (0, -1))
    # A name plate: the substation's number, white on blue.
    F.box("plate", 1.35, 1.8, 2.0, 2.25, 0, 0.012)
    # Sides: a high barred vent each; the back blank but for a low vent.
    for name in ("right", "left"):
        S = walls[name]
        h = hd
        vents = [(-0.6, 0.6, 2.0, 2.6)]
        S.wall("brick", -h, h, 0.3, EAVES, vents, depth=0.25, reveal="concrete")
        for a, b, c, e in vents:
            S.quad("subdoor", a, b, c, e, -0.15)
            grille(S, a, b, c, e)
            S.box("concrete", a - 0.08, b + 0.08, c - 0.06, c, 0, 0.05)
    B = walls["back"]
    B.wall("brick", -hw, hw, 0.3, EAVES, [(-0.4, 0.4, 0.45, 0.75)], depth=0.25, reveal="concrete")
    B.quad("subdoor", -0.4, 0.4, 0.45, 0.75, -0.12)
    # Ceiling seen when the roof is gone.
    m.poly("dark", [(x0, y0, EAVES - 0.02), (x1, y0, EAVES - 0.02), (x1, y1, EAVES - 0.02), (x0, y1, EAVES - 0.02)], out=-Z)


def roof(M):
    m = M.m
    x0, x1, y0, y1 = SH
    o = 0.3
    # A precast slab oversailing the walls, a drip under its edge, felt on top.
    m.box("concrete", (x0 - o, y0 - o, EAVES), (x1 + o, y1 + o, EAVES + 0.2))
    m.box("concrete", (x0 - o + 0.04, y0 - o + 0.04, EAVES - 0.03), (x1 + o - 0.04, y1 + o - 0.04, EAVES))
    m.box("roof", (x0 - o + 0.08, y0 - o + 0.08, EAVES + 0.2), (x1 + o - 0.08, y1 + o - 0.08, EAVES + 0.24), skip=("z0",))
    # A mushroom vent and a gutter spout at the back.
    vx, vy = (x0 + x1) / 2 + 0.6, (y0 + y1) / 2 + 0.5
    m.cyl("galv", vx, vy, 0.1, EAVES + 0.24, EAVES + 0.6, seg=10)
    m.cyl("galv", vx, vy, 0.22, EAVES + 0.6, EAVES + 0.66, seg=12, bottom=True)
    m.cyl("galv", vx, vy, 0.12, EAVES + 0.66, EAVES + 0.74, seg=12, r1=0.02)
    m.box("galv", (x1 - 0.5, y1 + o - 0.05, EAVES + 0.12), (x1 - 0.4, y1 + o + 0.25, EAVES + 0.2))


# ---- the transformer ------------------------------------------------------------------


def transformer(M):
    m = M.m
    tw, td, th = TANK
    # The bund: a low wall round a sump, the plinth in it.
    bw, bd = tw + 2.2, td + 2.4
    bx0, bx1, by0, by1 = TX - bw / 2, TX + bw / 2, TY - bd / 2, TY + bd / 2
    for lo, hi in (((bx0, by0, 0), (bx1, by0 + 0.2, 0.4)), ((bx0, by1 - 0.2, 0), (bx1, by1, 0.4)),
                   ((bx0, by0 + 0.2, 0), (bx0 + 0.2, by1 - 0.2, 0.4)), ((bx1 - 0.2, by0 + 0.2, 0), (bx1, by1 - 0.2, 0.4))):
        m.box("concrete", lo, hi, skip=("z0",))
    m.poly("gravel", [(bx0 + 0.2, by0 + 0.2, 0.12), (bx1 - 0.2, by0 + 0.2, 0.12), (bx1 - 0.2, by1 - 0.2, 0.12), (bx0 + 0.2, by1 - 0.2, 0.12)], out=Z)
    chamfer_box(m, "concrete", (TX - tw / 2 - 0.3, TY - td / 2 - 0.25, 0.1), (TX + tw / 2 + 0.3, TY + td / 2 + 0.25, PLINTH), 0.04)
    # Skid rails, the tank on them, its lid with a lip.
    z0 = PLINTH
    for dy in (-td / 2 + 0.15, td / 2 - 0.15):
        m.box("trafo", (TX - tw / 2 - 0.1, TY + dy - 0.07, z0), (TX + tw / 2 + 0.1, TY + dy + 0.07, z0 + 0.15))
    zt = z0 + 0.15
    chamfer_box(m, "trafo", (TX - tw / 2, TY - td / 2, zt), (TX + tw / 2, TY + td / 2, zt + th), 0.05)
    m.box("trafo", (TX - tw / 2 - 0.06, TY - td / 2 - 0.06, zt + th - 0.08), (TX + tw / 2 + 0.06, TY + td / 2 + 0.06, zt + th))
    lid = zt + th
    m.box("trafo", (TX - tw / 2 + 0.05, TY - td / 2 + 0.05, lid), (TX + tw / 2 - 0.05, TY + td / 2 - 0.05, lid + 0.06))
    lid += 0.06
    # Stiffening ribs up the ends, lifting lugs at the corners.
    for sx in (-1, 1):
        for dy in (-0.35, 0.35):
            m.box("trafo", (TX + sx * tw / 2 - (0.0 if sx > 0 else 0.08), TY + dy - 0.03, zt + 0.1), (TX + sx * tw / 2 + (0.08 if sx > 0 else 0.0), TY + dy + 0.03, zt + th - 0.1))
        for sy in (-1, 1):
            m.box("trafo", (TX + sx * (tw / 2 - 0.15) - 0.04, TY + sy * (td / 2 + 0.02) - 0.03, lid - 0.25), (TX + sx * (tw / 2 - 0.15) + 0.04, TY + sy * (td / 2 + 0.02) + 0.03, lid + 0.08))
    # Radiator banks on both long sides: pressed-steel fins between headers.
    for sy in (-1, 1):
        face = TY + sy * td / 2
        za, zb = zt + 0.3, zt + th - 0.3
        for hz in (za, zb):
            rod(m, "trafo", (TX - tw / 2 + 0.2, face + sy * 0.08, hz), (TX + tw / 2 - 0.2, face + sy * 0.08, hz), 0.06, seg=8)
            for x in (TX - tw / 2 + 0.25, TX + tw / 2 - 0.25):
                rod(m, "trafo", (x, face, hz), (x, face + sy * 0.12, hz), 0.05, seg=8, caps=False)
        n = 16
        for i in range(n):
            x = TX - tw / 2 + 0.3 + i * (tw - 0.6) / (n - 1)
            y0_, y1_ = sorted((face + sy * 0.12, face + sy * 0.6))
            m.box("trafo", (x - 0.012, y0_, za - 0.08), (x + 0.012, y1_, zb + 0.08))
    # The conservator: a drum on two brackets over the lid at one end, its pipe and breather.
    cz = lid + 0.75
    cx0, cx1 = TX - tw / 2 + 0.05, TX + 0.35
    cy = TY + td / 2 - 0.2
    rod(m, "trafo", (cx0, cy, cz), (cx1, cy, cz), 0.24, seg=14)
    for x in (cx0 + 0.25, cx1 - 0.25):
        m.box("trafo", (x - 0.04, cy - 0.18, lid), (x + 0.04, cy + 0.18, cz - 0.2))
    rod(m, "trafo", (cx1 - 0.05, cy, cz - 0.15), (cx1 + 0.3, cy - 0.15, lid), 0.035, seg=6)
    m.cyl("glass", cx0 + 0.15, cy - 0.3, 0.05, lid - 0.9, lid - 0.6, seg=8, bottom=True)
    rod(m, "trafo", (cx0 + 0.15, cy - 0.3, lid - 0.6), (cx0 + 0.15, cy - 0.2, cz - 0.1), 0.02, seg=6)
    # High voltage bushings: three porcelain stacks, galvanised caps and arcing horns.
    for x in PHASES:
        y = TY - 0.15
        bushing(m, x, y, lid, 1.0, 0.075, 0.15)
    # Low voltage bushings along the front, into a cable box.
    for i in range(4):
        x = TX + 0.5 + i * 0.22
        bushing(m, x, TY - td / 2 + 0.2, lid, 0.35, 0.04, 0.075, sheds=3)
    m.box("trafo", (TX + tw / 2, TY - 0.45, zt + 0.5), (TX + tw / 2 + 0.45, TY + 0.25, zt + 1.4))
    m.box("trafo", (TX + tw / 2 + 0.45, TY - 0.47, zt + 0.48), (TX + tw / 2 + 0.47, TY + 0.27, zt + 1.42))
    rod(m, "iron", (TX + tw / 2 + 0.22, TY - 0.1, zt + 0.5), (TX + tw / 2 + 0.22, TY - 0.1, YARD), 0.07, seg=8)
    # The rating plate, the gauge and the tap changer's handle on the front.
    front = TY - td / 2
    m.box("plate", (TX - 0.85, front - 0.012, zt + 1.1), (TX - 0.45, front, zt + 1.35))
    m.cyl("iron", TX - 0.15, front - 0.03, 0.09, zt + 1.5, zt + 1.53, seg=12)
    m.box("iron", (TX - 0.05, front - 0.05, zt + 0.9), (TX + 0.05, front, zt + 1.0))
    # Earth tape down a corner to the plinth.
    m.box("copper", (TX - tw / 2 - 0.02, TY - td / 2 + 0.05, PLINTH), (TX - tw / 2 + 0.0, TY - td / 2 + 0.09, zt + th - 0.1))


def bushing(m, x, y, z, h, r, shed, sheds=None):
    """A porcelain bushing from z up h: a core with sheds, a cap and a stud."""
    m.cyl("trafo", x, y, r + 0.05, z, z + 0.06, seg=10)
    m.cyl("porcelain", x, y, r, z + 0.06, z + h, seg=10)
    k = sheds or max(3, int(h / 0.11))
    for i in range(k):
        zz = z + 0.12 + i * (h - 0.16) / k
        m.cyl("porcelain", x, y, shed, zz, zz + 0.025, seg=12, bottom=True, r1=shed * 0.8)
    m.cyl("galv", x, y, r * 0.9, z + h, z + h + 0.08, seg=10)
    m.cyl("galv", x, y, 0.018, z + h + 0.08, z + h + 0.2, seg=6)


# ---- the gantry and the lines ---------------------------------------------------------


def lattice_column(m, x, y, h, s=0.45):
    """A square lattice column of four angles with zigzag bracing on each face."""
    hs = s / 2
    c = [(x - hs, y - hs), (x + hs, y - hs), (x + hs, y + hs), (x - hs, y + hs)]
    for cx, cy in c:
        m.strut("galv", (cx, cy, 0.25), (cx, cy, h), 0.06)
    m.box("concrete", (x - hs - 0.2, y - hs - 0.2, 0), (x + hs + 0.2, y + hs + 0.2, 0.3))
    k = int((h - 0.4) / s)
    step = (h - 0.4) / k
    for i in range(4):
        (ax, ay), (bx, by) = c[i], c[(i + 1) % 4]
        for j in range(k):
            z0, z1 = 0.35 + j * step, 0.35 + (j + 1) * step
            p0, p1 = ((ax, ay), (bx, by)) if j % 2 == 0 else ((bx, by), (ax, ay))
            m.strut("galv", (p0[0], p0[1], z0), (p1[0], p1[1], z1), 0.035)
        m.strut("galv", (ax, ay, h - 0.02), (bx, by, h - 0.02), 0.05)


def string(m, x, y, z, n=4, horizontal=None):
    """Disc insulators: hanging down from z, or along the vector `horizontal` from (x, y, z). Returns the far end."""
    p = Vector((x, y, z))
    d = Vector(horizontal).normalized() if horizontal else Vector((0, 0, -1))
    rod(m, "galv", p, p + d * 0.12, 0.015, seg=6)
    for i in range(n):
        c = p + d * (0.18 + i * 0.15)
        if horizontal:
            rod(m, "porcelain", c - d * 0.02, c + d * 0.02, 0.12, seg=12)
        else:
            m.cyl("porcelain", c.x, c.y, 0.12, c.z - 0.02, c.z + 0.02, seg=12, bottom=True, r1=0.04)
        rod(m, "galv", c, c + d * 0.15, 0.02, seg=6, caps=False)
    end = p + d * (0.18 + n * 0.15)
    return end


def gantry(M):
    m = M.m
    x0, x1 = GANTRY_X
    for x in (x0, x1):
        lattice_column(m, x, GANTRY_Y, GANTRY_H)
    # A lattice beam across the top: two chords each side and diagonals.
    zb, zt = GANTRY_H - 0.55, GANTRY_H
    for dy in (-0.2, 0.2):
        for z in (zb, zt):
            m.strut("galv", (x0, GANTRY_Y + dy, z), (x1, GANTRY_Y + dy, z), 0.06)
        k = 10
        for i in range(k):
            a = x0 + i * (x1 - x0) / k
            b = x0 + (i + 1) * (x1 - x0) / k
            za, zc = (zb, zt) if i % 2 == 0 else (zt, zb)
            m.strut("galv", (a, GANTRY_Y + dy, za), (b, GANTRY_Y + dy, zc), 0.035)
    for i in range(6):
        x = x0 + i * (x1 - x0) / 5
        m.strut("galv", (x, GANTRY_Y - 0.2, zb), (x, GANTRY_Y + 0.2, zb), 0.04)
    # The line comes in from the H-pole on strain strings and drops through
    # suspension strings to the bushings.
    for x in PHASES:
        far = string(m, x, GANTRY_Y + 0.25, zb + 0.1, n=4, horizontal=(0, 1, 0))
        pole_end = Vector((x, H_POLE_Y - 0.25, 7.95))
        sag(m, far, pole_end, 0.25)
        drop = string(m, x, GANTRY_Y - 0.2, zb, n=4)
        bush = Vector((x, TY - 0.15, PLINTH + 0.15 + TANK[2] + 0.06 + 1.2))
        mid = (drop + bush) / 2 + Vector((0, -0.25, 0))
        rod(m, "line", drop, mid, 0.014, seg=5)
        rod(m, "line", mid, bush, 0.014, seg=5)
        rod(m, "line", drop, far, 0.014, seg=5)


def sag(m, a, b, dip, n=6):
    """A conductor from a to b hanging in a shallow curve."""
    pts = []
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t)
        p.z -= dip * 4 * t * (1 - t)
        pts.append(p)
    for p, q in zip(pts, pts[1:]):
        rod(m, "line", p, q, 0.014, seg=5, caps=False)


def wood_pole(m, x, y, h, r0=0.15, r1=0.11):
    m.cyl("pole", x, y, r0, 0, h, seg=10, r1=r1)
    m.cyl("pole", x, y, r1 + 0.01, h, h + 0.04, seg=10, r1=0.02)


def poles(M):
    m = M.m
    # The incoming H-pole: two poles, a crossarm with three pin insulators and the strain strings' clamps, a cross brace.
    y = H_POLE_Y
    a, b = PHASES[0] - 0.9, PHASES[-1] + 0.9
    for x in (a, b):
        wood_pole(m, x, y, 8.6)
    m.box("pole", (a - 0.25, y - 0.07, 8.0), (b + 0.25, y + 0.07, 8.18))
    m.strut("galv", (a, y - 0.12, 3.2), (b, y - 0.12, 6.4), 0.05)
    m.strut("galv", (b, y - 0.12, 3.2), (a, y - 0.12, 6.4), 0.05)
    for x in PHASES:
        m.box("galv", (x - 0.06, y - 0.25, 7.9), (x + 0.06, y - 0.07, 8.0))
        bushing(m, x, y, 8.18, 0.3, 0.05, 0.11, sheds=2)
        # The line goes on over the hill: a short run out past the fence, falling away.
        rod(m, "line", Vector((x, y, 8.45)), Vector((x, y + 0.8, 8.2)), 0.014, seg=5)
    # Stay wires to the corners of the yard.
    for x in (a, b):
        rod(m, "galv", (x, y, 7.6), (x + (-1.6 if x == a else 1.6), y + 0.3, KERB), 0.012, seg=4)
    # The outgoing low voltage pole by the gate: a riser pipe up from the trench, a fuse box, a crossarm and four pins.
    px, py = LV_POLE
    wood_pole(m, px, py, 8.2)
    rod(m, "galv", (px - 0.2, py, YARD), (px - 0.2, py, 4.2), 0.05, seg=8)
    m.box("trafo", (px - 0.38, py - 0.12, 2.6), (px - 0.16, py + 0.12, 3.1))
    m.box("pole", (px - 0.9, py - 0.06, 7.6), (px + 0.9, py + 0.06, 7.75))
    for i, dx in enumerate((-0.75, -0.3, 0.3, 0.75)):
        bushing(m, px + dx, py, 7.75, 0.16, 0.03, 0.06, sheds=2)
        rod(m, "line", (px - 0.2, py, 4.2 + 0.05 * i), (px + dx, py, 7.9), 0.012, seg=4)
        # Out along the street, a span cut off where the next pole would take it.
        rod(m, "line", (px + dx, py, 7.92), (px + dx, py - 1.2, 7.8), 0.012, seg=4)
    m.box("plate", (px - 0.1, py - 0.16, 3.5), (px + 0.1, py - 0.15, 3.8))
    # A floodlight on the gantry for night work.
    gx = GANTRY_X[0]
    m.box("iron", (gx - 0.15, GANTRY_Y - 0.5, 5.2), (gx + 0.15, GANTRY_Y - 0.25, 5.45))
    m.box("lamp", (gx - 0.12, GANTRY_Y - 0.52, 5.23), (gx + 0.12, GANTRY_Y - 0.5, 5.42), skip=("y1",))
