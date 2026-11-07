//! The master plan as data: levels, the residents' needs, the lots that answer
//! them and the blueprints that fill those lots (`docs/GAME.md`).
//!
//! Lots are generated from the needs in order, and a lot's place in that list
//! is its index in the world for good, so the plan only ever grows at the
//! end: a new need goes after the last one, never between two, and a need's
//! lot count never changes. `lot_ids_are_pinned` holds the list as shipped.

pub const LEVELS: [&str; 4] = ["Hamlet", "Town", "City", "Metropolis"];

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Kind {
    Water,
    Power,
    Cottage,
    Shop,
    Workshop,
    Apartment,
    School,
    Clinic,
    FireStation,
    Square,
    Police,
    Library,
    Park,
    Office,
    Hospital,
    CityHall,
    Tower,
}

impl Kind {
    pub fn name(self) -> &'static str {
        match self {
            Kind::Water => "water",
            Kind::Power => "power",
            Kind::Cottage => "cottage",
            Kind::Shop => "shop",
            Kind::Workshop => "workshop",
            Kind::Apartment => "apartment",
            Kind::School => "school",
            Kind::Clinic => "clinic",
            Kind::FireStation => "fire_station",
            Kind::Square => "square",
            Kind::Police => "police",
            Kind::Library => "library",
            Kind::Park => "park",
            Kind::Office => "office",
            Kind::Hospital => "hospital",
            Kind::CityHall => "city_hall",
            Kind::Tower => "tower",
        }
    }

    /// Focused time one building of this kind takes.
    pub fn build_secs(self) -> u64 {
        let minutes = match self {
            Kind::Water | Kind::Power => 30,
            Kind::Cottage => 60,
            Kind::Shop => 90,
            Kind::Workshop => 120,
            Kind::Square => 180,
            Kind::Apartment | Kind::Park => 240,
            Kind::School | Kind::Clinic | Kind::FireStation => 300,
            Kind::Police | Kind::Library => 360,
            Kind::Office => 480,
            Kind::Hospital | Kind::CityHall => 720,
            Kind::Tower => 1500,
        };
        minutes * 60
    }

    /// Whether a lot of this kind is filled from a blueprint. Infrastructure
    /// and public buildings are built by the town (no models for them yet).
    pub fn designed(self) -> bool {
        matches!(
            self,
            Kind::Cottage
                | Kind::Shop
                | Kind::Workshop
                | Kind::Apartment
                | Kind::Office
                | Kind::Tower
        )
    }

    /// The size class renderers fall back to: 0 cottage, 1 shop, 2 apartment,
    /// 3 office, 4 landmark.
    pub fn grade(self) -> u32 {
        match self {
            Kind::Water | Kind::Power | Kind::Cottage => 0,
            Kind::Shop | Kind::Workshop | Kind::Square | Kind::Park => 1,
            Kind::Apartment
            | Kind::School
            | Kind::Clinic
            | Kind::FireStation
            | Kind::Police
            | Kind::Library => 2,
            Kind::Office | Kind::Hospital | Kind::CityHall => 3,
            Kind::Tower => 4,
        }
    }
}

/// Keeps a street coherent: a blueprint lists the districts it may stand in.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum District {
    Village,
    MainStreet,
    Works,
    Civic,
    Downtown,
}

impl District {
    pub fn name(self) -> &'static str {
        match self {
            District::Village => "village",
            District::MainStreet => "main_street",
            District::Works => "works",
            District::Civic => "civic",
            District::Downtown => "downtown",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Need {
    pub id: &'static str,
    pub level: u32,
    pub title: &'static str,
    /// What the residents say.
    pub words: &'static str,
    pub kind: Kind,
    pub district: District,
    pub lots: u32,
}

const fn need(
    id: &'static str,
    level: u32,
    title: &'static str,
    words: &'static str,
    kind: Kind,
    district: District,
    lots: u32,
) -> Need {
    Need {
        id,
        level,
        title,
        words,
        kind,
        district,
        lots,
    }
}

use District::*;
use Kind::*;

/// Append-only. Within a level, this is also the default build order.
pub const NEEDS: &[Need] = &[
    // Hamlet: 10 h.
    need(
        "hamlet-homes",
        0,
        "Housing shortage",
        "Four families share the old farmhouse.",
        Cottage,
        Village,
        4,
    ),
    need(
        "hamlet-shops",
        0,
        "Small business",
        "We walk an hour to buy a loaf of bread.",
        Shop,
        MainStreet,
        2,
    ),
    need(
        "hamlet-jobs",
        0,
        "Jobs",
        "The young ones leave to find work.",
        Workshop,
        Works,
        1,
    ),
    need(
        "hamlet-water",
        0,
        "Water",
        "We still carry water up from the river.",
        Water,
        Civic,
        1,
    ),
    need(
        "hamlet-power",
        0,
        "Electricity",
        "Candles at night, and the pump is worked by hand.",
        Power,
        Civic,
        1,
    ),
    // Town: about 40 h more.
    need(
        "town-homes",
        1,
        "More homes",
        "Newcomers are sleeping above the shops.",
        Cottage,
        Village,
        4,
    ),
    need(
        "town-flats",
        1,
        "Apartments",
        "Young couples cannot find a place to rent.",
        Apartment,
        MainStreet,
        2,
    ),
    need(
        "town-shops",
        1,
        "Shops and a café",
        "There is nowhere to sit and talk.",
        Shop,
        MainStreet,
        3,
    ),
    need(
        "town-jobs",
        1,
        "Work",
        "The works turns people away every Monday.",
        Workshop,
        Works,
        2,
    ),
    need(
        "town-school",
        1,
        "A school",
        "Our children ride the bus two towns over.",
        School,
        Civic,
        1,
    ),
    need(
        "town-clinic",
        1,
        "A clinic",
        "The nearest doctor is forty minutes away.",
        Clinic,
        Civic,
        1,
    ),
    need(
        "town-fire",
        1,
        "A fire station",
        "The barn fire last spring burned for an hour before help came.",
        FireStation,
        Civic,
        1,
    ),
    need(
        "town-square",
        1,
        "A square",
        "A town needs somewhere to gather.",
        Square,
        Civic,
        1,
    ),
    need(
        "town-water",
        1,
        "More water",
        "The taps run dry on wash day.",
        Water,
        Civic,
        1,
    ),
    need(
        "town-power",
        1,
        "More power",
        "The lights dim when the works runs late.",
        Power,
        Civic,
        1,
    ),
    // City: about 150 h more.
    need(
        "city-offices",
        2,
        "Offices",
        "Firms want to move here, but there are no desks.",
        Office,
        Downtown,
        6,
    ),
    need(
        "city-flats",
        2,
        "Apartments",
        "Rents doubled when the offices came.",
        Apartment,
        Downtown,
        6,
    ),
    need(
        "city-shops",
        2,
        "Shops",
        "Downtown closes at five.",
        Shop,
        Downtown,
        6,
    ),
    need(
        "city-hospital",
        2,
        "A hospital",
        "The clinic sends the serious cases away.",
        Hospital,
        Civic,
        1,
    ),
    need(
        "city-police",
        2,
        "A police station",
        "Bikes go missing from the station racks.",
        Police,
        Civic,
        1,
    ),
    need(
        "city-library",
        2,
        "A library",
        "The students study in the café until it closes.",
        Library,
        Civic,
        1,
    ),
    need(
        "city-park",
        2,
        "A park",
        "There is not a tree downtown.",
        Park,
        Civic,
        1,
    ),
    need(
        "city-hall",
        2,
        "City hall",
        "The council still meets above the bakery.",
        CityHall,
        Civic,
        1,
    ),
    need(
        "city-landmark",
        2,
        "A landmark",
        "Nobody would know our skyline.",
        Tower,
        Downtown,
        1,
    ),
    need(
        "city-water",
        2,
        "Water mains",
        "The old mains burst every winter.",
        Water,
        Civic,
        1,
    ),
    need(
        "city-power",
        2,
        "A power station",
        "Every new tower trips the grid.",
        Power,
        Civic,
        1,
    ),
    // Metropolis: open-ended later; this part is about 150 h.
    need(
        "metro-towers",
        3,
        "Towers",
        "Head offices want an address on the skyline.",
        Tower,
        Downtown,
        3,
    ),
    need(
        "metro-offices",
        3,
        "More offices",
        "Start-ups share desks in the library.",
        Office,
        Downtown,
        6,
    ),
    need(
        "metro-flats",
        3,
        "More apartments",
        "People commute in from three towns away.",
        Apartment,
        Downtown,
        6,
    ),
    need(
        "metro-shops",
        3,
        "Late shops",
        "A city this size should never sleep.",
        Shop,
        Downtown,
        4,
    ),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Blueprint {
    /// The model id renderers draw it with.
    pub id: &'static str,
    pub name: &'static str,
    pub kind: Kind,
    pub districts: &'static [District],
    /// The level from which it is for sale.
    pub level: u32,
    pub price: u64,
}

const fn bp(
    id: &'static str,
    name: &'static str,
    kind: Kind,
    districts: &'static [District],
    level: u32,
    price: u64,
) -> Blueprint {
    Blueprint {
        id,
        name,
        kind,
        districts,
        level,
        price,
    }
}

/// The starter blueprint, owned from the first session.
pub const STARTER: &str = "c1";

pub const BLUEPRINTS: &[Blueprint] = &[
    bp("c1", "Clapboard farmhouse", Cottage, &[Village], 0, 0),
    bp("c2", "Brick cottage", Cottage, &[Village], 0, 250),
    bp("c4", "A-frame cabin", Cottage, &[Village], 0, 250),
    bp(
        "s1",
        "Main-street shop",
        Shop,
        &[MainStreet, Downtown],
        0,
        300,
    ),
    bp("s3", "Diner", Shop, &[MainStreet], 0, 400),
    bp("s4", "Brick factory", Workshop, &[Works], 0, 400),
    bp("c3", "Modern house", Cottage, &[Village], 1, 400),
    bp("s2", "Corner café", Shop, &[MainStreet, Downtown], 1, 500),
    bp(
        "a1",
        "Brick apartment block",
        Apartment,
        &[MainStreet, Downtown],
        1,
        800,
    ),
    bp(
        "a2",
        "Brownstone row",
        Apartment,
        &[MainStreet, Downtown],
        1,
        900,
    ),
    bp(
        "a3",
        "Balcony block",
        Apartment,
        &[MainStreet, Downtown],
        1,
        900,
    ),
    bp(
        "o1",
        "Curtain-wall office tower",
        Office,
        &[Downtown],
        2,
        1500,
    ),
    bp("l1", "Art deco skyscraper", Tower, &[Downtown], 2, 3000),
];

pub fn blueprint(id: &str) -> Option<&'static Blueprint> {
    BLUEPRINTS.iter().find(|b| b.id == id)
}

pub fn need_by_id(id: &str) -> Option<(usize, &'static Need)> {
    NEEDS.iter().enumerate().find(|(_, n)| n.id == id)
}

impl Blueprint {
    pub fn fits(&self, need: &Need) -> bool {
        self.kind == need.kind && self.districts.contains(&need.district)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Lot {
    pub index: u32,
    /// `<need>-<n>`, counted from 1.
    pub id: String,
    pub need: usize,
    pub name: String,
    pub address: String,
    pub place: crate::layout::Place,
}

const SURNAMES: &[&str] = &[
    "Hart",
    "Fletcher",
    "Moreau",
    "Okafor",
    "Lindqvist",
    "Brennan",
    "Castillo",
    "Novak",
    "Whitlock",
    "Sato",
    "Abernathy",
    "Rossi",
    "Kowalski",
    "Haddad",
    "Ferreira",
    "Quinn",
    "Mbeki",
    "Dubois",
    "Larsen",
    "Calloway",
    "Petrov",
    "Nakamura",
    "Ashby",
    "Delgado",
    "Thorne",
    "Varga",
    "Oyelaran",
    "Marchetti",
    "Keane",
    "Sorensen",
    "Bianchi",
    "Holloway",
];
const TRADES: &[&str] = &[
    "Bakery",
    "Grocery",
    "Hardware",
    "Books",
    "Tailors",
    "Pharmacy",
    "Florist",
    "Butcher",
    "Records",
    "Cycles",
    "Deli",
    "Stationers",
];

fn default_name(need: &Need, n: u32, ordinal: usize) -> String {
    let surname = SURNAMES[(ordinal * 7 + 3) % SURNAMES.len()];
    let count = |s: &str| {
        if need.lots > 1 {
            format!("{s} No. {n}")
        } else {
            s.to_string()
        }
    };
    match need.kind {
        Cottage => format!("The {surname} house"),
        Shop => format!("{surname}'s {}", TRADES[(ordinal * 5) % TRADES.len()]),
        Workshop => format!("{surname} & Sons Works"),
        Apartment => format!("{surname} Court"),
        Office => format!("{surname} Building"),
        Tower => format!("{surname} Tower"),
        Water => count("Water tower"),
        Power => count(if need.level >= 2 {
            "Power station"
        } else {
            "Substation"
        }),
        School => "The school".into(),
        Clinic => "The clinic".into(),
        FireStation => "Fire station".into(),
        Square => "The square".into(),
        Police => "Police station".into(),
        Library => "Public library".into(),
        Park => "Memorial park".into(),
        Hospital => "General hospital".into(),
        CityHall => "City hall".into(),
    }
}

/// Every lot of the plan, in index order.
pub fn lots() -> &'static [Lot] {
    static LOTS: std::sync::OnceLock<Vec<Lot>> = std::sync::OnceLock::new();
    LOTS.get_or_init(|| {
        let mut out = Vec::new();
        let mut taken = std::collections::HashMap::<District, usize>::new();
        for (ni, need) in NEEDS.iter().enumerate() {
            for n in 1..=need.lots {
                let ordinal = out.len();
                let k = taken.entry(need.district).or_insert(0);
                let place = crate::layout::place(need.district, *k)
                    .unwrap_or_else(|| panic!("{} has no slot in the layout", need.id));
                *k += 1;
                let street = crate::layout::STREETS[place.street].name;
                out.push(Lot {
                    index: ordinal as u32,
                    id: format!("{}-{n}", need.id),
                    need: ni,
                    name: default_name(need, n, ordinal),
                    address: format!("{} {street}", place.number),
                    place,
                });
            }
        }
        out
    })
}

pub fn lot_by_id(id: &str) -> Option<&'static Lot> {
    lots().iter().find(|l| l.id == id)
}

/// The lots of one need, in build order.
pub fn need_lots(need: usize) -> impl Iterator<Item = &'static Lot> {
    lots().iter().filter(move |l| l.need == need)
}

/// Total build time of a level's needs.
pub fn level_secs(level: u32) -> u64 {
    NEEDS
        .iter()
        .filter(|n| n.level == level)
        .map(|n| n.kind.build_secs() * u64::from(n.lots))
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn level_hours_set_the_pace() {
        let h = |l| level_secs(l) as f64 / 3600.0;
        assert_eq!(h(0), 10.0);
        assert!((35.0..=45.0).contains(&h(1)), "town {}", h(1));
        assert!((140.0..=160.0).contains(&h(2)), "city {}", h(2));
    }

    #[test]
    fn every_designed_need_has_a_blueprint_for_sale_by_its_level() {
        for n in NEEDS {
            assert!(n.level < LEVELS.len() as u32);
            if n.kind.designed() {
                assert!(
                    BLUEPRINTS.iter().any(|b| b.fits(n) && b.level <= n.level),
                    "{} has no blueprint",
                    n.id
                );
            }
        }
        assert_eq!(blueprint(STARTER).unwrap().price, 0);
    }

    #[test]
    fn ids_are_unique() {
        let mut ids: Vec<&str> = NEEDS.iter().map(|n| n.id).collect();
        ids.extend(BLUEPRINTS.iter().map(|b| b.id));
        let n = ids.len();
        ids.sort_unstable();
        ids.dedup();
        assert_eq!(ids.len(), n);
    }

    #[test]
    fn levels_are_in_order() {
        assert!(NEEDS.windows(2).all(|w| w[0].level <= w[1].level));
    }

    /// The shipped plan. Appending is fine; anything else reshuffles every
    /// user's city.
    #[test]
    fn lot_ids_are_pinned() {
        let shipped: &[(&str, u32)] = &[
            ("hamlet-homes", 4),
            ("hamlet-shops", 2),
            ("hamlet-jobs", 1),
            ("hamlet-water", 1),
            ("hamlet-power", 1),
            ("town-homes", 4),
            ("town-flats", 2),
            ("town-shops", 3),
            ("town-jobs", 2),
            ("town-school", 1),
            ("town-clinic", 1),
            ("town-fire", 1),
            ("town-square", 1),
            ("town-water", 1),
            ("town-power", 1),
            ("city-offices", 6),
            ("city-flats", 6),
            ("city-shops", 6),
            ("city-hospital", 1),
            ("city-police", 1),
            ("city-library", 1),
            ("city-park", 1),
            ("city-hall", 1),
            ("city-landmark", 1),
            ("city-water", 1),
            ("city-power", 1),
            ("metro-towers", 3),
            ("metro-offices", 6),
            ("metro-flats", 6),
            ("metro-shops", 4),
        ];
        let now: Vec<(&str, u32)> = NEEDS.iter().map(|n| (n.id, n.lots)).collect();
        assert_eq!(&now[..shipped.len()], shipped);
        assert_eq!(lots()[0].id, "hamlet-homes-1");
        assert_eq!(lots()[4].id, "hamlet-shops-1");
        assert_eq!(lots().len(), 71);
    }

    #[test]
    fn names_and_addresses() {
        let l = &lots()[0];
        assert_eq!(l.address, "9 Main Street");
        assert_eq!(lots()[1].address, "11 Main Street");
        assert!(l.name.starts_with("The ") && l.name.ends_with(" house"));
        assert_eq!(lot_by_id("hamlet-water-1").unwrap().name, "Water tower");
        assert_eq!(lot_by_id("town-water-1").unwrap().address, "30 Main Street");
    }
}
