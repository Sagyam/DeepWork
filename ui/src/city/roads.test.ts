import { expect, test } from "bun:test";
import { lot, PITCH_X, PITCH_Z, plan, rng, onStreets, type CityPlan } from "./plan";
import { Flow, lanes, populate, signal, spotAt, walkLeft, type Car, type Spot } from "./roads";
import { ROAD_Z } from "./terrain";
import type { Plot, World } from "../proto";

function town(n: number, tier: number): CityPlan {
  const plots: Plot[] = Array.from({ length: n }, (_, i) => ({ index: i, district: Math.floor(i / 8), grade: 2, damage: 0, rubble: false, seed: i, session_id: i + 1, built_at: 0 }));
  const w: World = { tier, focused_secs: 0, tier_floor_secs: 0, next_tier_secs: null, streak_days: 0, plots, construction: null, history: [] };
  return plan(w);
}

const ROAD = { z: ROAD_Z, reach: 400 };

test("every lane keeps right, stays on the asphalt and leads on", () => {
  const p = town(150, 3);
  const all = lanes(p.blocks);
  expect(all.length).toBe(p.blocks.length * 4);
  for (const l of all) {
    expect(l.turns.length, `lane ${l.id}`).toBeGreaterThan(0);
    expect(l.turns.some((t) => t.kind === "right")).toBe(true);
    for (const t of l.turns) {
      for (let s = 0; s <= t.path.length; s += 0.5) {
        const q = t.path.at(s);
        expect(onStreets(p.blocks, q.x, q.z)).toBe(true);
      }
    }
    // The block whose pitch holds the lane is on its right.
    const m = l.path.at(l.path.length / 2);
    const b = p.blocks.find((b) => Math.abs(m.x - b.x) < PITCH_X / 2 && Math.abs(m.z - b.z) < PITCH_Z / 2)!;
    expect(-l.dz * (b.x - m.x) + l.dx * (b.z - m.z)).toBeGreaterThan(0);
  }
  // A town has straight runs and left turns, not only the ring round each block.
  const kinds = new Set(all.flatMap((l) => l.turns.map((t) => t.kind)));
  expect([...kinds].sort()).toEqual(["left", "right", "straight"]);
});

test("the open road runs through town both ways, even past a lone block", () => {
  // A hamlet's one block has Main Street on one side only.
  const hamlet = [{ x: -PITCH_X, z: -PITCH_Z }];
  const all = lanes(hamlet, ROAD);
  const ins = all.filter((l) => l.entry);
  expect(ins.length).toBe(2);
  for (const lane of ins) {
    // Follow straight on from each end: it leaves by the other.
    let l = lane;
    for (let i = 0; i < 10 && !l.exit; i++) l = l.turns.find((t) => t.kind === "straight")!.to;
    expect(l.exit).toBe(true);
    expect(l.dx).toBe(lane.dx);
  }
  // From the road into town and back out.
  const block = all.filter((l) => !l.entry && !l.exit && l.path.length < 70);
  expect(ins.some((l) => l.turns.some((t) => block.includes(t.to)))).toBe(true);
  expect(block.some((l) => l.turns.some((t) => t.to.exit))).toBe(true);
});

test("the walk phase stops every road", () => {
  for (let t = 0; t < 92; t += 0.25) {
    if (walkLeft(t) > 0) {
      expect(signal(t, "a")).toBe("red");
      expect(signal(t, "b")).toBe("red");
    }
    expect(signal(t, "a") === "red" || signal(t, "b") === "red").toBe(true);
  }
});

/** Car outlines from where() and their size, as rotated rectangles. */
function overlap(a: { x: number; z: number; heading: number; len: number; wid: number }, b: typeof a): boolean {
  const axes = [a.heading, a.heading + Math.PI / 2, b.heading, b.heading + Math.PI / 2].map((h) => [Math.sin(h), Math.cos(h)]);
  const corners = (c: typeof a) => {
    const [fx, fz] = [Math.sin(c.heading), Math.cos(c.heading)];
    const [rx, rz] = [fz, -fx];
    return [
      [1, 1],
      [1, -1],
      [-1, 1],
      [-1, -1],
    ].map(([i, j]) => [c.x + (fx * c.len * i) / 2 + (rx * c.wid * j) / 2, c.z + (fz * c.len * i) / 2 + (rz * c.wid * j) / 2]);
  };
  const [ca, cb] = [corners(a), corners(b)];
  for (const [ax, az] of axes) {
    const pa = ca.map(([x, z]) => x * ax + z * az);
    const pb = cb.map(([x, z]) => x * ax + z * az);
    if (Math.max(...pa) < Math.min(...pb) || Math.max(...pb) < Math.min(...pa)) return false;
  }
  return true;
}

for (const tier of [0, 2]) {
  test(`tier ${tier}: trips, no crashes, ${tier ? "stops at red" : "gives way"}, no gridlock`, () => {
    const p = town(150, tier);
    const all = lanes(p.blocks, ROAD);
    const spots: Spot[] = [];
    for (const b of p.buildings) {
      const l = lot(b.index);
      spots.push(spotAt(all, l.x + 5, l.z + Math.cos(l.rot) * 8, "lot")!);
    }
    expect(spots.every(Boolean)).toBe(true);
    const flow = new Flow(all, tier >= 1, rng(7), spots.filter(Boolean));
    const r = rng(3);
    const local = p.blocks.flatMap((_, i) => Array.from({ length: 4 }, (_, j) => (i % 5 === 0 && j === 0 ? { len: 12, bus: true } : { len: 4.6 })));
    const through = Array.from({ length: 16 }, () => ({ len: r() < 0.15 ? 7.6 : 4.6 }));
    const cars = populate(flow, local, through, r);
    const dt = 1 / 30;
    const moved = cars.map(() => 0);
    let parked = 0;
    let left = 0;
    for (let k = 0; k < 30 * 600; k++) {
      const t = k * dt;
      const before = cars.map((c) => ({ turn: c.turn, mode: c.mode }));
      flow.step(dt, t);
      cars.forEach((c, i) => {
        moved[i] += c.v * dt;
        if (before[i].mode === "drive" && c.mode === "in") parked++;
        if (before[i].mode === "drive" && c.mode === "away") left++;
        // Nobody enters a lit crossing on red (amber they may, if too close to stop):
        // a car over the line as amber ends reaches the crossing a moment later.
        if (flow.signals && c.turn && !before[i].turn && c.turn.from.lit) expect(signal(t - 1, c.turn.from.phase)).not.toBe("red");
      });
      if (k % 10) continue;
      const shown = cars
        .map((c: Car, i) => ({ c, i, ...flow.where(c), wid: c.len > 10 ? 2.5 : 2.1 }))
        .filter((s) => s.scale === 1)
        .map((s) => ({ ...s, len: s.c.len - 0.3, wid: s.wid - 0.3 }));
      for (let i = 0; i < shown.length; i++) {
        for (let j = i + 1; j < shown.length; j++) {
          if (Math.abs(shown[i].x - shown[j].x) > 14 || Math.abs(shown[i].z - shown[j].z) > 14) continue;
          expect(overlap(shown[i], shown[j]), `cars ${shown[i].i} (${shown[i].c.mode}) and ${shown[j].i} (${shown[j].c.mode}) at ${t.toFixed(1)} s`).toBe(false);
        }
      }
    }
    // Ten minutes: cars pulled into lots and left town, and nothing jammed.
    expect(parked).toBeGreaterThan(20);
    expect(left).toBeGreaterThan(10);
    const stuck = cars.filter((c, i) => c.mode === "drive" && moved[i] < 100);
    expect(stuck.length, `stuck: ${stuck.map((c) => `${c.lane.id}@${c.s.toFixed(1)}`).join(" ")}`).toBe(0);
  });
}
