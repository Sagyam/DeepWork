# S7, corner store: an American neighbourhood grocery of the 1920s. Red
# brick over a painted timber shopfront which turns both streets; their big
# display windows have panelled stallrisers and prism-glass transoms, with
# striped canvas awnings under the name fascia. The chamfered corner holds
# the grocery's door between two lamps and GROCERY in gilt letters. The
# flats have their own street door; above are two-over-two sashes, brick
# piers and stone dressings. A pressed-metal cornice, a stepped date panel
# and a little corner finial crown the parapet. The flat roof carries a
# skylight, a chimney, an aerial and the shop's condenser. The app tints the
# brick, joinery and cornice, and paints the store's name on both fascias.
#
# Pieces (base at the origin, stacked by the app):
#   ground  4.25 m: both shopfronts, the corner and flats' doors, the yard
#   floor   3.15 m: a storey of flats, one or two of them
#   awning  canvas awnings on the two street fronts
#   roof    cornice, parapet, date panel, roof and plant; the ghost sign on
#           the top storey's party wall hangs below it
import math

from lib import Model, Side, Z, awning, letters, lintel, new_id, pane, sash, sill

ID = "s7"
W, D = 11.2, 11.0
X0, X1, Y0, Y1 = -W / 2, W / 2, -D / 2, D / 2
C = 2.3  # the corner cut back along both streets
PL = 0.18
G = 4.25
FL = 3.15
SHOP_E = 3.28
FOOT = [(X0, Y0), (X1 - C, Y0), (X1, Y0 + C), (X1, Y1), (X0, Y1)]
DOWN = X0 + 0.55


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("floor", (0, 0, G))
    storey(M, G)
    M.piece("awning")
    awnings(M)
    M.piece("roof", (0, 0, G + FL))
    roof(M, G + FL)
    M.export(out, bake)


def facades(m):
    """The five faces, seen from outside, with their half-lengths."""
    q = math.sqrt(0.5)
    hf, hr = (W - C) / 2, (D - C) / 2
    return {
        "front": (Side(m, (X0 + hf, Y0, 0), (1, 0, 0), (0, -1, 0)), hf),
        "corner": (Side(m, (X1 - C / 2, Y0 + C / 2, 0), (q, q, 0), (q, -q, 0)), C * q),
        "right": (Side(m, (X1, Y0 + C + hr, 0), (0, 1, 0), (1, 0, 0)), hr),
        "back": (Side(m, (0, Y1, 0), (-1, 0, 0), (0, 1, 0)), W / 2),
        "left": (Side(m, (X0, 0, 0), (0, -1, 0), (-1, 0, 0)), D / 2),
    }


def downpipe(m, z0, z1):
    m.box("gutter", (DOWN - 0.045, Y1 + 0.03, z0), (DOWN + 0.045, Y1 + 0.12, z1))
    for z in (z0 + 0.8, z0 + 2.1):
        if z < z1:
            m.box("iron", (DOWN - 0.065, Y1, z), (DOWN + 0.065, Y1 + 0.14, z + 0.045))


# ---- shopfronts --------------------------------------------------------------------


def display(F, a, b):
    """A display in a painted frame: raised panels below, two or more lights,
    and a prism-glass transom divided into small square panes."""
    deep = 0.3
    wid = new_id()
    fw = 0.075
    stall = PL + 0.52
    transom = 2.63
    F.box("shopframe", a, b, PL, stall, -deep, -deep + 0.13)
    for box in ((a, a + fw, PL, SHOP_E), (b - fw, b, PL, SHOP_E),
                (a, b, stall - 0.05, stall + 0.04), (a, b, transom - 0.045, transom + 0.045),
                (a, b, SHOP_E - 0.08, SHOP_E)):
        F.box("shopframe", *box, -deep, -deep + 0.13)
    n = max(2, round((b - a) / 1.55))
    for i in range(n):
        u0 = a + fw + (b - a - 2 * fw) * i / n
        u1 = a + fw + (b - a - 2 * fw) * (i + 1) / n
        if i:
            F.box("shopframe", u0 - 0.028, u0 + 0.028, stall, transom, -deep + 0.015, -deep + 0.12)
        pane(F, "shopglass", a, b, PL, SHOP_E, u0 + 0.02, u1 - 0.02, stall + 0.04, transom - 0.045, -deep + 0.055, wid)
        # A raised and fielded panel under each light.
        F.box("shopframe", u0 + 0.09, u1 - 0.09, PL + 0.11, stall - 0.13, -deep + 0.13, -deep + 0.155)
        F.box("shopframe", u0 + 0.14, u1 - 0.14, PL + 0.16, stall - 0.18, -deep + 0.155, -deep + 0.17)
    pane(F, "shopglass", a, b, PL, SHOP_E, a + fw, b - fw, transom + 0.045, SHOP_E - 0.08, -deep + 0.055, wid)
    bars = max(3, round((b - a) / 0.36))
    for i in range(1, bars):
        u = a + fw + (b - a - 2 * fw) * i / bars
        F.box("shopframe", u - 0.014, u + 0.014, transom + 0.045, SHOP_E - 0.08, -deep + 0.04, -deep + 0.1)


def corner_door(M, F, a, b):
    """The corner entrance: a glazed and panelled door, sidelights and a transom."""
    deep = 0.42
    wid = new_id()
    mid = (a + b) / 2
    da, db = mid - 0.48, mid + 0.48
    w0, w1 = -deep, -deep + 0.12
    for u0, u1 in ((a, a + 0.08), (b - 0.08, b), (da - 0.06, da), (db, db + 0.06)):
        F.box("shopframe", u0, u1, PL, SHOP_E, w0, w1)
    for z0, z1 in ((PL, PL + 0.1), (2.58, 2.68), (SHOP_E - 0.08, SHOP_E)):
        F.box("shopframe", a, b, z0, z1, w0, w1)
    for u0, u1 in ((a + 0.08, da - 0.06), (db + 0.06, b - 0.08)):
        F.box("shopframe", u0, u1, PL, PL + 0.5, w0, w1)
        pane(F, "doorglass", a, b, PL, SHOP_E, u0 + 0.025, u1 - 0.025, PL + 0.58, 2.58, -deep + 0.05, wid)
    F.box("shopframe", da, db, PL + 0.1, PL + 0.62, w0, w1)
    F.box("shopframe", da + 0.09, db - 0.09, PL + 0.2, PL + 0.51, w1, w1 + 0.025)
    pane(F, "doorglass", a, b, PL, SHOP_E, da + 0.06, db - 0.06, PL + 0.72, 2.58, -deep + 0.045, wid)
    pane(F, "doorglass", a, b, PL, SHOP_E, a + 0.08, b - 0.08, 2.68, SHOP_E - 0.08, -deep + 0.05, wid)
    F.box("brass", db - 0.18, db - 0.13, 1.05, 1.55, -deep + 0.1, -deep + 0.16)
    F.box("granite", a - 0.12, b + 0.12, 0, PL, -0.05, 0.35, skip=("back",))
    # A small mosaic threshold and a pair of lamps on the diagonal face.
    F.box("panel", da, db, PL + 0.005, PL + 0.02, -deep, 0, skip=("back", "bottom"))
    for u in (-1.22, 1.22):
        F.box("iron", u - 0.035, u + 0.035, 2.65, 2.72, 0, 0.27)
        q = F.p(u, 0, 0.31)
        M.m.cyl("iron", q.x, q.y, 0.14, 2.25, 2.31, seg=8)
        M.m.cyl("lamp", q.x, q.y, 0.115, 2.31, 2.64, seg=8, top=False, r1=0.14)
        M.m.cyl("iron", q.x, q.y, 0.17, 2.64, 2.73, seg=8, r1=0.035)


def flats_door(F, a, b):
    """The flats' recessed street door, with four panels, a glazed top and a lamp."""
    deep, e = 0.38, 3.12
    wid = new_id()
    F.box("granite", a - 0.1, b + 0.1, 0, PL, -0.05, 0.3, skip=("back",))
    for u0, u1 in ((a, a + 0.075), (b - 0.075, b)):
        F.box("door", u0, u1, PL, e, -deep, -deep + 0.1)
    for z0, z1 in ((PL, PL + 0.1), (2.25, 2.34), (e - 0.07, e)):
        F.box("door", a, b, z0, z1, -deep, -deep + 0.1)
    for u0, u1 in ((a + 0.1, b - 0.1),):
        F.box("door", u0, u1, PL + 0.1, 1.18, -deep + 0.025, -deep + 0.06)
        for z0, z1 in ((PL + 0.2, PL + 0.57), (PL + 0.68, 1.08)):
            F.box("door", u0 + 0.1, u1 - 0.1, z0, z1, -deep + 0.06, -deep + 0.08)
    pane(F, "doorglass", a, b, PL, e, a + 0.1, b - 0.1, 1.28, 2.25, -deep + 0.045, wid)
    pane(F, "doorglass", a, b, PL, e, a + 0.075, b - 0.075, 2.34, e - 0.07, -deep + 0.045, wid)
    F.box("brass", b - 0.2, b - 0.14, 1.05, 1.12, -deep + 0.08, -deep + 0.13)
    F.box("stone", a - 0.14, b + 0.14, e, e + 0.24, 0, 0.07)
    letters(F.m, "brass", F, (a + b) / 2, e + 0.12, 0.075, "27", 0.16, depth=0.012)
    F.box("iron", b + 0.24, b + 0.3, 2.18, 2.24, 0, 0.16)
    F.box("lamp", b + 0.19, b + 0.35, 2.24, 2.49, 0.07, 0.19)
    F.box("iron", b + 0.17, b + 0.37, 2.49, 2.54, 0.04, 0.22)


def ground(M):
    m = M.m
    fs = facades(m)
    F, hf = fs["front"]
    K, hk = fs["corner"]
    R, hr = fs["right"]
    B, hb = fs["back"]
    L, hl = fs["left"]
    flat = (-hf + 0.5, -hf + 1.55)
    front = (flat[1] + 0.45, hf - 0.3)
    right = [(-hr + 0.32, -0.18), (0.18, hr - 0.32)]
    corner = (-0.76, 0.76)

    F.wall("brick", -hf, hf, PL, G, [(*flat, PL, 3.12, 0.38), (*front, PL, SHOP_E, 0.3)], depth=0.3, reveal="stone")
    flats_door(F, *flat)
    display(F, *front)
    R.wall("brick", -hr, hr, PL, G, [(a, b, PL, SHOP_E, 0.3) for a, b in right], depth=0.3, reveal="stone")
    for a, b in right:
        display(R, a, b)
    K.wall("brick", -hk, hk, PL, G, [(*corner, PL, SHOP_E, 0.42)], depth=0.42, reveal="stone")
    corner_door(M, K, *corner)

    # The yard: a delivery door, two barred windows, the electric meter.
    delivery = (1.9, 3.0)
    windows = [(-3.9, -2.8), (-0.7, 0.4)]
    B.wall("brick", -hb, hb, PL, G, [(*delivery, PL, 2.55, 0.25)] + [(a, b, 1.45, 2.8) for a, b in windows], depth=0.3, reveal="stone")
    a, b = delivery
    B.quad("door", a + 0.05, b - 0.05, PL, 2.5, -0.2)
    for z in (0.55, 1.35):
        B.box("door", a + 0.15, b - 0.15, z, z + 0.65, -0.2, -0.17)
    B.box("iron", b - 0.21, b - 0.14, 1.15, 1.23, -0.2, -0.14)
    B.box("concrete", a - 0.25, b + 0.25, 0, PL, 0, 0.65, skip=("back",))
    B.box("roof", a - 0.22, b + 0.22, 2.62, 2.69, 0, 0.65, skip=())
    B.box("lamp", a - 0.15, a + 0.15, 2.82, 2.94, 0, 0.12)
    for a, b in windows:
        sash(B, a, b, 1.45, 2.8, D=0.3, lights=(2, 1))
        sill(B, a, b, 1.45, D=0.3)
        lintel(B, a, b, 2.8, key_=False)
        for i in range(6):
            u = a + 0.1 + i * (b - a - 0.2) / 5
            B.box("iron", u - 0.012, u + 0.012, 1.47, 2.78, 0.02, 0.05)
    B.box("ac", 0.85, 1.35, 1.25, 1.95, 0, 0.2)
    B.box("dark", 0.91, 1.29, 1.43, 1.79, 0.2, 0.205, skip=("back",))
    L.wall("brick", -hl, hl, PL, G, [])
    m.psweep("granite", FOOT, [(0.04, 0), (0.04, PL - 0.035), (0.0, PL)])

    # The continuous name fascia, the corner's gilt GROCERY, and the cornice
    # which separates the shop from the flats.
    for name, (S, h) in fs.items():
        S.box("shopframe", -h - 0.02, h + 0.02, 3.43, 4.02, 0, 0.11)
        S.box("cornice", -h - 0.06, h + 0.06, 4.02, 4.12, 0, 0.19)
        S.box("cornice", -h - 0.08, h + 0.08, 4.12, G, 0, 0.24)
    for S, h in ((F, hf), (R, hr)):
        S.quad("sign", -h + 0.25, h - 0.25, 3.54, 3.92, 0.112, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    letters(m, "brass", K, 0, 3.73, 0.115, "GROCERY", 0.32, depth=0.025, spacing=1.08)
    m.poly("dark", [(x, y, G - 0.02) for x, y in FOOT], out=Z)
    downpipe(m, 0.05, G)


# ---- flats -------------------------------------------------------------------------


AXES = {
    "front": [-2.95, -0.55, 1.85],
    "right": [-2.65, -0.15, 2.35],
    "back": [-3.55, -0.85, 2.0],
}


def storey(M, z):
    m = M.m
    fs = facades(m)
    for name, (F, h) in fs.items():
        if name == "left":
            F.wall("brick", -h, h, z, z + FL, [])
            continue
        axes = [0.0] if name == "corner" else AXES[name]
        ww = 1.08 if name != "back" else 1.0
        c, e = z + 0.78, z + 2.58
        holes = [(u - ww / 2, u + ww / 2, c, e) for u in axes]
        F.wall("brick", -h, h, z, z + FL, holes, depth=0.25, reveal="stone")
        for a, b, c_, e_ in holes:
            sash(F, a, b, c_, e_, D=0.25, lights=(2, 1))
            sill(F, a, b, c_, D=0.25)
            lintel(F, a, b, e_, key_=name == "corner")
        if name in ("front", "right"):
            # Shallow brick piers between the bays, with stone bases and caps.
            edges = [-h + 0.14] + [(u + v) / 2 for u, v in zip(axes, axes[1:])] + [h - 0.14]
            for u in edges:
                F.box("brick", u - 0.12, u + 0.12, z, z + FL - 0.25, 0, 0.075)
                F.box("stone", u - 0.15, u + 0.15, z + 0.45, z + 0.56, 0, 0.1)
                F.box("stone", u - 0.16, u + 0.16, z + FL - 0.48, z + FL - 0.36, 0, 0.12)
    m.psweep("stone", FOOT, [(-0.01, z + 0.16), (0.055, z + 0.16), (0.055, z + 0.25), (-0.01, z + 0.25)])
    m.psweep("brick", FOOT, [(-0.01, z + FL - 0.3), (0.08, z + FL - 0.3), (0.08, z + FL - 0.2), (0.14, z + FL - 0.2), (0.14, z + FL - 0.08), (-0.01, z + FL - 0.08)])
    m.poly("dark", [(x, y, z + FL - 0.02) for x, y in FOOT], out=Z)
    downpipe(m, z, z + FL)


def awnings(M):
    fs = facades(M.m)
    F, hf = fs["front"]
    R, hr = fs["right"]
    flat_end = -hf + 1.55
    awning(F, flat_end + 0.4, hf - 0.25, 3.4, drop=0.58, depth=1.25)
    awning(R, -hr + 0.27, -0.13, 3.4, drop=0.58, depth=1.25)
    awning(R, 0.13, hr - 0.27, 3.4, drop=0.58, depth=1.25)


# ---- roof --------------------------------------------------------------------------


def roof(M, top):
    m = M.m
    fs = facades(m)
    F, _ = fs["front"]
    K, _ = fs["corner"]
    parapet = top + 0.76
    m.psweep("cornice", FOOT, [(-0.02, top - 0.04), (0.12, top - 0.04), (0.12, top + 0.06), (0.28, top + 0.12), (0.34, top + 0.22), (0.3, top + 0.3), (0.0, top + 0.3)])
    for name, (S, h) in fs.items():
        S.wall("brick", -h, h, top + 0.22, parapet, [])
        S.quad("brick", h - 0.25, -h + 0.25, top + 0.06, parapet, -0.25, out=-S.n)
        # Dentils under the metal cornice on the public elevations.
        if name in ("front", "corner", "right"):
            n = max(2, int(2 * h / 0.32))
            for i in range(n):
                u = -h + 0.12 + i * (2 * h - 0.24) / max(1, n - 1)
                S.box("cornice", u - 0.045, u + 0.045, top + 0.02, top + 0.14, 0.12, 0.27)
    m.psweep("stone", FOOT, [(-0.28, parapet), (0.09, parapet), (0.09, parapet + 0.1), (-0.28, parapet + 0.1)])

    # The front's stepped date panel and the corner's small capped pier.
    F.box("brick", -1.7, 1.7, parapet, parapet + 0.64, -0.25, 0, skip=())
    F.box("brick", -0.85, 0.85, parapet + 0.64, parapet + 0.84, -0.25, 0, skip=())
    F.box("stone", -1.76, 1.76, parapet + 0.58, parapet + 0.68, -0.3, 0.06, skip=())
    F.box("stone", -0.91, 0.91, parapet + 0.82, parapet + 0.93, -0.3, 0.06, skip=())
    F.box("stone", -1.3, 1.3, parapet + 0.1, parapet + 0.5, 0, 0.055)
    letters(m, "brass", F, 0, parapet + 0.3, 0.06, "1926", 0.29, depth=0.018, spacing=1.15)
    K.box("brick", -0.48, 0.48, parapet, parapet + 0.36, -0.25, 0, skip=())
    K.box("stone", -0.56, 0.56, parapet + 0.34, parapet + 0.45, -0.31, 0.07, skip=())
    q = K.p(0, 0, -0.05)
    m.cyl("stone", q.x, q.y, 0.15, parapet + 0.45, parapet + 0.67, seg=10, r1=0.1)
    m.cyl("stone", q.x, q.y, 0.11, parapet + 0.67, parapet + 0.88, seg=10, r1=0.0)

    # The flat deck and its rooflights and plant.
    m.poly("roof", [(x, y, top + 0.055) for x, y in FOOT], out=Z)
    cx, cy = X0 + 0.48, 2.25
    ct = top + 1.9
    m.box("brick", (cx - 0.38, cy - 0.58, top + 0.05), (cx + 0.38, cy + 0.58, ct))
    m.sweep("brick", 0.76, 1.16, [(-0.01, ct - 0.24), (0.06, ct - 0.24), (0.06, ct - 0.1), (0.1, ct - 0.1), (0.1, ct), (-0.01, ct)], cx=cx, cy=cy)
    m.box("stone", (cx - 0.46, cy - 0.66, ct), (cx + 0.46, cy + 0.66, ct + 0.09))
    for dy in (-0.32, 0.0, 0.32):
        m.cyl("terracotta", cx, cy + dy, 0.105, ct + 0.09, ct + 0.43, seg=10, r1=0.09)
    # A skylight over the stair, with a metal kerb and two glazed slopes.
    sx, sy = -0.6, 2.35
    m.box("wood", (sx - 0.85, sy - 0.65, top + 0.05), (sx + 0.85, sy + 0.65, top + 0.42))
    for sign in (-1, 1):
        pts = [(sx - 0.85, sy + sign * 0.65, top + 0.42), (sx + 0.85, sy + sign * 0.65, top + 0.42),
               (sx + 0.85, sy, top + 0.88), (sx - 0.85, sy, top + 0.88)]
        m.poly("canopy", pts, out=(0, sign, 1))
        m.strut("steel", pts[0], pts[3], 0.045)
        m.strut("steel", pts[1], pts[2], 0.045)
        m.strut("steel", (sx, sy + sign * 0.65, top + 0.42), (sx, sy, top + 0.88), 0.035)
    m.strut("steel", (sx - 0.9, sy, top + 0.88), (sx + 0.9, sy, top + 0.88), 0.06)
    # A roof hatch, the grocery's condenser, vent pipes and a television aerial.
    hx, hy = 2.25, 2.8
    m.box("wood", (hx - 0.55, hy - 0.55, top + 0.05), (hx + 0.55, hy + 0.55, top + 0.43))
    m.box("steel", (hx - 0.6, hy - 0.6, top + 0.43), (hx + 0.6, hy + 0.6, top + 0.5))
    ax, ay = 2.4, -0.65
    m.box("concrete", (ax - 0.72, ay - 0.5, top + 0.05), (ax + 0.72, ay + 0.5, top + 0.17))
    m.box("ac", (ax - 0.62, ay - 0.42, top + 0.17), (ax + 0.62, ay + 0.42, top + 0.93))
    m.cyl("dark", ax, ay, 0.31, top + 0.93, top + 0.95, seg=16)
    for x, y, h in ((0.5, 4.1, 0.75), (1.05, 4.15, 0.55), (-2.7, 0.4, 0.85)):
        m.cyl("ac", x, y, 0.065, top + 0.05, top + h, seg=10)
        m.cyl("ac", x, y, 0.1, top + h, top + h + 0.09, seg=10)
    m.strut("steel", (cx, cy - 0.65, ct - 0.6), (cx, cy - 0.65, ct + 1.35), 0.04)
    for zz, length in ((ct + 1.25, 0.75), (ct + 0.95, 0.56), (ct + 0.7, 0.4)):
        m.strut("steel", (cx - length, cy - 0.67, zz), (cx + length, cy - 0.67, zz), 0.022)
    # The faded painted advertisement on the party wall below this piece.
    fs["left"][0].quad("ghost", -4.55, 4.25, top - 2.65, top - 0.18, 0.004, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    m.box("gutter", (DOWN - 0.13, Y1 - 0.05, top + 0.05), (DOWN + 0.13, Y1 + 0.2, top + 0.17))
    downpipe(m, top, top + 0.18)
