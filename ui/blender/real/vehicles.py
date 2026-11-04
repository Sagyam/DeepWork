# Vehicles for the realistic city: the cars that park on drives and in
# bays and drive round the blocks (ui/src/city/traffic.ts), replacing the
# low-poly kit's four cars and bus.
#
# Built the way car models are: a coarse cage of cross-sections along the
# car (underbody, rocker, side, shoulder, belt, roof rail, roof), smoothed
# by Catmull-Clark subdivision with creases on the feature lines (shoulder,
# belt, cowl, the base of the back glass), so panels are smooth and the
# lines crisp. Wheel arches are cut by booleans, which leave the wheel
# wells; a pickup's bed is cut the same way. Everything that sits on the
# skin (window frames and glass, pillars, lamps, grille, intakes, number
# plates, panel seams) is projected onto the subdivided body by raycasts
# and laid a few millimetres above it, so it follows its curves. Door
# handles, mirrors, roof rails and wheels (tyres, multi-spoke rims, brake
# discs and calipers) are modelled on.
#
# Pieces (one per vehicle, at the origin, nose toward -y, i.e. glTF +z):
#   hatch, sedan, estate, suv, coupe, taxi, pickup, van, bus, truck
# Roles: carpaint (tinted per vehicle by the app), carglass, dark (wells,
# grilles, intakes), rubber (black trim and pillars), seam (panel gaps),
# chrome, rim, tyre, brake, caliper, headlight, taillight, indicator,
# plate, taxisign, led, cargo.
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from lib import Model

ID = "cars"
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def lerp(a, b, t):
    return a + (b - a) * t


# ---- the body: a subdivided cage ---------------------------------------------------------
# A station: (d from the nose, floor z, shoulder z, belt z, roof z, half-width
# factor at the shoulder, roof-rail half-width factor[, crease across]). At
# the hood and boot "belt" is the fender top and "roof" the panel's crown.

RING_CREASE = (0.25, 0.5, 0.0, 1.0, 0.7, 0.35)  # along the car, at points p0-p5


class Body:
    def __init__(self, S):
        self.S = S
        self.L, self.W = S["L"], S["W"]
        self.st = sorted(S["stations"])

    def at(self, d):
        """The station values interpolated at d."""
        st = self.st
        if d <= st[0][0]:
            return st[0][1:7]
        for a, b in zip(st, st[1:]):
            if d <= b[0]:
                t = (d - a[0]) / max(1e-6, b[0] - a[0])
                return tuple(lerp(p, q, t) for p, q in zip(a[1:7], b[1:7]))
        return st[-1][1:7]

    def ring(self, s):
        d, floor, sh, belt, roof, wf, rw = s[:7]
        W = self.W
        w = W / 2 * wf
        belt = max(belt, sh + 0.02)
        rail = max(belt + 0.015, roof - 0.07)
        top = max(rail + 0.012, roof)
        wr = min(rw * W / 2, w * 0.94)
        half = [(w * 0.8, floor), (w * 0.965, floor + 0.07), (w * 0.997, lerp(floor + 0.07, sh, 0.5)), (w, sh), (w * self.S.get("step", 0.935), belt), (wr, rail)]
        y = -self.L / 2 + d
        left = [Vector((-x, y, z)) for x, z in half]
        right = [Vector((x, y, z)) for x, z in reversed(half)]
        return [Vector((0, y, floor))] + left + [Vector((0, y, top))] + right

    def cage(self):
        """The cage as a bmesh, creases set, faces facing out."""
        bm = bmesh.new()
        cl = bm.edges.layers.float.new("crease_edge")
        rings = [[bm.verts.new(p) for p in self.ring(s)] for s in self.st]
        n = len(rings[0])
        point = [None] + list(range(6)) + [None] + list(range(5, -1, -1))  # ring index -> p0-p5
        crease = self.S.get("ring_crease", RING_CREASE)
        for i in range(len(rings) - 1):
            a, b = rings[i], rings[i + 1]
            for k in range(n):
                j = (k + 1) % n
                bm.faces.new((a[k], a[j], b[j], b[k]))
        for k in range(n):
            if point[k] is not None:
                for i in range(len(rings) - 1):
                    e = bm.edges.get((rings[i][k], rings[i + 1][k]))
                    e[cl] = crease[point[k]]
        for i, s in enumerate(self.st):
            if len(s) > 7 and s[7]:
                for k in range(n):
                    e = bm.edges.get((rings[i][k], rings[i][(k + 1) % n]))
                    e[cl] = s[7]
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return bm


def mesh_object(name, bm, role):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bpy.data.materials.get(role) or bpy.data.materials.new(role))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def cylinder_x(x0, x1, y, z, r, seg=40):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=abs(x1 - x0))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=((x0 + x1) / 2, y, z))
    return bm


def block(lo, hi):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    c = (Vector(lo) + Vector(hi)) / 2
    s = Vector(hi) - Vector(lo)
    bmesh.ops.scale(bm, verts=bm.verts, vec=s)
    bmesh.ops.translate(bm, verts=bm.verts, vec=c)
    return bm


def evaluate(body, cutters, levels=2):
    """Subdivides the body's cage, cuts the cutters (bmesh, role) out of it, returns the result as a bmesh."""
    ob = mesh_object("body", body.cage(), "carpaint")
    sub = ob.modifiers.new("subdiv", "SUBSURF")
    sub.levels = sub.render_levels = levels
    temps = [ob]
    for k, (bm, role) in enumerate(cutters):
        oc = mesh_object(f"cut{k}", bm, role)
        temps.append(oc)
        b = ob.modifiers.new(f"bool{k}", "BOOLEAN")
        b.operation, b.object, b.solver, b.material_mode = "DIFFERENCE", oc, "EXACT", "TRANSFER"
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    out = bmesh.new()
    out.from_mesh(me)
    roles = [m.name.split(".")[0] for m in me.materials]
    ev.to_mesh_clear()
    for o in temps:
        m = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(m)
    return out, roles


# ---- drawing on the body ------------------------------------------------------------------


class Car:
    """Draws one vehicle into the model's mesh, offset to its place in the bake."""

    def __init__(self, m, off, S):
        self.m, self.off, self.S = m, Vector(off), S
        self.L, self.W = S["L"], S["W"]
        self.body = Body(S) if "stations" in S else None
        self.bvh = None

    def poly(self, role, pts, out, smooth=True):
        self.m.poly(role, [tuple(Vector(p) + self.off) for p in pts], out=tuple(out), smooth=smooth)

    def emit(self, bm, roles):
        for f in bm.faces:
            self.poly(roles[f.material_index] if f.material_index < len(roles) else "carpaint", [v.co for v in f.verts], f.normal)

    def skin(self, cutters=(), levels=2):
        bm, roles = evaluate(self.body, cutters, levels)
        self.emit(bm, roles)
        self.bvh = BVHTree.FromBMesh(bm)
        bm.free()

    def zt(self, d, x=0.0):
        """The skin's height seen from above at (x, d): subdivision pulls it inside the cage."""
        h = self.hit((x, -self.L / 2 + d, 5), -Z)
        return h[0].z if h else self.body.at(d)[3]

    # Projection onto the skin.
    def hit(self, p, d):
        loc, nrm, _, _ = self.bvh.ray_cast(Vector(p) - d * 30, d, 60)
        if loc is None:
            return None
        return loc, (nrm if nrm.dot(d) < 0 else -nrm)

    def decal(self, role, corners, origin, U, V, d, off=0.004, n=(4, 2)):
        """A patch with these four (u, v) corners in the plane (origin, U, V), projected along d onto the skin."""
        nu, nv = n
        (a, b, c, e) = [Vector(q) for q in corners]
        grid = []
        for j in range(nv + 1):
            row = []
            for i in range(nu + 1):
                s, t = i / nu, j / nv
                uv = lerp(lerp(a, b, s), lerp(e, c, s), t)
                row.append(self.hit(origin + U * uv.x + V * uv.y, d))
            grid.append(row)
        for j in range(nv):
            for i in range(nu):
                cell = [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
                if any(h is None for h in cell):
                    continue
                nrm = sum((h[1] for h in cell), Vector()).normalized()
                self.poly(role, [h[0] + h[1] * off for h in cell], nrm)

    def side(self, role, corners, off=0.004, n=(4, 2), sides=(-1, 1)):
        """corners in (d from the nose, z), on both sides."""
        for sx in sides:
            self.decal(role, corners, Vector((0, -self.L / 2, 0)), Y, Z, X * -sx, off, n)

    def front(self, role, corners, off=0.004, n=(3, 2), mirror=True):
        """corners in (x, z) seen from the front; mirrored to the other side unless on the centre line."""
        self.decal(role, corners, Vector((0, 0, 0)), X, Z, Y, off, n)
        if mirror:
            self.decal(role, [(-u, v) for u, v in corners], Vector((0, 0, 0)), X, Z, Y, off, n)

    def rear(self, role, corners, off=0.004, n=(3, 2), mirror=True):
        self.decal(role, corners, Vector((0, 0, 0)), X, Z, -Y, off, n)
        if mirror:
            self.decal(role, [(-u, v) for u, v in corners], Vector((0, 0, 0)), X, Z, -Y, off, n)

    def top(self, role, corners, off=0.004, n=(3, 3)):
        """corners in (x, d from the nose), seen from above."""
        self.decal(role, corners, Vector((0, -self.L / 2, 0)), X, Y, -Z, off, n)

    def slope(self, role, a, b, corners, off=0.004, n=(6, 3)):
        """corners in (x, s) on the plane through a and b ((d, z) points), s from a toward b: windscreens, back glass."""
        pa = Vector((0, -self.L / 2 + a[0], a[1]))
        pb = Vector((0, -self.L / 2 + b[0], b[1]))
        V = (pb - pa).normalized()
        out = Vector((0, -V.z, V.y)) if V.y > 0 else Vector((0, V.z, -V.y))
        self.decal(role, corners, pa, X, V, -out, off, n)

    def box(self, role, centre, nrm, along, size):
        """A small box sitting on the skin: size (along, across, out)."""
        n = Vector(nrm).normalized()
        a = (Vector(along) - n * Vector(along).dot(n)).normalized()
        b = n.cross(a)
        c = Vector(centre)
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2]
        pts = {}
        for i, sa in enumerate((-1, 1)):
            for j, sb in enumerate((-1, 1)):
                for k, sz in enumerate((0, 1)):
                    pts[i, j, k] = c + a * sa * hx + b * sb * hy + n * sz * hz
        P = lambda *ks: [pts[k] for k in ks]  # noqa: E731
        self.poly(role, P((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)), n, False)
        self.poly(role, P((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)), -b, False)
        self.poly(role, P((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)), b, False)
        self.poly(role, P((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)), -a, False)
        self.poly(role, P((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)), a, False)

    def ellipsoid(self, role, c, r, seg=12, rings=7, flat_back=None):
        c, r = Vector(c), Vector(r)
        rows = []
        for i in range(rings + 1):
            th = math.pi * i / rings
            row = []
            for j in range(seg):
                ph = math.tau * j / seg
                p = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
                if flat_back is not None and p.dot(flat_back) > 0.35:
                    p -= flat_back * (p.dot(flat_back) - 0.35)
                row.append(c + Vector((p.x * r.x, p.y * r.y, p.z * r.z)))
            rows.append(row)
        for i in range(rings):
            for j in range(seg):
                jj = (j + 1) % seg
                q = [rows[i][j], rows[i + 1][j], rows[i + 1][jj], rows[i][jj]]
                mid = sum(q, Vector()) / 4 - c
                if i == 0:
                    self.poly(role, [rows[0][0], rows[1][j], rows[1][jj]], mid)
                elif i == rings - 1:
                    self.poly(role, [rows[i][j], rows[rings][0], rows[i][jj]], mid)
                else:
                    self.poly(role, q, mid)

    # Running gear.
    def wheel(self, x, y, R, tw, sx, seg=28, caliper="caliper", rim="rim"):
        """A tyre with a ten-spoke rim, a brake disc and caliper behind; axle along x, outer face toward sx."""
        def P(a, th, rho):
            return Vector((x + sx * a, y + rho * math.cos(th), R + rho * math.sin(th)))

        prof = [(-tw / 2, 0.66 * R), (-tw / 2 + 0.008, 0.86 * R), (-tw / 2 + 0.03, 0.975 * R), (-tw * 0.3, R), (tw * 0.3, R), (tw / 2 - 0.03, 0.975 * R), (tw / 2 - 0.008, 0.86 * R), (tw / 2, 0.66 * R)]
        for i in range(seg):
            t0, t1 = i / seg * math.tau, (i + 1) / seg * math.tau
            tm = (t0 + t1) / 2
            for (a0, p0), (a1, p1) in zip(prof, prof[1:]):
                am = (a0 + a1) / 2
                radial = Vector((0, math.cos(tm), math.sin(tm)))
                axial = Vector((sx * (1 if am > 0 else -1), 0, 0))
                w = min(1.0, abs(p1 - p0) / max(1e-6, abs(a1 - a0) + abs(p1 - p0)) * 2)
                self.poly("tyre", [P(a0, t0, p0), P(a0, t1, p0), P(a1, t1, p1), P(a1, t0, p1)], radial * (1 - w * 0.9) + axial * w)
        face = tw / 2 - 0.01
        lip, inner, hub = 0.655 * R, 0.6 * R, 0.17 * R
        ring = lambda rho, a: [P(a, i / seg * math.tau, rho) for i in range(seg)]  # noqa: E731
        o = Vector((sx, 0, 0))
        # Lip, barrel (dark, deep), disc and caliper behind the spokes.
        ra, rb = ring(lip, face), ring(inner, face - 0.012)
        for i in range(seg):
            j = (i + 1) % seg
            self.poly(rim, [ra[i], ra[j], rb[j], rb[i]], o)
        self.poly("dark", ring(inner, face - 0.11), o)
        dr, dq = ring(0.5 * R, face - 0.07), ring(0.5 * R, face - 0.09)
        self.poly("brake", dr, o)
        for i in range(seg):
            j = (i + 1) % seg
            self.poly("brake", [dr[i], dr[j], dq[j], dq[i]], (dr[i] + dr[j]) / 2 - Vector((x, y, R)))
        self.poly(caliper, [P(face - 0.045, 0.3, 0.38 * R), P(face - 0.045, 0.95, 0.38 * R), P(face - 0.045, 0.95, 0.56 * R), P(face - 0.045, 0.3, 0.56 * R)], o, False)
        # Ten spokes in five pairs, dished: the hub stands proud of the lip.
        for k in range(5):
            for pair in (-0.13, 0.13):
                th = k / 5 * math.tau + pair + 0.2
                w0, w1 = 0.055, 0.035
                pts = [P(face + 0.012, th - w0, hub), P(face + 0.012, th + w0, hub), P(face - 0.01, th + w1 * 0.6, inner), P(face - 0.01, th - w1 * 0.6, inner)]
                self.poly(rim, pts, o)
                # The spoke's sides, so it has depth.
                for e0, e1 in ((0, 3), (1, 2)):
                    a0, a1 = pts[e0], pts[e1]
                    mid = (a0 + a1) / 2
                    centre_line = P(face, th, (hub + inner) / 2)
                    self.poly(rim, [a0, a1, a1 - o * 0.03, a0 - o * 0.03], mid - centre_line)
        self.poly(rim, ring(hub, face + 0.013), o)
        self.poly("chrome", ring(hub * 0.45, face + 0.016), o)

    def wheels(self, dual=False):
        S = self.S
        R, tw = S["r"], S.get("tw", 0.225)
        for k, d in enumerate(S["wheels"]):
            y = -self.L / 2 + d
            for sx in (-1, 1):
                x = sx * (self.W / 2 - tw / 2 - S.get("inset", 0.035))
                self.wheel(x, y, R, tw, sx)
                if dual and k > 0:
                    self.wheel(x - sx * (tw + 0.02), y, R, tw, -sx, caliper="dark", rim="dark")

    def arches(self, extra=0.07):
        S = self.S
        R = S["r"]
        out = []
        for d in S["wheels"]:
            y = -self.L / 2 + d
            for sx in (-1, 1):
                x0, x1 = sorted((sx * (self.W / 2 - 0.42), sx * (self.W / 2 + 0.3)))
                out.append((cylinder_x(x0, x1, y, R + 0.025, R + extra), "dark"))
        return out


# ---- a passenger car's dressing -----------------------------------------------------------


def dress(c):
    """Glass, lamps, grille, seams, handles, mirrors and plates for a car from its spec."""
    S, B, L, W = c.S, c.body, c.L, c.W
    belt = lambda d: B.at(d)[2]  # noqa: E731
    roof = lambda d: B.at(d)[3]  # noqa: E731
    half = lambda d: W / 2 * B.at(d)[4]  # noqa: E731
    rail = lambda d: W / 2 * B.at(d)[5]  # noqa: E731
    # Windscreen and back glass: a black frame and the glass inside it,
    # between heights measured on the skin itself.
    a, b = S["screen"]
    pa, pb = (a, c.zt(a, half(a) * 0.5) + 0.01), (b, c.zt(b) - 0.03)
    ln = (Vector(pb) - Vector(pa)).length
    wa, wb = half(a) * 0.84, rail(b) * 0.86
    c.slope("rubber", pa, pb, [(-wa, 0.0), (wa, 0.0), (wb, ln), (-wb, ln)], 0.006, n=(10, 5))
    c.slope("carglass", pa, pb, [(-wa + 0.05, 0.05), (wa - 0.05, 0.05), (wb - 0.06, ln - 0.05), (-wb + 0.06, ln - 0.05)], 0.011, n=(10, 5))
    if S.get("back"):
        a, b = S["back"]
        pa, pb = (a, c.zt(a) - 0.03), (b, c.zt(b, rail(b) * 0.5) + 0.01)
        ln = (Vector(pb) - Vector(pa)).length
        wa, wb = rail(a) * 0.86, min(half(b), rail(b) * 1.1) * 0.82
        c.slope("rubber", pa, pb, [(-wa, 0.0), (wa, 0.0), (wb, ln), (-wb, ln)], 0.006, n=(10, 4))
        c.slope("carglass", pa, pb, [(-wa + 0.06, 0.05), (wa - 0.06, 0.05), (wb - 0.06, ln - 0.05), (-wb + 0.06, ln - 0.05)], 0.011, n=(10, 4))
    # Side glass: a black band from the A to the C pillar, the panes in it,
    # up to a little below where the roof turns over.
    d0, d1 = S["band"]
    ar, cr = S.get("a_rake", 0.55), S.get("c_rake", 0.4)
    top = lambda d: c.zt(d, rail(d) * 0.98) - 0.05  # noqa: E731
    zb0, zb1 = belt(d0) + 0.02, belt(d1) + 0.02
    c.side("rubber", [(d0, zb0), (d1, zb1), (d1 - cr, top(d1 - cr)), (d0 + ar, top(d0 + ar))], 0.006, n=(12, 3))
    for p0, p1, r0, r1 in S["panes"]:
        z0, z1 = belt(p0) + 0.05, belt(p1) + 0.05
        c.side("carglass", [(p0, z0), (p1, z1), (p1 - r1, top(p1 - r1) - 0.035), (p0 + r0, top(p0 + r0) - 0.035)], 0.011, n=(8, 3))
    # Panel seams: doors, the sill, the hood and the boot.
    fl = B.at(L / 2)[0]
    ds = S.get("doors", ())
    for d in ds:
        c.side("seam", [(d - 0.004, fl + 0.12), (d + 0.004, fl + 0.12), (d + 0.004, belt(d) - 0.015), (d - 0.004, belt(d) - 0.015)], 0.002, n=(1, 3))
    if ds:
        c.side("seam", [(ds[0], fl + 0.115), (ds[-1], fl + 0.115), (ds[-1], fl + 0.123), (ds[0], fl + 0.123)], 0.002, n=(6, 1))
        # Handles, behind each door's leading seam.
        for d in ds[:-1]:
            z = belt(d + 0.3) - 0.08
            for sx in (-1, 1):
                h = c.hit((sx * 3, -L / 2 + d + 0.28, z), X * -sx)
                if h:
                    c.box(S.get("handle", "carpaint"), h[0], h[1], Y, (0.17, 0.028, 0.022))
    hood = S["hood"]
    hx = half(hood[1]) * 0.86
    for sx in (-1, 1):
        c.top("seam", [(sx * hx - 0.004, hood[0]), (sx * hx + 0.004, hood[0]), (sx * hx + 0.004, hood[1]), (sx * hx - 0.004, hood[1])], 0.002, n=(1, 6))
    c.top("seam", [(-hx, hood[1] - 0.004), (hx, hood[1] - 0.004), (hx, hood[1] + 0.004), (-hx, hood[1] + 0.004)], 0.002, n=(6, 1))
    if S.get("boot"):
        b0, b1 = S["boot"]
        bx = half(b0) * 0.84
        c.top("seam", [(-bx, b0 - 0.004), (bx, b0 - 0.004), (bx, b0 + 0.004), (-bx, b0 + 0.004)], 0.002, n=(6, 1))
        for sx in (-1, 1):
            c.top("seam", [(sx * bx - 0.004, b0), (sx * bx + 0.004, b0), (sx * bx + 0.004, b1), (sx * bx - 0.004, b1)], 0.002, n=(1, 4))
    # Fuel flap on the right rear quarter.
    fd = S["wheels"][1] - 0.62
    fz = belt(fd) - 0.17
    c.decal("seam", [(fd - 0.09, fz - 0.08), (fd + 0.09, fz - 0.08), (fd + 0.09, fz + 0.08), (fd - 0.09, fz + 0.08)], Vector((0, -L / 2, 0)), Y, Z, -X, 0.002, (2, 2))
    c.decal("carpaint", [(fd - 0.082, fz - 0.072), (fd + 0.082, fz - 0.072), (fd + 0.082, fz + 0.072), (fd - 0.082, fz + 0.072)], Vector((0, -L / 2, 0)), Y, Z, -X, 0.003, (2, 2))
    # Door mirrors at the foot of the A pillar.
    md = S["screen"][0] + 0.32
    mz = belt(md) + 0.1
    for sx in (-1, 1):
        h = c.hit((sx * 3, -L / 2 + md, mz), X * -sx)
        if not h:
            continue
        base = h[0]
        ctr = base + Vector((sx * 0.14, 0.03, 0.03))
        c.box("rubber", base + Vector((-sx * 0.01, 0.0, -0.03)), Vector((sx, 0, 0)), Y, (0.14, 0.05, 0.08))
        c.ellipsoid("carpaint", ctr, (0.12, 0.05, 0.065), seg=14, rings=6, flat_back=Y)
        g = ctr + Vector((0, 0.034, 0))
        c.poly("chrome", [g + Vector((-0.095, 0, -0.045)), g + Vector((0.095, 0, -0.045)), g + Vector((0.095, 0, 0.045)), g + Vector((-0.095, 0, 0.045))], Y, False)
    front_end(c)
    rear_end(c)


def front_end(c):
    """Headlights (housing, reflector, lens, a running-light strip), indicators, grille with slats, intake, plate."""
    S, B, W = c.S, c.body, c.W
    w = W / 2
    xi, xo, zbi, zti, zbo, zto = S["head"]  # x inner and outer as fractions of the half-width; z of the bottom and top, inner and outer
    shape = [(xi * w, zbi), (xo * w, zbo), (xo * w, zto), (xi * w, zti)]
    c.front("rubber", shape, 0.005, n=(4, 2))

    def inset(q, k):
        cx, cz = sum(p[0] for p in q) / 4, sum(p[1] for p in q) / 4
        return [(lerp(cx, p[0], k), lerp(cz, p[1], k)) for p in q]

    c.front("chrome", inset(shape, 0.86), 0.006)
    c.front("headlight", inset(shape, 0.5), 0.008, n=(2, 1))
    c.front("headlight", [(xi * w + 0.01, zti - 0.025), (xo * w - 0.01, zto - 0.025), (xo * w - 0.01, zto - 0.01), (xi * w + 0.01, zti - 0.01)], 0.009, n=(3, 1))
    c.front("indicator", [(xo * w - 0.07, zbo + 0.008), (xo * w - 0.01, zbo + 0.008), (xo * w - 0.01, zbo + 0.03), (xo * w - 0.07, zbo + 0.03)], 0.009, n=(1, 1))
    gx, gz0, gz1 = S["grille"]
    g = [(-gx * w, gz0), (gx * w, gz0), (gx * w * 0.96, gz1), (-gx * w * 0.96, gz1)]
    c.front("chrome", [(u * 1.04, v + (0.012 if v > gz0 else -0.012)) for u, v in g], 0.003, n=(4, 1), mirror=False)
    c.front("dark", g, 0.005, n=(4, 1), mirror=False)
    for k in range(1, 4):
        z = lerp(gz0, gz1, k / 4)
        c.front("chrome", [(-gx * w * 0.95, z - 0.006), (gx * w * 0.95, z - 0.006), (gx * w * 0.95, z + 0.006), (-gx * w * 0.95, z + 0.006)], 0.007, n=(4, 1), mirror=False)
    fl = B.at(0.25)[0]
    ix, iz0, iz1 = S.get("intake", (0.62, fl + 0.06, fl + 0.2))
    c.front("dark", [(-ix * w, iz0), (ix * w, iz0), (ix * w * 0.94, iz1), (-ix * w * 0.94, iz1)], 0.004, n=(4, 1), mirror=False)
    pz = S.get("plate_front", (gz0 + iz1) / 2 - 0.055)
    c.front("plate", [(-0.26, pz), (0.26, pz), (0.26, pz + 0.11), (-0.26, pz + 0.11)], 0.009, n=(2, 1), mirror=False)


def rear_end(c):
    """Tail lights with a reversing lamp, a black diffuser, rear indicators, the plate in its recess."""
    S, B, W = c.S, c.body, c.W
    w = W / 2
    xi, xo, zbi, zti, zbo, zto = S["tail"]
    shape = [(xi * w, zbi), (xo * w, zbo), (xo * w, zto), (xi * w, zti)]
    c.rear("rubber", shape, 0.004)
    c.rear("taillight", [(lerp(xi, xo, 0.04) * w, zbi + 0.012), (xo * w - 0.012, zbo + 0.012), (xo * w - 0.012, zto - 0.012), (lerp(xi, xo, 0.04) * w, zti - 0.012)], 0.007)
    mid = (zbi + zti) / 2
    c.rear("chrome", [(xi * w + 0.03, mid - 0.012), (lerp(xi, xo, 0.45) * w, mid - 0.012), (lerp(xi, xo, 0.45) * w, mid + 0.012), (xi * w + 0.03, mid + 0.012)], 0.009, n=(2, 1))
    fl = B.at(c.L)[0]
    pz = S.get("plate_rear", fl + 0.33)
    c.rear("rubber", [(-0.3, pz - 0.03), (0.3, pz - 0.03), (0.3, pz + 0.14), (-0.3, pz + 0.14)], 0.003, n=(2, 1), mirror=False)
    c.rear("plate", [(-0.26, pz), (0.26, pz), (0.26, pz + 0.11), (-0.26, pz + 0.11)], 0.007, n=(2, 1), mirror=False)
    c.rear("rubber", [(-0.8 * w, fl + 0.03), (0.8 * w, fl + 0.03), (0.78 * w, fl + 0.14), (-0.78 * w, fl + 0.14)], 0.004, n=(4, 1), mirror=False)
    for sx in (-1, 1):
        c.rear("indicator", [(sx * 0.62 * w, fl + 0.16), (sx * 0.74 * w, fl + 0.16), (sx * 0.74 * w, fl + 0.19), (sx * 0.62 * w, fl + 0.19)], 0.006, n=(1, 1), mirror=False)


def roof_rails(c, d0, d1):
    B, W = c.body, c.W
    for sx in (-1, 1):
        prev = None
        for k in range(9):
            d = lerp(d0, d1, k / 8)
            h = c.hit((sx * W / 2 * B.at(d)[5] * 0.72, -c.L / 2 + d, 4), -Z)
            if not h:
                continue
            p = h[0] + h[1] * 0.045
            if prev is not None:
                c.box("rubber", (prev + p) / 2 - Z * 0.012, Z, p - prev, ((p - prev).length + 0.01, 0.035, 0.025))
            prev = p
        for d in (d0, d1):
            h = c.hit((sx * W / 2 * B.at(d)[5] * 0.72, -c.L / 2 + d, 4), -Z)
            if h:
                c.box("rubber", h[0], h[1], Y, (0.08, 0.04, 0.05))


# ---- the vehicles: dimensions of real cars of each class ------------------------------


def sedan_stations(L, h=0.0):
    """A three-box saloon's sections; h lifts the whole car."""
    return [
        (0.00, 0.30 + h, 0.66 + h, 0.70 + h, 0.72 + h, 0.88, 0.72),
        (0.06, 0.21 + h, 0.72 + h, 0.77 + h, 0.80 + h, 0.95, 0.76, 0.5),
        (0.28, 0.19 + h, 0.76 + h, 0.82 + h, 0.86 + h, 0.99, 0.79),
        (0.85, 0.18 + h, 0.79 + h, 0.86 + h, 0.91 + h, 1.0, 0.80),
        (1.62, 0.18 + h, 0.80 + h, 0.89 + h, 0.93 + h, 1.0, 0.80, 0.7),
        (2.08, 0.18 + h, 0.82 + h, 0.91 + h, 1.30 + h, 1.0, 0.76),
        (2.42, 0.18 + h, 0.83 + h, 0.92 + h, 1.43 + h, 1.0, 0.72, 0.3),
        (3.20, 0.18 + h, 0.84 + h, 0.94 + h, 1.45 + h, 1.0, 0.72),
        (3.62, 0.18 + h, 0.85 + h, 0.95 + h, 1.39 + h, 1.0, 0.73),
        (L - 0.68, 0.19 + h, 0.86 + h, 0.96 + h, 1.03 + h, 1.0, 0.80, 0.6),
        (L - 0.2, 0.22 + h, 0.86 + h, 0.96 + h, 1.01 + h, 0.98, 0.80),
        (L - 0.05, 0.26 + h, 0.83 + h, 0.92 + h, 0.96 + h, 0.94, 0.77, 0.5),
        (L, 0.32 + h, 0.76 + h, 0.84 + h, 0.87 + h, 0.88, 0.72),
    ]


CARS = {
    "sedan": dict(
        L=4.85, W=1.84, r=0.335, wheels=(0.98, 3.83), stations=sedan_stations(4.85),
        screen=(1.64, 2.4), back=(3.6, 4.15), band=(1.75, 3.95), a_rake=0.6, c_rake=0.42,
        panes=[(1.86, 2.98, 0.48, 0.02), (3.05, 3.85, 0.0, 0.32)], doors=(1.72, 3.0, 3.86),
        hood=(0.22, 1.6), boot=(4.18, 4.74),
        head=(0.5, 0.93, 0.67, 0.76, 0.70, 0.78), grille=(0.38, 0.46, 0.66), tail=(0.5, 0.95, 0.84, 0.92, 0.80, 0.9),
    ),
    "hatch": dict(
        L=4.28, W=1.79, r=0.32, wheels=(0.88, 3.5),
        stations=[
            (0.00, 0.29, 0.64, 0.68, 0.70, 0.88, 0.72), (0.06, 0.21, 0.70, 0.75, 0.78, 0.95, 0.76, 0.5),
            (0.26, 0.19, 0.74, 0.80, 0.84, 0.99, 0.79), (0.78, 0.18, 0.77, 0.84, 0.89, 1.0, 0.80),
            (1.30, 0.18, 0.79, 0.88, 0.93, 1.0, 0.80, 0.7), (1.78, 0.18, 0.81, 0.91, 1.32, 1.0, 0.76),
            (2.08, 0.18, 0.82, 0.92, 1.46, 1.0, 0.73, 0.3), (3.30, 0.18, 0.84, 0.95, 1.48, 1.0, 0.73),
            (3.78, 0.19, 0.86, 0.97, 1.44, 1.0, 0.74, 0.4), (4.13, 0.21, 0.86, 0.97, 1.08, 0.99, 0.78, 0.5),
            (4.24, 0.24, 0.84, 0.93, 0.99, 0.96, 0.76, 0.5), (4.28, 0.30, 0.78, 0.86, 0.9, 0.9, 0.72),
        ],
        screen=(1.32, 2.06), back=(3.8, 4.1), band=(1.42, 3.82), a_rake=0.58, c_rake=0.5,
        panes=[(1.54, 2.62, 0.46, 0.02), (2.69, 3.42, 0.0, 0.3)], doors=(1.4, 2.66, 3.45),
        hood=(0.2, 1.28),
        head=(0.48, 0.93, 0.65, 0.74, 0.68, 0.76), grille=(0.36, 0.44, 0.63), tail=(0.62, 0.97, 0.9, 1.04, 0.86, 1.06), plate_rear=0.55,
    ),
    "coupe": dict(
        L=4.7, W=1.9, r=0.345, tw=0.255, wheels=(1.08, 3.78),
        stations=[
            (0.00, 0.26, 0.56, 0.60, 0.62, 0.87, 0.72), (0.07, 0.18, 0.62, 0.67, 0.70, 0.95, 0.76, 0.5),
            (0.3, 0.16, 0.64, 0.70, 0.74, 0.985, 0.78), (1.0, 0.15, 0.70, 0.77, 0.82, 1.0, 0.80),
            (1.85, 0.15, 0.74, 0.83, 0.87, 1.0, 0.80, 0.7), (2.35, 0.15, 0.76, 0.85, 1.18, 1.0, 0.74),
            (2.72, 0.15, 0.77, 0.86, 1.31, 1.0, 0.70, 0.3), (3.2, 0.15, 0.78, 0.88, 1.29, 1.0, 0.70),
            (4.05, 0.16, 0.80, 0.90, 0.98, 1.0, 0.80, 0.5), (4.55, 0.2, 0.80, 0.89, 0.95, 0.98, 0.80),
            (4.66, 0.26, 0.75, 0.83, 0.88, 0.93, 0.76), (4.7, 0.32, 0.68, 0.75, 0.8, 0.86, 0.7),
        ],
        screen=(1.86, 2.68), back=(3.25, 4.05), band=(1.96, 3.5), a_rake=0.66, c_rake=0.42,
        panes=[(2.07, 3.25, 0.55, 0.3)], doors=(1.93, 3.28),
        hood=(0.25, 1.83), boot=(4.08, 4.6),
        head=(0.52, 0.95, 0.56, 0.63, 0.59, 0.65), grille=(0.42, 0.32, 0.5), tail=(0.35, 0.95, 0.80, 0.86, 0.78, 0.86), intake=(0.7, 0.22, 0.33),
    ),
    "suv": dict(
        L=4.62, W=1.87, r=0.37, tw=0.24, wheels=(0.96, 3.66), inset=0.04,
        stations=[
            (0.00, 0.40, 0.86, 0.90, 0.92, 0.88, 0.72), (0.07, 0.30, 0.93, 0.98, 1.01, 0.95, 0.76, 0.5),
            (0.26, 0.28, 0.98, 1.04, 1.08, 0.99, 0.79), (0.8, 0.27, 0.98, 1.05, 1.10, 1.0, 0.80),
            (1.36, 0.27, 1.02, 1.10, 1.15, 1.0, 0.80, 0.7), (1.85, 0.27, 1.04, 1.13, 1.52, 1.0, 0.77),
            (2.12, 0.27, 1.05, 1.14, 1.66, 1.0, 0.75, 0.3), (3.6, 0.27, 1.07, 1.17, 1.69, 1.0, 0.75),
            (4.22, 0.28, 1.08, 1.18, 1.66, 1.0, 0.75, 0.4), (4.5, 0.30, 1.07, 1.17, 1.3, 0.99, 0.78, 0.5),
            (4.58, 0.34, 1.03, 1.12, 1.18, 0.96, 0.76), (4.62, 0.44, 0.94, 1.02, 1.06, 0.9, 0.72),
        ],
        screen=(1.38, 2.1), back=(4.24, 4.48), band=(1.48, 4.3), a_rake=0.52, c_rake=0.3,
        panes=[(1.58, 2.78, 0.44, 0.02), (2.86, 3.66, 0.0, 0.0), (3.74, 4.18, 0.0, 0.25)], doors=(1.46, 2.82, 3.7),
        hood=(0.22, 1.34), roof_rails=(2.3, 4.1), cladding=True, handle="rubber",
        head=(0.5, 0.94, 0.88, 0.97, 0.91, 0.99), grille=(0.42, 0.56, 0.9), tail=(0.6, 0.96, 1.0, 1.1, 0.98, 1.12), plate_rear=0.78, intake=(0.66, 0.38, 0.52),
    ),
}
CARS["estate"] = dict(
    CARS["sedan"], L=4.8,
    stations=sedan_stations(4.8)[:8] + [
        (3.9, 0.18, 0.85, 0.95, 1.45, 1.0, 0.72), (4.48, 0.19, 0.86, 0.96, 1.42, 1.0, 0.74, 0.4), (4.68, 0.22, 0.86, 0.96, 1.14, 0.99, 0.78, 0.5),
        (4.76, 0.26, 0.84, 0.93, 1.0, 0.96, 0.76, 0.5), (4.8, 0.32, 0.78, 0.86, 0.9, 0.9, 0.72),
    ],
    back=(4.5, 4.66), band=(1.75, 4.5), c_rake=0.25, boot=None,
    panes=[(1.86, 2.98, 0.48, 0.02), (3.05, 3.85, 0.0, 0.0), (3.92, 4.38, 0.0, 0.2)],
    roof_rails=(2.5, 4.4), tail=(0.62, 0.96, 0.9, 1.04, 0.86, 1.06), plate_rear=0.55,
)
CARS["taxi"] = dict(CARS["sedan"])
CARS["pickup"] = dict(
    L=5.4, W=1.95, r=0.4, tw=0.265, wheels=(1.02, 4.25), inset=0.04,
    stations=[
        (0.00, 0.5, 0.92, 0.96, 0.98, 0.88, 0.72), (0.08, 0.38, 1.00, 1.05, 1.08, 0.95, 0.76),
        (0.3, 0.34, 1.06, 1.12, 1.15, 0.99, 0.80), (1.0, 0.33, 1.10, 1.17, 1.21, 1.0, 0.82),
        (1.48, 0.33, 1.12, 1.2, 1.24, 1.0, 0.82, 0.7), (1.98, 0.33, 1.13, 1.22, 1.68, 1.0, 0.78),
        (2.2, 0.33, 1.13, 1.22, 1.84, 1.0, 0.76, 0.3), (3.1, 0.33, 1.14, 1.23, 1.86, 1.0, 0.76, 0.5),
        (3.22, 0.33, 1.14, 1.23, 1.3, 1.0, 0.9, 0.8), (5.3, 0.34, 1.14, 1.23, 1.28, 1.0, 0.9),
        (5.4, 0.42, 1.08, 1.17, 1.2, 0.97, 0.88),
    ],
    ring_crease=(0.2, 0.45, 0.0, 0.9, 0.7, 0.6),
    screen=(1.5, 2.17), band=(1.6, 3.12), a_rake=0.5, c_rake=0.06,
    panes=[(1.72, 2.62, 0.4, 0.02), (2.7, 3.06, 0.0, 0.04)], doors=(1.58, 2.66, 3.1),
    hood=(0.25, 1.46), handle="rubber", cladding=True,
    head=(0.46, 0.94, 0.96, 1.07, 0.98, 1.08), grille=(0.42, 0.62, 1.04), tail=(0.86, 0.99, 0.9, 1.15, 0.9, 1.15), intake=(0.6, 0.42, 0.55), plate_rear=0.5,
)
CARS["van"] = dict(
    L=5.05, W=2.0, r=0.345, tw=0.23, wheels=(0.95, 4.25),
    stations=[
        (0.00, 0.36, 0.72, 0.76, 0.78, 0.88, 0.76), (0.08, 0.27, 0.80, 0.85, 0.88, 0.95, 0.80),
        (0.32, 0.24, 0.90, 0.97, 1.02, 0.99, 0.86), (0.75, 0.23, 1.0, 1.08, 1.14, 1.0, 0.9, 0.6),
        (1.38, 0.23, 1.06, 1.12, 1.92, 1.0, 0.94), (1.7, 0.23, 1.07, 1.13, 2.02, 1.0, 0.95, 0.3),
        (4.95, 0.24, 1.08, 1.14, 2.02, 1.0, 0.95), (5.05, 0.34, 1.04, 1.1, 1.96, 0.97, 0.94),
    ],
    ring_crease=(0.2, 0.5, 0.0, 0.7, 0.4, 0.8),
    screen=(0.78, 1.66), band=(0.9, 2.3), a_rake=0.65, c_rake=0.02,
    panes=[(1.0, 2.24, 0.55, 0.02)], doors=(0.92, 2.3, 2.42, 3.9, 4.98),
    hood=(0.2, 0.74), handle="rubber",
    head=(0.5, 0.94, 0.78, 0.9, 0.8, 0.92), grille=(0.42, 0.5, 0.74), tail=(0.86, 0.99, 0.8, 1.4, 0.8, 1.4), plate_rear=0.5, intake=(0.66, 0.32, 0.46),
)


def car(M, name, at):
    S = CARS[name]
    M.piece(name, at)
    c = Car(M.m, at, S)
    cutters = c.arches(0.055)
    if name == "pickup":
        cutters.append((block((-c.W / 2 + 0.09, -c.L / 2 + 3.3, 0.72), (c.W / 2 - 0.09, c.L / 2 - 0.1, 3.0)), "dark"))
    c.skin(cutters)
    dress(c)
    c.wheels()
    if S.get("roof_rails"):
        roof_rails(c, *S["roof_rails"])
    if S.get("cladding"):
        # Black plastic flares round the arches and along the sills.
        B, R = c.body, S["r"]
        for d in S["wheels"]:
            fl = B.at(d)[0]
            n = 14
            for k in range(n):
                t0, t1 = math.pi * k / n, math.pi * (k + 1) / n
                p = lambda t, r: (d - math.cos(t) * r, R + 0.025 + math.sin(t) * r)  # noqa: E731
                q = [p(t0, R + 0.05), p(t1, R + 0.05), p(t1, R + 0.13), p(t0, R + 0.13)]
                q = [(u, max(v, fl + 0.02)) for u, v in q]
                c.side("rubber", q, 0.004, n=(1, 1))
        a, b = S["wheels"][0] + R + 0.09, S["wheels"][1] - R - 0.09
        fl = B.at((a + b) / 2)[0]
        c.side("rubber", [(a, fl + 0.04), (b, fl + 0.04), (b, fl + 0.15), (a, fl + 0.15)], 0.004, n=(6, 1))
    if name == "taxi":
        h = c.hit((0, -c.L / 2 + 3.0, 4), -Z)
        if h:
            c.box("rubber", h[0], Z, Y, (0.2, 0.62, 0.03))
            c.box("taxisign", h[0] + Z * 0.03, Z, X, (0.78, 0.22, 0.2))
    if name == "pickup":
        # The tailgate's seam and handle, the bed's floor ribs.
        L = c.L
        c.rear("seam", [(-0.92, 1.18), (0.92, 1.18), (0.92, 1.19), (-0.92, 1.19)], 0.002, n=(4, 1), mirror=False)
        c.rear("chrome", [(-0.12, 1.06), (0.12, 1.06), (0.12, 1.1), (-0.12, 1.1)], 0.004, n=(1, 1), mirror=False)
        for k in range(6):
            x = -0.75 + k * 0.3
            c.poly("rubber", [(x - 0.03, -L / 2 + 3.32, 0.725), (x + 0.03, -L / 2 + 3.32, 0.725), (x + 0.03, L / 2 - 0.12, 0.725), (x - 0.03, L / 2 - 0.12, 0.725)], Z, False)
    if name == "van":
        # Rear doors' windows, the centre seam, the sliding door's rail.
        c.rear("rubber", [(0.06, 1.42), (0.86, 1.42), (0.86, 1.86), (0.06, 1.86)], 0.003)
        c.rear("carglass", [(0.1, 1.46), (0.82, 1.46), (0.82, 1.82), (0.1, 1.82)], 0.006)
        c.rear("seam", [(-0.004, 0.42), (0.004, 0.42), (0.004, 1.96), (-0.004, 1.96)], 0.003, n=(1, 4), mirror=False)
        c.side("rubber", [(2.42, 1.86), (3.9, 1.86), (3.9, 1.89), (2.42, 1.89)], 0.003, n=(6, 1), sides=(-1,))


# ---- bus and truck ---------------------------------------------------------------------------

BUS = dict(
    L=12.0, W=2.55, r=0.5, tw=0.3, wheels=(2.7, 8.65), inset=0.06,
    stations=[
        (0.0, 0.34, 1.02, 1.06, 3.02, 0.97, 0.95), (0.08, 0.3, 1.02, 1.06, 3.08, 0.995, 0.97, 0.5),
        (11.92, 0.3, 1.02, 1.06, 3.08, 0.995, 0.97, 0.5), (12.0, 0.34, 1.02, 1.06, 3.02, 0.97, 0.95),
    ],
    ring_crease=(0.6, 0.7, 0.0, 0.9, 0.9, 0.85),
)


def bus(M, at):
    M.piece("bus", at)
    c = Car(M.m, at, BUS)
    c.skin(c.arches(0.08), levels=2)
    L, W = c.L, c.W
    w = W / 2
    # Windscreen down to the bumper, destination display above it.
    c.front("rubber", [(-w * 0.94, 1.0), (w * 0.94, 1.0), (w * 0.94, 2.98), (-w * 0.94, 2.98)], 0.003, n=(6, 4), mirror=False)
    c.front("carglass", [(-w * 0.9, 1.06), (w * 0.9, 1.06), (w * 0.9, 2.6), (-w * 0.9, 2.6)], 0.006, n=(6, 4), mirror=False)
    c.front("led", [(-w * 0.75, 2.66), (w * 0.75, 2.66), (w * 0.75, 2.92), (-w * 0.75, 2.92)], 0.006, n=(4, 1), mirror=False)
    c.front("headlight", [(w * 0.62, 0.62), (w * 0.92, 0.62), (w * 0.92, 0.74), (w * 0.62, 0.74)], 0.006, n=(2, 1))
    c.front("rubber", [(-w * 0.96, 0.3), (w * 0.96, 0.3), (w * 0.96, 0.52), (-w * 0.96, 0.52)], 0.004, n=(6, 1), mirror=False)
    c.front("plate", [(-0.26, 0.38), (0.26, 0.38), (0.26, 0.49), (-0.26, 0.49)], 0.007, n=(1, 1), mirror=False)
    c.rear("rubber", [(-w * 0.7, 1.95), (w * 0.7, 1.95), (w * 0.7, 2.75), (-w * 0.7, 2.75)], 0.003, n=(4, 2), mirror=False)
    c.rear("carglass", [(-w * 0.66, 1.99), (w * 0.66, 1.99), (w * 0.66, 2.71), (-w * 0.66, 2.71)], 0.006, n=(4, 2), mirror=False)
    c.rear("taillight", [(w * 0.75, 0.7), (w * 0.95, 0.7), (w * 0.95, 1.2), (w * 0.75, 1.2)], 0.006, n=(1, 2))
    c.rear("rubber", [(-w * 0.96, 0.3), (w * 0.96, 0.3), (w * 0.96, 0.55), (-w * 0.96, 0.55)], 0.004, n=(6, 1), mirror=False)
    c.rear("plate", [(-0.26, 0.6), (0.26, 0.6), (0.26, 0.71), (-0.26, 0.71)], 0.007, n=(1, 1), mirror=False)
    # A band of black glazing with framed panes; doors on the kerb side (-x).
    c.side("rubber", [(0.5, 1.1), (11.6, 1.1), (11.6, 2.72), (0.5, 2.72)], 0.003, n=(16, 2))
    doors = [(0.55, 1.75), (5.25, 6.45)]
    x = 1.82
    while x < 11.4:
        x1 = min(11.5, x + 1.32)
        for sx in (-1, 1):
            if sx < 0 and any(a - 0.05 < x < b + 0.05 or a < x1 < b for a, b in doors):
                continue
            c.side("carglass", [(x + 0.06, 1.18), (x1 - 0.06, 1.18), (x1 - 0.06, 2.64), (x + 0.06, 2.64)], 0.006, n=(2, 2), sides=(sx,))
        x = x1
    for a, b in doors:
        c.side("rubber", [(a, 0.36), (b, 0.36), (b, 2.72), (a, 2.72)], 0.004, n=(2, 3), sides=(-1,))
        for p, q in ((a + 0.04, (a + b) / 2 - 0.02), ((a + b) / 2 + 0.02, b - 0.04)):
            c.side("carglass", [(p, 0.42), (q, 0.42), (q, 2.62), (p, 2.62)], 0.007, n=(1, 3), sides=(-1,))
    # Roof pods: air conditioning and the battery packs.
    for d0, d1, h in ((3.0, 5.6, 0.3), (7.4, 10.4, 0.24)):
        c.box("carpaint", Vector((0, -L / 2 + (d0 + d1) / 2, 3.07)), Z, Y, (d1 - d0, 1.8, h))
    c.wheels()


TRUCK = dict(
    L=2.35, W=2.36, r=0.48, tw=0.28, wheels=(1.08,), inset=0.05,
    stations=[
        (0.0, 0.5, 1.2, 1.25, 1.32, 0.94, 0.88), (0.1, 0.44, 1.3, 1.36, 1.44, 0.99, 0.9),
        (0.42, 0.42, 1.36, 1.42, 1.7, 1.0, 0.92, 0.6), (0.85, 0.42, 1.4, 1.46, 2.62, 1.0, 0.93),
        (1.1, 0.42, 1.42, 1.48, 2.74, 1.0, 0.94, 0.3), (2.35, 0.42, 1.42, 1.48, 2.74, 1.0, 0.94),
    ],
    ring_crease=(0.4, 0.6, 0.0, 0.8, 0.6, 0.7),
)


def truck(M, at):
    """A box truck: a chassis cab and a 5.2 m box behind, dual rear wheels."""
    M.piece("truck", at)
    L = 7.6
    cab_off = Vector(at) + Vector((0, -L / 2 + TRUCK["L"] / 2, 0))
    c = Car(M.m, cab_off, TRUCK)
    c.skin(c.arches(0.07))
    w = c.W / 2
    a, b = 0.44, 0.84
    c.slope("rubber", (a, 1.48), (b, 2.6), [(-w * 0.9, -0.02), (w * 0.9, -0.02), (w * 0.86, 1.2), (-w * 0.86, 1.2)], 0.003)
    c.slope("carglass", (a, 1.48), (b, 2.6), [(-w * 0.84, 0.04), (w * 0.84, 0.04), (w * 0.8, 1.13), (-w * 0.8, 1.13)], 0.006)
    c.side("rubber", [(0.92, 1.5), (1.85, 1.5), (1.85, 2.5), (0.98, 2.5)], 0.003, n=(3, 2))
    c.side("carglass", [(0.96, 1.54), (1.8, 1.54), (1.8, 2.45), (1.02, 2.45)], 0.006, n=(3, 2))
    c.side("seam", [(1.9, 0.5), (1.906, 0.5), (1.906, 2.5), (1.9, 2.5)], 0.002, n=(1, 3))
    c.front("rubber", [(w * 0.5, 0.78), (w * 0.92, 0.8), (w * 0.92, 0.95), (w * 0.5, 0.93)], 0.004)
    c.front("headlight", [(w * 0.56, 0.81), (w * 0.88, 0.83), (w * 0.88, 0.92), (w * 0.56, 0.9)], 0.007, n=(2, 1))
    c.front("chrome", [(-w * 0.44, 0.62), (w * 0.44, 0.62), (w * 0.44, 1.2), (-w * 0.44, 1.2)], 0.003, n=(4, 2), mirror=False)
    c.front("dark", [(-w * 0.4, 0.66), (w * 0.4, 0.66), (w * 0.4, 1.16), (-w * 0.4, 1.16)], 0.005, n=(4, 2), mirror=False)
    for k in range(1, 5):
        z = 0.66 + k * 0.1
        c.front("chrome", [(-w * 0.39, z - 0.008), (w * 0.39, z - 0.008), (w * 0.39, z + 0.008), (-w * 0.39, z + 0.008)], 0.007, n=(3, 1), mirror=False)
    c.front("rubber", [(-w * 0.97, 0.44), (w * 0.97, 0.44), (w * 0.97, 0.6), (-w * 0.97, 0.6)], 0.004, n=(6, 1), mirror=False)
    c.front("plate", [(-0.26, 0.46), (0.26, 0.46), (0.26, 0.57), (-0.26, 0.57)], 0.007, n=(1, 1), mirror=False)
    for sx in (-1, 1):
        h = c.hit((sx * 3, -c.L / 2 + 0.75, 2.0), X * -sx)
        if h:
            c.box("rubber", h[0] + Vector((sx * 0.12, 0, 0)), Vector((sx, 0, 0)), Z, (0.5, 0.06, 0.06))
            c.box("rubber", h[0] + Vector((sx * 0.26, 0.04, -0.15)), Y, Z, (0.42, 0.2, 0.06))
    c.wheels()
    # The box and chassis, in the truck's own frame.
    t = Car(M.m, at, dict(L=L, W=2.44, r=0.48, tw=0.28, wheels=(L - 1.75,), inset=0.05))
    y0 = -L / 2 + 2.42
    t.box("dark", Vector((0, (y0 + L / 2) / 2 - 0.05, 0.55)), Z, Y, (L / 2 - y0, 1.0, 0.3))
    t.box("chrome", Vector((0.82, y0 + 0.5, 0.55)), Z, Y, (1.0, 0.36, 0.4))
    bw, bz0, bz1 = 1.22, 0.98, 3.58
    t.box("cargo", Vector((0, (y0 + L / 2) / 2, bz0)), Z, Y, (L / 2 - y0, 2 * bw, bz1 - bz0))
    t.box("rubber", Vector((0, (y0 + L / 2) / 2, bz0 - 0.06)), Z, Y, (L / 2 - y0 + 0.02, 2 * bw + 0.04, 0.08))
    for sx in (-1, 1):
        for k in range(1, 9):
            yy = y0 + k * (L / 2 - y0) / 9
            t.box("cargo", Vector((sx * bw, yy, (bz0 + bz1) / 2)), Vector((sx, 0, 0)), Z, (bz1 - bz0 - 0.04, 0.05, 0.02))
    t.poly("seam", [(-0.004, L / 2 + 0.002, 1.02), (0.004, L / 2 + 0.002, 1.02), (0.004, L / 2 + 0.002, 3.5), (-0.004, L / 2 + 0.002, 3.5)], Y, False)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * 1.15, sx * 0.88))
        t.poly("taillight", [(x0, L / 2 + 0.003, 0.72), (x1, L / 2 + 0.003, 0.72), (x1, L / 2 + 0.003, 0.88), (x0, L / 2 + 0.003, 0.88)], Y, False)
    t.box("rubber", Vector((0, L / 2 - 0.05, 0.55)), Z, Y, (0.1, 2.4, 0.16))
    t.poly("plate", [(-0.26, L / 2 + 0.003, 0.65), (0.26, L / 2 + 0.003, 0.65), (0.26, L / 2 + 0.003, 0.76), (-0.26, L / 2 + 0.003, 0.76)], Y, False)
    # Mudguards over the dual rear wheels; the wheels.
    for sx in (-1, 1):
        t.box("rubber", Vector((sx * 0.95, L / 2 - 1.75, 1.0)), Z, Y, (1.3, 0.62, 0.03))
    t.wheels(dual=True)


ORDER = ["hatch", "sedan", "estate", "suv", "coupe", "taxi", "pickup", "van"]


def build(out, bake=True):
    M = Model(ID)
    M.sharp = math.radians(40)
    x = -20.0
    for name in ORDER:
        car(M, name, (x, 0, 0))
        x += 4.0
    bus(M, (x + 1.0, 0, 0))
    truck(M, (x + 6.0, 0, 0))
    M.export(out, bake, size=2048, samples=96, smooth=2.0)
