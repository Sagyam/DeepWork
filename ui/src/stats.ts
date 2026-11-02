// Stats over past sessions (`Request::History`). Pure, so it is unit tested;
// days are local calendar days, like the daemon's streaks and routines.
import type { Finished } from "./proto";

export interface Day {
  /** Local midnight, unix seconds. */
  start: number;
  /** Focused time of completed sessions that ended this day. */
  focusedSecs: number;
  completed: number;
  surrendered: number;
}

export interface Stats {
  /** Oldest first, ending today. */
  days: Day[];
  todaySecs: number;
  /** Since Monday 00:00. */
  weekSecs: number;
  /** Over all `days`. */
  totalSecs: number;
  completed: number;
  surrendered: number;
  /** Longest completed session. */
  longestSecs: number;
  /** Completed sessions started by a routine. */
  fromRoutines: number;
}

/** Local midnight `back` days before the day of `now` (unix seconds). */
export function midnight(now: number, back = 0): number {
  const d = new Date(now * 1000);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() - back).getTime() / 1000;
}

/** Monday 00:00 of the week of `now`. */
export function weekStart(now: number): number {
  const weekday = (new Date(now * 1000).getDay() + 6) % 7;
  return midnight(now, weekday);
}

export function summarize(sessions: Finished[], now: number, dayCount: number): Stats {
  const days: Day[] = Array.from({ length: dayCount }, (_, i) => ({
    start: midnight(now, dayCount - 1 - i),
    focusedSecs: 0,
    completed: 0,
    surrendered: 0,
  }));
  const week = weekStart(now);
  const stats: Stats = { days, todaySecs: 0, weekSecs: 0, totalSecs: 0, completed: 0, surrendered: 0, longestSecs: 0, fromRoutines: 0 };
  for (const f of sessions) {
    // Days can be 23 or 25 hours long, so search instead of dividing.
    let i = days.length - 1;
    while (i >= 0 && days[i].start > f.ended_at) i--;
    if (i < 0) continue;
    const day = days[i];
    const s = f.session;
    if (s.state === "surrendered") {
      day.surrendered++;
      stats.surrendered++;
    } else if (s.state === "completed") {
      day.completed++;
      day.focusedSecs += s.elapsed_secs;
      stats.completed++;
      stats.totalSecs += s.elapsed_secs;
      stats.longestSecs = Math.max(stats.longestSecs, s.elapsed_secs);
      if (s.routine) stats.fromRoutines++;
      if (f.ended_at >= week) stats.weekSecs += s.elapsed_secs;
    }
  }
  stats.todaySecs = days.length ? days[days.length - 1].focusedSecs : 0;
  return stats;
}
