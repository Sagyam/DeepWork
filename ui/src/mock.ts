// Canned daemon for developing the renderer in a browser: `bun run dev`, then
// open http://localhost:5173/?mock=city (empty, hamlet, city, metropolis,
// session, stopwatch, surrender, ruins). `&hour=22` fixes the time of day.
// Every scenario but `empty` has two routines, a month of past sessions and a
// pending config change, for the Routines and Stats panels.
// Each load replays the history (its timestamps are relative to now). In the
// console, `city.demo("collapse" | "build" | "damage", plot?)` plays one
// transition (the tallest building if no plot is given).
import type { Config, Construction, Finished, PendingConfig, Plot, Request, Response, RoutineInfo, SessionInfo, Status, World, WorldEvent } from "./proto";
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

const routines: RoutineInfo[] = [
  { name: "morning", days: ["mon", "tue", "wed", "thu", "fri"], start: "09:00", duration_mins: 90, profile: "deep" },
  { name: "evening", days: [], start: "20:30", duration_mins: 50, profile: "deep" },
];

/** The settings sheet in a browser has something real to edit. */
let config: Config = {
  dns: {
    port: 5454,
    upstreams: [
      { addr: "9.9.9.9:853", tls_name: "dns.quad9.net" },
      { addr: "1.1.1.1:853", tls_name: "cloudflare-dns.com" },
    ],
    forward: [{ suffix: "ts.net", server: "100.100.100.100:53" }],
    manage_resolved: true,
    container_dns: "172.17.0.1:53",
  },
  session: { default_profile: "deep", stopwatch_min_secs: 600, surrender_wait_secs: 600 },
  schedule: { heads_up_secs: 300, skip_tokens_per_week: 2 },
  nudge: { enabled: true, days: [], from: "09:00", until: "21:00", after_mins: 30, repeat_mins: 15 },
  inverted: { enabled: false, profile: null, free_mins_per_hour: 12, max_bank_mins: 120 },
  routines: routines.map((r) => ({ ...r, days: [...r.days], profile: null })),
  profiles: {
    deep: {
      mode: "block_list",
      throttle: { rtt_ms: 400, jitter_ms: 50, rate_kbit: 256, loss_pct: 0 },
      block_quic: true,
      inspect_sni: true,
      lock_docker: false,
      rules: [
        { domain: "youtube.com", action: "throttle" },
        { domain: "youtu.be", action: "throttle" },
        { domain: "reddit.com", action: "throttle" },
        { domain: "x.com", action: "throttle" },
        { domain: "instagram.com", action: "block" },
        { domain: "docs.rs", action: "allow" },
      ],
      escalation: [
        { after_mins: 10, throttle: { rtt_ms: 500, jitter_ms: 50, rate_kbit: 192, loss_pct: 0 } },
        { after_mins: 20, throttle: { rtt_ms: 600, jitter_ms: 50, rate_kbit: 128, loss_pct: 0 } },
      ],
    },
    trial: {
      mode: "allow_only",
      throttle: { rtt_ms: 300, jitter_ms: 40, rate_kbit: 512, loss_pct: 0 },
      block_quic: true,
      inspect_sni: true,
      lock_docker: false,
      rules: [{ domain: "docs.rs", action: "allow" }],
      escalation: [],
    },
  },
};

/** About a month of past sessions: mostly mornings, some evenings, a few surrenders. */
function pastSessions(): Finished[] {
  const r = rand(17);
  const out: Finished[] = [];
  for (let day = 27; day >= 0; day--) {
    const midnight = new Date(new Date().setHours(0, 0, 0, 0) - day * 86400_000).getTime() / 1000;
    for (const [hour, mins, routine] of [[9, 90, "morning"], [14, 50, null], [20.5, 50, "evening"]] as const) {
      if (r() < 0.35) continue;
      const surrendered = r() < 0.08;
      const elapsed = (surrendered ? Math.floor(mins * r()) : mins) * 60;
      const end = midnight + hour * 3600 + elapsed + (surrendered ? 600 : 0);
      if (end > t0) continue;
      const id = out.length + 1;
      out.push({
        ended_at: end,
        session: {
          ...session({ type: "countdown", secs: mins * 60 }, elapsed),
          id, routine, state: surrendered ? "surrendered" : "completed", started_at: midnight + hour * 3600,
          remaining_secs: mins * 60 - elapsed, stop_locked_secs: 0, distracted_secs: 0, escalation_stage: 0,
        },
      });
    }
  }
  return out.reverse();
}

function build(): { world: World; status: Status; past: Finished[]; pending: PendingConfig | null } {
  const status: Status = {
    session: null,
    profiles: ["deep", "trial"],
    dry_run: false,
    upcoming: [
      { routine: "morning", profile: "deep", starts_at: t0 + 5400, ends_at: t0 + 5400 + 5400, starts_in_secs: 5400, skipped: false },
      { routine: "evening", profile: "deep", starts_at: t0 + 30000, ends_at: t0 + 33000, starts_in_secs: 30000, skipped: false },
    ],
    heads_up_secs: 300,
    skip_tokens_left: 2,
    last: null,
    nudge: { level: 2, idle_secs: 4200 },
    free: null,
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
    case "inverted":
      status.nudge = null;
      status.free = { balance_secs: 1440, spending: false, stops_in_secs: null, max_bank_secs: 7200, free_mins_per_hour: 12, throttled: true };
      break;
    case "ruins":
      world.plots = plots(16, 5, [1, 2, 3], 0.7);
      break;
  }
  const empty = scenario === "empty";
  const pending: PendingConfig | null = empty
    ? null
    : { applies_at: t0 + 61000, applies_in_secs: 61000, reasons: ["profile deep: youtube.com no longer throttled"] };
  return { world, status, past: empty ? [] : pastSessions(), pending };
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
    case "skip": {
      const u = state.status.upcoming.find((u) => !u.skipped && u.starts_in_secs > 0 && (req.routine === null || u.routine === req.routine));
      if (!u) return { type: "error", message: "nothing to skip in the next 24 hours" };
      if (state.status.skip_tokens_left === 0) return { type: "error", message: "no skip tokens left this week (2 per week)" };
      u.skipped = true;
      state.status.skip_tokens_left--;
      return { type: "skipped", upcoming: u, tokens_left: state.status.skip_tokens_left };
    }
    case "history":
      return { type: "history", sessions: state.past.filter((f) => f.ended_at >= req.since) };
    case "routines":
      return { type: "routines", routines, skip_tokens_per_week: 2 };
    case "free": {
      const f = state.status.free;
      if (!f) return { type: "error", message: "inverted mode is off: nothing is throttled outside sessions" };
      if (s) return { type: "error", message: "free minutes cannot be spent during a session" };
      Object.assign(f, { spending: true, stops_in_secs: f.balance_secs, throttled: false });
      return { type: "free", ...f };
    }
    case "free_stop": {
      const f = state.status.free;
      if (!f?.spending) return { type: "error", message: "free time is not running" };
      Object.assign(f, { spending: false, stops_in_secs: null, throttled: true });
      return { type: "free", ...f };
    }
    case "config_status":
      return { type: "config", message: state.pending ? "a loosening change is waiting" : "no change waiting", pending: state.pending };
    case "get_config":
      return {
        type: "config_data",
        config,
        pending_config: state.pending ? config : null,
        pending: state.pending,
        message: "settings loaded",
      };
    case "set_config":
      config = JSON.parse(JSON.stringify(req.config)) as Config;
      state.pending = null;
      return { type: "config_data", config, pending_config: null, pending: null, message: "config applied" };
    case "export":
      return {
        type: "backup",
        backup: {
          format: "deepwork-backup",
          version: 1,
          exported_at: t0,
          config: "# the mock does not write TOML\n",
          sessions: state.past,
          events: history.filter((e) => e.kind === "quake" || e.kind === "damaged").map((e) => ({
            ts: e.ts,
            session_id: e.session_id,
            kind: e.cause === "tamper" ? "tamper" : "clock_jump",
            detail: "",
          })),
          routine_runs: [],
          free_bank: state.status.free ? { balance_ms: state.status.free.balance_secs * 1000, spending: null } : null,
        },
      };
    case "import":
      return { type: "imported", sessions: 0, message: "mock: backup accepted", pending: state.pending };
  }
}
