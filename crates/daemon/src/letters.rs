//! Thank-you letters from the residents (`docs/GAME.md`): who writes, and
//! what. Pure; `world.rs` decides when, from the ledger, so letters are
//! folded like everything else and nobody can write one by opening the app.

use crate::plan::Kind;

const FAMILIES: &str = include_str!("../names/families.txt");

fn families() -> &'static [&'static str] {
    static PILE: std::sync::OnceLock<Vec<&'static str>> = std::sync::OnceLock::new();
    PILE.get_or_init(|| {
        FAMILIES
            .lines()
            .map(str::trim)
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .collect()
    })
}

/// Cottages and apartments: the buildings families live in.
pub fn is_home(kind: Kind) -> bool {
    matches!(kind, Kind::Cottage | Kind::Apartment)
}

/// The family in a home: the one its name gives ("The Hart house"), else
/// one dealt by lot from the pile. Append-only pile, so a family never
/// changes once dealt.
pub fn family(lot: usize, name: &str) -> String {
    let surname = name
        .strip_prefix("The ")
        .and_then(|n| n.strip_suffix(" house"))
        .filter(|n| !n.contains(' '))
        .unwrap_or_else(|| {
            let pile = families();
            pile[lot % pile.len()]
        });
    format!("The {surname} family")
}

/// What a letter thanks the mayor for.
#[derive(Debug, Clone, Copy)]
pub enum About<'a> {
    /// A street paid up to `class` (1 street, 2 boulevard, 3 avenue).
    Street { street: &'a str, class: u32 },
    /// A damaged building whole again; `own`: the writers' own home.
    Repaired { building: &'a str, own: bool },
    /// A decoration placed in a park, by id (`DECORATIONS`).
    Decoration { decoration: &'a str, park: &'a str },
    /// A public building finished.
    Opened {
        kind: Kind,
        building: &'a str,
        street: &'a str,
    },
    /// Every lot on a street, or in a neighbourhood, built.
    Set { name: &'a str, neighbourhood: bool },
}

impl About<'_> {
    pub fn kind(&self) -> &'static str {
        match self {
            About::Street { .. } => "street",
            About::Repaired { .. } => "repair",
            About::Decoration { .. } => "park",
            About::Opened { .. } => "opened",
            About::Set { .. } => "set",
        }
    }
}

/// The letter's body. `roll` picks among a few wordings.
pub fn write(about: About, roll: u64) -> String {
    let pick = |options: &[String]| options[(roll % options.len() as u64) as usize].clone();
    match about {
        About::Street { street, class } => match class {
            1 => pick(&[
                format!(
                    "Thank you for the tarmac on {street}. The children ride their bikes to the end and back until it gets dark, and now the lamps let them stay out a little longer."
                ),
                format!(
                    "No more mud on {street}! We can finally hang the washing out without it coming back spotted. The new lamps make the walk home feel safe."
                ),
            ]),
            2 => pick(&[
                format!(
                    "The trees along {street} are in. We sit on the step in the evening and watch the leaves move. It feels like a proper town now."
                ),
                format!(
                    "Thank you for the boulevard. {street} has shade all afternoon, and the birds have found it before we did."
                ),
            ]),
            _ => pick(&[
                format!(
                    "{street} is an avenue! People from the other side of town walk down it just to look. We tell them we live here."
                ),
                format!(
                    "We never thought our street would be the grand one. Thank you for making {street} an avenue."
                ),
            ]),
        },
        About::Repaired {
            building,
            own: true,
        } => pick(&[
            format!(
                "Thank you for mending {building}. We are back in our own beds tonight, and the kettle is on."
            ),
            format!(
                "{building} is whole again. We were afraid you'd forgotten us. We know now you hadn't."
            ),
        ]),
        About::Repaired {
            building,
            own: false,
        } => pick(&[
            format!(
                "{building} stands whole again. The whole street breathed out when the scaffolding came down."
            ),
            format!(
                "It was hard to walk past {building} while it was broken. Thank you for putting it right."
            ),
        ]),
        About::Decoration { decoration, park } => {
            let thing = match decoration {
                "trees" => "new trees",
                "benches" => "benches and lamps",
                "statue" => "statue of the founder",
                other => other,
            };
            pick(&[
                format!(
                    "We took a picnic to {park} on Sunday to see the {thing}. Half the town had the same idea."
                ),
                format!(
                    "Thank you for the {thing} in {park}. Our youngest says it's the best thing in the whole world, and this week we agree."
                ),
            ])
        }
        // Public buildings by what they are ("the new school"): their plan
        // names are labels, not names to put in a sentence.
        About::Opened {
            kind,
            building,
            street,
        } => match kind {
            Kind::Water => pick(&[
                "Running water! No more carrying buckets up from the river. Thank you.".to_string(),
                "The taps run clear and strong now, even on the top floors. Thank you for the new waterworks.".to_string(),
            ]),
            Kind::Power => pick(&[
                format!("The lights came on all at once last night, every house on {street}. We stood in the road and clapped."),
                "No more flickering in the evenings. The new power station hums away, and we can all read past dark.".to_string(),
            ]),
            Kind::School => pick(&[format!(
                "Our two walk to the new school on {street} now. They complain about homework, which means they're learning."
            )]),
            Kind::Clinic => pick(&[
                "When our father fell ill last week, the clinic was there, five minutes away. Thank you.".to_string(),
            ]),
            Kind::Hospital => pick(&[
                "Our daughter was born at the new hospital this week. We'll tell her the town built it for her.".to_string(),
            ]),
            Kind::FireStation => pick(&[format!(
                "We sleep better knowing the fire station is on {street}. The children wave at the engine every morning."
            )]),
            Kind::Police => pick(&[
                "Bikes stay where we leave them now. Thank you for the police station.".to_string(),
            ]),
            Kind::Library => pick(&[
                "The library is open, and our eldest has read half of it already. Thank you for somewhere quiet.".to_string(),
            ]),
            Kind::CityHall => pick(&[format!(
                "We walked past the new city hall on {street} today and felt proud to live here. A town needs a heart."
            )]),
            Kind::Square => pick(&[
                "There's a market in the square on Saturdays now. We meet half our neighbours there before nine.".to_string(),
            ]),
            Kind::Park => pick(&[
                "The new park is the best thing in town. We go every evening, rain or not.".to_string(),
            ]),
            _ => pick(&[format!(
                "{building} on {street} opened this week. It feels like the town is looking after us."
            )]),
        },
        About::Set {
            name,
            neighbourhood: false,
        } => pick(&[
            format!(
                "Every house on {name} is built. We held a street party, and everyone asked us to say thank you."
            ),
            format!("{name} is finished, end to end. We know all our neighbours by name now."),
        ]),
        About::Set {
            name,
            neighbourhood: true,
        } => pick(&[
            format!(
                "All of {name} is built. When people ask where we live, we say {name}, and they know it."
            ),
            format!(
                "{name} is complete. We walked every street of it this evening, and there wasn't an empty plot left."
            ),
        ]),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn families_come_from_the_house_name_or_the_pile() {
        assert_eq!(family(4, "The Hart house"), "The Hart family");
        assert_eq!(
            family(0, "Willowbank"),
            format!("The {} family", families()[0])
        );
        let n = families().len();
        assert_eq!(family(n + 1, "Rosemount"), family(1, "Fernlea"));
        let mut seen = std::collections::HashSet::new();
        assert!(
            families().iter().all(|f| seen.insert(*f)),
            "no family twice"
        );
    }

    #[test]
    fn letters_name_what_they_thank_for() {
        for roll in 0..4 {
            let t = write(
                About::Street {
                    street: "Mill Lane",
                    class: 2,
                },
                roll,
            );
            assert!(t.contains("Mill Lane"), "{t}");
            let t = write(
                About::Set {
                    name: "Millbrook",
                    neighbourhood: true,
                },
                roll,
            );
            assert!(t.contains("Millbrook"), "{t}");
            let t = write(
                About::Decoration {
                    decoration: "fountain",
                    park: "The Green",
                },
                roll,
            );
            assert!(t.contains("fountain") && t.contains("The Green"), "{t}");
        }
    }
}
