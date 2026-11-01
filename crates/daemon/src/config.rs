//! Daemon configuration, read from `/etc/deepwork/config.toml`.
//!
//! Every field has a default, so a missing file means "use the built-in
//! profile". A `[profiles]` table in the file replaces the defaults entirely.

use std::collections::BTreeMap;
use std::net::SocketAddr;
use std::path::Path;

use anyhow::{Context, Result, bail, ensure};
use serde::Deserialize;

pub const DEFAULT_PATH: &str = "/etc/deepwork/config.toml";

#[derive(Debug, Clone, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Config {
    pub dns: DnsConfig,
    pub session: SessionConfig,
    pub profiles: BTreeMap<String, Profile>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct DnsConfig {
    /// Port the forwarder listens on, on 127.0.0.1 and ::1.
    pub port: u16,
    /// Upstreams, tried in order.
    pub upstreams: Vec<Upstream>,
    /// Names under these suffixes go to a specific server instead.
    pub forward: Vec<ForwardZone>,
    /// During a session, point systemd-resolved at the forwarder through a
    /// runtime drop-in. Needed when resolved uses DNS-over-TLS itself.
    pub manage_resolved: bool,
}

/// `"9.9.9.9:53"` for plain DNS, or
/// `{ addr = "9.9.9.9:853", tls_name = "dns.quad9.net" }` for DNS-over-TLS.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(untagged)]
pub enum Upstream {
    Plain(SocketAddr),
    Tls { addr: SocketAddr, tls_name: String },
}

impl Upstream {
    pub fn addr(&self) -> SocketAddr {
        match self {
            Upstream::Plain(addr) | Upstream::Tls { addr, .. } => *addr,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ForwardZone {
    pub suffix: String,
    pub server: SocketAddr,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct SessionConfig {
    pub default_profile: String,
    /// A stopwatch cannot be stopped before this many seconds.
    pub stopwatch_min_secs: u64,
    /// How long a surrender takes, with enforcement still on.
    pub surrender_wait_secs: u64,
}

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Profile {
    pub throttle: Throttle,
    /// Drop UDP 443 so browsers fall back from QUIC to TCP.
    pub block_quic: bool,
    pub rules: Vec<Rule>,
}

#[derive(Debug, Clone, Copy, PartialEq, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Throttle {
    /// Added round-trip time, split evenly between upload and download.
    pub rtt_ms: u32,
    pub jitter_ms: u32,
    /// Bandwidth cap per direction.
    pub rate_kbit: u32,
    pub loss_pct: f32,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Rule {
    /// Matches this domain and every subdomain of it.
    pub domain: String,
    #[serde(default)]
    pub action: Action,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    #[default]
    Throttle,
    Block,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            dns: DnsConfig::default(),
            session: SessionConfig::default(),
            profiles: BTreeMap::from([("deep".to_string(), Profile::default())]),
        }
    }
}

impl Default for DnsConfig {
    fn default() -> Self {
        Self {
            port: 5454,
            upstreams: vec![
                Upstream::Tls {
                    addr: "9.9.9.9:853".parse().unwrap(),
                    tls_name: "dns.quad9.net".into(),
                },
                Upstream::Tls {
                    addr: "1.1.1.1:853".parse().unwrap(),
                    tls_name: "cloudflare-dns.com".into(),
                },
            ],
            forward: vec![ForwardZone {
                suffix: "ts.net".into(),
                server: "100.100.100.100:53".parse().unwrap(),
            }],
            manage_resolved: true,
        }
    }
}

impl Default for SessionConfig {
    fn default() -> Self {
        Self {
            default_profile: "deep".into(),
            stopwatch_min_secs: 10 * 60,
            surrender_wait_secs: 10 * 60,
        }
    }
}

impl Default for Throttle {
    fn default() -> Self {
        Self {
            rtt_ms: 300,
            jitter_ms: 50,
            rate_kbit: 512,
            loss_pct: 0.0,
        }
    }
}

const DEFAULT_THROTTLED: &[&str] = &[
    "youtube.com",
    "youtu.be",
    "googlevideo.com",
    "ytimg.com",
    "reddit.com",
    "redd.it",
    "redditmedia.com",
    "redditstatic.com",
    "x.com",
    "twitter.com",
    "twimg.com",
    "instagram.com",
    "cdninstagram.com",
    "facebook.com",
    "fbcdn.net",
    "tiktok.com",
    "tiktokcdn.com",
    "netflix.com",
    "nflxvideo.net",
    "twitch.tv",
    "ttvnw.net",
];

impl Default for Profile {
    fn default() -> Self {
        Self {
            throttle: Throttle::default(),
            block_quic: true,
            rules: DEFAULT_THROTTLED
                .iter()
                .map(|d| Rule {
                    domain: (*d).into(),
                    action: Action::Throttle,
                })
                .collect(),
        }
    }
}

impl Config {
    /// Loads the config at `path`, falling back to defaults if it does not exist.
    pub fn load(path: &Path) -> Result<Self> {
        let config = match std::fs::read_to_string(path) {
            Ok(text) => {
                toml::from_str(&text).with_context(|| format!("parsing {}", path.display()))?
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Self::default(),
            Err(e) => return Err(e).with_context(|| format!("reading {}", path.display())),
        };
        config.validate()?;
        Ok(config)
    }

    pub fn validate(&self) -> Result<()> {
        ensure!(
            !self.profiles.is_empty(),
            "at least one profile is required"
        );
        ensure!(
            self.profiles.contains_key(&self.session.default_profile),
            "default_profile {:?} is not defined",
            self.session.default_profile
        );
        ensure!(
            !self.dns.upstreams.is_empty(),
            "at least one DNS upstream is required"
        );
        for upstream in &self.dns.upstreams {
            if let Upstream::Tls { tls_name, .. } = upstream {
                validate_domain(tls_name).context("upstream tls_name")?;
            }
        }
        for zone in &self.dns.forward {
            validate_domain(&zone.suffix)?;
        }
        for (name, profile) in &self.profiles {
            let t = &profile.throttle;
            ensure!(
                t.rate_kbit >= 8,
                "profile {name}: rate_kbit must be at least 8"
            );
            ensure!(
                t.rtt_ms <= 10_000,
                "profile {name}: rtt_ms must be at most 10000"
            );
            ensure!(
                t.jitter_ms <= t.rtt_ms,
                "profile {name}: jitter_ms must not exceed rtt_ms"
            );
            ensure!(
                (0.0..=50.0).contains(&t.loss_pct),
                "profile {name}: loss_pct must be between 0 and 50"
            );
            for rule in &profile.rules {
                validate_domain(&rule.domain).with_context(|| format!("profile {name}"))?;
            }
        }
        Ok(())
    }
}

fn validate_domain(domain: &str) -> Result<()> {
    let ok = !domain.is_empty()
        && domain.len() <= 253
        && !domain.starts_with('.')
        && !domain.ends_with('.')
        && domain
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-' || b == b'.');
    if !ok {
        bail!("invalid domain {domain:?}: use lowercase ASCII like \"example.com\"");
    }
    Ok(())
}

/// True if `name` is `suffix` or a subdomain of it. Both must be lowercase
/// without a trailing dot.
pub fn domain_matches(name: &str, suffix: &str) -> bool {
    name == suffix
        || (name.len() > suffix.len()
            && name.ends_with(suffix)
            && name.as_bytes()[name.len() - suffix.len() - 1] == b'.')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_are_valid() {
        Config::default().validate().unwrap();
    }

    #[test]
    fn parses_partial_file() {
        let config: Config = toml::from_str(
            r#"
            [session]
            default_profile = "work"

            [profiles.work]
            rules = [
                { domain = "youtube.com" },
                { domain = "reddit.com", action = "block" },
            ]
            "#,
        )
        .unwrap();
        config.validate().unwrap();
        let work = &config.profiles["work"];
        assert_eq!(work.rules[1].action, Action::Block);
        assert_eq!(work.throttle, Throttle::default());
        assert_eq!(config.dns.port, 5454);
    }

    #[test]
    fn parses_upstreams() {
        let config: Config = toml::from_str(
            r#"
            [dns]
            upstreams = [
                { addr = "45.90.28.0:853", tls_name = "abc123.dns.nextdns.io" },
                "192.168.1.1:53",
            ]
            "#,
        )
        .unwrap();
        config.validate().unwrap();
        assert_eq!(
            config.dns.upstreams[0],
            Upstream::Tls {
                addr: "45.90.28.0:853".parse().unwrap(),
                tls_name: "abc123.dns.nextdns.io".into()
            }
        );
        assert_eq!(
            config.dns.upstreams[1],
            Upstream::Plain("192.168.1.1:53".parse().unwrap())
        );
    }

    #[test]
    fn rejects_bad_domains() {
        for bad in [
            "",
            "YouTube.com",
            "a b.com",
            ".x.com",
            "x.com.",
            "x;flush ruleset",
        ] {
            assert!(validate_domain(bad).is_err(), "{bad:?} should be rejected");
        }
    }

    #[test]
    fn suffix_matching() {
        assert!(domain_matches("youtube.com", "youtube.com"));
        assert!(domain_matches("www.youtube.com", "youtube.com"));
        assert!(!domain_matches("notyoutube.com", "youtube.com"));
        assert!(!domain_matches("youtube.com.evil", "youtube.com"));
        assert!(!domain_matches("com", "youtube.com"));
    }
}
