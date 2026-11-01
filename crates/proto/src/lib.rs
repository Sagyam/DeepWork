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
    /// The progression world, derived from the ledger.
    World,
}

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

/// The progression world. Theme-agnostic: a renderer turns plots, grades and
/// damage into pictures (buildings in the skyline theme). Clients can only
/// read it; it is rebuilt from the ledger on every request.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct World {
    /// Settlement size, 0 to [`World::MAX_TIER`], from `focused_secs`.
    pub tier: u32,
    /// Focus time that counts: completed sessions only.
    pub focused_secs: u64,
    /// `focused_secs` needed for the current and the next tier.
    pub tier_floor_secs: u64,
    pub next_tier_secs: Option<u64>,
    /// Consecutive local days with a completed session, up to today.
    pub streak_days: u32,
    /// In build order. A plot keeps its index for good.
    pub plots: Vec<Plot>,
    /// The plot the running session is working on.
    pub construction: Option<Construction>,
    /// Recent world changes, oldest first.
    pub history: Vec<WorldEvent>,
}

impl World {
    pub const MAX_TIER: u32 = 3;
    /// Damage at which a building falls into rubble.
    pub const MAX_DAMAGE: u32 = 3;
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Plot {
    pub index: u32,
    /// Plots are grouped into districts of a fixed size, in index order.
    pub district: u32,
    /// Size / rarity, 0 to 4, from the length of the session that built it.
    pub grade: u32,
    /// 0 is intact; below [`World::MAX_DAMAGE`].
    pub damage: u32,
    /// Collapsed. The next completed session builds here.
    pub rubble: bool,
    /// Stable per-plot randomness for renderers.
    pub seed: u64,
    /// The session that built (or failed to build) it.
    pub session_id: i64,
    /// Unix seconds.
    pub built_at: i64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Construction {
    pub session_id: i64,
    /// Where it will stand: the oldest rubble plot, or a new one.
    pub index: u32,
    /// The grade it reaches if the session completes now (stopwatch) or on
    /// time (countdown).
    pub grade: u32,
    /// 0 to 1000; `None` for stopwatches.
    pub progress_permille: Option<u32>,
    pub surrendering: bool,
    pub seed: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorldEventKind {
    /// A completed session put up a building.
    Built,
    /// Damage taken away by a completed session.
    Repaired,
    /// A surrendered session: its plot collapsed and nearby buildings burned.
    Collapsed,
    /// Tampering with enforcement: a whole district was hit.
    Quake,
    /// A refused sudo / polkit attempt or a wall-clock jump: one building hit.
    Damaged,
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
    World(Box<World>),
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
