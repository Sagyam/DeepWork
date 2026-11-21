# O3, brutalist office: a late-1960s office block in board-marked concrete
# on a 1.8 m grid. Every storey is an egg-crate of precast fins and ledges
# standing out 0.3 m, and in each box a window set deep behind splayed
# reveals, the sill sloping out to shed the rain, bronze-framed glass in two
# lights. The upper storeys ride on a deep transfer beam carrying the name in
# cast letters, held up by tapered pilotis over a recessed glass lobby. Two
# windowless service towers (stairs, lifts, risers) stand out of the sides,
# a slot window up each, and rise past the roof as plant rooms with louvres
# under a heavy lid. On the roof: a deep attic band, the lift overrun, twin
# exhaust flues, condensers and a warning light. The app tints the concrete,
# the glass and the bronze, and picks the name, per building.
#
# Pieces (base at the origin, stacked by the app):
#   ground   5.0 m: pilotis, lobby glass, transfer beam with the name, towers
#   floor    3.7 m: a typical storey, 10.8 x 10.8 m plus fins and towers
#   roof     attic band, roof plant, the towers' tops
import math

import numpy as np

from lib import Model, Side, Z, fbm, glazing, new_id, normals, pane, sides, srgb

ID = "o3"
B = 1.8  # planning grid
X = 5.4  # the body's half width and half depth, to the facade plane
FIN = 0.3  # how far fins, ledges and the beam stand out of the facade plane
G = 5.0  # ground storey
BEAM = 1.2  # the transfer beam's depth, under the first floor
FL = 3.7  # typical storeys
LEDGE = 0.25  # the ledge at each floor line
SILL, HEAD = 1.0, 0.32  # spandrel up to the window, the head under the next ledge
D = 0.5  # how deep the glass is set behind the facade plane
SPLAY = 0.26  # how much the reveals narrow from the facade to the glass
TW, TY0, TY1 = 1.5, 0.0, 3.6  # the towers: how far out of the sides, front and back
TOWER = 4.4  # how far the towers rise above the roof slab
ATTIC = 1.6  # the attic band's height above the roof slab
YL = -X + B  # the lobby glass, behind the pilotis


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    storey(M.m, G)
    M.piece("roof", (0, 0, G + FL))
    roof(M.m, G + FL)
    M.export(out, bake)


def grid(u0, u1):
    n = round((u1 - u0) / B)
    return [u0 + i * B for i in range(n + 1)]


def faces(m):
    """The body's four facades at the facade plane: front (-y), right, back, left."""
    return sides(m, 2 * X, 2 * X)


def bays(name):
    """The (a, b) bays of a facade that are windows: the sides lose the bays the towers cover."""
    lines = grid(-X, X)
    out = list(zip(lines, lines[1:]))
    if name == "right":  # u = y
        return [(a, b) for a, b in out if b <= TY0 + 1e-6 or a >= TY1 - 1e-6]
    if name == "left":  # u = -y
        return [(a, b) for a, b in out if b <= -TY1 + 1e-6 or a >= -TY0 - 1e-6]
    return out


# ---- the egg-crate storey -------------------------------------------------------------


def window(F, a, b, z):
    """One bay of a storey: the spandrel and head faces between the fins, the
    four splayed reveals, and the bronze-framed glass at the back of them."""
    m = F.m
    f = 0.12  # the fins' half width
    ua, ub = a + f, b - f
    zo0, zo1 = z + SILL, z + FL - HEAD
    ia, ib = ua + SPLAY, ub - SPLAY
    zi0, zi1 = zo0 + 0.16, zo1 - 0.14
    F.quad("boardform", ua, ub, z + LEDGE, zo0)
    F.quad("boardform", ua, ub, zo1, z + FL)
    p = F.p
    # The reveals: sill sloping out, head and cheeks splayed.
    m.poly("boardform", [p(ua, zo0, 0), p(ub, zo0, 0), p(ib, zi0, -D), p(ia, zi0, -D)], out=Z + F.n * 0.3)
    m.poly("boardform", [p(ua, zo1, 0), p(ia, zi1, -D), p(ib, zi1, -D), p(ub, zo1, 0)], out=-Z + F.n * 0.3)
    m.poly("boardform", [p(ua, zo0, 0), p(ia, zi0, -D), p(ia, zi1, -D), p(ua, zo1, 0)], out=F.t + F.n * 0.3)
    m.poly("boardform", [p(ub, zo0, 0), p(ub, zo1, 0), p(ib, zi1, -D), p(ib, zi0, -D)], out=-F.t + F.n * 0.3)
    glazing(F, ia, ib, zi0, zi1, lights=2, D=D, fr="mullion", glass="officeglass")
    # A slim opening light's handle bar at the transom height, inside.
    F.box("mullion", ia + 0.05, ib - 0.05, zi0 + 0.9, zi0 + 0.95, -D - 0.03, -D + 0.04)


def fin(F, u, z0, z1):
    F.box("boardform", u - 0.12, u + 0.12, z0, z1, 0, FIN)


def corner(m, sx, sy, z0, z1):
    """The corner pier where two facades' end fins meet."""
    x, y = sx * X, sy * X
    m.box("boardform", (x - sx * 0.12, y - sy * 0.12, z0), (x + sx * FIN, y + sy * FIN, z1), skip=("z0", "z1"))


def tower(m, z0, z1, slot=True, door=False):
    """The service towers' segments from z0 to z1, out of both sides: board
    concrete, a slot window up the outer face, a joint at each floor line."""
    for sx in (-1, 1):
        x0, x1 = sorted((sx * X, sx * (X + TW)))
        m.box("boardform", (x0, TY0, z0), (x1, TY1, z1), skip=("z0", "z1", "x0", "x1"))
        F = Side(m, (sx * (X + TW), (TY0 + TY1) / 2, 0), (0, sx, 0), (sx, 0, 0))
        h = (TY1 - TY0) / 2
        holes = []
        if slot:
            holes.append((-0.25 + 0.6, 0.25 + 0.6, z0 + 0.6, z1 - 0.3))
        if door:
            holes.append((-1.1, 0.1, z0 + 0.15, z0 + 2.45))
        F.wall("boardform", -h, h, z0, z1, holes, depth=0.25)
        if slot:
            glazing(F, *holes[0], D=0.2, fr="mullion", glass="doorglass")
        if door:
            steel_door(F, -1.1, 0.1, z0 + 0.15, z0 + 2.45, 0.25)
            F.box("lamp", -0.65, -0.35, z0 + 2.65, z0 + 2.77, 0, 0.12)
        # A drip groove at the floor line: a thin dark joint in the concrete.
        F.box("dark", -h + 0.01, h - 0.01, z0 + 0.0, z0 + 0.03, -0.01, 0.003, skip=("back",))


def storey(m, z):
    S = faces(m)
    for name, F in S.items():
        for a, b in bays(name):
            window(F, a, b, z)
        for u in grid(-X, X)[1:-1]:
            if name in ("right", "left"):
                lo, hi = (TY0, TY1) if name == "right" else (-TY1, -TY0)
                if lo + 1e-6 < u < hi - 1e-6:
                    continue
            fin(F, u, z, z + FL)
        # The ledge at the floor line, the whole facade long.
        F.box("boardform", -X, X, z, z + LEDGE, 0, FIN, skip=("back", "left", "right"))
    for sx in (-1, 1):
        for sy in (-1, 1):
            corner(m, sx, sy, z, z + FL)
    tower(m, z, z + FL)
    # The slab's underside, seen only when the storey above is gone.
    m.poly("dark", [(-X, -X, z + FL - 0.02), (X, -X, z + FL - 0.02), (X, X, z + FL - 0.02), (-X, X, z + FL - 0.02)], out=-Z)


# ---- ground storey -----------------------------------------------------------------


def piloti(m, x, y, z0, z1, wb=0.5, wt=0.9):
    """A tapered column, square, wider at the head where it takes the beam."""
    pts = lambda w, z: [(x - w / 2, y - w / 2, z), (x + w / 2, y - w / 2, z), (x + w / 2, y + w / 2, z), (x - w / 2, y + w / 2, z)]  # noqa: E731
    lo, hi = pts(wb, z0), pts(wt, z1)
    for i in range(4):
        j = (i + 1) % 4
        mx = (lo[i][0] + lo[j][0]) / 2 - x
        my = (lo[i][1] + lo[j][1]) / 2 - y
        m.poly("boardform", [lo[i], lo[j], hi[j], hi[i]], out=(mx, my, 0.1))


def steel_door(F, a, b, c, e, d):
    """A flush steel door in a frame, with a push bar."""
    F.quad("ac", a + 0.05, b - 0.05, c, e - 0.05, -d + 0.03)
    F.box("mullion", a, a + 0.05, c, e, -d, -d + 0.06)
    F.box("mullion", b - 0.05, b, c, e, -d, -d + 0.06)
    F.box("mullion", a, b, e - 0.05, e, -d, -d + 0.06)
    F.box("dark", a + 0.15, b - 0.15, c + 0.95, c + 1.0, -d + 0.03, -d + 0.07)


def swing_door(F, a, b, c, e, wid):
    """A glass door in a heavy bronze frame, a push plate across it."""
    pane(F, "doorglass", a, b, c, e, a + 0.08, b - 0.08, c + 0.2, e - 0.08, -0.03, wid)
    F.box("mullion", a, a + 0.08, c, e, -0.06, 0.02)
    F.box("mullion", b - 0.08, b, c, e, -0.06, 0.02)
    F.box("mullion", a + 0.08, b - 0.08, c, c + 0.2, -0.06, 0.02)
    F.box("mullion", a + 0.08, b - 0.08, e - 0.08, e, -0.06, 0.02)
    F.box("mullion", a + 0.15, b - 0.15, c + 1.0, c + 1.1, 0.02, 0.06, skip=())


def ground(M):
    m = M.m
    c = 0.15
    zb = G - BEAM  # the beam's underside, the soffit over the undercroft
    # A concrete podium a step up from the plaza, out to the fins' line.
    m.box("concrete", (-X - FIN, -X - FIN, 0), (X + FIN, X + FIN, c), skip=("z0",))
    # The transfer beam round the body, the name cast in its front.
    S = faces(m)
    for name, F in S.items():
        F.box("boardform", -X - FIN, X + FIN, zb, G, -0.4, FIN, skip=("back", "left", "right"))
        F.box("dark", -X, X, zb, zb + 0.04, FIN - 0.02, FIN + 0.005, skip=("back", "left", "right", "top"))
    # The name, a decal so the bake leaves the beam alone.
    S["front"].quad("towername", -4.5, 4.5, zb + 0.32, G - 0.32, FIN + 0.005, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    # Pilotis along the front and at the front corners of the undercroft.
    for x in (-X + 0.15, -B, B, X - 0.15):
        piloti(m, x, -X + 0.15, c, zb)
    # The soffit over the undercroft, coffered by beams on the grid, with downlights.
    m.poly("boardform", [(-X - FIN, -X - FIN, zb), (X + FIN, -X - FIN, zb), (X + FIN, YL, zb), (-X - FIN, YL, zb)], out=-Z)
    for x in grid(-X, X)[1:-1]:
        m.box("boardform", (x - 0.15, -X - FIN, zb - 0.45), (x + 0.15, YL, zb), skip=("z1",))
    for x0, x1 in zip(grid(-X, X), grid(-X, X)[1:]):
        m.cyl("lamp", (x0 + x1) / 2, (-X + YL) / 2, 0.1, zb - 0.02, zb, seg=10, top=False, bottom=True)
    lobby(m, c, zb)
    flanks(m, c, zb)
    back(m, c, zb)
    tower(m, 0, G, slot=False, door=True)
    for sx in (-1, 1):
        for sy in (-1, 1):
            corner(m, sx, sy, zb, G)
    m.poly("dark", [(-X, -X, G - 0.02), (X, -X, G - 0.02), (X, X, G - 0.02), (-X, X, G - 0.02)], out=-Z)


def lobby(m, c, e):
    """The lobby's glass wall behind the pilotis: tall panes in bronze frames
    on the grid, a pair of doors in the middle bay under a transom."""
    F = Side(m, (0, YL, 0), (1, 0, 0), (0, -1, 0))
    lines = grid(-X, X)
    door = 2.6
    for a, b in zip(lines, lines[1:]):
        wid = new_id()
        if abs(a + B) < 1e-6 or abs(a) < 1e-6:
            pane(F, "doorglass", a, b, c, e, a + 0.04, b - 0.04, door + 0.1, e, -0.02, wid)
            F.box("mullion", a, b, door, door + 0.1, -0.05, 0.08)
            swing_door(F, a + 0.04, a + B / 2, c, door, wid)
            swing_door(F, a + B / 2, b - 0.04, c, door, wid)
        else:
            pane(F, "doorglass", a, b, c, e, a + 0.04, b - 0.04, c, e, -0.02, wid)
            F.box("mullion", a, b, door + 0.4, door + 0.48, -0.04, 0.05)
    for u in lines:
        F.box("mullion", u - 0.05, u + 0.05, c, e, -0.05, 0.1)
    F.box("mullion", -X, X, c, c + 0.1, -0.04, 0.06)
    # The lobby's ceiling seen over the doors, a concrete bench along the glass.
    m.poly("boardform", [(-X, YL, e), (X, YL, e), (X, YL + 0.5, e), (-X, YL + 0.5, e)], out=-Z)
    for x in (-3.6, 3.6):
        m.box("boardform", (x - 1.3, YL - 0.9, c), (x + 1.3, YL - 0.4, c + 0.45), skip=("z0",))


def flanks(m, c, zb):
    """The ground storey's sides behind the undercroft: board concrete with a
    tall window in each bay clear of the towers."""
    S = faces(m)
    for name in ("right", "left"):
        F = S[name]
        lo, hi = (YL, X) if name == "right" else (-X, -YL)
        holes = []
        for a, b in zip(grid(-X, X), grid(-X, X)[1:]):
            if a < lo - 1e-6 or b > hi + 1e-6:
                continue
            in_tower = (name == "right" and a < TY1 - 1e-6 and b > TY0 + 1e-6) or (name == "left" and a < -TY0 - 1e-6 and b > -TY1 + 1e-6)
            if not in_tower:
                holes.append((a + 0.4, b - 0.4, 0.9, zb - 0.4))
        F.wall("boardform", lo, hi, 0, zb, holes, depth=0.3)
        for h in holes:
            glazing(F, *h, D=0.25, fr="mullion", glass="officeglass")
        # The open end of the side wall, facing the undercroft.
        x0, x1 = sorted((X, X - 0.3) if name == "right" else (-X, -X + 0.3))
        m.poly("boardform", [(x0, YL, 0), (x1, YL, 0), (x1, YL, zb), (x0, YL, zb)], out=(0, -1, 0))


def back(m, c, zb):
    """The service side: a roller shutter to the loading bay, a fire exit,
    an intake louvre, a window."""
    F = Side(m, (0, X, 0), (-1, 0, 0), (0, 1, 0))  # u = -x
    shutter = (-4.8, -1.8, 0, 3.0)
    fire = (1.2, 2.2, c, 2.45)
    louvre = (3.0, 4.6, 1.4, 2.8)
    F.wall("boardform", -X, X, 0, zb, [shutter, fire, louvre], depth=0.3)
    F.quad("blades", shutter[0], shutter[1], 0, shutter[3], -0.25, uvs=[(0, 0), (3, 0), (3, 3.0), (0, 3.0)])
    for u in (shutter[0], shutter[1] - 0.08):
        F.box("mullion", u, u + 0.08, 0, shutter[3], -0.3, -0.15)
    F.box("mullion", shutter[0] - 0.1, shutter[1] + 0.1, shutter[3], shutter[3] + 0.4, 0, 0.3, skip=("back",))
    for u in (shutter[0] - 0.35, shutter[1] + 0.15):
        F.box("concrete", u, u + 0.2, 0, 1.0, 0, 0.25, skip=("back", "bottom"))
    steel_door(F, *fire, 0.3)
    F.quad("blades", louvre[0], louvre[1], louvre[2], louvre[3], -0.15, uvs=[(0, 0), (1.6, 0), (1.6, 1.4), (0, 1.4)])
    m.box("lamp", (-1.85, X, 2.65), (-1.55, X + 0.12, 2.77))


# ---- roof ------------------------------------------------------------------------------


def roof(m, z):
    """The attic band, the roof and its plant, and the towers' tops."""
    S = faces(m)
    top = z + ATTIC
    for name, F in S.items():
        # The attic band stands out at the fins' line, a recessed shadow joint at its foot.
        F.box("boardform", -X - FIN, X + FIN, z + 0.2, top, -0.3, FIN, skip=("back", "left", "right", "bottom"))
        F.box("dark", -X, X, z, z + 0.2, -0.3, FIN - 0.12, skip=("back", "left", "right", "top"))
        F.quad("boardform", -X + 0.3, X - 0.3, z + 0.12, top, -0.3, out=-F.n)
        # The band's underside, where it oversails the shadow joint.
        p = F.p
        m.poly("boardform", [p(-X - FIN, z + 0.2, FIN), p(X + FIN, z + 0.2, FIN), p(X + FIN, z + 0.2, FIN - 0.12), p(-X - FIN, z + 0.2, FIN - 0.12)], out=-Z)
    for sx in (-1, 1):
        for sy in (-1, 1):
            corner(m, sx, sy, z, z + 0.2)
    base = z + 0.12
    m.poly("roof", [(-X + 0.3, -X + 0.3, base), (X - 0.3, -X + 0.3, base), (X - 0.3, X - 0.3, base), (-X + 0.3, X - 0.3, base)], out=Z)
    towers_top(m, z)
    # The lift overrun at the back, a door onto the roof.
    x0, x1, y0, y1 = -1.8, 1.8, 1.6, 4.4
    h = 3.2
    m.box("boardform", (x0, y0, base), (x1, y1, base + h), skip=("z0",))
    m.box("boardform", (x0 - 0.15, y0 - 0.15, base + h), (x1 + 0.15, y1 + 0.15, base + h + 0.3), skip=())
    O = Side(m, (0, y0, 0), (1, 0, 0), (0, -1, 0))
    steel_door(O, -0.5, 0.5, base, base + 2.2, -0.02)
    m.box("lamp", (-0.15, y0 - 0.12, base + 2.4), (0.15, y0, base + 2.52))
    # Twin exhaust flues, steel, on a concrete plinth by the overrun.
    for fx in (-3.0, -2.2):
        m.box("concrete", (fx - 0.4, 3.2, base), (fx + 0.4, 4.0, base + 0.4), skip=("z0",))
        m.cyl("ac", fx, 3.6, 0.28, base + 0.4, top + 3.2, seg=14, top=False)
        m.cyl("dark", fx, 3.6, 0.26, top + 3.15, top + 3.2, seg=14)
        m.cyl("ac", fx, 3.6, 0.32, top + 3.0, top + 3.2, seg=14, top=False)
    # Condensers on steel frames at the front, behind the attic band.
    for k in range(4):
        x = -3.9 + k * 2.2
        y = -3.4
        m.box("iron", (x - 0.85, y - 0.55, base), (x + 0.85, y + 0.55, base + 0.25), skip=("z0",))
        m.box("ac", (x - 0.8, y - 0.5, base + 0.25), (x + 0.8, y + 0.5, base + 1.05), skip=("z0",))
        m.cyl("dark", x, y, 0.32, base + 1.05, base + 1.06, seg=14)
    # Ducts from the condensers to the overrun.
    m.box("ac", (-4.5, -2.6, base + 0.3), (4.5, -2.2, base + 0.7))
    m.box("ac", (-0.2, -2.2, base + 0.3), (0.2, y0, base + 0.7))


def towers_top(m, z):
    """The towers above the roof: the concrete rises to a heavy oversailing
    lid; under it, a band of louvres round the plant room. A warning light
    on the right tower."""
    t = z + TOWER
    lv0, lv1 = t - 2.0, t - 0.9
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (X - 0.6), sx * (X + TW)))
        # Below the louvres: solid, the slot window carried on up.
        m.box("boardform", (x0, TY0, z), (x1, TY1, lv0), skip=("z0", "z1"))
        # The louvre band, recessed, with concrete posts at the corners.
        for (ax, ay), (bx, by), out in (((x0, TY0), (x1, TY0), (0, -1, 0)), ((x1, TY0), (x1, TY1), (1, 0, 0)), ((x1, TY1), (x0, TY1), (0, 1, 0)), ((x0, TY1), (x0, TY0), (-1, 0, 0))):
            o = 0.15
            ax2, ay2 = ax - out[0] * o, ay - out[1] * o
            bx2, by2 = bx - out[0] * o, by - out[1] * o
            L = math.hypot(bx - ax, by - ay)
            m.poly("blades", [(ax2, ay2, lv0), (bx2, by2, lv0), (bx2, by2, lv1), (ax2, ay2, lv1)], out=out, uvs=[(0, 0), (L, 0), (L, lv1 - lv0), (0, lv1 - lv0)])
        for cx in (x0, x1):
            for cy in (TY0, TY1):
                m.box("boardform", (cx - 0.25, cy - 0.25, lv0), (cx + 0.25, cy + 0.25, lv1), skip=("z0", "z1"))
        # The lid: oversailing, deep, chamfered underneath.
        m.box("boardform", (x0 - 0.3, TY0 - 0.3, lv1 + 0.25), (x1 + 0.3, TY1 + 0.3, t), skip=("z0",))
        lo = [(x0, TY0, lv1), (x1, TY0, lv1), (x1, TY1, lv1), (x0, TY1, lv1)]
        hi = [(x0 - 0.3, TY0 - 0.3, lv1 + 0.25), (x1 + 0.3, TY0 - 0.3, lv1 + 0.25), (x1 + 0.3, TY1 + 0.3, lv1 + 0.25), (x0 - 0.3, TY1 + 0.3, lv1 + 0.25)]
        for i in range(4):
            j = (i + 1) % 4
            mx = (lo[i][0] + lo[j][0]) / 2 - (x0 + x1) / 2
            my = (lo[i][1] + lo[j][1]) / 2 - (TY0 + TY1) / 2
            m.poly("boardform", [lo[i], lo[j], hi[j], hi[i]], out=(mx, my, -1))
        m.poly("dark", lo, out=-Z)
    cx, cy = X + TW / 2, (TY0 + TY1) / 2
    m.cyl("ac", cx, cy, 0.06, t, t + 1.4, seg=8)
    m.cyl("beacon", cx, cy, 0.1, t + 1.4, t + 1.62, seg=8)


# ---- board-marked concrete -------------------------------------------------------------


def boardform_tex(t, n=1024):
    """Board-marked concrete, cast against rough-sawn planks: boards 0.15 m
    tall laid horizontally, butt joints staggered, each board's grain and
    tone printed in the concrete, thin ridges where boards met, tie holes on
    a 0.6 m grid, bug holes; tile 2.4 m. Pale grey for the app to tint."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    u, v = x / n * 2.4, y / n * 2.4
    rows = 16
    row = np.floor(v / 0.15).astype(int)
    fv = v / 0.15 - row
    rng = np.random.default_rng(301)
    # Each row's butt joint: one per row across the tile, at a random place.
    joint_u = rng.random(rows) * 2.4
    du = (u - joint_u[row]) % 2.4
    side = (du < 1.2).astype(int)
    board = row * 2 + side
    tone = rng.random(rows * 2)[board]
    sink = rng.random(rows * 2)[board]
    off = (rng.random(rows * 2)[board] * n).astype(int)
    grain = fbm(n, 4, 6, 302, stretch=(1, 12))
    grain = grain[(y.astype(int) + off // 3) % n, (x.astype(int) + off) % n]
    fine = fbm(n, 128, 3, 303)
    blot = fbm(n, 6, 5, 304)
    # Distance to the board's edges, in metres: ridges where the boards met.
    ev = np.minimum(fv, 1 - fv) * 0.15
    eu = np.minimum(du, 2.4 - du)
    eu = np.minimum(eu, np.abs(du - 1.2))
    ridge = np.exp(-(ev / 0.0025) ** 2) + 0.7 * np.exp(-(eu / 0.0025) ** 2)
    # Tie holes: plugged cones, 25 mm across, every 0.6 m, between board edges.
    tu, tv = (u % 0.6) - 0.3, (v % 0.6) - 0.3
    tie = np.hypot(tu, tv)
    hole = tie < 0.0125
    rim = (tie >= 0.0125) & (tie < 0.02)
    bugs = fbm(n, 256, 2, 305) > 0.78
    col = np.ones((n, n, 3), np.float32) * srgb(204, 202, 196)
    col *= (0.9 + 0.07 * tone + 0.16 * (grain - 0.5) + 0.05 * (fine - 0.5) + 0.1 * (blot - 0.5))[..., None]
    col *= (1 + 0.06 * ridge)[..., None]
    col[bugs] *= 0.78
    col[rim] *= 0.88
    col[hole] = srgb(120, 118, 114) * (0.9 + 0.1 * fine[hole])[..., None]
    h = 0.5 - 0.15 * sink + 0.35 * (grain - 0.5) + 0.45 * ridge + 0.05 * fine
    h = np.where(hole, 0.1, h) - 0.25 * bugs
    t.save("boardform_col", col)
    t.save("boardform_nrm", normals(h, 4.0))


TEXTURES = (boardform_tex,)
