//! SQLite persistence: sessions and an append-only event ledger. The future
//! game state is derived from the ledger, so nothing here is ever rewritten.

use std::collections::{HashMap, HashSet};
use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result};
use deepwork_proto::{SessionKind, SessionState};
use rusqlite::{Connection, OptionalExtension, params};

use crate::backup::{Backup, BackupEvent, BackupRun};
use crate::schedule::RunKey;
use crate::session::Session;
use crate::world::{Fact, FactKind};

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
    /// A userspace proxy or tunnel (`ssh -D`, Tor, ...) was running during a
    /// session (`tunnel.rs`).
    Tunnel,
    /// A config change took effect.
    ConfigApplied,
    /// A loosening config change was queued behind the delay.
    ConfigPending,
    /// The throttle moved to a harsher escalation stage.
    Escalate,
    /// A completed session added free minutes (inverted mode).
    FreeEarned,
    /// Free minutes started or stopped being spent.
    FreeStart,
    FreeEnd,
    /// Enforcement outside sessions (inverted mode) was changed and put back.
    /// Root is not locked then, and package upgrades can reload firewalls,
    /// so this is recorded but carries no penalty.
    AmbientRepair,
    /// The mayor's decisions (`docs/GAME.md`); `detail` is JSON.
    BlueprintBought,
    NeedChosen,
    SitePaused,
    BuildingRenamed,
    LandBought,
    RepairBought,
    StreetUpgraded,
    StreetRenamed,
    Decorated,
    /// Coins bet on the event's session; `detail` is a decision with `coins`.
    StakePlaced,
    ItemUsed,
    /// A running countdown was made longer; `detail` is the added seconds.
    Extend,
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
            EventKind::Tunnel => "tunnel",
            EventKind::ConfigApplied => "config_applied",
            EventKind::ConfigPending => "config_pending",
            EventKind::Escalate => "escalate",
            EventKind::FreeEarned => "free_earned",
            EventKind::FreeStart => "free_start",
            EventKind::FreeEnd => "free_end",
            EventKind::AmbientRepair => "ambient_repair",
            EventKind::BlueprintBought => "blueprint_bought",
            EventKind::NeedChosen => "need_chosen",
            EventKind::SitePaused => "site_paused",
            EventKind::BuildingRenamed => "building_renamed",
            EventKind::LandBought => "land_bought",
            EventKind::RepairBought => "repair_bought",
            EventKind::StreetUpgraded => "street_upgraded",
            EventKind::StreetRenamed => "street_renamed",
            EventKind::Decorated => "decorated",
            EventKind::StakePlaced => "stake_placed",
            EventKind::ItemUsed => "item_used",
            EventKind::Extend => "extend",
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

    /// Every session that has ended, oldest first, for a backup.
    pub fn all_finished(&self) -> Result<Vec<(Session, i64)>> {
        Ok(self
            .sessions_where("ended_at IS NOT NULL ORDER BY ended_at, id", [])?
            .into_iter()
            .filter_map(|(s, ended)| Some((s, ended?)))
            .collect())
    }

    /// Sessions that ended at or after `since`, newest first, with when they
    /// ended.
    pub fn finished_since(&self, since: i64, limit: usize) -> Result<Vec<(Session, i64)>> {
        Ok(self
            .sessions_where(
                "ended_at >= ?1 ORDER BY ended_at DESC, id DESC LIMIT ?2",
                params![since, limit as i64],
            )?
            .into_iter()
            .filter_map(|(s, ended)| Some((s, ended?)))
            .collect())
    }

    fn session_where(&self, clause: &str) -> Result<Option<(Session, Option<i64>)>> {
        Ok(self
            .sessions_where(&format!("{clause} LIMIT 1"), [])?
            .into_iter()
            .next())
    }

    fn sessions_where(
        &self,
        clause: &str,
        params: impl rusqlite::Params,
    ) -> Result<Vec<(Session, Option<i64>)>> {
        let sql = format!(
            "SELECT id, kind, profile, state, started_at, elapsed_ms, surrender_left_ms, routine,
                    ended_at
             FROM sessions WHERE {clause}"
        );
        let mut stmt = self.conn.prepare(&sql)?;
        let rows = stmt.query_map(params, |r| {
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
        })?;
        let mut out = Vec::new();
        for row in rows {
            let (id, kind, profile, state, started_at, elapsed, surrender_left, routine, ended) =
                row?;
            let session = Session {
                id,
                kind: serde_json::from_str::<SessionKind>(&kind)?,
                profile,
                routine,
                state: serde_json::from_value::<SessionState>(serde_json::Value::String(state))?,
                started_at,
                elapsed: from_millis(elapsed),
                surrender_left: surrender_left.map(from_millis),
            };
            out.push((session, ended));
        }
        Ok(out)
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

    /// Events that shape the world (penalties and the mayor's decisions),
    /// for a backup.
    pub fn penalty_events(&self) -> Result<Vec<BackupEvent>> {
        let mut stmt = self.conn.prepare(
            "SELECT ts, session_id, kind, detail FROM events
             WHERE kind IN ('tamper', 'escalation_denied', 'clock_jump', 'tunnel', 'blueprint_bought', 'need_chosen', 'site_paused', 'building_renamed', 'land_bought', 'repair_bought', 'street_upgraded', 'street_renamed', 'decorated', 'stake_placed', 'item_used')
             ORDER BY ts, id",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok(BackupEvent {
                ts: r.get(0)?,
                session_id: r.get(1)?,
                kind: r.get(2)?,
                detail: r.get(3)?,
            })
        })?;
        Ok(rows.collect::<rusqlite::Result<_>>()?)
    }

    /// Every routine run, for a backup.
    pub fn all_runs(&self) -> Result<Vec<BackupRun>> {
        let mut stmt = self.conn.prepare(
            "SELECT routine, date, outcome, ts, session_id FROM routine_runs ORDER BY date, routine",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok(BackupRun {
                routine: r.get(0)?,
                date: r.get(1)?,
                outcome: r.get(2)?,
                ts: r.get(3)?,
                session_id: r.get(4)?,
            })
        })?;
        Ok(rows.collect::<rusqlite::Result<_>>()?)
    }

    /// Merges a backup into the store. Returns how many sessions were new.
    /// Sessions already present (same profile and start) are skipped, and the
    /// same bundle is never merged twice, so importing is safe to repeat.
    pub fn import_backup(&self, b: &Backup) -> Result<usize> {
        // Exported-at plus the shape: two bundles exported in the same second
        // but with different contents are still merged.
        let marker = format!("{}:{}:{}", b.exported_at, b.sessions.len(), b.events.len());
        if self.get("backup.imported")?.as_deref() == Some(&marker) {
            return Ok(0);
        }
        let tx = self.conn.unchecked_transaction()?;
        let mut added = 0;
        let mut ids: HashMap<i64, i64> = HashMap::new();
        let mut seen: HashSet<i64> = HashSet::new();
        for s in &b.sessions {
            if !matches!(s.state, SessionState::Completed | SessionState::Surrendered) {
                continue;
            }
            let existing: Option<i64> = tx
                .query_row(
                    "SELECT id FROM sessions WHERE started_at = ?1 AND profile = ?2 LIMIT 1",
                    params![s.started_at, s.profile],
                    |r| r.get(0),
                )
                .optional()?;
            if let Some(id) = existing {
                seen.insert(s.id);
                ids.insert(s.id, id);
                continue;
            }
            tx.execute(
                "INSERT INTO sessions
                    (kind, profile, state, started_at, elapsed_ms, surrender_left_ms, routine, ended_at)
                 VALUES (?1, ?2, ?3, ?4, ?5, NULL, ?6, ?7)",
                params![
                    serde_json::to_string(&s.kind)?,
                    s.profile,
                    state_str(s.state)?,
                    s.started_at,
                    i64::try_from(s.elapsed_secs.saturating_mul(1000)).unwrap_or(i64::MAX),
                    s.routine,
                    s.ended_at,
                ],
            )?;
            ids.insert(s.id, tx.last_insert_rowid());
            added += 1;
        }
        for e in &b.events {
            let Some(kind) = penalty_kind(&e.kind) else {
                continue;
            };
            let session_id = match e.session_id {
                None => None,
                // A penalty on a session that was already here is already in
                // the ledger; one on a session missing from the bundle has
                // nowhere to point.
                Some(old) => match ids.get(&old) {
                    Some(new) if !seen.contains(&old) => Some(*new),
                    _ => continue,
                },
            };
            // A later backup of the same machine still carries events from
            // before; they are already here, so match them exactly.
            let duplicate: Option<i64> = tx
                .query_row(
                    "SELECT id FROM events
                     WHERE ts = ?1 AND session_id IS ?2 AND kind = ?3 AND detail = ?4
                     LIMIT 1",
                    params![e.ts, session_id, kind.as_str(), e.detail],
                    |r| r.get(0),
                )
                .optional()?;
            if duplicate.is_none() {
                tx.execute(
                    "INSERT INTO events (ts, session_id, kind, detail) VALUES (?1, ?2, ?3, ?4)",
                    params![e.ts, session_id, kind.as_str(), e.detail],
                )?;
            }
        }
        for r in &b.routine_runs {
            let session_id = r.session_id.and_then(|old| ids.get(&old).copied());
            tx.execute(
                "INSERT OR IGNORE INTO routine_runs (routine, date, outcome, ts, session_id)
                 VALUES (?1, ?2, ?3, ?4, ?5)",
                params![r.routine, r.date, r.outcome, r.ts, session_id],
            )?;
        }
        tx.commit()?;
        if let Some(bank) = &b.free_bank {
            self.set("free_bank", Some(&bank.to_string()))?;
        }
        self.set("backup.imported", Some(&marker))?;
        Ok(added)
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

    /// Everything the world is built from: ended sessions and penalty events.
    pub fn world_facts(&self) -> Result<Vec<Fact>> {
        let mut facts = Vec::new();
        let mut stmt = self.conn.prepare(
            "SELECT id, state, elapsed_ms, ended_at FROM sessions
             WHERE ended_at IS NOT NULL AND state IN ('completed', 'surrendered')",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok((
                r.get::<_, i64>(0)?,
                r.get::<_, String>(1)?,
                r.get::<_, i64>(2)?,
                r.get::<_, i64>(3)?,
            ))
        })?;
        for row in rows {
            let (id, state, elapsed, ended_at) = row?;
            let secs = from_millis(elapsed).as_secs();
            let kind = match state.as_str() {
                "completed" => FactKind::Completed { secs },
                _ => FactKind::Surrendered { secs },
            };
            facts.push(Fact {
                ts: ended_at,
                seq: 0,
                session_id: Some(id),
                kind,
            });
        }
        let mut stmt = self.conn.prepare(
            "SELECT ts, session_id, kind, detail, id FROM events
             WHERE kind IN ('tamper', 'escalation_denied', 'clock_jump', 'tunnel', 'blueprint_bought', 'need_chosen', 'site_paused', 'building_renamed', 'land_bought', 'repair_bought', 'street_upgraded', 'street_renamed', 'decorated', 'stake_placed', 'item_used')",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok((
                r.get::<_, i64>(0)?,
                r.get::<_, Option<i64>>(1)?,
                r.get::<_, String>(2)?,
                r.get::<_, String>(3)?,
                r.get::<_, i64>(4)?,
            ))
        })?;
        for row in rows {
            let (ts, session_id, kind, detail, seq) = row?;
            let Some(kind) = world_fact(&kind, &detail) else {
                continue;
            };
            facts.push(Fact {
                ts,
                seq,
                session_id,
                kind,
            });
        }
        Ok(facts)
    }

    #[cfg(test)]
    fn event_kinds(&self) -> Result<Vec<String>> {
        let mut stmt = self.conn.prepare("SELECT kind FROM events ORDER BY id")?;
        let rows = stmt.query_map([], |r| r.get(0))?;
        Ok(rows.collect::<rusqlite::Result<_>>()?)
    }
}

/// The detail of a mayor's decision.
#[derive(Debug, Default, serde::Serialize, serde::Deserialize)]
pub struct Decision {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub blueprint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub need: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub lot: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub street: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub spot: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub decoration: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub item: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub coins: Option<u64>,
}

fn world_fact(kind: &str, detail: &str) -> Option<FactKind> {
    let d = || serde_json::from_str::<Decision>(detail).unwrap_or_default();
    Some(match kind {
        "tamper" => FactKind::Tamper,
        "escalation_denied" => FactKind::Denied,
        "tunnel" => FactKind::Tunnel,
        "clock_jump" => FactKind::ClockJump,
        "blueprint_bought" => FactKind::Bought {
            blueprint: d().blueprint?,
        },
        "need_chosen" => {
            let d = d();
            FactKind::Chose {
                need: d.need?,
                blueprint: d.blueprint,
            }
        }
        "site_paused" => FactKind::Paused,
        "building_renamed" => {
            let d = d();
            FactKind::Renamed {
                lot: d.lot?,
                name: d.name.unwrap_or_default(),
            }
        }
        "land_bought" => FactKind::LandBought { lot: d().lot? },
        "repair_bought" => FactKind::RepairBought { lot: d().lot? },
        "street_upgraded" => FactKind::StreetUpgraded {
            street: d().street?,
        },
        "street_renamed" => {
            let d = d();
            FactKind::StreetRenamed {
                street: d.street?,
                name: d.name.unwrap_or_default(),
            }
        }
        "decorated" => {
            let d = d();
            FactKind::Decorated {
                spot: d.spot?,
                decoration: d.decoration?,
            }
        }
        "stake_placed" => FactKind::Staked { coins: d().coins? },
        "item_used" => {
            let d = d();
            FactKind::ItemUsed {
                item: d.item?,
                lot: d.lot,
            }
        }
        _ => return None,
    })
}

fn penalty_kind(kind: &str) -> Option<EventKind> {
    match kind {
        "tamper" => Some(EventKind::Tamper),
        "escalation_denied" => Some(EventKind::EscalationDenied),
        "clock_jump" => Some(EventKind::ClockJump),
        "tunnel" => Some(EventKind::Tunnel),
        "blueprint_bought" => Some(EventKind::BlueprintBought),
        "need_chosen" => Some(EventKind::NeedChosen),
        "site_paused" => Some(EventKind::SitePaused),
        "building_renamed" => Some(EventKind::BuildingRenamed),
        "land_bought" => Some(EventKind::LandBought),
        "repair_bought" => Some(EventKind::RepairBought),
        "street_upgraded" => Some(EventKind::StreetUpgraded),
        "street_renamed" => Some(EventKind::StreetRenamed),
        "decorated" => Some(EventKind::Decorated),
        "stake_placed" => Some(EventKind::StakePlaced),
        "item_used" => Some(EventKind::ItemUsed),
        _ => None,
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
    fn finished_since_newest_first() {
        let store = Store::in_memory().unwrap();
        let mut ended = Vec::new();
        for end in [100, 300, 200] {
            let mut s = Session::new(
                SessionKind::Countdown { secs: 600 },
                "deep".into(),
                end - 50,
            )
            .unwrap();
            store.insert_session(&mut s).unwrap();
            s.state = SessionState::Completed;
            store.save_session(&s, Some(end)).unwrap();
            ended.push(s);
        }
        let mut running =
            Session::new(SessionKind::Countdown { secs: 600 }, "deep".into(), 400).unwrap();
        store.insert_session(&mut running).unwrap();

        let got: Vec<i64> = store
            .finished_since(150, 10)
            .unwrap()
            .into_iter()
            .map(|(_, e)| e)
            .collect();
        assert_eq!(got, [300, 200]);
        assert_eq!(store.finished_since(0, 1).unwrap()[0].0, ended[1]);
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
    fn world_facts_from_sessions_and_events() {
        let store = Store::in_memory().unwrap();
        let mut done =
            Session::new(SessionKind::Countdown { secs: 600 }, "deep".into(), 1).unwrap();
        store.insert_session(&mut done).unwrap();
        done.advance(Duration::from_secs(600));
        store.save_session(&done, Some(700)).unwrap();
        let mut running = Session::new(SessionKind::Stopwatch, "deep".into(), 800).unwrap();
        store.insert_session(&mut running).unwrap();
        store
            .log_event(900, Some(running.id), EventKind::Tamper, "x")
            .unwrap();
        store
            .log_event(901, Some(running.id), EventKind::Escalate, "")
            .unwrap();
        store
            .log_event(902, None, EventKind::ClockJump, "")
            .unwrap();
        store
            .log_event(
                903,
                None,
                EventKind::NeedChosen,
                r#"{"need":"hamlet-homes","blueprint":"c1"}"#,
            )
            .unwrap();
        store
            .log_event(904, None, EventKind::BlueprintBought, "{}")
            .unwrap();
        let mut facts = store.world_facts().unwrap();
        facts.sort();
        let kinds: Vec<(i64, Option<i64>, FactKind)> = facts
            .into_iter()
            .map(|f| (f.ts, f.session_id, f.kind))
            .collect();
        assert_eq!(
            kinds,
            [
                (700, Some(done.id), FactKind::Completed { secs: 600 }),
                (900, Some(running.id), FactKind::Tamper),
                (902, None, FactKind::ClockJump),
                (
                    903,
                    None,
                    FactKind::Chose {
                        need: "hamlet-homes".into(),
                        blueprint: Some("c1".into())
                    }
                ),
            ],
            "a decision without its detail is dropped"
        );
    }

    #[test]
    fn backup_round_trip_merges_once() {
        let from = Store::in_memory().unwrap();
        let mut s =
            Session::new(SessionKind::Countdown { secs: 1500 }, "deep".into(), 100).unwrap();
        from.insert_session(&mut s).unwrap();
        s.advance(Duration::from_secs(1500));
        s.state = SessionState::Completed;
        from.save_session(&s, Some(1600)).unwrap();
        from.log_event(1700, Some(s.id), EventKind::Tamper, "nft")
            .unwrap();
        from.insert_run(
            &("morning".into(), "2026-11-02".into()),
            RunOutcome::Started,
            100,
            Some(s.id),
        )
        .unwrap();
        from.set("free_bank", Some(r#"{"balance_ms":60000,"spending":null}"#))
            .unwrap();

        let backup = Backup {
            format: crate::backup::FORMAT.into(),
            version: crate::backup::VERSION,
            exported_at: 1234,
            config: "[profiles.deep]\nrules = []\n".into(),
            sessions: from
                .all_finished()
                .unwrap()
                .into_iter()
                .map(|(s, ended_at)| crate::backup::BackupSession {
                    id: s.id,
                    kind: s.kind,
                    profile: s.profile,
                    routine: s.routine,
                    state: s.state,
                    started_at: s.started_at,
                    elapsed_secs: s.elapsed.as_secs(),
                    ended_at,
                })
                .collect(),
            events: from.penalty_events().unwrap(),
            routine_runs: from.all_runs().unwrap(),
            free_bank: from
                .get("free_bank")
                .unwrap()
                .and_then(|t| serde_json::from_str(&t).ok()),
        };

        let to = Store::in_memory().unwrap();
        assert_eq!(to.import_backup(&backup).unwrap(), 1);
        let (session, ended) = to.last_finished().unwrap().unwrap();
        assert_eq!(
            (session.profile.as_str(), session.elapsed.as_secs(), ended),
            ("deep", 1500, 1600)
        );
        assert_eq!(to.penalty_events().unwrap()[0].session_id, Some(session.id));
        assert_eq!(to.all_runs().unwrap()[0].session_id, Some(session.id));
        assert_eq!(to.get("free_bank").unwrap(), from.get("free_bank").unwrap());
        // Importing the same bundle again changes nothing.
        assert_eq!(to.import_backup(&backup).unwrap(), 0);
        assert_eq!(to.all_finished().unwrap().len(), 1);
        assert_eq!(to.penalty_events().unwrap().len(), 1);
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
