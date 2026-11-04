# C3, modern house: a contemporary two-storey family house. A white
# rendered ground storey with floor-to-ceiling glass wrapping the living
# room's corner and the front door in a timber-lined recess beside it; a
# timber-clad upper storey cantilevered 1.2 m over the front inside a white
# picture frame, with a ribbon window; a one-storey garage with a
# batten-clad door and a sedum roof; sliding doors onto a deck behind, and a
# heat pump. Flat roofs with aluminium copings; on the upper one gravel,
# solar panels, a rooflight and the wood stove's flue. The app tints the
# render, the cladding and the aluminium per house.
#
# Pieces (base at the origin):
#   ground  the ground storey, garage, deck and entrance, up to the upper floor
#   upper   the cantilevered upper storey, up to its roof slab
#   roof    parapets, gravel, solar panels, rooflight, flue
import math

from lib import Model, Side, Z, glazing

ID = "c3"
CY = -0.2  # centre of the main block: the cantilever in front and the deck behind keep the footprint centred
XA, XB, GX = -6.1, 2.3, 6.1  # left wall, the main block's right wall (the garage's left), the garage's right wall
Y0, Y1 = CY - 3.75, CY + 3.75  # main block, front and back
GY = Y0 + 6.3  # the garage's back wall
UY = Y0 - 1.2  # front of the cantilevered upper storey (its frame)
PF, FT = 0.35, 0.25  # the frame's depth in front of the cladding, and its members' width
CF = UY + PF  # the upper storey's cladding, front face
FL = 0.25  # ground floor level
G = 3.3  # upper floor level, top of the ground storey
TOP = 6.3  # the upper storey's roof slab
PAR = 0.4  # parapets above it
PT = 0.25  # parapet thickness
GR, GT = 2.88, 3.15  # the garage's roof and parapet top
YR, RX = Y0 + 1.4, -0.3  # the entrance recess: its back wall, its left side (it runs to XB)
DEPTH = 0.12  # glass depth in the walls
FLUE = (-4.6, 2.2)


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("upper", (0, 0, G))
    upper(M)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    M.export(out, bake)


# Facades with u along a world axis, so openings are given in plan coordinates.
def front(m, y=Y0):
    return Side(m, (0, y, 0), (1, 0, 0), (0, -1, 0))  # u = x


def back(m, y=Y1):
    return Side(m, (0, y, 0), (-1, 0, 0), (0, 1, 0))  # u = -x


def left(m, x=XA):
    return Side(m, (x, 0, 0), (0, -1, 0), (-1, 0, 0))  # u = -y


def right(m, x):
    return Side(m, (x, 0, 0), (0, 1, 0), (1, 0, 0))  # u = y


def flat(m, role, x0, x1, y0, y1, z, out=Z):
    m.poly(role, [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], out=out)


# ---- parts ------------------------------------------------------------------------


def pivot_door(F, a, b, c, e):
    """A tall flush door on a pivot, with a long stainless pull bar."""
    F.box("alu", a, a + 0.05, c, e, -0.1, 0.0)
    F.box("alu", b - 0.05, b, c, e, -0.1, 0.0)
    F.box("alu", a + 0.05, b - 0.05, e - 0.05, e, -0.1, 0.0)
    F.quad("door", a + 0.05, b - 0.05, c, e - 0.05, -0.06)
    u = b - 0.24
    F.box("ac", u, u + 0.035, c + 0.45, c + 2.05, 0.0, 0.035, skip=())
    for z in (c + 0.55, c + 1.95):
        F.box("ac", u + 0.005, u + 0.03, z, z + 0.03, -0.06, 0.0)


def flush_door(F, a, b, c, e):
    """A plain side door in a slim frame."""
    F.box("alu", a, b, e - 0.05, e, -0.12, -0.02)
    F.box("alu", a, a + 0.05, c, e, -0.12, -0.02)
    F.box("alu", b - 0.05, b, c, e, -0.12, -0.02)
    F.quad("door", a + 0.05, b - 0.05, c, e - 0.05, -0.08)
    F.box("ac", a + 0.12, a + 0.3, c + 1.0, c + 1.03, -0.08, -0.02)


def garage_door(F, a, b, c, e, d=0.2):
    """A sectional door clad in the house's battens: five sections with shadow gaps."""
    F.quad("dark", a, b, c, e, -d + 0.02)
    n = 5
    for i in range(n):
        z0, z1 = c + (e - c) * i / n, c + (e - c) * (i + 1) / n
        F.quad("cladding", a + 0.02, b - 0.02, z0 + (0.006 if i else 0), z1 - 0.006, -d + 0.06)
    F.box("alu", a, b, c, c + 0.03, -d, -d + 0.08)


def corner_glass(m, x, y, z0, z1):
    """The slim post where two glass walls meet at a corner."""
    m.box("alu", (x - 0.025, y - 0.025, z0), (x + 0.025, y + 0.025, z1))


def panel(m, x0, x1, y0, y1, base, tilt):
    """A solar panel on a low aluminium frame, its lower edge along y0, rising toward y1."""
    k = math.tan(tilt)
    z0 = base + 0.18
    z1 = z0 + (y1 - y0) * k
    t = 0.04
    lo = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)]
    hi = [(x, y, z + t) for x, y, z in lo]
    m.poly("solar", hi, out=(0, -k, 1), uvs=[(0, 1), (1, 1), (1, 0), (0, 0)])
    m.poly("alu", lo, out=(0, k, -1))
    for i in range(4):
        j = (i + 1) % 4
        mid = ((lo[i][0] + lo[j][0]) / 2, (lo[i][1] + lo[j][1]) / 2)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        m.poly("alu", [lo[i], lo[j], hi[j], hi[i]], out=(mid[0] - cx, mid[1] - cy, 0))
    for x in (x0 + 0.12, x1 - 0.16):
        m.box("alu", (x, y0 + 0.1, base), (x + 0.04, y0 + 0.14, z0 + 0.1 * k))
        m.box("alu", (x, y1 - 0.14, base), (x + 0.04, y1 - 0.1, z1 - 0.1 * k))
        m.box("alu", (x, y0 + 0.1, base), (x + 0.04, y1 - 0.1, base + 0.04))


# ---- ground storey -------------------------------------------------------------------


def ground(M):
    m = M.m
    # Plinth in dark concrete, a shadow gap under the render.
    m.sweep("concrete", XB - XA, Y1 - Y0, [(-0.03, 0.0), (-0.03, FL), (0.0, FL)], cx=(XA + XB) / 2, cy=CY)

    # Front: the living room's glass wall, round the corner.
    F = front(m)
    living = (XA, -1.1, FL, 2.95)
    F.wall("render", XA, RX, FL, G, [living], depth=DEPTH)
    glazing(F, *living, lights=3, ends=(False, True))
    L = left(m)
    corner = (-Y0 - 2.6, -Y0, FL, 2.95)
    slot = (-1.7, -1.0, FL + 0.1, 2.7)
    L.wall("render", -Y1, -Y0, FL, G, [corner, slot], depth=DEPTH)
    glazing(L, *corner, lights=2, ends=(True, False))
    glazing(L, *slot)
    corner_glass(m, XA + DEPTH, Y0 + DEPTH, FL, 2.95)

    # Back: sliding doors onto the deck, the kitchen window.
    B = back(m)
    slider = (0.4, 5.6, FL, 2.75)
    kitchen = (-1.9, -0.1, 1.15, 2.35)
    B.wall("render", -XB, -XA, FL, G, [slider, kitchen], depth=DEPTH)
    glazing(B, *slider, lights=4, slide=True)
    glazing(B, *kitchen, lights=2)
    m.box("deck", (XA, Y1, 0), (0.6, Y1 + 1.6, FL - 0.05), skip=("z0", "y0"))

    # Right: the bit of the main block behind the garage, and above its roof.
    R = right(m, XB)
    util = (GY + 0.3, GY + 0.9, 1.3, 2.4)
    R.wall("render", GY, Y1, FL, G, [util], depth=DEPTH)
    glazing(R, *util)
    R.quad("render", Y0, GY, GR, G)

    entrance(m)
    garage(m)
    # A ceiling over the top, seen only when the upper storey is gone.
    flat(m, "dark", XA, XB, Y0, Y1, G - 0.02)


def entrance(m):
    """The front door in a recess lined with battens, a landing and a step, a wall light."""
    E = front(m, YR)
    door = (0.0, 1.15, FL, FL + 2.6)
    side = (1.35, 1.95, FL, FL + 2.6)
    E.wall("cladding", RX, XB, FL, G, [door, side], depth=0.1, reveal="alu")
    pivot_door(E, *door)
    glazing(E, *side, D=0.08)
    m.poly("cladding", [(RX, Y0, FL), (RX, YR, FL), (RX, YR, G), (RX, Y0, G)], out=(1, 0, 0))
    m.poly("cladding", [(XB, Y0, FL), (XB, YR, FL), (XB, YR, G), (XB, Y0, G)], out=(-1, 0, 0))
    flat(m, "wood", RX, XB, Y0, YR, G, out=-Z)
    m.cyl("lamp", (RX + XB) / 2 + 0.3, (Y0 + YR) / 2, 0.07, G - 0.02, G, seg=10, top=False, bottom=True)
    m.box("concrete", (RX, Y0, 0), (XB, YR, FL), skip=("z0",))
    m.box("concrete", (RX + 0.3, Y0 - 0.45, 0), (XB - 0.3, Y0, FL / 2), skip=("z0", "y1"))
    m.box("lamp", (RX, Y0 + 0.45, 1.95), (RX + 0.07, Y0 + 0.6, 2.35))


def garage(m):
    """The garage: render on three sides, a batten door, a side door, a sedum roof inside parapets."""
    GF = front(m)
    door = (XB + 0.6, GX - 0.6, 0.0, 2.3)
    GF.wall("render", XB, GX, 0.0, GT, [door], depth=0.2)
    garage_door(GF, *door)
    # A car charger beside the door.
    GF.box("ac", GX - 0.48, GX - 0.2, 1.05, 1.42, 0, 0.12, skip=("back",))
    GF.box("dark", GX - 0.42, GX - 0.26, 1.24, 1.34, 0.12, 0.125, skip=("back",))
    S = right(m, GX)
    side = (Y0 + 4.7, Y0 + 5.6, 0.0, 2.15)
    high = (Y0 + 0.9, Y0 + 3.5, 1.7, 2.35)
    S.wall("render", Y0, GY, 0.0, GT, [side, high], depth=DEPTH)
    flush_door(S, *side)
    glazing(S, *high, lights=2)
    B = back(m, GY)
    win = (-GX + 0.6, -GX + 1.8, 1.2, 2.3)
    B.wall("render", -GX, -XB, 0.0, GT, [win], depth=DEPTH)
    glazing(B, *win)
    # Roof: sedum inside a gravel margin; parapets render inside, capped in aluminium.
    x0, x1, y0, y1 = XB, GX - PT, Y0 + PT, GY - PT
    flat(m, "gravel", x0, x1, y0, y1, GR)
    m.box("sedum", (x0 + 0.4, y0 + 0.4, GR), (x1 - 0.4, y1 - 0.4, GR + 0.07), skip=("z0",))
    m.poly("render", [(x0, y0, GR), (x1, y0, GR), (x1, y0, GT), (x0, y0, GT)], out=(0, 1, 0))
    m.poly("render", [(x1, y0, GR), (x1, y1, GR), (x1, y1, GT), (x1, y0, GT)], out=(-1, 0, 0))
    m.poly("render", [(x0, y1, GR), (x1, y1, GR), (x1, y1, GT), (x0, y1, GT)], out=(0, -1, 0))
    m.box("alu", (XB, Y0 - 0.03, GT), (GX + 0.03, y0 + 0.02, GT + 0.04))
    m.box("alu", (x1 - 0.02, Y0 - 0.03, GT), (GX + 0.03, GY + 0.03, GT + 0.04))
    m.box("alu", (XB, y1 - 0.02, GT), (GX + 0.03, GY + 0.03, GT + 0.04))
    # Rainwater: a hopper through the back parapet and a downpipe.
    m.box("alu", (GX - 0.5, GY, GR - 0.3), (GX - 0.26, GY + 0.2, GR + 0.05))
    m.box("alu", (GX - 0.42, GY + 0.04, 0.05), (GX - 0.34, GY + 0.12, GR - 0.3))
    m.box("alu", (GX - 0.42, GY + 0.04, 0.05), (GX - 0.34, GY + 0.3, 0.13))
    # The heat pump on a pad, in the corner behind the garage.
    hx = XB + 0.5
    m.box("concrete", (hx - 0.1, GY + 0.05, 0), (hx + 1.1, GY + 0.65, 0.1), skip=("z0",))
    m.box("ac", (hx, GY + 0.12, 0.1), (hx + 1.0, GY + 0.52, 0.95), skip=("z0",))
    m.poly("dark", [(hx + 0.1, GY + 0.525, 0.2), (hx + 0.66, GY + 0.525, 0.2), (hx + 0.66, GY + 0.525, 0.82), (hx + 0.1, GY + 0.525, 0.82)], out=(0, 1, 0))
    for z in (0.3, 0.45, 0.6, 0.75):
        m.box("ac", (hx + 0.1, GY + 0.52, z - 0.01), (hx + 0.66, GY + 0.54, z + 0.01))


# ---- upper storey --------------------------------------------------------------------


def upper(M):
    m = M.m
    # The white frame round the front, the cladding set back inside it.
    for x0, x1 in ((XA, XA + FT), (XB - FT, XB)):
        m.box("render", (x0, UY, G), (x1, CF, TOP), skip=("y1",))
    m.box("render", (XA + FT, UY, G), (XB - FT, CF, G + FT), skip=("y1", "x0", "x1"))
    m.box("render", (XA + FT, UY, TOP - FT), (XB - FT, CF, TOP), skip=("y1", "x0", "x1"))
    F = front(m, CF)
    ribbon = (-5.55, 0.95, G + 0.85, G + 2.4)
    slot = (1.3, 1.7, G + 0.35, TOP - 0.55)
    F.wall("cladding", XA + FT, XB - FT, G + FT, TOP - FT, [ribbon, slot], depth=DEPTH, reveal="alu")
    glazing(F, -5.55, -2.3, *ribbon[2:], lights=2)
    glazing(F, -2.3, 0.95, *ribbon[2:], lights=2)
    glazing(F, *slot)
    # The underside of the cantilever, in timber, with downlights.
    flat(m, "wood", XA, XB, CF, Y0, G, out=-Z)
    for x in (-4.6, -2.6):
        m.cyl("lamp", x, (CF + Y0) / 2, 0.07, G - 0.02, G, seg=10, top=False, bottom=True)

    L = left(m)
    lw = (0.6, 2.8, G + 0.85, G + 2.4)
    L.wall("cladding", -Y1, -CF, G, TOP, [lw], depth=DEPTH, reveal="alu")
    glazing(L, *lw, lights=2)
    B = back(m)
    juliet = (3.5, 5.4, G + 0.05, G + 2.45)
    bed = (-0.7, 1.5, G + 0.85, G + 2.45)
    B.wall("cladding", -XB, -XA, G, TOP, [juliet, bed], depth=DEPTH, reveal="alu")
    glazing(B, *juliet, lights=2, slide=True)
    glazing(B, *bed, lights=2)
    # A glass balustrade across the French window.
    B.box("canopy", 3.5, 5.4, G + 0.05, G + 1.02, 0.05, 0.065, skip=())
    B.box("alu", 3.47, 5.43, G + 1.02, G + 1.06, 0.04, 0.075, skip=())
    R = right(m, XB)
    rw = (-1.2, 0.8, G + 0.85, G + 2.4)
    R.wall("cladding", CF, Y1, G, TOP, [rw], depth=DEPTH, reveal="alu")
    glazing(R, *rw, lights=2)
    # Flashing where the cladding meets the render.
    m.box("alu", (XA - 0.025, Y0, G - 0.02), (XA, Y1, G + 0.03), skip=("x1",))
    m.box("alu", (XA, Y1, G - 0.02), (XB, Y1 + 0.025, G + 0.03), skip=("y0",))
    m.box("alu", (XB, GY, G - 0.02), (XB + 0.025, Y1, G + 0.03), skip=("x0",))
    flat(m, "dark", XA, XB, UY, Y1, TOP - 0.02)


# ---- roof ---------------------------------------------------------------------------


def roof(M):
    m = M.m
    t = TOP + PAR
    base = TOP + 0.06
    # The frame's top member carries on up as the front parapet.
    m.box("render", (XA, UY, TOP), (XB, CF, t), skip=("z0",))
    m.box("alu", (XA - 0.03, UY - 0.03, t), (XB + 0.03, CF + 0.02, t + 0.04))
    # The other parapets: cladding outside, render inside, aluminium copings.
    m.poly("cladding", [(XA, CF, TOP), (XA, Y1, TOP), (XA, Y1, t), (XA, CF, t)], out=(-1, 0, 0))
    m.poly("cladding", [(XB, CF, TOP), (XB, Y1, TOP), (XB, Y1, t), (XB, CF, t)], out=(1, 0, 0))
    m.poly("cladding", [(XA, Y1, TOP), (XB, Y1, TOP), (XB, Y1, t), (XA, Y1, t)], out=(0, 1, 0))
    xi0, xi1, yi = XA + PT, XB - PT, Y1 - PT
    m.poly("render", [(xi0, CF, base), (xi0, yi, base), (xi0, yi, t), (xi0, CF, t)], out=(1, 0, 0))
    m.poly("render", [(xi1, CF, base), (xi1, yi, base), (xi1, yi, t), (xi1, CF, t)], out=(-1, 0, 0))
    m.poly("render", [(xi0, yi, base), (xi1, yi, base), (xi1, yi, t), (xi0, yi, t)], out=(0, -1, 0))
    m.box("alu", (XA - 0.03, CF, t), (xi0 + 0.02, Y1 + 0.03, t + 0.04))
    m.box("alu", (xi1 - 0.02, CF, t), (XB + 0.03, Y1 + 0.03, t + 0.04))
    m.box("alu", (xi0 + 0.02, yi - 0.02, t), (xi1 - 0.02, Y1 + 0.03, t + 0.04))
    flat(m, "gravel", xi0, xi1, CF, yi, base)
    # Two rows of solar panels facing the street.
    for y0 in (CF + 0.7, CF + 3.3):
        for i in range(7):
            x = xi0 + 0.25 + i * 1.04
            panel(m, x, x + 1.0, y0, y0 + 1.7, base, math.radians(12))
    # A rooflight over the stairs.
    rx, ry = -1.9, Y1 - 1.9
    m.box("alu", (rx, ry, base), (rx + 1.3, ry + 1.0, base + 0.25), skip=("z0", "z1"))
    m.box("alu", (rx - 0.04, ry - 0.04, base + 0.25), (rx + 1.34, ry + 1.04, base + 0.3), skip=("z1",))
    flat(m, "skyglass", rx + 0.04, rx + 1.26, ry + 0.04, ry + 0.96, base + 0.33)
    for x0, x1, y0, y1 in ((rx - 0.04, rx + 1.34, ry - 0.04, ry + 0.04), (rx - 0.04, rx + 1.34, ry + 0.96, ry + 1.04), (rx - 0.04, rx + 0.04, ry + 0.04, ry + 0.96), (rx + 1.26, rx + 1.34, ry + 0.04, ry + 0.96)):
        m.box("alu", (x0, y0, base + 0.3), (x1, y1, base + 0.35), skip=("z0",))
    # The wood stove's twin-wall flue, with its rain cap.
    fx, fy = FLUE
    m.cyl("ac", fx, fy, 0.14, base, base + 0.12, seg=12)
    m.cyl("ac", fx, fy, 0.09, base + 0.12, TOP + 1.3, seg=12, top=False)
    m.cyl("ac", fx, fy, 0.18, TOP + 1.38, TOP + 1.42, seg=12, bottom=True)
    m.cyl("ac", fx, fy, 0.18, TOP + 1.42, TOP + 1.55, seg=12, r1=0.03)
    for a in range(3):
        ang = a * math.tau / 3
        x, y = fx + math.cos(ang) * 0.1, fy + math.sin(ang) * 0.1
        m.box("ac", (x - 0.012, y - 0.012, TOP + 1.3), (x + 0.012, y + 0.012, TOP + 1.38))
    # A spout through the right parapet onto the garage roof.
    m.box("alu", (XB - PT, 0.5, base), (XB + 0.3, 0.7, base + 0.1), skip=("x0",))
