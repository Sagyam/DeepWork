//! Rendering of the tc setup that slows down throttle-marked traffic. Pure
//! functions only.
//!
//! Egress: a 2-band `prio` root. Everything goes to band 1 (`fq_codel`), and an
//! `fw` filter moves throttle-marked packets to band 2 (`netem`).
//!
//! Ingress: `clsact` on the device copies the conntrack mark onto the packet
//! (`connmark`) and redirects it to an IFB device that has the same setup.

use std::fmt::Write;

use super::nft::{MARK_MASK, THROTTLE_MARK};
use crate::config::Throttle;

const IFB_PREFIX: &str = "dwifb";

/// Virtual and internal interfaces we never shape. Traffic forwarded from
/// containers and VMs is shaped when it leaves through a real interface.
const SKIP_PREFIXES: &[&str] = &[
    "lo", IFB_PREFIX, "ifb", "docker", "br-", "veth", "virbr", "vnet",
];

pub fn should_shape(dev: &str) -> bool {
    !SKIP_PREFIXES.iter().any(|p| dev.starts_with(p))
}

pub fn ifb_name(ifindex: u32) -> String {
    format!("{IFB_PREFIX}{ifindex}")
}

fn netem(t: &Throttle) -> String {
    let mut s = format!("netem delay {}ms", t.rtt_ms / 2);
    if t.jitter_ms > 0 {
        let _ = write!(s, " {}ms", t.jitter_ms / 2);
    }
    if t.loss_pct > 0.0 {
        let _ = write!(s, " loss {}%", t.loss_pct);
    }
    // Queue about one second of traffic at the capped rate. Longer queues add
    // so much delay that the throttle feels like a block.
    let limit = (u64::from(t.rate_kbit) * 1000 / 8 / 1500).max(16);
    let _ = write!(s, " rate {}kbit limit {limit}", t.rate_kbit);
    s
}

fn shape_egress(out: &mut String, dev: &str, t: &Throttle) {
    let _ = writeln!(
        out,
        "qdisc replace dev {dev} root handle d000: prio bands 2 priomap 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
    );
    let _ = writeln!(
        out,
        "qdisc replace dev {dev} parent d000:1 handle d001: fq_codel"
    );
    let _ = writeln!(
        out,
        "qdisc replace dev {dev} parent d000:2 handle d002: {}",
        netem(t)
    );
    let _ = writeln!(
        out,
        "filter replace dev {dev} parent d000: protocol all prio 1 handle 0x{THROTTLE_MARK:x}/0x{MARK_MASK:x} fw flowid d000:2"
    );
}

/// `tc -batch` script for one device and its IFB. The IFB must already exist.
pub fn render_shape(dev: &str, ifb: &str, t: &Throttle) -> String {
    let mut out = String::new();
    shape_egress(&mut out, dev, t);
    shape_egress(&mut out, ifb, t);
    let _ = writeln!(out, "qdisc replace dev {dev} clsact");
    let _ = writeln!(
        out,
        "filter replace dev {dev} ingress protocol all prio 1 handle 1 matchall action connmark action mirred egress redirect dev {ifb}"
    );
    out
}

/// `tc -batch` script changing the throttle of a shaped device and its IFB
/// in place, for escalation. Connections and queues are kept.
pub fn render_retune(dev: &str, ifb: &str, t: &Throttle) -> String {
    let mut out = String::new();
    for d in [dev, ifb] {
        let _ = writeln!(
            out,
            "qdisc change dev {d} parent d000:2 handle d002: {}",
            netem(t)
        );
    }
    out
}

/// Bytes sent through the throttle (`netem`) band, from `tc -s -j qdisc show`.
pub fn netem_bytes(json: &str) -> u64 {
    let Ok(serde_json::Value::Array(qdiscs)) = serde_json::from_str(json) else {
        return 0;
    };
    qdiscs
        .iter()
        .filter(|q| q["handle"] == "d002:")
        .filter_map(|q| q["bytes"].as_u64())
        .sum()
}

/// `tc -force -batch` script undoing [`render_shape`]. Errors are expected and
/// ignored for parts that are already gone.
pub fn render_unshape(dev: &str) -> String {
    format!("qdisc del dev {dev} root\nqdisc del dev {dev} clsact\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn skips_virtual_interfaces() {
        for dev in ["wlp7s0", "enp5s0", "tailscale0", "wg0"] {
            assert!(should_shape(dev), "{dev}");
        }
        for dev in [
            "lo", "dwifb3", "docker0", "br-1a2b", "veth12", "virbr0", "vnet4",
        ] {
            assert!(!should_shape(dev), "{dev}");
        }
    }

    #[test]
    fn netem_params() {
        let t = Throttle {
            rtt_ms: 600,
            jitter_ms: 100,
            rate_kbit: 256,
            loss_pct: 1.0,
        };
        assert_eq!(
            netem(&t),
            "netem delay 300ms 50ms loss 1% rate 256kbit limit 21"
        );
        let t = Throttle {
            rtt_ms: 0,
            jitter_ms: 0,
            rate_kbit: 8,
            loss_pct: 0.0,
        };
        assert_eq!(netem(&t), "netem delay 0ms rate 8kbit limit 16");
    }

    #[test]
    fn retune_and_counters() {
        let t = Throttle {
            rtt_ms: 600,
            jitter_ms: 50,
            rate_kbit: 128,
            loss_pct: 0.0,
        };
        assert_eq!(
            render_retune("wlp7s0", "dwifb3", &t),
            "qdisc change dev wlp7s0 parent d000:2 handle d002: netem delay 300ms 25ms rate 128kbit limit 16\n\
             qdisc change dev dwifb3 parent d000:2 handle d002: netem delay 300ms 25ms rate 128kbit limit 16\n"
        );
        let json = r#"[{"kind":"prio","handle":"d000:","bytes":900},
            {"kind":"fq_codel","handle":"d001:","bytes":500},
            {"kind":"netem","handle":"d002:","parent":"d000:2","bytes":400}]"#;
        assert_eq!(netem_bytes(json), 400);
        assert_eq!(netem_bytes("nonsense"), 0);
    }

    #[test]
    fn shape_script_covers_both_directions() {
        let s = render_shape("wlp7s0", "dwifb3", &Throttle::default());
        assert!(s.contains("qdisc replace dev wlp7s0 root handle d000: prio"));
        assert!(s.contains("qdisc replace dev dwifb3 parent d000:2 handle d002: netem"));
        assert!(s.contains("handle 0x4457/0xffff fw flowid d000:2"));
        assert!(s.contains("action connmark action mirred egress redirect dev dwifb3"));
    }
}
