# A7, canal houses: three narrow merchants' houses of the 17th and 18th
# centuries, wall to wall, as they line the canals of Amsterdam and Leiden.
# Each is one deep room wide, with big many-paned sashes, and ends in its
# own gable: a stepped gable on the left house, a neck gable with carved
# claw pieces on the plastered middle one, a bell gable on the right. A
# hoist beam juts from the top of every gable, over a loft door. The ground
# floor is raised over a half-sunk basement: a stoop of stone steps with an
# iron rail climbs to each front door, under a fanlight; the basement
# windows are barred. Iron wall anchors pin the floors to the fronts.
# Behind the gables, steep tiled roofs run back to plain brick back gables,
# with chimneys on the party walls. The app tints the bricks, the plaster,
# the shutters, the doors and the roof tiles.
#
# Pieces (base at the origin, stacked by the app):
#   ground   4.5 m: basement and raised ground floor, stoops and doors
#   floor    3.2 m: an upper storey
#   roof     the gables, roofs and chimneys
import math

from lib import Model, Side, Z, fpoly, letters, lintel, new_id, pane, sash, sill

ID = "a7"
HW = (5.0, 4.4, 5.6)  # the three houses' widths
W, D = sum(HW), 11.0
X0, X1 = -W / 2, W / 2
STOOP = 1.5  # the stoops' reach in front of the wall
Y0 = (STOOP - D) / 2  # front wall; the footprint (stoops to back wall) is centred
Y1 = Y0 + D
GL = 1.2  # the raised ground floor
G = 4.5  # top of the ground piece
FL = 3.2
RIDGE = 4.2  # the roofs' rise from the eaves to the ridge
T = 0.3  # gable thickness
WALL = ("brick", "render", "brick2")  # each house's front
DOOR = ("door", "door2", "door3")
SHUTTERS = (True, False, True)


def houses():
    """(index, centre x, half width) for each house, left to right seen from the street."""
    out, x = [], X0
    for i, w in enumerate(HW):
        out.append((i, x + w / 2, w / 2))
        x += w
    return out


def front(m, cx):
    return Side(m, (cx, Y0, 0), (1, 0, 0), (0, -1, 0))


def back(m, cx):
    return Side(m, (cx, Y1, 0), (-1, 0, 0), (0, 1, 0))


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    storey(M, G)
    M.piece("roof", (0, 0, G + FL))
    roof(M, G + FL)
    M.export(out, bake)


# ---- bays ---------------------------------------------------------------------------


def bays(i, h):
    """The window axes of house i (half width h): two on the narrow house, three on the others."""
    if HW[i] < 4.8:
        return [-h * 0.48, h * 0.48]
    return [-h * 0.62, 0.0, h * 0.62]


def door_axis(i, h):
    """The door takes the bay on the side away from the neighbour's door, so stoops pair up."""
    b = bays(i, h)
    return b[0] if i % 2 == 0 else b[-1]


def anchors(F, u, z):
    """A wrought-iron wall anchor where a floor beam is tied to the front: an S on its end."""
    F.box("iron", u - 0.03, u + 0.03, z - 0.34, z + 0.34, 0, 0.035)
    F.box("iron", u - 0.13, u - 0.03, z + 0.28, z + 0.34, 0, 0.035)
    F.box("iron", u + 0.03, u + 0.13, z - 0.34, z - 0.28, 0, 0.035)


def shutters(F, a, b, c, e):
    """A pair of panelled shutters folded back beside a window, in the house colours."""
    wd = (b - a) / 2
    for u0, u1 in ((a - wd - 0.02, a - 0.02), (b + 0.02, b + wd + 0.02)):
        F.box("shutter", u0, u1, c, e, 0, 0.05)
        F.box("trim", u0, u1, (c + e) / 2 - 0.04, (c + e) / 2 + 0.04, 0.05, 0.065)


def window(F, a, b, c, e, lights=(3, 2)):
    sash(F, a, b, c, e, D=0.2, lights=lights, fr="trim")
    sill(F, a, b, c, D=0.2)
    lintel(F, a, b, e, key_=True)


# ---- ground -------------------------------------------------------------------------


def stoop(M, F, u, i):
    """Six stone steps up to the door, between two iron rails."""
    m = M.m
    n = 6
    run = STOOP / n
    for k in range(n):
        z1 = GL * (k + 1) / n
        F.box("stone", u - 0.72, u + 0.72, 0, z1, run * (n - 1 - k), run * (n - k), skip=("back",) if k == n - 1 else ())
    for s in (-1, 1):
        x = u + s * 0.66
        foot, head = F.p(x, 0.95, STOOP - 0.08), F.p(x, GL + 0.95, 0.08)
        m.strut("iron", foot, head, 0.045)
        m.strut("iron", F.p(x, 0.12, STOOP - 0.08), F.p(x, 0.95, STOOP - 0.08), 0.06)
        m.strut("iron", F.p(x, GL, 0.08), head, 0.04)
        for k in range(1, 5):
            t = k / 5
            w = STOOP - 0.08 - t * (STOOP - 0.16)
            zb = GL * (1 - w / STOOP) + 0.02
            m.strut("iron", F.p(x, zb, w), F.p(x, zb + 0.93, w), 0.022)
        q = F.p(x, 0, STOOP - 0.08)
        m.cyl("brass", q.x, q.y, 0.045, 1.0, 1.08, seg=8)


def front_door(F, a, b, i):
    """A panelled door under a fanlight, in a painted surround with a small cornice."""
    e = GL + 2.45
    top = GL + 3.0
    wid = new_id()
    dr = DOOR[i]
    for u0, u1 in ((a, a + 0.08), (b - 0.08, b)):
        F.box("trim", u0, u1, GL, top, -0.3, -0.2)
    F.box("trim", a, b, e, e + 0.09, -0.3, -0.2)
    F.box("trim", a, b, top - 0.08, top, -0.3, -0.2)
    F.box(dr, a + 0.08, b - 0.08, GL, e, -0.3, -0.24)
    for z0, z1 in ((GL + 0.15, GL + 1.0), (GL + 1.15, e - 0.15)):
        F.box(dr, a + 0.2, b - 0.2, z0, z1, -0.24, -0.22)
    F.box("brass", (a + b) / 2 - 0.12, (a + b) / 2 + 0.12, GL + 1.3, GL + 1.36, -0.22, -0.2)
    # The fanlight: a half wheel of glazing bars over glass.
    pane(F, "glass", a, b, e + 0.09, top - 0.08, a + 0.08, b - 0.08, e + 0.09, top - 0.08, -0.27, wid)
    mid = (a + b) / 2
    for k in range(5):
        ang = math.pi * (k + 1) / 6
        r = min(mid - a - 0.1, top - e - 0.2)
        F.m.strut("trim", F.p(mid, e + 0.1, -0.25), F.p(mid - math.cos(ang) * r, e + 0.1 + math.sin(ang) * r, -0.25), 0.02)
    # The surround: pilaster strips, a frieze and a cornice on brackets.
    F.box("trim", a - 0.22, a, GL, top + 0.05, 0, 0.06)
    F.box("trim", b, b + 0.22, GL, top + 0.05, 0, 0.06)
    F.box("trim", a - 0.26, b + 0.26, top + 0.05, top + 0.28, 0, 0.07)
    F.box("trim", a - 0.34, b + 0.34, top + 0.28, top + 0.38, 0, 0.2)
    for u in (a - 0.2, b + 0.08):
        F.box("trim", u, u + 0.12, top + 0.05, top + 0.28, 0.07, 0.17)
    F.box("stone", a - 0.05, b + 0.05, GL - 0.04, GL, -0.3, 0.02)


def ground(M):
    m = M.m
    for i, cx, h in houses():
        F = front(m, cx)
        du = door_axis(i, h)
        others = [u for u in bays(i, h) if abs(u - du) > 0.01]
        ww = 1.02 if HW[i] > 4.8 else 1.1
        door = (du - 0.55, du + 0.55)
        base = [(u - ww / 2, u + ww / 2, 0.3, 0.98) for u in others]
        ups = [(u - ww / 2, u + ww / 2, GL + 0.5, GL + 2.75) for u in others]
        holes = [(*door, GL, GL + 3.0, 0.3)] + [(*hl, 0.2) for hl in base + ups]
        F.wall(WALL[i], -h, h, 0, G, holes, depth=0.2, reveal="stone" if WALL[i] != "render" else "render")
        front_door(F, *door, i)
        stoop(M, F, du, i)
        for a, b, c, e in base:
            # Barred basement windows: four panes behind iron bars.
            sash(F, a, b, c, e, D=0.2, lights=(2, 1), fr="trim")
            for k in range(5):
                u = a + 0.08 + k * (b - a - 0.16) / 4
                F.box("iron", u - 0.013, u + 0.013, c + 0.02, e - 0.02, 0.01, 0.04)
            F.box("stone", a - 0.06, b + 0.06, c - 0.08, c, -0.2, 0.05)
        for a, b, c, e in ups:
            window(F, a, b, c, e)
            if SHUTTERS[i]:
                shutters(F, a, b, c, e)
        # A sandstone plinth and a band at the ground floor's level.
        F.box("stone", -h, h, 0, 0.22, 0, 0.06)
        F.box("stone", -h, h, GL - 0.12, GL - 0.02, 0, 0.05)
        anchors(F, -h + 0.25, G - 0.25)
        anchors(F, h - 0.25, G - 0.25)
        # The back: a garden door and a window, plain brick for every house.
        B = back(m, cx)
        bu = -du
        bdoor = (bu - 0.5, bu + 0.5)
        bwin = [(u - 0.5, u + 0.5, GL + 0.6, GL + 2.5) for u in (-bu * 0.9, )]
        B.wall("brick", -h, h, 0, G, [(*bdoor, 0.0, 2.3, 0.15)] + [(*w_, 0.2) for w_ in bwin], depth=0.2, reveal="stone")
        B.box(DOOR[i], bdoor[0] + 0.05, bdoor[1] - 0.05, 0, 2.25, -0.15, -0.1)
        for a, b, c, e in bwin:
            window(B, a, b, c, e, lights=(2, 2))
    sides(m, 0, G)
    m.poly("dark", [(X0, Y0, G - 0.02), (X1, Y0, G - 0.02), (X1, Y1, G - 0.02), (X0, Y1, G - 0.02)], out=Z)


def sides(m, z0, z1):
    """The two blank party walls at the ends of the row."""
    Side(m, (X0, (Y0 + Y1) / 2, 0), (0, -1, 0), (-1, 0, 0)).wall("brick", -D / 2, D / 2, z0, z1, [])
    Side(m, (X1, (Y0 + Y1) / 2, 0), (0, 1, 0), (1, 0, 0)).wall("brick2", -D / 2, D / 2, z0, z1, [])


# ---- upper storeys ------------------------------------------------------------------


def storey(M, z):
    m = M.m
    for i, cx, h in houses():
        F = front(m, cx)
        ww = 1.02 if HW[i] > 4.8 else 1.1
        holes = [(u - ww / 2, u + ww / 2, z + 0.55, z + 2.65) for u in bays(i, h)]
        F.wall(WALL[i], -h, h, z, z + FL, holes, depth=0.2, reveal="stone" if WALL[i] != "render" else "render")
        for a, b, c, e in holes:
            window(F, a, b, c, e)
        if WALL[i] == "brick":
            F.box("stone", -h, h, z + 0.47, z + 0.55, 0, 0.04)
        anchors(F, -h + 0.25, z + FL - 0.25)
        anchors(F, h - 0.25, z + FL - 0.25)
        B = back(m, cx)
        bh = [(u - 0.5, u + 0.5, z + 0.7, z + 2.5) for u in (-h * 0.45, h * 0.45)]
        B.wall("brick", -h, h, z, z + FL, bh, depth=0.2, reveal="stone")
        for a, b, c, e in bh:
            window(B, a, b, c, e, lights=(2, 2))
    sides(m, z, z + FL)
    m.poly("dark", [(X0, Y0, z + FL - 0.02), (X1, Y0, z + FL - 0.02), (X1, Y1, z + FL - 0.02), (X0, Y1, z + FL - 0.02)], out=Z)


# ---- gables and roofs ---------------------------------------------------------------


def slab(F, role, pts, t=T, edges=True):
    """A gable of outline `pts` ((u, z) counter-clockwise from the bottom left), t thick behind the front."""
    fpoly(F, role, pts, 0.0)
    fpoly(F, role, list(reversed(pts)), -t, out=-F.n)
    if not edges:
        return
    n = len(pts)
    for k in range(n):
        (u0, z0), (u1, z1) = pts[k], pts[(k + 1) % n]
        if abs(z0 - z1) < 1e-6 and z0 <= min(p[1] for p in pts) + 1e-6:
            continue
        a, b = F.p(u0, z0, 0), F.p(u1, z1, 0)
        out = F.p(u1, z1, 0) - F.p(u0, z0, 0)
        nrm = out.cross(F.n)
        F.m.poly(role, [a, b, F.p(u1, z1, -t), F.p(u0, z0, -t)], out=nrm)


def coping(F, pts, r=0.09, w=0.02):
    """A sandstone bead along a run of outline points."""
    for (u0, z0), (u1, z1) in zip(pts, pts[1:]):
        F.m.strut("stone", F.p(u0, z0, w - T / 2), F.p(u1, z1, w - T / 2), T + 0.08, r * 2)


def hoist(M, F, z):
    """The hoist beam under its little hood, and the loft door below it."""
    F.box("wood", -0.1, 0.1, z - 0.12, z + 0.1, 0, 1.05, skip=("back",))
    F.box("iron", -0.02, 0.02, z - 0.5, z - 0.12, 0.92, 0.96)
    F.box("iron", -0.07, 0.07, z - 0.56, z - 0.5, 0.88, 1.0)
    F.box("wood", -0.25, 0.25, z + 0.1, z + 0.16, 0, 1.12, skip=("back",))


def loft_door(F, z0, z1, hw=0.42):
    F.box("trim", -hw - 0.08, hw + 0.08, z0 - 0.06, z1 + 0.08, -0.02, 0.03)
    F.box("shutter", -hw, 0, z0, z1, 0.03, 0.08)
    F.box("shutter", 0, hw, z0, z1, 0.03, 0.08)
    for zz in (z0 + 0.2, z1 - 0.2):
        F.box("iron", -hw + 0.05, hw - 0.05, zz - 0.02, zz + 0.02, 0.08, 0.1)


def gable_windows(F, role, z, us, ww=0.9, e=1.75, lights=(2, 2)):
    for u in us:
        a, b = u - ww / 2, u + ww / 2
        F.box("trim", a, b, z, z + e, -0.01, 0.0)
        sash(F, a, b, z, z + e, D=0.0, lights=lights, fr="trim")
        F.box("stone", a - 0.08, b + 0.08, z - 0.07, z, 0, 0.06)
        F.box("stone", a - 0.06, b + 0.06, z + e, z + e + 0.12, 0, 0.04)


def step_gable(M, F, top, h, role):
    """Five steps a side up to a capped top block with a date stone."""
    n, hn, zn, zt = 5, 0.62, top + 4.3, top + 5.5
    dz = (zn - top) / n
    left = [(-h, top)]
    for k in range(n):
        hk = h - (h - hn) * k / n
        hk1 = h - (h - hn) * (k + 1) / n
        left += [(-hk, top + (k + 1) * dz), (-hk1, top + (k + 1) * dz)]
    left.append((-hn, zt))
    right = [(-u, z) for u, z in reversed(left)]
    slab(F, role, left + right)
    # Each step's stone cap, the top block's cornice and a ball finial.
    for k in range(n):
        hk = h - (h - hn) * k / n
        hk1 = h - (h - hn) * (k + 1) / n
        zk = top + (k + 1) * dz
        for s in (-1, 1):
            a, b = sorted((s * hk, s * hk1))
            F.box("stone", a - 0.06, b + 0.06, zk, zk + 0.1, -T - 0.04, 0.06, skip=())
    F.box("stone", -hn - 0.1, hn + 0.1, zt, zt + 0.14, -T - 0.06, 0.1, skip=())
    q = F.p(0, zt + 0.14, -T / 2)
    M.m.cyl("stone", q.x, q.y, 0.09, zt + 0.14, zt + 0.3, seg=10, r1=0.14)
    M.m.cyl("stone", q.x, q.y, 0.14, zt + 0.3, zt + 0.5, seg=10, r1=0.0)
    F.box("stone", -0.48, 0.48, zn + 0.3, zn + 0.72, 0, 0.05)
    letters(M.m, "iron", F, 0, zn + 0.51, 0.05, "1652", 0.22, depth=0.015, spacing=1.15)
    gable_windows(F, role, top + 0.35, [-h * 0.45, h * 0.45], ww=0.95)
    loft_door(F, top + 2.45, top + 3.6)
    hoist(M, F, top + 3.95)


def neck_gable(M, F, top, h, role):
    """A tall neck between carved claw pieces, under a stone pediment."""
    nk, zs, zn = 0.85, top + 2.3, top + 5.2
    body = [(-h, top), (h, top), (h, zs), (nk, zs), (nk, zn), (-nk, zn), (-nk, zs), (-h, zs)]
    slab(F, role, body)
    F.box("stone", -h, h, zs, zs + 0.12, -T - 0.02, 0.08, skip=())
    for s in (-1, 1):
        # A claw piece of carved stone, its outer edge curving in to the neck.
        arc = [(s * (nk + 1.1 + 1.1 * math.cos(a)), zs + 2.02 + 1.9 * math.sin(a)) for a in [math.pi * (1.5 - k / 16) for k in range(9)]]
        claw = [(s * nk, zs + 0.12)] + arc
        slab(F, "stone", claw if s > 0 else list(reversed(claw)), t=T * 0.7)
        q = F.p(s * nk, 0, 0.0)
        M.m.cyl("stone", q.x, q.y, 0.12, zs + 1.95, zs + 2.15, seg=10)
        # A scroll at the claw's foot and a vase on the shoulder.
        q = F.p(s * (nk + 1.25), 0, -T / 2)
        M.m.cyl("stone", q.x, q.y, 0.11, zs + 0.12, zs + 0.32, seg=10, r1=0.07)
        M.m.cyl("stone", q.x, q.y, 0.07, zs + 0.32, zs + 0.5, seg=10, r1=0.13)
        M.m.cyl("stone", q.x, q.y, 0.13, zs + 0.5, zs + 0.56, seg=10)
    # The neck's pilasters, cornice and the triangular pediment over it.
    for s in (-1, 1):
        F.box("stone", s * nk - 0.12, s * nk + 0.12, zs + 0.12, zn, 0, 0.05)
    F.box("stone", -nk - 0.14, nk + 0.14, zn, zn + 0.16, -T - 0.03, 0.1, skip=())
    ped = [(-nk - 0.2, zn + 0.16), (nk + 0.2, zn + 0.16), (0, zn + 0.86)]
    slab(F, "stone", ped, t=T + 0.06)
    coping(F, [(-nk - 0.22, zn + 0.16), (0, zn + 0.9), (nk + 0.22, zn + 0.16)], r=0.05, w=0.04)
    gable_windows(F, role, top + 0.3, [-h * 0.5, h * 0.5], ww=0.9, e=1.6)
    loft_door(F, zs + 0.45, zs + 1.55, hw=0.38)
    hoist(M, F, zs + 1.95)
    F.box("stone", -0.3, 0.3, zn - 0.75, zn - 0.25, 0, 0.04)


def bell_gable(M, F, top, h, role):
    """A bell-shaped gable with a stone bead round its curve and a segmental crown."""
    nk, z0, z1, za = 0.92, top + 0.7, top + 4.6, top + 5.35
    curve = []
    for k in range(13):
        s = k / 12
        curve.append((-(nk + (h - nk) * (1 + math.cos(math.pi * s)) / 2), z0 + (z1 - z0) * s))
    crown = [(-nk * math.cos(a), z1 + (za - z1) * math.sin(a)) for a in [k * math.pi / 10 for k in range(1, 10)]]
    left = [(-h, top)] + curve
    right = [(-u, z) for u, z in reversed(curve)] + [(h, top)]
    slab(F, role, left + crown + right)
    bead = curve + crown + [(-u, z) for u, z in reversed(curve)]
    coping(F, bead, r=0.06, w=0.035)
    # Garlands of carved stone in the bell's shoulders and a cartouche at the crown.
    for s in (-1, 1):
        F.box("stone", s * (h - 0.62) - 0.22, s * (h - 0.62) + 0.22, z0 + 0.1, z0 + 0.62, 0, 0.06)
        q = F.p(s * (h - 0.62), 0, 0.05)
        M.m.cyl("stone", q.x, q.y, 0.14, z0 + 0.62, z0 + 0.72, seg=10)
    F.box("stone", -0.55, 0.55, z1 - 0.2, z1 + 0.35, 0, 0.06)
    F.box("stone", -0.42, 0.42, z1 + 0.35, z1 + 0.5, 0, 0.04)
    gable_windows(F, role, top + 0.35, [-h * 0.47, 0.0, h * 0.47], ww=0.85, e=1.7)
    loft_door(F, top + 2.5, top + 3.55, hw=0.4)
    hoist(M, F, top + 3.95)


GABLES = (step_gable, neck_gable, bell_gable)


def roof(M, top):
    m = M.m
    yf, yb = Y0 + T, Y1 - 0.2
    for i, cx, h in houses():
        F = front(m, cx)
        role = WALL[i]
        GABLES[i](M, F, top, h, role)
        # The tiled roof: two steep slopes from the party walls to the ridge,
        # a little lower at the eaves so the gables stand clear of it.
        x0, x1, rz = cx - h, cx + h, top + RIDGE
        for xa, xb, out in ((x0, cx, (-1, 0, 1)), (cx, x1, (1, 0, 1))):
            za = top if xa == x0 else rz
            zb = rz if xa == x0 else top
            m.poly("plaintile", [(xa, yf, za), (xb, yf, zb), (xb, yb, zb), (xa, yb, za)], out=out)
        m.strut("ridge", (cx, yf, rz + 0.04), (cx, yb + 0.1, rz + 0.04), 0.16)
        # The back gable, plain brick with a small window and a stone kneeler each side.
        B = back(m, cx)
        fpoly(B, "brick", [(-h, top), (h, top), (0, top + RIDGE)], 0.0)
        fpoly(B, "brick", [(-h, top), (0, top + RIDGE), (h, top)], -0.2, out=-B.n)
        for s in (-1, 1):
            B.m.strut("stone", B.p(s * h, top, 0.02), B.p(0, top + RIDGE + 0.02, 0.02), 0.12, 0.08)
        wa, wb = -0.42, 0.42
        B.box("trim", wa, wb, top + 0.6, top + 1.75, 0, 0.03)
        sash(B, wa, wb, top + 0.6, top + 1.75, D=-0.03, lights=(2, 2), fr="trim")
        # A lead-lined valley on each party wall.
        if i:
            m.box("lead", (x0 - 0.18, yf, top - 0.02), (x0 + 0.18, yb, top + 0.03))
    # Chimneys on the party walls and one on the end wall, with pots.
    for x, y in ((X0 + HW[0], Y0 + 4.2), (X0 + HW[0] + HW[1], Y1 - 3.2), (X1 - 0.35, Y0 + 6.5)):
        zt = top + RIDGE + 0.6
        m.box("brick", (x - 0.32, y - 0.42, top - 0.02), (x + 0.32, y + 0.42, zt))
        m.box("stone", (x - 0.38, y - 0.48, zt), (x + 0.38, y + 0.48, zt + 0.1))
        for dy in (-0.18, 0.18):
            m.cyl("terracotta", x, y + dy, 0.1, zt + 0.1, zt + 0.42, seg=10, r1=0.085)
    # The ends of the row's eaves: lead flashing over the top of the end walls.
    for x in (X0, X1):
        m.box("lead", (x - 0.03, yf, top - 0.02), (x + (0.06 if x == X1 else -0.06), yb, top + 0.04))
