//! Applies and removes network enforcement by running `nft`, `tc` and `ip`.
//!
//! [`Enforcer`] is blocking and lives on its own thread; the rest of the daemon
//! talks to it through [`EnforcerHandle`]. In dry-run mode every command is
//! logged instead of executed, so the daemon can be developed without root.

pub mod nft;
pub mod tc;

use std::collections::BTreeSet;
use std::io::Write as _;
use std::net::IpAddr;
use std::path::Path;
use std::process::{Command, Stdio};

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
    /// Started by systemd, so the stop lock applies.
    under_systemd: bool,
    active: Option<Profile>,
    /// Devices we have shaped during the current session.
    shaped: BTreeSet<String>,
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
        });
        self.run("nft", &["-f", "-"], Some(&script)).map(drop)
    }

    fn table_exists(&self) -> bool {
        self.dry_run
            || self
                .run("nft", &["list", "table", nft::TABLE], None)
                .is_ok()
    }

    fn engage(&mut self, profile: Profile) -> Result<()> {
        self.apply_ruleset(&profile)?;
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
        let mut devices = std::mem::take(&mut self.shaped);
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
            if !tc::should_shape(&dev) || self.shaped.contains(&dev) {
                continue;
            }
            match self.shape(&dev, ifindex, &profile) {
                Ok(()) => {
                    debug!("shaping {dev}");
                    self.shaped.insert(dev);
                }
                Err(e) => warn!("could not shape {dev}: {e:#}"),
            }
        }
    }

    fn shape(&self, dev: &str, ifindex: u32, profile: &Profile) -> Result<()> {
        let ifb = tc::ifb_name(ifindex);
        if self.dry_run || !Path::new("/sys/class/net").join(&ifb).exists() {
            self.run("ip", &["link", "add", &ifb, "type", "ifb"], None)?;
        }
        self.run("ip", &["link", "set", &ifb, "up"], None)?;
        self.run(
            "tc",
            &["-batch", "-"],
            Some(&tc::render_shape(dev, &ifb, &profile.throttle)),
        )
        .map(drop)
    }

    /// Puts back anything that was removed. Returns a note per repair, which
    /// the caller records as tampering.
    fn reassert(&mut self) -> Result<Vec<String>> {
        let Some(profile) = self.active.clone() else {
            return Ok(Vec::new());
        };
        let mut notes = Vec::new();
        if !self.table_exists() {
            notes.push("nft table was removed".to_string());
            self.apply_ruleset(&profile)?;
        }
        if !self.dry_run {
            let present: BTreeSet<String> = list_devices().into_iter().map(|(d, _)| d).collect();
            let missing: Vec<String> = self
                .shaped
                .iter()
                .filter(|dev| present.contains(*dev))
                .filter(|dev| {
                    self.run("tc", &["qdisc", "show", "dev", dev.as_str(), "root"], None)
                        .map(|out| !out.contains("d000:"))
                        .unwrap_or(true)
                })
                .cloned()
                .collect();
            for dev in missing {
                notes.push(format!("tc setup on {dev} was removed"));
                self.shaped.remove(&dev);
            }
            self.shaped.retain(|d| present.contains(d));
        }
        self.shape_new_devices();
        Ok(notes)
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
    Reassert(oneshot::Sender<Result<Vec<String>>>),
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
    pub fn spawn(dry_run: bool, dns_port: u16, manage_resolved: bool) -> Self {
        let (tx, mut rx) = mpsc::unbounded_channel();
        let mut enforcer = Enforcer {
            dry_run,
            dns_port,
            manage_resolved,
            under_systemd: std::env::var_os("INVOCATION_ID").is_some(),
            active: None,
            shaped: BTreeSet::new(),
        };
        std::thread::Builder::new()
            .name("enforcer".into())
            .spawn(move || {
                while let Some(cmd) = rx.blocking_recv() {
                    match cmd {
                        Cmd::Engage(profile, reply) => drop(reply.send(enforcer.engage(profile))),
                        Cmd::Release(reply) => drop(reply.send(enforcer.release())),
                        Cmd::Reassert(reply) => drop(reply.send(enforcer.reassert())),
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

    pub async fn reassert(&self) -> Result<Vec<String>> {
        self.call(Cmd::Reassert).await
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
