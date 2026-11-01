//! The daemon's brain: owns the running session and drives the store, the
//! enforcer and the resolver from requests and a once-a-second tick.

use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use anyhow::Result;
use deepwork_proto::{Request, Response, SessionKind, SessionState, Status};
use tracing::{error, info, warn};

use crate::config::{Config, Profile};
use crate::dns::Resolver;
use crate::enforcer::EnforcerHandle;
use crate::session::Session;
use crate::store::{EventKind, Store};

const PERSIST_EVERY: Duration = Duration::from_secs(5);
const REASSERT_EVERY: Duration = Duration::from_secs(15);

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
            Request::Status => Ok(Response::Status(Status {
                session: self.session.as_ref().map(|s| s.info(self.stopwatch_min())),
                profiles: self.cfg.profiles.keys().cloned().collect(),
                dry_run: self.dry_run,
            })),
            Request::Start { kind, profile } => self.start(kind, profile, uid).await,
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

    async fn start(
        &mut self,
        kind: SessionKind,
        profile: Option<String>,
        uid: u32,
    ) -> Result<Response, String> {
        if self.session.is_some() {
            return Err("a session is already running".into());
        }
        let name = profile.unwrap_or_else(|| self.cfg.session.default_profile.clone());
        let profile = self
            .cfg
            .profiles
            .get(&name)
            .cloned()
            .ok_or_else(|| format!("no profile named {name:?}"))?;
        let mut session = Session::new(kind, name, unix_now())?;

        if let Err(e) = self.enforcer.engage(profile.clone()).await {
            let _ = self.enforcer.release().await;
            return Err(format!("could not apply network rules: {e:#}"));
        }
        if let Err(e) = self.store.insert_session(&mut session) {
            let _ = self.enforcer.release().await;
            return Err(format!("could not save session: {e:#}"));
        }
        self.activate_dns(&profile);
        self.log(Some(session.id), EventKind::Start, &format!("uid {uid}"));
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
        Ok(Response::Session(info))
    }

    /// Records the end of the current session and lifts enforcement.
    async fn finish(&mut self) {
        let Some(session) = self.session.take() else {
            return;
        };
        info!("session {} ended: {:?}", session.id, session.state);
        if let Err(e) = self.store.save_session(&session, Some(unix_now())) {
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
    }

    pub async fn tick(&mut self) {
        let now = Instant::now();
        let delta = now - self.last_tick;
        self.last_tick = now;

        let Some(session) = self.session.as_mut() else {
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
