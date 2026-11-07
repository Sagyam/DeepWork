// Mirrors crates/proto/src/lib.rs. The daemon is the only authority; these
// are just the shapes it sends.

export type SessionKind = { type: "countdown"; secs: number } | { type: "stopwatch" };

export type Request =
  | { type: "status" }
  | { type: "start"; kind: SessionKind; profile: string | null; stake?: number }
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
  | { type: "extend"; secs: number }
  | { type: "buy_land"; lot: string }
  | { type: "repair"; lot: string }
  | { type: "upgrade_street"; street: string }
  | { type: "decorate"; spot: string; decoration: string }
  | { type: "rename_street"; street: string; name: string }
  | { type: "use_item"; item: string; lot: string | null };

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
  /** What repairing it now costs; null when undamaged. */
  repair_price?: number | null;
}

export interface Memory {
  started_at: number;
  parts: BuildPart[];
  focused_secs: number;
  streak_at_finish: number;
  scars: Scar[];
  first: boolean;
  /** Build time from hired help, not focus. */
  helped_secs?: number;
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
export type WorldCause = "completed" | "surrendered" | "tamper" | "escalation_denied" | "clock_jump" | "tunnel" | "mayor";

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
  /** The next lot's land, when not bought yet: what it costs. */
  land_price?: number | null;
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
  /** Coins won on a stake, on top of the stake coming back. */
  stake_won?: number;
  boxes?: BoxInfo[];
}

export interface BoxInfo {
  /** The goal that won it, or `set` for a finished set. */
  goal: string;
  item: string;
  /** The finished set's name. */
  set?: string | null;
}

/** A thank-you letter from a family in the city, for something focus or its coins paid for. */
export interface Letter {
  ts: number;
  kind: "street" | "repair" | "park" | "opened" | "set";
  /** "The Hart family". */
  from: string;
  /** The writers' address. */
  address: string;
  text: string;
  /** The building it is about, by lot index. */
  lot: number | null;
}

/** A collection set: every lot on a street, or in a neighbourhood. The last one built wins a box, once. */
export interface SetInfo {
  /** `street:<id>` or `hood:<id>`. */
  id: string;
  kind: "street" | "neighbourhood";
  name: string;
  built: number;
  total: number;
  done: boolean;
}

/** A named group of lot blocks. */
export interface NeighbourhoodInfo {
  id: string;
  name: string;
  /** Indices into `Layout.blocks`. */
  blocks: number[];
}

/** The master plan's ground. Block (x, y) holds 4 x 2 lots: slots 0-3 face north, 4-7 south. */
export interface Layout {
  blocks: BlockInfo[];
  streets: StreetInfo[];
  /** Every lot of the plan, by index. */
  lots: LotInfo[];
  neighbourhoods?: NeighbourhoodInfo[];
}

export interface BlockInfo {
  x: number;
  y: number;
  district: string | null;
  /** `green`, `plaza`, `park` or `sports`. */
  park: string | null;
  name: string | null;
  level: number;
  /** A park that is part of the town now. */
  open: boolean;
  spots: SpotInfo[];
}

export interface SpotInfo {
  id: string;
  decoration: string | null;
}

/** East-west line k runs between block rows k-1 and k; north-south line k between columns k-1 and k. */
export interface StreetInfo {
  id: string;
  name: string;
  axis: "ew" | "ns";
  line: number;
  from: number;
  to: number;
  /** 0 lane, 1 street, 2 boulevard, 3 avenue. */
  class: number;
  upgrade_price: number | null;
  /** Every lot on it is built: the mayor may rename it. */
  complete?: boolean;
}

export interface LotInfo {
  id: string;
  block: number;
  slot: number;
  street: number;
  address: string;
  owned: boolean;
  price: number;
  for_sale: boolean;
}

export interface DecorationInfo {
  id: string;
  name: string;
  price: number;
  level: number;
  unlocked: boolean;
}

export interface ItemInfo {
  id: string;
  name: string;
  count: number;
  rare: boolean;
}

export interface GoalInfo {
  id: string;
  title: string;
  /** Seconds, or sessions for `sessions`. */
  progress: number;
  target: number;
  done: boolean;
}

export const ROAD_CLASSES = ["lane", "street", "boulevard", "avenue"];

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
  layout?: Layout;
  /** The coins held at the start of the day, which prices rise with. */
  wealth?: number;
  decorations?: DecorationInfo[];
  /** Coins at stake on the running session. */
  stake?: number | null;
  stake_target_secs?: number;
  stake_max?: number;
  inventory?: ItemInfo[];
  goals?: GoalInfo[];
  boxes_to_rare?: number;
  /** Streets and neighbourhoods with lots, as collection sets. */
  sets?: SetInfo[];
  /** The residents' latest letters, oldest first. */
  letters?: Letter[];
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
