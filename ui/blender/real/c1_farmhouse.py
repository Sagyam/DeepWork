# C1, clapboard farmhouse: an American I-house, two storeys and one room
# deep under a side-gabled shingle roof, three bays with six-over-six sash
# windows and louvred shutters, a full-width front porch on turned-down
# square posts, a brick chimney on the left gable end and a one-storey
# lean-to kitchen at the back. Painted weatherboard, white trim; the app
# tints siding, shutters, door and roof per house.
#
# Pieces (base at the origin):
#   body        everything up to the eaves: walls, windows, porch, lean-to
#   roof        main roof, gables, chimney stack, gutters
#   fence       a 2.4 m picket fence panel (post at its left end)
#   fence_post  the post that ends a run
import math

from lib import Model, Side, Z, new_id, pane, sash, sides

ID = "c1"
W, D = 8.6, 6.0  # main block
CY = -0.2  # its centre: the porch in front and the lean-to behind keep the footprint centred
Y0, Y1 = CY - D / 2, CY + D / 2  # front and back walls (front faces -y)
BASE = 0.6  # top of the foundation, ground floor level
UP = 3.4  # upper floor level
PLATE = 6.1  # top of the walls
PITCH = math.radians(40)
RISE = math.tan(PITCH)
APEX = PLATE + D / 2 * RISE
EAVE, RAKE = 0.35, 0.22  # overhangs
DEPTH = 0.12  # window reveal
PORCH = Y0 - 2.1  # porch beam line
LEAN = (-3.7, 3.7, Y1, Y1 + 2.6)  # lean-to x0, x1, y0, y1
CHIM = (-W / 2 - 0.7, -W / 2)  # chimney breast, x


def build(out, bake=True):
    M = Model(ID)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, PLATE))
    roof(M)
    M.piece("fence", (20, 0, 0))
    fence(M.m, 20)
    M.piece("fence_post", (24, 0, 0))
    post(M.m, 24, 0)
    M.export(out, bake)


# ---- parts ------------------------------------------------------------------------


def loft(m, role, lo, hi):
    """Four sloped sides between two rectangles (x0, x1, y0, y1, z), lo below hi."""
    (a0, a1, b0, b1, z0), (c0, c1, d0, d1, z1) = lo, hi
    m.poly(role, [(a0, b0, z0), (a1, b0, z0), (c1, d0, z1), (c0, d0, z1)], out=(0, -1, 0.3))
    m.poly(role, [(a1, b0, z0), (a1, b1, z0), (c1, d1, z1), (c1, d0, z1)], out=(1, 0, 0.3))
    m.poly(role, [(a1, b1, z0), (a0, b1, z0), (c0, d1, z1), (c1, d1, z1)], out=(0, 1, 0.3))
    m.poly(role, [(a0, b1, z0), (a0, b0, z0), (c0, d0, z1), (c0, d1, z1)], out=(-1, 0, 0.3))


def slope(m, role, x0, x1, ya, za, yb, zb, out, uv=True):
    """A roof plane from the edge (ya, za) up to (yb, zb), across x0..x1; UV v runs up the slope."""
    L = math.hypot(yb - ya, zb - za)
    pts = [(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)]
    m.poly(role, pts, out=out, uvs=[(x0, 0), (x1, 0), (x1, L), (x0, L)] if uv else None)


def window(F, a, b, c, e, shutters=True, lights=(3, 2)):
    """A sash in a cased opening: flat casing, a drip cap, a sill, and louvred shutters."""
    sash(F, a, b, c, e, D=DEPTH, lights=lights)
    F.box("trim", a - 0.1, a, c, e, 0, 0.025)
    F.box("trim", b, b + 0.1, c, e, 0, 0.025)
    F.box("trim", a - 0.12, b + 0.12, e, e + 0.16, 0, 0.03)
    F.box("trim", a - 0.15, b + 0.15, e + 0.16, e + 0.2, 0, 0.07)
    F.box("trim", a - 0.06, b + 0.06, c - 0.06, c, -DEPTH + 0.02, 0.06)
    F.box("trim", a - 0.04, b + 0.04, c - 0.14, c - 0.06, 0, 0.03)
    if shutters:
        sw = (b - a) / 2 + 0.02
        for u0, u1 in ((a - 0.1 - sw, a - 0.1), (b + 0.1, b + 0.1 + sw)):
            F.box("shutter", u0, u1, c, e, 0.025, 0.055, skip=("back", "front"))
            F.quad("shutter", u0, u1, c, e, 0.055, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
            F.box("iron", u0 + 0.02 if u0 < a else u1 - 0.06, u0 + 0.06 if u0 < a else u1 - 0.02, c + 0.3, c + 0.33, 0.055, 0.07)


def door(F, a, b, c, t, e, role="door", lights=True):
    """A four-panel door from c to t in the opening (a..b, c..e) with a transom light above."""
    wid = new_id()
    F.box("trim", a, a + 0.05, c, e, -DEPTH, -DEPTH + 0.1)
    F.box("trim", b - 0.05, b, c, e, -DEPTH, -DEPTH + 0.1)
    F.box("trim", a + 0.05, b - 0.05, t, t + 0.06, -DEPTH, -DEPTH + 0.1)
    F.box("trim", a + 0.05, b - 0.05, e - 0.05, e, -DEPTH, -DEPTH + 0.1)
    pane(F, "glass", a, b, c, e, a + 0.05, b - 0.05, t + 0.06, e - 0.05, -DEPTH + 0.04, wid)
    da, db = a + 0.05, b - 0.05
    F.quad(role, da, db, c, t, -DEPTH + 0.03)
    mid = (da + db) / 2
    rows = [(c + 0.15, c + 0.75), (c + 0.9, t - 0.15)]
    if lights:
        # Glazed in the upper half, four lights.
        g0, g1 = rows[1]
        F.box(role, da + 0.12, db - 0.12, g0 - 0.02, g1 + 0.02, -DEPTH + 0.03, -DEPTH + 0.05, skip=("back", "front"))
        pane(F, "glass", a, b, c, e, da + 0.12, db - 0.12, g0, g1, -DEPTH + 0.04, new_id())
        F.box(role, mid - 0.015, mid + 0.015, g0, g1, -DEPTH + 0.04, -DEPTH + 0.055)
        F.box(role, da + 0.12, db - 0.12, (g0 + g1) / 2 - 0.015, (g0 + g1) / 2 + 0.015, -DEPTH + 0.04, -DEPTH + 0.055)
        rows = rows[:1]
    for z0, z1 in rows:
        for u0, u1 in ((da + 0.1, mid - 0.06), (mid + 0.06, db - 0.1)):
            F.box(role, u0, u1, z0, z1, -DEPTH + 0.03, -DEPTH + 0.05)
    F.box("brass", db - 0.12, db - 0.07, c + 0.95, c + 1.02, -DEPTH + 0.03, -DEPTH + 0.09)
    # Casing.
    F.box("trim", a - 0.11, a, c, e, 0, 0.025)
    F.box("trim", b, b + 0.11, c, e, 0, 0.025)
    F.box("trim", a - 0.13, b + 0.13, e, e + 0.18, 0, 0.03)
    F.box("trim", a - 0.16, b + 0.16, e + 0.18, e + 0.22, 0, 0.07)


def corners(F, h, z0, z1):
    F.box("trim", -h, -h + 0.14, z0, z1, 0, 0.025)
    F.box("trim", h - 0.14, h, z0, z1, 0, 0.025)


def rail_run(m, x0, y0, x1, y1, z):
    """A porch railing between two posts: top and bottom rails, square balusters."""
    a, b = (x0, y0), (x1, y1)
    L = math.hypot(x1 - x0, y1 - y0)
    tx, ty = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -ty, tx
    at = lambda s, o: (a[0] + tx * s + nx * o, a[1] + ty * s + ny * o)  # noqa: E731

    def bar(s0, s1, o0, o1, z0, z1):
        p0, p1 = at(s0, o0), at(s1, o1)
        m.box("trim", (p0[0], p0[1], z0), (p1[0], p1[1], z1))

    bar(0.08, L - 0.08, -0.045, 0.045, z + 0.86, z + 0.92)
    bar(0.08, L - 0.08, -0.035, 0.035, z + 0.08, z + 0.14)
    n = int((L - 0.16) / 0.11)
    for i in range(n):
        s = 0.08 + (i + 0.5) * (L - 0.16) / n
        bar(s - 0.02, s + 0.02, -0.02, 0.02, z + 0.14, z + 0.86)


# ---- body ---------------------------------------------------------------------------


def body(M):
    m = M.m
    walls = sides(m, W, D, cy=CY)
    # Brick foundation with vents, a water table board above it.
    m.sweep("brick", W, D, [(0.04, 0.0), (0.04, BASE), (-0.01, BASE)], cy=CY)
    m.sweep("trim", W, D, [(-0.01, BASE), (0.03, BASE), (0.03, BASE + 0.18), (0.05, BASE + 0.2), (0.05, BASE + 0.23), (-0.01, BASE + 0.23)], cy=CY)
    for name in ("right", "left"):
        walls[name].box("dark", -1.5, -1.1, 0.22, 0.38, 0.04, 0.045, skip=("back",))
        walls[name].box("dark", 1.1, 1.5, 0.22, 0.38, 0.04, 0.045, skip=("back",))

    wz = [(BASE + 0.7, BASE + 2.2), (UP + 0.72, UP + 2.22)]  # sash openings, both storeys
    ww = 0.92
    bays = [-2.85, 0.0, 2.85]
    for name, F in walls.items():
        h = W / 2 if name in ("front", "back") else D / 2
        holes, wins, doors = [], [], []
        if name == "front":
            for u in bays:
                if u == 0.0:
                    doors.append((-0.5, 0.5, BASE, BASE + 2.15, BASE + 2.5))
                    holes.append((-0.5, 0.5, BASE, BASE + 2.5))
                else:
                    wins.append((u - ww / 2, u + ww / 2, *wz[0]))
                wins.append((u - ww / 2, u + ww / 2, *wz[1]))
        elif name == "back":
            for u in bays:
                wins.append((u - ww / 2, u + ww / 2, *wz[1]))
        elif name == "right":
            for z in wz:
                for u in (-1.35, 1.35):
                    wins.append((u - ww / 2, u + ww / 2, *z))
        else:
            # Either side of the chimney breast.
            for z in wz:
                for u in (-1.75, 1.75):
                    wins.append((u - 0.8 / 2, u + 0.8 / 2, *z))
        holes += [w_[:4] for w_ in wins]
        F.wall("siding", -h, h, BASE, PLATE, holes, depth=DEPTH, reveal="trim")
        for a, b, c, e in wins:
            window(F, a, b, c, e, shutters=name in ("front", "right"), lights=(3, 2) if b - a > 0.85 else (2, 2))
        for d in doors:
            door(F, *d)
        corners(F, h, BASE, PLATE)
        if name in ("front", "back"):
            F.box("trim", -h, h, PLATE - 0.28, PLATE, 0, 0.03)
    # A ceiling over the top of the walls, seen only when the roof is gone.
    m.poly("dark", [(-W / 2, Y0, PLATE - 0.02), (W / 2, Y0, PLATE - 0.02), (W / 2, Y1, PLATE - 0.02), (-W / 2, Y1, PLATE - 0.02)], out=Z)
    # Upstairs floor line on the gables: a belt board.
    for name in ("right", "left"):
        walls[name].box("trim", -D / 2, D / 2, UP - 0.12, UP + 0.02, 0, 0.025)
    porch(m, walls["front"])
    chimney_breast(m)
    lean_to(m)
    # Downspouts at the back corners.
    for x in (-W / 2 + 0.12, W / 2 - 0.12):
        m.box("gutter", (x - 0.04, Y1 + 0.06, 0.05), (x + 0.04, Y1 + 0.13, PLATE - 0.25))
        m.box("gutter", (x - 0.04, Y1 + 0.06, 0.05), (x + 0.04, Y1 + 0.35, 0.12))


def porch(m, F):
    """Full-width porch: deck on brick piers, square posts, railings, a shed roof with a beadboard ceiling."""
    x0, x1 = -W / 2 - 0.1, W / 2 + 0.1
    deck = BASE - 0.05
    yb = PORCH - 0.15
    m.box("deck", (x0, yb, deck - 0.1), (x1, Y0, deck))
    m.box("trim", (x0 - 0.02, yb - 0.02, deck - 0.3), (x1 + 0.02, Y0, deck - 0.1), skip=("y1",))
    for x in (x0 + 0.2, -1.45, 1.45, x1 - 0.2):
        m.box("brick", (x - 0.17, yb + 0.05, 0), (x + 0.17, yb + 0.39, deck - 0.3))
    m.poly("dark", [(x0 + 0.05, yb + 0.25, 0), (x1 - 0.05, yb + 0.25, 0), (x1 - 0.05, yb + 0.25, deck - 0.3), (x0 + 0.05, yb + 0.25, deck - 0.3)], out=(0, -1, 0))
    for x in (x0, x1):
        m.poly("dark", [(x, yb + 0.25, 0), (x, Y0, 0), (x, Y0, deck - 0.3), (x, yb + 0.25, deck - 0.3)], out=(1 if x > 0 else -1, 0, 0))
    # Steps down to the path.
    for i, z in enumerate((deck - 0.2, deck - 0.38)):
        m.box("deck", (-0.85, yb - 0.3 * (i + 1), z - 0.04), (0.85, yb - 0.3 * i, z), skip=())
        m.box("trim", (-0.85, yb - 0.3 * (i + 1) + 0.02, 0), (0.85, yb - 0.3 * (i + 1) + 0.04, z - 0.04))
    for x in (-0.9, 0.86):
        m.poly("trim", [(x, yb, 0), (x, yb - 0.62, 0), (x, yb, deck - 0.1)], out=(-1, 0, 0))
        m.poly("trim", [(x + 0.04, yb, 0), (x + 0.04, yb - 0.62, 0), (x + 0.04, yb, deck - 0.1)], out=(1, 0, 0))
    # Posts, beam and railings.
    beam = 3.08
    px = [x0 + 0.15, -1.45, 1.45, x1 - 0.15]
    py = PORCH
    for x in px:
        m.box("trim", (x - 0.07, py - 0.07, deck), (x + 0.07, py + 0.07, beam))
        m.box("trim", (x - 0.1, py - 0.1, deck), (x + 0.1, py + 0.1, deck + 0.22))
        m.box("trim", (x - 0.1, py - 0.1, beam - 0.2), (x + 0.1, py + 0.1, beam - 0.12))
    m.box("trim", (x0 - 0.05, py - 0.11, beam), (x1 + 0.05, py + 0.11, beam + 0.24))
    rail_run(m, px[0], py, px[1], py, deck)
    rail_run(m, px[2], py, px[3], py, deck)
    for x in (px[0], px[3]):
        rail_run(m, x, py, x, Y0 - 0.05, deck)
    # Ceiling and roof.
    top = beam + 0.24
    hi = 3.92
    m.poly("ceiling", [(x0, py - 0.11, beam), (x1, py - 0.11, beam), (x1, Y0, beam), (x0, Y0, beam)], out=-Z)
    m.box("trim", (x0 - 0.05, Y0 - 0.04, beam), (x1 + 0.05, Y0, beam + 0.08))
    edge = py - 0.3
    k = (hi - top) / (Y0 - py)
    ze = top - (py - edge) * k
    slope(m, "shingle", x0 - 0.1, x1 + 0.1, edge, ze + 0.12, Y0, hi + 0.12, out=(0, -1, 3))
    slope(m, "trim", x0 - 0.1, x1 + 0.1, edge, ze, Y0, hi, out=(0, 1, -3), uv=False)
    m.box("trim", (x0 - 0.1, edge - 0.02, ze - 0.06), (x1 + 0.1, edge, ze + 0.14), skip=("y1",))
    for x, s in ((x0 - 0.1, -1), (x1 + 0.1, 1)):
        m.poly("trim", [(x, edge, ze - 0.06), (x, Y0, hi), (x, Y0, hi + 0.14), (x, edge, ze + 0.14)], out=(s, 0, 0))
    for x, s in ((x0, -1), (x1, 1)):
        m.poly("trim", [(x, py - 0.11, beam), (x, Y0, beam), (x, Y0, hi), (x, py - 0.11, top)], out=(s, 0, 0))
    m.box("trim", (x0 - 0.1, Y0 - 0.02, hi + 0.08), (x1 + 0.1, Y0, hi + 0.25))
    # Porch light by the door.
    F.box("iron", 0.78, 0.9, BASE + 1.85, BASE + 1.95, 0, 0.12)
    F.box("lamp", 0.76, 0.92, BASE + 1.95, BASE + 2.2, 0.04, 0.2, skip=())
    F.box("iron", 0.74, 0.94, BASE + 2.2, BASE + 2.25, 0.02, 0.22, skip=())


def chimney_breast(m):
    """The exterior brick chimney on the left gable: a wide base, sloped shoulders, the stack to the eaves."""
    xa, xb = CHIM
    m.box("brick", (xa, CY - 0.8, 0), (xb, CY + 0.8, 4.6), skip=("x1",))
    loft(m, "brick", (xa, xb, CY - 0.8, CY + 0.8, 4.6), (xa + 0.1, xb, CY - 0.45, CY + 0.45, 5.4))
    m.box("brick", (xa + 0.1, CY - 0.45, 5.4), (xb, CY + 0.45, PLATE), skip=("x1", "z1", "z0"))
    m.sweep("stone", xb - xa, 1.6, [(-0.01, 4.55), (0.03, 4.55), (0.03, 4.62), (-0.01, 4.62)], cx=(xa + xb) / 2, cy=CY)


def lean_to(m):
    """The one-storey kitchen behind, under a shed roof: a back door and a window."""
    x0, x1, y0, y1 = LEAN
    lw, lh = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hi, lo = UP + 0.42, 2.92  # wall heights at the house and at the back
    m.sweep("brick", lw, lh, [(0.04, 0.0), (0.04, BASE), (-0.01, BASE)], cx=cx, cy=cy)
    F = Side(m, (cx, y1, 0), (-1, 0, 0), (0, 1, 0))
    holes = [(-2.2, -1.3, BASE, BASE + 2.5), (0.9, 1.7, BASE + 0.9, BASE + 2.0)]
    F.wall("siding", -lw / 2, lw / 2, BASE, lo, holes, depth=DEPTH, reveal="trim")
    door(F, -2.2, -1.3, BASE, BASE + 2.15, BASE + 2.5, lights=False)
    window(F, 0.9, 1.7, BASE + 0.9, BASE + 2.0, shutters=False, lights=(2, 1))
    corners(F, lw / 2, BASE, lo)
    F.box("trim", -lw / 2, lw / 2, BASE, BASE + 0.2, 0, 0.03)
    F.box("deck", -2.5, -1.0, 0, BASE - 0.05, 0, 0.7, skip=("back",))
    for x, s in ((x0, -1), (x1, 1)):
        m.poly("siding", [(x, y0, BASE), (x, y1, BASE), (x, y1, lo), (x, y0, hi)], out=(s, 0, 0))
        m.box("trim", (x if s > 0 else x - 0.025, y1 - 0.14, BASE), (x + 0.025 if s > 0 else x, y1, lo), skip=())
    # Roof, with its fascia and a gutter.
    k = (hi - lo) / lh
    ye = y1 + 0.3
    ze = lo - 0.3 * k
    slope(m, "shingle", x0 - 0.2, x1 + 0.2, ye, ze + 0.14, y0, hi + 0.14, out=(0, 1, 3))
    slope(m, "trim", x0 - 0.2, x1 + 0.2, ye, ze, y0, hi, out=(0, -1, -3), uv=False)
    m.box("trim", (x0 - 0.2, ye, ze - 0.04), (x1 + 0.2, ye + 0.02, ze + 0.16), skip=("y0",))
    for x, s in ((x0 - 0.2, -1), (x1 + 0.2, 1)):
        m.poly("trim", [(x, ye, ze - 0.04), (x, y0, hi), (x, y0, hi + 0.14), (x, ye, ze + 0.16)], out=(s, 0, 0))
    m.box("gutter", (x0 - 0.2, ye + 0.02, ze - 0.1), (x1 + 0.2, ye + 0.14, ze + 0.02))
    m.box("gutter", (x1 - 0.1, ye + 0.04, 0.05), (x1 - 0.03, ye + 0.11, ze - 0.1))


# ---- roof ---------------------------------------------------------------------------


def roof(M):
    m = M.m
    x0, x1 = -W / 2 - RAKE, W / 2 + RAKE
    t = 0.2  # roof thickness, measured vertically
    ye0, ye1 = Y0 - EAVE, Y1 + EAVE
    ze = PLATE - EAVE * RISE  # underside at the eave edge
    # Shingle planes, the underside, fascia and rake boards.
    slope(m, "shingle", x0, x1, ye0, ze + t, CY, APEX + t, out=(0, -1, 1))
    slope(m, "shingle", x1, x0, ye1, ze + t, CY, APEX + t, out=(0, 1, 1))
    slope(m, "trim", x0, x1, ye0, ze, CY, APEX, out=(0, 1, -1), uv=False)
    slope(m, "trim", x1, x0, ye1, ze, CY, APEX, out=(0, -1, -1), uv=False)
    for y, s in ((ye0, -1), (ye1, 1)):
        m.poly("trim", [(x0, y, ze - 0.04), (x1, y, ze - 0.04), (x1, y, ze + t), (x0, y, ze + t)], out=(0, s, 0))
    for x, s in ((x0, -1), (x1, 1)):
        for ya in (ye0, ye1):
            m.poly("trim", [(x, ya, ze - 0.04), (x, CY, APEX - 0.04), (x, CY, APEX + t), (x, ya, ze + t)], out=(s, 0, 0))
        # Rake board just inside the edge, proud of the gable.
        g = W / 2 if s > 0 else -W / 2
        for ya in (Y0, Y1):
            m.poly("trim", [(g + s * 0.03, ya, PLATE), (g + s * 0.03, CY, APEX), (g + s * 0.03, CY, APEX - 0.22), (g + s * 0.03, ya, PLATE - 0.22)], out=(s, 0, 0))
    # Ridge cap.
    for y, s in ((CY - 0.13, -1), (CY + 0.13, 1)):
        m.poly("shingle", [(x0 - 0.02, y, APEX + t + 0.02 - 0.13 * RISE), (x1 + 0.02, y, APEX + t + 0.02 - 0.13 * RISE), (x1 + 0.02, CY, APEX + t + 0.05), (x0 - 0.02, CY, APEX + t + 0.05)], out=(0, s, 1))
    # Gable ends in siding, with a belt board at the plate and a louvred vent on the right.
    for x, s in ((-W / 2, -1), (W / 2, 1)):
        m.poly("siding", [(x, Y0, PLATE), (x, Y1, PLATE), (x, CY, APEX)], out=(s, 0, 0))
        m.box("trim", (x - (0.03 if s < 0 else 0), Y0, PLATE - 0.02), (x + (0.03 if s > 0 else 0), Y1, PLATE + 0.14))
    F = Side(m, (W / 2, CY, 0), (0, 1, 0), (1, 0, 0))
    vz = PLATE + 0.75
    F.box("trim", -0.36, 0.36, vz - 0.06, vz + 0.86, 0, 0.04)
    F.box("shutter", -0.3, 0.3, vz, vz + 0.8, 0.04, 0.05, skip=("back", "front"))
    F.quad("shutter", -0.3, 0.3, vz, vz + 0.8, 0.05, uvs=[(0, 0), (1.2, 0), (1.2, 0.53), (0, 0.53)])
    # Gutters along both eaves.
    for y, s in ((ye0, -1), (ye1, 1)):
        ya, yb = (y - 0.14, y) if s < 0 else (y, y + 0.14)
        m.box("gutter", (x0 + 0.05, ya, ze - 0.16), (x1 - 0.05, yb, ze - 0.02))
    # The chimney stack through the eaves, past the ridge, with a corbelled cap and flue pots.
    xa, xb = CHIM
    top = APEX + 0.9
    m.box("brick", (xa + 0.1, CY - 0.45, PLATE), (xb, CY + 0.45, top), skip=("z0",))
    m.sweep("brick", xb - xa - 0.1, 0.9, [(-0.01, top - 0.32), (0.05, top - 0.32), (0.05, top - 0.24), (0.09, top - 0.24), (0.09, top - 0.08), (0.04, top - 0.08), (0.04, top), (-0.01, top)], cx=(xa + 0.1 + xb) / 2, cy=CY)
    m.poly("stone", [(xa + 0.08, CY - 0.47, top), (xb + 0.02, CY - 0.47, top), (xb + 0.02, CY + 0.47, top), (xa + 0.08, CY + 0.47, top)], out=Z)
    for dy in (-0.2, 0.2):
        m.cyl("terracotta", (xa + 0.1 + xb) / 2, CY + dy, 0.11, top, top + 0.4, seg=10, r1=0.09)


# ---- fence --------------------------------------------------------------------------


def post(m, x, y):
    m.box("paint", (x - 0.045, y - 0.045, 0), (x + 0.045, y + 0.045, 1.08))
    m.box("paint", (x - 0.06, y - 0.06, 1.08), (x + 0.06, y + 0.06, 1.12))
    m.poly("paint", [(x - 0.06, y - 0.06, 1.12), (x + 0.06, y - 0.06, 1.12), (x, y, 1.2)], out=(0, -1, 1))
    m.poly("paint", [(x + 0.06, y - 0.06, 1.12), (x + 0.06, y + 0.06, 1.12), (x, y, 1.2)], out=(1, 0, 1))
    m.poly("paint", [(x + 0.06, y + 0.06, 1.12), (x - 0.06, y + 0.06, 1.12), (x, y, 1.2)], out=(0, 1, 1))
    m.poly("paint", [(x - 0.06, y + 0.06, 1.12), (x - 0.06, y - 0.06, 1.12), (x, y, 1.2)], out=(-1, 0, 1))


def fence(m, ox):
    """A 2.4 m picket panel along x from ox - 1.2, pickets on the -y (street) side of the rails."""
    post(m, ox - 1.2, 0)
    for z in (0.22, 0.78):
        m.box("paint", (ox - 1.155, 0.0, z), (ox + 1.155, 0.07, z + 0.08))
    n = 17
    for i in range(n):
        x = ox - 1.2 + (i + 0.5) * 2.4 / n
        a, b = x - 0.036, x + 0.036
        m.box("paint", (a, -0.022, 0.06), (b, 0.0, 0.93), skip=("z1",))
        for y, s in ((-0.022, -1), (0.0, 1)):
            m.poly("paint", [(a, y, 0.93), (b, y, 0.93), (x, y, 1.0)], out=(0, s, 0))
        m.poly("paint", [(a, -0.022, 0.93), (a, 0.0, 0.93), (x, 0.0, 1.0), (x, -0.022, 1.0)], out=(-1, 0, 1))
        m.poly("paint", [(b, -0.022, 0.93), (b, 0.0, 0.93), (x, 0.0, 1.0), (x, -0.022, 1.0)], out=(1, 0, 1))
