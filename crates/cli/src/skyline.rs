//! A text renderer for the world in the city skyline theme. One column per
//! lot of the plan, height from its kind; damage and ruins are marked below.
//! Then the mayor's desk: coins, the residents' needs and the sites.

use deepwork_proto::{World, WorldCause, WorldEvent, WorldEventKind};

const TIERS: [&str; 4] = ["Hamlet", "Town", "City", "Metropolis"];
const HEIGHTS: [char; 5] = ['▂', '▃', '▅', '▆', '█'];
const RUBBLE: char = '▁';
const SCAFFOLD: char = '┊';
const EMPTY: char = '·';
const DISTRICT_SIZE: usize = 8;

fn paint(s: impl std::fmt::Display, code: &str, color: bool) -> String {
    if color {
        format!("\x1b[{code}m{s}\x1b[0m")
    } else {
        s.to_string()
    }
}

pub fn fmt_hm(secs: u64) -> String {
    let (h, m) = (secs / 3600, secs / 60 % 60);
    if h > 0 {
        format!("{h}h {m:02}m")
    } else {
        format!("{m}m")
    }
}

fn header(w: &World) -> String {
    let tier = TIERS[w.tier.min(3) as usize];
    let next = match w.next_tier_secs {
        Some(n) => format!(
            " · {} of building to {}",
            fmt_hm(n.saturating_sub(w.built_secs)),
            TIERS[(w.tier as usize + 1).min(3)]
        ),
        None => " · the plan is finished".into(),
    };
    let streak = match w.streak_days {
        0 => String::new(),
        1 => " · streak 1 day".into(),
        n => format!(" · streak {n} days"),
    };
    let freezes = match w.freezes {
        0 => String::new(),
        n => format!(" ({n} freeze{})", if n == 1 { "" } else { "s" }),
    };
    format!(
        "{tier} · {} focused{next}{streak}{freezes}\n{} coins\n\n",
        fmt_hm(w.focused_secs),
        w.coins
    )
}

fn skyline(w: &World, color: bool) -> String {
    let mut out = String::new();
    let site = w
        .construction
        .as_ref()
        .map(|c| c.index as usize)
        .or_else(|| w.sites.iter().find(|s| s.active).map(|s| s.index as usize));
    let paused: Vec<usize> = w
        .sites
        .iter()
        .filter(|s| !s.active)
        .map(|s| s.index as usize)
        .collect();
    let columns = w
        .plots
        .iter()
        .map(|p| p.index as usize + 1)
        .chain(site.map(|i| i + 1))
        .chain(w.sites.iter().map(|s| s.index as usize + 1))
        .max()
        .unwrap_or(0);
    if columns == 0 {
        out += "  Empty land. Complete a session to start the first building.\n";
        return out;
    }
    for start in (0..columns).step_by(DISTRICT_SIZE) {
        let end = (start + DISTRICT_SIZE).min(columns);
        let mut top = format!("  district {:<3}", start / DISTRICT_SIZE + 1);
        let mut marks = " ".repeat(top.chars().count());
        let mut any_mark = false;
        for i in start..end {
            let plot = w.plots.iter().find(|p| p.index as usize == i);
            let (glyph, mark) = match plot {
                _ if site == Some(i) => (paint(SCAFFOLD, "36", color), '^'),
                _ if paused.contains(&i) => (paint(SCAFFOLD, "2", color), '='),
                None => (EMPTY.to_string(), ' '),
                Some(p) if p.rubble => (paint(RUBBLE, "2", color), 'x'),
                Some(p) => {
                    let h = HEIGHTS[p.grade.min(4) as usize];
                    match (p.damage, p.shiny) {
                        (0, true) => (paint(h, "93", color), '*'),
                        (0, false) => (h.to_string(), ' '),
                        (1, _) => (paint(h, "33", color), '1'),
                        _ => (paint(h, "31", color), '2'),
                    }
                }
            };
            any_mark |= mark != ' ';
            top += &format!(" {glyph}");
            marks.push(' ');
            marks.push(mark);
        }
        out += &top;
        out.push('\n');
        if any_mark {
            out += marks.trim_end();
            out.push('\n');
        }
    }
    out += "\n  1 / 2 damaged · x ruin · * shiny · ^ under construction · = paused\n";
    out
}

fn desk(w: &World) -> String {
    let mut out = String::new();
    if let Some(c) = &w.construction {
        let state = match (c.surrendering, c.progress_permille) {
            (true, _) => "work about to be lost (surrendering)".to_string(),
            (false, Some(p)) => format!("{}% done", p / 10),
            (false, None) => String::new(),
        };
        out += &format!("\nBuilding {}: {state}\n", c.name);
    }
    for s in &w.sites {
        let tag = if s.active { "building" } else { "paused" };
        out += &format!(
            "\n  {tag:<9} {} ({}): {} of {}",
            s.name,
            s.lot,
            fmt_hm(s.done_secs),
            fmt_hm(s.build_secs)
        );
    }
    if !w.sites.is_empty() {
        out.push('\n');
    }
    if w.idle_secs > 0 {
        out += &format!(
            "\n{} of crew hours wait for a site: `deepwork build <need>`\n",
            fmt_hm(w.idle_secs)
        );
    }
    if !w.needs.is_empty() {
        out += "\nThe residents ask for:\n";
        for n in &w.needs {
            if n.lots_done == n.lots {
                out += &format!("  ✓ {}\n", n.title);
                continue;
            }
            let design = match (n.designed, n.fits.is_empty()) {
                (false, _) => String::new(),
                (true, false) => format!(" · {}", n.fits.join(", ")),
                (true, true) => {
                    let forsale: Vec<String> = w
                        .blueprints
                        .iter()
                        .filter(|b| b.unlocked && n.fits_locked.contains(&b.id))
                        .map(|b| format!("{} {}", b.id, b.price))
                        .collect();
                    format!(
                        " · needs a blueprint: `deepwork buy` {}",
                        forsale.join(", ")
                    )
                }
            };
            out += &format!(
                "  {:<14} {} · {}/{} · {} each{design}\n                 \"{}\"\n",
                n.id,
                n.title,
                n.lots_done,
                n.lots,
                fmt_hm(n.build_secs),
                n.words
            );
        }
    }
    if w.auto {
        out += "\nThe plan builds itself in order until you choose a need.\n";
    }
    out
}

pub fn render(w: &World, now: i64, color: bool) -> String {
    let mut out = header(w);
    out += &skyline(w, color);
    out += &desk(w);
    if !w.history.is_empty() {
        out += "\nRecent:\n";
        for e in w.history.iter().rev().take(8) {
            let ago = crate::fmt_ago((now - e.ts).max(0) as u64);
            out += &format!("  {ago:>7} ago  {}\n", describe(w, e));
        }
    }
    out
}

/// The blueprints, for `deepwork buy` with no argument.
pub fn blueprints(w: &World) -> String {
    let mut out = format!("{} coins\n\n", w.coins);
    for b in &w.blueprints {
        let state = match (b.owned, b.unlocked) {
            (true, _) => format!("owned, {} built", b.built),
            (false, true) => format!("{} coins", b.price),
            (false, false) => format!(
                "{} coins, from the {}",
                b.price,
                TIERS[b.level.min(3) as usize]
            ),
        };
        out += &format!("  {:<4} {:<28} {:<10} {state}\n", b.id, b.name, b.kind);
    }
    out
}

fn name(w: &World, index: u32) -> String {
    w.plots
        .iter()
        .find(|p| p.index == index)
        .map(|p| p.name.clone())
        .or_else(|| {
            w.sites
                .iter()
                .find(|s| s.index == index)
                .map(|s| format!("the {} site", s.name))
        })
        .unwrap_or_else(|| format!("lot {}", index + 1))
}

fn names(w: &World, list: &[u32]) -> String {
    let names: Vec<String> = list.iter().map(|&i| name(w, i)).collect();
    names.join(", ")
}

fn describe(w: &World, e: &WorldEvent) -> String {
    let ruined = if e.ruined.is_empty() {
        String::new()
    } else {
        format!("; {} in ruins", names(w, &e.ruined))
    };
    let text = match e.kind {
        WorldEventKind::Built => format!("finished {}", names(w, &e.plots)),
        WorldEventKind::Repaired => format!("repaired {}", names(w, &e.plots)),
        WorldEventKind::Graduated => "every need was met: the settlement grew".into(),
        WorldEventKind::Collapsed => match e.plots.split_first() {
            None => "surrendered".into(),
            Some((_, [])) => "surrendered: the session built nothing".into(),
            Some((_, burned)) => format!("surrendered: fire spread to {}", names(w, burned)),
        },
        WorldEventKind::Quake if e.plots.is_empty() => {
            "earthquake (tampering) on empty land".into()
        }
        WorldEventKind::Quake => format!("earthquake (tampering) hit {}", names(w, &e.plots)),
        WorldEventKind::Damaged => {
            let why = match e.cause {
                WorldCause::ClockJump => "wall clock jump",
                WorldCause::Tunnel => "proxy / tunnel",
                _ => "refused root access",
            };
            match e.plots.is_empty() {
                true => format!("{why}, nothing to damage yet"),
                false => format!("{why} damaged {}", names(w, &e.plots)),
            }
        }
    };
    text + &ruined
}

#[cfg(test)]
mod tests {
    use super::*;
    use deepwork_proto::{Construction, NeedInfo, Plot, SiteInfo};

    fn plot(index: u32, grade: u32, damage: u32, rubble: bool) -> Plot {
        Plot {
            index,
            district: index / 8,
            grade,
            damage,
            rubble,
            name: format!("House {}", index + 1),
            ..Plot::default()
        }
    }

    #[test]
    fn renders_lots_marks_desk_and_history() {
        let w = World {
            focused_secs: 3 * 3600 + 20 * 60,
            next_tier_secs: Some(10 * 3600),
            built_secs: 3 * 3600,
            streak_days: 2,
            coins: 340,
            plots: vec![
                plot(0, 1, 0, false),
                plot(1, 4, 2, false),
                plot(3, 0, 3, true),
            ],
            construction: Some(Construction {
                index: 2,
                progress_permille: Some(400),
                name: "The Hart house".into(),
                ..Construction::default()
            }),
            sites: vec![SiteInfo {
                index: 2,
                lot: "hamlet-homes-3".into(),
                need: "hamlet-homes".into(),
                name: "The Hart house".into(),
                kind: "cottage".into(),
                design: Some("c1".into()),
                done_secs: 1200,
                build_secs: 3600,
                active: true,
                seed: 0,
            }],
            blueprints: vec![deepwork_proto::BlueprintInfo {
                id: "s1".into(),
                name: "Main-street shop".into(),
                kind: "shop".into(),
                districts: vec![],
                level: 0,
                price: 300,
                owned: false,
                unlocked: true,
                built: 0,
            }],
            needs: vec![NeedInfo {
                id: "hamlet-shops".into(),
                title: "Small business".into(),
                words: "We walk an hour.".into(),
                kind: "shop".into(),
                district: "main_street".into(),
                build_secs: 5400,
                lots: 2,
                lots_done: 0,
                next_lot: Some("hamlet-shops-1".into()),
                site: false,
                designed: true,
                fits: vec![],
                fits_locked: vec!["s1".into()],
                land_price: None,
            }],
            history: vec![WorldEvent {
                ts: 0,
                kind: WorldEventKind::Collapsed,
                cause: WorldCause::Surrendered,
                session_id: Some(3),
                plots: vec![2, 1],
                ruined: vec![],
            }],
            ..World::default()
        };
        let text = render(&w, 7200, false);
        assert!(
            text.starts_with(
                "Hamlet · 3h 20m focused · 7h 00m of building to Town · streak 2 days\n340 coins"
            ),
            "{text}"
        );
        assert!(text.contains("  district 1   ▃ █ ┊ ▁\n"), "{text}");
        assert!(text.contains("                 2 ^ x\n"), "{text}");
        assert!(text.contains("Building The Hart house: 40% done"));
        assert!(text.contains("building  The Hart house (hamlet-homes-3): 20m of 1h 00m"));
        assert!(
            text.contains("needs a blueprint: `deepwork buy` s1 300"),
            "{text}"
        );
        assert!(text.contains("2 h ago  surrendered: fire spread to House 2"));
    }

    #[test]
    fn empty() {
        let w = World {
            tier: 3,
            ..World::default()
        };
        let text = render(&w, 0, false);
        assert!(text.starts_with("Metropolis · 0m focused · the plan is finished\n"));
        assert!(text.contains("Empty land"));
    }
}
