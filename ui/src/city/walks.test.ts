import { expect, test } from "bun:test";
import { BLOCK_X, BLOCK_Z, PAVEMENT, lot, plan, rng, type CityPlan } from "./plan";
import { Flow, lanes, populate, spotAt, walkLeft, type Spot } from "./roads";
import { busStop, streetProps } from "./street";
import { ROAD_Z } from "./terrain";
import { BODY, Crowd, type CarShape } from "./walks";
import type { Plot, World } from "../proto";

function town(n: number, tier: number): CityPlan {
  const plots: Plot[] = Array.from({ length: n }, (_, i) => ({ index: i, district: Math.floor(i / 8), grade: 2, damage: 0, rubble: false, seed: i, session_id: i + 1, built_at: 0 }));
  const w: World = { tier, focused_secs: 0, tier_floor_secs: 0, next_tier_secs: null, streak_days: 0, plots, construction: null, history: [] };
  return plan(w);
}

/** Inside a block's pavement ring (out to the kerb), and how far out from the block. */
function onPavement(p: CityPlan, x: number, z: number): boolean {
  return p.blocks.some((b) => {
    const dx = Math.abs(x - b.x) - BLOCK_X / 2;
    const dz = Math.abs(z - b.z) - BLOCK_Z / 2;
    return dx < PAVEMENT + 0.05 && dz < PAVEMENT + 0.05;
  });
}

for (const tier of [0, 2]) {
  test(`tier ${tier} people keep to the pavement, round the furniture, apart, and out of the cars' way`, () => {
    const p = town(60, tier);
    const all = lanes(p.blocks, { z: ROAD_Z, reach: 300 });
    const spots: Spot[] = [];
    for (const b of p.buildings) {
      const l = lot(b.index);
      const s = spotAt(all, l.x + 5, l.z + Math.cos(l.rot) * 8, "lot");
      if (s) spots.push(s);
    }
    for (const b of p.blocks) {
      const at = busStop(b, tier);
      const s = at && spotAt(all, at.x, at.z, "stop", 12);
      if (s) spots.push(s);
    }
    const flow = new Flow(all, tier >= 1, rng(5), spots);
    const r = rng(9);
    const cars = populate(
      flow,
      p.blocks.flatMap((_, i) => Array.from({ length: 3 }, (_, j) => (tier && i % 3 === 0 && j === 0 ? { len: 12, bus: true } : { len: 4.6 }))),
      Array.from({ length: 8 }, () => ({ len: 4.6 })),
      r,
    );
    const crowd = new Crowd(p.blocks, tier, 9, rng(4));
    flow.people = (x, z, rad) => crowd.near(x, z, rad);
    flow.crossers = (x, z, rad) => crowd.crossing(x, z, rad);
    const furniture = p.blocks.flatMap((b) => streetProps(b, tier).flatMap((f) => f.boxes));
    const dt = 1 / 30;
    let crossed = 0;
    const walked = crowd.walkers.map(() => 0);
    for (let k = 0; k < 30 * 400; k++) {
      const t = k * dt;
      flow.step(dt, t);
      const shapes: CarShape[] = cars.flatMap((c) => {
        const at = flow.where(c);
        return at.scale ? [{ x: at.x, z: at.z, heading: at.heading, len: c.len, wid: c.len > 10 ? 2.5 : 2.1, v: c.v, drive: c.mode === "in" || c.mode === "out" ? flow.driveway(c.spot!) : null, committed: !!(c.turn || c.granted || c.held) }] : [];
      });
      const before = crowd.walkers.map((w) => w.mode);
      crowd.step(dt, t, shapes);
      crowd.walkers.forEach((w, i) => {
        walked[i] += w.v * dt;
        if (before[i] !== "cross" && w.mode === "cross") {
          crossed++;
          expect(walkLeft(t), `walker ${i} set off at ${t.toFixed(1)} s`).toBeGreaterThan(0);
        }
      });
      if (k % 10) continue;
      const at = crowd.walkers.map((w) => ({ w, ...crowd.pose(w, 0.2, 0.05) }));
      const faults: string[] = [];
      for (const [i, a] of at.entries()) {
        const where = `walker ${i} (${a.w.mode}) at ${a.x.toFixed(2)},${a.z.toFixed(2)}, ${t.toFixed(1)} s`;
        // On the pavement unless crossing.
        if (a.w.mode !== "cross" && !onPavement(p, a.x, a.z)) faults.push(`${where} off the pavement`);
        // Not through the furniture (a hand's breadth of slack).
        for (const f of furniture) {
          if (a.x > f.x0 - BODY + 0.12 && a.x < f.x1 + BODY - 0.12 && a.z > f.z0 - BODY + 0.12 && a.z < f.z1 + BODY - 0.12) faults.push(`${where} in furniture ${JSON.stringify(f)}`);
        }
        // Never under a car.
        for (const c of shapes) {
          const [fx, fz] = [Math.sin(c.heading), Math.cos(c.heading)];
          const [dx, dz] = [a.x - c.x, a.z - c.z];
          if (Math.abs(dx * fx + dz * fz) < c.len / 2 + 0.1 && Math.abs(dx * fz - dz * fx) < c.wid / 2 + 0.1) faults.push(`${where} under a car at ${c.x.toFixed(1)},${c.z.toFixed(1)}`);
        }
        // Not through each other (people walking in step may brush shoulders).
        for (let j = i + 1; j < at.length; j++) {
          const b = at[j];
          if (Math.hypot(a.x - b.x, a.z - b.z) <= 0.3) faults.push(`${where} and walker ${j} (${b.w.mode}) ${Math.hypot(a.x - b.x, a.z - b.z).toFixed(2)} m apart`);
        }
      }
      expect(faults).toEqual([]);
    }
    if (tier) expect(crossed).toBeGreaterThan(10);
    // Everyone keeps walking, at a walking pace.
    walked.forEach((d, i) => expect(d, `walker ${i}`).toBeGreaterThan(150));
  }, 60_000);
}
