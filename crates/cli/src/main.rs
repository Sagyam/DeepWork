use std::io::{BufRead, BufReader, IsTerminal, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use deepwork_proto::{Request, Response, SURRENDER_PHRASE, SessionInfo, SessionKind, SessionState};

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
            match status.session {
                Some(s) => print_session(&s),
                None => println!(
                    "No session running. Profiles: {}",
                    status.profiles.join(", ")
                ),
            }
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

fn request(socket: &PathBuf, req: &Request) -> Result<Response> {
    let mut stream = UnixStream::connect(socket)
        .with_context(|| format!("cannot reach deepworkd at {}", socket.display()))?;
    let mut line = serde_json::to_vec(req)?;
    line.push(b'\n');
    stream.write_all(&line)?;
    let mut reply = String::new();
    BufReader::new(stream).read_line(&mut reply)?;
    serde_json::from_str(&reply).context("bad reply from deepworkd")
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
    println!("Session #{} ({kind}, profile {})", s.id, s.profile);
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
