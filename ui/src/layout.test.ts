import { describe as group, expect, test } from "bun:test";
import { layout, rng, skyAt, slots } from "./layout";
import { clock, describe, hm } from "./format";
import type { Plot, World } from "./proto";

function plot(index: number, grade = 2, damage = 0, rubble = false): Plot {
  return { index, district: Math.floor(index / 8), grade, damage, rubble, seed: 1e15 + index * 7919, session_id: index + 1, built_at: 0 };
}

function world(plots: Plot[], extra: Partial<World> = {}): World {
  return { tier: 1, focused_secs: 0, tier_floor_secs: 0, next_tier_secs: null, streak_days: 0, plots, construction: null, history: [], ...extra };
}

group("layout", () => {
  test("is deterministic", () => {
    const w = world(Array.from({ length: 12 }, (_, i) => plot(i, i % 5, i % 3)));
    expect(layout(w, 1100, 720, 21)).toEqual(layout(w, 1100, 720, 21));
  });

  test("empty land has no buildings", () => {
    const s = layout(world([]), 800, 600, 12);
    expect(s.buildings).toHaveLength(0);
    expect(s.site).toBeNull();
    expect(s.far.length).toBeGreaterThan(0);
  });

  test("rubble and the construction site take their plots", () => {
    const plots = [plot(0), plot(1, 3, 0, true), plot(2)];
    const s = layout(world(plots, { construction: { session_id: 9, index: 3, grade: 1, progress_permille: 500, surrendering: false, seed: 5 } }), 1000, 700, 12);
    expect(s.buildings.map((b) => b.index).sort()).toEqual([0, 2]);
    expect(s.rubble.map((r) => r.index)).toEqual([1]);
    expect(s.site?.index).toBe(3);
    expect(s.site!.built).toBeCloseTo(s.site!.target / 2);
  });

  test("higher grades are taller", () => {
    const mean = (g: number) => {
      const s = layout(world(Array.from({ length: 16 }, (_, i) => plot(i, g))), 1200, 800, 12);
      return s.buildings.reduce((a, b) => a + b.h, 0) / s.buildings.length;
    };
    for (let g = 1; g <= 4; g++) expect(mean(g)).toBeGreaterThan(mean(g - 1));
  });

  test("buildings stay inside the window and their slots", () => {
    const s = layout(world(Array.from({ length: 30 }, (_, i) => plot(i, 4))), 1100, 720, 12);
    for (const b of s.buildings) {
      expect(b.x).toBeGreaterThanOrEqual(0);
      expect(b.x + b.w).toBeLessThanOrEqual(1100);
      expect(b.base - b.h).toBeGreaterThan(0);
    }
  });

  test("damage breaks windows and cuts the top", () => {
    const s = layout(world([plot(0, 3, 0), plot(1, 3, 2)]), 600, 600, 22);
    const [ok, hurt] = [s.buildings.find((b) => b.index === 0)!, s.buildings.find((b) => b.index === 1)!];
    expect(ok.windows.some((w) => w.broken)).toBe(false);
    expect(hurt.windows.some((w) => w.broken)).toBe(true);
    expect(hurt.notch).toBeGreaterThan(0);
    expect(hurt.cracks.length).toBe(4);
  });
});

group("slots", () => {
  test("districts get a gap", () => {
    const ss = slots(9, 1000, 600, 400);
    const step = ss[1].x - ss[0].x;
    expect(ss[8].x - ss[7].x).toBeGreaterThan(step * 1.5);
  });

  test("a big city moves older districts back, newest in front", () => {
    const ss = slots(120, 1100, 600, 400);
    expect(ss).toHaveLength(120);
    const depths = new Set(ss.map((s) => s.depth));
    expect(depths.size).toBeGreaterThan(1);
    expect(ss[119].depth).toBe(1);
    expect(ss[0].depth).toBeLessThan(1);
    for (const s of ss) {
      expect(s.x).toBeGreaterThanOrEqual(0);
      expect(s.x + s.w).toBeLessThanOrEqual(1100);
    }
  });

  test("one row while it fits", () => {
    expect(new Set(slots(16, 1100, 600, 400).map((s) => s.depth))).toEqual(new Set([1]));
  });
});

test("sky glows at night only", () => {
  expect(skyAt(0).glow).toBe(1);
  expect(skyAt(12).glow).toBe(0);
  expect(skyAt(19).glow).toBeGreaterThan(0);
  expect(skyAt(23.99).sky).toHaveLength(3);
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
  expect(describe(w, { ts: 0, kind: "damaged", cause: "clock_jump", session_id: null, plots: [0], ruined: [0] })).toBe(
    "wall clock jump damaged plot 1; plot 1 fell into rubble",
  );
});
