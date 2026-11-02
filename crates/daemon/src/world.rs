//! The progression world, folded from the ledger. Pure: the same facts always
//! give the same world, so it is rebuilt on every request and never stored,
//! and no client can edit it.
//!
//! Penalty tiers, mildest first:
//! - minor (refused sudo / polkit, wall-clock jump): the newest building
//!   takes 1 damage;
//! - major (tampering with the nft table or tc): every building in the
//!   biggest district takes 1 damage;
//! - severe (surrender): the plot under construction collapses into rubble,
//!   fire hits the nearest buildings for 2 damage, the session's time does
//!   not count and the streak is lost.
//!
//! A building at [`World::MAX_DAMAGE`] falls into rubble. Completed sessions
//! build on the oldest rubble first, then repair damage; streaks double the
//! repairs.

use deepwork_proto::{Construction, Plot, World, WorldCause, WorldEvent, WorldEventKind};
use jiff::Timestamp;
use jiff::civil::Date;
use jiff::tz::TimeZone;

pub const DISTRICT_SIZE: u32 = 8;
/// Session minutes needed for grades 1 to 4.
const GRADE_MINS: [u64; 4] = [25, 50, 90, 180];
/// Focused hours needed for tiers 1 to 3.
const TIER_HOURS: [u64; 3] = [10, 50, 200];
/// A completed session repairs one damage level, plus one per this many minutes.
const REPAIR_MINS: u64 = 25;
/// Streak length from which repairs are doubled.
const STREAK_BONUS_DAYS: u32 = 3;
const FIRE_SPREAD: usize = 3;
const FIRE_DAMAGE: u32 = 2;
/// One burst of tamper (or minor) events counts once.
const PENALTY_COOLDOWN: i64 = 10 * 60;
const HISTORY: usize = 30;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum FactKind {
    Completed {
        secs: u64,
    },
    Surrendered {
        secs: u64,
    },
    Tamper,
    /// A refused privilege escalation.
    Denied,
    ClockJump,
    /// A proxy or tunnel around the throttle.
    Tunnel,
}

/// Ordered by time first, so sorting gives a fixed fold order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Fact {
    /// Unix seconds.
    pub ts: i64,
    pub session_id: Option<i64>,
    pub kind: FactKind,
}

/// The session that is running now.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Running {
    pub session_id: i64,
    pub elapsed_secs: u64,
    /// Countdown length; `None` for stopwatches.
    pub target_secs: Option<u64>,
    pub surrendering: bool,
}

pub fn grade(secs: u64) -> u32 {
    GRADE_MINS.iter().filter(|&&m| secs >= m * 60).count() as u32
}

/// Stable randomness for a plot, from the session that built it.
fn seed(session_id: i64) -> u64 {
    // splitmix64
    let mut z = (session_id as u64).wrapping_add(0x9e37_79b9_7f4a_7c15);
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    z ^ (z >> 31)
}

#[derive(Default)]
struct Fold {
    plots: Vec<Plot>,
    focused_secs: u64,
    streak: u32,
    last_day: Option<Date>,
    last_quake: Option<i64>,
    last_minor: Option<i64>,
    history: Vec<WorldEvent>,
}

impl Fold {
    /// Where the next building goes: the oldest rubble, or a new plot.
    fn next_index(&self) -> u32 {
        self.plots
            .iter()
            .find(|p| p.rubble)
            .map_or(self.plots.len() as u32, |p| p.index)
    }

    fn put(&mut self, session_id: i64, grade: u32, ts: i64, rubble: bool) -> u32 {
        let index = self.next_index();
        let plot = Plot {
            index,
            district: index / DISTRICT_SIZE,
            grade,
            damage: 0,
            rubble,
            seed: seed(session_id),
            session_id,
            built_at: ts,
        };
        match self.plots.get_mut(index as usize) {
            Some(p) => *p = plot,
            None => self.plots.push(plot),
        }
        index
    }

    fn standing(&self) -> impl Iterator<Item = &Plot> {
        self.plots.iter().filter(|p| !p.rubble)
    }

    /// Damages plots; returns those that fell into rubble.
    fn damage(&mut self, plots: &[u32], amount: u32) -> Vec<u32> {
        let mut ruined = Vec::new();
        for &i in plots {
            let p = &mut self.plots[i as usize];
            p.damage += amount;
            if p.damage >= World::MAX_DAMAGE {
                p.damage = 0;
                p.rubble = true;
                ruined.push(i);
            }
        }
        ruined
    }

    fn record(
        &mut self,
        ts: i64,
        (kind, cause): (WorldEventKind, WorldCause),
        session_id: Option<i64>,
        plots: Vec<u32>,
        ruined: Vec<u32>,
    ) {
        self.history.push(WorldEvent {
            ts,
            kind,
            cause,
            session_id,
            plots,
            ruined,
        });
    }

    fn completed(&mut self, ts: i64, session_id: i64, secs: u64, tz: &TimeZone) {
        self.focused_secs += secs;
        let day = Timestamp::from_second(ts)
            .unwrap_or_default()
            .to_zoned(tz.clone())
            .date();
        self.streak = match self.last_day {
            Some(d) if d == day => self.streak.max(1),
            Some(d) if d.tomorrow().ok() == Some(day) => self.streak + 1,
            _ => 1,
        };
        self.last_day = Some(day);
        let index = self.put(session_id, grade(secs), ts, false);
        self.record(
            ts,
            (WorldEventKind::Built, WorldCause::Completed),
            Some(session_id),
            vec![index],
            vec![],
        );

        let mut budget = 1 + secs / (REPAIR_MINS * 60);
        if self.streak >= STREAK_BONUS_DAYS {
            budget *= 2;
        }
        let mut repaired = Vec::new();
        for _ in 0..budget {
            let Some(p) = self
                .plots
                .iter_mut()
                .filter(|p| !p.rubble && p.damage > 0)
                .max_by_key(|p| (p.damage, std::cmp::Reverse(p.index)))
            else {
                break;
            };
            p.damage -= 1;
            if !repaired.contains(&p.index) {
                repaired.push(p.index);
            }
        }
        if !repaired.is_empty() {
            repaired.sort_unstable();
            self.record(
                ts,
                (WorldEventKind::Repaired, WorldCause::Completed),
                Some(session_id),
                repaired,
                vec![],
            );
        }
    }

    fn surrendered(&mut self, ts: i64, session_id: i64, secs: u64) {
        self.streak = 0;
        self.last_day = None;
        let origin = self.put(session_id, grade(secs), ts, true);
        let mut near: Vec<&Plot> = self.standing().collect();
        near.sort_by_key(|p| (p.index.abs_diff(origin), p.index));
        let mut hit: Vec<u32> = near.iter().take(FIRE_SPREAD).map(|p| p.index).collect();
        hit.sort_unstable();
        let ruined = self.damage(&hit, FIRE_DAMAGE);
        let mut plots = vec![origin];
        plots.extend(hit);
        self.record(
            ts,
            (WorldEventKind::Collapsed, WorldCause::Surrendered),
            Some(session_id),
            plots,
            ruined,
        );
    }

    fn quake(&mut self, ts: i64, session_id: Option<i64>) {
        if self.last_quake.is_some_and(|t| ts - t < PENALTY_COOLDOWN) {
            return;
        }
        self.last_quake = Some(ts);
        let mut counts = std::collections::BTreeMap::<u32, usize>::new();
        for p in self.standing() {
            *counts.entry(p.district).or_default() += 1;
        }
        // The biggest district; the newest one on a tie.
        let district = counts
            .iter()
            .max_by_key(|&(d, n)| (*n, *d))
            .map(|(d, _)| *d);
        let hit: Vec<u32> = self
            .standing()
            .filter(|p| Some(p.district) == district)
            .map(|p| p.index)
            .collect();
        let ruined = self.damage(&hit, 1);
        self.record(
            ts,
            (WorldEventKind::Quake, WorldCause::Tamper),
            session_id,
            hit,
            ruined,
        );
    }

    fn minor(&mut self, ts: i64, session_id: Option<i64>, cause: WorldCause) {
        if self.last_minor.is_some_and(|t| ts - t < PENALTY_COOLDOWN) {
            return;
        }
        self.last_minor = Some(ts);
        let hit: Vec<u32> = self
            .standing()
            .max_by_key(|p| (p.built_at, p.index))
            .map(|p| p.index)
            .into_iter()
            .collect();
        let ruined = self.damage(&hit, 1);
        self.record(
            ts,
            (WorldEventKind::Damaged, cause),
            session_id,
            hit,
            ruined,
        );
    }
}

/// Folds `facts` (in any order) into the world as of `now`.
pub fn build(facts: &[Fact], running: Option<&Running>, now: Timestamp, tz: &TimeZone) -> World {
    let mut facts = facts.to_vec();
    facts.sort_unstable();
    let mut w = Fold::default();
    for f in &facts {
        match (f.kind, f.session_id) {
            (FactKind::Completed { secs }, Some(id)) => w.completed(f.ts, id, secs, tz),
            (FactKind::Surrendered { secs }, Some(id)) => w.surrendered(f.ts, id, secs),
            (FactKind::Completed { .. } | FactKind::Surrendered { .. }, None) => {}
            (FactKind::Tamper, id) => w.quake(f.ts, id),
            (FactKind::Denied, id) => w.minor(f.ts, id, WorldCause::EscalationDenied),
            (FactKind::ClockJump, id) => w.minor(f.ts, id, WorldCause::ClockJump),
            (FactKind::Tunnel, id) => w.minor(f.ts, id, WorldCause::Tunnel),
        }
    }

    let today = now.to_zoned(tz.clone()).date();
    let streak_days = match w.last_day {
        Some(d) if d == today || d.tomorrow().ok() == Some(today) => w.streak,
        _ => 0,
    };
    let hours = w.focused_secs / 3600;
    let tier = TIER_HOURS.iter().filter(|&&h| hours >= h).count();
    let construction = running.map(|r| Construction {
        session_id: r.session_id,
        index: w.next_index(),
        grade: grade(r.target_secs.unwrap_or(r.elapsed_secs)),
        progress_permille: r
            .target_secs
            .filter(|&t| t > 0)
            .map(|t| (r.elapsed_secs.min(t) * 1000 / t) as u32),
        surrendering: r.surrendering,
        seed: seed(r.session_id),
    });
    let skip = w.history.len().saturating_sub(HISTORY);
    World {
        tier: tier as u32,
        focused_secs: w.focused_secs,
        tier_floor_secs: tier.checked_sub(1).map_or(0, |i| TIER_HOURS[i] * 3600),
        next_tier_secs: TIER_HOURS.get(tier).map(|h| h * 3600),
        streak_days,
        plots: w.plots,
        construction,
        history: w.history.split_off(skip),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DAY: i64 = 86_400;
    const MIN: u64 = 60;

    fn done(ts: i64, id: i64, mins: u64) -> Fact {
        Fact {
            ts,
            session_id: Some(id),
            kind: FactKind::Completed { secs: mins * MIN },
        }
    }

    fn gave_up(ts: i64, id: i64, mins: u64) -> Fact {
        Fact {
            ts,
            session_id: Some(id),
            kind: FactKind::Surrendered { secs: mins * MIN },
        }
    }

    fn event(ts: i64, kind: FactKind) -> Fact {
        Fact {
            ts,
            session_id: Some(99),
            kind,
        }
    }

    fn world(facts: &[Fact], now: i64) -> World {
        build(
            facts,
            None,
            Timestamp::from_second(now).unwrap(),
            &TimeZone::UTC,
        )
    }

    fn damage(w: &World) -> Vec<(u32, bool)> {
        w.plots.iter().map(|p| (p.damage, p.rubble)).collect()
    }

    #[test]
    fn grades_follow_length() {
        assert_eq!(grade(5 * MIN), 0);
        assert_eq!(grade(25 * MIN), 1);
        assert_eq!(grade(89 * MIN), 2);
        assert_eq!(grade(90 * MIN), 3);
        assert_eq!(grade(6 * 3600), 4);
    }

    #[test]
    fn empty_world() {
        let w = world(&[], 0);
        assert_eq!((w.tier, w.focused_secs, w.streak_days), (0, 0, 0));
        assert_eq!(w.next_tier_secs, Some(10 * 3600));
        assert!(w.plots.is_empty());
    }

    #[test]
    fn completed_sessions_build_and_count() {
        let w = world(&[done(100, 1, 25), done(200, 2, 50)], 300);
        assert_eq!(w.plots.len(), 2);
        assert_eq!((w.plots[1].grade, w.plots[1].session_id), (2, 2));
        assert_eq!(w.focused_secs, 75 * MIN);
        assert_eq!(w.streak_days, 1);
        assert_eq!(w.history.len(), 2);
    }

    #[test]
    fn tiers() {
        let facts: Vec<Fact> = (0..20).map(|i| done(i * 10, i, 30)).collect();
        let w = world(&facts, 300);
        assert_eq!(w.tier, 1);
        assert_eq!(w.tier_floor_secs, 10 * 3600);
        assert_eq!(w.next_tier_secs, Some(50 * 3600));
    }

    #[test]
    fn streaks_count_days_and_break() {
        let facts = [
            done(DAY, 1, 25),
            done(2 * DAY, 2, 25),
            done(2 * DAY + 60, 3, 25),
        ];
        assert_eq!(world(&facts, 2 * DAY + 100).streak_days, 2);
        // Still alive the next day, gone the day after.
        assert_eq!(world(&facts, 3 * DAY + 100).streak_days, 2);
        assert_eq!(world(&facts, 4 * DAY + 100).streak_days, 0);
        let mut facts = facts.to_vec();
        facts.push(gave_up(2 * DAY + 200, 4, 10));
        assert_eq!(world(&facts, 2 * DAY + 300).streak_days, 0);
    }

    #[test]
    fn surrender_collapses_and_burns_neighbours() {
        let mut facts: Vec<Fact> = (1..=5).map(|i| done(i * 10, i, 10)).collect();
        facts.push(gave_up(100, 6, 40));
        let w = world(&facts, 200);
        assert_eq!(w.focused_secs, 50 * MIN, "surrendered time does not count");
        assert_eq!(
            damage(&w),
            [
                (0, false),
                (0, false),
                (2, false),
                (2, false),
                (2, false),
                (0, true)
            ]
        );
        let last = w.history.last().unwrap();
        assert_eq!(last.kind, WorldEventKind::Collapsed);
        assert_eq!(last.plots, [5, 2, 3, 4]);

        // A second surrender lands on the same rubble and ruins what is
        // still burning.
        facts.push(gave_up(200, 7, 5));
        let w = world(&facts, 300);
        assert_eq!(w.plots.len(), 6);
        assert_eq!(w.history.last().unwrap().ruined, [2, 3, 4]);
    }

    #[test]
    fn completed_session_builds_on_rubble_then_repairs() {
        let mut facts: Vec<Fact> = (1..=3).map(|i| done(i * 10, i, 10)).collect();
        facts.push(gave_up(100, 4, 10));
        assert_eq!(world(&facts, 200).plots.len(), 4);
        // 50 min: builds on the rubble (plot 3) and repairs 3 levels.
        facts.push(done(300, 5, 50));
        let w = world(&facts, 400);
        assert_eq!(w.plots.len(), 4);
        assert_eq!((w.plots[3].session_id, w.plots[3].rubble), (5, false));
        assert_eq!(damage(&w), [(1, false), (1, false), (1, false), (0, false)]);
        let last = w.history.last().unwrap();
        assert_eq!(
            (last.kind, last.plots.clone()),
            (WorldEventKind::Repaired, vec![0, 1, 2])
        );
    }

    #[test]
    fn streak_doubles_repairs() {
        let mut facts = vec![
            done(DAY, 1, 10),
            done(2 * DAY, 2, 10),
            gave_up(2 * DAY + 10, 3, 10),
            done(2 * DAY + 20, 4, 10),
        ];
        // The surrender reset the streak, so 1 repair.
        let w = world(&facts, 2 * DAY + 30);
        assert_eq!(w.plots.iter().map(|p| p.damage).sum::<u32>(), 3);
        facts.extend([done(3 * DAY, 5, 10), done(4 * DAY, 6, 10)]);
        // Day 4 has a 3-day streak: 2 repairs instead of 1.
        let w = world(&facts, 4 * DAY + 10);
        assert_eq!(w.streak_days, 3);
        assert_eq!(w.plots.iter().map(|p| p.damage).sum::<u32>(), 0);
    }

    #[test]
    fn quake_hits_the_biggest_district_once_per_burst() {
        let mut facts: Vec<Fact> = (0..10).map(|i| done(i * 10, i, 10)).collect();
        facts.extend([
            event(200, FactKind::Tamper),
            event(201, FactKind::Tamper),
            event(300, FactKind::Tamper),
        ]);
        let w = world(&facts, 400);
        let hit: Vec<u32> = w.plots.iter().map(|p| p.damage).collect();
        assert_eq!(hit, [1, 1, 1, 1, 1, 1, 1, 1, 0, 0]);
        assert_eq!(w.history.last().unwrap().kind, WorldEventKind::Quake);

        facts.push(event(200 + PENALTY_COOLDOWN, FactKind::Tamper));
        let w = world(&facts, 2000);
        assert_eq!(w.plots[0].damage, 2);
    }

    #[test]
    fn minor_penalties_hit_the_newest_building() {
        let facts = [
            done(10, 1, 10),
            done(20, 2, 10),
            event(30, FactKind::Denied),
            event(31, FactKind::Denied),
            event(40 + PENALTY_COOLDOWN, FactKind::ClockJump),
            event(50 + 2 * PENALTY_COOLDOWN, FactKind::Denied),
        ];
        let w = world(&facts, 5000);
        assert_eq!(damage(&w), [(0, false), (0, true)]);
        assert_eq!(w.history.last().unwrap().ruined, [1]);
    }

    #[test]
    fn a_tunnel_damages_like_a_minor_penalty() {
        let facts = [done(10, 1, 10), event(30, FactKind::Tunnel)];
        let w = world(&facts, 100);
        assert_eq!(w.plots[0].damage, 1);
        let last = w.history.last().unwrap();
        assert_eq!(
            (last.kind, last.cause),
            (WorldEventKind::Damaged, WorldCause::Tunnel)
        );
    }

    #[test]
    fn penalties_on_an_empty_world_are_harmless() {
        let w = world(
            &[event(1, FactKind::Tamper), event(2, FactKind::Denied)],
            10,
        );
        assert!(w.plots.is_empty());
        assert_eq!(w.history.len(), 2);
    }

    #[test]
    fn construction() {
        let running = Running {
            session_id: 7,
            elapsed_secs: 15 * MIN,
            target_secs: Some(60 * MIN),
            surrendering: false,
        };
        let w = build(
            &[done(10, 1, 10)],
            Some(&running),
            Timestamp::from_second(100).unwrap(),
            &TimeZone::UTC,
        );
        let c = w.construction.unwrap();
        assert_eq!((c.index, c.grade, c.progress_permille), (1, 2, Some(250)));

        let stopwatch = Running {
            target_secs: None,
            ..running
        };
        let w = build(&[], Some(&stopwatch), Timestamp::UNIX_EPOCH, &TimeZone::UTC);
        let c = w.construction.unwrap();
        assert_eq!((c.index, c.grade, c.progress_permille), (0, 0, None));
    }

    #[test]
    fn same_facts_same_world_in_any_order() {
        let facts = [
            done(10, 1, 30),
            event(20, FactKind::Tamper),
            event(20, FactKind::Denied),
            gave_up(30, 2, 5),
        ];
        let mut reversed = facts;
        reversed.reverse();
        assert_eq!(world(&facts, 100), world(&reversed, 100));
    }
}
