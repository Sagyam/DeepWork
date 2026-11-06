//! `deepwork-agent`: runs in the user's graphical session, polls `deepworkd`
//! and turns its status into desktop notifications. Holds no policy: nudge
//! timing and routines come from the daemon, this only decides what changed.

use std::collections::HashSet;
use std::path::PathBuf;
use std::process::Command;
use std::time::Duration;

use anyhow::Result;
use clap::Parser;
use deepwork_proto::{
    Request, Response, SessionInfo, SessionKind, SessionState, Status, World, WorldCause,
    WorldEvent, WorldEventKind,
};

#[derive(Parser)]
#[command(version, about = "DeepWork desktop notifications")]
struct Args {
    #[arg(long, env = "DEEPWORK_SOCKET", default_value = deepwork_proto::DEFAULT_SOCKET)]
    socket: PathBuf,
    /// Seconds between polls.
    #[arg(long, default_value_t = 2)]
    interval: u64,
    /// Print notifications instead of sending them.
    #[arg(long)]
    print: bool,
}

/// Polls in a row that fail before warning that the daemon is gone.
const DOWN_AFTER: u32 = 3;
/// The world is fetched every this many status polls.
const WORLD_EVERY: u32 = 5;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Urgency {
    Low,
    Normal,
    Critical,
}

impl Urgency {
    fn as_str(self) -> &'static str {
        match self {
            Urgency::Low => "low",
            Urgency::Normal => "normal",
            Urgency::Critical => "critical",
        }
    }
}

/// Notifications that replace their previous copy instead of stacking.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Slot {
    Nudge,
    Daemon,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct Note {
    summary: String,
    body: String,
    urgency: Urgency,
    slot: Option<Slot>,
}

impl Note {
    fn new(urgency: Urgency, summary: impl Into<String>, body: impl Into<String>) -> Self {
        Self {
            summary: summary.into(),
            body: body.into(),
            urgency,
            slot: None,
        }
    }

    fn in_slot(mut self, slot: Slot) -> Self {
        self.slot = Some(slot);
        self
    }
}

/// What the agent remembers between polls.
#[derive(Default)]
struct Watch {
    /// `None` until the first successful poll, so a running session is not
    /// announced as new when the agent starts.
    prev: Option<Status>,
    failures: u32,
    /// `(routine, starts_at)` runs already announced.
    warned: HashSet<(String, i64)>,
    /// The daemon's last nudge level, and how many nudges were shown since
    /// the last session. Shown nudges escalate one step at a time, even if
    /// the daemon's level is already high when the agent first sees it.
    nudge_level: u32,
    nudge_step: u32,
    /// The newest world event seen; outer `None` before the first fetch, so
    /// old losses are not announced again when the agent starts.
    world_seen: Option<Option<WorldEvent>>,
    /// The session of the last award seen, likewise.
    award_seen: Option<Option<i64>>,
}

impl Watch {
    fn on_status(&mut self, cur: Status) -> Vec<Note> {
        let mut notes = Vec::new();
        if self.failures >= DOWN_AFTER {
            notes.push(
                Note::new(
                    Urgency::Low,
                    "DeepWork is back",
                    "deepworkd is reachable again.",
                )
                .in_slot(Slot::Daemon),
            );
        }
        self.failures = 0;
        if let Some(prev) = &self.prev {
            session_changes(prev, &cur, &mut notes);
            free_changes(prev, &cur, &mut notes);
        }
        self.heads_up(&cur, &mut notes);
        self.nudge(&cur, &mut notes);
        self.prev = Some(cur);
        notes
    }

    fn on_error(&mut self) -> Vec<Note> {
        self.failures += 1;
        if self.failures != DOWN_AFTER {
            return Vec::new();
        }
        vec![
            Note::new(
                Urgency::Critical,
                "DeepWork daemon is not running",
                "Sessions and routines are not enforced. `systemctl status deepworkd`",
            )
            .in_slot(Slot::Daemon),
        ]
    }

    /// Announces losses in the world since the last fetch, and what a
    /// completed session earned and built.
    fn on_world(&mut self, w: &World) -> Vec<Note> {
        let award = w.last_award.as_ref().map(|a| a.session_id);
        let award_seen = self.award_seen.replace(award);
        let mut notes = Vec::new();
        if award_seen.is_some_and(|a| a != award)
            && let Some(a) = &w.last_award
        {
            notes.push(award_note(w, a));
        }
        let seen = self.world_seen.replace(w.history.last().cloned());
        let Some(seen) = seen else {
            return notes;
        };
        let new = match &seen {
            None => &w.history[..],
            Some(last) => match w.history.iter().rposition(|e| e == last) {
                Some(i) => &w.history[i + 1..],
                None => {
                    let i = w.history.partition_point(|e| e.ts <= last.ts);
                    &w.history[i..]
                }
            },
        };
        notes.extend(new.iter().filter_map(|e| loss_note(w, e)));
        notes
    }

    fn heads_up(&mut self, cur: &Status, notes: &mut Vec<Note>) {
        let horizon = cur.heads_up_secs as i64;
        self.warned.retain(|(r, at)| {
            cur.upcoming
                .iter()
                .any(|u| &u.routine == r && u.starts_at == *at)
        });
        if cur.session.is_some() {
            return;
        }
        for u in &cur.upcoming {
            if u.skipped || u.starts_in_secs <= 0 || u.starts_in_secs > horizon {
                continue;
            }
            if !self.warned.insert((u.routine.clone(), u.starts_at)) {
                continue;
            }
            let mins = (u.ends_at - u.starts_at) / 60;
            let skip = if cur.skip_tokens_left > 0 {
                format!(
                    "`deepwork skip {}` to skip ({} left this week).",
                    u.routine,
                    tokens(cur.skip_tokens_left)
                )
            } else {
                "No skip tokens left this week.".to_string()
            };
            notes.push(Note::new(
                Urgency::Normal,
                format!(
                    "{} starts in {}",
                    u.routine,
                    fmt_mins(u.starts_in_secs as u64)
                ),
                format!("{mins} min focus, profile {}. {skip}", u.profile),
            ));
        }
    }

    fn nudge(&mut self, cur: &Status, notes: &mut Vec<Note>) {
        let Some(n) = cur.nudge else {
            self.nudge_level = 0;
            self.nudge_step = 0;
            return;
        };
        if n.level <= self.nudge_level {
            return;
        }
        self.nudge_level = n.level;
        self.nudge_step += 1;
        let idle = fmt_mins(n.idle_secs);
        let note = match self.nudge_step {
            1 => Note::new(
                Urgency::Low,
                "Time to focus?",
                format!("No session for {idle}. `deepwork start`"),
            ),
            2 => Note::new(
                Urgency::Normal,
                "Still no focus session",
                format!("{idle} without focus. Start a short one: `deepwork start 25m`"),
            ),
            _ => Note::new(
                Urgency::Critical,
                "You said this mattered",
                format!("{idle} without focus. `deepwork start`"),
            ),
        };
        notes.push(note.in_slot(Slot::Nudge));
    }
}

fn session_changes(prev: &Status, cur: &Status, notes: &mut Vec<Note>) {
    let prev_s = prev.session.as_ref();
    let cur_s = cur.session.as_ref();
    if let Some(p) = prev_s
        && cur_s.is_none_or(|c| c.id != p.id)
    {
        let ended = cur
            .last
            .as_ref()
            .filter(|l| l.session.id == p.id)
            .map(|l| &l.session);
        notes.push(ended_note(ended.unwrap_or(p)));
    }
    let Some(c) = cur_s else {
        return;
    };
    match prev_s {
        Some(p) if p.id == c.id => {
            if c.escalation_stage > p.escalation_stage {
                notes.push(Note::new(
                    Urgency::Normal,
                    "Throttle tightened",
                    format!(
                        "{} on distracting sites this session. They get slower the longer you stay.",
                        fmt_mins(c.distracted_secs)
                    ),
                ));
            }
            if p.state == SessionState::Active && c.state == SessionState::Surrendering {
                notes.push(Note::new(
                    Urgency::Critical,
                    "Surrendering",
                    format!(
                        "Enforcement stays on for {}. Finishing the session instead still counts.",
                        fmt_mins(c.surrender_remaining_secs.unwrap_or(0))
                    ),
                ));
            }
        }
        _ => notes.push(started_note(c)),
    }
}

/// Free minutes in inverted mode: earned, running out, used up.
fn free_changes(prev: &Status, cur: &Status, notes: &mut Vec<Note>) {
    let (Some(p), Some(c)) = (prev.free, cur.free) else {
        return;
    };
    if c.balance_secs > p.balance_secs {
        notes.push(Note::new(
            Urgency::Low,
            "Free time earned",
            format!(
                "+{}, {} banked. `deepwork free` lifts the throttle.",
                fmt_mins(c.balance_secs - p.balance_secs),
                fmt_mins(c.balance_secs)
            ),
        ));
    }
    let left = |f: &deepwork_proto::FreeInfo| f.stops_in_secs.unwrap_or(0);
    if p.spending && c.spending && left(&p) > 60 && left(&c) <= 60 {
        notes.push(Note::new(
            Urgency::Normal,
            "1 minute of free time left",
            "Distracting sites slow down again after that.",
        ));
    }
    if p.spending && !c.spending && cur.session.is_none() {
        notes.push(Note::new(
            Urgency::Normal,
            "Free time over",
            format!(
                "Distracting sites are slowed down again. {} banked.",
                fmt_mins(c.balance_secs)
            ),
        ));
    }
}

fn started_note(s: &SessionInfo) -> Note {
    let what = match s.kind {
        SessionKind::Countdown { .. } => {
            format!("{} focus", fmt_mins(s.remaining_secs.unwrap_or(0)))
        }
        SessionKind::Stopwatch => "Stopwatch".to_string(),
    };
    let summary = match &s.routine {
        Some(r) => format!("Routine {r} started"),
        None => "Focus session started".to_string(),
    };
    Note::new(
        Urgency::Normal,
        summary,
        format!(
            "{what}, profile {}. Distractions are slowed down.",
            s.profile
        ),
    )
}

fn ended_note(s: &SessionInfo) -> Note {
    let focused = fmt_mins(s.elapsed_secs);
    match s.state {
        SessionState::Surrendered => Note::new(
            Urgency::Critical,
            "Session surrendered",
            format!("{focused} focused before giving up."),
        ),
        _ => Note::new(
            Urgency::Normal,
            "Session complete",
            format!("{focused} focused. Nice work."),
        ),
    }
}

fn plot_name(w: &World, index: u32) -> Option<&str> {
    w.plots
        .iter()
        .find(|p| p.index == index)
        .map(|p| p.name.as_str())
}

fn award_note(w: &World, a: &deepwork_proto::Award) -> Note {
    let mut body = Vec::new();
    let finished: Vec<&str> = a.finished.iter().filter_map(|&i| plot_name(w, i)).collect();
    if !finished.is_empty() {
        body.push(format!("Finished {}.", finished.join(", ")));
    }
    match w.sites.iter().find(|s| s.active) {
        Some(s) => body.push(format!(
            "{}: {} of {} built.",
            s.name,
            fmt_mins(s.done_secs),
            fmt_mins(s.build_secs)
        )),
        None if w.idle_secs > 0 => body.push(format!(
            "{} of crew hours wait: pick what to build next.",
            fmt_mins(w.idle_secs)
        )),
        None => body.push("Pick what to build next.".into()),
    }
    if a.rested_bonus > 0 {
        body.push("Welcome back: double coins.".into());
    }
    if a.freeze_earned {
        body.push("A streak freeze earned.".into());
    }
    if a.freezes_used > 0 {
        body.push("A streak freeze saved your streak.".into());
    }
    Note::new(Urgency::Low, format!("+{} coins", a.coins), body.join(" "))
}

fn loss_note(w: &World, e: &WorldEvent) -> Option<Note> {
    let ruined = match e.ruined.len() {
        0 => String::new(),
        1 => " One is in ruins.".into(),
        n => format!(" {n} are in ruins."),
    };
    let repair = "Completed sessions repair them.";
    let note = match e.kind {
        WorldEventKind::Built | WorldEventKind::Repaired | WorldEventKind::Graduated => {
            return None;
        }
        WorldEventKind::Collapsed => {
            let burned = e.plots.len().saturating_sub(1);
            let fire = match burned {
                0 => String::new(),
                _ => format!(" Fire spread to {}.{ruined} {repair}", buildings(burned)),
            };
            Note::new(
                Urgency::Critical,
                "Your city burned",
                format!("Surrendering built nothing and earned nothing.{fire}"),
            )
        }
        WorldEventKind::Quake => Note::new(
            Urgency::Critical,
            "Earthquake",
            format!(
                "Tampering with DeepWork damaged {}.{ruined} {repair}",
                buildings(e.plots.len())
            ),
        ),
        WorldEventKind::Damaged if e.plots.is_empty() => return None,
        WorldEventKind::Damaged => {
            let why = match e.cause {
                WorldCause::ClockJump => "Changing the clock",
                WorldCause::Tunnel => "Tunnelling around the throttle",
                _ => "Asking for root during a session",
            };
            Note::new(
                Urgency::Normal,
                "A building was damaged",
                format!(
                    "{why} damaged {}.{ruined}",
                    e.plots
                        .first()
                        .and_then(|&i| plot_name(w, i))
                        .unwrap_or("your newest building")
                ),
            )
        }
    };
    Some(note)
}

fn buildings(n: usize) -> String {
    match n {
        1 => "1 building".into(),
        _ => format!("{n} buildings"),
    }
}

fn tokens(n: u32) -> String {
    match n {
        1 => "1 skip token".into(),
        _ => format!("{n} skip tokens"),
    }
}

fn fmt_mins(secs: u64) -> String {
    let mins = secs.div_ceil(60);
    match mins {
        0..60 => format!("{mins} min"),
        _ if mins.is_multiple_of(60) => format!("{} h", mins / 60),
        _ => format!("{} h {} min", mins / 60, mins % 60),
    }
}

/// Sends notifications through `notify-send`, replacing the previous one in
/// the same slot.
struct Notifier {
    print: bool,
    nudge_id: Option<String>,
    daemon_id: Option<String>,
}

impl Notifier {
    fn send(&mut self, note: &Note) {
        if self.print {
            println!(
                "[{}] {}: {}",
                note.urgency.as_str(),
                note.summary,
                note.body
            );
            return;
        }
        let mut cmd = Command::new("notify-send");
        cmd.args(["--app-name=DeepWork", "--print-id"])
            .arg(format!("--urgency={}", note.urgency.as_str()));
        let slot = match note.slot {
            Some(Slot::Nudge) => Some(&mut self.nudge_id),
            Some(Slot::Daemon) => Some(&mut self.daemon_id),
            None => None,
        };
        if let Some(Some(id)) = slot.as_deref() {
            cmd.arg(format!("--replace-id={id}"));
        }
        cmd.arg("--").arg(&note.summary).arg(&note.body);
        match cmd.output() {
            Ok(out) if out.status.success() => {
                if let Some(slot) = slot {
                    let id = String::from_utf8_lossy(&out.stdout).trim().to_string();
                    *slot = (!id.is_empty()).then_some(id);
                }
            }
            Ok(out) => eprintln!(
                "notify-send failed: {}",
                String::from_utf8_lossy(&out.stderr).trim()
            ),
            Err(e) => eprintln!("cannot run notify-send: {e}"),
        }
    }
}

fn main() -> Result<()> {
    let args = Args::parse();
    let mut watch = Watch::default();
    let mut notifier = Notifier {
        print: args.print,
        nudge_id: None,
        daemon_id: None,
    };
    let interval = Duration::from_secs(args.interval.max(1));
    let mut poll = 0u32;
    loop {
        let mut notes = match deepwork_proto::request(&args.socket, &Request::Status) {
            Ok(Response::Status(status)) => watch.on_status(*status),
            _ => watch.on_error(),
        };
        if poll.is_multiple_of(WORLD_EVERY)
            && let Ok(Response::World(world)) =
                deepwork_proto::request(&args.socket, &Request::World)
        {
            notes.extend(watch.on_world(&world));
        }
        for note in &notes {
            notifier.send(note);
        }
        poll = poll.wrapping_add(1);
        std::thread::sleep(interval);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use deepwork_proto::{Finished, Nudge, Upcoming};

    fn status() -> Status {
        Status {
            session: None,
            profiles: vec!["deep".into()],
            dry_run: false,
            upcoming: Vec::new(),
            heads_up_secs: 300,
            skip_tokens_left: 2,
            last: None,
            nudge: None,
            free: None,
        }
    }

    fn session(id: i64, state: SessionState) -> SessionInfo {
        SessionInfo {
            id,
            kind: SessionKind::Countdown { secs: 1500 },
            profile: "deep".into(),
            routine: None,
            state,
            started_at: 0,
            elapsed_secs: 600,
            remaining_secs: Some(900),
            stop_locked_secs: 0,
            surrender_remaining_secs: Some(600),
            distracted_secs: 0,
            escalation_stage: 0,
        }
    }

    fn world(history: Vec<WorldEvent>) -> World {
        World {
            history,
            ..World::default()
        }
    }

    fn world_event(
        ts: i64,
        kind: WorldEventKind,
        cause: WorldCause,
        plots: Vec<u32>,
    ) -> WorldEvent {
        WorldEvent {
            ts,
            kind,
            cause,
            session_id: None,
            plots,
            ruined: Vec::new(),
        }
    }

    #[test]
    fn world_losses() {
        let mut w = Watch::default();
        let built = world_event(1, WorldEventKind::Built, WorldCause::Completed, vec![0]);
        let quake = world_event(2, WorldEventKind::Quake, WorldCause::Tamper, vec![0, 1]);
        // Losses from before the agent started are not announced.
        assert!(
            w.on_world(&world(vec![built.clone(), quake.clone()]))
                .is_empty()
        );
        assert!(
            w.on_world(&world(vec![built.clone(), quake.clone()]))
                .is_empty()
        );

        let mut fire = world_event(
            3,
            WorldEventKind::Collapsed,
            WorldCause::Surrendered,
            vec![4, 2, 3],
        );
        fire.ruined = vec![3];
        let denied = world_event(
            4,
            WorldEventKind::Damaged,
            WorldCause::EscalationDenied,
            vec![2],
        );
        let notes = w.on_world(&world(vec![built, quake, fire.clone(), denied.clone()]));
        assert_eq!(
            summaries(&notes),
            ["Your city burned", "A building was damaged"]
        );
        assert_eq!(
            notes[0].body,
            "Surrendering built nothing and earned nothing. Fire spread to 2 buildings. One is in \
             ruins. Completed sessions repair them."
        );
        // The seen event rolled out of the history window.
        let rebuilt = world_event(5, WorldEventKind::Built, WorldCause::Completed, vec![4]);
        let quake2 = world_event(6, WorldEventKind::Quake, WorldCause::Tamper, vec![1]);
        let notes = w.on_world(&world(vec![rebuilt, quake2]));
        assert_eq!(summaries(&notes), ["Earthquake"]);
    }

    #[test]
    fn awards_are_announced_once() {
        let mut w = Watch::default();
        let award = |id| deepwork_proto::Award {
            session_id: id,
            ts: 0,
            coins: 216,
            length_bonus: 50,
            streak_bonus: 0,
            rested_bonus: 0,
            build_secs: 6000,
            finished: vec![0],
            freeze_earned: false,
            freezes_used: 0,
        };
        let mut world = World {
            last_award: Some(award(1)),
            plots: vec![deepwork_proto::Plot {
                name: "The Hart house".into(),
                ..deepwork_proto::Plot::default()
            }],
            idle_secs: 600,
            ..World::default()
        };
        assert!(w.on_world(&world).is_empty());
        assert!(w.on_world(&world).is_empty());
        world.last_award = Some(award(2));
        let notes = w.on_world(&world);
        assert_eq!(summaries(&notes), ["+216 coins"]);
        assert_eq!(
            notes[0].body,
            "Finished The Hart house. 10 min of crew hours wait: pick what to build next."
        );
    }

    fn summaries(notes: &[Note]) -> Vec<&str> {
        notes.iter().map(|n| n.summary.as_str()).collect()
    }

    #[test]
    fn session_lifecycle() {
        let mut w = Watch::default();
        let mut s = status();
        s.session = Some(session(1, SessionState::Active));
        // Already running when the agent starts: not announced.
        assert!(w.on_status(s.clone()).is_empty());
        assert!(w.on_status(s.clone()).is_empty());

        let mut escalated = session(1, SessionState::Active);
        escalated.escalation_stage = 1;
        s.session = Some(escalated);
        assert_eq!(summaries(&w.on_status(s.clone())), ["Throttle tightened"]);

        s.session = Some(session(1, SessionState::Surrendering));
        assert_eq!(summaries(&w.on_status(s.clone())), ["Surrendering"]);

        s.session = None;
        s.last = Some(Finished {
            session: session(1, SessionState::Surrendered),
            ended_at: 0,
        });
        assert_eq!(summaries(&w.on_status(s.clone())), ["Session surrendered"]);

        s.session = Some(session(2, SessionState::Active));
        assert_eq!(summaries(&w.on_status(s)), ["Focus session started"]);
    }

    #[test]
    fn free_time() {
        let free = |balance_secs, stops_in_secs: Option<u64>| deepwork_proto::FreeInfo {
            balance_secs,
            spending: stops_in_secs.is_some(),
            stops_in_secs,
            max_bank_secs: 7200,
            free_mins_per_hour: 12,
            throttled: stops_in_secs.is_none(),
        };
        let mut w = Watch::default();
        let mut s = status();
        s.free = Some(free(0, None));
        assert!(w.on_status(s.clone()).is_empty());
        s.free = Some(free(300, None));
        assert_eq!(summaries(&w.on_status(s.clone())), ["Free time earned"]);
        s.free = Some(free(200, Some(61)));
        assert!(w.on_status(s.clone()).is_empty());
        s.free = Some(free(199, Some(60)));
        assert_eq!(
            summaries(&w.on_status(s.clone())),
            ["1 minute of free time left"]
        );
        s.free = Some(free(139, None));
        assert_eq!(summaries(&w.on_status(s)), ["Free time over"]);
    }

    #[test]
    fn heads_up_once_per_run() {
        let mut w = Watch::default();
        let mut s = status();
        let mut u = Upcoming {
            routine: "morning".into(),
            profile: "deep".into(),
            starts_at: 1000,
            ends_at: 1000 + 5400,
            starts_in_secs: 600,
            skipped: false,
        };
        s.upcoming = vec![u.clone()];
        assert!(w.on_status(s.clone()).is_empty());
        u.starts_in_secs = 300;
        s.upcoming = vec![u.clone()];
        let notes = w.on_status(s.clone());
        assert_eq!(summaries(&notes), ["morning starts in 5 min"]);
        assert!(notes[0].body.contains("deepwork skip morning"));
        u.starts_in_secs = 298;
        s.upcoming = vec![u.clone()];
        assert!(w.on_status(s.clone()).is_empty());

        // A skipped run is not announced.
        let mut w = Watch::default();
        u.skipped = true;
        s.upcoming = vec![u];
        assert!(w.on_status(s).is_empty());
    }

    #[test]
    fn nudges_escalate_and_reset() {
        let mut w = Watch::default();
        let mut s = status();
        let at = |level| {
            Some(Nudge {
                level,
                idle_secs: 1800 + u64::from(level - 1) * 900,
            })
        };
        s.nudge = at(1);
        let notes = w.on_status(s.clone());
        assert_eq!(notes[0].urgency, Urgency::Low);
        assert_eq!(notes[0].slot, Some(Slot::Nudge));
        assert!(w.on_status(s.clone()).is_empty());
        s.nudge = at(4);
        assert_eq!(w.on_status(s.clone())[0].urgency, Urgency::Normal);
        s.nudge = at(5);
        assert_eq!(w.on_status(s.clone())[0].urgency, Urgency::Critical);
        s.nudge = None;
        assert!(w.on_status(s.clone()).is_empty());
        // Already high when first seen: still starts gently.
        s.nudge = at(6);
        assert_eq!(w.on_status(s)[0].urgency, Urgency::Low);
    }

    #[test]
    fn daemon_down_once() {
        let mut w = Watch::default();
        assert!(w.on_error().is_empty());
        assert!(w.on_error().is_empty());
        assert_eq!(summaries(&w.on_error()), ["DeepWork daemon is not running"]);
        assert!(w.on_error().is_empty());
        assert_eq!(summaries(&w.on_status(status())), ["DeepWork is back"]);
    }

    #[test]
    fn minutes() {
        assert_eq!(fmt_mins(299), "5 min");
        assert_eq!(fmt_mins(5400), "1 h 30 min");
        assert_eq!(fmt_mins(7200), "2 h");
    }
}
