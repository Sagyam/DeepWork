//! The config in effect, kept in the store, and the file on disk.
//!
//! The daemon does not simply trust `/etc/deepwork/config.toml`: on start and
//! on reload it compares the file with the config in effect. Tightening and
//! neutral changes apply at once; loosening ones wait [`LOOSEN_DELAY`] as a
//! pending change. Editing the file again restarts the wait; putting it back
//! cancels the pending change. A file that does not parse is ignored while a
//! config is in effect, so a typo cannot take the daemon down mid-session.

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use anyhow::{Context, Result, bail};
use tracing::warn;

use crate::config::Config;
use crate::loosen::{LOOSEN_DELAY, loosenings};
use crate::store::Store;

const EFFECTIVE: &str = "config.effective";
const PENDING: &str = "config.pending";

/// A loosening change waiting for its delay.
#[derive(Debug, Clone, PartialEq)]
pub struct Pending {
    pub text: String,
    pub config: Config,
    /// Unix seconds.
    pub applies_at: i64,
    pub reasons: Vec<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Outcome {
    Unchanged,
    /// The file is in effect now.
    Applied,
    /// A new loosening change is waiting.
    Queued,
    /// The file still matches the change already waiting.
    StillPending,
    /// The file was put back; the pending change is dropped.
    Cancelled,
    /// The file is broken; the config in effect is kept.
    Rejected(String),
}

/// What to do with `file` given the config in effect and any pending change.
/// Pure. `effective` is `None` on first start.
pub fn decide(
    effective: Option<(&str, &Config)>,
    pending: Option<&Pending>,
    file: &str,
    now: i64,
) -> (Outcome, Option<Pending>) {
    let parsed = Config::parse(file);
    let Some((eff_text, eff)) = effective else {
        return match parsed {
            Ok(_) => (Outcome::Applied, None),
            Err(e) => (Outcome::Rejected(format!("{e:#}")), None),
        };
    };
    let new = match parsed {
        Ok(c) => c,
        Err(e) => return (Outcome::Rejected(format!("{e:#}")), pending.cloned()),
    };
    if file == eff_text || new == *eff {
        let outcome = match pending {
            Some(_) => Outcome::Cancelled,
            None => Outcome::Unchanged,
        };
        return (outcome, None);
    }
    if let Some(p) = pending
        && p.text == file
    {
        return (Outcome::StillPending, Some(p.clone()));
    }
    let reasons = loosenings(eff, &new);
    if reasons.is_empty() {
        return (Outcome::Applied, None);
    }
    let pending = Pending {
        text: file.to_string(),
        config: new,
        applies_at: now + LOOSEN_DELAY.as_secs() as i64,
        reasons,
    };
    (Outcome::Queued, Some(pending))
}

/// The config in effect and the pending change, as stored.
pub struct State {
    pub config: Config,
    pub pending: Option<Pending>,
}

fn load_pending(store: &Store) -> Result<Option<Pending>> {
    let Some(json) = store.get(PENDING)? else {
        return Ok(None);
    };
    let v: serde_json::Value = serde_json::from_str(&json)?;
    let text = v["text"].as_str().unwrap_or_default().to_string();
    let Ok(config) = Config::parse(&text) else {
        warn!("dropping a stored pending config that no longer parses");
        return Ok(None);
    };
    Ok(Some(Pending {
        text,
        config,
        applies_at: v["applies_at"].as_i64().unwrap_or(0),
        reasons: v["reasons"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|r| r.as_str().map(String::from))
            .collect(),
    }))
}

fn store_state(store: &Store, text: &str, pending: Option<&Pending>) -> Result<()> {
    store.set(EFFECTIVE, Some(text))?;
    let json = pending.map(|p| {
        serde_json::json!({ "text": p.text, "applies_at": p.applies_at, "reasons": p.reasons })
            .to_string()
    });
    store.set(PENDING, json.as_deref())
}

fn stored_effective(store: &Store) -> Result<Option<(String, Config)>> {
    Ok(store
        .get(EFFECTIVE)?
        .and_then(|text| match Config::parse(&text) {
            Ok(config) => Some((text, config)),
            Err(e) => {
                warn!("stored config no longer parses, using the file: {e:#}");
                None
            }
        }))
}

/// Settles `file` against the config in effect and writes the store. Pure
/// apart from the store.
fn settle(
    store: &Store,
    stored: Option<(String, Config)>,
    pending: Option<Pending>,
    file: &str,
    now: i64,
) -> Result<(State, Outcome)> {
    let (outcome, pending) = decide(
        stored.as_ref().map(|(t, c)| (t.as_str(), c)),
        pending.as_ref(),
        file,
        now,
    );
    let (text, config) = match (&outcome, stored) {
        (Outcome::Applied, _) => (file.to_string(), Config::parse(file)?),
        // A broken file keeps the config in effect. Only fatal on first start.
        (Outcome::Rejected(e), None) => bail!("{e}"),
        (_, Some((text, config))) => (text, config),
        (_, None) => unreachable!("decide applies the file on first start"),
    };
    store_state(store, &text, pending.as_ref())?;
    Ok((State { config, pending }, outcome))
}

/// Reads the file and the stored state and settles them. Errors only when
/// there is no usable config at all (first start with a broken file).
pub fn sync(store: &Store, path: &Path, now: i64) -> Result<(State, Outcome)> {
    let stored = stored_effective(store)?;
    let pending = load_pending(store)?;
    let file = Config::read_text(path)?;
    settle(store, stored, pending, &file, now).with_context(|| format!("in {}", path.display()))
}

/// Writes config text and settles it, as if the user had edited the file.
/// Used by the app's settings screen. Validates before touching anything.
pub fn apply(store: &Store, path: &Path, text: &str, now: i64) -> Result<(State, Outcome)> {
    Config::parse(text).with_context(|| "checking the new settings")?;
    // Write first: if the file is not writable (a dry-run daemon owned by the
    // user, a read-only /etc), the config in the store is left untouched.
    write_file(path, text)?;
    let stored = stored_effective(store)?;
    let pending = load_pending(store)?;
    settle(store, stored, pending, text, now)
}

/// Replaces the config file atomically, so a crash or power loss cannot leave
/// a half-written file that the daemon would reject on start.
fn write_file(path: &Path, text: &str) -> Result<()> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).with_context(|| format!("creating {}", dir.display()))?;
    }
    let tmp = path.with_extension("toml.tmp");
    std::fs::write(&tmp, text).with_context(|| format!("writing {}", tmp.display()))?;
    std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o644))?;
    std::fs::rename(&tmp, path).with_context(|| format!("replacing {}", path.display()))?;
    Ok(())
}

/// Makes a pending change the config in effect.
pub fn promote(store: &Store, pending: &Pending) -> Result<()> {
    store_state(store, &pending.text, None)
}

#[cfg(test)]
mod tests {
    use super::*;

    const STRICT: &str = "[schedule]\nskip_tokens_per_week = 1\n";
    const LOOSE: &str = "[schedule]\nskip_tokens_per_week = 5\n";
    const STRICTER: &str = "[schedule]\nskip_tokens_per_week = 0\n";

    fn eff(text: &str) -> (String, Config) {
        (text.to_string(), Config::parse(text).unwrap())
    }

    #[test]
    fn first_start_applies_the_file() {
        assert_eq!(decide(None, None, LOOSE, 0).0, Outcome::Applied);
        assert!(matches!(
            decide(None, None, "nope = 1", 0).0,
            Outcome::Rejected(_)
        ));
    }

    #[test]
    fn tightening_applies_loosening_waits() {
        let (t, c) = eff(STRICT);
        assert_eq!(
            decide(Some((&t, &c)), None, STRICT, 0).0,
            Outcome::Unchanged
        );
        assert_eq!(
            decide(Some((&t, &c)), None, STRICTER, 0).0,
            Outcome::Applied
        );

        let (outcome, pending) = decide(Some((&t, &c)), None, LOOSE, 100);
        assert_eq!(outcome, Outcome::Queued);
        let p = pending.unwrap();
        assert_eq!(p.applies_at, 100 + 24 * 3600);
        assert_eq!(p.reasons, ["more skip tokens"]);

        // Same file again: the wait keeps running.
        let (outcome, again) = decide(Some((&t, &c)), Some(&p), LOOSE, 5000);
        assert_eq!(
            (outcome, again.unwrap().applies_at),
            (Outcome::StillPending, p.applies_at)
        );

        // A different loosening edit restarts the wait.
        let looser = "[schedule]\nskip_tokens_per_week = 6\n";
        let (outcome, again) = decide(Some((&t, &c)), Some(&p), looser, 5000);
        assert_eq!(
            (outcome, again.unwrap().applies_at),
            (Outcome::Queued, 5000 + 24 * 3600)
        );

        // Putting the file back cancels it; a stricter file applies and cancels it.
        assert_eq!(
            decide(Some((&t, &c)), Some(&p), STRICT, 0),
            (Outcome::Cancelled, None)
        );
        assert_eq!(
            decide(Some((&t, &c)), Some(&p), STRICTER, 0),
            (Outcome::Applied, None)
        );
    }

    #[test]
    fn apply_writes_the_file_and_respects_the_delay() {
        let dir = std::env::temp_dir().join(format!("dw-apply-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("config.toml");
        let store = Store::in_memory().unwrap();

        std::fs::write(&path, STRICT).unwrap();
        sync(&store, &path, 0).unwrap();

        let (state, outcome) = apply(&store, &path, STRICTER, 10).unwrap();
        assert_eq!(outcome, Outcome::Applied);
        assert_eq!(state.config.schedule.skip_tokens_per_week, 0);
        assert_eq!(std::fs::read_to_string(&path).unwrap(), STRICTER);

        let (state, outcome) = apply(&store, &path, LOOSE, 20).unwrap();
        assert_eq!(outcome, Outcome::Queued);
        assert_eq!(state.config.schedule.skip_tokens_per_week, 0);
        assert_eq!(state.pending.unwrap().applies_at, 20 + 24 * 3600);
        // The file still holds what the user asked for.
        assert_eq!(std::fs::read_to_string(&path).unwrap(), LOOSE);

        let (state, outcome) = sync(&store, &path, 30).unwrap();
        assert_eq!(outcome, Outcome::StillPending);
        assert_eq!(state.config.schedule.skip_tokens_per_week, 0);

        std::fs::write(&path, "[broken").unwrap();
        let (state, outcome) = sync(&store, &path, 40).unwrap();
        assert!(matches!(outcome, Outcome::Rejected(_)));
        assert_eq!(state.config.schedule.skip_tokens_per_week, 0);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn broken_file_keeps_the_config_and_the_pending_change() {
        let (t, c) = eff(STRICT);
        let (_, p) = decide(Some((&t, &c)), None, LOOSE, 0);
        let (outcome, kept) = decide(Some((&t, &c)), p.as_ref(), "[session\n", 0);
        assert!(matches!(outcome, Outcome::Rejected(_)));
        assert_eq!(kept, p);
    }

    #[test]
    fn sync_round_trip() {
        let dir = std::env::temp_dir().join(format!("dw-cfg-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("config.toml");
        let store = Store::in_memory().unwrap();

        std::fs::write(&path, STRICT).unwrap();
        let (state, outcome) = sync(&store, &path, 0).unwrap();
        assert_eq!(outcome, Outcome::Applied);
        assert_eq!(state.config, Config::parse(STRICT).unwrap());

        std::fs::write(&path, LOOSE).unwrap();
        let (state, outcome) = sync(&store, &path, 10).unwrap();
        assert_eq!(outcome, Outcome::Queued);
        assert_eq!(state.config.schedule.skip_tokens_per_week, 1);
        let p = state.pending.unwrap();

        // Survives a restart.
        let (state, outcome) = sync(&store, &path, 20).unwrap();
        assert_eq!(outcome, Outcome::StillPending);
        assert_eq!(state.pending.as_ref(), Some(&p));

        promote(&store, &p).unwrap();
        let (state, outcome) = sync(&store, &path, 30).unwrap();
        assert_eq!(outcome, Outcome::Unchanged);
        assert_eq!(state.config.schedule.skip_tokens_per_week, 5);

        std::fs::write(&path, "[broken").unwrap();
        let (state, outcome) = sync(&store, &path, 40).unwrap();
        assert!(matches!(outcome, Outcome::Rejected(_)));
        assert_eq!(state.config, Config::parse(LOOSE).unwrap());
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
