// City theme: people on the pavements. Each block is ringed by pavement
// with two walking lines: the inside one walked with the block on the
// right, the kerb-side one the other way, each bent round the furniture
// in its way (the inside one behind a bench or shelter, the kerb-side one
// in front), so the two never meet. People keep their distance in single
// file, wait short of a car turning into a lot, and cross at the zebras
// when every light is red (walkLeft() in roads.ts): over to the kerb when
// the line they cut across is clear, and back into a line when there is a
// gap. Pure: traffic.ts draws them.
import { BLOCK_X, BLOCK_Z, PAVEMENT, PITCH_X, PITCH_Z } from "./plan";
import { walkLeft, ZEBRA } from "./roads";
import { KERB_SET, LAMP_T, streetProps, TREE_T, type Box } from "./street";

/** Radius the walking lines take round a corner; distance round the ring (u) is measured on it. */
const M = 1;
/** Half a person's width, with a little room. */
export const BODY = 0.27;
/** The walking lines, out from the block's edge: inside (walked with the block on the right) and kerb side. */
const LINES = [0.4, 0.98];
/** How far a line may bend toward the block or the road to get round something. */
const MIN_L = -0.15;
const MAX_L = 2;
/** Where people wait to cross, two abreast either side of the zebra's middle. */
const KERB_L = 1.75;
const ABREAST = [0.35, 0.95];
/** Metres per stride cycle (two steps); centre to centre in a queue. */
const STRIDE = 1.45;
const SPACING = 0.8;
/** The lines are sampled this often along a side and bend no steeper than this. */
const SAMPLE = 0.2;
const SLOPE = 0.5;
/** How far a zebra runs from kerb to kerb. */
const ACROSS = PITCH_Z - BLOCK_Z - 2 * PAVEMENT;
/** Walking pace over the road. */
const CROSSING = 1.7;

type V2 = [number, number];

interface Obstacle {
  a0: number;
  a1: number;
  l0: number;
  l1: number;
}

interface Zebra {
  /** Along this side; the block and side it leads to. */
  a: number;
  to: number;
  side: number;
  /** Who waits where. */
  slots: (Walker | null)[];
}

interface Side {
  len: number;
  /** Where it starts (u), its start corner, direction and the outward normal. */
  u: number;
  c: V2;
  d: V2;
  n: V2;
  obstacles: Obstacle[];
  zebras: Zebra[];
  /** Each line's distance out from the block, every SAMPLE metres along. */
  lines: Float32Array[];
}

interface Ring {
  x: number;
  z: number;
  sides: Side[];
  length: number;
}

export type WalkMode = "walk" | "kerb" | "wait" | "cross" | "landed" | "join" | "back";

export interface Walker {
  id: number;
  ring: number;
  /** 0 the inside line (walking u up), 1 the kerb-side line (u down). */
  line: number;
  u: number;
  /** Out from the block's edge. */
  l: number;
  speed: number;
  v: number;
  /** Stride phase (radians) and how far the limbs swing (0 standing, 1 walking). */
  phase: number;
  amp: number;
  /**
   * walk: on its line; kerb: over to a zebra's waiting place; wait: there;
   * cross: over the road; landed: on the far kerb, waiting for a gap; join:
   * into a line; back: to the kerb again, when the way into the line stayed blocked.
   */
  mode: WalkMode;
  zebra: Zebra | null;
  slot: number;
  /** Over the road: from, to (world) and progress 0 to 1. To the kerb or into a line: to as [u, l], and from where it stepped off. */
  from: V2;
  to: V2;
  k: number;
  /** The side of the far block it lands on. */
  land: number;
  /** Which way it faces, for drawing: +1 up the ring, -1 down. */
  facing: number;
  /** Seconds held up on the road. */
  held: number;
}

/** A car as people see it; `drive` is the pavement it crosses turning into a lot or out (x0, x1, z0, z1). */
export interface CarShape {
  x: number;
  z: number;
  heading: number;
  len: number;
  wid: number;
  v: number;
  drive: [number, number, number, number] | null;
  /** In a crossing, or cleared into one: it may yet roll over a zebra by it. */
  committed: boolean;
}

export interface Pose {
  x: number;
  y: number;
  z: number;
  heading: number;
  phase: number;
  amp: number;
}

/** Sides of a block in walking order (block on the right), as for the lanes (roads.ts). */
function sidesOf(b: { x: number; z: number }): Omit<Side, "obstacles" | "zebras" | "lines">[] {
  const hx = BLOCK_X / 2;
  const hz = BLOCK_Z / 2;
  const raw: [V2, V2, V2, number][] = [
    [[b.x - hx, b.z - hz], [1, 0], [0, -1], BLOCK_X],
    [[b.x + hx, b.z - hz], [0, 1], [1, 0], BLOCK_Z],
    [[b.x + hx, b.z + hz], [-1, 0], [0, 1], BLOCK_X],
    [[b.x - hx, b.z + hz], [0, -1], [-1, 0], BLOCK_Z],
  ];
  let u = 0;
  return raw.map(([c, d, n, len]) => {
    const s = { len, u, c, d, n };
    u += len + (Math.PI / 2) * M;
    return s;
  });
}

/** A side's coordinates of a world point: along it, and out from the block. */
const local = (s: { c: V2; d: V2; n: V2 }, x: number, z: number): V2 => [(x - s.c[0]) * s.d[0] + (z - s.c[1]) * s.d[1], (x - s.c[0]) * s.n[0] + (z - s.c[1]) * s.n[1]];

const inBox = (o: Obstacle, a: number, l: number, pad = BODY) => a > o.a0 - pad && a < o.a1 + pad && l > o.l0 - pad && l < o.l1 + pad;

/**
 * A walking line along a side: at its base distance out, bending toward
 * the block (inside line) or the road (kerb side) wherever something stands
 * in the way, no steeper than SLOPE.
 */
function line(len: number, obstacles: Obstacle[], base: number, toward: -1 | 1): Float32Array {
  const n = Math.ceil(len / SAMPLE) + 1;
  const want = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const a = i * SAMPLE;
    let l = base;
    // Step past each thing in the way, toward the line's own side.
    for (let pass = 0; pass < 4; pass++) {
      const hit = obstacles.find((o) => inBox(o, a, l, BODY + 0.03));
      if (!hit) break;
      // Round its own side if there is room there, else the other.
      const [below, above] = [hit.l0 - BODY - 0.04, hit.l1 + BODY + 0.04];
      const fits = (x: number) => x >= MIN_L && x <= MAX_L;
      l = toward < 0 ? (fits(below) ? below : above) : fits(above) ? above : below;
    }
    want[i] = l;
  }
  // Bend in ahead of time: the line never comes back toward its base faster than SLOPE.
  const out = new Float32Array(n);
  const reach = Math.ceil(2 / (SLOPE * SAMPLE));
  for (let i = 0; i < n; i++) {
    let l = base;
    for (let j = Math.max(0, i - reach); j < Math.min(n, i + reach + 1); j++) {
      const ramp = want[j] - toward * SLOPE * SAMPLE * Math.abs(i - j);
      l = toward < 0 ? Math.min(l, ramp) : Math.max(l, ramp);
    }
    out[i] = l;
  }
  return out;
}

const lineAt = (xs: Float32Array, a: number) => {
  const t = Math.min(Math.max(a / SAMPLE, 0), xs.length - 1);
  const i = Math.min(Math.floor(t), xs.length - 2);
  return xs[i] + (xs[i + 1] - xs[i]) * (t - i);
};

export class Crowd {
  walkers: Walker[] = [];
  private rings: Ring[] = [];
  /** This step's people by ring (crossers under the ring they land on), and everyone crossing. */
  private by: Walker[][] = [];
  private crossers: Walker[] = [];

  /**
   * `blocks` with their road classes ([north, south, west, east], 0 lane to
   * 3 avenue); `signs`: blocks with a street sign at their north-east corner.
   * People cross only where signals stand (a town on) and a zebra is painted.
   */
  constructor(
    blocks: { x: number; z: number; roads: number[] }[],
    tier: number,
    perBlock: number,
    private r: () => number,
    signs: Set<string> = new Set(),
  ) {
    const index = new Map(blocks.map((b, i) => [`${Math.round(b.x)},${Math.round(b.z)}`, i]));
    const pw = PAVEMENT;
    // Road class by side (north, east, south, west) and the neighbour across it.
    const classOf = (b: { roads: number[] }, k: number) => [b.roads[0], b.roads[3], b.roads[1], b.roads[2]][k];
    const across: V2[] = [
      [0, -PITCH_Z],
      [PITCH_X, 0],
      [0, PITCH_Z],
      [-PITCH_X, 0],
    ];
    this.rings = blocks.map((b) => {
      const boxes: Box[] = streetProps(b, tier).flatMap((p) => p.boxes);
      const pole = (x: number, z: number, h: number) => boxes.push({ x0: x - h, x1: x + h, z0: z - h, z1: z + h });
      const ex = BLOCK_X / 2 + pw - KERB_SET;
      const ez = BLOCK_Z / 2 + pw - KERB_SET;
      for (const lz of [-1, 1]) {
        const cls = lz < 0 ? b.roads[0] : b.roads[1];
        if (cls > 0) for (const t of LAMP_T) pole(b.x + t * (BLOCK_X / 2 - 1), b.z + lz * ez, 0.17);
        if (cls > 1) for (const t of TREE_T) pole(b.x + t * (BLOCK_X / 2 - 1), b.z + lz * ez, 0.25);
      }
      for (const sx of [-1, 1]) if ((sx < 0 ? b.roads[2] : b.roads[3]) > 1) pole(b.x + sx * ex, b.z, 0.25);
      if (signs.has(`${b.x},${b.z}`)) pole(b.x + BLOCK_X / 2 + pw - 0.5, b.z - BLOCK_Z / 2 + 1.5, 0.12);
      const sides: Side[] = sidesOf(b).map((s, k) => {
        const obstacles: Obstacle[] = [];
        for (const o of boxes) {
          const ps = [local(s, o.x0, o.z0), local(s, o.x1, o.z1)];
          const [a0, a1] = [Math.min(ps[0][0], ps[1][0]), Math.max(ps[0][0], ps[1][0])];
          const [l0, l1] = [Math.min(ps[0][1], ps[1][1]), Math.max(ps[0][1], ps[1][1])];
          if (a1 > -1 && a0 < s.len + 1 && l1 > MIN_L - BODY && l0 < MAX_L + BODY) obstacles.push({ a0, a1, l0, l1 });
        }
        const zebras: Zebra[] = [];
        const nb = index.get(`${Math.round(b.x + across[k][0])},${Math.round(b.z + across[k][1])}`);
        if (tier >= 1 && nb !== undefined && classOf(b, k) > 0) for (const a of [ZEBRA, s.len - ZEBRA]) zebras.push({ a, to: nb, side: (k + 2) % 4, slots: [] });
        return { ...s, obstacles, zebras, lines: [line(s.len, obstacles, LINES[0], -1), line(s.len, obstacles, LINES[1], 1)] };
      });
      const length = sides.reduce((t, s) => t + s.len + (Math.PI / 2) * M, 0);
      return { x: b.x, z: b.z, sides, length };
    });
    this.rings.forEach((ring, i) => {
      // Spread out along each line.
      const n = Math.ceil(perBlock / 2);
      for (let j = 0; j < perBlock; j++) {
        const lane = j % 2;
        const u = (ring.length * (Math.floor(j / 2) + 0.2 + 0.6 * r())) / n;
        const w: Walker = { id: this.walkers.length, ring: i, line: lane, u, l: 0, speed: 1.15 + r() * 0.4, v: 0, phase: r() * 6.28, amp: 0, mode: "walk", zebra: null, slot: -1, from: [0, 0], to: [0, 0], k: 0, land: 0, facing: lane ? -1 : 1, held: 0 };
        w.l = this.lineOf(ring, lane, u);
        this.walkers.push(w);
      }
    });
  }

  /** The side and how far along it, or null on a corner. */
  private sideAt(ring: Ring, u: number): { side: Side; k: number; a: number } | null {
    const t = this.wrap(ring, u);
    for (let k = 0; k < 4; k++) {
      const s = ring.sides[k];
      if (t >= s.u && t < s.u + s.len) return { side: s, k, a: t - s.u };
    }
    return null;
  }

  private wrap(ring: Ring, u: number) {
    return ((u % ring.length) + ring.length) % ring.length;
  }

  /** Signed distance round the ring from `a` to `b`, the short way. */
  private gap(ring: Ring, a: number, b: number) {
    return this.wrap(ring, b - a + ring.length / 2) - ring.length / 2;
  }

  /** How far out a line runs at `u` (on a corner, its base). */
  private lineOf(ring: Ring, lane: number, u: number): number {
    const s = this.sideAt(ring, u);
    return s ? lineAt(s.side.lines[lane], s.a) : LINES[lane];
  }

  /** World position and direction of travel (u increasing) at `u`, `l` out from the block. */
  private place(ring: Ring, u: number, l: number): { x: number; z: number; heading: number } {
    const t = this.wrap(ring, u);
    for (let k = 0; k < 4; k++) {
      const s = ring.sides[k];
      if (t < s.u + s.len) {
        const a = t - s.u;
        return { x: s.c[0] + s.d[0] * a + s.n[0] * l, z: s.c[1] + s.d[1] * a + s.n[1] * l, heading: Math.atan2(s.d[0], s.d[1]) };
      }
      const arc = (Math.PI / 2) * M;
      if (t < s.u + s.len + arc) {
        const th = (t - s.u - s.len) / M;
        const [cx, cz] = [s.c[0] + s.d[0] * s.len, s.c[1] + s.d[1] * s.len];
        const nx = s.n[0] * Math.cos(th) + s.d[0] * Math.sin(th);
        const nz = s.n[1] * Math.cos(th) + s.d[1] * Math.sin(th);
        const tx = -s.n[0] * Math.sin(th) + s.d[0] * Math.cos(th);
        const tz = -s.n[1] * Math.sin(th) + s.d[1] * Math.cos(th);
        return { x: cx + nx * l, z: cz + nz * l, heading: Math.atan2(tx, tz) };
      }
    }
    return { x: ring.x, z: ring.z, heading: 0 };
  }

  /** Where a zebra's waiting place `j` is: along its side, and out from the block. */
  private slotAt(z: Zebra, s: Side, j: number): V2 {
    // Keep right on the crossing: people bound across stand right of the zebra's middle.
    const right = -s.n[1] * s.d[0] + s.n[0] * s.d[1] > 0 ? 1 : -1;
    return [z.a + right * ABREAST[j], KERB_L];
  }

  /** A free place to wait, with a clear way to the kerb here and up from it on the far side. */
  private freeSlot(z: Zebra, s: Side): number {
    const dest = this.rings[z.to].sides[z.side];
    for (let j = 0; j < ABREAST.length; j++) {
      if (z.slots[j]) continue;
      const [a, l] = this.slotAt(z, s, j);
      const [fa] = local(dest, s.c[0] + s.d[0] * a, s.c[1] + s.d[1] * a);
      const clear = (side: Side, a: number) => !side.obstacles.some((o) => [l, MAX_L].some((l) => inBox(o, a, l)));
      if (clear(s, a) && clear(dest, fa)) return j;
    }
    return -1;
  }

  /** Whether a car is on the zebra or bearing down on it. */
  private carOn(x: number, z: number, alongX: boolean, cars: CarShape[]): boolean {
    for (const c of cars) {
      const [sx, cx] = [Math.abs(Math.sin(c.heading)), Math.abs(Math.cos(c.heading))];
      const ext = [(sx * c.len) / 2 + (cx * c.wid) / 2, (cx * c.len) / 2 + (sx * c.wid) / 2];
      // The stripes run across the road, 2.6 m wide along it.
      const [along, acrossD] = alongX ? [Math.abs(c.x - x), Math.abs(c.z - z)] : [Math.abs(c.z - z), Math.abs(c.x - x)];
      const [extAlong, extAcross] = alongX ? ext : [ext[1], ext[0]];
      if (along < extAlong + 1.7 && acrossD < extAcross + ACROSS / 2 + 1) return true;
      if ((c.v > 1 || c.committed || c.drive) && Math.hypot(c.x - x, c.z - z) < 14) return true;
    }
    return false;
  }

  /** Whether `o` (on its line, or stepping across or standing in `lane`) is in that line's way. */
  private onLine(o: Walker, ring: Ring, lane: number): boolean {
    if (o.mode === "walk") return o.line === lane;
    if (o.mode === "cross") return false;
    // Stepping across it, or standing in it.
    return Math.abs(o.l - this.lineOf(ring, lane, o.u)) < 2 * BODY + 0.1;
  }

  /** Whether a line is clear within `room` of `u`; `moving`: of people moving along it (whoever stands there waits, then follows). */
  private lineClear(ringIndex: number, lane: number, u: number, room: number, except?: Walker, moving = false): boolean {
    const ring = this.rings[ringIndex];
    return !this.by[ringIndex].some((o) => o !== except && (!moving || o.v > 0) && this.onLine(o, ring, lane) && Math.abs(this.gap(ring, o.u, u)) < room);
  }

  step(dt: number, t: number, cars: CarShape[] = []) {
    const drives = cars.flatMap((c) => (c.drive ? [c.drive] : []));
    this.by = this.rings.map(() => []);
    for (const w of this.walkers) this.by[w.ring].push(w);
    this.crossers = this.walkers.filter((w) => w.mode === "cross");
    for (const w of this.walkers) {
      const ring = this.rings[w.ring];
      if (w.mode === "walk") this.walk(w, ring, dt, drives);
      else if (w.mode === "kerb" || w.mode === "join" || w.mode === "back") this.edge(w, ring, dt);
      else if (w.mode === "wait") this.wait(w, ring, t, cars);
      else if (w.mode === "cross") this.cross(w, ring, t, dt);
      else this.landed(w, ring);
      this.stride(w, dt);
    }
  }

  /** Along its line, behind whoever is ahead on it. */
  private walk(w: Walker, ring: Ring, dt: number, drives: number[][]) {
    const dir = w.line ? -1 : 1;
    let v = w.speed;
    for (const o of this.by[w.ring]) {
      if (o === w || !this.onLine(o, ring, w.line)) continue;
      const ahead = this.gap(ring, w.u, o.u) * dir;
      if (ahead <= 0 || ahead > SPACING + 1) continue;
      v = Math.min(v, Math.max(0, (ahead - SPACING) * 2.5 + (o.mode === "walk" ? o.v : 0)));
    }
    // A car turning into a lot or out of one has the pavement: wait short of its driveway.
    const here = this.place(ring, w.u, w.l);
    const next = this.place(ring, w.u + dir * 0.6, this.lineOf(ring, w.line, w.u + dir * 0.6));
    const inDrive = (p: { x: number; z: number }, [x0, x1, z0, z1]: number[]) => p.x > x0 - BODY && p.x < x1 + BODY && p.z > z0 - BODY && p.z < z1 + BODY;
    for (const d of drives) if (inDrive(next, d) && !inDrive(here, d)) v = 0;
    w.v = v === 0 ? 0 : Math.max(0, w.v + Math.max(-4 * dt, Math.min(2 * dt, v - w.v)));
    const before = this.sideAt(ring, w.u);
    // Round a corner the line is shorter or longer than u measures.
    const scale = before ? 1 : M / Math.max(0.3, w.l);
    w.u = this.wrap(ring, w.u + dir * w.v * dt * scale);
    w.l = this.lineOf(ring, w.line, w.u);
    w.facing = dir;
    // Passing a zebra: now and then go over to wait and cross.
    const now = this.sideAt(ring, w.u);
    if (!before || !now || now.side !== before.side) return;
    for (const z of now.side.zebras) {
      if ((before.a - z.a) * (now.a - z.a) > 0 || this.r() > 0.35) continue;
      const j = this.freeSlot(z, now.side);
      if (j < 0) continue;
      const [sa, sl] = this.slotAt(z, now.side, j);
      const su = now.side.u + sa;
      // From the inside line, only with the kerb-side line clear to cut across.
      if (w.line === 0 && !this.lineClear(w.ring, 1, su, 2.5, w)) continue;
      if (!this.pathClear(ring, w.u, w.l, su, sl)) continue;
      z.slots[j] = w;
      [w.mode, w.zebra, w.slot, w.to, w.from, w.k] = ["kerb", z, j, [su, sl], [w.u, w.l], 0];
      return;
    }
  }

  /** To the kerb, or from it into a line: straight there, unless someone is in the way. */
  private edge(w: Walker, ring: Ring, dt: number) {
    const [tu, tl] = w.to;
    const du = this.gap(ring, w.u, tu);
    const dist = Math.hypot(du, tl - w.l);
    const step = Math.min(dist, w.speed * dt);
    const [nu, nl] = dist > 0.01 ? [w.u + (du / dist) * step, w.l + ((tl - w.l) / dist) * step] : [tu, tl];
    if (this.crowded(w, ring, nu, nl)) {
      w.v = 0;
      // Held up for long on the way to the kerb: give up crossing and walk on.
      w.k += dt;
      if (w.mode === "kerb" && w.k > 4) {
        w.zebra!.slots[w.slot] = null;
        const u = this.wrap(ring, w.u + (w.line ? -1 : 1) * 0.8);
        [w.mode, w.zebra, w.slot, w.k, w.to] = ["join", null, -1, 0, [u, this.lineOf(ring, w.line, u)]];
      } else if (w.mode === "join" && w.k > 3 + this.r()) {
        // Two stepping into the lines across each other's way: back to the kerb, and think again.
        [w.mode, w.k, w.to] = ["back", 0, w.from];
      } else if (w.mode === "back" && w.k > 3) [w.mode, w.k] = ["landed", 0];
    } else {
      w.k = 0;
      if (Math.abs(du) > 0.05) w.facing = du > 0 ? 1 : -1;
      [w.u, w.l, w.v] = [this.wrap(ring, nu), nl, step / dt];
    }
    if (Math.hypot(this.gap(ring, w.u, tu), tl - w.l) > 0.01) return;
    if (w.mode === "kerb") [w.mode, w.v] = ["wait", 0];
    else if (w.mode === "back") [w.mode, w.v] = ["landed", 0];
    else [w.mode, w.facing] = ["walk", w.line ? -1 : 1];
  }

  /** A straight walk from (u0, l0) to (u1, l1) clear of the furniture. */
  private pathClear(ring: Ring, u0: number, l0: number, u1: number, l1: number): boolean {
    const du = this.gap(ring, u0, u1);
    for (let i = 0; i <= 8; i++) {
      const at = this.sideAt(ring, u0 + (du * i) / 8);
      const l = l0 + ((l1 - l0) * i) / 8;
      if (at && at.side.obstacles.some((o) => inBox(o, at.a, l))) return false;
    }
    return true;
  }

  /** Someone within arm's reach of where `w` would step, and nearer than now. */
  private crowded(w: Walker, ring: Ring, u: number, l: number): boolean {
    const here = this.place(ring, w.u, w.l);
    const next = this.place(ring, u, l);
    // Including anyone stepping up off the road.
    return [...this.by[w.ring], ...this.crossers].some((o) => {
      if (o === w) return false;
      const p = o.mode === "cross" ? { x: o.from[0] + (o.to[0] - o.from[0]) * o.k, z: o.from[1] + (o.to[1] - o.from[1]) * o.k } : this.place(ring, o.u, o.l);
      const d = Math.hypot(p.x - next.x, p.z - next.z);
      return d < 2 * BODY + 0.1 && d < Math.hypot(p.x - here.x, p.z - here.z);
    });
  }

  /** At the kerb: over when every light is red, there is time to cross, and no car is on the zebra. */
  private wait(w: Walker, ring: Ring, t: number, cars: CarShape[]) {
    w.v = 0;
    const z = w.zebra!;
    const s = this.sideAt(ring, w.u)!.side;
    const p = this.place(ring, w.u, w.l);
    const dest = this.rings[z.to].sides[z.side];
    const [fa] = local(dest, p.x, p.z);
    const to = dest.c.map((c, i) => c + dest.d[i] * fa + dest.n[i] * KERB_L) as V2;
    const dist = Math.hypot(to[0] - p.x, to[1] - p.z);
    const zx = s.c[0] + s.d[0] * z.a + s.n[0] * (ACROSS / 2 + PAVEMENT);
    const zz = s.c[1] + s.d[1] * z.a + s.n[1] * (ACROSS / 2 + PAVEMENT);
    if (walkLeft(t) > dist / CROSSING + 0.5 && !this.carOn(zx, zz, s.d[1] === 0, cars)) {
      z.slots[w.slot] = null;
      [w.mode, w.from, w.to, w.k, w.ring, w.slot, w.land, w.zebra] = ["cross", [p.x, p.z], to, 0, z.to, -1, z.side, null];
    }
  }

  /** Over the road at a brisk walk, behind whoever is just ahead; onto the far kerb when there is room. */
  private cross(w: Walker, ring: Ring, t: number, dt: number) {
    const dist = Math.hypot(w.to[0] - w.from[0], w.to[1] - w.from[1]);
    const [hx, hz] = [(w.to[0] - w.from[0]) / dist, (w.to[1] - w.from[1]) / dist];
    const me = [w.from[0] + hx * w.k * dist, w.from[1] + hz * w.k * dist];
    const s = ring.sides[w.land];
    let [la, ll] = local(s, w.to[0], w.to[1]);
    const taken = (a: number) => this.by[w.ring].some((o) => o !== w && o.mode !== "cross" && Math.abs(this.gap(ring, o.u, s.u + a)) < 2 * BODY + 0.1 && Math.abs(o.l - ll) < 2 * BODY + 0.1);
    // Someone standing where it would step up (or held up long): aim for a free bit of kerb beside them.
    if ((1 - w.k) * dist < 2.5 && (taken(la) || w.held > 2)) {
      w.held = 0;
      // A straight way there from here that misses the furniture on the kerb.
      const clear = (a: number) => {
        for (let i = 0; i <= 10; i++) {
          const [pa, pl] = local(s, me[0] + (s.c[0] + s.d[0] * a + s.n[0] * ll - me[0]) * (i / 10), me[1] + (s.c[1] + s.d[1] * a + s.n[1] * ll - me[1]) * (i / 10));
          if (s.obstacles.some((o) => inBox(o, pa, pl))) return false;
        }
        return true;
      };
      const free = [0.6, -0.6, 1.2, -1.2, 1.8, -1.8, 2.4, -2.4].map((d) => la + d).find((a) => a > 0.5 && a < s.len - 0.5 && !taken(a) && clear(a));
      if (free !== undefined) {
        la = free;
        w.from = [me[0], me[1]];
        w.to = [s.c[0] + s.d[0] * la + s.n[0] * ll, s.c[1] + s.d[1] * la + s.n[1] * ll];
        w.k = 0;
        return;
      }
    }
    const lu = s.u + la;
    // Room where it steps up (waited for only while the lights still hold the traffic).
    const full = walkLeft(t) > 0 && (1 - w.k) * dist < 1.2 && taken(la);
    // Whoever is just ahead, crossing too or standing on the kerb short of where it steps up.
    const reach = Math.min(SPACING, (1 - w.k) * dist + 2 * BODY);
    const queued = [...this.by[w.ring], ...this.crossers].some((o) => {
      if (o === w) return false;
      const op = o.mode === "cross" ? null : this.place(this.rings[o.ring], o.u, o.l);
      const [ox, oz] = op ? [op.x, op.z] : [o.from[0] + (o.to[0] - o.from[0]) * o.k, o.from[1] + (o.to[1] - o.from[1]) * o.k];
      const ahead = (ox - me[0]) * hx + (oz - me[1]) * hz;
      return ahead > 0 && ahead < reach && Math.abs((ox - me[0]) * hz - (oz - me[1]) * hx) < 2 * BODY;
    });
    w.v = full || queued ? 0 : CROSSING;
    w.held = w.v ? 0 : w.held + dt;
    w.k += (w.v * dt) / dist;
    if (w.k >= 1) [w.u, w.l, w.mode, w.k] = [lu, ll, "landed", 0];
  }

  /** On the far kerb: into the kerb-side line, or across it to the inside one, when there is a gap. */
  private landed(w: Walker, ring: Ring) {
    w.v = 0;
    // Already standing in a line (held up stepping into it): walk on along it, and whoever queued behind follows.
    for (const lane of [1, 0]) {
      if (Math.abs(w.l - this.lineOf(ring, lane, w.u)) < 0.45) {
        [w.line, w.mode, w.facing] = [lane, "walk", lane ? -1 : 1];
        return;
      }
    }
    // Waiting on the kerb holds up nobody, so only a gap among people moving along counts.
    const kerbSide = this.lineClear(w.ring, 1, w.u, 2.5, w, true);
    const lanes = [1, 0].filter((lane) => kerbSide && (lane === 1 || this.lineClear(w.ring, 0, w.u, 2.5, w, true)));
    if (!lanes.length) return;
    const lane = lanes[Math.floor(this.r() * lanes.length)];
    // A diagonal step into the line that misses the furniture.
    for (const ahead of [1.2, 0.6, 0, 2, 3]) {
      const u = this.wrap(ring, w.u + (lane ? -1 : 1) * ahead);
      const l = this.lineOf(ring, lane, u);
      if (!this.pathClear(ring, w.u, w.l, u, l)) continue;
      [w.line, w.mode, w.to, w.from, w.k] = [lane, "join", [u, l], [w.u, w.l], 0];
      return;
    }
  }

  private stride(w: Walker, dt: number) {
    w.phase += ((w.v * dt) / STRIDE) * 2 * Math.PI;
    const target = Math.min(1, w.v / 1.1);
    w.amp += Math.sign(target - w.amp) * Math.min(Math.abs(target - w.amp), 3 * dt);
  }

  /** Where `w` is and how it moves; `kerb` is the pavement's height, `road` the street's. */
  pose(w: Walker, kerb: number, road: number): Pose {
    const bob = 0.022 * w.amp * Math.abs(Math.cos(w.phase));
    if (w.mode === "cross") {
      const x = w.from[0] + (w.to[0] - w.from[0]) * w.k;
      const z = w.from[1] + (w.to[1] - w.from[1]) * w.k;
      const dist = Math.hypot(w.to[0] - w.from[0], w.to[1] - w.from[1]);
      // Down off the kerb and up again.
      const on = Math.min(w.k * dist, (1 - w.k) * dist);
      const kerbAt = PAVEMENT - KERB_L;
      const y = on < kerbAt ? kerb : on < kerbAt + 0.25 ? kerb + ((road - kerb) * (on - kerbAt)) / 0.25 : road;
      return { x, y: y + bob, z, heading: Math.atan2(w.to[0] - w.from[0], w.to[1] - w.from[1]), phase: w.phase, amp: w.amp };
    }
    const ring = this.rings[w.ring];
    const p = this.place(ring, w.u, w.l);
    let heading = p.heading + (w.facing < 0 ? Math.PI : 0);
    if (w.mode === "wait" || w.mode === "landed") {
      // Facing the road while waiting to cross; along the kerb when just over.
      const s = this.sideAt(ring, w.u)?.side;
      if (s && w.mode === "wait") heading = Math.atan2(s.n[0], s.n[1]);
    }
    return { x: p.x, y: kerb + bob, z: p.z, heading, phase: w.phase, amp: w.amp };
  }

  /** Whether anyone crossing the road is within `r` of a point. */
  crossing(x: number, z: number, r: number): boolean {
    for (const w of this.walkers) {
      if (w.mode !== "cross") continue;
      const [x1, z1] = [w.from[0] + (w.to[0] - w.from[0]) * w.k, w.from[1] + (w.to[1] - w.from[1]) * w.k];
      if (Math.hypot(x1 - x, z1 - z) < r) return true;
    }
    return false;
  }

  /** Whether anyone is on the pavement within `r` of a point. */
  near(x: number, z: number, r: number): boolean {
    for (const w of this.walkers) {
      if (w.mode === "cross") continue;
      const p = this.place(this.rings[w.ring], w.u, w.l);
      if (Math.hypot(p.x - x, p.z - z) < r) return true;
    }
    return false;
  }
}
