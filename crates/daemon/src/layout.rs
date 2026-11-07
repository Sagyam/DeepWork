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
}

/// The `n`-th lot (from 0) of a district, or `None` past the plan's slots.
pub fn place(district: District, n: usize) -> Option<Place> {
    let (_, slots) = DISTRICT_SLOTS.iter().find(|(d, _)| *d == district)?;
    let (x, y, slot) = slots
        .iter()
        .flat_map(|&(x, y, first, count)| (first..first + count).map(move |s| (x, y, s)))
        .nth(n)?;
    let back = slot >= 4;
    let line = if back { y + 1 } else { y };
    let street = STREETS
        .iter()
        .position(|s| s.axis == Axis::EastWest && s.line == line && (s.from..=s.to).contains(&x))
        .expect("every planned lot fronts a street");
    let along = (x - STREETS[street].from) as u32 * 4 + slot % 4;
    Some(Place {
        block: block_at(x, y),
        slot,
        street,
        number: if back { along * 2 + 1 } else { along * 2 + 2 },
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::plan::{self, NEEDS};

    #[test]
    fn every_lot_has_its_own_slot() {
        let mut seen = std::collections::HashSet::new();
        for lot in plan::lots() {
            assert!(seen.insert((lot.place.block, lot.place.slot)), "{}", lot.id);
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
    fn numbers_are_odd_north_even_south() {
        let main = STREETS.iter().position(|s| s.id == "main").unwrap();
        // The first home: north of Main Street, the block west of the middle.
        let first = place(Village, 0).unwrap();
        assert_eq!((first.street, first.number), (main, 9));
        let shop = place(MainStreet, 4).unwrap();
        assert_eq!((shop.street, shop.number), (main, 18));
    }
}
