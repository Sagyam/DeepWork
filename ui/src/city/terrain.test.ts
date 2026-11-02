import { expect, test } from "bun:test";
import { LAKE, RADIUS, ROAD_Z, WATER, riverX, terrain } from "./terrain";

const bounds = { minX: -80, maxX: 80, minZ: -50, maxZ: 50 };
const land = terrain(bounds);

test("the city stands on flat, dry ground", () => {
  for (let x = bounds.minX; x <= bounds.maxX; x += 7) {
    for (let z = bounds.minZ; z <= bounds.maxZ; z += 7) expect(land.height(x, z)).toBe(0);
  }
});

test("the river and the lake hold water; their surroundings are dry", () => {
  for (let z = -2000; z <= 2000; z += 37) {
    expect(land.height(riverX(z), z)).toBeLessThan(WATER - 1);
    expect(land.height(riverX(z) + 40, z)).toBeGreaterThan(WATER + 1);
  }
  expect(land.height(LAKE.x, LAKE.z)).toBeLessThan(WATER - 1);
});

test("the road out of town is level across its width and climbs into the hills", () => {
  let climb = 0;
  for (let x = bounds.maxX; x < RADIUS * 0.9; x += 11) {
    if (Math.abs(x - land.bridge.x) > 60) {
      expect(Math.abs(land.height(x, ROAD_Z - 4) - land.height(x, ROAD_Z + 4))).toBeLessThan(0.05);
    }
    climb = Math.max(climb, land.height(x, ROAD_Z));
  }
  expect(climb).toBeGreaterThan(20);
  expect(land.height(land.bridge.x, ROAD_Z)).toBeLessThan(WATER);
});

test("hills beyond town and mountains on the horizon", () => {
  let hill = 0;
  let peak = 0;
  for (let a = 0; a < Math.PI * 2; a += 0.05) {
    hill = Math.max(hill, land.height(Math.cos(a) * 300, Math.sin(a) * 300 + 150));
    peak = Math.max(peak, land.height(Math.cos(a) * 2000, Math.sin(a) * 2000));
  }
  expect(hill).toBeGreaterThan(8);
  expect(peak).toBeGreaterThan(250);
});

test("a bigger city flattens more ground but keeps the same river", () => {
  const big = terrain({ minX: -200, maxX: 200, minZ: -120, maxZ: 120 });
  expect(big.height(150, 100)).toBe(0);
  expect(big.bridge).toEqual(land.bridge);
});
