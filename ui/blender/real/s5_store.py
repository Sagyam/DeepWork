# S5, department store: a downtown store of about 1910 on a 14 m frontage.
# The street front is limestone, five bays between piers, each upper bay
# a Chicago window (a wide fixed light between two narrow sashes) in bronze
# over a sunk spandrel. The ground storey is all display: bronze
# shopfronts on polished black granite stallrisers, prism-glass transoms
# above them, and in the middle bay a deep vestibule with double doors. A
# steel canopy on tie rods runs across the front, carrying the store's name
# and lamps under it. The sides and back are brick: a party wall on the
# left, windows on the right, the loading door and the staff door at the
# back. On top an attic band, a deep cornice on modillions, a parapet with
# a raised centre and a clock in it, and on the roof a timber water tank on
# steel legs. The app tints the stone, brick, metalwork and cornice per
# building and picks the name.
#
# Pieces (base at the origin, stacked by the app):
#   ground  5.2 m: displays, entrance, canopy with the name, loading door
#   floor   4.0 m: a sales floor, one to three of them
#   roof    attic, cornice, parapet and clock, the roof and its tank
import math

from lib import Model, Side, Z, lintel, new_id, pane, sash, sides, sill
from s4_factory import annulus, disc

ID = "s5"
W, D = 14.0, 12.0
HW, HD = W / 2, D / 2
G = 5.2
FL = 4.0
PIERS = [-6.7, -4.2, -1.4, 1.4, 4.2, 6.7]  # pier centres on the front
PW = 0.6
PO = 0.12  # how far the piers stand proud
DISPLAY = 3.5  # display windows' head; prism transoms above
CAN0, CAN1, CAND = 3.55, 4.05, 1.9  # canopy underside, top, depth


def build(out, bake=True):
    M = Model(ID, seed=5)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    storey(M.m, G)
    top = G + FL
    M.piece("roof", (0, 0, top))
    roof(M, top)
    M.export(out, bake)


def bays():
    return [(a + PW / 2, b - PW / 2) for a, b in zip(PIERS, PIERS[1:])]


def piers(F, z0, z1, role="cladstone"):
    for u in PIERS:
        a, b = max(-HW, u - PW / 2), min(HW, u + PW / 2)
        F.box(role, a, b, z0, z1, 0, PO, skip=("back",))


def ceiling(m, z):
    m.poly("dark", [(-HW, -HD, z), (HW, -HD, z), (HW, HD, z), (-HW, HD, z)], out=-Z)


# ---- ground storey --------------------------------------------------------------------


def ground(M):
    m = M.m
    S = sides(m, W, D)
    F = S["front"]
    holes = [(a, b, 0.0, G - 0.75, 1.3 if i == 2 else 0.25) for i, (a, b) in enumerate(bays())]
    F.wall("cladstone", -HW, HW, 0, G, holes, reveal="jet")
    for i, (a, b) in enumerate(bays()):
        if i == 2:
            entrance(m, F, a, b)
        else:
            display(F, a, b)
    # The piers: polished granite bases, stone above.
    for u in PIERS:
        a, b = max(-HW, u - PW / 2), min(HW, u + PW / 2)
        F.box("jet", a - 0.03, b + 0.03, 0, 0.7, 0, PO + 0.03, skip=("back", "bottom"))
        F.box("cladstone", a, b, 0.7, G, 0, PO, skip=("back",))
    # A band over the ground storey.
    F.box("cladstone", -HW, HW, G - 0.45, G - 0.3, 0, PO + 0.1, skip=())
    canopy(m, F)
    # The right side: one display at the front corner, the rest brick.
    R = S["right"]
    R.wall("brick", -HD, HD, 0, G, [(-HD + 0.6, -HD + 3.2, 0.6, DISPLAY, 0.25), (1.5, 3.0, 2.2, 3.8)], depth=0.3, reveal="stone")
    display(R, -HD + 0.6, -HD + 3.2, rise=False)
    sash(R, 1.5, 3.0, 2.2, 3.8, D=0.3, lights=(2, 2))
    sill(R, 1.5, 3.0, 2.2, D=0.3)
    lintel(R, 1.5, 3.0, 3.8, key_=False)
    S["left"].quad("brick", -HD, HD, 0, G)
    back(S["back"])
    ceiling(m, G - 0.02)


def display(F, a, b, rise=True):
    """A display window: a granite stallriser, bronze frame, a prism-glass transom above."""
    D_ = 0.25
    F.box("jet", a, b, 0, 0.6, -D_, -D_ + 0.1, skip=("back",))
    wid = new_id()
    pane(F, "shopglass", a, b, 0.6, DISPLAY, a + 0.08, b - 0.08, 0.66, DISPLAY - 0.06, -D_ + 0.04, wid)
    for box in ((a, a + 0.08, 0.6, DISPLAY), (b - 0.08, b, 0.6, DISPLAY), (a, b, 0.6, 0.66), (a, b, DISPLAY - 0.06, DISPLAY + 0.06)):
        F.box("bronze", *box, -D_, -D_ + 0.08)
    if rise:
        top = G - 0.75
        pane(F, "shopglass", a, b, DISPLAY + 0.06, top, a + 0.06, b - 0.06, DISPLAY + 0.06, top - 0.06, -D_ + 0.04, new_id())
        n = max(2, round((b - a) / 0.4))
        for k in range(1, n):
            u = a + (b - a) * k / n
            F.box("bronze", u - 0.015, u + 0.015, DISPLAY + 0.06, top, -D_ + 0.02, -D_ + 0.07)
        F.box("bronze", a, b, top - 0.06, top, -D_, -D_ + 0.08)


def entrance(m, F, a, b):
    """The middle bay: a vestibule 1.3 m deep, a mosaic floor, double doors in bronze under a transom."""
    D_ = 1.3
    top = G - 0.75
    F.box("granite", a, b, 0, 0.06, -D_, 0, skip=("back", "bottom"))
    wid = new_id()
    door = 2.6
    for u0, u1 in ((a + 0.1, (a + b) / 2), ((a + b) / 2, b - 0.1)):
        pane(F, "doorglass", a, b, 0.06, top, u0 + 0.07, u1 - 0.07, 0.3, door - 0.07, -D_ + 0.03, wid)
        for box in ((u0, u0 + 0.07, 0.06, door), (u1 - 0.07, u1, 0.06, door), (u0, u1, 0.06, 0.3), (u0, u1, door - 0.07, door)):
            F.box("bronze", *box, -D_, -D_ + 0.06)
        h = u1 - 0.18 if u0 < a + 0.2 else u0 + 0.14
        F.box("brass", h, h + 0.04, 1.0, 1.6, -D_ + 0.06, -D_ + 0.12, skip=())
    F.box("bronze", a, a + 0.1, 0.06, top, -D_, -D_ + 0.08)
    F.box("bronze", b - 0.1, b, 0.06, top, -D_, -D_ + 0.08)
    F.box("bronze", a, b, door, door + 0.12, -D_, -D_ + 0.08)
    pane(F, "doorglass", a, b, 0.06, top, a + 0.1, b - 0.1, door + 0.12, top, -D_ + 0.03, wid)
    m.poly("panel", [F.p(a, top, 0), F.p(b, top, 0), F.p(b, top, -D_), F.p(a, top, -D_)], out=-Z)


def canopy(m, F):
    """A steel canopy across the front on tie rods: lamps under it, the name on the fascia."""
    a, b = -HW + 0.6, HW - 0.6
    F.box("bronze", a, b, CAN0, CAN1, PO, PO + CAND, skip=("back",))
    F.quad("towername", -4.2, 4.2, CAN0 + 0.05, CAN1 - 0.03, PO + CAND + 0.005, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    for u in (-5.0, -2.5, 0.0, 2.5, 5.0):
        F.box("lamp", u - 0.12, u + 0.12, CAN0 - 0.04, CAN0, PO + 0.7, PO + 0.95, skip=("top",))
    for u in (-4.2, 4.2):
        m.strut("iron", F.p(u, CAN1, PO + CAND - 0.15), F.p(u, G - 0.5, PO), 0.05)
        F.box("bronze", u - 0.12, u + 0.12, G - 0.65, G - 0.4, PO, PO + 0.08, skip=("back",))


def back(F):
    """The loading door with a roller shutter under a steel beam, the staff door, a downpipe."""
    F.wall("brick", -HW, HW, 0, G, [(-4.5, -1.3, 0, 3.6, 0.3), (1.6, 2.6, 0, 2.4, 0.25)], depth=0.3, reveal="concrete")
    F.quad("roller", -4.5, -1.3, 0, 3.6, -0.25, uvs=[(0, 0), (3.2, 0), (3.2, 3.6), (0, 3.6)])
    F.box("steel", -4.8, -1.0, 3.6, 3.9, 0, 0.12, skip=("back",))
    for u in (-4.7, -1.1):
        F.box("steel", u - 0.1, u + 0.1, 0, 1.0, 0, 0.2, skip=("back", "bottom"))
    F.quad("door", 1.65, 2.55, 0, 2.35, -0.2)
    F.box("iron", 2.35, 2.45, 1.0, 1.06, -0.2, -0.14, skip=("back",))
    F.box("lamp", 2.0, 2.2, 2.6, 2.75, 0, 0.12, skip=("back",))
    F.box("gutter", 5.5, 5.6, 0, G, 0.03, 0.13, skip=("back",))


# ---- sales floors ----------------------------------------------------------------------


def chicago(F, a, b, c, e, D_=0.25):
    """A Chicago window: a wide fixed light between two narrow sashes, bronze frames."""
    s = (b - a) * 0.22
    pane(F, "shopglass", a, b, c, e, a + s + 0.05, b - s - 0.05, c + 0.06, e - 0.06, -D_ + 0.05, new_id())
    for box in ((a, a + 0.06, c, e), (b - 0.06, b, c, e), (a, b, c, c + 0.08), (a, b, e - 0.06, e), (a + s - 0.05, a + s + 0.05, c, e), (b - s - 0.05, b - s + 0.05, c, e)):
        F.box("bronze", *box, -D_, -D_ + 0.08)
    for u0, u1 in ((a + 0.06, a + s - 0.05), (b - s + 0.05, b - 0.06)):
        wid = new_id()
        mid = (c + e) / 2
        for z0, z1, w in ((c + 0.08, mid + 0.03, -D_ + 0.02), (mid - 0.03, e - 0.06, -D_ + 0.06)):
            pane(F, "shopglass", a, b, c, e, u0 + 0.04, u1 - 0.04, z0 + 0.04, z1 - 0.04, w, wid)
            for box in ((u0, u0 + 0.04, z0, z1), (u1 - 0.04, u1, z0, z1), (u0, u1, z0, z0 + 0.04), (u0, u1, z1 - 0.04, z1)):
                F.box("bronze", *box, w - 0.02, w + 0.02)


def storey(m, z):
    S = sides(m, W, D)
    F = S["front"]
    c, e = z + 0.95, z + FL - 0.45
    holes = [(a, b, c, e) for a, b in bays()]
    F.wall("cladstone", -HW, HW, z, z + FL, holes, depth=0.25)
    for a, b in bays():
        chicago(F, a, b, c, e)
        # The spandrel sunk between the piers, a sill course.
        F.box("cladstone", a, b, z + 0.2, c - 0.2, -0.06, 0, skip=("back", "left", "right"))
        F.box("cladstone", a - 0.05, b + 0.05, c - 0.1, c, 0, 0.08, skip=("back",))
    piers(F, z, z + FL)
    for name, wins in (("right", [-3.6, 0.0, 3.6]), ("back", [-4.0, 0.0, 4.0])):
        Sd = S[name]
        h = HD if name == "right" else HW
        holes = [(u - 0.75, u + 0.75, z + 1.0, z + 3.2) for u in wins]
        Sd.wall("brick", -h, h, z, z + FL, holes, depth=0.3, reveal="stone")
        for a, b, c_, e_ in holes:
            sash(Sd, a, b, c_, e_, D=0.3, lights=(2, 2))
            sill(Sd, a, b, c_, D=0.3)
            lintel(Sd, a, b, e_, key_=False)
    S["left"].quad("brick", -HD, HD, z, z + FL)
    S["back"].box("gutter", 5.5, 5.6, z, z + FL, 0.03, 0.13, skip=("back",))
    ceiling(m, z + FL - 0.02)


# ---- roof ------------------------------------------------------------------------------

ATTIC = 1.3
CORN = 0.9  # the cornice's projection
PAR = 1.0


def roof(M, z):
    m = M.m
    S = sides(m, W, D)
    F = S["front"]
    # The attic band: small square lights between the piers, a moulding over them.
    holes = [((a + b) / 2 - 0.55, (a + b) / 2 + 0.55, z + 0.25, z + 0.95) for a, b in bays()]
    F.wall("cladstone", -HW, HW, z, z + ATTIC, holes, depth=0.2)
    for a, b, c, e in holes:
        pane(F, "shopglass", a, b, c, e, a, b, c, e, -0.15, new_id())
        F.box("bronze", (a + b) / 2 - 0.02, (a + b) / 2 + 0.02, c, e, -0.16, -0.12)
    piers(F, z, z + ATTIC)
    for name in ("right", "back", "left"):
        h = HD if name in ("right", "left") else HW
        S[name].quad("brick", -h, h, z, z + ATTIC + PAR)
    # The cornice: a bed moulding, modillions, the corona; returned 1.5 m down the right side.
    cz = z + ATTIC
    F.box("cornice", -HW, HW, cz - 0.15, cz, 0, PO + 0.18, skip=("back",))
    for i in range(int(W / 0.5)):
        u = -HW + 0.25 + i * 0.5
        F.box("cornice", u - 0.07, u + 0.07, cz, cz + 0.2, 0, CORN - 0.1, skip=("back", "top"))
    m.box("cornice", (-HW - 0.1, -HD - CORN, cz + 0.2), (HW + CORN, -HD + 1.5, cz + 0.5), skip=("x0",))
    m.box("cornice", (-HW - 0.1, -HD - CORN - 0.05, cz + 0.5), (HW + CORN + 0.05, -HD + 1.5, cz + 0.6), skip=("x0",))
    # The parapet over it, and the raised centre with the clock.
    pz = cz + 0.6
    F.box("cladstone", -HW, HW, pz, pz + 0.5, -0.3, 0, skip=("bottom",))
    for name in ("right", "back", "left"):
        h = HD if name in ("right", "left") else HW
        S[name].box("stone", -h, h, z + ATTIC + PAR, z + ATTIC + PAR + 0.08, -0.33, 0.04, skip=())
        S[name].quad("brick", h - 0.3, -h + 0.3, cz, z + ATTIC + PAR, -0.3, out=-S[name].n)
    # Balusters along the front parapet either side of the centre.
    for u in [x * 0.3 for x in range(-22, 23)]:
        if abs(u) < 2.6 or abs(u) > HW - 0.3:
            continue
        F.box("cladstone", u - 0.06, u + 0.06, pz + 0.5, pz + PAR, -0.25, -0.13, skip=("bottom", "top"))
    F.box("cladstone", -HW, HW, pz + PAR, pz + PAR + 0.1, -0.3, -0.08)
    cw, ch = 2.5, 2.2
    F.box("cladstone", -cw, cw, pz, pz + ch, -0.5, 0.05)
    F.box("cladstone", -cw - 0.1, cw + 0.1, pz + ch, pz + ch + 0.15, -0.55, 0.12)
    F.box("cladstone", -0.8, 0.8, pz + ch + 0.15, pz + ch + 0.6, -0.4, 0.0)
    clock(m, F, 0, pz + 1.15, 0.05)
    # Flagpole on the centre.
    m.cyl("steel", 0, -HD + 0.2, 0.05, pz + ch + 0.6, pz + ch + 5.5, seg=8)
    m.cyl("brass", 0, -HD + 0.2, 0.09, pz + ch + 5.5, pz + ch + 5.65, seg=8)
    # The roof deck, a skylight, a stair head, the water tank.
    deck = cz + 0.1
    m.poly("roof", [(-HW + 0.3, -HD + 0.3, deck), (HW - 0.3, -HD + 0.3, deck), (HW - 0.3, HD - 0.3, deck), (-HW + 0.3, HD - 0.3, deck)], out=Z)
    m.box("brick", (-5.5, 2.5, deck), (-3.3, 5.4, deck + 2.6), skip=("z0",))
    m.box("steel", (-5.6, 2.4, deck + 2.6), (-3.2, 5.5, deck + 2.72), skip=())
    Sd = Side(m, (-4.4, 2.5, 0), (1, 0, 0), (0, -1, 0))
    Sd.quad("door", -0.45, 0.45, deck, deck + 2.1, 0.01)
    for s in (-1, 1):
        m.poly("canopy", [(-1.4, 0.5 * s, deck + 0.4), (1.4, 0.5 * s, deck + 0.4), (1.4, 0, deck + 1.0), (-1.4, 0, deck + 1.0)], out=(0, s, 1))
    m.box("steel", (-1.45, -0.55, deck), (1.45, 0.55, deck + 0.4), skip=("z0",))
    tank(m, 3.2, 2.6, deck)


def clock(m, F, u, z, w):
    r = 0.62
    annulus(F, "bronze", u, z, r, r + 0.14, w + 0.08, seg=24)
    disc(F, "clock", u, z, r, w + 0.04, seg=24)
    for i in range(12):
        a = i / 12 * math.tau
        q = 0.05 if i % 3 else 0.08
        cu, cz = u + math.sin(a) * (r - 0.1), z + math.cos(a) * (r - 0.1)
        m.strut("iron", F.p(cu - math.sin(a) * q, cz - math.cos(a) * q, w + 0.05), F.p(cu + math.sin(a) * q, cz + math.cos(a) * q, w + 0.05), 0.012, 0.03)
    for ang, ln in ((-60, 0.32), (150, 0.48)):
        a = math.radians(ang)
        m.strut("iron", F.p(u, z, w + 0.06), F.p(u + math.sin(a) * ln, z + math.cos(a) * ln, w + 0.06), 0.015, 0.04)


def tank(m, x, y, z):
    """A timber water tank on a steel stand, hooped, under a conical roof."""
    legs = 2.6
    for dx in (-0.9, 0.9):
        for dy in (-0.9, 0.9):
            m.box("steel", (x + dx - 0.08, y + dy - 0.08, z), (x + dx + 0.08, y + dy + 0.08, z + legs))
    m.strut("steel", (x - 0.9, y - 0.9, z + 0.3), (x + 0.9, y - 0.9, z + legs - 0.2), 0.05)
    m.strut("steel", (x - 0.9, y + 0.9, z + legs - 0.2), (x + 0.9, y + 0.9, z + 0.3), 0.05)
    m.box("steel", (x - 1.35, y - 1.35, z + legs), (x + 1.35, y + 1.35, z + legs + 0.15))
    t0, t1 = z + legs + 0.15, z + legs + 3.0
    m.cyl("wood", x, y, 1.3, t0, t1, seg=20, top=False, bottom=True, uv=True)
    for hz in (0.3, 1.0, 1.7, 2.4):
        m.cyl("iron", x, y, 1.33, t0 + hz, t0 + hz + 0.05, seg=20, top=False)
    m.cyl("roof", x, y, 1.42, t1, t1 + 0.9, seg=20, r1=0.08)
