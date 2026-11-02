//! A small forwarding DNS resolver. During a session systemd-resolved uses it
//! as its upstream, and nft redirects every other port 53 packet to it.
//!
//! Answers are passed through unchanged. When a session is running and an
//! answer belongs to a profile rule, its addresses are handed to the enforcer.

use std::collections::HashMap;
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr};
use std::sync::{Arc, Mutex, RwLock};
use std::time::Duration;

use anyhow::{Context, Result, bail};
use hickory_proto::op::{Message, MessageType, Query, ResponseCode};
use hickory_proto::rr::{Name, RData, RecordType};
use tokio::net::{TcpListener, TcpSocket, TcpStream, UdpSocket};
use tokio::sync::Semaphore;
use tokio::task::JoinSet;
use tokio::time::timeout;
use tokio_rustls::TlsConnector;
use tokio_rustls::rustls::pki_types::ServerName;
use tokio_rustls::rustls::{self, ClientConfig, RootCertStore};
use tracing::{debug, info, warn};

use crate::config::{Action, DnsConfig, Rule, Upstream, domain_matches};
use crate::dot::{self, Pipeline, read_framed, write_framed};
use crate::enforcer::EnforcerHandle;
use crate::enforcer::nft::EXEMPT_MARK;

/// Firefox-family browsers disable their built-in DoH when this name fails.
const DOH_CANARY: &str = "use-application-dns.net";
const UPSTREAM_TIMEOUT: Duration = Duration::from_secs(2);
const TCP_IDLE_TIMEOUT: Duration = Duration::from_secs(10);
/// Addresses stay in the sets this long past their DNS TTL, so a browser that
/// caches longer than the TTL is still caught.
const SET_TIMEOUT_SLACK_SECS: u32 = 3600;
const PRIME_CONCURRENCY: usize = 4;

pub struct Resolver {
    cfg: DnsConfig,
    /// `None` in dry-run, where setting `SO_MARK` is not permitted.
    mark: Option<u32>,
    rules: RwLock<Option<Arc<Vec<Rule>>>>,
    enforcer: EnforcerHandle,
    tls: TlsConnector,
    /// One reused connection per DNS-over-TLS upstream.
    dot: Mutex<HashMap<(SocketAddr, String), Pipeline>>,
}

impl Resolver {
    pub fn new(cfg: DnsConfig, dry_run: bool, enforcer: EnforcerHandle) -> Result<Arc<Self>> {
        let roots = RootCertStore {
            roots: webpki_roots::TLS_SERVER_ROOTS.to_vec(),
        };
        let tls =
            ClientConfig::builder_with_provider(Arc::new(rustls::crypto::ring::default_provider()))
                .with_safe_default_protocol_versions()?
                .with_root_certificates(roots)
                .with_no_client_auth();
        Ok(Arc::new(Self {
            cfg,
            mark: (!dry_run).then_some(EXEMPT_MARK),
            rules: RwLock::new(None),
            enforcer,
            tls: TlsConnector::from(Arc::new(tls)),
            dot: Mutex::new(HashMap::new()),
        }))
    }

    /// Rules to act on, or `None` outside a session.
    pub fn set_rules(&self, rules: Option<Vec<Rule>>) {
        *self.rules.write().unwrap() = rules.map(Arc::new);
    }

    /// The rules of the running session, also used by the SNI inspector.
    pub fn rules(&self) -> Option<Arc<Vec<Rule>>> {
        self.rules.read().unwrap().clone()
    }

    pub async fn serve(self: Arc<Self>) -> Result<()> {
        let mut tasks = JoinSet::new();
        let mut bound = 0;
        for ip in [
            IpAddr::V4(Ipv4Addr::LOCALHOST),
            IpAddr::V6(Ipv6Addr::LOCALHOST),
        ] {
            let addr = SocketAddr::new(ip, self.cfg.port);
            match UdpSocket::bind(addr).await {
                Ok(sock) => {
                    tasks.spawn(self.clone().serve_udp(Arc::new(sock)));
                    bound += 1;
                }
                Err(e) => warn!("dns: cannot bind udp {addr}: {e}"),
            }
            match TcpListener::bind(addr).await {
                Ok(listener) => {
                    tasks.spawn(self.clone().serve_tcp(listener));
                }
                Err(e) => warn!("dns: cannot bind tcp {addr}: {e}"),
            }
        }
        if bound == 0 {
            bail!("dns: could not bind port {}", self.cfg.port);
        }
        info!("dns: listening on port {}", self.cfg.port);
        while let Some(res) = tasks.join_next().await {
            res??;
        }
        Ok(())
    }

    async fn serve_udp(self: Arc<Self>, sock: Arc<UdpSocket>) -> Result<()> {
        let mut buf = vec![0u8; 65535];
        loop {
            let (len, peer) = sock.recv_from(&mut buf).await?;
            let query = buf[..len].to_vec();
            let (this, sock) = (self.clone(), sock.clone());
            tokio::spawn(async move {
                if let Some(resp) = this.handle(&query, false).await {
                    let _ = sock.send_to(&resp, peer).await;
                }
            });
        }
    }

    async fn serve_tcp(self: Arc<Self>, listener: TcpListener) -> Result<()> {
        loop {
            let (stream, _) = listener.accept().await?;
            let this = self.clone();
            tokio::spawn(async move {
                if let Err(e) = this.serve_tcp_conn(stream).await {
                    debug!("dns: tcp connection ended: {e:#}");
                }
            });
        }
    }

    async fn serve_tcp_conn(&self, mut stream: TcpStream) -> Result<()> {
        loop {
            let Ok(query) = timeout(TCP_IDLE_TIMEOUT, read_framed(&mut stream)).await else {
                return Ok(());
            };
            let query = query?;
            let Some(resp) = self.handle(&query, true).await else {
                continue;
            };
            write_framed(&mut stream, &resp).await?;
        }
    }

    /// Answers one query. `None` means the query was unparseable and is dropped.
    async fn handle(&self, query: &[u8], tcp: bool) -> Option<Vec<u8>> {
        let req = Message::from_vec(query).ok()?;
        let qname = req.queries.first().map(|q| normalize(q.name()))?;

        if qname == DOH_CANARY {
            return reply_with_code(&req, ResponseCode::NXDomain);
        }

        let servers: Vec<Upstream> = match self
            .cfg
            .forward
            .iter()
            .find(|z| domain_matches(&qname, &z.suffix))
        {
            Some(zone) => vec![Upstream::Plain(zone.server)],
            None => self.cfg.upstreams.clone(),
        };

        for server in servers {
            let result = match &server {
                Upstream::Tls { addr, tls_name } => self.forward_tls(*addr, tls_name, query).await,
                Upstream::Plain(addr) if tcp => self.forward_tcp(*addr, query).await,
                Upstream::Plain(addr) => self.forward_udp(*addr, query, req.metadata.id).await,
            };
            match result {
                Ok(resp) => {
                    self.record(&resp);
                    return Some(if tcp { resp } else { fit_udp(&req, resp) });
                }
                Err(e) => debug!("dns: {} failed for {qname}: {e:#}", server.addr()),
            }
        }
        reply_with_code(&req, ResponseCode::ServFail)
    }

    async fn forward_udp(&self, server: SocketAddr, query: &[u8], id: u16) -> Result<Vec<u8>> {
        let local: SocketAddr = if server.is_ipv4() {
            (Ipv4Addr::UNSPECIFIED, 0).into()
        } else {
            (Ipv6Addr::UNSPECIFIED, 0).into()
        };
        let sock = UdpSocket::bind(local).await?;
        if let Some(mark) = self.mark {
            socket2::SockRef::from(&sock).set_mark(mark)?;
        }
        sock.connect(server).await?;
        sock.send(query).await?;
        let mut buf = vec![0u8; 65535];
        timeout(UPSTREAM_TIMEOUT, async {
            loop {
                let len = sock.recv(&mut buf).await?;
                // Ignore anything that is not the reply to our query.
                if len >= 2 && u16::from_be_bytes([buf[0], buf[1]]) == id {
                    return Ok(buf[..len].to_vec());
                }
            }
        })
        .await
        .context("timed out")?
    }

    async fn forward_tcp(&self, server: SocketAddr, query: &[u8]) -> Result<Vec<u8>> {
        timeout(UPSTREAM_TIMEOUT, async {
            let mut stream = connect_tcp(server, self.mark).await?;
            write_framed(&mut stream, query).await?;
            Ok(read_framed(&mut stream).await?)
        })
        .await
        .context("timed out")?
    }

    /// DNS-over-TLS (RFC 7858) over a reused, pipelined connection.
    async fn forward_tls(
        &self,
        server: SocketAddr,
        tls_name: &str,
        query: &[u8],
    ) -> Result<Vec<u8>> {
        let pipeline = self.pipeline(server, tls_name)?;
        timeout(UPSTREAM_TIMEOUT, pipeline.query(query))
            .await
            .context("timed out")?
    }

    fn pipeline(&self, server: SocketAddr, tls_name: &str) -> Result<Pipeline> {
        let mut pipes = self.dot.lock().unwrap();
        let key = (server, tls_name.to_string());
        if let Some(p) = pipes.get(&key) {
            return Ok(p.clone());
        }
        let name = ServerName::try_from(tls_name.to_string())?;
        let (tls, mark) = (self.tls.clone(), self.mark);
        let connect: dot::Connect = Arc::new(move || {
            let (tls, name) = (tls.clone(), name.clone());
            Box::pin(async move {
                let tcp = connect_tcp(server, mark).await?;
                let stream = tls.connect(name, tcp).await?;
                Ok(Box::new(stream) as Box<dyn dot::Stream>)
            })
        });
        let p = Pipeline::new(connect);
        pipes.insert(key, p.clone());
        Ok(p)
    }

    /// Hands addresses from a matching answer to the enforcer.
    fn record(&self, resp: &[u8]) {
        let Some(rules) = self.rules() else {
            return;
        };
        let Ok(msg) = Message::from_vec(resp) else {
            return;
        };
        if let Some((action, addrs, ttl)) = matching_addrs(&msg, &rules) {
            debug!("dns: {action:?} {addrs:?}");
            self.enforcer
                .add_addrs(action, addrs, ttl.saturating_add(SET_TIMEOUT_SLACK_SECS));
        }
    }

    /// Resolves every rule domain once, so the sets are filled before the
    /// browser asks.
    pub async fn prime(self: Arc<Self>, domains: Vec<String>) {
        // Upstreams reset connections when we open dozens of TLS sessions at
        // once.
        let limit = Arc::new(Semaphore::new(PRIME_CONCURRENCY));
        let mut tasks = JoinSet::new();
        for domain in domains {
            for name in [domain.clone(), format!("www.{domain}")] {
                for qtype in [RecordType::A, RecordType::AAAA] {
                    let Ok(name) = Name::from_ascii(&name) else {
                        continue;
                    };
                    let mut msg = Message::query();
                    msg.metadata.recursion_desired = true;
                    msg.add_query(Query::query(name, qtype));
                    let Ok(bytes) = msg.to_vec() else { continue };
                    let this = self.clone();
                    let limit = limit.clone();
                    tasks.spawn(async move {
                        let _permit = limit.acquire().await;
                        this.handle(&bytes, false).await
                    });
                }
            }
        }
        while tasks.join_next().await.is_some() {}
    }
}

/// A TCP connection that carries the exempt mark, so nft does not redirect it
/// back to us.
async fn connect_tcp(server: SocketAddr, mark: Option<u32>) -> Result<TcpStream> {
    let sock = if server.is_ipv4() {
        TcpSocket::new_v4()?
    } else {
        TcpSocket::new_v6()?
    };
    if let Some(mark) = mark {
        socket2::SockRef::from(&sock).set_mark(mark)?;
    }
    Ok(sock.connect(server).await?)
}

fn normalize(name: &Name) -> String {
    name.to_ascii().trim_end_matches('.').to_ascii_lowercase()
}

/// If any name in `msg` falls under a rule, returns the strictest action, every
/// A/AAAA address in the answer, and the smallest TTL among them.
fn matching_addrs(msg: &Message, rules: &[Rule]) -> Option<(Action, Vec<IpAddr>, u32)> {
    let names = msg
        .queries
        .iter()
        .map(|q| normalize(q.name()))
        .chain(msg.answers.iter().map(|r| normalize(&r.name)));
    let mut action = None;
    for name in names {
        for rule in rules.iter().filter(|r| domain_matches(&name, &r.domain)) {
            if action != Some(Action::Block) {
                action = Some(rule.action);
            }
        }
    }
    let action = action?;

    let mut ttl = u32::MAX;
    let addrs: Vec<IpAddr> = msg
        .answers
        .iter()
        .filter_map(|r| {
            let ip = match &r.data {
                RData::A(a) => IpAddr::V4(a.0),
                RData::AAAA(a) => IpAddr::V6(a.0),
                _ => return None,
            };
            ttl = ttl.min(r.ttl);
            Some(ip)
        })
        .collect();
    (!addrs.is_empty()).then_some((action, addrs, ttl))
}

/// An answer that fits the client's UDP limit (EDNS payload size, or 512
/// bytes without EDNS). A DoT or TCP upstream can return more than that; the
/// client then gets the header and question with TC set and retries over TCP.
fn fit_udp(req: &Message, resp: Vec<u8>) -> Vec<u8> {
    if resp.len() <= usize::from(req.max_payload()) {
        return resp;
    }
    let mut truncated = match Message::from_vec(&resp) {
        Ok(mut msg) => {
            msg.answers.clear();
            msg.authorities.clear();
            msg.additionals.clear();
            msg
        }
        Err(_) => {
            let mut msg = Message::response(req.metadata.id, req.metadata.op_code);
            msg.metadata.recursion_desired = req.metadata.recursion_desired;
            msg.metadata.recursion_available = true;
            msg.add_queries(req.queries.iter().cloned());
            msg
        }
    };
    truncated.metadata.truncation = true;
    truncated.to_vec().unwrap_or(resp)
}

fn reply_with_code(req: &Message, code: ResponseCode) -> Option<Vec<u8>> {
    let mut resp = Message::error_msg(req.metadata.id, req.metadata.op_code, code);
    resp.metadata.message_type = MessageType::Response;
    resp.metadata.recursion_desired = req.metadata.recursion_desired;
    resp.metadata.recursion_available = true;
    resp.add_queries(req.queries.iter().cloned());
    resp.to_vec().ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use hickory_proto::rr::Record;
    use hickory_proto::rr::rdata::{A, AAAA, CNAME};

    fn rule(domain: &str, action: Action) -> Rule {
        Rule {
            domain: domain.into(),
            action,
        }
    }

    fn answer(qname: &str, records: Vec<Record>) -> Message {
        let mut msg = Message::response(7, hickory_proto::op::OpCode::Query);
        msg.add_query(Query::query(
            Name::from_ascii(qname).unwrap(),
            RecordType::A,
        ));
        msg.add_answers(records);
        msg
    }

    fn rec(name: &str, ttl: u32, data: RData) -> Record {
        Record::from_rdata(Name::from_ascii(name).unwrap(), ttl, data)
    }

    #[test]
    fn follows_cname_chain() {
        let msg = answer(
            "www.youtube.com.",
            vec![
                rec(
                    "www.youtube.com.",
                    300,
                    RData::CNAME(CNAME(Name::from_ascii("youtube-ui.l.google.com.").unwrap())),
                ),
                rec(
                    "youtube-ui.l.google.com.",
                    120,
                    RData::A(A::new(142, 250, 1, 1)),
                ),
                rec(
                    "youtube-ui.l.google.com.",
                    90,
                    RData::AAAA(AAAA::new(0x2607, 0xf8b0, 0, 0, 0, 0, 0, 1)),
                ),
            ],
        );
        let (action, addrs, ttl) =
            matching_addrs(&msg, &[rule("youtube.com", Action::Throttle)]).unwrap();
        assert_eq!(action, Action::Throttle);
        assert_eq!(addrs.len(), 2);
        assert_eq!(ttl, 90);
    }

    #[test]
    fn block_wins_and_unmatched_is_ignored() {
        let msg = answer(
            "old.reddit.com.",
            vec![rec("old.reddit.com.", 60, RData::A(A::new(1, 2, 3, 4)))],
        );
        let rules = [
            rule("com", Action::Throttle),
            rule("reddit.com", Action::Block),
        ];
        assert_eq!(matching_addrs(&msg, &rules).unwrap().0, Action::Block);
        assert!(matching_addrs(&msg, &[rule("youtube.com", Action::Throttle)]).is_none());
    }

    #[test]
    fn large_udp_answers_are_truncated() {
        let mut req = Message::query();
        req.add_query(Query::query(
            Name::from_ascii("big.example.").unwrap(),
            RecordType::A,
        ));
        let records = (0..60u8)
            .map(|i| rec("big.example.", 60, RData::A(A::new(10, 0, 0, i))))
            .collect();
        let mut big = answer("big.example.", records);
        big.metadata.id = req.metadata.id;
        let bytes = big.to_vec().unwrap();
        assert!(bytes.len() > 512);

        let out = Message::from_vec(&fit_udp(&req, bytes.clone())).unwrap();
        assert!(out.metadata.truncation);
        assert_eq!(out.metadata.id, req.metadata.id);
        assert!(out.answers.is_empty());
        assert_eq!(out.queries.len(), 1);

        // With a 4096-byte EDNS size it fits and is passed through.
        let mut edns = hickory_proto::op::Edns::new();
        edns.set_max_payload(4096);
        req.edns = Some(edns);
        assert_eq!(fit_udp(&req, bytes.clone()), bytes);
        // Unparseable upstream bytes still produce a truncated reply.
        let junk = vec![0u8; 600];
        assert!(
            Message::from_vec(&fit_udp(&Message::query(), junk))
                .unwrap()
                .metadata
                .truncation
        );
    }

    #[test]
    fn canary_reply_is_nxdomain() {
        let mut req = Message::query();
        req.add_query(Query::query(
            Name::from_ascii("use-application-dns.net.").unwrap(),
            RecordType::A,
        ));
        let resp =
            Message::from_vec(&reply_with_code(&req, ResponseCode::NXDomain).unwrap()).unwrap();
        assert_eq!(resp.metadata.id, req.metadata.id);
        assert_eq!(resp.metadata.response_code, ResponseCode::NXDomain);
        assert_eq!(resp.metadata.message_type, MessageType::Response);
    }
}
