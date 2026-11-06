# E2, police station: the City's divisional station of about 1910, an
# Edwardian block on a corner lot. The ground storey in rusticated
# Portland-type stone on a granite plinth: the public entrance on the axis
# up three steps, in a stone doorcase with Tuscan pilasters and a segmental
# pediment, and over it on a wrought-iron bracket the blue lamp lettered
# POLICE (lit at night); sashes either side behind iron bars. A stone band
# lettered POLICE STATION. The upper storey in red brick with stone quoins:
# five sashes under keyed stone lintels, the middle one opening on a small
# balcony. A modillioned stone cornice, a brick parapet with a shaped stone
# centrepiece carrying the borough's arms and the year, a hipped slate roof
# behind it with two chimneys, and the flagpole. Down the right side the
# charge-room door and the barred cell windows; the yard (cars) is the
# app's (models.ts).
#
# Pieces (base at the origin, stacked by the app):
#   ground  4.4 m: the stone storey, steps, doorcase and the lamp
#   floor   3.7 m: the brick storey
#   roof    cornice, parapet, the slate hip, chimneys, the flagpole
import math

from lib import Model, Z, fpoly, grille, letters, lintel, new_id, pane, sash, sides, sill

ID = "e2"
W, D = 12.0, 10.0
HW, HD = W / 2, D / 2
PLINTH = 0.45
G = 4.4
FL = 3.7
TOP = G + FL
DOOR = (-0.75, 0.75)
STEPS = 3
TREAD = 0.32
UP = [-4.4, -2.2, 0.0, 2.2, 4.4]  # the upper storey's windows (front)
GW = [-4.0, -2.3, 2.3, 4.0]  # ground storey windows (front)


def build(out, bake=True):
    M = Model(ID, seed=31)
    M.sharp = math.radians(40)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    upper(M)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    M.export(out, bake)


# ---- ground storey --------------------------------------------------------------------


def ground(M):
    m = M.m
    m.sweep("granite", W, D, [(0.08, 0.0), (0.08, PLINTH - 0.05), (0.04, PLINTH), (-0.01, PLINTH)])
    walls = sides(m, W, D)
    c, e = PLINTH + 0.75, G - 0.75
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        if name == "front":
            holes = [(u - 0.5, u + 0.5, c, e) for u in GW] + [(DOOR[0], DOOR[1], PLINTH, 2.95, 0.3)]
        elif name == "right":
            # The charge-room door, three barred cell windows set high.
            holes = [(-3.6, -2.6, PLINTH, 2.6, 0.3)] + [(u - 0.35, u + 0.35, 2.4, 3.2) for u in (-0.8, 1.2, 3.2)]
        elif name == "left":
            holes = [(u - 0.5, u + 0.5, c, e) for u in (-2.6, 0.0, 2.6)]
        else:
            holes = [(u - 0.5, u + 0.5, c, e) for u in (-3.8, -1.3, 3.8)] + [(0.6, 1.6, PLINTH, 2.6, 0.3)]
        F.wall("ashlar", -h, h, PLINTH, G, holes, depth=0.35)
        for hole in holes:
            a, b, c_, e_ = hole[:4]
            if len(hole) == 5:
                continue
            if name == "right":
                sash(F, a, b, c_, e_, D=0.35, lights=(3, 1), glass="frosted")
                grille(F, a, b, c_, e_)
            else:
                sash(F, a, b, c_, e_, D=0.35, lights=(2, 2))
                if name == "front":
                    grille(F, a, b, c_, e_)
            sill(F, a, b, c_, D=0.35)
            # A voussoired flat arch with a dropped key.
            F.box("stone", a - 0.12, b + 0.12, e_, e_ + 0.32, 0, 0.04)
            F.box("stone", (a + b) / 2 - 0.13, (a + b) / 2 + 0.13, e_ - 0.08, e_ + 0.42, 0, 0.08)
        # The band over the storey; POLICE STATION on the front.
        F.box("stone", -h - 0.04, h + 0.04, G - 0.55, G - 0.05, 0, 0.1)
        F.box("stone", -h - 0.07, h + 0.07, G - 0.05, G, 0, 0.16)
        if name == "front":
            doorcase(M, F)
        elif name == "right":
            side_door(F, -3.6, -2.6)
        elif name == "back":
            side_door(F, 0.6, 1.6)
    letters(m, "iron", walls["front"], -3.55, G - 0.3, 0.1, "POLICE", 0.24, depth=0.02, spacing=1.3)
    letters(m, "iron", walls["front"], 3.55, G - 0.3, 0.1, "STATION", 0.24, depth=0.02, spacing=1.3)
    m.poly("dark", [(-HW, -HD, G - 0.02), (HW, -HD, G - 0.02), (HW, HD, G - 0.02), (-HW, HD, G - 0.02)], out=-Z)


def side_door(F, a, b):
    """A ledged door in green under a plain stone head, a step."""
    F.quad("door2", a, b, PLINTH, 2.6, -0.24)
    for k in range(3):
        F.box("door2", a + 0.06, b - 0.06, PLINTH + 0.2 + k * 0.7, PLINTH + 0.75 + k * 0.7, -0.24, -0.22)
    F.box("brass", b - 0.2, b - 0.12, 1.4, 1.48, -0.22, -0.18)
    F.box("stone", a - 0.15, b + 0.15, 2.6, 2.85, 0, 0.06)
    F.box("granite", a - 0.1, b + 0.1, 0.0, PLINTH, 0, 0.35)


def doorcase(M, F):
    """The public entrance: panelled double doors under a fanlight, Tuscan pilasters,
    a segmental pediment; steps; the blue lamp on its bracket."""
    m = M.m
    a, b = DOOR
    de = 2.45
    for u0, u1 in ((a + 0.02, 0.0), (0.0, b - 0.02)):
        F.quad("door", u0, u1, PLINTH, de, -0.28)
        for k in range(2):
            F.box("door", u0 + 0.08, u1 - 0.08, PLINTH + 0.2 + k * 0.95, PLINTH + 0.95 + k * 0.95, -0.28, -0.25)
    F.box("brass", -0.12, -0.04, 1.35, 1.42, -0.25, -0.2)
    F.box("brass", 0.04, 0.12, 1.35, 1.42, -0.25, -0.2)
    F.box("frame", a, b, de, de + 0.08, -0.3, -0.2)
    wid = new_id()
    pane(F, "doorglass", a, b, de + 0.08, 2.95, a + 0.05, b - 0.05, de + 0.1, 2.9, -0.27, wid)
    for i in range(1, 4):
        u = a + i * (b - a) / 4
        F.box("frame", u - 0.015, u + 0.015, de + 0.08, 2.95, -0.27, -0.24)
    # Pilasters, an entablature, the segmental pediment.
    for u in (a - 0.45, b + 0.1):
        F.box("stone", u, u + 0.35, PLINTH, 3.15, 0, 0.18)
        F.box("stone", u - 0.04, u + 0.39, PLINTH, PLINTH + 0.3, 0, 0.22)
        F.box("stone", u - 0.04, u + 0.39, 3.0, 3.15, 0, 0.22)
    F.box("stone", a - 0.55, b + 0.55, 3.15, 3.5, 0, 0.22)
    F.box("stone", a - 0.65, b + 0.65, 3.5, 3.6, 0, 0.3)
    seg = 12
    R, rise = 1.6, 0.45
    hw = b + 0.65
    zc = 3.6 + rise - R
    arc = [(math.sin(t) * R, zc + math.cos(t) * R) for t in [-math.asin(hw / R) + 2 * math.asin(hw / R) * i / seg for i in range(seg + 1)]]
    fpoly(F, "stone", [(-hw, 3.6)] + arc + [(hw, 3.6)], 0.32)
    for (u0, z0), (u1, z1) in zip(arc, arc[1:]):
        um, zm = (u0 + u1) / 2, (z0 + z1) / 2
        m.poly("stone", [F.p(u0, z0, 0.0), F.p(u1, z1, 0.0), F.p(u1, z1, 0.32), F.p(u0, z0, 0.32)], out=F.t * um + Z * (zm - zc))
        # The raking cornice: a lip standing proud along the curve.
        m.poly("stone", [F.p(u0, z0 - 0.08, 0.36), F.p(u1, z1 - 0.08, 0.36), F.p(u1, z1, 0.36), F.p(u0, z0, 0.36)], out=F.n)
        m.poly("stone", [F.p(u0, z0, 0.32), F.p(u1, z1, 0.32), F.p(u1, z1, 0.36), F.p(u0, z0, 0.36)], out=F.t * um + Z * (zm - zc))
    # Steps.
    for i in range(STEPS):
        zz = PLINTH - i * PLINTH / STEPS
        F.box("granite", a - 0.9 - i * 0.15, b + 0.9 + i * 0.15, 0.0, zz, 0, 0.35 + i * TREAD, skip=("back", "bottom"))
    # The blue lamp: a wrought-iron bracket from the pediment, a square lantern.
    lz = 4.05
    F.box("iron", -0.04, 0.04, 3.95, lz + 0.05, 0.3, 0.38)
    m.strut("iron", F.p(0, 3.98, 0.33), F.p(0, lz + 0.08, 0.95), 0.04)
    m.strut("iron", F.p(0, lz + 0.08, 0.36), F.p(0, lz + 0.08, 0.95), 0.04)
    m.tube("iron", [F.p(0, lz - 0.05, 0.55 + 0.12 * math.cos(t)) + Z * (0.12 * math.sin(t)) for t in [i / 8 * math.tau for i in range(8)]], 0.012, F.t)
    lc = F.p(0, lz - 0.38, 0.95)
    s, hgt = 0.2, 0.42
    m.box("iron", (lc.x - s - 0.03, lc.y - s - 0.03, lc.z + hgt), (lc.x + s + 0.03, lc.y + s + 0.03, lc.z + hgt + 0.05))
    m.cyl("iron", lc.x, lc.y, s + 0.02, lc.z + hgt + 0.05, lc.z + hgt + 0.2, seg=4, r1=0.04)
    m.box("iron", (lc.x - s - 0.02, lc.y - s - 0.02, lc.z - 0.06), (lc.x + s + 0.02, lc.y + s + 0.02, lc.z))
    m.box("bluelamp", (lc.x - s, lc.y - s, lc.z), (lc.x + s, lc.y + s, lc.z + hgt))
    L = sides(m, 2 * s, 2 * s, lc.x, lc.y, lc.z)
    for Fl in L.values():
        letters(m, "paint", Fl, 0, 0.21, 0.004, "POLICE", 0.065, depth=0.004)
        for u in (-s, s):
            Fl.box("iron", u - 0.015, u + 0.015, 0, hgt, 0, 0.012)


# ---- upper storey ---------------------------------------------------------------------


def quoins(F, h, z0, z1):
    i = 0
    z = z0
    while z < z1 - 0.1:
        z2 = min(z1, z + 0.35)
        long = i % 2 == 0
        for u, s in ((-h, 1), (h, -1)):
            lw = 0.55 if long else 0.32
            u0, u1 = sorted((u, u + s * lw))
            F.box("stone", u0, u1, z + 0.01, z2 - 0.01, 0, 0.03)
        z, i = z2, i + 1


def upper(M):
    m = M.m
    z = G
    walls = sides(m, W, D)
    c, e = z + 0.7, z + FL - 0.55
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        us = UP if name == "front" else ([-3.0, -1.0, 1.0, 3.0] if name in ("left", "right") else [-4.0, -1.6, 1.6, 4.0])
        holes = [(u - 0.5, u + 0.5, c if u else z + 0.05, e) for u in us] if name == "front" else [(u - 0.48, u + 0.48, c, e) for u in us]
        F.wall("brick", -h, h, z, z + FL, holes, depth=0.3, reveal="stone")
        for a, b, c_, e_ in holes:
            if name == "front" and a < 0 < b:
                balcony_door(M, F, a, b, c_, e_)
            else:
                sash(F, a, b, c_, e_, D=0.3, lights=(2, 2))
                sill(F, a, b, c_, D=0.3)
            lintel(F, a, b, e_)
        quoins(F, h, z, z + FL)
    m.poly("dark", [(-HW, -HD, TOP - 0.02), (HW, -HD, TOP - 0.02), (HW, HD, TOP - 0.02), (-HW, HD, TOP - 0.02)], out=-Z)


def balcony_door(M, F, a, b, c, e):
    """The middle window, a French window onto a stone balcony on consoles with a balustrade."""
    m = M.m
    wid = new_id()
    F.box("frame", a, a + 0.08, c, e, -0.3, -0.19)
    F.box("frame", b - 0.08, b, c, e, -0.3, -0.19)
    F.box("frame", a, b, e - 0.08, e, -0.3, -0.19)
    F.box("frame", -0.03, 0.03, c, e - 0.6, -0.28, -0.2)
    F.box("frame", a, b, e - 0.66, e - 0.6, -0.3, -0.19)
    pane(F, "glass", a, b, c, e, a + 0.08, b - 0.08, c + 0.05, e - 0.08, -0.25, wid)
    for k in range(1, 4):
        F.box("frame", a + 0.08, b - 0.08, c + k * (e - 0.66 - c) / 4 - 0.015, c + k * (e - 0.66 - c) / 4 + 0.015, -0.25, -0.22)
    # The balcony slab and its consoles.
    F.box("stone", a - 0.5, b + 0.5, c - 0.18, c, 0, 0.75)
    for u in (a - 0.3, b + 0.1):
        F.box("stone", u, u + 0.2, c - 0.6, c - 0.18, 0, 0.6)
    for u in [a - 0.42 + i * (b - a + 0.84) / 7 for i in range(8)]:
        m.cyl("stone", F.p(u, 0, 0).x, F.p(0, 0, 0.62).y, 0.05, c, c + 0.72, seg=6)
    F.box("stone", a - 0.5, b + 0.5, c + 0.72, c + 0.82, 0.52, 0.72)
    for u0, u1 in ((a - 0.5, a - 0.38), (b + 0.38, b + 0.5)):
        F.box("stone", u0, u1, c, c + 0.82, 0, 0.72)


# ---- roof -----------------------------------------------------------------------------


def roof(M):
    m = M.m
    walls = sides(m, W, D)
    # Frieze, modillions and the cornice.
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.box("stone", -h - 0.02, h + 0.02, TOP, TOP + 0.3, 0, 0.05)
        F.box("stone", -h - 0.05, h + 0.05, TOP + 0.3, TOP + 0.42, 0, 0.18)
        for i in range(int(2 * h / 0.5)):
            u = -h + 0.25 + i * 0.5
            F.box("stone", u - 0.06, u + 0.06, TOP + 0.3, TOP + 0.42, 0.18, 0.36)
        F.box("stone", -h - 0.08, h + 0.08, TOP + 0.42, TOP + 0.58, 0, 0.42)
    zp = TOP + 0.58
    ph = 0.75  # the parapet
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.box("brick", -h, h, zp, zp + ph, -0.25, 0.0, skip=())
        F.box("stone", -h - 0.05, h + 0.05, zp + ph, zp + ph + 0.12, -0.3, 0.05)
    # The shaped centrepiece over the middle bays: scrolled shoulders, a pediment, the arms and the year.
    F = walls["front"]
    F.box("stone", -1.6, 1.6, zp + ph, zp + ph + 0.9, -0.3, 0.06, skip=())
    for s in (-1, 1):
        for i in range(4):
            u0 = s * (1.6 + i * 0.18)
            u1 = s * (1.6 + (i + 1) * 0.18)
            top = zp + ph + 0.9 * (1 - (i + 1) / 4) ** 1.5
            F.box("stone", min(u0, u1), max(u0, u1), zp + ph, max(top, zp + ph + 0.12), -0.3, 0.04)
    pz = zp + ph + 0.9
    fpoly(F, "stone", [(-1.75, pz), (1.75, pz), (0, pz + 0.75)], 0.09)
    fpoly(F, "stone", [(-1.75, pz), (1.75, pz), (0, pz + 0.75)], -0.3, out=-F.n)
    for s in (-1, 1):
        A, B = F.p(s * 1.85, pz - 0.02, 0.12), F.p(0, pz + 0.82, 0.12)
        m.poly("stone", [A, B, F.p(0, pz + 0.82, -0.32), F.p(s * 1.85, pz - 0.02, -0.32)], out=(s * 0.5, 0, 1))
        m.poly("stone", [F.p(s * 1.85, pz - 0.14, 0.12), F.p(0, pz + 0.7, 0.12), B, A], out=F.n)
    F.box("stone", -1.85, 1.85, pz - 0.14, pz, -0.32, 0.12)
    letters(m, "iron", F, 0, zp + ph + 0.25, 0.06, "1910", 0.26, depth=0.02)
    fpoly(F, "bronze", [(-0.2, pz + 0.55), (0.2, pz + 0.55), (0.2, pz + 0.32), (0.0, pz + 0.12), (-0.2, pz + 0.32)], 0.1)
    # Behind the parapet: a gutter, then the slate hip.
    zr = zp + 0.2
    m.poly("roof", [(-HW + 0.25, -HD + 0.25, zr), (HW - 0.25, -HD + 0.25, zr), (HW - 0.25, HD - 0.25, zr), (-HW + 0.25, HD - 0.25, zr)], out=Z)
    x0, x1, y0, y1 = -HW + 0.6, HW - 0.6, -HD + 0.6, HD - 0.6
    rise = 2.6
    run = (y1 - y0) / 2
    rz = zr + rise
    rx0, rx1 = x0 + run, x1 - run
    m.poly("slate", [(x0, y0, zr), (x1, y0, zr), (rx1, 0, rz), (rx0, 0, rz)], out=(0, -1, 1))
    m.poly("slate", [(x1, y1, zr), (x0, y1, zr), (rx0, 0, rz), (rx1, 0, rz)], out=(0, 1, 1))
    m.poly("slate", [(x0, y1, zr), (x0, y0, zr), (rx0, 0, rz)], out=(-1, 0, 1))
    m.poly("slate", [(x1, y0, zr), (x1, y1, zr), (rx1, 0, rz)], out=(1, 0, 1))
    m.strut("ridge", (rx0, 0, rz + 0.04), (rx1, 0, rz + 0.04), 0.14)
    for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        m.strut("ridge", (cx, cy, zr + 0.04), (rx0 if cx < 0 else rx1, 0, rz + 0.04), 0.1)
    # Chimneys through the back slope, banded stacks with pots.
    for cx in (-3.2, 3.2):
        cy = 2.2
        t = rz + 1.3
        m.box("brick", (cx - 0.45, cy - 0.35, zr + 0.5), (cx + 0.45, cy + 0.35, t))
        m.box("stone", (cx - 0.52, cy - 0.42, t - 0.5), (cx + 0.52, cy + 0.42, t - 0.4))
        m.box("stone", (cx - 0.55, cy - 0.45, t), (cx + 0.55, cy + 0.45, t + 0.12))
        for dx in (-0.2, 0.2):
            m.cyl("terracotta", cx + dx, cy, 0.1, t + 0.12, t + 0.5, seg=10, r1=0.08)
    # The flagpole on the parapet behind the centrepiece, with a gilt ball.
    fy = -HD + 0.35
    m.box("stone", (-0.25, fy - 0.2, zr), (0.25, fy + 0.2, zp + ph + 0.12))
    m.cyl("paint", 0, fy, 0.06, zp + ph + 0.12, zp + ph + 6.5, seg=10, r1=0.035)
    m.cyl("brass", 0, fy, 0.09, zp + ph + 6.5, zp + ph + 6.68, seg=10, r1=0.03)
    # The flag, hanging still in the lee.
    m.poly("flag", [(0.05, fy, zp + ph + 6.3), (1.5, fy, zp + ph + 6.1), (1.45, fy, zp + ph + 5.3), (0.05, fy, zp + ph + 5.4)], out=(0, -1, 0))
    m.poly("flag", [(0.05, fy + 0.002, zp + ph + 6.3), (1.5, fy + 0.002, zp + ph + 6.1), (1.45, fy + 0.002, zp + ph + 5.3), (0.05, fy + 0.002, zp + ph + 5.4)], out=(0, 1, 0))
