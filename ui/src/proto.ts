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
  | { type: "config_status" };

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

export interface Status {
  session: SessionInfo | null;
  profiles: string[];
  dry_run: boolean;
  upcoming: Upcoming[];
  heads_up_secs: number;
  skip_tokens_left: number;
  last: Finished | null;
  nudge: { level: number; idle_secs: number } | null;
}

export interface Plot {
  index: number;
  district: number;
  grade: number;
  damage: number;
  rubble: boolean;
  /** A u64 on the wire; JSON numbers round it, which is still stable. */
  seed: number;
  session_id: number;
  built_at: number;
}

export interface Construction {
  session_id: number;
  index: number;
  grade: number;
  progress_permille: number | null;
  surrendering: boolean;
  seed: number;
}

export type WorldEventKind = "built" | "repaired" | "collapsed" | "quake" | "damaged";
export type WorldCause = "completed" | "surrendered" | "tamper" | "escalation_denied" | "clock_jump";

export interface WorldEvent {
  ts: number;
  kind: WorldEventKind;
  cause: WorldCause;
  session_id: number | null;
  plots: number[];
  ruined: number[];
}

export interface World {
  tier: number;
  focused_secs: number;
  tier_floor_secs: number;
  next_tier_secs: number | null;
  streak_days: number;
  plots: Plot[];
  construction: Construction | null;
  history: WorldEvent[];
}

export const MAX_DAMAGE = 3;
export const DISTRICT_SIZE = 8;

export const SURRENDER_PHRASE = "I am choosing distraction over the work I said mattered to me";

export type Response =
  | ({ type: "status" } & Status)
  | ({ type: "session" } & SessionInfo)
  | { type: "skipped"; upcoming: Upcoming; tokens_left: number }
  | { type: "config"; message: string; pending: PendingConfig | null }
  | ({ type: "world" } & World)
  | { type: "history"; sessions: Finished[] }
  | { type: "routines"; routines: RoutineInfo[]; skip_tokens_per_week: number }
  | { type: "error"; message: string };
