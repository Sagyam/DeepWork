//! DeepWork window: a view over the daemon. Every request goes to `deepworkd`
//! over its socket, which decides what is allowed; the app holds no state.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod models;

use std::path::PathBuf;
use std::sync::Arc;

use deepwork_proto::{Request, Response};
use models::Models;

/// Backups are small; refuse anything that could be a mistake.
const MAX_BACKUP_BYTES: u64 = 32 * 1024 * 1024;

fn socket() -> PathBuf {
    std::env::var_os("DEEPWORK_SOCKET")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(deepwork_proto::DEFAULT_SOCKET))
}

/// Forwards one request to the daemon. Daemon refusals come back as
/// `Response::Error`; only a failure to reach it is an `Err`.
#[tauri::command]
async fn daemon(request: Request) -> Result<Response, String> {
    if matches!(request, Request::Gate { .. }) {
        return Err("not available from the app".into());
    }
    let path = socket();
    tauri::async_runtime::spawn_blocking(move || {
        deepwork_proto::request(&path, &request)
            .map_err(|e| format!("deepworkd is not reachable at {}: {e}", path.display()))
    })
    .await
    .map_err(|e| e.to_string())?
}

/// Reads a backup the user chose in the native dialog. The path comes from
/// the dialog, not from page content.
#[tauri::command]
async fn read_file(path: String) -> Result<String, String> {
    let meta = std::fs::metadata(&path).map_err(|e| format!("reading {path}: {e}"))?;
    if meta.len() > MAX_BACKUP_BYTES {
        return Err(format!(
            "{path} is larger than 32 MB; that is not a DeepWork backup"
        ));
    }
    std::fs::read_to_string(&path).map_err(|e| format!("reading {path}: {e}"))
}

/// Writes a backup to the path the user chose. Atomic, so a full disk cannot
/// leave half a backup behind.
#[tauri::command]
async fn write_file(path: String, contents: String) -> Result<(), String> {
    let target = PathBuf::from(&path);
    let tmp = target.with_extension("json.tmp");
    std::fs::write(&tmp, contents).map_err(|e| format!("writing {}: {e}", tmp.display()))?;
    std::fs::rename(&tmp, &target).map_err(|e| format!("saving {path}: {e}"))?;
    Ok(())
}

/// Whether the realistic city's models are on disk yet, and where to read them.
#[tauri::command]
fn models(state: tauri::State<Arc<Models>>) -> models::Status {
    state.status()
}

fn main() {
    let pack = Models::start();
    let serving = pack.clone();
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(pack)
        .register_asynchronous_uri_scheme_protocol(
            models::SCHEME,
            move |_ctx, request, responder| {
                let m = serving.clone();
                std::thread::spawn(move || responder.respond(m.serve(&request)));
            },
        )
        .invoke_handler(tauri::generate_handler![
            daemon, read_file, write_file, models
        ])
        .run(tauri::generate_context!())
        .expect("error while running DeepWork");
}
