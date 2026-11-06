# E1, school: the town's schoolhouse of the 1920s. Two tall storeys of red
# brick on a raised stone basement, symmetrical about an entrance pavilion:
# steps up to double doors under a round-arched fanlight in a stone
# surround, SCHOOL lettered over it and the year in the pediment that rises
# in front of the roof. Each classroom is lit by a bank of four tall
# sashes between brick mullions, stone sills and a continuous lintel band.
# A hipped slate roof with a white bell cupola on the ridge (louvred sides,
# a little copper roof and a weathervane), a chimney at each end.
#
# Pieces (base at the origin, stacked by the app):
#   ground  4.6 m: the basement and the ground floor, the doors and steps
#   floor   3.9 m: the upper classrooms
#   roof    eaves, the hipped roof, the pediment, the cupola, chimneys
import math

from lib import Model, Z, fpoly, letters, new_id, pane, sash, sides, sill

ID = "e1"
W, D = 14.0, 10.0
HW, HD = W / 2, D / 2
BASE = 0.75  # the raised basement, stone
G = 4.6
FL = 3.9
TOP = G + FL
PAV = (-1.9, 1.9)  # the entrance pavilion, x
PROUD = 0.5  # how far it stands out
RIDGE = 3.6  # roof rise


def bank(cx, n=4, w=0.85, gap=0.28):
    """Openings of a bank of n windows centred at cx."""
    total = n * w + (n - 1) * gap
    a0 = cx - total / 2
    return [(a0 + i * (w + gap), a0 + i * (w + gap) + w) for i in range(n)]


BANKS = [-4.55, 4.55]


def build(out, bake=True):
    M = Model(ID, seed=19)
    M.sharp = math.radians(40)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    storey(M, G)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    M.export(out, bake)


def classroom_windows(F, z, c, e, banks, lights=(2, 3)):
    """Banks of tall sashes on facade F, sills at c, heads at e."""
    holes = []
    for cx in banks:
        holes += [(a, b, c, e) for a, b in bank(cx)]
    return holes


def finish_windows(F, holes, D_, lights=(2, 3)):
    for a, b, c, e in holes:
        sash(F, a, b, c, e, D=D_, lights=lights)
    # One sill and one lintel band per bank (holes come in fours).
    for i in range(0, len(holes), 4):
        grp = holes[i:i + 4]
        a, b, c, e = grp[0][0], grp[-1][1], grp[0][2], grp[0][3]
        sill(F, a, b, c, D=D_)
        F.box("stone", a - 0.25, b + 0.25, e, e + 0.32, 0, 0.04)


# ---- ground storey --------------------------------------------------------------------


def ground(M):
    m = M.m
    walls = sides(m, W, D)
    # The basement: stone, with low windows, a water table on top.
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        vents = [(u - 0.4, u + 0.4, 0.2, 0.6) for u in ((-4.55, 4.55) if name in ("front", "back") else (-2.5, 2.5))]
        F.wall("ashlar", -h, h, 0.0, BASE, vents, depth=0.2)
        for a, b, c, e in vents:
            F.quad("dark", a, b, c, e, -0.15)
            F.box("iron", a, b, (c + e) / 2 - 0.02, (c + e) / 2 + 0.02, -0.12, -0.08)
        F.box("stone", -h - 0.06, h + 0.06, BASE - 0.08, BASE + 0.04, 0, 0.1)
    c, e = BASE + 1.0, G - 0.45
    F = walls["front"]
    holes = classroom_windows(F, 0, c, e, BANKS)
    F.wall("brick", -HW, HW, BASE, G, holes, depth=0.3)
    finish_windows(F, holes, 0.3)
    pavilion(M, F, BASE, G, ground_floor=True)
    for name in ("right", "left"):
        S = walls[name]
        hs = [(u - 0.45, u + 0.45, c, e) for u in (-2.6, 0.0, 2.6)]
        S.wall("brick", -HD, HD, BASE, G, hs, depth=0.3)
        for a, b, c_, e_ in hs:
            sash(S, a, b, c_, e_, D=0.3, lights=(2, 3))
            sill(S, a, b, c_, D=0.3)
            S.box("stone", a - 0.12, b + 0.12, e_, e_ + 0.32, 0, 0.04)
    B = walls["back"]
    door = (-0.7, 0.7)
    holes = classroom_windows(B, 0, c, e, BANKS)
    B.wall("brick", -HW, HW, BASE, G, holes + [(*door, BASE, 3.1, 0.3)], depth=0.3)
    finish_windows(B, holes, 0.3)
    B.quad("door", *door, BASE, 3.1, -0.25)
    B.box("stone", door[0] - 0.15, door[1] + 0.15, 3.1, 3.4, 0, 0.05)
    B.box("concrete", door[0] - 0.6, door[1] + 0.6, 0.0, BASE, 0, 1.4, skip=("back",))
    for i in range(3):
        B.box("concrete", door[0] - 0.6, door[1] + 0.6, 0.0, BASE - (i + 1) * 0.19, 1.4, 1.4 + (i + 1) * 0.3, skip=("back",))
    # Belt course between the storeys.
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.box("stone", -h - 0.04, h + 0.04, G - 0.18, G, 0, 0.07)
    m.poly("dark", [(-HW, -HD, G - 0.02), (HW, -HD, G - 0.02), (HW, HD, G - 0.02), (-HW, HD, G - 0.02)], out=-Z)


def pavilion(M, F, z0, z1, ground_floor):
    """The entrance pavilion in front of the main wall, z0 to z1."""
    m = M.m
    a, b = PAV
    y = -HD - PROUD
    P = sides(m, b - a, PROUD, (a + b) / 2, -HD - PROUD / 2)
    front, right, left = P["front"], P["right"], P["left"]
    if ground_floor:
        # Basement under it, the steps, the door.
        front.wall("ashlar", a - (a + b) / 2, b - (a + b) / 2, 0.0, z0, [], depth=0.2)
        for S in (right, left):
            S.wall("ashlar", -PROUD / 2, PROUD / 2, 0.0, z0, [])
        da, db = -0.85, 0.85
        spring = z0 + 2.55
        hole = [(da, db, z0, spring + 0.85, 0.45)]
        front.wall("brick", a - (a + b) / 2, b - (a + b) / 2, z0, z1, hole, depth=0.45, reveal="stone")
        doors(m, front, da, db, z0, spring)
        # Stone surround: pilasters, an archivolt, a keystone; SCHOOL on the frieze.
        for u in (da - 0.32, db):
            front.box("stone", u, u + 0.32, z0, spring, 0, 0.08)
        arc = [(-math.cos(t) * 1.17, spring + math.sin(t) * 1.17) for t in [i / 12 * math.pi for i in range(13)]]
        inner = [(-math.cos(t) * 0.85, spring + math.sin(t) * 0.85) for t in [i / 12 * math.pi for i in range(13)]]
        for (u0, v0), (u1, v1), (i0, j0), (i1, j1) in zip(arc, arc[1:], inner, inner[1:]):
            fpoly(front, "stone", [(i0, j0), (i1, j1), (u1, v1), (u0, v0)], 0.08)
            m.poly("stone", [front.p(u0, v0, 0), front.p(u1, v1, 0), front.p(u1, v1, 0.08), front.p(u0, v0, 0.08)], out=front.p(u0 + u1, v0 + v1 - 2 * spring, 0) - front.p(0, 0, 0))
        front.box("stone", -0.14, 0.14, spring + 0.7, spring + 1.25, 0, 0.12)
        front.box("stone", -1.75, 1.75, z1 - 0.95, z1 - 0.3, 0, 0.06)
        letters(m, "stone", front, 0, z1 - 0.62, 0.06, "SCHOOL", 0.38, depth=0.035, spacing=1.25)
        # Steps out to the path, with iron rails.
        for i in range(4):
            dz = z0 - i * z0 / 4
            m.box("stone", (a + 0.2, y - (i + 1) * 0.32, 0.0), (b - 0.2, y, dz), skip=("z0",))
        for u in (a + 0.35, b - 0.35):
            m.strut("iron", (u, y - 1.2, 0.9), (u, y - 0.1, BASE + 0.9), 0.04)
            for k in (0.0, 1.0):
                m.strut("iron", (u, y - 0.1 - 1.1 * k, BASE + 0.0 * k + (1 - k) * 0.0 + 0.0), (u, y - 0.1 - 1.1 * k, (BASE + 0.9) * (1 - k) + 0.9 * k), 0.035)
        lamp = [(da - 0.75, spring - 0.3), (db + 0.75, spring - 0.3)]
        for u, z in lamp:
            front.box("iron", u - 0.06, u + 0.06, z - 0.05, z + 0.4, 0, 0.12)
            front.box("lamp", u - 0.1, u + 0.1, z, z + 0.35, 0.12, 0.3, skip=())
    else:
        hole = [(-1.3, 1.3, z0 + 0.75, z1 - 0.6)]
        front.wall("brick", a - (a + b) / 2, b - (a + b) / 2, z0, z1, hole, depth=0.3)
        for k, (u0, u1) in enumerate(((-1.3, -0.47), (-0.42, 0.42), (0.47, 1.3))):
            sash(front, u0, u1, z0 + 0.75, z1 - 0.6, D=0.3, lights=(2, 3))
        front.box("brick", -0.47, -0.42, z0 + 0.75, z1 - 0.6, -0.3, 0.0)
        front.box("brick", 0.42, 0.47, z0 + 0.75, z1 - 0.6, -0.3, 0.0)
        sill(front, -1.3, 1.3, z0 + 0.75, D=0.3)
        front.box("stone", -1.55, 1.55, z1 - 0.6, z1 - 0.28, 0, 0.04)
    for S in (right, left):
        S.wall("brick", -PROUD / 2, PROUD / 2, z0, z1, [])
    # Stone quoins on the pavilion's corners.
    for u0, u1 in ((a - (a + b) / 2, a - (a + b) / 2 + 0.4), (b - (a + b) / 2 - 0.4, b - (a + b) / 2)):
        for i in range(int((z1 - z0) / 0.5)):
            zz = z0 + i * 0.5
            k = 0.12 if i % 2 == 0 else 0.0
            front.box("stone", u0 - (k if u0 < 0 else 0), u1 + (k if u1 > 0 else 0), zz, zz + 0.42, 0, 0.04)


def doors(m, F, a, b, c, spring):
    """Double doors of six panels under a fanlight of radiating bars, set back 0.4 m."""
    D_ = 0.4
    F.quad("door", a, b, c, spring - 0.1, -D_)
    mid = (a + b) / 2
    for u0, u1 in ((a + 0.08, mid - 0.04), (mid + 0.04, b - 0.08)):
        for z0, z1 in ((c + 0.15, c + 0.95), (c + 1.05, c + 1.75), (c + 1.85, spring - 0.25)):
            F.box("door", u0 + 0.06, u1 - 0.06, z0, z1, -D_, -D_ + 0.03)
    F.box("door", mid - 0.03, mid + 0.03, c, spring - 0.1, -D_, -D_ + 0.04)
    F.box("brass", mid - 0.12, mid - 0.06, c + 1.0, c + 1.15, -D_, -D_ + 0.07)
    F.box("brass", mid + 0.06, mid + 0.12, c + 1.0, c + 1.15, -D_, -D_ + 0.07)
    F.box("frame", a, b, spring - 0.1, spring, -D_, -D_ + 0.06)
    wid = new_id()
    r = (b - a) / 2
    pts = [(mid - math.cos(t) * r, spring + math.sin(t) * r) for t in [i / 12 * math.pi for i in range(13)]]
    for (u0, v0), (u1, v1) in zip(pts, pts[1:]):
        uv = lambda u, v: (wid + (u - a) / (b - a), (v - spring) / r)  # noqa: E731
        F.m.poly("glass", [F.p(mid, spring, -D_ + 0.02), F.p(u0, v0, -D_ + 0.02), F.p(u1, v1, -D_ + 0.02)], out=F.n, uvs=[uv(mid, spring), uv(u0, v0), uv(u1, v1)])
    for k in range(1, 6):
        t = k / 6 * math.pi
        F.m.strut("frame", F.p(mid, spring, -D_ + 0.04), F.p(mid - math.cos(t) * r, spring + math.sin(t) * r, -D_ + 0.04), 0.03)


# ---- upper storey ---------------------------------------------------------------------


def storey(M, z):
    m = M.m
    walls = sides(m, W, D)
    c, e = z + 0.85, z + FL - 0.5
    F = walls["front"]
    holes = classroom_windows(F, z, c, e, BANKS)
    F.wall("brick", -HW, HW, z, z + FL, holes, depth=0.3)
    finish_windows(F, holes, 0.3)
    pavilion(M, F, z, z + FL, ground_floor=False)
    for name in ("right", "left"):
        S = walls[name]
        hs = [(u - 0.45, u + 0.45, c, e) for u in (-2.6, 0.0, 2.6)]
        S.wall("brick", -HD, HD, z, z + FL, hs, depth=0.3)
        for a, b, c_, e_ in hs:
            sash(S, a, b, c_, e_, D=0.3, lights=(2, 3))
            sill(S, a, b, c_, D=0.3)
            S.box("stone", a - 0.12, b + 0.12, e_, e_ + 0.32, 0, 0.04)
    B = walls["back"]
    holes = classroom_windows(B, z, c, e, BANKS)
    B.wall("brick", -HW, HW, z, z + FL, holes, depth=0.3)
    finish_windows(B, holes, 0.3)
    m.poly("dark", [(-HW, -HD, z + FL - 0.02), (HW, -HD, z + FL - 0.02), (HW, HD, z + FL - 0.02), (-HW, HD, z + FL - 0.02)], out=-Z)


# ---- roof -----------------------------------------------------------------------------


def roof(M):
    m = M.m
    walls = sides(m, W, D)
    # A plain stone cornice and a boxed eaves soffit.
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.box("stone", -h - 0.05, h + 0.05, TOP, TOP + 0.28, 0, 0.12)
    o = 0.55  # eaves overhang
    z = TOP + 0.28
    x0, x1, y0, y1 = -HW - o, HW + o, -HD - o, HD + o
    m.box("trim", (x0, y0, z - 0.12), (x1, y1, z), skip=("z1",))
    # The hip: the ridge along x, rising RIDGE over a run of (D/2 + o).
    run = HD + o
    rz = z + RIDGE
    rx0, rx1 = x0 + run, x1 - run
    m.poly("slate", [(x0, y0, z), (x1, y0, z), (rx1, 0, rz), (rx0, 0, rz)], out=(0, -1, 1))
    m.poly("slate", [(x1, y1, z), (x0, y1, z), (rx0, 0, rz), (rx1, 0, rz)], out=(0, 1, 1))
    m.poly("slate", [(x0, y1, z), (x0, y0, z), (rx0, 0, rz)], out=(-1, 0, 1))
    m.poly("slate", [(x1, y0, z), (x1, y1, z), (rx1, 0, rz)], out=(1, 0, 1))
    # Ridge and hip rolls, gutters.
    m.strut("ridge", (rx0, 0, rz + 0.04), (rx1, 0, rz + 0.04), 0.14)
    for (cx, cy) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        m.strut("ridge", (cx, cy, z + 0.04), (rx0 if cx < 0 else rx1, 0, rz + 0.04), 0.1)
    for lo, hi in (((x0, y0 - 0.1, z - 0.18), (x1, y0, z - 0.02)), ((x0, y1, z - 0.18), (x1, y1 + 0.1, z - 0.02)),
                   ((x0 - 0.1, y0, z - 0.18), (x0, y1, z - 0.02)), ((x1, y0, z - 0.18), (x1 + 0.1, y1, z - 0.02))):
        m.box("gutter", lo, hi)
    # The pediment over the pavilion, standing in front of the slope.
    a, b = PAV
    py = -HD - PROUD
    pz = TOP + 0.28
    peak = pz + 1.6
    PD = 3.0  # deep enough that the roof slope swallows its back
    P = sides(m, b - a + 0.3, PD, 0, py + PD / 2)
    F = P["front"]
    hw = (b - a + 0.3) / 2
    F.box("stone", -hw, hw, TOP, pz, 0, 0.12)
    fpoly(F, "brick", [(-hw, pz), (hw, pz), (0, peak)], 0.0)
    fpoly(P["back"], "brick", [(-hw, pz), (hw, pz), (0, peak)], 0.0)
    # Raked coping, the year in a roundel.
    for s in (-1, 1):
        a3 = (s * (hw + 0.12), pz - 0.05)
        b3 = (0, peak + 0.14)
        # Stone coping at the front, slate behind it back into the main roof (a cross gable).
        for role, w0, w1 in (("stone", -0.3, 0.12), ("slate", -PD, -0.3)):
            pts = [F.p(a3[0], a3[1], w0), F.p(b3[0], b3[1], w0), F.p(b3[0], b3[1], w1), F.p(a3[0], a3[1], w1)]
            m.poly(role, pts, out=(s * 0.6, 0, 1))
            pts2 = [F.p(a3[0], a3[1] - 0.2, w1), F.p(b3[0], b3[1] - 0.2, w1), F.p(b3[0], b3[1], w1), F.p(a3[0], a3[1], w1)]
            m.poly("stone", pts2, out=(0, -1, 0))
        # The slope under the coping, back into the roof.
        m.poly("brick", [F.p(s * hw, pz, 0), F.p(0, peak, 0), F.p(0, peak, -PD), F.p(s * hw, pz, -PD)], out=(s, 0, 1))
    seg = 16
    rc = pz + 0.7
    fpoly(F, "stone", [(math.cos(i / seg * math.tau) * 0.42, rc + math.sin(i / seg * math.tau) * 0.42) for i in range(seg)], 0.03)
    letters(m, "brass", F, 0, rc, 0.03, "1924", 0.2, depth=0.015)
    # Chimneys at either end of the ridge.
    for cx in (rx0 - 0.4, rx1 + 0.4):
        t = rz + 1.2
        m.box("brick", (cx - 0.4, -0.55, z + 0.5), (cx + 0.4, 0.55, t))
        m.box("stone", (cx - 0.48, -0.63, t), (cx + 0.48, 0.63, t + 0.12))
        for dy in (-0.25, 0.25):
            m.cyl("terracotta", cx, dy, 0.1, t + 0.12, t + 0.45, seg=10, r1=0.08)
    cupola(m, rz)


def cupola(m, rz):
    """A square white bell cupola straddling the ridge: a boarded base, louvred
    stage with corner posts, a cornice and a copper ogee roof with a weathervane."""
    s = 0.85
    z0 = rz - 0.9
    m.box("trim", (-s, -s, z0), (s, s, rz + 0.35))
    for name, F in sides(m, 2 * s - 0.1, 2 * s - 0.1, 0, 0, rz + 0.35).items():
        F.quad("cupola", -s + 0.15, s - 0.15, 0.1, 1.15, -0.06)
        for u in (-s + 0.05, s - 0.15):
            F.box("trim", u, u + 0.1, 0.0, 1.3, -0.05, 0.05)
        F.box("trim", -s + 0.05, s - 0.05, 1.15, 1.3, -0.05, 0.03)
        F.box("trim", -s + 0.05, s - 0.05, 0.0, 0.1, -0.05, 0.03)
    z1 = rz + 0.35 + 1.3
    m.box("trim", (-s - 0.12, -s - 0.12, z1), (s + 0.12, s + 0.12, z1 + 0.15))
    zb = z1 + 0.15
    prof = [(s + 0.05, 0.0), (s - 0.05, 0.18), (0.62, 0.42), (0.38, 0.62), (0.2, 0.9), (0.06, 1.15)]
    for (r0, h0), (r1, h1) in zip(prof, prof[1:]):
        for i in range(4):
            c0 = [(-1, -1), (1, -1), (1, 1), (-1, 1)][i]
            c1 = [(-1, -1), (1, -1), (1, 1), (-1, 1)][(i + 1) % 4]
            mid = ((c0[0] + c1[0]) / 2, (c0[1] + c1[1]) / 2)
            m.poly("copper", [(c0[0] * r0, c0[1] * r0, zb + h0), (c1[0] * r0, c1[1] * r0, zb + h0), (c1[0] * r1, c1[1] * r1, zb + h1), (c0[0] * r1, c0[1] * r1, zb + h1)], out=(mid[0], mid[1], 0.6))
    top = zb + 1.15
    m.cyl("copper", 0, 0, 0.06, top, top + 0.12, seg=8)
    m.cyl("iron", 0, 0, 0.02, top + 0.12, top + 1.1, seg=6)
    m.box("iron", (-0.02, -0.4, top + 0.85), (0.02, 0.4, top + 0.88))
    m.poly("iron", [(0, 0.15, top + 0.95), (0, 0.6, top + 0.95), (0, 0.6, top + 1.15)], out=(1, 0, 0))
    m.poly("iron", [(0, -0.55, top + 0.92), (0, -0.25, top + 0.92), (0, -0.4, top + 1.02)], out=(1, 0, 0))
    m.poly("iron", [(0, 0.15, top + 0.95), (0, 0.6, top + 0.95), (0, 0.6, top + 1.15)], out=(-1, 0, 0))
    m.poly("iron", [(0, -0.55, top + 0.92), (0, -0.25, top + 0.92), (0, -0.4, top + 1.02)], out=(-1, 0, 0))
    for d in ((1, 0), (0, 1)):
        m.box("iron", (-0.35 * d[0] - 0.01, -0.35 * d[1] - 0.01, top + 0.6), (0.35 * d[0] + 0.01, 0.35 * d[1] + 0.01, top + 0.62))
