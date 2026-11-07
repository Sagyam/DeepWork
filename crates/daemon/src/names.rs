//! Building names, dealt when a lot gets its design (`docs/GAME.md`).
//!
//! One pile per class of building in `crates/daemon/names/`: one name per
//! line, `#` comments, and a `[design]` header before names only that
//! blueprint gets (a diner's name is a diner's). Names before any header fit
//! every design of the kind.
//!
//! Names are folded from the ledger, not stored, so piles are append-only
//! like the plan's lots: a building gets the first name in pile order that
//! no other building has, and adding names at the end of a section never
//! changes a name already dealt. Reordering or removing one renames cities.

use crate::plan::Kind;

const HOUSES: &str = include_str!("../names/houses.txt");
const APARTMENTS: &str = include_str!("../names/apartments.txt");
const OFFICES: &str = include_str!("../names/offices.txt");
const SHOPS: &str = include_str!("../names/shops.txt");
const WORKSHOPS: &str = include_str!("../names/workshops.txt");
const TOWERS: &str = include_str!("../names/towers.txt");

fn pile(kind: Kind) -> Option<&'static str> {
    Some(match kind {
        Kind::Cottage => HOUSES,
        Kind::Apartment => APARTMENTS,
        Kind::Office => OFFICES,
        Kind::Shop => SHOPS,
        Kind::Workshop => WORKSHOPS,
        Kind::Tower => TOWERS,
        _ => return None,
    })
}

/// The names a building of this kind and design may get, in pile order:
/// the design's own first, then the kind's shared ones.
pub fn candidates(kind: Kind, design: &str) -> Vec<&'static str> {
    let Some(text) = pile(kind) else {
        return Vec::new();
    };
    let (mut own, mut shared) = (Vec::new(), Vec::new());
    let mut section: Option<&str> = None;
    for line in text.lines().map(str::trim) {
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some(id) = line.strip_prefix('[').and_then(|l| l.strip_suffix(']')) {
            section = Some(id.trim());
        } else if section.is_none() {
            shared.push(line);
        } else if section == Some(design) {
            own.push(line);
        }
    }
    own.extend(shared);
    own
}

/// A name for a new building: the first candidate no other building has.
/// When all are taken, the first free numbered one.
pub fn deal(kind: Kind, design: &str, taken: &[&str]) -> Option<String> {
    let names = candidates(kind, design);
    if names.is_empty() {
        return None;
    }
    let free = |n: &str| !taken.iter().any(|t| t.eq_ignore_ascii_case(n));
    if let Some(n) = names.iter().find(|n| free(n)) {
        return Some(n.to_string());
    }
    (2..)
        .flat_map(|k| names.iter().map(move |n| format!("{n} No. {k}")))
        .find(|n| free(n))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::plan::{BLUEPRINTS, NEEDS};

    #[test]
    fn every_design_has_enough_names_for_the_plan() {
        for b in BLUEPRINTS {
            let lots: u32 = NEEDS.iter().filter(|n| b.fits(n)).map(|n| n.lots).sum();
            let names = candidates(b.kind, b.id);
            assert!(
                names.len() as u32 >= lots,
                "{} has {} names for {lots} lots",
                b.id,
                names.len()
            );
        }
    }

    #[test]
    fn names_are_unique_and_fit_a_deed() {
        for kind in [
            Kind::Cottage,
            Kind::Apartment,
            Kind::Office,
            Kind::Shop,
            Kind::Workshop,
            Kind::Tower,
        ] {
            let text = pile(kind).unwrap();
            let mut seen = std::collections::HashSet::new();
            for line in text.lines().map(str::trim) {
                if line.is_empty() || line.starts_with('#') || line.starts_with('[') {
                    continue;
                }
                assert!(seen.insert(line.to_lowercase()), "{line} twice");
                assert!(line.chars().count() <= crate::world::NAME_MAX, "{line}");
            }
        }
    }

    #[test]
    fn diners_get_diner_names() {
        let names = candidates(Kind::Shop, "s3");
        assert!(names.iter().all(|n| !n.starts_with("Café")));
        assert!(names.contains(&"Starlite Diner"));
        let shops = candidates(Kind::Shop, "s1");
        assert!(
            candidates(Kind::Shop, "s2")
                .iter()
                .all(|n| !shops.contains(n))
        );
    }

    #[test]
    fn dealing_skips_taken_names_then_numbers_them() {
        let all = candidates(Kind::Tower, "l1");
        assert_eq!(deal(Kind::Tower, "l1", &[]).as_deref(), Some(all[0]));
        assert_eq!(deal(Kind::Tower, "l1", &[all[0]]).as_deref(), Some(all[1]));
        let upper = all[0].to_uppercase();
        assert_eq!(deal(Kind::Tower, "l1", &[&upper]).as_deref(), Some(all[1]));
        assert_eq!(
            deal(Kind::Tower, "l1", &all).unwrap(),
            format!("{} No. 2", all[0])
        );
        assert_eq!(deal(Kind::Water, "", &[]), None);
    }
}
