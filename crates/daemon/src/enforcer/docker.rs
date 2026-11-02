//! Optional lock on the Docker socket during sessions (profile `lock_docker`).
//!
//! Membership in the `docker` group is root in all but name: `docker run
//! --privileged -v /:/host` can flush the nft table without sudo, so the PAM
//! lock does not help. The lock takes group and other access off
//! `/run/docker.sock`; only root can talk to Docker until the session ends.
//! Running containers keep running.
//!
//! The socket's own mode is saved in a marker file in the state directory
//! before it is changed, so a crash or reboot mid-session still restores it
//! on the next start (a rebooted Docker recreates the socket open anyway).
//! Without a marker, [`DockerLock::lift`] leaves the socket alone: a socket
//! someone closed on purpose stays closed.

use std::os::unix::fs::PermissionsExt as _;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};

pub const SOCKET: &str = "/run/docker.sock";
const MARKER: &str = "docker-sock.mode";

/// `mode` with group and other access taken away.
pub fn locked_mode(mode: u32) -> u32 {
    mode & !0o077
}

pub fn is_locked(mode: u32) -> bool {
    mode & 0o077 == 0
}

/// Parses the marker file: the socket's mode before the lock, in octal.
pub fn parse_marker(text: &str) -> Option<u32> {
    u32::from_str_radix(text.trim(), 8)
        .ok()
        .filter(|m| *m <= 0o7777)
}

pub struct DockerLock {
    socket: PathBuf,
    marker: PathBuf,
}

impl DockerLock {
    pub fn new(state_dir: &Path) -> Self {
        Self::at(PathBuf::from(SOCKET), state_dir.join(MARKER))
    }

    fn at(socket: PathBuf, marker: PathBuf) -> Self {
        Self { socket, marker }
    }

    pub fn socket(&self) -> &Path {
        &self.socket
    }

    /// The socket's permission bits, or `None` if there is no socket
    /// (Docker not installed or not started).
    fn mode(&self) -> Result<Option<u32>> {
        match std::fs::metadata(&self.socket) {
            Ok(meta) => Ok(Some(meta.permissions().mode() & 0o7777)),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(e) => Err(e).with_context(|| format!("reading {}", self.socket.display())),
        }
    }

    fn chmod(&self, mode: u32) -> Result<()> {
        std::fs::set_permissions(&self.socket, std::fs::Permissions::from_mode(mode))
            .with_context(|| format!("chmod {:o} {}", mode, self.socket.display()))
    }

    /// Closes the socket if it is open. Returns true if it was open.
    pub fn apply(&self) -> Result<bool> {
        let Some(mode) = self.mode()? else {
            return Ok(false);
        };
        if is_locked(mode) {
            return Ok(false);
        }
        // Keep the first saved mode: a socket that is open again mid-session
        // was reopened, and that is not what to restore.
        if !self.marker.exists() {
            std::fs::write(&self.marker, format!("{mode:o}\n"))
                .with_context(|| format!("writing {}", self.marker.display()))?;
        }
        self.chmod(locked_mode(mode))?;
        Ok(true)
    }

    /// Restores the mode saved by [`DockerLock::apply`]. Returns true if the
    /// socket was changed.
    pub fn lift(&self) -> Result<bool> {
        let saved = match std::fs::read_to_string(&self.marker) {
            Ok(text) => parse_marker(&text),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(false),
            Err(e) => return Err(e).with_context(|| format!("reading {}", self.marker.display())),
        };
        let mut changed = false;
        if let (Some(saved), Some(mode)) = (saved, self.mode()?)
            && is_locked(mode)
            && mode != saved
        {
            self.chmod(saved)?;
            changed = true;
        }
        std::fs::remove_file(&self.marker)
            .with_context(|| format!("removing {}", self.marker.display()))?;
        Ok(changed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::net::UnixListener;

    #[test]
    fn modes() {
        assert_eq!(locked_mode(0o660), 0o600);
        assert_eq!(locked_mode(0o666), 0o600);
        assert!(is_locked(0o600));
        assert!(!is_locked(0o660));
        assert!(!is_locked(0o606));
        assert_eq!(parse_marker("660\n"), Some(0o660));
        assert_eq!(parse_marker("rw"), None);
        assert_eq!(parse_marker("77777"), None);
    }

    #[test]
    fn locks_and_restores_a_real_socket() {
        let dir = std::env::temp_dir().join(format!("dw-docker-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let lock = DockerLock::at(dir.join("docker.sock"), dir.join(MARKER));
        let mode = |l: &DockerLock| l.mode().unwrap();

        // No socket: nothing to do either way.
        assert!(!lock.apply().unwrap());
        assert!(!lock.lift().unwrap());

        let _listener = UnixListener::bind(lock.socket()).unwrap();
        lock.chmod(0o660).unwrap();
        assert!(lock.apply().unwrap());
        assert_eq!(mode(&lock), Some(0o600));
        assert!(!lock.apply().unwrap());

        // Opened again mid-session: closed again, and the first mode is kept.
        lock.chmod(0o666).unwrap();
        assert!(lock.apply().unwrap());
        assert_eq!(mode(&lock), Some(0o600));

        assert!(lock.lift().unwrap());
        assert_eq!(mode(&lock), Some(0o660));
        assert!(!dir.join(MARKER).exists());

        // Without a marker a closed socket is left closed.
        lock.chmod(0o600).unwrap();
        assert!(!lock.lift().unwrap());
        assert_eq!(mode(&lock), Some(0o600));

        std::fs::remove_dir_all(&dir).unwrap();
    }
}
