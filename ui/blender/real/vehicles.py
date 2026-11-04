# Vehicles for the realistic city: the cars that park on drives and in
# bays and drive round the blocks (ui/src/city/traffic.ts), replacing the
# low-poly kit's four cars and bus.
#
# Passenger cars are lofted: a cross-section (rocker, door, shoulder, glass,
# roof) is interpolated along the car between keyframes of its profile, so
# hood, windscreen, roof and boot come out of one smooth skin. Wheel arches
# are cut by raising the section's floor over each wheel, with a dark liner
# behind. The glass, pillars and roof are picked per face from where the
# face sits along the car. Bus, van and truck use the same skin, squarer.
#
# Pieces (one per vehicle, at the origin, nose toward -y, i.e. glTF +z):
#   hatch, sedan, estate, suv, pickup, coupe, taxi, van, bus, truck
# Roles: carpaint (tinted per vehicle by the app), carglass, dark (grilles,
# liners, underbody), rubber (black plastic trim), chrome, rim, tyre,
# headlight, taillight, plate, taxisign, led, cargo.
import math

from lib import Model, Vector

ID = "cars"


def lerp(a, b, t):
    return a + (b - a) * t


class Profile:
    """Keyframes along the car, by distance from the nose: (d, floor, shoulder, roof, width, roof width)."""

    def __init__(self, keys):
        self.keys = sorted(keys)

    def at(self, d):
        k = self.keys
        if d <= k[0][0]:
            return k[0][1:]
        for a, b in zip(k, k[1:]):
            if d <= b[0]:
                t = (d - a[0]) / max(1e-6, b[0] - a[0])
                return tuple(lerp(x, y, t) for x, y in zip(a[1:], b[1:]))
        return k[-1][1:]


def body(m, S):
    """The lofted skin of a vehicle from its spec S (see CARS)."""
    L, W = S["L"], S["W"]
    prof = Profile(S["keys"])
    wheels = S["wheels"]  # distances from the nose
    R = S["r"]
    arch = R + 0.07
    glass = S["glass"]  # (from, to, kind) along the car: "screen", "side", "back"
    pillars = S.get("pillars", [])
    crown = S.get("crown", 0.03)
    # Stations: even steps, keyframes, and dense round the arches.
    ds = {round(i * L / 28, 4) for i in range(29)}
    ds |= {k[0] for k in S["keys"]}
    for wd in wheels:
        for i in range(-5, 6):
            ds.add(round(wd + i * arch / 5, 4))
    for g0, g1, _ in glass:
        ds |= {g0, g1}
    for p0, p1 in pillars:
        ds |= {p0, p1}
    ds = sorted(d for d in ds if 0 <= d <= L)

    def floor(d, zb):
        for wd in wheels:
            dd = abs(d - wd)
            if dd < arch:
                zb = max(zb, R + math.sqrt(arch * arch - dd * dd))
        return zb

    def ring(d):
        zb0, zs, zr, wf, wrf = prof.at(d)
        zb = floor(d, zb0)
        w = W / 2 * wf
        wr = w * wrf
        z1 = min(zb + 0.1, zs - 0.16)
        z2 = max(z1 + 0.02, lerp(z1, zs, 0.55))
        # Heights only rise toward the roof, so the section never folds
        # over itself where the roof comes down to the hood or the boot.
        z4 = zs + 0.012
        z5 = max(z4 + 0.008, zr - 0.08)
        z6 = max(z5 + 0.006, zr - 0.012)
        half = [
            (w * 0.93, zb),
            (w * 0.985, z1),
            (w, z2),
            (w * 0.975, zs - 0.02),
            (w * 0.95, z4),
            (min(wr, w * 0.93), z5),
            (min(wr * 0.9, w * 0.86), z6),
            (wr * 0.45, max(z6 + 0.004, zr + crown * 0.8)),
        ]
        y = -L / 2 + d
        left = [(-x, y, z) for x, z in half]
        right = [(x, y, z) for x, z in reversed(half)]
        top = (0, y, max(z6 + 0.006, zr + crown))
        return left + [top] + right, zb0

    def kind(d0, d1):
        mid = (d0 + d1) / 2
        for g0, g1, k in glass:
            if g0 <= mid <= g1:
                return k
        return None

    def pillar(d0, d1):
        mid = (d0 + d1) / 2
        return any(p0 <= mid <= p1 for p0, p1 in pillars)

    head_d, tail_d = S.get("head_d", 0.3), S.get("tail_d", 0.2)
    ds = sorted(set(ds) | {head_d, L - tail_d, 0.1, L - 0.06})
    rings = [ring(d) for d in ds]
    n = len(rings[0][0])  # 17 points: 8 left, top, 8 right
    for i in range(len(ds) - 1):
        (ra, _), (rb, _) = rings[i], rings[i + 1]
        k = kind(ds[i], ds[i + 1])
        for j in range(n - 1):
            # Segment index from the bottom on either side: 0 rocker .. 7 roof centre.
            s = min(j, n - 2 - j)
            role = "carpaint"
            if s == 0:
                role = "rubber"
            elif s == 4 and k == "side" and not pillar(ds[i], ds[i + 1]):
                role = "carglass"
            elif s == 4 and k in ("screen", "back"):
                role = "rubber"
            elif s >= 5 and k in ("screen", "back"):
                role = "carglass"
            elif s >= 4 and k == "cover":
                role = "rubber"
            elif s == 4 and k == "side":
                role = S.get("pillar_role", "rubber")
            # Lamps wrap the corners: the upper side and shoulder bands at
            # the nose and tail; the bumpers' lower bands are black.
            mid = (ds[i] + ds[i + 1]) / 2
            if s in (2, 3) and mid < head_d:
                role = "headlight"
            elif s in (2, 3) and mid > L - tail_d:
                role = "taillight"
            elif s == 1 and (mid < 0.1 or mid > L - 0.06):
                role = "rubber"
            m.poly(role, [ra[j], rb[j], rb[j + 1], ra[j + 1]], out=_out(ra, rb, j), smooth=True)
        # Underbody, flat between the bottom points.
        m.poly("dark", [ra[0], rb[0], rb[-1], ra[-1]], out=(0, 0, -1))
    # Nose and tail caps: fans from the middle, the section being convex.
    # The nose is the grille.
    for (r, _), out, role in ((rings[0], (0, -1, 0), "dark"), (rings[-1], (0, 1, 0), "carpaint")):
        c = Vector((0, r[0][1], sum(p[2] for p in r) / len(r)))
        for a, b in zip(r, r[1:] + r[:1]):
            m.poly(role, [tuple(c), a, b], out=out)
    # Wheel-arch liners, so the arches do not show through the car.
    for wd in wheels:
        zb0 = prof.at(wd)[0]
        y = -L / 2 + wd
        x = W / 2 - S.get("tw", 0.22) - 0.06
        pts = [(arch * math.cos(a), arch * math.sin(a)) for a in [math.pi * i / 12 for i in range(13)]]
        for sx in (-1, 1):
            poly = [(sx * x, y - arch, zb0)] + [(sx * x, y - dy, R + dz) for dy, dz in pts] + [(sx * x, y + arch, zb0)]
            m.poly("dark", poly, out=(sx, 0, 0))
    return rings, ds


def _out(ra, rb, j):
    """Outward normal from the winding: rings run left-bottom, over the roof, to right-bottom; stations run nose to tail."""
    a0, a1, b0, b1 = (Vector(p) for p in (ra[j], ra[j + 1], rb[j], rb[j + 1]))
    n = (a1 - a0).cross(b0 - a0) + (b1 - b0).cross(b0 - a0) + (a1 - a0).cross(b1 - a1)
    return n if n.length > 1e-9 else Vector((0, 0, 1))


def wheel(m, x, y, r, w, sx, seg=16, rim="rim"):
    """A tyre with a five-spoke rim; axle along x, outer face toward sx."""
    def P(a, th, rho):
        return (x + sx * a, y + rho * math.cos(th), r + rho * math.sin(th))

    prof = [(-w / 2, r * 0.66), (-w / 2, r * 0.9), (-w * 0.42, r), (w * 0.42, r), (w / 2, r * 0.9), (w / 2, r * 0.66)]
    for i in range(seg):
        t0, t1 = i / seg * math.tau, (i + 1) / seg * math.tau
        tm = (t0 + t1) / 2
        for (a0, p0), (a1, p1) in zip(prof, prof[1:]):
            am = (a0 + a1) / 2
            side = abs(a0 - a1) < 1e-6
            ax = sx * (1 if am > 0 else -1) * (1.0 if side else 0.5 if abs(am) > 0.3 * w else 0.0)
            rad = 0.0 if side else 1.0
            out = (ax, math.cos(tm) * rad, math.sin(tm) * rad)
            m.poly("tyre", [P(a0, t0, p0), P(a0, t1, p0), P(a1, t1, p1), P(a1, t0, p1)], out=out, smooth=not side)
    # Rim: dished face with five spokes over a dark barrel.
    face = w / 2 - 0.02
    rim_r, hub = r * 0.64, r * 0.16
    ring_pts = lambda rho, a: [P(a, i / seg * math.tau, rho) for i in range(seg)]  # noqa: E731
    m.poly("dark", ring_pts(rim_r, face - 0.06), out=(sx, 0, 0))
    outer, inner = ring_pts(rim_r, face), ring_pts(rim_r * 0.86, face - 0.01)
    for i in range(seg):
        j = (i + 1) % seg
        m.poly(rim, [outer[i], outer[j], inner[j], inner[i]], out=(sx, 0, 0))
    m.poly(rim, ring_pts(hub, face - 0.005), out=(sx, 0, 0))
    for k in range(5):
        th = k / 5 * math.tau + 0.3
        a0, a1 = th - 0.14, th + 0.14
        b0, b1 = th - 0.07, th + 0.07
        m.poly(rim, [P(face - 0.004, b0, hub), P(face - 0.004, b1, hub), P(face - 0.012, a1, rim_r * 0.87), P(face - 0.012, a0, rim_r * 0.87)], out=(sx, 0, 0))


def box(m, role, lo, hi, skip=()):
    m.box(role, lo, hi, skip)


def lights(m, S, rings, ds):
    """Number plates on the nose and tail, and door mirrors (the lamps are bands of the skin)."""
    L, W = S["L"], S["W"]
    prof = Profile(S["keys"])
    zb = prof.at(0)[0]
    m.box("plate", (-0.26, -L / 2 - 0.03, zb + 0.06), (0.26, -L / 2 - 0.01, zb + 0.17))
    zb, zs = prof.at(L)[:2]
    pz = S.get("plate_z", zb + 0.12)
    m.box("plate", (-0.26, L / 2 + 0.01, pz), (0.26, L / 2 + 0.03, pz + 0.11))
    # Door mirrors at the foot of the windscreen.
    screen = next((g for g in S["glass"] if g[2] == "screen"), None)
    if screen and S.get("mirrors", True):
        d = screen[1] - 0.05 if S.get("cab_forward") else screen[0] + 0.3
        zb, zs, zr, wf, _ = prof.at(d)
        w = W / 2 * wf
        yy = -L / 2 + d
        for sx in (-1, 1):
            # A stalk from the door to a housing with the glass facing back.
            m.box("rubber", (min(sx * (w - 0.02), sx * (w + 0.06)), yy + 0.02, zs + 0.03), (max(sx * (w - 0.02), sx * (w + 0.06)), yy + 0.08, zs + 0.07))
            x0, x1 = sorted((sx * (w + 0.04), sx * (w + 0.2)))
            m.box("carpaint", (x0, yy, zs + 0.04), (x1, yy + 0.08, zs + 0.15))
            m.poly("chrome", [(x0 + 0.01, yy + 0.082, zs + 0.05), (x1 - 0.01, yy + 0.082, zs + 0.05), (x1 - 0.01, yy + 0.082, zs + 0.14), (x0 + 0.01, yy + 0.082, zs + 0.14)], out=(0, 1, 0))


def all_wheels(m, S, dual_rear=False):
    L, W, r = S["L"], S["W"], S["r"]
    tw = S.get("tw", 0.22)
    for k, d in enumerate(S["wheels"]):
        y = -L / 2 + d
        for sx in (-1, 1):
            x = sx * (W / 2 - tw / 2 - 0.04)
            wheel(m, x, y, r, tw, sx)
            if dual_rear and k > 0:
                wheel(m, x - sx * (tw + 0.02), y, r, tw, -sx, rim="dark")


# ---- the vehicles ---------------------------------------------------------------------
# keys: (d from nose, floor z, shoulder z, roof z, width factor, roof width factor)

def keys(L, a, b, c, e, ground=0.18, nose=0.6, hood=0.92, belt=0.96, roof=1.44, deck=1.0, tail=0.9, rwf=0.78, tailgate=False):
    """A passenger car's keyframes from its design lines: the windscreen runs
    from a to b, the roof to c, the back glass to e; the nose and tail are
    rounded in plan and section; with `tailgate` the back drops near-vertical."""
    g = ground
    k = [
        (0.0, g + 0.18, nose, nose + 0.03, 0.8, 0.8),
        (0.05, g + 0.09, nose + 0.08, nose + 0.12, 0.9, 0.8),
        (0.16, g + 0.03, nose + 0.15, nose + 0.2, 0.96, 0.82),
        (0.38, g + 0.01, nose + 0.21, nose + 0.27, 0.99, 0.83),
        (0.75, g, hood - 0.04, hood + 0.03, 1.0, 0.84),
        (a, g, hood, hood + 0.07, 1.0, 0.84),
        (b - 0.16, g, belt - 0.01, roof - 0.04, 1.0, rwf + 0.01),
        (b, g, belt, roof, 1.0, rwf),
        (c, g, belt + 0.03, roof - 0.02, 1.0, rwf),
        (e, g, deck, deck + 0.06, 1.0, 0.84),
    ]
    t0 = max(e + 0.05, L - 0.42)
    if tailgate:
        k += [(L - 0.1, g + 0.05, deck - 0.03, deck + 0.01, 0.97, 0.84), (L, g + 0.17, tail, tail + 0.03, 0.88, 0.82)]
    else:
        k += [
            (t0, g + 0.02, deck - 0.01, deck + 0.04, 0.99, 0.84),
            (max(t0 + 0.05, L - 0.15), g + 0.06, deck - 0.04, deck, 0.96, 0.84),
            (max(t0 + 0.08, L - 0.04), g + 0.13, deck - 0.09, deck - 0.05, 0.9, 0.82),
            (L, g + 0.2, tail, tail + 0.03, 0.84, 0.8),
        ]
    return k


CARS = {
    "hatch": dict(
        L=4.25, W=1.79, r=0.315, wheels=(0.86, 3.5),
        keys=keys(4.25, 1.3, 2.1, 3.6, 4.08, nose=0.58, hood=0.9, belt=0.98, roof=1.46, deck=1.1, tail=0.86, tailgate=True),
        glass=[(1.32, 2.08, "screen"), (2.1, 3.62, "side"), (3.62, 4.06, "back")],
        pillars=[(2.85, 2.95), (3.42, 3.62)],
    ),
    "sedan": dict(
        L=4.75, W=1.83, r=0.325, wheels=(0.98, 3.8),
        keys=keys(4.75, 1.5, 2.32, 3.45, 4.12, hood=0.92, belt=0.96, roof=1.43, deck=1.02, tail=0.9),
        glass=[(1.52, 2.3, "screen"), (2.32, 3.6, "side"), (3.6, 4.1, "back")],
        pillars=[(3.0, 3.1)],
    ),
    "estate": dict(
        L=4.8, W=1.84, r=0.325, wheels=(0.98, 3.8),
        keys=keys(4.8, 1.5, 2.32, 4.4, 4.72, belt=0.97, roof=1.46, deck=1.3, tail=0.9, tailgate=True),
        glass=[(1.52, 2.3, "screen"), (2.32, 4.45, "side"), (4.45, 4.72, "back")],
        pillars=[(3.0, 3.1), (3.86, 3.98)],
    ),
    "suv": dict(
        L=4.65, W=1.89, r=0.37, tw=0.25, wheels=(0.98, 3.73),
        keys=keys(4.65, 1.35, 2.12, 4.22, 4.55, ground=0.26, nose=0.78, hood=1.1, belt=1.14, roof=1.68, deck=1.45, tail=1.05, rwf=0.8, tailgate=True),
        glass=[(1.37, 2.1, "screen"), (2.12, 4.28, "side"), (4.28, 4.55, "back")],
        pillars=[(2.95, 3.06), (3.75, 3.88)],
    ),
    "coupe": dict(
        L=4.5, W=1.86, r=0.33, tw=0.25, wheels=(1.05, 3.65),
        keys=keys(4.5, 1.6, 2.55, 3.15, 4.15, ground=0.15, nose=0.52, hood=0.84, belt=0.88, roof=1.3, deck=0.96, tail=0.86, rwf=0.75),
        glass=[(1.62, 2.53, "screen"), (2.55, 3.2, "side"), (3.2, 4.12, "back")],
    ),
}
CARS["taxi"] = dict(CARS["sedan"])
_pk = keys(5.35, 1.4, 2.2, 3.12, 3.18, ground=0.29, nose=0.86, hood=1.15, belt=1.19, roof=1.8, deck=1.2, tail=1.12, rwf=0.8, tailgate=True)
CARS["pickup"] = dict(
    L=5.35, W=1.9, r=0.38, tw=0.26, wheels=(1.0, 4.15),
    keys=[k for k in _pk if k[0] < 3.12] + [(3.12, 0.29, 1.2, 1.79, 1.0, 0.8), (3.26, 0.29, 1.2, 1.22, 1.0, 0.98), (5.25, 0.31, 1.2, 1.22, 1.0, 0.98), (5.35, 0.42, 1.12, 1.16, 0.96, 0.96)],
    glass=[(1.42, 2.18, "screen"), (2.2, 3.1, "side"), (3.1, 3.2, "back"), (3.3, 5.28, "cover")],
    pillars=[(2.6, 2.7)],
)
CARS["van"] = dict(
    L=5.0, W=2.0, r=0.34, tw=0.23, wheels=(0.95, 4.2), crown=0.04,
    keys=[(0.0, 0.36, 0.72, 0.76, 0.88, 0.8), (0.1, 0.27, 0.82, 0.86, 0.96, 0.84), (0.35, 0.24, 0.92, 0.98, 0.99, 0.88),
          (0.75, 0.23, 1.04, 1.12, 1.0, 0.9), (1.45, 0.23, 1.1, 2.18, 1.0, 0.93), (1.75, 0.23, 1.11, 2.36, 1.0, 0.95),
          (4.85, 0.24, 1.12, 2.36, 1.0, 0.95), (5.0, 0.36, 1.08, 2.3, 0.97, 0.94)],
    glass=[(0.77, 1.5, "screen"), (1.5, 2.3, "side")],
    pillars=[], pillar_role="carpaint", head_d=0.32, tail_d=0.1, plate_z=0.45, cab_forward=True,
)

BUS = dict(
    L=12.0, W=2.55, r=0.5, tw=0.3, wheels=(2.7, 8.6), crown=0.04,
    keys=[(0.0, 0.32, 1.02, 3.0, 0.97, 0.96), (0.12, 0.3, 1.02, 3.08, 1.0, 0.97), (11.88, 0.3, 1.02, 3.08, 1.0, 0.97), (12.0, 0.32, 1.02, 3.0, 0.97, 0.96)],
    glass=[(0.25, 11.3, "side")],
    pillars=[(0.25 + i * 1.47, 0.25 + i * 1.47 + 0.14) for i in range(8)], pillar_role="rubber",
    head_d=0, tail_d=0,
)
TRUCK_CAB = dict(
    L=2.3, W=2.3, r=0.48, tw=0.28, wheels=(1.05,), crown=0.05,
    keys=[(0.0, 0.48, 1.25, 1.35, 0.94, 0.9), (0.1, 0.42, 1.3, 1.45, 0.99, 0.92), (0.4, 0.4, 1.36, 1.7, 1.0, 0.94),
          (0.85, 0.4, 1.4, 2.62, 1.0, 0.94), (1.05, 0.4, 1.42, 2.72, 1.0, 0.95), (2.3, 0.4, 1.42, 2.72, 1.0, 0.95)],
    glass=[(0.42, 0.85, "screen"), (0.9, 1.7, "side")],
    pillars=[], pillar_role="carpaint", head_d=0.25, tail_d=0,
)


def car(M, name, S, at):
    M.piece(name, at)
    m = M.m
    ax, ay, _ = at
    S = dict(S)
    # Draw at the reference position: offset every point by `at`.
    off = Vector(at)
    sub = Shifted(m, off)
    rings, ds = body(sub, S)
    lights(sub, S, rings, ds)
    all_wheels(sub, S)
    if name == "taxi":
        prof = Profile(S["keys"])
        d = 3.0
        zr = prof.at(d)[2] + S.get("crown", 0.03)
        y = -S["L"] / 2 + d
        sub.box("taxisign", (-0.38, y - 0.12, zr + 0.02), (0.38, y + 0.12, zr + 0.24))
        sub.box("rubber", (-0.3, y - 0.08, zr - 0.02), (0.3, y + 0.08, zr + 0.03))
    if name == "van":
        # Sliding-door rail and rear-door seam on the panel sides, roof ribs.
        L, W = S["L"], S["W"]
        for k in range(5):
            y = -L / 2 + 2.0 + k * 0.6
            sub.box("carpaint", (-W / 2 * 0.9, y, 2.39), (W / 2 * 0.9, y + 0.08, 2.43))
        for sx in (-1, 1):
            sub.box("rubber", (sx * W / 2 - 0.01, -L / 2 + 2.6, 1.85), (sx * W / 2 + 0.02, -L / 2 + 4.0, 1.88))
        sub.poly("carglass", [(-0.85, L / 2 + 0.014, 1.5), (0.85, L / 2 + 0.014, 1.5), (0.85, L / 2 + 0.014, 2.1), (-0.85, L / 2 + 0.014, 2.1)], out=(0, 1, 0))
        sub.box("rubber", (-0.02, L / 2 - 0.01, 0.55), (0.02, L / 2 + 0.02, 2.2))


def bus(M, at):
    M.piece("bus", at)
    S = dict(BUS)
    sub = Shifted(M.m, Vector(at))
    body(sub, S)
    L, W = S["L"], S["W"]
    y = -L / 2
    # Windscreen and destination sign on the flat front; doors on the kerb side (-x).
    sub.poly("carglass", [(-1.18, y - 0.012, 1.1), (1.18, y - 0.012, 1.1), (1.18, y - 0.012, 2.62), (-1.18, y - 0.012, 2.62)], out=(0, -1, 0))
    sub.poly("led", [(-1.0, y - 0.013, 2.68), (1.0, y - 0.013, 2.68), (1.0, y - 0.013, 2.92), (-1.0, y - 0.013, 2.92)], out=(0, -1, 0))
    for sx in (-1, 1):
        x0, x1 = sorted((sx * 1.18, sx * 0.8))
        sub.poly("headlight", [(x0, y - 0.014, 0.62), (x1, y - 0.014, 0.62), (x1, y - 0.014, 0.76), (x0, y - 0.014, 0.76)], out=(0, -1, 0))
        x0, x1 = sorted((sx * 1.2, sx * 0.95))
        sub.poly("taillight", [(x0, L / 2 + 0.012, 0.7), (x1, L / 2 + 0.012, 0.7), (x1, L / 2 + 0.012, 1.1), (x0, L / 2 + 0.012, 1.1)], out=(0, 1, 0))
    sub.box("rubber", (-1.25, y - 0.04, 0.3), (1.25, y + 0.05, 0.55))
    sub.box("rubber", (-1.25, L / 2 - 0.05, 0.3), (1.25, L / 2 + 0.04, 0.55))
    sub.poly("carglass", [(-0.9, L / 2 + 0.012, 1.9), (0.9, L / 2 + 0.012, 1.9), (0.9, L / 2 + 0.012, 2.65), (-0.9, L / 2 + 0.012, 2.65)], out=(0, 1, 0))
    for d0 in (0.35, 5.2):
        yy = y + d0
        sub.poly("carglass", [(-W / 2 - 0.012, yy, 0.38), (-W / 2 - 0.012, yy + 1.2, 0.38), (-W / 2 - 0.012, yy + 1.2, 1.05), (-W / 2 - 0.012, yy, 1.05)], out=(-1, 0, 0))
        sub.box("rubber", (-W / 2 - 0.02, yy + 0.58, 0.32), (-W / 2 + 0.01, yy + 0.62, 2.62))
    # Roof pods: air conditioning and the battery or gas tanks.
    sub.box("carpaint", (-0.9, y + 3.0, 3.08), (0.9, y + 5.6, 3.38))
    sub.box("carpaint", (-0.8, y + 7.5, 3.08), (0.8, y + 9.8, 3.3))
    for d in S["wheels"]:
        for sx in (-1, 1):
            wheel(sub, sx * (W / 2 - S["tw"] / 2 - 0.06), y + d, S["r"], S["tw"], sx)


def truck(M, at):
    """A box truck: a cab-over chassis cab and a 5.2 m box behind, dual rear wheels."""
    M.piece("truck", at)
    sub = Shifted(M.m, Vector(at))
    S = dict(TRUCK_CAB)
    L = 7.6
    y0 = -L / 2
    S2 = dict(S, L=S["L"])
    # The cab is lofted at the front of the truck.
    cab = Shifted(M.m, Vector(at) + Vector((0, y0 + S["L"] / 2, 0)))
    rings, ds = body(cab, S2)
    lights(cab, S2, rings, ds)
    W = 2.4
    # Chassis rails, fuel tank, the box.
    sub.box("dark", (-0.5, y0 + 2.2, 0.55), (0.5, L / 2 - 0.2, 0.85))
    sub.box("chrome", (0.55, y0 + 2.4, 0.55), (1.05, y0 + 3.4, 0.95))
    bx0 = y0 + 2.42
    sub.box("cargo", (-W / 2, bx0, 0.95), (W / 2, L / 2, 3.55))
    sub.box("rubber", (-W / 2 - 0.02, bx0, 0.92), (W / 2 + 0.02, L / 2 + 0.02, 1.02))
    for sx in (-1, 1):
        for k in range(1, 9):
            yy = bx0 + k * (L / 2 - bx0) / 9
            sub.box("rubber", (sx * W / 2 - 0.015, yy, 1.02), (sx * W / 2 + 0.015, yy + 0.05, 3.5))
    sub.box("rubber", (-0.02, L / 2, 1.0), (0.02, L / 2 + 0.025, 3.5))
    for sx in (-1, 1):
        x0, x1 = sorted((sx * 1.15, sx * 0.9))
        sub.poly("taillight", [(x0, L / 2 + 0.03, 0.75), (x1, L / 2 + 0.03, 0.75), (x1, L / 2 + 0.03, 0.9), (x0, L / 2 + 0.03, 0.9)], out=(0, 1, 0))
    sub.box("rubber", (-1.2, L / 2 - 0.1, 0.55), (1.2, L / 2 + 0.03, 0.7))
    tw, r = S["tw"], S["r"]
    for sx in (-1, 1):
        x = sx * (2.3 / 2 - tw / 2 - 0.04)
        wheel(sub, x, y0 + 1.05, r, tw, sx)
        wheel(sub, x, L / 2 - 1.7, r, tw, sx)
        wheel(sub, x - sx * (tw + 0.02), L / 2 - 1.7, r, tw, -sx, rim="dark")
    # Rear wheel arches in the box's skirt.
    sub.box("dark", (-W / 2 + 0.05, L / 2 - 2.35, 0.55), (W / 2 - 0.05, L / 2 - 1.05, 0.95))


class Shifted:
    """Draws into a Mesh with every point moved by `off` (the piece's reference position)."""

    def __init__(self, m, off):
        self.m, self.off = m, off

    def _p(self, p):
        return tuple(Vector(p) + self.off)

    def poly(self, role, pts, out=None, uvs=None, smooth=False):
        return self.m.poly(role, [self._p(p) for p in pts], out=out, uvs=uvs, smooth=smooth)

    def box(self, role, lo, hi, skip=()):
        self.m.box(role, self._p(lo), self._p(hi), skip)

    def __getattr__(self, k):
        return getattr(self.m, k)


ORDER = ["hatch", "sedan", "estate", "suv", "coupe", "taxi", "pickup", "van"]


def build(out, bake=True):
    M = Model(ID)
    x = -20.0
    for name in ORDER:
        car(M, name, CARS[name], (x, 0, 0))
        x += 4.0
    bus(M, (x + 1.0, 0, 0))
    truck(M, (x + 6.0, 0, 0))
    M.export(out, bake, size=2048, samples=128, smooth=2.0)
