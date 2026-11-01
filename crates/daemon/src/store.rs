//! SQLite persistence: sessions and an append-only event ledger. The future
//! game state is derived from the ledger, so nothing here is ever rewritten.

use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result};
use deepwork_proto::{SessionKind, SessionState};
use rusqlite::{Connection, OptionalExtension, params};

use crate::schedule::RunKey;
use crate::session::Session;

const SCHEMA_VERSION: i64 = 3;

pub struct Store {
    conn: Connection,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EventKind {
    Start,
    Resume,
    Completed,
    SurrenderBegin,
    Surrendered,
    Tamper,
    EnforceError,
    Skip,
    /// The wall clock moved relative to boot time. Routines follow the wall
    /// clock, so this can skip one.
    ClockJump,
    /// sudo, su, pkexec or a guarded polkit action refused during a session.
    EscalationDenied,
    /// A config change took effect.
    ConfigApplied,
    /// A loosening config change was queued behind the delay.
    ConfigPending,
    /// The throttle moved to a harsher escalation stage.
    Escalate,
}

/// What happened to a routine run. Each run is recorded once.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RunOutcome {
    Started,
    Skipped,
}

impl RunOutcome {
    fn as_str(self) -> &'static str {
        match self {
            RunOutcome::Started => "started",
            RunOutcome::Skipped => "skipped",
        }
    }

    fn parse(s: &str) -> Option<Self> {
        match s {
            "started" => Some(RunOutcome::Started),
            "skipped" => Some(RunOutcome::Skipped),
            _ => None,
        }
    }
}

impl EventKind {
    fn as_str(self) -> &'static str {
        match self {
            EventKind::Start => "start",
            EventKind::Resume => "resume",
            EventKind::Completed => "completed",
            EventKind::SurrenderBegin => "surrender_begin",
            EventKind::Surrendered => "surrendered",
            EventKind::Tamper => "tamper",
            EventKind::EnforceError => "enforce_error",
            EventKind::Skip => "skip",
            EventKind::ClockJump => "clock_jump",
            EventKind::EscalationDenied => "escalation_denied",
            EventKind::ConfigApplied => "config_applied",
            EventKind::ConfigPending => "config_pending",
            EventKind::Escalate => "escalate",
        }
    }
}

impl Store {
    pub fn open(path: &Path) -> Result<Self> {
        let conn = Connection::open(path).with_context(|| format!("opening {}", path.display()))?;
        Self::init(conn)
    }

    #[cfg(test)]
    pub fn in_memory() -> Result<Self> {
        Self::init(Connection::open_in_memory()?)
    }

    fn init(conn: Connection) -> Result<Self> {
        conn.pragma_update(None, "journal_mode", "WAL")?;
        let version: i64 = conn.pragma_query_value(None, "user_version", |r| r.get(0))?;
        if version < 1 {
            conn.execute_batch(
                "CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY,
                    kind TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at INTEGER NOT NULL,
                    elapsed_ms INTEGER NOT NULL,
                    surrender_left_ms INTEGER,
                    ended_at INTEGER
                );
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY,
                    ts INTEGER NOT NULL,
                    session_id INTEGER,
                    kind TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT ''
                );",
            )?;
        }
        if version < 2 {
            conn.execute_batch(
                "ALTER TABLE sessions ADD COLUMN routine TEXT;
                CREATE TABLE routine_runs (
                    routine TEXT NOT NULL,
                    date TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    session_id INTEGER,
                    PRIMARY KEY (routine, date)
                );",
            )?;
        }
        if version < 3 {
            conn.execute_batch("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);")?;
        }
        conn.pragma_update(None, "user_version", SCHEMA_VERSION)?;
        Ok(Self { conn })
    }

    pub fn insert_session(&self, s: &mut Session) -> Result<()> {
        self.conn.execute(
            "INSERT INTO sessions (kind, profile, state, started_at, elapsed_ms, surrender_left_ms, routine)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                serde_json::to_string(&s.kind)?,
                s.profile,
                state_str(s.state)?,
                s.started_at,
                millis(s.elapsed),
                s.surrender_left.map(millis),
                s.routine,
            ],
        )?;
        s.id = self.conn.last_insert_rowid();
        Ok(())
    }

    pub fn save_session(&self, s: &Session, ended_at: Option<i64>) -> Result<()> {
        self.conn.execute(
            "UPDATE sessions SET state = ?2, elapsed_ms = ?3, surrender_left_ms = ?4, ended_at = ?5
             WHERE id = ?1",
            params![
                s.id,
                state_str(s.state)?,
                millis(s.elapsed),
                s.surrender_left.map(millis),
                ended_at,
            ],
        )?;
        Ok(())
    }

    /// The session that was running when the daemon last stopped, if any.
    pub fn running_session(&self) -> Result<Option<Session>> {
        Ok(self
            .session_where("state IN ('active', 'surrendering') ORDER BY id DESC")?
            .map(|(s, _)| s))
    }

    /// The most recently ended session and when it ended.
    pub fn last_finished(&self) -> Result<Option<(Session, i64)>> {
        Ok(self
            .session_where("ended_at IS NOT NULL ORDER BY ended_at DESC, id DESC")?
            .and_then(|(s, ended)| Some((s, ended?))))
    }

    fn session_where(&self, clause: &str) -> Result<Option<(Session, Option<i64>)>> {
        let sql = format!(
            "SELECT id, kind, profile, state, started_at, elapsed_ms, surrender_left_ms, routine,
                    ended_at
             FROM sessions WHERE {clause} LIMIT 1"
        );
        self.conn
            .query_row(&sql, [], |r| {
                Ok((
                    r.get::<_, i64>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                    r.get::<_, String>(3)?,
                    r.get::<_, i64>(4)?,
                    r.get::<_, i64>(5)?,
                    r.get::<_, Option<i64>>(6)?,
                    r.get::<_, Option<String>>(7)?,
                    r.get::<_, Option<i64>>(8)?,
                ))
            })
            .optional()?
            .map(
                |(
                    id,
                    kind,
                    profile,
                    state,
                    started_at,
                    elapsed,
                    surrender_left,
                    routine,
                    ended,
                )| {
                    let session = Session {
                        id,
                        kind: serde_json::from_str::<SessionKind>(&kind)?,
                        profile,
                        routine,
                        state: serde_json::from_value::<SessionState>(serde_json::Value::String(
                            state,
                        ))?,
                        started_at,
                        elapsed: from_millis(elapsed),
                        surrender_left: surrender_left.map(from_millis),
                    };
                    Ok((session, ended))
                },
            )
            .transpose()
    }

    /// Records what happened to a routine run. Fails if it was already
    /// recorded, so a run can never be used twice.
    pub fn insert_run(
        &self,
        key: &RunKey,
        outcome: RunOutcome,
        ts: i64,
        session_id: Option<i64>,
    ) -> Result<()> {
        self.conn.execute(
            "INSERT INTO routine_runs (routine, date, outcome, ts, session_id)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![key.0, key.1, outcome.as_str(), ts, session_id],
        )?;
        Ok(())
    }

    /// Runs on or after `date` (`YYYY-MM-DD`).
    pub fn runs_since(&self, date: &str) -> Result<Vec<(RunKey, RunOutcome)>> {
        let mut stmt = self
            .conn
            .prepare("SELECT routine, date, outcome FROM routine_runs WHERE date >= ?1")?;
        let rows = stmt.query_map([date], |r| {
            Ok((
                r.get::<_, String>(0)?,
                r.get::<_, String>(1)?,
                r.get::<_, String>(2)?,
            ))
        })?;
        let mut out = Vec::new();
        for row in rows {
            let (routine, date, outcome) = row?;
            if let Some(outcome) = RunOutcome::parse(&outcome) {
                out.push(((routine, date), outcome));
            }
        }
        Ok(out)
    }

    /// Skip tokens spent at or after `ts`.
    pub fn skips_since(&self, ts: i64) -> Result<u32> {
        Ok(self.conn.query_row(
            "SELECT COUNT(*) FROM routine_runs WHERE outcome = 'skipped' AND ts >= ?1",
            [ts],
            |r| r.get(0),
        )?)
    }

    pub fn get(&self, key: &str) -> Result<Option<String>> {
        Ok(self
            .conn
            .query_row("SELECT value FROM kv WHERE key = ?1", [key], |r| r.get(0))
            .optional()?)
    }

    /// Sets `key`, or deletes it for `None`.
    pub fn set(&self, key: &str, value: Option<&str>) -> Result<()> {
        match value {
            Some(v) => self.conn.execute(
                "INSERT INTO kv (key, value) VALUES (?1, ?2)
                 ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                params![key, v],
            )?,
            None => self.conn.execute("DELETE FROM kv WHERE key = ?1", [key])?,
        };
        Ok(())
    }

    pub fn log_event(
        &self,
        ts: i64,
        session_id: Option<i64>,
        kind: EventKind,
        detail: &str,
    ) -> Result<()> {
        self.conn.execute(
            "INSERT INTO events (ts, session_id, kind, detail) VALUES (?1, ?2, ?3, ?4)",
            params![ts, session_id, kind.as_str(), detail],
        )?;
        Ok(())
    }

    #[cfg(test)]
    fn event_kinds(&self) -> Result<Vec<String>> {
        let mut stmt = self.conn.prepare("SELECT kind FROM events ORDER BY id")?;
        let rows = stmt.query_map([], |r| r.get(0))?;
        Ok(rows.collect::<rusqlite::Result<_>>()?)
    }
}

fn state_str(state: SessionState) -> Result<String> {
    match serde_json::to_value(state)? {
        serde_json::Value::String(s) => Ok(s),
        other => anyhow::bail!("unexpected state encoding {other}"),
    }
}

fn millis(d: Duration) -> i64 {
    i64::try_from(d.as_millis()).unwrap_or(i64::MAX)
}

fn from_millis(ms: i64) -> Duration {
    Duration::from_millis(ms.max(0) as u64)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn running_session_round_trip() {
        let store = Store::in_memory().unwrap();
        assert!(store.running_session().unwrap().is_none());

        let mut s = Session::new(SessionKind::Countdown { secs: 1500 }, "deep".into(), 42).unwrap();
        store.insert_session(&mut s).unwrap();
        s.advance(Duration::from_millis(61_500));
        s.surrender(deepwork_proto::SURRENDER_PHRASE, Duration::from_secs(600))
            .unwrap();
        store.save_session(&s, None).unwrap();
        assert_eq!(store.running_session().unwrap().as_ref(), Some(&s));

        s.state = SessionState::Surrendered;
        s.surrender_left = None;
        store.save_session(&s, Some(100)).unwrap();
        assert!(store.running_session().unwrap().is_none());
    }

    #[test]
    fn last_finished_and_routine() {
        let store = Store::in_memory().unwrap();
        assert!(store.last_finished().unwrap().is_none());
        let mut s = Session::new(SessionKind::Countdown { secs: 600 }, "deep".into(), 1).unwrap();
        s.routine = Some("morning".into());
        store.insert_session(&mut s).unwrap();
        s.state = SessionState::Completed;
        store.save_session(&s, Some(700)).unwrap();
        let (last, ended) = store.last_finished().unwrap().unwrap();
        assert_eq!((last, ended), (s, 700));
    }

    #[test]
    fn runs_are_recorded_once() {
        let store = Store::in_memory().unwrap();
        let key = ("morning".to_string(), "2026-11-02".to_string());
        store
            .insert_run(&key, RunOutcome::Skipped, 100, None)
            .unwrap();
        assert!(
            store
                .insert_run(&key, RunOutcome::Started, 200, Some(1))
                .is_err()
        );
        let other = ("morning".to_string(), "2026-11-03".to_string());
        store
            .insert_run(&other, RunOutcome::Started, 300, Some(1))
            .unwrap();
        assert_eq!(
            store.runs_since("2026-11-03").unwrap(),
            [(other, RunOutcome::Started)]
        );
        assert_eq!(store.skips_since(0).unwrap(), 1);
        assert_eq!(store.skips_since(101).unwrap(), 0);
    }

    #[test]
    fn migrates_v1() {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch(
            "CREATE TABLE sessions (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL, profile TEXT NOT NULL,
                state TEXT NOT NULL, started_at INTEGER NOT NULL, elapsed_ms INTEGER NOT NULL,
                surrender_left_ms INTEGER, ended_at INTEGER
            );
            CREATE TABLE events (
                id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, session_id INTEGER,
                kind TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO sessions (kind, profile, state, started_at, elapsed_ms)
                VALUES ('{\"type\":\"stopwatch\"}', 'deep', 'active', 5, 1000);
            PRAGMA user_version = 1;",
        )
        .unwrap();
        let store = Store::init(conn).unwrap();
        let s = store.running_session().unwrap().unwrap();
        assert_eq!((s.routine, s.elapsed), (None, Duration::from_secs(1)));
    }

    #[test]
    fn key_values() {
        let store = Store::in_memory().unwrap();
        assert_eq!(store.get("a").unwrap(), None);
        store.set("a", Some("1")).unwrap();
        store.set("a", Some("2")).unwrap();
        assert_eq!(store.get("a").unwrap().as_deref(), Some("2"));
        store.set("a", None).unwrap();
        assert_eq!(store.get("a").unwrap(), None);
    }

    #[test]
    fn events_append() {
        let store = Store::in_memory().unwrap();
        store.log_event(1, Some(1), EventKind::Start, "").unwrap();
        store
            .log_event(2, Some(1), EventKind::Tamper, "nft table missing")
            .unwrap();
        assert_eq!(store.event_kinds().unwrap(), ["start", "tamper"]);
    }
}
