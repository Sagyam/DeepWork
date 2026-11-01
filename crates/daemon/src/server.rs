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

use crate::engine::Core;

const MAX_LINE: u64 = 64 * 1024;

pub async fn serve(path: &Path, core: Arc<Mutex<Core>>) -> Result<()> {
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

    loop {
        let (stream, _) = listener.accept().await?;
        let core = core.clone();
        tokio::spawn(async move {
            if let Err(e) = handle_conn(stream, core).await {
                debug!("client disconnected: {e:#}");
            }
        });
    }
}

async fn handle_conn(stream: UnixStream, core: Arc<Mutex<Core>>) -> Result<()> {
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
            Ok(req) => core.lock().await.handle(req, uid).await,
            Err(e) => Response::error(format!("bad request: {e}")),
        };
        let mut out = serde_json::to_vec(&resp)?;
        out.push(b'\n');
        write.write_all(&out).await?;
    }
}
