import { expect, test } from "bun:test";
import { unread } from "./letters";
import type { Letter } from "./proto";

const letter = (ts: number): Letter => ({ ts, kind: "street", from: "The Hart family", address: "9 Main Street", text: "Thank you.", lot: null });

test("a first run has nothing unread; after that, letters past the last read", () => {
  const ls = [letter(10), letter(20), letter(30)];
  expect(unread(ls, null)).toBe(0);
  expect(unread(ls, 20)).toBe(1);
  expect(unread(ls, 0)).toBe(3);
});
