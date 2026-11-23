import { expect, test } from "bun:test";
import { zoneCity } from "./live";

test("the time zone names a city to find", () => {
  expect(zoneCity("Asia/Kathmandu")).toBe("Kathmandu");
  expect(zoneCity("America/New_York")).toBe("New York");
  expect(zoneCity("America/Argentina/Buenos_Aires")).toBe("Buenos Aires");
  expect(zoneCity("UTC")).toBeNull();
  expect(zoneCity("Etc/GMT+5")).toBeNull();
});
