//! Managed browser policies that keep lookups on the system resolver:
//! DNS-over-HTTPS off (it would bypass deepworkd entirely) and Encrypted
//! Client Hello off (phase 4 reads the SNI of new TLS connections).
//!
//! Firefox-family browsers (Zen) read `distribution/policies.json`, which
//! package updates overwrite, so the daemon merges its keys back in at
//! startup, at session start and every minute. Chromium-family browsers read
//! every file in their managed policy directory; ours is `deepwork.json`.
//! Browsers pick policies up on restart.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde_json::{Map, Value, json};

const FIREFOX_ECH_PREFS: [&str; 2] = [
    "network.dns.echconfig.enabled",
    "network.dns.http3_echconfig.enabled",
];

const CHROMIUM_POLICY_DIRS: [&str; 3] = [
    "/etc/chromium/policies/managed",
    "/etc/opt/chrome/policies/managed",
    "/etc/brave/policies/managed",
];

fn firefox_doh() -> Value {
    json!({ "Enabled": false, "Locked": true })
}

fn firefox_pref() -> Value {
    json!({ "Value": false, "Status": "locked" })
}

fn chromium_policy() -> String {
    let policy = json!({
        "DnsOverHttpsMode": "off",
        "EncryptedClientHelloEnabled": false,
    });
    format!("{}\n", serde_json::to_string_pretty(&policy).unwrap())
}

/// `existing` merged with our keys (`apply`) or with them taken out. `None`
/// if nothing changes. Keys the user or the package set are kept.
pub fn merge_firefox(existing: Option<&str>, apply: bool) -> Result<Option<String>> {
    let mut doc: Value = match existing {
        Some(text) if !text.trim().is_empty() => {
            serde_json::from_str(text).context("policies.json is not valid JSON")?
        }
        _ => json!({}),
    };
    let before = doc.clone();
    let root = doc
        .as_object_mut()
        .context("policies.json is not an object")?;
    let policies = root
        .entry("policies")
        .or_insert_with(|| Value::Object(Map::new()))
        .as_object_mut()
        .context("\"policies\" is not an object")?;
    if apply {
        policies.insert("DNSOverHTTPS".into(), firefox_doh());
        let prefs = policies
            .entry("Preferences")
            .or_insert_with(|| Value::Object(Map::new()))
            .as_object_mut()
            .context("\"Preferences\" is not an object")?;
        for pref in FIREFOX_ECH_PREFS {
            prefs.insert(pref.into(), firefox_pref());
        }
    } else {
        if policies.get("DNSOverHTTPS") == Some(&firefox_doh()) {
            policies.remove("DNSOverHTTPS");
        }
        if let Some(prefs) = policies
            .get_mut("Preferences")
            .and_then(Value::as_object_mut)
        {
            for pref in FIREFOX_ECH_PREFS {
                if prefs.get(pref) == Some(&firefox_pref()) {
                    prefs.remove(pref);
                }
            }
            if prefs.is_empty() {
                policies.remove("Preferences");
            }
        }
    }
    if doc == before && existing.is_some() {
        return Ok(None);
    }
    Ok(Some(format!("{}\n", serde_json::to_string_pretty(&doc)?)))
}

/// `distribution/policies.json` of every installed Firefox-family browser.
fn firefox_policy_files() -> Vec<PathBuf> {
    let mut apps: Vec<PathBuf> = std::fs::read_dir("/opt")
        .into_iter()
        .flatten()
        .flatten()
        .map(|e| e.path())
        .filter(|p| {
            p.file_name()
                .and_then(|n| n.to_str())
                .is_some_and(|n| n.starts_with("zen-browser"))
        })
        .collect();
    apps.extend(["/usr/lib/zen-browser", "/usr/lib/firefox"].map(PathBuf::from));
    apps.into_iter()
        // A real install, not a leftover distribution directory.
        .filter(|app| app.join("application.ini").exists())
        .map(|app| app.join("distribution/policies.json"))
        .collect()
}

fn write_if_changed(path: &Path, contents: &str) -> Result<bool> {
    if std::fs::read_to_string(path).is_ok_and(|old| old == contents) {
        return Ok(false);
    }
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)?;
    }
    let tmp = path.with_extension("deepwork-tmp");
    std::fs::write(&tmp, contents).with_context(|| format!("writing {}", tmp.display()))?;
    std::fs::rename(&tmp, path).with_context(|| format!("replacing {}", path.display()))?;
    Ok(true)
}

/// Applies or removes the policies. Returns the files that changed.
pub fn sync(apply: bool) -> Result<Vec<PathBuf>> {
    let mut changed = Vec::new();
    for path in firefox_policy_files() {
        let existing = std::fs::read_to_string(&path).ok();
        if existing.is_none() && !apply {
            continue;
        }
        let merged = merge_firefox(existing.as_deref(), apply)
            .with_context(|| format!("merging {}", path.display()))?;
        if let Some(text) = merged
            && write_if_changed(&path, &text)?
        {
            changed.push(path);
        }
    }
    for dir in CHROMIUM_POLICY_DIRS.map(Path::new) {
        let path = dir.join("deepwork.json");
        // `/etc/chromium` exists once Chromium is installed.
        let browser = dir.parent().and_then(Path::parent);
        if apply && browser.is_some_and(Path::exists) {
            if write_if_changed(&path, &chromium_policy())? {
                changed.push(path);
            }
        } else if !apply && path.exists() {
            std::fs::remove_file(&path)?;
            changed.push(path);
        }
    }
    Ok(changed)
}

#[cfg(test)]
mod tests {
    use super::*;

    const ZEN: &str = r#"{
  "policies": {
    "DisableAppUpdate": true,
    "Preferences": { "apz.overscroll.enabled": { "Value": true, "Status": "default" } }
  }
}"#;

    #[test]
    fn merges_and_keeps_other_keys() {
        let merged = merge_firefox(Some(ZEN), true).unwrap().unwrap();
        let doc: Value = serde_json::from_str(&merged).unwrap();
        let p = &doc["policies"];
        assert_eq!(p["DisableAppUpdate"], true);
        assert_eq!(p["DNSOverHTTPS"], firefox_doh());
        assert_eq!(p["Preferences"]["apz.overscroll.enabled"]["Value"], true);
        assert_eq!(
            p["Preferences"]["network.dns.echconfig.enabled"],
            firefox_pref()
        );

        // Applying again changes nothing.
        assert_eq!(merge_firefox(Some(&merged), true).unwrap(), None);

        // Removing puts the package's file back.
        let removed = merge_firefox(Some(&merged), false).unwrap().unwrap();
        let back: Value = serde_json::from_str(&removed).unwrap();
        assert_eq!(back, serde_json::from_str::<Value>(ZEN).unwrap());
    }

    #[test]
    fn creates_missing_file_and_rejects_garbage() {
        let created = merge_firefox(None, true).unwrap().unwrap();
        assert!(created.contains("DNSOverHTTPS"));
        assert!(merge_firefox(Some("{ not json"), true).is_err());
        assert!(merge_firefox(Some("[]"), true).is_err());
    }

    #[test]
    fn remove_leaves_user_values_alone() {
        let user = r#"{"policies": {"DNSOverHTTPS": {"Enabled": true}}}"#;
        assert_eq!(merge_firefox(Some(user), false).unwrap(), None);
    }
}
