// The streets as a lane graph, and the traffic that drives it. Each block
// is ringed by four lanes, one per side, travelled with the block on the
// right; a neighbour's lane on the same road runs the other way. The road
// out of town (terrain.ts) carries Main Street's traffic in from the hills
// and back out. Cars make trips: from beyond the map or out of a lot, along
// the shortest way to a lot (where they pull in and park a while), a bus
// stop, or out of town. At every crossing they wait at red, give way inside
// the crossing, keep a gap to the car ahead and slow for corners. Pure:
// traffic.ts draws it.
import { BLOCK_X, BLOCK_Z, PAVEMENT, PITCH_X, PITCH_Z, ROAD, onStreets } from "./plan";

/** The lane next to the block: a quarter of the way across the carriageway. */
export const LANE = PAVEMENT + (ROAD - 2 * PAVEMENT) / 4;
/** Acceleration and braking, m/s². */
const ACCEL = 2.5;
const BRAKE = 4;
/** Braking hard, for an amber light. */
const HARD = 6;
/** Easing off for a corner or a slower road ahead, m/s². */
const EASE = 2;
/** Bumper to bumper when queued, m. */
const GAP = 2;
/** From the stop line to the end of the lane, past the zebra crossing. */
export const STOP_LINE = 4;
/** The zebra's middle, this far into the street from the crossing (scene.ts paints it). */
export const ZEBRA = 2.2;
/** Speed limits, m/s: town streets, the open road, and round corners. */
export const LIMIT = { street: 11, highway: 22, straight: 11, right: 4.5, left: 6 };
/** When roaming with no trip: straight on twice as often as each turn. */
const TURN_WEIGHT = { straight: 2, right: 1, left: 1 };
/** Route costs, m: a left turn waits for oncoming traffic, a right one is slow. */
const TURN_COST = { straight: 0, right: 6, left: 20 };
/** Longer than this (a bus, a lorry) takes no tight right turns and parks in no lot. */
const LONG = 6;
/** Seconds to pull into a lot or out of it; a bus's stop at a shelter. */
export const PULL = 3;
const DWELL = 8;

export type Light = "green" | "amber" | "red";

/**
 * The signal cycle, shared with the lenses (real.ts): road "a" (along z)
 * gets green, amber, then red; every road is red for the walk phase; then
 * road "b" (along x) has its turn, and another walk phase.
 */
const GREEN = 13;
const AMBER = 3;
const HALF = 23;
const mod = (t: number, n: number) => ((t % n) + n) % n;

export function signal(t: number, phase: string): Light {
  const k = mod(phase === "a" ? t : t + HALF, 2 * HALF);
  return k < GREEN ? "green" : k < GREEN + AMBER ? "amber" : "red";
}

/** Seconds of the walk phase left (all roads red), 0 outside it. */
export function walkLeft(t: number): number {
  const k = mod(t, HALF);
  return k >= GREEN + AMBER ? HALF - k : 0;
}

/** A path sampled by distance; heading turns +z to the direction of travel. */
export class Path {
  readonly length: number;
  private cum: number[] = [0];

  constructor(private pts: [number, number][]) {
    for (let i = 1; i < pts.length; i++) this.cum.push(this.cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    this.length = this.cum[this.cum.length - 1];
  }

  at(s: number): { x: number; z: number; heading: number } {
    const t = Math.min(Math.max(s, 0), this.length);
    let i = 1;
    while (i < this.cum.length - 1 && this.cum[i] < t) i++;
    const [a, b] = [this.pts[i - 1], this.pts[i]];
    const seg = this.cum[i] - this.cum[i - 1] || 1;
    const k = (t - this.cum[i - 1]) / seg;
    return { x: a[0] + (b[0] - a[0]) * k, z: a[1] + (b[1] - a[1]) * k, heading: Math.atan2(b[0] - a[0], b[1] - a[1]) };
  }
}

export interface Lane {
  id: number;
  /** Direction of travel, a unit vector along x or z. */
  dx: number;
  dz: number;
  /** Signal phase: "a" for roads along z, "b" along x. */
  phase: "a" | "b";
  /** The crossing it ends at, and whether signals stand there. */
  to: string;
  lit: boolean;
  path: Path;
  turns: Turn[];
  limit: number;
  /** On the open road: cars come in from beyond the map, or leave by it. */
  entry?: boolean;
  exit?: boolean;
}

export interface Turn {
  id: string;
  from: Lane;
  to: Lane;
  kind: "straight" | "right" | "left";
  corner: string;
  path: Path;
  limit: number;
}

/** Sides of a block in driving order: direction and the outward normal. */
const SIDES = [
  { d: [1, 0], n: [0, -1] },
  { d: [0, 1], n: [1, 0] },
  { d: [-1, 0], n: [0, 1] },
  { d: [0, -1], n: [-1, 0] },
] as const;

const key = (x: number, z: number) => `${Math.round(x)},${Math.round(z)}`;

/** The road out of town: its centre line, and how far past the town it is driven. */
export interface Highway {
  z: number;
  reach: number;
}

/**
 * Every lane round the blocks, and the turns between them that stay on the
 * asphalt. With `road`, the open road joins the street it runs along: it
 * fills that street's lanes where no block has one, and runs `reach` metres
 * on past the town each way.
 */
export function lanes(blocks: { x: number; z: number }[], road?: Highway): Lane[] {
  const all: Lane[] = [];
  const starts = new Map<string, Lane[]>();
  const corners = new Set<string>();
  for (const b of blocks) for (const sx of [-1, 1]) for (const sz of [-1, 1]) corners.add(key(b.x + (sx * PITCH_X) / 2, b.z + (sz * PITCH_Z) / 2));
  const add = (a: [number, number], e: [number, number], from: string, to: string, extra: Partial<Lane> = {}) => {
    const dx = Math.sign(e[0] - a[0]);
    const dz = Math.sign(e[1] - a[1]);
    const lane: Lane = { id: all.length, dx, dz, phase: dz ? "a" : "b", to, lit: corners.has(to), path: new Path([a, e]), turns: [], limit: LIMIT.street, ...extra };
    all.push(lane);
    starts.set(from, [...(starts.get(from) ?? []), lane]);
    return lane;
  };
  const along = new Set<string>();
  for (const b of blocks) {
    for (const { d, n } of SIDES) {
      const out = n[0] ? BLOCK_X / 2 : BLOCK_Z / 2;
      const half = d[0] ? BLOCK_X / 2 : BLOCK_Z / 2;
      const pitchOut = n[0] ? PITCH_X / 2 : PITCH_Z / 2;
      const pitchAlong = d[0] ? PITCH_X / 2 : PITCH_Z / 2;
      const lx = b.x + n[0] * (out + LANE);
      const lz = b.z + n[1] * (out + LANE);
      const from = key(b.x + n[0] * pitchOut - d[0] * pitchAlong, b.z + n[1] * pitchOut - d[1] * pitchAlong);
      const to = key(b.x + n[0] * pitchOut + d[0] * pitchAlong, b.z + n[1] * pitchOut + d[1] * pitchAlong);
      add([lx - d[0] * half, lz - d[1] * half], [lx + d[0] * half, lz + d[1] * half], from, to);
      along.add(`${from}>${to}`);
    }
  }
  let open = (_x: number, _z: number) => false;
  if (road) {
    const line = blocks.filter((b) => Math.abs(Math.abs(b.z - road.z) - PITCH_Z / 2) < 1);
    if (line.length) {
      const z = road.z;
      const off = ROAD / 2 - LANE;
      const h = ROAD / 2;
      const xs = line.map((b) => Math.round(b.x / PITCH_X));
      const [c0, c1] = [Math.min(...xs), Math.max(...xs)];
      const xw = (c0 - 0.5) * PITCH_X;
      const xe = (c1 + 0.5) * PITCH_X;
      const highway = { limit: LIMIT.highway };
      add([xw - road.reach, z + off], [xw - h, z + off], "west", key(xw, z), { ...highway, entry: true });
      add([xw - h, z - off], [xw - road.reach, z - off], key(xw, z), "west-end", { ...highway, exit: true });
      add([xe + road.reach, z - off], [xe + h, z - off], "east", key(xe, z), { ...highway, entry: true });
      add([xe + h, z + off], [xe + road.reach, z + off], key(xe, z), "east-end", { ...highway, exit: true });
      // Through town, the street's own lanes; the road where it has none.
      for (let c = c0; c <= c1; c++) {
        const [x0, x1] = [(c - 0.5) * PITCH_X, (c + 0.5) * PITCH_X];
        if (!along.has(`${key(x0, z)}>${key(x1, z)}`)) add([x0 + h, z + off], [x1 - h, z + off], key(x0, z), key(x1, z));
        if (!along.has(`${key(x1, z)}>${key(x0, z)}`)) add([x1 - h, z - off], [x0 + h, z - off], key(x1, z), key(x0, z));
      }
      open = (_x, zz) => Math.abs(zz - z) < 4.5;
    }
  }
  for (const a of all) {
    const p = a.path.at(a.path.length);
    for (const b of starts.get(a.to) ?? []) {
      const dot = a.dx * b.dx + a.dz * b.dz;
      if (dot < -0.5) continue;
      // +x to +z is a right turn: right of the heading is (-dz, dx).
      const cross = a.dx * b.dz - a.dz * b.dx;
      const kind = dot > 0.5 ? "straight" : cross > 0 ? "right" : "left";
      const q = b.path.at(0);
      const pts: [number, number][] = [];
      if (kind === "straight") pts.push([p.x, p.z], [q.x, q.z]);
      else {
        const c = a.dx ? [q.x, p.z] : [p.x, q.z];
        for (let i = 0; i <= 10; i++) {
          const t = i / 10;
          pts.push([(1 - t) ** 2 * p.x + 2 * t * (1 - t) * c[0] + t * t * q.x, (1 - t) ** 2 * p.z + 2 * t * (1 - t) * c[1] + t * t * q.z]);
        }
      }
      // A left turn round a missing block would cut across the grass.
      if (pts.some(([x, z]) => !onStreets(blocks, x, z) && !open(x, z))) continue;
      a.turns.push({ id: `${a.id}>${b.id}`, from: a, to: b, kind, corner: a.to, path: new Path(pts), limit: LIMIT[kind] });
    }
  }
  return all;
}

/** Where a trip can end: in front of a lot, or at a bus shelter. */
export interface Spot {
  lane: Lane;
  s: number;
  kind: "lot" | "stop";
}

/** The spot on the lane beside a point on the pavement's far side, or null if none runs there. */
export function spotAt(all: Lane[], x: number, z: number, kind: Spot["kind"], len = 5): Spot | null {
  let best: Spot | null = null;
  let near = 7;
  for (const lane of all) {
    if (lane.entry || lane.exit) continue;
    const a = lane.path.at(0);
    // Across the lane from it, with the lot on the lane's right.
    const across = (x - a.x) * -lane.dz + (z - a.z) * lane.dx;
    const s = (x - a.x) * lane.dx + (z - a.z) * lane.dz;
    if (across < 0 || across > near || s < 0 || s > lane.path.length) continue;
    near = across;
    // Clear of the zebra at the start of the lane, and short of the stop line.
    best = { lane, s: Math.min(Math.max(s, ZEBRA + 1.5 + len / 2), lane.path.length - STOP_LINE - LONG - 1), kind };
  }
  return best;
}

export type Mode = "drive" | "in" | "parked" | "out" | "dwell" | "away";

export interface Car {
  len: number;
  /** Share of the limit it drives at. */
  pace: number;
  bus: boolean;
  /** On a lane, or crossing on a turn. */
  lane: Lane;
  turn: Turn | null;
  /** The turn it will take at the end of its lane (none at the edge of the map). */
  next: Turn | null;
  s: number;
  v: number;
  /** Cleared to enter the crossing ahead. */
  granted: boolean;
  /** The crossing behind, until its tail is out of it; the turn it came by. */
  held: string | null;
  prev: Turn | null;
  /** Lanes driven, to tell a car that roams from one that circles. */
  driven: number;
  /** Where this trip ends: a spot, or an exit lane's end. */
  goal: Spot | Lane | null;
  mode: Mode;
  /** In a lot or at a shelter: the spot; pulling in or out: progress 0 to 1, else seconds left. */
  spot: Spot | null;
  k: number;
}

/** Cars on the lane graph. `signals` false: no lights, give way in the crossing. */
export class Flow {
  cars: Car[] = [];
  /** Cars cleared into each crossing and the turn they take, until their tails are out of it. */
  private inside = new Map<string, { car: Car; turn: Turn }[]>();
  /** Cars on each lane or turn. */
  private on = new Map<Lane | Turn, Car[]>();
  /** Per goal lane (and for long vehicles, which take no tight right turns), the turn to take from each lane on the shortest way there. */
  private routes = new Map<string, Map<Lane, Turn>>();
  /** The turns onto each lane. */
  private into = new Map<Lane, Turn[]>();
  /** Driveways with a car turning in or backing out. */
  private busy = new Set<Spot>();
  /** Whether anyone is on the pavement within `r` of a point; a car waits for them to cross its driveway. */
  people: (x: number, z: number, r: number) => boolean = () => false;
  /** Whether anyone is crossing the road within `r` of a point: nobody drives over a zebra with someone on it. */
  crossers: (x: number, z: number, r: number) => boolean = () => false;
  private lots: Spot[];
  private stops: Spot[];
  private entries: Lane[];
  private exits: Lane[];

  constructor(
    public lanes: Lane[],
    public signals: boolean,
    private r: () => number,
    spots: Spot[] = [],
  ) {
    this.lots = spots.filter((s) => s.kind === "lot");
    this.stops = spots.filter((s) => s.kind === "stop");
    this.entries = lanes.filter((l) => l.entry);
    this.exits = lanes.filter((l) => l.exit);
    for (const l of lanes) for (const t of l.turns) this.into.set(t.to, [...(this.into.get(t.to) ?? []), t]);
  }

  /** A car driving on `lane`; `local` ones live in town, the rest come in by the open road. */
  add(lane: Lane, s: number, len: number, pace: number, opts: { bus?: boolean; local?: boolean } = {}): Car {
    const car: Car = { len, pace, bus: !!opts.bus, lane, turn: null, next: null, s, v: 0, granted: false, held: null, prev: null, driven: 0, goal: null, mode: "drive", spot: null, k: 0 };
    this.cars.push(car);
    this.move(car, null, lane);
    this.trip(car, !opts.local);
    car.next = this.pick(car, lane);
    return car;
  }

  /** A car parked in a lot, which pulls out after `wait` seconds. */
  park(spot: Spot, len: number, pace: number, wait: number): Car {
    const car: Car = { len, pace, bus: false, lane: spot.lane, turn: null, next: null, s: spot.s, v: 0, granted: false, held: null, prev: null, driven: 0, goal: null, mode: "parked", spot, k: wait };
    this.cars.push(car);
    return car;
  }

  /** A car out of town, which comes in by the open road after `wait` seconds. */
  away(len: number, pace: number, wait: number): Car {
    const car: Car = { len, pace, bus: false, lane: this.entries[0] ?? this.lanes[0], turn: null, next: null, s: 0, v: 0, granted: false, held: null, prev: null, driven: 0, goal: null, mode: "away", spot: null, k: wait };
    this.cars.push(car);
    return car;
  }

  get hasLots() {
    return this.lots.length > 0;
  }

  /** A lot to start parked in. */
  anyLot(): Spot | null {
    return this.any(this.lots);
  }

  private at(piece: Lane | Turn): Car[] {
    return this.on.get(piece) ?? [];
  }

  private move(c: Car, from: Lane | Turn | null, to: Lane | Turn | null) {
    if (from) this.on.set(from, this.at(from).filter((o) => o !== c));
    if (to) this.on.set(to, [...this.at(to), c]);
  }

  private any<T>(xs: T[]): T | null {
    return xs.length ? xs[Math.floor(this.r() * xs.length)] : null;
  }

  /** A new trip: from out of town, half drive through; buses go shelter to shelter. */
  private trip(c: Car, arrived: boolean) {
    if (c.bus) {
      c.goal = this.any(this.stops.filter((s) => s.lane !== c.lane)) ?? null;
      return;
    }
    // Lots are for cars: a lorry pulling in would swing across the other lane.
    const lots = c.len > LONG ? [] : this.lots;
    const leave = this.exits.length > 0 && (lots.length === 0 || this.r() < (arrived ? 0.5 : 0.3));
    // Through traffic keeps its direction; a car from town takes either way out.
    const ahead = this.exits.filter((l) => l.dx === c.lane.dx);
    c.goal = leave ? this.any(arrived && ahead.length ? ahead : this.exits) : this.any(lots);
  }

  private goalLane(c: Car): Lane | null {
    return !c.goal ? null : "kind" in c.goal ? c.goal.lane : c.goal;
  }

  /** The best turn from each lane toward `goal` (Dijkstra over the lanes, backwards). */
  private route(goal: Lane, long: boolean): Map<Lane, Turn> {
    const id = `${goal.id}${long ? "L" : ""}`;
    let hop = this.routes.get(id);
    if (hop) return hop;
    const ok = (t: Turn) => !long || t.kind !== "right";
    // Cost from the start of a lane to the start of the goal.
    const dist = new Map<Lane, number>([[goal, 0]]);
    const done = new Set<Lane>();
    for (;;) {
      let best: Lane | null = null;
      for (const [l, d] of dist) if (!done.has(l) && (!best || d < dist.get(best)!)) best = l;
      if (!best) break;
      done.add(best);
      for (const t of this.into.get(best) ?? []) {
        if (!ok(t)) continue;
        const d = dist.get(best)! + t.path.length + TURN_COST[t.kind] + t.from.path.length;
        if (d < (dist.get(t.from) ?? Infinity)) dist.set(t.from, d);
      }
    }
    hop = new Map();
    for (const l of this.lanes) {
      let best: Turn | null = null;
      let cost = Infinity;
      for (const t of l.turns) {
        const d = t.path.length + TURN_COST[t.kind] + (dist.get(t.to) ?? Infinity);
        if (ok(t) && d < cost) [best, cost] = [t, d];
      }
      if (best) hop.set(l, best);
    }
    this.routes.set(id, hop);
    return hop;
  }

  /** The turn at the end of `lane`: toward the goal, else at random. */
  private pick(c: Car, lane: Lane): Turn | null {
    if (!lane.turns.length) return null;
    const goal = this.goalLane(c);
    const long = c.len > LONG;
    if (goal) {
      const t = this.route(goal, long).get(lane);
      if (t) return t;
      c.goal = null;
    }
    // A long vehicle turns right only where there is no other way.
    const w = lane.turns.map((t) => TURN_WEIGHT[t.kind] * (t.to.exit ? 0.3 : 1) * (long && t.kind === "right" && lane.turns.length > 1 ? 0 : 1));
    let k = this.r() * w.reduce((a, b) => a + b, 0);
    for (let i = 0; i < w.length; i++) if ((k -= w[i]) < 0) return lane.turns[i];
    return lane.turns[lane.turns.length - 1];
  }

  /** The piece the car is on and where it goes after. */
  private path(c: Car) {
    return c.turn ? c.turn.path : c.lane.path;
  }

  /** Free road ahead of `c` to the nearest car, bumper to bumper. */
  private clear(c: Car, limit: number): number {
    let best = limit;
    const ahead = (o: Car, dist: number) => {
      if (o !== c) best = Math.min(best, dist - (c.len + o.len) / 2);
    };
    // Whoever went into the crossing from this lane before, on any turn,
    // until its tail is out: measured as if on the same path.
    const lane = c.turn ? c.turn.from : c.lane;
    const leaders = (this.inside.get(lane.to) ?? []).filter((o) => o.turn.from === lane && o.car !== c);
    const progress = (o: { car: Car; turn: Turn }) => (o.car.turn ? o.car.s : o.turn.path.length + o.car.s);
    // People on a zebra ahead: stop short of its stripes (1.3 m either side of its middle).
    const zebra = (dist: number) => (best = Math.min(best, dist - 1.8 - c.len / 2 + GAP));
    if (c.turn) {
      const rest = c.turn.path.length - c.s;
      for (const o of this.at(c.turn)) if (o.s > c.s) ahead(o, o.s - c.s);
      for (const o of this.at(c.turn.to)) ahead(o, rest + o.s);
      for (const o of leaders) if (progress(o) > c.s) ahead(o.car, progress(o) - c.s);
      if (this.zebraBusy(c.turn.to, ZEBRA)) zebra(rest + ZEBRA);
      return best;
    }
    const rest = c.lane.path.length - c.s;
    for (const o of this.at(c.lane)) if (o.s > c.s) ahead(o, o.s - c.s);
    for (const o of leaders) ahead(o.car, rest + progress(o));
    if (c.granted && c.next && rest - ZEBRA > c.len / 2 + 1.8 && this.zebraBusy(c.lane, c.lane.path.length - ZEBRA)) zebra(rest - ZEBRA);
    if (c.granted && c.next && this.zebraBusy(c.next.to, ZEBRA)) zebra(rest + c.next.path.length + ZEBRA);
    if (c.granted && c.next) {
      for (const o of this.at(c.next)) ahead(o, rest + o.s);
      for (const o of this.at(c.next.to)) ahead(o, rest + c.next.path.length + o.s);
    }
    return best;
  }

  /** Whether `c` may enter the crossing ahead now. */
  private mayEnter(c: Car, turn: Turn, t: number, toLine: number): boolean {
    if (this.signals && c.lane.lit) {
      const light = signal(t, c.lane.phase);
      if (light === "red") return false;
      // On amber only a car too close to stop, even braking hard, goes on.
      if (light === "amber" && toLine > (c.v * c.v) / (2 * HARD) - 0.5) return false;
    }
    const inside = this.inside.get(turn.corner) ?? [];
    for (const { turn: o } of inside) {
      if (o.from === c.lane) continue;
      if (o.from.phase !== c.lane.phase) return false;
      // Oncoming: straight and right pass each other; a left turn waits.
      if (o.kind === "left" || turn.kind === "left") return false;
    }
    // Nobody still on the zebras either side of the crossing.
    if (this.zebraBusy(c.lane, c.lane.path.length - ZEBRA) || this.zebraBusy(turn.to, ZEBRA)) return false;
    // Room on the far side for everyone headed there.
    let room = turn.to.path.length;
    for (const o of this.at(turn.to)) room = Math.min(room, o.s - o.len / 2);
    const need = [...inside.filter((o) => o.turn.to === turn.to && o.car.lane !== turn.to).map((o) => o.car), c].reduce((a, o) => a + o.len + GAP, 0);
    return room >= need;
  }

  /** Someone crossing on the zebra across `lane` at `s` (painted where streets are paved; its middle is the road's). */
  private zebraBusy(lane: Lane, s: number): boolean {
    if (lane.entry || lane.exit) return false;
    const p = lane.path.at(s);
    const off = ROAD / 2 - LANE;
    return this.crossers(p.x + lane.dz * off, p.z - lane.dx * off, ROAD / 2 + 1);
  }

  /** Room for a car of length `len` to join `lane` at `s` from standing. */
  roomAt(lane: Lane, s: number, len: number): boolean {
    for (const o of this.at(lane)) if (o.s - o.len / 2 < s + len / 2 + GAP + 2 && o.s + o.len / 2 > s - len / 2 - 30) return false;
    // Cars about to come off the crossing behind.
    if (s < 30) for (const [, cs] of this.inside) for (const o of cs) if (o.turn.to === lane) return false;
    return true;
  }

  private stopAt(c: Car): number | null {
    const g = c.goal;
    return g && "kind" in g && g.lane === c.lane && !c.turn && c.s <= g.s + 0.5 ? g.s : null;
  }

  step(dt: number, t: number) {
    for (const c of this.cars) {
      if (c.mode !== "drive") {
        this.idle(c, dt);
        continue;
      }
      let free = this.clear(c, 200);
      const stop = this.stopAt(c);
      if (stop !== null) free = Math.min(free, stop - c.s + GAP);
      // Cleared on green, but the light changed before it reached the line: stop if it can.
      if (!c.turn && c.granted && c.next && this.signals && c.lane.lit && signal(t, c.lane.phase) !== "green") {
        const toLine = c.lane.path.length - STOP_LINE - c.len / 2 - c.s;
        if (toLine > -0.5 && toLine >= (c.v * c.v) / (2 * BRAKE) - 0.2) {
          c.granted = false;
          const at = this.inside.get(c.next.corner) ?? [];
          this.inside.set(c.next.corner, at.filter((o) => o.car !== c));
        }
      }
      if (!c.turn && !c.granted && c.next) {
        const toLine = c.lane.path.length - STOP_LINE - c.len / 2 - c.s;
        const first = !this.at(c.lane).some((o) => o.s > c.s);
        if (stop === null && first && toLine < (c.v * c.v) / (2 * BRAKE) + 3 && this.mayEnter(c, c.next, t, toLine)) {
          c.granted = true;
          this.inside.set(c.next.corner, [...(this.inside.get(c.next.corner) ?? []), { car: c, turn: c.next }]);
          free = this.clear(c, 200);
        } else free = Math.min(free, toLine + GAP);
      }
      // Ease off for the corner or the slower road ahead.
      const rest = this.path(c).length - c.s;
      const after = c.turn ? c.turn.to.limit : (c.next?.limit ?? Infinity);
      const limit = Math.min((c.turn ? c.turn.limit : c.lane.limit) * c.pace, Math.sqrt((after * c.pace) ** 2 + 2 * EASE * Math.max(0, rest)));
      const target = Math.min(limit, Math.sqrt(2 * BRAKE * Math.max(0, free - GAP)));
      c.v = Math.min(target, c.v + ACCEL * dt);
      // Turning in swings the nose 4 m on: wait for the car ahead to move up.
      if (stop !== null && Math.abs(stop - c.s) < 0.6 && c.v < 0.4 && ((c.goal as Spot).kind === "stop" || (this.clear(c, 200) > 6 && !this.busy.has(c.goal as Spot) && this.driveClear(c.goal as Spot)))) this.arrive(c);
    }
    for (const c of this.cars) {
      if (c.mode !== "drive") continue;
      c.s += c.v * dt;
      if (!c.turn && c.held && c.s - c.len / 2 > 1) this.release(c);
      const len = this.path(c).length;
      if (c.lane.exit && !c.turn) {
        if (c.s >= len - c.len) this.depart(c);
        continue;
      }
      if (c.s < len) continue;
      if (c.turn) {
        c.s -= len;
        this.move(c, c.turn, c.turn.to);
        c.lane = c.turn.to;
        c.held = c.turn.corner;
        c.prev = c.turn;
        c.turn = null;
        c.next = this.pick(c, c.lane);
        c.driven++;
      } else if (c.granted && c.next) {
        c.s -= len;
        this.move(c, c.lane, c.next);
        c.turn = c.next;
        c.granted = false;
      } else c.s = len;
    }
  }

  /** Its tail is out of the crossing: others may use it. */
  private release(c: Car) {
    const at = this.inside.get(c.held!) ?? [];
    this.inside.set(c.held!, at.filter((o) => o.car !== c));
    c.held = null;
  }

  /** The stretch of pavement a car crosses to its lot: x0, x1, z0, z1. */
  driveway(spot: Spot): [number, number, number, number] {
    const p = spot.lane.path.at(spot.s);
    const [dx, dz] = [spot.lane.dx, spot.lane.dz];
    const [cx, cz] = [p.x + dx * 4 - dz * (LANE - 1), p.z + dz * 4 + dx * (LANE - 1)];
    const [ha, hr] = [3, 1.3];
    const [hx, hz] = dx ? [ha, hr] : [hr, ha];
    return [cx - hx, cx + hx, cz - hz, cz + hz];
  }

  /** Nobody on the pavement where the car crosses it into the lot. */
  private driveClear(spot: Spot): boolean {
    const [x0, x1, z0, z1] = this.driveway(spot);
    return !this.people((x0 + x1) / 2, (z0 + z1) / 2, 3.6);
  }

  /** At its spot: a bus waits at the shelter, a car pulls into the lot. */
  private arrive(c: Car) {
    const spot = c.goal as Spot;
    c.v = 0;
    c.spot = spot;
    c.mode = spot.kind === "stop" ? "dwell" : "in";
    c.k = spot.kind === "stop" ? DWELL : 0;
    if (c.mode === "in") this.busy.add(spot);
  }

  /** Off the edge of the map: back on the open road in a while. */
  private depart(c: Car) {
    this.move(c, c.lane, null);
    c.mode = "away";
    c.k = 4 + this.r() * 30;
    c.v = 0;
  }

  private idle(c: Car, dt: number) {
    switch (c.mode) {
      case "in":
        c.k += dt / PULL;
        // Out of the lane once its tail has cleared it.
        if (c.k >= 0.6 && this.at(c.lane).includes(c)) this.move(c, c.lane, null);
        if (c.k >= 1) {
          [c.mode, c.k] = ["parked", 20 + this.r() * 70];
          this.busy.delete(c.spot!);
        }
        return;
      case "parked": {
        c.k -= dt;
        const spot = c.spot!;
        if (c.k > 0) return;
        if (this.busy.has(spot) || !this.roomAt(spot.lane, spot.s, c.len) || !this.driveClear(spot)) {
          c.k = 1 + this.r() * 2;
          return;
        }
        // On the lane from the start, so traffic behind waits for it.
        [c.lane, c.turn, c.prev, c.s, c.v, c.granted] = [spot.lane, null, null, spot.s, 0, false];
        this.move(c, null, c.lane);
        [c.mode, c.k] = ["out", 0];
        this.busy.add(spot);
        return;
      }
      case "out":
        c.k += dt / PULL;
        if (c.k < 1) return;
        this.busy.delete(c.spot!);
        c.mode = "drive";
        c.spot = null;
        this.trip(c, false);
        c.next = this.pick(c, c.lane);
        return;
      case "dwell":
        c.k -= dt;
        if (c.k > 0) return;
        c.mode = "drive";
        c.spot = null;
        this.trip(c, false);
        c.next = this.pick(c, c.lane);
        return;
      case "away": {
        c.k -= dt;
        if (c.k > 0) return;
        const lane = this.any(this.entries);
        if (!lane || !this.at(lane).every((o) => o.s - o.len / 2 > c.len + 20)) {
          c.k = 1 + this.r() * 3;
          return;
        }
        [c.lane, c.turn, c.prev, c.s, c.v, c.granted, c.mode] = [lane, null, null, c.len / 2, lane.limit * c.pace, false, "drive"];
        this.move(c, null, lane);
        this.trip(c, true);
        c.next = this.pick(c, lane);
      }
    }
  }

  /** Where the car is, and its size (0 hidden: parked, or out of town). */
  where(c: Car): { x: number; z: number; heading: number; scale: number } {
    if (c.mode === "parked" || c.mode === "away") return { x: 0, z: 0, heading: 0, scale: 0 };
    if ((c.mode === "in" || c.mode === "out") && c.spot) {
      // A right turn through the pavement into the lot; out, it reverses
      // back along the same line and ends up facing along the lane.
      const p = c.spot.lane.path.at(c.spot.s);
      const [dx, dz, rx, rz] = [c.spot.lane.dx, c.spot.lane.dz, -c.spot.lane.dz, c.spot.lane.dx];
      const deep = LANE + 2;
      const [a, m, b] = [
        [p.x, p.z],
        [p.x + dx * 4, p.z + dz * 4],
        [p.x + dx * 4 + rx * deep, p.z + dz * 4 + rz * deep],
      ];
      const k0 = c.mode === "in" ? c.k : 1 - c.k;
      const k = k0 * k0 * (3 - 2 * k0);
      const at = (t: number) => [0, 1].map((i) => (1 - t) ** 2 * a[i] + 2 * t * (1 - t) * m[i] + t * t * b[i]);
      const [x, z] = at(k);
      const [x2, z2] = at(Math.min(1, k + 0.02));
      const [x1, z1] = at(Math.max(0, k - 0.02));
      // Into the lot (out of sight) at its end.
      const hide = (1 - k0) / 0.15;
      return { x, z, heading: Math.atan2(x2 - x1, z2 - z1), scale: Math.min(1, Math.max(0, hide)) };
    }
    // The body spans two points on its path, a wheelbase apart, so it
    // follows a corner rather than swinging about its middle.
    const half = c.len * 0.3;
    const f = this.along(c, half);
    const b = this.along(c, -half);
    return { x: (f.x + b.x) / 2, z: (f.z + b.z) / 2, heading: Math.atan2(f.x - b.x, f.z - b.z), scale: 1 };
  }

  /** A point `ds` ahead of the car's middle (behind if negative), across into the next piece or back into the last. */
  private along(c: Car, ds: number): { x: number; z: number } {
    const s = c.s + ds;
    const here = this.path(c);
    if (s >= 0 && s <= here.length) return here.at(s);
    const beyond = (p: Path, d: number, end: boolean) => {
      const q = p.at(end ? p.length : 0);
      const sign = end ? 1 : -1;
      return { x: q.x + Math.sin(q.heading) * d * sign, z: q.z + Math.cos(q.heading) * d * sign };
    };
    if (s > here.length) {
      const next = c.turn ? c.turn.to.path : c.granted && c.next ? c.next.path : null;
      return next && s - here.length <= next.length ? next.at(s - here.length) : beyond(here, s - here.length, true);
    }
    const prev = c.turn ? c.turn.from.path : c.prev?.path;
    return prev && -s <= prev.length ? prev.at(prev.length + s) : beyond(here, -s, false);
  }
}

export interface Vehicle {
  len: number;
  bus?: boolean;
}

/**
 * Puts vehicles on the map: `local` ones in town (buses driving, the rest
 * driving or parked in a lot), `through` ones on the open road or about to
 * come in by it. Returns their cars in the order given.
 */
export function populate(flow: Flow, local: Vehicle[], through: Vehicle[], r: () => number): Car[] {
  const town = flow.lanes.filter((l) => !l.entry && !l.exit);
  const entries = flow.lanes.filter((l) => l.entry);
  const pace = () => 0.85 + r() * 0.2;
  const drive = (lanes: Lane[], v: Vehicle, local: boolean): Car | null => {
    for (let tries = 0; tries < 30 && lanes.length; tries++) {
      const lane = lanes[Math.floor(r() * lanes.length)];
      const room = lane.path.length - STOP_LINE - v.len - 4;
      if (room < 0) continue;
      const s = v.len / 2 + 2 + r() * room;
      if (flow.roomAt(lane, s, v.len)) return flow.add(lane, s, v.len, pace(), { bus: v.bus, local });
    }
    return null;
  };
  const cars: Car[] = [];
  for (const v of local) {
    const lot = !v.bus && v.len <= LONG && r() < 0.4 ? flow.anyLot() : null;
    cars.push((lot ? flow.park(lot, v.len, pace(), r() * 60) : drive(town, v, true)) ?? flow.away(v.len, pace(), r() * 20));
  }
  for (const v of through) cars.push(drive(entries, v, false) ?? flow.away(v.len, pace(), r() * 30));
  return cars;
}
