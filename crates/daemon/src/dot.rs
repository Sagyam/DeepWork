//! One long-lived, pipelined connection per DNS-over-TLS upstream (RFC 7858
//! section 3.3), instead of a TCP and TLS handshake per query.
//!
//! Queries get an internal message ID on the wire, so answers may come back
//! in any order and callers that reuse IDs never collide. The connection is
//! opened on the first query, closed after [`IDLE`] without traffic, and
//! reopened on demand. The transport is generic so tests can use in-memory
//! streams.

use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Result, anyhow, bail};
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};
use tokio::sync::{mpsc, oneshot};
use tracing::debug;

/// Close the connection after this long with nothing in flight.
pub const IDLE: Duration = Duration::from_secs(20);

pub trait Stream: AsyncRead + AsyncWrite + Send + Unpin + 'static {}
impl<T: AsyncRead + AsyncWrite + Send + Unpin + 'static> Stream for T {}

pub type Connect =
    Arc<dyn Fn() -> Pin<Box<dyn Future<Output = Result<Box<dyn Stream>>> + Send>> + Send + Sync>;

type Reply = oneshot::Sender<Result<Vec<u8>>>;

/// Handle to the connection task. Cheap to clone.
#[derive(Clone)]
pub struct Pipeline {
    tx: mpsc::Sender<(Vec<u8>, Reply)>,
}

impl Pipeline {
    pub fn new(connect: Connect) -> Self {
        let (tx, rx) = mpsc::channel(256);
        tokio::spawn(run(connect, rx));
        Self { tx }
    }

    /// Sends one query and waits for its answer. The caller applies its own
    /// timeout. An error on a connection that was already open is retried
    /// once on a fresh one, since servers close idle connections.
    pub async fn query(&self, msg: &[u8]) -> Result<Vec<u8>> {
        if msg.len() < 12 {
            bail!("query too short");
        }
        let mut last = anyhow!("no attempt");
        for _ in 0..2 {
            let (reply, rx) = oneshot::channel();
            self.tx
                .send((msg.to_vec(), reply))
                .await
                .map_err(|_| anyhow!("connection task is gone"))?;
            match rx.await {
                Ok(Ok(resp)) => return Ok(resp),
                Ok(Err(e)) => last = e,
                Err(_) => last = anyhow!("connection dropped the query"),
            }
        }
        Err(last)
    }
}

/// One open connection: a writer half, a reader task feeding `frames`, and the
/// queries waiting for an answer, by wire ID.
struct Conn {
    write: tokio::io::WriteHalf<Box<dyn Stream>>,
    frames: mpsc::Receiver<std::io::Result<Vec<u8>>>,
    pending: HashMap<u16, (u16, Reply)>,
    next_id: u16,
}

impl Conn {
    async fn open(connect: &Connect) -> Result<Self> {
        let stream = connect().await?;
        let (mut read, write) = tokio::io::split(stream);
        let (frame_tx, frames) = mpsc::channel(64);
        tokio::spawn(async move {
            loop {
                let frame = read_framed(&mut read).await;
                let failed = frame.is_err();
                if frame_tx.send(frame).await.is_err() || failed {
                    return;
                }
            }
        });
        Ok(Self {
            write,
            frames,
            pending: HashMap::new(),
            next_id: rand_id(),
        })
    }

    fn fail_all(&mut self, why: &str) {
        for (_, (_, reply)) in self.pending.drain() {
            let _ = reply.send(Err(anyhow!("{why}")));
        }
    }

    async fn send(&mut self, mut msg: Vec<u8>, reply: Reply) -> std::io::Result<()> {
        // Callers that gave up (timeout) no longer need their slot.
        self.pending.retain(|_, (_, r)| !r.is_closed());
        let id = loop {
            let id = self.next_id;
            self.next_id = self.next_id.wrapping_add(1);
            if !self.pending.contains_key(&id) {
                break id;
            }
        };
        let orig = u16::from_be_bytes([msg[0], msg[1]]);
        msg[..2].copy_from_slice(&id.to_be_bytes());
        self.pending.insert(id, (orig, reply));
        write_framed(&mut self.write, &msg).await
    }

    fn deliver(&mut self, mut frame: Vec<u8>) {
        if frame.len() < 2 {
            return;
        }
        let id = u16::from_be_bytes([frame[0], frame[1]]);
        if let Some((orig, reply)) = self.pending.remove(&id) {
            frame[..2].copy_from_slice(&orig.to_be_bytes());
            let _ = reply.send(Ok(frame));
        }
    }
}

fn rand_id() -> u16 {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.subsec_nanos());
    (nanos ^ (nanos >> 16)) as u16
}

async fn run(connect: Connect, mut rx: mpsc::Receiver<(Vec<u8>, Reply)>) {
    let mut conn: Option<Conn> = None;
    loop {
        let Some(c) = conn.as_mut() else {
            // Idle with no connection: wait for a query, then connect.
            let Some((msg, reply)) = rx.recv().await else {
                return;
            };
            match Conn::open(&connect).await {
                Ok(mut c) => {
                    if let Err(e) = c.send(msg, reply).await {
                        c.fail_all(&format!("write failed: {e}"));
                        continue;
                    }
                    conn = Some(c);
                }
                Err(e) => {
                    let _ = reply.send(Err(e));
                }
            }
            continue;
        };
        tokio::select! {
            req = rx.recv() => {
                let Some((msg, reply)) = req else { return };
                if let Err(e) = c.send(msg, reply).await {
                    c.fail_all(&format!("write failed: {e}"));
                    conn = None;
                }
            }
            frame = c.frames.recv() => match frame {
                Some(Ok(frame)) => c.deliver(frame),
                Some(Err(e)) => {
                    debug!("dot: connection closed: {e}");
                    c.fail_all(&format!("connection closed: {e}"));
                    conn = None;
                }
                None => {
                    c.fail_all("connection closed");
                    conn = None;
                }
            },
            () = tokio::time::sleep(IDLE), if c.pending.is_empty() => {
                debug!("dot: closing idle connection");
                conn = None;
            }
        }
    }
}

pub async fn read_framed(stream: &mut (impl AsyncRead + Unpin)) -> std::io::Result<Vec<u8>> {
    let len = stream.read_u16().await?;
    let mut buf = vec![0u8; usize::from(len)];
    stream.read_exact(&mut buf).await?;
    Ok(buf)
}

pub async fn write_framed(
    stream: &mut (impl AsyncWrite + Unpin),
    msg: &[u8],
) -> std::io::Result<()> {
    let len = u16::try_from(msg.len())
        .map_err(|_| std::io::Error::new(std::io::ErrorKind::InvalidInput, "message too long"))?;
    let mut out = Vec::with_capacity(msg.len() + 2);
    out.extend_from_slice(&len.to_be_bytes());
    out.extend_from_slice(msg);
    stream.write_all(&out).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    /// A fake server: answers each query with `query bytes + b"!"`, holding
    /// back the first `reverse` queries and answering them in reverse order.
    /// Closes the connection after `max` queries.
    fn server(connects: Arc<AtomicUsize>, reverse: usize, max: usize) -> Connect {
        Arc::new(move || {
            connects.fetch_add(1, Ordering::SeqCst);
            Box::pin(async move {
                let (client, mut srv) = tokio::io::duplex(4096);
                tokio::spawn(async move {
                    let mut held = Vec::new();
                    for n in 0..max {
                        let Ok(mut q) = read_framed(&mut srv).await else {
                            return;
                        };
                        q.push(b'!');
                        if n < reverse {
                            held.push(q);
                            if held.len() == reverse {
                                for q in held.drain(..).rev() {
                                    write_framed(&mut srv, &q).await.unwrap();
                                }
                            }
                        } else {
                            write_framed(&mut srv, &q).await.unwrap();
                        }
                    }
                });
                Ok(Box::new(client) as Box<dyn Stream>)
            })
        })
    }

    fn query(id: u16, tag: u8) -> Vec<u8> {
        let mut q = id.to_be_bytes().to_vec();
        q.extend_from_slice(&[0; 10]);
        q.push(tag);
        q
    }

    #[tokio::test]
    async fn reuses_one_connection_out_of_order() {
        let connects = Arc::new(AtomicUsize::new(0));
        let p = Pipeline::new(server(connects.clone(), 2, 100));
        // Same caller ID on both: the pipeline must keep them apart.
        let (qa, qb) = (query(7, b'a'), query(7, b'b'));
        let (a, b) = tokio::join!(p.query(&qa), p.query(&qb));
        let (a, b) = (a.unwrap(), b.unwrap());
        assert_eq!(&a[..2], &7u16.to_be_bytes());
        assert_eq!(&a[12..], b"a!");
        assert_eq!(&b[12..], b"b!");
        for i in 0..5 {
            let r = p.query(&query(i, b'x')).await.unwrap();
            assert_eq!(&r[..2], &i.to_be_bytes());
        }
        assert_eq!(connects.load(Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn reconnects_after_server_closes() {
        let connects = Arc::new(AtomicUsize::new(0));
        let p = Pipeline::new(server(connects.clone(), 0, 1));
        p.query(&query(1, b'a')).await.unwrap();
        // The server hung up after one answer; the next query reconnects.
        tokio::time::sleep(Duration::from_millis(20)).await;
        let r = p.query(&query(2, b'b')).await.unwrap();
        assert_eq!(&r[12..], b"b!");
        assert_eq!(connects.load(Ordering::SeqCst), 2);
    }

    #[tokio::test(start_paused = true)]
    async fn closes_when_idle() {
        let connects = Arc::new(AtomicUsize::new(0));
        let p = Pipeline::new(server(connects.clone(), 0, 100));
        p.query(&query(1, b'a')).await.unwrap();
        tokio::time::sleep(IDLE + Duration::from_secs(1)).await;
        p.query(&query(2, b'b')).await.unwrap();
        assert_eq!(connects.load(Ordering::SeqCst), 2);
    }

    #[tokio::test]
    async fn connect_errors_are_returned() {
        let p = Pipeline::new(Arc::new(|| Box::pin(async { Err(anyhow!("refused")) })));
        assert!(p.query(&query(1, b'a')).await.is_err());
        assert!(p.query(&[1, 2]).await.is_err());
    }
}
