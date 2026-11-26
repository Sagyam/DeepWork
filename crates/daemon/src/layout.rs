//! The master plan's ground: blocks on a grid, the streets between them, and
//! where each lot of the plan stands (`docs/GAME.md`).
//!
//! Block (x, y) is a cell of the grid holding 4 x 2 lots: the front row
//! (slots 0-3, west to east) faces the street on its north edge, the back
//! row (slots 4-7) the one on its south edge. East-west street line `k` runs
//! between block rows k-1 and k; north-south line `k` between columns k-1
//! and k. Renderers turn cells into metres; line 0 east-west is the highway.
//!
//! Like the lots, this only grows: a district's slots are taken in order, so
//! new slots go at the end of its list, and streets and parks at the end of
//! theirs.
//!
//! Landmarks stand on sites of several slots (`SITES`): a half block is two
//! slots across both rows, a whole block all eight. Their blocks are lot
//! blocks of their district, listed after the parks (`LANDMARK_BLOCKS`).

use crate::plan::District::{self, *};

/// A run of slots in one block: `(x, y, first slot, count)`.
type Slots = (i32, i32, u32, u32);

/// The slots each district's lots take, in order.
const DISTRICT_SLOTS: &[(District, &[Slots])] = &[
    // West along Main Street, then the lane behind.
    (
        Village,
        &[(-1, -1, 4, 4), (-1, 0, 0, 4), (-1, 0, 4, 4), (-1, -1, 0, 4)],
    ),
    // Both sides of Main Street, in the middle.
    (
        MainStreet,
        &[(0, -1, 4, 4), (0, 0, 0, 4), (0, 0, 4, 4), (0, -1, 0, 4)],
    ),
    // East, toward the river.
    (Works, &[(2, -1, 4, 4), (2, 0, 0, 4), (2, 0, 4, 4)]),
    (
        Civic,
        &[(1, -1, 4, 4), (1, 0, 0, 4), (1, -1, 0, 4), (1, 0, 4, 4)],
    ),
    // South of Church Street, two rows deep.
    (
        Downtown,
        &[
            (0, 1, 0, 8),
            (1, 1, 0, 8),
            (-1, 1, 0, 8),
            (0, 2, 0, 8),
            (1, 2, 0, 8),
        ],
    ),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParkKind {
    Green,
    Plaza,
    Park,
    Sports,
}

impl ParkKind {
    /// Places for decorations: the centre and four quarters, except on a
    /// sports ground, whose pitch fills the block.
    pub fn spots(self) -> u32 {
        match self {
            ParkKind::Sports => 0,
            _ => 5,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            ParkKind::Green => "green",
            ParkKind::Plaza => "plaza",
            ParkKind::Park => "park",
            ParkKind::Sports => "sports",
        }
    }
}

/// Blocks for landmark sites, after the parks: `(x, y, district)`.
const LANDMARK_BLOCKS: &[(i32, i32, District)] = &[
    // North of Church Hill, across Mill Lane: city hall and the town square.
    (1, -2, Civic),
];

/// Where a landmark stands: `(need, x, y, slot, cols)`. It takes `cols`
/// slots across both rows from `slot`, and faces the street of `slot`'s
/// row. Its district's slot list still counts it, so moving a landmark here
/// moved no other lot.
const SITES: &[(&str, i32, i32, u32, u32)] =
    &[("city-hall", 1, -2, 4, 2), ("town-square", 1, -2, 6, 2)];

/// Blocks kept as open ground: `(x, y, kind, name, level it opens at)`.
const PARKS: &[(i32, i32, ParkKind, &str, u32)] = &[
    (0, -2, ParkKind::Green, "The Green", 0),
    (2, 1, ParkKind::Plaza, "Market Square", 1),
    (-2, 1, ParkKind::Park, "City Park", 2),
    (2, 2, ParkKind::Sports, "Riverside Ground", 2),
    (-2, 2, ParkKind::Plaza, "Founders' Square", 3),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Axis {
    /// Along x.
    EastWest,
    /// Along z.
    NorthSouth,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Street {
    pub id: &'static str,
    pub name: &'static str,
    pub axis: Axis,
    pub line: i32,
    /// The block columns (east-west) or rows (north-south) it runs past.
    pub from: i32,
    pub to: i32,
}

const fn street(id: &'static str, name: &'static str, axis: Axis, line: i32) -> Street {
    Street {
        id,
        name,
        axis,
        line,
        from: -2,
        to: 2,
    }
}

pub const STREETS: &[Street] = &[
    street("orchard", "Orchard Way", Axis::EastWest, -2),
    street("mill", "Mill Lane", Axis::EastWest, -1),
    street("main", "Main Street", Axis::EastWest, 0),
    street("church", "Church Street", Axis::EastWest, 1),
    street("commerce", "Commerce Avenue", Axis::EastWest, 2),
    street("skyline", "Skyline Boulevard", Axis::EastWest, 3),
    street("west", "West Road", Axis::NorthSouth, -2),
    street("baker", "Baker Street", Axis::NorthSouth, -1),
    street("market", "Market Street", Axis::NorthSouth, 0),
    street("station", "Station Road", Axis::NorthSouth, 1),
    street("foundry", "Foundry Lane", Axis::NorthSouth, 2),
    street("river", "River Road", Axis::NorthSouth, 3),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Neighbourhood {
    pub id: &'static str,
    pub name: &'static str,
    /// Its lot blocks, `(x, y)`.
    pub blocks: &'static [(i32, i32)],
}

/// Named groups of lot blocks. Each lot block is in exactly one; parks in
/// none (they carry their own names). Finishing every lot in one is a set.
pub const NEIGHBOURHOODS: &[Neighbourhood] = &[
    hood("millbrook", "Millbrook", &[(-1, -1), (-1, 0)]),
    hood("old_town", "Old Town", &[(0, -1), (0, 0)]),
    hood("church_hill", "Church Hill", &[(1, -1), (1, 0)]),
    hood("canal", "The Canal Quarter", &[(2, -1), (2, 0)]),
    hood("exchange", "The Exchange", &[(-1, 1), (0, 1), (1, 1)]),
    hood("highgate", "Highgate", &[(0, 2), (1, 2)]),
    hood("civic_centre", "Civic Centre", &[(1, -2)]),
];

const fn hood(
    id: &'static str,
    name: &'static str,
    blocks: &'static [(i32, i32)],
) -> Neighbourhood {
    Neighbourhood { id, name, blocks }
}

/// The neighbourhood a block is in, by index into [`NEIGHBOURHOODS`].
pub fn neighbourhood_of(block: usize) -> Option<usize> {
    let b = blocks()[block];
    NEIGHBOURHOODS
        .iter()
        .position(|n| n.blocks.contains(&(b.x, b.y)))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Ground {
    Lots(District),
    Park(ParkKind, &'static str),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Block {
    pub x: i32,
    pub y: i32,
    pub ground: Ground,
    /// The level from which it is part of the town (parks); 0 for lot blocks,
    /// which show once land in them is bought.
    pub level: u32,
}

/// Every block of the plan: lot blocks in the order districts first take
/// them, then the parks.
pub fn blocks() -> &'static [Block] {
    static BLOCKS: std::sync::OnceLock<Vec<Block>> = std::sync::OnceLock::new();
    BLOCKS.get_or_init(|| {
        let mut out: Vec<Block> = Vec::new();
        for (district, slots) in DISTRICT_SLOTS {
            for &(x, y, _, _) in *slots {
                if !out.iter().any(|b| (b.x, b.y) == (x, y)) {
                    out.push(Block {
                        x,
                        y,
                        ground: Ground::Lots(*district),
                        level: 0,
                    });
                }
            }
        }
        for &(x, y, kind, name, level) in PARKS {
            out.push(Block {
                x,
                y,
                ground: Ground::Park(kind, name),
                level,
            });
        }
        for &(x, y, district) in LANDMARK_BLOCKS {
            out.push(Block {
                x,
                y,
                ground: Ground::Lots(district),
                level: 0,
            });
        }
        out
    })
}

fn block_at(x: i32, y: i32) -> usize {
    blocks()
        .iter()
        .position(|b| (b.x, b.y) == (x, y))
        .expect("a planned block")
}

/// Where a lot stands.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Place {
    /// Index into [`blocks`].
    pub block: usize,
    pub slot: u32,
    /// Index into [`STREETS`]: the street it fronts.
    pub street: usize,
    /// Its number on that street: odd on the north side, even on the south.
    pub number: u32,
    /// Slots it spans across, from `slot`: 1 for a lot, more for a landmark.
    pub cols: u32,
    /// Rows it spans: 1 for a lot, 2 for a landmark (it reaches the back street).
    pub rows: u32,
}

impl Place {
    /// The slots it covers.
    #[cfg(test)]
    pub fn slots(&self) -> impl Iterator<Item = u32> + '_ {
        let col = self.slot % 4;
        let row = self.slot / 4;
        let rows = if self.rows > 1 { 0..2 } else { row..row + 1 };
        rows.flat_map(move |r| (col..col + self.cols).map(move |c| r * 4 + c))
    }
}

/// The `n`-th lot (from 0) of a district, or `None` past the plan's slots.
pub fn place(district: District, n: usize) -> Option<Place> {
    let (_, slots) = DISTRICT_SLOTS.iter().find(|(d, _)| *d == district)?;
    let (x, y, slot) = slots
        .iter()
        .flat_map(|&(x, y, first, count)| (first..first + count).map(move |s| (x, y, s)))
        .nth(n)?;
    Some(at(x, y, slot, 1, 1))
}

/// The landmark site of a need, if it has one (`SITES`).
pub fn site(need: &str) -> Option<Place> {
    SITES
        .iter()
        .find(|s| s.0 == need)
        .map(|&(_, x, y, slot, cols)| at(x, y, slot, cols, 2))
}

fn at(x: i32, y: i32, slot: u32, cols: u32, rows: u32) -> Place {
    let back = slot >= 4;
    let line = if back { y + 1 } else { y };
    let street = STREETS
        .iter()
        .position(|s| s.axis == Axis::EastWest && s.line == line && (s.from..=s.to).contains(&x))
        .expect("every planned lot fronts a street");
    let along = (x - STREETS[street].from) as u32 * 4 + slot % 4;
    Place {
        block: block_at(x, y),
        slot,
        street,
        number: if back { along * 2 + 1 } else { along * 2 + 2 },
        cols,
        rows,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::plan::{self, NEEDS};

    #[test]
    fn every_lot_has_its_own_slot() {
        let mut seen = std::collections::HashSet::new();
        for lot in plan::lots() {
            for slot in lot.place.slots() {
                assert!(seen.insert((lot.place.block, slot)), "{}", lot.id);
            }
            let b = blocks()[lot.place.block];
            assert_eq!(
                b.ground,
                Ground::Lots(NEEDS[lot.need].district),
                "{}",
                lot.id
            );
        }
    }

    #[test]
    fn blocks_do_not_overlap_and_streets_bound_them() {
        let all = blocks();
        for (i, a) in all.iter().enumerate() {
            assert!(!all[..i].iter().any(|b| (b.x, b.y) == (a.x, a.y)));
            for (axis, line, along) in [
                (Axis::EastWest, a.y, a.x),
                (Axis::EastWest, a.y + 1, a.x),
                (Axis::NorthSouth, a.x, a.y),
                (Axis::NorthSouth, a.x + 1, a.y),
            ] {
                assert!(
                    STREETS.iter().any(|s| s.axis == axis
                        && s.line == line
                        && (s.from..=s.to).contains(&along)),
                    "block {},{} has no street on line {line}",
                    a.x,
                    a.y
                );
            }
        }
    }

    #[test]
    fn every_lot_block_is_in_one_neighbourhood() {
        for (i, b) in blocks().iter().enumerate() {
            let n = NEIGHBOURHOODS
                .iter()
                .filter(|n| n.blocks.contains(&(b.x, b.y)))
                .count();
            let lots = matches!(b.ground, Ground::Lots(_));
            assert_eq!(n, usize::from(lots), "block {},{}", b.x, b.y);
            assert_eq!(neighbourhood_of(i).is_some(), lots);
        }
        for n in NEIGHBOURHOODS {
            for &(x, y) in n.blocks {
                assert!(blocks().iter().any(|b| (b.x, b.y) == (x, y)), "{}", n.id);
            }
        }
    }

    #[test]
    fn landmarks_stand_on_their_sites() {
        for &(need, x, y, slot, cols) in SITES {
            assert!(plan::NEEDS.iter().any(|n| n.id == need), "{need}");
            assert!(slot % 4 + cols <= 4, "{need} runs off its block");
            let lot = plan::lots()
                .iter()
                .find(|l| NEEDS[l.need].id == need)
                .unwrap();
            let b = blocks()[lot.place.block];
            assert_eq!(
                (b.x, b.y, lot.place.slots().count()),
                (x, y, cols as usize * 2),
                "{need}"
            );
        }
        // City hall faces Mill Lane, toward Church Hill.
        let hall = site("city-hall").unwrap();
        assert_eq!(STREETS[hall.street].id, "mill");
    }

    #[test]
    fn numbers_are_odd_north_even_south() {
        let main = STREETS.iter().position(|s| s.id == "main").unwrap();
        // The first home: north of Main Street, the block west of the middle.
        let first = place(Village, 0).unwrap();
        assert_eq!((first.street, first.number), (main, 9));
        let shop = place(MainStreet, 4).unwrap();
        assert_eq!((shop.street, shop.number), (main, 18));
    }
}
