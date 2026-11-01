//! Routine and nudge timing. Pure: callers pass the current local time, so
//! everything here is unit tested without a clock.
//!
//! Routines are the one place the daemon reads the wall clock. A clock change
//! can therefore move a routine, which the engine logs as a `clock_jump`.

use jiff::civil::Date;
use jiff::tz::TimeZone;
use jiff::{SignedDuration, Timestamp, ToSpan, Zoned};

use crate::config::{NudgeConfig, Routine, on_day};
use crate::session::MIN_COUNTDOWN;

/// One run of a routine: its window on a given local date.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Occurrence {
    pub routine: String,
    pub profile: Option<String>,
    /// Local date the run starts on. With the routine name, this identifies
    /// the run in the store.
    pub date: Date,
    pub start: Timestamp,
    pub end: Timestamp,
}

impl Occurrence {
    pub fn key(&self) -> RunKey {
        (self.routine.clone(), self.date.to_string())
    }
}

/// `(routine name, local date)`.
pub type RunKey = (String, String);

/// Runs whose window ends after `now` and that start within `horizon`, soonest
/// first. Yesterday is included so a window running past midnight is found.
pub fn occurrences(routines: &[Routine], now: &Zoned, horizon: SignedDuration) -> Vec<Occurrence> {
    let tz = now.time_zone();
    let now_ts = now.timestamp();
    let last = now_ts + horizon;
    let mut out = Vec::new();
    let Ok(mut date) = now.date().checked_sub(1.day()) else {
        return out;
    };
    let last_date = last.to_zoned(tz.clone()).date();
    while date <= last_date {
        for r in routines {
            if !on_day(&r.days, date.weekday()) {
                continue;
            }
            let Some(start) = local(date, r.start.0, tz) else {
                continue;
            };
            let end = start + SignedDuration::from_mins(i64::from(r.duration_mins));
            if end > now_ts && start <= last {
                out.push(Occurrence {
                    routine: r.name.clone(),
                    profile: r.profile.clone(),
                    date,
                    start,
                    end,
                });
            }
        }
        let Ok(next) = date.checked_add(1.day()) else {
            break;
        };
        date = next;
    }
    out.sort_by(|a, b| a.start.cmp(&b.start).then(a.routine.cmp(&b.routine)));
    out
}

/// A local time on `date`. In a DST gap this is the moment just after it.
fn local(date: Date, time: jiff::civil::Time, tz: &TimeZone) -> Option<Timestamp> {
    date.to_datetime(time)
        .to_zoned(tz.clone())
        .ok()
        .map(|z| z.timestamp())
}

/// The run that should be running now and is not done yet, with how long its
/// session gets: whatever is left of the window. A window with less than a
/// minute left is let go.
pub fn due(
    occs: &[Occurrence],
    now: Timestamp,
    done: impl Fn(&Occurrence) -> bool,
) -> Option<(&Occurrence, u64)> {
    occs.iter()
        .filter(|o| o.start <= now && now < o.end && !done(o))
        .map(|o| (o, o.end.duration_since(now).as_secs().max(0) as u64))
        .find(|(_, secs)| *secs >= MIN_COUNTDOWN.as_secs())
}

/// Monday 00:00 of the current week, local time.
pub fn week_start(now: &Zoned) -> Timestamp {
    let date = now.date();
    let back = i64::from(date.weekday().to_monday_zero_offset());
    date.checked_sub(back.days())
        .ok()
        .and_then(|d| d.to_zoned(now.time_zone().clone()).ok())
        .map_or(now.timestamp(), |z| z.timestamp())
}

/// How hard to push the user to start, given that no session is running.
/// `None` outside active hours, shortly before a routine, or when a session
/// ended recently.
pub fn nudge(
    cfg: &NudgeConfig,
    now: &Zoned,
    last_end: Option<Timestamp>,
    next_routine: Option<Timestamp>,
) -> Option<deepwork_proto::Nudge> {
    if !cfg.enabled || !on_day(&cfg.days, now.weekday()) {
        return None;
    }
    let tz = now.time_zone();
    let from = local(now.date(), cfg.from.0, tz)?;
    let until = local(now.date(), cfg.until.0, tz)?;
    let now_ts = now.timestamp();
    if now_ts < from || now_ts >= until {
        return None;
    }
    let after = SignedDuration::from_mins(i64::from(cfg.after_mins));
    if next_routine.is_some_and(|start| start.duration_since(now_ts) <= after) {
        return None;
    }
    let since = last_end.map_or(from, |end| end.max(from));
    let idle = now_ts.duration_since(since).as_secs().max(0) as u64;
    let after = after.as_secs() as u64;
    if idle < after {
        return None;
    }
    let repeat = u64::from(cfg.repeat_mins) * 60;
    Some(deepwork_proto::Nudge {
        level: 1 + ((idle - after) / repeat) as u32,
        idle_secs: idle,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{ClockTime, Day};
    use jiff::civil::{Time, Weekday, date};

    fn at(y: i16, m: i8, d: i8, h: i8, min: i8) -> Zoned {
        date(y, m, d)
            .at(h, min, 0, 0)
            .to_zoned(TimeZone::get("Asia/Kathmandu").unwrap())
            .unwrap()
    }

    fn routine(name: &str, days: &[Weekday], h: i8, m: i8, mins: u32) -> Routine {
        Routine {
            name: name.into(),
            days: days.iter().map(|d| Day(*d)).collect(),
            start: ClockTime(Time::new(h, m, 0, 0).unwrap()),
            duration_mins: mins,
            profile: None,
        }
    }

    const DAY: SignedDuration = SignedDuration::from_hours(24);

    #[test]
    fn lists_upcoming_runs() {
        // 2026-11-02 is a Monday. The first run is already in its window.
        let now = at(2026, 11, 2, 9, 30);
        let rs = [
            routine("morning", &[Weekday::Monday, Weekday::Tuesday], 9, 0, 90),
            routine("evening", &[], 20, 0, 60),
        ];
        let occs = occurrences(&rs, &now, DAY);
        let names: Vec<_> = occs
            .iter()
            .map(|o| (o.routine.as_str(), o.date.to_string()))
            .collect();
        assert_eq!(
            names,
            [
                ("morning", "2026-11-02".to_string()),
                ("evening", "2026-11-02".to_string()),
                ("morning", "2026-11-03".to_string()),
            ]
        );
        assert_eq!(occs[0].start, at(2026, 11, 2, 9, 0).timestamp());
        assert_eq!(occs[0].end, at(2026, 11, 2, 10, 30).timestamp());
    }

    #[test]
    fn window_across_midnight() {
        let rs = [routine("late", &[Weekday::Sunday], 23, 0, 120)];
        let now = at(2026, 11, 2, 0, 30);
        let occs = occurrences(&rs, &now, DAY);
        assert_eq!(occs.len(), 1);
        assert_eq!(occs[0].date.to_string(), "2026-11-01");
        let (o, secs) = due(&occs, now.timestamp(), |_| false).unwrap();
        assert_eq!(o.routine, "late");
        assert_eq!(secs, 30 * 60);
    }

    #[test]
    fn due_runs_for_what_is_left() {
        let rs = [routine("morning", &[], 9, 0, 90)];
        let now = at(2026, 11, 2, 8, 59);
        let occs = occurrences(&rs, &now, DAY);
        assert!(due(&occs, now.timestamp(), |_| false).is_none());

        let now = at(2026, 11, 2, 9, 30);
        let (_, secs) = due(&occs, now.timestamp(), |_| false).unwrap();
        assert_eq!(secs, 60 * 60);
        assert!(due(&occs, now.timestamp(), |_| true).is_none());

        // Less than a minute left: not worth a session.
        let now = at(2026, 11, 2, 10, 29) + SignedDuration::from_secs(30);
        assert!(due(&occs, now.timestamp(), |_| false).is_none());
    }

    #[test]
    fn dst_gap_moves_start_forward() {
        // US clocks jump from 02:00 to 03:00 on 2026-03-08.
        let tz = TimeZone::get("America/New_York").unwrap();
        let now = date(2026, 3, 8)
            .at(1, 0, 0, 0)
            .to_zoned(tz.clone())
            .unwrap();
        let occs = occurrences(&[routine("r", &[], 2, 30, 60)], &now, DAY);
        let start = occs[0].start.to_zoned(tz);
        assert_eq!(start.date(), date(2026, 3, 8));
        assert_eq!(start.hour(), 3);
    }

    #[test]
    fn week_starts_monday() {
        let ws = week_start(&at(2026, 11, 8, 23, 0)); // Sunday
        assert_eq!(ws, at(2026, 11, 2, 0, 0).timestamp());
        assert_eq!(week_start(&at(2026, 11, 2, 0, 0)), ws);
    }

    #[test]
    fn nudges_escalate() {
        let cfg = NudgeConfig::default(); // 09:00-21:00, after 30, repeat 15
        assert_eq!(nudge(&cfg, &at(2026, 11, 2, 8, 0), None, None), None);
        assert_eq!(nudge(&cfg, &at(2026, 11, 2, 9, 29), None, None), None);
        assert_eq!(
            nudge(&cfg, &at(2026, 11, 2, 9, 30), None, None)
                .unwrap()
                .level,
            1
        );
        assert_eq!(
            nudge(&cfg, &at(2026, 11, 2, 10, 0), None, None)
                .unwrap()
                .level,
            3
        );
        assert_eq!(nudge(&cfg, &at(2026, 11, 2, 21, 0), None, None), None);

        // Counted from the end of the last session.
        let end = at(2026, 11, 2, 12, 0).timestamp();
        assert_eq!(nudge(&cfg, &at(2026, 11, 2, 12, 20), Some(end), None), None);
        let n = nudge(&cfg, &at(2026, 11, 2, 12, 50), Some(end), None).unwrap();
        assert_eq!((n.level, n.idle_secs), (2, 50 * 60));

        // Quiet when a routine is about to start anyway.
        let soon = at(2026, 11, 2, 10, 20).timestamp();
        assert_eq!(nudge(&cfg, &at(2026, 11, 2, 10, 0), None, Some(soon)), None);

        let off = NudgeConfig {
            days: vec![Day(Weekday::Saturday)],
            ..NudgeConfig::default()
        };
        assert_eq!(nudge(&off, &at(2026, 11, 2, 12, 0), None, None), None);
    }
}
