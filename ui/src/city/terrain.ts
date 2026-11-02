// City theme: the land around the city. Pure and deterministic, so it is
// unit tested; land.ts builds the meshes from it.
//
// The geography is fixed: a river winds north-south east of the city and a
// lake lies to the west, with hills beyond the town and a ring of mountains
// on the horizon. Only the flattened area under the city follows its size,
// so the city grows into the hills, never into the water.
import { PITCH_Z } from "./plan";

/** Water surface height; the land is dry wherever it is above this. */
export const WATER = -2;
/** Radius of the modelled land. */
export const RADIUS = 3200;
/** The road out of town runs along this z, east and west. */
export const ROAD_Z = -PITCH_Z / 2;
export const LAKE = { x: -430, z: 300, r: 125 };

function hash(x: number, y: number): number {
  let h = Math.imul(x | 0, 0x27d4eb2d) ^ Math.imul(y | 0, 0x165667b1);
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

/** Smooth value noise in [0, 1]. */
export function noise(x: number, y: number): number {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const xf = x - xi;
  const yf = y - yi;
  const u = xf * xf * (3 - 2 * xf);
  const v = yf * yf * (3 - 2 * yf);
  const a = hash(xi, yi);
  const b = hash(xi + 1, yi);
  const c = hash(xi, yi + 1);
  const d = hash(xi + 1, yi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}

export function fbm(x: number, y: number, octaves = 4): number {
  let sum = 0;
  let amp = 0.5;
  let norm = 0;
  for (let i = 0; i < octaves; i++) {
    sum += noise(x, y) * amp;
    norm += amp;
    x = x * 2.03 + 17.1;
    y = y * 2.03 + 9.7;
    amp *= 0.5;
  }
  return sum / norm;
}

/** Ridged noise: sharp crests, for mountain ranges. */
function ridged(x: number, y: number): number {
  let sum = 0;
  let amp = 0.5;
  let norm = 0;
  let weight = 1;
  for (let i = 0; i < 5; i++) {
    const n = 1 - Math.abs(2 * noise(x, y) - 1);
    const r = n * n * weight;
    weight = Math.min(1, r * 2);
    sum += r * amp;
    norm += amp;
    x = x * 2.1 + 31.7;
    y = y * 2.1 + 5.3;
    amp *= 0.5;
  }
  return sum / norm;
}

export const smoothstep = (x: number, a: number, b: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/** The river's centre line: x as a function of z. */
export function riverX(z: number): number {
  return 430 + 75 * Math.sin(z / 230) + 30 * Math.sin(z / 87 + 1.3);
}

/** Horizontal distance from the river's centre line (good while it meanders gently). */
export function riverDistance(x: number, z: number): number {
  const dxdz = (75 / 230) * Math.cos(z / 230) + (30 / 87) * Math.cos(z / 87 + 1.3);
  return Math.abs(x - riverX(z)) / Math.sqrt(1 + dxdz * dxdz);
}

export interface Bounds {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
}

export interface Land {
  height(x: number, z: number): number;
  /** 0 on the city's flat ground, 1 out in open country. */
  wild(x: number, z: number): number;
  /** 0 on the city's flat pad, 1 where the land starts to rise. */
  open(x: number, z: number): number;
  /** Where the east road crosses the river. */
  bridge: { x: number; z: number };
}

export function terrain(b: Bounds): Land {
  const rect = (x: number, z: number) => {
    const dx = Math.max(b.minX - x, 0, x - b.maxX);
    const dz = Math.max(b.minZ - z, 0, z - b.maxZ);
    return Math.hypot(dx, dz);
  };
  /** 0 under the city's flat pad, 1 out in open country. */
  const open = (x: number, z: number) => smoothstep(rect(x, z), 12, 62);
  /** 0 under the city's flat pad, 1 where the hills proper begin. */
  const country = (x: number, z: number) => smoothstep(rect(x, z), 55, 520);
  /** The road runs on a level shelf; country either side of it stays wild. */
  const wild = (x: number, z: number) =>
    smoothstep(rect(x, z), 30, 130) * smoothstep(Math.abs(z - ROAD_Z), 12, 46);
  const bridge = { x: riverX(ROAD_Z), z: ROAD_Z };
  /** The land as it would be with no road: swells, foothills, the range. */
  const natural = (x: number, z: number) => {
    const r = Math.hypot(x, z);
    const dRiver = riverDistance(x, z);
    const lake = Math.hypot(x - LAKE.x, z - LAKE.z) / LAKE.r;
    // Low swells just outside town, so the fields are never a billiard table
    // and the town is not sunk in a bowl either.
    const roll = (8 * Math.pow(fbm(x / 150 + 1.7, z / 150 - 9.2, 3), 1.3) + 4 * Math.pow(fbm(x / 58 + 5.5, z / 58 - 2.2, 2), 2)) * open(x, z);
    const hills = 55 * Math.pow(fbm(x / 270 + 3.1, z / 270 - 7.4), 2) * 1.6 * country(x, z);
    // Wooded foothills climb toward the range in ragged spurs.
    const foot = 170 * ridged(x / 520 + 5, z / 520 + 2) * smoothstep(r, 380, 1300) * (0.4 + 0.6 * noise(x / 300 + 3, z / 300 - 6)) * country(x, z);
    const mountains = 720 * ridged(x / 780 + 11, z / 780 - 4) * smoothstep(r, 820, 2100);
    // A wall of peaks at the rim hides the edge of the world.
    const rim = 340 * smoothstep(r, 2450, 3150);
    // The river runs in a floodplain and the lake in its own shallow basin.
    return (roll + hills + foot + mountains + rim) * smoothstep(dRiver, 24, 110) * smoothstep(lake, 1.05, 2.4);
  };
  /** Height of the road bed at x: the land it crosses, level over the bridge. */
  const roadY = (x: number) => (Math.abs(x - bridge.x) < 46 ? 0 : natural(x, ROAD_Z));
  const height = (x: number, z: number) => {
    const dRiver = riverDistance(x, z);
    const lake = Math.hypot(x - LAKE.x, z - LAKE.z) / LAKE.r;
    let h = natural(x, z);
    // Grade the road bed level across its width; keep it off the bridge span
    // so the river runs under the deck instead of around a causeway.
    const onRoad = 1 - smoothstep(Math.abs(z - ROAD_Z), 8, 30);
    h += (roadY(x) - h) * onRoad * smoothstep(dRiver, 26, 52);
    h -= 4.3 * (1 - smoothstep(dRiver, 9, 17));
    h -= 5 * (1 - smoothstep(lake, 0.72, 1.02));
    return h;
  };
  return { height, wild, open, bridge };
}
