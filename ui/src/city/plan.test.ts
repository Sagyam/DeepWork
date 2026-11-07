import { describe as group, expect, test } from "bun:test";
import { BLOCK_X, BLOCK_Z, KINDS, LOT, PAVEMENT, PITCH_X, PITCH_Z, PUBLIC, ROAD, STYLES, blockLoop, cells, onStreets, districtCell, isPark, lookOf, lot, plan, rng, shape, spiral } from "./plan";
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
    // Six districts, and the two parks among them.
    expect(p.blocks).toHaveLength(8);
    expect(p.parks.map((k) => k.kind)).toEqual(["plaza", "park"]);
    for (const b of p.buildings) {
      expect(b.x).toBeGreaterThan(p.bounds.minX);
      expect(b.x).toBeLessThan(p.bounds.maxX);
      expect(b.z).toBeGreaterThan(p.bounds.minZ);
      expect(b.z).toBeLessThan(p.bounds.maxZ);
    }
    for (const t of p.trees) {
      const onBlock = p.blocks.some((b) => Math.abs(t.x - b.x) < PITCH_X / 2 && Math.abs(t.z - b.z) < PITCH_Z / 2);
      expect(onBlock).toBe(false);
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

test("every style turns up, and buildings stay on their lots", () => {
  for (const [g, kind] of KINDS.entries()) {
    const seen = new Set<string>();
    for (let i = 0; i < 400; i++) seen.add(shape(g, i * 7919 + 1).style);
    expect([...seen].sort()).toEqual(STYLES[kind].map(([s]) => s).sort());
  }
  const p = plan(world(Array.from({ length: 64 }, (_, i) => plot(i, i % 5))));
  for (const b of p.buildings) {
    const l = lot(b.index);
    // Set back from the street, but the footprint never leaves the lot.
    const front = l.z < Math.round(l.z / PITCH_Z) * PITCH_Z ? -1 : 1;
    expect(Math.abs(b.x - l.x)).toBeLessThan(1e-9);
    expect(Math.abs(b.z - l.z) + b.d / 2).toBeLessThanOrEqual(LOT / 2);
    expect(b.yard).toBeGreaterThanOrEqual(0);
    expect(Math.sign(b.z - l.z) || front).toBe(front);
  }
});

test("blocks grow outward as a disc, every fourth cell a park", () => {
  const c = cells(60);
  expect(c[0]).toEqual([0, 0]);
  expect(new Set(c.map(([x, y]) => `${x},${y}`)).size).toBe(60);
  const dist = c.map(([x, y]) => Math.hypot(x * PITCH_X, y * PITCH_Z));
  for (let i = 1; i < dist.length; i++) expect(dist[i]).toBeGreaterThanOrEqual(dist[i - 1] - 1e-9);
  // Districts take the cells that are not parks, in order, once each.
  const used = Array.from({ length: 40 }, (_, d) => districtCell(d));
  expect(used.some(isPark)).toBe(false);
  expect(new Set(used).size).toBe(40);
  for (let i = 0; i < used[39]; i++) expect(isPark(i) || used.includes(i)).toBe(true);
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
  const w = world([plot(0, 1), { ...plot(1, 4), name: "Hart Tower" }]);
  expect(describe(w, { ts: 0, kind: "collapsed", cause: "surrendered", session_id: 3, plots: [2, 1, 0], ruined: [1] })).toBe(
    "surrendered: fire spread to Hart Tower and plot 1; Hart Tower in ruins",
  );
  expect(describe(w, { ts: 0, kind: "built", cause: "completed", session_id: 2, plots: [1], ruined: [] })).toBe("finished Hart Tower");
});

group("progression v2", () => {
  test("a blueprint picks the look and the model", () => {
    const p = plan(world([{ ...plot(0, 0), kind: "cottage", design: "c4" }, { ...plot(1, 1), kind: "workshop", design: "s4" }]));
    expect(p.buildings[0]).toMatchObject({ kind: "cottage", style: "aframe", model: "c4" });
    expect(p.buildings[1]).toMatchObject({ kind: "shop", style: "factory", model: "s4", floors: 1 });
  });

  test("public buildings get stand-ins", () => {
    const p = plan(world([{ ...plot(7, 0), kind: "water", design: null }, { ...plot(12, 1), kind: "square", design: null }]));
    expect(p.buildings.map((b) => b.style)).toEqual(["water", "square"]);
  });

  test("lots fill out of order; the gaps stay empty lots", () => {
    const p = plan(world([plot(0), { ...plot(7), kind: "water" }]));
    expect(p.buildings.map((b) => b.index)).toEqual([0, 7]);
    expect(p.emptyLots).toHaveLength(6);
    expect(p.blocks).toHaveLength(1);
  });

  test("paused sites stand half built; the session's own site is live", () => {
    const sites = [
      { index: 3, lot: "hamlet-homes-4", need: "hamlet-homes", name: "The Sato house", kind: "cottage", design: "c1", done_secs: 1800, build_secs: 3600, active: false, seed: 9 },
      { index: 4, lot: "hamlet-shops-1", need: "hamlet-shops", name: "Hart's Bakery", kind: "shop", design: "s1", done_secs: 600, build_secs: 5400, active: true, seed: 8 },
    ];
    const construction = { session_id: 9, index: 4, grade: 1, progress_permille: 300, surrendering: false, seed: 8, kind: "shop", design: "s1" };
    const p = plan(world([plot(0)], { sites, construction }));
    expect(p.paused.map((s) => [s.index, s.progress, s.model])).toEqual([[3, 0.5, "c1"]]);
    expect(p.site).toMatchObject({ index: 4, progress: 0.3, model: "s1" });
    expect(p.emptyLots.map((l) => l.seed)).not.toContain(3 * 2654435761);
  });

  test("shiny and ruined buildings", () => {
    const p = plan(world([{ ...plot(0), shiny: true }, { ...plot(1), damage: 3, rubble: true }]));
    expect(p.buildings[0].shiny).toBe(true);
    expect(p.buildings[1]).toMatchObject({ rubble: true, damage: 2 });
  });
});

test("traffic loops keep the block on the right and stay in their lane", () => {
  const lane = PAVEMENT + (ROAD - 2 * PAVEMENT) / 4;
  const hx = BLOCK_X / 2 + lane;
  const hz = BLOCK_Z / 2 + lane;
  const loop = blockLoop(PITCH_X, 0, hx, hz, 3.5);
  expect(loop.length).toBeGreaterThan(2 * (hx + hz));
  for (let d = 0; d < loop.length; d += 1.7) {
    const p = loop.at(d);
    // Inside the lane: no further out than the loop, never onto the pavement.
    expect(Math.abs(p.x - PITCH_X)).toBeLessThanOrEqual(hx + 1e-6);
    expect(Math.abs(p.z)).toBeLessThanOrEqual(hz + 1e-6);
    expect(Math.max(Math.abs(p.x - PITCH_X) - BLOCK_X / 2, Math.abs(p.z) - BLOCK_Z / 2)).toBeGreaterThan(PAVEMENT);
    // The block centre is on the right of the direction of travel.
    const f = { x: Math.sin(p.heading), z: Math.cos(p.heading) };
    const right = { x: -f.z, z: f.x };
    expect(right.x * (PITCH_X - p.x) + right.z * (0 - p.z)).toBeGreaterThan(0);
  }
  // Wraps around.
  expect(loop.at(loop.length + 5).x).toBeCloseTo(loop.at(5).x, 6);
});

test("the City's power and water get their own models; the public buildings have theirs", () => {
  expect(lookOf(null, "power", "hamlet-power")?.model).toBe("p1");
  expect(lookOf(null, "power", "city-power")?.model).toBe("p2");
  expect(lookOf(null, "water", "town-water")?.model).toBeUndefined();
  expect(lookOf(null, "water", "city-water")?.model).toBe("w2");
  // A blueprint wins over the need.
  expect(lookOf("s4", "power", "city-power")?.model).toBe("s4");
  expect([PUBLIC.hospital.model, PUBLIC.police.model, PUBLIC.library.model]).toEqual(["h2", "e2", "e3"]);
  // A built City power station is drawn as P2.
  const p = plan(world([{ ...plot(0, 1), kind: "power", need: "city-power" }]), 0);
  expect(p.buildings[0].model).toBe("p2");
  expect(p.buildings[0].style).toBe("powerstation");
});

test("every look the plan can give a building has a model", async () => {
  // real.ts reads the page's URL at load; bun has none.
  (globalThis as unknown as { location: object }).location ??= { search: "" };
  const { DEFS } = await import("./real");
  const { DESIGNS, NEED_LOOKS } = await import("./plan");
  const drawn = (kind: string, style: string) => Object.values(DEFS).some((d) => d.kind === kind && d.style === style);
  const built = new Set(["water", "square", "park"]);
  for (const kind of KINDS) for (const [style] of STYLES[kind]) expect(drawn(kind, style), `${kind} ${style}`).toBe(true);
  for (const [id, look] of Object.entries(DESIGNS)) expect(DEFS[id]?.style, id).toBe(look.style);
  for (const look of [...Object.values(PUBLIC), ...Object.values(NEED_LOOKS)]) {
    if (built.has(look.style)) continue;
    expect(look.model && DEFS[look.model]?.style, look.style).toBe(look.style);
  }
});

test("every road strip counts as street, and the grass past it does not", () => {
  const p = plan(world(Array.from({ length: 40 }, (_, i) => plot(i))));
  const strips: [number, number][] = [];
  for (const b of p.blocks) {
    // From the block's edge to the pitch's: pavement, lanes and the centre line.
    for (let t = 0; t <= 1; t += 0.05) {
      for (let d = BLOCK_X / 2; d <= PITCH_X / 2; d += 0.5) strips.push([b.x + d, b.z + (t - 0.5) * PITCH_Z], [b.x - d, b.z + (t - 0.5) * PITCH_Z]);
      for (let d = BLOCK_Z / 2; d <= PITCH_Z / 2; d += 0.5) strips.push([b.x + (t - 0.5) * PITCH_X, b.z + d], [b.x + (t - 0.5) * PITCH_X, b.z - d]);
    }
  }
  for (const [x, z] of strips) expect(onStreets(p.blocks, x, z), `${x},${z}`).toBe(true);
  const { maxX, minZ } = p.bounds;
  expect(onStreets(p.blocks, maxX + 3, (minZ + p.bounds.maxZ) / 2, 1.5)).toBe(false);
  expect(onStreets(p.blocks, (p.bounds.minX + maxX) / 2, minZ - 3, 1.5)).toBe(false);
});
