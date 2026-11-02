//! DeepWork window: a view over the daemon. Every request goes to `deepworkd`
//! over its socket, which decides what is allowed; the app holds no state.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;

use deepwork_proto::{Request, Response};

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

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![daemon])
        .run(tauri::generate_context!())
        .expect("error while running DeepWork");
}
