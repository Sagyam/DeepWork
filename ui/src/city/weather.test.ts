import { expect, test } from "bun:test";
import { fromReport, weatherOn } from "./weather";

const day = (iso: string) => Math.floor(Date.parse(iso) / 86_400_000);
const year = (start: string, n: number, south = false) => Array.from({ length: n }, (_, d) => weatherOn(day(start) + d, south).kind);
const share = (kinds: string[], k: string) => kinds.filter((x) => x === k).length / kinds.length;

test("weather is fixed per day and mostly fair", () => {
  expect(weatherOn(20000)).toEqual(weatherOn(20000));
  const kinds = Array.from({ length: 2000 }, (_, d) => weatherOn(19000 + d).kind);
  expect(share(kinds, "clear") + share(kinds, "fair")).toBeGreaterThan(0.45);
  expect(share(kinds, "rain")).toBeGreaterThan(0.03);
  expect(share(kinds, "rain")).toBeLessThan(0.16);
  expect(new Set(kinds).size).toBe(9);
});

test("snow falls in winter, storms in summer", () => {
  // Five Julys and five Januarys.
  const july = [2021, 2022, 2023, 2024, 2025].flatMap((y) => year(`${y}-07-01`, 31));
  const jan = [2021, 2022, 2023, 2024, 2025].flatMap((y) => year(`${y}-01-01`, 31));
  expect(share(july, "snow")).toBe(0);
  expect(share(jan, "snow")).toBeGreaterThan(0.1);
  expect(share(jan, "storm")).toBe(0);
  expect(share(july, "storm")).toBeGreaterThan(0);
  // The southern hemisphere's July is winter.
  const southJuly = [2021, 2022, 2023, 2024, 2025].flatMap((y) => year(`${y}-07-01`, 31, true));
  expect(share(southJuly, "snow")).toBeGreaterThan(0.1);
});

test("live reports map to the right weather", () => {
  expect(fromReport({ weather_code: 0 }).kind).toBe("clear");
  expect(fromReport({ weather_code: 2, cloud_cover: 60 }).cloud).toBeCloseTo(0.6);
  expect(fromReport({ weather_code: 45 }).kind).toBe("fog");
  expect(fromReport({ weather_code: 53 }).kind).toBe("drizzle");
  expect(fromReport({ weather_code: 65 }).rain).toBe(1);
  expect(fromReport({ weather_code: 81 }).kind).toBe("rain");
  expect(fromReport({ weather_code: 75 }).snow).toBe(1);
  expect(fromReport({ weather_code: 96 }).lightning).toBe(true);
  // Old snow under a clear sky still lies; none, none.
  expect(fromReport({ weather_code: 0, snow_depth: 0.1 }).cover).toBe(1);
  expect(fromReport({ weather_code: 0, snow_depth: 0 }).cover).toBe(0);
  expect(fromReport({ weather_code: 3, visibility: 500 }).fog).toBeGreaterThan(0.8);
  expect(fromReport({ weather_code: 61, wind_speed_10m: 100 }).wind).toBe(1);
});
