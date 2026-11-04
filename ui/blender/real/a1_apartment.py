# A1, pre-war brick apartment block (the prototype): storeys of brick with
# stone trim and sash windows over a rusticated ground storey with two shops
# and the residents' entrance, balconies on the front, a fire escape on the
# right, a bracketed cornice, and a water tank on the roof.
#
# Pieces (base at the origin, stacked by the app):
#   ground   4.5 m: shops, entrance, plinth, string course
#   first    3.1 m: the first upper storey, pedimented window heads, the
#            fire escape's drop ladder
#   floor_a, floor_b  3.1 m: typical storeys with the front balcony; they
#            differ in their air conditioners and alternate up the stack
#   last     3.1 m: the top storey, no balcony, no stairs up
#   roof     frieze, cornice, parapet, roof with bulkhead, tank and plant
import random

from mathutils import Vector

from lib import Model, Side, Z, ac_unit, awning, balcony, french, grille, hood, lintel, new_id, pane, railing, sash, shopfront, sides, sill

ID = "a1"
W, D = 14.0, 12.0
G = 4.5  # ground storey
FL = 3.1  # upper storeys
PLINTH = 0.45
BAYS = {"front": [-5.2, -2.6, 0.0, 2.6, 5.2], "back": [-5.2, -2.6, 0.0, 2.6, 5.2], "right": [-4.2, -1.4, 1.4, 4.2], "left": [-4.2, -1.4, 1.4, 4.2]}
HALF = {"front": W / 2, "back": W / 2, "right": D / 2, "left": D / 2}
STOREYS = ("first", "floor_a", "floor_b", "last")  # the reference stack


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    for f, kind in enumerate(STOREYS):
        z = G + f * FL
        M.piece(kind, (0, 0, z))
        storey(M, kind, z, f)
    top = G + len(STOREYS) * FL
    M.piece("roof", (0, 0, top))
    roof(M, top)
    M.export(out, bake)


def ground(M):
    m, cut = M.m, M.cut
    m.sweep("granite", W, D, [(0.06, 0.0), (0.06, PLINTH - 0.04), (0.02, PLINTH), (-0.01, PLINTH)])
    m.sweep("stone", W, D, [(-0.01, G - 0.12), (0.05, G - 0.12), (0.05, G), (0.12, G + 0.06), (0.12, G + 0.2), (0.07, G + 0.24), (0.04, G + 0.3), (-0.01, G + 0.3)])
    for name, F in sides(m, W, D).items():
        h = HALF[name]
        if name == "front":
            shops = [(-6.3, -2.1), (2.1, 6.3)]
            entry = (-0.95, 0.95)
            holes = [(a, b, PLINTH, 3.45) for a, b in shops] + [(entry[0], entry[1], PLINTH, 3.3, 1.0)]
            F.wall("ashlar", -h, h, PLINTH, G, holes, depth=0.3, reveal="stone")
            for i, (a, b) in enumerate(shops):
                shopfront(F, a, b, PLINTH, 3.45, sign=i, door_left=i == 1)
            awning(F, shops[0][0] - 0.1, shops[0][1] + 0.1, 3.5)
            entrance(F, *entry)
        else:
            holes = [(u - 0.6, u + 0.6, 1.4, 3.3) for u in BAYS[name]]
            F.wall("ashlar", -h, h, PLINTH, G, holes, depth=0.3, reveal="stone")
            for a, b, c, e in holes:
                sash(F, a, b, c, e, D=0.3)
                F.box("stone", a - 0.08, b + 0.08, c - 0.08, c + 0.015, -0.26, 0.07)
                grille(F, a, b, c, e)


def storey(M, kind, z, f):
    """One upper storey from z: brick with quoins, sash windows, trim, a landing of the fire escape."""
    m, cut = M.m, M.cut
    R = random.Random(f * 31 + 7)
    ww, wh, sh = 1.3, 1.8, 0.9
    balc = kind in ("floor_a", "floor_b")
    for name, F in sides(m, W, D).items():
        h = HALF[name]
        holes, kinds = [], []
        for u in BAYS[name]:
            b = balc and name == "front" and u == 0.0
            holes.append((u - 0.7, u + 0.7, z + 0.05, z + 2.5) if b else (u - ww / 2, u + ww / 2, z + sh, z + sh + wh))
            kinds.append((u, b))
        F.wall("brick", -h, h, z, z + FL, holes, depth=0.22)
        for (a, b, c, e), (u, bal) in zip(holes, kinds):
            if bal:
                french(F, a, b, c, e)
                balcony(F, cut, u, c - 0.05)
                lintel(F, a, b, e)
                continue
            sash(F, a, b, c, e)
            sill(F, a, b, c)
            if kind == "first" and name != "back":
                hood(F, a, b, e)
            else:
                lintel(F, a, b, e, key_=name != "back")
            if name in ("left", "back") and R.random() < 0.22 and kind != "last":
                ac_unit(F, u, c)
        # Quoins: eight courses a storey, long and short in turn.
        q = FL / 8
        for i in range(8):
            z0 = z + i * q
            L = 0.62 if i % 2 == 0 else 0.36
            F.box("stone", -h, -h + L, z0 + 0.012, z0 + q - 0.012, 0, 0.025, skip=("back", "left"))
            F.box("stone", h - L, h, z0 + 0.012, z0 + q - 0.012, 0, 0.025, skip=("back", "right"))
    fire_escape(sides(m, W, D)["right"], cut, z, f, stairs=kind != "last", ladder=kind == "first")


def entrance(F, a, b):
    """The residents' door: recessed, with a fanlight, a stone surround and a glass canopy."""
    D_ = 1.0
    c, e = PLINTH, 3.3
    F.box("granite", a, b, c - 0.01, c, -D_, 0, skip=())
    F.box("granite", a - 0.4, b + 0.4, 0, 0.15, 0, 0.75, skip=("back",))
    F.box("granite", a - 0.3, b + 0.3, 0.15, 0.3, 0, 0.45, skip=("back",))
    F.box("granite", a - 0.2, b + 0.2, 0.3, PLINTH, 0, 0.15, skip=("back",))
    F.quad("stone", a, b, c, e, -D_)
    dr = "door"
    wid = new_id()
    da, db = a + 0.12, b - 0.12
    t = 2.65
    F.box(dr, da - 0.08, db + 0.08, c, t + 0.08, -D_, -D_ + 0.08)
    m = (da + db) / 2
    for l0, l1 in ((da, m - 0.005), (m + 0.005, db)):
        F.box(dr, l0, l1, c, t, -D_, -D_ + 0.13)
        pane(F, "doorglass", a, b, c, e, l0 + 0.12, l1 - 0.12, c + 1.0, t - 0.15, -D_ + 0.135, wid)
        F.box("dark", l0 + 0.1, l1 - 0.1, c + 0.25, c + 0.8, -D_ + 0.13, -D_ + 0.14)
    F.box("brass", m - 0.12, m - 0.04, 1.4, 1.48, -D_ + 0.13, -D_ + 0.18)
    F.box("brass", m + 0.04, m + 0.12, 1.4, 1.48, -D_ + 0.13, -D_ + 0.18)
    pane(F, "doorglass", a, b, c, e, da, db, t + 0.08, e - 0.05, -D_ + 0.04, wid)
    for i in range(1, 6):
        u = da + i * (db - da) / 6
        F.box(dr, u - 0.015, u + 0.015, t + 0.08, e - 0.05, -D_ + 0.04, -D_ + 0.07)
    for u0, u1 in ((a - 0.35, a), (b, b + 0.35)):
        F.box("stone", u0, u1, PLINTH, e + 0.05, 0, 0.1)
        F.box("stone", u0 - 0.04, u1 + 0.04, PLINTH, PLINTH + 0.3, 0, 0.14)
    F.box("stone", a - 0.42, b + 0.42, e + 0.05, e + 0.45, 0, 0.12)
    F.box("stone", a - 0.5, b + 0.5, e + 0.45, e + 0.55, 0, 0.22)
    F.box("iron", a - 0.6, b + 0.6, e + 0.6, e + 0.68, 0, 1.3, skip=())
    F.box("canopy", a - 0.55, b + 0.55, e + 0.68, e + 0.7, 0.05, 1.25, skip=())
    p = F.p
    for u in (a - 0.5, b + 0.5):
        F.m.strut("iron", p(u, e + 1.6, 0.0), p(u, e + 0.7, 1.25), 0.025)
    for u in (a - 0.6, b + 0.6):
        F.box("iron", u - 0.06, u + 0.06, 2.0, 2.06, 0, 0.18)
        F.box("lamp", u - 0.07, u + 0.07, 2.06, 2.32, 0.11, 0.25, skip=())
        F.box("iron", u - 0.09, u + 0.09, 2.32, 2.36, 0.09, 0.27, skip=())
    F.box("brass", b + 0.42, b + 0.62, 2.0, 2.2, 0.0, 0.02)


def fire_escape(F, cut, z0, f, stairs, ladder):
    """The landing at the storey from z0, stairs up to the next (alternating), the drop ladder below the first."""
    u0, u1 = -2.5, 2.5
    w = 1.05
    z = z0 + 0.75
    for out in (Z, -Z):
        cut.poly("grate", [F.p(u0, z, 0.02), F.p(u1, z, 0.02), F.p(u1, z, w), F.p(u0, z, w)], out=out, uvs=[(0, 0), (5, 0), (5, w), (0, w)])
    F.box("iron", u0, u1, z - 0.1, z, w - 0.04, w, skip=())
    F.box("iron", u0, u1, z - 0.1, z, 0.0, 0.04, skip=())
    for u in (u0, u1):
        F.box("iron", u - 0.02, u + 0.02, z - 0.1, z, 0.0, w, skip=())
        F.m.strut("iron", F.p(u, z - 0.9, 0.0), F.p(u, z - 0.05, w - 0.05), 0.04)
    railing(F, cut, u0, u1, z, 0.02, w)
    if stairs:
        s0, s1 = (u0 + 0.5, u1 - 0.9) if f % 2 == 0 else (u1 - 0.5, u0 + 0.9)
        zt = z + FL
        wa, wb = 0.1, 0.65
        for wq in (wa, wb):
            F.m.strut("iron", F.p(s0, z, wq), F.p(s1, zt, wq), 0.05, 0.16)
            F.m.strut("iron", F.p(s0, z + 0.85, wq), F.p(s1, zt + 0.85, wq), 0.035)
        steps = 15
        for i in range(1, steps):
            k = i / steps
            us, zs = s0 + (s1 - s0) * k, z + (zt - z) * k
            F.box("iron", us - 0.1, us + 0.1, zs - 0.02, zs, wa + 0.02, wb - 0.02, skip=())
    if ladder:
        for wq in (0.35, 0.75):
            F.m.strut("iron", F.p(u1 - 0.4, z, wq), F.p(u1 - 0.4, 2.6, wq), 0.04)
        for i in range(int((z - 2.6) / 0.3)):
            zz = 2.7 + i * 0.3
            F.m.strut("iron", F.p(u1 - 0.4, zz, 0.35), F.p(u1 - 0.4, zz, 0.75), 0.025)


def roof(M, TOP):
    """Frieze, cornice and parapet from TOP, then the roof and what stands on it."""
    m = M.m
    m.sweep("stone", W, D, [(-0.01, TOP), (0.06, TOP), (0.06, TOP + 0.22), (0.03, TOP + 0.26), (-0.01, TOP + 0.26)])
    cz = TOP + 0.95  # cornice soffit
    m.sweep("stone", W, D, [(-0.01, cz - 0.2), (0.1, cz - 0.2), (0.1, cz - 0.1), (0.16, cz - 0.04), (0.18, cz), (0.62, cz), (0.66, cz + 0.06), (0.66, cz + 0.2), (0.74, cz + 0.28), (0.76, cz + 0.36), (0.6, cz + 0.4), (-0.01, cz + 0.42)])
    PT = cz + 0.42  # parapet base
    PH = 0.9
    m.sweep("stone", W, D, [(-0.31, PT + PH - 0.02), (-0.36, PT + PH - 0.02), (-0.36, PT + PH + 0.12), (0.05, PT + PH + 0.12), (0.05, PT + PH - 0.02), (-0.01, PT + PH - 0.02)])
    for name, F in sides(m, W, D).items():
        h = HALF[name]
        F.wall("brick", -h, h, TOP, PT, [])
        for i in range(int((2 * h) / 0.22)):
            u = -h + 0.11 + i * 0.22
            F.box("stone", u - 0.06, u + 0.06, cz - 0.36, cz - 0.2, 0, 0.09)
        n = int((2 * h) / 0.75)
        for i in range(n + 1):
            u = -h + 0.35 + i * (2 * h - 0.7) / n
            F.box("stone", u - 0.08, u + 0.08, cz - 0.1, cz, 0.08, 0.58)
            F.box("stone", u - 0.08, u + 0.08, cz - 0.22, cz - 0.1, 0.08, 0.2)
        F.wall("brick", -h, h, PT, PT + PH, [])
        F.quad("brick", h - 0.3, -h + 0.3, PT, PT + PH, -0.3, out=-F.n)
    z = PT - 0.05
    m.poly("roof", [(-W / 2 + 0.3, -D / 2 + 0.3, z), (W / 2 - 0.3, -D / 2 + 0.3, z), (W / 2 - 0.3, D / 2 - 0.3, z), (-W / 2 + 0.3, D / 2 - 0.3, z)], out=Z)
    # Stair bulkhead with a door.
    bx0, bx1, by0, by1 = -5.6, -2.2, 1.6, 5.4
    h = 2.7
    for name, F in {
        "f": Side(m, ((bx0 + bx1) / 2, by0, z), (1, 0, 0), (0, -1, 0)),
        "r": Side(m, (bx1, (by0 + by1) / 2, z), (0, 1, 0), (1, 0, 0)),
        "b": Side(m, ((bx0 + bx1) / 2, by1, z), (-1, 0, 0), (0, 1, 0)),
        "l": Side(m, (bx0, (by0 + by1) / 2, z), (0, -1, 0), (-1, 0, 0)),
    }.items():
        L = (bx1 - bx0) / 2 if name in "fb" else (by1 - by0) / 2
        holes = [(-0.5, 0.5, 0.0, 2.1)] if name == "f" else []
        F.wall("brick", -L, L, 0, h, holes, depth=0.12)
        if holes:
            F.quad("door", -0.5, 0.5, 0, 2.1, -0.12)
            F.box("iron", -0.62, 0.62, 2.1, 2.2, 0, 0.6, skip=())
    m.sweep("stone", bx1 - bx0, by1 - by0, [(-0.01, z + h), (0.06, z + h), (0.06, z + h + 0.12), (-0.01, z + h + 0.12)], cx=(bx0 + bx1) / 2, cy=(by0 + by1) / 2)
    m.poly("roof", [(bx0 + 0.05, by0 + 0.05, z + h + 0.1), (bx1 - 0.05, by0 + 0.05, z + h + 0.1), (bx1 - 0.05, by1 - 0.05, z + h + 0.1), (bx0 + 0.05, by1 - 0.05, z + h + 0.1)], out=Z)
    # Water tank on a steel stand.
    tx, ty, tr = 3.4, 2.4, 1.45
    legs = 2.4
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = tx + dx * tr * 0.72, ty + dy * tr * 0.72
        m.box("steel", (x - 0.08, y - 0.08, z), (x + 0.08, y + 0.08, z + legs))
    for (dx0, dy0), (dx1, dy1) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
        a = Vector((tx + dx0 * tr * 0.72, ty + dy0 * tr * 0.72, z + 0.3))
        b = Vector((tx + dx1 * tr * 0.72, ty + dy1 * tr * 0.72, z + legs - 0.2))
        m.strut("steel", a, b, 0.04)
        m.strut("steel", Vector((a.x, a.y, b.z)), Vector((b.x, b.y, a.z)), 0.04)
    m.box("steel", (tx - tr - 0.1, ty - tr - 0.1, z + legs), (tx + tr + 0.1, ty + tr + 0.1, z + legs + 0.15))
    t0, t1 = z + legs + 0.15, z + legs + 2.75
    m.cyl("wood", tx, ty, tr, t0, t1, seg=32, top=False, uv=True)
    m.cyl("wood", tx, ty, tr, t1, t1 + 0.75, seg=32, r1=0.12, uv=True)
    m.cyl("steel", tx, ty, 0.14, t1 + 0.7, t1 + 0.95, seg=8, r1=0.0)
    for k in range(5):
        hz = t0 + 0.3 + k * 0.52
        m.cyl("steel", tx, ty, tr + 0.025, hz, hz + 0.05, seg=32, top=False)
    m.strut("steel", (tx + tr + 0.15, ty, z + 0.2), (tx + tr + 0.15, ty, t1 + 0.1), 0.04)
    # Rooftop plant: two condensers and vents.
    for x, y in ((-0.5, -3.6), (2.3, -3.6)):
        m.box("ac", (x - 0.9, y - 0.6, z), (x + 0.9, y + 0.6, z + 1.1))
        m.cyl("dark", x - 0.42, y, 0.36, z + 1.1, z + 1.13, seg=16)
        m.cyl("dark", x + 0.42, y, 0.36, z + 1.1, z + 1.13, seg=16)
        m.box("concrete", (x - 1.0, y - 0.7, z), (x + 1.0, y + 0.7, z + 0.12))
    for x, y, hh in ((0.6, 4.6, 1.2), (1.4, 4.9, 0.9), (-1.0, 0.0, 0.8), (5.6, -1.4, 1.0)):
        m.cyl("ac", x, y, 0.08, z, z + hh, seg=10)
        m.cyl("ac", x, y, 0.13, z + hh, z + hh + 0.12, seg=10)
    # Chimney stacks on the party walls.
    for x in (-3.5, 3.0):
        y = D / 2 - 0.15
        m.box("brick", (x - 0.55, y - 0.5, z), (x + 0.55, y + 0.1, z + 2.2))
        m.sweep("stone", 1.1, 0.6, [(-0.01, z + 2.2), (0.06, z + 2.2), (0.06, z + 2.32), (-0.01, z + 2.32)], cx=x, cy=y - 0.2)
        m.poly("stone", [(x - 0.56, y - 0.51, z + 2.32), (x + 0.56, y - 0.51, z + 2.32), (x + 0.56, y + 0.11, z + 2.32), (x - 0.56, y + 0.11, z + 2.32)], out=Z)
        for k in (-0.25, 0.25):
            m.cyl("terracotta", x + k, y - 0.2, 0.11, z + 2.32, z + 2.7, seg=10, r1=0.09)
