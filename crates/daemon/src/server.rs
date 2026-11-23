//! The Unix socket clients talk to. Any local user may connect; the daemon
//! decides what each request is allowed to do. System accounts (services,
//! `nobody`) are refused outright, so a compromised service cannot start a
//! session that locks the user out of sudo, or change their settings.

use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::sync::Arc;

use anyhow::{Context, Result};
use deepwork_proto::{Request, Response};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio::net::{UnixListener, UnixStream};
use tokio::sync::Mutex;
use tracing::debug;

use crate::engine::{self, Core, GateWatch};

/// Backups can carry thousands of sessions, so a request line may be large.
/// 8 MiB is far past the ~2 MB a decade of sessions takes.
const MAX_LINE: u64 = 8 * 1024 * 1024;

/// `UID_MIN` in the default `/etc/login.defs` of Arch, Debian and Fedora.
const FIRST_USER_UID: u32 = 1000;
const NOBODY: u32 = 65534;

/// Root and people may ask; system accounts may not.
fn may_ask(uid: u32) -> bool {
    uid == 0 || (FIRST_USER_UID..NOBODY).contains(&uid)
}

/// The account the polkit rule runs the gate as.
fn polkitd_uid() -> Option<u32> {
    static UID: std::sync::OnceLock<Option<u32>> = std::sync::OnceLock::new();
    *UID.get_or_init(|| {
        let passwd = std::fs::read_to_string("/etc/passwd").ok()?;
        passwd_uid(&passwd, "polkitd")
    })
}

fn passwd_uid(passwd: &str, name: &str) -> Option<u32> {
    passwd.lines().find_map(|line| {
        let mut fields = line.split(':');
        (fields.next()? == name).then(|| fields.nth(1)?.parse().ok())?
    })
}

/// Whether a gate request comes from one of the hooks: `pam_exec` runs the
/// gate with root's effective uid (inside sudo, su, polkit's helper), the
/// polkit rule as polkitd. Only theirs may name the uid asking and count as
/// a refused escalation; anyone else gets the same answer for themselves.
fn from_hook(peer: u32) -> bool {
    peer == 0 || Some(peer) == polkitd_uid()
}

/// Binds the socket. Separate from [`serve`] so the daemon can report itself
/// ready to systemd only once clients can connect.
pub fn bind(path: &Path) -> Result<UnixListener> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).with_context(|| format!("creating {}", dir.display()))?;
    }
    match std::fs::remove_file(path) {
        Err(e) if e.kind() != std::io::ErrorKind::NotFound => return Err(e.into()),
        _ => {}
    }
    let listener =
        UnixListener::bind(path).with_context(|| format!("binding {}", path.display()))?;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o666))?;
    tracing::info!("listening on {}", path.display());
    Ok(listener)
}

pub async fn serve(listener: UnixListener, core: Arc<Mutex<Core>>, gate: GateWatch) -> Result<()> {
    loop {
        let (stream, _) = listener.accept().await?;
        let core = core.clone();
        let gate = gate.clone();
        tokio::spawn(async move {
            if let Err(e) = handle_conn(stream, core, gate).await {
                debug!("client disconnected: {e:#}");
            }
        });
    }
}

async fn handle_conn(stream: UnixStream, core: Arc<Mutex<Core>>, gate: GateWatch) -> Result<()> {
    let peer = stream.peer_cred()?.uid();
    let (read, mut write) = stream.into_split();
    let mut reader = BufReader::new(read);
    let mut line = String::new();
    loop {
        line.clear();
        if (&mut reader).take(MAX_LINE).read_line(&mut line).await? == 0 {
            return Ok(());
        }
        let resp = match serde_json::from_str::<Request>(&line) {
            Ok(Request::Gate { service, uid }) if from_hook(peer) => {
                answer_gate(&core, &gate, service, uid, true)
            }
            Ok(Request::Gate { service, .. }) => {
                answer_gate(&core, &gate, service, Some(peer), false)
            }
            Ok(_) if !may_ask(peer) => {
                Response::error(format!("uid {peer} is a system account; ask as a user"))
            }
            Ok(req) => core.lock().await.handle(req, peer).await,
            Err(e) => Response::error(format!("bad request: {e}")),
        };
        let mut out = serde_json::to_vec(&resp)?;
        out.push(b'\n');
        write.write_all(&out).await?;
    }
}

/// Answers the privilege gate from the published lockout, never waiting for
/// the core: a refusal is logged afterwards, in the background.
fn answer_gate(
    core: &Arc<Mutex<Core>>,
    gate: &GateWatch,
    service: String,
    uid: Option<u32>,
    log: bool,
) -> Response {
    let lockout = gate.borrow().clone();
    let resp = engine::gate_answer(lockout.as_ref(), uid);
    if let (Response::Gate { allow: false, .. }, Some(l), true) = (&resp, lockout, log) {
        let core = core.clone();
        tokio::spawn(async move { core.lock().await.log_denied(l.session_id, &service, uid) });
    }
    resp
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_root_and_people_may_ask() {
        assert!(may_ask(0));
        assert!(may_ask(1000));
        assert!(may_ask(60000));
        assert!(!may_ask(33), "http");
        assert!(!may_ask(102), "polkitd asks only through the gate");
        assert!(!may_ask(NOBODY));
    }

    #[test]
    fn finds_polkitd() {
        let passwd =
            "root:x:0:0::/root:/bin/bash\npolkitd:x:102:102:User for polkitd:/:/usr/bin/nologin\n";
        assert_eq!(passwd_uid(passwd, "polkitd"), Some(102));
        assert_eq!(passwd_uid(passwd, "polkit"), None);
        assert_eq!(
            passwd_uid("polkitd:x:oops:1::/:/bin/false", "polkitd"),
            None
        );
    }
}
