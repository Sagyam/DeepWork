# A4, art deco block: a streamline moderne apartment house of the 1930s, the
# kind on Miami Beach's Collins Avenue and in London's mansion blocks of the
# same years. Smooth pastel render, every line horizontal but one: three
# raised speed lines run round the building at every floor, ribbon windows
# in dark steel frames with horizontal glazing bars, and the front corners
# rounded off by curved balconies, a solid parapet and two pipe rails, with
# the glass wrapping the corner behind them. The one vertical is the stair
# tower in the middle of the front: a strip of glass blocks the full height,
# lit from inside at night, between fluted fins, rising over the roof in two
# steps to a flagpole. The entrance at its foot: bronze doors under a
# rounded canopy, a polished black plinth. The app tints the render, the
# bands and the fins.
#
# Pieces (base at the origin, stacked by the app):
#   ground   3.6 m: the entrance, ground-floor flats, the black plinth
#   floor_a, floor_b  3.0 m: typical storeys with the corner balconies; they
#            differ in their eyebrows and what is out on the balconies
#   roof     the parapet, the tower's stepped top, the roof deck
import math

from mathutils import Vector

from lib import Model, Side, Z, glazing, letters, sides

ID = "a4"
W, D = 13.2, 11.0
X0, X1, Y0, Y1 = -W / 2, W / 2, -D / 2, D / 2
G = 3.6
FL = 3.0
STOREYS = ("floor_a", "floor_b")  # the reference stack
DEPTH = 0.14  # glass depth in the walls
TW = 1.4  # the stair tower's half width
TP = 0.55  # how far it stands out of the front
BR = 1.2  # the corner balconies' reach
BL = 2.8  # and their length along each face from the corner
# The windows on each face, (a, b): the first and last run to the corner.
FRONT = [(-6.6, -4.2), (-3.6, -2.0), (2.0, 3.6), (4.2, 6.6)]
SIDE = [(-5.5, -3.7), (-2.6, -0.6), (1.2, 3.4)]  # from the front corner (u = -5.5 on the right side)
BACK = [(-5.8, -4.2), (-3.4, -1.6), (-0.6, 0.6), (1.6, 3.4), (4.2, 5.8)]


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    storey(M, "ground", 0.0, G)
    for f, kind in enumerate(STOREYS):
        z = G + f * FL
        M.piece(kind, (0, 0, z))
        storey(M, kind, z, FL)
    top = G + len(STOREYS) * FL
    M.piece("roof", (0, 0, top))
    roof(M, top)
    M.export(out, bake)


# ---- windows ------------------------------------------------------------------------------


def steel(F, a, b, c, e, ends=(True, True)):
    """A steel window: slim dark frames, a mullion every 0.9 m, glazing bars across in thirds."""
    n = max(1, round((b - a) / 0.9))
    glazing(F, a, b, c, e, lights=n, D=DEPTH, fr="iron", ends=ends)
    ia = a + (0.05 if ends[0] else DEPTH)
    ib = b - (0.05 if ends[1] else DEPTH)
    for k in (1, 2):
        z = c + k * (e - c) / 3
        F.box("iron", ia, ib, z - 0.012, z + 0.012, -DEPTH - 0.02, -DEPTH + 0.02)
    F.box("trim", a - (0.04 if ends[0] else 0), b + (0.04 if ends[1] else 0), c - 0.05, c, -DEPTH + 0.02, 0.05)


# ---- the corner balconies ------------------------------------------------------------------


def corner_path(sx, r, n=8):
    """The plan outline of a corner balcony's edge, r out from the walls: along the
    front from BL in from the corner, round the corner on a quarter circle, back
    along the side. sx = -1 is the left corner, 1 the right."""
    cx, cy = sx * W / 2, Y0
    pts = [Vector((cx - sx * BL, cy - r, 0))]
    for k in range(n + 1):
        t = (math.pi / 2) * k / n
        pts.append(Vector((cx + sx * math.sin(t) * r, cy - math.cos(t) * r, 0)))
    pts.append(Vector((cx + sx * r, cy + BL, 0)))
    return pts


def band(m, role, outer, inner, z0, z1, top=True, bottom=False, ends=True):
    """A strip standing on a path: its outer and inner faces (outer and inner outlines,
    point for point), the top, the bottom, the end caps."""
    up = Vector((0, 0, 1))
    for (a, b), (c, d) in zip(zip(outer, outer[1:]), zip(inner, inner[1:])):
        mid = (a + b) / 2 - (c + d) / 2
        m.poly(role, [a + up * z0, b + up * z0, b + up * z1, a + up * z1], out=mid)
        m.poly(role, [c + up * z0, d + up * z0, d + up * z1, c + up * z1], out=-mid)
        if top:
            m.poly(role, [a + up * z1, b + up * z1, d + up * z1, c + up * z1], out=Z)
        if bottom:
            m.poly(role, [a + up * z0, b + up * z0, d + up * z0, c + up * z0], out=-Z)
    if ends:
        for o, i, nb in ((outer[0], inner[0], outer[1]), (outer[-1], inner[-1], outer[-2])):
            m.poly(role, [o + up * z0, i + up * z0, i + up * z1, o + up * z1], out=o - nb)


def corner_balcony(M, sx, z, things):
    """A balcony round the corner at floor z: a slab with a rounded edge, a solid parapet,
    two pipe rails on posts above it, the soffit painted."""
    m = M.m
    c = Vector((sx * W / 2, Y0, 0))
    outer = corner_path(sx, BR)
    inner = corner_path(sx, BR - 0.12)
    # The slab: a fan from the corner of the walls.
    fan = [Vector((sx * (W / 2 - BL), Y0, 0))] + outer + [Vector((sx * W / 2, Y0 + BL, 0))]
    for zz, out in ((z, Z), (z - 0.2, -Z)):
        for a, b in zip(fan, fan[1:]):
            m.poly("paint" if out.z < 0 else "concrete", [c + Z * zz, a + Z * zz, b + Z * zz], out=out)
    band(m, "render", outer, inner, z - 0.2, z + 0.62)
    # The parapet's coping, a shade proud, and a speed line round its face.
    proud = corner_path(sx, BR + 0.03)
    band(m, "trim", proud, inner, z + 0.62, z + 0.68, bottom=True)
    for zz in (z - 0.05, z + 0.12):
        band(m, "band", corner_path(sx, BR + 0.025), outer, zz, zz + 0.05, bottom=True, ends=False)
    # Pipe rails over the parapet.
    rail = corner_path(sx, BR - 0.06, n=12)
    for h in (0.92, 1.08):
        m.tube("trim", [p + Z * (z + h) for p in rail], 0.022, Z, closed=False)
    for p in rail[::3] + [rail[-1]]:
        m.cyl("trim", p.x, p.y, 0.018, z + 0.68, z + 1.08, seg=6, top=False)
    # What is out on it.
    for t in things:
        if t == "plants":
            for k, p in enumerate((rail[2], rail[6], rail[10])):
                q = p + (c - p).normalized() * 0.3
                m.cyl("terracotta", q.x, q.y, 0.18, z, z + 0.42, seg=10, r1=0.22)
                for j in range(3):
                    m.cyl("sedum", q.x + 0.04 * (j - 1), q.y, 0.2 - 0.05 * j, z + 0.42 + 0.2 * j, z + 0.68 + 0.2 * j, seg=8, r1=0.12 - 0.03 * j)
        elif t == "chairs":
            q = c + Vector((sx * -0.2, -0.85, 0))
            for k in (-1, 1):
                p = q + Vector((k * 0.45 - sx * 0.6, 0, 0))
                m.box("chair", (p.x - 0.25, p.y - 0.25, z + 0.38), (p.x + 0.25, p.y + 0.25, z + 0.44))
                m.box("chair", (p.x - 0.25, p.y + 0.2, z + 0.44), (p.x + 0.25, p.y + 0.26, z + 0.85))
                for dx in (-0.22, 0.2):
                    for dy in (-0.22, 0.2):
                        m.box("iron", (p.x + dx, p.y + dy, z), (p.x + dx + 0.02, p.y + dy + 0.02, z + 0.38))
        elif t == "parasol":
            q = c + Vector((sx * -0.9, -0.7, 0))
            m.cyl("iron", q.x, q.y, 0.02, z, z + 2.1, seg=6)
            m.cyl("parasol", q.x, q.y, 0.95, z + 1.85, z + 2.2, seg=12, r1=0.04, bottom=True)


# ---- the storeys ------------------------------------------------------------------------------


def storey(M, kind, z0, h):
    m = M.m
    walls = sides(m, W, D)
    ground = kind == "ground"
    c, e = (z0 + 0.95, z0 + 2.45) if ground else (z0 + 0.9, z0 + 2.3)
    # Behind the corner balconies the glass runs down to the floor.
    cc = c if ground else z0 + 0.12
    F = walls["front"]
    holes, wins = [], []
    for a, b in FRONT:
        corner = a == X0 or b == X1
        lo = cc if corner else c
        if ground and corner:
            lo = c
        holes.append((a, b, lo, e))
        wins.append((a, b, lo, e, (a != X0, b != X1)))
    if ground:
        F.wall("render", X0, -TW, z0 + 0.5, z0 + h, [hh for hh in holes if hh[1] < 0], depth=DEPTH)
        F.wall("render", TW, X1, z0 + 0.5, z0 + h, [hh for hh in holes if hh[0] > 0], depth=DEPTH)
    else:
        F.wall("render", X0, -TW, z0, z0 + h, [hh for hh in holes if hh[1] < 0], depth=DEPTH)
        F.wall("render", TW, X1, z0, z0 + h, [hh for hh in holes if hh[0] > 0], depth=DEPTH)
    for a, b, lo, hi, ends in wins:
        steel(F, a, b, lo, hi, ends)
    for name in ("right", "left"):
        S = walls[name]
        sg = -1 if name == "right" else 1  # which end of u is the front corner
        hs = SIDE if sg < 0 else [(-b, -a) for a, b in SIDE]
        sh, sw = [], []
        for a, b in hs:
            corner = abs(a) == D / 2 or abs(b) == D / 2
            lo = cc if corner and not ground else c
            sh.append((a, b, lo, e))
            sw.append((a, b, lo, e, (abs(a) != D / 2, abs(b) != D / 2)))
        S.wall("render", -D / 2, D / 2, z0 + (0.5 if ground else 0.0), z0 + h, sh, depth=DEPTH)
        for a, b, lo, hi, ends in sw:
            steel(S, a, b, lo, hi, ends)
    B = walls["back"]
    bh = [(a, b, c + (0.4 if b - a < 1.6 else 0.0), e) for a, b in BACK]
    if ground:
        bh[2] = (-0.6, 0.6, z0 + 0.15, z0 + 2.3)
    B.wall("render", X0, X1, z0 + (0.5 if ground else 0.0), z0 + h, bh, depth=DEPTH)
    for i, (a, b, cl, el) in enumerate(bh):
        if ground and i == 2:
            B.quad("door", a, b, cl, el, -DEPTH)
            B.box("concrete", a - 0.3, b + 0.3, z0, z0 + 0.15, 0.0, 0.8, skip=("back", "bottom"))
            B.box("trim", a - 0.4, b + 0.4, el + 0.1, el + 0.2, 0.0, 0.7, skip=("back",))
            continue
        steel(B, a, b, cl, el)
    # Three speed lines round the building in the spandrel under the windows, a coping line over.
    for k in range(3):
        zz = z0 + 0.28 + k * 0.16 if not ground else z0 + 0.62 + k * 0.1
        m.sweep("band", W, D, [(-0.01, zz), (0.035, zz), (0.035, zz + 0.05), (-0.01, zz + 0.05)])
    if ground:
        plinth(M, walls)
    tower(M, kind, z0, h)
    if not ground:
        fill = {"floor_a": (("chairs",), ("plants", "parasol")), "floor_b": (("plants",), ("chairs",))}[kind]
        for sx, things in zip((-1, 1), fill):
            corner_balcony(M, sx, z0, things)
        if kind == "floor_a":
            # Eyebrows over the middle windows: thin concrete ledges with a rounded nose.
            for a, b in FRONT[1:3]:
                F.box("trim", a - 0.25, b + 0.25, e + 0.12, e + 0.2, 0.0, 0.55, skip=("back",))
    core(m, z0, z0 + h)
    ceiling(m, z0 + h - 0.01)


def plinth(M, walls):
    """The polished black plinth to 0.5 m round the ground storey, a bronze bead over it."""
    for name, S in walls.items():
        hh = W / 2 if name in ("front", "back") else D / 2
        runs = [(-hh - 0.04, hh + 0.04)]
        if name == "front":
            runs = [(-hh - 0.04, -TW), (TW, hh + 0.04)]
        if name == "back":
            runs = [(-hh - 0.04, -0.6), (0.6, hh + 0.04)]
        for u0, u1 in runs:
            S.box("jet", u0, u1, 0.0, 0.5, -0.01, 0.04, skip=("back", "bottom"))
            S.box("bronze", u0, u1, 0.5, 0.53, -0.01, 0.045, skip=("back", "bottom"))


def tower(M, kind, z0, h):
    """The stair tower's storey: render returns, a full-height strip of glass blocks
    between fins; at the foot, the entrance."""
    m = M.m
    T = Side(m, (0, Y0 - TP, 0), (1, 0, 0), (0, -1, 0))
    ground = kind == "ground"
    gb = (-0.6, 0.6)
    if ground:
        # The entrance: bronze doors in a recess under a rounded canopy.
        a, b, e = -1.0, 1.0, 2.7
        cz = e + 0.75
        lo = cz + 0.25
        T.wall("render", -TW, TW, z0 + 0.5, z0 + h, [(a, b, 0.5, e, 0.7), (gb[0], gb[1], lo, z0 + h)], depth=0.1)
        T.box("jet", -TW - 0.04, a, 0.0, 0.5, 0.0, 0.04, skip=("back", "bottom"))
        T.box("jet", b, TW + 0.04, 0.0, 0.5, 0.0, 0.04, skip=("back", "bottom"))
        T.box("jet", a, b, 0.34, 0.5, 0.0, 0.04, skip=("back", "bottom"))
        T.box("concrete", a - 0.3, b + 0.3, 0.0, 0.17, 0.0, 1.0, skip=("back", "bottom"))
        T.box("concrete", a - 0.15, b + 0.15, 0.17, 0.34, 0.0, 0.6, skip=("back", "bottom"))
        glazing(T, a, b, 0.5, e, lights=3, D=0.7, fr="bronze", glass="doorglass")
        T.box("bronze", -0.05, 0.05, 1.3, 2.0, -0.66, -0.6)
        # The surround: stepped bronze frames, the house number over.
        for k, d in enumerate((0.0, 0.12, 0.24)):
            T.box("bronze", a - 0.08 - d, a - d, 0.5, e + 0.08 + d, 0.0, 0.04 + 0.02 * k)
            T.box("bronze", b + d, b + 0.08 + d, 0.5, e + 0.08 + d, 0.0, 0.04 + 0.02 * k)
            T.box("bronze", a - 0.08 - d, b + 0.08 + d, e + d, e + 0.08 + d, 0.0, 0.04 + 0.02 * k)
        letters(m, "bronze", T, 0.0, e + 0.4, 0.0, "1934", 0.22, depth=0.03)
        # The canopy: a thin slab with a half-round front, a light in its soffit.
        r = 1.1
        pts = [T.p(math.cos(math.pi * k / 12) * r, 0, 0.0 + math.sin(math.pi * k / 12) * r) for k in range(13)]
        for zz, out in ((cz + 0.12, Z), (cz, -Z)):
            m.poly("paint", [Vector((p.x, p.y, zz)) for p in pts], out=out)
        for p0, p1 in zip(pts, pts[1:]):
            mid = (p0 + p1) / 2 - T.p(0, 0, 0)
            mid.z = 0
            m.poly("band", [Vector((p0.x, p0.y, cz)), Vector((p1.x, p1.y, cz)), Vector((p1.x, p1.y, cz + 0.12)), Vector((p0.x, p0.y, cz + 0.12))], out=mid)
        q = T.p(0, 0, 0.7)
        m.cyl("lamp", q.x, q.y, 0.16, cz - 0.02, cz, seg=12, bottom=True)
    else:
        lo = z0
        T.wall("render", -TW, TW, z0, z0 + h, [(gb[0], gb[1], lo, z0 + h)], depth=0.1)
    T.quad("glassblock", gb[0], gb[1], lo, z0 + h, -0.08)
    for u in gb:
        T.box("trim", u - 0.03, u + 0.03, lo, z0 + h, -0.08, 0.02)
    # Fins either side of the strip: three, stepping back from the strip outward.
    for sx in (-1, 1):
        for k, (u, w) in enumerate(((0.78, 0.3), (1.0, 0.22), (1.22, 0.14))):
            T.box("fin", sx * u - 0.05, sx * u + 0.05, z0 + (0.5 if ground else 0.0), z0 + h, 0.0, w, skip=("back", "top", "bottom"))
    # The tower's returns to the front wall.
    for sx, out in ((-1, (-1, 0, 0)), (1, (1, 0, 0))):
        x = sx * TW
        m.poly("render", [(x, Y0 - TP, z0), (x, Y0, z0), (x, Y0, z0 + h), (x, Y0 - TP, z0 + h)], out=out)


def core(m, z0, z1):
    m.box("dark", (X0 + 0.2, Y0 + 0.2, z0), (X1 - 0.2, Y1 - 0.2, z1), skip=("z0", "z1"))


def ceiling(m, z):
    e = 0.02
    m.poly("dark", [(X0 + e, Y0 + e, z), (X1 - e, Y0 + e, z), (X1 - e, Y1 - e, z), (X0 + e, Y1 - e, z)], out=Z)


# ---- the roof -----------------------------------------------------------------------------------


def roof(M, z):
    m = M.m
    # The parapet: render to 0.9 m, a projecting coping, two speed lines.
    PH = 0.9
    m.sweep("render", W, D, [(-0.01, z), (0.0, z), (0.0, z + PH)])
    m.sweep("trim", W, D, [(0.0, z + PH), (0.08, z + PH), (0.08, z + PH + 0.1), (-0.25, z + PH + 0.1)])
    m.sweep("render", W - 0.5, D - 0.5, [(0.0, z + PH + 0.1), (0.0, z + 0.1)])
    for zz in (z + 0.3, z + 0.46):
        m.sweep("band", W, D, [(-0.01, zz), (0.035, zz), (0.035, zz + 0.05), (-0.01, zz + 0.05)])
    zr = z + 0.1
    m.poly("gravel", [(X0 + 0.25, Y0 + 0.25, zr), (X1 - 0.25, Y0 + 0.25, zr), (X1 - 0.25, Y1 - 0.25, zr), (X0 + 0.25, Y1 - 0.25, zr)], out=Z)
    # The corner balconies' last parapet becomes a roof terrace's: tiles and a pergola at each corner.
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (W / 2 - 0.25), sx * (W / 2 - 4.2)))
        m.box("concrete", (x0, Y0 + 0.25, zr), (x1, Y0 + 3.6, zr + 0.04), skip=("z0",))
        for x in (x0 + 0.3, x1 - 0.3):
            for y in (Y0 + 0.6, Y0 + 3.2):
                m.box("trim", (x - 0.07, y - 0.07, zr), (x + 0.07, y + 0.07, zr + 2.4))
        for y in (Y0 + 0.6, Y0 + 3.2):
            m.box("trim", (x0 + 0.15, y - 0.08, zr + 2.4), (x1 - 0.15, y + 0.08, zr + 2.56))
        for k in range(9):
            x = x0 + 0.3 + k * (x1 - x0 - 0.6) / 8
            m.box("trim", (x - 0.04, Y0 + 0.35, zr + 2.56), (x + 0.04, Y0 + 3.45, zr + 2.64))
    # The stair tower: on up through the roof in two steps, glass blocks to the first.
    tower_top(M, z)
    # Vents and a tank housing behind the tower.
    m.box("render", (-2.2, 1.2, zr), (2.2, 3.6, zr + 2.0), skip=("z0",))
    m.box("trim", (-2.3, 1.1, zr + 2.0), (2.3, 3.7, zr + 2.1))
    for x in (-4.6, -3.8, 3.8, 4.6):
        m.cyl("ac", x, 3.8, 0.08, zr, zr + 0.8, seg=8)
        m.cyl("ac", x, 3.8, 0.13, zr + 0.8, zr + 0.9, seg=8)


def tower_top(M, z):
    m = M.m
    T = Side(m, (0, Y0 - TP, 0), (1, 0, 0), (0, -1, 0))
    gb = (-0.6, 0.6)
    s1 = z + 3.2
    T.wall("render", -TW, TW, z, s1, [(gb[0], gb[1], z, s1 - 0.5)], depth=0.1)
    T.quad("glassblock", gb[0], gb[1], z, s1 - 0.5, -0.08)
    for u in gb:
        T.box("trim", u - 0.03, u + 0.03, z, s1 - 0.5, -0.08, 0.02)
    T.box("trim", gb[0] - 0.03, gb[1] + 0.03, s1 - 0.53, s1 - 0.47, -0.08, 0.02)
    for sx in (-1, 1):
        for k, (u, w, hh) in enumerate(((0.78, 0.3, 0.0), (1.0, 0.22, 0.4), (1.22, 0.14, 0.8))):
            T.box("fin", sx * u - 0.05, sx * u + 0.05, z, s1 - hh, 0.0, w, skip=("back", "bottom"))
    # The tower's body behind: back to 4 m into the plan, its sides and back.
    yb = Y0 + 4.0
    for sx in (-1, 1):
        x = sx * TW
        m.poly("render", [(x, Y0 - TP, z), (x, yb, z), (x, yb, s1), (x, Y0 - TP, s1)], out=(sx, 0, 0))
    m.poly("render", [(-TW, yb, z), (TW, yb, z), (TW, yb, s1), (-TW, yb, s1)], out=(0, 1, 0))
    # A door out onto the roof in its back.
    B = Side(m, (0, yb, 0), (-1, 0, 0), (0, 1, 0))
    B.box("door", -0.45, 0.45, z + 0.1, z + 2.2, 0.0, 0.03)
    B.box("trim", -0.65, 0.65, z + 2.3, z + 2.38, 0.0, 0.6)
    # The coping, then a second, narrower step, then a third, then the flagpole.
    steps = ((TW, Y0 - TP, yb, s1, 0.0), (TW - 0.45, Y0 - TP + 0.4, yb - 0.8, s1 + 1.1, 0.0), (TW - 0.9, Y0 - TP + 0.8, yb - 1.6, s1 + 1.9, 0.0))
    for i, (hw, ya, yb_, zz, _) in enumerate(steps):
        m.box("trim", (-hw - 0.08, ya - 0.08, zz), (hw + 0.08, yb_ + 0.08, zz + 0.12))
        if i + 1 < len(steps):
            hw2, ya2, yb2, zz2, _ = steps[i + 1]
            m.box("render", (-hw2, ya2, zz + 0.12), (hw2, yb2, zz2), skip=("z0",))
            for zb in (zz + 0.35, zz + 0.5):
                m.box("band", (-hw2 - 0.03, ya2 - 0.03, zb), (hw2 + 0.03, yb2 + 0.03, zb + 0.05), skip=("z0",))
    hw, ya, yb_, zz, _ = steps[-1]
    fx, fy = 0.0, (ya + yb_) / 2
    m.cyl("trim", fx, fy, 0.05, zz + 0.12, zz + 5.0, seg=8, r1=0.03)
    m.cyl("bronze", fx, fy, 0.08, zz + 5.0, zz + 5.16, seg=10)
