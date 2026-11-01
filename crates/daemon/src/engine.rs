//! The daemon's brain: owns the running session and drives the store, the
//! enforcer and the resolver from requests and a once-a-second tick.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use anyhow::Result;
use deepwork_proto::{
    Finished, Request, Response, SessionInfo, SessionKind, SessionState, Status, Upcoming,
};
use jiff::tz::TimeZone;
use jiff::{SignedDuration, Timestamp, ToSpan, Zoned};
use tracing::{error, info, warn};

use crate::config::{Config, Profile};
use crate::dns::Resolver;
use crate::enforcer::EnforcerHandle;
use crate::schedule::{self, Occurrence, RunKey};
use crate::session::Session;
use crate::store::{EventKind, RunOutcome, Store};

const PERSIST_EVERY: Duration = Duration::from_secs(5);
const REASSERT_EVERY: Duration = Duration::from_secs(15);
/// How far ahead routine runs are listed and can be skipped.
const HORIZON: SignedDuration = SignedDuration::from_hours(24);
/// Wait this long before retrying a routine whose session failed to start.
const ROUTINE_RETRY: Duration = Duration::from_secs(60);
/// Wall-clock moves larger than this, relative to boot time, are logged.
const CLOCK_JUMP: SignedDuration = SignedDuration::from_secs(120);

pub struct Core {
    cfg: Config,
    store: Store,
    enforcer: EnforcerHandle,
    resolver: Arc<Resolver>,
    dry_run: bool,
    session: Option<Session>,
    last_tick: Instant,
    last_persist: Instant,
    last_reassert: Instant,
    tz: TimeZone,
    /// Routine runs from the last few days, mirrored from the store.
    runs: HashMap<RunKey, RunOutcome>,
    routine_retry_at: Option<Instant>,
    last: Option<(Session, i64)>,
    last_wall: Timestamp,
    last_boot: Duration,
}

/// Time since boot, including suspend (`CLOCK_BOOTTIME`).
fn boottime() -> Duration {
    let mut ts = libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    // SAFETY: `ts` is a valid, writable timespec.
    unsafe { libc::clock_gettime(libc::CLOCK_BOOTTIME, &mut ts) };
    Duration::new(
        ts.tv_sec.max(0) as u64,
        ts.tv_nsec.clamp(0, 999_999_999) as u32,
    )
}

fn unix_now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_secs() as i64)
}

impl Core {
    pub async fn new(
        cfg: Config,
        store: Store,
        enforcer: EnforcerHandle,
        resolver: Arc<Resolver>,
        dry_run: bool,
    ) -> Result<Self> {
        let now = Instant::now();
        let tz = TimeZone::try_system().unwrap_or_else(|e| {
            warn!("could not read the local time zone, using UTC for routines: {e}");
            TimeZone::UTC
        });
        let since = Timestamp::now()
            .to_zoned(tz.clone())
            .date()
            .checked_sub(3.days())
            .map(|d| d.to_string())
            .unwrap_or_default();
        let runs = store.runs_since(&since)?.into_iter().collect();
        let last = store.last_finished()?;
        let mut core = Self {
            cfg,
            store,
            enforcer,
            resolver,
            dry_run,
            session: None,
            last_tick: now,
            last_persist: now,
            last_reassert: now,
            tz,
            runs,
            routine_retry_at: None,
            last,
            last_wall: Timestamp::now(),
            last_boot: boottime(),
        };
        match core.store.running_session()? {
            Some(session) => core.resume(session).await?,
            // Clear anything left behind by a crash outside a session.
            None => core.enforcer.release().await?,
        }
        Ok(core)
    }

    fn stopwatch_min(&self) -> Duration {
        Duration::from_secs(self.cfg.session.stopwatch_min_secs)
    }

    /// The profile for a session. Falls back to the default profile if the
    /// config changed while it was running, so enforcement never just stops.
    fn profile_for(&self, name: &str) -> Profile {
        self.cfg
            .profiles
            .get(name)
            .or_else(|| self.cfg.profiles.get(&self.cfg.session.default_profile))
            .cloned()
            .unwrap_or_default()
    }

    async fn resume(&mut self, session: Session) -> Result<()> {
        info!("resuming session {} ({:?})", session.id, session.kind);
        let profile = self.profile_for(&session.profile);
        if let Err(e) = self.enforcer.engage(profile.clone()).await {
            error!("could not re-apply enforcement: {e:#}");
            self.store.log_event(
                unix_now(),
                Some(session.id),
                EventKind::EnforceError,
                &format!("{e:#}"),
            )?;
        }
        self.activate_dns(&profile);
        self.store
            .log_event(unix_now(), Some(session.id), EventKind::Resume, "")?;
        self.session = Some(session);
        Ok(())
    }

    fn activate_dns(&self, profile: &Profile) {
        self.resolver.set_rules(Some(profile.rules.clone()));
        let domains = profile.rules.iter().map(|r| r.domain.clone()).collect();
        tokio::spawn(self.resolver.clone().prime(domains));
    }

    pub async fn handle(&mut self, req: Request, uid: u32) -> Response {
        match self.try_handle(req, uid).await {
            Ok(resp) => resp,
            Err(message) => Response::error(message),
        }
    }

    async fn try_handle(&mut self, req: Request, uid: u32) -> Result<Response, String> {
        match req {
            Request::Status => Ok(Response::Status(Box::new(self.status()))),
            Request::Start { kind, profile } => {
                let name = profile.unwrap_or_else(|| self.cfg.session.default_profile.clone());
                let info = self.begin(kind, name, None, &format!("uid {uid}")).await?;
                Ok(Response::Session(info))
            }
            Request::Skip { routine } => self.skip(routine.as_deref(), uid),
            Request::Gate { service, uid } => Ok(self.gate(&service, uid)),
            Request::Stop => {
                let min = self.stopwatch_min();
                let session = self.session.as_mut().ok_or("no session is running")?;
                session.stop(min)?;
                let info = session.info(min);
                self.finish().await;
                Ok(Response::Session(info))
            }
            Request::Surrender { phrase } => {
                let wait = Duration::from_secs(self.cfg.session.surrender_wait_secs);
                let min = self.stopwatch_min();
                let session = self.session.as_mut().ok_or("no session is running")?;
                session.surrender(&phrase, wait)?;
                let info = session.info(min);
                let id = session.id;
                self.persist();
                self.log(Some(id), EventKind::SurrenderBegin, &format!("uid {uid}"));
                Ok(Response::Session(info))
            }
        }
    }

    fn now(&self) -> Zoned {
        Timestamp::now().to_zoned(self.tz.clone())
    }

    fn occurrences(&self, now: &Zoned) -> Vec<Occurrence> {
        schedule::occurrences(&self.cfg.routines, now, HORIZON)
    }

    fn skip_tokens_left(&self, now: &Zoned) -> u32 {
        let week = schedule::week_start(now).as_second();
        let used = self.store.skips_since(week).unwrap_or_else(|e| {
            error!("could not count skips: {e:#}");
            u32::MAX
        });
        self.cfg.schedule.skip_tokens_per_week.saturating_sub(used)
    }

    fn upcoming(&self, now: &Zoned) -> Vec<Upcoming> {
        self.occurrences(now)
            .into_iter()
            .filter_map(|o| {
                let outcome = self.runs.get(&o.key()).copied();
                (outcome != Some(RunOutcome::Started)).then(|| Upcoming {
                    profile: o
                        .profile
                        .clone()
                        .unwrap_or_else(|| self.cfg.session.default_profile.clone()),
                    starts_at: o.start.as_second(),
                    ends_at: o.end.as_second(),
                    starts_in_secs: o.start.duration_since(now.timestamp()).as_secs(),
                    skipped: outcome == Some(RunOutcome::Skipped),
                    routine: o.routine,
                })
            })
            .collect()
    }

    fn status(&self) -> Status {
        let now = self.now();
        let upcoming = self.upcoming(&now);
        let nudge = if self.session.is_none() {
            let last_end = self
                .last
                .as_ref()
                .and_then(|(_, e)| Timestamp::from_second(*e).ok());
            let next = upcoming
                .iter()
                .find(|u| !u.skipped)
                .and_then(|u| Timestamp::from_second(u.starts_at).ok());
            schedule::nudge(&self.cfg.nudge, &now, last_end, next)
        } else {
            None
        };
        let min = self.stopwatch_min();
        Status {
            session: self.session.as_ref().map(|s| s.info(min)),
            profiles: self.cfg.profiles.keys().cloned().collect(),
            dry_run: self.dry_run,
            upcoming,
            heads_up_secs: self.cfg.schedule.heads_up_secs,
            skip_tokens_left: self.skip_tokens_left(&now),
            last: self.last.as_ref().map(|(s, ended_at)| Finished {
                session: s.info(min),
                ended_at: *ended_at,
            }),
            nudge,
        }
    }

    fn skip(&mut self, routine: Option<&str>, uid: u32) -> Result<Response, String> {
        if let Some(name) = routine
            && !self.cfg.routines.iter().any(|r| r.name == name)
        {
            return Err(format!("no routine named {name:?}"));
        }
        let now = self.now();
        let occ = self
            .occurrences(&now)
            .into_iter()
            .filter(|o| routine.is_none_or(|name| o.routine == name))
            .find(|o| !self.runs.contains_key(&o.key()))
            .ok_or("nothing to skip in the next 24 hours")?;
        let left = self.skip_tokens_left(&now);
        if left == 0 {
            return Err(format!(
                "no skip tokens left this week ({} per week)",
                self.cfg.schedule.skip_tokens_per_week
            ));
        }
        let key = occ.key();
        self.store
            .insert_run(&key, RunOutcome::Skipped, now.timestamp().as_second(), None)
            .map_err(|e| format!("could not record the skip: {e:#}"))?;
        self.runs.insert(key.clone(), RunOutcome::Skipped);
        self.log(
            None,
            EventKind::Skip,
            &format!("{} {} uid {uid}", key.0, key.1),
        );
        info!("skipped routine {} on {}", key.0, key.1);
        let upcoming = self
            .upcoming(&now)
            .into_iter()
            .find(|u| u.routine == key.0 && u.starts_at == occ.start.as_second())
            .ok_or("skipped, but the run vanished")?;
        Ok(Response::Skipped {
            upcoming,
            tokens_left: left - 1,
        })
    }

    /// Decides whether a privilege escalation may go ahead: not while a
    /// session is running. Root is always allowed.
    fn gate(&self, service: &str, uid: Option<u32>) -> Response {
        let allow = |message: &str| Response::Gate {
            allow: true,
            message: message.into(),
        };
        if uid == Some(0) {
            return allow("root");
        }
        let Some(session) = self.session.as_ref().filter(|s| s.is_running()) else {
            return allow("no session");
        };
        let left = match session.info(self.stopwatch_min()) {
            i if i.state == SessionState::Surrendering => format!(
                "surrender finishes in {} min",
                i.surrender_remaining_secs.unwrap_or(0).div_ceil(60)
            ),
            i => match i.remaining_secs {
                Some(rem) => format!("{} min left", rem.div_ceil(60)),
                None => "stopwatch running".into(),
            },
        };
        let who = uid.map(|u| format!(" uid {u}")).unwrap_or_default();
        warn!("refused {service}{who} during session {}", session.id);
        self.log(
            Some(session.id),
            EventKind::EscalationDenied,
            &format!("{service}{who}"),
        );
        Response::Gate {
            allow: false,
            message: format!(
                "deepwork: root access is locked during the focus session ({left}). \
                 TTY root login still works; `deepwork surrender` ends the session."
            ),
        }
    }

    /// Starts the routine run that is due, if any.
    async fn check_routines(&mut self) {
        if self.session.is_some() || self.routine_retry_at.is_some_and(|t| Instant::now() < t) {
            return;
        }
        let now = self.now();
        let occs = self.occurrences(&now);
        let Some((occ, secs)) =
            schedule::due(&occs, now.timestamp(), |o| self.runs.contains_key(&o.key()))
        else {
            return;
        };
        let occ = occ.clone();
        let profile = occ
            .profile
            .clone()
            .unwrap_or_else(|| self.cfg.session.default_profile.clone());
        let kind = SessionKind::Countdown { secs };
        let who = format!("routine {}", occ.routine);
        if let Err(e) = self.begin(kind, profile, Some(&occ), &who).await {
            error!("routine {} could not start: {e}", occ.routine);
            self.log(None, EventKind::EnforceError, &format!("{who}: {e}"));
            self.routine_retry_at = Some(Instant::now() + ROUTINE_RETRY);
        }
    }

    /// Logs a wall-clock change, which could move a routine out of the way.
    fn check_clock(&mut self) {
        let wall = Timestamp::now();
        let boot = boottime();
        let wall_delta = wall.duration_since(self.last_wall);
        let boot_delta = SignedDuration::try_from(boot.saturating_sub(self.last_boot))
            .unwrap_or(SignedDuration::ZERO);
        self.last_wall = wall;
        self.last_boot = boot;
        let drift = wall_delta - boot_delta;
        if drift.abs() > CLOCK_JUMP {
            let note = format!("wall clock moved {:+}s", drift.as_secs());
            warn!("{note}");
            let id = self.session.as_ref().map(|s| s.id);
            self.log(id, EventKind::ClockJump, &note);
        }
    }

    async fn begin(
        &mut self,
        kind: SessionKind,
        name: String,
        routine: Option<&Occurrence>,
        who: &str,
    ) -> Result<SessionInfo, String> {
        if self.session.is_some() {
            return Err("a session is already running".into());
        }
        let profile = self
            .cfg
            .profiles
            .get(&name)
            .cloned()
            .ok_or_else(|| format!("no profile named {name:?}"))?;
        let mut session = Session::new(kind, name, unix_now())?;
        session.routine = routine.map(|o| o.routine.clone());

        if let Err(e) = self.enforcer.engage(profile.clone()).await {
            let _ = self.enforcer.release().await;
            return Err(format!("could not apply network rules: {e:#}"));
        }
        if let Err(e) = self.store.insert_session(&mut session) {
            let _ = self.enforcer.release().await;
            return Err(format!("could not save session: {e:#}"));
        }
        if let Some(occ) = routine {
            let key = occ.key();
            let ts = unix_now();
            if let Err(e) = self
                .store
                .insert_run(&key, RunOutcome::Started, ts, Some(session.id))
            {
                error!("could not record routine run: {e:#}");
            }
            self.runs.insert(key, RunOutcome::Started);
        }
        self.routine_retry_at = None;
        self.activate_dns(&profile);
        self.log(Some(session.id), EventKind::Start, who);
        info!(
            "started session {} ({:?}, profile {})",
            session.id, session.kind, session.profile
        );

        let info = session.info(self.stopwatch_min());
        let now = Instant::now();
        self.last_tick = now;
        self.last_persist = now;
        self.last_reassert = now;
        self.session = Some(session);
        Ok(info)
    }

    /// Records the end of the current session and lifts enforcement.
    async fn finish(&mut self) {
        let Some(session) = self.session.take() else {
            return;
        };
        info!("session {} ended: {:?}", session.id, session.state);
        let ended_at = unix_now();
        if let Err(e) = self.store.save_session(&session, Some(ended_at)) {
            error!("could not save session: {e:#}");
        }
        let kind = match session.state {
            SessionState::Surrendered => EventKind::Surrendered,
            _ => EventKind::Completed,
        };
        self.log(
            Some(session.id),
            kind,
            &format!("{}s", session.elapsed.as_secs()),
        );
        self.resolver.set_rules(None);
        if let Err(e) = self.enforcer.release().await {
            error!("could not lift enforcement: {e:#}");
        }
        self.last = Some((session, ended_at));
    }

    pub async fn tick(&mut self) {
        let now = Instant::now();
        let delta = now - self.last_tick;
        self.last_tick = now;
        self.check_clock();

        let Some(session) = self.session.as_mut() else {
            self.check_routines().await;
            return;
        };
        let id = session.id;
        if session.advance(delta).is_some() {
            self.finish().await;
            return;
        }
        if now - self.last_persist >= PERSIST_EVERY {
            self.persist();
        }
        if now - self.last_reassert >= REASSERT_EVERY {
            self.last_reassert = now;
            match self.enforcer.reassert().await {
                Ok(notes) => {
                    for note in notes {
                        warn!("tamper: {note}");
                        self.log(Some(id), EventKind::Tamper, &note);
                    }
                }
                Err(e) => {
                    error!("re-applying enforcement failed: {e:#}");
                    self.log(Some(id), EventKind::EnforceError, &format!("{e:#}"));
                }
            }
        }
    }

    /// Saves the running session. Called on shutdown too; enforcement is left
    /// in place so stopping the daemon does not end a session.
    pub fn persist(&mut self) {
        self.last_persist = Instant::now();
        if let Some(session) = &self.session
            && let Err(e) = self.store.save_session(session, None)
        {
            error!("could not save session: {e:#}");
        }
    }

    fn log(&self, session_id: Option<i64>, kind: EventKind, detail: &str) {
        if let Err(e) = self.store.log_event(unix_now(), session_id, kind, detail) {
            error!("could not log event: {e:#}");
        }
    }
}
