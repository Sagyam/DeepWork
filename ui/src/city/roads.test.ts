import { expect, test } from "bun:test";
import { PITCH_X, PITCH_Z, plan, rng, onStreets, type CityPlan } from "./plan";
import { Flow, lanes, signal } from "./roads";
import type { Plot, World } from "../proto";

function town(n: number, tier: number): CityPlan {
  const plots: Plot[] = Array.from({ length: n }, (_, i) => ({ index: i, district: Math.floor(i / 8), grade: 2, damage: 0, rubble: false, seed: i, session_id: i + 1, built_at: 0 }));
  const w: World = { tier, focused_secs: 0, tier_floor_secs: 0, next_tier_secs: null, streak_days: 0, plots, construction: null, history: [] };
  return plan(w);
}

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

for (const tier of [0, 2]) {
  test(`tier ${tier} traffic roams, keeps its distance and ${tier ? "stops at red" : "gives way"}`, () => {
    const p = town(150, tier);
    const flow = new Flow(lanes(p.blocks), tier >= 1, rng(7));
    const r = rng(3);
    flow.lanes.forEach((l, i) => {
      if (i % 2 === 0) flow.add(l, l.path.length * 0.3, r() < 0.1 ? 12 : 4.6, 7 + r() * 3);
    });
    const dt = 1 / 30;
    const start = flow.cars.map((c) => c.lane);
    const travelled = flow.cars.map(() => 0);
    for (let k = 0; k < 30 * 600; k++) {
      const t = k * dt;
      const before = flow.cars.map((c) => ({ turn: c.turn, s: c.s }));
      flow.step(dt, t);
      flow.cars.forEach((c, i) => {
        travelled[i] += c.v * dt;
        // Nobody enters a crossing on red (amber they may, if too close to stop).
        if (flow.signals && c.turn && !before[i].turn) expect(signal(t, c.turn.from.phase)).not.toBe("red");
      });
      if (k % 15) continue;
      const at = flow.cars.map((c) => flow.where(c));
      for (let i = 0; i < at.length; i++) {
        for (let j = i + 1; j < at.length; j++) {
          const d = Math.hypot(at[i].x - at[j].x, at[i].z - at[j].z);
          expect(d, `cars ${i} and ${j} at ${t.toFixed(1)} s`).toBeGreaterThan(2.5);
        }
      }
    }
    // Ten minutes: every car has left its first lane and kept moving.
    flow.cars.forEach((c, i) => {
      expect(c.driven, `car ${i}`).toBeGreaterThan(5);
      expect(travelled[i]).toBeGreaterThan(600);
      expect(c.lane !== start[i] || c.driven > 0).toBe(true);
    });
  });
}
