//! SQLite persistence: sessions and an append-only event ledger. The future
//! game state is derived from the ledger, so nothing here is ever rewritten.

use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result};
use deepwork_proto::{SessionKind, SessionState};
use rusqlite::{Connection, OptionalExtension, params};

use crate::session::Session;

const SCHEMA_VERSION: i64 = 1;

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
        conn.pragma_update(None, "user_version", SCHEMA_VERSION)?;
        Ok(Self { conn })
    }

    pub fn insert_session(&self, s: &mut Session) -> Result<()> {
        self.conn.execute(
            "INSERT INTO sessions (kind, profile, state, started_at, elapsed_ms, surrender_left_ms)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                serde_json::to_string(&s.kind)?,
                s.profile,
                state_str(s.state)?,
                s.started_at,
                millis(s.elapsed),
                s.surrender_left.map(millis),
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
        self.conn
            .query_row(
                "SELECT id, kind, profile, state, started_at, elapsed_ms, surrender_left_ms
                 FROM sessions WHERE state IN ('active', 'surrendering')
                 ORDER BY id DESC LIMIT 1",
                [],
                |r| {
                    Ok((
                        r.get::<_, i64>(0)?,
                        r.get::<_, String>(1)?,
                        r.get::<_, String>(2)?,
                        r.get::<_, String>(3)?,
                        r.get::<_, i64>(4)?,
                        r.get::<_, i64>(5)?,
                        r.get::<_, Option<i64>>(6)?,
                    ))
                },
            )
            .optional()?
            .map(
                |(id, kind, profile, state, started_at, elapsed, surrender_left)| {
                    Ok(Session {
                        id,
                        kind: serde_json::from_str::<SessionKind>(&kind)?,
                        profile,
                        state: serde_json::from_value::<SessionState>(serde_json::Value::String(
                            state,
                        ))?,
                        started_at,
                        elapsed: from_millis(elapsed),
                        surrender_left: surrender_left.map(from_millis),
                    })
                },
            )
            .transpose()
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
    fn events_append() {
        let store = Store::in_memory().unwrap();
        store.log_event(1, Some(1), EventKind::Start, "").unwrap();
        store
            .log_event(2, Some(1), EventKind::Tamper, "nft table missing")
            .unwrap();
        assert_eq!(store.event_kinds().unwrap(), ["start", "tamper"]);
    }
}
