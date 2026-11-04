# S1, main-street shop: the American two-part commercial block, a smaller
# sibling of A1. A brick building with one shop on the ground storey (a
# cast-iron shopfront with its sign fascia, a canvas awning) and the door to
# the flats beside it; one or two storeys of flats above, three bays of tall
# one-over-one sashes between brick pilasters; a pressed-metal cornice on
# brackets and a raised name panel on the front parapet, plainer parapets
# stepping down the sides, a chimney on the blank party wall and a faded
# advertisement painted on it. The app tints the brick, the shopfront and
# the cornice per building and picks the sign and the advertisement.
#
# Pieces (base at the origin, stacked by the app):
#   ground  4.45 m: shopfront, flats door, store windows, back door, the
#           shop cornice
#   floor   3.3 m: a storey of flats, one or two of them
#   awning  the shop's awning (not every shop has one)
#   roof    corbel table, cornice, parapets, roof with chimney and plant;
#           the ghost sign on the top storey's party wall hangs below it
from lib import Model, Z, awning, grille, hood, lintel, new_id, pane, sash, shopfront, sides, sill

ID = "s1"
W, D = 9.0, 11.0
PLINTH = 0.3  # shop floor above the pavement
G = 4.45  # ground storey
FL = 3.3  # upper storeys
HW, HD = W / 2, D / 2
SHOP = (-2.3, 4.1)  # shopfront opening
SHOP_E = 3.35  # its head
FLATS = (-3.95, -3.0)  # the flats' door
BAYS = [-2.8, 0.0, 2.8]
PILASTERS = [(-HW, -HW + 0.4), (-1.58, -1.22), (1.22, 1.58), (HW - 0.4, HW)]
DOWN = HW - 0.35  # downpipe on the back, x


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    storey(M, G)
    M.piece("awning")
    awning(sides(M.m, W, D)["front"], SHOP[0] - 0.1, SHOP[1] + 0.1, SHOP_E + 0.05, drop=0.8, depth=1.6)
    top = G + FL
    M.piece("roof", (0, 0, top))
    roof(M, top)
    M.export(out, bake)


def downpipe(m, z0, z1):
    m.box("gutter", (DOWN - 0.05, HD + 0.03, z0), (DOWN + 0.05, HD + 0.13, z1))


# ---- ground storey ------------------------------------------------------------------


def ground(M):
    m = M.m
    m.sweep("granite", W, D, [(0.05, 0.0), (0.05, PLINTH - 0.03), (0.02, PLINTH), (-0.01, PLINTH)])
    walls = sides(m, W, D)
    F = walls["front"]
    holes = [(*SHOP, PLINTH, SHOP_E), (*FLATS, PLINTH, 3.05, 0.4)]
    F.wall("brick", -HW, HW, PLINTH, G, holes, depth=0.3, reveal="stone")
    shopfront(F, *SHOP, PLINTH, SHOP_E, sign=0, sign_w=4.4)
    flats_door(F, *FLATS)
    for a, b in ((SHOP[1] - 1.25, SHOP[1] - 0.05), (FLATS[0] - 0.1, FLATS[1] + 0.1)):
        F.box("granite", a, b, 0, PLINTH, 0, 0.35, skip=("back",))
    # Iron piers either end of the shopfront, on granite bases.
    for a, b in ((-HW + 0.05, -HW + 0.35), (FLATS[1] + 0.12, SHOP[0] - 0.05), (SHOP[1] + 0.06, HW - 0.05)):
        F.box("shopframe", a, b, PLINTH, SHOP_E + 0.05, 0, 0.06)
        F.box("shopframe", a - 0.03, b + 0.03, SHOP_E - 0.1, SHOP_E + 0.05, 0, 0.09)
        F.box("granite", a - 0.02, b + 0.02, PLINTH, PLINTH + 0.25, 0, 0.09)
    # The shop cornice, across the whole front.
    F.box("cornice", -HW - 0.05, HW + 0.05, G - 0.2, G - 0.05, 0, 0.22, skip=())
    F.box("cornice", -HW - 0.08, HW + 0.08, G - 0.05, G, 0, 0.28, skip=())
    for name in ("right", "left"):
        S = walls[name]
        wins = [(u - 0.45, u + 0.45, 2.25, 3.05) for u in (-1.2, 2.8)]
        S.wall("brick", -HD, HD, PLINTH, G, wins, depth=0.3, reveal="stone")
        for a, b, c, e in wins:
            sash(S, a, b, c, e, D=0.3, lights=(2, 1))
            sill(S, a, b, c, D=0.3)
            grille(S, a, b, c, e)
            S.box("stone", a - 0.1, b + 0.1, e, e + 0.22, 0, 0.025)
    back(m, walls["back"])
    # A ceiling over the ground storey, seen when the floors above are gone.
    m.poly("dark", [(-HW, -HD, G - 0.02), (HW, -HD, G - 0.02), (HW, HD, G - 0.02), (-HW, HD, G - 0.02)], out=Z)


def flats_door(F, a, b):
    """The flats' street door, recessed: four panels under a glazed upper half, a transom, a house number."""
    D_ = 0.4
    c, e = PLINTH, 3.05
    t = 2.45
    F.quad("stone", a, b, c, e, -D_)
    F.box("granite", a, b, c - 0.01, c, -D_, 0, skip=())
    dr = "door"
    wid = new_id()
    F.box(dr, a, a + 0.07, c, e, -D_, -D_ + 0.1)
    F.box(dr, b - 0.07, b, c, e, -D_, -D_ + 0.1)
    F.box(dr, a + 0.07, b - 0.07, t, t + 0.08, -D_, -D_ + 0.1)
    F.box(dr, a + 0.07, b - 0.07, e - 0.06, e, -D_, -D_ + 0.1)
    pane(F, "doorglass", a, b, c, e, a + 0.07, b - 0.07, t + 0.08, e - 0.06, -D_ + 0.04, wid)
    da, db = a + 0.07, b - 0.07
    F.quad(dr, da, db, c, t, -D_ + 0.03)
    F.box(dr, da + 0.1, db - 0.1, c + 1.15, t - 0.12, -D_ + 0.03, -D_ + 0.05, skip=("back", "front"))
    pane(F, "doorglass", a, b, c, e, da + 0.1, db - 0.1, c + 1.15, t - 0.12, -D_ + 0.04, wid)
    mid = (da + db) / 2
    for u0, u1 in ((da + 0.1, mid - 0.05), (mid + 0.05, db - 0.1)):
        F.box(dr, u0, u1, c + 0.15, c + 1.0, -D_ + 0.03, -D_ + 0.05)
    F.box("brass", db - 0.13, db - 0.08, c + 1.0, c + 1.07, -D_ + 0.03, -D_ + 0.09)
    F.box("brass", mid - 0.15, mid + 0.15, c + 0.95, c + 1.0, -D_ + 0.03, -D_ + 0.05)
    # Stone head with the street number, and a lamp.
    F.box("stone", a - 0.12, b + 0.12, e, e + 0.3, 0, 0.05)
    F.box("brass", (a + b) / 2 - 0.12, (a + b) / 2 + 0.12, e + 0.06, e + 0.24, 0.05, 0.06)
    F.box("iron", a - 0.4, a - 0.28, 2.1, 2.16, 0, 0.16)
    F.box("lamp", a - 0.41, a - 0.27, 2.16, 2.4, 0.06, 0.2, skip=())
    F.box("iron", a - 0.43, a - 0.25, 2.4, 2.44, 0.04, 0.22)


def back(m, F):
    """The yard side: the shop's back door under a hood, a barred window, the meter box and a downpipe."""
    holes = [(-3.1, -2.1, PLINTH, 2.55, 0.25), (0.6, 1.8, 1.2, 2.7)]
    F.wall("brick", -HW, HW, PLINTH, G, holes, depth=0.3, reveal="stone")
    a, b = -3.1, -2.1
    F.quad("door", a + 0.05, b - 0.05, PLINTH, 2.5, -0.2)
    F.box("door", a, a + 0.05, PLINTH, 2.55, -0.25, -0.15)
    F.box("door", b - 0.05, b, PLINTH, 2.55, -0.25, -0.15)
    F.box("door", a + 0.05, b - 0.05, 2.5, 2.55, -0.25, -0.15)
    F.box("iron", b - 0.2, b - 0.12, 1.25, 1.3, -0.2, -0.15)
    F.box("concrete", a - 0.3, b + 0.3, 0, PLINTH, 0, 0.9, skip=("back",))
    F.box("iron", a - 0.25, b + 0.25, 2.7, 2.76, 0, 0.7, skip=())
    F.box("roof", a - 0.25, b + 0.25, 2.76, 2.8, 0, 0.7, skip=())
    F.box("lamp", b + 0.15, b + 0.3, 2.3, 2.45, 0, 0.12)
    sash(F, 0.6, 1.8, 1.2, 2.7, D=0.3)
    sill(F, 0.6, 1.8, 1.2, D=0.3)
    grille(F, 0.6, 1.8, 1.2, 2.7)
    lintel(F, 0.6, 1.8, 2.7, key_=False)
    F.box("ac", -1.2, -0.7, 1.3, 1.9, 0, 0.18)
    F.box("dark", -1.15, -0.75, 1.55, 1.75, 0.18, 0.185, skip=("back",))
    downpipe(m, 0.05, G)
    m.box("gutter", (DOWN - 0.05, HD + 0.03, 0.05), (DOWN + 0.05, HD + 0.35, 0.13))


# ---- upper storeys --------------------------------------------------------------------


def storey(M, z):
    """A storey of flats from z: three bays on the front, two windows a side and at the back."""
    m = M.m
    ww, c, e = 1.0, z + 0.8, z + 2.8
    for name, F in sides(m, W, D).items():
        h = HW if name in ("front", "back") else HD
        if name == "front":
            holes = [(u - ww / 2, u + ww / 2, c, e) for u in BAYS]
        elif name == "back":
            holes = [(-2.9, -1.9, c, e), (-0.3, 0.3, z + 1.6, z + 2.5), (1.4, 2.4, c, e)]
        elif name == "right":
            holes = [(u - 0.45, u + 0.45, c + 0.1, e) for u in (-2.6, 2.6)]
        else:
            holes = []  # the party wall, built for a neighbour
        F.wall("brick", -h, h, z, z + FL, holes, depth=0.25)
        for a, b, c_, e_ in holes:
            sash(F, a, b, c_, e_, D=0.25, lights=(1, 1))
            sill(F, a, b, c_, D=0.25)
            if name == "front":
                hood(F, a, b, e_)
            else:
                lintel(F, a, b, e_, key_=False)
        if name == "front":
            for u0, u1 in PILASTERS:
                F.box("brick", u0, u1, z, z + FL, 0, 0.07)
                F.box("stone", u0 - 0.02, u1 + 0.02, c - 0.12, c - 0.04, 0, 0.1)
    downpipe(m, z, z + FL)
    m.poly("dark", [(-HW, -HD, z + FL - 0.02), (HW, -HD, z + FL - 0.02), (HW, HD, z + FL - 0.02), (-HW, HD, z + FL - 0.02)], out=Z)


# ---- roof -----------------------------------------------------------------------------


def roof(M, TOP):
    """Corbel table, cornice and parapets from TOP; the roof, its chimney and plant."""
    m = M.m
    walls = sides(m, W, D)
    CZ = TOP + 0.55  # cornice soffit
    PF = CZ + 1.05  # front parapet top
    PS = TOP + 0.85  # side and back parapet top
    STEP = 2.2  # sides keep the front's height this far back
    deck = TOP + 0.3
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        top = PF if name == "front" else PS
        F.wall("brick", -h, h, TOP, top, [])
        if name == "front":
            for u0, u1 in PILASTERS:
                F.box("brick", u0, u1, TOP, CZ, 0, 0.07)
            # Corbel table: brick courses stepping out under the cornice.
            F.box("brick", -HW, HW, CZ - 0.25, CZ - 0.17, 0, 0.1)
            F.box("brick", -HW, HW, CZ - 0.17, CZ, 0, 0.14)
            for i in range(int(W / 0.3)):
                u = -HW + 0.15 + i * 0.3
                F.box("brick", u - 0.07, u + 0.07, CZ - 0.42, CZ - 0.25, 0, 0.1)
        if name in ("right", "left"):
            # The side parapet steps up to the front's height at the front corner.
            u0, u1 = (-h, -h + STEP) if name == "right" else (h - STEP, h)
            F.box("brick", u0, u1, PS, PF, -0.3, 0, skip=())
            F.box("stone", u0 - (0.05 if name == "right" else 0), u1 + (0.05 if name == "left" else 0), PF, PF + 0.08, -0.33, 0.05, skip=())
        # Coping, and the inside face of the parapet.
        F.box("stone", -h - 0.05, h + 0.05, top, top + 0.08, -0.33, 0.05, skip=())
        F.quad("brick", h - 0.3, -h + 0.3, deck, top, -0.3, out=-F.n)
    # The pressed-metal cornice on the front, returning a little down the sides.
    x0, x1 = -HW - 0.14, HW + 0.14
    y = -HD
    for z0, z1, p in ((CZ, CZ + 0.12, 0.58), (CZ + 0.12, CZ + 0.3, 0.52), (CZ + 0.3, CZ + 0.38, 0.66), (CZ + 0.38, CZ + 0.44, 0.7)):
        m.box("cornice", (x0 - (p - 0.58), y - p, z0), (x1 + (p - 0.58), y + 0.5, z1))
    m.box("cornice", (x0 + 0.04, y - 0.12, CZ - 0.12), (x1 - 0.04, y + 0.45, CZ))
    F = walls["front"]
    for u in [(a + b) / 2 for a, b in PILASTERS]:
        F.box("cornice", u - 0.09, u + 0.09, CZ - 0.55, CZ, 0.07, 0.24)
        F.box("cornice", u - 0.09, u + 0.09, CZ - 0.2, CZ, 0.24, 0.5)
        F.box("cornice", u - 0.11, u + 0.11, CZ - 0.6, CZ - 0.55, 0.07, 0.26)
    for i in range(int((2 * HW) / 0.16)):
        u = -HW + 0.08 + i * 0.16
        if all(abs(u - (a + b) / 2) > 0.2 for a, b in PILASTERS):
            F.box("cornice", u - 0.04, u + 0.04, CZ - 0.2, CZ - 0.12, 0.12, 0.22)
    # Raised name panel in the middle of the front parapet, with a blank tablet.
    pa, pb, ph = -1.7, 1.7, PF + 0.55
    F.box("brick", pa, pb, PF, ph, -0.3, 0, skip=())
    F.box("stone", pa - 0.06, pb + 0.06, ph, ph + 0.1, -0.35, 0.06, skip=())
    F.box("stone", -0.35, 0.35, ph + 0.1, ph + 0.35, -0.3, 0.04, skip=())
    F.box("stone", -1.2, 1.2, PF - 0.55, PF + 0.4, 0, 0.07)
    F.box("stone", -1.1, 1.1, PF - 0.45, PF + 0.3, 0.07, 0.085)
    for u in (pa + 0.05, pb - 0.35):
        F.box("stone", u, u + 0.3, PF + 0.4, ph, 0, 0.04)
    # A painted advertisement on the party wall, faded (u, v over the sign; the app picks it).
    walls["left"].quad("ghost", -4.7, 4.1, TOP - 2.95, TOP - 0.2, 0.004, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    # Roof deck, the scupper and the head of the downpipe.
    m.poly("roof", [(-HW + 0.3, -HD + 0.3, deck), (HW - 0.3, -HD + 0.3, deck), (HW - 0.3, HD - 0.3, deck), (-HW + 0.3, HD - 0.3, deck)], out=Z)
    m.box("gutter", (DOWN - 0.12, HD - 0.05, deck), (DOWN + 0.12, HD + 0.2, deck + 0.12))
    m.box("gutter", (DOWN - 0.16, HD + 0.03, deck - 0.55), (DOWN + 0.16, HD + 0.3, deck - 0.12))
    downpipe(m, TOP, deck - 0.55)
    # Chimney stack on the left party wall, corbelled cap and two pots.
    cx, cy = -HW + 0.35, 1.6
    ct = PS + 1.6
    m.box("brick", (cx - 0.35, cy - 0.55, deck), (cx + 0.4, cy + 0.55, ct))
    m.sweep("brick", 0.75, 1.1, [(-0.01, ct - 0.25), (0.05, ct - 0.25), (0.05, ct - 0.1), (0.08, ct - 0.1), (0.08, ct), (-0.01, ct)], cx=cx + 0.025, cy=cy)
    m.poly("stone", [(cx - 0.43, cy - 0.63, ct), (cx + 0.48, cy - 0.63, ct), (cx + 0.48, cy + 0.63, ct), (cx - 0.43, cy + 0.63, ct)], out=Z)
    for dy in (-0.25, 0.25):
        m.cyl("terracotta", cx + 0.03, cy + dy, 0.11, ct, ct + 0.38, seg=10, r1=0.09)
    # Roof hatch, a skylight over the stair, vent stacks, a condenser and a TV aerial.
    hx, hy = 2.2, 2.8
    m.box("wood", (hx - 0.55, hy - 0.55, deck), (hx + 0.55, hy + 0.55, deck + 0.45))
    m.box("steel", (hx - 0.6, hy - 0.6, deck + 0.45), (hx + 0.6, hy + 0.6, deck + 0.52))
    sx, sy = -2.6, -1.0
    m.box("wood", (sx - 0.7, sy - 0.5, deck), (sx + 0.7, sy + 0.5, deck + 0.35))
    for s, pts in ((-1, [(sx - 0.7, sy - 0.5, deck + 0.35), (sx + 0.7, sy - 0.5, deck + 0.35), (sx + 0.7, sy, deck + 0.75), (sx - 0.7, sy, deck + 0.75)]),
                   (1, [(sx - 0.7, sy + 0.5, deck + 0.35), (sx + 0.7, sy + 0.5, deck + 0.35), (sx + 0.7, sy, deck + 0.75), (sx - 0.7, sy, deck + 0.75)])):
        m.poly("canopy", pts, out=(0, s, 1))
    for pts, out in (([(sx - 0.7, sy - 0.5, deck + 0.35), (sx - 0.7, sy + 0.5, deck + 0.35), (sx - 0.7, sy, deck + 0.75)], (-1, 0, 0)),
                     ([(sx + 0.7, sy - 0.5, deck + 0.35), (sx + 0.7, sy + 0.5, deck + 0.35), (sx + 0.7, sy, deck + 0.75)], (1, 0, 0))):
        m.poly("wood", pts, out=out)
    for x, y, hh in ((0.4, 3.9, 0.9), (1.0, 4.1, 0.6), (-0.6, 0.8, 0.7)):
        m.cyl("ac", x, y, 0.07, deck, deck + hh, seg=10)
        m.cyl("ac", x, y, 0.11, deck + hh, deck + hh + 0.1, seg=10)
    ax, ay = 2.4, -2.6
    m.box("ac", (ax - 0.55, ay - 0.4, deck + 0.12), (ax + 0.55, ay + 0.4, deck + 0.95))
    m.cyl("dark", ax, ay, 0.3, deck + 0.95, deck + 0.97, seg=16)
    m.box("concrete", (ax - 0.65, ay - 0.5, deck), (ax + 0.65, ay + 0.5, deck + 0.12))
    mx, my = cx + 0.03, cy
    m.strut("steel", (mx, my - 0.56, ct - 0.6), (mx, my - 0.56, ct + 1.6), 0.04)
    for zz, L in ((ct + 1.5, 0.75), (ct + 1.25, 0.6), (ct + 1.0, 0.45)):
        m.strut("steel", (mx - L, my - 0.6, zz), (mx + L, my - 0.6, zz), 0.02)
    m.strut("steel", (mx, my - 0.6, ct + 1.5), (mx, my - 1.5, ct + 1.5), 0.02)
