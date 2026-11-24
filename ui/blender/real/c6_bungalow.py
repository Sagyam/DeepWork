# C6, craftsman bungalow: an American Arts and Crafts bungalow, one storey
# on a river-rock foundation under a low front-gabled roof with deep eaves,
# exposed rafter tails and knee braces under the rakes. A broad porch
# under its own gable, off centre, on tapered timber columns standing on
# river-rock piers, with a shingled knee wall; clapboard walls, cedar
# shakes in the gables, grouped three-over-one sashes in wide casings, a
# door with a row of small lights, an outside chimney on the right. The app
# tints siding, shakes, trim, door and roof per house; the garden is drawn
# round it.
#
# Pieces (base at the origin):
#   body   the foundation, walls to the plate, windows, the porch to its beam
#   roof   the main and porch roofs, the gables, braces, rafter tails, the stack's top
import math

from mathutils import Vector

from lib import Model, Side, Z, fpoly, new_id, pane, sash, sides

ID = "c6"
W, D = 9.0, 8.4  # main block
Y0 = -3.2  # front wall: the porch and its steps in front keep the footprint centred
Y1 = Y0 + D
CY = (Y0 + Y1) / 2
BASE = 0.7  # floor level, on the foundation
PLATE = 3.45
PITCH = math.radians(25)
K = math.tan(PITCH)
EAVE, RAKE = 0.75, 0.6
T = 0.16  # roof thickness, measured vertically
RIDGE = PLATE + W / 2 * K
DEPTH = 0.14
PX0, PX1 = -W / 2, 2.3  # the porch, across the front's left part
PCX = (PX0 + PX1) / 2
PY = Y0 - 2.2  # its front edge
PBEAM = 3.0  # top of its beam: the porch roof's wall plate
DOOR = (PCX - 0.46, PCX + 0.46)


def build(out, bake=True):
    M = Model(ID)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, PLATE))
    roof(M)
    M.export(out, bake)


# ---- parts --------------------------------------------------------------------------


def window(F, a, b, c, e, upper=3):
    """A three-over-one sash (`upper` lights across the top sash, one below) in a wide flat casing with a capped head."""
    sash(F, a, b, c, e, D=DEPTH, lights=(1, 1))
    # Muntins in the upper sash only.
    ia, ib, ie = a + 0.07 + 0.05, b - 0.07 - 0.05, e - 0.07 - 0.05
    mid = (c + 0.05 + e - 0.07) / 2 + 0.04
    for i in range(1, upper):
        u = ia + i * (ib - ia) / upper
        F.box("frame", u - 0.014, u + 0.014, mid + 0.025, ie, -DEPTH + 0.085, -DEPTH + 0.1)
    casing(F, a, b, c, e)


def casing(F, a, b, c, e, sill_=True):
    F.box("timber", a - 0.12, a, c, e, 0, 0.03)
    F.box("timber", b, b + 0.12, c, e, 0, 0.03)
    F.box("timber", a - 0.16, b + 0.16, e, e + 0.2, 0, 0.035)
    F.box("timber", a - 0.2, b + 0.2, e + 0.2, e + 0.26, 0, 0.08)
    if sill_:
        F.box("timber", a - 0.16, b + 0.16, c - 0.06, c, -DEPTH + 0.02, 0.07)
        F.box("timber", a - 0.1, b + 0.1, c - 0.16, c - 0.06, 0, 0.03)


def door(F, a, b, c, t):
    """A craftsman door: three tall panels under a dentil shelf and a row of four small lights."""
    wid = new_id()
    d = -DEPTH + 0.03
    F.quad("door", a, b, c, t, d)
    w = b - a
    g0, g1 = t - 0.5, t - 0.16
    F.box("door", a + 0.1, b - 0.1, g0 - 0.03, g1 + 0.03, d, d + 0.02, skip=("back", "front"))
    pane(F, "glass", a, b, c, t, a + 0.1, b - 0.1, g0, g1, d + 0.01, wid)
    for i in range(1, 4):
        u = a + 0.1 + i * (w - 0.2) / 4
        F.box("door", u - 0.015, u + 0.015, g0, g1, d + 0.01, d + 0.03)
    F.box("door", a + 0.06, b - 0.06, g0 - 0.12, g0 - 0.05, d, d + 0.07)
    for i in range(8):
        u = a + 0.1 + (i + 0.5) * (w - 0.2) / 8
        F.box("door", u - 0.02, u + 0.02, g0 - 0.17, g0 - 0.12, d, d + 0.045)
    for i in range(3):
        u0 = a + 0.1 + i * (w - 0.2) / 3
        F.box("door", u0 + 0.04, u0 + (w - 0.2) / 3 - 0.04, c + 0.15, g0 - 0.3, d, d + 0.02)
    F.box("brass", b - 0.13, b - 0.08, c + 0.95, c + 1.1, d, d + 0.06)
    for u0, u1 in ((a, a + 0.05), (b - 0.05, b)):
        F.box("timber", u0, u1, c, t, -DEPTH, -DEPTH + 0.1)
    casing(F, a, b, c, t, sill_=False)


def column(m, x, y, z0, z1, r0=0.22, r1=0.13):
    """A tapered square timber column from z0 to z1, half-widths r0 at the foot to r1 at the head, with a cap."""
    lo = [(x - r0, y - r0), (x + r0, y - r0), (x + r0, y + r0), (x - r0, y + r0)]
    hi = [(x - r1, y - r1), (x + r1, y - r1), (x + r1, y + r1), (x - r1, y + r1)]
    outs = [(0, -1, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0)]
    for i in range(4):
        j = (i + 1) % 4
        m.poly("timber", [(*lo[i], z0), (*lo[j], z0), (*hi[j], z1), (*hi[i], z1)], out=Vector(outs[i]) + Z * 0.05)
    m.box("timber", (x - r1 - 0.05, y - r1 - 0.05, z1), (x + r1 + 0.05, y + r1 + 0.05, z1 + 0.1), skip=("z0",))
    m.box("timber", (x - r0 - 0.03, y - r0 - 0.03, z0), (x + r0 + 0.03, y + r0 + 0.03, z0 + 0.08), skip=("z0",))


def pier(m, x, y, z1, r=0.32):
    m.box("fieldstone", (x - r, y - r, 0), (x + r, y + r, z1), skip=("z0",))
    m.box("stone", (x - r - 0.04, y - r - 0.04, z1), (x + r + 0.04, y + r + 0.04, z1 + 0.08), skip=("z0",))


def brace(m, x, y0, y1, zt, drop):
    """A knee brace under a rake: a post on the wall, an arm out to y1 at zt, and the strut between."""
    s = 1 if y1 > y0 else -1
    m.box("timber", (x - 0.06, min(y0, y0 + s * 0.12), zt - drop), (x + 0.06, max(y0, y0 + s * 0.12), zt), skip=())
    m.box("timber", (x - 0.06, min(y0, y1), zt - 0.16), (x + 0.06, max(y0, y1), zt), skip=())
    m.strut("timber", (x, y0 + s * 0.08, zt - drop + 0.1), (x, y1 - s * 0.12, zt - 0.12), 0.1)


def gable_roof(m, cx, hw, ya, yb, zp, eave, rake_a, rake_b):
    """A front-gabled roof over cx +- hw from ya to yb, wall plate zp: shingle planes, open soffit,
    fascias, barge boards at the ends that have a rake, a ridge cap. Returns the ridge height."""
    zr = zp + hw * K
    ze = zp - eave * K
    y0, y1 = ya - rake_a, yb + rake_b
    for s in (-1, 1):
        xe = cx + s * (hw + eave)
        L = math.hypot(hw + eave, zr - ze)
        top = [(xe, y0, ze + T), (xe, y1, ze + T), (cx, y1, zr + T), (cx, y0, zr + T)]
        m.poly("shingle", top, out=(s * K, 0, 1), uvs=[(0 if s < 0 else y1, 0), (y1 - y0 if s < 0 else y0, 0), (y1 - y0 if s < 0 else y0, L), (0 if s < 0 else y1, L)])
        m.poly("boards", [(xe, y0, ze), (xe, y1, ze), (cx, y1, zr), (cx, y0, zr)], out=(-s * K, 0, -1))
        m.poly("timber", [(xe, y0, ze - 0.02), (xe, y1, ze - 0.02), (xe, y1, ze + T), (xe, y0, ze + T)], out=(s, 0, 0))
        # Rafter tails under the eave, out past the wall, every 0.6 m.
        n = int((y1 - y0) / 0.6)
        for i in range(n + 1):
            y = y0 + 0.1 + i * (y1 - y0 - 0.2) / n
            m.strut("timber", (cx + s * (hw - 0.05), y, zp - 0.075 + 0.05 * K), (cx + s * (hw + eave - 0.02), y, ze - 0.075), 0.06, 0.15)
        for y, rk, o in ((y0, rake_a, -1), (y1, rake_b, 1)):
            if rk <= 0:
                continue
            for dy in (0.0, -o * 0.05):
                m.poly("timber", [(xe, y + dy, ze - 0.14), (cx, y + dy, zr - 0.14), (cx, y + dy, zr + T + 0.02), (xe, y + dy, ze + T + 0.02)], out=(0, o if dy == 0 else -o, 0))
            # The barge board's underside.
            m.poly("timber", [(xe, y, ze - 0.14), (cx, y, zr - 0.14), (cx, y - o * 0.05, zr - 0.14), (xe, y - o * 0.05, ze - 0.14)], out=(-s * K, 0, -1))
    for s in (-1, 1):
        m.poly("shingle", [(cx + s * 0.16, y0 - 0.02, zr + T + 0.02 - 0.16 * K), (cx + s * 0.16, y1 + 0.02, zr + T + 0.02 - 0.16 * K), (cx, y1 + 0.02, zr + T + 0.06), (cx, y0 - 0.02, zr + T + 0.06)], out=(s, 0, 1))
    return zr


# ---- body ---------------------------------------------------------------------------


def body(M):
    m = M.m
    walls = sides(m, W, D, cy=CY)
    c, e = BASE + 0.8, BASE + 2.25
    wins = {
        "front": [(-4.0, -3.45, 2), (-3.35, -2.25, 4), (-2.15, -1.6, 2), (2.85, 3.85, 3)],
        "back": [(-3.3, -2.3, 3), (-1.6, -0.6, 3), (2.6, 3.6, 3)],
        "left": [(-3.0, -2.0, 3), (-1.9, -0.9, 3), (1.4, 2.4, 3)],
        "right": [(-2.2, -1.5, 2), (0.8, 1.5, 2), (2.5, 3.4, 3)],
    }
    doors = {"front": DOOR, "back": (0.6, 1.5)}
    for name, F in walls.items():
        h = W / 2 if name in ("front", "back") else D / 2
        hs = [(a, b, c if b - a > 0.8 else c + 0.6, e) for a, b, _ in wins[name]]
        if name in doors:
            a, b = doors[name]
            hs.append((a, b, BASE, BASE + 2.1))
        F.wall("siding", -h, h, BASE, PLATE, hs, depth=DEPTH, reveal="timber")
        for a, b, n in wins[name]:
            window(F, a, b, c if b - a > 0.8 else c + 0.6, e, upper=n)
        # The foundation in river rock, a water table board over it, corner boards and a frieze under the eaves.
        F.box("fieldstone", -h - 0.06, h + 0.06, 0, BASE, 0, 0.06)
        F.box("timber", -h - 0.05, h + 0.05, BASE, BASE + 0.14, 0, 0.05)
        F.box("timber", -h, -h + 0.14, BASE, PLATE, 0, 0.03)
        F.box("timber", h - 0.14, h, BASE, PLATE, 0, 0.03)
        F.box("timber", -h, h, PLATE - 0.28, PLATE, 0, 0.03)
    for name in doors:
        a, b = doors[name]
        door(walls[name], a, b, BASE, BASE + 2.1)
    porch(m)
    # Back stoop: concrete steps to the kitchen door, a little shed hood on brackets.
    B = walls["back"]
    a, b = doors["back"]
    for i in range(3):
        B.box("concrete", a - 0.3, b + 0.3, 0, BASE - i * BASE / 3, 0, 0.3 * (3 - i) + 0.2, skip=("back", "bottom"))
    B.box("timber", a - 0.4, b + 0.4, BASE + 2.55, BASE + 2.65, 0, 0.75)
    B.box("shingle", a - 0.42, b + 0.42, BASE + 2.65, BASE + 2.7, 0, 0.77)
    for u in (a - 0.3, b + 0.22):
        m.strut("timber", B.p(u + 0.04, BASE + 2.0, 0.05), B.p(u + 0.04, BASE + 2.52, 0.6), 0.08)
    chimney(m, PLATE)
    # A ceiling, seen only when the roof is gone.
    m.poly("dark", [(-W / 2, Y0, PLATE - 0.02), (W / 2, Y0, PLATE - 0.02), (W / 2, Y1, PLATE - 0.02), (-W / 2, Y1, PLATE - 0.02)], out=Z)


def porch(m):
    """The porch: a boarded floor on the foundation, river-rock piers, tapered columns, a shingled knee wall and the beam."""
    x0, x1 = PX0, PX1
    m.box("fieldstone", (x0, PY, 0), (x1, Y0, BASE - 0.06), skip=("z0", "y1"))
    m.box("deck", (x0 - 0.04, PY - 0.04, BASE - 0.06), (x1 + 0.04, Y0, BASE), skip=("y1",))
    knee = BASE + 0.85
    xs = [x0 + 0.32, DOOR[0] - 0.55, DOOR[1] + 0.55, x1 - 0.32]
    for x in xs:
        pier(m, x, PY + 0.32, knee)
        column(m, x, PY + 0.32, knee + 0.08, PBEAM - 0.36)
    # Knee walls between the outer and the inner piers, and back along the sides to the house.
    F = Side(m, (0, PY + 0.32, 0), (1, 0, 0), (0, -1, 0))
    for ua, ub in ((xs[0] + 0.32, xs[1] - 0.32), (xs[2] + 0.32, xs[3] - 0.32)):
        F.box("shake", ua, ub, BASE, knee - 0.06, -0.12, 0.12, skip=())
        F.box("timber", ua - 0.02, ub + 0.02, knee - 0.06, knee, -0.16, 0.16, skip=())
    for x in (x0 + 0.32, x1 - 0.32):
        m.box("shake", (x - 0.12, PY + 0.64, BASE), (x + 0.12, Y0, knee - 0.06), skip=("y1",))
        m.box("timber", (x - 0.16, PY + 0.64, knee - 0.06), (x + 0.16, Y0, knee), skip=("y1",))
    # Steps up between the inner piers.
    a, b = xs[1] + 0.32, xs[2] - 0.32
    n = 3
    for i in range(n):
        m.box("concrete", (a, PY - (n - i) * 0.3, 0), (b, PY, (i + 1) * BASE / n), skip=("z0", "y1"))
    # The beam along the front and the side beams back to the wall, boxed in.
    m.box("timber", (x0, PY + 0.1, PBEAM - 0.36), (x1, PY + 0.55, PBEAM), skip=())
    for x in (x0 + 0.1, x1 - 0.55):
        m.box("timber", (x, PY + 0.55, PBEAM - 0.3), (x + 0.45, Y0, PBEAM), skip=("y1",))
    # A ceiling of beadboard over the porch.
    m.poly("boards", [(x0, PY + 0.55, PBEAM - 0.3), (x1, PY + 0.55, PBEAM - 0.3), (x1, Y0, PBEAM - 0.3), (x0, Y0, PBEAM - 0.3)], out=-Z)
    # A porch light by the door, a swing seat at the left end.
    F = Side(m, (0, Y0, 0), (1, 0, 0), (0, -1, 0))
    F.box("iron", DOOR[1] + 0.3, DOOR[1] + 0.42, BASE + 1.75, BASE + 1.83, 0, 0.14)
    F.box("lamp", DOOR[1] + 0.27, DOOR[1] + 0.45, BASE + 1.83, BASE + 2.1, 0.02, 0.2, skip=())
    sx = x0 + 1.4
    sy = Y0 - 0.75
    m.box("wood", (sx - 0.8, sy - 0.25, BASE + 0.45), (sx + 0.8, sy + 0.25, BASE + 0.5), skip=())
    m.box("wood", (sx - 0.8, sy + 0.2, BASE + 0.5), (sx + 0.8, sy + 0.25, BASE + 0.95), skip=())
    for x in (sx - 0.75, sx + 0.75):
        m.box("iron", (x - 0.01, sy - 0.01, BASE + 0.5), (x + 0.01, sy + 0.01, PBEAM - 0.3))


def chimney(m, top):
    """The outside chimney on the right wall in river rock: a broad base, shoulders, the stack up to the plate."""
    x = W / 2
    yc = CY + 0.6
    m.box("fieldstone", (x, yc - 0.85, 0), (x + 0.62, yc + 0.85, 2.3), skip=("z0", "x0"))
    m.poly("fieldstone", [(x + 0.62, yc - 0.85, 2.3), (x + 0.62, yc + 0.85, 2.3), (x + 0.5, yc + 0.42, 2.9), (x + 0.5, yc - 0.42, 2.9)], out=(1, 0, 1))
    for s in (-1, 1):
        m.poly("fieldstone", [(x, yc + s * 0.85, 2.3), (x + 0.62, yc + s * 0.85, 2.3), (x + 0.5, yc + s * 0.42, 2.9), (x, yc + s * 0.42, 2.9)], out=(0, s, 1))
    m.box("fieldstone", (x, yc - 0.42, 2.9), (x + 0.5, yc + 0.42, top), skip=("z0", "x0"))


# ---- roof ---------------------------------------------------------------------------


def roof(M):
    m = M.m
    gable_roof(m, 0.0, W / 2, Y0, Y1, PLATE, EAVE, RAKE, RAKE)
    # Gables in shakes over a belt board, with a louvred vent in each.
    for y, s in ((Y0, -1), (Y1, 1)):
        m.poly("shake", [(-W / 2, y, PLATE), (W / 2, y, PLATE), (0, y, RIDGE)], out=(0, s, 0))
        m.box("timber", (-W / 2 - 0.04, min(y, y + s * 0.08), PLATE - 0.04), (W / 2 + 0.04, max(y, y + s * 0.08), PLATE + 0.12), skip=())
        G = Side(m, (0, y, 0), (-s, 0, 0), (0, s, 0))
        vz = RIDGE - 1.05
        G.box("timber", -0.5, 0.5, vz - 0.08, vz + 0.62, 0, 0.04)
        G.box("timber", -0.56, 0.56, vz + 0.62, vz + 0.7, 0, 0.09)
        G.box("shutter", -0.42, 0.42, vz, vz + 0.54, 0.04, 0.05, skip=("back", "front"))
        G.quad("shutter", -0.42, 0.42, vz, vz + 0.54, 0.05, uvs=[(0, 0), (1.4, 0), (1.4, 0.9), (0, 0.9)])
        # Knee braces under the rake, at the wall's quarter points.
        for x in (-W / 2 + 0.6, -1.7, 1.7, W / 2 - 0.6):
            zt = PLATE + (W / 2 - abs(x)) * K - 0.02
            brace(m, x, y, y + s * (RAKE - 0.06), zt, 0.9)
    # The porch roof, off centre and lower, back to the front wall.
    hw = (PX1 - PX0) / 2
    zr = gable_roof(m, PCX, hw, PY + 0.1, Y0, PBEAM, 0.45, 0.4, -0.001)
    y = PY + 0.1 - 0.4
    G = Side(m, (PCX, PY + 0.32, 0), (1, 0, 0), (0, -1, 0))
    fpoly(G, "shake", [(-hw, PBEAM), (hw, PBEAM), (0, zr)], w=-0.05)
    fpoly(G, "shake", [(-hw, PBEAM), (0, zr), (hw, PBEAM)], w=-0.3, out=-G.n)
    G.box("timber", -hw - 0.04, hw + 0.04, PBEAM - 0.02, PBEAM + 0.14, -0.06, 0.04, skip=())
    G.box("timber", -0.08, 0.08, PBEAM + 0.14, zr - 0.15, -0.06, 0.04)
    for x in (PCX - hw + 0.5, PCX + hw - 0.5):
        zt = PBEAM + (hw - abs(x - PCX)) * K - 0.02
        brace(m, x, PY + 0.32, y + 0.06, zt, 0.7)
    # The chimney stack, up past the eave beside the ridge.
    x = W / 2
    yc = CY + 0.6
    top = RIDGE + 0.4
    m.box("fieldstone", (x, yc - 0.42, PLATE), (x + 0.5, yc + 0.42, top - 0.15), skip=("z0",))
    m.box("stone", (x - 0.05, yc - 0.47, top - 0.15), (x + 0.55, yc + 0.47, top), skip=())
    m.cyl("terracotta", x + 0.25, yc, 0.12, top, top + 0.35, seg=10, r1=0.1)
