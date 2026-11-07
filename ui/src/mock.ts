// Canned daemon for developing the renderer in a browser: `bun run dev`, then
// open http://localhost:5173/?mock=city (empty, hamlet, city, metropolis,
// session, stopwatch, surrender, ruins, desk, nearmiss, levelup). `&hour=22` fixes the time of day.
// Every scenario but `empty` has two routines, a month of past sessions and a
// pending config change, for the Stats and Session logs sections.
// Each load replays the history (its timestamps are relative to now). In the
// console, `city.demo("collapse" | "build" | "damage", plot?)` plays one
// transition (the tallest building if no plot is given).
import type { Config, Finished, PendingConfig, Request, Response, RoutineInfo, SessionInfo, Status } from "./proto";
import { SURRENDER_PHRASE } from "./proto";
import { MockCity } from "./mockcity";

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

/** Grows a city by `n` completed sessions of `mins`, a day apart, ending yesterday. */
function grow(city: MockCity, n: number, mins: number) {
  for (let k = 0; k < n; k++) city.complete(mins * 60, t0 - (n - k) * 86400 + 36000);
}

function build(): { city: MockCity; status: Status; past: Finished[]; pending: PendingConfig | null } {
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
  const city = new MockCity();
  city.streak = 4;
  city.freeLand = scenario !== "empty";
  const r = rand(7);
  const scar = (share: number) => {
    for (const i of city.built.keys()) if (r() < share) city.hurt(i, 1 + Math.floor(r() * 3), t0 - 20000 + i);
  };
  switch (scenario) {
    case "empty":
      city.streak = 0;
      break;
    case "hamlet":
      grow(city, 6, 60);
      break;
    case "desk":
      // The mayor at work: a choice made, a site paused, crew hours waiting.
      grow(city, 5, 60);
      city.buy("s4");
      city.choose("hamlet-jobs", null, t0 - 7000);
      city.complete(50 * 60, t0 - 6000);
      city.choose("hamlet-water", null, t0 - 5000);
      city.complete(45 * 60, t0 - 3000);
      break;
    case "levelup":
      // One 50 min session short of the Town: the countdown below finishes it.
      grow(city, 11, 50);
      break;
    case "metropolis":
      grow(city, 200, 150);
      scar(0.05);
      break;
    case "ruins":
      grow(city, 60, 90);
      scar(0.6);
      break;
    default:
      grow(city, 80, 90);
      scar(0.12);
  }
  switch (scenario) {
    case "session":
      status.nudge = null;
      status.session = session({ type: "countdown", secs: 3000 }, 1260);
      break;
    case "stopwatch":
      status.nudge = null;
      status.session = session({ type: "stopwatch" }, 3300);
      break;
    case "surrender":
      status.nudge = null;
      status.session = session({ type: "countdown", secs: 5400 }, 2000, true);
      break;
    case "levelup":
      // Ends 15s after opening, so the graduation plays live.
      status.nudge = null;
      status.session = session({ type: "countdown", secs: 3000 }, 2985);
      break;
    case "nearmiss":
      // A countdown about to end a few minutes short of a finish line.
      status.nudge = null;
      status.session = session({ type: "countdown", secs: 3000 }, 2950);
      break;
    case "inverted":
      status.nudge = null;
      status.free = { balance_secs: 1440, spending: false, stops_in_secs: null, max_bank_secs: 7200, free_mins_per_hour: 12, throttled: true };
      break;
  }
  if (scenario === "nearmiss") {
    // Leave the site 55 min short, so 5 more minutes than the countdown finish it.
    const site = city.construction(99, 0, false);
    if (site) {
      const total = (site.remaining_secs ?? 0) + (city.sites.get(site.index)?.done ?? 0);
      city.sites.set(site.index, { design: site.design ?? null, done: Math.max(0, total - 3300) });
      city.active = site.index;
    }
  }
  const empty = scenario === "empty";
  const pending: PendingConfig | null = empty
    ? null
    : { applies_at: t0 + 61000, applies_in_secs: 61000, reasons: ["profile deep: youtube.com no longer throttled"] };
  city.freeLand = false;
  if (scenario !== "empty" && scenario !== "hamlet") city.dress();
  return { city, status, past: empty ? [] : pastSessions(), pending };
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
    case "world": {
      const now = Math.floor(Date.now() / 1000);
      if (s?.kind.type === "countdown" && s.state === "active" && now - s.started_at >= s.kind.secs) {
        // The countdown ran out: it completes, as the daemon would.
        state.city.complete(s.kind.secs, now);
        state.status.session = null;
      }
      const live = state.status.session;
      const site = live ? state.city.construction(live.id, Math.max(0, now - live.started_at), live.state === "surrendering") : null;
      return { type: "world", ...state.city.world(now, site) };
    }
    case "start": {
      if (s) return { type: "error", message: "a session is already running" };
      if (req.stake) {
        const err = state.city.stake(req.stake, req.kind.type === "countdown" ? req.kind.secs : null);
        if (err) return { type: "error", message: err };
      }
      state.status.session = session(req.kind, 0);
      state.status.nudge = null;
      return { type: "session", ...state.status.session };
    }
    case "stop":
      if (!s || s.kind.type !== "stopwatch") return { type: "error", message: "countdowns cannot be stopped" };
      if (s.stop_locked_secs > 0) return { type: "error", message: "too early to stop" };
      state.status.session = null;
      state.city.complete(s.elapsed_secs, Math.floor(Date.now() / 1000));
      return { type: "session", ...s, state: "completed" };
    case "surrender":
      if (!s) return { type: "error", message: "no session" };
      if (req.phrase !== SURRENDER_PHRASE) return { type: "error", message: "the phrase does not match" };
      s.state = "surrendering";
      s.surrender_remaining_secs = 600;
      return { type: "session", ...s };
    case "buy":
    case "choose":
    case "pause":
    case "rename":
    case "buy_land":
    case "repair":
    case "upgrade_street":
    case "decorate":
    case "use_item": {
      if (s && req.type !== "rename") return { type: "error", message: "the mayor's desk opens when the session ends" };
      const now = Math.floor(Date.now() / 1000);
      const c = state.city;
      const err =
        req.type === "buy" ? c.buy(req.blueprint)
        : req.type === "choose" ? c.choose(req.need, req.blueprint, now)
        : req.type === "pause" ? c.pause()
        : req.type === "buy_land" ? c.buyLand(req.lot)
        : req.type === "repair" ? c.repair(req.lot, false)
        : req.type === "upgrade_street" ? c.upgrade(req.street)
        : req.type === "decorate" ? c.decorate(req.spot, req.decoration)
        : req.type === "use_item" ? c.useItem(req.item, req.lot)
        : c.rename(req.lot, req.name);
      if (err) return { type: "error", message: err };
      return { type: "world", ...c.world(now, null) };
    }
    case "extend": {
      if (!s || s.state !== "active") return { type: "error", message: "no session is running" };
      if (s.kind.type !== "countdown") return { type: "error", message: "a stopwatch runs as long as you like already" };
      if (s.kind.secs + req.secs > 6 * 3600) return { type: "error", message: "a session can be at most 6 hours" };
      s.kind = { type: "countdown", secs: s.kind.secs + req.secs };
      s.remaining_secs = s.kind.secs - s.elapsed_secs;
      return { type: "session", ...s };
    }
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
          events: [],
          routine_runs: [],
          free_bank: state.status.free ? { balance_ms: state.status.free.balance_secs * 1000, spending: null } : null,
        },
      };
    case "import":
      return { type: "imported", sessions: 0, message: "mock: backup accepted", pending: state.pending };
  }
}
