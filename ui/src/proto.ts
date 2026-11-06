// Mirrors crates/proto/src/lib.rs. The daemon is the only authority; these
// are just the shapes it sends.

export type SessionKind = { type: "countdown"; secs: number } | { type: "stopwatch" };

export type Request =
  | { type: "status" }
  | { type: "start"; kind: SessionKind; profile: string | null }
  | { type: "stop" }
  | { type: "surrender"; phrase: string }
  | { type: "skip"; routine: string | null }
  | { type: "world" }
  | { type: "history"; since: number }
  | { type: "routines" }
  | { type: "config_status" }
  | { type: "get_config" }
  | { type: "set_config"; config: Config }
  | { type: "export" }
  | { type: "import"; backup: unknown }
  | { type: "free"; secs: number | null }
  | { type: "free_stop" }
  | { type: "buy"; blueprint: string }
  | { type: "choose"; need: string; blueprint: string | null }
  | { type: "pause" }
  | { type: "rename"; lot: string; name: string }
  | { type: "extend"; secs: number };

export type SessionState = "active" | "surrendering" | "completed" | "surrendered";

export interface SessionInfo {
  id: number;
  kind: SessionKind;
  profile: string;
  routine: string | null;
  state: SessionState;
  started_at: number;
  elapsed_secs: number;
  remaining_secs: number | null;
  stop_locked_secs: number;
  surrender_remaining_secs: number | null;
  distracted_secs: number;
  escalation_stage: number;
}

export interface Upcoming {
  routine: string;
  profile: string;
  starts_at: number;
  ends_at: number;
  starts_in_secs: number;
  skipped: boolean;
}

export interface Finished {
  session: SessionInfo;
  ended_at: number;
}

export interface RoutineInfo {
  name: string;
  /** "mon" .. "sun"; every day if empty. */
  days: string[];
  /** "HH:MM", local. */
  start: string;
  duration_mins: number;
  profile: string;
}

export interface PendingConfig {
  applies_at: number;
  applies_in_secs: number;
  reasons: string[];
}

/** Mirrors the daemon's `config.rs`. Everything but the profiles has a
 * default, so hand-written partial files still parse; the app always sends a
 * whole config back. */
export type ListMode = "block_list" | "allow_only";
export type RuleAction = "throttle" | "block" | "allow";

export interface Rule {
  domain: string;
  action: RuleAction;
}

export interface Throttle {
  rtt_ms: number;
  jitter_ms: number;
  rate_kbit: number;
  loss_pct: number;
}

export interface Stage {
  after_mins: number;
  throttle: Throttle;
}

export interface Profile {
  mode: ListMode;
  throttle: Throttle;
  block_quic: boolean;
  inspect_sni: boolean;
  lock_docker: boolean;
  rules: Rule[];
  escalation: Stage[];
}

export interface Routine {
  name: string;
  days: string[];
  start: string;
  duration_mins: number;
  profile: string | null;
}

export type Upstream = string | { addr: string; tls_name: string };

export interface ForwardZone {
  suffix: string;
  server: string;
}

export interface DnsConfig {
  port: number;
  upstreams: Upstream[];
  forward: ForwardZone[];
  manage_resolved: boolean;
  container_dns: string | null;
}

export interface SessionConfig {
  default_profile: string;
  stopwatch_min_secs: number;
  surrender_wait_secs: number;
}

export interface ScheduleConfig {
  heads_up_secs: number;
  skip_tokens_per_week: number;
}

export interface NudgeConfig {
  enabled: boolean;
  days: string[];
  from: string;
  until: string;
  after_mins: number;
  repeat_mins: number;
}

export interface InvertedConfig {
  enabled: boolean;
  profile: string | null;
  free_mins_per_hour: number;
  max_bank_mins: number;
}

export interface Config {
  dns: DnsConfig;
  session: SessionConfig;
  schedule: ScheduleConfig;
  nudge: NudgeConfig;
  inverted: InvertedConfig;
  routines: Routine[];
  profiles: Record<string, Profile>;
}

/** Inverted mode: distractions are throttled outside sessions too, unless
 * free minutes earned by focus are being spent. */
export interface FreeInfo {
  balance_secs: number;
  spending: boolean;
  stops_in_secs: number | null;
  max_bank_secs: number;
  free_mins_per_hour: number;
  /** The outside-session throttle is on right now. */
  throttled: boolean;
}

export interface Status {
  session: SessionInfo | null;
  profiles: string[];
  dry_run: boolean;
  upcoming: Upcoming[];
  heads_up_secs: number;
  skip_tokens_left: number;
  last: Finished | null;
  nudge: { level: number; idle_secs: number } | null;
  /** Set when inverted mode is on. */
  free: FreeInfo | null;
}

export interface Plot {
  /** The lot's index in the plan. */
  index: number;
  district: number;
  /** Size class from the lot's kind: 0 cottage to 4 landmark. */
  grade: number;
  /** 0 intact, up to MAX_DAMAGE (a ruin, still standing). */
  damage: number;
  rubble: boolean;
  /** A u64 on the wire; JSON numbers round it, which is still stable. */
  seed: number;
  /** The session that finished it, and when (unix seconds). */
  session_id: number;
  built_at: number;
  // Progression v2; absent from an older daemon.
  lot?: string;
  /** `cottage`, `shop`, `water`, `school`, ... */
  kind?: string;
  /** The blueprint (a model id); null for buildings the town provides. */
  design?: string | null;
  name?: string;
  address?: string;
  need?: string;
  shiny?: boolean;
  memory?: Memory;
}

export interface Memory {
  started_at: number;
  parts: BuildPart[];
  focused_secs: number;
  streak_at_finish: number;
  scars: Scar[];
  first: boolean;
}

export interface BuildPart {
  session_id: number;
  ts: number;
  secs: number;
  session_secs: number;
}

export interface Scar {
  ts: number;
  cause: WorldCause;
  damage: number;
  repaired: boolean;
}

export interface Construction {
  session_id: number;
  index: number;
  grade: number;
  /** Counting this session so far. */
  progress_permille: number | null;
  surrendering: boolean;
  seed: number;
  lot?: string;
  kind?: string;
  design?: string | null;
  name?: string;
  /** The need the lot meets (`city-power`, ...); absent from an older daemon. */
  need?: string;
  /** Build time the site still needed when the session started. */
  remaining_secs?: number;
}

export type WorldEventKind = "built" | "repaired" | "collapsed" | "quake" | "damaged" | "graduated";
export type WorldCause = "completed" | "surrendered" | "tamper" | "escalation_denied" | "clock_jump" | "tunnel";

export interface WorldEvent {
  ts: number;
  kind: WorldEventKind;
  cause: WorldCause;
  session_id: number | null;
  plots: number[];
  ruined: number[];
}

export interface NeedInfo {
  id: string;
  title: string;
  /** What the residents say. */
  words: string;
  kind: string;
  district: string;
  build_secs: number;
  lots: number;
  lots_done: number;
  next_lot: string | null;
  site: boolean;
  designed: boolean;
  /** Owned blueprints that fit, and ones that would if bought. */
  fits: string[];
  fits_locked: string[];
}

export interface BlueprintInfo {
  id: string;
  name: string;
  kind: string;
  districts: string[];
  level: number;
  price: number;
  owned: boolean;
  unlocked: boolean;
  built: number;
}

export interface SiteInfo {
  index: number;
  lot: string;
  need: string;
  name: string;
  kind: string;
  design: string | null;
  done_secs: number;
  build_secs: number;
  active: boolean;
  seed: number;
}

export interface Award {
  session_id: number;
  ts: number;
  coins: number;
  length_bonus: number;
  streak_bonus: number;
  rested_bonus: number;
  build_secs: number;
  finished: number[];
  freeze_earned: boolean;
  freezes_used: number;
}

export interface World {
  tier: number;
  focused_secs: number;
  /** Build time of the plan up to this level and the next. */
  tier_floor_secs: number;
  next_tier_secs: number | null;
  /** Build time put into the plan; progress between the two above. */
  built_secs?: number;
  streak_days: number;
  plots: Plot[];
  construction: Construction | null;
  history: WorldEvent[];
  coins?: number;
  coins_earned?: number;
  needs?: NeedInfo[];
  next_needs?: string[];
  blueprints?: BlueprintInfo[];
  sites?: SiteInfo[];
  idle_secs?: number;
  freezes?: number;
  /** The plan builds itself until the mayor first chooses. */
  auto?: boolean;
  last_award?: Award | null;
}

export const MAX_PAUSED = 3;
export const MAX_DAMAGE = 3;
export const DISTRICT_SIZE = 8;

export const SURRENDER_PHRASE = "I am choosing distraction over the work I said mattered to me";

export type Response =
  | ({ type: "status" } & Status)
  | ({ type: "session" } & SessionInfo)
  | { type: "skipped"; upcoming: Upcoming; tokens_left: number }
  | { type: "config"; message: string; pending: PendingConfig | null }
  | {
      type: "config_data";
      config: Config;
      /** The settings the waiting change would apply, if any. */
      pending_config: Config | null;
      pending: PendingConfig | null;
      message: string;
    }
  | { type: "backup"; backup: unknown }
  | { type: "imported"; sessions: number; message: string; pending: PendingConfig | null }
  | ({ type: "world" } & World)
  | { type: "history"; sessions: Finished[] }
  | { type: "routines"; routines: RoutineInfo[]; skip_tokens_per_week: number }
  | ({ type: "free" } & FreeInfo)
  | { type: "error"; message: string };
