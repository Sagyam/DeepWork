//! Daemon configuration, read from `/etc/deepwork/config.toml`.
//!
//! Every field has a default, so a missing file means "use the built-in
//! profile". A `[profiles]` table in the file replaces the defaults entirely.

use std::collections::BTreeMap;
use std::net::SocketAddr;
use std::path::Path;

use anyhow::{Context, Result, bail, ensure};
use jiff::civil::{Time, Weekday};
use serde::Deserialize;

pub const DEFAULT_PATH: &str = "/etc/deepwork/config.toml";

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Config {
    pub dns: DnsConfig,
    pub session: SessionConfig,
    pub schedule: ScheduleConfig,
    pub nudge: NudgeConfig,
    pub inverted: InvertedConfig,
    pub routines: Vec<Routine>,
    pub profiles: BTreeMap<String, Profile>,
}

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct ScheduleConfig {
    /// Clients warn this long before a routine starts.
    pub heads_up_secs: u64,
    /// Routine runs that may be skipped per week (Monday to Sunday).
    pub skip_tokens_per_week: u32,
}

/// Reminders to start a session when none has run for a while, inside active
/// hours.
#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct NudgeConfig {
    pub enabled: bool,
    pub days: Vec<Day>,
    pub from: ClockTime,
    pub until: ClockTime,
    /// First nudge after this many minutes without a session.
    pub after_mins: u32,
    /// Then one more, a notch more urgent, every this many minutes.
    pub repeat_mins: u32,
}

/// Inverted mode: distractions are throttled whenever no session runs, and
/// completed sessions earn free minutes that lift the throttle for a while.
#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct InvertedConfig {
    pub enabled: bool,
    /// The profile throttled outside sessions; `default_profile` if unset.
    /// Its `lock_docker` is ignored: outside sessions nothing is locked.
    pub profile: Option<String>,
    /// Free minutes earned per hour of completed focus.
    pub free_mins_per_hour: u32,
    /// Free minutes are banked up to this many.
    pub max_bank_mins: u32,
}

/// A focus slot that starts a countdown on its own.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Routine {
    pub name: String,
    /// Every day if empty.
    #[serde(default)]
    pub days: Vec<Day>,
    pub start: ClockTime,
    pub duration_mins: u32,
    /// The default profile if unset.
    pub profile: Option<String>,
}

/// `"mon"` .. `"sun"`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(try_from = "String")]
pub struct Day(pub Weekday);

impl TryFrom<String> for Day {
    type Error = String;
    fn try_from(s: String) -> Result<Self, String> {
        let day = match s.to_ascii_lowercase().as_str() {
            "mon" | "monday" => Weekday::Monday,
            "tue" | "tuesday" => Weekday::Tuesday,
            "wed" | "wednesday" => Weekday::Wednesday,
            "thu" | "thursday" => Weekday::Thursday,
            "fri" | "friday" => Weekday::Friday,
            "sat" | "saturday" => Weekday::Saturday,
            "sun" | "sunday" => Weekday::Sunday,
            _ => return Err(format!("unknown day {s:?}: use mon, tue, ... sun")),
        };
        Ok(Day(day))
    }
}

impl std::fmt::Display for Day {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self.0 {
            Weekday::Monday => "mon",
            Weekday::Tuesday => "tue",
            Weekday::Wednesday => "wed",
            Weekday::Thursday => "thu",
            Weekday::Friday => "fri",
            Weekday::Saturday => "sat",
            Weekday::Sunday => "sun",
        })
    }
}

/// True if `days` is empty (every day) or contains `day`.
pub fn on_day(days: &[Day], day: Weekday) -> bool {
    days.is_empty() || days.iter().any(|d| d.0 == day)
}

/// Local wall-clock time, `"HH:MM"`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(try_from = "String")]
pub struct ClockTime(pub Time);

impl std::fmt::Display for ClockTime {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{:02}:{:02}", self.0.hour(), self.0.minute())
    }
}

impl TryFrom<String> for ClockTime {
    type Error = String;
    fn try_from(s: String) -> Result<Self, String> {
        let bad = || format!("bad time {s:?}: use 24-hour \"HH:MM\"");
        let (h, m) = s.split_once(':').ok_or_else(bad)?;
        if h.is_empty() || h.len() > 2 || m.len() != 2 {
            return Err(bad());
        }
        let h: i8 = h.parse().map_err(|_| bad())?;
        let m: i8 = m.parse().map_err(|_| bad())?;
        Time::new(h, m, 0, 0).map(ClockTime).map_err(|_| bad())
    }
}

#[derive(Debug, Clone, PartialEq, Deserialize)]
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
    /// During a session, DNS that containers and VMs send to other servers
    /// (port 53, forwarded from docker / br- / virbr interfaces) is sent here
    /// instead, e.g. resolved's `DNSStubListenerExtra=172.17.0.1`. IPv4 only.
    /// Unset: such queries are rejected. Forwarded IPv6 DNS is always rejected.
    pub container_dns: Option<std::net::SocketAddrV4>,
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

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ForwardZone {
    pub suffix: String,
    pub server: SocketAddr,
}

#[derive(Debug, Clone, PartialEq, Deserialize)]
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
    /// Judge new TLS connections by the server name in their ClientHello
    /// (NFQUEUE), on top of the addresses learned from DNS.
    pub inspect_sni: bool,
    /// Take group access off `/run/docker.sock`, so members of the `docker`
    /// group cannot start privileged containers to get around the session.
    pub lock_docker: bool,
    pub rules: Vec<Rule>,
    /// Harsher throttles the longer throttled sites are used in a session.
    /// `[]` turns escalation off.
    pub escalation: Vec<Stage>,
}

/// After `after_mins` of distracted time in a session, use `throttle`.
#[derive(Debug, Clone, Copy, PartialEq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Stage {
    pub after_mins: u32,
    pub throttle: Throttle,
}

impl Profile {
    /// The escalation stage reached after `distracted` time (0 = none) and
    /// the throttle that goes with it.
    pub fn throttle_after(&self, distracted: std::time::Duration) -> (usize, Throttle) {
        let reached = self
            .escalation
            .iter()
            .take_while(|s| distracted.as_secs() >= u64::from(s.after_mins) * 60)
            .count();
        match reached {
            0 => (0, self.throttle),
            n => (n, self.escalation[n - 1].throttle),
        }
    }
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
            schedule: ScheduleConfig::default(),
            nudge: NudgeConfig::default(),
            inverted: InvertedConfig::default(),
            routines: Vec::new(),
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
            container_dns: None,
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

impl Default for ScheduleConfig {
    fn default() -> Self {
        Self {
            heads_up_secs: 5 * 60,
            skip_tokens_per_week: 2,
        }
    }
}

impl Default for NudgeConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            days: Vec::new(),
            from: ClockTime(Time::constant(9, 0, 0, 0)),
            until: ClockTime(Time::constant(21, 0, 0, 0)),
            after_mins: 30,
            repeat_mins: 15,
        }
    }
}

impl Default for InvertedConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            profile: None,
            free_mins_per_hour: 12,
            max_bank_mins: 120,
        }
    }
}

impl Default for Throttle {
    fn default() -> Self {
        Self {
            rtt_ms: 400,
            jitter_ms: 50,
            rate_kbit: 256,
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
            inspect_sni: true,
            lock_docker: false,
            rules: DEFAULT_THROTTLED
                .iter()
                .map(|d| Rule {
                    domain: (*d).into(),
                    action: Action::Throttle,
                })
                .collect(),
            escalation: vec![
                Stage {
                    after_mins: 10,
                    throttle: Throttle {
                        rtt_ms: 500,
                        rate_kbit: 192,
                        ..Throttle::default()
                    },
                },
                Stage {
                    after_mins: 20,
                    throttle: Throttle {
                        rtt_ms: 600,
                        rate_kbit: 128,
                        ..Throttle::default()
                    },
                },
            ],
        }
    }
}

impl Config {
    /// The profile throttled outside sessions in inverted mode.
    pub fn ambient_profile(&self) -> Option<&Profile> {
        if !self.inverted.enabled {
            return None;
        }
        let name = self
            .inverted
            .profile
            .as_ref()
            .unwrap_or(&self.session.default_profile);
        self.profiles.get(name)
    }

    /// Loads the config at `path`, falling back to defaults if it does not exist.
    pub fn load(path: &Path) -> Result<Self> {
        Self::parse(&Self::read_text(path)?).with_context(|| format!("in {}", path.display()))
    }

    /// The file's text, or `""` (the defaults) if it does not exist.
    pub fn read_text(path: &Path) -> Result<String> {
        match std::fs::read_to_string(path) {
            Ok(text) => Ok(text),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(String::new()),
            Err(e) => Err(e).with_context(|| format!("reading {}", path.display())),
        }
    }

    /// Parses and validates config text. Empty text means the defaults.
    pub fn parse(text: &str) -> Result<Self> {
        let config: Self = if text.trim().is_empty() {
            Self::default()
        } else {
            toml::from_str(text).context("parsing config")?
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
        let n = &self.nudge;
        ensure!(n.from.0 < n.until.0, "nudge: from must be before until");
        ensure!(
            n.after_mins >= 1 && n.repeat_mins >= 1,
            "nudge: after_mins and repeat_mins must be at least 1"
        );
        let inv = &self.inverted;
        if let Some(p) = &inv.profile {
            ensure!(
                self.profiles.contains_key(p),
                "inverted: profile {p:?} is not defined"
            );
        }
        ensure!(
            inv.free_mins_per_hour <= 60,
            "inverted: free_mins_per_hour must be at most 60"
        );
        ensure!(
            inv.max_bank_mins <= 24 * 60,
            "inverted: max_bank_mins must be at most 1440"
        );
        let max_mins = crate::session::MAX_SESSION.as_secs() / 60;
        for (i, r) in self.routines.iter().enumerate() {
            ensure!(
                !r.name.is_empty()
                    && r.name.len() <= 64
                    && r.name
                        .bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_'),
                "routine {:?}: names may only use letters, digits, - and _",
                r.name
            );
            ensure!(
                self.routines[..i].iter().all(|o| o.name != r.name),
                "routine {:?} is defined twice",
                r.name
            );
            ensure!(
                (1..=max_mins).contains(&u64::from(r.duration_mins)),
                "routine {}: duration_mins must be between 1 and {max_mins}",
                r.name
            );
            if let Some(p) = &r.profile {
                ensure!(
                    self.profiles.contains_key(p),
                    "routine {}: profile {p:?} is not defined",
                    r.name
                );
            }
        }
        for (name, profile) in &self.profiles {
            validate_throttle(&profile.throttle).with_context(|| format!("profile {name}"))?;
            let mut last = 0;
            for stage in &profile.escalation {
                ensure!(
                    stage.after_mins > last,
                    "profile {name}: escalation after_mins must be at least 1 and increasing"
                );
                last = stage.after_mins;
                validate_throttle(&stage.throttle)
                    .with_context(|| format!("profile {name}, escalation after {last} min"))?;
            }
            for rule in &profile.rules {
                validate_domain(&rule.domain).with_context(|| format!("profile {name}"))?;
            }
        }
        Ok(())
    }
}

fn validate_throttle(t: &Throttle) -> Result<()> {
    ensure!(t.rate_kbit >= 8, "rate_kbit must be at least 8");
    ensure!(t.rtt_ms <= 10_000, "rtt_ms must be at most 10000");
    ensure!(t.jitter_ms <= t.rtt_ms, "jitter_ms must not exceed rtt_ms");
    ensure!(
        (0.0..=50.0).contains(&t.loss_pct),
        "loss_pct must be between 0 and 50"
    );
    Ok(())
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
    fn escalation_stages() {
        let p = Profile::default();
        let min = |m: u64| std::time::Duration::from_secs(m * 60);
        assert_eq!(p.throttle_after(min(9)), (0, p.throttle));
        assert_eq!(p.throttle_after(min(10)).0, 1);
        assert_eq!(p.throttle_after(min(25)), (2, p.escalation[1].throttle));

        let config: Config = toml::from_str(
            r#"
            [profiles.deep]
            escalation = [
                { after_mins = 5, throttle = { rate_kbit = 100 } },
                { after_mins = 5, throttle = { rate_kbit = 50 } },
            ]
            "#,
        )
        .unwrap();
        assert!(config.validate().is_err());
        let off: Config = toml::from_str("[profiles.deep]\nescalation = []").unwrap();
        assert_eq!(off.profiles["deep"].throttle_after(min(600)).0, 0);
    }

    #[test]
    fn parses_inverted() {
        assert!(Config::default().ambient_profile().is_none());
        let config = Config::parse(
            "[inverted]\nenabled = true\nfree_mins_per_hour = 10\n[profiles.deep]\n[profiles.home]\nrules = []",
        )
        .unwrap();
        assert_eq!(config.ambient_profile(), Some(&config.profiles["deep"]));
        assert_eq!(config.inverted.max_bank_mins, 120);
        let home =
            Config::parse("[inverted]\nenabled = true\nprofile = \"home\"\n[profiles.deep]\n[profiles.home]\nrules = []")
                .unwrap();
        assert!(home.ambient_profile().unwrap().rules.is_empty());
        for bad in [
            "[inverted]\nprofile = \"nope\"",
            "[inverted]\nfree_mins_per_hour = 61",
            "[inverted]\nmax_bank_mins = 2000",
        ] {
            assert!(Config::parse(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn parses_routines() {
        let config: Config = toml::from_str(
            r#"
            [schedule]
            skip_tokens_per_week = 1

            [[routines]]
            name = "morning"
            days = ["mon", "tue", "Friday"]
            start = "9:00"
            duration_mins = 90
            "#,
        )
        .unwrap();
        config.validate().unwrap();
        let r = &config.routines[0];
        assert_eq!(r.start.0, Time::constant(9, 0, 0, 0));
        assert_eq!(r.days[2].0, Weekday::Friday);
        assert_eq!(r.start.to_string(), "09:00");
        assert_eq!(r.days[2].to_string(), "fri");
        assert_eq!(config.schedule.heads_up_secs, 300);

        for bad in ["24:00", "9", "09:5", "9:60", "-1:00"] {
            assert!(ClockTime::try_from(bad.to_string()).is_err(), "{bad}");
        }
        assert!(Day::try_from("funday".to_string()).is_err());
    }

    #[test]
    fn rejects_bad_routines() {
        for bad in [
            r#"[[routines]]
            name = "a"
            start = "09:00"
            duration_mins = 400"#,
            r#"[[routines]]
            name = "a"
            start = "09:00"
            duration_mins = 60
            profile = "nope""#,
            r#"[[routines]]
            name = "a b"
            start = "09:00"
            duration_mins = 60"#,
            r#"[[routines]]
            name = "a"
            start = "09:00"
            duration_mins = 60
            [[routines]]
            name = "a"
            start = "10:00"
            duration_mins = 60"#,
        ] {
            let config: Config = toml::from_str(bad).unwrap();
            assert!(config.validate().is_err(), "{bad}");
        }
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
