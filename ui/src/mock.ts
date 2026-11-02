// Canned daemon for developing the renderer in a browser: `bun run dev`, then
// open http://localhost:5173/?mock=city (empty, hamlet, city, metropolis,
// session, stopwatch, surrender, ruins). `&hour=22` fixes the time of day.
// Each load replays the history (its timestamps are relative to now). In the
// console, `city.demo("collapse" | "build" | "damage", plot?)` plays one
// transition (the tallest building if no plot is given).
import type { Construction, Plot, Request, Response, SessionInfo, Status, World, WorldEvent } from "./proto";
import { SURRENDER_PHRASE } from "./proto";

const scenario = new URLSearchParams(location.search).get("mock") ?? "city";
const t0 = Math.floor(Date.now() / 1000);

function rand(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function plots(n: number, seed: number, grades: number[], damage = 0.15): Plot[] {
  const r = rand(seed);
  return Array.from({ length: n }, (_, index) => {
    const x = r();
    return {
      index,
      district: Math.floor(index / 8),
      grade: grades[Math.floor(r() * grades.length)],
      damage: x < damage ? 1 + Math.floor(r() * 2) : 0,
      rubble: x > 1 - damage / 3,
      seed: Math.floor(r() * 2 ** 52),
      session_id: index + 1,
      built_at: t0 - (n - index) * 7200,
    };
  });
}

const history: WorldEvent[] = [
  { ts: t0 - 86400, kind: "built", cause: "completed", session_id: 1, plots: [0], ruined: [] },
  { ts: t0 - 50000, kind: "quake", cause: "tamper", session_id: null, plots: [1, 2, 3], ruined: [] },
  { ts: t0 - 20000, kind: "collapsed", cause: "surrendered", session_id: 4, plots: [4, 2, 3], ruined: [3] },
  { ts: t0 - 3000, kind: "repaired", cause: "completed", session_id: 5, plots: [1, 2], ruined: [] },
  { ts: t0 - 3000, kind: "built", cause: "completed", session_id: 5, plots: [4], ruined: [] },
];

function session(kind: SessionInfo["kind"], elapsed: number, surrendering = false): SessionInfo {
  const secs = kind.type === "countdown" ? kind.secs : null;
  return {
    id: 99,
    kind,
    profile: "deep",
    routine: null,
    state: surrendering ? "surrendering" : "active",
    started_at: t0 - elapsed,
    elapsed_secs: elapsed,
    remaining_secs: secs === null ? null : secs - elapsed,
    stop_locked_secs: Math.max(0, 600 - elapsed),
    surrender_remaining_secs: surrendering ? 431 : null,
    distracted_secs: 735,
    escalation_stage: 1,
  };
}

function build(): { world: World; status: Status } {
  const status: Status = {
    session: null,
    profiles: ["deep", "trial"],
    dry_run: false,
    upcoming: [
      { routine: "morning", profile: "deep", starts_at: t0 + 5400, ends_at: t0 + 5400 + 5400, starts_in_secs: 5400, skipped: false },
    ],
    heads_up_secs: 300,
    skip_tokens_left: 2,
    last: null,
    nudge: { level: 2, idle_secs: 4200 },
  };
  const world: World = {
    tier: 2,
    focused_secs: 71 * 3600,
    tier_floor_secs: 50 * 3600,
    next_tier_secs: 200 * 3600,
    streak_days: 4,
    plots: plots(30, 7, [0, 1, 1, 2, 2, 3, 3, 4]),
    construction: null,
    history,
  };
  const site = (grade: number, progress: number | null, surrendering = false): Construction => ({
    session_id: 99,
    index: world.plots.findIndex((p) => p.rubble) >= 0 ? world.plots.findIndex((p) => p.rubble) : world.plots.length,
    grade,
    progress_permille: progress,
    surrendering,
    seed: 123456789,
  });
  switch (scenario) {
    case "empty":
      Object.assign(world, { tier: 0, focused_secs: 0, tier_floor_secs: 0, next_tier_secs: 36000, streak_days: 0, plots: [], history: [] });
      break;
    case "hamlet":
      Object.assign(world, { tier: 0, focused_secs: 5 * 3600, tier_floor_secs: 0, next_tier_secs: 36000, plots: plots(5, 3, [0, 0, 1], 0), history: history.slice(0, 1) });
      break;
    case "metropolis":
      Object.assign(world, { tier: 3, focused_secs: 260 * 3600, tier_floor_secs: 200 * 3600, next_tier_secs: null, plots: plots(120, 11, [1, 2, 3, 3, 4, 4], 0.08) });
      break;
    case "session":
      status.nudge = null;
      status.session = session({ type: "countdown", secs: 3000 }, 1260);
      world.construction = site(2, 420);
      break;
    case "stopwatch":
      status.nudge = null;
      status.session = session({ type: "stopwatch" }, 3300);
      world.construction = site(1, null);
      break;
    case "surrender":
      status.nudge = null;
      status.session = session({ type: "countdown", secs: 5400 }, 2000, true);
      world.construction = site(3, 370, true);
      break;
    case "ruins":
      world.plots = plots(16, 5, [1, 2, 3], 0.7);
      break;
  }
  return { world, status };
}

const state = build();

export function mockDaemon(req: Request): Response {
  const s = state.status.session;
  switch (req.type) {
    case "status": {
      if (s) {
        const elapsed = Math.floor(Date.now() / 1000) - s.started_at;
        s.elapsed_secs = elapsed;
        if (s.kind.type === "countdown") s.remaining_secs = Math.max(0, s.kind.secs - elapsed);
        s.stop_locked_secs = Math.max(0, 600 - elapsed);
      }
      return { type: "status", ...state.status };
    }
    case "world":
      return { type: "world", ...state.world };
    case "start":
      if (s) return { type: "error", message: "a session is already running" };
      state.status.session = session(req.kind, 0);
      state.status.nudge = null;
      state.world.construction = { session_id: 99, index: state.world.plots.length, grade: 0, progress_permille: req.kind.type === "countdown" ? 0 : null, surrendering: false, seed: 42 };
      return { type: "session", ...state.status.session };
    case "stop":
      if (!s || s.kind.type !== "stopwatch") return { type: "error", message: "countdowns cannot be stopped" };
      if (s.stop_locked_secs > 0) return { type: "error", message: "too early to stop" };
      state.status.session = null;
      state.world.construction = null;
      return { type: "session", ...s, state: "completed" };
    case "surrender":
      if (!s) return { type: "error", message: "no session" };
      if (req.phrase !== SURRENDER_PHRASE) return { type: "error", message: "the phrase does not match" };
      s.state = "surrendering";
      s.surrender_remaining_secs = 600;
      if (state.world.construction) state.world.construction.surrendering = true;
      return { type: "session", ...s };
    case "skip":
      return { type: "error", message: "no routine to skip" };
  }
}
