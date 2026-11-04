# The river bridge for the realistic city: a riveted steel Pratt through
# truss carrying the road out of town, replacing the kit's truss. Same
# footprint as the kit's: 44 m along x, 11 m wide, the road deck at the
# origin's height, stone abutments down into the banks.
#
# Two trusses (built-up chords, I-section verticals, flat-bar diagonals,
# gusset plates at the joints) stand on the deck's edges; portal frames
# with a nameplate and X-bracing tie their tops. Between them: an 8 m
# carriageway with markings, kerbed footways with iron railings, and
# lanterns on the end posts. Under the deck: cross girders and stringers
# on bearings.
#
# Piece: bridge. Roles: girder (the truss paint), road, pave, concrete,
# stone, iron, lamp, marking, panel (the nameplate).
import math

from lib import Model, Vector

ID = "bridge"
L, W, H = 44.0, 11.0, 6.4  # length, width over the trusses, truss height
N = 11  # panels
STEP = L / N
TY = W / 2 - 0.25  # truss centre lines at y = +-TY
DECK = 0.065  # top of the road
CW = 4.1  # half the carriageway
FOOT = 0.18  # footway kerb height


def chord(m, x0, x1, y, z, h=0.5, w=0.42):
    """A built-up box chord along x, with a flange lip each side."""
    m.box("girder", (x0, y - w / 2, z - h / 2), (x1, y + w / 2, z + h / 2))
    for s in (-1, 1):
        m.box("girder", (x0, y + s * w / 2 - 0.02, z + h / 2 - 0.03), (x1, y + s * (w / 2 + 0.05), z + h / 2))
        m.box("girder", (x0, y + s * w / 2 - 0.02, z - h / 2), (x1, y + s * (w / 2 + 0.05), z - h / 2 + 0.03))


def ibeam(m, a, b, d, w, role="girder"):
    """An I-section member from a to b in the truss plane (xz), web d deep across it, flanges w wide (y)."""
    a, b = Vector(a), Vector(b)
    ax = (b - a).normalized()
    across = Vector((-ax.z, 0, ax.x))  # in the xz plane, perpendicular
    # Mesh.strut's first size runs along ax x z (y here), unless the bar is
    # vertical, when it runs along x: give sizes as (across y, in the plane).
    vertical = abs(ax.z) > 0.99

    def bar(p, q, ys, ps):
        m.strut(role, tuple(p), tuple(q), *((ps, ys) if vertical else (ys, ps)))

    for s in (-1, 1):
        off = across * (d / 2 * s)
        bar(a + off, b + off, w, 0.04)
    bar(a, b, 0.03, d)


def gusset(m, x, y, z, s=0.9):
    for side in (-1, 1):
        yy = y + side * 0.24
        m.poly("girder", [(x - s / 2, yy, z - s / 2), (x + s / 2, yy, z - s / 2), (x + s / 2, yy, z + s / 2), (x - s / 2, yy, z + s / 2)], out=(0, side, 0))


def truss(m, y):
    zb, zt = DECK + 0.45, DECK + H
    chord(m, -L / 2, L / 2, y, zb, h=0.7)
    chord(m, -L / 2 + STEP, L / 2 - STEP, y, zt)
    for i in range(N + 1):
        x = -L / 2 + i * STEP
        gusset(m, x, y, zb)
        if 0 < i < N:
            gusset(m, x, y, zt)
            ibeam(m, (x, y, zb), (x, y, zt), 0.32, 0.3)
    # End posts, inclined.
    for s in (-1, 1):
        ibeam(m, (s * L / 2, y, zb), (s * (L / 2 - STEP), y, zt), 0.5, 0.42)
    # Pratt diagonals, sloping down toward the middle.
    for i in range(1, N - 1):
        x0 = -L / 2 + i * STEP
        x1 = x0 + STEP
        if x1 <= 0.01:
            a, b = (x0, y, zt), (x1, y, zb)
        else:
            a, b = (x1, y, zt), (x0, y, zb)
        ibeam(m, a, b, 0.2, 0.26)


def portal(m, s):
    """The portal frame at an end: a deep lattice girder between the end posts, a nameplate."""
    x = s * (L / 2 - STEP) + s * 0.6
    z0, z1 = DECK + H - 1.5, DECK + H - 0.3
    for z in (z0, z1):
        m.strut("girder", (x, -TY, z), (x, TY, z), 0.24, 0.24)
    n = 8
    for k in range(n):
        y0 = -TY + k * (2 * TY) / n
        y1 = y0 + (2 * TY) / n
        m.strut("girder", (x, y0, z0), (x, y1, z1), 0.08)
        m.strut("girder", (x, y0, z1), (x, y1, z0), 0.08)
    m.box("panel", (x - 0.02 * s - 0.03, -1.6, z0 + 0.2), (x - 0.02 * s + 0.03, 1.6, z1 - 0.2))


def top_bracing(m):
    zt = DECK + H
    for i in range(1, N):
        x = -L / 2 + i * STEP
        m.strut("girder", (x, -TY, zt), (x, TY, zt), 0.22, 0.3)
        if i < N - 1:
            m.strut("girder", (x, -TY, zt + 0.05), (x + STEP, TY, zt + 0.05), 0.08)
            m.strut("girder", (x, TY, zt + 0.05), (x + STEP, -TY, zt + 0.05), 0.08)
        # Knee braces under the struts, the trusses' sway frames.
        for s in (-1, 1):
            m.strut("girder", (x, s * TY, zt - 1.2), (x, s * (TY - 1.0), zt - 0.1), 0.08)


def deck(m):
    # Concrete slab with the road on it, kerbed footways inside the trusses.
    m.box("concrete", (-L / 2, -W / 2, -0.55), (L / 2, W / 2, 0.0))
    m.poly("road", [(-L / 2, -CW, DECK), (L / 2, -CW, DECK), (L / 2, CW, DECK), (-L / 2, CW, DECK)], out=(0, 0, 1))
    for s in (-1, 1):
        y0, y1 = sorted((s * CW, s * (TY - 0.3)))
        m.box("pave", (-L / 2, y0, 0.0), (L / 2, y1, DECK + FOOT))
        k0, k1 = sorted((s * CW, s * (CW + 0.2)))
        m.box("concrete", (-L / 2, k0, 0.0), (L / 2, k1, DECK + FOOT + 0.01))
        # Iron railing along the footway's outer edge (inside the truss).
        y = s * (TY - 0.45)
        m.box("iron", (-L / 2, y - 0.03, DECK + FOOT + 1.05), (L / 2, y + 0.03, DECK + FOOT + 1.12))
        m.box("iron", (-L / 2, y - 0.015, DECK + FOOT + 0.12), (L / 2, y + 0.015, DECK + FOOT + 0.16))
        for k in range(int(L / 0.6) + 1):
            x = -L / 2 + k * 0.6
            m.box("iron", (x - 0.012, y - 0.012, DECK + FOOT), (x + 0.012, y + 0.012, DECK + FOOT + 1.06))
    # Markings: a dashed centre line, solid edges.
    for k in range(int(L / 6)):
        x = -L / 2 + 1.5 + k * 6
        m.poly("marking", [(x, -0.07, DECK + 0.004), (x + 3, -0.07, DECK + 0.004), (x + 3, 0.07, DECK + 0.004), (x, 0.07, DECK + 0.004)], out=(0, 0, 1))
    for s in (-1, 1):
        y = s * (CW - 0.3)
        m.poly("marking", [(-L / 2, y - 0.07, DECK + 0.004), (L / 2, y - 0.07, DECK + 0.004), (L / 2, y + 0.07, DECK + 0.004), (-L / 2, y + 0.07, DECK + 0.004)], out=(0, 0, 1))


def underside(m):
    for i in range(N + 1):
        x = -L / 2 + i * STEP
        m.box("girder", (x - 0.2, -TY, -1.35), (x + 0.2, TY, -0.55))
    for y in (-3.2, -1.1, 1.1, 3.2):
        m.box("girder", (-L / 2, y - 0.15, -1.0), (L / 2, y + 0.15, -0.55))
    # Bearings on the abutments.
    for s in (-1, 1):
        for y in (-TY, TY):
            m.box("iron", (s * (L / 2 - 0.6) - 0.35, y - 0.35, -1.6), (s * (L / 2 - 0.6) + 0.35, y + 0.35, -1.35))


def abutments(m):
    for s in (-1, 1):
        x0, x1 = sorted((s * L / 2, s * (L / 2 - 3.5)))
        m.box("stone", (x0, -W / 2 - 0.8, -6.5), (x1, W / 2 + 0.8, -1.6))
        m.box("stone", (x0 - 0.1, -W / 2 - 0.9, -1.6), (x1 + 0.1, W / 2 + 0.9, -1.45))
        # Wing walls back into the bank, and a pier cap under each truss.
        for t in (-1, 1):
            y = t * (W / 2 + 0.5)
            m.box("stone", (x0, y - 0.6, -6.5), (x1, y + 0.6, 1.2))
            m.box("stone", (x0 - 0.1, y - 0.7, 1.2), (x1 + 0.1, y + 0.7, 1.4))


def lanterns(m):
    """Cast-iron lanterns on the abutments' wing walls, lit at night."""
    for s in (-1, 1):
        for t in (-1, 1):
            x, y = s * (L / 2 - 1.75), t * (W / 2 + 0.5)
            m.cyl("iron", x, y, 0.12, 1.4, 1.6, seg=8, r1=0.08)
            m.cyl("iron", x, y, 0.06, 1.6, 4.2, seg=8, r1=0.045)
            m.cyl("lamp", x, y, 0.16, 4.2, 4.65, seg=8, r1=0.2)
            m.cyl("iron", x, y, 0.24, 4.65, 4.8, seg=8, r1=0.04)


def build(out, bake=True):
    M = Model(ID)
    M.piece("bridge")
    m = M.m
    deck(m)
    for y in (-TY, TY):
        truss(m, y)
    for s in (-1, 1):
        portal(m, s)
    top_bracing(m)
    underside(m)
    abutments(m)
    lanterns(m)
    M.export(out, bake, size=2048, samples=96, smooth=1.5)
