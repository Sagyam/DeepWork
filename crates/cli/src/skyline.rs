//! A text renderer for the world in the city skyline theme. One column per
//! plot, height from its grade; damage and rubble are marked below.

use deepwork_proto::{World, WorldCause, WorldEvent, WorldEventKind};

const TIERS: [&str; 4] = ["Hamlet", "Town", "City", "Metropolis"];
const BUILDINGS: [&str; 5] = [
    "house",
    "shop",
    "tower block",
    "high-rise",
    "landmark tower",
];
const HEIGHTS: [char; 5] = ['▂', '▃', '▅', '▆', '█'];
const RUBBLE: char = '▁';
const SCAFFOLD: char = '┊';
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

pub fn render(w: &World, now: i64, color: bool) -> String {
    let mut out = String::new();
    let tier = TIERS[w.tier.min(3) as usize];
    let next = match w.next_tier_secs {
        Some(n) => format!(
            " · {} to {}",
            fmt_hm(n.saturating_sub(w.focused_secs)),
            TIERS[(w.tier as usize + 1).min(3)]
        ),
        None => String::new(),
    };
    let streak = match w.streak_days {
        0 => String::new(),
        1 => " · streak 1 day".into(),
        n => format!(" · streak {n} days"),
    };
    out += &format!(
        "{tier} · {} focused{next}{streak}\n\n",
        fmt_hm(w.focused_secs)
    );

    let site = w.construction.as_ref().map(|c| c.index as usize);
    let columns = w.plots.len().max(site.map_or(0, |i| i + 1));
    if columns == 0 {
        out += "  Empty land. Complete a session to put up the first building.\n";
    }
    for start in (0..columns).step_by(DISTRICT_SIZE) {
        let end = (start + DISTRICT_SIZE).min(columns);
        let mut top = format!("  district {:<3}", start / DISTRICT_SIZE + 1);
        let mut marks = " ".repeat(top.chars().count());
        let mut any_mark = false;
        for i in start..end {
            let (glyph, mark) = if site == Some(i) {
                (paint(SCAFFOLD, "36", color), '^')
            } else {
                let p = &w.plots[i];
                if p.rubble {
                    (paint(RUBBLE, "2", color), 'x')
                } else {
                    let h = HEIGHTS[p.grade.min(4) as usize];
                    match p.damage {
                        0 => (h.to_string(), ' '),
                        1 => (paint(h, "33", color), '1'),
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
    if columns > 0 {
        out += "\n  1 / 2 damaged · x rubble · ^ under construction\n";
    }

    if let Some(c) = &w.construction {
        let what = BUILDINGS[c.grade.min(4) as usize];
        let state = match (c.surrendering, c.progress_permille) {
            (true, _) => "about to collapse (surrendering)".to_string(),
            (false, Some(p)) => format!("{}% done", p / 10),
            (false, None) => "growing while the stopwatch runs".to_string(),
        };
        out += &format!("\nBuilding a {what} on plot {}: {state}\n", c.index + 1);
    }

    if !w.history.is_empty() {
        out += "\nRecent:\n";
        for e in w.history.iter().rev().take(8) {
            let ago = crate::fmt_ago((now - e.ts).max(0) as u64);
            out += &format!("  {ago:>7} ago  {}\n", describe(w, e));
        }
    }
    out
}

fn plots(list: &[u32]) -> String {
    let names: Vec<String> = list.iter().map(|i| (i + 1).to_string()).collect();
    match names.len() {
        1 => format!("plot {}", names[0]),
        _ => format!("plots {}", names.join(", ")),
    }
}

fn describe(w: &World, e: &WorldEvent) -> String {
    let ruined = if e.ruined.is_empty() {
        String::new()
    } else {
        format!("; {} fell into rubble", plots(&e.ruined))
    };
    let text = match e.kind {
        WorldEventKind::Built => {
            let grade = e
                .plots
                .first()
                .and_then(|&i| w.plots.get(i as usize))
                .filter(|p| e.session_id == Some(p.session_id))
                .map_or(String::from("building"), |p| {
                    BUILDINGS[p.grade.min(4) as usize].to_string()
                });
            format!("built a {grade} ({})", plots(&e.plots))
        }
        WorldEventKind::Repaired => format!("repaired {}", plots(&e.plots)),
        WorldEventKind::Collapsed => {
            let (site, burned) = e.plots.split_first().map_or((0, &[][..]), |(s, b)| (*s, b));
            let fire = if burned.is_empty() {
                String::new()
            } else {
                format!(", fire spread to {}", plots(burned))
            };
            format!("surrendered: plot {} collapsed{fire}", site + 1)
        }
        WorldEventKind::Quake if e.plots.is_empty() => {
            "earthquake (tampering) on empty land".into()
        }
        WorldEventKind::Quake => format!("earthquake (tampering) hit {}", plots(&e.plots)),
        WorldEventKind::Damaged => {
            let why = match e.cause {
                WorldCause::ClockJump => "wall clock jump",
                WorldCause::Tunnel => "proxy / tunnel",
                _ => "refused root access",
            };
            match e.plots.is_empty() {
                true => format!("{why}, nothing to damage yet"),
                false => format!("{why} damaged {}", plots(&e.plots)),
            }
        }
    };
    text + &ruined
}

#[cfg(test)]
mod tests {
    use super::*;
    use deepwork_proto::{Construction, Plot};

    fn plot(index: u32, grade: u32, damage: u32, rubble: bool) -> Plot {
        Plot {
            index,
            district: index / 8,
            grade,
            damage,
            rubble,
            seed: 0,
            session_id: index as i64 + 1,
            built_at: 0,
        }
    }

    #[test]
    fn renders_plots_marks_and_history() {
        let w = World {
            tier: 0,
            focused_secs: 3 * 3600 + 20 * 60,
            tier_floor_secs: 0,
            next_tier_secs: Some(10 * 3600),
            streak_days: 2,
            plots: vec![
                plot(0, 1, 0, false),
                plot(1, 4, 2, false),
                plot(2, 0, 0, true),
            ],
            construction: Some(Construction {
                session_id: 9,
                index: 2,
                grade: 2,
                progress_permille: Some(400),
                surrendering: false,
                seed: 0,
            }),
            history: vec![WorldEvent {
                ts: 0,
                kind: WorldEventKind::Collapsed,
                cause: WorldCause::Surrendered,
                session_id: Some(3),
                plots: vec![2, 1],
                ruined: vec![],
            }],
        };
        let text = render(&w, 7200, false);
        assert!(text.starts_with("Hamlet · 3h 20m focused · 6h 40m to Town · streak 2 days"));
        assert!(text.contains("  district 1   ▃ █ ┊\n"), "{text}");
        assert!(text.contains("                 2 ^\n"), "{text}");
        assert!(text.contains("Building a tower block on plot 3: 40% done"));
        assert!(text.contains("2 h ago  surrendered: plot 3 collapsed, fire spread to plot 2"));
    }

    #[test]
    fn empty() {
        let w = World {
            tier: 3,
            focused_secs: 0,
            tier_floor_secs: 0,
            next_tier_secs: None,
            streak_days: 0,
            plots: vec![],
            construction: None,
            history: vec![],
        };
        let text = render(&w, 0, false);
        assert!(text.starts_with("Metropolis · 0m focused\n"));
        assert!(text.contains("Empty land"));
    }
}
