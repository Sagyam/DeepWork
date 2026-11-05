# O1, curtain-wall office tower: a late-modern speculative office on a
# 1.6 m planning grid. Stick-system curtain wall of tinted vision glass
# between opaque spandrel glass at the slab lines, aluminium mullions with
# deep fins and slim transoms, square corner posts. The ground storey is a
# double-height glass lobby set back behind a colonnade of polished granite
# columns, a revolving door between swing doors, the building's name in
# steel letters on the granite fascia, downlights in the soffit. The service
# core is a stone-clad strip up the back, rising above the roof as the lift
# overrun. A third of the way down the stack the tower steps back a bay at
# the front and sides onto a planted terrace behind the parapet. On the
# roof: a plant screen of louvre blades round the chillers, a window-cleaning
# gantry (BMU) on its rails, condensers, and an antenna mast with an aircraft
# warning light. The app tints the glass, the spandrels and the metalwork,
# and picks the name, per building.
#
# Pieces (base at the origin, stacked by the app):
#   ground   5.4 m: colonnade, lobby, revolving door, granite fascia with the name
#   floor    3.6 m: a typical storey of the lower block, 14.4 x 11.2 m
#   setback  the lower block's parapet and the terrace, at the top of the
#            lower block (no height: the upper storeys start on it)
#   upper    3.6 m: a typical storey of the upper block, 11.2 x 9.6 m
#   roof     parapet, plant screen, chillers, overrun, BMU, mast
import math

from lib import Model, Side, Z, glazing, new_id, pane, sides

ID = "o1"
B = 1.6  # planning grid
XL, Y0, Y1 = 7.2, -5.6, 5.6  # the lower block: half width, front and back
XU, YU = 5.6, Y0 + B  # the upper block: half width, front (it is flush at the back)
G = 5.4  # ground storey
FL = 3.6  # typical storeys
SILL, HEAD = 0.75, 2.95  # vision glass between, the spandrels below and above
CORE = 2.4  # the core strip's half width, up the middle of the back
CP = 0.3  # how far the core stands proud of the glass
GLASS_W = -0.03  # the glass plane, just behind the facade line
PAR = 1.15  # parapet height
YL = Y0 + B  # the lobby glass, behind the colonnade
FASCIA = G - 0.9  # the colonnade's soffit, under the granite fascia


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    storey(M, G, XL, Y0)
    top = G + FL
    M.piece("setback", (0, 0, top))
    setback(M, top)
    M.piece("upper", (0, 0, top))
    storey(M, top, XU, YU)
    M.piece("roof", (0, 0, top + FL))
    roof(M, top + FL)
    M.export(out, bake)


def block(m, X, Yf):
    """The four facades of a block X either side of the centre line, from Yf to the back."""
    return sides(m, 2 * X, Y1 - Yf, 0.0, (Yf + Y1) / 2)


def grid(u0, u1):
    """Grid lines from u0 to u1 (both on the grid), inclusive."""
    n = round((u1 - u0) / B)
    return [u0 + i * B for i in range(n + 1)]


# ---- curtain wall ---------------------------------------------------------------------


def mullion(F, u, z0, z1, deep=0.24):
    """A mullion: the pressure plate on the glass and a fin standing out from it."""
    F.box("mullion", u - 0.04, u + 0.04, z0, z1, GLASS_W, 0.05)
    F.box("mullion", u - 0.02, u + 0.02, z0, z1, 0.05, deep)


def curtain(F, u0, u1, z, ends=(True, True)):
    """One storey of curtain wall from u0 to u1 (on the grid) at height z:
    spandrel glass over the slab, vision glass between transoms, a mullion on
    every grid line (the ends only if `ends` says so: corners have posts)."""
    lines = grid(u0, u1)
    for i, (a, b) in enumerate(zip(lines, lines[1:])):
        wid = new_id()
        ga, gb = a + 0.04, b - 0.04
        F.quad("spandrel", ga, gb, z, z + SILL - 0.03, GLASS_W)
        F.quad("spandrel", ga, gb, z + HEAD + 0.03, z + FL, GLASS_W)
        pane(F, "officeglass", ga, gb, z + SILL, z + HEAD, ga, gb, z + SILL + 0.03, z + HEAD - 0.03, GLASS_W - 0.01, wid)
        for h in (SILL, HEAD):
            F.box("mullion", ga, gb, z + h - 0.03, z + h + 0.03, GLASS_W, 0.06)
        # The stack joint at the slab, where one storey's units meet the next.
        F.box("mullion", ga, gb, z, z + 0.025, GLASS_W, 0.03)
    for i, u in enumerate(lines):
        if (i == 0 and not ends[0]) or (i == len(lines) - 1 and not ends[1]):
            continue
        mullion(F, u, z, z + FL)


def post(m, x, y, z0, z1):
    """A square corner post where two curtain walls meet."""
    m.box("mullion", (x - 0.13, y - 0.13, z0), (x + 0.13, y + 0.13, z1))


def core(m, z0, z1, slot=True, door=False):
    """The stone-clad core strip up the back, standing proud of the glass, with
    the stair's slot window (or the service door at the foot)."""
    F = Side(m, (0, Y1 + CP, 0), (-1, 0, 0), (0, 1, 0))  # u = -x
    holes = []
    if slot:
        holes.append((-0.35, 0.35, z0 + SILL, z0 + HEAD))
    if door:
        holes.append((-0.6, 0.6, z0 + 0.15, z0 + 2.45))
    F.wall("stone", -CORE, CORE, z0, z1, holes, depth=0.2)
    if slot:
        glazing(F, -0.35, 0.35, z0 + SILL, z0 + HEAD, D=0.16, fr="mullion", glass="doorglass")
    if door:
        steel_door(F, -0.6, 0.6, z0 + 0.15, z0 + 2.45, 0.2)
    for x, out in ((-CORE, (-1, 0, 0)), (CORE, (1, 0, 0))):
        m.poly("stone", [(x, Y1 - 0.02, z0), (x, Y1 + CP, z0), (x, Y1 + CP, z1), (x, Y1 - 0.02, z1)], out=out)
    # A drip at each floor line, in the stone.
    F.box("stone", -CORE - 0.02, CORE + 0.02, z0, z0 + 0.06, 0, 0.03)


def steel_door(F, a, b, c, e, d):
    """A flush steel door in a frame, with a push bar."""
    F.quad("ac", a + 0.05, b - 0.05, c, e - 0.05, -d + 0.03)
    F.box("mullion", a, a + 0.05, c, e, -d, -d + 0.06)
    F.box("mullion", b - 0.05, b, c, e, -d, -d + 0.06)
    F.box("mullion", a, b, e - 0.05, e, -d, -d + 0.06)
    F.box("dark", a + 0.15, b - 0.15, c + 0.95, c + 1.0, -d + 0.03, -d + 0.07)


def storey(M, z, X, Yf):
    """A typical storey of a block: curtain wall round it, the core on the back, corner posts."""
    m = M.m
    S = block(m, X, Yf)
    D2 = (Y1 - Yf) / 2
    curtain(S["front"], -X, X, z, ends=(False, False))
    curtain(S["right"], -D2, D2, z, ends=(False, False))
    curtain(S["left"], -D2, D2, z, ends=(False, False))
    curtain(S["back"], -X, -CORE, z, ends=(False, True))
    curtain(S["back"], CORE, X, z, ends=(True, False))
    core(m, z, z + FL)
    for x in (-X, X):
        for y in (Yf, Y1):
            post(m, x, y, z, z + FL)
    # The slab's underside, seen only when the storey above is gone.
    m.poly("dark", [(-X, Yf, z + FL - 0.02), (X, Yf, z + FL - 0.02), (X, Y1, z + FL - 0.02), (-X, Y1, z + FL - 0.02)], out=-Z)


# ---- ground storey -----------------------------------------------------------------


def ground(M):
    m = M.m
    # The colonnade's granite floor, a step up from the plaza.
    m.box("granite", (-XL - 0.05, Y0 - 0.05, 0), (XL + 0.05, YL, 0.15), skip=("z0",))
    # Columns: the corners and two more either side of the entrance, polished granite on steel shoes.
    for x in (-XL + 0.32, -4.0, 4.0, XL - 0.32):
        m.box("granite", (x - 0.3, Y0 + 0.02, 0.15), (x + 0.3, Y0 + 0.62, FASCIA), skip=("z0", "z1"))
        m.box("stainless", (x - 0.31, Y0 + 0.01, 0.15), (x + 0.31, Y0 + 0.63, 0.33), skip=("z0",))
    # Fascia: granite round the top of the storey, the name on the front.
    S = sides(m, 2 * XL, Y1 - Y0)
    for name, F in S.items():
        h = XL if name in ("front", "back") else (Y1 - Y0) / 2
        F.box("granite", -h, h, FASCIA, G, -0.02, 0.06, skip=("back", "top"))
    F = S["front"]
    F.quad("towername", -XL + 0.4, XL - 0.4, FASCIA + 0.12, G - 0.12, 0.065, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    # The soffit over the colonnade, with downlights.
    m.poly("panel", [(-XL, Y0, FASCIA), (XL, Y0, FASCIA), (XL, YL, FASCIA), (-XL, YL, FASCIA)], out=-Z)
    for x in grid(-XL + 0.8, XL - 0.8):
        m.cyl("lamp", x, (Y0 + YL) / 2, 0.08, FASCIA - 0.02, FASCIA, seg=10, top=False, bottom=True)
    lobby(m)
    flanks(m)
    back(m)
    m.poly("dark", [(-XL, Y0, G - 0.02), (XL, Y0, G - 0.02), (XL, Y1, G - 0.02), (-XL, Y1, G - 0.02)], out=-Z)


def lobby(m):
    """The lobby's glass wall behind the colonnade: tall panes on slim posts,
    a revolving door in the middle between two swing doors."""
    F = Side(m, (0, YL, 0), (1, 0, 0), (0, -1, 0))  # u = x
    c, e = 0.15, FASCIA
    lines = grid(-XL, XL)
    door = 2.75  # the doors' head
    for a, b in zip(lines, lines[1:]):
        if -CORE - 0.01 < a < CORE - 0.01:
            continue  # the entrance bays
        pane(F, "doorglass", a, b, c, e, a + 0.02, b - 0.02, c, e, -0.02, new_id())
    wid = new_id()
    for u in lines:
        F.box("mullion", u - 0.03, u + 0.03, c, e, -0.02, 0.04)
    F.box("mullion", -XL, XL, c, c + 0.08, -0.02, 0.05)
    # The entrance: transom glass above the door head, swing doors, the revolving door.
    pane(F, "doorglass", -CORE, CORE, c, e, -CORE + 0.03, CORE - 0.03, door + 0.06, e, -0.02, wid)
    F.box("mullion", -CORE, CORE, door, door + 0.08, -0.04, 0.06)
    for a, b in ((-CORE, -0.8), (0.8, CORE)):
        swing_door(F, a + 0.03, b - 0.03, c, door, wid)
    revolving(m, F, c, door)
    # The lobby's ceiling seen over the doors, and the ends of the glass where the flanks start.
    m.poly("panel", [(-XL, YL, e), (XL, YL, e), (XL, YL + 0.3, e), (-XL, YL + 0.3, e)], out=-Z)


def swing_door(F, a, b, c, e, wid):
    """A frameless glass door with a stainless rail at the foot and a long pull."""
    pane(F, "doorglass", a, b, c, e, a + 0.02, b - 0.02, c + 0.12, e - 0.02, -0.03, wid)
    F.box("stainless", a, b, c, c + 0.12, -0.05, 0.0)
    u = b - 0.15 if a < 0 else a + 0.15
    F.box("stainless", u - 0.02, u + 0.02, c + 0.7, c + 2.0, 0.0, 0.06, skip=())


def revolving(m, F, c, e):
    """A four-wing revolving door in a glass drum, half out of the lobby wall,
    under a stainless canopy; the vestibule behind it."""
    r, seg = 1.1, 20
    yc = YL
    # Curved glass either side, the openings to the street and the lobby.
    for mid in (0.0, math.pi):
        pts = [mid + (i / 6 - 0.5) * math.radians(110) for i in range(7)]
        for a0, a1 in zip(pts, pts[1:]):
            p = lambda a, z: (math.cos(a) * r, yc + math.sin(a) * r, z)  # noqa: E731
            m.poly("canopy", [p(a0, c), p(a1, c), p(a1, e), p(a0, e)], out=(math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0))
        for a in (pts[0], pts[-1]):
            m.box("stainless", (math.cos(a) * r - 0.03, yc + math.sin(a) * r - 0.03, c), (math.cos(a) * r + 0.03, yc + math.sin(a) * r + 0.03, e))
    m.cyl("stainless", 0, yc, r + 0.05, e, e + 0.32, seg=seg, bottom=True)
    m.cyl("stainless", 0, yc, r + 0.05, c, c + 0.03, seg=seg)
    m.cyl("stainless", 0, yc, 0.06, c, e, seg=8, top=False)
    # Four wings at 45 degrees, glass in stainless frames.
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = (math.cos(a), math.sin(a), 0)
        n = (-math.sin(a), math.cos(a), 0)
        W = Side(m, (0, yc, 0), d, n)
        W.quad("canopy", 0.08, r - 0.06, c + 0.12, e - 0.08, 0.0, out=n)
        W.quad("canopy", 0.08, r - 0.06, c + 0.12, e - 0.08, 0.0, out=(-n[0], -n[1], 0))
        W.box("stainless", r - 0.06, r - 0.02, c + 0.02, e - 0.02, -0.02, 0.02, skip=())
        W.box("stainless", 0.06, r - 0.02, c + 0.02, c + 0.12, -0.02, 0.02, skip=())
        W.box("stainless", 0.06, r - 0.02, e - 0.08, e - 0.02, -0.02, 0.02, skip=())
    # The vestibule: glass to the lobby behind the drum, panelled sides and ceiling.
    V = Side(m, (0, YL + r + 0.05, 0), (1, 0, 0), (0, -1, 0))
    pane(V, "doorglass", -r - 0.05, r + 0.05, c, e, -r - 0.05, r + 0.05, c, e, 0, new_id())
    for x, out in ((-r - 0.05, (1, 0, 0)), (r + 0.05, (-1, 0, 0))):
        m.poly("panel", [(x, YL, c), (x, YL + r + 0.05, c), (x, YL + r + 0.05, e), (x, YL, e)], out=out)
    m.poly("panel", [(-r - 0.05, YL, e), (r + 0.05, YL, e), (r + 0.05, YL + r + 0.05, e), (-r - 0.05, YL + r + 0.05, e)], out=-Z)
    m.poly("granite", [(-r - 0.05, YL, c), (r + 0.05, YL, c), (r + 0.05, YL + r + 0.05, c), (-r - 0.05, YL + r + 0.05, c)], out=Z)


def flanks(m):
    """The ground storey's sides behind the colonnade: granite with tall windows between piers."""
    S = sides(m, 2 * XL, Y1 - Y0)
    D2 = (Y1 - Y0) / 2
    for name in ("right", "left"):
        F = S[name]
        # u runs from the front (right) or the back (left).
        lo, hi = (YL - (Y0 + Y1) / 2, D2) if name == "right" else (-D2, -(YL - (Y0 + Y1) / 2))
        lines = grid(lo, hi)
        holes = [(a + 0.2, b - 0.2, 0.6, FASCIA - 0.25) for a, b in zip(lines, lines[1:])]
        F.wall("granite", lo, hi, 0, FASCIA, holes, depth=0.18)
        for h in holes:
            glazing(F, *h, D=0.16, fr="mullion", glass="officeglass")
            F.box("granite", h[0] - 0.04, h[1] + 0.04, h[2] - 0.06, h[2], -0.16, 0.05)
        F.box("granite", lo, hi, 0, 0.3, 0, 0.03, skip=("back", "left", "right"))
        # The open end of the colonnade, between the corner column and the lobby glass.
        if name == "right":
            m.poly("granite", [(XL, YL, 0.15), (XL, YL, FASCIA), (XL - 0.3, YL, FASCIA), (XL - 0.3, YL, 0.15)], out=(0, -1, 0))
        else:
            m.poly("granite", [(-XL, YL, 0.15), (-XL, YL, FASCIA), (-XL + 0.3, YL, FASCIA), (-XL + 0.3, YL, 0.15)], out=(0, -1, 0))


def back(m):
    """The service side: a loading bay's roller shutter, a fire exit, intake
    louvres, a window, and the core's door."""
    F = Side(m, (0, Y1, 0), (-1, 0, 0), (0, 1, 0))  # u = -x
    shutter = (-6.6, -3.6, 0, 3.4)
    fire = (3.3, 4.3, 0.15, 2.45)
    louvre = (3.1, 4.5, 3.0, 4.0)
    win = (5.15, 6.75, 1.0, 3.9)
    F.wall("granite", -XL, -CORE, 0, FASCIA, [shutter], depth=0.25)
    F.wall("granite", CORE, XL, 0, FASCIA, [fire, louvre, win], depth=0.2)
    # The shutter: blades, guides, the coil's box over it, a buffer kerb.
    F.quad("blades", shutter[0], shutter[1], 0, shutter[3], -0.2, uvs=[(0, 0), (3, 0), (3, 3.4), (0, 3.4)])
    for u in (shutter[0], shutter[1] - 0.08):
        F.box("mullion", u, u + 0.08, 0, shutter[3], -0.25, -0.12)
    F.box("mullion", shutter[0] - 0.1, shutter[1] + 0.1, shutter[3], shutter[3] + 0.45, 0, 0.35, skip=("back",))
    for u in (shutter[0] - 0.35, shutter[1] + 0.15):
        F.box("concrete", u, u + 0.2, 0, 1.0, 0, 0.25, skip=("back", "bottom"))
    steel_door(F, *fire, 0.2)
    F.quad("blades", louvre[0], louvre[1], louvre[2], louvre[3], -0.12, uvs=[(0, 0), (1.4, 0), (1.4, 1.0), (0, 1.0)])
    glazing(F, *win, lights=2, D=0.16, fr="mullion", glass="officeglass")
    # Granite base course.
    for u0, u1 in ((-XL, shutter[0] - 0.35), (shutter[1] + 0.35, -CORE), (CORE, fire[0]), (fire[1], XL)):
        F.box("granite", u0, u1, 0, 0.3, 0, 0.03, skip=("back", "left", "right"))
    core(m, 0, FASCIA, slot=False, door=True)
    m.poly("stone", [(-CORE, Y1 + CP, FASCIA), (CORE, Y1 + CP, FASCIA), (CORE, Y1 + CP, G), (-CORE, Y1 + CP, G)], out=(0, 1, 0))
    for x, out in ((-CORE, (-1, 0, 0)), (CORE, (1, 0, 0))):
        m.poly("stone", [(x, Y1 + 0.06, FASCIA), (x, Y1 + CP, FASCIA), (x, Y1 + CP, G), (x, Y1 + 0.06, G)], out=out)
    # A lamp over the core door, and one over the shutter.
    m.box("lamp", (-0.15, Y1 + CP, 2.7), (0.15, Y1 + CP + 0.12, 2.82))
    m.box("lamp", (4.95, Y1 + 0.35, 3.95), (5.25, Y1 + 0.47, 4.07))


# ---- the setback: lower block's parapet and the terrace -------------------------------------


def parapet(m, F, u0, u1, z, h=PAR, ends=(True, True)):
    """A parapet along facade F from u0 to u1 at z: the spandrel glass carried
    on up, mullion stubs, a panelled inside face, an aluminium coping."""
    F.quad("spandrel", u0, u1, z, z + h, GLASS_W)
    for i, u in enumerate(grid(u0, u1)):
        if (i == 0 and not ends[0]) or (abs(u - u1) < 1e-6 and not ends[1]):
            continue
        mullion(F, u, z, z + h, deep=0.2)
    F.quad("panel", u0, u1, z + 0.1, z + h, -0.3, out=-F.n)
    F.box("mullion", u0 - 0.02, u1 + 0.02, z + h, z + h + 0.06, -0.32, 0.08, skip=())


def setback(M, z):
    m = M.m
    S = block(m, XL, Y0)
    D2 = (Y1 - Y0) / 2
    parapet(m, S["front"], -XL, XL, z, ends=(False, False))
    parapet(m, S["right"], -D2, D2, z, ends=(False, False))
    parapet(m, S["left"], -D2, D2, z, ends=(False, False))
    parapet(m, S["back"], -XL, -XU, z, ends=(False, True))
    parapet(m, S["back"], XU, XL, z, ends=(True, False))
    for x in (-XL, XL):
        for y in (Y0, Y1):
            post(m, x, y, z, z + PAR + 0.06)
    # The terrace: paving slabs on pedestals over the roof, in a U round the upper block.
    i = 0.3
    t = z + 0.14
    paving = [(-XL + i, XL - i, Y0 + i, YU), (XU, XL - i, YU, Y1 - i), (-XL + i, -XU, YU, Y1 - i)]
    for x0, x1, y0, y1 in paving:
        m.poly("pave", [(x0, y0, t), (x1, y0, t), (x1, y1, t), (x0, y1, t)], out=Z)
    # Planters along the parapet with low planting, teak benches facing out.
    for x in (-4.6, 0.0, 4.6):
        planter(m, x - 1.4, x + 1.4, Y0 + i + 0.05, Y0 + i + 0.75, t)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (XL - i - 0.05), sx * (XL - i - 0.75)))
        planter(m, x0, x1, -1.0, 2.6, t)
        bench(m, sx * 2.3, YU - 0.55, t)
        bench(m, sx * (XU + 0.55), 4.2, t, along_y=True)
    # A glass screen on the parapet at the front, for the wind.
    for F, a, b in ((S["front"], -XL, XL),):
        F.quad("canopy", a + 0.15, b - 0.15, z + PAR + 0.06, z + PAR + 0.66, -0.12)
        F.quad("canopy", a + 0.15, b - 0.15, z + PAR + 0.06, z + PAR + 0.66, -0.12, out=-F.n)
        F.box("mullion", a + 0.15, b - 0.15, z + PAR + 0.66, z + PAR + 0.7, -0.15, -0.09, skip=())


def planter(m, x0, x1, y0, y1, z, h=0.55):
    m.box("concrete", (x0, y0, z), (x1, y1, z + h), skip=("z0", "z1"))
    m.box("concrete", (x0, y0, z + h), (x1, y1, z + h + 0.04), skip=("z0",))
    m.box("sedum", (x0 + 0.06, y0 + 0.06, z + h - 0.05), (x1 - 0.06, y1 - 0.06, z + h + 0.08), skip=("z0",))


def bench(m, x, y, z, along_y=False):
    """A teak slab bench on two concrete blocks, 1.8 m long."""
    hx, hy = (0.22, 0.9) if along_y else (0.9, 0.22)
    m.box("wood", (x - hx, y - hy, z + 0.38), (x + hx, y + hy, z + 0.45))
    for k in (-0.6, 0.6):
        cx, cy = (x, y + k) if along_y else (x + k, y)
        m.box("concrete", (cx - (0.18 if along_y else 0.1), cy - (0.1 if along_y else 0.18), z), (cx + (0.18 if along_y else 0.1), cy + (0.1 if along_y else 0.18), z + 0.38), skip=("z0",))


# ---- roof ------------------------------------------------------------------------------


def roof(M, z):
    m = M.m
    S = block(m, XU, YU)
    D2 = (Y1 - YU) / 2
    parapet(m, S["front"], -XU, XU, z, ends=(False, False))
    parapet(m, S["right"], -D2, D2, z, ends=(False, False))
    parapet(m, S["left"], -D2, D2, z, ends=(False, False))
    parapet(m, S["back"], -XU, -CORE, z, ends=(False, True))
    parapet(m, S["back"], CORE, XU, z, ends=(True, False))
    for x in (-XU, XU):
        for y in (YU, Y1):
            post(m, x, y, z, z + PAR + 0.06)
    i = 0.3
    base = z + 0.12
    m.poly("roof", [(-XU + i, YU + i, base), (XU - i, YU + i, base), (XU - i, Y1 - i, base), (-XU + i, Y1 - i, base)], out=Z)
    overrun(m, z, base)
    plant(m, base)
    bmu(m, base)
    # Condensers in a row at the back left, on a steel frame.
    for k in range(3):
        y = 2.5 + k * 1.05
        m.box("iron", (-5.0, y - 0.05, base), (-3.4, y + 0.85, base + 0.3), skip=("z0",))
        m.box("ac", (-4.95, y, base + 0.3), (-3.45, y + 0.8, base + 1.1), skip=("z0",))
        m.cyl("dark", -4.2, y + 0.4, 0.3, base + 1.1, base + 1.11, seg=14)


def overrun(m, z, base):
    """The core above the roof: the lift overrun and the stair head, stone-clad, a
    door onto the roof, louvres, a parapet of its own; the mast on top."""
    h = 4.2
    x0, x1, y0, y1 = -CORE, CORE, Y1 - 3.1, Y1 + CP
    m.box("stone", (x0, y0, z), (x1, y1, z + h), skip=("z0", "z1"))
    m.box("stone", (x0 - 0.05, y0 - 0.05, z + h), (x1 + 0.05, y1 + 0.05, z + h + 0.15), skip=())
    F = Side(m, (0, y0, 0), (1, 0, 0), (0, -1, 0))
    door = (0.9, 1.9, base, base + 2.2)
    F.quad("dark", door[0], door[1], door[2], door[3], 0.001)
    steel_door(F, door[0], door[1], door[2], door[3], -0.02)
    F.quad("blades", -1.9, -0.3, z + 2.2, z + 3.5, 0.002, uvs=[(0, 0), (1.6, 0), (1.6, 1.3), (0, 1.3)])
    F.box("mullion", -1.95, -0.25, z + 2.15, z + 3.55, 0, 0.04, skip=("back", "front"))
    m.box("lamp", (1.25, y0 - 0.12, base + 2.4), (1.55, y0, base + 2.52))
    # The mast: a lattice of three legs would be fine detail; a steel pole with
    # panel antennas, a dish and the red warning light.
    mx, my, mz = 1.4, Y1 - 1.2, z + h + 0.15
    m.box("iron", (mx - 0.3, my - 0.3, mz), (mx + 0.3, my + 0.3, mz + 0.12), skip=("z0",))
    m.cyl("ac", mx, my, 0.07, mz + 0.12, mz + 7.5, seg=8)
    for k in range(3):
        a = k * math.tau / 3
        px, py = mx + math.cos(a) * 0.16, my + math.sin(a) * 0.16
        m.box("ac", (px - 0.09, py - 0.09, mz + 4.6), (px + 0.09, py + 0.09, mz + 6.0))
    m.cyl("ac", mx + 0.25, my, 0.3, mz + 3.2, mz + 3.3, seg=14, bottom=True)
    m.cyl("beacon", mx, my, 0.09, mz + 7.5, mz + 7.72, seg=8)
    # Ladder up the overrun's side.
    for x in (-CORE - 0.05, -CORE - 0.5):
        m.box("iron", (x - 0.03, y0 + 0.6, base), (x + 0.03, y0 + 0.66, z + h + 1.0))
    for k in range(14):
        zz = base + 0.3 + k * 0.3
        m.box("iron", (-CORE - 0.5, y0 + 0.61, zz), (-CORE - 0.05, y0 + 0.65, zz + 0.025))


def plant(m, base):
    """A screen of louvre blades round the chillers, open to the sky."""
    x0, x1, y0, y1, h = -4.9, 1.7, -3.3, 1.5, 2.7
    for (ax, ay), (bx, by), out in (((x0, y0), (x1, y0), (0, -1, 0)), ((x1, y0), (x1, y1), (1, 0, 0)), ((x1, y1), (x0, y1), (0, 1, 0)), ((x0, y1), (x0, y0), (-1, 0, 0))):
        L = math.hypot(bx - ax, by - ay)
        m.poly("blades", [(ax, ay, base), (bx, by, base), (bx, by, base + h), (ax, ay, base + h)], out=out, uvs=[(0, 0), (L, 0), (L, h), (0, h)])
        m.poly("dark", [(ax, ay, base), (bx, by, base), (bx, by, base + h), (ax, ay, base + h)], out=(-out[0], -out[1], 0))
        # Posts every 2 m along it, a capping rail.
        n = max(1, round(L / 2.2))
        for k in range(n + 1):
            px, py = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
            m.box("mullion", (px - 0.06, py - 0.06, base), (px + 0.06, py + 0.06, base + h + 0.05))
        lo = (min(ax, bx) - 0.05, min(ay, by) - 0.05, base + h)
        hi = (max(ax, bx) + 0.05, max(ay, by) + 0.05, base + h + 0.08)
        m.box("mullion", lo, hi)
    # Two air-cooled chillers, fans on top behind guards.
    for cx in (-3.2, 0.0):
        y = (y0 + y1) / 2
        m.box("iron", (cx - 1.3, y - 1.6, base), (cx + 1.3, y + 1.6, base + 0.25), skip=("z0",))
        m.box("ac", (cx - 1.15, y - 1.5, base + 0.25), (cx + 1.15, y + 1.5, base + 2.0), skip=("z0",))
        for k in (-1, 0, 1):
            fy = y + k * 1.0
            m.cyl("dark", cx, fy, 0.42, base + 2.0, base + 2.01, seg=16)
            m.cyl("ac", cx, fy, 0.08, base + 2.01, base + 2.12, seg=8)
            m.cyl("iron", cx, fy, 0.45, base + 2.0, base + 2.2, seg=16, top=False)
        # Pipework to the plant room.
        m.box("ac", (cx - 0.12, y + 1.5, base + 0.5), (cx + 0.12, y1 + 0.6, base + 0.74))


def bmu(m, base):
    """The window-cleaning gantry, parked on its rails along the right."""
    rx = (3.5, 4.6)
    for x in rx:
        m.box("iron", (x - 0.05, YU + 0.6, base), (x + 0.05, Y1 - 0.6, base + 0.14), skip=("z0",))
    y = 2.2
    m.box("ac", (3.25, y - 0.9, base + 0.14), (4.85, y + 0.9, base + 1.0), skip=("z0",))
    for x in rx:
        for dy in (-0.7, 0.7):
            m.cyl("dark", x, y + dy, 0.13, base + 0.05, base + 0.3, seg=8)
    m.box("ac", (3.85, y - 0.25, base + 1.0), (4.25, y + 0.25, base + 3.2))
    # The jib, slewed to lie along the roof, and the cradle parked under it.
    m.box("ac", (3.92, y - 4.6, base + 3.2), (4.18, y + 0.6, base + 3.55))
    m.box("iron", (3.95, y - 4.5, base + 2.4), (4.15, y - 4.3, base + 3.2))
    m.box("ac", (3.45, y - 5.0, base + 0.14), (4.65, y - 3.8, base + 0.24), skip=("z0",))
    for x in (3.45, 4.62):
        m.box("ac", (x, y - 5.0, base + 0.24), (x + 0.03, y - 3.8, base + 1.15))
    m.box("ac", (3.45, y - 5.0, base + 1.12), (4.65, y - 4.97, base + 1.15))
    m.box("ac", (3.45, y - 3.83, base + 1.12), (4.65, y - 3.8, base + 1.15))
