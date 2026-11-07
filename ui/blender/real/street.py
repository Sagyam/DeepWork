# Street furniture for the realistic city: lights, traffic signals, fences
# and walls, and the small things on a pavement.
#
# Pieces (base at the origin; the "front", -y here and +z in the app, is the
# side that faces the street):
#   lamp_led       7 m tapered pole, a slim LED head on an arm over the road (front)
#   lamp_heritage  4.2 m cast-iron post with a lantern (old town, parks)
#   lamp_park      3.6 m post-top with a glass cylinder (parks, paths)
#   signal_mast    6 m pole, a 4.5 m mast arm over the road (front) with two
#                  signal heads facing +x, a pedestrian signal and push button
#   signal_post    3.4 m post, a signal head facing +x, a pedestrian signal (front)
#   fence_panel    1.8 m timber close-board panel with posts, 2.4 m along x
#   fence_rail     post-and-rail, three rails, 2.4 m
#   fence_iron     iron railing with spear tops on a stone plinth, 2.4 m
#   wall_brick     a 1 m garden wall with a stone coping, 2.4 m
#   hydrant, bin, bench, bollard, busstop
# Roles: galv (galvanised steel), iron, dark (signal housings), lamp (lit at
# night), sig_red, sig_amber, sig_green, ped_red, ped_white (signal lenses,
# set by the app's signal cycle), wood, brick, stone, concrete, hydrant,
# panel (the bus stop's timetable and sign), busflag, canopy (its glass).
import math

from lib import Model, Vector

ID = "street"


class Shift:
    """Draws into a Mesh with every point moved by `off` (the piece's place in the bake)."""

    def __init__(self, m, off):
        self.m, self.off = m, Vector(off)

    def _p(self, p):
        return tuple(Vector(p) + self.off)

    def poly(self, role, pts, out=None, uvs=None, smooth=False):
        return self.m.poly(role, [self._p(p) for p in pts], out=out, uvs=uvs, smooth=smooth)

    def box(self, role, lo, hi, skip=()):
        self.m.box(role, self._p(lo), self._p(hi), skip)

    def cyl(self, role, x, y, r, z0, z1, seg=12, top=True, bottom=False, r1=None):
        o = self.off
        self.m.cyl(role, x + o.x, y + o.y, r, z0 + o.z, z1 + o.z, seg=seg, top=top, bottom=bottom, r1=r1)

    def strut(self, role, a, b, t, t2=None):
        self.m.strut(role, self._p(a), self._p(b), t, t2)


def disc(m, role, c, r, n, seg=12):
    """A flat disc at c facing n (a signal lens)."""
    c, n = Vector(c), Vector(n).normalized()
    t = n.orthogonal().normalized()
    b = n.cross(t)
    pts = [c + (t * math.cos(i / seg * math.tau) + b * math.sin(i / seg * math.tau)) * r for i in range(seg)]
    m.poly(role, [tuple(p) for p in pts], out=n)


def signal_head(m, c, face, lenses=("sig_red", "sig_amber", "sig_green")):
    """A three-aspect signal head centred at c facing `face` (+x or -y), with backplate and visors."""
    c = Vector(c)
    f = Vector(face)
    side = Vector((0, 0, 1)).cross(f).normalized()
    w, d, h = 0.34, 0.26, 1.0
    lo = c - side * (w / 2) - f * d + Vector((0, 0, -h / 2))
    hi = c + side * (w / 2) + Vector((0, 0, h / 2))
    m.box("dark", tuple(Vector((min(lo.x, hi.x), min(lo.y, hi.y), lo.z))), tuple(Vector((max(lo.x, hi.x), max(lo.y, hi.y), hi.z))))
    # Backplate with a white border.
    bp = c - f * (d + 0.01)
    for (ww, hh, role, off) in ((0.6, 1.24, "panel", 0.0), (0.54, 1.18, "dark", 0.005)):
        p = bp - f * off
        corners = [p - side * ww / 2 + Vector((0, 0, -hh / 2)), p + side * ww / 2 + Vector((0, 0, -hh / 2)), p + side * ww / 2 + Vector((0, 0, hh / 2)), p - side * ww / 2 + Vector((0, 0, hh / 2))]
        m.poly(role, [tuple(q) for q in corners], out=-f)
        m.poly(role, [tuple(q) for q in corners], out=f)
    for k, role in enumerate(lenses):
        z = h / 2 - 0.18 - k * 0.32
        lc = c + f * 0.006 + Vector((0, 0, z))
        disc(m, role, lc, 0.1, f)
        # Visor: a hood over the lens.
        a = lc + Vector((0, 0, 0.13)) - side * 0.13
        b = lc + Vector((0, 0, 0.13)) + side * 0.13
        m.poly("dark", [tuple(a), tuple(b), tuple(b + f * 0.18 - Vector((0, 0, 0.04))), tuple(a + f * 0.18 - Vector((0, 0, 0.04)))], out=Vector((0, 0, 1)))


def ped_head(m, c, face):
    c, f = Vector(c), Vector(face)
    side = Vector((0, 0, 1)).cross(f).normalized()
    w, h, d = 0.3, 0.6, 0.2
    a = c - side * w / 2 - f * d - Vector((0, 0, h / 2))
    b = c + side * w / 2 + Vector((0, 0, h / 2))
    m.box("dark", (min(a.x, b.x), min(a.y, b.y), a.z), (max(a.x, b.x), max(a.y, b.y), b.z))
    for z, role in ((0.14, "ped_red"), (-0.14, "ped_white")):
        q = c + f * 0.006 + Vector((0, 0, z))
        m.poly(role, [tuple(q - side * 0.11 - Vector((0, 0, 0.11))), tuple(q + side * 0.11 - Vector((0, 0, 0.11))), tuple(q + side * 0.11 + Vector((0, 0, 0.11))), tuple(q - side * 0.11 + Vector((0, 0, 0.11)))], out=f)


def pole(m, role, h, r0, r1, seg=12):
    m.cyl(role, 0, 0, r0, 0, h, seg=seg, r1=r1)


def lamp_led(m):
    pole(m, "galv", 7.0, 0.09, 0.055)
    m.cyl("galv", 0, 0, 0.16, 0, 0.5, seg=12, r1=0.12)  # base collar
    # A curved arm out to the front, then the flat head.
    pts = [Vector((0, 0, 6.85)), Vector((0, -0.4, 7.15)), Vector((0, -0.95, 7.3)), Vector((0, -1.5, 7.32))]
    for a, b in zip(pts, pts[1:]):
        m.strut("galv", tuple(a), tuple(b), 0.07)
    m.box("galv", (-0.17, -2.15, 7.24), (0.17, -1.42, 7.38))
    m.box("lamp", (-0.14, -2.1, 7.23), (0.14, -1.47, 7.24))


def lamp_heritage(m):
    # Fluted cast-iron post: a stepped base, a tapering shaft, a cross-arm, a lantern.
    m.cyl("iron", 0, 0, 0.22, 0, 0.5, seg=12, r1=0.17)
    m.cyl("iron", 0, 0, 0.17, 0.5, 0.62, seg=12, r1=0.1)
    m.cyl("iron", 0, 0, 0.085, 0.62, 3.5, seg=10, r1=0.06)
    m.cyl("iron", 0, 0, 0.1, 3.5, 3.6, seg=10)
    m.strut("iron", (-0.32, 0, 3.4), (0.32, 0, 3.4), 0.035)
    # Lantern: a tapered glass box under a cap and finial.
    z0, z1 = 3.65, 4.25
    for k in range(4):
        a0, a1 = k / 4 * math.tau + math.pi / 4, (k + 1) / 4 * math.tau + math.pi / 4
        p = lambda a, r, z: (math.cos(a) * r, math.sin(a) * r, z)  # noqa: E731
        m.poly("lamp", [p(a0, 0.16, z0), p(a1, 0.16, z0), p(a1, 0.22, z1), p(a0, 0.22, z1)], out=(math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0))
        m.strut("iron", p(a0, 0.16, z0), p(a0, 0.22, z1), 0.02)
    m.cyl("iron", 0, 0, 0.12, 3.6, 3.66, seg=8, bottom=True)
    m.cyl("iron", 0, 0, 0.27, 4.25, 4.45, seg=8, r1=0.05)
    m.cyl("iron", 0, 0, 0.03, 4.45, 4.6, seg=6, r1=0.0)


def lamp_park(m):
    pole(m, "galv", 3.0, 0.06, 0.05, seg=10)
    m.cyl("lamp", 0, 0, 0.13, 3.0, 3.45, seg=12)
    m.cyl("galv", 0, 0, 0.16, 3.45, 3.55, seg=12, r1=0.14)


def signal_mast(m):
    pole(m, "galv", 6.2, 0.15, 0.11, seg=12)
    m.cyl("galv", 0, 0, 0.24, 0, 0.35, seg=12, r1=0.2)
    m.strut("galv", (0, 0, 5.7), (0, -4.6, 5.85), 0.12, 0.12)
    m.strut("galv", (0, 0, 4.9), (0, -1.6, 5.72), 0.05)
    for y in (-2.4, -4.3):
        m.strut("dark", (0, y, 5.8), (0, y, 5.55), 0.04)
        signal_head(m, (0.13, y, 5.0), (1, 0, 0))
    signal_head(m, (0.25, 0, 3.3), (1, 0, 0))
    ped_head(m, (0, -0.22, 2.5), (0, -1, 0))
    m.box("dark", (-0.07, -0.21, 1.05), (0.07, -0.13, 1.3))
    m.box("sig_amber", (-0.03, -0.216, 1.17), (0.03, -0.21, 1.22))


def signal_post(m):
    pole(m, "galv", 3.6, 0.08, 0.07, seg=10)
    signal_head(m, (0.2, 0, 2.95), (1, 0, 0))
    ped_head(m, (0, -0.15, 2.0), (0, -1, 0))
    m.box("dark", (-0.06, -0.14, 1.0), (0.06, -0.08, 1.24))
    m.box("sig_amber", (-0.025, -0.146, 1.12), (0.025, -0.14, 1.16))


def fence_panel(m, L=2.4):
    for x in (-L / 2, L / 2):
        m.box("wood", (x - 0.05, -0.05, 0), (x + 0.05, 0.05, 1.9))
        m.box("wood", (x - 0.06, -0.06, 1.9), (x + 0.06, 0.06, 1.94))
    m.box("concrete", (-L / 2 + 0.05, -0.02, 0), (L / 2 - 0.05, 0.02, 0.15))
    # Feather-edge boards, overlapping, on two arris rails behind.
    n = 16
    for i in range(n):
        x0 = -L / 2 + 0.05 + i * (L - 0.1) / n
        m.box("wood", (x0, -0.035 + (i % 2) * 0.01, 0.15), (x0 + (L - 0.1) / n + 0.02, -0.015 + (i % 2) * 0.01, 1.8))
    for z in (0.45, 1.45):
        m.box("wood", (-L / 2, -0.015, z), (L / 2, 0.035, z + 0.08))
    m.box("wood", (-L / 2 + 0.05, -0.05, 1.8), (L / 2 - 0.05, 0.0, 1.84))


def fence_rail(m, L=2.4):
    for x in (-L / 2, L / 2):
        m.box("wood", (x - 0.07, -0.07, 0), (x + 0.07, 0.07, 1.25))
    for z in (0.3, 0.68, 1.05):
        m.box("wood", (-L / 2, -0.03, z), (L / 2, 0.03, z + 0.11))


def fence_iron(m, L=2.4):
    m.box("stone", (-L / 2, -0.15, 0), (L / 2, 0.15, 0.45))
    m.box("stone", (-L / 2 - 0.02, -0.17, 0.45), (L / 2 + 0.02, 0.17, 0.5))
    for x in (-L / 2, L / 2):
        m.box("stone", (x - 0.2, -0.2, 0), (x + 0.2, 0.2, 1.4))
        m.box("stone", (x - 0.23, -0.23, 1.4), (x + 0.23, 0.23, 1.48))
    for z in (0.62, 1.32):
        m.box("iron", (-L / 2 + 0.2, -0.015, z), (L / 2 - 0.2, 0.015, z + 0.035))
    n = 15
    for i in range(n):
        x = -L / 2 + 0.28 + i * (L - 0.56) / (n - 1)
        m.box("iron", (x - 0.012, -0.012, 0.5), (x + 0.012, 0.012, 1.42))
        m.poly("iron", [(x - 0.03, 0, 1.42), (x + 0.03, 0, 1.42), (x, 0, 1.52)], out=(0, -1, 0))
        m.poly("iron", [(x - 0.03, 0, 1.42), (x + 0.03, 0, 1.42), (x, 0, 1.52)], out=(0, 1, 0))


def wall_brick(m, L=2.4):
    m.box("brick", (-L / 2, -0.12, 0), (L / 2, 0.12, 0.92))
    m.box("stone", (-L / 2, -0.16, 0.92), (L / 2, 0.16, 0.98))
    m.poly("stone", [(-L / 2, -0.16, 0.98), (L / 2, -0.16, 0.98), (L / 2, 0, 1.05), (-L / 2, 0, 1.05)], out=(0, -0.4, 1))
    m.poly("stone", [(-L / 2, 0, 1.05), (L / 2, 0, 1.05), (L / 2, 0.16, 0.98), (-L / 2, 0.16, 0.98)], out=(0, 0.4, 1))


def hydrant(m):
    m.cyl("hydrant", 0, 0, 0.16, 0, 0.08, seg=12, r1=0.13)
    m.cyl("hydrant", 0, 0, 0.12, 0.08, 0.6, seg=12, r1=0.11)
    m.cyl("hydrant", 0, 0, 0.14, 0.6, 0.66, seg=12)
    m.cyl("hydrant", 0, 0, 0.12, 0.66, 0.8, seg=12, r1=0.04)
    m.cyl("hydrant", 0, 0, 0.03, 0.8, 0.86, seg=6)
    for d in ((1, 0), (-1, 0), (0, -1)):
        a = Vector((d[0] * 0.1, d[1] * 0.1, 0.45))
        b = Vector((d[0] * 0.2, d[1] * 0.2, 0.45))
        m.strut("hydrant", tuple(a), tuple(b), 0.09)
        m.strut("galv", tuple(b), tuple(b + Vector((d[0], d[1], 0)) * 0.03), 0.1)


def bin_(m):
    m.cyl("dark", 0, 0, 0.26, 0, 0.92, seg=14)
    m.cyl("galv", 0, 0, 0.28, 0.92, 0.98, seg=14, r1=0.24)
    m.cyl("galv", 0, 0, 0.27, 0.06, 0.14, seg=14)
    m.box("galv", (-0.04, -0.3, 0), (0.04, -0.24, 0.9))


def bench(m):
    for x in (-0.75, 0.75):
        m.box("iron", (x - 0.04, -0.25, 0), (x + 0.04, 0.2, 0.06))
        m.box("iron", (x - 0.04, -0.22, 0.06), (x + 0.04, -0.16, 0.44))
        m.box("iron", (x - 0.04, 0.12, 0.06), (x + 0.04, 0.18, 0.86))
        m.box("iron", (x - 0.04, -0.24, 0.42), (x + 0.04, 0.2, 0.46))
    for k in range(4):
        y = -0.24 + k * 0.105
        m.box("wood", (-1.0, y, 0.46), (1.0, y + 0.085, 0.5))
    for k in range(3):
        z = 0.56 + k * 0.11
        m.box("wood", (-1.0, 0.2, z), (1.0, 0.235, z + 0.085))


def bollard(m):
    m.cyl("iron", 0, 0, 0.09, 0, 0.85, seg=10)
    m.cyl("iron", 0, 0, 0.1, 0.85, 0.92, seg=10, r1=0.03)
    m.cyl("panel", 0, 0, 0.092, 0.72, 0.76, seg=10, top=False)


def busstop(m):
    """A glazed shelter facing the street (front), a seat, a timetable and a flag sign."""
    W, D, H = 3.2, 1.3, 2.45
    for x in (-W / 2, W / 2):
        for y in (-D / 2 + 0.05, D / 2 - 0.05):
            m.box("galv", (x - 0.04, y - 0.04, 0), (x + 0.04, y + 0.04, H))
    m.box("galv", (-W / 2 - 0.1, -D / 2 - 0.15, H), (W / 2 + 0.1, D / 2 + 0.05, H + 0.1))
    m.poly("canopy", [(-W / 2, D / 2 - 0.05, 0.1), (W / 2, D / 2 - 0.05, 0.1), (W / 2, D / 2 - 0.05, H - 0.05), (-W / 2, D / 2 - 0.05, H - 0.05)], out=(0, 1, 0))
    m.poly("canopy", [(-W / 2, D / 2 - 0.05, 0.1), (W / 2, D / 2 - 0.05, 0.1), (W / 2, D / 2 - 0.05, H - 0.05), (-W / 2, D / 2 - 0.05, H - 0.05)], out=(0, -1, 0))
    for x in (-W / 2, W / 2):
        pts = [(x, -D / 2 + 0.25, 0.1), (x, D / 2 - 0.05, 0.1), (x, D / 2 - 0.05, H - 0.05), (x, -D / 2 + 0.25, H - 0.05)]
        m.poly("canopy", pts, out=(1, 0, 0))
        m.poly("canopy", pts, out=(-1, 0, 0))
    m.box("panel", (W / 2 - 0.9, D / 2 - 0.12, 0.9), (W / 2 - 0.1, D / 2 - 0.07, 2.1))
    m.box("galv", (-W / 2 + 0.2, D / 2 - 0.45, 0.45), (W / 2 - 1.1, D / 2 - 0.1, 0.5))
    # The stop's flag on its own pole, by the kerb.
    m.cyl("galv", -W / 2 - 0.6, -D / 2 - 0.1, 0.04, 0, 2.9, seg=8)
    m.box("panel", (-W / 2 - 0.9, -D / 2 - 0.14, 2.3), (-W / 2 - 0.3, -D / 2 - 0.06, 2.9))
    m.box("busflag", (-W / 2 - 0.86, -D / 2 - 0.145, 2.62), (-W / 2 - 0.34, -D / 2 - 0.14, 2.86))


PIECES = [
    ("lamp_led", lamp_led), ("lamp_heritage", lamp_heritage), ("lamp_park", lamp_park),
    ("signal_mast", signal_mast), ("signal_post", signal_post),
    ("fence_panel", fence_panel), ("fence_rail", fence_rail), ("fence_iron", fence_iron), ("wall_brick", wall_brick),
    ("hydrant", hydrant), ("bin", bin_), ("bench", bench), ("bollard", bollard), ("busstop", busstop),
]


def build(out, bake=True):
    M = Model(ID)
    x = 0.0
    for name, make in PIECES:
        M.piece(name, (x, 0, 0))
        make(Shift(M.m, (x, 0, 0)))
        x += 7.0
    M.export(out, bake, size=2048, samples=96, smooth=1.5)
