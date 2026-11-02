import { describe as group, expect, test } from "bun:test";
import { BLOCK_X, BLOCK_Z, KINDS, lot, plan, rng, shape, spiral } from "./plan";
import { clock, describe, hm } from "../format";
import type { Plot, World } from "../proto";

function plot(index: number, grade = 2, damage = 0, rubble = false): Plot {
  return { index, district: Math.floor(index / 8), grade, damage, rubble, seed: 1e15 + index * 7919, session_id: index + 1, built_at: 0 };
}

function world(plots: Plot[], extra: Partial<World> = {}): World {
  return { tier: 1, focused_secs: 0, tier_floor_secs: 0, next_tier_secs: null, streak_days: 0, plots, construction: null, history: [], ...extra };
}

group("plan", () => {
  test("is deterministic", () => {
    const w = world(Array.from({ length: 20 }, (_, i) => plot(i, i % 5, i % 3)));
    expect(plan(w)).toEqual(plan(w));
  });

  test("empty land still has one block of empty lots", () => {
    const p = plan(world([]));
    expect(p.buildings).toHaveLength(0);
    expect(p.blocks).toHaveLength(1);
    expect(p.emptyLots).toHaveLength(8);
  });

  test("the construction site replaces its plot", () => {
    const plots = [plot(0), plot(1, 3, 0, true), plot(2)];
    const p = plan(world(plots, { construction: { session_id: 9, index: 1, grade: 2, progress_permille: 500, surrendering: true, seed: 5 } }));
    expect(p.buildings.map((b) => b.index)).toEqual([0, 2]);
    expect(p.site).toMatchObject({ index: 1, progress: 0.5, surrendering: true, stopwatch: false, kind: "apartment" });
    expect(p.emptyLots).toHaveLength(5);
  });

  test("a stopwatch site stays near the top of its grade", () => {
    const p = plan(world([], { construction: { session_id: 9, index: 0, grade: 1, progress_permille: null, surrendering: false, seed: 5 } }), 450);
    expect(p.site!.stopwatch).toBe(true);
    expect(p.site!.progress).toBeGreaterThanOrEqual(0.8);
  });

  test("rubble keeps its grade and damage marks", () => {
    const p = plan(world([plot(0, 3, 0, true), plot(1, 1, 2)]));
    expect(p.buildings[0]).toMatchObject({ rubble: true, kind: "office" });
    expect(p.buildings[1]).toMatchObject({ damage: 2, kind: "shop" });
  });

  test("the city grows by blocks and the bounds hold them all", () => {
    const p = plan(world(Array.from({ length: 41 }, (_, i) => plot(i))));
    expect(p.blocks).toHaveLength(6);
    for (const b of p.buildings) {
      expect(b.x).toBeGreaterThan(p.bounds.minX);
      expect(b.x).toBeLessThan(p.bounds.maxX);
      expect(b.z).toBeGreaterThan(p.bounds.minZ);
      expect(b.z).toBeLessThan(p.bounds.maxZ);
    }
    for (const t of p.trees) {
      const inside = t.x > p.bounds.minX && t.x < p.bounds.maxX && t.z > p.bounds.minZ && t.z < p.bounds.maxZ;
      expect(inside).toBe(false);
    }
  });

  test("more trees with a higher tier", () => {
    expect(plan(world([], { tier: 3 })).trees.length).toBeGreaterThan(plan(world([], { tier: 0 })).trees.length);
  });
});

test("spiral visits each block once, outward from the centre", () => {
  const s = spiral(25);
  expect(new Set(s.map(([x, y]) => `${x},${y}`)).size).toBe(25);
  expect(s.slice(0, 3)).toEqual([[0, 0], [1, 0], [1, 1]]);
  for (const [x, y] of s) expect(Math.max(Math.abs(x), Math.abs(y))).toBeLessThanOrEqual(2);
});

test("lots tile their block and face the road", () => {
  const seen = new Set<string>();
  for (let i = 0; i < 8; i++) {
    const l = lot(i);
    seen.add(`${l.x},${l.z}`);
    expect(Math.abs(l.x)).toBeLessThan(BLOCK_X / 2);
    expect(Math.abs(l.z)).toBeLessThan(BLOCK_Z / 2);
    expect(l.rot).toBe(l.z < 0 ? Math.PI : 0);
  }
  expect(seen.size).toBe(8);
});

test("higher grades are taller and the kinds follow the grade", () => {
  const mean = (g: number) => {
    let sum = 0;
    for (let i = 0; i < 40; i++) sum += shape(g, i * 7919).height;
    return sum / 40;
  };
  for (let g = 1; g <= 4; g++) expect(mean(g)).toBeGreaterThan(mean(g - 1));
  expect(KINDS.map((_, g) => shape(g, 1).kind)).toEqual(KINDS);
  // Footprints fit their lot.
  for (let g = 0; g <= 4; g++) expect(shape(g, 3).w).toBeLessThan(12);
});

test("rng is stable for rounded u64 seeds", () => {
  const seed = JSON.parse("10451216379200822465");
  expect(rng(seed)()).toBe(rng(seed)());
  expect(rng(seed)()).not.toBe(rng(seed + 4096)());
});

test("format", () => {
  expect(clock(59)).toBe("0:59");
  expect(clock(25 * 60)).toBe("25:00");
  expect(clock(3909)).toBe("1:05:09");
  expect(hm(3 * 3600 + 20 * 60)).toBe("3h 20m");
  const w = world([plot(0, 1), plot(1, 4)]);
  expect(describe(w, { ts: 0, kind: "collapsed", cause: "surrendered", session_id: 3, plots: [2, 1], ruined: [] })).toBe(
    "surrendered: plot 3 collapsed, fire spread to plot 2",
  );
  expect(describe(w, { ts: 0, kind: "built", cause: "completed", session_id: 2, plots: [1], ruined: [] })).toBe("built a landmark tower (plot 2)");
});
