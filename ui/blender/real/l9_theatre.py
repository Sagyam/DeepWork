# L9, the theatre: a Beaux-Arts playhouse of about 1900 on its whole block,
# its front to Founders' Square. Three volumes one behind the other, as such
# theatres are: the foyer block, the auditorium's drum, the fly tower.
#
# The foyer: a rusticated ground storey of seven arched doorways under an
# iron and glass canopy lit with bulbs, the theatre's name on its fascia;
# above, a loggia of paired Corinthian columns before the tall arched
# windows of the grand foyer, a bronze figure in a niche at each end; an
# entablature, and an attic carrying the name again in gilt, gilt figures on
# its corners, a copper roof behind. The auditorium rises behind it as a
# drum ringed with pilasters and round windows lit from inside, under a
# ribbed copper dome with a lantern and a gilt crown. Behind that the fly
# tower, tall and plain, with a lunette and a pediment crowned by a gilt
# figure; at its back the scenery dock's big doors, the stage door on the
# side under a lamp.
#
# Laid out like every model, its front toward -y; the app turns it a
# quarter round to face the square across its site (DEFS.l9 in real.ts).
#
# Pieces (base at the origin, stacked by the app):
#   ground  the ground storey everywhere, the canopy, to 6 m
#   upper   the loggia and its columns, the walls to 14 m
#   roof    entablature, attic, roofs, the drum's top and dome, the fly tower above 14 m
import math

from mathutils import Vector

from civic import lathe
from l5_cityhall import baluster_run
from l7_monument import wreath
from l8_museum import face_x, face_y, figure
from lib import Model, Side, Z, fpoly, letters, new_id, pane, sides

ID = "l9"
G = 6.0  # the ground storey, the loggia's floor
UP = 14.0  # the loggia's columns' tops, the upper piece's top
CORN = 15.6  # the foyer's cornice
ATTIC = 18.2
FW = 13.0  # the foyer's half width
FY0, FY1 = -21.0, -7.0  # its front and back walls
LOG = 1.9  # the loggia's depth
BAYS = [-9.6, -6.4, -3.2, 0.0, 3.2, 6.4, 9.6]
PIERS = [-8.0, -4.8, -1.6, 1.6, 4.8, 8.0]
END = 10.8  # the loggia's end blocks start
CR = 0.3  # the loggia's columns
DY, DR = 1.0, 12.0  # the drum's centre (y) and radius
DTOP = 16.8  # its cornice
DOME0, DOME1 = 17.4, 23.0
TX, TY0, TY1 = 11.5, 8.0, 23.0  # the fly tower
FT = 27.0  # its cornice
APEX = 31.2
KX, KY = 8.0, 26.5  # the scenery dock
KH = 9.0
CAN = 3.4  # how far the canopy reaches
CAN_X = 8.2
SHIFT = -((FY0 - CAN) + (KY + 0.3)) / 2


def build(out, bake=True):
    M = Model(ID, seed=67)
    M.sharp = math.radians(40)
    M.piece("ground")
    ground(M)
    M.piece("upper", (0, 0, G))
    upper(M)
    M.piece("roof", (0, 0, UP))
    roof(M)
    for mesh in (M.m, M.cut, M.decal):
        for v in mesh.bm.verts:
            v.co.y += SHIFT
    M.export(out, bake)


# ---- helpers --------------------------------------------------------------------------


def arch_head(F, a, b, spring, D, role="ashlar", seg=8):
    """Turns a square-headed opening (a..b up to spring + half its width) into
    a round-headed one: spandrels in the wall's plane, the soffit round the curve."""
    mid, r = (a + b) / 2, (b - a) / 2
    e = spring + r
    pts = [(mid - r * math.cos(math.pi * i / seg), spring + r * math.sin(math.pi * i / seg)) for i in range(seg + 1)]
    for (u0, z0), (u1, z1) in zip(pts, pts[1:]):
        fpoly(F, role, [(u0, z0), (u1, z1), (u1, e), (u0, e)])
        um, zm = (u0 + u1) / 2, (z0 + z1) / 2
        F.m.poly(role, [F.p(u0, z0, 0), F.p(u1, z1, 0), F.p(u1, z1, -D), F.p(u0, z0, -D)], out=F.t * (mid - um) + Z * (spring - zm))


def arched_glass(F, role, a, b, c, spring, D, bars=True):
    """Glass in a round-headed opening D deep: a pane to the springing, a
    fanlight over it with radiating bars, a frame round both."""
    mid, r = (a + b) / 2, (b - a) / 2
    e = spring + r
    wid = new_id()
    w = -D + 0.05
    uv = lambda u, z: (wid + (u - a) / (b - a), (z - c) / (e - c))  # noqa: E731
    pane(F, role, a, b, c, e, a, b, c, spring, w, wid)
    seg = 8
    pts = [(mid + r * math.cos(math.pi * i / seg), spring + r * math.sin(math.pi * i / seg)) for i in range(seg + 1)]
    F.m.poly(role, [F.p(u, z, w) for u, z in pts], out=F.n, uvs=[uv(u, z) for u, z in pts])
    fr = "frame"
    F.box(fr, a, a + 0.08, c, spring, w - 0.02, w + 0.06)
    F.box(fr, b - 0.08, b, c, spring, w - 0.02, w + 0.06)
    F.box(fr, a, b, spring - 0.04, spring + 0.04, w - 0.02, w + 0.06)
    F.box(fr, a, b, c, c + 0.08, w - 0.02, w + 0.07)
    F.box(fr, mid - 0.03, mid + 0.03, c, spring, w, w + 0.05)
    if bars:
        for k in range(1, 4):
            ang = math.pi * k / 4
            F.m.strut(fr, F.p(mid, spring, w + 0.03), F.p(mid + math.cos(ang) * r, spring + math.sin(ang) * r, w + 0.03), 0.04)
        for k in range(seg):
            (u0, z0), (u1, z1) = pts[k], pts[k + 1]
            F.m.strut(fr, F.p(u0, z0, w + 0.03), F.p(u1, z1, w + 0.03), 0.07, 0.05)


def surround(F, a, b, spring, w=0.0, t=0.22, role="stone", key=True):
    """A moulded archivolt round a round head, with a keystone."""
    mid, r = (a + b) / 2, (b - a) / 2
    seg = 8
    for i in range(seg):
        a0, a1 = math.pi * i / seg, math.pi * (i + 1) / seg
        pts = [(mid - (r + d) * math.cos(t_), spring + (r + d) * math.sin(t_)) for d, t_ in ((0, a0), (0, a1), (t, a1), (t, a0))]
        fpoly(F, role, pts, w + 0.05)
    if key:
        F.box(role, mid - 0.2, mid + 0.2, spring + r - 0.05, spring + r + t + 0.15, w, w + 0.12)


def runs(u0, u1, z, holes):
    """The stretches of u0..u1 at height z that no opening crosses."""
    out, u = [], u0
    for a, b in sorted((h[0], h[1]) for h in holes if h[2] <= z <= h[3]):
        if a > u + 1e-6:
            out.append((u, a))
        u = max(u, b)
    if u1 > u + 1e-6:
        out.append((u, u1))
    return out


def rustication(F, u0, u1, z0, z1, holes=(), step=0.6):
    """Channelled joints across a rusticated storey, a granite plinth at its foot, both broken by the openings."""
    for a, b in runs(u0 - 0.04, u1 + 0.04, z0 + 0.25, holes):
        F.box("granite", a, b, z0, z0 + 0.5, 0, 0.1)
    z = z0 + 0.5 + step
    while z < z1 - 0.2:
        for a, b in runs(u0, u1, z, holes):
            F.box("dark", a, b, z - 0.025, z + 0.025, -0.001, 0.004)
        z += step


def column(m, x, y, z0, z1, r=CR):
    """A Corinthian column from z0 to z1: an Attic base, a plain shaft with a
    gentle entasis, a bell of two rings of leaves under a moulded abacus."""
    lathe(m, "stone", [(r + 0.14, z0), (r + 0.14, z0 + 0.1), (r + 0.06, z0 + 0.18), (r + 0.09, z0 + 0.26), (r, z0 + 0.34)], seg=14, c=(x, y), uv=False)
    zc = z1 - 0.85
    zs = [z0 + 0.34, (z0 + 0.34 + zc) / 2, zc]
    rz = lambda z: r * (1 - 0.12 * (z - zs[0]) / (zc - zs[0]))  # noqa: E731
    lathe(m, "stone", [(rz(z), z) for z in zs], seg=14, c=(x, y), uv=False)
    rt = rz(zc)
    lathe(m, "stone", [(rt + 0.04, zc), (rt + 0.04, zc + 0.05), (rt, zc + 0.07), (rt * 1.02, zc + 0.3), (rt * 1.18, zc + 0.56), (rt * 1.4, zc + 0.7)], seg=14, c=(x, y), uv=False)
    for ring, (za, zb, out) in enumerate(((zc + 0.08, zc + 0.36, 0.14), (zc + 0.3, zc + 0.62, 0.2))):
        for i in range(8):
            ang = (i + 0.5 * ring) / 8 * math.tau
            c_, s_ = math.cos(ang), math.sin(ang)
            m.strut("stone", (x + c_ * rt, y + s_ * rt, za), (x + c_ * (rt + out), y + s_ * (rt + out), zb), 0.12, 0.05)
    a = r + 0.32
    m.box("stone", (x - a, y - a, z1 - 0.15), (x + a, y + a, z1))


def hip(m, role, x0, x1, y0, y1, z0, z1):
    """A hipped roof over a rectangle longer in x: four slopes to a ridge along x."""
    hd = (y1 - y0) / 2
    cy = (y0 + y1) / 2
    r0, r1 = x0 + hd, x1 - hd
    m.poly(role, [(x0, y0, z0), (x1, y0, z0), (r1, cy, z1), (r0, cy, z1)], out=(0, -1, 1))
    m.poly(role, [(x1, y1, z0), (x0, y1, z0), (r0, cy, z1), (r1, cy, z1)], out=(0, 1, 1))
    m.poly(role, [(x1, y0, z0), (x1, y1, z0), (r1, cy, z1)], out=(1, 0, 1))
    m.poly(role, [(x0, y1, z0), (x0, y0, z0), (r0, cy, z1)], out=(-1, 0, 1))
    # Standing seams down the long slopes, a roll on the ridge and hips.
    n = int((x1 - x0) / 0.9)
    for i in range(1, n):
        x = x0 + i * (x1 - x0) / n
        t = min(1.0, (x - x0) / hd, (x1 - x) / hd)
        for yy in (y0, y1):
            m.strut(role, (x, yy, z0 + 0.02), (x, yy + (cy - yy) * t, z0 + (z1 - z0) * t + 0.02), 0.04, 0.05)
    m.strut(role, (r0, cy, z1 + 0.04), (r1, cy, z1 + 0.04), 0.14, 0.1)
    for a, b in (((x0, y0), (r0, cy)), ((x1, y0), (r1, cy)), ((x0, y1), (r0, cy)), ((x1, y1), (r1, cy))):
        m.strut(role, (*a, z0 + 0.04), (*b, z1 + 0.04), 0.12, 0.1)


def entablature(m, x0, x1, y0, y1, z0, z1, faces, dentils=True):
    """Architrave, frieze and cornice from z0 to z1 over a rectangle; `faces` names the sides that show."""
    W, D = x1 - x0, y1 - y0
    cz = z1 - 0.5
    m.box("stone", (x0, y0, z0), (x1, y1, cz))
    S = sides(m, W, D, (x0 + x1) / 2, (y0 + y1) / 2)
    for name in faces:
        F = S[name]
        h = W / 2 if name in ("front", "back") else D / 2
        F.box("stone", -h, h, z0, z0 + 0.22, 0, 0.03)
        F.box("stone", -h, h, z0 + 0.22, z0 + 0.48, 0, 0.06)
        F.box("stone", -h - 0.02, h + 0.02, z0 + 0.48, z0 + 0.56, 0, 0.1)
        if dentils:
            n = int(2 * h / 0.3)
            for i in range(n):
                u = -h + (i + 0.5) * 2 * h / n
                F.box("stone", u - 0.07, u + 0.07, cz, cz + 0.14, 0.02, 0.15)
    m.sweep("stone", W, D, [(0.0, cz), (0.18, cz + 0.14), (0.22, cz + 0.17), (0.5, cz + 0.32), (0.55, cz + 0.38), (0.55, cz + 0.44), (0.48, z1), (0.0, z1)], (x0 + x1) / 2, (y0 + y1) / 2)
    m.poly("lead", [(x0, y0, z1 - 0.01), (x1, y0, z1 - 0.01), (x1, y1, z1 - 0.01), (x0, y1, z1 - 0.01)], out=Z)


# ---- the ground storey ------------------------------------------------------------------


def ground(M):
    m = M.m
    foyer_ground(m)
    canopy(M)
    drum(m, 0.0, G)
    tower(m, 0.0, G)
    dock(m)


def foyer_ground(m):
    """Seven round-headed doorways across the front, three windows down each side, all in rustication."""
    F = face_y(m, FY0, -1)
    holes = [(u - 1.1, u + 1.1, 0.0, 3.6 + 1.1, 0.5) for u in BAYS]
    F.wall("ashlar", -FW, FW, 0.0, G, holes, depth=0.5)
    rustication(F, -FW, FW, 0.0, G - 0.4, holes)
    for a, b, c, e, D in holes:
        arch_head(F, a, b, 3.6, D)
        # Glazed doors in pairs, a fanlight over them.
        arched_glass(F, "doorglass", a, b, c, 3.6, D)
        F.box("door", a + 0.08, b - 0.08, 0.0, 0.9, -D + 0.06, -D + 0.12)
        surround(F, a, b, 3.6)
    # Posters in brass frames on the piers.
    for i, u in enumerate(PIERS):
        F.box("brass", u - 0.42, u + 0.42, 1.0, 2.6, 0, 0.05)
        F.quad("banner" if i % 2 else "banner2", u - 0.36, u + 0.36, 1.06, 2.54, 0.055)
        F.quad("paint", u - 0.36, u + 0.36, 2.1, 2.3, 0.057)
    F.box("stone", -FW - 0.06, FW + 0.06, G - 0.4, G, 0, 0.2)
    for s in (-1, 1):
        S = face_x(m, s * FW, s)
        u0, u1 = sorted((s * FY0, s * FY1))
        holes = [(s * y - 1.0, s * y + 1.0, 1.0, 3.6 + 1.0, 0.4) for y in (-18.0, -14.0, -10.0)]
        S.wall("ashlar", u0, u1, 0.0, G, holes, depth=0.4)
        rustication(S, u0, u1, 0.0, G - 0.4, holes)
        for a, b, c, e, D in holes:
            arch_head(S, a, b, 3.6, D)
            arched_glass(S, "doorglass", a, b, c, 3.6, D)
            surround(S, a, b, 3.6)
        S.box("stone", u0 - 0.06, u1 + 0.06, G - 0.4, G, 0, 0.2)
    # The back, where it shows either side of the drum.
    B = face_y(m, FY1, 1)
    B.wall("ashlar", -FW, FW, 0.0, G, [])
    rustication(B, -FW, FW, 0.0, G - 0.4)


def canopy(M):
    """The iron and glass canopy over the five middle doors: bulbs round its
    edge and under it, the name on its fascia, rods back to the piers."""
    m = M.m
    y0, y1 = FY0 - CAN, FY0
    zb, zt = 4.45, 5.2
    m.poly("paint", [(-CAN_X, y0, zb), (CAN_X, y0, zb), (CAN_X, y1, zb), (-CAN_X, y1, zb)], out=-Z)
    m.poly("skyglass", [(-CAN_X, y0, zt - 0.05), (CAN_X, y0, zt - 0.05), (CAN_X, y1, zt + 0.1), (-CAN_X, y1, zt + 0.1)], out=Z)
    # Glazing bars over the glass, front to back, and a ridge rail along it.
    n = int(2 * CAN_X / 0.7)
    for i in range(n + 1):
        x = -CAN_X + i * 2 * CAN_X / n
        m.strut("iron", (x, y0, zt - 0.02), (x, y1, zt + 0.13), 0.05, 0.06)
    for y, z in ((y0 + 1.1, zt + 0.02), (y0 + 2.3, zt + 0.07)):
        m.strut("iron", (-CAN_X, y, z), (CAN_X, y, z), 0.04, 0.05)
    F = face_y(m, y0, -1)
    F.box("iron", -CAN_X, CAN_X, zb - 0.05, zt, 0, 0.08)
    for s in (-1, 1):
        S = face_x(m, s * CAN_X, s)
        S.box("iron", *sorted((s * y0, s * y1)), zb - 0.05, zt, 0, 0.08)
    F.quad("theatrename", -5.3, 5.3, zb + 0.06, zt - 0.06, 0.081, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    # Bulbs along the fascia's foot, in rows under the soffit.
    n = int(2 * CAN_X / 0.4)
    for i in range(n + 1):
        x = -CAN_X + i * 2 * CAN_X / n
        m.box("bulb", (x - 0.05, y0 - 0.13, zb - 0.12), (x + 0.05, y0 - 0.03, zb - 0.02))
    for k in range(3):
        y = y0 + 0.7 + k * (CAN - 1.2) / 2
        for i in range(9):
            x = -CAN_X + 0.9 + i * (2 * CAN_X - 1.8) / 8
            m.cyl("bulb", x, y, 0.08, zb - 0.1, zb, seg=6, top=False, bottom=True)
    for x in PIERS:
        m.strut("iron", (x, FY0, 6.6), (x, y0 + 0.2, zt), 0.05)


# ---- the loggia ------------------------------------------------------------------------


def upper(M):
    m = M.m
    loggia(m)
    face_y(m, FY1, 1).wall("ashlar", -FW, FW, G, UP, [])
    for s in (-1, 1):
        S = face_x(m, s * FW, s)
        u0, u1 = sorted((s * FY0, s * FY1))
        holes = [(s * y - 0.9, s * y + 0.9, 7.2, 11.3 + 0.9, 0.4) for y in (-18.0, -14.0, -10.0)]
        S.wall("ashlar", u0, u1, G, UP, holes, depth=0.4)
        for a, b, c, e, D in holes:
            arch_head(S, a, b, 11.3, D)
            arched_glass(S, "doorglass", a, b, c, 11.3, D)
            surround(S, a, b, 11.3)
            S.box("stone", a - 0.15, b + 0.15, c - 0.12, c, 0, 0.12)
        for y in (-20.6, -16.0, -12.0, -7.4):
            S.box("stone", s * y - 0.3, s * y + 0.3, G, UP, 0, 0.1)
    drum(m, G, UP)
    tower(m, G, UP)


def loggia(m):
    """Paired columns on pedestals with a balustrade between, before the
    grand foyer's arched windows; solid end blocks, each with a figure in a niche."""
    F = face_y(m, FY0, -1)
    yc = FY0 + 0.45  # the columns' line
    # The floor and the back wall with its windows.
    m.poly("stone", [(-END, FY0, G + 0.002), (END, FY0, G + 0.002), (END, FY0 + LOG, G + 0.002), (-END, FY0 + LOG, G + 0.002)], out=Z)
    W_ = face_y(m, FY0 + LOG, -1)
    wins = [(u - (0.9 if abs(u) > 9 else 1.0), u + (0.9 if abs(u) > 9 else 1.0), 7.0, 11.6 + (0.9 if abs(u) > 9 else 1.0), 0.35) for u in BAYS]
    W_.wall("ashlar", -END, END, G, UP, wins, depth=0.35)
    for a, b, c, e, D in wins:
        spring = e - (b - a) / 2
        arch_head(W_, a, b, spring, D)
        arched_glass(W_, "doorglass", a, b, c, spring, D)
        surround(W_, a, b, spring)
    for u in PIERS:
        W_.box("stone", u - 0.35, u + 0.35, G, UP, 0, 0.1)
    # Pedestals and paired columns at each pier, the balustrade between.
    for u in PIERS:
        m.box("stone", (u - 0.95, FY0, G), (u + 0.95, FY0 + 0.95, G + 1.2))
        m.box("stone", (u - 1.0, FY0 - 0.05, G + 1.1), (u + 1.0, FY0 + 1.0, G + 1.2))
        for k in (-1, 1):
            column(m, u + k * 0.45, yc, G + 1.2, UP)
    for a, b in zip([-END] + PIERS, PIERS + [END]):
        a_ = a + (0 if a == -END else 0.95)
        b_ = b - (0 if b == END else 0.95)
        baluster_run(m, (a_, yc), (b_, yc), G, h=1.0, step=0.3)
    # The end blocks: ashlar, a niche with a bronze figure, pilasters.
    for s in (-1, 1):
        a, b = sorted((s * END, s * FW))
        mid = (a + b) / 2
        niche = [(mid - 0.65, mid + 0.65, G + 1.2, G + 5.4, 0.55)]
        F.wall("ashlar", a, b, G, UP, niche, depth=0.55)
        for na, nb, c, e, D in niche:
            F.quad("ashlar", na, nb, c, e, -D)
            arch_head(F, na, nb, e - 0.65, D)
            surround(F, na, nb, e - 0.65, key=False)
            F.box("stone", na - 0.2, nb + 0.2, c - 0.15, c, 0, 0.15)
            figure(m, "statuary", mid, FY0 + 0.3, c, 2.3, lean=-0.5 * s, seg=7)
        for u in (a + 0.3, b - 0.3):
            F.box("stone", u - 0.28, u + 0.28, G, UP, 0, 0.12)
        # The end walls of the loggia, inside.
        I = face_x(m, s * END, -s)
        I.wall("ashlar", *sorted((-s * FY0, -s * (FY0 + LOG))), G, UP, [])


# ---- entablature, attic and the roofs ---------------------------------------------------


def roof(M):
    m = M.m
    entablature(m, -FW, FW, FY0, FY1, UP, CORN, ["front", "right", "left"])
    # Coffers in the loggia's ceiling.
    for u in BAYS:
        hw = 0.9 if abs(u) > 9 else 1.1
        m.box("dark", (u - hw, FY0 + 0.6, UP - 0.001), (u + hw, FY0 + LOG - 0.25, UP), skip=("z1",))
    attic(M)
    drum(m, UP, DTOP)
    dome(m)
    tower(m, UP, FT)
    gable(m)


def attic(M):
    """The foyer's attic: the name in gilt on a panel between wreaths, plinths
    at the corners with gilt figures, a copper roof behind."""
    m = M.m
    x0, x1, y0, y1 = -FW + 0.2, FW - 0.2, FY0 + 0.2, FY1 - 0.2
    S = sides(m, x1 - x0, y1 - y0, 0, (y0 + y1) / 2, CORN)
    h = ATTIC - CORN
    for name, F in S.items():
        hw = (x1 - x0) / 2 if name in ("front", "back") else (y1 - y0) / 2
        F.wall("ashlar", -hw, hw, 0.0, h, [])
        F.box("stone", -hw, hw, 0.0, 0.2, 0, 0.08)
    m.sweep("stone", x1 - x0, y1 - y0, [(0.0, ATTIC - 0.3), (0.12, ATTIC - 0.2), (0.25, ATTIC - 0.08), (0.25, ATTIC), (0.0, ATTIC)], 0, (y0 + y1) / 2)
    F = S["front"]
    F.box("stone", -7.6, 7.6, 0.45, h - 0.45, 0, 0.08)
    F.quad("jet", -7.4, 7.4, 0.55, h - 0.55, 0.081)
    F.quad("theatrename", -7.3, 7.3, h / 2 - 0.46, h / 2 + 0.46, 0.083, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    for u in (-9.6, 9.6):
        wreath(m, F, u, h / 2, 0.55, 0.0)
    # The corner plinths with gilt figures.
    for s in (-1, 1):
        x = s * (FW - 0.9)
        m.box("stone", (x - 0.8, y0 - 0.15, ATTIC), (x + 0.8, y0 + 1.45, ATTIC + 0.9))
        m.box("stone", (x - 0.9, y0 - 0.25, ATTIC + 0.8), (x + 0.9, y0 + 1.55, ATTIC + 0.95))
        figure(m, "gilt", x, y0 + 0.65, ATTIC + 0.95, 2.6, lean=-0.6 * s, seg=7)
    hip(m, "copper", x0 + 0.4, x1 - 0.4, y0 + 0.4, y1 - 0.3, ATTIC - 0.05, ATTIC + 3.0)


# ---- the auditorium's drum and dome ------------------------------------------------------


def drum(m, z0, z1):
    """The drum's wall from z0 to z1: courses, pilasters, and in each bay a
    round window lit from the house inside (the upper register)."""
    prof = [(DR, z0), (DR, z1)]
    lathe(m, "ashlar", prof, seg=40, c=(0, DY))
    if z0 == 0:
        lathe(m, "granite", [(DR + 0.12, 0.0), (DR + 0.12, 0.5), (DR, 0.55)], seg=40, c=(0, DY), uv=False)
        lathe(m, "stone", [(DR, G - 0.35), (DR + 0.15, G - 0.3), (DR + 0.15, G), (DR, G)], seg=40, c=(0, DY), uv=False)
    if z1 == DTOP:
        lathe(m, "stone", [(DR, UP), (DR + 0.12, UP + 0.1), (DR + 0.12, UP + 0.35), (DR, UP + 0.4)], seg=40, c=(0, DY), uv=False)
        lathe(m, "stone", [(DR, DTOP - 0.7), (DR + 0.2, DTOP - 0.55), (DR + 0.5, DTOP - 0.25), (DR + 0.55, DTOP - 0.1), (DR + 0.5, DTOP), (DR - 0.4, DTOP), (DR - 0.4, DOME0), (DR - 0.6, DOME0)], seg=40, c=(0, DY), uv=False)
    n = 20
    for i in range(n):
        a = (i + 0.5) / n * math.tau
        # Only the bays that show: between the foyer and the fly tower.
        y = DY + math.sin(a) * DR
        if y > TY0 + 0.5 or y < FY1 - 0.5:
            continue
        P = Side(m, (math.cos(a) * DR, y, 0), (-math.sin(a), math.cos(a), 0), (math.cos(a), math.sin(a), 0))
        P.box("stone", -0.35, 0.35, z0, z1 if z1 < DTOP else DTOP - 0.7, 0, 0.14)
        b = a + math.pi / n
        yb = DY + math.sin(b) * DR
        if yb > TY0 + 0.3 or yb < FY1 - 0.3:
            continue
        Q = Side(m, (math.cos(b) * DR, yb, 0), (-math.sin(b), math.cos(b), 0), (math.cos(b), math.sin(b), 0))
        if z0 == 0:
            Q.box("stone", -0.9, 0.9, 1.0, 4.6, 0, 0.05)
            Q.quad("ashlar", -0.75, 0.75, 1.15, 4.45, 0.051)
        elif z0 == G:
            Q.box("stone", -0.9, 0.9, 7.0, 9.8, 0, 0.05)
            seg = 14
            r = 0.75
            ring = [(math.cos(k / seg * math.tau), math.sin(k / seg * math.tau)) for k in range(seg)]
            fpoly(Q, "stone", [(c * (r + 0.2), 11.8 + s_ * (r + 0.2)) for c, s_ in ring], 0.05)
            fpoly(Q, "crownglass", [(c * r, 11.8 + s_ * r) for c, s_ in ring], 0.07)
            for k in range(4):
                ang = k / 4 * math.pi
                m.strut("iron", Q.p(math.cos(ang) * r, 11.8 + math.sin(ang) * r, 0.08), Q.p(-math.cos(ang) * r, 11.8 - math.sin(ang) * r, 0.08), 0.04)


def dome(m):
    """A ribbed copper dome over the drum, a lantern of columns and a gilt crown on top."""
    R0 = DR - 0.5
    steps = 10
    prof = [(R0, DOME0)]
    for i in range(1, steps + 1):
        t = i / steps * (math.pi / 2) * 0.86
        prof.append((R0 * math.cos(t), DOME0 + (DOME1 - DOME0) * math.sin(t) / math.sin(math.pi / 2 * 0.86)))
    top_r = prof[-1][0]
    lathe(m, "copper", prof, seg=40, c=(0, DY), uv=False)
    for i in range(16):
        a = i / 16 * math.tau
        pts = [Vector((math.cos(a) * (r + 0.04), DY + math.sin(a) * (r + 0.04), z)) for r, z in prof]
        for p, q in zip(pts, pts[1:]):
            m.strut("copper", p, q, 0.12, 0.08)
    # Round dormers in the dome, facing out between ribs.
    for i in range(8):
        a = (i + 0.5) / 8 * math.tau
        r = R0 * math.cos(0.35) + 0.1
        x, y = math.cos(a) * r, DY + math.sin(a) * r
        z = DOME0 + (DOME1 - DOME0) * math.sin(0.35) / math.sin(math.pi / 2 * 0.86)
        Q = Side(m, (x, y, 0), (-math.sin(a), math.cos(a), 0), (math.cos(a), math.sin(a), 0))
        Q.box("copper", -0.6, 0.6, z - 0.1, z + 1.3, -0.6, 0.15)
        fpoly(Q, "crownglass", [(-0.4, z + 0.1), (0.4, z + 0.1), (0.4, z + 0.8), (0, z + 1.15), (-0.4, z + 0.8)], 0.16)
    m.poly("copper", [(top_r * math.cos(k / 40 * math.tau), DY + top_r * math.sin(k / 40 * math.tau), DOME1) for k in range(40)], out=Z)
    # The lantern: a ring of columns round a lit core, a cap, the gilt crown.
    L0, L1 = DOME1, DOME1 + 2.0
    m.cyl("crownglass", 0, DY, 1.1, L0, L1, seg=12, top=False)
    for i in range(8):
        a = i / 8 * math.tau
        m.cyl("stone", math.cos(a) * 1.45, DY + math.sin(a) * 1.45, 0.11, L0, L1, seg=8)
    lathe(m, "stone", [(1.75, L1), (1.75, L1 + 0.3), (1.9, L1 + 0.42), (0.0, L1 + 0.42)], seg=16, c=(0, DY), uv=False)
    lathe(m, "copper", [(1.5, L1 + 0.42), (1.2, L1 + 0.9), (0.6, L1 + 1.3), (0.15, L1 + 1.45)], seg=16, c=(0, DY), uv=False)
    lathe(m, "gilt", [(0.35, L1 + 1.45), (0.45, L1 + 1.65), (0.3, L1 + 1.95), (0.42, L1 + 2.2), (0.05, L1 + 2.6)], seg=12, c=(0, DY), uv=False)
    for i in range(8):
        a = i / 8 * math.tau
        m.strut("gilt", (math.cos(a) * 0.35, DY + math.sin(a) * 0.35, L1 + 1.8), (math.cos(a) * 0.7, DY + math.sin(a) * 0.7, L1 + 2.25), 0.06)


# ---- the fly tower and the scenery dock -------------------------------------------------


def tower(m, z0, z1):
    """The fly tower's walls from z0 to z1: pilaster strips, rows of
    dressing-room windows on the sides, tall blind arcades above, a lunette to the front."""
    F = face_y(m, TY0, -1)
    holes = []
    if z1 == FT:
        holes = [(-4.0, 4.0, 20.0, 24.0, 0.4)]
    F.wall("ashlar", -TX, TX, z0, z1, holes, depth=0.4)
    for a, b, c, e, D in holes:
        arch_head(F, a, b, 20.0, D)
        fpoly(F, "crownglass", [(a + 4 * (1 - math.cos(math.pi * i / 8)), 20.0 + 4 * math.sin(math.pi * i / 8)) for i in range(9)], -D + 0.05)
        for k in range(1, 8):
            u = a + k * (b - a) / 8
            h = math.sqrt(max(0.0, 16 - (u - (a + b) / 2) ** 2))
            F.box("frame", u - 0.04, u + 0.04, 20.0, 20.0 + h, -D + 0.05, -D + 0.1)
        surround(F, a, b, 20.0, t=0.35)
        F.box("stone", a - 0.2, b + 0.2, 19.7, 20.0, 0, 0.2)
    for u in (-TX + 0.4, TX - 0.4):
        F.box("stone", u - 0.4, u + 0.4, z0, z1, 0, 0.15)
    B = face_y(m, TY1, 1)
    # Above the dock, the back carries the sides' blind arcade.
    panels = [(u - 1.6, u + 1.6, max(z0, KH + 1.5), min(z1, 24.8), 0.25) for u in (-7.6, -2.55, 2.55, 7.6)] if z1 > KH + 1.5 else []
    B.wall("ashlar", -TX, TX, z0, z1, panels, depth=0.25)
    for a, b, c, e, D in panels:
        B.quad("ashlar", a, b, c, e, -D)
        if e >= 24.8 - 1e-6:
            arch_head(B, a, b, 24.8 - 1.6, D)
    for u in (-5.1, 0.0, 5.1):
        B.box("stone", u - 0.35, u + 0.35, max(z0, KH), z1, 0, 0.12)
    for u in (-TX + 0.4, TX - 0.4):
        B.box("stone", u - 0.4, u + 0.4, z0, z1, 0, 0.15)
    for s in (-1, 1):
        S = face_x(m, s * TX, s)
        u0, u1 = sorted((s * TY0, s * TY1))
        holes = []
        for y in (14.5, 17.5, 20.5):
            for c, e in ((2.2, 3.8), (7.6, 9.2), (10.6, 12.2)):
                if c >= z0 - 1e-6 and e <= z1 + 1e-6:
                    holes.append((s * y - 0.55, s * y + 0.55, c, e, 0.3))
        panels = [(s * y - 1.1, s * y + 1.1, max(z0, 15.4), min(z1, 24.8), 0.25) for y in (11.0, 14.5, 17.5, 20.5)] if z1 > 15.4 else []
        S.wall("ashlar", u0, u1, z0, z1, holes + panels, depth=0.3)
        for a, b, c, e, D in panels:
            S.quad("ashlar", a, b, c, e, -D)
            if e >= 24.8 - 1e-6:
                arch_head(S, a, b, 24.8 - 1.1, D)
        for a, b, c, e, D in holes:
            wid = new_id()
            pane(S, "glass", a, b, c, e, a, b, c, e, -D + 0.05, wid)
            S.box("frame", a, b, (c + e) / 2 - 0.03, (c + e) / 2 + 0.03, -D + 0.05, -D + 0.1)
            S.box("stone", a - 0.1, b + 0.1, c - 0.1, c, 0, 0.1)
            S.box("stone", a - 0.1, b + 0.1, e, e + 0.18, 0, 0.06)
        for y in (TY0 + 0.4, 12.75, 16.0, 19.0, TY1 - 0.4):
            S.box("stone", s * y - 0.35, s * y + 0.35, z0, z1, 0, 0.12)
        if z0 == 0:
            S.box("granite", u0 - 0.04, u1 + 0.04, 0.0, 0.5, 0, 0.1)
        if z0 < G <= z1:
            S.box("stone", u0, u1, G - 0.3, G, 0, 0.15)
        if s > 0 and z0 == 0:
            stage_door(m, S)


def stage_door(m, S):
    """The stage door on the fly tower's side: a panelled door, STAGE DOOR over it, a lamp on a bracket."""
    u = 11.0
    a, b, e = u - 0.6, u + 0.6, 2.5
    S.quad("door2", a, b, 0.0, e, 0.01)
    for z in (0.3, 1.4):
        S.box("door2", a + 0.12, b - 0.12, z, z + 0.85, 0.01, 0.04)
    S.box("stone", a - 0.25, b + 0.25, e, e + 0.25, 0, 0.12)
    for x in (a - 0.25, b):
        S.box("stone", x, x + 0.25, 0.0, e, 0, 0.12)
    letters(m, "fireletter", S, u, e + 0.55, 0.0, "STAGE DOOR", 0.2, depth=0.02, spacing=1.2)
    S.box("iron", b + 0.5, b + 0.56, e + 0.3, e + 0.36, 0, 0.6)
    p = S.p(b + 0.53, e + 0.05, 0.6)
    m.cyl("lamp", p.x, p.y, 0.16, p.z - 0.4, p.z, seg=8, bottom=True, r1=0.19)
    m.cyl("iron", p.x, p.y, 0.21, p.z, p.z + 0.08, seg=8, r1=0.04)


def gable(m):
    """The fly tower's cornice, its gabled copper roof, the pediments, the gilt figures."""
    W, D = 2 * TX, TY1 - TY0
    cy = (TY0 + TY1) / 2
    m.sweep("stone", W, D, [(0.0, FT - 0.6), (0.15, FT - 0.45), (0.4, FT - 0.25), (0.45, FT - 0.1), (0.4, FT), (0.0, FT)], 0, cy)
    m.poly("lead", [(-TX, TY0, FT - 0.01), (TX, TY0, FT - 0.01), (TX, TY1, FT - 0.01), (-TX, TY1, FT - 0.01)], out=Z)
    for y, sgn in ((TY0, -1), (TY1, 1)):
        F = face_y(m, y, sgn)
        fpoly(F, "ashlar", [(-TX, FT), (TX, FT), (0, APEX)], 0.0)
        for s in (-1, 1):
            a = F.p(s * (TX + 0.45), FT - 0.05, 0.45)
            b = F.p(0, APEX + 0.25, 0.45)
            m.strut("stone", a + (b - a).normalized() * 0.0, b, 0.5, 0.35)
    for s in (-1, 1):
        A, Bp = Vector((s * (TX + 0.45), TY0 - 0.45, FT - 0.05)), Vector((0, TY0 - 0.45, APEX + 0.1))
        A1, B1 = Vector((s * (TX + 0.45), TY1 + 0.45, FT - 0.05)), Vector((0, TY1 + 0.45, APEX + 0.1))
        m.poly("copper", [A, Bp, B1, A1], out=(s * 0.35, 0, 1))
        n = int(D / 0.9)
        for i in range(1, n):
            y = TY0 + i * D / n
            m.strut("copper", (s * (TX + 0.4), y, FT), (0, y, APEX + 0.12), 0.05, 0.05)
    m.strut("copper", (0, TY0 - 0.45, APEX + 0.15), (0, TY1 + 0.45, APEX + 0.15), 0.16, 0.12)
    # A gilt figure with a raised arm on the apex, two more at the front's corners.
    m.box("stone", (-0.7, TY0 - 0.6, APEX - 0.3), (0.7, TY0 + 0.6, APEX + 0.6))
    figure(m, "gilt", 0, TY0, APEX + 0.6, 3.4, lean=0.7, seg=7)
    for s in (-1, 1):
        x = s * (TX - 0.3)
        m.box("stone", (x - 0.6, TY0 - 0.6, FT), (x + 0.6, TY0 + 0.6, FT + 0.7))
        figure(m, "gilt", x, TY0, FT + 0.7, 2.4, lean=-0.6 * s, seg=7)


def dock(m):
    """The scenery dock behind the fly tower: tall doors for the flats, a lamp over them."""
    W, D = 2 * KX, KY - TY1
    cy = (TY1 + KY) / 2
    S = sides(m, W, D, 0, cy)
    for name, F in S.items():
        if name == "front":
            continue
        h = W / 2 if name in ("front", "back") else D / 2
        holes = [(-2.6, 2.6, 0.0, 6.4, 0.3)] if name == "back" else []
        F.wall("ashlar", -h, h, 0.0, KH, holes, depth=0.3)
        F.box("granite", -h - 0.04, h + 0.04, 0.0, 0.5, 0, 0.1)
        for a, b, c, e, D_ in holes:
            F.quad("doors", a, b, c, e, -D_)
            F.box("iron", a, b, e - 0.2, e, -D_, -D_ + 0.06)
            F.box("iron", -0.03, 0.03, c, e - 0.2, -D_, -D_ + 0.06)
            F.box("stone", a - 0.3, b + 0.3, e, e + 0.5, 0, 0.12)
            m.cyl("lamp", 0, KY + 0.5, 0.18, e + 0.8, e + 1.3, seg=8, bottom=True, r1=0.2)
            m.cyl("iron", 0, KY + 0.5, 0.22, e + 1.3, e + 1.38, seg=8, r1=0.04)
            F.box("iron", -0.03, 0.03, e + 1.3, e + 1.4, 0, 0.5)
    m.sweep("stone", W, D, [(0.0, KH - 0.4), (0.25, KH - 0.2), (0.3, KH), (0.0, KH)], 0, cy)
    m.poly("lead", [(-KX, TY1, KH - 0.01), (KX, TY1, KH - 0.01), (KX, KY, KH - 0.01), (-KX, KY, KH - 0.01)], out=Z)
