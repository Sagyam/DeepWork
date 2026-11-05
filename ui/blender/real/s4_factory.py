# S4, brick factory: a late-Victorian machine works on a town lot. A single-
# storey brick shed under a three-bay sawtooth roof, its serrated gables to
# the street: each bay a slope of corrugated sheet rising to a ridge and a
# wall of north-light glazing dropping back to the valley. A plinth of blue
# engineering brick, pilasters between the bays, tall steel windows of small
# panes (a hopper tilted open in some) under segmental brick arches with
# stone keys, a stone string course and a flush frieze above it that carries
# the firm's name painted on the brick, a corbelled eaves band, coped gables
# with a works clock in the middle one and round vents in the others.
#
# On the street: a raised loading dock with steps, rubber buffers and a
# corrugated canopy on steel brackets in front of ledged-and-braced doors
# under a steel beam, and the office door under a pedimented stone hood. To
# the right a lean-to boiler house and, on a square base fed by a brick flue,
# the round chimney stack: tapering, banded in iron, with ladder staples, a
# copper lightning conductor and a corbelled cap. The app tints the brick,
# the steelwork and the doors, the roof sheet, and picks the painted name.
#
# Pieces (base at the origin):
#   body  the walls to the eaves, the dock and its canopy, the boiler house,
#         the stack's base and flue
#   roof  gables and copings, the sawtooth with its glazing and gutters,
#         clock and vents, ventilators, and the stack's shaft
import math

from lib import Model, Z, fpoly, hood, letters, new_id, pane, sides, sill
from mathutils import Vector

ID = "s4"
N, TW = 3, 3.6  # sawtooth bays and their width
X0 = -6.75  # the shed's left wall
X1 = X0 + N * TW  # its right wall, under the last north light
BX = 6.75  # the boiler house's right wall
YD, DOCK = -5.2, 1.4  # the dock's front, its depth
YF = YD + DOCK  # the shed's front
YB = 5.2  # the shed's back (and the boiler house's)
YH = 1.7  # the boiler house's front
WALL = 0.34  # a brick and a half
PL = 0.5  # the blue-brick plinth
HV = 5.3  # wall top, the valleys and the eaves: the roof piece's base
RISE = 2.2
HR = HV + RISE  # the ridges
PAR = 0.35  # the gables stand this far above the roof
SC = 4.0  # string course
BH, BT = 3.3, 3.9  # the boiler house's wall top, and its roof against the shed
CX, CY, CR0, CR1, CT = 5.4, -1.2, 0.8, 0.5, 17.2  # the stack: centre, radius at the base and top, top
CB = 3.45  # top of the stack's base
WS, DS = X1 - X0, YB - YF
SX, SY = (X0 + X1) / 2, (YF + YB) / 2


def build(out, bake=True):
    M = Model(ID, seed=11)
    M.sharp = math.radians(40)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, HV))
    roof(M)
    M.export(out, bake)


# ---- helpers ------------------------------------------------------------------------


def disc(F, role, u, z, r, w, seg=20):
    fpoly(F, role, [(u + math.cos(i / seg * math.tau) * r, z + math.sin(i / seg * math.tau) * r) for i in range(seg)], w)


def annulus(F, role, u, z, r0, r1, w, seg=20, rim=True):
    """A flat ring in the facade plane at depth w, and its outer rim back to the wall."""
    m = F.m
    for i in range(seg):
        a0, a1 = i / seg * math.tau, (i + 1) / seg * math.tau
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        fpoly(F, role, [(u + c0 * r0, z + s0 * r0), (u + c1 * r0, z + s1 * r0), (u + c1 * r1, z + s1 * r1), (u + c0 * r1, z + s0 * r1)], w)
        if rim:
            m.poly(role, [F.p(u + c0 * r1, z + s0 * r1, 0), F.p(u + c1 * r1, z + s1 * r1, 0), F.p(u + c1 * r1, z + s1 * r1, w), F.p(u + c0 * r1, z + s0 * r1, w)],
                   out=F.t * (c0 + c1) + Z * (s0 + s1), smooth=True)


def arch(F, a, b, e, rise=0.28, ring=0.34, D=WALL):
    """A segmental arch over the opening (a..b, ..e) whose crown is at e: brick
    spandrels filling the opening's top corners, the soffit round the curve,
    and a ring of voussoirs standing proud with a stone key."""
    m = F.m
    mid, half = (a + b) / 2, (b - a) / 2
    R = (half * half + rise * rise) / (2 * rise)
    zc = e - R
    th = math.asin(half / R)
    at = lambda t, r: (mid + r * math.sin(t), zc + r * math.cos(t))  # noqa: E731
    n = 10
    arc = [at(-th + 2 * th * i / n, R) for i in range(n + 1)]
    for (u0, z0), (u1, z1) in zip(arc, arc[1:]):
        fpoly(F, "brick", [(u0, z0), (u1, z1), (u1, e), (u0, e)])
        um, zm = (u0 + u1) / 2, (z0 + z1) / 2
        m.poly("brick", [F.p(u0, z0, 0), F.p(u1, z1, 0), F.p(u1, z1, -D), F.p(u0, z0, -D)], out=F.t * (mid - um) + Z * (zc - zm))
    L = 2 * th * (R + ring / 2)
    nv = int(L / 0.13) | 1
    step = 2 * th / nv
    for j in range(nv):
        t0, t1 = -th + j * step, -th + (j + 1) * step
        key = j == nv // 2
        role, ro, w = ("stone", R + ring + 0.1, 0.05) if key else ("rubbed", R + ring, 0.02)
        if key:
            t0, t1 = t0 - step * 0.6, t1 + step * 0.6
        g = 0.0 if key else 0.006 / R  # the joint
        ta, tb = t0 + g, t1 - g
        pts = [at(ta, R), at(tb, R), at(tb, ro), at(ta, ro)]
        fpoly(F, role, pts, w)
        tm = (ta + tb) / 2
        outs = (  # extrados, the side at ta, the side at tb, intrados
            (pts[2], pts[3], (math.sin(tm), math.cos(tm))),
            (pts[3], pts[0], (-math.cos(ta), math.sin(ta))),
            (pts[1], pts[2], (math.cos(tb), -math.sin(tb))),
            (pts[0], pts[1], (-math.sin(tm), -math.cos(tm))),
        )
        for (u0, z0), (u1, z1), (ou, oz) in outs:
            m.poly(role, [F.p(u0, z0, 0), F.p(u1, z1, 0), F.p(u1, z1, w), F.p(u0, z0, w)], out=F.t * ou + Z * oz)


def steel(M, F, a, b, c, e, hopper=None, D=WALL, glass="worksglass"):
    """A steel window of small panes in the opening (a..b, c..e): a slim frame,
    glazing bars on a grid of ~0.42 x 0.45 m lights, one pane behind them all
    (one room); `hopper` (columns i0, i1 and row j) tilts that strip of
    lights in at the top, open."""
    m, fr = F.m, "steelframe"
    wid = new_id()
    wg = -D + 0.12
    fw = 0.05
    F.box(fr, a, a + fw, c, e, wg - 0.04, wg + 0.04)
    F.box(fr, b - fw, b, c, e, wg - 0.04, wg + 0.04)
    F.box(fr, a + fw, b - fw, e - fw, e, wg - 0.04, wg + 0.04)
    F.box(fr, a + fw, b - fw, c, c + fw, wg - 0.04, wg + 0.05)
    ia, ib, ic, ie = a + fw, b - fw, c + fw, e - fw
    nx = max(2, round((ib - ia) / 0.42))
    ny = max(3, round((ie - ic) / 0.45))
    us = [ia + i * (ib - ia) / nx for i in range(nx + 1)]
    zs = [ic + j * (ie - ic) / ny for j in range(ny + 1)]
    if hopper:
        i0, i1, j = hopper
        hu0, hu1, hz0, hz1 = us[i0], us[i1], zs[j], zs[j + 1]
        pane(F, glass, a, b, c, e, ia, ib, ic, hz0, wg, wid)
        pane(F, glass, a, b, c, e, ia, ib, hz1, ie, wg, wid)
        if hu0 > ia + 1e-6:
            pane(F, glass, a, b, c, e, ia, hu0, hz0, hz1, wg, wid)
        if hu1 < ib - 1e-6:
            pane(F, glass, a, b, c, e, hu1, ib, hz0, hz1, wg, wid)
        # The hopper, hinged at its foot and tilted in, with a dark gap above it.
        tilt = math.radians(24)
        h = hz1 - hz0
        tz, tw = hz0 + h * math.cos(tilt), wg - h * math.sin(tilt)
        uv = lambda u, z: (wid + (u - a) / (b - a), (z - c) / (e - c))  # noqa: E731
        m.poly(glass, [F.p(hu0, hz0, wg), F.p(hu1, hz0, wg), F.p(hu1, tz, tw), F.p(hu0, tz, tw)],
               out=F.n * math.cos(tilt) + Z * math.sin(tilt), uvs=[uv(hu0, hz0), uv(hu1, hz0), uv(hu1, hz1), uv(hu0, hz1)])
        for u in (hu0 + 0.02, hu1 - 0.02):
            m.strut(fr, F.p(u, hz0, wg + 0.01), F.p(u, tz, tw + 0.01), 0.035, 0.035)
        m.strut(fr, F.p(hu0, tz, tw + 0.01), F.p(hu1, tz, tw + 0.01), 0.035, 0.035)
        for i in range(i0 + 1, i1):
            m.strut(fr, F.p(us[i], hz0, wg + 0.01), F.p(us[i], tz, tw + 0.01), 0.025, 0.025)
        F.quad("dark", hu0, hu1, hz0, hz1, tw - 0.08)
    else:
        pane(F, glass, a, b, c, e, ia, ib, ic, ie, wg, wid)
    for i in range(1, nx):
        runs = [(ic, ie)]
        if hopper and hopper[0] < i < hopper[1]:
            runs = [(ic, zs[hopper[2]]), (zs[hopper[2] + 1], ie)]
        for z0, z1 in runs:
            F.box(fr, us[i] - 0.014, us[i] + 0.014, z0, z1, wg - 0.005, wg + 0.03)
    for j in range(1, ny):
        F.box(fr, ia, ib, zs[j] - 0.014, zs[j] + 0.014, wg - 0.005, wg + 0.03)


def window(M, F, a, b, c=1.25, e=3.75, rise=0.28):
    """A steel window under a segmental arch, on a stone sill; some have a hopper open."""
    w = b - a
    nx = max(2, round((w - 0.1) / 0.42))
    hop = None
    if M.R.random() < 0.55:
        k = 2 if nx >= 4 else 1
        i0 = M.R.randrange(0, nx - k + 1)
        hop = (i0, i0 + k, M.R.choice((1, 2)))
    steel(M, F, a, b, c, e, hop)
    arch(F, a, b, e, rise)
    sill(F, a, b, c, D=WALL)


def ledged(F, a, b, c, e, D=0.24, leaves=2):
    """Timber doors, framed, ledged and braced, on iron strap hinges."""
    dr = "doors"
    F.quad(dr, a, b, c, e, -D)
    lw = (b - a) / leaves
    for i in range(leaves):
        u0, u1 = a + i * lw, a + (i + 1) * lw
        for x0, x1 in ((u0, u0 + 0.12), (u1 - 0.12, u1)):
            F.box(dr, x0, x1, c, e, -D, -D + 0.05)
        for z in (c + 0.12, (c + e) / 2, e - 0.12):
            F.box(dr, u0 + 0.12, u1 - 0.12, z - 0.09, z + 0.09, -D, -D + 0.045)
        # Braces rising toward the hinge side, between the rails.
        hinge_left = i == 0
        for zb, zt in ((c + 0.21, (c + e) / 2 - 0.09), ((c + e) / 2 + 0.09, e - 0.21)):
            lo, hi = (u1 - 0.18, u0 + 0.18) if hinge_left else (u0 + 0.18, u1 - 0.18)
            F.m.strut(dr, F.p(lo, zb + 0.05, -D + 0.02), F.p(hi, zt - 0.05, -D + 0.02), 0.04, 0.12)
        hx = u0 if hinge_left else u1
        sgn = 1 if hinge_left else -1
        for z in (c + 0.35, e - 0.35):
            F.box("iron", min(hx, hx + sgn * 0.7), max(hx, hx + sgn * 0.7), z - 0.035, z + 0.035, -D + 0.05, -D + 0.065)
    F.box("iron", (a + b) / 2 - 0.02, (a + b) / 2 + 0.02, c + 1.0, c + 1.4, -D + 0.05, -D + 0.1)


def rsj(F, a, b, z, D=WALL):
    """A painted steel beam over a wide opening, its flange showing, with rivet plates at the bearings."""
    F.box("steelframe", a - 0.25, b + 0.25, z, z + 0.3, -0.05, 0.02)
    F.box("steelframe", a - 0.25, b + 0.25, z - 0.02, z + 0.02, -D + 0.05, 0.03)
    for u in (a - 0.2, b + 0.05):
        F.box("steelframe", u, u + 0.15, z + 0.03, z + 0.27, 0.02, 0.03)


def lamp(F, u, z):
    """A bulkhead lamp on a swan-neck bracket."""
    F.box("iron", u - 0.03, u + 0.03, z - 0.25, z + 0.05, 0, 0.05)
    F.m.strut("iron", F.p(u, z, 0.03), F.p(u, z + 0.12, 0.42), 0.035)
    F.box("iron", u - 0.2, u + 0.2, z + 0.1, z + 0.16, 0.22, 0.62, skip=())
    F.box("lamp", u - 0.11, u + 0.11, z - 0.06, z + 0.1, 0.31, 0.53, skip=())


def plinth(F, u0, u1, gaps=()):
    """The blue-brick plinth along a wall, stopping at doorways: a course proud with a chamfered top."""
    edges = [u0]
    for a, b in sorted(gaps):
        edges += [a, b]
    edges.append(u1)
    for a, b in zip(edges[::2], edges[1::2]):
        if b - a < 1e-3:
            continue
        F.box("bluebrick", a, b, 0, PL - 0.06, 0, 0.06, skip=("back", "bottom", "top"))
        F.m.poly("bluebrick", [F.p(a, PL - 0.06, 0.06), F.p(b, PL - 0.06, 0.06), F.p(b, PL, 0), F.p(a, PL, 0)], out=F.n + Z)


def pilasters(F, spans):
    for u0, u1 in spans:
        F.box("bluebrick", u0 - 0.03, u1 + 0.03, 0, PL, 0, 0.15, skip=("back", "bottom"))
        F.box("brick", u0, u1, PL, SC - 0.1, 0, 0.12, skip=("back",))
        F.box("stone", u0 - 0.03, u1 + 0.03, SC - 0.1, SC, 0, 0.16, skip=("back",))


def downpipe(m, x, y, n, top, head=True):
    """A cast-iron downpipe at (x, y) off a wall facing n (+-1 in y), from `top` to a shoe at the foot."""
    y0, y1 = (y, y + 0.12) if n > 0 else (y - 0.12, y)
    m.box("iron", (x - 0.05, y0 + 0.01 * n, 0.15), (x + 0.05, y1, top))
    m.box("iron", (x - 0.06, y0, 0.0), (x + 0.06, y1 + 0.1 * n, 0.16))
    if head:
        m.box("iron", (x - 0.16, y0, top - 0.05), (x + 0.16, y1 + 0.12 * n, top + 0.3))
    for z in (1.2, 2.8, top - 0.6):
        m.box("iron", (x - 0.07, y0, z), (x + 0.07, y0 + 0.04 * n, z + 0.05))


# ---- body -----------------------------------------------------------------------------


def body(M):
    m = M.m
    walls = sides(m, WS, DS, SX, SY)
    # Front: the window of the left bay, the loading door of the middle one, the office.
    F = walls["front"]
    LD = (-1.4, 1.4, 1.1, 3.6)
    OD = (2.3, 3.4, 0.3, 3.0)
    holes = [(-4.65, -2.55, 1.25, 3.75), (*LD, 0.24), (*OD, 0.3), (3.75, 4.85, 1.25, 3.75)]
    F.wall("brick", -WS / 2, WS / 2, 0, HV, holes, depth=WALL)
    window(M, F, -4.65, -2.55)
    window(M, F, 3.75, 4.85, rise=0.2)
    ledged(F, *LD)
    rsj(F, LD[0], LD[1], LD[3])
    office(F, *OD)
    plinth(F, -WS / 2, WS / 2, [(OD[0], OD[1])])
    pilasters(F, [(-5.52, -5.02), (-2.05, -1.55), (1.55, 2.05), (5.02, 5.52)])
    dock(M, F)
    # The frieze carries the firm's name, painted on the brick (u, v over the sign; the app picks it).
    F.quad("works", -5.0, 5.0, SC + 0.18, HV - 0.5, 0.004, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)

    # Left side: three bays of windows.
    S = walls["left"]
    holes = [(u - 0.95, u + 0.95, 1.25, 3.75) for u in (3.0, 0.0, -3.0)]
    S.wall("brick", -DS / 2, DS / 2, 0, HV, holes, depth=WALL)
    for a, b, c, e in holes:
        window(M, S, a, b)
    plinth(S, -DS / 2, DS / 2)
    pilasters(S, [(4.0, 4.5), (1.25, 1.75), (-1.75, -1.25), (-4.5, -4.0)])
    for y in (YF + 0.75, YB - 0.6):
        m.box("iron", (X0 - 0.3, y - 0.05, 0.15), (X0 - 0.2, y + 0.05, HV - 0.25))
        m.box("iron", (X0 - 0.4, y - 0.06, 0.0), (X0 - 0.2, y + 0.06, 0.16))
        m.box("iron", (X0 - 0.31, y - 0.06, HV - 0.45), (X0, y + 0.06, HV - 0.4))

    # Right side: two windows; the boiler house against the back half.
    S = walls["right"]
    holes = [(u - 0.95, u + 0.95, 1.25, 3.75) for u in (-3.0, 0.0)]
    S.wall("brick", -DS / 2, DS / 2, 0, HV, holes, depth=WALL)
    for a, b, c, e in holes:
        window(M, S, a, b)
    plinth(S, -DS / 2, YH - SY)
    pilasters(S, [(-4.5, -4.0), (-1.75, -1.25)])

    # Back: windows either side of the yard doors, downpipes from the valleys.
    S = walls["back"]
    YDR = (-1.3, 1.3, 0.0, 3.3)
    holes = [(2.55, 4.65, 1.25, 3.75), (*YDR, 0.24), (-4.65, -2.55, 1.25, 3.75)]
    S.wall("brick", -WS / 2, WS / 2, 0, HV, holes, depth=WALL)
    window(M, S, 2.55, 4.65)
    window(M, S, -4.65, -2.55)
    ledged(S, *YDR)
    rsj(S, YDR[0], YDR[1], YDR[3])
    S.box("concrete", YDR[0] - 0.2, YDR[1] + 0.2, -0.02, 0.04, 0, 0.6, skip=("back", "bottom"))
    plinth(S, -WS / 2, WS / 2, [(YDR[0], YDR[1])])
    pilasters(S, [(5.02, 5.52), (1.55, 2.05), (-2.05, -1.55)])
    lamp(S, 0.0, 3.72)
    for k in range(1, N):
        downpipe(m, X0 + k * TW + 0.16, YB + 0.17, 1, HV - 0.45)

    # String course and the corbelled eaves band, all round the shed.
    m.sweep("stone", WS, DS, [(0.0, SC), (0.07, SC), (0.07, SC + 0.12), (0.0, SC + 0.15)], SX, SY)
    m.sweep("brick", WS, DS, [(0.0, HV - 0.32), (0.06, HV - 0.32), (0.06, HV - 0.17), (0.11, HV - 0.17), (0.11, HV), (0.0, HV)], SX, SY)
    F = walls["front"]
    for i in range(int(WS / 0.28)):
        u = -WS / 2 + 0.14 + i * 0.28
        F.box("brick", u - 0.06, u + 0.06, HV - 0.44, HV - 0.32, 0, 0.06)
    # A ceiling at the eaves, seen when the roof is gone.
    m.poly("dark", [(X0, YF, HV - 0.02), (X1, YF, HV - 0.02), (X1, YB, HV - 0.02), (X0, YB, HV - 0.02)], out=Z)
    boiler(M)
    stack_base(M)


def office(F, a, b, c, e):
    """The office door up two steps: a four-panel door, a fanlight, a stone hood with the word in brass."""
    m = F.m
    D_ = 0.3
    F.box("stone", a - 0.15, b + 0.15, 0, 0.15, 0, 0.62, skip=("back", "bottom"))
    F.box("stone", a - 0.1, b + 0.1, 0.15, c, 0, 0.32, skip=("back", "bottom"))
    t = c + 2.15
    wid = new_id()
    dr = "door"
    F.box(dr, a, a + 0.07, c, e, -D_, -D_ + 0.1)
    F.box(dr, b - 0.07, b, c, e, -D_, -D_ + 0.1)
    F.box(dr, a + 0.07, b - 0.07, t, t + 0.08, -D_, -D_ + 0.1)
    F.box(dr, a + 0.07, b - 0.07, e - 0.06, e, -D_, -D_ + 0.1)
    pane(F, "doorglass", a, b, c, e, a + 0.07, b - 0.07, t + 0.08, e - 0.06, -D_ + 0.04, wid)
    da, db = a + 0.07, b - 0.07
    F.quad(dr, da, db, c, t, -D_ + 0.03)
    mid = (da + db) / 2
    for z0, z1 in ((c + 0.12, c + 0.95), (c + 1.1, t - 0.12)):
        for u0, u1 in ((da + 0.1, mid - 0.05), (mid + 0.05, db - 0.1)):
            F.box(dr, u0, u1, z0, z1, -D_ + 0.03, -D_ + 0.055)
    F.box("brass", db - 0.13, db - 0.08, c + 1.0, c + 1.07, -D_ + 0.03, -D_ + 0.09)
    # Architraves, the hood, and OFFICE on its frieze.
    for u0, u1 in ((a - 0.16, a), (b, b + 0.16)):
        F.box("stone", u0, u1, c, e, 0, 0.04)
    hood(F, a, b, e)
    letters(m, "brass", F, (a + b) / 2, e + 0.15, 0.04, "OFFICE", 0.13, depth=0.012, spacing=1.15)


def dock(M, F):
    """The loading dock before the middle bay: concrete with a steel nosing and
    buffers, steps at the left end with a pipe rail, a canopy above on brackets."""
    m = F.m
    u0, u1, h = -1.75, 1.95, 1.1
    F.box("concrete", u0, u1, 0, h, 0, DOCK, skip=("back", "bottom"))
    F.box("iron", u0, u1, h - 0.08, h + 0.005, DOCK - 0.005, DOCK + 0.01, skip=("back",))
    F.box("iron", u0, u1, h, h + 0.005, DOCK - 0.08, DOCK + 0.01, skip=("back", "bottom"))
    for u in (u0 + 0.5, u1 - 0.5):
        F.box("rubber", u - 0.13, u + 0.13, 0.4, 0.95, DOCK, DOCK + 0.13, skip=("back",))
    for k, top in enumerate((h * 2 / 3, h / 3)):
        F.box("concrete", u0 - 0.32 * (k + 1), u0 - 0.32 * k, 0, top, 0.02, 1.05, skip=("back", "bottom"))
    # The rail on the steps' open side.
    w = 1.0
    pts = [F.p(u0 + 0.6, h + 0.95, w), F.p(u0 - 0.05, h + 0.95, w), F.p(u0 - 0.64, h / 3 + 0.95, w)]
    m.tube("iron", pts, 0.025, F.n, closed=False, seg=6)
    for (u, z) in ((u0 + 0.6, h), (u0 - 0.05, h), (u0 - 0.64, h / 3)):
        m.strut("iron", F.p(u, z, w), F.p(u, z + 0.95, w), 0.04)
    # Canopy: corrugated sheet on a steel frame, brackets from the pilasters.
    cz, cd = 3.92, 1.95
    F.box("corrugated", -2.1, 2.3, cz, cz + 0.06, 0, cd, skip=("back",))
    F.box("steelframe", -2.1, 2.3, cz - 0.16, cz, cd - 0.08, cd)
    for u in (-1.8, 1.8):
        F.box("steelframe", u - 0.04, u + 0.04, cz - 0.16, cz, 0.12, cd - 0.08)
        m.strut("steelframe", F.p(u, cz - 1.05, 0.12), F.p(u, cz - 0.14, cd - 0.3), 0.06, 0.06)
    F.box("steelframe", -2.1, 2.3, cz - 0.12, cz, 0.0, 0.1)
    F.box("iron", -0.03, 0.03, cz - 0.22, cz - 0.12, 1.12, 1.18)
    F.box("lamp", -0.16, 0.16, cz - 0.34, cz - 0.22, 1.0, 1.3, skip=())


def boiler(M):
    """The lean-to boiler house against the right wall, toward the back."""
    m = M.m
    bw, bd = BX - X1, YB - YH
    bx, by = (X1 + BX) / 2, (YB + YH) / 2
    walls = sides(m, bw, bd, bx, by)
    F = walls["front"]
    holes = [(-0.95, -0.15, 1.4, 2.5)]
    F.wall("brick", -bw / 2, bw / 2, 0, BH, holes, depth=WALL)
    fpoly(F, "brick", [(-bw / 2, BH), (bw / 2, BH), (-bw / 2, BT)])
    window(M, F, -0.95, -0.15, 1.4, 2.5, rise=0.15)
    plinth(F, -bw / 2, bw / 2)
    S = walls["right"]
    holes = [(-1.2, -0.4, 0.45, 1.15, 0.12), (0.45, 1.25, 1.4, 2.5)]
    S.wall("brick", -bd / 2, bd / 2, 0, BH, holes, depth=WALL)
    S.quad("steelframe", -1.2, -0.4, 0.45, 1.15, -0.1)
    for z in (0.65, 0.95):
        S.box("steelframe", -1.17, -0.43, z - 0.02, z + 0.02, -0.1, -0.08)
    S.box("stone", -1.3, -0.3, 0.33, 0.45, 0, 0.1, skip=("back",))
    window(M, S, 0.45, 1.25, 1.4, 2.5, rise=0.15)
    plinth(S, -bd / 2, bd / 2)
    S = walls["back"]
    holes = [(-0.6, 0.4, 0.0, 2.2, 0.12)]
    S.wall("brick", -bw / 2, bw / 2, 0, BH, holes, depth=WALL)
    fpoly(S, "brick", [(-bw / 2, BH), (bw / 2, BH), (bw / 2, BT)])
    S.quad("steelframe", -0.6, 0.4, 0.0, 2.2, -0.1)
    for z in (0.5, 1.1, 1.7):
        S.box("steelframe", -0.57, 0.37, z - 0.03, z + 0.03, -0.1, -0.075)
    S.box("iron", 0.25, 0.3, 1.0, 1.15, -0.1, -0.03)
    arch(S, -0.6, 0.4, 2.2, rise=0.12)
    plinth(S, -bw / 2, bw / 2, [(-0.6, 0.4)])
    # The lean-to roof in corrugated sheet, its gutter and a downpipe.
    s = (BT - BH) / bw
    xa, xb = X1, BX + 0.22
    za, zb = BT + 0.06, BH + 0.06 - 0.22 * s
    ya, yb = YH - 0.15, YB + 0.15
    m.poly("corrugated", [(xa, ya, za), (xb, ya, zb), (xb, yb, zb), (xa, yb, za)], out=(s, 0, 1),
           uvs=[(ya, (xb - xa) * math.hypot(1, s)), (ya, 0), (yb, 0), (yb, (xb - xa) * math.hypot(1, s))])
    m.poly("corrugated", [(xa, ya, za - 0.03), (xb, ya, zb - 0.03), (xb, yb, zb - 0.03), (xa, yb, za - 0.03)], out=(-s, 0, -1))
    for y in (ya, yb):
        m.poly("corrugated", [(xa, y, za - 0.03), (xb, y, zb - 0.03), (xb, y, zb), (xa, y, za)], out=(0, y - by, 0))
    m.poly("corrugated", [(xb, ya, zb - 0.03), (xb, yb, zb - 0.03), (xb, yb, zb), (xb, ya, zb)], out=(1, 0, 0))
    m.box("galv", (X1, ya, za - 0.05), (X1 + 0.12, yb, za + 0.22))
    m.box("iron", (xb - 0.02, ya, zb - 0.18), (xb + 0.14, yb, zb - 0.04))
    m.box("iron", (xb + 0.02, yb - 0.25, 0.15), (xb + 0.12, yb - 0.15, zb - 0.1))
    m.box("iron", (xb + 0.0, yb - 0.26, 0.0), (xb + 0.22, yb - 0.14, 0.16))
    m.poly("dark", [(X1, YH, BH - 0.02), (BX, YH, BH - 0.02), (BX, YB, BH - 0.02), (X1, YB, BH - 0.02)], out=Z)


def stack_base(M):
    """The chimney's square base, its cleaning door, and the brick flue from the boiler house."""
    m = M.m
    h = 0.9
    m.box("bluebrick", (CX - h - 0.05, CY - h - 0.05, 0), (CX + h + 0.05, CY + h + 0.05, PL), skip=("z0",))
    m.box("brick", (CX - h, CY - h, PL), (CX + h, CY + h, CB - 0.25), skip=("z0", "z1"))
    m.sweep("stone", 2 * h, 2 * h, [(0.0, CB - 0.25), (0.08, CB - 0.25), (0.08, CB - 0.12), (-0.1, CB), (-0.75, CB)], CX, CY)
    F = sides(m, 2 * h, 2 * h, CX, CY)["front"]
    F.box("steelframe", -0.32, 0.32, PL + 0.1, PL + 1.0, 0, 0.04)
    for z in (PL + 0.35, PL + 0.75):
        F.box("iron", -0.36, -0.2, z - 0.03, z + 0.03, 0.04, 0.06)
    arch(F, -0.42, 0.42, PL + 1.25, rise=0.15, ring=0.23)
    fl = (CX - 0.45, CX + 0.45)
    m.box("brick", (fl[0], CY + h, 0), (fl[1], YH, 1.25), skip=("z0", "y0", "y1"))
    m.box("stone", (fl[0] - 0.05, CY + h, 1.25), (fl[1] + 0.05, YH, 1.37), skip=("z0", "y0", "y1"))


# ---- roof -----------------------------------------------------------------------------


def slope(x, x0):
    return HV + (x - x0) * RISE / TW


def roof(M):
    m = M.m
    y0, y1 = YF + WALL - 0.01, YB - WALL + 0.01
    for k in range(N):
        x0, x1 = X0 + k * TW, X0 + (k + 1) * TW
        # The slope, from the eaves or the valley gutter up to the ridge.
        xa = x0 - 0.22 if k == 0 else x0 + 0.3
        za, L = slope(xa, x0), math.hypot(x1 - xa, HR - slope(xa, x0))
        m.poly("corrugated", [(xa, y0, za), (x1, y0, HR), (x1, y1, HR), (xa, y1, za)], out=(-RISE, 0, TW),
               uvs=[(y0, 0), (y0, L), (y1, L), (y1, 0)])
        if k == 0:
            m.poly("corrugated", [(xa, y0, za - 0.04), (x1, y0, HR - 0.04), (x1, y1, HR - 0.04), (xa, y1, za - 0.04)], out=(RISE, 0, -TW))
            m.poly("corrugated", [(xa, y0, za - 0.04), (xa, y1, za - 0.04), (xa, y1, za), (xa, y0, za)], out=(-1, 0, 0))
            # The eaves gutter, an ogee in cast iron.
            m.box("iron", (X0 - 0.38, YF - 0.12, HV - 0.33), (X0 - 0.2, YB + 0.12, HV - 0.17))
            m.box("iron", (X0 - 0.4, YF - 0.12, HV - 0.19), (X0 - 0.36, YB + 0.12, HV - 0.14))
        else:
            # The valley gutter in front of the last bay's glazing.
            m.box("galv", (x0 - 0.02, y0, HV - 0.06), (x0 + 0.32, y1, HV + 0.12), skip=("z0",))
            m.box("dark", (x0 + 0.03, y0, HV + 0.12), (x0 + 0.27, y1, HV + 0.125), skip=("z0",))
        # The north light: an upstand, the glass, patent glazing bars, the ridge capping.
        m.box("galv", (x1 - 0.1, y0, HV), (x1 + 0.03, y1, HV + 0.26), skip=("z0",))
        m.poly("northlight", [(x1, y0, HV + 0.26), (x1, y1, HV + 0.26), (x1, y1, HR - 0.05), (x1, y0, HR - 0.05)], out=(1, 0, 0))
        nb = int((y1 - y0) / 0.62)
        for i in range(nb + 1):
            y = y0 + 0.03 + i * (y1 - y0 - 0.06) / nb
            m.box("galv", (x1, y - 0.025, HV + 0.24), (x1 + 0.06, y + 0.025, HR - 0.02), skip=("x0",))
        m.box("galv", (x1, y0, (HV + HR) / 2 + 0.1), (x1 + 0.045, y1, (HV + HR) / 2 + 0.14), skip=("x0",))
        m.box("galv", (x1 - 0.18, y0 - 0.02, HR - 0.07), (x1 + 0.09, y1 + 0.02, HR + 0.05), skip=("z0",))
        # The gables, front and back: coped, with a stone block at the apex.
        for y, o in ((YF, -1), (YB, 1)):
            yi = y - o * WALL
            for yy, oo in ((y, o), (yi, -o)):
                m.poly("brick", [(x0, yy, HV), (x1, yy, HV), (x1, yy, HR + PAR), (x0, yy, HV + PAR)], out=(0, oo, 0))
            m.poly("brick", [(x1, y, HV), (x1, yi, HV), (x1, yi, HR + PAR), (x1, y, HR + PAR)], out=(1, 0, 0))
            if k == 0:
                m.poly("brick", [(x0, y, HV), (x0, yi, HV), (x0, yi, HV + PAR), (x0, y, HV + PAR)], out=(-1, 0, 0))
            yc = y - o * WALL / 2
            m.strut("stone", (x0 - 0.06, yc, HV + PAR + 0.05), (x1 + 0.03, yc, HR + PAR + 0.05), 0.46, 0.1)
            m.box("stone", (x1 - 0.32, yc - 0.25, HR + PAR - 0.12), (x1 + 0.04, yc + 0.25, HR + PAR + 0.22))
            m.box("stone", (x1 - 0.36, yc - 0.27, HR + PAR + 0.22), (x1 + 0.06, yc + 0.27, HR + PAR + 0.28))
            if k == 0:
                m.box("stone", (x0 - 0.12, yc - 0.25, HV - 0.02), (x0 + 0.3, yc + 0.25, HV + PAR + 0.12))
        # A ventilator on the outer bays' slopes.
        if k != 1:
            x = x0 + 0.62 * TW
            z = slope(x, x0)
            for y in ((YF + YB) / 2 - 1.6, (YF + YB) / 2 + 1.9)[: 1 + (k == 0)]:
                m.cyl("galv", x, y, 0.15, z - 0.1, z + 0.5, seg=12, top=False)
                m.cyl("galv", x, y, 0.36, z + 0.5, z + 0.62, seg=14, top=False, bottom=True)
                m.cyl("galv", x, y, 0.36, z + 0.62, z + 0.95, seg=14, r1=0.06)
    gable_dress(M)
    shaft(M)


def gable_dress(M):
    """The works clock in the middle gable, round vents in the outer ones."""
    m = M.m
    F = sides(m, WS, DS, SX, SY)["front"]
    for k in range(N):
        x0 = X0 + k * TW
        u = x0 + 2.45 - SX
        z = HV + 1.0
        if k == 1:
            r = 0.46
            annulus(F, "stone", u, z, r, r + 0.13, 0.07, seg=24)
            disc(F, "cream", u, z, r, 0.05, seg=24)
            for i in range(12):
                a = i / 12 * math.tau
                q = 0.035 if i % 3 else 0.05
                cu, cz = u + math.sin(a) * (r - 0.07), z + math.cos(a) * (r - 0.07)
                m.strut("iron", F.p(cu - math.sin(a) * q, cz - math.cos(a) * q, 0.055), F.p(cu + math.sin(a) * q, cz + math.cos(a) * q, 0.055), 0.008, 0.025)
            for ang, ln, wd in ((-50, 0.24, 0.035), (60, 0.36, 0.025)):  # ten past ten
                a = math.radians(ang)
                m.strut("iron", F.p(u - math.sin(a) * 0.06, z - math.cos(a) * 0.06, 0.06), F.p(u + math.sin(a) * ln, z + math.cos(a) * ln, 0.06), 0.012, wd)
            disc(F, "iron", u, z, 0.035, 0.072, seg=8)
        else:
            r = 0.34
            annulus(F, "stone", u, z, r, r + 0.12, 0.06, seg=20)
            disc(F, "dark", u, z, r, -0.06, seg=20)
            for i in range(-2, 3):
                zz = z + i * 0.12
                hw = math.sqrt(max(r * r - (i * 0.12) ** 2, 0.0))
                m.strut("iron", F.p(u - hw, zz, -0.02), F.p(u + hw, zz, -0.02), 0.07, 0.025)


def shaft(M):
    """The stack's round shaft in brick, tapering, iron bands, ladder staples, a conductor and the corbelled cap."""
    m = M.m
    r = lambda z: CR0 + (CR1 - CR0) * (z - CB) / (CT - 0.9 - CB)  # noqa: E731
    bands = [5.4, 7.9, 10.4, 12.9, 15.0]
    zs = [CB, *bands, CT - 0.9]
    for za, zb in zip(zs, zs[1:]):
        m.cyl("brick", CX, CY, r(za), za, zb, seg=20, top=False, uv=True, r1=r(zb))
    for z in bands:
        m.cyl("iron", CX, CY, r(z) + 0.025, z - 0.04, z + 0.04, seg=20, top=False)
    # Corbelled cap: courses stepping out, a cast-iron cope, the dark flue inside.
    z, rr = CT - 0.9, r(CT - 0.9)
    for dz, dr in ((0.15, 0.04), (0.15, 0.09), (0.45, 0.14), (0.15, 0.1)):
        m.cyl("brick", CX, CY, rr + dr, z, z + dz, seg=20, top=False, bottom=True, uv=True)
        z += dz
    ro = rr + 0.16
    m.cyl("iron", CX, CY, ro, z, z + 0.08, seg=20, top=False, bottom=True)
    z += 0.08
    for i in range(20):
        a0, a1 = i / 20 * math.tau, (i + 1) / 20 * math.tau
        p = lambda a, q: (CX + math.cos(a) * q, CY + math.sin(a) * q, z)  # noqa: E731
        m.poly("iron", [p(a0, rr - 0.12), p(a1, rr - 0.12), p(a1, ro), p(a0, ro)], out=Z)
    m.poly("dark", [(CX + math.cos(i / 16 * math.tau) * (rr - 0.12), CY + math.sin(i / 16 * math.tau) * (rr - 0.12), z - 0.25) for i in range(16)], out=Z)
    # Ladder staples up the street side, angled toward the corner.
    ang = math.radians(-60)
    d = Vector((math.cos(ang), math.sin(ang), 0))
    s = d.cross(Z)
    zz = CB + 0.4
    while zz < CT - 1.2:
        p0 = Vector((CX, CY, zz)) + d * (r(zz) + 0.16)
        m.strut("iron", p0 - s * 0.2, p0 + s * 0.2, 0.025)
        for k in (-0.19, 0.19):
            m.strut("iron", Vector((CX, CY, zz)) + d * (r(zz) - 0.02) + s * k, p0 + s * k, 0.022)
        zz += 0.36
    # The lightning conductor, a copper tape down the far side, and its rod.
    b = Vector((math.cos(ang + 2.4), math.sin(ang + 2.4), 0))
    m.strut("copper", Vector((CX, CY, CB)) + b * (CR0 + 0.01), Vector((CX, CY, CT - 0.9)) + b * (rr + 0.01), 0.006, 0.03)
    m.strut("copper", Vector((CX, CY, CT - 0.9)) + b * (rr + 0.17), Vector((CX, CY, CT + 1.1)) + b * (rr + 0.05), 0.025)
