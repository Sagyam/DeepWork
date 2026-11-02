// City theme, step 1: lays the theme-agnostic world out as a 3D city plan.
// Pure and deterministic (seeded per plot) so it is unit tested; the
// three.js side only builds meshes from what this returns.
//
// Each district is a city block of 8 lots (4 x 2) ringed by road. Blocks
// are placed in a square spiral from the centre, so the city grows outward.
import { DISTRICT_SIZE, type Construction, type Plot, type World } from "../proto";

export const LOT = 12;
export const ROAD = 9;
export const BLOCK_X = 4 * LOT;
export const BLOCK_Z = 2 * LOT;
export const PITCH_X = BLOCK_X + ROAD;
export const PITCH_Z = BLOCK_Z + ROAD;

export type Kind = "cottage" | "shop" | "apartment" | "office" | "landmark";
export const KINDS: Kind[] = ["cottage", "shop", "apartment", "office", "landmark"];

export interface Spec {
  index: number;
  kind: Kind;
  grade: number;
  /** Lot centre on the ground plane. */
  x: number;
  z: number;
  /** Rotation about Y so the front faces its road. */
  rot: number;
  w: number;
  d: number;
  floors: number;
  floorH: number;
  /** Body height, without roof furniture. */
  height: number;
  /** Indexes into the renderer's palettes. */
  wall: number;
  accent: number;
  /** Per-building randomness for details (window pattern, roof gear). */
  seed: number;
  damage: number;
  rubble: boolean;
}

export interface SiteSpec extends Spec {
  /** 0 to 1; a stopwatch pulses near the top of its current grade. */
  progress: number;
  surrendering: boolean;
  stopwatch: boolean;
}

export interface CityPlan {
  /** Block centres in use (including the one the site is on), spiral order. */
  blocks: { x: number; z: number }[];
  buildings: Spec[];
  site: SiteSpec | null;
  /** Empty lots in used blocks: grass, maybe a tree. */
  emptyLots: { x: number; z: number; seed: number }[];
  /** Trees outside the city, more with the tier. */
  trees: { x: number; z: number; s: number; seed: number }[];
  bounds: { minX: number; maxX: number; minZ: number; maxZ: number };
  tier: number;
}

/** mulberry32, seeded from a u64 that JSON may have rounded to a double. */
export function rng(seed: number): () => number {
  let s = (Math.floor(seed / 2 ** 32) ^ Math.imul(seed >>> 0, 0x9e3779b1)) | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Square spiral: (0,0), (1,0), (1,1), (0,1), (-1,1), (-1,0), ... */
export function spiral(n: number): [number, number][] {
  const out: [number, number][] = [];
  let x = 0;
  let y = 0;
  let dx = 1;
  let dy = 0;
  let leg = 1;
  let walked = 0;
  let turns = 0;
  while (out.length < n) {
    out.push([x, y]);
    x += dx;
    y += dy;
    if (++walked === leg) {
      walked = 0;
      [dx, dy] = [-dy, dx];
      if (++turns % 2 === 0) leg++;
    }
  }
  return out;
}

export function blockCentre(district: number): { x: number; z: number } {
  const [bx, bz] = spiral(district + 1)[district];
  return { x: bx * PITCH_X, z: bz * PITCH_Z };
}

/** Lot centre and facing for a plot index. Front row faces -z, back row +z. */
export function lot(index: number): { x: number; z: number; rot: number } {
  const c = blockCentre(Math.floor(index / DISTRICT_SIZE));
  const k = index % DISTRICT_SIZE;
  const col = k % 4;
  const back = k >= 4;
  return {
    x: c.x - BLOCK_X / 2 + LOT / 2 + col * LOT,
    z: c.z + (back ? LOT / 2 : -LOT / 2),
    rot: back ? 0 : Math.PI,
  };
}

const between = (r: () => number, a: number, b: number) => a + (b - a) * r();
const pick = (r: () => number, n: number) => Math.floor(r() * n);

/** Shape of a building of a grade, from its seed. */
export function shape(grade: number, seed: number) {
  const r = rng(seed);
  const g = Math.min(4, Math.max(0, grade));
  const kind = KINDS[g];
  let w: number, d: number, floors: number, floorH: number;
  switch (kind) {
    case "cottage":
      [w, d, floors, floorH] = [between(r, 6, 7.5), between(r, 5.5, 7), 1, 3.2];
      break;
    case "shop":
      [w, d, floors, floorH] = [between(r, 8, 9.5), between(r, 7, 9), 2 + pick(r, 2), 3.4];
      break;
    case "apartment":
      [w, d, floors, floorH] = [between(r, 8.5, 9.8), between(r, 8.5, 9.8), 4 + pick(r, 4), 3.1];
      break;
    case "office":
      [w, d, floors, floorH] = [between(r, 9, 10.2), between(r, 9, 10.2), 9 + pick(r, 6), 3.5];
      break;
    case "landmark":
      [w, d, floors, floorH] = [10.4, 10.4, 18 + pick(r, 8), 3.5];
      break;
  }
  return { kind, grade: g, w, d, floors, floorH, height: floors * floorH, wall: pick(r, 8), accent: pick(r, 6), seed: Math.floor(r() * 2 ** 31) };
}

function spec(p: Plot): Spec {
  const l = lot(p.index);
  return { index: p.index, ...l, ...shape(p.grade, p.seed), damage: p.damage, rubble: p.rubble };
}

function siteSpec(c: Construction, elapsedSecs: number): SiteSpec {
  const l = lot(c.index);
  const progress = c.progress_permille === null ? 0.8 + 0.2 * ((elapsedSecs % 900) / 900) : c.progress_permille / 1000;
  return {
    index: c.index,
    ...l,
    ...shape(c.grade, c.seed),
    damage: 0,
    rubble: false,
    progress: Math.min(1, Math.max(0, progress)),
    surrendering: c.surrendering,
    stopwatch: c.progress_permille === null,
  };
}

export function plan(w: World, elapsedSecs = 0): CityPlan {
  const siteIndex = w.construction?.index ?? -1;
  const lots = Math.max(w.plots.length, siteIndex + 1);
  const districts = Math.max(1, Math.ceil(lots / DISTRICT_SIZE));
  const blocks = Array.from({ length: districts }, (_, d) => blockCentre(d));
  const buildings = w.plots.filter((p) => p.index !== siteIndex).map(spec);
  const site = w.construction ? siteSpec(w.construction, elapsedSecs) : null;

  const emptyLots: CityPlan["emptyLots"] = [];
  for (let i = lots; i < districts * DISTRICT_SIZE; i++) emptyLots.push({ ...lot(i), seed: i * 2654435761 });

  const half = { x: PITCH_X / 2, z: PITCH_Z / 2 };
  const bounds = {
    minX: Math.min(...blocks.map((b) => b.x)) - half.x,
    maxX: Math.max(...blocks.map((b) => b.x)) + half.x,
    minZ: Math.min(...blocks.map((b) => b.z)) - half.z,
    maxZ: Math.max(...blocks.map((b) => b.z)) + half.z,
  };

  // A ring of countryside around the city; denser parkland at higher tiers.
  const r = rng(0x7ee5 + districts);
  const trees: CityPlan["trees"] = [];
  const count = 40 + w.tier * 30 + districts * 6;
  const pad = 70;
  for (let i = 0; i < count * 4 && trees.length < count; i++) {
    const x = between(r, bounds.minX - pad, bounds.maxX + pad);
    const z = between(r, bounds.minZ - pad, bounds.maxZ + pad);
    const inside = x > bounds.minX - 3 && x < bounds.maxX + 3 && z > bounds.minZ - 3 && z < bounds.maxZ + 3;
    if (!inside) trees.push({ x, z, s: between(r, 0.7, 1.4), seed: Math.floor(r() * 2 ** 31) });
  }

  return { blocks, buildings, site, emptyLots, trees, bounds, tier: w.tier };
}

/** A closed path that can be sampled by distance travelled. */
export interface Loop {
  length: number;
  /** Position and heading (rotation about y that turns +z to the direction of travel) at distance d. */
  at(d: number): { x: number; z: number; heading: number };
}

/**
 * A loop around a block centre, `hx` / `hz` out from it, with rounded
 * corners. Travel keeps the block on the right (right-hand traffic: a car
 * in the lane next to its block drives with the kerb on its right).
 */
export function blockLoop(cx: number, cz: number, hx: number, hz: number, r: number): Loop {
  const pts: [number, number][] = [];
  const arc = (ox: number, oz: number, a0: number) => {
    for (let i = 0; i <= 6; i++) {
      const a = a0 + (Math.PI / 2) * (i / 6);
      pts.push([ox + r * Math.cos(a), oz + r * Math.sin(a)]);
    }
  };
  arc(cx + hx - r, cz - hz + r, -Math.PI / 2);
  arc(cx + hx - r, cz + hz - r, 0);
  arc(cx - hx + r, cz + hz - r, Math.PI / 2);
  arc(cx - hx + r, cz - hz + r, Math.PI);
  pts.push(pts[0]);
  const cum = [0];
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const length = cum[cum.length - 1];
  return {
    length,
    at(d: number) {
      const t = ((d % length) + length) % length;
      let i = 1;
      while (i < cum.length - 1 && cum[i] < t) i++;
      const seg = cum[i] - cum[i - 1] || 1;
      const k = (t - cum[i - 1]) / seg;
      const [x0, z0] = pts[i - 1];
      const [x1, z1] = pts[i];
      return { x: x0 + (x1 - x0) * k, z: z0 + (z1 - z0) * k, heading: Math.atan2(x1 - x0, z1 - z0) };
    },
  };
}
