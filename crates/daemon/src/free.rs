//! Free minutes for inverted mode. Pure.
//!
//! Completed sessions add to a bank; spending it lifts the outside-session
//! throttle until the bank is empty or the requested span is over. Time is
//! counted from monotonic tick deltas, like sessions, so suspend and clock
//! changes neither use nor create free time.

use std::time::Duration;

use serde::{Deserialize, Serialize};

use crate::config::InvertedConfig;

/// The shortest spend worth lifting the throttle for.
pub const MIN_SPEND: Duration = Duration::from_secs(60);

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Bank {
    pub balance_ms: u64,
    /// Free time is being spent. `Some(None)` spends until the bank is
    /// empty, `Some(Some(n))` for at most `n` more milliseconds.
    pub spending: Option<Option<u64>>,
}

/// Free time earned for `focused` time at `cfg`'s rate, before the cap.
pub fn earned(cfg: &InvertedConfig, focused: Duration) -> Duration {
    Duration::from_secs(focused.as_secs() * u64::from(cfg.free_mins_per_hour) / 60)
}

impl Bank {
    pub fn is_spending(&self) -> bool {
        self.spending.is_some()
    }

    pub fn balance_secs(&self) -> u64 {
        self.balance_ms / 1000
    }

    /// Adds `earned` up to the cap. Returns what was actually added.
    pub fn deposit(&mut self, earned: Duration, cfg: &InvertedConfig) -> Duration {
        let cap = u64::from(cfg.max_bank_mins) * 60_000;
        let before = self.balance_ms;
        self.balance_ms = before
            .saturating_add(earned.as_millis() as u64)
            .min(cap.max(before));
        Duration::from_millis(self.balance_ms - before)
    }

    /// Starts spending, for at most `limit` if given.
    pub fn spend(&mut self, limit: Option<Duration>) -> Result<(), String> {
        if self.is_spending() {
            return Err("free time is already running".into());
        }
        if self.balance_ms < MIN_SPEND.as_millis() as u64 {
            return Err(format!(
                "not enough free time banked ({} s); complete a session to earn more",
                self.balance_secs()
            ));
        }
        if let Some(l) = limit
            && l < MIN_SPEND
        {
            return Err("spend at least a minute".into());
        }
        self.spending = Some(limit.map(|l| l.as_millis() as u64));
        Ok(())
    }

    /// Stops spending; what is left stays banked. False if not spending.
    pub fn stop(&mut self) -> bool {
        self.spending.take().is_some()
    }

    /// Seconds until spending stops on its own.
    pub fn stops_in(&self) -> Option<u64> {
        self.spending
            .map(|limit| limit.map_or(self.balance_ms, |l| l.min(self.balance_ms)) / 1000)
    }

    /// Uses `delta` of free time. Returns true when spending just ended.
    pub fn advance(&mut self, delta: Duration) -> bool {
        let Some(limit) = self.spending else {
            return false;
        };
        let d = delta.as_millis() as u64;
        self.balance_ms = self.balance_ms.saturating_sub(d);
        let limit = limit.map(|l| l.saturating_sub(d));
        if self.balance_ms == 0 || limit == Some(0) {
            self.spending = None;
            return true;
        }
        self.spending = Some(limit);
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg() -> InvertedConfig {
        InvertedConfig {
            enabled: true,
            profile: None,
            free_mins_per_hour: 12,
            max_bank_mins: 30,
        }
    }

    #[test]
    fn earning_and_cap() {
        let c = cfg();
        assert_eq!(
            earned(&c, Duration::from_secs(3600)),
            Duration::from_secs(720)
        );
        assert_eq!(
            earned(&c, Duration::from_secs(25 * 60)),
            Duration::from_secs(300)
        );
        let mut bank = Bank::default();
        let min = |m: u64| Duration::from_secs(m * 60);
        assert_eq!(bank.deposit(min(20), &c), min(20));
        assert_eq!(bank.deposit(min(20), &c), min(10));
        assert_eq!(bank.balance_secs(), 30 * 60);
        // A lower cap later does not take banked time away.
        let lower = InvertedConfig {
            max_bank_mins: 10,
            ..c
        };
        assert_eq!(bank.deposit(min(1), &lower), Duration::ZERO);
        assert_eq!(bank.balance_secs(), 30 * 60);
    }

    #[test]
    fn spending_until_empty_or_limit() {
        let mut bank = Bank {
            balance_ms: 30_000,
            spending: None,
        };
        assert!(bank.spend(None).is_err(), "less than a minute banked");
        bank.balance_ms = 300_000;
        assert!(bank.spend(Some(Duration::from_secs(10))).is_err());
        bank.spend(Some(Duration::from_secs(120))).unwrap();
        assert!(bank.spend(None).is_err(), "already running");
        assert_eq!(bank.stops_in(), Some(120));
        for _ in 0..119 {
            assert!(!bank.advance(Duration::from_secs(1)));
        }
        assert!(bank.advance(Duration::from_secs(1)));
        assert_eq!(bank.balance_secs(), 180);
        assert!(!bank.is_spending());

        bank.spend(None).unwrap();
        assert_eq!(bank.stops_in(), Some(180));
        assert!(!bank.advance(Duration::from_millis(1100)));
        assert_eq!(bank.balance_ms, 178_900);
        assert!(bank.stop());
        assert!(!bank.stop());
        assert!(!bank.advance(Duration::from_secs(5)), "not spending");
        assert_eq!(bank.balance_ms, 178_900);

        bank.spend(None).unwrap();
        assert!(bank.advance(Duration::from_secs(500)));
        assert_eq!(bank.balance_ms, 0);
    }

    #[test]
    fn round_trips_through_json() {
        let bank = Bank {
            balance_ms: 90_000,
            spending: Some(Some(60_000)),
        };
        let text = serde_json::to_string(&bank).unwrap();
        assert_eq!(serde_json::from_str::<Bank>(&text).unwrap(), bank);
    }
}
