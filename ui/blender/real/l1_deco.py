# L1, art deco skyscraper: a setback office tower of about 1930 on its own
# lot, 14.4 m square on a 1.8 m bay. Sawn limestone piers run unbroken from
# the pavement to the crown between recessed bays of steel windows, cast
# chevron spandrel panels between the storeys; the corners are notched. The
# ground storey stands on a polished black granite plinth: shop windows and
# a mezzanine in bronze frames, and in the middle a portal stepped back in
# three orders to bronze doors under a sunburst grille, the building's name
# over it between two lanterns. The tower steps back twice (14.4, 10.8, 7.2
# m) behind parapets of cast panels, the piers rising through them as
# stepped finials and the corners as ziggurat pylons, floodlights on the
# terraces. The crown climbs in two floodlit stages of tall lit windows,
# stainless fins on the upper one's corners, to an octagonal stainless drum
# and a 14 m spire with an aircraft light. The app tints the stone and the
# metalwork (bronze, black, aluminium, green) and picks the name.
#
# Pieces (base at the origin, stacked by the app):
#   ground  6.0 m: plinth, shopfronts, mezzanine, portal, the name
#   floor1  3.5 m: a storey of the lower tier, 14.4 m square, 8 bays a side
#   ledge1  its parapet and the terrace round the middle tier (no height)
#   floor2  3.5 m: the middle tier, 10.8 m, 6 bays
#   ledge2  the same round the upper tier
#   floor3  3.5 m: the upper tier, 7.2 m, 4 bays
#   crown   the upper tier's parapet, the two lit stages, the drum, the spire
import math

from lib import Model, Side, Z, glazing, new_id, pane, sides

ID = "l1"
B = 1.8  # bay
X1, X2, X3 = 7.2, 5.4, 3.6  # the tiers' half widths
G = 6.0  # ground storey
FL = 3.5  # typical storeys
SILL, HEAD = 0.95, 3.0  # window sill and head above the floor
SPAN = FL - HEAD + SILL  # one spandrel panel: a window's head to the sill above
R = 0.3  # how deep the bays are recessed behind the piers' faces
PW = 0.6  # piers
CW = 0.8  # the corner piers, each way
NOTCH = 0.16  # the notch out of each corner
PH = 1.3  # parapets


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    z = G
    M.piece("floor1", (0, 0, z))
    storey(M.m, X1, z)
    z += FL
    M.piece("ledge1", (0, 0, z))
    ledge(M.m, X1, X2, z)
    M.piece("floor2", (0, 0, z))
    storey(M.m, X2, z)
    z += FL
    M.piece("ledge2", (0, 0, z))
    ledge(M.m, X2, X3, z)
    M.piece("floor3", (0, 0, z))
    storey(M.m, X3, z)
    z += FL
    M.piece("crown", (0, 0, z))
    crown(M.m, z)
    M.export(out, bake)


def lines(X):
    n = round(2 * X / B)
    return [-X + i * B for i in range(n + 1)]


def bays(X, w=CW):
    """(a, b) of each bay between the piers' sides; the end bays stop at the corner piers (w wide)."""
    ls = lines(X)
    n = len(ls) - 1
    return [(ls[i] + (w if i == 0 else PW / 2), ls[i + 1] - (w if i == n - 1 else PW / 2)) for i in range(n)]


# ---- the shaft --------------------------------------------------------------------------


def spandrel(F, a, b, z0, z1, zs, w=-R):
    """Part of a spandrel panel on facade F between z0 and z1; a whole panel runs
    from one storey's window head to the next storey's sill, `zs` the storey the
    part belongs to, so the parts of stacked pieces line up."""
    v = lambda z: (z - (zs - (FL - HEAD))) / SPAN  # noqa: E731
    F.quad("deco", a, b, z0, z1, w, uvs=[(0, v(z0)), (1, v(z0)), (1, v(z1)), (0, v(z1))])


def panel(F, a, b, z0, z1, w, role="deco"):
    """A whole cast panel."""
    F.quad(role, a, b, z0, z1, w, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])


def window(F, a, b, c, e, glass="decoglass", w=-R, transom=0.7, wid=None):
    """A steel window in bronze filling a bay from c to e: frame, a transom, a
    mullion if it is wide; the glass just behind the recess."""
    wid = wid or new_id()
    gw = w - 0.06
    fr = "bronze"
    pane(F, glass, a, b, c, e, a, b, c, e, gw, wid)
    F.box(fr, a, a + 0.06, c, e, gw - 0.01, w + 0.02, skip=("back", "top", "bottom", "left"))
    F.box(fr, b - 0.06, b, c, e, gw - 0.01, w + 0.02, skip=("back", "top", "bottom", "right"))
    F.box(fr, a + 0.06, b - 0.06, e - 0.07, e, gw - 0.01, w + 0.02, skip=("back", "left", "right", "top"))
    F.box(fr, a + 0.06, b - 0.06, c, c + 0.08, gw - 0.01, w + 0.05, skip=("back", "left", "right", "bottom"))
    if transom:
        t = c + (e - c) * transom
        F.box(fr, a + 0.06, b - 0.06, t - 0.03, t + 0.03, gw, gw + 0.04, skip=("back", "left", "right"))
    if b - a > 1.0:
        u = (a + b) / 2
        F.box(fr, u - 0.03, u + 0.03, c + 0.08, e - 0.07, gw, gw + 0.04, skip=("back", "top", "bottom"))
    return wid


def pier(F, u, z0, z1, role="cladstone"):
    F.box(role, u - PW / 2, u + PW / 2, z0, z1, -R, 0, skip=("back", "top", "bottom"))


def corners(m, X, z0, z1, role="cladstone", k=0.0, cw=CW, ends=("z0", "z1")):
    """The four notched corner piers of a block X either side of the centre,
    inset k (a pylon's steps)."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            a, b, n = X - cw + k, X - k, X - k - NOTCH
            m.box(role, (sx * a, sy * a, z0), (sx * n, sy * b, z1), skip=ends)
            m.box(role, (sx * n, sy * a, z0), (sx * b, sy * n, z1), skip=ends)


def storey(m, X, z):
    """A typical storey of a tier: piers, recessed bays of windows over spandrels, notched corners."""
    S = sides(m, 2 * X, 2 * X)
    for F in S.values():
        for a, b in bays(X):
            spandrel(F, a, b, z, z + SILL, z)
            window(F, a, b, z + SILL, z + HEAD)
            spandrel(F, a, b, z + HEAD, z + FL, z)
        for u in lines(X)[1:-1]:
            pier(F, u, z, z + FL)
    corners(m, X, z, z + FL)
    # The slab's underside, seen only when the storey above is gone.
    i = X - R
    m.poly("dark", [(-i, -i, z + FL - 0.02), (i, -i, z + FL - 0.02), (i, i, z + FL - 0.02), (-i, i, z + FL - 0.02)], out=-Z)


# ---- ground storey -------------------------------------------------------------------------


def ground(M):
    m = M.m
    S = sides(m, 2 * X1, 2 * X1)
    for name, F in S.items():
        for i, (a, b) in enumerate(bays(X1)):
            if name == "front" and i in (3, 4):
                continue  # the portal
            if name == "back":
                back_bay(F, a, b, i)
            else:
                shop_bay(F, a, b)
        for u in lines(X1)[1:-1]:
            if name == "front" and abs(u) < 2.0:
                continue
            pier(F, u, 0.6, G)
            F.box("jet", u - PW / 2 - 0.03, u + PW / 2 + 0.03, 0, 0.6, -R, 0.03, skip=("back", "bottom"))
    corners(m, X1, 0.6, G)
    corners(m, X1 + 0.03, 0, 0.6, role="jet", cw=CW + 0.03, ends=("z0",))
    portal(m, S["front"])
    i = X1 - R
    m.poly("dark", [(-i, -i, G - 0.02), (i, -i, G - 0.02), (i, i, G - 0.02), (-i, i, G - 0.02)], out=-Z)


def shop_bay(F, a, b):
    """A shop window over a granite stallriser, a cast panel, the mezzanine's window, the spandrel."""
    F.quad("jet", a, b, 0, 0.6, -R + 0.02)
    F.box("jet", a, b, 0.55, 0.62, -R, -R + 0.1, skip=("back", "left", "right", "bottom"))
    window(F, a, b, 0.6, 3.7, glass="shopglass", transom=0.82)
    panel(F, a, b, 3.7, 4.3, -R)
    window(F, a, b, 4.3, G - (FL - HEAD), transom=0)
    spandrel(F, a, b, G - (FL - HEAD), G, G - FL)


def back_bay(F, a, b, i):
    """The service side: stone with small office windows, the service door in the middle."""
    W = Side(F.m, F.p(0, 0, -R), F.t, F.n)
    if i in (3, 4):
        door = (a + 0.15, b - 0.15, 0, 2.6) if i == 3 else None
        holes = [door] if door else []
        holes.append((a + 0.2, b - 0.2, 3.2, 4.8))
        W.wall("cladstone", a, b, 0, G, holes, depth=0.15)
        if door:
            W.quad("bronze", door[0], door[1], 0, 2.6, -0.12)
            W.box("brass", door[1] - 0.2, door[1] - 0.16, 1.0, 1.15, -0.12, -0.06, skip=())
            W.box("lamp", (a + b) / 2 - 0.15, (a + b) / 2 + 0.15, 2.75, 2.85, 0, 0.12, skip=("back",))
        glazing(W, a + 0.2, b - 0.2, 3.2, 4.8, D=0.12, fr="bronze", glass="decoglass")
        return
    W.wall("cladstone", a, b, 0, G, [(a + 0.2, b - 0.2, 2.2, 4.8)], depth=0.15)
    glazing(W, a + 0.2, b - 0.2, 2.2, 4.8, D=0.12, fr="bronze", glass="decoglass")
    W.quad("jet", a, b, 0, 0.6, 0.02)


def portal(m, F):
    """The entrance: a block of stone across the two middle bays, the opening
    stepped back in three orders to bronze doors under a sunburst grille; the
    name over it, a lantern either side, a granite step."""
    h = 2.025
    orders = [(0.0, 1.5, 5.1), (-0.15, 1.3, 4.9), (-0.3, 1.1, 4.7)]
    outer = Side(m, F.p(0, 0, 0), F.t, F.n)
    outer.wall("cladstone", -h, h, 0, G, [(-1.5, 1.5, 0, 5.1)], depth=0.15)
    outer.box("cladstone", -h, h, 0.6, G, -R, 0, skip=("back", "front", "top", "bottom"))
    for u0, u1 in ((-h - 0.03, -1.5), (1.5, h + 0.03)):
        outer.box("jet", u0, u1, 0, 0.6, -R, 0.03, skip=("back", "bottom"))
    for (w, hw, top), (_, hw2, top2) in zip(orders, orders[1:]):
        W = Side(m, F.p(0, 0, w - 0.15), F.t, F.n)
        W.wall("cladstone", -hw, hw, 0, top, [(-hw2, hw2, 0, top2)], depth=0.15 if hw2 > 1.2 else 0.6)
    # Doors and the grille, 0.9 m in.
    D = Side(m, F.p(0, 0, -0.9), F.t, F.n)
    wid = new_id()
    door = 2.6
    pane(D, "doorglass", -1.1, 1.1, 0, 4.7, -1.1, 1.1, 0, 4.7, -0.02, wid)
    for a, b in ((-1.1, -0.05), (0.05, 1.1)):
        for u0, u1 in ((a, (a + b) / 2), ((a + b) / 2, b)):
            D.box("bronze", u0, u0 + 0.08, 0, door, -0.03, 0.04, skip=("back", "top", "bottom"))
            D.box("bronze", u1 - 0.08, u1, 0, door, -0.03, 0.04, skip=("back", "top", "bottom"))
            D.box("bronze", u0 + 0.08, u1 - 0.08, 0, 0.3, -0.03, 0.04, skip=("back", "bottom"))
            D.box("brass", (u0 + u1) / 2 - 0.15, (u0 + u1) / 2 + 0.15, 1.0, 1.06, 0.04, 0.09, skip=("back",))
    D.box("bronze", -0.05, 0.05, 0, door, -0.03, 0.05, skip=("back", "bottom"))
    D.box("bronze", -1.1, 1.1, door, door + 0.16, -0.03, 0.06, skip=("back",))
    # The sunburst: rays from the middle of the transom bar to the opening's edge.
    cz = door + 0.16
    for k in range(11):
        a = math.pi * (k + 0.5) / 11
        dx, dz = math.cos(a), math.sin(a)
        s = min(1.1 / max(abs(dx), 1e-6), (4.7 - cz) / max(dz, 1e-6))
        m.strut("bronze", D.p(0, cz, 0.0), D.p(dx * s, cz + dz * s, 0.0), 0.035)
    D.box("bronze", -0.35, 0.35, cz, cz + 0.35, -0.03, 0.05, skip=("back",))
    for u0, u1, z0, z1 in ((-1.1, -1.04, cz, 4.7), (1.04, 1.1, cz, 4.7), (-1.1, 1.1, 4.64, 4.7)):
        D.box("bronze", u0, u1, z0, z1, -0.03, 0.04, skip=("back",))
    # The step and the vestibule floor.
    F.box("jet", -1.35, 1.35, 0, 0.15, -0.9, 0.3, skip=("back", "bottom"))
    # The name over the portal, lanterns either side of it.
    outer.quad("deconame", -1.95, 1.95, 5.22, 5.84, 0.005, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    for u in (-1.78, 1.78):
        outer.box("bronze", u - 0.05, u + 0.05, 2.9, 3.5, 0, 0.18, skip=("back",))
        outer.box("bronze", u - 0.13, u + 0.13, 3.5, 3.56, 0.02, 0.3, skip=("back",))
        outer.box("lamp", u - 0.11, u + 0.11, 3.56, 4.25, 0.04, 0.28, skip=("back", "bottom"))
        outer.box("bronze", u - 0.15, u + 0.15, 4.25, 4.32, 0.02, 0.3, skip=("back",))
        outer.box("bronze", u - 0.04, u + 0.04, 4.32, 4.5, 0.12, 0.2, skip=("back",))


# ---- setbacks --------------------------------------------------------------------------------


def parapet(m, X, z, pylon=(1.4, 2.2, 2.8), tall=1.0):
    """A tier's parapet at z: cast panels between the piers, which rise through
    it as stepped finials (every other one tall), a coping, corner pylons
    stepping in like a ziggurat."""
    S = sides(m, 2 * X, 2 * X)
    for F in S.values():
        for a, b in bays(X):
            F.box("cladstone", a, b, z, z + PH, -R, -0.2, skip=("back", "left", "right", "top"))
            panel(F, a + 0.1, b - 0.1, z + 0.18, z + PH - 0.15, -0.19)
            F.box("cladstone", a, b, z + PH, z + PH + 0.1, -0.5, 0.0, skip=("left", "right", "bottom"))
            F.quad("cladstone", a, b, z, z + PH, -0.5, out=-F.n)
        for i, u in enumerate(lines(X)[1:-1]):
            if i % 2:
                F.box("cladstone", u - PW / 2, u + PW / 2, z, z + PH + 0.3, -R - 0.2, 0, skip=("back", "bottom"))
            else:
                F.box("cladstone", u - PW / 2, u + PW / 2, z, z + PH + tall, -R - 0.2, 0, skip=("back", "bottom"))
                F.box("cladstone", u - PW / 2 + 0.07, u + PW / 2 - 0.07, z + PH + tall, z + PH + tall + 0.5, -R - 0.1, -0.08, skip=("back", "bottom"))
                F.box("cladstone", u - 0.08, u + 0.08, z + PH + tall + 0.5, z + PH + tall + 0.8, -R, -0.14, skip=("back", "bottom"))
    k0 = 0.0
    for k, top in enumerate(pylon):
        corners(m, X, z if not k else z + pylon[k - 1], z + top, k=k0, ends=("z0",))
        k0 += 0.12


def terrace(m, Xo, Xi, z):
    """Paving round the tier above, floodlights aimed up at it."""
    t = z + 0.15
    o = Xo - 0.5
    for x0, x1, y0, y1 in ((-o, o, -o, -Xi), (-o, o, Xi, o), (-o, -Xi, -Xi, Xi), (Xi, o, -Xi, Xi)):
        m.poly("pave", [(x0, y0, t), (x1, y0, t), (x1, y1, t), (x0, y1, t)], out=Z)
    for F in sides(m, 2 * Xi, 2 * Xi).values():
        for u in (-Xi * 0.5, Xi * 0.5):
            F.box("iron", u - 0.2, u + 0.2, t, t + 0.18, 0.55, 0.85, skip=("bottom",))
            F.box("iron", u - 0.17, u + 0.17, t + 0.18, t + 0.42, 0.62, 0.82, skip=("bottom",))
            F.quad("lamp", u - 0.14, u + 0.14, t + 0.2, t + 0.4, 0.6, out=-F.n)


def ledge(m, Xo, Xi, z):
    parapet(m, Xo, z)
    terrace(m, Xo, Xi, z)


# ---- crown -------------------------------------------------------------------------------------

XA, HA = 2.7, 7.0  # the lower lit stage
XB, HB = 1.6, 5.5  # the upper lit stage


def crown(m, z):
    parapet(m, X3, z, pylon=(1.8, 2.8, 3.6), tall=1.4)
    terrace(m, X3, XA, z)
    stage_a(m, z)
    stage_b(m, z + HA + 0.12)
    spire(m, z + HA + 0.12 + HB + 0.12)


def coping(m, X, z, role="floodstone"):
    m.sweep(role, 2 * X, 2 * X, [(0.0, z), (0.1, z), (0.1, z + 0.12), (0.0, z + 0.12)])
    m.poly("roof", [(-X, -X, z + 0.12), (X, -X, z + 0.12), (X, X, z + 0.12), (-X, X, z + 0.12)], out=Z)


def stage_a(m, z):
    """Three tall lit windows a side between floodlit piers; the middle one taller."""
    S = sides(m, 2 * XA, 2 * XA)
    for F in S.values():
        for i, (a, b) in enumerate(bays(XA)):
            top = 6.0 if i == 1 else 5.2
            panel(F, a, b, z, z + 1.0, -R)
            wid = new_id()
            pane(F, "crownglass", a, b, z + 1.0, z + top, a, b, z + 1.0, z + top, -R - 0.06, wid)
            for u in (a + (b - a) / 3, a + 2 * (b - a) / 3):
                F.box("bronze", u - 0.03, u + 0.03, z + 1.0, z + top, -R - 0.06, -R, skip=("back", "top", "bottom"))
            for u0, u1 in ((a, a + 0.05), (b - 0.05, b)):
                F.box("bronze", u0, u1, z + 1.0, z + top, -R - 0.07, -R + 0.02, skip=("back", "top", "bottom"))
            F.box("bronze", a, b, z + 1.0, z + 1.07, -R - 0.07, -R + 0.05, skip=("back", "left", "right", "bottom"))
            panel(F, a, b, z + top, z + HA, -R)
        for u in lines(XA)[1:-1]:
            pier(F, u, z, z + HA, role="floodstone")
    corners(m, XA, z, z + HA, role="floodstone")
    coping(m, XA, z + HA)
    # The corners rise as small pylons over the coping.
    corners(m, XA, z + HA + 0.12, z + HA + 1.0, role="floodstone", k=0.1, cw=0.5, ends=("z0",))
    corners(m, XA, z + HA + 1.0, z + HA + 1.6, role="floodstone", k=0.2, cw=0.4, ends=("z0",))


def stage_b(m, z):
    """One tall slot of lit glass a side in floodlit stone, stainless fins stepping down the corners."""
    S = sides(m, 2 * XB, 2 * XB)
    for F in S.values():
        F.wall("floodstone", -XB, XB, z, z + HB, [(-0.38, 0.38, z + 0.7, z + 4.6)], depth=0.25)
        wid = new_id()
        pane(F, "crownglass", -0.38, 0.38, z + 0.7, z + 4.6, -0.38, 0.38, z + 0.7, z + 4.6, -0.2, wid)
        F.box("bronze", -0.03, 0.03, z + 0.7, z + 4.6, -0.2, -0.14, skip=("back", "top", "bottom"))
        # Chevrons over the slot.
        panel(F, -0.7, 0.7, z + 4.8, z + 5.25, 0.01)
    coping(m, XB, z + HB)
    for sx in (-1, 1):
        for sy in (-1, 1):
            d = (sx / math.sqrt(2), sy / math.sqrt(2), 0)
            n = (-sy / math.sqrt(2), sx / math.sqrt(2), 0)
            Fn = Side(m, (sx * XB, sy * XB, 0), d, n)
            for out, top in ((0.55, HB - 1.6), (0.38, HB - 0.6), (0.22, HB + 0.9)):
                Fn.box("stainless", -0.1, out, z, z + top, -0.035, 0.035, skip=("bottom",))


def spire(m, z):
    """An octagonal stainless drum tapering in, the spire, collars, the aircraft light."""
    m.cyl("stainless", 0, 0, 1.2, z, z + 3.2, seg=8, r1=0.8)
    for k in range(8):
        a = (k + 0.5) * math.tau / 8
        d = (math.cos(a), math.sin(a), 0)
        n = (-math.sin(a), math.cos(a), 0)
        Fn = Side(m, (0, 0, 0), d, n)
        Fn.box("stainless", 0.9, 1.45, z, z + 1.2, -0.03, 0.03, skip=("bottom",))
        Fn.box("stainless", 0.8, 1.2, z + 1.2, z + 2.4, -0.03, 0.03, skip=("bottom",))
    s0 = z + 3.2
    m.cyl("stainless", 0, 0, 0.5, s0, s0 + 13.5, seg=8, r1=0.04)
    for h, r in ((0.0, 0.62), (2.5, 0.53), (5.5, 0.42)):
        m.cyl("bronze", 0, 0, r, s0 + h, s0 + h + 0.18, seg=8, bottom=True)
    m.cyl("beacon", 0, 0, 0.08, s0 + 13.4, s0 + 13.7, seg=8)
