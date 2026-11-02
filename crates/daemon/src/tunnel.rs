//! Tunnel and proxy heuristics. Kernel VPNs (WireGuard, OpenVPN, Tailscale)
//! are no way around the throttle: nft sees their packets before they are
//! encrypted. A userspace proxy is: `ssh -D`, Tor or a v2ray-style client
//! encrypts inside a process, so DNS, the address sets and SNI never see the
//! sites behind it. They cannot be told apart from honest traffic on the
//! wire, but they all listen on a local socket for the browser. So during a
//! session the daemon looks for known proxy programs holding a listening TCP
//! socket, and for anything listening on a SOCKS port, and logs a `tunnel`
//! event (a penalty in the world). Nothing is blocked or killed.
//!
//! Parsing and classification are pure; [`scan`] reads `/proc`.

use std::collections::{HashMap, HashSet};
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr};
use std::path::Path;
use std::time::{Duration, Instant};

/// Proxy and tunnel clients, by process name (`comm`, at most 15 bytes) or
/// the file name of `argv[0]` / `argv[1]` (for scripts like sshuttle).
const PROXY_TOOLS: &[&str] = &[
    "tor",
    "ss-local",
    "sslocal",
    "ss-redir",
    "v2ray",
    "xray",
    "sing-box",
    "clash",
    "clash-meta",
    "mihomo",
    "hysteria",
    "trojan",
    "trojan-go",
    "gost",
    "chisel",
    "naive",
    "brook",
    "microsocks",
    "sshuttle",
    "wstunnel",
    "psiphon",
    "lantern",
];

/// Ports SOCKS proxies use by default (generic, Tor, Tor Browser).
const SOCKS_PORTS: &[u16] = &[1080, 9050, 9150];

/// A tunnel still running is reported again this often.
pub const REPORT_EVERY: Duration = Duration::from_secs(10 * 60);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Finding {
    pub pid: u32,
    /// What it is: `ssh -D`, `tor`, or `SOCKS port`.
    pub tool: String,
    pub listen: SocketAddr,
}

impl std::fmt::Display for Finding {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{} (pid {}) listening on {}",
            self.tool, self.pid, self.listen
        )
    }
}

/// Listening sockets in `/proc/net/tcp` or `tcp6`: `(inode, address)`.
pub fn parse_listeners(text: &str) -> Vec<(u64, SocketAddr)> {
    text.lines()
        .skip(1)
        .filter_map(|line| {
            let f: Vec<&str> = line.split_whitespace().collect();
            if f.len() < 10 || f[3] != "0A" {
                return None;
            }
            let (ip, port) = f[1].split_once(':')?;
            let port = u16::from_str_radix(port, 16).ok()?;
            let inode = f[9].parse().ok()?;
            Some((inode, SocketAddr::new(parse_hex_ip(ip)?, port)))
        })
        .collect()
}

/// The kernel prints addresses as 32-bit words in host byte order.
fn parse_hex_ip(hex: &str) -> Option<IpAddr> {
    let words = |n: usize| -> Option<Vec<[u8; 4]>> {
        (0..n)
            .map(|i| {
                let w = u32::from_str_radix(hex.get(i * 8..i * 8 + 8)?, 16).ok()?;
                Some(w.to_ne_bytes())
            })
            .collect()
    };
    match hex.len() {
        8 => Some(IpAddr::V4(Ipv4Addr::from(words(1)?[0]))),
        32 => {
            let bytes: Vec<u8> = words(4)?.concat();
            let v6 = Ipv6Addr::from(<[u8; 16]>::try_from(bytes).ok()?);
            Some(match v6.to_ipv4_mapped() {
                Some(v4) => IpAddr::V4(v4),
                None => IpAddr::V6(v6),
            })
        }
        _ => None,
    }
}

fn base(arg: &str) -> &str {
    arg.rsplit('/').next().unwrap_or(arg)
}

/// True if an ssh command line asks for dynamic (SOCKS) forwarding. Plain
/// `-L` / `-R` forwards are everyday work (a database port) and do not count.
pub fn ssh_dynamic(argv: &[String]) -> bool {
    // Options of ssh that take an argument; D among them.
    const WITH_ARG: &[u8] = b"BbcDEeFIiJLlmOopQRSWw";
    let mut args = argv.iter().skip(1);
    while let Some(arg) = args.next() {
        // The first non-option is the host; the remote command follows.
        let Some(flags) = arg.strip_prefix('-').filter(|f| !f.is_empty() && *f != "-") else {
            return false;
        };
        for (i, c) in flags.bytes().enumerate() {
            if c == b'D' {
                return true;
            }
            if WITH_ARG.contains(&c) {
                let value = match &flags[i + 1..] {
                    "" => args.next().map_or("", String::as_str),
                    rest => rest,
                };
                if c == b'o' && value.to_ascii_lowercase().starts_with("dynamicforward") {
                    return true;
                }
                break;
            }
        }
    }
    false
}

/// What a process holding a listening TCP socket on `listen` is, if it looks
/// like a proxy for getting around the throttle.
pub fn classify(comm: &str, argv: &[String], listen: SocketAddr) -> Option<String> {
    let names = [
        Some(comm),
        argv.first().map(|a| base(a)),
        argv.get(1).map(|a| base(a)),
    ];
    // argv[0] is the interpreter when ssh is a wrapper script.
    let at = argv.iter().take(2).position(|a| base(a) == "ssh");
    if at.is_some() || comm == "ssh" {
        return ssh_dynamic(&argv[at.unwrap_or(0)..]).then(|| "ssh -D".to_string());
    }
    if let Some(tool) = PROXY_TOOLS
        .iter()
        .find(|t| names.iter().flatten().any(|n| n == *t))
    {
        return Some((*tool).to_string());
    }
    SOCKS_PORTS
        .contains(&listen.port())
        .then(|| format!("{comm} on a SOCKS port"))
}

/// Every process that [`classify`] flags. Unreadable processes are skipped.
pub fn scan() -> Vec<Finding> {
    scan_root(Path::new("/proc"))
}

fn scan_root(proc: &Path) -> Vec<Finding> {
    let listeners: HashMap<u64, SocketAddr> = ["net/tcp", "net/tcp6"]
        .iter()
        .filter_map(|f| std::fs::read_to_string(proc.join(f)).ok())
        .flat_map(|text| parse_listeners(&text))
        .collect();
    if listeners.is_empty() {
        return Vec::new();
    }
    let Ok(entries) = std::fs::read_dir(proc) else {
        return Vec::new();
    };
    let mut found = Vec::new();
    let mut seen = HashSet::new();
    for entry in entries.flatten() {
        let Some(pid) = entry
            .file_name()
            .to_str()
            .and_then(|s| s.parse::<u32>().ok())
        else {
            continue;
        };
        let dir = entry.path();
        let Ok(fds) = std::fs::read_dir(dir.join("fd")) else {
            continue;
        };
        let socks: Vec<SocketAddr> = fds
            .flatten()
            .filter_map(|fd| {
                let link = std::fs::read_link(fd.path()).ok()?;
                let inode = link.to_str()?.strip_prefix("socket:[")?.strip_suffix(']')?;
                listeners.get(&inode.parse().ok()?).copied()
            })
            .collect();
        let Some(&listen) = socks.first() else {
            continue;
        };
        let comm = std::fs::read_to_string(dir.join("comm")).unwrap_or_default();
        let argv: Vec<String> = std::fs::read(dir.join("cmdline"))
            .unwrap_or_default()
            .split(|b| *b == 0)
            .filter(|a| !a.is_empty())
            .map(|a| String::from_utf8_lossy(a).into_owned())
            .collect();
        // Prefer the socket that explains the verdict (a SOCKS port).
        let listen = socks
            .iter()
            .copied()
            .find(|a| SOCKS_PORTS.contains(&a.port()))
            .unwrap_or(listen);
        if let Some(tool) = classify(comm.trim(), &argv, listen)
            && seen.insert(pid)
        {
            found.push(Finding { pid, tool, listen });
        }
    }
    found.sort_by_key(|f| f.pid);
    found
}

/// Which findings to log: new ones at once, the same process again every
/// [`REPORT_EVERY`] while it keeps running.
#[derive(Default)]
pub struct Reporter {
    last: HashMap<(u32, String), Instant>,
}

impl Reporter {
    pub fn due(&mut self, now: Instant, findings: Vec<Finding>) -> Vec<Finding> {
        let alive: HashSet<(u32, String)> =
            findings.iter().map(|f| (f.pid, f.tool.clone())).collect();
        self.last.retain(|k, _| alive.contains(k));
        findings
            .into_iter()
            .filter(|f| {
                let key = (f.pid, f.tool.clone());
                match self.last.get(&key) {
                    Some(t) if now.duration_since(*t) < REPORT_EVERY => false,
                    _ => {
                        self.last.insert(key, now);
                        true
                    }
                }
            })
            .collect()
    }

    pub fn clear(&mut self) {
        self.last.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn argv(s: &str) -> Vec<String> {
        s.split_whitespace().map(String::from).collect()
    }

    fn addr(s: &str) -> SocketAddr {
        s.parse().unwrap()
    }

    #[test]
    fn parses_proc_net_tcp() {
        let v4 = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 0100007F:0438 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 41234 1 0000000000000000 100 0 0 10 0
   1: 0100007F:A1B2 0200007F:0438 01 00000000:00000000 00:00000000 00000000  1000        0 41235 1 0000000000000000 20 4 30 10 -1";
        assert_eq!(parse_listeners(v4), [(41234, addr("127.0.0.1:1080"))]);
        let v6 = "  sl  local_address                         remote_address                        st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 00000000000000000000000001000000:2382 00000000000000000000000000000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 777 1 0000000000000000 100 0 0 10 0
   1: 0000000000000000FFFF00000100007F:1F90 00000000000000000000000000000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 778 1 0000000000000000 100 0 0 10 0";
        assert_eq!(
            parse_listeners(v6),
            [(777, addr("[::1]:9090")), (778, addr("127.0.0.1:8080"))]
        );
        assert!(parse_listeners("header only").is_empty());
    }

    #[test]
    fn ssh_forwards() {
        for yes in [
            "ssh -D 1080 host",
            "ssh -fND1080 host",
            "/usr/bin/ssh -N -D 127.0.0.1:9999 host",
            "ssh -o DynamicForward=1080 host",
            "ssh -oDynamicForward 1080 host",
            "ssh -p 22 -D 1080 host",
        ] {
            assert!(ssh_dynamic(&argv(yes)), "{yes}");
        }
        for no in [
            "ssh host",
            "ssh -L 5432:db:5432 host",
            "ssh -L D:1:x:2 host",
            "ssh -i ~/.ssh/D host",
            "ssh -l D host",
            "ssh -o ServerAliveInterval=30 host",
            "ssh host echo -D",
        ] {
            assert!(!ssh_dynamic(&argv(no)), "{no}");
        }
    }

    #[test]
    fn classifies_processes() {
        let local = addr("127.0.0.1:1080");
        let other = addr("127.0.0.1:5432");
        assert_eq!(
            classify("ssh", &argv("ssh -D 1080 h"), local).as_deref(),
            Some("ssh -D")
        );
        assert_eq!(
            classify("ssh", &argv("/usr/bin/python3 ./ssh -N -D 1080"), local).as_deref(),
            Some("ssh -D")
        );
        // A plain -L forward, even on a SOCKS port, is still ssh's business.
        assert_eq!(classify("ssh", &argv("ssh -L 5432:db:5432 h"), other), None);
        assert_eq!(
            classify("tor", &argv("/usr/bin/tor"), addr("127.0.0.1:9050")).as_deref(),
            Some("tor")
        );
        assert_eq!(
            classify(
                "python3",
                &argv("/usr/bin/python3 /usr/bin/sshuttle -r h 0/0"),
                other
            )
            .as_deref(),
            Some("sshuttle")
        );
        assert_eq!(
            classify("sing-box", &argv("sing-box run"), other).as_deref(),
            Some("sing-box")
        );
        assert_eq!(
            classify("myproxy", &argv("./myproxy"), local).as_deref(),
            Some("myproxy on a SOCKS port")
        );
        assert_eq!(classify("postgres", &argv("postgres"), other), None);
        assert_eq!(
            classify(
                "python3",
                &argv("python3 -m http.server"),
                addr("0.0.0.0:8000")
            ),
            None
        );
    }

    #[test]
    fn reports_new_then_every_ten_minutes() {
        let f = |pid| Finding {
            pid,
            tool: "tor".into(),
            listen: addr("127.0.0.1:9050"),
        };
        let mut r = Reporter::default();
        let t0 = Instant::now();
        assert_eq!(r.due(t0, vec![f(1)]), [f(1)]);
        assert!(r.due(t0 + Duration::from_secs(15), vec![f(1)]).is_empty());
        assert_eq!(
            r.due(t0 + Duration::from_secs(30), vec![f(1), f(2)]),
            [f(2)]
        );
        assert_eq!(r.due(t0 + REPORT_EVERY, vec![f(1), f(2)]), [f(1)]);
        // Gone and back (a restart) counts as new.
        assert!(r.due(t0 + REPORT_EVERY, vec![]).is_empty());
        assert_eq!(r.due(t0 + REPORT_EVERY, vec![f(2)]), [f(2)]);
    }

    #[test]
    fn scans_a_proc_tree() {
        let root = std::env::temp_dir().join(format!("deepwork-proc-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        let net = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 0100007F:0438 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 100 1 0 100 0 0 10 0
   1: 0100007F:1538 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 200 1 0 100 0 0 10 0
";
        std::fs::create_dir_all(root.join("net")).unwrap();
        std::fs::write(root.join("net/tcp"), net).unwrap();
        // pid 10: ssh -D on 1080; pid 20: postgres on 5432; pid 30: ssh, no listener.
        for (pid, comm, cmd, inode) in [
            (10, "ssh", "ssh\0-ND\x001080\0host\0", Some(100)),
            (20, "postgres", "postgres\0", Some(200)),
            (30, "ssh", "ssh\0-D\x001080\0host\0", None),
        ] {
            let dir = root.join(pid.to_string());
            std::fs::create_dir_all(dir.join("fd")).unwrap();
            std::fs::write(dir.join("comm"), format!("{comm}\n")).unwrap();
            std::fs::write(dir.join("cmdline"), cmd).unwrap();
            std::os::unix::fs::symlink("/dev/null", dir.join("fd/0")).unwrap();
            if let Some(inode) = inode {
                std::os::unix::fs::symlink(format!("socket:[{inode}]"), dir.join("fd/3")).unwrap();
            }
        }
        let found = scan_root(&root);
        std::fs::remove_dir_all(&root).unwrap();
        assert_eq!(
            found,
            [Finding {
                pid: 10,
                tool: "ssh -D".into(),
                listen: addr("127.0.0.1:1080")
            }]
        );
        assert_eq!(
            found[0].to_string(),
            "ssh -D (pid 10) listening on 127.0.0.1:1080"
        );
    }
}
