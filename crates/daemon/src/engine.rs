//! The daemon's brain: owns the running session and drives the store, the
//! enforcer and the resolver from requests and a once-a-second tick.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::Result;
use deepwork_proto::{
    ConfigInfo, Finished, FreeInfo, HISTORY_LIMIT, PendingConfig, Request, Response, RoutineInfo,
    SessionInfo, SessionKind, SessionState, Status, Upcoming,
};
use jiff::tz::TimeZone;
use jiff::{SignedDuration, Timestamp, ToSpan, Zoned};
use tracing::{error, info, warn};

use crate::backup::{self, Backup, BackupSession};
use crate::cfgstate::{self, Outcome, Pending};
use crate::clock;
use crate::config::{Config, Profile};
use crate::dns::Resolver;
use crate::enforcer::{EnforcerHandle, Mode};
use crate::free;
use crate::schedule::{self, Occurrence, RunKey};
use crate::session::Session;
use crate::store::{Decision, EventKind, RunOutcome, Store};
use crate::tunnel;
use crate::world;

const PERSIST_EVERY: Duration = Duration::from_secs(5);
const REASSERT_EVERY: Duration = Duration::from_secs(15);
const BROWSER_POLICIES_EVERY: Duration = Duration::from_secs(60);
/// How far ahead routine runs are listed and can be skipped.
const HORIZON: SignedDuration = SignedDuration::from_hours(24);
/// Wait this long before retrying a routine whose session failed to start.
const ROUTINE_RETRY: Duration = Duration::from_secs(60);
/// A reassert interval with at least this much throttled traffic counts as
/// distracted time. Filters out keep-alives from idle background tabs.
const DISTRACTED_BYTES: u64 = 16 * 1024;
/// Wall-clock moves larger than this, relative to boot time, are logged.
const CLOCK_JUMP: SignedDuration = SignedDuration::from_secs(120);
/// Wait this long before retrying inverted-mode enforcement that failed.
const AMBIENT_RETRY: Duration = Duration::from_secs(60);
/// Store key for the free-minute bank.
const BANK_KEY: &str = "free_bank";

pub struct Core {
    cfg: Config,
    config_path: PathBuf,
    /// A loosening change waiting for its delay.
    pending_cfg: Option<Pending>,
    store: Store,
    enforcer: EnforcerHandle,
    resolver: Arc<Resolver>,
    dry_run: bool,
    session: Option<Session>,
    last_tick: Instant,
    last_persist: Instant,
    last_reassert: Instant,
    /// Escalation bookkeeping for the running session. In memory only: a
    /// daemon restart starts the session's escalation over.
    distracted: Duration,
    last_throttled: u64,
    stage: usize,
    last_policies: Option<Instant>,
    tz: TimeZone,
    /// Routine runs from the last few days, mirrored from the store.
    runs: HashMap<RunKey, RunOutcome>,
    routine_retry_at: Option<Instant>,
    last: Option<(Session, i64)>,
    last_wall: Timestamp,
    last_boot: Duration,
    /// Proxies already reported in the running session.
    tunnels: tunnel::Reporter,
    /// Free minutes for inverted mode.
    bank: free::Bank,
    /// The profile enforced outside sessions (inverted mode), if engaged.
    ambient: Option<Profile>,
    ambient_retry_at: Option<Instant>,
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
    clock::unix_now()
}

impl Core {
    pub async fn new(
        (cfg_state, outcome): (cfgstate::State, Outcome),
        config_path: PathBuf,
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
        let since = clock::timestamp()
            .to_zoned(tz.clone())
            .date()
            .checked_sub(3.days())
            .map(|d| d.to_string())
            .unwrap_or_default();
        let runs = store.runs_since(&since)?.into_iter().collect();
        let last = store.last_finished()?;
        let bank = match store.get(BANK_KEY)? {
            Some(text) => serde_json::from_str(&text).unwrap_or_else(|e| {
                error!("free-minute bank unreadable, starting empty: {e}");
                free::Bank::default()
            }),
            None => free::Bank::default(),
        };
        let mut core = Self {
            cfg: cfg_state.config,
            config_path,
            pending_cfg: cfg_state.pending,
            store,
            enforcer,
            resolver,
            dry_run,
            session: None,
            last_tick: now,
            last_persist: now,
            last_reassert: now,
            distracted: Duration::ZERO,
            last_throttled: 0,
            stage: 0,
            last_policies: None,
            tz,
            runs,
            routine_retry_at: None,
            last,
            last_wall: clock::timestamp(),
            last_boot: boottime(),
            tunnels: tunnel::Reporter::default(),
            bank,
            ambient: None,
            ambient_retry_at: None,
        };
        core.log_config_outcome(&outcome);
        match core.store.running_session()? {
            Some(session) => core.resume(session).await?,
            // Clears anything left behind by a crash outside a session.
            None => core.settle().await,
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
        if let Err(e) = self.enforcer.engage(profile.clone(), Mode::Session).await {
            error!("could not re-apply enforcement: {e:#}");
            self.store.log_event(
                unix_now(),
                Some(session.id),
                EventKind::EnforceError,
                &format!("{e:#}"),
            )?;
        }
        self.activate_dns(&profile);
        self.reset_escalation();
        self.tunnels.clear();
        self.store
            .log_event(unix_now(), Some(session.id), EventKind::Resume, "")?;
        self.session = Some(session);
        Ok(())
    }

    fn activate_dns(&self, profile: &Profile) {
        let lists = profile.lists();
        let domains = lists.prime_domains();
        self.resolver.set_rules(Some(lists));
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
            Request::Start {
                kind,
                profile,
                stake,
            } => {
                if let Some(coins) = stake {
                    let secs = match kind {
                        SessionKind::Countdown { secs } => Some(secs),
                        SessionKind::Stopwatch => None,
                    };
                    self.city()?.check_stake(coins, secs)?;
                }
                let name = profile.unwrap_or_else(|| self.cfg.session.default_profile.clone());
                let info = self.begin(kind, name, None, &format!("uid {uid}")).await?;
                if let Some(coins) = stake {
                    let detail = serde_json::to_string(&Decision {
                        coins: Some(coins),
                        ..Decision::default()
                    })
                    .map_err(|e| e.to_string())?;
                    self.store
                        .log_event(unix_now(), Some(info.id), EventKind::StakePlaced, &detail)
                        .map_err(|e| {
                            format!("the session started, but the stake was not recorded: {e:#}")
                        })?;
                }
                Ok(Response::Session(info))
            }
            Request::Skip { routine } => self.skip(routine.as_deref(), uid),
            Request::Gate { service, uid } => Ok(self.gate(&service, uid)),
            Request::ConfigStatus => {
                Ok(Response::Config(self.config_info(match self.pending_cfg {
                    Some(_) => "a loosening change is waiting".into(),
                    None => "no change waiting".into(),
                })))
            }
            Request::ReloadConfig => Ok(Response::Config(self.reload())),
            Request::GetConfig => Ok(Response::ConfigData {
                config: serde_json::to_value(&self.cfg)
                    .map_err(|e| format!("could not read the settings: {e}"))?,
                pending_config: self.pending_config_json()?,
                pending: self.pending_info(),
                message: "settings loaded".into(),
            }),
            Request::SetConfig { config } => self.set_settings(config).await,
            Request::Export => Ok(Response::Backup {
                backup: self.export()?,
            }),
            Request::Import { backup } => self.import(backup).await,
            Request::World => Ok(Response::World(Box::new(self.world()?))),
            Request::History { since } => Ok(Response::History {
                sessions: self.history(since)?,
            }),
            Request::Routines => Ok(Response::Routines {
                routines: self.routines(),
                skip_tokens_per_week: self.cfg.schedule.skip_tokens_per_week,
            }),
            Request::Free { secs } => {
                if !self.cfg.inverted.enabled {
                    return Err(
                        "inverted mode is off: nothing is throttled outside sessions".into(),
                    );
                }
                if self.session.is_some() {
                    return Err("free minutes cannot be spent during a session".into());
                }
                self.bank.spend(secs.map(Duration::from_secs))?;
                let banked = self.bank.balance_secs();
                let note = match secs {
                    Some(s) => format!("up to {s}s of {banked}s banked, uid {uid}"),
                    None => format!("all {banked}s banked, uid {uid}"),
                };
                info!("free time started: {note}");
                self.log(None, EventKind::FreeStart, &note);
                self.save_bank();
                self.sync_ambient().await;
                Ok(Response::Free(
                    self.free_info().ok_or("inverted mode is off")?,
                ))
            }
            Request::FreeStop => {
                if !self.bank.stop() {
                    return Err("free time is not running".into());
                }
                self.end_free(&format!("stopped, uid {uid}")).await;
                Ok(Response::Free(
                    self.free_info().ok_or("inverted mode is off")?,
                ))
            }
            Request::Stop => {
                let min = self.stopwatch_min();
                let session = self.session.as_mut().ok_or("no session is running")?;
                session.stop(min)?;
                let info = session.info(min);
                self.finish().await;
                Ok(Response::Session(info))
            }
            Request::Buy { blueprint } => {
                self.mayor_closed()?;
                let city = self.city()?;
                let b = city.check_buy(&blueprint)?;
                self.decide(
                    EventKind::BlueprintBought,
                    Decision {
                        blueprint: Some(b.id.into()),
                        ..Decision::default()
                    },
                )
            }
            Request::Choose { need, blueprint } => {
                self.mayor_closed()?;
                let city = self.city()?;
                let (_, design) = city.check_choose(&need, blueprint.as_deref())?;
                self.decide(
                    EventKind::NeedChosen,
                    Decision {
                        need: Some(need),
                        blueprint: design.map(str::to_string),
                        ..Decision::default()
                    },
                )
            }
            Request::Pause => {
                self.mayor_closed()?;
                self.city()?.check_pause()?;
                self.decide(EventKind::SitePaused, Decision::default())
            }
            Request::Rename { lot, name } => {
                let (_, name) = self.city()?.check_rename(&lot, &name)?;
                self.decide(
                    EventKind::BuildingRenamed,
                    Decision {
                        lot: Some(lot),
                        name: Some(name.unwrap_or_default()),
                        ..Decision::default()
                    },
                )
            }
            Request::BuyLand { lot } => {
                self.mayor_closed()?;
                self.city()?.check_land(&lot)?;
                self.decide(
                    EventKind::LandBought,
                    Decision {
                        lot: Some(lot),
                        ..Decision::default()
                    },
                )
            }
            Request::Repair { lot } => {
                self.mayor_closed()?;
                self.city()?.check_repair(&lot)?;
                self.decide(
                    EventKind::RepairBought,
                    Decision {
                        lot: Some(lot),
                        ..Decision::default()
                    },
                )
            }
            Request::UpgradeStreet { street } => {
                self.mayor_closed()?;
                self.city()?.check_upgrade(&street)?;
                self.decide(
                    EventKind::StreetUpgraded,
                    Decision {
                        street: Some(street),
                        ..Decision::default()
                    },
                )
            }
            Request::RenameStreet { street, name } => {
                let (_, name) = self.city()?.check_street_name(&street, &name)?;
                self.decide(
                    EventKind::StreetRenamed,
                    Decision {
                        street: Some(street),
                        name: Some(name.unwrap_or_default()),
                        ..Decision::default()
                    },
                )
            }
            Request::Decorate { spot, decoration } => {
                self.mayor_closed()?;
                self.city()?.check_decorate(&spot, &decoration)?;
                self.decide(
                    EventKind::Decorated,
                    Decision {
                        spot: Some(spot),
                        decoration: Some(decoration),
                        ..Decision::default()
                    },
                )
            }
            Request::UseItem { item, lot } => {
                self.mayor_closed()?;
                self.city()?.check_use(&item, lot.as_deref())?;
                self.decide(
                    EventKind::ItemUsed,
                    Decision {
                        item: Some(item),
                        lot,
                        ..Decision::default()
                    },
                )
            }
            Request::Extend { secs } => {
                let min = self.stopwatch_min();
                let session = self.session.as_mut().ok_or("no session is running")?;
                session.extend(secs)?;
                let info = session.info(min);
                let id = session.id;
                self.persist();
                self.log(Some(id), EventKind::Extend, &format!("{secs}s, uid {uid}"));
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
        clock::timestamp().to_zoned(self.tz.clone())
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

    /// Profile names with the default first, so a client that starts a
    /// session without picking one gets the configured default.
    fn profile_names(&self) -> Vec<String> {
        let default = &self.cfg.session.default_profile;
        let mut names: Vec<String> = self.cfg.profiles.keys().cloned().collect();
        names.sort_by_key(|n| n != default);
        names
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
            session: self.session.as_ref().map(|s| {
                let mut info = s.info(min);
                info.distracted_secs = self.distracted.as_secs();
                info.escalation_stage = self.stage as u32;
                info
            }),
            profiles: self.profile_names(),
            dry_run: self.dry_run,
            upcoming,
            heads_up_secs: self.cfg.schedule.heads_up_secs,
            skip_tokens_left: self.skip_tokens_left(&now),
            last: self.last.as_ref().map(|(s, ended_at)| Finished {
                session: s.info(min),
                ended_at: *ended_at,
            }),
            nudge,
            free: self.free_info(),
        }
    }

    fn free_info(&self) -> Option<FreeInfo> {
        let inv = &self.cfg.inverted;
        inv.enabled.then(|| FreeInfo {
            balance_secs: self.bank.balance_secs(),
            spending: self.bank.is_spending(),
            stops_in_secs: self.bank.stops_in(),
            max_bank_secs: u64::from(inv.max_bank_mins) * 60,
            free_mins_per_hour: inv.free_mins_per_hour,
            throttled: self.ambient.is_some(),
        })
    }

    fn save_bank(&self) {
        let text = serde_json::to_string(&self.bank).expect("bank serializes");
        if let Err(e) = self.store.set(BANK_KEY, Some(&text)) {
            error!("could not save the free-minute bank: {e:#}");
        }
    }

    /// Logs the end of free time (already stopped in the bank) and puts the
    /// throttle back.
    async fn end_free(&mut self, why: &str) {
        info!("free time ended: {why}");
        self.log(
            None,
            EventKind::FreeEnd,
            &format!("{why}, {}s left", self.bank.balance_secs()),
        );
        self.save_bank();
        self.sync_ambient().await;
    }

    /// The profile inverted mode wants enforced right now, if any.
    fn wanted_ambient(&self) -> Option<Profile> {
        if self.session.is_some() || self.bank.is_spending() {
            return None;
        }
        self.cfg.ambient_profile().cloned()
    }

    /// Outside a session: brings enforcement in line with inverted mode.
    async fn sync_ambient(&mut self) {
        if self.session.is_some() {
            return;
        }
        let want = self.wanted_ambient();
        if want == self.ambient {
            return;
        }
        match want {
            Some(profile) => {
                if self.ambient_retry_at.is_some_and(|t| Instant::now() < t) {
                    return;
                }
                self.engage_ambient(profile).await;
            }
            None => {
                info!("inverted mode: throttle lifted");
                self.ambient = None;
                self.release().await;
            }
        }
    }

    async fn engage_ambient(&mut self, profile: Profile) {
        match self.enforcer.engage(profile.clone(), Mode::Ambient).await {
            Ok(()) => {
                info!("inverted mode: throttling outside sessions");
                self.activate_dns(&profile);
                self.ambient = Some(profile);
                self.ambient_retry_at = None;
                self.last_reassert = Instant::now();
            }
            Err(e) => {
                error!("could not apply inverted-mode enforcement: {e:#}");
                self.log(
                    None,
                    EventKind::EnforceError,
                    &format!("inverted mode: {e:#}"),
                );
                self.ambient = None;
                self.ambient_retry_at = Some(Instant::now() + AMBIENT_RETRY);
                self.release().await;
            }
        }
    }

    async fn release(&mut self) {
        self.resolver.set_rules(None);
        if let Err(e) = self.enforcer.release().await {
            error!("could not lift enforcement: {e:#}");
        }
    }

    /// With no session running: inverted-mode enforcement if it is wanted,
    /// otherwise none at all.
    async fn settle(&mut self) {
        self.ambient = None;
        match self.wanted_ambient() {
            Some(profile) => self.engage_ambient(profile).await,
            None => self.release().await,
        }
    }

    fn city(&self) -> Result<world::City, String> {
        let facts = self
            .store
            .world_facts()
            .map_err(|e| format!("could not read the ledger: {e:#}"))?;
        Ok(world::City::fold_at(&facts, unix_now(), &self.tz))
    }

    fn world(&self) -> Result<deepwork_proto::World, String> {
        let running = self.session.as_ref().map(|s| world::Running {
            session_id: s.id,
            elapsed_secs: s.elapsed.as_secs(),
            surrendering: s.state == SessionState::Surrendering,
        });
        Ok(self
            .city()?
            .world(running.as_ref(), clock::timestamp(), &self.tz))
    }

    /// The shop and the plan stay shut while a session runs: the session is
    /// for the work, not the game.
    fn mayor_closed(&self) -> Result<(), String> {
        match self.session {
            Some(_) => Err("the mayor's desk opens when the session ends".into()),
            None => Ok(()),
        }
    }

    /// Records a decision the fold was just asked about, and answers with the
    /// world it makes.
    fn decide(&mut self, kind: EventKind, d: Decision) -> Result<Response, String> {
        let detail = serde_json::to_string(&d).map_err(|e| e.to_string())?;
        self.store
            .log_event(unix_now(), None, kind, &detail)
            .map_err(|e| format!("could not record it: {e:#}"))?;
        Ok(Response::World(Box::new(self.world()?)))
    }

    fn history(&self, since: i64) -> Result<Vec<Finished>, String> {
        let min = self.stopwatch_min();
        let sessions = self
            .store
            .finished_since(since, HISTORY_LIMIT)
            .map_err(|e| format!("could not read past sessions: {e:#}"))?;
        Ok(sessions
            .into_iter()
            .map(|(s, ended_at)| Finished {
                session: s.info(min),
                ended_at,
            })
            .collect())
    }

    fn routines(&self) -> Vec<RoutineInfo> {
        self.cfg
            .routines
            .iter()
            .map(|r| RoutineInfo {
                name: r.name.clone(),
                days: r.days.iter().map(|d| d.to_string()).collect(),
                start: r.start.to_string(),
                duration_mins: r.duration_mins,
                profile: r
                    .profile
                    .clone()
                    .unwrap_or_else(|| self.cfg.session.default_profile.clone()),
            })
            .collect()
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

    /// The settings a waiting loosening change would apply.
    fn pending_config_json(&self) -> Result<Option<serde_json::Value>, String> {
        self.pending_cfg
            .as_ref()
            .map(|p| {
                serde_json::to_value(&p.config)
                    .map_err(|e| format!("could not read the waiting settings: {e}"))
            })
            .transpose()
    }

    fn pending_info(&self) -> Option<PendingConfig> {
        self.pending_cfg.as_ref().map(|p| PendingConfig {
            applies_at: p.applies_at,
            applies_in_secs: p.applies_at - unix_now(),
            reasons: p.reasons.clone(),
        })
    }

    fn config_info(&self, message: String) -> ConfigInfo {
        ConfigInfo {
            message,
            pending: self.pending_info(),
        }
    }

    /// Validates settings from the app, writes them to the config file and
    /// makes them the config in effect (or queues a loosening change).
    async fn set_settings(&mut self, value: serde_json::Value) -> Result<Response, String> {
        let cfg: Config =
            serde_json::from_value(value).map_err(|e| format!("invalid settings: {e}"))?;
        cfg.validate()
            .map_err(|e| format!("invalid settings: {e:#}"))?;
        let text = cfg
            .to_toml()
            .map_err(|e| format!("could not write the settings: {e:#}"))?;
        let message = self.apply_config_text(&text).await?;
        Ok(Response::ConfigData {
            config: serde_json::to_value(&self.cfg)
                .map_err(|e| format!("could not read the settings: {e}"))?,
            pending_config: self.pending_config_json()?,
            pending: self.pending_info(),
            message,
        })
    }

    /// Applies config text through the same delay rules as an edited file.
    /// Returns the message for the user.
    async fn apply_config_text(&mut self, text: &str) -> Result<String, String> {
        let before = self.session.as_ref().map(|s| self.profile_for(&s.profile));
        let (state, outcome) = cfgstate::apply(&self.store, &self.config_path, text, unix_now())
            .map_err(|e| format!("could not apply the settings: {e:#}"))?;
        let changed = matches!(outcome, Outcome::Applied);
        self.set_config(state.config);
        self.pending_cfg = state.pending;
        let message = self.log_config_outcome(&outcome);
        if changed {
            self.reapply_session(before).await;
        }
        self.sync_ambient().await;
        Ok(message)
    }

    /// A profile change reaches a running session at once when it tightens
    /// (or is neutral): the UI must not claim a block list is applied when
    /// the session still runs the old one.
    async fn reapply_session(&mut self, before: Option<Profile>) {
        let Some((id, name)) = self.session.as_ref().map(|s| (s.id, s.profile.clone())) else {
            return;
        };
        let profile = self.profile_for(&name);
        if before.as_ref() == Some(&profile) {
            return;
        }
        match self.enforcer.engage(profile.clone(), Mode::Session).await {
            Ok(()) => {
                self.activate_dns(&profile);
                self.reset_escalation();
                info!("re-applied profile {name} to session {id}");
            }
            Err(e) => {
                error!("could not apply the changed profile to session {id}: {e:#}");
                self.log(
                    Some(id),
                    EventKind::EnforceError,
                    &format!("settings: {e:#}"),
                );
            }
        }
    }

    /// Settings and progress in one bundle, for a backup.
    fn export(&self) -> Result<serde_json::Value, String> {
        let mut b = Backup::new(
            self.cfg
                .to_toml()
                .map_err(|e| format!("could not write the settings: {e:#}"))?,
        );
        b.exported_at = unix_now();
        b.sessions = self
            .store
            .all_finished()
            .map_err(|e| format!("could not read past sessions: {e:#}"))?
            .into_iter()
            .map(|(s, ended_at)| BackupSession {
                id: s.id,
                kind: s.kind,
                profile: s.profile,
                routine: s.routine,
                state: s.state,
                started_at: s.started_at,
                elapsed_secs: s.elapsed.as_secs(),
                ended_at,
            })
            .collect();
        b.events = self
            .store
            .penalty_events()
            .map_err(|e| format!("could not read the ledger: {e:#}"))?;
        b.routine_runs = self
            .store
            .all_runs()
            .map_err(|e| format!("could not read routine runs: {e:#}"))?;
        b.free_bank = self
            .store
            .get(BANK_KEY)
            .map_err(|e| format!("could not read the free-minute bank: {e:#}"))?
            .and_then(|text| serde_json::from_str(&text).ok());
        serde_json::to_value(&b).map_err(|e| format!("could not write the backup: {e}"))
    }

    /// Merges a backup: settings and progress. Refused during a session so
    /// the world cannot change under a construction site.
    async fn import(&mut self, value: serde_json::Value) -> Result<Response, String> {
        if self.session.is_some() {
            return Err("end the session before importing a backup".into());
        }
        let b: Backup =
            serde_json::from_value(value).map_err(|e| format!("not a DeepWork backup: {e}"))?;
        if b.format != backup::FORMAT {
            return Err(format!(
                "not a DeepWork backup: unknown format {:?}",
                b.format
            ));
        }
        if b.version > backup::VERSION {
            return Err(format!(
                "this backup is from a newer DeepWork (format {}); update first",
                b.version
            ));
        }
        Config::parse(&b.config)
            .map_err(|e| format!("the backup's settings are invalid: {e:#}"))?;
        let message = self.apply_config_text(&b.config).await?;
        let sessions = self
            .store
            .import_backup(&b)
            .map_err(|e| format!("could not import the progress: {e:#}"))?;
        // Refresh what the daemon mirrors in memory.
        let since = clock::timestamp()
            .to_zoned(self.tz.clone())
            .date()
            .checked_sub(3.days())
            .map(|d| d.to_string())
            .unwrap_or_default();
        self.runs = self
            .store
            .runs_since(&since)
            .map_err(|e| format!("could not reload routine runs: {e:#}"))?
            .into_iter()
            .collect();
        self.last = self
            .store
            .last_finished()
            .map_err(|e| format!("could not reload past sessions: {e:#}"))?;
        let current_balance = self.bank.balance_ms;
        let mut bank: free::Bank = match self
            .store
            .get(BANK_KEY)
            .map_err(|e| format!("could not read the free-minute bank: {e:#}"))?
        {
            Some(text) => serde_json::from_str(&text).unwrap_or_default(),
            None => free::Bank::default(),
        };
        // Merging progress never takes earned time away: an older backup
        // cannot shrink a newer bank. A backup restores the balance, never an
        // active spend.
        bank.stop();
        bank.balance_ms = bank.balance_ms.max(current_balance);
        self.bank = bank;
        self.save_bank();
        self.log(
            None,
            EventKind::ConfigApplied,
            &format!("backup imported: {sessions} new sessions"),
        );
        info!("backup imported: {sessions} new sessions");
        self.sync_ambient().await;
        Ok(Response::Imported {
            sessions,
            message,
            pending: self.pending_info(),
        })
    }

    /// Re-reads the config file (request or SIGHUP).
    pub fn reload(&mut self) -> ConfigInfo {
        let (state, outcome) = match cfgstate::sync(&self.store, &self.config_path, unix_now()) {
            Ok(r) => r,
            Err(e) => return self.config_info(format!("reload failed: {e:#}")),
        };
        self.set_config(state.config);
        self.pending_cfg = state.pending;
        let message = self.log_config_outcome(&outcome);
        self.config_info(message)
    }

    fn set_config(&mut self, cfg: Config) {
        if cfg.dns != self.cfg.dns {
            warn!("[dns] changes take effect when deepworkd restarts");
        }
        self.cfg = cfg;
    }

    fn log_config_outcome(&self, outcome: &Outcome) -> String {
        let message = match outcome {
            Outcome::Unchanged => "config unchanged".to_string(),
            Outcome::Applied => {
                self.log(None, EventKind::ConfigApplied, "immediately");
                "config applied".to_string()
            }
            Outcome::Queued => {
                let reasons = self
                    .pending_cfg
                    .as_ref()
                    .map(|p| p.reasons.join(", "))
                    .unwrap_or_default();
                self.log(None, EventKind::ConfigPending, &reasons);
                format!("the change loosens enforcement ({reasons}); it applies in 24 hours")
            }
            Outcome::StillPending => "the change is still waiting".to_string(),
            Outcome::Cancelled => {
                "pending change cancelled: the file matches the config in effect".to_string()
            }
            Outcome::Rejected(e) => format!("config file ignored, keeping the one in effect: {e}"),
        };
        info!("config: {message}");
        message
    }

    /// Applies a pending change once its delay is over.
    fn check_pending_config(&mut self) {
        let Some(p) = &self.pending_cfg else {
            return;
        };
        if unix_now() < p.applies_at {
            return;
        }
        let p = self.pending_cfg.take().unwrap();
        if let Err(e) = cfgstate::promote(&self.store, &p) {
            error!("could not apply the pending config: {e:#}");
            self.pending_cfg = Some(p);
            return;
        }
        info!(
            "pending config applied after the delay: {}",
            p.reasons.join(", ")
        );
        self.log(None, EventKind::ConfigApplied, "after delay");
        self.set_config(p.config);
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
        let wall = clock::timestamp();
        let boot = boottime();
        let wall_delta = wall.duration_since(self.last_wall);
        let boot_delta =
            SignedDuration::try_from(clock::scale(boot.saturating_sub(self.last_boot)))
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

        // The session's rules replace the ambient ones, or nothing at all
        // if this fails; the next tick puts ambient enforcement back.
        self.ambient = None;
        if let Err(e) = self.enforcer.engage(profile.clone(), Mode::Session).await {
            self.release().await;
            return Err(format!("could not apply network rules: {e:#}"));
        }
        if let Err(e) = self.store.insert_session(&mut session) {
            self.release().await;
            return Err(format!("could not save session: {e:#}"));
        }
        if self.bank.stop() {
            info!("free time ended: session started");
            self.log(
                None,
                EventKind::FreeEnd,
                &format!("session started, {}s left", self.bank.balance_secs()),
            );
            self.save_bank();
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
        self.reset_escalation();
        self.tunnels.clear();
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
        if kind == EventKind::Completed && self.cfg.inverted.enabled {
            let earned = free::earned(&self.cfg.inverted, session.elapsed);
            let added = self.bank.deposit(earned, &self.cfg.inverted);
            info!(
                "earned {}s of free time ({}s banked)",
                added.as_secs(),
                self.bank.balance_secs()
            );
            self.log(
                Some(session.id),
                EventKind::FreeEarned,
                &format!("{}s", added.as_secs()),
            );
            self.save_bank();
        }
        self.last = Some((session, ended_at));
        self.settle().await;
    }

    pub async fn tick(&mut self) {
        let now = Instant::now();
        let delta = clock::scale(now - self.last_tick);
        self.last_tick = now;
        self.check_clock();
        self.check_pending_config();
        if self
            .last_policies
            .is_none_or(|t| now - t >= BROWSER_POLICIES_EVERY)
        {
            self.last_policies = Some(now);
            self.enforcer.sync_browser_policies();
        }

        let Some(session) = self.session.as_mut() else {
            self.tick_outside(now, delta).await;
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
                Ok(found) => {
                    for note in &found.notes {
                        warn!("tamper: {note}");
                        self.log(Some(id), EventKind::Tamper, note);
                    }
                    if found.reprime
                        && let Some(session) = &self.session
                    {
                        let profile = self.profile_for(&session.profile);
                        self.activate_dns(&profile);
                    }
                    self.escalate(id, found.throttled_bytes).await;
                    self.check_tunnels(id).await;
                }
                Err(e) => {
                    error!("re-applying enforcement failed: {e:#}");
                    self.log(Some(id), EventKind::EnforceError, &format!("{e:#}"));
                }
            }
        }
    }

    /// Inverted mode between sessions: spends free time and keeps the
    /// ambient enforcement in place.
    async fn tick_outside(&mut self, now: Instant, delta: Duration) {
        if self.bank.is_spending() {
            if !self.cfg.inverted.enabled {
                self.bank.stop();
                self.end_free("inverted mode turned off").await;
            } else if self.bank.advance(delta) {
                let why = if self.bank.balance_secs() == 0 {
                    "bank empty"
                } else {
                    "time up"
                };
                self.end_free(why).await;
            } else if now - self.last_persist >= PERSIST_EVERY {
                self.persist();
            }
        }
        self.sync_ambient().await;
        let Some(profile) = self.ambient.clone() else {
            return;
        };
        if now - self.last_reassert < REASSERT_EVERY {
            return;
        }
        self.last_reassert = now;
        match self.enforcer.reassert().await {
            Ok(found) => {
                for note in &found.notes {
                    warn!("inverted mode: put back: {note}");
                    self.log(None, EventKind::AmbientRepair, note);
                }
                if found.reprime {
                    self.activate_dns(&profile);
                }
            }
            Err(e) => {
                error!("re-applying inverted-mode enforcement failed: {e:#}");
                self.log(
                    None,
                    EventKind::EnforceError,
                    &format!("inverted mode: {e:#}"),
                );
            }
        }
    }

    /// Logs proxies that get around the throttle; see `tunnel.rs`.
    async fn check_tunnels(&mut self, id: i64) {
        let Ok(found) = tokio::task::spawn_blocking(tunnel::scan).await else {
            return;
        };
        for finding in self.tunnels.due(Instant::now(), found) {
            warn!("tunnel during session {id}: {finding}");
            self.log(Some(id), EventKind::Tunnel, &finding.to_string());
        }
    }

    fn reset_escalation(&mut self) {
        self.distracted = Duration::ZERO;
        self.last_throttled = 0;
        self.stage = 0;
    }

    /// Counts distracted time from the throttle counters and moves to a
    /// harsher stage when one is due.
    async fn escalate(&mut self, id: i64, throttled_bytes: u64) {
        // Counters restart when a device is shaped again.
        let delta = throttled_bytes
            .checked_sub(self.last_throttled)
            .unwrap_or(throttled_bytes);
        self.last_throttled = throttled_bytes;
        if delta >= DISTRACTED_BYTES {
            self.distracted += REASSERT_EVERY;
        }
        let Some(session) = &self.session else {
            return;
        };
        let profile = self.profile_for(&session.profile);
        let (stage, throttle) = profile.throttle_after(self.distracted);
        if stage == self.stage {
            return;
        }
        match self.enforcer.retune(throttle).await {
            Ok(()) => {
                let note = format!(
                    "stage {stage} after {} min: {} kbit/s, +{} ms",
                    self.distracted.as_secs() / 60,
                    throttle.rate_kbit,
                    throttle.rtt_ms
                );
                info!("escalation: {note}");
                self.log(Some(id), EventKind::Escalate, &note);
                self.stage = stage;
            }
            Err(e) => error!("could not escalate the throttle: {e:#}"),
        }
    }

    /// Saves the running session. Called on shutdown too; enforcement is left
    /// in place so stopping the daemon does not end a session.
    pub fn persist(&mut self) {
        self.last_persist = Instant::now();
        if self.bank.is_spending() {
            self.save_bank();
        }
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
