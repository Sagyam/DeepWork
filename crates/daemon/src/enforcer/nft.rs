//! Rendering of the `inet deepwork` nftables table. Pure functions only.

use std::fmt::Write;
use std::net::IpAddr;

use crate::config::Action;

pub const TABLE: &str = "inet deepwork";

/// Low 16 bits of the packet / conntrack mark for throttled traffic. The high
/// bits are preserved because Tailscale and others use them.
pub const THROTTLE_MARK: u32 = 0x4457;
/// Socket mark on the daemon's own upstream DNS traffic, exempt from redirects.
pub const EXEMPT_MARK: u32 = 0x4458;
pub const MARK_MASK: u32 = 0xffff;

/// SNI judgements (`sni.rs`). The daemon hands a queued packet back with one
/// of these as its mark, and the ruleset stores it in the conntrack mark so
/// the connection is not queued again. `SNI_KEEP` becomes `SNI_SLOW` on a
/// connection the address sets already throttle, `SNI_PASS` otherwise.
pub const SNI_PASS: u32 = 0x4459;
pub const SNI_BLOCK: u32 = 0x445a;
/// Throttled after inspection. tc treats it like [`THROTTLE_MARK`].
pub const SNI_SLOW: u32 = 0x445b;
pub const SNI_KEEP: u32 = 0x445c;
/// NFQUEUE number the inspector reads.
pub const SNI_QUEUE: u16 = 0x4457;

/// Well-known DNS-over-HTTPS resolvers. Port 443 to these is rejected during a
/// session so browsers cannot resolve around us.
#[rustfmt::skip]
const DOH_V4: &[&str] = &[
    // Cloudflare, including the endpoints Chrome and Firefox use by default
    "1.1.1.1", "1.0.0.1", "1.1.1.2", "1.0.0.2", "1.1.1.3", "1.0.0.3",
    "162.159.61.3", "172.64.41.3", "162.159.61.4", "172.64.41.4",
    // Google
    "8.8.8.8", "8.8.4.4",
    // Quad9
    "9.9.9.9", "9.9.9.10", "9.9.9.11", "149.112.112.112", "149.112.112.10", "149.112.112.11",
    // OpenDNS
    "208.67.222.222", "208.67.220.220", "146.112.41.2",
    // AdGuard
    "94.140.14.14", "94.140.15.15", "94.140.14.140", "94.140.14.141",
    // NextDNS
    "45.90.28.0/24", "45.90.30.0/24",
    // CleanBrowsing
    "185.228.168.9", "185.228.169.9",
];
#[rustfmt::skip]
const DOH_V6: &[&str] = &[
    // Cloudflare
    "2606:4700:4700::1111", "2606:4700:4700::1001",
    "2803:f800:53::3", "2a06:98c1:52::3", "2803:f800:53::4", "2a06:98c1:52::4",
    // Google
    "2001:4860:4860::8888", "2001:4860:4860::8844",
    // Quad9
    "2620:fe::fe", "2620:fe::9",
    // OpenDNS
    "2620:119:35::35", "2620:119:53::53", "2620:119:fc::2",
    // AdGuard
    "2a10:50c0::ad1:ff", "2a10:50c0::ad2:ff",
];

pub struct RulesetParams {
    pub dns_port: u16,
    pub block_quic: bool,
    pub container_dns: Option<std::net::SocketAddrV4>,
    pub inspect_sni: bool,
}

/// Bridges that containers and VMs sit behind.
const GUEST_IFACES: &str = r#"{ "docker*", "br-*", "virbr*" }"#;

/// The whole table as one `nft -f` transaction. Replaces any previous copy.
pub fn render_ruleset(p: &RulesetParams) -> String {
    let throttle = format!("0x{THROTTLE_MARK:x}");
    let exempt = format!("0x{EXEMPT_MARK:x}");
    let keep = format!("0x{:x}", !MARK_MASK);
    let mask = format!("0x{MARK_MASK:x}");
    let quic = if p.block_quic {
        "\t\tudp dport 443 reject\n"
    } else {
        ""
    };
    // Queued packets nobody reads (daemon down) pass unjudged (`bypass`), so
    // the address sets still apply.
    let sni = if p.inspect_sni {
        let queue = format!(
            "\t\ttcp dport 443 ct state established ct mark and {mask} {{ 0x0, {throttle} }} queue flags bypass to {SNI_QUEUE}\n"
        );
        format!(
            "
\tchain sni_output {{
\t\ttype filter hook output priority filter - 1; policy accept;
{queue}\t}}

\tchain sni_forward {{
\t\ttype filter hook forward priority filter - 1; policy accept;
{queue}\t}}
"
        )
    } else {
        String::new()
    };
    let (pass, block, slow, keep_v) = (
        format!("0x{SNI_PASS:x}"),
        format!("0x{SNI_BLOCK:x}"),
        format!("0x{SNI_SLOW:x}"),
        format!("0x{SNI_KEEP:x}"),
    );
    let guest_dns = match p.container_dns {
        Some(to) => format!(
            "\t\tiifname {GUEST_IFACES} meta nfproto ipv4 meta l4proto {{ tcp, udp }} th dport 53 dnat ip to {to}\n"
        ),
        None => String::new(),
    };
    format!(
        "destroy table {TABLE}
table {TABLE} {{
\tset slow_v4 {{ type ipv4_addr; flags timeout; }}
\tset slow_v6 {{ type ipv6_addr; flags timeout; }}
\tset block_v4 {{ type ipv4_addr; flags timeout; }}
\tset block_v6 {{ type ipv6_addr; flags timeout; }}
\tset doh_v4 {{ type ipv4_addr; flags interval; elements = {{ {doh_v4} }}; }}
\tset doh_v6 {{ type ipv6_addr; flags interval; elements = {{ {doh_v6} }}; }}

\tchain dns_redirect {{
\t\ttype nat hook output priority -100; policy accept;
\t\tmeta mark and {mask} == {exempt} return
\t\tip daddr 127.0.0.53 return
\t\tmeta l4proto {{ tcp, udp }} th dport 53 redirect to :{port}
\t}}

\tchain guest_dns {{
\t\ttype nat hook prerouting priority -100; policy accept;
\t\tfib daddr type local return
{guest_dns}\t}}
{sni}
\tchain output {{
\t\ttype filter hook output priority filter; policy accept;
\t\tmeta mark and {mask} == {exempt} accept
\t\tjump enforce
\t}}

\tchain forward {{
\t\ttype filter hook forward priority filter; policy accept;
\t\tmeta l4proto {{ tcp, udp }} th dport 53 reject
\t\tjump enforce
\t}}

\tchain enforce {{
\t\tip daddr @block_v4 meta l4proto tcp reject with tcp reset
\t\tip6 daddr @block_v6 meta l4proto tcp reject with tcp reset
\t\tip daddr @block_v4 drop
\t\tip6 daddr @block_v6 drop
\t\ttcp dport 853 reject with tcp reset
\t\tudp dport 853 drop
\t\tip daddr @doh_v4 tcp dport 443 reject with tcp reset
\t\tip6 daddr @doh_v6 tcp dport 443 reject with tcp reset
{quic}\t\tmeta mark and {mask} == {keep_v} ct mark and {mask} == {throttle} meta mark set meta mark and {keep} or {slow}
\t\tmeta mark and {mask} == {keep_v} ip daddr @slow_v4 meta mark set meta mark and {keep} or {slow}
\t\tmeta mark and {mask} == {keep_v} ip6 daddr @slow_v6 meta mark set meta mark and {keep} or {slow}
\t\tmeta mark and {mask} == {keep_v} meta mark set meta mark and {keep} or {pass}
\t\tmeta mark and {mask} == {pass} ct mark set ct mark and {keep} or {pass}
\t\tmeta mark and {mask} == {block} ct mark set ct mark and {keep} or {block}
\t\tmeta mark and {mask} == {slow} ct mark set ct mark and {keep} or {slow}
\t\tct direction original ct mark and {mask} == {block} reject with tcp reset
\t\tct mark and {mask} == {pass} meta mark set meta mark and {keep} return
\t\tip daddr @slow_v4 ct mark and {mask} == 0x0 ct mark set ct mark and {keep} or {throttle}
\t\tip6 daddr @slow_v6 ct mark and {mask} == 0x0 ct mark set ct mark and {keep} or {throttle}
\t\tct mark and {mask} {{ {throttle}, {slow} }} meta mark set meta mark and {keep} or {throttle}
\t}}
}}
",
        doh_v4 = DOH_V4.join(", "),
        doh_v6 = DOH_V6.join(", "),
        port = p.dns_port,
    )
}

/// Sets filled from DNS answers, with the action they enforce.
pub const DYNAMIC_SETS: [(&str, Action); 4] = [
    ("slow_v4", Action::Throttle),
    ("slow_v6", Action::Throttle),
    ("block_v4", Action::Block),
    ("block_v6", Action::Block),
];

/// Static sets whose contents are part of the tamper fingerprint.
pub const STATIC_SETS: [&str; 2] = ["doh_v4", "doh_v6"];

/// `nft -f` script adding resolved addresses to the matching sets.
pub fn render_add_elements(action: Action, addrs: &[IpAddr], timeout_secs: u32) -> Option<String> {
    let timed: Vec<(IpAddr, u32)> = addrs.iter().map(|a| (*a, timeout_secs)).collect();
    render_add_timed(action, &timed)
}

/// Like [`render_add_elements`], with a timeout per address.
pub fn render_add_timed(action: Action, addrs: &[(IpAddr, u32)]) -> Option<String> {
    let prefix = match action {
        Action::Throttle => "slow",
        Action::Block => "block",
    };
    let mut out = String::new();
    for (family, is_v4) in [("v4", true), ("v6", false)] {
        let elems: Vec<String> = addrs
            .iter()
            .filter(|(a, _)| a.is_ipv4() == is_v4)
            .map(|(a, t)| format!("{a} timeout {}s", (*t).max(1)))
            .collect();
        if !elems.is_empty() {
            let _ = writeln!(
                out,
                "add element {TABLE} {prefix}_{family} {{ {} }}",
                elems.join(", ")
            );
        }
    }
    (!out.is_empty()).then_some(out)
}

/// Addresses and seconds left from `nft -j list set`.
pub fn parse_set_elements(json: &str) -> Vec<(IpAddr, u32)> {
    let Ok(doc) = serde_json::from_str::<serde_json::Value>(json) else {
        return Vec::new();
    };
    let sets = doc["nftables"].as_array().into_iter().flatten();
    sets.filter_map(|item| item["set"]["elem"].as_array())
        .flatten()
        .filter_map(|e| {
            let elem = &e["elem"];
            let ip = elem["val"].as_str()?.parse().ok()?;
            let left = elem["expires"].as_u64().or(elem["timeout"].as_u64())?;
            Some((ip, u32::try_from(left).unwrap_or(u32::MAX)))
        })
        .collect()
}

/// True for `nft monitor` lines that change our table's structure. Element
/// changes are ignored: the daemon adds them all the time and they expire.
pub fn monitor_line_is_ours(line: &str) -> bool {
    line.split_whitespace()
        .collect::<Vec<_>>()
        .windows(2)
        .any(|w| w == ["inet", "deepwork"])
        && !line.contains(" element ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ruleset_contains_port_and_quic() {
        let r = render_ruleset(&RulesetParams {
            dns_port: 5454,
            block_quic: true,
            container_dns: Some("172.17.0.1:53".parse().unwrap()),
            inspect_sni: true,
        });
        assert!(r.starts_with("destroy table inet deepwork\n"));
        assert!(r.contains("redirect to :5454"));
        assert!(r.contains("udp dport 443 reject"));
        assert!(r.contains("ct mark set ct mark and 0xffff0000 or 0x4457"));
        assert!(r.contains("queue flags bypass to 17495"));

        assert!(r.contains("th dport 53 dnat ip to 172.17.0.1:53"));

        let r = render_ruleset(&RulesetParams {
            dns_port: 5454,
            block_quic: false,
            container_dns: None,
            inspect_sni: false,
        });
        assert!(!r.contains("udp dport 443"));
        assert!(!r.contains("queue"));
        assert!(!r.contains("dnat"));
        assert!(r.contains("th dport 53 reject"));
    }

    #[test]
    fn add_elements_split_by_family() {
        let addrs: Vec<IpAddr> = vec!["1.2.3.4".parse().unwrap(), "2001:db8::1".parse().unwrap()];
        let s = render_add_elements(Action::Block, &addrs, 60).unwrap();
        assert_eq!(
            s,
            "add element inet deepwork block_v4 { 1.2.3.4 timeout 60s }\n\
             add element inet deepwork block_v6 { 2001:db8::1 timeout 60s }\n"
        );
        assert!(render_add_elements(Action::Throttle, &[], 60).is_none());
    }

    #[test]
    fn parses_set_listing() {
        let json = r#"{"nftables": [{"metainfo": {"version": "1.1.7"}}, {"set": {"family": "inet",
            "name": "slow_v4", "table": "deepwork", "type": "ipv4_addr", "flags": ["timeout"],
            "elem": [{"elem": {"val": "1.2.3.4", "timeout": 3600, "expires": 3599}},
                     {"elem": {"val": "5.6.7.8", "timeout": 60, "expires": 59}}]}}]}"#;
        assert_eq!(
            parse_set_elements(json),
            [
                ("1.2.3.4".parse().unwrap(), 3599),
                ("5.6.7.8".parse().unwrap(), 59)
            ]
        );
        assert!(parse_set_elements("{}").is_empty());
        assert!(parse_set_elements("garbage").is_empty());
    }

    #[test]
    fn monitor_filter() {
        assert!(monitor_line_is_ours(
            "delete rule inet deepwork enforce handle 22"
        ));
        assert!(monitor_line_is_ours(
            "insert rule inet deepwork enforce accept"
        ));
        assert!(monitor_line_is_ours("delete table inet deepwork"));
        assert!(!monitor_line_is_ours(
            "add element inet deepwork slow_v4 { 9.9.9.9 timeout 1m expires 1m }"
        ));
        assert!(!monitor_line_is_ours("add rule inet filter input accept"));
        assert!(!monitor_line_is_ours("add table inet deepworkx"));
    }
}
