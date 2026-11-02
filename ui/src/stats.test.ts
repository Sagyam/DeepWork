import { expect, test } from "bun:test";
import { dayName } from "./format";
import { midnight, summarize, weekStart } from "./stats";
import type { Finished, SessionState } from "./proto";

const at = (d: number, h: number, m = 0) => new Date(2026, 10, d, h, m).getTime() / 1000;

function ended(end: number, mins: number, state: SessionState = "completed", routine: string | null = null): Finished {
  const s = mins * 60;
  return {
    ended_at: end,
    session: {
      id: end, kind: { type: "countdown", secs: s }, profile: "deep", routine, state, started_at: end - s,
      elapsed_secs: s, remaining_secs: 0, stop_locked_secs: 0, surrender_remaining_secs: null,
      distracted_secs: 0, escalation_stage: 0,
    },
  };
}

test("days are local midnights, weeks start on Monday", () => {
  expect(midnight(at(4, 15))).toBe(at(4, 0));
  expect(midnight(at(4, 0, 30), 3)).toBe(at(1, 0));
  expect(weekStart(at(8, 23))).toBe(at(2, 0)); // Sunday
  expect(weekStart(at(2, 0))).toBe(at(2, 0));
});

test("buckets sessions by the local day they ended", () => {
  const now = at(4, 18); // Wednesday
  const st = summarize(
    [
      ended(at(4, 10), 50, "completed", "morning"),
      ended(at(4, 0, 10), 90), // just after midnight: today
      ended(at(3, 23, 50), 25),
      ended(at(3, 12), 40, "surrendered"),
      ended(at(1, 12), 180), // Sunday: in the window, not this week
      ended(at(20, 12, 0) - 40 * 86400, 25), // before the window
    ],
    now,
    7,
  );
  expect(st.days.map((d) => d.focusedSecs / 60)).toEqual([0, 0, 0, 180, 0, 25, 140]);
  expect(st.days[5].surrendered).toBe(1);
  expect(st.todaySecs).toBe(140 * 60);
  expect(st.weekSecs).toBe(165 * 60);
  expect(st.totalSecs).toBe(345 * 60);
  expect([st.completed, st.surrendered, st.fromRoutines]).toEqual([4, 1, 1]);
  expect(st.longestSecs).toBe(180 * 60);
});

test("day names", () => {
  const now = at(4, 18);
  expect([at(4, 9), at(3, 23), at(1, 12), at(5, 9), at(20, 9) - 30 * 86400].map((t) => dayName(t, now))).toEqual(["Today", "Yesterday", "Sun", "Tomorrow", "21 Oct"]);
});
