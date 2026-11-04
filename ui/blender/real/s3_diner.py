# S3, diner: a 1950s factory-built diner, long side to the street. A body of
# fluted stainless steel with rounded ends, two bands of coloured porcelain
# enamel along it, a continuous band of windows (a booth behind each; glass
# block round the corners), an enamel frieze carrying the diner's name, and a
# barrel roof that curves down over the ends too. A projecting vestibule
# with glass-block sides and a stainless door, steps with pipe rails; a
# box sign on the roof with channel letters trimmed in neon; a brick kitchen
# behind with its exhaust fan; and a roadside pylon at the lot's corner with
# EAT down a blade, an arrow of bulbs pointing in, and a neon star on top.
# The app picks the enamel colour, the neon colours and the name.
#
# Pieces (base at the origin):
#   body  the diner to the top of its frieze, vestibule, steps, the kitchen's
#         walls, the pylon
#   roof  eaves and barrel roof, the roof sign and vents, the kitchen roof
import math

from lib import Model, Side, Z, letters, neon, new_id, pane, sides
from mathutils import Vector

ID = "s3"
L, D, R = 13.6, 5.0, 1.1  # the body: length, depth and plan radius of its rounded corners
CY = -0.7  # the body's centre; vestibule and steps in front, kitchen behind keep the footprint centred
YF, YB = CY - D / 2, CY + D / 2  # front and back of the body
XS, YS = L / 2 - R, D / 2 - R  # half-lengths of the straight runs, front and ends
FLR = 0.75  # the diner's floor
WB, WT = 1.66, 2.76  # the window band
TOP = 3.36  # top of the frieze trim: the roof piece's base
EAVE, OV, RISE = 3.5, 0.28, 0.55  # top of the fascia, the eaves' overhang, the barrel's rise
VW, VD, VR = 1.2, 1.1, 0.3  # vestibule: half-width, depth, corner radius
YV = YF - VD  # its front
VT = 2.7  # its window band's head
DOOR = (-0.5, 0.5)
KW, KD, KH = 3.6, 3.4, 3.15  # the kitchen: half-width, depth, wall height
YK = YB + KD
PX, PY = 6.1, -6.6  # the pylon
MULL = [1.35 + i * (5.62 - 1.35) / 3 for i in range(4)]  # mullion centres on each half of the front
BAND = [  # (o, z) profile of the skin from the plinth to the sill, by role
    ("concrete", [(-0.08, 0.0), (-0.08, 0.26)]),
    ("stainless", [(-0.08, 0.25), (0.02, 0.25), (0.02, 0.4), (0.0, 0.42)]),
    ("fluted", [(0.0, 0.42), (0.0, 0.88)]),
    ("enamel", [(0.0, 0.88), (0.012, 0.88), (0.012, 0.96), (0.0, 0.96)]),
    ("fluted", [(0.0, 0.96), (0.0, 1.46)]),
    ("enamel", [(0.0, 1.46), (0.015, 1.46), (0.015, 1.6)]),
    ("stainless", [(0.015, 1.6), (0.07, 1.61), (0.07, 1.64), (-0.03, WB)]),
]


def build(out, bake=True):
    M = Model(ID)
    M.sharp = math.radians(40)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, TOP))
    roof(M)
    M.export(out, bake)


# ---- paths and sweeps -------------------------------------------------------------------


def arc(cx, cy, r, a0, a1, seg):
    """Points and outward normals round an arc, angles in degrees."""
    out = []
    for i in range(seg + 1):
        a = math.radians(a0 + (a1 - a0) * i / seg)
        n = Vector((math.cos(a), math.sin(a), 0))
        out.append((Vector((cx, cy, 0)) + n * r, n))
    return out


def ring(o, seg=8):
    """The body's plan offset o outward (negative: inward), anticlockwise from the
    front's right end: (point, normal) pairs, four arcs joined by the straights.
    Corners stay rounded as the outline shrinks, down to a radius of 2 cm."""
    r = max(R + o, 0.02)
    cx, cy = L / 2 + o - r, D / 2 + o - r
    pts = []
    for (sx, sy), a0 in (((1, -1), -90), ((1, 1), 0), ((-1, 1), 90), ((-1, -1), 180)):
        pts += arc(sx * cx, CY + sy * cy, r, a0, a0 + 90, seg)
    return pts


def vestibule_path():
    """The vestibule's walls from the body on its left round to the body on its right,
    with the door's jambs as vertices of their own."""
    pts = [(Vector((-VW, YF, 0)), Vector((-1, 0, 0)))]
    pts += arc(-VW + VR, YV + VR, VR, 180, 270, 4)
    pts += [(Vector((DOOR[0] - 0.06, YV, 0)), Vector((0, -1, 0))), (Vector((DOOR[1] + 0.06, YV, 0)), Vector((0, -1, 0)))]
    pts += arc(VW - VR, YV + VR, VR, 270, 360, 4)
    pts.append((Vector((VW, YF, 0)), Vector((1, 0, 0))))
    return pts


def sweep(m, role, path, profile, closed=True, skip=(), z0=0.0):
    """Sweeps (offset, z) points along a path of (point, normal); segments in `skip` are left out."""
    n = len(path)
    for (o0, za), (o1, zb) in zip(profile, profile[1:]):
        for i in range(n if closed else n - 1):
            if i in skip:
                continue
            (p0, n0), (p1, n1) = path[i], path[(i + 1) % n]
            if (p1 - p0).length < 1e-6:
                continue
            nm = (n0 + n1).normalized()
            out = nm * (zb - za) - Z * (o1 - o0)
            if out.length < 1e-6:
                continue
            pts = [p0 + n0 * o0 + Z * (za + z0), p1 + n1 * o0 + Z * (za + z0), p1 + n1 * o1 + Z * (zb + z0), p0 + n0 * o1 + Z * (zb + z0)]
            m.poly(role, pts, out=out, smooth=True)


def blocks(m, path, i0, i1, z0, z1, o=-0.03):
    """Glass block between path vertices i0 and i1, UVs along the wall in metres."""
    s = 0.0
    for i in range(i0, i1):
        (p0, n0), (p1, n1) = path[i], path[i + 1]
        a, b = p0 + n0 * o, p1 + n1 * o
        ds = (b - a).length
        if ds < 1e-6:
            continue
        m.poly("glassblock", [a + Z * z0, b + Z * z0, b + Z * z1, a + Z * z1], out=n0 + n1, uvs=[(s, z0), (s + ds, z0), (s + ds, z1), (s, z1)], smooth=True)
        s += ds


def window(F, a, b, c=WB, e=WT):
    """A fixed light between two mullions, a booth behind it, a vent light at the top."""
    wid = new_id()
    F.box("stainless", a, b, c, c + 0.05, -0.09, -0.03)
    F.box("stainless", a, b, e - 0.05, e, -0.09, -0.03)
    F.box("stainless", a, b, e - 0.33, e - 0.29, -0.085, -0.05)
    pane(F, "dinerglass", a, b, c + 0.05, e - 0.05, a, b, c + 0.05, e - 0.05, -0.07, wid)


def mullion(F, u, c=WB, e=WT):
    F.box("stainless", u - 0.04, u + 0.04, c, e, -0.09, 0.02)


def panel(F, u0, u1, c=WB, e=WT, role="fluted"):
    F.quad(role, u0, u1, c, e, -0.03)


def zroof(y):
    """Height of the barrel roof at distance y (from the body's centre line) across it."""
    S = D / 2 + OV
    rb = (S * S + RISE * RISE) / (2 * RISE)
    return EAVE + math.sqrt(max(rb * rb - y * y, 0.0)) - (rb - RISE)


# ---- body ------------------------------------------------------------------------------


def body(M):
    m = M.m
    path = ring(0.0)
    k = len(path) // 4  # points per corner: corner c runs path[c*k .. c*k + k-1], the straights between
    for role, prof in BAND:
        sweep(m, role, path, prof)
    for role, prof in (("stainless", [(-0.03, WT), (0.035, WT), (0.035, WT + 0.06), (0.0, WT + 0.06)]),
                       ("enamel", [(0.0, WT + 0.06), (0.0, 3.3)]),
                       ("stainless", [(0.0, 3.3), (0.045, 3.3), (0.045, TOP)])):
        sweep(m, role, path, prof)
    for c in range(4):
        blocks(m, path, c * k, c * k + k - 1, WB, WT)
    # The front: three booths' windows either side of the vestibule.
    F = Side(m, (0, YF, 0), (1, 0, 0), (0, -1, 0))
    for s in (-1, 1):
        us = [s * u for u in MULL]
        for u in us:
            mullion(F, u)
        for u0, u1 in zip(us, us[1:]):
            window(F, min(u0, u1) + 0.04, max(u0, u1) - 0.04)
        panel(F, *sorted((s * VW, s * (MULL[0] - 0.04))))
        panel(F, *sorted((s * (MULL[-1] + 0.04), s * XS)))
    # The ends: one wide window each.
    for sx in (1, -1):
        E = Side(m, (sx * L / 2, CY, 0), (0, sx, 0), (sx, 0, 0))
        for u in (-0.79, 0.79):
            mullion(E, u)
        window(E, -0.75, 0.75)
        panel(E, -YS, -0.83)
        panel(E, 0.83, YS)
    # The back, behind the back bar: plain.
    Bk = Side(m, (0, YB, 0), (-1, 0, 0), (0, 1, 0))
    panel(Bk, -XS, XS)
    # The frieze carries the name (the app picks it), a decal so the bake leaves the enamel alone.
    F.quad("dinername", -3.2, 3.2, WT + 0.1, WT + 0.5, 0.004, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    # A ceiling, seen when the roof has gone.
    m.poly("dark", [p + n * -0.05 + Z * (TOP - 0.02) for p, n in ring(0.0)], out=Z)
    vestibule(m)
    kitchen(m)
    pylon(m)


def vestibule(m):
    path = vestibule_path()
    door = next(i for i, (p, n) in enumerate(path) if abs(p.x - (DOOR[0] - 0.06)) < 1e-6)
    # The door cuts the skin from the floor up; the plinth and kick run under it.
    for i, (role, prof) in enumerate(BAND):
        sweep(m, role, path, prof, closed=False, skip=(door,) if i >= 2 else ())
    F = Side(m, (0, YV, 0), (1, 0, 0), (0, -1, 0))
    a, b = DOOR
    F.quad("fluted", a - 0.06, b + 0.06, 0.42, FLR)
    # Glass block all round the band but the door; a stainless head over it all.
    blocks(m, path, 0, door, WB, VT)
    blocks(m, path, door + 1, len(path) - 1, WB, VT)
    sweep(m, "stainless", path, [(-0.03, VT), (0.03, VT), (0.03, VT + 0.06)], closed=False)
    # The canopy: soffit, an enamel fascia and a flat top.
    sweep(m, "stainless", path, [(0.03, VT + 0.06), (0.25, VT + 0.06)], closed=False)
    sweep(m, "enamel", path, [(0.25, VT + 0.06), (0.25, VT + 0.22)], closed=False)
    sweep(m, "stainless", path, [(0.25, VT + 0.22), (0.27, VT + 0.22), (0.27, VT + 0.25)], closed=False)
    m.poly("roof", [p + n * 0.27 + Z * (VT + 0.25) for p, n in path], out=Z)
    # The door: stainless jambs and head, a glazed leaf with a fluted kick plate and a push bar.
    F.box("stainless", a - 0.06, a, FLR, VT, -0.1, 0.02)
    F.box("stainless", b, b + 0.06, FLR, VT, -0.1, 0.02)
    F.box("stainless", a - 0.06, b + 0.06, WB, VT, -0.1, -0.03, skip=("front", "back", "left", "right", "top"))
    F.box("stainless", a - 0.06, b + 0.06, FLR - 0.02, FLR + 0.02, -0.12, 0.04, skip=())
    F.quad("dark", a, b, FLR, VT, -0.1)
    lw = -0.07
    F.box("stainless", a, a + 0.09, FLR + 0.02, VT - 0.03, lw - 0.02, lw + 0.02)
    F.box("stainless", b - 0.09, b, FLR + 0.02, VT - 0.03, lw - 0.02, lw + 0.02)
    F.box("stainless", a + 0.09, b - 0.09, VT - 0.12, VT - 0.03, lw - 0.02, lw + 0.02)
    F.box("fluted", a + 0.09, b - 0.09, FLR + 0.02, FLR + 0.4, lw - 0.02, lw + 0.02)
    pane(F, "doorglass", a, b, FLR, VT, a + 0.09, b - 0.09, FLR + 0.4, VT - 0.12, lw, new_id())
    m.tube("stainless", [F.p(a + 0.14, 1.72, lw + 0.08), F.p(b - 0.14, 1.72, lw + 0.08)], 0.016, Z, closed=False)
    for u in (a + 0.16, b - 0.16):
        m.tube("stainless", [F.p(u, 1.72, lw + 0.02), F.p(u, 1.72, lw + 0.08)], 0.012, F.t, closed=False)
    # Steps up to the door, with pipe rails, and a mat-well landing.
    for k in range(3):
        F.box("stone", -VW + 0.15, VW - 0.15, 0, FLR - 0.1875 * (k + 1), 0, 0.3 * (k + 1), skip=("back", "bottom"))
    for x in (-VW + 0.22, VW - 0.22):
        m.tube("stainless", [(x, YV - 0.85, 0.2), (x, YV - 0.85, 1.12), (x, YV - 0.12, 1.6), (x, YV - 0.12, FLR + 0.1)], 0.02, (1, 0, 0), closed=False)
    # A lamp either side of the door.
    for u in (a - 0.32, b + 0.32):
        F.box("stainless", u - 0.05, u + 0.05, 2.2, 2.26, 0, 0.12)
        m.cyl("lamp", F.p(u, 0, 0.17).x, F.p(u, 0, 0.17).y, 0.07, 2.1, 2.36, seg=8, bottom=True)


def kitchen(m):
    """The kitchen behind: brick, a back door on a stoop, a frosted window, a louvred vent."""
    walls = sides(m, 2 * KW, KD, cy=(YB + YK) / 2)
    Bk = walls["back"]
    door = (0.9, 1.9)
    win = (-2.3, -1.2)
    Bk.wall("brick", -KW, KW, 0, KH, [(*door, FLR, 2.85, 0.15), (*win, 1.55, 2.45, 0.2)], depth=0.2, reveal="concrete")
    a, b = door
    Bk.quad("door", a, b, FLR, 2.85, -0.15)
    for u in (a + 0.12, b - 0.12):
        Bk.box("door", u - 0.06, u + 0.06, FLR, 2.85, -0.15, -0.13)
    Bk.box("stainless", b - 0.2, b - 0.12, 1.75, 1.8, -0.15, -0.09)
    Bk.box("stainless", a + 0.15, b - 0.15, FLR + 0.05, FLR + 0.35, -0.15, -0.14)
    Bk.box("concrete", a - 0.4, b + 0.4, 0, FLR - 0.03, 0, 1.0, skip=("back", "bottom"))
    Bk.box("concrete", a - 0.2, b + 0.2, 0, (FLR - 0.03) / 2, 1.0, 1.3, skip=("back", "bottom"))
    Bk.box("iron", a - 0.3, b + 0.3, 3.0, 3.05, 0, 0.8, skip=())
    Bk.box("lamp", b + 0.2, b + 0.34, 2.55, 2.75, 0, 0.12)
    a, b = win
    Bk.quad("skyglass", a, b, 1.55, 2.45, -0.12)
    Bk.box("stainless", a, b, 1.55, 1.6, -0.2, -0.1)
    Bk.box("concrete", a - 0.06, b + 0.06, 1.48, 1.55, -0.2, 0.05)
    for i in range(6):
        u = a + 0.08 + i * (b - a - 0.16) / 5
        Bk.box("iron", u - 0.012, u + 0.012, 1.58, 2.42, 0.01, 0.04)
    for name in ("right", "left"):
        S = walls[name]
        S.wall("brick", -KD / 2, KD / 2, 0, KH, [])
    R_ = walls["right"]
    R_.box("stainless", -0.5, 0.5, 2.0, 2.7, 0, 0.06)
    for i in range(6):
        z = 2.08 + i * 0.1
        R_.box("dark", -0.42, 0.42, z, z + 0.05, 0.06, 0.065, skip=("back",))
        R_.box("stainless", -0.42, 0.42, z + 0.05, z + 0.08, 0.04, 0.1)
    walls["left"].box("ac", 0.6, 1.1, 1.3, 1.9, 0, 0.18)
    walls["left"].box("dark", 0.65, 1.05, 1.55, 1.75, 0.18, 0.185, skip=("back",))
    # Downpipe and the parapet's coping.
    m.box("gutter", (KW - 0.4, YK + 0.02, 0.05), (KW - 0.3, YK + 0.12, KH))
    for name, F in walls.items():
        if name != "front":
            h = KW if name == "back" else KD / 2
            F.box("stone", -h - 0.04, h + 0.04, KH, KH + 0.07, -0.26, 0.04, skip=())
    m.box("concrete", (-KW - 0.05, YB, 0), (KW + 0.05, YK + 0.05, 0.22), skip=("y0", "z0"))


def pylon(m):
    """The roadside sign: a pole on a base, an arrow of bulbs pointing in, EAT down a blade, a star."""
    m.cyl("concrete", PX, PY, 0.35, 0, 0.35, seg=12)
    m.cyl("iron", PX, PY, 0.11, 0.35, 4.2, seg=10)
    # The arrow, edge-on to the street, pointing to the diner (+y), on both faces.
    t = 0.08
    shape = [(-1.3, 3.25), (0.6, 3.25), (0.6, 3.0), (1.35, 3.5), (0.6, 4.0), (0.6, 3.75), (-1.3, 3.75)]
    for sx in (1, -1):
        m.poly("cream", [(PX + sx * t, PY + y, z) for y, z in shape], out=(sx, 0, 0))
    for (y0, z0), (y1, z1) in zip(shape, shape[1:] + shape[:1]):
        m.poly("enamel", [(PX - t, PY + y0, z0), (PX + t, PY + y0, z0), (PX + t, PY + y1, z1), (PX - t, PY + y1, z1)], out=(0, z1 - z0, -(y1 - y0)))
    for sx in (1, -1):
        for i in range(9):
            y = -1.15 + i * 0.2
            bulb(m, PX + sx * t, PY + y, 3.5, sx)
        for y, z in ((0.75, 3.5), (0.95, 3.5), (1.15, 3.5), (0.75, 3.25), (0.75, 3.75)):
            bulb(m, PX + sx * t, PY + y, z, sx)
    # The blade: enamel, stainless edges, EAT in channel letters and neon on both faces, a neon border.
    z0, z1, hw = 4.1, 6.7, 0.5
    m.box("enamel", (PX - 0.15, PY - hw, z0), (PX + 0.15, PY + hw, z1))
    for y0, y1, za, zb in ((-hw - 0.03, -hw + 0.03, z0, z1), (hw - 0.03, hw + 0.03, z0, z1), (-hw - 0.03, hw + 0.03, z1, z1 + 0.06), (-hw - 0.03, hw + 0.03, z0 - 0.06, z0)):
        m.box("stainless", (PX - 0.17, PY + y0, za), (PX + 0.17, PY + y1, zb))
    for sx in (1, -1):
        F = Side(m, (PX + sx * 0.15, PY, 0), (0, sx, 0), (sx, 0, 0))
        for ch, z in zip("EAT", (6.2, 5.4, 4.6)):
            letters(m, "cream", F, 0, z, 0, ch, 0.95, depth=0.06, offset=0.01)
            neon(m, "neon", F, 0, z, 0.075, ch, 0.95, r=0.011, inset=0.035, offset=0.01)
        rect = [(-hw + 0.1, z0 + 0.1), (hw - 0.1, z0 + 0.1), (hw - 0.1, z1 - 0.1), (-hw + 0.1, z1 - 0.1)]
        m.tube("neon2", [F.p(u, z, 0.04) for u, z in rect], 0.01, F.n, seg=5)
        for u, z in rect:
            F.box("iron", u - 0.01, u + 0.01, z - 0.01, z + 0.01, 0, 0.035)
    # The star on top, on a stub.
    m.cyl("iron", PX, PY, 0.04, z1 + 0.06, z1 + 0.25, seg=8)
    sc = Vector((PX, PY, z1 + 0.65))
    star = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r_ = 0.45 if i % 2 == 0 else 0.19
        star.append(Vector((0, math.cos(a) * r_, math.sin(a) * r_)))
    th = 0.05
    for sx in (1, -1):
        m.poly("cream", [sc + Vector((sx * th, p.y, p.z)) for p in star], out=(sx, 0, 0))
        m.tube("neon2", [sc + Vector((sx * (th + 0.02), p.y * 0.86, p.z * 0.86)) for p in star], 0.01, (1, 0, 0), seg=5)
    for p, q in zip(star, star[1:] + star[:1]):
        e = q - p
        m.poly("enamel", [sc + Vector((-th, p.y, p.z)), sc + Vector((th, p.y, p.z)), sc + Vector((th, q.y, q.z)), sc + Vector((-th, q.y, q.z))], out=(0, e.z, -e.y))


def bulb(m, x, y, z, sx):
    """A lamp bulb on a sign face, pointing along x (sx): a low six-sided dome."""
    ax = Vector((sx, 0, 0))
    c = Vector((x, y, z))
    ring_ = [Vector((0, math.cos(a) * 0.032, math.sin(a) * 0.032)) for a in (i / 6 * math.tau for i in range(6))]
    tip = c + ax * 0.06
    for p, q in zip(ring_, ring_[1:] + ring_[:1]):
        m.poly("bulb", [c + p, c + q, c + ax * 0.03 + q * 0.9, c + ax * 0.03 + p * 0.9], out=(p + q) / 2)
        m.poly("bulb", [c + ax * 0.03 + p * 0.9, c + ax * 0.03 + q * 0.9, tip], out=(p + q) / 2 + ax * 0.03)


# ---- roof ------------------------------------------------------------------------------


def roof(M):
    m = M.m
    path = ring(0.0)
    sweep(m, "stainless", path, [(0.0, TOP), (OV + 0.02, TOP), (OV + 0.02, EAVE), (OV, EAVE)])
    # The barrel: rings shrinking inward, rising on the arc; the ends curve down like the sides.
    S = D / 2 + OV
    ds = [0.0, 0.2, 0.45, 0.75, 1.1, 1.5, 1.95, 2.4, S - 0.12]
    rings = [[(p, zroof(S - d)) for p, n in ring(OV - d)] for d in ds]
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(len(r0)):
            j = (i + 1) % len(r0)
            pts = [r0[i][0] + Z * r0[i][1], r0[j][0] + Z * r0[j][1], r1[j][0] + Z * r1[j][1], r1[i][0] + Z * r1[i][1]]
            if (pts[0] - pts[1]).length < 1e-5 and (pts[2] - pts[3]).length < 1e-5:
                continue
            m.poly("roof", pts, out=Z, smooth=True)
    m.poly("roof", [p + Z * z for p, z in rings[-1]], out=Z, smooth=True)
    # Mushroom vents on the crown.
    for x in (-3.6, 3.4):
        zc = zroof(0.0)
        m.cyl("stainless", x, CY, 0.11, zc - 0.05, zc + 0.3, seg=10)
        m.cyl("stainless", x, CY, 0.24, zc + 0.3, zc + 0.36, seg=12, r1=0.2)
        m.cyl("stainless", x, CY, 0.2, zc + 0.36, zc + 0.44, seg=12, r1=0.04)
    sign(m)
    kitchen_roof(m)


def sign(m):
    """The roof sign: a box of enamel with a stainless frame, DINER in cream channel
    letters trimmed with neon, a neon border, on posts braced back to the roof."""
    ys = YF + 1.15
    F = Side(m, (0, ys, 0), (1, 0, 0), (0, -1, 0))
    hw, z0, z1 = 2.9, 4.2, 5.4
    F.box("enamel", -hw, hw, z0, z1, -0.24, 0, skip=())
    for u0, u1, za, zb in ((-hw - 0.04, -hw + 0.04, z0 - 0.04, z1 + 0.04), (hw - 0.04, hw + 0.04, z0 - 0.04, z1 + 0.04),
                           (-hw, hw, z1 - 0.04, z1 + 0.04), (-hw, hw, z0 - 0.04, z0 + 0.04)):
        F.box("stainless", u0, u1, za, zb, -0.26, 0.03, skip=())
    zc = (z0 + z1) / 2
    letters(m, "cream", F, 0, zc, 0, "DINER", 1.05, depth=0.08, offset=0.014, spacing=1.12)
    neon(m, "neon", F, 0, zc, 0.095, "DINER", 1.05, r=0.012, inset=0.04, offset=0.014, spacing=1.12)
    rect = [(-hw + 0.14, z0 + 0.12), (hw - 0.14, z0 + 0.12), (hw - 0.14, z1 - 0.12), (-hw + 0.14, z1 - 0.12)]
    m.tube("neon2", [F.p(u, z, 0.05) for u, z in rect], 0.011, F.n, seg=5)
    for u, z in rect:
        F.box("iron", u - 0.012, u + 0.012, z - 0.012, z + 0.012, 0, 0.045)
    # Posts down to the roof, braced back.
    for x in (-1.9, 1.9):
        y = ys + 0.12
        m.strut("iron", (x, y, zroof(y - CY) - 0.05), (x, y, z1 - 0.1), 0.08)
        y2 = ys + 1.3
        m.strut("iron", (x, y + 0.04, z1 - 0.2), (x, y2, zroof(y2 - CY) - 0.03), 0.05)
        m.box("iron", (x - 0.12, y - 0.12, zroof(y - CY) - 0.05), (x + 0.12, y + 0.12, zroof(y - CY) + 0.04))


def kitchen_roof(m):
    """The kitchen's roof inside its parapet: deck, the exhaust fan on its curb, a condenser and vent pipes."""
    deck = KH - 0.2
    x0, x1, y0, y1 = -KW + 0.22, KW - 0.22, YB + 0.05, YK - 0.22
    m.poly("roof", [(x0, y0, deck), (x1, y0, deck), (x1, y1, deck), (x0, y1, deck)], out=Z)
    walls = sides(m, 2 * KW, KD, cy=(YB + YK) / 2)
    for name, F in walls.items():
        if name == "front":
            continue
        h = KW if name == "back" else KD / 2
        F.quad("brick", h - 0.22, -h + 0.22, deck, KH, -0.22, out=-F.n)
    fx, fy = -1.2, YB + 1.6
    m.box("galv", (fx - 0.5, fy - 0.5, deck), (fx + 0.5, fy + 0.5, deck + 0.35))
    m.cyl("galv", fx, fy, 0.34, deck + 0.35, deck + 0.7, seg=14)
    m.cyl("galv", fx, fy, 0.56, deck + 0.7, deck + 0.82, seg=16, r1=0.5)
    m.cyl("galv", fx, fy, 0.5, deck + 0.82, deck + 0.98, seg=16, r1=0.1)
    ax, ay = 1.6, YB + 1.9
    m.box("concrete", (ax - 0.6, ay - 0.45, deck), (ax + 0.6, ay + 0.45, deck + 0.1))
    m.box("ac", (ax - 0.5, ay - 0.38, deck + 0.1), (ax + 0.5, ay + 0.38, deck + 0.85))
    m.cyl("dark", ax, ay, 0.28, deck + 0.85, deck + 0.87, seg=16)
    for x, y, h in ((2.8, YK - 0.6, 0.8), (-2.9, YB + 0.7, 0.6)):
        m.cyl("galv", x, y, 0.06, deck, deck + h, seg=8)
        m.cyl("galv", x, y, 0.1, deck + h, deck + h + 0.08, seg=8)
