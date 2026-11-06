# F1, fire station: the town's engine house of about 1915. Red brick on a
# granite plinth, two tall engine bays under a stone band lettered FIRE
# STATION, each closed by four folding doors in fire-engine red with glazed
# tops; a pier between them with the station's number and a red lamp on a
# bracket either side. Crew quarters above, five two-over-two sashes under
# stone lintels; a corbelled brick cornice and a parapet. The hose tower
# rises from the back right corner well over the roof: slit windows, a
# stone band, an open belfry of arches with the alarm bell in it, a slate
# pyramid and a copper finial. A personnel door on the right with a lamp,
# the yard door and windows behind; a flagpole on the parapet.
#
# Pieces (base at the origin, stacked by the app):
#   ground  5.0 m: the engine bays, the lettered band
#   floor   3.4 m: the crew quarters
#   roof    cornice, parapet and deck, the chimney, the flagpole and the
#           hose tower above the roof
import math

from lib import Model, Z, fpoly, letters, lintel, new_id, pane, sash, sides, sill

ID = "f1"
W, D = 11.0, 13.0
HW, HD = W / 2, D / 2
PLINTH = 0.25
G = 5.0
FL = 3.4
TOP = G + FL
BAYS = [(-4.85, -1.05), (1.05, 4.85)]  # the engine doors
BAY_E = 4.05
# The hose tower, in the back right corner.
# It stands 0.12 m proud of the side and back walls all the way up.
PROUD = 0.12
TX0, TX1 = HW - 3.2, HW + PROUD
TY0, TY1 = HD - 3.2, HD + PROUD
TW = TX1 - TX0
SHAFT = TOP + 6.0  # top of the shaft, where the belfry starts
BELFRY = 2.4


def build(out, bake=True):
    M = Model(ID, seed=17)
    M.sharp = math.radians(40)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    storey(M, G)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    M.export(out, bake)


# ---- ground storey --------------------------------------------------------------------


def ground(M):
    m = M.m
    m.sweep("granite", W, D, [(0.06, 0.0), (0.06, PLINTH - 0.04), (0.03, PLINTH), (-0.01, PLINTH)])
    walls = sides(m, W, D)
    F = walls["front"]
    holes = [(a, b, 0.0, BAY_E, 0.35) for a, b in BAYS]
    F.wall("brick", -HW, HW, PLINTH, G, holes, depth=0.35, reveal="stone")
    # The plinth's granite stops at the bays; the apron runs in.
    for a, b in BAYS:
        F.box("concrete", a, b, -0.01, 0.0, -0.35, 0.0, skip=("back", "bottom"))
        engine_doors(F, a, b)
        # A steel beam over the opening, a stone head and rubbing posts at the jambs.
        F.box("steelframe", a - 0.05, b + 0.05, BAY_E, BAY_E + 0.3, -0.02, 0.0)
        for u in (a, b):
            F.box("granite", u - 0.14, u + 0.14, 0.0, 0.9, 0, 0.12)
            F.box("granite", u - 0.12, u + 0.12, 0.9, 1.0, 0, 0.1)
    # Brick quoins at the corners and the central pier, in a deeper red.
    for u0, u1 in ((-HW, -HW + 0.5), (-0.75, 0.75), (HW - 0.5, HW)):
        for i in range(int((G - PLINTH) / 0.45)):
            z0 = PLINTH + i * 0.45
            k = 0.08 if i % 2 == 0 else 0.0
            F.box("rubbed", u0 - (k if u0 < -1 else 0), u1 + (k if u1 > 1 else 0), z0, z0 + 0.38, 0, 0.04)
    # The station's number on the pier, a red lamp either side of the bays.
    F.box("stone", -0.55, 0.55, 2.2, 2.95, 0, 0.06)
    F.box("stone", -0.45, 0.45, 2.3, 2.85, 0.06, 0.08)
    letters(m, "brass", F, 0, 2.575, 0.08, "No 1", 0.28, depth=0.025)
    for u in (-HW + 0.25, 0.0, HW - 0.25):
        redlamp(m, F, u, 3.55 if u else 3.4)
    # The lettered band across the front, and the shop cornice over it.
    F.box("stone", -HW - 0.02, HW + 0.02, G - 0.75, G - 0.1, 0, 0.06)
    F.box("stone", -HW - 0.06, HW + 0.06, G - 0.1, G, 0, 0.14)
    F.box("stone", -HW - 0.04, HW + 0.04, G - 0.82, G - 0.75, 0, 0.1)
    letters(m, "fireletter", F, 0, G - 0.43, 0.06, "FIRE STATION", 0.4, depth=0.03, spacing=1.2)
    # Sides: the personnel door on the right, high windows; the left blank but for windows.
    R = walls["right"]
    door = (-4.6, -3.6)
    wins = [(u - 0.5, u + 0.5, 2.2, 3.9) for u in (-1.6, 0.6)]
    R.wall("brick", -HD, HD, PLINTH, G, [(*door, PLINTH, 2.6, 0.3), *wins], depth=0.3, reveal="stone")
    plain_door(m, R, *door, PLINTH, 2.6)
    R.box("iron", door[1] + 0.25, door[1] + 0.4, 2.55, 2.78, 0, 0.12)
    R.box("lamp", door[1] + 0.27, door[1] + 0.38, 2.57, 2.76, 0.12, 0.15, skip=("back",))
    R.box("concrete", door[0] - 0.3, door[1] + 0.3, 0.0, PLINTH, 0, 0.7, skip=("back",))
    for a, b, c, e in wins:
        sash(R, a, b, c, e, D=0.3, lights=(2, 2), glass="worksglass")
        sill(R, a, b, c, D=0.3)
        lintel(R, a, b, e, key_=False)
    L = walls["left"]
    lw = [(u - 0.5, u + 0.5, 2.2, 3.9) for u in (-4.0, -1.0, 2.0, 4.6)]
    L.wall("brick", -HD, HD, PLINTH, G, lw, depth=0.3, reveal="stone")
    for a, b, c, e in lw:
        sash(L, a, b, c, e, D=0.3, lights=(2, 2), glass="worksglass")
        sill(L, a, b, c, D=0.3)
        lintel(L, a, b, e, key_=False)
    # Back: the yard door (a smaller engine door for the hose cart), a window.
    B = walls["back"]
    yd = (-1.0, 1.4)
    bw = (2.6, 3.6, 2.0, 3.7)
    B.wall("brick", -HW, HW, PLINTH, G, [(*yd, 0.0, 3.2, 0.3), bw], depth=0.3, reveal="stone")
    B.quad("firedoor", *yd, 0.0, 3.2, -0.25)
    for k in range(1, 4):
        u = yd[0] + k * (yd[1] - yd[0]) / 4
        B.box("firedoor", u - 0.03, u + 0.03, 0.0, 3.2, -0.25, -0.2)
    B.box("steelframe", yd[0] - 0.05, yd[1] + 0.05, 3.2, 3.45, -0.02, 0.0)
    sash(B, *bw, D=0.3, lights=(2, 2), glass="worksglass")
    sill(B, bw[0], bw[1], bw[2], D=0.3)
    lintel(B, bw[0], bw[1], bw[3], key_=False)
    tower_face(m, 0.0, G)
    # Ceiling over the bays.
    m.poly("dark", [(-HW, -HD, G - 0.02), (HW, -HD, G - 0.02), (HW, HD, G - 0.02), (-HW, HD, G - 0.02)], out=-Z)


def engine_doors(F, a, b):
    """Four folding leaves across the bay, set back in the reveal: red
    boarded lower panels, glazed tops of six lights, strap hinges."""
    D_ = 0.3
    c, e = 0.0, BAY_E
    n = 4
    lw = (b - a) / n
    wid = new_id()
    for i in range(n):
        u0, u1 = a + i * lw, a + (i + 1) * lw
        # A slight fold at the meeting stiles shows the leaves.
        w = -D_ + (0.03 if i % 2 else 0.0)
        F.box("firedoor", u0, u0 + 0.08, c, e, w - 0.06, w)
        F.box("firedoor", u1 - 0.08, u1, c, e, w - 0.06, w)
        F.box("firedoor", u0 + 0.08, u1 - 0.08, e - 0.1, e, w - 0.06, w)
        F.box("firedoor", u0 + 0.08, u1 - 0.08, c, c + 0.15, w - 0.06, w)
        F.box("firedoor", u0 + 0.08, u1 - 0.08, 2.45, 2.55, w - 0.06, w)
        F.box("firedoor", u0 + 0.08, u1 - 0.08, 1.3, 1.38, w - 0.06, w)
        F.quad("firedoor", u0 + 0.08, u1 - 0.08, c + 0.15, 2.45, w - 0.04)
        # Raised panels below.
        for z0, z1 in ((0.3, 1.2), (1.48, 2.35)):
            F.box("firedoor", u0 + 0.16, u1 - 0.16, z0, z1, w - 0.04, w - 0.01)
        # Six lights above.
        gz0, gz1 = 2.55, e - 0.1
        pane(F, "worksglass", a, b, c, e, u0 + 0.08, u1 - 0.08, gz0, gz1, w - 0.045, wid)
        for k in (1, 2):
            z = gz0 + k * (gz1 - gz0) / 3
            F.box("firedoor", u0 + 0.08, u1 - 0.08, z - 0.02, z + 0.02, w - 0.05, w - 0.01)
        mid = (u0 + u1) / 2
        F.box("firedoor", mid - 0.02, mid + 0.02, gz0, gz1, w - 0.05, w - 0.01)
        F.box("iron", u0 + 0.04, u0 + 0.55, 0.6, 0.66, w - 0.01, w + 0.005)
        F.box("iron", u0 + 0.04, u0 + 0.55, 3.3, 3.36, w - 0.01, w + 0.005)
    F.box("brass", (a + b) / 2 - 0.03, (a + b) / 2 + 0.03, 1.1, 1.4, -D_ + 0.0, -D_ + 0.04)


def redlamp(m, F, u, z):
    """A red globe lamp on a scrolled iron bracket."""
    F.box("iron", u - 0.04, u + 0.04, z - 0.15, z + 0.35, 0, 0.05)
    F.box("iron", u - 0.025, u + 0.025, z + 0.25, z + 0.3, 0.05, 0.45)
    p = F.p(u, z + 0.05, 0.45)
    m.cyl("iron", p.x, p.y, 0.02, z + 0.15, z + 0.27, seg=6)
    m.cyl("redlamp", p.x, p.y, 0.13, z - 0.1, z + 0.15, seg=12, bottom=True, r1=0.1)
    m.cyl("iron", p.x, p.y, 0.1, z + 0.15, z + 0.19, seg=12)


def plain_door(m, F, a, b, c, e):
    D_ = 0.3
    F.quad("firedoor", a, b, c, e, -D_ + 0.05)
    F.box("firedoor", a + 0.12, b - 0.12, c + 0.2, c + 1.0, -D_ + 0.05, -D_ + 0.08)
    wid = new_id()
    pane(F, "worksglass", a, b, c, e, a + 0.15, b - 0.15, c + 1.3, e - 0.2, -D_ + 0.06, wid)
    F.box("brass", b - 0.16, b - 0.1, c + 1.0, c + 1.07, -D_ + 0.05, -D_ + 0.1)
    F.box("stone", a - 0.12, b + 0.12, e, e + 0.28, 0, 0.04)


# ---- the crew's storey -------------------------------------------------------------------


def storey(M, z):
    m = M.m
    c, e = z + 0.75, z + 2.65
    for name, F in sides(m, W, D).items():
        h = HW if name in ("front", "back") else HD
        if name == "front":
            us = [-4.0, -2.0, 0.0, 2.0, 4.0]
        elif name == "back":
            us = [1.2, 3.6]  # the tower stands at u < -2.3
        elif name == "right":
            us = [-4.6, -2.4, -0.2]
        else:
            us = [-4.0, -1.5, 1.0, 3.5]
        holes = [(u - 0.48, u + 0.48, c, e) for u in us]
        F.wall("brick", -h, h, z, z + FL, holes, depth=0.28)
        for a, b, c_, e_ in holes:
            sash(F, a, b, c_, e_, D=0.28, lights=(2, 1))
            sill(F, a, b, c_, D=0.28)
            lintel(F, a, b, e_, key_=name == "front")
        if name == "front":
            # Stone string course at the sills, quoins carried up.
            F.box("stone", -h - 0.02, h + 0.02, c - 0.14, c - 0.06, 0, 0.06)
            for u0, u1 in ((-h, -h + 0.5), (h - 0.5, h)):
                for i in range(int(FL / 0.45)):
                    z0 = z + i * 0.45
                    k = 0.08 if i % 2 == 0 else 0.0
                    F.box("rubbed", u0 - (k if u0 < 0 else 0), u1 + (k if u1 > 0 else 0), z0, z0 + 0.38, 0, 0.04)
    tower_face(m, z, z + FL)
    m.poly("dark", [(-HW, -HD, z + FL - 0.02), (HW, -HD, z + FL - 0.02), (HW, HD, z + FL - 0.02), (-HW, HD, z + FL - 0.02)], out=-Z)


def tower_face(m, z0, z1):
    """The hose tower's walls where it stands proud of the right and back walls, z0 to z1, with a slit each storey."""
    m.box("brick", (HW, TY0, max(z0, PLINTH)), (TX1, TY1, z1), skip=("x0", "z0", "z1"))
    m.box("brick", (TX0, HD, max(z0, PLINTH)), (HW, TY1, z1), skip=("y0", "z0", "z1"))
    if z0 == 0.0:
        m.box("granite", (HW, TY0 - 0.03, 0), (TX1 + 0.03, TY1 + 0.03, PLINTH), skip=("x0", "z0"))
        m.box("granite", (TX0 - 0.03, HD, 0), (HW, TY1 + 0.03, PLINTH), skip=("y0", "z0"))
    zc = z0 + 1.6
    for lo, hi in (((TX1, (TY0 + TY1) / 2 - 0.18, zc), (TX1 + 0.01, (TY0 + TY1) / 2 + 0.18, zc + 1.0)),
                   (((TX0 + TX1) / 2 - 0.18, TY1, zc), ((TX0 + TX1) / 2 + 0.18, TY1 + 0.01, zc + 1.0))):
        m.box("dark", lo, hi, skip=("x0", "y0"))
    m.box("stone", (TX1, TY0, z1 - 0.12), (TX1 + 0.05, TY1 + 0.05, z1), skip=("x0",))
    m.box("stone", (TX0, TY1, z1 - 0.12), (TX1 + 0.05, TY1 + 0.05, z1), skip=("y0",))


# ---- roof, parapet and the hose tower ----------------------------------------------------


def roof(M):
    m = M.m
    walls = sides(m, W, D)
    CZ = TOP + 0.45
    PT = CZ + 0.7
    deck = TOP + 0.25
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.wall("brick", -h, h, TOP, PT, [])
        # Corbel table: three courses stepping out, dentils under them.
        F.box("brick", -h, h, CZ - 0.2, CZ - 0.12, 0, 0.06)
        F.box("brick", -h, h, CZ - 0.12, CZ, 0, 0.12)
        for i in range(int(2 * h / 0.32)):
            u = -h + 0.16 + i * 0.32
            F.box("brick", u - 0.07, u + 0.07, CZ - 0.36, CZ - 0.2, 0, 0.07)
        F.box("stone", -h - 0.06, h + 0.06, CZ, CZ + 0.1, 0, 0.18)
        F.box("stone", -h - 0.06, h + 0.06, PT, PT + 0.09, -0.32, 0.06, skip=())
        F.quad("brick", h - 0.3, -h + 0.3, deck, PT, -0.3, out=-F.n)
    # A raised name panel over the middle of the front.
    F = walls["front"]
    F.box("brick", -1.8, 1.8, PT, PT + 0.6, -0.3, 0, skip=())
    F.box("stone", -1.9, 1.9, PT + 0.6, PT + 0.7, -0.35, 0.06, skip=())
    F.box("stone", -1.3, 1.3, PT - 0.25, PT + 0.45, 0, 0.05)
    letters(m, "stone", F, 0, PT + 0.1, 0.05, "1915", 0.32, depth=0.03)
    m.poly("roof", [(-HW + 0.3, -HD + 0.3, deck), (HW - 0.3, -HD + 0.3, deck), (HW - 0.3, HD - 0.3, deck), (-HW + 0.3, HD - 0.3, deck)], out=Z)
    # Chimney on the left wall, a hatch, a vent stack.
    cx, cy = -HW + 0.35, 1.0
    ct = PT + 1.4
    m.box("brick", (cx - 0.35, cy - 0.5, deck), (cx + 0.4, cy + 0.5, ct))
    m.box("stone", (cx - 0.42, cy - 0.57, ct), (cx + 0.47, cy + 0.57, ct + 0.1))
    for dy in (-0.22, 0.22):
        m.cyl("terracotta", cx + 0.03, cy + dy, 0.1, ct + 0.1, ct + 0.45, seg=10, r1=0.08)
    m.box("wood", (-1.6, 3.0, deck), (-0.6, 4.0, deck + 0.45))
    m.box("steel", (-1.65, 2.95, deck + 0.45), (-0.55, 4.05, deck + 0.52))
    m.cyl("ac", 1.2, 1.5, 0.08, deck, deck + 0.9, seg=10)
    # The flagpole on the front parapet, a gilt ball on top.
    fx, fy = -HW + 1.0, -HD + 0.15
    m.cyl("paint", fx, fy, 0.12, PT + 0.09, PT + 0.3, seg=10)
    m.cyl("paint", fx, fy, 0.05, PT + 0.3, PT + 6.5, seg=10, r1=0.03)
    m.cyl("brass", fx, fy, 0.07, PT + 6.5, PT + 6.62, seg=10)
    tower(m, deck)


def tower(m, deck):
    """The hose tower above the roof: shaft, belfry, pyramid."""
    cx, cy = (TX0 + TX1) / 2, (TY0 + TY1) / 2
    T = sides(m, TW, TW, cx, cy)
    for name, F in T.items():
        # Narrow slits up the shaft, every 2.2 m.
        slits = [(-0.18, 0.18, z, z + 1.0) for z in (TOP + 1.6, TOP + 3.8)]
        F.wall("brick", -TW / 2, TW / 2, TOP, SHAFT, slits, depth=0.25, reveal="stone")
        for a, b, c, e in slits:
            pane(F, "worksglass", a, b, c, e, a, b, c, e, -0.18, new_id())
            sill(F, a, b, c, D=0.25)
            F.box("stone", a - 0.1, b + 0.1, e, e + 0.2, 0, 0.03)
        # Quoins.
        for u0, u1 in ((-TW / 2, -TW / 2 + 0.4), (TW / 2 - 0.4, TW / 2)):
            for i in range(int((SHAFT - TOP) / 0.45)):
                z0 = TOP + i * 0.45
                k = 0.07 if i % 2 == 0 else 0.0
                F.box("rubbed", u0 - (k if u0 < 0 else 0), u1 + (k if u1 > 0 else 0), z0, z0 + 0.38, 0, 0.04)
        # A stone band under the belfry.
        F.box("stone", -TW / 2 - 0.08, TW / 2 + 0.08, SHAFT - 0.1, SHAFT + 0.15, 0, 0.12)
        # The belfry: an arch each face between brick piers.
        bz0, bz1 = SHAFT + 0.15, SHAFT + BELFRY
        a, b = -0.8, 0.8
        spring = bz1 - 0.95
        F.box("brick", -TW / 2, a, bz0, bz1, -0.3, 0, skip=())
        F.box("brick", b, TW / 2, bz0, bz1, -0.3, 0, skip=())
        arch = [(a, spring)] + [(-math.cos(t) * 0.8, spring + math.sin(t) * 0.8) for t in [i / 8 * math.pi for i in range(1, 8)]] + [(b, spring)]
        fpoly(F, "brick", [(a, spring), (a, bz1), (b, bz1), (b, spring)] + [(-math.cos(t) * 0.8, spring + math.sin(t) * 0.8) for t in [i / 8 * math.pi for i in range(7, 0, -1)]], 0.0)
        for (u0, z0), (u1, z1) in zip(arch, arch[1:]):
            m.poly("stone", [F.p(u0, z0, 0), F.p(u1, z1, 0), F.p(u1, z1, -0.3), F.p(u0, z0, -0.3)], out=-Z)
        F.box("stone", a - 0.05, b + 0.05, bz0, bz0 + 0.12, 0, 0.06)
        for u in (a, b):
            F.box("stone", u - 0.12, u + 0.12, spring - 0.1, spring, 0, 0.05)
        F.box("stone", -0.12, 0.12, spring + 0.68, spring + 0.98, 0, 0.06)
        # Cornice over the belfry.
        F.box("stone", -TW / 2 - 0.12, TW / 2 + 0.12, bz1, bz1 + 0.12, 0, 0.18)
    # Floor of the belfry, its ceiling, the alarm bell hung from a beam.
    bz0 = SHAFT + 0.15
    m.poly("dark", [(TX0 + 0.3, TY0 + 0.3, bz0), (TX1 - 0.3, TY0 + 0.3, bz0), (TX1 - 0.3, TY1 - 0.3, bz0), (TX0 + 0.3, TY1 - 0.3, bz0)], out=Z)
    top = SHAFT + BELFRY + 0.12
    m.poly("dark", [(TX0, TY0, top - 0.12), (TX1, TY0, top - 0.12), (TX1, TY1, top - 0.12), (TX0, TY1, top - 0.12)], out=-Z)
    m.box("wood", (TX0 + 0.3, cy - 0.08, top - 0.45), (TX1 - 0.3, cy + 0.08, top - 0.3))
    bz = top - 1.25
    m.cyl("bronze", cx, cy, 0.42, bz, bz + 0.55, seg=16, r1=0.3, bottom=False, top=False)
    m.cyl("bronze", cx, cy, 0.3, bz + 0.55, bz + 0.8, seg=16, r1=0.18)
    m.cyl("iron", cx, cy, 0.04, bz + 0.8, top - 0.45, seg=6)
    # The slate pyramid and a copper finial.
    o = 0.25
    r = TW / 2 + o
    apex = (cx, cy, top + 2.8)
    corners = [(cx - r, cy - r, top), (cx + r, cy - r, top), (cx + r, cy + r, top), (cx - r, cy + r, top)]
    for i in range(4):
        a_, b_ = corners[i], corners[(i + 1) % 4]
        mid = ((a_[0] + b_[0]) / 2 - cx, (a_[1] + b_[1]) / 2 - cy, 0.5)
        m.poly("slate", [a_, b_, apex], out=mid)
        # Lead on the hips.
        m.strut("lead", a_, apex, 0.08)
    m.poly("stone", corners, out=-Z)
    m.box("stone", (cx - r, cy - r, top - 0.12), (cx + r, cy + r, top), skip=("z1",))
    m.cyl("copper", cx, cy, 0.08, top + 2.7, top + 3.6, seg=8, r1=0.02)
    m.cyl("copper", cx, cy, 0.12, top + 3.05, top + 3.25, seg=10)
