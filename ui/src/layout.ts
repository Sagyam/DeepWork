// Skyline theme, step 1: turns the theme-agnostic world into a scene of
// shapes with positions and colours. Pure and deterministic (seeded by plot),
// so it is unit tested; skyline.ts only draws what this returns.
import { DISTRICT_SIZE, type Construction, type Plot, type World } from "./proto";

export type Roof = "pitched" | "awning" | "tank" | "antenna" | "spire";

export interface Window {
  x: number;
  y: number;
  w: number;
  h: number;
  /** Fraction of the evening at which it lights up: lit when `glow > on`. */
  on: number;
  broken: boolean;
}

export interface Building {
  index: number;
  x: number;
  /** Ground line of its row. */
  base: number;
  w: number;
  h: number;
  grade: number;
  damage: number;
  roof: Roof;
  facade: number;
  windows: Window[];
  /** Missing top corner for heavily damaged buildings, as a fraction of w. */
  notch: number;
  /** Crack polylines (absolute coordinates). */
  cracks: number[][];
  /** 1 for the front row, smaller and hazier behind. */
  depth: number;
}

export interface Rubble {
  index: number;
  points: number[];
  beams: { x: number; y: number; len: number; angle: number }[];
  depth: number;
}

export interface Site {
  index: number;
  x: number;
  base: number;
  w: number;
  /** Full height of the building being built. */
  target: number;
  /** Built so far. */
  built: number;
  grade: number;
  surrendering: boolean;
  stopwatch: boolean;
  depth: number;
}

export interface Scene {
  width: number;
  height: number;
  ground: number;
  sky: number[];
  /** 0 by day to 1 at night; windows, stars and lamps follow it. */
  glow: number;
  buildings: Building[];
  rubble: Rubble[];
  site: Site | null;
  /** Distant silhouettes behind the city, grows with the tier. */
  far: { points: number[]; color: number }[];
  lamps: number[];
}

/** Height range (fraction of the tallest possible building) per grade. */
const HEIGHT: [number, number][] = [
  [0.1, 0.14],
  [0.19, 0.26],
  [0.33, 0.43],
  [0.52, 0.64],
  [0.76, 0.9],
];
const WIDTH: [number, number][] = [
  [0.72, 0.86],
  [0.76, 0.92],
  [0.62, 0.8],
  [0.56, 0.74],
  [0.52, 0.66],
];
/** Tallest a building may be for its width, so narrow slots don't make needles. */
const ASPECT = [1.2, 2.4, 4.5, 7, 10];
const ROOFS: Roof[][] = [["pitched"], ["awning", "pitched"], ["tank", "tank", "antenna"], ["antenna", "tank"], ["spire"]];
const FACADES = [0x5b6378, 0x6e5a55, 0x52675f, 0x6a6577, 0x7a6c58, 0x4f5d73, 0x75635f, 0x5e6e7c];

const MIN_SLOT = 26;
const MAX_SLOT = 90;
const DISTRICT_GAP = 0.7;

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

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const between = (r: () => number, [a, b]: [number, number]) => lerp(a, b, r());

export function mix(a: number, b: number, t: number): number {
  const ch = (c: number, s: number) => (c >> s) & 0xff;
  const m = (s: number) => Math.round(lerp(ch(a, s), ch(b, s), t)) << s;
  return m(16) | m(8) | m(0);
}

/** Sky colours, top to bottom, for a local hour (0 to 24). */
const SKIES: [number, number[]][] = [
  [0, [0x070a1a, 0x101634, 0x1c2145]],
  [5, [0x0b1030, 0x2a2a5a, 0x5a4470]],
  [6.5, [0x3a5a9a, 0xe0907a, 0xffc98a]],
  [9, [0x3f7fd0, 0x7fb4e6, 0xc4def0]],
  [16, [0x3a78c8, 0x86b6e0, 0xd2e2ee]],
  [18.5, [0x2d3f7a, 0xd0705a, 0xffb070]],
  [20, [0x0f1438, 0x2a2650, 0x55365a]],
  [22, [0x070a1a, 0x101634, 0x1c2145]],
  [24, [0x070a1a, 0x101634, 0x1c2145]],
];

export function skyAt(hour: number): { sky: number[]; glow: number } {
  let i = SKIES.findIndex(([h]) => h > hour) - 1;
  if (i < 0) i = SKIES.length - 2;
  const [h0, c0] = SKIES[i];
  const [h1, c1] = SKIES[i + 1];
  const t = (hour - h0) / (h1 - h0);
  const sky = c0.map((c, k) => mix(c, c1[k], t));
  // Lights come on through dusk and go off through dawn.
  const glow =
    hour < 5 || hour >= 20.5 ? 1 : hour < 7.5 ? 1 - (hour - 5) / 2.5 : hour < 17.5 ? 0 : (hour - 17.5) / 3;
  return { sky, glow: Math.min(1, Math.max(0, glow)) };
}

interface Slot {
  index: number;
  x: number;
  base: number;
  w: number;
  depth: number;
  maxH: number;
}

/**
 * Plots go left to right in districts with a gap between them. When they no
 * longer fit, older districts move to rows further back, smaller and hazier.
 */
export function slots(columns: number, width: number, ground: number, maxH: number): Slot[] {
  const districts = Math.ceil(columns / DISTRICT_SIZE);
  if (districts === 0) return [];
  const margin = Math.max(24, width * 0.04);
  const usable = width - 2 * margin;
  const span = (n: number) => n * DISTRICT_SIZE + (n - 1) * DISTRICT_GAP;
  let rows = 1;
  let perRow = districts;
  while (usable / span(perRow) < MIN_SLOT && rows < 4) {
    rows++;
    perRow = Math.ceil(districts / rows);
  }
  const slot0 = Math.min(MAX_SLOT, usable / span(perRow));
  const out: Slot[] = [];
  for (let d = 0; d < districts; d++) {
    // Newest districts in front: row 0 holds the last `perRow` districts and
    // the back row whatever is left over.
    const row = Math.min(rows - 1, Math.floor((districts - 1 - d) / perRow));
    const first = row === rows - 1 ? 0 : districts - (row + 1) * perRow;
    const inRow = row === rows - 1 ? districts - (rows - 1) * perRow : perRow;
    const pos = d - first;
    const depth = Math.pow(0.72, row);
    const slot = slot0 * depth;
    const rowWidth = span(inRow) * slot;
    const left = (width - rowWidth) / 2;
    const base = ground - row * Math.max(10, (width / 60) * depth);
    for (let k = 0; k < DISTRICT_SIZE; k++) {
      const index = d * DISTRICT_SIZE + k;
      if (index >= columns) break;
      out.push({
        index,
        x: left + (pos * (DISTRICT_SIZE + DISTRICT_GAP) + k) * slot,
        base,
        w: slot,
        depth,
        maxH: maxH * depth,
      });
    }
  }
  return out;
}

function building(p: Plot, s: Slot, glowSeed: number): Building {
  const r = rng(p.seed);
  const g = Math.min(4, Math.max(0, p.grade));
  // Never wider than the slot, never a needle.
  const w = Math.max(s.w * between(r, WIDTH[g]), 8 * s.depth);
  const h = Math.max(Math.min(between(r, HEIGHT[g]) * s.maxH, w * ASPECT[g]), w * 0.7);
  const x = s.x + (s.w - w) / 2 + (r() - 0.5) * (s.w - w) * 0.6;
  const roofs = ROOFS[g];
  const roof = roofs[Math.floor(r() * roofs.length)];
  const facade = FACADES[Math.floor(r() * FACADES.length)];
  const top = s.base - h;
  const roofH = roof === "pitched" ? Math.min(w * 0.45, h * 0.5) : 0;
  const bodyTop = top + roofH;

  const pitch = Math.max(5, Math.min(12, w / 4)) * Math.max(0.6, s.depth);
  const cols = Math.max(1, Math.floor((w - pitch * 0.6) / pitch));
  const rows = Math.max(1, Math.floor((s.base - bodyTop - pitch * 1.1) / (pitch * 1.25)));
  const winW = pitch * 0.5;
  const winH = pitch * 0.62;
  const padX = (w - cols * pitch) / 2 + (pitch - winW) / 2;
  const windows: Window[] = [];
  const brokenShare = [0, 0.3, 0.6][Math.min(2, p.damage)];
  const wr = rng(p.seed ^ glowSeed);
  for (let row = 0; row < rows; row++) {
    for (let c = 0; c < cols; c++) {
      windows.push({
        x: x + padX + c * pitch,
        y: bodyTop + pitch * 0.55 + row * pitch * 1.25,
        w: winW,
        h: winH,
        // A third of the windows stay dark even late at night.
        on: wr() * 1.45 + 0.05,
        broken: wr() < brokenShare,
      });
    }
  }

  const notch = p.damage >= 2 ? 0.25 + r() * 0.3 : 0;
  const cracks: number[][] = [];
  for (let i = 0; i < p.damage * 2; i++) {
    let cx = x + w * (0.15 + r() * 0.7);
    let cy = bodyTop + (s.base - bodyTop) * r() * 0.6;
    const line = [cx, cy];
    for (let k = 0; k < 4; k++) {
      cx += (r() - 0.5) * w * 0.25;
      cy += h * (0.04 + r() * 0.06);
      line.push(Math.min(x + w, Math.max(x, cx)), Math.min(s.base, cy));
    }
    cracks.push(line);
  }

  return { index: p.index, x, base: s.base, w, h, grade: g, damage: p.damage, roof, facade, windows, notch, cracks, depth: s.depth };
}

function rubble(p: Plot, s: Slot): Rubble {
  const r = rng(p.seed);
  const w = s.w * 0.85;
  const x0 = s.x + (s.w - w) / 2;
  const peak = Math.min(s.maxH * 0.08, w * 0.45);
  const points = [x0, s.base];
  const n = 7;
  for (let i = 1; i < n; i++) {
    const t = i / n;
    const hump = Math.sin(t * Math.PI);
    points.push(x0 + t * w, s.base - peak * hump * (0.55 + r() * 0.45));
  }
  points.push(x0 + w, s.base);
  const beams = Array.from({ length: 2 + Math.floor(r() * 2) }, () => ({
    x: x0 + w * (0.2 + r() * 0.6),
    y: s.base - peak * (0.3 + r() * 0.5),
    len: w * (0.3 + r() * 0.3),
    angle: (r() - 0.5) * 1.6,
  }));
  return { index: p.index, points, beams, depth: s.depth };
}

function site(c: Construction, s: Slot, elapsedSecs: number): Site {
  const r = rng(c.seed);
  const g = Math.min(4, Math.max(0, c.grade));
  const w = Math.max(s.w * between(r, WIDTH[g]), 8 * s.depth);
  const target = Math.max(Math.min(between(r, HEIGHT[g]) * s.maxH, w * ASPECT[g]), w * 0.7);
  // A stopwatch has no end, so its building is always as tall as its grade so
  // far and keeps a slow pulse of new floors.
  const progress = c.progress_permille === null ? 0.85 + 0.15 * ((elapsedSecs % 600) / 600) : c.progress_permille / 1000;
  return {
    index: c.index,
    x: s.x + (s.w - w) / 2,
    base: s.base,
    w,
    target,
    built: target * Math.max(0.04, progress),
    grade: g,
    surrendering: c.surrendering,
    stopwatch: c.progress_permille === null,
    depth: s.depth,
  };
}

function farLayers(tier: number, width: number, ground: number, maxH: number): Scene["far"] {
  const r = rng(0x5eed + tier);
  const layers: Scene["far"] = [];
  // Hills always; distant towns from tier 1, a far skyline from tier 2.
  const hills: number[] = [0, ground];
  for (let x = 0; x <= width; x += width / 24) {
    hills.push(x, ground - maxH * (0.08 + 0.06 * Math.sin(x / width * 5 + 1) + r() * 0.03));
  }
  hills.push(width, ground);
  layers.push({ points: hills, color: 0x2b3a3a });
  for (let k = 0; k < Math.min(tier, 2); k++) {
    const pts: number[] = [0, ground];
    const scale = k === 0 ? 0.12 + tier * 0.05 : 0.26;
    let x = 0;
    while (x < width) {
      const bw = width * (0.012 + r() * 0.02);
      const bh = maxH * scale * (0.25 + r() * 0.75) * (r() < 0.2 ? 0.3 : 1);
      pts.push(x, ground - bh, x + bw, ground - bh);
      x += bw + (r() < 0.3 ? width * 0.01 : 0);
    }
    pts.push(width, ground);
    layers.unshift({ points: pts, color: k === 0 ? 0x33405a : 0x2a3350 });
  }
  return layers;
}

/**
 * Lays the world out for a viewport. `hour` is the local time of day;
 * `elapsedSecs` the running session's time (only moves stopwatch sites).
 */
export function layout(w: World, width: number, height: number, hour: number, elapsedSecs = 0): Scene {
  const ground = Math.round(height - Math.max(56, height * 0.14));
  const maxH = ground * 0.66;
  const { sky, glow } = skyAt(hour);
  const siteIndex = w.construction?.index ?? -1;
  const columns = Math.max(w.plots.length, siteIndex + 1);
  const ss = slots(columns, width, ground, maxH);
  const buildings: Building[] = [];
  const rubbles: Rubble[] = [];
  let siteScene: Site | null = null;
  for (const s of ss) {
    if (s.index === siteIndex && w.construction) {
      siteScene = site(w.construction, s, elapsedSecs);
      continue;
    }
    const p = w.plots[s.index];
    if (!p) continue;
    if (p.rubble) rubbles.push(rubble(p, s));
    else buildings.push(building(p, s, 0x1234));
  }
  // Back rows first so the front row draws over them.
  buildings.sort((a, b) => a.depth - b.depth);
  rubbles.sort((a, b) => a.depth - b.depth);
  const lampGap = Math.max(90, width / (6 + w.tier * 3));
  const lamps: number[] = [];
  for (let x = lampGap / 2; x < width; x += lampGap) lamps.push(x);
  return {
    width,
    height,
    ground,
    sky,
    glow,
    buildings,
    rubble: rubbles,
    site: siteScene,
    far: farLayers(w.tier, width, ground, maxH),
    lamps,
  };
}
