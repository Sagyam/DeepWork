# L7, the monument: the founders' column at the west gateway on Main
# Street. A fluted Doric column of pale limestone on a pedestal of ashlar
# over three granite steps, a bronze lamp at each corner of the top step.
# The pedestal's die carries FOUNDERS and the year in bronze letters on the
# front, a bronze laurel wreath on each side and a tablet at the back. Over
# the capital, a viewing gallery inside an iron railing; on it a drum, and
# a gilt urn holding a gilt flame, floodlit at night.
#
# Pieces (base at the origin, stacked by the app):
#   base   the steps, the pedestal and the column's base, to 6.1 m
#   lower  the shaft to 15.05 m
#   upper  the shaft to 24 m
#   top    the capital, the gallery, the drum, the urn and the flame
import math

from mathutils import Vector

from civic import lathe
from lib import Model, Z, letters, sides

ID = "l7"
STEP_H, TREAD, STEPS = 0.18, 0.45, 3
HALF = 4.4  # the bottom step
PLAT = STEP_H * STEPS  # the top step
PH = 2.2  # the die's half width
DIE0, DIE1 = 1.0, 4.6
CORN = 5.2  # top of the pedestal's cornice
SHAFT0, MID, SHAFT1 = 6.1, 15.05, 24.0
R0 = 1.15  # the shaft at its foot
FLUTES = 20


def build(out, bake=True):
    M = Model(ID, seed=41)
    M.sharp = math.radians(40)
    M.piece("base")
    base(M.m)
    M.piece("lower", (0, 0, SHAFT0))
    shaft(M.m, SHAFT0, MID)
    M.piece("upper", (0, 0, MID))
    shaft(M.m, MID, SHAFT1)
    M.piece("top", (0, 0, SHAFT1))
    top(M.m)
    M.export(out, bake)


# ---- the steps and the pedestal ---------------------------------------------------------


def base(m):
    for k in range(STEPS):
        h = HALF - k * TREAD
        m.box("granite", (-h, -h, 0.0), (h, h, (k + 1) * STEP_H), skip=("z0",))
    # The plinth course: granite, a moulded top.
    sq = [(-PH, -PH), (PH, -PH), (PH, PH), (-PH, PH)]
    m.psweep("granite", sq, [(0.35, PLAT), (0.35, 0.78), (0.24, 0.84), (0.24, 0.88), (0.08, 0.96), (0.04, DIE0), (0.0, DIE0)])
    # The die, ashlar, a raised panel on each face.
    for name, F in sides(m, 2 * PH, 2 * PH).items():
        F.wall("ashlar", -PH, PH, DIE0, DIE1, [])
        F.box("stone", -PH + 0.25, PH - 0.25, DIE0 + 0.3, DIE1 - 0.3, 0, 0.04)
        F.box("stone", -PH + 0.35, PH - 0.35, DIE0 + 0.4, DIE1 - 0.4, 0.04, 0.06, skip=("back", "top", "bottom", "left", "right"))
        if name == "front":
            letters(m, "statuary", F, 0, 3.35, 0.06, "FOUNDERS", 0.5, depth=0.035, spacing=1.25)
            letters(m, "statuary", F, 0, 2.55, 0.06, "MDCCCLXXII", 0.3, depth=0.03, spacing=1.2)
            wreath(m, F, 0, 1.75, 0.38, 0.06)
        elif name == "back":
            tablet(m, F)
        else:
            wreath(m, F, 0, 2.9, 0.62, 0.06)
    # The cornice, a blocking course and the column's plinth.
    m.psweep("stone", sq, [(0.0, DIE1), (0.06, DIE1 + 0.06), (0.1, DIE1 + 0.12), (0.1, DIE1 + 0.2), (0.3, DIE1 + 0.38), (0.36, DIE1 + 0.4), (0.36, DIE1 + 0.5), (0.2, DIE1 + 0.5), (0.2, CORN), (0.0, CORN)])
    m.poly("stone", [(-PH, -PH, CORN), (PH, -PH, CORN), (PH, PH, CORN), (-PH, PH, CORN)], out=Z)
    m.box("stone", (-1.55, -1.55, CORN), (1.55, 1.55, 5.6), skip=("z0",))
    lathe(m, "stone", [(1.45, 5.6), (1.5, 5.68), (1.46, 5.78), (1.32, 5.84), (1.27, 5.88), (1.32, 5.93), (1.24, 6.0), (R0 + 0.04, 6.06), (R0, SHAFT0)], seg=40, uv=False)
    # A bronze lamp on a granite block at each corner of the top step.
    c = HALF - (STEPS - 1) * TREAD - 0.5
    for sx in (-1, 1):
        for sy in (-1, 1):
            lamp(m, sx * c, sy * c, PLAT)


def lamp(m, x, y, z):
    m.box("granite", (x - 0.32, y - 0.32, z), (x + 0.32, y + 0.32, z + 0.7), skip=("z0",))
    m.box("granite", (x - 0.36, y - 0.36, z + 0.7), (x + 0.36, y + 0.36, z + 0.8))
    z += 0.8
    lathe(m, "statuary", [(0.2, z), (0.2, z + 0.12), (0.12, z + 0.25), (0.09, z + 0.6), (0.06, z + 0.7)], seg=10, c=(x, y), uv=False)
    m.cyl("statuary", x, y, 0.055, z + 0.7, z + 2.6, seg=8)
    m.cyl("statuary", x, y, 0.1, z + 2.6, z + 2.68, seg=10)
    m.cyl("lamp", x, y, 0.17, z + 2.68, z + 3.18, seg=12, r1=0.21)
    lathe(m, "statuary", [(0.25, z + 3.18), (0.25, z + 3.24), (0.12, z + 3.42), (0.03, z + 3.6)], seg=12, c=(x, y), uv=False)


def wreath(m, F, u, z, r, w):
    """A laurel wreath on facade F: a ring of leaves in two rows, tied with a ribbon below."""
    n = 28
    ring = [F.p(u + math.cos(i / n * math.tau) * r, z + math.sin(i / n * math.tau) * r, w + 0.04) for i in range(n)]
    m.tube("statuary", ring, 0.035 * r / 0.6 + 0.01, F.n, seg=5)
    for i in range(n):
        a = i / n * math.tau
        for side in (-1, 1):
            # Each leaf leans along the ring, out on one side, in on the other.
            a1 = a + 0.16
            rr = r + side * 0.07 * r / 0.6
            p0 = F.p(u + math.cos(a) * r, z + math.sin(a) * r, w + 0.05)
            p1 = F.p(u + math.cos(a1) * rr, z + math.sin(a1) * rr, w + 0.06)
            m.strut("statuary", p0, p1, 0.07 * r / 0.6, 0.025)
    # The ribbon: a knot at the bottom and two tails.
    m.box("statuary", *sorted_box(F, u - 0.06, u + 0.06, z - r - 0.06, z - r + 0.06, w, w + 0.09))
    for s in (-1, 1):
        m.strut("statuary", F.p(u, z - r, w + 0.06), F.p(u + s * 0.22 * r / 0.6, z - r - 0.42 * r / 0.6, w + 0.05), 0.07 * r / 0.6, 0.015)


def sorted_box(F, u0, u1, z0, z1, w0, w1):
    a, b = F.p(u0, z0, w0), F.p(u1, z1, w1)
    return tuple(min(a[i], b[i]) for i in range(3)), tuple(max(a[i], b[i]) for i in range(3))


def tablet(m, F):
    """The back: a bronze tablet in a moulded frame, its lines of names in low relief."""
    a, b, c, e = -1.25, 1.25, 1.75, 3.85
    F.box("statuary", a - 0.08, b + 0.08, c - 0.08, e + 0.08, 0.06, 0.1)
    F.box("statuary", a, b, c, e, 0.1, 0.11)
    letters(m, "statuary", F, 0, e - 0.28, 0.11, "IN HONOUR OF", 0.18, depth=0.015)
    for i in range(9):
        zz = e - 0.62 - i * 0.16
        for col, (u0, u1) in enumerate(((a + 0.2, -0.12), (0.12, b - 0.2))):
            cut = (i * 7 + col * 3) % 5 * 0.08
            F.box("statuary", u0, u1 - cut, zz - 0.035, zz + 0.035, 0.11, 0.118)


# ---- the shaft ----------------------------------------------------------------------------


def radius(z):
    """The shaft's radius at z: an entasis over its whole height, so the two pieces meet."""
    t = (z - SHAFT0) / (SHAFT1 - SHAFT0)
    return R0 * (1 - 0.15 * t**1.5)


def shaft(m, z0, z1, rings=5, sub=6):
    """Fluted, the flutes meeting in sharp arrises (Doric): each a shallow round groove."""
    depth = 0.075

    def ring(z):
        r = radius(z)
        pts = []
        for i in range(FLUTES):
            for k in range(sub):
                a = (i + k / sub) / FLUTES * math.tau
                rr = r - depth * (r / R0) * math.sin(math.pi * k / sub)
                pts.append(Vector((math.cos(a) * rr, math.sin(a) * rr, z)))
        return pts

    zs = [z0 + (z1 - z0) * j / (rings - 1) for j in range(rings)]
    rs = [ring(z) for z in zs]
    n = FLUTES * sub
    for r0, r1 in zip(rs, rs[1:]):
        for i in range(n):
            j = (i + 1) % n
            mid = (r0[i] + r0[j]) / 2
            m.poly("stone", [r0[i], r0[j], r1[j], r1[i]], out=(mid.x, mid.y, 0), smooth=True)
    # Drums: the joints every 1.5 m, a faint dark line.
    z = SHAFT0 + 1.5
    while z < z1 - 0.05:
        if z > z0 + 0.05:
            lathe(m, "stone", [(radius(z) - 0.02, z - 0.008), (radius(z) - 0.005, z), (radius(z) - 0.02, z + 0.008)], seg=FLUTES, uv=False)
        z += 1.5


# ---- the capital, the gallery and the flame -----------------------------------------------


def top(m):
    z = SHAFT1
    r = radius(z)
    # Annulets, the echinus and the abacus.
    lathe(m, "stone", [(r, z), (r + 0.04, z + 0.04), (r, z + 0.08), (r + 0.04, z + 0.12), (r, z + 0.16), (r + 0.03, z + 0.22), (r + 0.18, z + 0.36), (r + 0.42, z + 0.62), (1.6, z + 0.72), (1.6, z + 0.74)], seg=40, uv=False)
    ab0, ab1 = z + 0.74, z + 1.24
    A = 1.85
    m.box("stone", (-A, -A, ab0), (A, A, ab1))
    m.box("stone", (-A - 0.06, -A - 0.06, ab1 - 0.12), (A + 0.06, A + 0.06, ab1))
    # The gallery's railing round the abacus: iron posts, two rails, a top rail.
    g = A - 0.08
    rh = 1.15
    for p, q in (((-g, -g), (g, -g)), ((g, -g), (g, g)), ((g, g), (-g, g)), ((-g, g), (-g, -g))):
        a, b = Vector((*p, ab1)), Vector((*q, ab1))
        L = (b - a).length
        k = int(L / 0.14)
        for i in range(k + 1):
            c = a + (b - a) * (i / k)
            m.strut("iron", c, c + Z * rh, 0.025)
        for h, t in ((0.08, 0.04), (rh - 0.12, 0.035), (rh, 0.06)):
            m.strut("iron", a + Z * h, b + Z * h, t, t * 0.8)
        # A finial knob at each corner.
        m.cyl("iron", a.x, a.y, 0.05, ab1 + rh, ab1 + rh + 0.12, seg=6)
    # The drum: a stone cylinder with a base, a band and a cap; a small door.
    d0 = ab1
    DR = 0.95
    lathe(m, "stone", [(DR + 0.12, d0), (DR + 0.12, d0 + 0.18), (DR, d0 + 0.26), (DR, d0 + 1.2), (DR + 0.1, d0 + 1.26), (DR + 0.1, d0 + 1.4), (DR + 0.18, d0 + 1.5), (DR + 0.18, d0 + 1.6), (0.0, d0 + 1.6)], seg=24, uv=False)
    F = sides(m, 2 * DR, 2 * DR)["front"]
    F.box("dark", -0.32, 0.32, d0 + 0.26, d0 + 1.05, -0.04, 0.03)
    F.box("stone", -0.42, 0.42, d0 + 1.05, d0 + 1.14, -0.02, 0.06)
    # The urn: a foot, a stem, a gadrooned bowl and a lip, gilt.
    u0 = d0 + 1.6
    prof = [(0.62, u0), (0.62, u0 + 0.12), (0.4, u0 + 0.22), (0.32, u0 + 0.45), (0.42, u0 + 0.55), (0.75, u0 + 0.75), (0.98, u0 + 1.05), (1.02, u0 + 1.3), (0.94, u0 + 1.5), (0.98, u0 + 1.58), (1.04, u0 + 1.66), (0.9, u0 + 1.7)]
    lathe(m, "gilt", prof, seg=24, uv=False)
    for i in range(16):
        a = i / 16 * math.tau
        pts = [Vector((math.cos(a) * (rr + 0.025), math.sin(a) * (rr + 0.025), zz)) for rr, zz in prof[4:9]]
        for p, q in zip(pts, pts[1:]):
            m.strut("gilt", p, q, 0.08, 0.05)
    m.poly("gilt", [(math.cos(i / 24 * math.tau) * 0.9, math.sin(i / 24 * math.tau) * 0.9, u0 + 1.68) for i in range(24)], out=Z)
    # The flame: gilt tongues licking up from the bowl, the middle one tallest.
    f0 = u0 + 1.6
    tongue(m, Vector((0, 0, f0)), 0.0, 3.2, 0.55, 0.0)
    for i in range(7):
        a = i / 7 * math.tau + 0.3
        tongue(m, Vector((math.cos(a) * 0.45, math.sin(a) * 0.45, f0)), a, 1.6 + 0.5 * ((i * 3) % 4) / 3, 0.32, 0.5 if i % 2 else -0.5)


def tongue(m, base, a, h, r, twist, n=9, seg=8):
    """One tongue of the flame: a tapering, curling body from `base`, leaning out along angle a."""
    out = Vector((math.cos(a), math.sin(a), 0))
    side = Vector((-out.y, out.x, 0))
    path = []
    for k in range(n):
        t = k / (n - 1)
        lean = out * (0.35 * math.sin(t * math.pi * 0.8) * (h / 2)) * (0 if h > 3 else 1)
        curl = side * (twist * 0.3 * math.sin(t * math.pi * 1.4))
        sway = Vector((0.12 * math.sin(t * 5 + a), 0.12 * math.cos(t * 4 + a), 0)) * t
        path.append(base + Z * (h * t) + lean + curl + sway)
    rings = []
    for k, p in enumerate(path):
        t = k / (n - 1)
        rr = r * (1 - t) ** 0.75 * (1 + 0.25 * math.sin(t * math.pi))
        q = path[min(k + 1, n - 1)] - path[max(k - 1, 0)]
        q.normalize()
        u = q.cross(side if abs(q.dot(side)) < 0.9 else out).normalized()
        v = q.cross(u).normalized()
        # A flattened section, like a tongue of fire rather than a cone.
        rings.append([p + (u * math.cos(s / seg * math.tau) * rr + v * math.sin(s / seg * math.tau) * rr * 0.55) for s in range(seg)])
    for k in range(n - 1):
        for s in range(seg):
            j = (s + 1) % seg
            c = (path[k] + path[k + 1]) / 2
            mid = (rings[k][s] + rings[k][j] + rings[k + 1][s] + rings[k + 1][j]) / 4 - c
            if k == n - 2:
                m.poly("gilt", [rings[k][s], rings[k][j], path[-1]], out=mid, smooth=True)
            else:
                m.poly("gilt", [rings[k][s], rings[k][j], rings[k + 1][j], rings[k + 1][s]], out=mid, smooth=True)
