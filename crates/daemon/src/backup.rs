//! Backup bundles: the settings and the progress they produced in one JSON
//! file, so a reinstall or a second machine can carry both over.
//!
//! The world is derived from ended sessions and penalty events, so those are
//! the progress that has to travel; the free-minute bank and routine runs
//! travel too because they are state the user earned or spent. A bundle is
//! merged, not restored over the top: a session already present (same profile
//! and start) is skipped, so importing the same file twice is harmless.

use deepwork_proto::{SessionKind, SessionState};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "deepwork-backup";
pub const VERSION: u32 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Backup {
    pub format: String,
    pub version: u32,
    /// Unix seconds.
    pub exported_at: i64,
    /// The settings as TOML, exactly as the app would write the file.
    pub config: String,
    #[serde(default)]
    pub sessions: Vec<BackupSession>,
    /// Penalty events: tampering, refused root access, clock jumps, tunnels.
    #[serde(default)]
    pub events: Vec<BackupEvent>,
    #[serde(default)]
    pub routine_runs: Vec<BackupRun>,
    /// The inverted-mode bank, as the daemon stores it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub free_bank: Option<serde_json::Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BackupSession {
    /// The id in the exporting daemon; events refer to it. Remapped on import.
    pub id: i64,
    pub kind: SessionKind,
    pub profile: String,
    #[serde(default)]
    pub routine: Option<String>,
    pub state: SessionState,
    pub started_at: i64,
    pub elapsed_secs: u64,
    pub ended_at: i64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BackupEvent {
    pub ts: i64,
    pub session_id: Option<i64>,
    /// `tamper`, `escalation_denied`, `clock_jump` or `tunnel`.
    pub kind: String,
    #[serde(default)]
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BackupRun {
    pub routine: String,
    /// Local date, `YYYY-MM-DD`.
    pub date: String,
    /// `started` or `skipped`.
    pub outcome: String,
    pub ts: i64,
    #[serde(default)]
    pub session_id: Option<i64>,
}

/// Leeway for clocks that differ a little between machines.
const CLOCK_SLACK_SECS: i64 = 5 * 60;

impl Backup {
    /// Refuses a bundle no daemon could have written: sessions longer than
    /// [`MAX_SESSION`](crate::session::MAX_SESSION), ending before they start,
    /// or anything dated in the future. Overlapping sessions are dropped on
    /// merge instead (`Store::import_backup`), since clock changes can make
    /// genuine ones touch.
    pub fn check(&self, now: i64) -> Result<(), String> {
        let max = crate::session::MAX_SESSION.as_secs();
        let future = |ts: i64| ts > now.saturating_add(CLOCK_SLACK_SECS);
        for s in &self.sessions {
            let what = format!("session {} (started {})", s.id, s.started_at);
            if s.elapsed_secs > max {
                return Err(format!("{what} lasts longer than a session can"));
            }
            if s.ended_at < s.started_at {
                return Err(format!("{what} ends before it starts"));
            }
            if future(s.ended_at) {
                return Err(format!("{what} ends in the future"));
            }
        }
        if let Some(e) = self.events.iter().find(|e| future(e.ts)) {
            return Err(format!("event {} at {} is in the future", e.kind, e.ts));
        }
        if let Some(r) = self.routine_runs.iter().find(|r| future(r.ts)) {
            return Err(format!(
                "routine run {} {} is in the future",
                r.routine, r.date
            ));
        }
        Ok(())
    }

    pub fn new(config: String) -> Self {
        Self {
            format: FORMAT.into(),
            version: VERSION,
            exported_at: 0,
            config,
            sessions: Vec::new(),
            events: Vec::new(),
            routine_runs: Vec::new(),
            free_bank: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn check_refuses_what_no_daemon_writes() {
        let now = 1_700_000_000;
        let session = |started_at: i64, elapsed_secs: u64, ended_at: i64| BackupSession {
            id: 1,
            kind: SessionKind::Stopwatch,
            profile: "deep".into(),
            routine: None,
            state: SessionState::Completed,
            started_at,
            elapsed_secs,
            ended_at,
        };
        let with = |s: BackupSession| {
            let mut b = Backup::new(String::new());
            b.sessions.push(s);
            b
        };
        assert!(
            with(session(now - 7200, 3600, now - 3600))
                .check(now)
                .is_ok()
        );
        let longest = crate::session::MAX_SESSION.as_secs();
        assert!(
            with(session(now - 86_400, longest + 1, now - 1))
                .check(now)
                .is_err()
        );
        assert!(with(session(now - 100, 60, now - 200)).check(now).is_err());
        assert!(with(session(now, 3600, now + 3600)).check(now).is_err());

        let mut b = Backup::new(String::new());
        b.events.push(BackupEvent {
            ts: now + 86_400,
            session_id: None,
            kind: "tamper".into(),
            detail: String::new(),
        });
        assert!(b.check(now).is_err());
    }

    #[test]
    fn round_trips_through_json() {
        let mut b = Backup::new("[session]\ndefault_profile = \"deep\"\n".into());
        b.exported_at = 1_700_000_000;
        b.sessions.push(BackupSession {
            id: 3,
            kind: SessionKind::Countdown { secs: 1500 },
            profile: "deep".into(),
            routine: Some("morning".into()),
            state: SessionState::Completed,
            started_at: 1_699_999_000,
            elapsed_secs: 1500,
            ended_at: 1_700_000_500,
        });
        b.events.push(BackupEvent {
            ts: 1_699_999_100,
            session_id: Some(3),
            kind: "tunnel".into(),
            detail: "ssh -D 1080".into(),
        });
        b.routine_runs.push(BackupRun {
            routine: "morning".into(),
            date: "2026-11-02".into(),
            outcome: "started".into(),
            ts: 1_699_999_000,
            session_id: Some(3),
        });
        let text = serde_json::to_string(&b).unwrap();
        assert_eq!(serde_json::from_str::<Backup>(&text).unwrap(), b);
    }
}
