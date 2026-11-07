import { expect, test } from "bun:test";
import { weatherOn } from "./weather";

test("weather is fixed per day and mostly fair", () => {
  expect(weatherOn(20000)).toEqual(weatherOn(20000));
  const kinds = Array.from({ length: 2000 }, (_, d) => weatherOn(19000 + d).kind);
  const share = (k: string) => kinds.filter((x) => x === k).length / kinds.length;
  expect(share("clear")).toBeGreaterThan(0.45);
  expect(share("rain")).toBeGreaterThan(0.04);
  expect(share("rain")).toBeLessThan(0.16);
});
