import { expect, test } from "bun:test";
import { QUALITIES, QUALITY } from "./quality";

test("every preset keeps MSAA for alpha to coverage", () => {
  for (const q of Object.values(QUALITY)) expect(q.msaa).toBeGreaterThanOrEqual(2);
});

test("presets get cheaper from high to low", () => {
  const [low, medium, high] = QUALITIES.map((q) => QUALITY[q.key]);
  expect(low.scale).toBeLessThan(medium.scale);
  expect(medium.scale).toBeLessThanOrEqual(high.scale);
  expect(low.shadow).toBeLessThanOrEqual(medium.shadow);
});
