//! Which config changes loosen enforcement. Pure.
//!
//! Loosening changes wait [`LOOSEN_DELAY`] before they apply; tightening and
//! neutral changes (DNS plumbing, heads-up timing) apply at once. A change is
//! judged against the config in effect, field by field, and anything that is
//! not clearly stricter or equal counts as loosening.

use std::time::Duration;

use std::collections::BTreeSet;

use crate::config::{
    Action, Config, Day, InvertedConfig, ListMode, NudgeConfig, Profile, Routine, Throttle,
    Verdict, judge, on_day,
};

/// Fixed in code, so it cannot itself be loosened through the config.
pub const LOOSEN_DELAY: Duration = Duration::from_secs(24 * 60 * 60);

/// Every way `new` is looser than `old`, in words. Empty if none.
pub fn loosenings(old: &Config, new: &Config) -> Vec<String> {
    let mut out = Vec::new();
    let (os, ns) = (&old.session, &new.session);
    if ns.default_profile != os.default_profile {
        out.push(format!(
            "default profile {} -> {}",
            os.default_profile, ns.default_profile
        ));
    }
    if ns.stopwatch_min_secs < os.stopwatch_min_secs {
        out.push("shorter stopwatch minimum".into());
    }
    if ns.surrender_wait_secs < os.surrender_wait_secs {
        out.push("shorter surrender wait".into());
    }
    if new.schedule.skip_tokens_per_week > old.schedule.skip_tokens_per_week {
        out.push("more skip tokens".into());
    }
    nudge(&old.nudge, &new.nudge, &mut out);
    inverted(old, new, &mut out);
    for r in &old.routines {
        match new.routines.iter().find(|n| n.name == r.name) {
            None => out.push(format!("routine {} removed", r.name)),
            Some(n) => routine(r, n, &mut out),
        }
    }
    for (name, p) in &old.profiles {
        match new.profiles.get(name) {
            None => out.push(format!("profile {name} removed")),
            Some(n) => profile(name, p, n, &mut out),
        }
    }
    out
}

/// True if every day in `old` is also in `new` (empty means every day).
fn covers(new: &[Day], old: &[Day]) -> bool {
    use jiff::civil::Weekday::*;
    [
        Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday,
    ]
    .into_iter()
    .all(|d| !on_day(old, d) || on_day(new, d))
}

fn nudge(old: &NudgeConfig, new: &NudgeConfig, out: &mut Vec<String>) {
    if !old.enabled {
        return;
    }
    if !new.enabled {
        out.push("nudges turned off".into());
        return;
    }
    if !covers(&new.days, &old.days) {
        out.push("nudges on fewer days".into());
    }
    if new.from.0 > old.from.0 || new.until.0 < old.until.0 {
        out.push("shorter nudge hours".into());
    }
    if new.after_mins > old.after_mins || new.repeat_mins > old.repeat_mins {
        out.push("slower nudges".into());
    }
}

fn inverted(old: &Config, new: &Config, out: &mut Vec<String>) {
    let (o, n): (&InvertedConfig, &InvertedConfig) = (&old.inverted, &new.inverted);
    if o.enabled && !n.enabled {
        out.push("inverted mode turned off".into());
    }
    // Turning it on, with any settings, is stricter than having it off.
    if !o.enabled || !n.enabled {
        return;
    }
    if n.free_mins_per_hour > o.free_mins_per_hour {
        out.push("more free minutes per hour".into());
    }
    if n.max_bank_mins > o.max_bank_mins {
        out.push("larger free-minute bank".into());
    }
    let name = |c: &Config| {
        c.inverted
            .profile
            .clone()
            .unwrap_or_else(|| c.session.default_profile.clone())
    };
    if name(old) != name(new) {
        out.push(format!(
            "inverted mode uses profile {} instead of {}",
            name(new),
            name(old)
        ));
    }
}

fn routine(old: &Routine, new: &Routine, out: &mut Vec<String>) {
    let name = &old.name;
    if !covers(&new.days, &old.days) {
        out.push(format!("routine {name} on fewer days"));
    }
    if new.start != old.start {
        out.push(format!("routine {name} moved"));
    }
    if new.duration_mins < old.duration_mins {
        out.push(format!("routine {name} shortened"));
    }
    if new.profile != old.profile {
        out.push(format!("routine {name} uses another profile"));
    }
}

fn gentler(new: &Throttle, old: &Throttle) -> bool {
    new.rate_kbit > old.rate_kbit
        || new.rtt_ms < old.rtt_ms
        || new.jitter_ms < old.jitter_ms
        || new.loss_pct < old.loss_pct
}

fn profile(name: &str, old: &Profile, new: &Profile, out: &mut Vec<String>) {
    if old.block_quic && !new.block_quic {
        out.push(format!("profile {name}: QUIC allowed"));
    }
    if old.inspect_sni && !new.inspect_sni {
        out.push(format!("profile {name}: SNI inspection off"));
    }
    if old.lock_docker && !new.lock_docker {
        out.push(format!("profile {name}: Docker socket unlocked"));
    }
    if gentler(&new.throttle, &old.throttle) {
        out.push(format!("profile {name}: gentler throttle"));
    }
    for (i, stage) in old.escalation.iter().enumerate() {
        match new.escalation.get(i) {
            None => out.push(format!(
                "profile {name}: escalation stage {} removed",
                i + 1
            )),
            Some(n) if n.after_mins > stage.after_mins || gentler(&n.throttle, &stage.throttle) => {
                out.push(format!(
                    "profile {name}: escalation stage {} softened",
                    i + 1
                ));
            }
            Some(_) => {}
        }
    }
    if old.mode == ListMode::AllowOnly && new.mode == ListMode::BlockList {
        out.push(format!("profile {name}: allow-only mode off"));
    }
    // Every name is decided by the rules covering its most specific listed
    // domain (or by the mode, if none does), so comparing the listed domains
    // of both versions and the mode covers every name.
    let domains: BTreeSet<&str> = old
        .rules
        .iter()
        .chain(&new.rules)
        .map(|r| r.domain.as_str())
        .collect();
    let listed = |p: &Profile, d: &str| p.rules.iter().find(|r| r.domain == d).map(|r| r.action);
    for d in domains {
        let was = old.mode.verdict(judge(&old.rules, d));
        let now = new.mode.verdict(judge(&new.rules, d));
        if now >= was {
            continue;
        }
        let why = match (listed(old, d), listed(new, d), now) {
            (Some(_), None, _) => "removed",
            (Some(Action::Block), Some(Action::Throttle), _) => "throttled, not blocked",
            (_, Some(Action::Allow), _) => "allowed",
            (_, _, Verdict::Pass) => "full speed",
            _ => "slowed, not blocked",
        };
        out.push(format!("profile {name}: {d} {why}"));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(text: &str) -> Config {
        Config::parse(text).unwrap()
    }

    const BASE: &str = r#"
        [schedule]
        skip_tokens_per_week = 2

        [nudge]
        days = ["mon", "tue", "wed", "thu", "fri"]

        [[routines]]
        name = "morning"
        days = ["mon", "wed"]
        start = "09:00"
        duration_mins = 90

        [profiles.deep]
        rules = [{ domain = "youtube.com" }, { domain = "reddit.com", action = "block" }]
    "#;

    fn changed(from: &str, to: &str) -> Vec<String> {
        let base = parse(BASE);
        let new = parse(&BASE.replace(from, to));
        assert_ne!(base, new, "the replacement did not change anything: {from}");
        loosenings(&base, &new)
    }

    #[test]
    fn same_or_stricter_is_not_loosening() {
        assert!(loosenings(&parse(BASE), &parse(BASE)).is_empty());
        for (from, to) in [
            ("skip_tokens_per_week = 2", "skip_tokens_per_week = 1"),
            (
                r#"days = ["mon", "wed"]"#,
                r#"days = ["mon", "wed", "fri"]"#,
            ),
            (r#"days = ["mon", "wed"]"#, "days = []"),
            ("duration_mins = 90", "duration_mins = 120"),
            (
                r#"{ domain = "youtube.com" }"#,
                r#"{ domain = "youtube.com", action = "block" }"#,
            ),
            (
                r#"[profiles.deep]"#,
                "[profiles.extra]\n[profiles.deep]\nthrottle = { rate_kbit = 128 }",
            ),
            (
                "[[routines]]",
                "[[routines]]\nname = \"new\"\nstart = \"14:00\"\nduration_mins = 30\n[[routines]]",
            ),
            ("[schedule]", "[dns]\nport = 5999\n[schedule]"),
            ("[profiles.deep]", "[profiles.deep]\nlock_docker = true"),
            (
                "[schedule]",
                "[inverted]\nenabled = true\nfree_mins_per_hour = 30\n[schedule]",
            ),
        ] {
            assert_eq!(changed(from, to), Vec::<String>::new(), "{to}");
        }
    }

    #[test]
    fn loosening_is_named() {
        for (from, to, why) in [
            (
                "skip_tokens_per_week = 2",
                "skip_tokens_per_week = 3",
                "more skip tokens",
            ),
            (
                r#"days = ["mon", "wed"]"#,
                r#"days = ["mon"]"#,
                "routine morning on fewer days",
            ),
            (
                r#"start = "09:00""#,
                r#"start = "10:00""#,
                "routine morning moved",
            ),
            (
                "duration_mins = 90",
                "duration_mins = 60",
                "routine morning shortened",
            ),
            (
                r#", { domain = "reddit.com", action = "block" }"#,
                "",
                "profile deep: reddit.com removed",
            ),
            (
                r#"{ domain = "reddit.com", action = "block" }"#,
                r#"{ domain = "reddit.com" }"#,
                "profile deep: reddit.com throttled, not blocked",
            ),
            (
                "[profiles.deep]",
                "[profiles.deep]\nthrottle = { rate_kbit = 512 }",
                "profile deep: gentler throttle",
            ),
            (
                "[profiles.deep]",
                "[profiles.deep]\nblock_quic = false",
                "profile deep: QUIC allowed",
            ),
            (
                "[profiles.deep]",
                "[profiles.deep]\ninspect_sni = false",
                "profile deep: SNI inspection off",
            ),
            (
                r#"days = ["mon", "tue", "wed", "thu", "fri"]"#,
                r#"days = ["mon"]"#,
                "nudges on fewer days",
            ),
            ("[nudge]", "[nudge]\nenabled = false", "nudges turned off"),
            (
                "[nudge]",
                "[nudge]\nfrom = \"10:00\"",
                "shorter nudge hours",
            ),
            ("[nudge]", "[nudge]\nafter_mins = 60", "slower nudges"),
            (
                "[schedule]",
                "[session]\nsurrender_wait_secs = 60\n[schedule]",
                "shorter surrender wait",
            ),
            (
                "[profiles.deep]",
                "[profiles.deep]\nescalation = [{ after_mins = 10, throttle = { rtt_ms = 500, rate_kbit = 192 } }]",
                "profile deep: escalation stage 2 removed",
            ),
            (
                "[profiles.deep]",
                "[profiles.deep]\nescalation = [{ after_mins = 15, throttle = { rtt_ms = 500, rate_kbit = 192 } }, { after_mins = 20, throttle = { rtt_ms = 600, rate_kbit = 128 } }]",
                "profile deep: escalation stage 1 softened",
            ),
        ] {
            assert_eq!(changed(from, to), [why], "{to}");
        }
        let on = BASE.replace("[schedule]", "[inverted]\nenabled = true\n[schedule]");
        assert_eq!(
            loosenings(&parse(&on), &parse(BASE)),
            ["inverted mode turned off"]
        );
        let more = on.replace(
            "enabled = true",
            "enabled = true\nfree_mins_per_hour = 20\nmax_bank_mins = 200",
        );
        assert_eq!(
            loosenings(&parse(&on), &parse(&more)),
            ["more free minutes per hour", "larger free-minute bank"]
        );
        let other = on
            .replace("enabled = true", "enabled = true\nprofile = \"lax\"")
            .replace("[profiles.deep]", "[profiles.lax]\n[profiles.deep]");
        assert_eq!(
            loosenings(&parse(&on), &parse(&other)),
            ["inverted mode uses profile lax instead of deep"]
        );
        let locked = BASE.replace("[profiles.deep]", "[profiles.deep]\nlock_docker = true");
        assert_eq!(
            loosenings(&parse(&locked), &parse(BASE)),
            ["profile deep: Docker socket unlocked"]
        );
        let allow = BASE.replace(
            r#"{ domain = "reddit.com", action = "block" }"#,
            r#"{ domain = "reddit.com", action = "block" }, { domain = "music.youtube.com", action = "allow" }"#,
        );
        assert_eq!(
            loosenings(&parse(BASE), &parse(&allow)),
            ["profile deep: music.youtube.com allowed"]
        );
        // Dropping an exception, or allowing a site nothing slowed, is not looser.
        assert!(loosenings(&parse(&allow), &parse(BASE)).is_empty());
        let unrelated = BASE.replace(
            r#"{ domain = "youtube.com" }"#,
            r#"{ domain = "youtube.com" }, { domain = "docs.rs", action = "allow" }"#,
        );
        assert!(loosenings(&parse(BASE), &parse(&unrelated)).is_empty());

        let only = BASE.replace("[profiles.deep]", "[profiles.deep]\nmode = \"allow_only\"");
        assert!(loosenings(&parse(BASE), &parse(&only)).is_empty());
        assert_eq!(
            loosenings(&parse(&only), &parse(BASE)),
            ["profile deep: allow-only mode off"]
        );
        let more = only.replace(
            r#"{ domain = "youtube.com" }"#,
            r#"{ domain = "youtube.com" }, { domain = "docs.rs", action = "allow" }"#,
        );
        assert_eq!(
            loosenings(&parse(&only), &parse(&more)),
            ["profile deep: docs.rs allowed"]
        );
        // In allow-only mode an explicit throttle rule is the default anyway.
        let fewer = only.replace(r#"{ domain = "youtube.com" }, "#, "");
        assert!(loosenings(&parse(&only), &parse(&fewer)).is_empty());

        let gone = loosenings(&parse(BASE), &parse("[profiles.deep]\nrules = []\n"));
        assert!(gone.contains(&"routine morning removed".to_string()));
        assert!(gone.contains(&"profile deep: youtube.com removed".to_string()));
    }
}
