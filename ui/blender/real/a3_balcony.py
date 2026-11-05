# A3, balcony block: a rendered apartment block of the early 1960s, the
# kind built by the thousand in Zurich, Hamburg and the inner suburbs of
# American cities. Two flats a floor either side of the stair. The stair is
# a vertical band up the middle of the front: tall landing windows over
# coloured panels, the entrance at its foot under a thin cantilevered
# canopy, in a recess lined with polished granite, letterboxes and the
# house number beside the glass doors. Either side of it a stack of deep
# cantilevered balconies, one a flat on every floor, their slab edges
# drawing white lines across the front; aluminium-framed rails of frosted
# glass, a coloured panel and sliding doors behind each, roller shutters
# in boxes over the openings, some let down. Planters, chairs, a striped
# sun awning here and there. Smooth render on the walls, a granite plinth.
# The flat roof is a thin slab oversailing the walls and the top
# balconies, gravel on it behind an aluminium coping, the stair's bulkhead
# with a door out, a forest of TV aerials, vents and a boiler flue. The app
# tints the render, the panels, the aluminium and the chairs.
#
# Pieces (base at the origin, stacked by the app):
#   ground   3.2 m: the entrance and the ground-floor flats
#   floor_a, floor_b  2.9 m: typical storeys, each with its row of
#            balconies at its foot; they differ in what is out on the
#            balconies and how far the shutters are down, and alternate
#   roof     the oversailing roof slab and what stands on it
import math

from mathutils import Vector

from lib import Model, Side, Z, aerial, awning, glazing, letters, new_id, pane, sides

ID = "a3"
W, D = 15.0, 11.0  # the walls
BAL = 1.6  # the balconies' reach in front of the wall
OV = 0.3  # the roof slab's overhang at the sides and back
Y0 = (BAL + 0.1 - D - OV) / 2  # front wall: the footprint (roof edge to roof edge) is centred
Y1 = Y0 + D
CY = (Y0 + Y1) / 2
X0, X1 = -W / 2, W / 2
G = 3.2  # ground storey
FL = 2.9  # typical storeys
STOREYS = ("floor_a", "floor_b")  # the reference stack
DEPTH = 0.16  # glass depth in the walls
STAIR = 1.35  # the stair band's half width
STACKS = ((-7.3, -1.55), (1.55, 7.3))  # the balconies, left and right
SLAB = 0.18  # balcony slab thickness
HEAD = 2.2  # door and window heads above the floor
BOX = 0.24  # roller-shutter boxes over them
ROOF = 0.42  # the roof slab's depth
ENTRY = (-1.15, 1.15, 0.3, 2.65, 1.1)  # the entrance recess: a, b, floor, head, depth


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    for f, kind in enumerate(STOREYS):
        z = G + f * FL
        M.piece(kind, (0, 0, z))
        storey(M, kind, z)
    top = G + len(STOREYS) * FL
    M.piece("roof", (0, 0, top))
    roof(M, top)
    M.export(out, bake)


# ---- openings ---------------------------------------------------------------------


def roller(F, a, b, e, down):
    """A roller-shutter box over an opening (a..b, head e) and its blind, let down `down` of the way to h."""
    F.box("alu", a, b, e - 0.02, e + 0.02, -DEPTH + 0.06, 0.0, skip=("back",))
    if down > 0.02:
        h = down
        F.quad("roller", a + 0.02, b - 0.02, e - h, e, -0.07, uvs=[(0, 0), (b - a, 0), (b - a, h), (0, h)])
        F.box("alu", a + 0.02, b - 0.02, e - h - 0.03, e - h, -0.09, -0.05, skip=())
        for u in (a + 0.01, b - 0.03):
            F.box("alu", u, u + 0.02, e - h, e, -0.1, -0.05)


def window(F, a, b, c, e, down=0.0, lights=2, panel=True, sill=True):
    """A window in an aluminium frame, a coloured panel under it from the floor line if `panel`,
    a shutter box over it; c is the sill, e the head."""
    glazing(F, a, b, c, e, lights=lights, D=DEPTH)
    if sill:
        F.box("alu", a - 0.04, b + 0.04, c - 0.04, c + 0.01, -DEPTH + 0.04, 0.05)
    roller(F, a, b, e, down)


def slider(F, a, b, c, e, down=0.0):
    """Sliding doors onto a balcony: two leaves, a fixed light at the side, a shutter box over."""
    glazing(F, a, b, c, e, lights=3, D=DEPTH, slide=True)
    F.box("alu", a, b, c, c + 0.03, -DEPTH - 0.02, 0.02)
    roller(F, a, b, e, down)


# ---- the front ---------------------------------------------------------------------


def front_holes(z0, ground_=False):
    """The front's openings in a storey from z0: per balcony a sliding door, a window
    over a coloured panel; the stair band's landing window; their (a, b, c, e)."""
    holes = []
    for xa, xb in STACKS:
        left = xa < 0
        # Living room (sliding doors, or a window at ground level) on the stair side, bedroom outboard.
        d0, d1 = (xb - 3.3, xb - 0.35) if left else (xa + 0.35, xa + 3.3)
        w0, w1 = (xa + 0.35, xa + 1.75) if left else (xb - 1.75, xb - 0.35)
        if ground_:
            holes.append((d0, d1, 1.0, 0.6 + HEAD, "window"))
            holes.append((w0, w1, 0.5, 0.6 + HEAD, "panel"))
        else:
            holes.append((d0, d1, z0, z0 + HEAD, "slider"))
            holes.append((w0, w1, z0 + 0.1, z0 + HEAD, "panel"))
    return holes


def front(M, F, z0, h, ground_=False, downs=()):
    """A storey of the front from z0, h tall: render either side of the stair band
    with the openings, and the band: the entrance in granite at the foot, a tall
    landing window between coloured panels on every floor above."""
    z1 = z0 + h
    holes = front_holes(z0, ground_)
    for u0, u1 in ((X0, -STAIR), (STAIR, X1)):
        F.wall("render", u0, u1, z0, z1, [hh[:4] for hh in holes if u0 <= hh[0] and hh[1] <= u1], depth=DEPTH)
    for i, (a, b, c, e, kind) in enumerate(holes):
        down = downs[i] if i < len(downs) else 0.0
        if kind == "slider":
            slider(F, a, b, c, e, down)
        elif kind == "window":
            window(F, a, b, c, e, down, lights=3)
        else:
            # The coloured panel and the window over it in one frame.
            mid = c + (0.5 if ground_ else 0.8)
            F.quad("infill", a, b, c, mid - 0.03, -DEPTH + 0.02)
            F.box("alu", a, b, mid - 0.04, mid + 0.02, -DEPTH - 0.02, -DEPTH + 0.05)
            for u in (a, b - 0.05):
                F.box("alu", u, u + 0.05, c, mid, -DEPTH - 0.02, -DEPTH + 0.05)
            F.box("alu", a, b, c, c + 0.05, -DEPTH - 0.02, -DEPTH + 0.05)
            glazing(F, a, b, mid, e, lights=2, D=DEPTH)
            roller(F, a, b, e, down)
    if ground_:
        F.wall("granite", -STAIR, STAIR, z0, z1, [ENTRY], depth=DEPTH)
        return
    a, b, c, e = -0.8, 0.8, z0 + 0.45, z0 + 2.55
    F.wall("render", -STAIR, STAIR, z0, z1, [(a, b, z0, z1)], depth=0.06)
    F.quad("infill", a, b, z0, c, -0.04)
    F.quad("infill", a, b, e, z1, -0.04)
    glazing(F, a, b, c, e, lights=3, D=0.08, glass="doorglass")
    F.box("alu", a, b, c - 0.04, c + 0.01, -0.08, 0.03)
    for u in (a - 0.06, b):
        F.box("alu", u, u + 0.06, z0, z1, 0.0, 0.03, skip=("back", "top", "bottom"))
    # A white fin each side of the band, standing proud of the render.
    for u in (-STAIR, STAIR - 0.12):
        F.box("paint", u, u + 0.12, z0, z1, 0.0, 0.16, skip=("back", "top", "bottom"))


def balcony(M, F, xa, xb, z, things, awn=False):
    """A cantilevered balcony from xa to xb at floor level z: the slab with a white edge
    and a drip, a tiled top, a frosted-glass rail in an aluminium frame round it, and
    what is out on it (`things`: "chairs", "planters", "table", "dryer", "bike")."""
    m, R = M.m, M.R
    p = F.p
    w1 = BAL
    # The slab: top, edge band, soffit.
    F.box("concrete", xa, xb, z - 0.02, z + 0.02, 0.0, w1 - 0.02, skip=("back", "bottom"))
    F.box("paint", xa - 0.02, xb + 0.02, z - SLAB, z - 0.02, 0.0, w1, skip=("back",))
    F.box("paint", xa - 0.02, xb + 0.02, z - SLAB - 0.03, z - SLAB, w1 - 0.06, w1, skip=("back", "top"))
    # The rail: posts, a bottom rail, a handrail, frosted glass between.
    rz0, rz1 = z + 0.08, z + 1.0
    wr = w1 - 0.08
    posts = []
    n = max(2, round((xb - xa) / 1.45))
    for i in range(n + 1):
        posts.append(xa + 0.04 + i * (xb - xa - 0.08) / n)
    for u in posts:
        F.box("alu", u - 0.025, u + 0.025, z + 0.02, rz1, wr - 0.025, wr + 0.025, skip=("back", "bottom"))
    for wa in (0.78,):
        for u in (xa + 0.04, xb - 0.04):
            F.box("alu", u - 0.025, u + 0.025, z + 0.02, rz1, wa - 0.025, wa + 0.025, skip=("bottom",))
    # Handrail and the bottom channel, front and returns.
    F.box("alu", xa + 0.01, xb - 0.01, rz1, rz1 + 0.05, wr - 0.04, wr + 0.04, skip=())
    F.box("alu", xa + 0.04, xb - 0.04, z + 0.02, rz0, wr - 0.02, wr + 0.02, skip=("bottom",))
    for u in (xa + 0.04, xb - 0.04):
        F.box("alu", u - 0.035, u + 0.035, rz1, rz1 + 0.05, 0.0, wr - 0.04, skip=("back",))
        F.box("alu", u - 0.02, u + 0.02, z + 0.02, rz0, 0.0, wr - 0.02, skip=("back", "bottom"))
    for u0, u1 in zip(posts, posts[1:]):
        F.box("railglass", u0 + 0.03, u1 - 0.03, rz0, rz1 - 0.02, wr - 0.006, wr + 0.006, skip=("top", "bottom", "left", "right"))
    for u in (xa + 0.04, xb - 0.04):
        s = 1 if u > 0 else -1
        S = Side(m, p(u, 0, 0), F.n, F.t * s)
        S.box("railglass", 0.03, wr - 0.03, rz0, rz1 - 0.02, -0.006, 0.006, skip=("top", "bottom", "left", "right"))
    # The drip's shadow line under the slab edge is in the AO; a downpipe stub at the outer end.
    outer = xa if xa < 0 else xb
    sx = 1 if outer > 0 else -1
    F.box("alu", outer - sx * 0.3 - 0.03, outer - sx * 0.3 + 0.03, z - SLAB - 0.15, z - SLAB, w1 - 0.25, w1 - 0.19, skip=())
    c = (xa + xb) / 2
    left = xa < 0
    for t in things:
        if t == "planters":
            # Planter troughs on the rail's bottom channel, sedum and herbs in them.
            for k in range(2):
                u = xa + 0.4 + k * 0.95 if left else xb - 1.3 - k * 0.95
                F.box("terracotta", u, u + 0.8, z + 0.02, z + 0.32, wr - 0.33, wr - 0.06, skip=("bottom",))
                F.box("sedum", u + 0.03, u + 0.77, z + 0.32, z + 0.4, wr - 0.3, wr - 0.09, skip=("bottom",))
        elif t == "chairs":
            for k, (u, rot) in enumerate(((c - 0.75, 1), (c + 0.55, -1))):
                chair(F, u, z, 0.7 + 0.1 * k)
        elif t == "table":
            u = c - 0.1
            F.box("iron", u - 0.02, u + 0.02, z + 0.02, z + 0.7, 0.68, 0.72, skip=("bottom",))
            m.cyl("alu", *p(u, 0, 0.7).xy, 0.32, z + 0.7, z + 0.73, seg=16, bottom=True)
            m.cyl("iron", *p(u, 0, 0.7).xy, 0.22, z + 0.02, z + 0.04, seg=12)
        elif t == "dryer":
            # A folding clothes airer with towels on it, by the wall.
            u = xb - 0.9 if left else xa + 0.2
            for uu in (u, u + 0.7):
                F.box("alu", uu, uu + 0.02, z + 0.02, z + 0.95, 0.35, 0.37)
                F.box("alu", uu, uu + 0.02, z + 0.02, z + 0.95, 0.85, 0.87)
            F.box("alu", u, u + 0.72, z + 0.93, z + 0.95, 0.35, 0.87)
            for k, wv in enumerate((0.45, 0.6, 0.75)):
                F.box("awning" if k != 1 else "infill", u + 0.06, u + 0.66, z + 0.55 + 0.06 * k, z + 0.95, wv, wv + 0.012, skip=())
        elif t == "plant":
            # A big pot with a shrub in it in the corner.
            u = xa + 0.35 if left else xb - 0.35
            q = p(u, 0, 0.35)
            m.cyl("terracotta", q.x, q.y, 0.2, z + 0.02, z + 0.42, seg=12, r1=0.25)
            m.cyl("sedum", q.x, q.y, 0.24, z + 0.42, z + 0.44, seg=12)
            for k in range(3):
                o = Vector((R.uniform(-0.06, 0.06), R.uniform(-0.06, 0.06), 0))
                m.cyl("sedum", q.x + o.x, q.y + o.y, 0.22 - 0.05 * k, z + 0.44 + 0.25 * k, z + 0.72 + 0.25 * k, seg=8, r1=0.14 - 0.04 * k)
    if awn:
        awning(F, xa + 0.2, xb - 0.2, z + HEAD + BOX + 0.08, drop=0.55, depth=BAL - 0.15)


def chair(F, u, z, w):
    """A stacking chair, seat and back in colour on a steel frame, facing the street."""
    F.box("chair", u - 0.22, u + 0.22, z + 0.42, z + 0.46, w - 0.2, w + 0.22, skip=())
    F.box("chair", u - 0.22, u + 0.22, z + 0.48, z + 0.86, w - 0.24, w - 0.2, skip=())
    for uu in (u - 0.2, u + 0.18):
        for ww in (w - 0.2, w + 0.18):
            F.box("iron", uu, uu + 0.02, z + 0.02, z + 0.42, ww, ww + 0.02, skip=("bottom", "top"))


# ---- sides and back ------------------------------------------------------------------

# The back's windows per flat (left half; mirrored): kitchen, bathroom, bedroom.
BACK = [(-6.6, -5.2, 0.95), (-4.3, -3.1, 1.0), (-2.3, -1.7, 1.45)]


def back(M, B, z0, h, door=False, downs=()):
    """A storey of the back: per flat a kitchen, a bathroom and a bedroom window;
    the stair's landing window in the middle, or the back door at the foot."""
    holes = [(a, b, z0 + c, z0 + HEAD + 0.05, "small" if b - a < 0.7 else "window") for a, b, c in BACK]
    holes += [(-b, -a, c, e, k) for a, b, c, e, k in holes]
    holes.append((-0.6, 0.6, 0.15, 2.3, "door") if door else (-0.6, 0.6, z0 + 1.6, z0 + 2.75, "stair"))
    B.wall("render", -W / 2, W / 2, z0, z0 + h, [hh[:4] for hh in holes], depth=DEPTH)
    i = 0
    for a, b, c, e, kind in holes:
        if kind == "window":
            window(B, a, b, c, e, downs[i % len(downs)] if downs else 0.0, lights=2)
            i += 1
            continue
        glazing(B, a, b, c, e, lights=1, D=DEPTH, glass="glass" if kind == "small" else "doorglass")
        if kind == "door":
            B.box("concrete", a - 0.3, b + 0.3, 0.0, 0.15, 0.0, 0.9, skip=("back", "bottom"))
            B.box("paint", a - 0.5, b + 0.5, e + 0.15, e + 0.27, 0.0, 0.9, skip=("back",))
            B.box("alu", b - 0.12, b - 0.09, c + 0.8, c + 1.3, -DEPTH + 0.05, -DEPTH + 0.1)
        else:
            B.box("alu", a - 0.03, b + 0.03, c - 0.04, c + 0.01, -DEPTH + 0.04, 0.05)


def ends(M, walls, z0, h):
    """The end walls: render, a small window towards each end (kitchen and hall)."""
    for name in ("left", "right"):
        S = walls[name]
        holes = [(-3.4, -2.6, z0 + 1.2, z0 + HEAD), (2.6, 3.4, z0 + 1.2, z0 + HEAD)]
        S.wall("render", -D / 2, D / 2, z0, z0 + h, holes, depth=DEPTH)
        for a, b, c, e in holes:
            glazing(S, a, b, c, e, lights=1, D=DEPTH)
            S.box("alu", a - 0.03, b + 0.03, c - 0.04, c + 0.01, -DEPTH + 0.04, 0.05)


# ---- the ground storey ------------------------------------------------------------------


def ground(M):
    m = M.m
    walls = sides(m, W, D, cy=CY)
    F = walls["front"]
    # A polished granite plinth all round, the render stopping on an aluminium bead above it; gaps for the doors.
    for name, S in walls.items():
        h = W / 2 if name in ("front", "back") else D / 2
        gap = {"front": (ENTRY[0], ENTRY[1]), "back": (-0.6, 0.6)}.get(name)
        runs = [(-h - 0.03, gap[0]), (gap[1], h + 0.03)] if gap else [(-h - 0.03, h + 0.03)]
        for u0, u1 in runs:
            S.box("granite", u0, u1, 0.0, 0.42, 0.0, 0.03, skip=("back", "bottom"))
            S.box("alu", u0, u1, 0.42, 0.45, 0.0, 0.015, skip=("back", "bottom"))
    front(M, F, 0.0, G, ground_=True, downs=(0.0, 0.35, 0.9, 0.0))
    entrance(M, F)
    back(M, walls["back"], 0.0, G, door=True, downs=(0.0, 0.5, 0.0, 0.2))
    ends(M, walls, 0.0, G)
    core(m, 0.0, G)
    ceiling(m, G - 0.01)


def entrance(M, F):
    """The entrance at the foot of the stair band: a recess lined with granite, glass
    doors with side lights, letterboxes, a thin canopy with downlights, steps, the number."""
    m = M.m
    a, b, c, e, d = ENTRY
    glazing(F, a, b, c, e, lights=3, D=d, glass="doorglass")
    for u in (-0.38, 0.38):
        F.box("brass", u - 0.02, u + 0.02, c + 0.7, c + 1.5, -d + 0.05, -d + 0.1)
    # Letterboxes on the recess wall, two rows of six.
    for i in range(6):
        for j in range(2):
            w, z = -d + 0.12 + i * 0.13, c + 1.0 + j * 0.24
            q0 = F.p(b, z, w)
            m.box("alu", (q0.x - 0.08, q0.y - 0.06, z), (q0.x, q0.y + 0.06, z + 0.21))
            m.box("dark", (q0.x - 0.085, q0.y - 0.04, z + 0.15), (q0.x - 0.079, q0.y + 0.04, z + 0.17))
    # The bell panel on the other side.
    q = F.p(a, c + 1.2, -0.3)
    m.box("alu", (q.x, q.y - 0.12, q.z), (q.x + 0.03, q.y + 0.12, q.z + 0.45))
    # The canopy: a thin slab out over the steps, downlights under it.
    F.box("paint", -1.9, 1.9, e + 0.08, e + 0.2, 0.0, 1.45, skip=("back",))
    F.box("alu", -1.92, 1.92, e + 0.2, e + 0.24, 1.38, 1.47, skip=("back", "bottom"))
    for u in (-0.9, 0.9):
        q = F.p(u, 0, 0.75)
        m.cyl("lamp", q.x, q.y, 0.09, e + 0.065, e + 0.08, seg=12, bottom=True)
    # Two steps up to the recess.
    F.box("concrete", -1.5, 1.5, 0.0, 0.15, 0.0, 0.7, skip=("back", "bottom"))
    F.box("concrete", -1.3, 1.3, 0.15, 0.3, 0.0, 0.35, skip=("back", "bottom"))
    # The house number in brass over the canopy.
    letters(m, "brass", F, 0.0, e + 0.42, 0.0, "14", 0.34, depth=0.03)


def core(m, z0, z1):
    """A dark box inside the storey's walls, so hairline cracks where wall faces meet
    show dark, not the sky through the building (in front, behind the entrance recess)."""
    m.box("dark", (X0 + 0.25, Y0 + 1.25, z0), (X1 - 0.25, Y1 - 0.25, z1), skip=("z0", "z1"))


def ceiling(m, z):
    """A dark ceiling over a storey, seen only when what is above has gone."""
    e = 0.02
    m.poly("dark", [(X0 + e, Y0 + e, z), (X1 - e, Y0 + e, z), (X1 - e, Y1 - e, z), (X0 + e, Y1 - e, z)], out=Z)


# ---- typical storeys ----------------------------------------------------------------------


def storey(M, kind, z0):
    m, R = M.m, M.R
    walls = sides(m, W, D, cy=CY)
    F = walls["front"]
    if kind == "floor_a":
        downs = (0.0, 0.0, 0.0, 0.55)
        fill = (("chairs", "planters", "table"), ("dryer", "plant"))
        awns = (False, False)
        bdowns = (0.0, 0.6, 0.0, 0.3)
    else:
        downs = (0.9, 0.3, 0.0, 0.0)
        fill = (("plant",), ("chairs", "planters"))
        awns = (False, True)
        bdowns = (0.4, 0.0, 0.85, 0.0)
    front(M, F, z0, FL, downs=downs)
    for (xa, xb), things, awn in zip(STACKS, fill, awns):
        balcony(M, F, xa, xb, z0, things, awn)
    back(M, walls["back"], z0, FL, downs=bdowns)
    ends(M, walls, z0, FL)
    # A dish on the rail of one balcony in floor_a.
    if kind == "floor_a":
        dish(m, F.p(STACKS[1][1] - 0.4, z0 + 1.05, BAL - 0.08))
    core(m, z0, z0 + FL)
    ceiling(m, z0 + FL - 0.01)


def dish(m, q):
    """A satellite dish clamped to the handrail, looking south-west and up."""
    x, y, z = q
    m.box("iron", (x - 0.02, y - 0.02, z - 0.1), (x + 0.02, y + 0.02, z + 0.35))
    # The dish: a shallow cone of a few facets, tilted by drawing it as a fan.
    c = Vector((x, y - 0.12, z + 0.45))
    n = Vector((0.0, -0.8, 0.45)).normalized()
    t1 = n.cross(Z).normalized()
    t2 = n.cross(t1).normalized()
    rim = [c + (t1 * math.cos(i / 12 * math.tau) + t2 * math.sin(i / 12 * math.tau)) * 0.3 for i in range(12)]
    apex = c - n * 0.08
    for i in range(12):
        m.poly("ac", [apex, rim[i], rim[(i + 1) % 12]], out=n)
        m.poly("ac", [apex - n * 0.01, rim[(i + 1) % 12] - n * 0.01, rim[i] - n * 0.01], out=-n)
    m.strut("iron", c - n * 0.06, c + n * 0.3, 0.015)
    lnb = c + n * 0.3
    m.box("dark", tuple(lnb - Vector((0.03, 0.03, 0.03))), tuple(lnb + Vector((0.03, 0.03, 0.03))))


# ---- roof ------------------------------------------------------------------------------------


def roof(M, z):
    m = M.m
    # The roof slab oversailing the walls, and over the top balconies to their edge.
    xa, xb = X0 - OV, X1 + OV
    ya, yb = Y0 - BAL - 0.1, Y1 + OV
    zt = z + ROOF
    m.box("paint", (xa, ya, z), (xb, yb, zt - 0.12), skip=("z1",))
    m.box("alu", (xa - 0.02, ya - 0.02, zt - 0.12), (xb + 0.02, yb + 0.02, zt + 0.05), skip=("z0", "z1"))
    # Gravel inside the coping's upstand.
    m.poly("gravel", [(xa + 0.12, ya + 0.12, zt), (xb - 0.12, ya + 0.12, zt), (xb - 0.12, yb - 0.12, zt), (xa + 0.12, yb - 0.12, zt)], out=Z)
    for (x0, y0, x1, y1) in ((xa, ya, xb, ya + 0.12), (xa, yb - 0.12, xb, yb), (xa, ya, xa + 0.12, yb), (xb - 0.12, ya, xb, yb)):
        m.poly("alu", [(x0, y0, zt + 0.05), (x1, y0, zt + 0.05), (x1, y1, zt + 0.05), (x0, y1, zt + 0.05)], out=Z)
    zr = zt
    # The stair's bulkhead behind the band: render, a flat lid, a door out onto the roof.
    bx, by0, by1 = 1.6, Y0 + 0.3, Y0 + 4.2
    bh = 2.4
    S = sides(m, 2 * bx, by1 - by0, 0.0, (by0 + by1) / 2)
    for name, F in S.items():
        h = bx if name in ("front", "back") else (by1 - by0) / 2
        holes = []
        if name == "back":
            holes = [(-0.45, 0.45, zr + 0.15, zr + 2.15)]
        if name == "front":
            holes = [(-0.9, 0.9, zr + 1.3, zr + 2.0)]
        F.wall("render", -h, h, zr, zr + bh, holes, depth=0.12)
        for a, b, c, e in holes:
            if name == "back":
                F.quad("ac", a + 0.04, b - 0.04, c, e - 0.04, -0.1)
                F.box("alu", a, b, e - 0.04, e, -0.12, -0.06)
                for u in (a, b - 0.04):
                    F.box("alu", u, u + 0.04, c, e, -0.12, -0.06)
                F.box("dark", a + 0.62, a + 0.72, c + 1.0, c + 1.04, -0.1, -0.06)
                F.box("concrete", a - 0.2, b + 0.2, zr, zr + 0.12, 0.0, 0.6, skip=("back", "bottom"))
            else:
                glazing(F, a, b, c, e, lights=3, D=0.1, glass="doorglass")
    m.box("paint", (-bx - 0.15, by0 - 0.15, zr + bh), (bx + 0.15, by1 + 0.15, zr + bh + 0.2))
    m.box("alu", (-bx - 0.17, by0 - 0.17, zr + bh + 0.2), (bx + 0.17, by1 + 0.17, zr + bh + 0.25), skip=("z0",))
    # The lift's motor room vent and a lamp over the roof door.
    m.box("blades", (-0.5, by1 + 0.0, zr + 2.2), (0.5, by1 + 0.02, zr + 2.32))
    m.cyl("lamp", 0.0, by1 + 0.08, 0.06, zr + 2.18, zr + 2.24, seg=8, bottom=True)
    # TV aerials on short masts in tripods, one a flat, crowded on the roof.
    spots = [(-5.8, Y0 + 2.0), (-3.4, Y1 - 2.0), (-1.0, Y1 - 1.0), (2.8, Y0 + 3.0), (4.9, Y1 - 2.6), (6.2, Y0 + 1.6)]
    for i, (x, y) in enumerate(spots):
        h = 2.2 + 0.35 * (i % 3)
        for k in range(3):
            a = k / 3 * math.tau + i
            m.strut("iron", Vector((x + math.cos(a) * 0.45, y + math.sin(a) * 0.45, zr)), Vector((x + 0.02, y, zr + 0.9)), 0.02)
        aerial(m, x - 0.025, y, zr + h - 1.0)
        if h > 2.4:
            m.box("iron", (x - 0.025, y - 0.025, zr), (x + 0.025, y + 0.025, zr + h - 2.4))
    # Soil vent pipes over the bathrooms and the boiler's flue in the middle of the back.
    for x in (-3.7, 3.7, -1.9, 1.9):
        m.cyl("iron", x, Y1 - 1.8, 0.055, zr, zr + 0.7, seg=8)
        m.cyl("iron", x, Y1 - 1.8, 0.08, zr + 0.7, zr + 0.78, seg=8, r1=0.04)
    fx, fy = 0.0, Y1 - 1.6
    m.box("render", (fx - 0.45, fy - 0.35, zr), (fx + 0.45, fy + 0.35, zr + 1.5), skip=("z0",))
    m.box("paint", (fx - 0.5, fy - 0.4, zr + 1.5), (fx + 0.5, fy + 0.4, zr + 1.58))
    for x in (fx - 0.18, fx + 0.18):
        m.cyl("steel", x, fy, 0.1, zr + 1.58, zr + 2.4, seg=10)
        m.cyl("steel", x, fy, 0.16, zr + 2.4, zr + 2.46, seg=10)
        m.cyl("steel", x, fy, 0.16, zr + 2.56, zr + 2.62, seg=10, r1=0.03)
        for k in range(3):
            a = k / 3 * math.tau
            m.strut("steel", Vector((x + math.cos(a) * 0.1, fy + math.sin(a) * 0.1, zr + 2.46)), Vector((x + math.cos(a) * 0.1, fy + math.sin(a) * 0.1, zr + 2.56)), 0.015)
    # Rooflights over the stairs' top flight, and a hatch for the lift.
    for x in (-4.8, 4.8):
        m.box("concrete", (x - 0.55, CY - 0.55, zr), (x + 0.55, CY + 0.55, zr + 0.25), skip=("z0",))
        m.box("skyglass", (x - 0.5, CY - 0.5, zr + 0.25), (x + 0.5, CY + 0.5, zr + 0.45), skip=("z0",))
    # A walkway of concrete pavers from the door to the aerials and the flue.
    for i in range(6):
        y = by1 + 0.7 + i * 0.62
        if y > Y1 - 0.6:
            break
        m.box("concrete", (-0.3, y - 0.28, zr), (0.3, y + 0.28, zr + 0.04), skip=("z0",))
