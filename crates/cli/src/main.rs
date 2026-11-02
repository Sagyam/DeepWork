mod skyline;

use std::io::{IsTerminal, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use deepwork_proto::{
    FreeInfo, PendingConfig, Request, Response, SURRENDER_PHRASE, SessionInfo, SessionKind,
    SessionState, Status, Upcoming,
};

#[derive(Parser)]
#[command(version, about = "DeepWork: focus sessions that are hard to escape")]
struct Cli {
    #[arg(long, env = "DEEPWORK_SOCKET", default_value = deepwork_proto::DEFAULT_SOCKET, global = true)]
    socket: PathBuf,
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand)]
enum Command {
    /// Show the current session (default).
    Status {
        /// Print raw JSON.
        #[arg(long)]
        json: bool,
    },
    /// Start a session: a countdown like `25m`, `1h30m` or `90` (minutes), or `--stopwatch`.
    Start {
        duration: Option<String>,
        #[arg(long, conflicts_with = "duration")]
        stopwatch: bool,
        #[arg(long, short)]
        profile: Option<String>,
    },
    /// End a stopwatch session (after its minimum time).
    Stop,
    /// Give up the current session. Takes a while, and it will cost you.
    Surrender,
    /// List the routines and their runs in the next 24 hours.
    Routines,
    /// List sessions that ended in the last few days.
    History {
        #[arg(long, default_value_t = 7)]
        days: u32,
        /// Print raw JSON.
        #[arg(long)]
        json: bool,
    },
    /// Spend a skip token on the next run of a routine (or of any routine).
    Skip { routine: Option<String> },
    /// Show your city: what focus built and what giving in cost.
    World {
        /// Print raw JSON.
        #[arg(long)]
        json: bool,
    },
    /// Inverted mode: spend banked free minutes (all, or e.g. `15m`), lifting
    /// the throttle outside sessions. `--stop` banks the rest again.
    Free {
        duration: Option<String>,
        #[arg(long, conflicts_with = "duration")]
        stop: bool,
    },
    /// Print one line of Waybar-style JSON, for a bar module.
    Bar,
    /// Show the config change waiting behind the 24h loosening delay, reload
    /// the file after editing it, or back up / restore settings and progress.
    Config {
        #[command(subcommand)]
        action: Option<ConfigAction>,
    },
}

#[derive(Subcommand)]
enum ConfigAction {
    /// Re-read the config file. Stricter changes apply now, looser ones in 24h.
    Reload,
    /// Write settings and progress to a JSON backup (`-` or no file: stdout).
    Export { file: Option<PathBuf> },
    /// Merge a backup made by `config export` into this machine.
    Import { file: PathBuf },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command.unwrap_or(Command::Status { json: false }) {
        Command::Status { json } => {
            let resp = request(&cli.socket, &Request::Status)?;
            if json {
                println!("{}", serde_json::to_string(&resp)?);
                return Ok(());
            }
            let Response::Status(status) = expect_ok(resp)? else {
                bail!("unexpected reply")
            };
            if status.dry_run {
                println!("(daemon is in dry-run mode: nothing is enforced)");
            }
            match &status.session {
                Some(s) => print_session(s),
                None => println!(
                    "No session running. Profiles: {}",
                    status.profiles.join(", ")
                ),
            }
            if let Some(u) = status.upcoming.iter().find(|u| !u.skipped) {
                println!("Next routine: {}", describe(u));
            }
            if let Some(f) = &status.free {
                println!("{}", describe_free(f));
            }
        }
        Command::Free { duration, stop } => {
            let req = match (stop, duration) {
                (true, _) => Request::FreeStop,
                (false, d) => Request::Free {
                    secs: d.as_deref().map(parse_duration).transpose()?,
                },
            };
            let Response::Free(f) = expect_ok(request(&cli.socket, &req)?)? else {
                bail!("unexpected reply")
            };
            println!("{}", describe_free(&f));
        }
        Command::Routines => {
            let Response::Routines {
                routines,
                skip_tokens_per_week,
            } = expect_ok(request(&cli.socket, &Request::Routines)?)?
            else {
                bail!("unexpected reply")
            };
            if routines.is_empty() {
                println!("No routines configured.");
            }
            for r in &routines {
                let days = if r.days.is_empty() {
                    "every day".to_string()
                } else {
                    r.days.join(" ")
                };
                println!(
                    "{} at {} for {} min, {days}, profile {}",
                    r.name, r.start, r.duration_mins, r.profile
                );
            }
            let Response::Status(status) = expect_ok(request(&cli.socket, &Request::Status)?)?
            else {
                bail!("unexpected reply")
            };
            println!();
            if status.upcoming.is_empty() {
                println!("No routine runs in the next 24 hours.");
            }
            for u in &status.upcoming {
                println!("  {}", describe(u));
            }
            println!(
                "Skip tokens left this week: {} of {skip_tokens_per_week}",
                status.skip_tokens_left
            );
        }
        Command::History { days, json } => {
            let since = unix_now() - i64::from(days) * 86400;
            let resp = request(&cli.socket, &Request::History { since })?;
            if json {
                println!("{}", serde_json::to_string(&resp)?);
                return Ok(());
            }
            let Response::History { sessions } = expect_ok(resp)? else {
                bail!("unexpected reply")
            };
            if sessions.is_empty() {
                println!("No sessions ended in the last {days} days.");
            }
            let mut focused = 0;
            for f in &sessions {
                let s = &f.session;
                let outcome = match s.state {
                    SessionState::Completed => {
                        focused += s.elapsed_secs;
                        "completed"
                    }
                    SessionState::Surrendered => "SURRENDERED",
                    _ => "ended",
                };
                let routine = s
                    .routine
                    .as_ref()
                    .map(|r| format!(", routine {r}"))
                    .unwrap_or_default();
                let ago = (unix_now() - f.ended_at).max(0) as u64;
                println!(
                    "{:>7} ago  {outcome:<11} {:>8}  profile {}{routine}",
                    fmt_ago(ago),
                    fmt_secs(s.elapsed_secs),
                    s.profile
                );
            }
            if !sessions.is_empty() {
                println!("Focused (completed): {}", fmt_secs(focused));
            }
        }
        Command::Skip { routine } => {
            if !std::io::stdin().is_terminal() {
                bail!("skipping has to be confirmed by hand");
            }
            let Response::Status(status) = expect_ok(request(&cli.socket, &Request::Status)?)?
            else {
                bail!("unexpected reply")
            };
            let Some(next) = status
                .upcoming
                .iter()
                .filter(|u| !u.skipped)
                .find(|u| routine.as_ref().is_none_or(|r| &u.routine == r))
            else {
                bail!("nothing to skip in the next 24 hours");
            };
            if status.skip_tokens_left == 0 {
                bail!("no skip tokens left this week");
            }
            print!(
                "Skip {}? This uses 1 of {} skip tokens left this week. [y/N] ",
                describe(next),
                status.skip_tokens_left
            );
            std::io::stdout().flush()?;
            let mut answer = String::new();
            std::io::stdin().read_line(&mut answer)?;
            if !answer.trim().eq_ignore_ascii_case("y") {
                println!("Not skipped.");
                return Ok(());
            }
            let req = Request::Skip {
                routine: Some(next.routine.clone()),
            };
            let Response::Skipped {
                upcoming,
                tokens_left,
            } = expect_ok(request(&cli.socket, &req)?)?
            else {
                bail!("unexpected reply")
            };
            println!(
                "Skipped {}. Skip tokens left this week: {tokens_left}.",
                describe(&upcoming)
            );
        }
        Command::Config { action } => match action {
            Some(ConfigAction::Export { file }) => {
                let Response::Backup { backup } =
                    expect_ok(request(&cli.socket, &Request::Export)?)?
                else {
                    bail!("unexpected reply")
                };
                let text = serde_json::to_string_pretty(&backup)?;
                match file {
                    Some(path) if path != Path::new("-") => {
                        std::fs::write(&path, format!("{text}\n"))
                            .with_context(|| format!("writing {}", path.display()))?;
                        println!("Wrote {}", path.display());
                    }
                    _ => println!("{text}"),
                }
            }
            Some(ConfigAction::Import { file }) => {
                let text = std::fs::read_to_string(&file)
                    .with_context(|| format!("reading {}", file.display()))?;
                let backup: serde_json::Value = serde_json::from_str(&text)
                    .with_context(|| format!("{} is not a DeepWork backup", file.display()))?;
                let Response::Imported {
                    sessions,
                    message,
                    pending,
                } = expect_ok(request(&cli.socket, &Request::Import { backup })?)?
                else {
                    bail!("unexpected reply")
                };
                println!("{message}");
                println!("Imported {sessions} new session{}.", plural(sessions));
                describe_pending(pending);
            }
            action => {
                let req = match action {
                    Some(ConfigAction::Reload) => Request::ReloadConfig,
                    None => Request::ConfigStatus,
                    _ => unreachable!(),
                };
                let Response::Config(info) = expect_ok(request(&cli.socket, &req)?)? else {
                    bail!("unexpected reply")
                };
                println!("{}", info.message);
                describe_pending(info.pending);
            }
        },
        Command::World { json } => {
            let resp = expect_ok(request(&cli.socket, &Request::World)?)?;
            if json {
                println!("{}", serde_json::to_string(&resp)?);
                return Ok(());
            }
            let Response::World(world) = resp else {
                bail!("unexpected reply")
            };
            let color = std::io::stdout().is_terminal() && std::env::var_os("NO_COLOR").is_none();
            print!("{}", skyline::render(&world, unix_now(), color));
        }
        Command::Bar => {
            let line = match request(&cli.socket, &Request::Status) {
                Ok(Response::Status(status)) => bar(&status),
                _ => serde_json::json!({
                    "text": "focus off",
                    "tooltip": "deepworkd is not reachable",
                    "class": "down",
                }),
            };
            println!("{line}");
        }
        Command::Start {
            duration,
            stopwatch,
            profile,
        } => {
            let kind = match (duration, stopwatch) {
                (_, true) => SessionKind::Stopwatch,
                (Some(d), false) => SessionKind::Countdown {
                    secs: parse_duration(&d)?,
                },
                (None, false) => SessionKind::Countdown { secs: 25 * 60 },
            };
            let Response::Session(s) =
                expect_ok(request(&cli.socket, &Request::Start { kind, profile })?)?
            else {
                bail!("unexpected reply")
            };
            println!("Session started.");
            print_session(&s);
        }
        Command::Stop => {
            let Response::Session(s) = expect_ok(request(&cli.socket, &Request::Stop)?)? else {
                bail!("unexpected reply")
            };
            println!("Session complete: {} focused.", fmt_secs(s.elapsed_secs));
        }
        Command::Surrender => {
            if !std::io::stdin().is_terminal() {
                bail!("surrender has to be typed by hand");
            }
            println!("To surrender, type this exactly:\n\n  {SURRENDER_PHRASE}\n");
            print!("> ");
            std::io::stdout().flush()?;
            let mut phrase = String::new();
            std::io::stdin().read_line(&mut phrase)?;
            let Response::Session(s) =
                expect_ok(request(&cli.socket, &Request::Surrender { phrase })?)?
            else {
                bail!("unexpected reply")
            };
            println!(
                "Surrender started. Blocking stays on for another {}.",
                fmt_secs(s.surrender_remaining_secs.unwrap_or(0))
            );
        }
    }
    Ok(())
}

fn request(socket: &Path, req: &Request) -> Result<Response> {
    deepwork_proto::request(socket, req)
        .with_context(|| format!("cannot reach deepworkd at {}", socket.display()))
}

fn unix_now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_secs() as i64)
}

/// `morning in 4:59 (90 min, profile deep)`.
fn describe(u: &Upcoming) -> String {
    let when = if u.starts_in_secs > 0 {
        format!("in {}", fmt_secs(u.starts_in_secs as u64))
    } else if u.skipped {
        "now".to_string()
    } else {
        "now, after the current session".to_string()
    };
    let mins = (u.ends_at - u.starts_at) / 60;
    let skipped = if u.skipped { " [skipped]" } else { "" };
    format!(
        "{} {when} ({mins} min, profile {}){skipped}",
        u.routine, u.profile
    )
}

/// `Free time: 12:00 left (40:00 banked)` and the like.
fn describe_free(f: &FreeInfo) -> String {
    let banked = fmt_secs(f.balance_secs);
    match f.stops_in_secs {
        Some(left) if f.spending => {
            format!(
                "Free time: {} left, throttle lifted ({banked} banked)",
                fmt_secs(left)
            )
        }
        _ => format!(
            "Inverted mode: {banked} free banked (max {}, {} min per focused hour){}",
            fmt_secs(f.max_bank_secs),
            f.free_mins_per_hour,
            if f.throttled {
                "; distractions throttled"
            } else {
                ""
            }
        ),
    }
}

/// Waybar / Omarchy bar module output.
fn bar(status: &Status) -> serde_json::Value {
    let mut tooltip = Vec::new();
    let (text, class) = if let Some(s) = &status.session {
        let label = s.routine.as_deref().unwrap_or("focus");
        tooltip.push(format!(
            "{label}: {} focused, profile {}",
            fmt_secs(s.elapsed_secs),
            s.profile
        ));
        if s.state == SessionState::Surrendering {
            let left = s.surrender_remaining_secs.unwrap_or(0);
            tooltip.push(format!("surrendering, {} left", fmt_secs(left)));
            (format!("surrender {}", fmt_secs(left)), "surrendering")
        } else if let Some(rem) = s.remaining_secs {
            (format!("● {}", fmt_secs(rem)), "active")
        } else {
            (format!("● +{}", fmt_secs(s.elapsed_secs)), "active")
        }
    } else if let Some(f) = status.free.filter(|f| f.spending) {
        let left = f.stops_in_secs.unwrap_or(0);
        tooltip.push(format!("free time: throttle lifted for {}", fmt_secs(left)));
        (format!("◌ free {}", fmt_secs(left)), "free")
    } else if let Some(u) = status.upcoming.iter().find(|u| {
        !u.skipped && u.starts_in_secs > 0 && u.starts_in_secs <= status.heads_up_secs as i64
    }) {
        (
            format!("{} in {}", u.routine, fmt_secs(u.starts_in_secs as u64)),
            "upcoming",
        )
    } else if let Some(n) = status.nudge {
        tooltip.push(format!(
            "No focus for {} min. `deepwork start`",
            n.idle_secs / 60
        ));
        ("○ focus?".to_string(), "nudge")
    } else {
        ("○".to_string(), "idle")
    };
    if let Some(u) = status.upcoming.iter().find(|u| !u.skipped) {
        tooltip.push(format!("next: {}", describe(u)));
    }
    if let Some(last) = &status.last
        && status.session.is_none()
    {
        let ago = (unix_now() - last.ended_at).max(0) as u64;
        tooltip.push(format!(
            "last: {} focused, ended {} ago",
            fmt_secs(last.session.elapsed_secs),
            fmt_ago(ago)
        ));
    }
    tooltip.push(format!("skip tokens: {}", status.skip_tokens_left));
    if let Some(f) = status.free.filter(|f| !f.spending) {
        tooltip.push(format!(
            "free time banked: {} (`deepwork free`)",
            fmt_secs(f.balance_secs)
        ));
    }
    if status.dry_run {
        tooltip.push("dry run: nothing is enforced".into());
    }
    serde_json::json!({ "text": text, "tooltip": tooltip.join("\n"), "class": class })
}

fn fmt_ago(secs: u64) -> String {
    match secs {
        0..3600 => format!("{} min", secs / 60),
        3600..86400 => format!("{} h", secs / 3600),
        _ => format!("{} d", secs / 86400),
    }
}

fn plural(n: usize) -> &'static str {
    if n == 1 { "" } else { "s" }
}

fn describe_pending(p: Option<PendingConfig>) {
    if let Some(p) = p {
        println!(
            "Waiting change applies in {}:",
            fmt_secs(p.applies_in_secs.max(0) as u64)
        );
        for reason in p.reasons {
            println!("  - {reason}");
        }
    }
}

fn expect_ok(resp: Response) -> Result<Response> {
    match resp {
        Response::Error { message } => bail!(message),
        other => Ok(other),
    }
}

fn print_session(s: &SessionInfo) {
    let kind = match s.kind {
        SessionKind::Countdown { secs } => format!("countdown {}", fmt_secs(secs)),
        SessionKind::Stopwatch => "stopwatch".to_string(),
    };
    let routine = s
        .routine
        .as_ref()
        .map(|r| format!(", routine {r}"))
        .unwrap_or_default();
    println!("Session #{} ({kind}, profile {}{routine})", s.id, s.profile);
    println!("  focused    {}", fmt_secs(s.elapsed_secs));
    if let Some(rem) = s.remaining_secs {
        println!("  remaining  {}", fmt_secs(rem));
    }
    if s.stop_locked_secs > 0 {
        println!("  can stop in {}", fmt_secs(s.stop_locked_secs));
    }
    if s.state == SessionState::Surrendering {
        println!(
            "  surrendering, {} left",
            fmt_secs(s.surrender_remaining_secs.unwrap_or(0))
        );
    }
}

fn fmt_secs(secs: u64) -> String {
    let (h, m, s) = (secs / 3600, secs / 60 % 60, secs % 60);
    if h > 0 {
        format!("{h}:{m:02}:{s:02}")
    } else {
        format!("{m}:{s:02}")
    }
}

/// `90` (minutes), `25m`, `1h`, `1h30m`, `45s`.
fn parse_duration(input: &str) -> Result<u64> {
    let input = input.trim();
    if let Ok(mins) = input.parse::<u64>() {
        return Ok(mins * 60);
    }
    let mut total = 0u64;
    let mut num = String::new();
    for c in input.chars() {
        if c.is_ascii_digit() {
            num.push(c);
            continue;
        }
        let n: u64 = num
            .parse()
            .with_context(|| format!("bad duration {input:?}"))?;
        num.clear();
        total += n * match c {
            'h' => 3600,
            'm' => 60,
            's' => 1,
            _ => bail!("bad duration {input:?}: use units h, m, s"),
        };
    }
    if !num.is_empty() {
        bail!("bad duration {input:?}: missing unit after {num}");
    }
    Ok(total)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn durations() {
        assert_eq!(parse_duration("90").unwrap(), 5400);
        assert_eq!(parse_duration("25m").unwrap(), 1500);
        assert_eq!(parse_duration("1h30m").unwrap(), 5400);
        assert_eq!(parse_duration("45s").unwrap(), 45);
        assert!(parse_duration("1x").is_err());
        assert!(parse_duration("1h30").is_err());
        assert!(parse_duration("m").is_err());
    }

    #[test]
    fn formatting() {
        assert_eq!(fmt_secs(59), "0:59");
        assert_eq!(fmt_secs(3725), "1:02:05");
    }
}
