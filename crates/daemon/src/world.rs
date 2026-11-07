//! The progression world, folded from the ledger (`docs/GAME.md`).
//! Pure: the same facts always give the same world, so it is rebuilt on every
//! request and never stored, and no client can edit it.
//!
//! Focused time of completed sessions pays twice: coins (with bonuses) that
//! buy blueprints, and build time (at face value) that goes into the active
//! construction site. The mayor picks a residents' need; the fold takes that
//! need's next lot of the plan (`plan.rs`), so the city always ends up laid
//! out as planned. Until the mayor first chooses anything, the plan builds
//! itself in its default order, so old ledgers convert by themselves.
//!
//! Penalty tiers, mildest first:
//! - minor (refused sudo / polkit, wall-clock jump, tunnel): the newest
//!   building takes 1 damage;
//! - major (tampering with the nft table or tc): every building in the
//!   biggest district takes 1 damage;
//! - severe (surrender): the session earns nothing and builds nothing, fire
//!   hits the 3 buildings nearest the site for 2 damage, and the streak is
//!   lost.
//!
//! A building at [`World::MAX_DAMAGE`] is a ruin, and stays one (on its lot)
//! until repairs bring it back. Every completed session repairs damage, most
//! damaged first; streaks double the repairs.

use std::collections::{BTreeMap, BTreeSet, VecDeque};

use deepwork_proto::{
    Award, BlockInfo, BlueprintInfo, BoxInfo, BuildPart, Construction, DecorationInfo, GoalInfo,
    ItemInfo, Layout, LotInfo, Memory, NeedInfo, Plot, Scar, SiteInfo, SpotInfo, StreetInfo, World,
    WorldCause, WorldEvent, WorldEventKind,
};
use jiff::Timestamp;
use jiff::civil::Date;
use jiff::tz::TimeZone;

use crate::economy::{self, Goal, Item};
use crate::layout::{self, Axis, Ground, STREETS};
use crate::plan::{self, BLUEPRINTS, Blueprint, NEEDS, Need};
const COINS_PER_HOUR: u64 = 100;
/// Coin rate per minute of a session, in tenths, by how far into the session
/// the minute is: depth pays, but a stopwatch left running does not.
const LENGTH_BANDS: [(u64, u64, u64); 4] = [
    (0, 50, 10),
    (50, 90, 15),
    (90, 180, 20),
    (180, u64::MAX, 10),
];
/// A session this long or longer makes a streak day.
const STREAK_MIN_SECS: u64 = 25 * 60;
/// Coins get this many percent per streak day from the third, up to the cap.
const STREAK_PCT_PER_DAY: u64 = 10;
const STREAK_PCT_MAX: u64 = 50;
/// A streak freeze is earned every this many streak days.
const FREEZE_EVERY: u32 = 7;
const MAX_FREEZES: u32 = 2;
/// A completed session repairs one damage level, plus one per this many minutes.
const REPAIR_MINS: u64 = 25;
/// Streak length from which repairs are doubled.
const STREAK_BONUS_DAYS: u32 = 3;
const FIRE_SPREAD: usize = 3;
const FIRE_DAMAGE: u32 = 2;
/// One burst of tamper (or minor) events counts once.
const PENALTY_COOLDOWN: i64 = 10 * 60;
const HISTORY: usize = 30;
/// Chance in a thousand that a finished building comes out shiny, and the
/// most longer sessions can raise it to.
const SHINY_BASE: u64 = 50;
const SHINY_MAX: u64 = 250;
pub const NAME_MAX: usize = 40;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
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
    /// The mayor's decisions.
    Bought {
        blueprint: String,
    },
    Chose {
        need: String,
        blueprint: Option<String>,
    },
    Paused,
    Renamed {
        lot: String,
        name: String,
    },
    LandBought {
        lot: String,
    },
    RepairBought {
        lot: String,
    },
    StreetUpgraded {
        street: String,
    },
    Decorated {
        spot: String,
        decoration: String,
    },
    /// Coins bet on the fact's session finishing.
    Staked {
        coins: u64,
    },
    ItemUsed {
        item: String,
        lot: Option<String>,
    },
}

/// Ordered by time first, so sorting gives a fixed fold order.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Fact {
    /// Unix seconds.
    pub ts: i64,
    /// Ledger order within a second: the event's row id, 0 for sessions.
    pub seq: i64,
    pub session_id: Option<i64>,
    pub kind: FactKind,
}

/// The session that is running now.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Running {
    pub session_id: i64,
    pub elapsed_secs: u64,
    pub surrendering: bool,
}

/// splitmix64: stable randomness from a number.
fn mix(x: u64) -> u64 {
    let mut z = x.wrapping_add(0x9e37_79b9_7f4a_7c15);
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    z ^ (z >> 31)
}

/// Stable randomness for a lot built from a design.
fn lot_seed(index: usize, design: Option<&str>) -> u64 {
    let d = design
        .unwrap_or("")
        .bytes()
        .fold(0u64, |h, b| h.wrapping_mul(31).wrapping_add(u64::from(b)));
    mix((index as u64) << 32 ^ d)
}

/// What a completed session earns, before any comeback bonus:
/// `(coins, length bonus, streak bonus)`.
pub fn coins(secs: u64, streak: u32) -> (u64, u64, u64) {
    let mins = secs / 60;
    let units: u64 = LENGTH_BANDS
        .iter()
        .map(|&(from, to, rate)| mins.clamp(from, to).saturating_sub(from) * rate)
        .sum();
    // Units are tenths of a minute at 1x: this many make a coin.
    let per = 600 / COINS_PER_HOUR;
    let base = mins * 10 / per;
    let with_length = units / per;
    let pct = if streak >= 3 {
        (u64::from(streak - 2) * STREAK_PCT_PER_DAY).min(STREAK_PCT_MAX)
    } else {
        0
    };
    let total = with_length * (100 + pct) / 100;
    (total, with_length - base, total - with_length)
}

fn shiny_odds(session_secs: u64) -> u64 {
    let mins = session_secs / 60;
    (SHINY_BASE + mins.saturating_sub(50) * 50 / 30).min(SHINY_MAX)
}

#[derive(Debug, Clone, Default)]
struct LotState {
    /// A site stands (or stood) here.
    site: bool,
    design: Option<&'static str>,
    done_secs: u64,
    /// When, and by which session, it was finished.
    finished: Option<(i64, i64)>,
    damage: u32,
    /// The mayor's name for it.
    name: Option<String>,
    /// The name dealt from the piles when its design was set.
    dealt: Option<String>,
    shiny: bool,
    memory: Memory,
}

/// The world as the fold goes. Also answers whether a decision is allowed,
/// so the daemon refuses exactly what the fold would ignore.
#[derive(Debug, Clone)]
pub struct City {
    lots: Vec<LotState>,
    active: Option<usize>,
    /// Focus waiting for a site, oldest first.
    idle: Vec<BuildPart>,
    owned: BTreeSet<&'static str>,
    /// The mayor has decided something; until then the plan builds itself.
    manual: bool,
    level: u32,
    coins_earned: u64,
    coins_spent: u64,
    focused_secs: u64,
    streak: u32,
    /// The last streak day, and the last day with any completed session.
    last_day: Option<Date>,
    last_completed_day: Option<Date>,
    freezes: u32,
    last_quake: Option<i64>,
    last_minor: Option<i64>,
    finished_count: u32,
    history: Vec<WorldEvent>,
    award: Option<Award>,
    /// Land bought, by lot. The first plot comes free.
    land: Vec<bool>,
    /// Road class by street (`STREETS`).
    roads: Vec<u32>,
    /// Decorations by park spot.
    spots: BTreeMap<String, &'static str>,
    /// The balance at the start of `wealth_day`, which prices rise with.
    wealth: u64,
    wealth_day: Option<Date>,
    /// Lengths of the last completed sessions, oldest first.
    recent: VecDeque<u64>,
    /// Coins at stake, by session.
    stakes: BTreeMap<i64, u64>,
    today: Today,
    inventory: BTreeMap<Item, u32>,
    /// Boxes opened since the last rare item.
    since_rare: u32,
}

/// Progress on the day's goals.
#[derive(Debug, Clone, Default)]
struct Today {
    day: Option<Date>,
    focus: u64,
    sessions: u64,
    longest: u64,
    paid: BTreeSet<Goal>,
}

impl Today {
    fn progress(&self, goal: Goal) -> u64 {
        match goal {
            Goal::DailyFocus => self.focus,
            Goal::LongStretch => self.longest,
            Goal::Sessions => self.sessions,
        }
    }
}

impl Default for City {
    fn default() -> Self {
        Self {
            lots: vec![LotState::default(); plan::lots().len()],
            active: None,
            idle: Vec::new(),
            owned: BTreeSet::from([plan::STARTER]),
            manual: false,
            level: 0,
            coins_earned: 0,
            coins_spent: 0,
            focused_secs: 0,
            streak: 0,
            last_day: None,
            last_completed_day: None,
            freezes: 0,
            last_quake: None,
            last_minor: None,
            finished_count: 0,
            history: Vec::new(),
            award: None,
            land: {
                let mut land = vec![false; plan::lots().len()];
                land[0] = true;
                land
            },
            roads: vec![0; STREETS.len()],
            spots: BTreeMap::new(),
            wealth: 0,
            wealth_day: None,
            recent: VecDeque::new(),
            stakes: BTreeMap::new(),
            today: Today::default(),
            inventory: BTreeMap::new(),
            since_rare: 0,
        }
    }
}

fn day_of(ts: i64, tz: &TimeZone) -> Date {
    Timestamp::from_second(ts)
        .unwrap_or_default()
        .to_zoned(tz.clone())
        .date()
}

fn days_between(a: Date, b: Date) -> i64 {
    a.until(b).map_or(0, |s| i64::from(s.get_days()))
}

fn need_of(lot: usize) -> &'static Need {
    &NEEDS[plan::lots()[lot].need]
}

/// Where a lot stands on the ground, in lot widths, roads included.
fn ground_pos(lot: usize) -> (i32, i32) {
    let p = plan::lots()[lot].place;
    let b = layout::blocks()[p.block];
    (b.x * 5 + (p.slot % 4) as i32, b.y * 3 + (p.slot / 4) as i32)
}

impl City {
    /// Folds `facts` (in any order).
    pub fn fold(facts: &[Fact], tz: &TimeZone) -> Self {
        Self::fold_from(City::default(), facts, tz)
    }

    fn fold_from(mut c: City, facts: &[Fact], tz: &TimeZone) -> Self {
        let mut facts = facts.to_vec();
        facts.sort_unstable();
        for f in &facts {
            c.apply(f, tz);
        }
        c
    }

    /// A city whose land is all bought, for tests of everything else.
    #[cfg(test)]
    fn fold_landed(facts: &[Fact], tz: &TimeZone) -> Self {
        let mut c = City::default();
        c.land.fill(true);
        Self::fold_from(c, facts, tz)
    }

    /// Folds `facts`, with prices as of `now`.
    pub fn fold_at(facts: &[Fact], now: i64, tz: &TimeZone) -> Self {
        let mut c = Self::fold(facts, tz);
        c.roll_day(now, tz);
        c
    }

    /// On a new local day, prices start from the balance as it stands.
    fn roll_day(&mut self, ts: i64, tz: &TimeZone) {
        let day = day_of(ts, tz);
        if self.wealth_day != Some(day) {
            self.wealth = self.balance();
            self.wealth_day = Some(day);
        }
    }

    /// A list price as it stands today.
    fn cost(&self, list: u64) -> u64 {
        economy::price(list, self.wealth)
    }

    fn apply(&mut self, f: &Fact, tz: &TimeZone) {
        self.roll_day(f.ts, tz);
        match (&f.kind, f.session_id) {
            (FactKind::Completed { secs }, Some(id)) => self.completed(f.ts, id, *secs, tz),
            (FactKind::Surrendered { .. }, Some(id)) => self.surrendered(f.ts, id),
            (FactKind::Completed { .. } | FactKind::Surrendered { .. }, None) => {}
            (FactKind::Tamper, id) => self.quake(f.ts, id),
            (FactKind::Denied, id) => self.minor(f.ts, id, WorldCause::EscalationDenied),
            (FactKind::ClockJump, id) => self.minor(f.ts, id, WorldCause::ClockJump),
            (FactKind::Tunnel, id) => self.minor(f.ts, id, WorldCause::Tunnel),
            (FactKind::Bought { blueprint }, _) => {
                if let Ok(b) = self.check_buy(blueprint) {
                    self.manual = true;
                    self.owned.insert(b.id);
                    self.coins_spent += self.cost(b.price);
                }
            }
            (FactKind::Chose { need, blueprint }, _) => {
                if let Ok((ni, design)) = self.check_choose(need, blueprint.as_deref()) {
                    self.manual = true;
                    self.choose(f.ts, ni, design);
                }
            }
            (FactKind::Paused, _) => {
                if self.check_pause().is_ok() {
                    self.manual = true;
                    self.active = None;
                }
            }
            (FactKind::Renamed { lot, name }, _) => {
                if let Ok((i, name)) = self.check_rename(lot, name) {
                    self.lots[i].name = name;
                }
            }
            (FactKind::LandBought { lot }, _) => {
                if let Ok((i, price)) = self.check_land(lot) {
                    self.land[i] = true;
                    self.coins_spent += price;
                    // While the plan builds itself, waiting focus goes in now.
                    if !self.manual && self.active.is_none() {
                        for part in std::mem::take(&mut self.idle) {
                            self.pour(part, f.ts);
                        }
                    }
                }
            }
            (FactKind::RepairBought { lot }, _) => {
                if let Ok((i, price)) = self.check_repair(lot) {
                    self.coins_spent += price;
                    self.fix(i, f.ts);
                }
            }
            (FactKind::StreetUpgraded { street }, _) => {
                if let Ok((si, price)) = self.check_upgrade(street) {
                    self.coins_spent += price;
                    self.roads[si] += 1;
                }
            }
            (FactKind::Decorated { spot, decoration }, _) => {
                if let Ok((d, price)) = self.check_decorate(spot, decoration) {
                    self.coins_spent += price;
                    self.spots.insert(spot.clone(), d.id);
                }
            }
            (FactKind::Staked { coins }, Some(id)) => {
                if *coins > 0 && *coins <= self.stake_max() {
                    self.coins_spent += coins;
                    self.stakes.insert(id, *coins);
                }
            }
            (FactKind::Staked { .. }, None) => {}
            (FactKind::ItemUsed { item, lot }, _) => {
                if let Ok((item, i)) = self.check_use(item, lot.as_deref()) {
                    self.use_item(item, i, f.ts);
                }
            }
        }
    }

    pub fn check_land(&self, id: &str) -> Result<(usize, u64), String> {
        let lot = plan::lot_by_id(id).ok_or_else(|| format!("no lot {id:?}"))?;
        let i = lot.index as usize;
        if self.land[i] {
            return Err(format!("the plot at {} is already yours", lot.address));
        }
        let need = need_of(i);
        if need.level > self.level {
            return Err(format!(
                "the plot at {} is for sale from the {}",
                lot.address,
                plan::LEVELS[need.level as usize].to_lowercase()
            ));
        }
        let price = self.land_cost(i);
        self.afford(&format!("the plot at {}", lot.address), price)?;
        Ok((i, price))
    }

    fn land_cost(&self, i: usize) -> u64 {
        let need = need_of(i);
        self.cost(economy::land_price(need.district, need.level))
    }

    fn afford(&self, what: &str, price: u64) -> Result<(), String> {
        if self.balance() < price {
            return Err(format!(
                "{what} costs {price} coins; you have {}",
                self.balance()
            ));
        }
        Ok(())
    }

    pub fn check_repair(&self, id: &str) -> Result<(usize, u64), String> {
        let i = self.damaged(id)?;
        let price = self.repair_cost(i);
        self.afford(&format!("repairing {}", self.name(i)), price)?;
        Ok((i, price))
    }

    fn damaged(&self, id: &str) -> Result<usize, String> {
        let lot = plan::lot_by_id(id).ok_or_else(|| format!("no lot {id:?}"))?;
        let i = lot.index as usize;
        if !self.finished(i) {
            return Err(format!("{} is not built yet", self.name(i)));
        }
        if self.lots[i].damage == 0 {
            return Err(format!("{} needs no repair", self.name(i)));
        }
        Ok(i)
    }

    fn repair_cost(&self, i: usize) -> u64 {
        self.cost(economy::REPAIR_PER_DAMAGE * u64::from(self.lots[i].damage))
    }

    /// Repairs a building fully, by the mayor's hand.
    fn fix(&mut self, i: usize, ts: i64) {
        let lot = &mut self.lots[i];
        lot.damage = 0;
        lot.memory.scars.push(Scar {
            ts,
            cause: WorldCause::Mayor,
            damage: 0,
            repaired: true,
        });
        self.record(
            ts,
            (WorldEventKind::Repaired, WorldCause::Mayor),
            None,
            vec![i as u32],
            vec![],
        );
    }

    /// Whether a block is part of the town: land in it bought, or an open park.
    fn block_open(&self, b: usize) -> bool {
        match layout::blocks()[b].ground {
            Ground::Lots(_) => plan::lots()
                .iter()
                .any(|l| l.place.block == b && self.land[l.index as usize]),
            Ground::Park(..) => layout::blocks()[b].level <= self.level,
        }
    }

    /// The street's next class: its list price and the level it needs.
    pub fn check_upgrade(&self, id: &str) -> Result<(usize, u64), String> {
        let si = STREETS
            .iter()
            .position(|s| s.id == id)
            .ok_or_else(|| format!("no street {id:?}"))?;
        let street = &STREETS[si];
        let next = self.roads[si] + 1;
        let (list, level) = economy::road_upgrade(next)
            .ok_or_else(|| format!("{} is already an avenue", street.name))?;
        if level > self.level {
            return Err(format!(
                "{} can become a {} from the {}",
                street.name,
                economy::ROAD_CLASSES[next as usize],
                plan::LEVELS[level as usize].to_lowercase()
            ));
        }
        let borders = layout::blocks().iter().enumerate().any(|(b, block)| {
            let (line, along) = match street.axis {
                Axis::EastWest => ([block.y, block.y + 1], block.x),
                Axis::NorthSouth => ([block.x, block.x + 1], block.y),
            };
            line.contains(&street.line)
                && (street.from..=street.to).contains(&along)
                && self.block_open(b)
        });
        if !borders {
            return Err(format!("nobody lives on {} yet", street.name));
        }
        let price = self.cost(list);
        self.afford(
            &format!(
                "making {} a {}",
                street.name,
                economy::ROAD_CLASSES[next as usize]
            ),
            price,
        )?;
        Ok((si, price))
    }

    /// A spot is `<block>:<n>`: the park block's index and the spot on it.
    pub fn check_decorate(
        &self,
        spot: &str,
        id: &str,
    ) -> Result<(&'static economy::Decoration, u64), String> {
        let (b, _) = spot
            .split_once(':')
            .and_then(|(b, n)| Some((b.parse::<usize>().ok()?, n.parse::<u32>().ok()?)))
            .filter(|&(b, n)| b < layout::blocks().len() && n < economy::PARK_SPOTS)
            .ok_or_else(|| format!("no spot {spot:?}"))?;
        let Ground::Park(_, name) = layout::blocks()[b].ground else {
            return Err(format!("no spot {spot:?}"));
        };
        if !self.block_open(b) {
            return Err(format!("{name} is not laid out yet"));
        }
        let d = economy::decoration(id).ok_or_else(|| format!("no decoration {id:?}"))?;
        if d.level > self.level {
            return Err(format!(
                "a {} is for sale from the {}",
                d.name.to_lowercase(),
                plan::LEVELS[d.level as usize].to_lowercase()
            ));
        }
        if self.spots.get(spot) == Some(&d.id) {
            return Err(format!("that spot already has a {}", d.name.to_lowercase()));
        }
        let price = self.cost(d.price);
        self.afford(&format!("a {}", d.name.to_lowercase()), price)?;
        Ok((d, price))
    }

    /// The most a session can have at stake now.
    fn stake_max(&self) -> u64 {
        economy::STAKE_MAX.min(self.balance())
    }

    /// The length a staked countdown must reach.
    pub fn stake_target(&self) -> u64 {
        let recent: Vec<u64> = self.recent.iter().copied().collect();
        economy::stake_target(&recent)
    }

    /// Whether a session of `countdown_secs` (`None`: a stopwatch) may take
    /// a stake of `coins`.
    pub fn check_stake(&self, coins: u64, countdown_secs: Option<u64>) -> Result<(), String> {
        let target = self.stake_target();
        match countdown_secs {
            Some(secs) if secs >= target => {}
            _ => {
                return Err(format!(
                    "a stake needs a countdown of at least {} minutes, your usual length",
                    target.div_ceil(60)
                ));
            }
        }
        if coins == 0 {
            return Err("stake at least one coin".into());
        }
        if coins > self.stake_max() {
            return Err(format!(
                "the most you can stake now is {} coins",
                self.stake_max()
            ));
        }
        Ok(())
    }

    pub fn check_use(&self, id: &str, lot: Option<&str>) -> Result<(Item, usize), String> {
        let item = Item::parse(id).ok_or_else(|| format!("no item {id:?}"))?;
        if self.inventory.get(&item).copied().unwrap_or(0) == 0 {
            return Err(format!("you have no {}", item.name().to_lowercase()));
        }
        let i = match item {
            Item::RepairKit => self.damaged(lot.ok_or("say which building to repair")?)?,
            Item::HiredHelp | Item::MasterCrew => self
                .active
                .ok_or("there is no construction site to help on")?,
        };
        Ok((item, i))
    }

    fn use_item(&mut self, item: Item, i: usize, ts: i64) {
        if let Some(n) = self.inventory.get_mut(&item) {
            *n -= 1;
        }
        let pct = match item {
            Item::RepairKit => return self.fix(i, ts),
            Item::HiredHelp => economy::HELP_PCT,
            Item::MasterCrew => economy::CREW_PCT,
        };
        let total = need_of(i).kind.build_secs();
        let lot = &mut self.lots[i];
        let take = (total * pct / 100).min(total.saturating_sub(lot.done_secs));
        lot.done_secs += take;
        lot.memory.helped_secs += take;
        if lot.memory.started_at == 0 {
            lot.memory.started_at = ts;
        }
        if lot.done_secs >= total {
            // Finished by help, not by a session: no award to add it to.
            let award = self.award.take();
            self.finish(i, ts, 0, 0);
            self.award = award;
        }
    }

    pub fn balance(&self) -> u64 {
        self.coins_earned.saturating_sub(self.coins_spent)
    }

    fn finished(&self, i: usize) -> bool {
        self.lots[i].finished.is_some()
    }

    /// The need's next lot to build: its standing site, or its first empty lot.
    fn next_lot(&self, ni: usize) -> Option<usize> {
        plan::need_lots(ni)
            .map(|l| l.index as usize)
            .find(|&i| !self.finished(i))
    }

    fn open(&self, ni: usize) -> bool {
        NEEDS[ni].level == self.level && self.next_lot(ni).is_some()
    }

    fn sites(&self) -> impl Iterator<Item = usize> + '_ {
        (0..self.lots.len()).filter(|&i| self.lots[i].site && !self.finished(i))
    }

    fn paused(&self) -> usize {
        self.sites().filter(|&i| Some(i) != self.active).count()
    }

    fn owned_fitting(&self, need: &Need) -> impl Iterator<Item = &'static Blueprint> + '_ {
        let need = *need;
        BLUEPRINTS
            .iter()
            .filter(move |b| b.fits(&need) && self.owned.contains(b.id))
    }

    pub fn check_buy(&self, id: &str) -> Result<&'static Blueprint, String> {
        let b = plan::blueprint(id).ok_or_else(|| format!("no blueprint {id:?}"))?;
        if self.owned.contains(b.id) {
            return Err(format!("the {} blueprint is already yours", b.name));
        }
        if b.level > self.level {
            return Err(format!(
                "the {} blueprint is for sale from the {}",
                b.name,
                plan::LEVELS[b.level as usize].to_lowercase()
            ));
        }
        let price = self.cost(b.price);
        if self.balance() < price {
            return Err(format!(
                "the {} blueprint costs {price} coins; you have {}",
                b.name,
                self.balance()
            ));
        }
        Ok(b)
    }

    /// The need's index and the design its lot gets.
    pub fn check_choose(
        &self,
        id: &str,
        blueprint: Option<&str>,
    ) -> Result<(usize, Option<&'static str>), String> {
        let (ni, need) = plan::need_by_id(id).ok_or_else(|| format!("no need {id:?}"))?;
        if need.level > self.level {
            return Err(format!("nobody has asked for {:?} yet", need.title));
        }
        let Some(lot) = self.next_lot(ni).filter(|_| self.open(ni)) else {
            return Err(format!("{:?} is already met", need.title));
        };
        if !self.land[lot] {
            return Err(format!(
                "buy the plot at {} first",
                plan::lots()[lot].address
            ));
        }
        let site = &self.lots[lot];
        let design = if !need.kind.designed() {
            if blueprint.is_some() {
                return Err(format!(
                    "{:?} is built by the town, not from a blueprint",
                    need.title
                ));
            }
            None
        } else if site.done_secs > 0 {
            match blueprint {
                Some(b) if Some(b) != site.design => {
                    return Err(format!(
                        "{} is already half built from another blueprint",
                        self.name(lot)
                    ));
                }
                _ => site.design,
            }
        } else if let Some(id) = blueprint {
            let b = plan::blueprint(id).ok_or_else(|| format!("no blueprint {id:?}"))?;
            if !b.fits(need) {
                return Err(format!("the {} does not fit {:?}", b.name, need.title));
            }
            if !self.owned.contains(b.id) {
                return Err(format!("buy the {} blueprint first", b.name));
            }
            Some(b.id)
        } else {
            let first = self.owned_fitting(need).next().ok_or_else(|| {
                format!("buy a blueprint for {:?} first", need.title.to_lowercase())
            })?;
            Some(first.id)
        };
        let pauses_one = self.active.is_some_and(|a| a != lot);
        if pauses_one && !site.site && self.paused() >= World::MAX_PAUSED {
            return Err(format!(
                "{} sites already stand half built; finish or resume one first",
                World::MAX_PAUSED
            ));
        }
        Ok((ni, design))
    }

    pub fn check_pause(&self) -> Result<(), String> {
        match self.active {
            Some(_) => Ok(()),
            None => Err("nothing is under construction".into()),
        }
    }

    /// The lot's index and its new name (`None`: the one it was dealt).
    pub fn check_rename(&self, id: &str, name: &str) -> Result<(usize, Option<String>), String> {
        let lot = plan::lot_by_id(id).ok_or_else(|| format!("no lot {id:?}"))?;
        let i = lot.index as usize;
        if !self.finished(i) {
            return Err(format!("{} is not built yet", self.name(i)));
        }
        let name = name.trim();
        if name.chars().count() > NAME_MAX {
            return Err(format!("a name can be at most {NAME_MAX} characters"));
        }
        if name.chars().any(char::is_control) {
            return Err("a name cannot hold control characters".into());
        }
        Ok((i, (!name.is_empty()).then(|| name.to_string())))
    }

    fn choose(&mut self, ts: i64, ni: usize, design: Option<&'static str>) {
        let Some(lot) = self.next_lot(ni) else { return };
        if self.lots[lot].done_secs == 0 {
            self.set_design(lot, design);
        }
        self.lots[lot].site = true;
        self.active = Some(lot);
        let idle = std::mem::take(&mut self.idle);
        for part in idle {
            self.pour(part, ts);
        }
    }

    /// The plan's own pick while the mayor has chosen nothing: the first open
    /// need in plan order that can be built, buying its cheapest blueprint
    /// when none is owned and the coins are there.
    fn auto_pick(&mut self) -> Option<usize> {
        for (ni, need) in NEEDS.iter().enumerate() {
            if !self.open(ni) || !self.next_lot(ni).is_some_and(|l| self.land[l]) {
                continue;
            }
            let design = if need.kind.designed() {
                if let Some(b) = self.owned_fitting(need).next() {
                    Some(b.id)
                } else {
                    let level = self.level;
                    let cheapest = BLUEPRINTS
                        .iter()
                        .filter(|b| b.fits(need) && b.level <= level)
                        .min_by_key(|b| b.price)?;
                    let price = self.cost(cheapest.price);
                    if self.balance() < price {
                        continue;
                    }
                    self.owned.insert(cheapest.id);
                    self.coins_spent += price;
                    Some(cheapest.id)
                }
            } else {
                None
            };
            let lot = self.next_lot(ni)?;
            self.set_design(lot, design);
            self.lots[lot].site = true;
            return Some(lot);
        }
        None
    }

    /// Puts focused time into the active site, then the next ones.
    fn pour(&mut self, part: BuildPart, ts: i64) {
        let mut left = part.secs;
        while left > 0 {
            let site = match self.active {
                Some(a) => Some(a),
                None if !self.manual => self.auto_pick(),
                None => None,
            };
            let Some(a) = site else { break };
            self.active = Some(a);
            let total = need_of(a).kind.build_secs();
            let lot = &mut self.lots[a];
            let take = left.min(total.saturating_sub(lot.done_secs));
            lot.done_secs += take;
            left -= take;
            if take > 0 {
                if lot.memory.parts.is_empty() {
                    lot.memory.started_at = part.ts;
                }
                lot.memory.parts.push(BuildPart { secs: take, ..part });
                lot.memory.focused_secs += take;
            }
            if lot.done_secs >= total {
                self.finish(a, part.ts.max(ts), part.session_id, part.session_secs);
            }
        }
        if left > 0 {
            self.idle.push(BuildPart { secs: left, ..part });
        }
    }

    fn finish(&mut self, i: usize, ts: i64, session_id: i64, session_secs: u64) {
        let roll = mix(lot_seed(i, None) ^ (session_id as u64).rotate_left(17)) % 1000;
        let first = self.finished_count == 0;
        let streak = self.streak;
        let lot = &mut self.lots[i];
        lot.finished = Some((ts, session_id));
        lot.shiny = roll < shiny_odds(session_secs);
        lot.memory.streak_at_finish = streak;
        lot.memory.first = first;
        if lot.memory.started_at == 0 {
            lot.memory.started_at = ts;
        }
        let design = lot.design;
        self.finished_count += 1;
        self.active = None;
        self.record(
            ts,
            (WorldEventKind::Built, WorldCause::Completed),
            Some(session_id),
            vec![i as u32],
            vec![],
        );
        if let Some(a) = self.award.as_mut() {
            a.finished.push(i as u32);
        }
        while (self.level as usize) < plan::LEVELS.len()
            && NEEDS
                .iter()
                .enumerate()
                .all(|(ni, n)| n.level != self.level || self.next_lot(ni).is_none())
        {
            self.level += 1;
            self.record(
                ts,
                (WorldEventKind::Graduated, WorldCause::Completed),
                Some(session_id),
                vec![],
                vec![],
            );
        }
        // The mayor's need goes on to its next lot, same design.
        let ni = plan::lots()[i].need;
        if self.manual
            && self.open(ni)
            && let Some(next) = self.next_lot(ni)
            && self.land[next]
        {
            if !self.lots[next].site {
                self.set_design(next, design);
                self.lots[next].site = true;
            }
            self.active = Some(next);
        }
    }

    /// Sets a lot's design and deals it a name to match; a site whose design
    /// stays keeps its name.
    fn set_design(&mut self, i: usize, design: Option<&'static str>) {
        let lot = &self.lots[i];
        if lot.site && lot.design == design {
            return;
        }
        self.lots[i].design = design;
        self.lots[i].dealt = None;
        let Some(d) = design else { return };
        let names: Vec<String> = (0..self.lots.len())
            .filter(|&j| j != i && self.lots[j].site)
            .map(|j| self.name(j))
            .collect();
        let taken: Vec<&str> = names.iter().map(String::as_str).collect();
        self.lots[i].dealt = crate::names::deal(need_of(i).kind, d, &taken);
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

    /// Finished buildings that can still take damage.
    fn standing(&self) -> impl Iterator<Item = usize> + '_ {
        (0..self.lots.len())
            .filter(|&i| self.finished(i) && self.lots[i].damage < World::MAX_DAMAGE)
    }

    fn newest(&self) -> Option<usize> {
        self.standing()
            .max_by_key(|&i| (self.lots[i].finished.map(|f| f.0), i))
    }

    /// Damages lots; returns those that became ruins.
    fn damage(&mut self, lots: &[u32], amount: u32, ts: i64, cause: WorldCause) -> Vec<u32> {
        let mut ruined = Vec::new();
        for &i in lots {
            let lot = &mut self.lots[i as usize];
            let before = lot.damage;
            lot.damage = (before + amount).min(World::MAX_DAMAGE);
            if lot.damage == before {
                continue;
            }
            lot.memory.scars.push(Scar {
                ts,
                cause,
                damage: lot.damage,
                repaired: false,
            });
            if lot.damage == World::MAX_DAMAGE {
                ruined.push(i);
            }
        }
        ruined
    }

    fn completed(&mut self, ts: i64, session_id: i64, secs: u64, tz: &TimeZone) {
        self.focused_secs += secs;
        let day = day_of(ts, tz);
        let mut award = Award {
            session_id,
            ts,
            coins: 0,
            length_bonus: 0,
            streak_bonus: 0,
            rested_bonus: 0,
            build_secs: secs,
            finished: vec![],
            freeze_earned: false,
            freezes_used: 0,
            stake_won: 0,
            boxes: Vec::new(),
        };
        if secs >= STREAK_MIN_SECS {
            let gap = self.last_day.map(|d| days_between(d, day));
            let grew = match gap {
                Some(0) => {
                    self.streak = self.streak.max(1);
                    false
                }
                Some(1) => {
                    self.streak += 1;
                    true
                }
                Some(g) if g > 1 && g - 1 <= i64::from(self.freezes) => {
                    let used = (g - 1) as u32;
                    self.freezes -= used;
                    award.freezes_used = used;
                    self.streak += 1;
                    true
                }
                _ => {
                    self.streak = 1;
                    false
                }
            };
            self.last_day = Some(day);
            if grew && self.streak.is_multiple_of(FREEZE_EVERY) && self.freezes < MAX_FREEZES {
                self.freezes += 1;
                award.freeze_earned = true;
            }
        }
        let rested = award.freezes_used == 0
            && self
                .last_completed_day
                .is_some_and(|d| days_between(d, day) >= 2);
        self.last_completed_day = Some(day);

        let (coins, length_bonus, streak_bonus) = coins(secs, self.streak_now(day));
        award.coins = if rested { coins * 2 } else { coins };
        award.length_bonus = length_bonus;
        award.streak_bonus = streak_bonus;
        award.rested_bonus = award.coins - coins;
        self.coins_earned += award.coins;

        if let Some(stake) = self.stakes.remove(&session_id) {
            // The stake comes back, and as much again.
            self.coins_spent -= stake;
            self.coins_earned += stake;
            award.stake_won = stake;
        }
        self.recent.push_back(secs);
        if self.recent.len() > economy::STAKE_HISTORY {
            self.recent.pop_front();
        }
        self.goals(day, session_id, secs, &mut award);

        self.award = Some(award);
        self.pour(
            BuildPart {
                session_id,
                ts,
                secs,
                session_secs: secs,
            },
            ts,
        );
        self.repair(ts, session_id, secs);
    }

    /// Counts a completed session toward the day's goals, and opens a box
    /// for each goal it meets.
    fn goals(&mut self, day: Date, session_id: i64, secs: u64, award: &mut Award) {
        if self.today.day != Some(day) {
            self.today = Today {
                day: Some(day),
                ..Today::default()
            };
        }
        let t = &mut self.today;
        t.focus += secs;
        t.longest = t.longest.max(secs);
        if secs >= economy::GOAL_SESSION_SECS {
            t.sessions += 1;
        }
        for goal in Goal::ALL {
            if self.today.paid.contains(&goal) || self.today.progress(goal) < goal.target() {
                continue;
            }
            self.today.paid.insert(goal);
            let roll = mix((session_id as u64).rotate_left(23) ^ ((goal as u64 + 1) * 0x9e37_79b9));
            let item = economy::open_box(goal, roll, self.since_rare);
            self.since_rare = if item.rare() { 0 } else { self.since_rare + 1 };
            *self.inventory.entry(item).or_default() += 1;
            award.boxes.push(BoxInfo {
                goal: goal.id().into(),
                item: item.id().into(),
            });
        }
    }

    /// The streak that counts on `day`: kept until the end of the next day.
    fn streak_now(&self, day: Date) -> u32 {
        match self.last_day {
            Some(d) if days_between(d, day) - 1 <= i64::from(self.freezes) => self.streak,
            _ => 0,
        }
    }

    fn repair(&mut self, ts: i64, session_id: i64, secs: u64) {
        let mut budget = 1 + secs / (REPAIR_MINS * 60);
        if self.streak >= STREAK_BONUS_DAYS {
            budget *= 2;
        }
        let mut repaired = Vec::new();
        for _ in 0..budget {
            let Some(i) = (0..self.lots.len())
                .filter(|&i| self.finished(i) && self.lots[i].damage > 0)
                .max_by_key(|&i| (self.lots[i].damage, std::cmp::Reverse(i)))
            else {
                break;
            };
            self.lots[i].damage -= 1;
            if !repaired.contains(&(i as u32)) {
                repaired.push(i as u32);
            }
        }
        for &i in &repaired {
            let lot = &mut self.lots[i as usize];
            lot.memory.scars.push(Scar {
                ts,
                cause: WorldCause::Completed,
                damage: lot.damage,
                repaired: true,
            });
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

    fn surrendered(&mut self, ts: i64, session_id: i64) {
        // A stake on it is lost.
        self.stakes.remove(&session_id);
        self.streak = 0;
        self.last_day = None;
        let Some(origin) = self.active.or_else(|| self.newest()) else {
            self.record(
                ts,
                (WorldEventKind::Collapsed, WorldCause::Surrendered),
                Some(session_id),
                vec![],
                vec![],
            );
            return;
        };
        let mut near: Vec<usize> = self.standing().collect();
        let (ox, oy) = ground_pos(origin);
        near.sort_by_key(|&i| {
            let (x, y) = ground_pos(i);
            ((x - ox).pow(2) + (y - oy).pow(2), i)
        });
        let mut hit: Vec<u32> = near.iter().take(FIRE_SPREAD).map(|&i| i as u32).collect();
        hit.sort_unstable();
        let ruined = self.damage(&hit, FIRE_DAMAGE, ts, WorldCause::Surrendered);
        let mut plots = vec![origin as u32];
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
        let block = |i: usize| plan::lots()[i].place.block;
        let mut counts = BTreeMap::<usize, usize>::new();
        for i in self.standing() {
            *counts.entry(block(i)).or_default() += 1;
        }
        // The biggest block; the latest planned on a tie.
        let district = counts
            .iter()
            .max_by_key(|&(d, n)| (*n, *d))
            .map(|(d, _)| *d);
        let hit: Vec<u32> = self
            .standing()
            .map(|i| i as u32)
            .filter(|&i| Some(block(i as usize)) == district)
            .collect();
        let ruined = self.damage(&hit, 1, ts, WorldCause::Tamper);
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
        let hit: Vec<u32> = self.newest().map(|i| i as u32).into_iter().collect();
        let ruined = self.damage(&hit, 1, ts, cause);
        self.record(
            ts,
            (WorldEventKind::Damaged, cause),
            session_id,
            hit,
            ruined,
        );
    }

    fn name(&self, i: usize) -> String {
        let lot = &self.lots[i];
        lot.name
            .clone()
            .or_else(|| lot.dealt.clone())
            .unwrap_or_else(|| plan::lots()[i].name.clone())
    }

    fn plot(&self, i: usize) -> Plot {
        let lot = &self.lots[i];
        let plan_lot = &plan::lots()[i];
        let need = need_of(i);
        let (built_at, session_id) = lot.finished.unwrap_or_default();
        Plot {
            index: i as u32,
            district: plan_lot.place.block as u32,
            grade: need.kind.grade(),
            damage: lot.damage,
            rubble: lot.damage >= World::MAX_DAMAGE,
            seed: lot_seed(i, lot.design),
            session_id,
            built_at,
            lot: plan_lot.id.clone(),
            kind: need.kind.name().into(),
            design: lot.design.map(str::to_string),
            name: self.name(i),
            address: plan_lot.address.clone(),
            need: need.id.into(),
            shiny: lot.shiny,
            memory: lot.memory.clone(),
            repair_price: (lot.damage > 0).then(|| self.repair_cost(i)),
        }
    }

    fn need_info(&self, ni: usize) -> NeedInfo {
        let need = &NEEDS[ni];
        let next = self.next_lot(ni);
        let fits_locked = BLUEPRINTS
            .iter()
            .filter(|b| b.fits(need) && !self.owned.contains(b.id))
            .map(|b| b.id.to_string())
            .collect();
        NeedInfo {
            id: need.id.into(),
            title: need.title.into(),
            words: need.words.into(),
            kind: need.kind.name().into(),
            district: need.district.name().into(),
            build_secs: need.kind.build_secs(),
            lots: need.lots,
            lots_done: plan::need_lots(ni)
                .filter(|l| self.finished(l.index as usize))
                .count() as u32,
            next_lot: next.map(|i| plan::lots()[i].id.clone()),
            site: next.is_some_and(|i| self.lots[i].site),
            designed: need.kind.designed(),
            fits: self.owned_fitting(need).map(|b| b.id.to_string()).collect(),
            fits_locked,
            land_price: next.filter(|&i| !self.land[i]).map(|i| self.land_cost(i)),
        }
    }

    fn site_info(&self, i: usize) -> SiteInfo {
        let lot = &self.lots[i];
        let need = need_of(i);
        SiteInfo {
            index: i as u32,
            lot: plan::lots()[i].id.clone(),
            need: need.id.into(),
            name: self.name(i),
            kind: need.kind.name().into(),
            design: lot.design.map(str::to_string),
            done_secs: lot.done_secs,
            build_secs: need.kind.build_secs(),
            active: self.active == Some(i),
            seed: lot_seed(i, lot.design),
        }
    }

    /// The world as of `now`, with the running session's site.
    pub fn world(&self, running: Option<&Running>, now: Timestamp, tz: &TimeZone) -> World {
        let today = now.to_zoned(tz.clone()).date();
        let level = self.level.min(plan::LEVELS.len() as u32);
        let tier_floor_secs: u64 = (0..level).map(plan::level_secs).sum();
        let next_tier_secs = ((level as usize) < plan::LEVELS.len())
            .then(|| tier_floor_secs + plan::level_secs(level));
        let built_secs = self.lots.iter().map(|l| l.done_secs).sum();

        let construction = running.and_then(|r| {
            // While the plan builds itself, show the lot it would pick.
            let mut preview = self.clone();
            let site = preview.active.or_else(|| {
                if preview.manual {
                    None
                } else {
                    preview.auto_pick()
                }
            })?;
            let lot = &preview.lots[site];
            let need = need_of(site);
            let kind = need.kind;
            let total = kind.build_secs();
            let remaining = total.saturating_sub(lot.done_secs);
            let done = lot.done_secs + r.elapsed_secs.min(remaining);
            Some(Construction {
                session_id: r.session_id,
                index: site as u32,
                grade: kind.grade(),
                progress_permille: Some((done * 1000 / total.max(1)) as u32),
                surrendering: r.surrendering,
                seed: lot_seed(site, lot.design),
                lot: plan::lots()[site].id.clone(),
                kind: kind.name().into(),
                design: lot.design.map(str::to_string),
                name: preview.name(site),
                need: need.id.into(),
                remaining_secs: remaining,
            })
        });

        let mut sites: Vec<SiteInfo> = self.sites().map(|i| self.site_info(i)).collect();
        sites.sort_by_key(|s| !s.active);
        let blueprints = BLUEPRINTS
            .iter()
            .map(|b| BlueprintInfo {
                id: b.id.into(),
                name: b.name.into(),
                kind: b.kind.name().into(),
                districts: b.districts.iter().map(|d| d.name().into()).collect(),
                level: b.level,
                price: self.cost(b.price),
                owned: self.owned.contains(b.id),
                unlocked: b.level <= self.level,
                built: (0..self.lots.len())
                    .filter(|&i| self.finished(i) && self.lots[i].design == Some(b.id))
                    .count() as u32,
            })
            .collect();
        let skip = self.history.len().saturating_sub(HISTORY);
        World {
            tier: level.min(World::MAX_TIER),
            focused_secs: self.focused_secs,
            tier_floor_secs,
            next_tier_secs,
            built_secs,
            streak_days: self.streak_now(today),
            plots: (0..self.lots.len())
                .filter(|&i| self.finished(i))
                .map(|i| self.plot(i))
                .collect(),
            construction,
            history: self.history[skip..].to_vec(),
            coins: self.balance(),
            coins_earned: self.coins_earned,
            needs: (0..NEEDS.len())
                .filter(|&ni| NEEDS[ni].level == level)
                .map(|ni| self.need_info(ni))
                .collect(),
            next_needs: NEEDS
                .iter()
                .filter(|n| n.level == level + 1)
                .map(|n| n.title.to_string())
                .collect(),
            blueprints,
            sites,
            idle_secs: self.idle.iter().map(|p| p.secs).sum(),
            freezes: self.freezes,
            auto: !self.manual,
            last_award: self.award.clone(),
            layout: self.layout_info(),
            wealth: self.wealth,
            decorations: economy::DECORATIONS
                .iter()
                .map(|d| DecorationInfo {
                    id: d.id.into(),
                    name: d.name.into(),
                    price: self.cost(d.price),
                    level: d.level,
                    unlocked: d.level <= self.level,
                })
                .collect(),
            stake: running.and_then(|r| self.stakes.get(&r.session_id).copied()),
            stake_target_secs: self.stake_target(),
            stake_max: self.stake_max(),
            inventory: Item::ALL
                .iter()
                .filter_map(|&item| {
                    let count = self.inventory.get(&item).copied().unwrap_or(0);
                    (count > 0).then(|| ItemInfo {
                        id: item.id().into(),
                        name: item.name().into(),
                        count,
                        rare: item.rare(),
                    })
                })
                .collect(),
            goals: Goal::ALL
                .iter()
                .map(|&g| {
                    let on = self.today.day == Some(today);
                    GoalInfo {
                        id: g.id().into(),
                        title: g.title().into(),
                        progress: if on { self.today.progress(g) } else { 0 },
                        target: g.target(),
                        done: on && self.today.paid.contains(&g),
                    }
                })
                .collect(),
            boxes_to_rare: economy::PITY.saturating_sub(self.since_rare),
        }
    }

    fn layout_info(&self) -> Layout {
        let blocks = layout::blocks()
            .iter()
            .enumerate()
            .map(|(b, block)| {
                let (district, park, name) = match block.ground {
                    Ground::Lots(d) => (Some(d.name().to_string()), None, None),
                    Ground::Park(kind, name) => {
                        (None, Some(kind.name().to_string()), Some(name.to_string()))
                    }
                };
                let spots = if park.is_some() {
                    (0..economy::PARK_SPOTS)
                        .map(|n| {
                            let id = format!("{b}:{n}");
                            SpotInfo {
                                decoration: self.spots.get(&id).map(|d| d.to_string()),
                                id,
                            }
                        })
                        .collect()
                } else {
                    Vec::new()
                };
                BlockInfo {
                    x: block.x,
                    y: block.y,
                    district,
                    park,
                    name,
                    level: block.level,
                    open: self.block_open(b),
                    spots,
                }
            })
            .collect();
        let streets = STREETS
            .iter()
            .enumerate()
            .map(|(si, s)| StreetInfo {
                id: s.id.into(),
                name: s.name.into(),
                axis: match s.axis {
                    Axis::EastWest => "ew".into(),
                    Axis::NorthSouth => "ns".into(),
                },
                line: s.line,
                from: s.from,
                to: s.to,
                class: self.roads[si],
                upgrade_price: self.check_upgrade(s.id).ok().map(|(_, p)| p).or_else(|| {
                    // Unaffordable still shows its price; not yet allowed does not.
                    let next = self.roads[si] + 1;
                    economy::road_upgrade(next)
                        .filter(|&(_, level)| level <= self.level)
                        .map(|(list, _)| self.cost(list))
                }),
            })
            .collect();
        let lots = plan::lots()
            .iter()
            .map(|l| {
                let i = l.index as usize;
                LotInfo {
                    id: l.id.clone(),
                    block: l.place.block as u32,
                    slot: l.place.slot,
                    street: l.place.street as u32,
                    address: l.address.clone(),
                    owned: self.land[i],
                    price: self.land_cost(i),
                    for_sale: need_of(i).level <= self.level,
                }
            })
            .collect();
        Layout {
            blocks,
            streets,
            lots,
        }
    }
}

/// Folds `facts` (in any order) into the world as of `now`, with all land
/// bought (`bare` tests buy their own).
#[cfg(test)]
pub fn build(facts: &[Fact], running: Option<&Running>, now: Timestamp, tz: &TimeZone) -> World {
    let mut c = City::fold_landed(facts, tz);
    c.roll_day(now.as_second(), tz);
    c.world(running, now, tz)
}

#[cfg(test)]
mod tests {
    use super::*;

    const DAY: i64 = 86_400;
    const MIN: u64 = 60;

    fn done(ts: i64, id: i64, mins: u64) -> Fact {
        Fact {
            ts,
            seq: 0,
            session_id: Some(id),
            kind: FactKind::Completed { secs: mins * MIN },
        }
    }

    fn gave_up(ts: i64, id: i64, mins: u64) -> Fact {
        Fact {
            ts,
            seq: 0,
            session_id: Some(id),
            kind: FactKind::Surrendered { secs: mins * MIN },
        }
    }

    fn event(ts: i64, kind: FactKind) -> Fact {
        Fact {
            ts,
            seq: 0,
            session_id: Some(99),
            kind,
        }
    }

    fn mayor(ts: i64, kind: FactKind) -> Fact {
        Fact {
            ts,
            seq: 0,
            session_id: None,
            kind,
        }
    }

    fn chose(ts: i64, need: &str, blueprint: Option<&str>) -> Fact {
        mayor(
            ts,
            FactKind::Chose {
                need: need.into(),
                blueprint: blueprint.map(str::to_string),
            },
        )
    }

    fn bought(ts: i64, blueprint: &str) -> Fact {
        mayor(
            ts,
            FactKind::Bought {
                blueprint: blueprint.into(),
            },
        )
    }

    fn world(facts: &[Fact], now: i64) -> World {
        build(
            facts,
            None,
            Timestamp::from_second(now).unwrap(),
            &TimeZone::UTC,
        )
    }

    fn lots(w: &World) -> Vec<&str> {
        w.plots.iter().map(|p| p.lot.as_str()).collect()
    }

    fn damage(w: &World) -> Vec<u32> {
        w.plots.iter().map(|p| p.damage).collect()
    }

    /// One session a day from day 1, each `mins` long.
    fn daily(n: i64, mins: u64) -> Vec<Fact> {
        (1..=n).map(|d| done(d * DAY, d, mins)).collect()
    }

    #[test]
    fn coins_pay_for_depth() {
        assert_eq!(coins(50 * MIN, 0), (83, 0, 0));
        // 50 at 1x, 40 at 1.5x, 10 at 2x.
        assert_eq!(coins(100 * MIN, 0).0, 216);
        assert!(coins(100 * MIN, 0).0 > 2 * coins(50 * MIN, 0).0);
        // Past 3 hours the bonus stops.
        let three = coins(180 * MIN, 0).0;
        assert_eq!(coins(240 * MIN, 0).0 - three, 100);
        // Streak: +10% a day from day 3, capped at +50%.
        assert_eq!(coins(60 * MIN, 2).2, 0);
        assert_eq!(coins(60 * MIN, 0), (108, 8, 0));
        assert_eq!(coins(60 * MIN, 3), (118, 8, 10));
        assert_eq!(coins(60 * MIN, 30).0, 162);
        assert_eq!(coins(30, 0).0, 0);
    }

    #[test]
    fn empty_world() {
        let w = world(&[], 0);
        assert_eq!(
            (w.tier, w.focused_secs, w.streak_days, w.coins),
            (0, 0, 0, 0)
        );
        assert_eq!(w.next_tier_secs, Some(10 * 3600));
        assert!(w.plots.is_empty() && w.sites.is_empty());
        assert!(w.auto);
        assert_eq!(w.needs.len(), 5);
        assert_eq!(w.needs[0].fits, ["c1"]);
        assert!(w.blueprints.iter().any(|b| b.id == "c1" && b.owned));
        assert!(w.next_needs.contains(&"A school".to_string()));
    }

    #[test]
    fn a_cottage_takes_an_hour_across_sessions() {
        let w = world(&[done(100, 1, 40)], 200);
        assert!(w.plots.is_empty());
        assert_eq!(w.sites.len(), 1);
        assert_eq!(
            (w.sites[0].lot.as_str(), w.sites[0].done_secs),
            ("hamlet-homes-1", 40 * MIN)
        );
        assert_eq!(w.sites[0].design.as_deref(), Some("c1"));
        assert_eq!(w.coins, 66);

        let w = world(&[done(100, 1, 40), done(200, 2, 30)], 300);
        assert_eq!(lots(&w), ["hamlet-homes-1"]);
        let m = &w.plots[0].memory;
        assert_eq!(m.parts.len(), 2);
        assert_eq!(
            (m.parts[1].secs, m.parts[1].session_secs),
            (20 * MIN, 30 * MIN)
        );
        assert_eq!(m.focused_secs, 60 * MIN);
        assert!(m.first);
        // The rest went on to the next house.
        assert_eq!(w.sites[0].lot, "hamlet-homes-2");
        assert_eq!(w.sites[0].done_secs, 10 * MIN);
        assert_eq!(w.built_secs, 70 * MIN);
        assert_eq!(w.history.last().unwrap().kind, WorldEventKind::Built);
        assert_eq!(w.last_award.as_ref().unwrap().finished, [0]);
    }

    #[test]
    fn auto_mode_buys_and_builds_the_hamlet_in_order() {
        // 4 homes (4 h), then the shops need a 300-coin blueprint, which
        // 4 h of focus pays for.
        let w = world(&daily(5, 60), 6 * DAY);
        assert_eq!(w.plots.len(), 4);
        assert_eq!(w.sites[0].lot, "hamlet-shops-1");
        assert_eq!(w.sites[0].design.as_deref(), Some("s1"));
        assert!(w.blueprints.iter().any(|b| b.id == "s1" && b.owned));
        // A whole hamlet (10 h): graduation to town, whose homes come next.
        let w = world(&daily(12, 60), 13 * DAY);
        assert_eq!(w.tier, 1);
        assert_eq!(w.plots.len(), 11);
        assert_eq!(w.plots[10].lot, "town-homes-2");
        assert!(
            w.history
                .iter()
                .any(|e| e.kind == WorldEventKind::Graduated)
        );
        assert_eq!(w.tier_floor_secs, 10 * 3600);
        assert!(w.needs.iter().all(|n| n.id.starts_with("town-")));
    }

    #[test]
    fn auto_mode_continues_a_need_and_keeps_the_change() {
        let facts: Vec<Fact> = (0..6).map(|i| done(100 + i * 10, i + 1, 60)).collect();
        let w = world(&facts, 1000);
        // Four homes, then the shop blueprint bought from 540 coins, one shop
        // built in 90 min and the next begun.
        assert_eq!(w.plots.len(), 5);
        assert_eq!(w.coins, 6 * 108 - 300);
        assert_eq!(
            (w.sites[0].lot.as_str(), w.sites[0].done_secs),
            ("hamlet-shops-2", 30 * MIN)
        );
    }

    #[test]
    fn the_mayor_picks_the_need_and_the_plan_the_lot() {
        let facts = vec![
            done(100, 1, 60),
            chose(150, "hamlet-water", None),
            done(200, 2, 50),
        ];
        let w = world(&facts, 300);
        assert!(!w.auto);
        assert_eq!(lots(&w), ["hamlet-homes-1", "hamlet-water-1"]);
        // Water met: the rest waits as crew hours.
        assert!(w.sites.is_empty());
        assert_eq!(w.idle_secs, 20 * MIN);
        // Choosing the next need pours them in.
        let mut facts = facts;
        facts.push(chose(400, "hamlet-power", None));
        let w = world(&facts, 500);
        assert_eq!(w.sites[0].done_secs, 20 * MIN);
        assert_eq!(w.idle_secs, 0);
    }

    #[test]
    fn a_need_continues_to_its_next_lot() {
        let facts = vec![chose(10, "hamlet-homes", Some("c1")), done(100, 1, 150)];
        let w = world(&facts, 300);
        assert_eq!(lots(&w), ["hamlet-homes-1", "hamlet-homes-2"]);
        assert_eq!(w.sites[0].lot, "hamlet-homes-3");
        assert_eq!(w.sites[0].done_secs, 30 * MIN);
    }

    #[test]
    fn pausing_and_switching_leaves_sites_half_built() {
        let mut facts = vec![
            chose(10, "hamlet-homes", None),
            done(100, 1, 30),
            chose(150, "hamlet-water", None),
            done(200, 2, 10),
        ];
        let w = world(&facts, 300);
        assert_eq!(w.sites.len(), 2);
        assert!(w.sites[0].active && w.sites[0].lot == "hamlet-water-1");
        assert_eq!(w.sites[1].done_secs, 30 * MIN);
        facts.push(mayor(250, FactKind::Paused));
        facts.push(done(300, 3, 25));
        let w = world(&facts, 400);
        assert!(w.sites.iter().all(|s| !s.active));
        assert_eq!(w.idle_secs, 25 * MIN);
        // Back to the homes: the house resumes where it was.
        facts.push(chose(450, "hamlet-homes", None));
        let w = world(&facts, 500);
        let home = w.sites.iter().find(|s| s.active).unwrap();
        assert_eq!(
            (home.lot.as_str(), home.done_secs),
            ("hamlet-homes-1", 55 * MIN)
        );
    }

    #[test]
    fn choices_the_daemon_would_refuse_are_ignored() {
        let facts = vec![
            chose(10, "town-school", None),
            chose(20, "hamlet-shops", None),
            bought(30, "s1"),
            chose(40, "hamlet-homes", Some("c2")),
        ];
        let c = City::fold_landed(&facts, &TimeZone::UTC);
        assert!(!c.manual);
        let w = c.world(None, Timestamp::UNIX_EPOCH, &TimeZone::UTC);
        assert!(w.auto && w.sites.is_empty() && w.coins == 0);
        assert!(
            c.check_choose("town-school", None)
                .unwrap_err()
                .contains("nobody")
        );
        assert!(
            c.check_choose("hamlet-shops", None)
                .unwrap_err()
                .contains("buy a blueprint")
        );
        assert!(c.check_buy("s1").unwrap_err().contains("costs 300"));
        assert!(c.check_buy("o1").unwrap_err().contains("city"));
        assert!(c.check_buy("c1").unwrap_err().contains("already"));
        assert!(c.check_choose("hamlet-water", Some("c1")).is_err());
        assert!(c.check_pause().is_err());
    }

    #[test]
    fn buying_spends_coins_and_unlocks_the_design() {
        let mut facts: Vec<Fact> = (0..4).map(|i| done(i * 10, i + 1, 60)).collect();
        facts.push(bought(100, "c2"));
        facts.push(chose(110, "hamlet-shops", None));
        let c = City::fold_landed(&facts, &TimeZone::UTC);
        assert_eq!(c.balance(), 4 * 108 - 250);
        // c2 is a cottage: still no shop blueprint, so no site.
        assert!(c.sites().next().is_none());
        assert!(c.check_buy("s3").unwrap_err().contains("costs 400"));
        let w = c.world(None, Timestamp::UNIX_EPOCH, &TimeZone::UTC);
        let shops = w.needs.iter().find(|n| n.id == "hamlet-shops").unwrap();
        assert!(shops.fits.is_empty());
        assert_eq!(shops.fits_locked, ["s1", "s3", "s2"]);
    }

    #[test]
    fn at_most_three_paused_sites() {
        let tz = TimeZone::UTC;
        let mut c = City {
            coins_earned: 10_000,
            ..City::default()
        };
        c.land.fill(true);
        c.apply(&bought(1, "s1"), &tz);
        c.apply(&bought(2, "s4"), &tz);
        let mut ts = 10;
        for need in [
            "hamlet-homes",
            "hamlet-shops",
            "hamlet-jobs",
            "hamlet-water",
        ] {
            c.apply(&chose(ts, need, None), &tz);
            c.apply(&done(ts + 1, ts, 5), &tz);
            ts += 10;
        }
        assert_eq!(c.paused(), 3);
        assert!(
            c.check_choose("hamlet-power", None)
                .unwrap_err()
                .contains("half built")
        );
        // Resuming one is always allowed.
        c.check_choose("hamlet-homes", None).unwrap();
        c.apply(&chose(ts, "hamlet-homes", None), &tz);
        assert_eq!(c.paused(), 3);
        assert_eq!(c.active, Some(0));
    }

    #[test]
    fn rested_bonus_doubles_the_comeback() {
        let w = world(&[done(DAY, 1, 60), done(4 * DAY, 2, 60)], 4 * DAY + 10);
        let a = w.last_award.unwrap();
        assert_eq!((a.coins, a.rested_bonus), (216, 108));
        // The next day is not a comeback.
        let w = world(&[done(DAY, 1, 60), done(2 * DAY, 2, 60)], 2 * DAY + 10);
        assert_eq!(w.last_award.unwrap().rested_bonus, 0);
    }

    #[test]
    fn streaks_count_days_of_25_minutes_and_break() {
        let facts = [
            done(DAY, 1, 25),
            done(2 * DAY, 2, 25),
            done(2 * DAY + 60, 3, 25),
            done(3 * DAY, 4, 10),
        ];
        assert_eq!(world(&facts[..3], 2 * DAY + 100).streak_days, 2);
        // A 10-minute session is not a streak day.
        assert_eq!(world(&facts, 3 * DAY + 100).streak_days, 2);
        assert_eq!(world(&facts, 4 * DAY + 100).streak_days, 0);
        let mut facts = facts.to_vec();
        facts.push(gave_up(3 * DAY + 200, 5, 10));
        assert_eq!(world(&facts, 3 * DAY + 300).streak_days, 0);
    }

    #[test]
    fn a_seven_day_streak_earns_a_freeze_that_saves_a_missed_day() {
        let mut facts = daily(7, 30);
        let w = world(&facts, 7 * DAY + 10);
        assert_eq!((w.streak_days, w.freezes), (7, 1));
        assert!(w.last_award.unwrap().freeze_earned);
        // Day 8 missed; the streak still shows on day 9, then goes on.
        assert_eq!(world(&facts, 9 * DAY + 10).streak_days, 7);
        assert_eq!(world(&facts, 10 * DAY + 10).streak_days, 0);
        facts.push(done(9 * DAY, 9, 30));
        let w = world(&facts, 9 * DAY + 10);
        assert_eq!((w.streak_days, w.freezes), (8, 0));
        let a = w.last_award.unwrap();
        assert_eq!((a.freezes_used, a.rested_bonus), (1, 0));
    }

    #[test]
    fn surrender_burns_the_buildings_near_the_site() {
        let mut facts = vec![chose(5, "hamlet-homes", None), done(10, 1, 240)];
        facts.push(chose(20, "hamlet-water", None));
        facts.push(done(30, 2, 10));
        facts.push(gave_up(100, 3, 40));
        let w = world(&facts, 200);
        assert_eq!(w.coins_earned, coins(240 * MIN, 1).0 + coins(10 * MIN, 1).0);
        assert_eq!(w.focused_secs, 250 * MIN, "surrendered time does not count");
        // The water tower site (lot 7) loses nothing banked but burns the
        // three homes nearest it.
        assert_eq!(damage(&w), [0, 2, 2, 2]);
        let last = w.history.last().unwrap();
        assert_eq!(last.kind, WorldEventKind::Collapsed);
        assert_eq!(last.plots, [7, 1, 2, 3]);
        assert_eq!(w.sites[0].done_secs, 10 * MIN);
        // A second surrender ruins them; they stay standing as ruins.
        facts.push(gave_up(200, 4, 5));
        let w = world(&facts, 300);
        assert_eq!(w.plots.len(), 4);
        assert_eq!(w.history.last().unwrap().ruined, [1, 2, 3]);
        assert!(w.plots[1].rubble);
        assert_eq!(w.plots[1].memory.scars.len(), 2);
    }

    #[test]
    fn completed_sessions_repair_ruins_back() {
        let mut facts = vec![chose(5, "hamlet-homes", None), done(10, 1, 240)];
        facts.push(gave_up(100, 2, 10));
        facts.push(gave_up(200, 3, 10));
        let w = world(&facts, 300);
        assert_eq!(damage(&w), [0, 3, 3, 3]);
        // 50 min: 3 levels, most damaged first.
        facts.push(done(300, 4, 50));
        let w = world(&facts, 400);
        assert_eq!(damage(&w), [0, 2, 2, 2]);
        assert!(w.plots[1].memory.scars.last().unwrap().repaired);
    }

    #[test]
    fn streak_doubles_repairs() {
        let mut facts = vec![chose(5, "hamlet-homes", None)];
        facts.extend(daily(3, 60));
        facts.push(event(3 * DAY + 10, FactKind::Tamper));
        let w = world(&facts, 3 * DAY + 20);
        assert_eq!(damage(&w).iter().sum::<u32>(), 3);
        facts.push(done(3 * DAY + 100, 9, 10));
        // Day 3 of a streak: 2 repairs for a short session.
        let w = world(&facts, 3 * DAY + 200);
        assert_eq!(damage(&w).iter().sum::<u32>(), 1);
    }

    #[test]
    fn quake_hits_the_biggest_block_once_per_burst() {
        let facts: Vec<Fact> = daily(12, 60);
        let mut facts = facts;
        facts.extend([
            event(20 * DAY, FactKind::Tamper),
            event(20 * DAY + 1, FactKind::Tamper),
        ]);
        let w = world(&facts, 21 * DAY);
        let hit: Vec<u32> = damage(&w);
        // The Hamlet's four homes share a block; no other block has as many.
        assert_eq!(hit, [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]);
        assert_eq!(w.history.last().unwrap().kind, WorldEventKind::Quake);
        facts.push(event(20 * DAY + PENALTY_COOLDOWN, FactKind::Tamper));
        assert_eq!(world(&facts, 21 * DAY).plots[0].damage, 2);
    }

    #[test]
    fn minor_penalties_hit_the_newest_building() {
        let facts = [
            done(10, 1, 120),
            event(30, FactKind::Denied),
            event(31, FactKind::Denied),
            event(40 + PENALTY_COOLDOWN, FactKind::ClockJump),
            event(50 + 2 * PENALTY_COOLDOWN, FactKind::Tunnel),
        ];
        let w = world(&facts, 5000);
        assert_eq!(damage(&w), [0, 3]);
        assert_eq!(w.history.last().unwrap().ruined, [1]);
        assert_eq!(w.history.last().unwrap().cause, WorldCause::Tunnel);
    }

    #[test]
    fn penalties_on_an_empty_world_are_harmless() {
        let w = world(
            &[
                event(1, FactKind::Tamper),
                event(2, FactKind::Denied),
                gave_up(3, 1, 10),
            ],
            10,
        );
        assert!(w.plots.is_empty());
        assert_eq!(w.history.len(), 3);
    }

    #[test]
    fn buildings_are_named_by_design_and_never_twice() {
        let facts = daily(12, 60);
        let w = world(&facts, 13 * DAY);
        let homes = crate::names::candidates(plan::Kind::Cottage, "c1");
        assert_eq!(w.plots[0].name, homes[0]);
        assert_eq!(w.plots[1].name, homes[1]);
        let shop = w.plots.iter().find(|p| p.kind == "shop").unwrap();
        let s1 = crate::names::candidates(plan::Kind::Shop, "s1");
        assert!(s1.contains(&shop.name.as_str()), "{}", shop.name);
        let mut names: Vec<&str> = w.plots.iter().map(|p| p.name.as_str()).collect();
        let n = names.len();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), n);
    }

    #[test]
    fn a_mayors_name_is_not_dealt_again() {
        let homes = crate::names::candidates(plan::Kind::Cottage, "c1");
        let facts = vec![
            done(DAY, 1, 60),
            mayor(
                DAY + 1,
                FactKind::Renamed {
                    lot: "hamlet-homes-1".into(),
                    name: homes[1].into(),
                },
            ),
            done(2 * DAY, 2, 60),
        ];
        let w = world(&facts, 3 * DAY);
        assert_eq!(w.plots[0].name, homes[1]);
        assert_eq!(w.plots[1].name, homes[0]);
    }

    /// A city that buys its own land.
    fn bare(facts: &[Fact], now: i64) -> (City, World) {
        let c = City::fold_at(facts, now, &TimeZone::UTC);
        let w = c.world(None, Timestamp::from_second(now).unwrap(), &TimeZone::UTC);
        (c, w)
    }

    fn land(ts: i64, lot: &str) -> Fact {
        mayor(ts, FactKind::LandBought { lot: lot.into() })
    }

    #[test]
    fn the_first_plot_is_free_and_the_rest_are_bought() {
        let mut facts = daily(2, 60);
        let (c, w) = bare(&facts, 2 * DAY + 10);
        assert_eq!(w.plots.len(), 1, "the second home waits for its land");
        assert_eq!(w.idle_secs, 3600);
        let price = w.needs[0].land_price.unwrap();
        assert!(price > 0);
        assert!(
            c.check_choose("hamlet-homes", None)
                .unwrap_err()
                .contains("buy the plot")
        );
        assert!(
            c.check_land("town-homes-1")
                .unwrap_err()
                .contains("from the town")
        );
        // Buying it puts the waiting hour in at once.
        facts.push(land(2 * DAY + 20, "hamlet-homes-2"));
        let (c, w) = bare(&facts, 2 * DAY + 30);
        assert_eq!(w.plots.len(), 2);
        assert_eq!(w.coins, c.coins_earned - price);
        assert!(w.layout.lots[1].owned && !w.layout.lots[2].owned);
        assert!(
            c.check_land("hamlet-homes-2")
                .unwrap_err()
                .contains("already yours")
        );
    }

    #[test]
    fn prices_rise_with_the_mornings_balance() {
        let facts = daily(3, 180);
        let (c, w) = bare(&facts, 3 * DAY + 10);
        // Day 3 opened with days 1 and 2 earned.
        let opening = c.coins_earned - coins(180 * MIN, 3).0;
        assert_eq!(w.wealth, opening);
        let s1 = w.blueprints.iter().find(|b| b.id == "s1").unwrap();
        assert_eq!(s1.price, economy::price(300, opening));
        // The next morning it is today's balance.
        let (_, w) = bare(&facts, 4 * DAY + 10);
        assert_eq!(w.wealth, w.coins);
    }

    #[test]
    fn repairs_can_be_bought_or_done_with_a_kit() {
        let mut facts = daily(1, 60);
        facts.push(event(DAY + 10, FactKind::Denied));
        let (c, w) = bare(&facts, DAY + 20);
        assert_eq!(w.plots[0].damage, 1);
        let price = w.plots[0].repair_price.unwrap();
        assert_eq!(c.check_repair("hamlet-homes-1").unwrap().1, price);
        facts.push(mayor(
            DAY + 30,
            FactKind::RepairBought {
                lot: "hamlet-homes-1".into(),
            },
        ));
        let (c, w) = bare(&facts, DAY + 40);
        assert_eq!(w.plots[0].damage, 0);
        assert_eq!(
            w.plots[0].memory.scars.last().unwrap().cause,
            WorldCause::Mayor
        );
        assert!(
            c.check_repair("hamlet-homes-1")
                .unwrap_err()
                .contains("no repair")
        );
        assert!(c.check_use("repair_kit", Some("hamlet-homes-1")).is_err());
    }

    #[test]
    fn streets_upgrade_where_people_live() {
        let mut facts = daily(3, 180);
        let (c, w) = bare(&facts, 3 * DAY + 10);
        let main = w.layout.streets.iter().find(|s| s.id == "main").unwrap();
        assert_eq!(main.class, 0);
        assert!(main.upgrade_price.is_some());
        assert!(
            c.check_upgrade("skyline")
                .unwrap_err()
                .contains("nobody lives")
        );
        facts.push(mayor(
            3 * DAY + 20,
            FactKind::StreetUpgraded {
                street: "main".into(),
            },
        ));
        let (c, w) = bare(&facts, 3 * DAY + 30);
        assert_eq!(
            w.layout
                .streets
                .iter()
                .find(|s| s.id == "main")
                .unwrap()
                .class,
            1
        );
        // A boulevard waits for the town.
        assert!(
            c.check_upgrade("main")
                .unwrap_err()
                .contains("from the town")
        );
    }

    #[test]
    fn decorations_go_on_open_parks() {
        let facts = daily(3, 180);
        let (c, w) = bare(&facts, 3 * DAY + 10);
        let green = w
            .layout
            .blocks
            .iter()
            .position(|b| b.name.as_deref() == Some("The Green"))
            .unwrap();
        let square = w
            .layout
            .blocks
            .iter()
            .position(|b| b.name.as_deref() == Some("Market Square"))
            .unwrap();
        assert!(w.layout.blocks[green].open && !w.layout.blocks[square].open);
        c.check_decorate(&format!("{green}:0"), "trees").unwrap();
        assert!(
            c.check_decorate(&format!("{green}:0"), "fountain")
                .unwrap_err()
                .contains("from the town")
        );
        assert!(
            c.check_decorate(&format!("{square}:0"), "trees")
                .unwrap_err()
                .contains("not laid out")
        );
        assert!(c.check_decorate(&format!("{green}:9"), "trees").is_err());
        let mut facts = facts;
        facts.push(mayor(
            3 * DAY + 20,
            FactKind::Decorated {
                spot: format!("{green}:0"),
                decoration: "trees".into(),
            },
        ));
        let (c, w) = bare(&facts, 3 * DAY + 30);
        assert_eq!(
            w.layout.blocks[green].spots[0].decoration.as_deref(),
            Some("trees")
        );
        assert!(
            c.check_decorate(&format!("{green}:0"), "trees")
                .unwrap_err()
                .contains("already")
        );
    }

    fn staked(ts: i64, id: i64, coins: u64) -> Fact {
        Fact {
            ts,
            seq: 0,
            session_id: Some(id),
            kind: FactKind::Staked { coins },
        }
    }

    #[test]
    fn a_stake_comes_back_double_or_burns() {
        let mut facts = daily(3, 60);
        let (c, w) = bare(&facts, 3 * DAY + 10);
        assert_eq!(w.stake_target_secs, 3600, "the median of recent sessions");
        assert!(
            c.check_stake(50, Some(1800))
                .unwrap_err()
                .contains("60 minutes")
        );
        assert!(c.check_stake(50, None).is_err());
        assert!(c.check_stake(w.coins + 1, Some(3600)).is_err());
        c.check_stake(50, Some(3600)).unwrap();
        let before = w.coins;
        facts.push(staked(4 * DAY - 3600, 4, 50));
        facts.push(done(4 * DAY, 4, 60));
        let (_, w) = bare(&facts, 4 * DAY + 10);
        let award = w.last_award.unwrap();
        assert_eq!(award.stake_won, 50);
        assert_eq!(w.coins, before + award.coins + 50);
        let before = w.coins;
        facts.push(staked(5 * DAY - 600, 5, 50));
        facts.push(gave_up(5 * DAY, 5, 10));
        let (_, w) = bare(&facts, 5 * DAY + 10);
        assert_eq!(w.coins, before - 50);
    }

    #[test]
    fn goals_pay_one_box_each_a_day() {
        let mut facts = vec![done(DAY, 1, 30), done(DAY + 3600, 2, 30)];
        let (_, w) = bare(&facts, DAY + 3700);
        assert!(w.goals.iter().all(|g| !g.done));
        assert!(w.inventory.is_empty());
        // The third 30-minute session: three sessions, not yet two hours.
        facts.push(done(DAY + 7200, 3, 30));
        let (_, w) = bare(&facts, DAY + 7300);
        let goal = |w: &World, id: &str| w.goals.iter().find(|g| g.id == id).unwrap().clone();
        assert!(goal(&w, "sessions").done && !goal(&w, "daily_focus").done);
        assert_eq!(w.last_award.as_ref().unwrap().boxes.len(), 1);
        // A 90-minute session meets the other two, once.
        facts.push(done(DAY + 20_000, 4, 90));
        facts.push(done(DAY + 30_000, 5, 90));
        let (_, w) = bare(&facts, DAY + 30_100);
        assert!(w.goals.iter().all(|g| g.done));
        assert_eq!(w.inventory.iter().map(|i| i.count).sum::<u32>(), 3);
        assert_eq!(w.boxes_to_rare, economy::PITY - 3);
        // A new day starts the goals over.
        let (_, w) = bare(&facts, 2 * DAY + 10);
        assert!(w.goals.iter().all(|g| !g.done && g.progress == 0));
    }

    #[test]
    fn hired_help_builds_but_is_not_focus() {
        let mut c = City {
            coins_earned: 10_000,
            ..City::default()
        };
        c.land.fill(true);
        c.inventory.insert(Item::HiredHelp, 1);
        let tz = TimeZone::UTC;
        assert!(
            c.check_use("hired_help", None)
                .unwrap_err()
                .contains("no construction")
        );
        c.apply(&done(DAY, 1, 30), &tz);
        assert_eq!(c.active, Some(0));
        c.apply(
            &mayor(
                DAY + 10,
                FactKind::ItemUsed {
                    item: "hired_help".into(),
                    lot: None,
                },
            ),
            &tz,
        );
        assert_eq!(c.lots[0].done_secs, 30 * 60 + 15 * 60);
        assert_eq!(c.lots[0].memory.helped_secs, 15 * 60);
        assert_eq!(c.lots[0].memory.focused_secs, 30 * 60);
        assert!(
            c.check_use("hired_help", None)
                .unwrap_err()
                .contains("no hired help")
        );
    }

    #[test]
    fn renames() {
        let mut facts = vec![done(10, 1, 60)];
        let c = City::fold_landed(&facts, &TimeZone::UTC);
        assert!(c.check_rename("hamlet-homes-2", "x").is_err());
        assert!(c.check_rename("hamlet-homes-1", &"x".repeat(41)).is_err());
        assert!(c.check_rename("hamlet-homes-1", "a\nb").is_err());
        facts.push(mayor(
            20,
            FactKind::Renamed {
                lot: "hamlet-homes-1".into(),
                name: "  Grandma's  ".into(),
            },
        ));
        assert_eq!(world(&facts, 30).plots[0].name, "Grandma's");
        facts.push(mayor(
            40,
            FactKind::Renamed {
                lot: "hamlet-homes-1".into(),
                name: "".into(),
            },
        ));
        let w = world(&facts, 50);
        let homes = crate::names::candidates(plan::Kind::Cottage, "c1");
        assert_eq!(w.plots[0].name, homes[0], "back to its dealt name");
        assert!(w.auto, "a rename is not a building decision");
    }

    #[test]
    fn shiny_odds_rise_with_length() {
        assert_eq!(shiny_odds(25 * MIN), SHINY_BASE);
        assert!(shiny_odds(110 * MIN) > SHINY_BASE);
        assert_eq!(shiny_odds(6 * 3600), SHINY_MAX);
        // Over a whole plan some come out shiny, most do not.
        let w = world(&daily(400, 120), 401 * DAY);
        let shiny = w.plots.iter().filter(|p| p.shiny).count();
        assert!(shiny > 0 && shiny < w.plots.len() / 2, "{shiny}");
    }

    #[test]
    fn construction_shows_the_site_with_this_session() {
        let running = Running {
            session_id: 7,
            elapsed_secs: 15 * MIN,
            surrendering: false,
        };
        let w = build(
            &[done(10, 1, 30)],
            Some(&running),
            Timestamp::from_second(100).unwrap(),
            &TimeZone::UTC,
        );
        let c = w.construction.unwrap();
        assert_eq!(
            (c.index, c.progress_permille, c.remaining_secs),
            (0, Some(750), 30 * MIN)
        );
        assert_eq!(c.design.as_deref(), Some("c1"));
        // The mayor paused: nothing is built, the session banks.
        let w = build(
            &[done(10, 1, 30), mayor(20, FactKind::Paused)],
            Some(&running),
            Timestamp::from_second(100).unwrap(),
            &TimeZone::UTC,
        );
        assert!(w.construction.is_none());
    }

    #[test]
    fn same_facts_same_world_in_any_order() {
        let facts = [
            done(10, 1, 30),
            event(20, FactKind::Tamper),
            event(20, FactKind::Denied),
            chose(25, "hamlet-water", None),
            gave_up(30, 2, 5),
        ];
        let mut reversed = facts.clone();
        reversed.reverse();
        assert_eq!(world(&facts, 100), world(&reversed, 100));
    }
}
