//! A minimal NFQUEUE client over a raw netlink socket, for the SNI inspector
//! (`sni.rs`). Message building and parsing are pure and unit tested; only
//! [`Queue`] touches the socket.

use std::io;
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
use std::sync::Arc;
use std::time::{Duration, Instant};

use tracing::{debug, info, trace, warn};

use crate::config::Rule;
use crate::enforcer::nft::{MARK_MASK, SNI_QUEUE};
use crate::sni::Inspector;

const NFNL_SUBSYS_QUEUE: u16 = 3;
const NFQNL_MSG_PACKET: u16 = 0;
const NFQNL_MSG_VERDICT: u16 = 1;
const NFQNL_MSG_CONFIG: u16 = 2;

const NFQA_CFG_CMD: u16 = 1;
const NFQA_CFG_PARAMS: u16 = 2;
const NFQA_CFG_QUEUE_MAXLEN: u16 = 3;
const NFQA_CFG_MASK: u16 = 4;
const NFQA_CFG_FLAGS: u16 = 5;
const NFQNL_CFG_CMD_BIND: u8 = 1;
const NFQNL_COPY_PACKET: u8 = 2;
/// Accept instead of dropping when the queue is full.
const NFQA_CFG_F_FAIL_OPEN: u32 = 1;
/// Hand over GSO packets whole instead of segmenting them first.
const NFQA_CFG_F_GSO: u32 = 4;

const NFQA_PACKET_HDR: u16 = 1;
const NFQA_VERDICT_HDR: u16 = 2;
const NFQA_MARK: u16 = 3;
const NFQA_PAYLOAD: u16 = 10;

const NF_ACCEPT: u32 = 1;

const NLMSG_ERROR: u16 = 2;
const NLM_F_REQUEST: u16 = 1;
const NLM_F_ACK: u16 = 4;
const NLA_TYPE_MASK: u16 = 0x3fff;
const NETLINK_NO_ENOBUFS: libc::c_int = 5;

/// Packets copied up to this many bytes; a ClientHello fits many times over.
const COPY_RANGE: u32 = 0xffff;
const QUEUE_MAXLEN: u32 = 4096;
const RETRY: Duration = Duration::from_secs(60);

fn push_attr(buf: &mut Vec<u8>, kind: u16, data: &[u8]) {
    let len = 4 + data.len();
    buf.extend((len as u16).to_ne_bytes());
    buf.extend(kind.to_ne_bytes());
    buf.extend(data);
    buf.resize(buf.len().next_multiple_of(4), 0);
}

/// One netlink message: header, `nfgenmsg` for queue `queue`, attributes.
fn message(msg: u16, flags: u16, seq: u32, queue: u16, attrs: &[(u16, Vec<u8>)]) -> Vec<u8> {
    let mut buf = vec![0; 16];
    buf.extend([libc::AF_UNSPEC as u8, 0]);
    buf.extend(queue.to_be_bytes());
    for (kind, data) in attrs {
        push_attr(&mut buf, *kind, data);
    }
    let len = buf.len() as u32;
    buf[0..4].copy_from_slice(&len.to_ne_bytes());
    buf[4..6].copy_from_slice(&(NFNL_SUBSYS_QUEUE << 8 | msg).to_ne_bytes());
    buf[6..8].copy_from_slice(&flags.to_ne_bytes());
    buf[8..12].copy_from_slice(&seq.to_ne_bytes());
    buf
}

/// The config messages that bind `queue` and set it up, each asking for an
/// acknowledgement.
fn bind_messages(queue: u16) -> Vec<Vec<u8>> {
    let flags = NLM_F_REQUEST | NLM_F_ACK;
    let mut params = COPY_RANGE.to_be_bytes().to_vec();
    params.push(NFQNL_COPY_PACKET);
    let cfg_flags = NFQA_CFG_F_FAIL_OPEN | NFQA_CFG_F_GSO;
    vec![
        message(
            NFQNL_MSG_CONFIG,
            flags,
            1,
            queue,
            &[(NFQA_CFG_CMD, vec![NFQNL_CFG_CMD_BIND, 0, 0, 0])],
        ),
        message(
            NFQNL_MSG_CONFIG,
            flags,
            2,
            queue,
            &[
                (NFQA_CFG_PARAMS, params),
                (NFQA_CFG_QUEUE_MAXLEN, QUEUE_MAXLEN.to_be_bytes().to_vec()),
                (NFQA_CFG_FLAGS, cfg_flags.to_be_bytes().to_vec()),
                (NFQA_CFG_MASK, cfg_flags.to_be_bytes().to_vec()),
            ],
        ),
    ]
}

/// Accepts packet `id`, optionally with a new packet mark.
fn verdict_message(queue: u16, id: u32, mark: Option<u32>) -> Vec<u8> {
    let mut hdr = NF_ACCEPT.to_be_bytes().to_vec();
    hdr.extend(id.to_be_bytes());
    let mut attrs = vec![(NFQA_VERDICT_HDR, hdr)];
    if let Some(mark) = mark {
        attrs.push((NFQA_MARK, mark.to_be_bytes().to_vec()));
    }
    message(NFQNL_MSG_VERDICT, NLM_F_REQUEST, 0, queue, &attrs)
}

#[derive(Debug, PartialEq, Eq)]
pub enum Incoming<'a> {
    Packet {
        id: u32,
        mark: u32,
        payload: &'a [u8],
    },
    /// An acknowledgement (0) or error (negative errno) for message `seq`.
    Ack { seq: u32, errno: i32 },
}

/// The messages in one datagram from the socket. Anything unexpected is
/// skipped.
pub fn parse_datagram(mut buf: &[u8]) -> Vec<Incoming<'_>> {
    let mut out = Vec::new();
    while buf.len() >= 16 {
        let len = u32::from_ne_bytes(buf[0..4].try_into().unwrap()) as usize;
        if len < 16 || len > buf.len() {
            break;
        }
        let kind = u16::from_ne_bytes([buf[4], buf[5]]);
        let seq = u32::from_ne_bytes(buf[8..12].try_into().unwrap());
        let body = &buf[16..len];
        if kind == NLMSG_ERROR && body.len() >= 4 {
            let errno = i32::from_ne_bytes(body[0..4].try_into().unwrap());
            out.push(Incoming::Ack { seq, errno });
        } else if kind == NFNL_SUBSYS_QUEUE << 8 | NFQNL_MSG_PACKET
            && body.len() >= 4
            && let Some(packet) = parse_packet_attrs(&body[4..])
        {
            out.push(packet);
        }
        buf = &buf[len.next_multiple_of(4).min(buf.len())..];
    }
    out
}

fn parse_packet_attrs(mut attrs: &[u8]) -> Option<Incoming<'_>> {
    let (mut id, mut mark, mut payload) = (None, 0, None);
    while attrs.len() >= 4 {
        let len = usize::from(u16::from_ne_bytes([attrs[0], attrs[1]]));
        if len < 4 || len > attrs.len() {
            break;
        }
        let data = &attrs[4..len];
        match u16::from_ne_bytes([attrs[2], attrs[3]]) & NLA_TYPE_MASK {
            NFQA_PACKET_HDR if data.len() >= 4 => {
                id = Some(u32::from_be_bytes(data[0..4].try_into().unwrap()));
            }
            NFQA_MARK if data.len() >= 4 => {
                mark = u32::from_be_bytes(data[0..4].try_into().unwrap());
            }
            NFQA_PAYLOAD => payload = Some(data),
            _ => {}
        }
        attrs = &attrs[len.next_multiple_of(4).min(attrs.len())..];
    }
    Some(Incoming::Packet {
        id: id?,
        mark,
        payload: payload.unwrap_or(&[]),
    })
}

struct Queue {
    fd: OwnedFd,
    num: u16,
}

impl Queue {
    fn open(num: u16) -> io::Result<Self> {
        // SAFETY: plain socket calls on a descriptor we own.
        let fd = unsafe {
            libc::socket(
                libc::AF_NETLINK,
                libc::SOCK_RAW | libc::SOCK_CLOEXEC,
                libc::NETLINK_NETFILTER,
            )
        };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: `fd` is a fresh descriptor.
        let fd = unsafe { OwnedFd::from_raw_fd(fd) };
        let queue = Self { fd, num };
        let one: libc::c_int = 1;
        let rcvbuf: libc::c_int = 4 << 20;
        // SAFETY: valid pointers to ints of the right size. Failures only
        // make bursts more likely to overflow, which fails open.
        unsafe {
            libc::setsockopt(
                queue.fd.as_raw_fd(),
                libc::SOL_NETLINK,
                NETLINK_NO_ENOBUFS,
                (&raw const one).cast(),
                size_of::<libc::c_int>() as libc::socklen_t,
            );
            libc::setsockopt(
                queue.fd.as_raw_fd(),
                libc::SOL_SOCKET,
                libc::SO_RCVBUF,
                (&raw const rcvbuf).cast(),
                size_of::<libc::c_int>() as libc::socklen_t,
            );
        }
        let mut buf = vec![0u8; 8192];
        for msg in bind_messages(num) {
            queue.send(&msg)?;
            let seq = u32::from_ne_bytes(msg[8..12].try_into().unwrap());
            loop {
                let n = queue.recv(&mut buf)?;
                let ack = parse_datagram(&buf[..n]).into_iter().find_map(|m| match m {
                    Incoming::Ack { seq: s, errno } if s == seq => Some(errno),
                    _ => None,
                });
                match ack {
                    Some(0) => break,
                    Some(errno) => return Err(io::Error::from_raw_os_error(-errno)),
                    None => {}
                }
            }
        }
        Ok(queue)
    }

    fn send(&self, msg: &[u8]) -> io::Result<()> {
        // SAFETY: an all-zero sockaddr_nl addresses the kernel.
        let mut addr: libc::sockaddr_nl = unsafe { std::mem::zeroed() };
        addr.nl_family = libc::AF_NETLINK as libc::sa_family_t;
        // SAFETY: `msg` and `addr` are valid for the given lengths.
        let n = unsafe {
            libc::sendto(
                self.fd.as_raw_fd(),
                msg.as_ptr().cast(),
                msg.len(),
                0,
                (&raw const addr).cast(),
                size_of::<libc::sockaddr_nl>() as libc::socklen_t,
            )
        };
        if n < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }

    fn recv(&self, buf: &mut [u8]) -> io::Result<usize> {
        loop {
            // SAFETY: `buf` is valid for writes of its length.
            let n =
                unsafe { libc::recv(self.fd.as_raw_fd(), buf.as_mut_ptr().cast(), buf.len(), 0) };
            if n >= 0 {
                return Ok(n as usize);
            }
            let err = io::Error::last_os_error();
            if err.kind() != io::ErrorKind::Interrupted {
                return Err(err);
            }
        }
    }

    fn verdict(&self, id: u32, mark: Option<u32>) -> io::Result<()> {
        self.send(&verdict_message(self.num, id, mark))
    }
}

/// Reads the SNI queue for the life of the daemon. `rules` gives the rules
/// of the running session. If the queue cannot be bound (no
/// `nfnetlink_queue`), queued packets pass unjudged and binding is retried.
pub fn spawn(rules: Arc<dyn Fn() -> Option<Arc<Vec<Rule>>> + Send + Sync>) {
    let spawned = std::thread::Builder::new()
        .name("sni".into())
        .spawn(move || {
            let mut warned = false;
            loop {
                match Queue::open(SNI_QUEUE) {
                    Ok(queue) => {
                        info!("SNI inspection reading queue {SNI_QUEUE}");
                        warned = false;
                        if let Err(e) = serve(&queue, &*rules) {
                            warn!("SNI queue failed: {e}; binding it again");
                        }
                    }
                    Err(e) if !warned => {
                        warn!(
                            "cannot bind SNI queue {SNI_QUEUE}: {e}; TLS is judged by address only"
                        );
                        warned = true;
                    }
                    Err(_) => {}
                }
                std::thread::sleep(RETRY);
            }
        });
    if let Err(e) = spawned {
        warn!("cannot start the SNI inspector: {e}");
    }
}

fn serve(queue: &Queue, rules: &dyn Fn() -> Option<Arc<Vec<Rule>>>) -> io::Result<()> {
    let mut inspector = Inspector::default();
    let mut buf = vec![0u8; COPY_RANGE as usize + 4096];
    loop {
        let n = match queue.recv(&mut buf) {
            Ok(n) => n,
            Err(e) if e.raw_os_error() == Some(libc::ENOBUFS) => continue,
            Err(e) => return Err(e),
        };
        let rules = rules();
        for msg in parse_datagram(&buf[..n]) {
            let Incoming::Packet { id, mark, payload } = msg else {
                continue;
            };
            let (judgement, name) =
                inspector.inspect(Instant::now(), payload, rules.as_deref().map(Vec::as_slice));
            match name {
                Some(name) => debug!("sni {name}: {judgement:?}"),
                None => trace!("sni packet {id}: {judgement:?}"),
            }
            let mark = judgement.mark().map(|v| mark & !MARK_MASK | v);
            queue.verdict(id, mark)?;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verdict_layout() {
        let msg = verdict_message(0x4457, 7, Some(0x0001_445b));
        assert_eq!(msg.len(), 16 + 4 + 12 + 8);
        assert_eq!(u32::from_ne_bytes(msg[0..4].try_into().unwrap()), 40);
        assert_eq!(u16::from_ne_bytes([msg[4], msg[5]]), 0x0301);
        assert_eq!(&msg[18..20], &[0x44, 0x57]);
        // Verdict header: NF_ACCEPT, packet id; then the mark.
        assert_eq!(&msg[20..24], &[12, 0, 2, 0]);
        assert_eq!(&msg[24..32], &[0, 0, 0, 1, 0, 0, 0, 7]);
        assert_eq!(&msg[32..40], &[8, 0, 3, 0, 0, 1, 0x44, 0x5b]);
        assert_eq!(verdict_message(1, 7, None).len(), 32);
    }

    #[test]
    fn bind_layout() {
        let msgs = bind_messages(9);
        assert_eq!(msgs.len(), 2);
        // Bind command, then params padded from 9 to 12 bytes.
        assert_eq!(&msgs[0][20..28], &[8, 0, 1, 0, 1, 0, 0, 0]);
        assert_eq!(&msgs[1][20..24], &[9, 0, 2, 0]);
        assert_eq!(&msgs[1][24..29], &[0, 0, 0xff, 0xff, 2]);
        assert_eq!(&msgs[1][32..36], &[8, 0, 3, 0]);
        for m in &msgs {
            assert_eq!(m.len() % 4, 0);
            assert_eq!(u16::from_ne_bytes([m[6], m[7]]), NLM_F_REQUEST | NLM_F_ACK);
        }
    }

    fn packet_msg(id: u32, mark: Option<u32>, payload: &[u8]) -> Vec<u8> {
        let mut hdr = id.to_be_bytes().to_vec();
        hdr.extend([0x08, 0x00, 3]);
        let mut attrs = vec![(NFQA_PACKET_HDR, hdr)];
        if let Some(m) = mark {
            attrs.push((NFQA_MARK, m.to_be_bytes().to_vec()));
        }
        attrs.push((NFQA_PAYLOAD, payload.to_vec()));
        message(NFQNL_MSG_PACKET, 0, 0, 0x4457, &attrs)
    }

    #[test]
    fn parses_packets_and_acks() {
        let mut dgram = packet_msg(5, Some(0x1_0000), b"abc");
        dgram.extend(packet_msg(6, None, b""));
        let mut ack = vec![0u8; 36];
        ack[0..4].copy_from_slice(&36u32.to_ne_bytes());
        ack[4..6].copy_from_slice(&NLMSG_ERROR.to_ne_bytes());
        ack[8..12].copy_from_slice(&2u32.to_ne_bytes());
        ack[16..20].copy_from_slice(&(-1i32).to_ne_bytes());
        dgram.extend(ack);
        assert_eq!(
            parse_datagram(&dgram),
            [
                Incoming::Packet {
                    id: 5,
                    mark: 0x1_0000,
                    payload: b"abc"
                },
                Incoming::Packet {
                    id: 6,
                    mark: 0,
                    payload: b""
                },
                Incoming::Ack { seq: 2, errno: -1 },
            ]
        );
        assert!(parse_datagram(&[1, 2, 3]).is_empty());
        let mut truncated = packet_msg(5, None, b"abc");
        truncated[0] = 200;
        assert!(parse_datagram(&truncated).is_empty());
    }
}
