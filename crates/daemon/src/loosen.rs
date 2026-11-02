//! Which config changes loosen enforcement. Pure.
//!
//! Loosening changes wait [`LOOSEN_DELAY`] before they apply; tightening and
//! neutral changes (DNS plumbing, heads-up timing) apply at once. A change is
//! judged against the config in effect, field by field, and anything that is
//! not clearly stricter or equal counts as loosening.

use std::time::Duration;

use crate::config::{Action, Config, Day, NudgeConfig, Profile, Routine, Throttle, on_day};

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
    for rule in &old.rules {
        match new.rules.iter().find(|r| r.domain == rule.domain) {
            None => out.push(format!("profile {name}: {} removed", rule.domain)),
            Some(r) if rule.action == Action::Block && r.action == Action::Throttle => {
                out.push(format!(
                    "profile {name}: {} throttled, not blocked",
                    rule.domain
                ));
            }
            Some(_) => {}
        }
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
        let gone = loosenings(&parse(BASE), &parse("[profiles.deep]\nrules = []\n"));
        assert!(gone.contains(&"routine morning removed".to_string()));
        assert!(gone.contains(&"profile deep: youtube.com removed".to_string()));
    }
}
