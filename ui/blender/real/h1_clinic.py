# H1, clinic: the town's health centre of the early 1960s. One long storey
# of white render on a dark brick plinth, a ribbon of aluminium windows
# under a deep flat roof whose fascia oversails the walls all round. The
# entrance is a recessed glass screen under a thin cantilevered canopy
# that carries CLINIC in letters and a green cross on a lightbox (lit at
# night), reached by a ramp with steel rails beside three steps. A
# lean-to ambulance bay on the right with its own canopy, a bench by the
# door, roof plant behind a louvre screen, a flue.
#
# Pieces (base at the origin):
#   body  the storey to the roof (3.6 m), the entrance, ramp and bay
#   roof  the slab, fascia, canopy, the cross, plant and flue
import math

from lib import Model, Z, glazing, letters, new_id, pane, sides, sill

ID = "h1"
W, D = 13.0, 9.0
HW, HD = W / 2, D / 2
PLINTH = 0.45
H = 3.6  # top of the walls
ENT = (-1.4, 1.4)  # the entrance recess, x
RECESS = 1.2
BAY = (HW, HW + 2.2)  # the ambulance bay's canopy, x (beside the right wall)


def build(out, bake=True):
    M = Model(ID, seed=23)
    M.sharp = math.radians(40)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, H))
    roof(M)
    lift(M, H)
    M.export(out, bake)


def lift(M, dz):
    """Moves the current piece's faces up by dz: the roof is drawn from z = 0 at the wall head."""
    for mesh in (M.m, M.cut):
        vs = {v for f in mesh.bm.faces if f[mesh.piece] == mesh.part for v in f.verts}
        for v in vs:
            v.co.z += dz


def ribbon(F, u0, u1, c, e, D_=0.15, n=None):
    """A ribbon of windows: aluminium glazing in lights about 1.2 m wide, opening top lights."""
    n = n or max(1, round((u1 - u0) / 1.2))
    glazing(F, u0, u1, c, e, lights=n, D=D_)
    # Transom bar with top-hung vents.
    tz = e - 0.45
    F.box("alu", u0 + 0.05, u1 - 0.05, tz - 0.025, tz + 0.025, -D_ - 0.03, -D_ + 0.05)


def body(M):
    m = M.m
    walls = sides(m, W, D)
    c, e = PLINTH + 0.95, H - 0.35
    for name, F in walls.items():
        h = HW if name in ("front", "back") else HD
        F.box("brick", -h, h, 0.0, PLINTH, -0.0, 0.03)
        if name == "front":
            holes = [(-HW + 0.6, ENT[0] - 0.5, c, e), (ENT[1] + 0.5, HW - 0.6, c, e), (ENT[0], ENT[1], PLINTH, e + 0.0, RECESS)]
            F.wall("render", -h, h, PLINTH, H, holes, depth=0.15)
            for a, b, c_, e_ in holes[:2]:
                ribbon(F, a, b, c_, e_)
                sill(F, a, b, c_, D=0.15, role="alu")
                # Coloured spandrel panels under the ribbon.
                F.box("clinicpanel", a, b, PLINTH + 0.1, c_ - 0.12, 0, 0.02)
            entrance(m, F)
        elif name == "back":
            holes = [(-HW + 0.8, -1.0, c, e), (1.0, 2.2, c + 0.6, e), (3.4, 4.4, PLINTH, 2.5, 0.15)]
            F.wall("render", -h, h, PLINTH, H, holes, depth=0.15)
            ribbon(F, -HW + 0.8, -1.0, c, e)
            sill(F, -HW + 0.8, -1.0, c, D=0.15, role="alu")
            glazing(F, 1.0, 2.2, c + 0.6, e, lights=1, D=0.15, glass="frosted")
            F.quad("door", 3.4, 4.4, PLINTH, 2.5, -0.12)
            F.box("concrete", 3.1, 4.7, 0.0, PLINTH, 0, 1.0, skip=("back",))
        elif name == "left":
            holes = [(-2.4, 2.4, c, e)]
            F.wall("render", -h, h, PLINTH, H, holes, depth=0.15)
            ribbon(F, -2.4, 2.4, c, e)
            sill(F, -2.4, 2.4, c, D=0.15, role="alu")
        else:
            # The right wall: the ambulance doors under the bay canopy.
            holes = [(-1.4, 0.6, PLINTH, 2.6, 0.15), (1.6, 3.4, c, e)]
            F.wall("render", -h, h, PLINTH, H, holes, depth=0.15)
            glazing(F, -1.4, 0.6, PLINTH, 2.6, lights=2, D=0.12, glass="doorglass")
            F.box("alu", -0.43, -0.37, PLINTH + 0.9, PLINTH + 1.1, -0.1, -0.06)
            ribbon(F, 1.6, 3.4, c, e)
            sill(F, 1.6, 3.4, c, D=0.15, role="alu")
            # A ramp from the bay up to the doors.
            m.box("concrete", (HW, -1.7, 0.0), (HW + 2.2, 0.9, PLINTH * 0.99), skip=("z0",))
    bay(m)
    m.poly("dark", [(-HW, -HD, H - 0.02), (HW, -HD, H - 0.02), (HW, HD, H - 0.02), (-HW, HD, H - 0.02)], out=-Z)


def entrance(m, F):
    """The recess: a glass screen with sliding doors, its floor, ramp and steps out front."""
    a, b = ENT
    y = -HD
    # Recess floor (its walls and ceiling are the opening's reveals).
    m.box("granite", (a, y, PLINTH - 0.04), (b, y + RECESS, PLINTH), skip=("z0",))
    # The screen at the back of the recess: sliding doors in the middle, glass either side.
    S = sides(m, b - a, 2 * RECESS, 0, y + 2 * RECESS)["front"]
    S.box("alu", a, b, PLINTH, PLINTH + 0.05, -0.05, 0.05)
    wid = new_id()
    for u0, u1 in ((a, -0.9), (0.9, b)):
        S.box("alu", u0, u0 + 0.06, PLINTH, H - 0.35, -0.05, 0.05)
        S.box("alu", u1 - 0.06, u1, PLINTH, H - 0.35, -0.05, 0.05)
        pane(S, "doorglass", a, b, PLINTH, H - 0.35, u0 + 0.06, u1 - 0.06, PLINTH + 0.05, H - 0.4, 0.0, wid)
    S.box("alu", -0.9, 0.9, H - 0.75, H - 0.35, -0.05, 0.05)
    S.box("dark", -0.85, 0.85, H - 0.7, H - 0.4, 0.05, 0.06)
    for u0, u1 in ((-0.9, 0.0), (0.0, 0.9)):
        S.box("alu", u0, u0 + 0.05, PLINTH, H - 0.75, -0.03, 0.03)
        S.box("alu", u1 - 0.05, u1, PLINTH, H - 0.75, -0.03, 0.03)
        S.box("alu", u0, u1, PLINTH, PLINTH + 0.12, -0.03, 0.03)
        pane(S, "doorglass", a, b, PLINTH, H - 0.35, u0 + 0.05, u1 - 0.05, PLINTH + 0.12, H - 0.8, 0.0, wid)
    # Steps on the left of the landing, the ramp running off to the right.
    ly = y - 1.6
    m.box("concrete", (a - 0.2, ly, 0.0), (b + 0.2, y, PLINTH), skip=("z0",))
    for i in range(3):
        m.box("concrete", (a - 0.2, ly - (i + 1) * 0.3, 0.0), (a + 1.2, ly - i * 0.3, PLINTH - (i + 1) * PLINTH / 3), skip=("z0",))
    rl = 4.6  # ramp length, 1 in 10
    rx0, rx1 = b + 0.2, b + 0.2 + rl
    ry0, ry1 = ly, ly + 1.3
    m.poly("concrete", [(rx0, ry0, PLINTH), (rx1, ry0, 0.0), (rx1, ry1, 0.0), (rx0, ry1, PLINTH)], out=Z)
    for yy in (ry0, ry1):
        m.poly("concrete", [(rx0, yy, 0.0), (rx1, yy, 0.0), (rx0, yy, PLINTH)], out=(0, -1 if yy == ry0 else 1, 0))
    # Steel handrails: along the ramp's outer edge and the landing's front.
    def rail(p, q):
        m.strut("galv", p, q, 0.045)
    for k in range(5):
        t = k / 4
        x = rx0 + t * (rx1 - rx0)
        z = PLINTH * (1 - t)
        rail((x, ry0 + 0.05, z), (x, ry0 + 0.05, z + 0.95))
    rail((rx0, ry0 + 0.05, PLINTH + 0.95), (rx1, ry0 + 0.05, 0.95))
    rail((rx0, ry0 + 0.05, PLINTH + 0.6), (rx1, ry0 + 0.05, 0.6))
    rail((a + 1.25, ly + 0.05, PLINTH + 0.95), (rx0, ly + 0.05, PLINTH + 0.95))
    for x in (a + 1.25, rx0):
        rail((x, ly + 0.05, PLINTH), (x, ly + 0.05, PLINTH + 0.95))
    # A bench against the wall left of the entrance, a bin.
    bx = a - 2.6
    m.box("wood", (bx - 0.9, y - 0.55, 0.42), (bx + 0.9, y - 0.15, 0.47))
    for dx in (-0.75, 0.75):
        m.box("iron", (bx + dx - 0.03, y - 0.5, 0.0), (bx + dx + 0.03, y - 0.2, 0.42))
    m.cyl("iron", a - 0.45, y - 0.4, 0.2, PLINTH, PLINTH + 0.75, seg=12)


def bay(m):
    """The ambulance bay: posts and a steel canopy off the right wall, a marked bay on the ground."""
    x0, x1 = BAY
    y0, y1 = -2.2, 1.4
    for y in (y0 + 0.1, y1 - 0.1):
        m.box("steelframe", (x1 - 0.18, y - 0.08, 0.0), (x1 - 0.02, y + 0.08, 3.0))


# ---- roof -----------------------------------------------------------------------------


def roof(M):
    m = M.m
    o = 0.6
    x0, x1, y0, y1 = -HW - o, HW + o, -HD - o, HD + o
    # The slab and its deep white fascia; a dark soffit.
    m.box("paint", (x0, y0, 0.0), (x1, y1, 0.45), skip=("z0", "z1"))
    m.poly("panel", [(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)], out=-Z)
    m.box("alu", (x0 - 0.02, y0 - 0.02, 0.45), (x1 + 0.02, y1 + 0.02, 0.5))
    m.poly("roof", [(x0 + 0.1, y0 + 0.1, 0.42), (x1 - 0.1, y0 + 0.1, 0.42), (x1 - 0.1, y1 - 0.1, 0.42), (x0 + 0.1, y1 - 0.1, 0.42)], out=Z)
    m.box("paint", (x0, y0, 0.42), (x1, y0 + 0.1, 0.45), skip=("z0",))
    # The ambulance bay canopy, lower, off the right side.
    bx0, bx1 = BAY
    m.box("steelframe", (bx0, -2.2, -0.6), (bx1, 1.4, -0.4))
    m.box("paint", (bx0, -2.2, -0.4), (bx1, 1.4, -0.3), skip=("z0",))
    letters(m, "danger", sides(m, bx1 - bx0, 3.6, (bx0 + bx1) / 2, -0.4, -0.6)["right"], 0, 0.1, 0.0, "AMBULANCE", 0.15, depth=0.01)
    # The entrance canopy: a thin slab cantilevered from the fascia, CLINIC on its edge.
    a, b = ENT
    cy0 = -HD - 2.2
    m.box("paint", (a - 1.4, cy0, -0.7), (b + 1.4, y0, -0.5))
    m.poly("panel", [(a - 1.4, cy0, -0.7), (b + 1.4, cy0, -0.7), (b + 1.4, y0, -0.7), (a - 1.4, y0, -0.7)], out=-Z)
    F = sides(m, b - a + 2.8, 2.0, 0, cy0 + 1.0, -0.7)["front"]
    letters(m, "clinicname", F, -0.8, 0.1, 0.0, "CLINIC", 0.15, depth=0.015, spacing=1.3)
    for u in (-1.2, 1.2):
        F.box("lamp", u - 0.15, u + 0.15, -0.03, 0.0, -1.3, -1.0, skip=())
    # The green cross on a lightbox above the canopy at its right end.
    cx, cz = b + 0.9, 0.0
    m.box("paint", (cx - 0.45, cy0 + 0.3, -0.5), (cx + 0.45, cy0 + 0.5, 0.4))
    for lo, hi in (((cx - 0.38, cy0 + 0.28, -0.22), (cx + 0.38, cy0 + 0.3, 0.12)), ((cx - 0.12, cy0 + 0.28, -0.42), (cx + 0.12, cy0 + 0.3, 0.32))):
        m.box("cross", lo, hi, skip=("y1",))
    # Plant behind a louvre screen, a flue, a rooflight.
    px, py = 2.0, 1.6
    S = sides(m, 3.2, 2.0, px, py, 0.42)
    for F_ in S.values():
        hw = (3.2 if F_ in (S["front"], S["back"]) else 2.0) / 2
        F_.quad("roller", -hw, hw, 0.0, 1.2)
        F_.box("alu", -hw, hw, 1.2, 1.25, -0.03, 0.03)
    m.poly("dark", [(px - 1.6, py - 1.0, 0.43), (px + 1.6, py - 1.0, 0.43), (px + 1.6, py + 1.0, 0.43), (px - 1.6, py + 1.0, 0.43)], out=Z)
    m.box("ac", (px - 1.0, py - 0.5, 0.42), (px + 0.4, py + 0.5, 1.1))
    m.cyl("galv", -3.8, 2.4, 0.12, 0.42, 1.9, seg=10)
    m.cyl("galv", -3.8, 2.4, 0.2, 1.9, 1.95, seg=10, r1=0.05)
    m.box("concrete", (-2.2, -0.8, 0.42), (-0.6, 0.8, 0.6))
    m.poly("skyglass", [(-2.1, -0.7, 0.62), (-0.7, -0.7, 0.62), (-0.7, 0.7, 0.62), (-2.1, 0.7, 0.62)], out=Z)
    m.box("concrete", (-2.2, -0.8, 0.6), (-0.6, -0.7, 0.62), skip=("z0",))
