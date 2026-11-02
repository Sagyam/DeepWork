//! SNI inspection. During a session the first data packets of every TLS
//! connection to port 443 are queued to the daemon (NFQUEUE, see
//! `nfqueue.rs`), which reads the server name from the ClientHello and judges
//! the connection by it. That catches distracting sites reached without our
//! DNS (hardcoded IPs, stale caches), and lets a site that shares a CDN
//! address with a throttled one (Google Docs and YouTube) go at full speed.
//!
//! Parsing and bookkeeping only; no I/O.

use std::collections::HashMap;
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};
use std::time::{Duration, Instant};

use crate::config::{Action, ListMode, Lists, judge};
use crate::enforcer::nft::{SNI_BLOCK, SNI_KEEP, SNI_PASS, SNI_SLOW};

/// A ClientHello larger than this, or spread over more segments, is given up
/// on. Real ones are under 2 KB (about 1.8 KB with a post-quantum key share,
/// which takes two segments).
const MAX_HELLO: usize = 16 * 1024;
const MAX_SEGMENTS: u8 = 8;
/// Payload-less packets (the handshake ACK) seen before giving up on a flow.
/// A connection that only ACKs, like a download opened before the session,
/// would otherwise be queued for good.
const MAX_EMPTY: u8 = 3;
const FLOW_TTL: Duration = Duration::from_secs(10);
const MAX_FLOWS: usize = 4096;

/// What happens to a queued packet, and to its connection.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Judgement {
    /// Let this packet through; the connection stays unjudged and its next
    /// packet is queued too (ClientHello not complete yet).
    Wait,
    /// No usable name: whatever the address sets say.
    Keep,
    /// A name no rule matches: full speed, even on a throttled address.
    Pass,
    Slow,
    Block,
}

impl Judgement {
    /// The packet mark that carries the judgement back into nft.
    pub fn mark(self) -> Option<u32> {
        match self {
            Judgement::Wait => None,
            Judgement::Keep => Some(SNI_KEEP),
            Judgement::Pass => Some(SNI_PASS),
            Judgement::Slow => Some(SNI_SLOW),
            Judgement::Block => Some(SNI_BLOCK),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct FlowKey {
    pub src: IpAddr,
    pub dst: IpAddr,
    pub sport: u16,
    pub dport: u16,
}

#[derive(Debug, PartialEq, Eq)]
pub struct TcpPacket<'a> {
    pub key: FlowKey,
    pub seq: u32,
    pub payload: &'a [u8],
}

/// The TCP segment in a raw IPv4 / IPv6 packet. `None` for anything else,
/// including fragments and IPv6 extension headers.
pub fn parse_packet(pkt: &[u8]) -> Option<TcpPacket<'_>> {
    let version = pkt.first()? >> 4;
    let (src, dst, tcp) = match version {
        4 => {
            let ihl = usize::from(pkt[0] & 0x0f) * 4;
            if ihl < 20 || pkt.len() < ihl || pkt[9] != 6 {
                return None;
            }
            let frag = u16::from_be_bytes([pkt[6], pkt[7]]);
            if frag & 0x3fff != 0 {
                return None;
            }
            // A GSO packet may be longer than its total length field says
            // it is (0 above 64 KB).
            let total = usize::from(u16::from_be_bytes([pkt[2], pkt[3]]));
            let end = if total >= ihl {
                total.min(pkt.len())
            } else {
                pkt.len()
            };
            let src = Ipv4Addr::from(<[u8; 4]>::try_from(&pkt[12..16]).ok()?);
            let dst = Ipv4Addr::from(<[u8; 4]>::try_from(&pkt[16..20]).ok()?);
            (IpAddr::V4(src), IpAddr::V4(dst), &pkt[ihl..end])
        }
        6 => {
            if pkt.len() < 40 || pkt[6] != 6 {
                return None;
            }
            let len = usize::from(u16::from_be_bytes([pkt[4], pkt[5]]));
            let end = if len > 0 {
                (40 + len).min(pkt.len())
            } else {
                pkt.len()
            };
            let src = Ipv6Addr::from(<[u8; 16]>::try_from(&pkt[8..24]).ok()?);
            let dst = Ipv6Addr::from(<[u8; 16]>::try_from(&pkt[24..40]).ok()?);
            (IpAddr::V6(src), IpAddr::V6(dst), &pkt[40..end])
        }
        _ => return None,
    };
    if tcp.len() < 20 {
        return None;
    }
    let doff = usize::from(tcp[12] >> 4) * 4;
    if doff < 20 || tcp.len() < doff {
        return None;
    }
    Some(TcpPacket {
        key: FlowKey {
            src,
            dst,
            sport: u16::from_be_bytes([tcp[0], tcp[1]]),
            dport: u16::from_be_bytes([tcp[2], tcp[3]]),
        },
        seq: u32::from_be_bytes([tcp[4], tcp[5], tcp[6], tcp[7]]),
        payload: &tcp[doff..],
    })
}

#[derive(Debug, PartialEq, Eq)]
pub enum Hello {
    /// Looks like a ClientHello so far; more bytes are needed.
    Incomplete,
    /// Not a TLS ClientHello, or a malformed one.
    Foreign,
    Parsed {
        sni: Option<String>,
        /// Encrypted ClientHello: the name above is only the outer one.
        ech: bool,
    },
}

const EXT_SERVER_NAME: u16 = 0x0000;
const EXT_ECH: u16 = 0xfe0d;

/// Reads the server name from the start of a TLS client stream. The
/// handshake may be split over several records.
pub fn parse_client_hello(stream: &[u8]) -> Hello {
    let mut hs = Vec::new();
    let mut rest = stream;
    loop {
        if hs.len() >= 4 {
            if hs[0] != 1 {
                return Hello::Foreign;
            }
            let len = 4 + (usize::from(hs[1]) << 16 | usize::from(hs[2]) << 8 | usize::from(hs[3]));
            if len > MAX_HELLO {
                return Hello::Foreign;
            }
            if hs.len() >= len {
                return parse_hello_body(&hs[4..len]).unwrap_or(Hello::Foreign);
            }
        }
        if rest.len() < 5 {
            return Hello::Incomplete;
        }
        if rest[0] != 0x16 || rest[1] != 3 {
            return Hello::Foreign;
        }
        let len = usize::from(u16::from_be_bytes([rest[3], rest[4]]));
        if len == 0 || len > 16384 + 2048 {
            return Hello::Foreign;
        }
        if rest.len() < 5 + len {
            // Enough of the record may already be here for the whole
            // handshake message; otherwise wait for the rest.
            hs.extend_from_slice(&rest[5..]);
            rest = &[];
            continue;
        }
        hs.extend_from_slice(&rest[5..5 + len]);
        rest = &rest[5 + len..];
    }
}

struct Reader<'a>(&'a [u8]);

impl<'a> Reader<'a> {
    fn take(&mut self, n: usize) -> Option<&'a [u8]> {
        if self.0.len() < n {
            return None;
        }
        let (head, tail) = self.0.split_at(n);
        self.0 = tail;
        Some(head)
    }
    fn u8(&mut self) -> Option<u8> {
        Some(self.take(1)?[0])
    }
    fn u16(&mut self) -> Option<u16> {
        let b = self.take(2)?;
        Some(u16::from_be_bytes([b[0], b[1]]))
    }
    fn vec8(&mut self) -> Option<&'a [u8]> {
        let n = self.u8()?;
        self.take(usize::from(n))
    }
    fn vec16(&mut self) -> Option<&'a [u8]> {
        let n = self.u16()?;
        self.take(usize::from(n))
    }
}

fn parse_hello_body(body: &[u8]) -> Option<Hello> {
    let mut r = Reader(body);
    r.take(2 + 32)?; // legacy_version, random
    r.vec8()?; // session id
    r.vec16()?; // cipher suites
    r.vec8()?; // compression methods
    if r.0.is_empty() {
        return Some(Hello::Parsed {
            sni: None,
            ech: false,
        });
    }
    let mut exts = Reader(r.vec16()?);
    let (mut sni, mut ech) = (None, false);
    while !exts.0.is_empty() {
        let kind = exts.u16()?;
        let data = exts.vec16()?;
        match kind {
            EXT_SERVER_NAME => sni = server_name(data),
            EXT_ECH => ech = true,
            _ => {}
        }
    }
    Some(Hello::Parsed { sni, ech })
}

fn server_name(data: &[u8]) -> Option<String> {
    let mut list = Reader(Reader(data).vec16()?);
    while !list.0.is_empty() {
        let kind = list.u8()?;
        let name = list.vec16()?;
        if kind == 0 {
            let name = std::str::from_utf8(name).ok()?;
            if name.is_empty()
                || !name
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b"-._".contains(&b))
            {
                return None;
            }
            return Some(name.trim_end_matches('.').to_ascii_lowercase());
        }
    }
    None
}

/// The judgement for a parsed ClientHello, from the rule that decides the
/// name (see [`judge`]). A name no rule covers is full speed in a block list
/// and slow in an allow-only profile. An encrypted ClientHello only shows a
/// cover name, so it never earns full speed: the address decides.
pub fn decide(sni: Option<&str>, ech: bool, lists: &Lists) -> Judgement {
    let Some(name) = sni else {
        return Judgement::Keep;
    };
    match judge(&lists.rules, name) {
        Some(Action::Block) => Judgement::Block,
        Some(Action::Throttle) => Judgement::Slow,
        _ if ech => Judgement::Keep,
        None if lists.mode == ListMode::AllowOnly => Judgement::Slow,
        Some(Action::Allow) | None => Judgement::Pass,
    }
}

struct Flow {
    first_seq: u32,
    next_seq: u32,
    buf: Vec<u8>,
    segments: u8,
    empty: u8,
    since: Instant,
}

/// Follows connections across queued packets until their ClientHello is
/// complete.
#[derive(Default)]
pub struct Inspector {
    flows: HashMap<FlowKey, Flow>,
}

impl Inspector {
    /// Judges one queued packet. `lists` is `None` outside a session. The
    /// name is returned once the ClientHello has been read.
    pub fn inspect(
        &mut self,
        now: Instant,
        pkt: &[u8],
        lists: Option<&Lists>,
    ) -> (Judgement, Option<String>) {
        let (Some(lists), Some(tcp)) = (lists, parse_packet(pkt)) else {
            return (Judgement::Keep, None);
        };
        if self.flows.len() >= MAX_FLOWS {
            self.flows
                .retain(|_, f| now.duration_since(f.since) < FLOW_TTL);
            if self.flows.len() >= MAX_FLOWS {
                self.flows.clear();
            }
        }
        let flow = self.flows.entry(tcp.key).or_insert_with(|| Flow {
            first_seq: tcp.seq,
            next_seq: tcp.seq,
            buf: Vec::new(),
            segments: 0,
            empty: 0,
            since: now,
        });
        if now.duration_since(flow.since) >= FLOW_TTL {
            self.flows.remove(&tcp.key);
            return (Judgement::Keep, None);
        }
        if tcp.payload.is_empty() {
            flow.empty += 1;
            if flow.empty > MAX_EMPTY && flow.buf.is_empty() {
                self.flows.remove(&tcp.key);
                return (Judgement::Keep, None);
            }
            return (Judgement::Wait, None);
        }
        if flow.buf.is_empty() || tcp.seq == flow.first_seq {
            // First data, or the first segment sent again.
            flow.first_seq = tcp.seq;
            flow.buf.clear();
            flow.segments = 0;
        } else if tcp.seq != flow.next_seq {
            self.flows.remove(&tcp.key);
            return (Judgement::Keep, None);
        }
        flow.buf.extend_from_slice(tcp.payload);
        flow.segments += 1;
        flow.next_seq = tcp.seq.wrapping_add(tcp.payload.len() as u32);
        match parse_client_hello(&flow.buf) {
            Hello::Incomplete if flow.buf.len() <= MAX_HELLO && flow.segments < MAX_SEGMENTS => {
                (Judgement::Wait, None)
            }
            Hello::Incomplete | Hello::Foreign => {
                self.flows.remove(&tcp.key);
                (Judgement::Keep, None)
            }
            Hello::Parsed { sni, ech } => {
                self.flows.remove(&tcp.key);
                (decide(sni.as_deref(), ech, lists), sni)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::Rule;

    /// A ClientHello record with the given extensions (type, data).
    pub fn client_hello(exts: &[(u16, Vec<u8>)]) -> Vec<u8> {
        let mut body = vec![3, 3];
        body.extend([7u8; 32]);
        body.push(32);
        body.extend([9u8; 32]);
        body.extend([0, 4, 0x13, 0x01, 0x13, 0x02]);
        body.extend([1, 0]);
        let mut ext_bytes = Vec::new();
        for (kind, data) in exts {
            ext_bytes.extend(kind.to_be_bytes());
            ext_bytes.extend((data.len() as u16).to_be_bytes());
            ext_bytes.extend(data);
        }
        body.extend((ext_bytes.len() as u16).to_be_bytes());
        body.extend(ext_bytes);
        let mut hs = vec![1, 0];
        hs.extend((body.len() as u16).to_be_bytes());
        hs.extend(body);
        let mut rec = vec![0x16, 3, 1];
        rec.extend((hs.len() as u16).to_be_bytes());
        rec.extend(hs);
        rec
    }

    pub fn sni_ext(name: &str) -> (u16, Vec<u8>) {
        let mut entry = vec![0];
        entry.extend((name.len() as u16).to_be_bytes());
        entry.extend(name.as_bytes());
        let mut data = (entry.len() as u16).to_be_bytes().to_vec();
        data.extend(entry);
        (EXT_SERVER_NAME, data)
    }

    /// An IPv4 TCP packet from 10.0.0.1:40000 to 10.0.0.2:443.
    pub fn tcp4(seq: u32, payload: &[u8]) -> Vec<u8> {
        let total = 40 + payload.len();
        let mut p = vec![0x45, 0];
        p.extend((total as u16).to_be_bytes());
        p.extend([0, 0, 0x40, 0, 64, 6, 0, 0, 10, 0, 0, 1, 10, 0, 0, 2]);
        p.extend(40000u16.to_be_bytes());
        p.extend(443u16.to_be_bytes());
        p.extend(seq.to_be_bytes());
        p.extend([0, 0, 0, 0, 0x50, 0x18, 0xff, 0xff, 0, 0, 0, 0]);
        p.extend(payload);
        p
    }

    fn rule(domain: &str, action: Action) -> Rule {
        Rule {
            domain: domain.into(),
            action,
        }
    }

    fn rules() -> Lists {
        Lists {
            mode: ListMode::BlockList,
            rules: vec![
                rule("youtube.com", Action::Throttle),
                rule("reddit.com", Action::Block),
                rule("music.youtube.com", Action::Allow),
            ],
        }
    }

    #[test]
    fn reads_server_name() {
        let hello = client_hello(&[(0x000a, vec![0, 2, 0, 29]), sni_ext("WWW.YouTube.com.")]);
        assert_eq!(
            parse_client_hello(&hello),
            Hello::Parsed {
                sni: Some("www.youtube.com".into()),
                ech: false
            }
        );
        let ech = client_hello(&[sni_ext("cover.example"), (EXT_ECH, vec![1, 2, 3])]);
        assert_eq!(
            parse_client_hello(&ech),
            Hello::Parsed {
                sni: Some("cover.example".into()),
                ech: true
            }
        );
        assert_eq!(
            parse_client_hello(&client_hello(&[])),
            Hello::Parsed {
                sni: None,
                ech: false
            }
        );
    }

    #[test]
    fn partial_and_foreign_streams() {
        let hello = client_hello(&[sni_ext("youtube.com")]);
        for cut in [0, 3, 5, 40, hello.len() - 1] {
            assert_eq!(
                parse_client_hello(&hello[..cut]),
                Hello::Incomplete,
                "{cut}"
            );
        }
        assert_eq!(parse_client_hello(b"GET / HTTP/1.1\r\n"), Hello::Foreign);
        // A ServerHello is a handshake, but not ours to read.
        let mut server = hello.clone();
        server[5] = 2;
        assert_eq!(parse_client_hello(&server), Hello::Foreign);
        // An extension that runs past the end of the message.
        let mut bad = hello.clone();
        let n = bad.len();
        bad[n - 18] = 0xff;
        assert_eq!(parse_client_hello(&bad), Hello::Foreign);
    }

    #[test]
    fn handshake_split_over_records() {
        let hello = client_hello(&[sni_ext("youtube.com")]);
        let hs = &hello[5..];
        let (a, b) = hs.split_at(30);
        let mut stream = Vec::new();
        for part in [a, b] {
            stream.extend([0x16, 3, 3]);
            stream.extend((part.len() as u16).to_be_bytes());
            stream.extend(part);
        }
        assert_eq!(
            parse_client_hello(&stream),
            Hello::Parsed {
                sni: Some("youtube.com".into()),
                ech: false
            }
        );
    }

    #[test]
    fn judgement_by_name() {
        let r = rules();
        assert_eq!(decide(Some("m.youtube.com"), false, &r), Judgement::Slow);
        assert_eq!(decide(Some("old.reddit.com"), true, &r), Judgement::Block);
        assert_eq!(decide(Some("docs.google.com"), false, &r), Judgement::Pass);
        assert_eq!(decide(Some("docs.google.com"), true, &r), Judgement::Keep);
        assert_eq!(decide(None, false, &r), Judgement::Keep);
        // An allowed exception inside a slowed site.
        assert_eq!(
            decide(Some("music.youtube.com"), false, &r),
            Judgement::Pass
        );
        assert_eq!(decide(Some("music.youtube.com"), true, &r), Judgement::Keep);

        let only = Lists {
            mode: ListMode::AllowOnly,
            rules: vec![
                rule("google.com", Action::Allow),
                rule("mail.google.com", Action::Block),
            ],
        };
        assert_eq!(
            decide(Some("docs.google.com"), false, &only),
            Judgement::Pass
        );
        assert_eq!(
            decide(Some("mail.google.com"), false, &only),
            Judgement::Block
        );
        assert_eq!(decide(Some("example.com"), false, &only), Judgement::Slow);
        assert_eq!(decide(Some("example.com"), true, &only), Judgement::Keep);
    }

    #[test]
    fn parses_ipv4_and_ipv6() {
        let p = tcp4(7, b"hi");
        let tcp = parse_packet(&p).unwrap();
        assert_eq!(tcp.key.dport, 443);
        assert_eq!(tcp.key.src, "10.0.0.1".parse::<IpAddr>().unwrap());
        assert_eq!((tcp.seq, tcp.payload), (7, &b"hi"[..]));

        let mut v6 = vec![0x60, 0, 0, 0, 0, 22, 6, 64];
        v6.extend("2001:db8::1".parse::<Ipv6Addr>().unwrap().octets());
        v6.extend("2001:db8::2".parse::<Ipv6Addr>().unwrap().octets());
        v6.extend(&p[20..]);
        let tcp = parse_packet(&v6).unwrap();
        assert_eq!(tcp.key.dst, "2001:db8::2".parse::<IpAddr>().unwrap());
        assert_eq!(tcp.payload, b"hi");

        // UDP, fragments and junk are not ours.
        let mut udp = p.clone();
        udp[9] = 17;
        assert!(parse_packet(&udp).is_none());
        let mut frag = p.clone();
        frag[6] = 0x20;
        assert!(parse_packet(&frag).is_none());
        assert!(parse_packet(&[0x45, 0, 0]).is_none());
    }

    #[test]
    fn follows_a_hello_over_segments() {
        let r = rules();
        let now = Instant::now();
        let mut ins = Inspector::default();
        let hello = client_hello(&[(0x11ec, vec![0; 1200]), sni_ext("www.youtube.com")]);
        let (a, b) = hello.split_at(1000);
        // Handshake ACK, first segment, the first segment again, the rest.
        assert_eq!(
            ins.inspect(now, &tcp4(100, &[]), Some(&r)).0,
            Judgement::Wait
        );
        assert_eq!(ins.inspect(now, &tcp4(100, a), Some(&r)).0, Judgement::Wait);
        assert_eq!(ins.inspect(now, &tcp4(100, a), Some(&r)).0, Judgement::Wait);
        assert_eq!(
            ins.inspect(now, &tcp4(1100, b), Some(&r)),
            (Judgement::Slow, Some("www.youtube.com".into()))
        );
        assert!(ins.flows.is_empty());

        // A gap in the stream gives up on the connection.
        ins.inspect(now, &tcp4(100, a), Some(&r));
        assert_eq!(
            ins.inspect(now, &tcp4(1500, b), Some(&r)).0,
            Judgement::Keep
        );
        assert!(ins.flows.is_empty());
    }

    #[test]
    fn gives_up_on_silent_and_stale_flows() {
        let r = rules();
        let now = Instant::now();
        let mut ins = Inspector::default();
        for _ in 0..MAX_EMPTY {
            assert_eq!(ins.inspect(now, &tcp4(1, &[]), Some(&r)).0, Judgement::Wait);
        }
        assert_eq!(ins.inspect(now, &tcp4(1, &[]), Some(&r)).0, Judgement::Keep);

        let hello = client_hello(&[sni_ext("docs.google.com")]);
        ins.inspect(now, &tcp4(1, &hello[..20]), Some(&r));
        let later = now + FLOW_TTL;
        assert_eq!(
            ins.inspect(later, &tcp4(21, &hello[20..]), Some(&r)).0,
            Judgement::Keep
        );

        // Mid-stream data from a connection opened before the session.
        assert_eq!(
            ins.inspect(now, &tcp4(5, b"\x17\x03\x03\x00\x10"), Some(&r))
                .0,
            Judgement::Keep
        );
        // No session.
        assert_eq!(ins.inspect(now, &tcp4(1, &hello), None).0, Judgement::Keep);
        assert_eq!(
            ins.inspect(now, &tcp4(1, &hello), Some(&r)),
            (Judgement::Pass, Some("docs.google.com".into()))
        );
    }
}
