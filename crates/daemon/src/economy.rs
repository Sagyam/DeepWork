//! What coins buy besides blueprints, and what focus wins besides coins
//! (`docs/GAME.md`): prices, land, street classes, decorations, stakes, the
//! day's goals and the boxes they pay. Pure tables and rules; `world.rs`
//! folds the ledger through them.

use crate::plan::District;

/// Every price is its list price plus this many percent of the coins held
/// at the start of the local day, so a pile of coins costs more to spend
/// than a trickle, but saving still gets there (`price` never outruns the
/// balance it is based on). The day's opening balance, not the current
/// one, so spending first doesn't make the next thing cheaper.
pub const WEALTH_PCT: u64 = 10;

/// A list price, adjusted for wealth, rounded up to 5 coins.
pub fn price(list: u64, wealth: u64) -> u64 {
    let p = list + wealth * WEALTH_PCT / 100;
    p.div_ceil(5) * 5
}

/// List price of one lot of land.
pub fn land_price(district: District, level: u32) -> u64 {
    let base = match district {
        District::Village => 60,
        District::Works => 80,
        District::Civic => 100,
        District::MainStreet => 120,
        District::Downtown => 250,
    };
    base * (1 + u64::from(level) / 2)
}

/// Repairing one level of damage now, instead of waiting for sessions.
pub const REPAIR_PER_DAMAGE: u64 = 40;

/// Road classes, in upgrade order. Every street starts as a gravel lane.
pub const ROAD_CLASSES: [&str; 4] = ["lane", "street", "boulevard", "avenue"];

/// List price of upgrading a street to `class`, and the level that allows it.
pub fn road_upgrade(class: u32) -> Option<(u64, u32)> {
    match class {
        1 => Some((150, 0)),
        2 => Some((400, 1)),
        3 => Some((900, 2)),
        _ => None,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Decoration {
    pub id: &'static str,
    pub name: &'static str,
    pub price: u64,
    /// The level from which it is for sale.
    pub level: u32,
}

const fn deco(id: &'static str, name: &'static str, price: u64, level: u32) -> Decoration {
    Decoration {
        id,
        name,
        price,
        level,
    }
}

/// What a park's spots can hold. Renderers draw each by its id.
pub const DECORATIONS: &[Decoration] = &[
    deco("trees", "A ring of trees", 80, 0),
    deco("benches", "Benches and lamps", 120, 0),
    deco("fountain", "Fountain", 350, 1),
    deco("statue", "Statue of the founder", 450, 1),
    deco("bandstand", "Bandstand", 600, 2),
];

pub fn decoration(id: &str) -> Option<&'static Decoration> {
    DECORATIONS.iter().find(|d| d.id == id)
}

/// Spots on a park block: the centre and the four quarters.
pub const PARK_SPOTS: u32 = 5;

/// A stake may be at most this many coins.
pub const STAKE_MAX: u64 = 1000;
/// Completed sessions the stake target looks back on, and the target with
/// fewer than `STAKE_HISTORY_MIN` of them.
pub const STAKE_HISTORY: usize = 10;
pub const STAKE_HISTORY_MIN: usize = 3;
pub const STAKE_DEFAULT_SECS: u64 = 25 * 60;

/// The length a staked countdown must reach: the median of recent completed
/// sessions, so a bet is on going longer than usual.
pub fn stake_target(recent: &[u64]) -> u64 {
    if recent.len() < STAKE_HISTORY_MIN {
        return STAKE_DEFAULT_SECS;
    }
    let mut v = recent.to_vec();
    v.sort_unstable();
    v[v.len() / 2]
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Goal {
    /// Focused time in one day.
    DailyFocus,
    /// One long session.
    LongStretch,
    /// Several sessions in one day.
    Sessions,
}

impl Goal {
    pub const ALL: [Goal; 3] = [Goal::DailyFocus, Goal::LongStretch, Goal::Sessions];

    pub fn id(self) -> &'static str {
        match self {
            Goal::DailyFocus => "daily_focus",
            Goal::LongStretch => "long_stretch",
            Goal::Sessions => "sessions",
        }
    }

    pub fn title(self) -> &'static str {
        match self {
            Goal::DailyFocus => "Two hours of focus today",
            Goal::LongStretch => "One 90-minute session",
            Goal::Sessions => "Three sessions today",
        }
    }

    /// What today must reach: seconds, seconds, or sessions of 25 minutes.
    pub fn target(self) -> u64 {
        match self {
            Goal::DailyFocus => 2 * 3600,
            Goal::LongStretch => 90 * 60,
            Goal::Sessions => 3,
        }
    }

    /// Chance in a hundred that its box is rare (before the pity counter).
    fn rare_pct(self) -> u64 {
        match self {
            Goal::LongStretch => 15,
            _ => 8,
        }
    }
}

/// Sessions shorter than this don't count toward [`Goal::Sessions`].
pub const GOAL_SESSION_SECS: u64 = 25 * 60;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Item {
    /// Repairs one building fully.
    RepairKit,
    /// Puts `HELP_PCT` of a building's build time into the active site.
    HiredHelp,
    /// Rare: puts `CREW_PCT` in.
    MasterCrew,
}

/// Of a building's build time, what hired help and a master crew add.
pub const HELP_PCT: u64 = 25;
pub const CREW_PCT: u64 = 50;
/// After this many boxes without a rare item, the next one is rare.
pub const PITY: u32 = 5;

impl Item {
    pub const ALL: [Item; 3] = [Item::RepairKit, Item::HiredHelp, Item::MasterCrew];

    pub fn id(self) -> &'static str {
        match self {
            Item::RepairKit => "repair_kit",
            Item::HiredHelp => "hired_help",
            Item::MasterCrew => "master_crew",
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Item::RepairKit => "Repair kit",
            Item::HiredHelp => "Hired help",
            Item::MasterCrew => "Master crew",
        }
    }

    pub fn parse(id: &str) -> Option<Item> {
        Item::ALL.into_iter().find(|i| i.id() == id)
    }

    pub fn rare(self) -> bool {
        self == Item::MasterCrew
    }
}

/// What a box holds, from a roll the ledger fixes (so no reroll) and the
/// boxes since the last rare one.
pub fn open_box(goal: Goal, roll: u64, since_rare: u32) -> Item {
    if since_rare + 1 >= PITY || roll % 100 < goal.rare_pct() {
        return Item::MasterCrew;
    }
    // Repair kits and hired help, even.
    if (roll / 100).is_multiple_of(2) {
        Item::RepairKit
    } else {
        Item::HiredHelp
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wealth_raises_prices_but_saving_gets_there() {
        assert_eq!(price(300, 0), 300);
        assert_eq!(price(300, 2000), 500);
        assert_eq!(price(298, 0), 300, "rounded up to 5");
        // Saving for the dearest blueprint: enough coins always catch up.
        let list: u64 = 3000;
        let saved = (list * 100).div_ceil(100 - WEALTH_PCT) + 5;
        assert!(price(list, saved) <= saved);
    }

    #[test]
    fn stake_target_is_the_recent_median() {
        assert_eq!(stake_target(&[3000]), STAKE_DEFAULT_SECS);
        assert_eq!(stake_target(&[1500, 6000, 3000]), 3000);
        assert_eq!(stake_target(&[1500, 6000, 3000, 9000]), 6000);
    }

    #[test]
    fn boxes_have_a_pity_counter() {
        assert_eq!(open_box(Goal::DailyFocus, 50, PITY - 1), Item::MasterCrew);
        assert_eq!(open_box(Goal::DailyFocus, 50, 0), Item::RepairKit);
        assert_eq!(open_box(Goal::DailyFocus, 150, 0), Item::HiredHelp);
        assert_eq!(open_box(Goal::LongStretch, 10, 0), Item::MasterCrew);
        assert_eq!(open_box(Goal::DailyFocus, 10, 0), Item::RepairKit);
    }
}
