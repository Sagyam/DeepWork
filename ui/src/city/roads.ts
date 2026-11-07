// The streets as a lane graph, and the traffic that drives it. Each block
// is ringed by four lanes, one per side, travelled with the block on the
// right; a neighbour's lane on the same road runs the other way. At every
// crossing a car goes straight, turns right or turns left onto another
// lane, waits at red, gives way inside the crossing and keeps a gap to the
// car ahead. Pure: traffic.ts draws it.
import { BLOCK_X, BLOCK_Z, PAVEMENT, PITCH_X, PITCH_Z, ROAD, onStreets } from "./plan";

/** The lane next to the block: a quarter of the way across the carriageway. */
export const LANE = PAVEMENT + (ROAD - 2 * PAVEMENT) / 4;
/** Braking and acceleration, m/s². */
const ACCEL = 3;
const BRAKE = 4;
/** Bumper to bumper when queued, m. */
const GAP = 2;
/** From the stop line to the end of the lane, past the zebra crossing. */
const STOP_LINE = 4;
/** Straight on twice as often as each turn. */
const TURN_WEIGHT = { straight: 2, right: 1, left: 1 };

export type Light = "green" | "amber" | "red";

/**
 * The signal cycle, shared with the lenses (real.ts): 30 s in which road
 * "a" (along z) gets green, amber, then red while road "b" (along x) waits,
 * and the other way round.
 */
export function signal(t: number, phase: string): Light {
  const T = 30;
  const c = ((t % T) + T) % T;
  const k = phase === "a" ? c : (c + T / 2) % T;
  return k < 12 ? "green" : k < 15 ? "amber" : "red";
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
  /** The crossing it ends at. */
  to: string;
  path: Path;
  turns: Turn[];
}

export interface Turn {
  id: string;
  from: Lane;
  to: Lane;
  kind: "straight" | "right" | "left";
  corner: string;
  path: Path;
}

/** Sides of a block in driving order: direction and the outward normal. */
const SIDES = [
  { d: [1, 0], n: [0, -1] },
  { d: [0, 1], n: [1, 0] },
  { d: [-1, 0], n: [0, 1] },
  { d: [0, -1], n: [-1, 0] },
] as const;

const key = (x: number, z: number) => `${Math.round(x)},${Math.round(z)}`;

/** Every lane round the blocks, and the turns between them that stay on the asphalt. */
export function lanes(blocks: { x: number; z: number }[]): Lane[] {
  const all: Lane[] = [];
  const starts = new Map<string, Lane[]>();
  const ends: { lane: Lane; p: [number, number] }[] = [];
  for (const b of blocks) {
    for (const { d, n } of SIDES) {
      const out = n[0] ? BLOCK_X / 2 : BLOCK_Z / 2;
      const along = d[0] ? BLOCK_X / 2 : BLOCK_Z / 2;
      const pitchOut = n[0] ? PITCH_X / 2 : PITCH_Z / 2;
      const pitchAlong = d[0] ? PITCH_X / 2 : PITCH_Z / 2;
      const lx = b.x + n[0] * (out + LANE);
      const lz = b.z + n[1] * (out + LANE);
      const a: [number, number] = [lx - d[0] * along, lz - d[1] * along];
      const e: [number, number] = [lx + d[0] * along, lz + d[1] * along];
      const from = key(b.x + n[0] * pitchOut - d[0] * pitchAlong, b.z + n[1] * pitchOut - d[1] * pitchAlong);
      const to = key(b.x + n[0] * pitchOut + d[0] * pitchAlong, b.z + n[1] * pitchOut + d[1] * pitchAlong);
      const lane: Lane = { id: all.length, dx: d[0], dz: d[1], phase: d[1] ? "a" : "b", to, path: new Path([a, e]), turns: [] };
      all.push(lane);
      starts.set(from, [...(starts.get(from) ?? []), lane]);
      ends.push({ lane, p: e });
    }
  }
  const startOf = (l: Lane) => l.path.at(0);
  for (const { lane: a, p } of ends) {
    for (const b of starts.get(a.to) ?? []) {
      const dot = a.dx * b.dx + a.dz * b.dz;
      if (dot < -0.5) continue;
      // +x to +z is a right turn: right of the heading is (-dz, dx).
      const cross = a.dx * b.dz - a.dz * b.dx;
      const kind = dot > 0.5 ? "straight" : cross > 0 ? "right" : "left";
      const q = startOf(b);
      const pts: [number, number][] = [];
      if (kind === "straight") pts.push(p, [q.x, q.z]);
      else {
        const c = a.dx ? [q.x, p[1]] : [p[0], q.z];
        for (let i = 0; i <= 10; i++) {
          const t = i / 10;
          pts.push([(1 - t) ** 2 * p[0] + 2 * t * (1 - t) * c[0] + t * t * q.x, (1 - t) ** 2 * p[1] + 2 * t * (1 - t) * c[1] + t * t * q.z]);
        }
      }
      // A left turn round a missing block would cut across the grass.
      if (pts.some(([x, z]) => !onStreets(blocks, x, z))) continue;
      a.turns.push({ id: `${a.id}>${b.id}`, from: a, to: b, kind, corner: a.to, path: new Path(pts) });
    }
  }
  return all;
}

export interface Car {
  len: number;
  cruise: number;
  /** On a lane, or crossing on a turn. */
  lane: Lane;
  turn: Turn | null;
  /** The turn it will take at the end of its lane. */
  next: Turn;
  s: number;
  v: number;
  /** Cleared to enter the crossing ahead. */
  granted: boolean;
  /** Lanes driven, to tell a car that roams from one that circles. */
  driven: number;
}

/** Cars on the lane graph. `signals` false: no lights, give way in the crossing. */
export class Flow {
  cars: Car[] = [];
  /** Cars cleared into each crossing, until they leave it. */
  private inside = new Map<string, Car[]>();
  /** Cars on each lane or turn. */
  private on = new Map<Lane | Turn, Car[]>();

  constructor(
    public lanes: Lane[],
    public signals: boolean,
    private r: () => number,
  ) {}

  add(lane: Lane, s: number, len: number, cruise: number): Car {
    const car: Car = { len, cruise, lane, turn: null, next: this.pick(lane), s, v: 0, granted: false, driven: 0 };
    this.cars.push(car);
    this.move(car, null, lane);
    return car;
  }

  private at(piece: Lane | Turn): Car[] {
    return this.on.get(piece) ?? [];
  }

  private move(c: Car, from: Lane | Turn | null, to: Lane | Turn) {
    if (from) this.on.set(from, this.at(from).filter((o) => o !== c));
    this.on.set(to, [...this.at(to), c]);
  }

  private pick(lane: Lane): Turn {
    const w = lane.turns.map((t) => TURN_WEIGHT[t.kind]);
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
    if (c.turn) {
      const rest = c.turn.path.length - c.s;
      for (const o of this.at(c.turn)) if (o.s > c.s) ahead(o, o.s - c.s);
      for (const o of this.at(c.turn.to)) ahead(o, rest + o.s);
      return best;
    }
    const rest = c.lane.path.length - c.s;
    for (const o of this.at(c.lane)) if (o.s > c.s) ahead(o, o.s - c.s);
    if (c.granted) {
      for (const o of this.at(c.next)) ahead(o, rest + o.s);
      for (const o of this.at(c.next.to)) ahead(o, rest + c.next.path.length + o.s);
    }
    return best;
  }

  /** Whether `c` may enter the crossing ahead now. */
  private mayEnter(c: Car, t: number, toLine: number): boolean {
    const turn = c.next;
    if (this.signals) {
      const light = signal(t, c.lane.phase);
      if (light === "red") return false;
      if (light === "amber" && toLine > (c.v * c.v) / (2 * BRAKE)) return false;
    }
    const inside = this.inside.get(turn.corner) ?? [];
    for (const o of inside) {
      const from = o.turn?.from ?? o.lane;
      if (from === c.lane) continue;
      if (from.phase !== c.lane.phase) return false;
      // Oncoming: straight and right pass each other; a left turn waits.
      if (o.next.kind === "left" || turn.kind === "left") return false;
    }
    // Room on the far side for everyone headed there.
    let room = turn.to.path.length;
    for (const o of this.at(turn.to)) room = Math.min(room, o.s - o.len / 2);
    const need = [...inside.filter((o) => o.next.to === turn.to), c].reduce((a, o) => a + o.len + GAP, 0);
    return room >= need;
  }

  step(dt: number, t: number) {
    for (const c of this.cars) {
      let free = this.clear(c, 200);
      if (!c.turn && !c.granted) {
        const toLine = c.lane.path.length - STOP_LINE - c.len / 2 - c.s;
        const first = !this.at(c.lane).some((o) => o.s > c.s);
        if (first && toLine < (c.v * c.v) / (2 * BRAKE) + 3 && this.mayEnter(c, t, toLine)) {
          c.granted = true;
          this.inside.set(c.next.corner, [...(this.inside.get(c.next.corner) ?? []), c]);
          free = this.clear(c, 200);
        } else free = Math.min(free, toLine);
      }
      const target = Math.min(c.cruise, Math.sqrt(2 * BRAKE * Math.max(0, free - GAP)));
      c.v = Math.min(target, c.v + ACCEL * dt);
    }
    for (const c of this.cars) {
      c.s += c.v * dt;
      const len = this.path(c).length;
      if (c.s < len) continue;
      if (c.turn) {
        const at = this.inside.get(c.turn.corner) ?? [];
        this.inside.set(c.turn.corner, at.filter((o) => o !== c));
        c.s -= len;
        this.move(c, c.turn, c.turn.to);
        c.lane = c.turn.to;
        c.turn = null;
        c.next = this.pick(c.lane);
        c.driven++;
      } else if (c.granted) {
        c.s -= len;
        this.move(c, c.lane, c.next);
        c.turn = c.next;
        c.granted = false;
      } else c.s = len;
    }
  }

  where(c: Car) {
    return this.path(c).at(c.s);
  }
}
