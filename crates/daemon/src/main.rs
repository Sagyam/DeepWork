mod cfgstate;
mod config;
mod dns;
mod dot;
mod enforcer;
mod engine;
mod free;
mod loosen;
mod nfqueue;
mod schedule;
mod server;
mod session;
mod sni;
mod store;
mod tunnel;
mod world;

use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use clap::Parser;
use tokio::signal::unix::{SignalKind, signal};
use tokio::sync::Mutex;
use tracing::info;

use crate::config::Config;
use crate::dns::Resolver;
use crate::enforcer::EnforcerHandle;
use crate::engine::Core;
use crate::store::Store;

#[derive(Parser)]
#[command(version, about = "DeepWork focus daemon")]
struct Args {
    #[arg(long, default_value = config::DEFAULT_PATH)]
    config: PathBuf,
    /// Defaults to /var/lib/deepwork, or ~/.local/state/deepwork-dev with --dry-run.
    #[arg(long)]
    state_dir: Option<PathBuf>,
    /// Defaults to /run/deepwork/deepworkd.sock, or $XDG_RUNTIME_DIR/deepwork-dev.sock with --dry-run.
    #[arg(long)]
    socket: Option<PathBuf>,
    /// Log nft/tc/ip commands instead of running them. Does not need root.
    #[arg(long)]
    dry_run: bool,
    /// Print the nft ruleset and tc script for a profile (default profile if
    /// none is given), then exit.
    #[arg(long, value_name = "PROFILE")]
    print_rules: Option<Option<String>>,
    /// Apply or remove the managed browser policies (DoH and ECH off), then
    /// exit. The running daemon re-applies them every minute.
    #[arg(long, value_name = "ACTION")]
    browser_policies: Option<PolicyAction>,
}

#[derive(Clone, Copy, clap::ValueEnum)]
enum PolicyAction {
    Apply,
    Remove,
}

fn effective_uid() -> Result<u32> {
    let status = std::fs::read_to_string("/proc/self/status")?;
    status
        .lines()
        .find_map(|l| l.strip_prefix("Uid:"))
        .and_then(|rest| rest.split_whitespace().nth(1))
        .and_then(|uid| uid.parse().ok())
        .context("reading effective uid")
}

/// Tells systemd (`Type=notify`) that the daemon is ready. A no-op elsewhere.
fn notify_ready() {
    use std::os::linux::net::SocketAddrExt;
    use std::os::unix::net::{SocketAddr, UnixDatagram};

    let Some(path) = std::env::var_os("NOTIFY_SOCKET") else {
        return;
    };
    let path = path.to_string_lossy();
    let addr = match path.strip_prefix('@') {
        Some(name) => SocketAddr::from_abstract_name(name.as_bytes()),
        None => SocketAddr::from_pathname(path.as_ref()),
    };
    let result = addr.and_then(|addr| UnixDatagram::unbound()?.send_to_addr(b"READY=1", &addr));
    if let Err(e) = result {
        tracing::warn!("could not notify systemd: {e}");
    }
}

fn default_paths(dry_run: bool) -> (PathBuf, PathBuf) {
    if !dry_run {
        return (
            PathBuf::from("/var/lib/deepwork"),
            PathBuf::from(deepwork_proto::DEFAULT_SOCKET),
        );
    }
    let home = std::env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| "/tmp".into());
    let state = std::env::var_os("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| home.join(".local/state"))
        .join("deepwork-dev");
    let runtime = std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| "/tmp".into());
    (state, runtime.join("deepwork-dev.sock"))
}

fn print_rules(cfg: &Config, profile: Option<&str>) -> Result<()> {
    let name = profile.unwrap_or(&cfg.session.default_profile);
    let Some(profile) = cfg.profiles.get(name) else {
        bail!("no profile named {name:?}");
    };
    print!(
        "# nft -f -\n{}",
        enforcer::nft::render_ruleset(&enforcer::nft::RulesetParams {
            dns_port: cfg.dns.port,
            block_quic: profile.block_quic,
            inspect_sni: profile.inspect_sni,
            container_dns: cfg.dns.container_dns,
        })
    );
    print!(
        "\n# tc -batch -  (per device; IFB created with `ip link add dwifb<ifindex> type ifb`)\n{}",
        enforcer::tc::render_shape("DEV", "dwifbN", &profile.throttle)
    );
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .init();
    let args = Args::parse();
    if let Some(profile) = &args.print_rules {
        return print_rules(&Config::load(&args.config)?, profile.as_deref());
    }
    if let Some(action) = args.browser_policies {
        let apply = matches!(action, PolicyAction::Apply);
        for path in enforcer::browser::sync(apply)? {
            println!(
                "{} {}",
                if apply { "updated" } else { "cleaned" },
                path.display()
            );
        }
        return Ok(());
    }
    if !args.dry_run && effective_uid()? != 0 {
        bail!("deepworkd must run as root (or pass --dry-run to only log what it would do)");
    }

    let (default_state, default_socket) = default_paths(args.dry_run);
    let state_dir = args.state_dir.unwrap_or(default_state);
    let socket = args.socket.unwrap_or(default_socket);
    std::fs::create_dir_all(&state_dir)
        .with_context(|| format!("creating {}", state_dir.display()))?;
    let store = Store::open(&state_dir.join("deepwork.db"))?;
    let unix_now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs() as i64);
    let (cfg_state, outcome) = cfgstate::sync(&store, &args.config, unix_now)?;
    let cfg = cfg_state.config.clone();

    let enforcer = EnforcerHandle::spawn(args.dry_run, &cfg.dns, &state_dir);
    let resolver = Resolver::new(cfg.dns.clone(), args.dry_run, enforcer.clone())?;
    if !args.dry_run {
        let resolver = resolver.clone();
        nfqueue::spawn(Arc::new(move || resolver.rules()));
    }
    let core = Arc::new(Mutex::new(
        Core::new(
            (cfg_state, outcome),
            args.config.clone(),
            store,
            enforcer,
            resolver.clone(),
            args.dry_run,
        )
        .await?,
    ));

    let ticker = {
        let core = core.clone();
        async move {
            let mut interval = tokio::time::interval(Duration::from_secs(1));
            interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
            loop {
                interval.tick().await;
                core.lock().await.tick().await;
            }
        }
    };

    let listener = server::bind(&socket)?;
    notify_ready();

    let mut sigterm = signal(SignalKind::terminate())?;
    let reloader = {
        let core = core.clone();
        let mut sighup = signal(SignalKind::hangup())?;
        async move {
            while sighup.recv().await.is_some() {
                let info = core.lock().await.reload();
                info!("SIGHUP: {}", info.message);
            }
        }
    };
    tokio::select! {
        () = reloader => {}
        res = resolver.serve() => res?,
        res = server::serve(listener, core.clone()) => res?,
        () = ticker => {}
        _ = sigterm.recv() => info!("SIGTERM"),
        _ = tokio::signal::ctrl_c() => info!("interrupted"),
    }

    // Enforcement deliberately stays in place: stopping the daemon must not
    // end a session.
    core.lock().await.persist();
    let _ = std::fs::remove_file(&socket);
    Ok(())
}
