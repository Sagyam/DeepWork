//! The daemon's wall clock and focus time. In a normal build both are real.
//!
//! The `speedrun` feature runs them `SPEED` times faster, to play through the
//! progression in an afternoon: a focused hour passes in seconds, a day in
//! minutes. Wall time runs from an anchor kept in the state directory, so it
//! never goes backwards across restarts. Never ship this build.

use std::path::Path;
use std::sync::OnceLock;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use jiff::Timestamp;

/// How many times faster than real time the daemon's clock runs.
pub const SPEED: u32 = if cfg!(feature = "speedrun") { 360 } else { 1 };

static ANCHOR: OnceLock<i64> = OnceLock::new();

fn real_now() -> Duration {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
}

/// Fixes where sped-up time starts: read from `state_dir`, or now on first run.
pub fn init(state_dir: &Path) {
    if SPEED == 1 {
        return;
    }
    let path = state_dir.join("speedrun-anchor");
    let anchor = std::fs::read_to_string(&path)
        .ok()
        .and_then(|s| s.trim().parse().ok())
        .unwrap_or_else(|| {
            let now = real_now().as_secs() as i64;
            if let Err(e) = std::fs::write(&path, now.to_string()) {
                tracing::error!("could not save {}: {e}", path.display());
            }
            now
        });
    let _ = ANCHOR.set(anchor);
    tracing::warn!("SPEEDRUN build: time runs {SPEED}x from {anchor}");
}

/// Now, as the daemon sees it.
pub fn timestamp() -> Timestamp {
    let real = real_now();
    let Some(&anchor) = ANCHOR.get().filter(|_| SPEED > 1) else {
        return Timestamp::try_from(SystemTime::now()).unwrap_or(Timestamp::UNIX_EPOCH);
    };
    let since = real.saturating_sub(Duration::from_secs(anchor.max(0) as u64));
    let virt = Duration::from_secs(anchor as u64) + since * SPEED;
    Timestamp::from_second(virt.as_secs() as i64).unwrap_or(Timestamp::UNIX_EPOCH)
}

/// Unix seconds, as the daemon sees them.
pub fn unix_now() -> i64 {
    timestamp().as_second()
}

/// A real interval in the daemon's time.
pub fn scale(real: Duration) -> Duration {
    real * SPEED
}
