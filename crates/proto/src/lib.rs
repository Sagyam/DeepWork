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
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Status {
    pub session: Option<SessionInfo>,
    pub profiles: Vec<String>,
    pub dry_run: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Response {
    Status(Status),
    Session(SessionInfo),
    Error { message: String },
}

impl Response {
    pub fn error(message: impl Into<String>) -> Self {
        Response::Error {
            message: message.into(),
        }
    }
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
