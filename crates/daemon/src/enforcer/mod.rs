//! Applies and removes network enforcement by running `nft`, `tc` and `ip`.
//!
//! [`Enforcer`] is blocking and lives on its own thread; the rest of the daemon
//! talks to it through [`EnforcerHandle`]. In dry-run mode every command is
//! logged instead of executed, so the daemon can be developed without root.

pub mod browser;
pub mod nft;
pub mod tc;

use std::collections::{BTreeMap, BTreeSet};
use std::io::{BufRead as _, BufReader, Write as _};
use std::net::IpAddr;
use std::path::Path;
use std::process::{Command, Stdio};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use anyhow::{Context, Result, bail};
use tokio::sync::{mpsc, oneshot};
use tracing::{debug, info, warn};

use crate::config::{Action, Profile};

/// Runtime drop-in that points systemd-resolved at our forwarder for the
/// length of a session. It lives in /run, so a reboot removes it.
const RESOLVED_DROPIN: &str = "/run/systemd/resolved.conf.d/zz-deepwork.conf";

fn resolved_dropin(dns_port: u16) -> String {
    // `DNS=` with no value clears servers set by earlier files.
    format!(
        "# Written by deepworkd for the current focus session; removed when it ends.\n\
         [Resolve]\nDNS=\nDNS=127.0.0.1:{dns_port}\nDNSOverTLS=no\nDomains=~.\n"
    )
}

/// Runtime drop-in that makes `systemctl stop/restart deepworkd` fail for the
/// length of a session. Outside sessions the daemon can be stopped and
/// upgraded normally. Crashes still restart it (`Restart=always`).
const STOP_DROPIN: &str = "/run/systemd/system/deepworkd.service.d/50-session.conf";
const STOP_DROPIN_TEXT: &str = "# Written by deepworkd for the current focus session; removed when it ends.\n\
                                [Unit]\nRefuseManualStop=yes\n";

struct Enforcer {
    dry_run: bool,
    dns_port: u16,
    manage_resolved: bool,
    container_dns: Option<std::net::SocketAddrV4>,
    /// Started by systemd, so the stop lock applies.
    under_systemd: bool,
    active: Option<Profile>,
    /// Devices shaped during the current session, with a fingerprint of their
    /// tc setup (device and IFB) taken right after shaping.
    shaped: BTreeMap<String, String>,
    /// `nft -t list` of our table (plus the static sets) right after it was
    /// applied. Any difference later is tampering.
    baseline: Option<String>,
    /// Tamper notes found between two [`Enforcer::reassert`] calls.
    pending: Vec<String>,
    /// The dynamic sets were lost; DNS answers have to be collected again.
    reprime: bool,
    /// Devices whose shaping failed, and when to try again. Keeps a failing
    /// device from looping through `tc monitor` events.
    retry_at: BTreeMap<String, Instant>,
}

const SHAPE_RETRY: Duration = Duration::from_secs(30);

/// What [`Enforcer::reassert`] found and fixed.
#[derive(Debug, Default)]
pub struct Reasserted {
    pub notes: Vec<String>,
    pub reprime: bool,
}

impl Enforcer {
    fn run(&self, prog: &str, args: &[&str], stdin: Option<&str>) -> Result<String> {
        if self.dry_run {
            match stdin {
                Some(script) => info!("[dry-run] {prog} {}\n{script}", args.join(" ")),
                None => info!("[dry-run] {prog} {}", args.join(" ")),
            }
            return Ok(String::new());
        }
        let mut child = Command::new(prog)
            .args(args)
            .stdin(if stdin.is_some() {
                Stdio::piped()
            } else {
                Stdio::null()
            })
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .with_context(|| format!("spawning {prog}"))?;
        if let Some(script) = stdin {
            child.stdin.take().unwrap().write_all(script.as_bytes())?;
        }
        let out = child.wait_with_output()?;
        if !out.status.success() {
            bail!(
                "{prog} {} failed: {}",
                args.join(" "),
                String::from_utf8_lossy(&out.stderr).trim()
            );
        }
        Ok(String::from_utf8_lossy(&out.stdout).into_owned())
    }

    fn apply_ruleset(&self, profile: &Profile) -> Result<()> {
        let script = nft::render_ruleset(&nft::RulesetParams {
            dns_port: self.dns_port,
            block_quic: profile.block_quic,
            container_dns: self.container_dns,
        });
        self.run("nft", &["-f", "-"], Some(&script)).map(drop)
    }

    /// Applies the ruleset and records its fingerprint.
    fn install_ruleset(&mut self, profile: &Profile) -> Result<()> {
        self.apply_ruleset(profile)?;
        self.baseline = self.table_listing();
        Ok(())
    }

    /// Our table without the contents of the dynamic sets, or `None` if it
    /// is gone.
    fn table_listing(&self) -> Option<String> {
        let mut out = self
            .run("nft", &["-t", "list", "table", nft::TABLE], None)
            .ok()?;
        for set in nft::STATIC_SETS {
            out += &self
                .run("nft", &["list", "set", nft::TABLE, set], None)
                .ok()?;
        }
        Some(out)
    }

    /// Re-applies the table if it was removed or changed, keeping the
    /// addresses learned so far. Returns a tamper note if it had to.
    fn verify_table(&mut self) -> Result<Option<String>> {
        let Some(profile) = self.active.clone() else {
            return Ok(None);
        };
        let current = self.table_listing();
        let note = match &current {
            None => "nft table was removed",
            Some(listing) if Some(listing) != self.baseline.as_ref() => "nft table was modified",
            _ => return Ok(None),
        };
        let saved: Vec<(Action, Vec<(IpAddr, u32)>)> = if current.is_some() {
            nft::DYNAMIC_SETS
                .iter()
                .map(|(set, action)| {
                    let json = self
                        .run("nft", &["-j", "list", "set", nft::TABLE, set], None)
                        .unwrap_or_default();
                    (*action, nft::parse_set_elements(&json))
                })
                .collect()
        } else {
            Vec::new()
        };
        self.install_ruleset(&profile)?;
        let mut restored = 0;
        for (action, elems) in saved {
            if let Some(script) = nft::render_add_timed(action, &elems)
                && self.run("nft", &["-f", "-"], Some(&script)).is_ok()
            {
                restored += elems.len();
            }
        }
        if restored == 0 {
            self.reprime = true;
        }
        warn!("tamper: {note}; re-applied ({restored} addresses kept)");
        Ok(Some(note.to_string()))
    }

    /// The tc setup of a shaped device and its IFB, as `tc` prints it.
    fn tc_fingerprint(&self, dev: &str, ifb: &str) -> String {
        let views: [&[&str]; 5] = [
            &["qdisc", "show", "dev", dev],
            &["filter", "show", "dev", dev],
            &["filter", "show", "dev", dev, "ingress"],
            &["qdisc", "show", "dev", ifb],
            &["filter", "show", "dev", ifb],
        ];
        views
            .iter()
            .map(|args| {
                self.run("tc", args, None)
                    .unwrap_or_else(|e| format!("error: {e}"))
            })
            .collect()
    }

    /// Forgets devices whose tc setup changed, so the next
    /// [`Enforcer::shape_new_devices`] shapes them again.
    fn verify_tc(&mut self) {
        if self.active.is_none() || self.dry_run {
            return;
        }
        let present: BTreeMap<String, u32> = list_devices().into_iter().collect();
        for (dev, fingerprint) in self.shaped.clone() {
            let Some(ifindex) = present.get(&dev) else {
                self.shaped.remove(&dev);
                continue;
            };
            if self.tc_fingerprint(&dev, &tc::ifb_name(*ifindex)) != fingerprint {
                warn!("tamper: tc setup on {dev} was changed");
                self.pending.push(format!("tc setup on {dev} was changed"));
                self.shaped.remove(&dev);
            }
        }
    }

    fn sync_browser_policies(&self) {
        if self.dry_run {
            debug!("[dry-run] sync browser policies");
            return;
        }
        match browser::sync(true) {
            Ok(changed) => {
                for path in changed {
                    info!("browser policy re-applied: {}", path.display());
                }
            }
            Err(e) => warn!("could not apply browser policies: {e:#}"),
        }
    }

    fn engage(&mut self, profile: Profile) -> Result<()> {
        self.sync_browser_policies();
        self.install_ruleset(&profile)?;
        if self.manage_resolved {
            // resolved may use DNS-over-TLS, which the ruleset now blocks, so
            // it has to go through us. Restarting also empties its cache.
            self.write_file(RESOLVED_DROPIN, &resolved_dropin(self.dns_port))?;
            self.run("systemctl", &["restart", "systemd-resolved"], None)?;
        } else if let Err(e) = self.run("resolvectl", &["flush-caches"], None) {
            // Cached answers would never reach our resolver, so their
            // addresses would never be added to the sets.
            warn!("could not flush resolved cache: {e:#}");
        }
        self.active = Some(profile);
        self.shaped.clear();
        self.shape_new_devices();
        if let Err(e) = self.set_stop_lock(true) {
            warn!("could not lock the service against manual stops: {e:#}");
        }
        Ok(())
    }

    fn set_stop_lock(&self, on: bool) -> Result<()> {
        if !self.under_systemd && !self.dry_run {
            return Ok(());
        }
        if on {
            self.write_file(STOP_DROPIN, STOP_DROPIN_TEXT)?;
        } else if self.dry_run || Path::new(STOP_DROPIN).exists() {
            if !self.dry_run {
                std::fs::remove_file(STOP_DROPIN)?;
            }
        } else {
            return Ok(());
        }
        self.run("systemctl", &["daemon-reload"], None).map(drop)
    }

    fn write_file(&self, path: &str, contents: &str) -> Result<()> {
        if self.dry_run {
            info!("[dry-run] write {path}\n{contents}");
            return Ok(());
        }
        let path = Path::new(path);
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        std::fs::write(path, contents).with_context(|| format!("writing {}", path.display()))
    }

    fn release(&mut self) -> Result<()> {
        self.active = None;
        self.baseline = None;
        self.pending.clear();
        self.reprime = false;
        self.retry_at.clear();
        if let Err(e) = self.set_stop_lock(false) {
            warn!("could not lift the manual stop lock: {e:#}");
        }
        self.run("nft", &["destroy", "table", nft::TABLE], None)?;
        // Only after the table is gone, so resolved can reach its own
        // DNS-over-TLS servers again.
        if self.dry_run || Path::new(RESOLVED_DROPIN).exists() {
            if !self.dry_run {
                std::fs::remove_file(RESOLVED_DROPIN)?;
            }
            self.run("systemctl", &["restart", "systemd-resolved"], None)?;
        }
        // Also cleans up after a crash: any device with a dwifb twin is ours.
        let mut devices: BTreeSet<String> = std::mem::take(&mut self.shaped).into_keys().collect();
        for (dev, ifindex) in list_devices() {
            if Path::new("/sys/class/net")
                .join(tc::ifb_name(ifindex))
                .exists()
            {
                devices.insert(dev);
            }
        }
        for dev in devices {
            let _ = self.run(
                "tc",
                &["-force", "-batch", "-"],
                Some(&tc::render_unshape(&dev)),
            );
        }
        for (dev, _) in list_devices() {
            if dev.starts_with("dwifb") {
                let _ = self.run("ip", &["link", "del", &dev], None);
            }
        }
        Ok(())
    }

    fn shape_new_devices(&mut self) {
        let Some(profile) = self.active.clone() else {
            return;
        };
        for (dev, ifindex) in list_devices() {
            if !tc::should_shape(&dev) || self.shaped.contains_key(&dev) {
                continue;
            }
            if self.retry_at.get(&dev).is_some_and(|t| Instant::now() < *t) {
                continue;
            }
            match self.shape(&dev, ifindex, &profile) {
                Ok(()) => {
                    debug!("shaping {dev}");
                    self.retry_at.remove(&dev);
                    let fingerprint = self.tc_fingerprint(&dev, &tc::ifb_name(ifindex));
                    self.shaped.insert(dev, fingerprint);
                }
                Err(e) => {
                    warn!("could not shape {dev}: {e:#}");
                    self.retry_at.insert(dev, Instant::now() + SHAPE_RETRY);
                }
            }
        }
    }

    fn shape(&self, dev: &str, ifindex: u32, profile: &Profile) -> Result<()> {
        let ifb = tc::ifb_name(ifindex);
        if self.dry_run || !Path::new("/sys/class/net").join(&ifb).exists() {
            self.run("ip", &["link", "add", &ifb, "type", "ifb"], None)?;
        }
        self.run("ip", &["link", "set", &ifb, "up"], None)?;
        // An existing ingress filter makes `filter replace` fail with "File
        // exists", so a partly removed setup could never be repaired.
        let _ = self.run("tc", &["qdisc", "del", "dev", dev, "clsact"], None);
        self.run(
            "tc",
            &["-batch", "-"],
            Some(&tc::render_shape(dev, &ifb, &profile.throttle)),
        )
        .map(drop)
    }

    /// Puts back anything that was removed or changed. Returns the tamper
    /// notes found since the last call, including those from the watchers.
    fn reassert(&mut self) -> Result<Reasserted> {
        if self.active.is_none() {
            return Ok(Reasserted::default());
        }
        if let Some(note) = self.verify_table()? {
            self.pending.push(note);
        }
        self.verify_tc();
        self.shape_new_devices();
        Ok(Reasserted {
            notes: std::mem::take(&mut self.pending),
            reprime: std::mem::take(&mut self.reprime),
        })
    }

    fn add_addrs(&self, action: Action, addrs: &[IpAddr], timeout_secs: u32) {
        if self.active.is_none() {
            return;
        }
        if let Some(script) = nft::render_add_elements(action, addrs, timeout_secs)
            && let Err(e) = self.run("nft", &["-f", "-"], Some(&script))
        {
            warn!("adding addresses failed: {e:#}");
        }
    }
}

/// One flag per watcher: set while its check is queued, so a burst of events
/// (`nft flush ruleset` prints dozens of lines) queues one check.
#[derive(Default)]
struct Flags {
    nft: Arc<AtomicBool>,
    tc: Arc<AtomicBool>,
    link: Arc<AtomicBool>,
}

/// Runs a `* monitor` command for the life of the daemon and turns matching
/// output lines into enforcer commands. Restarts it if it exits.
fn spawn_watch(
    argv: &'static [&'static str],
    tx: mpsc::UnboundedSender<Cmd>,
    queued: Arc<AtomicBool>,
    cmd: fn() -> Cmd,
    matches: fn(&str) -> bool,
) {
    let name = argv.join(" ");
    let spawned = std::thread::Builder::new()
        .name(format!("watch {}", argv[0]))
        .spawn(move || {
            loop {
                let mut command = Command::new(argv[0]);
                command
                    .args(&argv[1..])
                    .stdin(Stdio::null())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::null());
                // SAFETY: prctl is async-signal-safe. The monitor dies with
                // this thread, which lives as long as the daemon.
                unsafe {
                    use std::os::unix::process::CommandExt as _;
                    command.pre_exec(|| {
                        libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGTERM);
                        Ok(())
                    });
                }
                match command.spawn() {
                    Ok(mut child) => {
                        let stdout = child.stdout.take().expect("piped stdout");
                        for line in BufReader::new(stdout).lines() {
                            let Ok(line) = line else { break };
                            if matches(&line) && !queued.swap(true, Ordering::SeqCst) {
                                debug!("{name}: {line}");
                                if tx.send(cmd()).is_err() {
                                    let _ = child.kill();
                                    return;
                                }
                            }
                        }
                        let _ = child.kill();
                        let _ = child.wait();
                        warn!("`{name}` exited; restarting it");
                    }
                    Err(e) => warn!("cannot run `{name}`: {e}"),
                }
                std::thread::sleep(Duration::from_secs(5));
            }
        });
    if let Err(e) = spawned {
        warn!("cannot start the `{}` watcher: {e}", argv.join(" "));
    }
}

/// `(name, ifindex)` for every network device.
fn list_devices() -> Vec<(String, u32)> {
    let Ok(entries) = std::fs::read_dir("/sys/class/net") else {
        return Vec::new();
    };
    entries
        .flatten()
        .filter_map(|e| {
            let name = e.file_name().into_string().ok()?;
            let ifindex = std::fs::read_to_string(e.path().join("ifindex")).ok()?;
            Some((name, ifindex.trim().parse().ok()?))
        })
        .collect()
}

enum Cmd {
    Engage(Profile, oneshot::Sender<Result<()>>),
    Release(oneshot::Sender<Result<()>>),
    Reassert(oneshot::Sender<Result<Reasserted>>),
    /// `nft monitor` saw a change to our table.
    CheckNft,
    /// `tc monitor` saw a qdisc or filter change.
    CheckTc,
    /// `ip monitor link` saw a device appear or change.
    Rescan,
    SyncBrowserPolicies,
    AddAddrs {
        action: Action,
        addrs: Vec<IpAddr>,
        timeout_secs: u32,
    },
}

#[derive(Clone)]
pub struct EnforcerHandle {
    tx: mpsc::UnboundedSender<Cmd>,
}

impl EnforcerHandle {
    pub fn spawn(dry_run: bool, dns: &crate::config::DnsConfig) -> Self {
        let (dns_port, manage_resolved, container_dns) =
            (dns.port, dns.manage_resolved, dns.container_dns);
        let (tx, mut rx) = mpsc::unbounded_channel();
        let mut enforcer = Enforcer {
            dry_run,
            dns_port,
            manage_resolved,
            container_dns,
            under_systemd: std::env::var_os("INVOCATION_ID").is_some(),
            active: None,
            shaped: BTreeMap::new(),
            baseline: None,
            pending: Vec::new(),
            reprime: false,
            retry_at: BTreeMap::new(),
        };
        let flags = Flags::default();
        if !dry_run {
            spawn_watch(
                &["nft", "monitor", "ruleset"],
                tx.clone(),
                flags.nft.clone(),
                || Cmd::CheckNft,
                nft::monitor_line_is_ours,
            );
            spawn_watch(
                &["tc", "monitor"],
                tx.clone(),
                flags.tc.clone(),
                || Cmd::CheckTc,
                |_| true,
            );
            spawn_watch(
                &["ip", "monitor", "link"],
                tx.clone(),
                flags.link.clone(),
                || Cmd::Rescan,
                |_| true,
            );
        }
        std::thread::Builder::new()
            .name("enforcer".into())
            .spawn(move || {
                while let Some(cmd) = rx.blocking_recv() {
                    match cmd {
                        Cmd::Engage(profile, reply) => drop(reply.send(enforcer.engage(profile))),
                        Cmd::Release(reply) => drop(reply.send(enforcer.release())),
                        Cmd::Reassert(reply) => drop(reply.send(enforcer.reassert())),
                        Cmd::CheckNft => {
                            flags.nft.store(false, Ordering::SeqCst);
                            match enforcer.verify_table() {
                                Ok(Some(note)) => enforcer.pending.push(note),
                                Ok(None) => {}
                                Err(e) => warn!("re-applying the nft table failed: {e:#}"),
                            }
                        }
                        Cmd::CheckTc => {
                            flags.tc.store(false, Ordering::SeqCst);
                            enforcer.verify_tc();
                            enforcer.shape_new_devices();
                        }
                        Cmd::SyncBrowserPolicies => enforcer.sync_browser_policies(),
                        Cmd::Rescan => {
                            flags.link.store(false, Ordering::SeqCst);
                            enforcer.shape_new_devices();
                        }
                        Cmd::AddAddrs {
                            action,
                            addrs,
                            timeout_secs,
                        } => enforcer.add_addrs(action, &addrs, timeout_secs),
                    }
                }
            })
            .expect("spawning enforcer thread");
        Self { tx }
    }

    async fn call<T>(&self, make: impl FnOnce(oneshot::Sender<Result<T>>) -> Cmd) -> Result<T> {
        let (reply, rx) = oneshot::channel();
        self.tx
            .send(make(reply))
            .map_err(|_| anyhow::anyhow!("enforcer thread is gone"))?;
        rx.await.context("enforcer thread is gone")?
    }

    pub async fn engage(&self, profile: Profile) -> Result<()> {
        self.call(|r| Cmd::Engage(profile, r)).await
    }

    pub async fn release(&self) -> Result<()> {
        self.call(Cmd::Release).await
    }

    pub async fn reassert(&self) -> Result<Reasserted> {
        self.call(Cmd::Reassert).await
    }

    /// Re-applies the browser policies if a package update replaced them.
    pub fn sync_browser_policies(&self) {
        let _ = self.tx.send(Cmd::SyncBrowserPolicies);
    }

    /// Fire and forget; used from the DNS path.
    pub fn add_addrs(&self, action: Action, addrs: Vec<IpAddr>, timeout_secs: u32) {
        let _ = self.tx.send(Cmd::AddAddrs {
            action,
            addrs,
            timeout_secs,
        });
    }
}
