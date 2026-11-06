//! The realistic city's models, downloaded on first run (docs/models.md,
//! "Downloading the models"). Releases do not carry them: `models.json`, made
//! by `bun run pack` and compiled in, lists every file of the pack with its
//! size and SHA-256, and the pack lives in a GitHub release of its own. Files
//! are fetched as the user (never by the daemon), checked against the
//! manifest, and kept in `~/.local/share/deepwork/assets/<id>/`; the page
//! reads them through the `models://` scheme. Until they are all there the
//! city is drawn with the embedded low-poly kit.
//!
//! `DEEPWORK_MODELS=<dir>` serves a local directory instead (unchecked), for
//! trying a pack before it is published: `DEEPWORK_MODELS=ui/public/models`.

use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tauri::http::{Request, Response, StatusCode, header};

/// The scheme the page loads models from (`models://localhost/a1.glb`).
pub const SCHEME: &str = "models";
/// Marks a pack whose every file has been checked.
const COMPLETE: &str = ".complete";
/// Parallel downloads: the files are small (under 4 MB), so latency rules.
const WORKERS: usize = 4;

#[derive(Deserialize)]
struct Manifest {
    id: String,
    url: String,
    files: Vec<Entry>,
}

#[derive(Deserialize, Clone)]
struct Entry {
    path: String,
    size: u64,
    sha256: String,
    asset: String,
}

/// What the page is told (`invoke("models")`).
#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case", tag = "state")]
pub enum Status {
    /// No pack in this build: the kit only.
    None,
    Downloading {
        done: u64,
        total: u64,
    },
    /// The last attempt failed; the next one starts in `retry_secs`.
    Retrying {
        done: u64,
        total: u64,
        error: String,
        retry_secs: u64,
    },
    Ready {
        base: String,
    },
}

pub struct Models {
    /// Path → file, for the pack; empty when serving an override directory.
    files: HashMap<String, Entry>,
    dir: Option<PathBuf>,
    state: Mutex<Status>,
    /// When the next attempt starts, while `Retrying`.
    retry_at: Mutex<Option<Instant>>,
}

fn data_dir() -> Option<PathBuf> {
    std::env::var_os("XDG_DATA_HOME")
        .map(PathBuf::from)
        .filter(|p| p.is_absolute())
        .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".local/share")))
}

fn base() -> String {
    format!("{SCHEME}://localhost/")
}

impl Models {
    /// Reads the compiled-in manifest and, if the pack is not on disk yet,
    /// starts fetching it in the background.
    pub fn start() -> Arc<Self> {
        if let Some(dir) = std::env::var_os("DEEPWORK_MODELS") {
            return Arc::new(Self {
                files: HashMap::new(),
                dir: Some(PathBuf::from(dir)),
                state: Mutex::new(Status::Ready { base: base() }),
                retry_at: Mutex::new(None),
            });
        }
        let manifest: Manifest = match serde_json::from_str(include_str!("../models.json")) {
            Ok(m) => m,
            Err(e) => {
                eprintln!("models.json: {e}");
                return Arc::new(Self::none());
            }
        };
        let Some(root) = data_dir().map(|d| d.join("deepwork/assets")) else {
            return Arc::new(Self::none());
        };
        if manifest.files.is_empty() {
            return Arc::new(Self::none());
        }
        let dir = root.join(&manifest.id);
        let ready = dir.join(COMPLETE).exists();
        let total = manifest.files.iter().map(|f| f.size).sum();
        let models = Arc::new(Self {
            files: manifest
                .files
                .iter()
                .map(|f| (f.path.clone(), f.clone()))
                .collect(),
            dir: Some(dir.clone()),
            state: Mutex::new(if ready {
                Status::Ready { base: base() }
            } else {
                Status::Downloading { done: 0, total }
            }),
            retry_at: Mutex::new(None),
        });
        if !ready {
            let m = models.clone();
            std::thread::spawn(move || m.fetch(&manifest, &root, &dir));
        }
        models
    }

    fn none() -> Self {
        Self {
            files: HashMap::new(),
            dir: None,
            state: Mutex::new(Status::None),
            retry_at: Mutex::new(None),
        }
    }

    pub fn status(&self) -> Status {
        let mut s = self.state.lock().unwrap().clone();
        if let (Status::Retrying { retry_secs, .. }, Some(at)) =
            (&mut s, *self.retry_at.lock().unwrap())
        {
            *retry_secs = at.saturating_duration_since(Instant::now()).as_secs();
        }
        s
    }

    fn set(&self, s: Status) {
        *self.state.lock().unwrap() = s;
    }

    /// Fetches until the whole pack is there, waiting longer after each failure
    /// (a session that blocks GitHub, no network): 15 s, then up to 10 min.
    fn fetch(&self, manifest: &Manifest, root: &Path, dir: &Path) {
        let total: u64 = manifest.files.iter().map(|f| f.size).sum();
        let mut wait = 15;
        loop {
            match download(manifest, dir, |done| {
                self.set(Status::Downloading { done, total })
            }) {
                Ok(()) => break,
                Err((done, error)) => {
                    eprintln!("models: {error}; retrying in {wait} s");
                    *self.retry_at.lock().unwrap() =
                        Some(Instant::now() + Duration::from_secs(wait));
                    self.set(Status::Retrying {
                        done,
                        total,
                        error,
                        retry_secs: wait,
                    });
                    std::thread::sleep(Duration::from_secs(wait));
                    wait = (wait * 4).min(600);
                }
            }
        }
        if let Err(e) = File::create(dir.join(COMPLETE)) {
            eprintln!("models: marking {} complete: {e}", dir.display());
        }
        // Older packs are not needed once this one is whole.
        if let Ok(entries) = fs::read_dir(root) {
            for e in entries.flatten() {
                if e.path() != dir && e.path().is_dir() {
                    let _ = fs::remove_dir_all(e.path());
                }
            }
        }
        self.set(Status::Ready { base: base() });
    }

    /// The bytes for one `models://` request. Only the manifest's files are
    /// served (or, with `DEEPWORK_MODELS`, plain names inside that directory).
    pub fn serve(&self, request: &Request<Vec<u8>>) -> Response<Vec<u8>> {
        let reply = |status: StatusCode, kind: &str, body: Vec<u8>| {
            Response::builder()
                .status(status)
                .header(header::CONTENT_TYPE, kind)
                .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, "*")
                .body(body)
                .unwrap()
        };
        let not_found = || reply(StatusCode::NOT_FOUND, "text/plain", b"not found".to_vec());
        let path = request.uri().path().trim_start_matches('/');
        let (Some(dir), Status::Ready { .. }) = (&self.dir, self.status()) else {
            return not_found();
        };
        let allowed = if self.files.is_empty() {
            !path.is_empty()
                && path
                    .split('/')
                    .all(|c| !c.is_empty() && c != "." && c != "..")
        } else {
            self.files.contains_key(path)
        };
        if !allowed {
            return not_found();
        }
        match fs::read(dir.join(path)) {
            Ok(bytes) => reply(StatusCode::OK, content_type(path), bytes),
            Err(_) => not_found(),
        }
    }
}

fn content_type(path: &str) -> &'static str {
    match path.rsplit('.').next() {
        Some("glb") => "model/gltf-binary",
        Some("json") => "application/json",
        Some("png") => "image/png",
        _ => "application/octet-stream",
    }
}

/// Downloads every file not yet in `dir`. A file lands under its own name
/// only once its size and sum match, so whatever is there is good, and a
/// broken connection costs at most the files in flight. `progress` gets the
/// bytes so far; an error comes with them.
fn download(
    manifest: &Manifest,
    dir: &Path,
    progress: impl Fn(u64) + Sync,
) -> Result<(), (u64, String)> {
    let done = AtomicU64::new(0);
    let todo: Vec<&Entry> = manifest
        .files
        .iter()
        .filter(|f| match fs::metadata(dir.join(&f.path)) {
            Ok(m) if m.len() == f.size => {
                done.fetch_add(f.size, Ordering::Relaxed);
                false
            }
            _ => true,
        })
        .collect();
    progress(done.load(Ordering::Relaxed));
    let agent: ureq::Agent = ureq::Agent::config_builder()
        .timeout_connect(Some(Duration::from_secs(20)))
        .timeout_recv_response(Some(Duration::from_secs(30)))
        // A throttled session can make a 4 MB file slow, but not this slow.
        .timeout_recv_body(Some(Duration::from_secs(600)))
        .user_agent(concat!("deepwork-ui/", env!("CARGO_PKG_VERSION")))
        .build()
        .into();
    let next = AtomicUsize::new(0);
    let error = Mutex::new(None::<String>);
    std::thread::scope(|s| {
        for _ in 0..WORKERS {
            s.spawn(|| {
                while error.lock().unwrap().is_none() {
                    let Some(f) = todo.get(next.fetch_add(1, Ordering::Relaxed)) else {
                        break;
                    };
                    let url = format!("{}{}", manifest.url, f.asset);
                    let got = fetch_one(&agent, &url, f, dir, |n| {
                        progress(done.fetch_add(n, Ordering::Relaxed) + n);
                    });
                    match got {
                        Ok(()) => {}
                        Err(e) => {
                            // Its partial bytes no longer count.
                            *error.lock().unwrap() = Some(format!("{}: {e}", f.path));
                        }
                    }
                }
            });
        }
    });
    let error = error.into_inner().unwrap();
    // Recount from disk: what failed mid-file was counted as it came in.
    let on_disk = manifest
        .files
        .iter()
        .filter(|f| fs::metadata(dir.join(&f.path)).is_ok_and(|m| m.len() == f.size))
        .map(|f| f.size)
        .sum();
    match error {
        None => Ok(()),
        Some(e) => Err((on_disk, e)),
    }
}

fn fetch_one(
    agent: &ureq::Agent,
    url: &str,
    f: &Entry,
    dir: &Path,
    progress: impl Fn(u64),
) -> Result<(), String> {
    let target = dir.join(&f.path);
    let part = target.with_file_name(format!(
        ".{}.part",
        target
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("file")
    ));
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("creating {}: {e}", parent.display()))?;
    }
    let mut response = agent.get(url).call().map_err(|e| e.to_string())?;
    let mut body = response.body_mut().with_config().limit(f.size + 1).reader();
    let mut out = File::create(&part).map_err(|e| format!("writing {}: {e}", part.display()))?;
    let mut hash = Sha256::new();
    let mut size = 0u64;
    let mut buf = vec![0u8; 64 * 1024];
    loop {
        let n = body.read(&mut buf).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        out.write_all(&buf[..n])
            .map_err(|e| format!("writing {}: {e}", part.display()))?;
        hash.update(&buf[..n]);
        size += n as u64;
        progress(n as u64);
    }
    out.sync_all().map_err(|e| e.to_string())?;
    let sum = hex(&hash.finalize());
    if size != f.size || sum != f.sha256 {
        let _ = fs::remove_file(&part);
        return Err(format!(
            "got {size} bytes with SHA-256 {sum}, expected {} bytes with {}",
            f.size, f.sha256
        ));
    }
    fs::rename(&part, &target).map_err(|e| format!("saving {}: {e}", target.display()))
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn models(files: &[&str], dir: &Path) -> Models {
        Models {
            files: files
                .iter()
                .map(|p| {
                    let e = Entry {
                        path: p.to_string(),
                        size: 0,
                        sha256: String::new(),
                        asset: p.replace('/', "."),
                    };
                    (p.to_string(), e)
                })
                .collect(),
            dir: Some(dir.to_path_buf()),
            state: Mutex::new(Status::Ready { base: base() }),
            retry_at: Mutex::new(None),
        }
    }

    fn get(m: &Models, path: &str) -> StatusCode {
        let req = Request::builder()
            .uri(format!("models://localhost/{path}"))
            .body(Vec::new())
            .unwrap();
        m.serve(&req).status()
    }

    #[test]
    fn serves_only_manifest_files() {
        let dir = std::env::temp_dir().join(format!("deepwork-models-test-{}", std::process::id()));
        fs::create_dir_all(dir.join("tex")).unwrap();
        fs::write(dir.join("a1.glb"), b"glb").unwrap();
        fs::write(dir.join("tex/brick.bc7"), b"bc7").unwrap();
        fs::write(dir.join("secret"), b"no").unwrap();
        let m = models(&["a1.glb", "tex/brick.bc7"], &dir);
        assert_eq!(get(&m, "a1.glb"), StatusCode::OK);
        assert_eq!(get(&m, "tex/brick.bc7"), StatusCode::OK);
        assert_eq!(get(&m, "secret"), StatusCode::NOT_FOUND);
        assert_eq!(get(&m, "../etc/passwd"), StatusCode::NOT_FOUND);
        // Not served until the pack is whole.
        m.set(Status::Downloading { done: 0, total: 1 });
        assert_eq!(get(&m, "a1.glb"), StatusCode::NOT_FOUND);
        // An override directory serves plain names, never a way out of it.
        let o = models(&[], &dir);
        assert_eq!(get(&o, "secret"), StatusCode::OK);
        assert_eq!(get(&o, "tex/../secret"), StatusCode::NOT_FOUND);
        assert_eq!(get(&o, "tex//brick.bc7"), StatusCode::NOT_FOUND);
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn manifest_parses() {
        let m: Manifest = serde_json::from_str(include_str!("../models.json")).unwrap();
        assert!(
            m.url
                .starts_with("https://github.com/Sagyam/DeepWork/releases/download/models-")
        );
        assert!(m.url.ends_with(&format!("models-{}/", m.id)));
        for f in &m.files {
            assert_eq!(f.sha256.len(), 64);
            assert_eq!(f.asset, f.path.replace('/', "."));
            assert!(!f.path.contains(".."));
        }
    }
}
