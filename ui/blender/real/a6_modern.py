# A6, modern apartments: a brick block of the 2020s, the kind going up in
# London, Copenhagen and Brooklyn. Brick in one colour, crisp precast bands
# at every floor, tall windows in deep reveals with bronze-anodised frames
# and a rail of flat bars across each. Loggias cut into the front, one bay
# in three on every floor, staggered storey to storey into a checkerboard:
# lined in timber, sliding doors at the back, a rail of flat bronze bars
# in front, a chair or a plant out in each. At the foot a glazed lobby under
# a timber soffit and the bike store's door. On the roof a penthouse set back
# behind a terrace with a glass balustrade, clad in timber, glass across its
# front; solar panels and a sedum roof over it. The app tints the brick,
# the timber and the frames.
#
# Pieces (base at the origin, stacked by the app):
#   ground   3.8 m: the lobby, the bike store, ground-floor flats
#   floor_a  3.1 m: loggias in the two outer bays
#   floor_b  3.1 m: a loggia in the middle bay; they alternate
#   roof     the parapet, the terrace, the penthouse
import math

from mathutils import Vector

from lib import Model, Side, Z, glazing, letters, sides

ID = "a6"
W, D = 14.0, 11.5
X0, X1, Y0, Y1 = -W / 2, W / 2, -D / 2, D / 2
G = 3.8
FL = 3.1
STOREYS = ("floor_a", "floor_b")  # the reference stack
DEPTH = 0.3  # deep reveals
BAYS = (-4.6, 0.0, 4.6)  # the front's three bays
BW = 1.55  # half a bay's opening
LOG = 1.7  # a loggia's depth
BAND = 0.32  # the precast band at each floor
SIDE = (-3.6, -1.2, 1.2, 3.6)
BACK = (-5.4, -3.0, -0.8, 1.6, 4.4)


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    for f, kind in enumerate(STOREYS):
        z = G + f * FL
        M.piece(kind, (0, 0, z))
        storey(M, kind, z)
    top = G + len(STOREYS) * FL
    M.piece("roof", (0, 0, top))
    roof(M, top)
    M.export(out, bake)


# ---- openings ------------------------------------------------------------------------------


def window(F, a, b, c, e, juliet=True, lights=2):
    """A tall window in bronze frames, a deep brick reveal, a precast sill;
    a rail of flat bars across the opening when it runs to the floor."""
    glazing(F, a, b, c, e, lights=lights, D=DEPTH, fr="bronze")
    F.box("concrete", a - 0.02, b + 0.02, c - 0.05, c, -DEPTH + 0.04, 0.03)
    if juliet:
        # A rail of flat bronze bars across it, as in the loggias.
        F.box("bronze", a, b, c + 1.03, c + 1.08, -0.08, -0.03, skip=())
        n = int((b - a) / 0.12)
        for i in range(1, n):
            u = a + i * (b - a) / n
            F.box("bronze", u - 0.006, u + 0.006, c + 0.02, c + 1.03, -0.08, -0.04, skip=("top", "bottom", "back"))


def loggia(M, F, u, z, things):
    """A loggia cut into the front at bay u from floor z: timber-lined, sliding doors
    across the back, a deck, a rail of flat bronze bars in front."""
    m = M.m
    a, b = u - BW, u + BW
    top = z + FL - BAND
    # The lining: the sides and the soffit in timber, the deck in boards.
    for uu, out in ((a, F.t), (b, -F.t)):
        m.poly("cladding", [F.p(uu, z, 0), F.p(uu, z, -LOG), F.p(uu, top, -LOG), F.p(uu, top, 0)], out=out)
    m.poly("cladding", [F.p(a, top, 0), F.p(b, top, 0), F.p(b, top, -LOG), F.p(a, top, -LOG)], out=-Z)
    m.poly("deck", [F.p(a, z + 0.05, 0), F.p(b, z + 0.05, 0), F.p(b, z + 0.05, -LOG), F.p(a, z + 0.05, -LOG)], out=Z)
    # The back: sliding doors the width of the loggia.
    B = Side(m, F.p(0, 0, -LOG), F.t, F.n)
    glazing(B, a + 0.1, b - 0.1, z + 0.05, top - 0.1, lights=3, D=0.08, fr="bronze", slide=True)
    B.quad("cladding", a, b, top - 0.1, top, 0.0)
    B.quad("cladding", a, a + 0.1, z + 0.05, top - 0.1, 0.0)
    B.quad("cladding", b - 0.1, b, z + 0.05, top - 0.1, 0.0)
    # The rail: a top bar and flat bars on edge every 0.11 m.
    F.box("bronze", a, b, z + 1.06, z + 1.1, -0.12, -0.04, skip=())
    F.box("bronze", a, b, z + 0.05, z + 0.09, -0.12, -0.04, skip=())
    n = int((b - a) / 0.11)
    for i in range(1, n):
        uu = a + i * (b - a) / n
        F.box("bronze", uu - 0.006, uu + 0.006, z + 0.09, z + 1.06, -0.12, -0.04, skip=("top", "bottom"))
    # What is out in it.
    for t in things:
        if t == "chairs":
            for k, uu in enumerate((u - 0.7, u + 0.2)):
                chair(F, uu, z + 0.05, -0.9 + 0.1 * k)
            q = F.p(u - 0.25, 0, -0.75)
            m.cyl("bronze", q.x, q.y, 0.03, z + 0.05, z + 0.7, seg=6)
            m.cyl("bronze", q.x, q.y, 0.3, z + 0.7, z + 0.73, seg=14, bottom=True)
        elif t == "plant":
            q = F.p(a + 0.45, 0, -0.5)
            m.cyl("concrete", q.x, q.y, 0.3, z + 0.05, z + 0.6, seg=12)
            for k in range(3):
                m.cyl("sedum", q.x, q.y, 0.34 - 0.08 * k, z + 0.6 + 0.3 * k, z + 0.95 + 0.3 * k, seg=10, r1=0.2 - 0.06 * k)
        elif t == "bike":
            q0, q1 = F.p(b - 0.5, 0, -1.4), F.p(b - 0.5, 0, -0.4)
            for q in (q0, q1):
                m.tube("iron", [q + Vector((0, 0, z + 0.05 + 0.33)) + (F.n * math.cos(k / 10 * math.tau) + Z * math.sin(k / 10 * math.tau)) * 0.32 for k in range(10)], 0.02, F.t)
            m.strut("chair", q0 + Vector((0, 0, z + 0.4)), q1 + Vector((0, 0, z + 0.75)), 0.04)
            m.strut("chair", q0 + Vector((0, 0, z + 0.38)), q1 + Vector((0, 0, z + 0.38)), 0.04)


def chair(F, u, z, w):
    """A slatted garden chair, facing the street."""
    F.box("chair", u - 0.24, u + 0.24, z + 0.4, z + 0.44, w - 0.22, w + 0.22, skip=())
    F.box("chair", u - 0.24, u + 0.24, z + 0.44, z + 0.85, w - 0.26, w - 0.22, skip=())
    for uu in (u - 0.22, u + 0.2):
        for ww in (w - 0.2, w + 0.18):
            F.box("bronze", uu, uu + 0.02, z, z + 0.4, ww, ww + 0.02, skip=("bottom", "top"))


# ---- the storeys ------------------------------------------------------------------------------


def core(m, z0, z1):
    m.box("dark", (X0 + 0.3, Y0 + LOG + 0.05, z0), (X1 - 0.3, Y1 - 0.3, z1), skip=("z0", "z1"))


def ceiling(m, z):
    e = 0.02
    m.poly("dark", [(X0 + e, Y0 + e, z), (X1 - e, Y0 + e, z), (X1 - e, Y1 - e, z), (X0 + e, Y1 - e, z)], out=Z)


def band(m, z):
    """The precast band at a floor: flush, a shadow gap under it."""
    m.sweep("concrete", W, D, [(-0.01, z), (0.012, z), (0.012, z + BAND), (-0.01, z + BAND)])


def sides_and_back(m, walls, z0, h, ground=False):
    """Slot windows in the sides, staggered storey to storey; the back's windows."""
    for name in ("left", "right"):
        S = walls[name]
        f = int(round((z0 - G) / FL)) if not ground else 0
        us = [u + (0.6 if (f % 2) else -0.6) for u in SIDE[::2]] if not ground else [SIDE[1], SIDE[2]]
        holes = [(u - 0.45, u + 0.45, z0 + (0.9 if ground else 0.35), z0 + h - BAND - 0.25) for u in us]
        S.wall("brick", -D / 2, D / 2, z0 + (0.0 if not ground else 0.3), z0 + h - BAND, holes, depth=DEPTH)
        for a, b, c, e in holes:
            window(S, a, b, c, e, juliet=False, lights=1)
    B = walls["back"]
    holes = []
    for i, u in enumerate(BACK):
        wide = i in (1, 3)
        hw = 0.8 if wide else 0.5
        holes.append((u - hw, u + hw, z0 + (0.15 if wide and not ground else 0.9), z0 + h - BAND - 0.25))
    if ground:
        holes[2] = (BACK[2] - 0.55, BACK[2] + 0.55, z0 + 0.3, z0 + 2.5)
    B.wall("brick", -W / 2, W / 2, z0 + (0.3 if ground else 0.0), z0 + h - BAND, holes, depth=DEPTH)
    for i, (a, b, c, e) in enumerate(holes):
        if ground and i == 2:
            glazing(B, a, b, c, e, lights=1, D=DEPTH, fr="bronze", glass="doorglass")
            continue
        window(B, a, b, c, e, juliet=c < z0 + 0.5, lights=2 if b - a > 1.2 else 1)


def storey(M, kind, z0):
    m = M.m
    walls = sides(m, W, D)
    F = walls["front"]
    logs = {"floor_a": (0, 2), "floor_b": (1,)}[kind]
    holes = []
    for i, u in enumerate(BAYS):
        if i in logs:
            holes.append((u - BW, u + BW, z0, z0 + FL - BAND, 0.001))  # lined in timber, not brick
        else:
            holes.append((u - 1.2, u + 1.2, z0 + 0.15, z0 + FL - BAND - 0.25))
    F.wall("brick", X0, X1, z0, z0 + FL - BAND, holes, depth=DEPTH)
    fills = {"floor_a": (("chairs",), ("plant", "bike")), "floor_b": (("chairs", "plant"),)}[kind]
    k = 0
    for i, u in enumerate(BAYS):
        a, b, c, e = holes[i][:4]
        if i in logs:
            loggia(M, F, u, z0, fills[k])
            k += 1
        else:
            window(F, a, b, c, e, lights=2)
    sides_and_back(m, walls, z0, FL)
    band(m, z0 + FL - BAND)
    core(m, z0, z0 + FL)
    ceiling(m, z0 + FL - 0.01)


def ground(M):
    m = M.m
    walls = sides(m, W, D)
    F = walls["front"]
    # A plinth of dark engineering brick under the brick.
    m.sweep("granite", W, D, [(0.02, 0.0), (0.02, 0.3), (-0.01, 0.3)])
    lobby = (-1.6, 1.6, 0.3, 3.0, 0.001)  # lined in timber
    bikes = (-6.2, -4.2, 0.3, 2.6)
    flat = (2.6, 6.2, 0.9, 3.0)
    F.wall("brick", X0, X1, 0.3, G - BAND, [lobby, bikes, flat], depth=DEPTH)
    # The lobby: a recess lined in timber, glass from the floor, the door in it.
    a, b, c, e, _ = lobby
    d = 1.2
    B = Side(m, F.p(0, 0, -d), F.t, F.n)
    glazing(B, a, b, c, e, lights=3, D=0.05, fr="bronze", glass="doorglass")
    B.box("bronze", -0.04, 0.04, 1.2, 1.9, 0.0, 0.06)
    for uu, out in ((a, F.t), (b, -F.t)):
        m.poly("cladding", [F.p(uu, c, 0), F.p(uu, c, -d), F.p(uu, e, -d), F.p(uu, e, 0)], out=out)
    m.poly("cladding", [F.p(a, e, 0), F.p(b, e, 0), F.p(b, e, -d), F.p(a, e, -d)], out=-Z)
    m.poly("concrete", [F.p(a, c, 0), F.p(b, c, 0), F.p(b, c, -d), F.p(a, c, -d)], out=Z)
    F.box("concrete", a - 0.4, b + 0.4, 0.0, 0.15, 0.0, 1.2, skip=("back", "bottom"))
    F.box("concrete", a, b, 0.15, 0.3, 0.0, 0.5, skip=("back", "bottom"))
    # A light over the door and the number in bronze on the brick beside it.
    for uu in (-0.8, 0.8):
        q = F.p(uu, 0, -d / 2)
        m.cyl("lamp", q.x, q.y, 0.1, e - 0.02, e, seg=12, bottom=True)
    letters(m, "bronze", F, b + 0.55, 2.0, 0.0, "9", 0.4, depth=0.03)
    # The bike store: a perforated bronze door.
    a, b, c, e = bikes
    F.quad("door", a, b, c, e, -DEPTH + 0.05)
    for k in range(1, 14):
        uu = a + k * (b - a) / 14
        F.box("bronze", uu - 0.01, uu + 0.01, c + 0.1, e - 0.1, -DEPTH + 0.05, -DEPTH + 0.08)
    F.box("concrete", a - 0.1, b + 0.1, 0.0, 0.3, 0.0, 0.6, skip=("back", "bottom"))
    # The ground-floor flat: a wide window behind a planter.
    a, b, c, e = flat
    window(F, a, b, c, e, juliet=False, lights=3)
    F.box("concrete", a - 0.2, b + 0.2, 0.0, 0.7, 0.0, 0.8, skip=("back", "bottom"))
    F.quad("sedum", a - 0.12, b + 0.12, 0.7, 0.7, 0.0)
    m.poly("sedum", [F.p(a - 0.12, 0.68, 0.08), F.p(b + 0.12, 0.68, 0.08), F.p(b + 0.12, 0.68, 0.72), F.p(a - 0.12, 0.68, 0.72)], out=Z)
    for k in range(6):
        q = F.p(a + 0.3 + k * (b - a - 0.6) / 5, 0, 0.4)
        m.cyl("sedum", q.x, q.y, 0.28, 0.68, 1.1 + 0.08 * (k % 2), seg=8, r1=0.12)
    sides_and_back(m, walls, 0.0, G, ground=True)
    # The precast band over the ground storey, deeper than the rest.
    band(m, G - BAND)
    # A timber soffit canopy over the lobby.
    F.box("cladding", -2.4, 2.4, 3.05, 3.12, 0.0, 1.4, skip=("back",))
    F.box("bronze", -2.42, 2.42, 3.12, 3.3, 0.0, 1.42, skip=("back", "bottom"))
    core(m, 0.0, G)
    ceiling(m, G - 0.01)


# ---- the roof ---------------------------------------------------------------------------------


def roof(M, z):
    m = M.m
    PH = 1.1
    # The parapet: brick, a bronze coping, the terrace inside it.
    m.sweep("brick", W, D, [(-0.01, z), (0.0, z), (0.0, z + PH)])
    m.sweep("bronze", W, D, [(0.0, z + PH), (0.03, z + PH), (0.03, z + PH + 0.06), (-0.3, z + PH + 0.06)])
    m.sweep("brick", W, D, [(-0.3, z + PH + 0.06), (-0.3, z + 0.15)])
    zr = z + 0.15
    m.poly("deck", [(X0 + 0.3, Y0 + 0.3, zr), (X1 - 0.3, Y0 + 0.3, zr), (X1 - 0.3, Y0 + 3.0, zr), (X0 + 0.3, Y0 + 3.0, zr)], out=Z)
    m.poly("gravel", [(X0 + 0.3, Y0 + 3.0, zr), (X1 - 0.3, Y0 + 3.0, zr), (X1 - 0.3, Y1 - 0.3, zr), (X0 + 0.3, Y1 - 0.3, zr)], out=Z)
    # A glass balustrade on the parapet along the front, so the terrace has a rail at 1.1 m above its deck.
    for x0, x1 in ((X0 + 0.1, -0.05), (0.05, X1 - 0.1)):
        m.box("railglass", (x0, Y0 + 0.12, z + PH + 0.06), (x1, Y0 + 0.14, z + PH + 0.5), skip=("x0", "x1", "z0", "z1"))
    # Planters on the terrace.
    for x in (-5.2, 5.2):
        m.box("concrete", (x - 0.9, Y0 + 0.4, zr), (x + 0.9, Y0 + 0.9, zr + 0.55))
        m.poly("sedum", [(x - 0.85, Y0 + 0.45, zr + 0.5), (x + 0.85, Y0 + 0.45, zr + 0.5), (x + 0.85, Y0 + 0.85, zr + 0.5), (x - 0.85, Y0 + 0.85, zr + 0.5)], out=Z)
        for k in range(4):
            m.cyl("sedum", x - 0.6 + k * 0.4, Y0 + 0.65, 0.22, zr + 0.5, zr + 0.95 + 0.1 * (k % 2), seg=8, r1=0.1)
    # The penthouse: set back 3 m from the front, 1.2 m from the sides, 1 m from the back.
    px0, px1, py0, py1 = X0 + 1.2, X1 - 1.2, Y0 + 3.0, Y1 - 1.0
    ph = 3.0
    P = sides(m, px1 - px0, py1 - py0, 0.0, (py0 + py1) / 2, zr)
    hw = (px1 - px0) / 2
    hd = (py1 - py0) / 2
    F = P["front"]
    F.wall("cladding", -hw, hw, 0.0, ph, [(-hw + 0.6, hw - 0.6, 0.05, ph - 0.35)], depth=0.2)
    glazing(F, -hw + 0.6, hw - 0.6, 0.05, ph - 0.35, lights=5, D=0.2, fr="bronze", slide=True)
    for name in ("left", "right"):
        S = P[name]
        S.wall("cladding", -hd, hd, 0.0, ph, [(-hd + 0.8, -hd + 2.0, 0.6, ph - 0.35)], depth=0.2)
        glazing(S, -hd + 0.8, -hd + 2.0, 0.6, ph - 0.35, lights=1, D=0.2, fr="bronze")
    P["back"].wall("cladding", -hw, hw, 0.0, ph, [(-0.5, 0.5, 0.0, 2.2)], depth=0.15)
    P["back"].quad("door", -0.5, 0.5, 0.0, 2.2, -0.15)
    zt = zr + ph
    # Its roof: a thin oversailing slab with a bronze fascia, sedum and solar panels on it.
    m.box("bronze", (px0 - 0.4, py0 - 0.8, zt), (px1 + 0.4, py1 + 0.3, zt + 0.3), skip=())
    m.poly("sedum", [(px0 - 0.3, py0 - 0.7, zt + 0.301), (px1 + 0.3, py0 - 0.7, zt + 0.301), (px1 + 0.3, py1 + 0.2, zt + 0.301), (px0 - 0.3, py1 + 0.2, zt + 0.301)], out=Z)
    zs = zt + 0.3
    for row in range(2):
        y = py0 + 0.6 + row * 2.2
        for col in range(5):
            x = px0 + 0.4 + col * 2.0
            a, b = Vector((x, y, zs + 0.15)), Vector((x + 1.8, y, zs + 0.15))
            lift = 0.55
            m.poly("solar", [a, b, b + Vector((0, 1.0, lift)), a + Vector((0, 1.0, lift))], out=(0, -0.48, 0.88))
            m.poly("alu", [a, a + Vector((0, 1.0, lift)), b + Vector((0, 1.0, lift)), b], out=(0, 0.48, -0.88))
            for xx in (x + 0.1, x + 1.7):
                m.box("alu", (xx - 0.02, y + 0.9, zs), (xx + 0.02, y + 0.94, zs + 0.15 + lift))
    # Vents from the flats below, a lift overrun.
    for x in (-5.8, 5.8):
        m.cyl("alu", x, Y1 - 0.8, 0.12, zr, zr + 0.9, seg=10)
        m.cyl("alu", x, Y1 - 0.8, 0.2, zr + 0.9, zr + 1.0, seg=10, r1=0.05)
