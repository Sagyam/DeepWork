//! IPC types shared by `deepworkd` and its clients.
//!
//! The wire format is newline-delimited JSON: one [`Request`] per line from the
//! client, one [`Response`] per line from the daemon.

use serde::{Deserialize, Serialize};

pub const DEFAULT_SOCKET: &str = "/run/deepwork/deepworkd.sock";

/// The phrase a user has to type to surrender a session.
pub const SURRENDER_PHRASE: &str = "I am choosing distraction over the work I said mattered to me";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum SessionKind {
    Countdown { secs: u64 },
    Stopwatch,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Request {
    Status,
    Start {
        kind: SessionKind,
        profile: Option<String>,
    },
    /// End a stopwatch session. Refused for countdowns and before the minimum.
    Stop,
    /// Begin the surrender wait. `phrase` must equal [`SURRENDER_PHRASE`].
    Surrender {
        phrase: String,
    },
    /// Spend a skip token on the next occurrence of a routine (any routine if
    /// `None`) that has not started yet.
    Skip {
        routine: Option<String>,
    },
    /// Asked by the PAM / polkit hook before a privilege escalation.
    /// `uid` is the real uid of the caller, if known.
    Gate {
        service: String,
        uid: Option<u32>,
    },
    /// The config change waiting behind the loosening delay, if any.
    ConfigStatus,
    /// Re-read the config file. Loosening changes wait 24 hours.
    ReloadConfig,
    /// The config in effect, as JSON in the daemon's config shape.
    GetConfig,
    /// Replace the config (as JSON in the daemon's config shape) and write it
    /// to the config file. Stricter and neutral changes apply at once;
    /// loosening ones wait 24 hours.
    SetConfig {
        config: serde_json::Value,
    },
    /// Settings and progress (sessions, penalties, routine runs, free minutes)
    /// in one JSON bundle, for a backup.
    Export,
    /// Restore a bundle made by [`Request::Export`]. Merges: sessions already
    /// present (same profile and start) are skipped.
    Import {
        backup: serde_json::Value,
    },
    /// The progression world, derived from the ledger.
    World,
    /// Sessions that ended at or after `since` (unix seconds), newest first.
    /// At most [`HISTORY_LIMIT`].
    History {
        since: i64,
    },
    /// The routines in the config.
    Routines,
    /// Inverted mode: spend banked free minutes, lifting the outside-session
    /// throttle until the bank is empty or after `secs`.
    Free {
        secs: Option<u64>,
    },
    /// Stop spending free minutes; the rest stays banked.
    FreeStop,
    /// Buy a blueprint with coins. Refused during a session.
    Buy {
        blueprint: String,
    },
    /// The mayor picks the residents' need to build for next, with the
    /// blueprint to fill its lot (`None`: the only or the first owned one
    /// that fits). The current site, if another, is paused. Refused during a
    /// session.
    Choose {
        need: String,
        #[serde(default)]
        blueprint: Option<String>,
    },
    /// Pause the active construction site; focus then banks as crew hours.
    Pause,
    /// Rename a finished building. An empty name restores the plan's.
    Rename {
        lot: String,
        name: String,
    },
    /// Add minutes to the running countdown, up to the session cap.
    Extend {
        secs: u64,
    },
}

/// The most sessions one [`Request::History`] returns.
pub const HISTORY_LIMIT: usize = 2000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionState {
    Active,
    Surrendering,
    Completed,
    Surrendered,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SessionInfo {
    pub id: i64,
    pub kind: SessionKind,
    pub profile: String,
    /// The routine that started this session, if any.
    #[serde(default)]
    pub routine: Option<String>,
    pub state: SessionState,
    /// Unix seconds.
    pub started_at: i64,
    /// Focused seconds so far. Does not include suspend or downtime.
    pub elapsed_secs: u64,
    /// Seconds left on a countdown; `None` for stopwatches.
    pub remaining_secs: Option<u64>,
    /// Seconds until a stopwatch may be stopped; 0 once allowed.
    pub stop_locked_secs: u64,
    /// Seconds left in the surrender wait, if surrendering.
    pub surrender_remaining_secs: Option<u64>,
    /// Time with real traffic to throttled sites in this session.
    #[serde(default)]
    pub distracted_secs: u64,
    /// Throttle escalation stage reached (0 = the profile's own throttle).
    #[serde(default)]
    pub escalation_stage: u32,
}

/// One scheduled run of a routine.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Upcoming {
    pub routine: String,
    pub profile: String,
    /// Unix seconds.
    pub starts_at: i64,
    pub ends_at: i64,
    /// Seconds until the start, by the daemon's clock. Negative once the
    /// window is open but the session has not started (another session is
    /// running).
    pub starts_in_secs: i64,
    pub skipped: bool,
}

/// A session that has ended.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Finished {
    pub session: SessionInfo,
    /// Unix seconds.
    pub ended_at: i64,
}

/// The daemon asking the user to start a session. `level` goes up by one
/// every repeat interval, so clients can escalate.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Nudge {
    pub level: u32,
    /// Seconds without a session, counted from the start of active hours.
    pub idle_secs: u64,
}

/// Inverted mode: distractions are throttled outside sessions too, unless
/// free minutes earned by focus are being spent.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct FreeInfo {
    pub balance_secs: u64,
    /// Free time is running; the throttle is lifted.
    pub spending: bool,
    /// When spending, seconds until it stops on its own.
    pub stops_in_secs: Option<u64>,
    pub max_bank_secs: u64,
    pub free_mins_per_hour: u32,
    /// The outside-session throttle is on right now.
    pub throttled: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Status {
    pub session: Option<SessionInfo>,
    pub profiles: Vec<String>,
    pub dry_run: bool,
    /// Routine runs in the next 24 hours, soonest first.
    #[serde(default)]
    pub upcoming: Vec<Upcoming>,
    /// Clients should warn about a routine this many seconds ahead.
    #[serde(default)]
    pub heads_up_secs: u64,
    #[serde(default)]
    pub skip_tokens_left: u32,
    #[serde(default)]
    pub last: Option<Finished>,
    #[serde(default)]
    pub nudge: Option<Nudge>,
    /// Set when inverted mode is on.
    #[serde(default)]
    pub free: Option<FreeInfo>,
}

/// A routine as configured. Its runs show up in [`Status::upcoming`].
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RoutineInfo {
    pub name: String,
    /// `"mon"` .. `"sun"`; every day if empty.
    pub days: Vec<String>,
    /// Local wall-clock time, `"HH:MM"`.
    pub start: String,
    pub duration_mins: u32,
    pub profile: String,
}

/// A loosening config change waiting for its delay.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PendingConfig {
    /// Unix seconds.
    pub applies_at: i64,
    pub applies_in_secs: i64,
    /// What it loosens, in words.
    pub reasons: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConfigInfo {
    /// What the last reload did, or a summary for a status request.
    pub message: String,
    pub pending: Option<PendingConfig>,
}

/// The progression world. Theme-agnostic: a renderer turns lots, kinds and
/// damage into pictures (buildings in the skyline theme). Clients can only
/// read it; it is rebuilt from the ledger on every request.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct World {
    /// Settlement level, 0 to [`World::MAX_TIER`]: Hamlet, Town, City,
    /// Metropolis. It goes up when every need of a level is met.
    pub tier: u32,
    /// Focus time that counts: completed sessions only.
    pub focused_secs: u64,
    /// Build time of the plan up to the current level, and up to the next
    /// one (`None` once the plan is finished). Progress is [`World::built_secs`].
    pub tier_floor_secs: u64,
    pub next_tier_secs: Option<u64>,
    /// Build time put into the plan's lots, finished or under construction.
    #[serde(default)]
    pub built_secs: u64,
    /// Consecutive local days with a completed session of 25 minutes or
    /// more, up to today (a freeze covers a missed day).
    pub streak_days: u32,
    /// Finished buildings, by lot index. A lot keeps its index for good.
    pub plots: Vec<Plot>,
    /// The site the running session is working on.
    pub construction: Option<Construction>,
    /// Recent world changes, oldest first.
    pub history: Vec<WorldEvent>,
    /// Coins to spend, and all ever earned.
    #[serde(default)]
    pub coins: u64,
    #[serde(default)]
    pub coins_earned: u64,
    /// The current level's needs, in the plan's order.
    #[serde(default)]
    pub needs: Vec<NeedInfo>,
    /// The next level's needs, by title, as a teaser.
    #[serde(default)]
    pub next_needs: Vec<String>,
    /// Every blueprint, for sale or not.
    #[serde(default)]
    pub blueprints: Vec<BlueprintInfo>,
    /// Construction sites standing half built: the active one and the paused.
    #[serde(default)]
    pub sites: Vec<SiteInfo>,
    /// Focus waiting for a site to be chosen.
    #[serde(default)]
    pub idle_secs: u64,
    /// Streak freezes held; each saves the streak on one missed day.
    #[serde(default)]
    pub freezes: u32,
    /// The mayor has not chosen anything yet: the plan builds itself in its
    /// default order, buying the default blueprint when coins allow.
    #[serde(default)]
    pub auto: bool,
    /// What the last completed session earned.
    #[serde(default)]
    pub last_award: Option<Award>,
}

impl World {
    pub const MAX_TIER: u32 = 3;
    /// Damage at which a building is a ruin. It stays one until repaired.
    pub const MAX_DAMAGE: u32 = 3;
    /// Sites that may stand paused at once.
    pub const MAX_PAUSED: usize = 3;
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Plot {
    /// The lot's index in the plan.
    pub index: u32,
    /// Plots are grouped into districts of a fixed size, in index order.
    pub district: u32,
    /// Size class, 0 cottage to 4 landmark, from the lot's kind.
    pub grade: u32,
    /// 0 is intact, up to [`World::MAX_DAMAGE`].
    pub damage: u32,
    /// A ruin (damage at the maximum). Repairs bring it back.
    pub rubble: bool,
    /// Stable per-plot randomness for renderers.
    pub seed: u64,
    /// The session that finished it.
    pub session_id: i64,
    /// Unix seconds, when it was finished.
    pub built_at: i64,
    /// The plan's lot id.
    #[serde(default)]
    pub lot: String,
    /// What it is: `cottage`, `shop`, `water`, ...
    #[serde(default)]
    pub kind: String,
    /// The blueprint it was built from (a model id); `None` for buildings the
    /// town provides.
    #[serde(default)]
    pub design: Option<String>,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub address: String,
    /// The need it answered.
    #[serde(default)]
    pub need: String,
    /// It came out rare.
    #[serde(default)]
    pub shiny: bool,
    #[serde(default)]
    pub memory: Memory,
}

/// How a building came to be.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Memory {
    /// Unix seconds: first work on it.
    pub started_at: i64,
    /// Sessions that put time into it, in order.
    pub parts: Vec<BuildPart>,
    pub focused_secs: u64,
    /// The streak when it was finished.
    pub streak_at_finish: u32,
    /// Damage and repairs, in order.
    pub scars: Vec<Scar>,
    /// It was the first building of the city.
    pub first: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BuildPart {
    pub session_id: i64,
    /// Unix seconds the session ended.
    pub ts: i64,
    /// Seconds of it that went into this building.
    pub secs: u64,
    /// The whole session's length.
    pub session_secs: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Scar {
    pub ts: i64,
    pub cause: WorldCause,
    /// Damage after it.
    pub damage: u32,
    /// Repaired rather than damaged.
    pub repaired: bool,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct NeedInfo {
    pub id: String,
    pub title: String,
    /// What the residents say.
    pub words: String,
    pub kind: String,
    pub district: String,
    /// Build time of one of its lots.
    pub build_secs: u64,
    pub lots: u32,
    pub lots_done: u32,
    /// The lot it is building, or would build next.
    pub next_lot: Option<String>,
    /// Its site stands (active or paused).
    pub site: bool,
    /// Whether its lots are filled from a blueprint.
    pub designed: bool,
    /// Owned blueprints that fit, and ones that would fit if bought.
    pub fits: Vec<String>,
    pub fits_locked: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BlueprintInfo {
    /// The model id.
    pub id: String,
    pub name: String,
    pub kind: String,
    pub districts: Vec<String>,
    /// The level it is for sale from.
    pub level: u32,
    pub price: u64,
    pub owned: bool,
    /// For sale now (owned or not).
    pub unlocked: bool,
    /// Buildings standing from it.
    pub built: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SiteInfo {
    pub index: u32,
    pub lot: String,
    pub need: String,
    pub name: String,
    pub kind: String,
    pub design: Option<String>,
    pub done_secs: u64,
    pub build_secs: u64,
    /// Being built; the others are paused.
    pub active: bool,
    pub seed: u64,
}

/// What one completed session earned.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Award {
    pub session_id: i64,
    pub ts: i64,
    pub coins: u64,
    /// Of `coins`: from the session length, the streak and a comeback.
    pub length_bonus: u64,
    pub streak_bonus: u64,
    pub rested_bonus: u64,
    pub build_secs: u64,
    /// Buildings it finished, by lot index.
    pub finished: Vec<u32>,
    /// A streak freeze was earned, or one was spent.
    pub freeze_earned: bool,
    pub freezes_used: u32,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Construction {
    pub session_id: i64,
    /// The lot being built.
    pub index: u32,
    /// Size class of the lot's kind.
    pub grade: u32,
    /// 0 to 1000, counting this session so far. `None` when no site is
    /// chosen and the session banks crew hours.
    pub progress_permille: Option<u32>,
    pub surrendering: bool,
    pub seed: u64,
    #[serde(default)]
    pub lot: String,
    #[serde(default)]
    pub kind: String,
    #[serde(default)]
    pub design: Option<String>,
    #[serde(default)]
    pub name: String,
    /// Build time the site still needed when the session started.
    #[serde(default)]
    pub remaining_secs: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorldEventKind {
    /// A building was finished (`plots`: one lot).
    Built,
    /// Damage taken away by a completed session.
    Repaired,
    /// A surrendered session: its work on the site (`plots[0]`) was lost and
    /// the buildings after it in `plots` burned.
    Collapsed,
    /// Tampering with enforcement: a whole district was hit.
    Quake,
    /// A refused sudo / polkit attempt, a wall-clock jump or a tunnel: one
    /// building hit.
    Damaged,
    /// Every need of a level was met; `plots` is empty.
    Graduated,
}

/// The ledger event behind a world change.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorldCause {
    Completed,
    Surrendered,
    Tamper,
    EscalationDenied,
    ClockJump,
    /// A proxy or tunnel around the throttle (`ssh -D`, Tor, ...).
    Tunnel,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorldEvent {
    /// Unix seconds.
    pub ts: i64,
    pub kind: WorldEventKind,
    pub cause: WorldCause,
    pub session_id: Option<i64>,
    /// Plots affected.
    pub plots: Vec<u32>,
    /// Plots that fell into rubble because of it.
    #[serde(default)]
    pub ruined: Vec<u32>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Response {
    Status(Box<Status>),
    Session(SessionInfo),
    Skipped {
        upcoming: Upcoming,
        tokens_left: u32,
    },
    Gate {
        allow: bool,
        message: String,
    },
    Config(ConfigInfo),
    /// The config in effect (JSON), any pending change, and what the last
    /// save / reload did. `pending_config` is the settings the waiting change
    /// would apply; an editor should show that one, with `pending` as the
    /// warning, so a queued edit does not look like it vanished.
    ConfigData {
        config: serde_json::Value,
        #[serde(default)]
        pending_config: Option<serde_json::Value>,
        pending: Option<PendingConfig>,
        message: String,
    },
    /// A backup bundle made by [`Request::Export`].
    Backup {
        backup: serde_json::Value,
    },
    /// How many sessions a [`Request::Import`] added.
    Imported {
        sessions: usize,
        message: String,
        pending: Option<PendingConfig>,
    },
    World(Box<World>),
    History {
        sessions: Vec<Finished>,
    },
    Routines {
        routines: Vec<RoutineInfo>,
        skip_tokens_per_week: u32,
    },
    Free(FreeInfo),
    Error {
        message: String,
    },
}

impl Response {
    pub fn error(message: impl Into<String>) -> Self {
        Response::Error {
            message: message.into(),
        }
    }
}

/// Sends one request to the daemon and reads the reply. Blocking.
pub fn request(socket: &std::path::Path, req: &Request) -> std::io::Result<Response> {
    request_timeout(socket, req, std::time::Duration::from_secs(10))
}

/// [`request`] with a custom read / write timeout.
pub fn request_timeout(
    socket: &std::path::Path,
    req: &Request,
    timeout: std::time::Duration,
) -> std::io::Result<Response> {
    use std::io::{BufRead, BufReader, Write};
    let mut stream = std::os::unix::net::UnixStream::connect(socket)?;
    stream.set_read_timeout(Some(timeout))?;
    stream.set_write_timeout(Some(timeout))?;
    let mut line = serde_json::to_vec(req)?;
    line.push(b'\n');
    stream.write_all(&line)?;
    let mut reply = String::new();
    BufReader::new(stream).read_line(&mut reply)?;
    Ok(serde_json::from_str(&reply)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn request_round_trip() {
        let req = Request::Start {
            kind: SessionKind::Countdown { secs: 1500 },
            profile: Some("deep".into()),
        };
        let line = serde_json::to_string(&req).unwrap();
        assert_eq!(serde_json::from_str::<Request>(&line).unwrap(), req);
    }
}
