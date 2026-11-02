// The read-only views shown inside the settings sheet (upcoming routine runs,
// Stats, Session logs) and the pending-config notice, as HTML. The HUD poll
// pushes fresh data in; skips still go through the daemon like everything else.
import { dayName, describe, escapeHtml, hhmm, hm, isLoss, weekday } from "./format";
import type { Finished, PendingConfig, Status, Upcoming, World } from "./proto";
import type { Day, Stats } from "./stats";

/** The run a skip would spend a token on: the routine's next unskipped run that has not started. */
export function skippable(st: Status, routine: string): Upcoming | undefined {
  return st.upcoming.find((u) => u.routine === routine && !u.skipped && u.starts_in_secs > 0);
}

/** Next 24 hours of routine runs, with a Skip per run. Sits above the editor in Settings → Routines. */
export function runsPanel(st: Status, perWeek: number, now: number): string {
  const runs = st.upcoming.length
    ? `<ul class="list">${st.upcoming
        .map((u) => {
          const when = `${dayName(u.starts_at, now)} ${hhmm(u.starts_at)}–${hhmm(u.ends_at)}`;
          let right: string;
          if (u.skipped) right = `<span class="tag">skipped</span>`;
          else if (u.starts_in_secs <= 0) right = `<span class="tag">after this session</span>`;
          else if (skippable(st, u.routine) === u && st.skip_tokens_left > 0)
            right = `<button class="link" data-action="skip" data-routine="${escapeHtml(u.routine)}">Skip</button>`;
          else right = "";
          const soon = u.starts_in_secs > 0 && !u.skipped ? `<div class="small muted">in ${hm(u.starts_in_secs)}</div>` : "";
          return `<li><span class="grow">${escapeHtml(u.routine)}<div class="small muted">${when}</div></span><span class="num">${soon}</span>${right}</li>`;
        })
        .join("")}</ul>`
    : `<p class="muted small">Nothing scheduled in the next 24 hours.</p>`;

  return `<h3>Next 24 hours</h3>
    ${runs}
    <p class="small muted">${st.skip_tokens_left} of ${perWeek} skip token${perWeek === 1 ? "" : "s"} left this week. Loosening changes wait 24 hours.</p>`;
}

function tile(label: string, value: string, loss = false): string {
  return `<div class="tile"><div class="label">${label}</div><div class="value${loss ? " loss" : ""}">${value}</div></div>`;
}

/** Rounded up to a whole hour, at least one. */
const scaleTop = (secs: number) => Math.max(3600, Math.ceil(secs / 3600) * 3600);

function chart(days: Day[]): string {
  const top = scaleTop(Math.max(...days.map((d) => d.focusedSecs)));
  const cols = days
    .map((d, i) => {
      const pct = (d.focusedSecs / top) * 100;
      return `<div class="col" data-day="${i}"><div class="fill" style="height:${pct.toFixed(1)}%"></div></div>`;
    })
    .join("");
  const today = days[days.length - 1].start;
  const labels = days
    .map((d) => {
      const isToday = d.start === today;
      const name = isToday ? "today" : weekday(d.start).slice(0, 2);
      return `<span class="${isToday ? "today" : ""}">${name}<i class="${d.surrendered ? "" : "none"}"></i></span>`;
    })
    .join("");
  return `<div class="chart" role="img" aria-label="Focused time per day, last ${days.length} days">
      <div class="max">${top / 3600}h</div>${cols}</div>
    <div class="axis">${labels}</div>`;
}

/** Tooltip text for one chart column. */
export function dayTip(d: Day): string {
  const date = new Date(d.start * 1000);
  const label = `${weekday(d.start)} ${date.getDate()} ${date.toLocaleString("en", { month: "short" })}`;
  const parts = [`<strong>${label}</strong> · ${hm(d.focusedSecs)} focused`];
  if (d.completed) parts.push(`${d.completed} completed`);
  if (d.surrendered) parts.push(`<span class="loss">${d.surrendered} surrendered</span>`);
  return parts.join(" · ");
}

function outcome(f: Finished): string {
  switch (f.session.state) {
    case "completed":
      return `<span class="tag">done</span>`;
    case "surrendered":
      return `<span class="tag loss">surrendered</span>`;
    default:
      return `<span class="tag">${f.session.state}</span>`;
  }
}

/** The Stats section. Rendered inside the settings sheet; the sheet adds the title. */
export function statsPanel(stats: Stats, sessions: Finished[], world: World | null, now: number): string {
  const n = stats.days.length;
  const tiles = [
    tile("Today", hm(stats.todaySecs)),
    tile("This week", hm(stats.weekSecs)),
    tile(`Last ${n} days`, hm(stats.totalSecs)),
    tile("Completed", String(stats.completed)),
    tile("Surrendered", String(stats.surrendered), stats.surrendered > 0),
    tile("Streak", world ? `${world.streak_days} day${world.streak_days === 1 ? "" : "s"}` : "–"),
  ].join("");
  const ended = stats.completed + stats.surrendered;
  const rate = ended ? Math.round((stats.completed / ended) * 100) : 100;
  const facts = ended
    ? `<p class="small muted">${rate}% of sessions finished · longest ${hm(stats.longestSecs)} · ${stats.fromRoutines} started by routines${
        world ? ` · ${hm(world.focused_secs)} focused in all` : ""
      }</p>`
    : "";
  const recent = sessions.slice(0, 10).map((f) => {
    const s = f.session;
    const label = s.routine ? `${escapeHtml(s.routine)} · ${escapeHtml(s.profile)}` : escapeHtml(s.profile);
    return `<li><span class="num">${dayName(s.started_at, now)} ${hhmm(s.started_at)}</span>
      <span class="grow small muted">${label}</span><span class="num">${hm(s.elapsed_secs)}</span>${outcome(f)}</li>`;
  });
  return `<div class="tiles">${tiles}</div>
    ${facts}
    <h3>Focused per day, last ${Math.min(14, n)} days</h3>
    ${chart(stats.days.slice(-14))}
    <h3>Recent sessions</h3>
    ${recent.length ? `<ul class="list">${recent.join("")}</ul>` : `<p class="muted small">No sessions yet.</p>`}`;
}

/** The Session logs section: the city's event log, newest first. */
export function logsPanel(w: World | null, now: number): string {
  if (!w) return `<p class="muted">Loading…</p>`;
  const items = w.history
    .slice()
    .reverse()
    .map(
      (e) =>
        `<li class="${isLoss(e) ? "loss" : ""}"><time>${dayName(e.ts, now)} ${hhmm(e.ts)}</time><span class="grow">${escapeHtml(describe(w, e))}</span></li>`,
    )
    .join("");
  return items ? `<ul class="list">${items}</ul>` : `<p class="muted">Nothing yet. Complete a session to put up the first building.</p>`;
}

export function notice(p: PendingConfig | null): string {
  if (!p) return "";
  const reasons = p.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("");
  return `<div class="nudge">Config change waiting, applies in ${hm(Math.max(0, p.applies_in_secs))}</div><ul>${reasons}</ul>
    <button class="link" data-action="settings" data-section="session">Review settings</button>`;
}
