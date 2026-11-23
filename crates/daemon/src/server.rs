//! The Unix socket clients talk to. Any local user may connect; the daemon
//! decides what each request is allowed to do.

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
    let uid = stream.peer_cred()?.uid();
    let (read, mut write) = stream.into_split();
    let mut reader = BufReader::new(read);
    let mut line = String::new();
    loop {
        line.clear();
        if (&mut reader).take(MAX_LINE).read_line(&mut line).await? == 0 {
            return Ok(());
        }
        let resp = match serde_json::from_str::<Request>(&line) {
            Ok(Request::Gate { service, uid }) => answer_gate(&core, &gate, service, uid),
            Ok(req) => core.lock().await.handle(req, uid).await,
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
) -> Response {
    let lockout = gate.borrow().clone();
    let resp = engine::gate_answer(lockout.as_ref(), uid);
    if let (Response::Gate { allow: false, .. }, Some(l)) = (&resp, lockout) {
        let core = core.clone();
        tokio::spawn(async move { core.lock().await.log_denied(l.session_id, &service, uid) });
    }
    resp
}
