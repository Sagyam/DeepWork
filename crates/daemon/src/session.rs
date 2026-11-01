//! The session state machine. Pure: time only moves through [`Session::advance`],
//! which the daemon feeds with `Instant` (CLOCK_MONOTONIC) deltas. Suspend,
//! downtime and wall-clock changes therefore never count as focus time.

use std::time::Duration;

use deepwork_proto::{SURRENDER_PHRASE, SessionInfo, SessionKind, SessionState};

/// No session may run longer than this, whatever the config says. This is a
/// safety rail against bugs locking the user out.
pub const MAX_SESSION: Duration = Duration::from_secs(6 * 60 * 60);
pub const MIN_COUNTDOWN: Duration = Duration::from_secs(60);

#[derive(Debug, Clone, PartialEq)]
pub struct Session {
    /// 0 until the store assigns one.
    pub id: i64,
    pub kind: SessionKind,
    pub profile: String,
    pub state: SessionState,
    /// Unix seconds, for display and history only.
    pub started_at: i64,
    pub elapsed: Duration,
    /// Remaining surrender wait while `state == Surrendering`.
    pub surrender_left: Option<Duration>,
}

impl Session {
    pub fn new(kind: SessionKind, profile: String, started_at: i64) -> Result<Self, String> {
        if let SessionKind::Countdown { secs } = kind {
            let d = Duration::from_secs(secs);
            if d < MIN_COUNTDOWN {
                return Err("a countdown must be at least 1 minute".into());
            }
            if d > MAX_SESSION {
                return Err(format!(
                    "a countdown can be at most {} hours",
                    MAX_SESSION.as_secs() / 3600
                ));
            }
        }
        Ok(Self {
            id: 0,
            kind,
            profile,
            state: SessionState::Active,
            started_at,
            elapsed: Duration::ZERO,
            surrender_left: None,
        })
    }

    pub fn is_running(&self) -> bool {
        matches!(
            self.state,
            SessionState::Active | SessionState::Surrendering
        )
    }

    fn target(&self) -> Duration {
        match self.kind {
            SessionKind::Countdown { secs } => Duration::from_secs(secs),
            SessionKind::Stopwatch => MAX_SESSION,
        }
    }

    /// Moves time forward. Returns the final state if the session ended.
    pub fn advance(&mut self, delta: Duration) -> Option<SessionState> {
        if !self.is_running() {
            return None;
        }
        self.elapsed += delta;
        if let Some(left) = self.surrender_left.as_mut() {
            *left = left.saturating_sub(delta);
            if left.is_zero() {
                self.surrender_left = None;
                self.state = SessionState::Surrendered;
                return Some(self.state);
            }
        }
        if self.elapsed >= self.target() {
            self.elapsed = self.target();
            self.surrender_left = None;
            self.state = SessionState::Completed;
            return Some(self.state);
        }
        None
    }

    /// Ends a stopwatch session normally.
    pub fn stop(&mut self, stopwatch_min: Duration) -> Result<(), String> {
        if !self.is_running() {
            return Err("no session is running".into());
        }
        match self.kind {
            SessionKind::Countdown { .. } => Err(
                "a countdown cannot be stopped early; `deepwork surrender` is the only way out"
                    .into(),
            ),
            SessionKind::Stopwatch if self.elapsed < stopwatch_min => Err(format!(
                "a stopwatch can be stopped after {} minutes ({} left)",
                stopwatch_min.as_secs() / 60,
                fmt_secs((stopwatch_min - self.elapsed).as_secs())
            )),
            SessionKind::Stopwatch => {
                self.surrender_left = None;
                self.state = SessionState::Completed;
                Ok(())
            }
        }
    }

    /// Starts the surrender wait. Enforcement stays on until it runs out.
    pub fn surrender(&mut self, phrase: &str, wait: Duration) -> Result<(), String> {
        match self.state {
            SessionState::Active => {}
            SessionState::Surrendering => return Err("already surrendering".into()),
            _ => return Err("no session is running".into()),
        }
        if phrase.trim() != SURRENDER_PHRASE {
            return Err("the phrase does not match".into());
        }
        self.state = SessionState::Surrendering;
        self.surrender_left = Some(wait.max(Duration::from_secs(1)));
        Ok(())
    }

    pub fn info(&self, stopwatch_min: Duration) -> SessionInfo {
        let remaining_secs = match self.kind {
            SessionKind::Countdown { .. } => {
                Some(self.target().saturating_sub(self.elapsed).as_secs())
            }
            SessionKind::Stopwatch => None,
        };
        let stop_locked_secs = match self.kind {
            SessionKind::Stopwatch => stopwatch_min.saturating_sub(self.elapsed).as_secs(),
            SessionKind::Countdown { .. } => 0,
        };
        SessionInfo {
            id: self.id,
            kind: self.kind,
            profile: self.profile.clone(),
            state: self.state,
            started_at: self.started_at,
            elapsed_secs: self.elapsed.as_secs(),
            remaining_secs,
            stop_locked_secs,
            surrender_remaining_secs: self.surrender_left.map(|d| d.as_secs()),
        }
    }
}

fn fmt_secs(secs: u64) -> String {
    format!("{}:{:02}", secs / 60, secs % 60)
}

#[cfg(test)]
mod tests {
    use super::*;

    const MIN: Duration = Duration::from_secs(60);

    fn countdown(mins: u64) -> Session {
        Session::new(SessionKind::Countdown { secs: mins * 60 }, "deep".into(), 0).unwrap()
    }

    fn stopwatch() -> Session {
        Session::new(SessionKind::Stopwatch, "deep".into(), 0).unwrap()
    }

    #[test]
    fn countdown_completes() {
        let mut s = countdown(25);
        assert_eq!(s.advance(24 * MIN), None);
        assert_eq!(s.info(10 * MIN).remaining_secs, Some(60));
        assert_eq!(s.advance(2 * MIN), Some(SessionState::Completed));
        assert_eq!(s.elapsed, 25 * MIN);
        assert_eq!(s.advance(MIN), None);
    }

    #[test]
    fn countdown_bounds() {
        assert!(Session::new(SessionKind::Countdown { secs: 30 }, "d".into(), 0).is_err());
        assert!(Session::new(SessionKind::Countdown { secs: 7 * 3600 }, "d".into(), 0).is_err());
    }

    #[test]
    fn countdown_cannot_stop() {
        let mut s = countdown(25);
        s.advance(24 * MIN);
        assert!(s.stop(10 * MIN).is_err());
        assert!(s.is_running());
    }

    #[test]
    fn stopwatch_min_and_max() {
        let mut s = stopwatch();
        s.advance(5 * MIN);
        assert!(s.stop(10 * MIN).is_err());
        assert_eq!(s.info(10 * MIN).stop_locked_secs, 300);
        s.advance(5 * MIN);
        assert!(s.stop(10 * MIN).is_ok());
        assert_eq!(s.state, SessionState::Completed);

        let mut s = stopwatch();
        assert_eq!(s.advance(MAX_SESSION), Some(SessionState::Completed));
    }

    #[test]
    fn surrender_waits_then_ends() {
        let mut s = countdown(60);
        assert!(s.surrender("let me out", 10 * MIN).is_err());
        s.surrender(SURRENDER_PHRASE, 10 * MIN).unwrap();
        assert!(s.surrender(SURRENDER_PHRASE, 10 * MIN).is_err());
        assert_eq!(s.advance(9 * MIN), None);
        assert!(s.is_running());
        assert_eq!(s.advance(MIN), Some(SessionState::Surrendered));
    }

    #[test]
    fn completion_beats_surrender() {
        let mut s = countdown(25);
        s.advance(20 * MIN);
        s.surrender(SURRENDER_PHRASE, 10 * MIN).unwrap();
        assert_eq!(s.advance(5 * MIN), Some(SessionState::Completed));
    }
}
