// The mayor's desk (docs/progression.md): the residents' needs, the sites,
// the blueprint shop, a building's deed and its hover tag. Text only; main.ts
// wires the clicks to the daemon, which decides everything.
import { TIERS, ago, escapeHtml, hm } from "./format";
import type { BlueprintInfo, NeedInfo, Plot, SessionInfo, SiteInfo, World } from "./proto";

const KIND_NAMES: Record<string, string> = {
  cottage: "Cottage", shop: "Shop", workshop: "Workshop", apartment: "Apartments", office: "Office", tower: "Tower",
  water: "Water", power: "Power", school: "School", clinic: "Clinic", fire_station: "Fire station", square: "Square",
  police: "Police", library: "Library", park: "Park", hospital: "Hospital", city_hall: "City hall",
};
const DISTRICTS: Record<string, string> = { village: "village", main_street: "main street", works: "the works", civic: "civic", downtown: "downtown" };

const blueprint = (w: World, id: string | null | undefined) => (id ? w.blueprints?.find((b) => b.id === id) : undefined);
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** A small outline of a kind of building, for the shop's tiles and locked silhouettes. */
export function silhouette(kind: string): string {
  const shapes: Record<string, string> = {
    cottage: "M6 30V17l12-9 12 9v13Z M22 11V6h3v7",
    shop: "M5 30V12h26v18Z M3 16h30l-2 4H5Z",
    workshop: "M4 30V16l7-5v5l7-5v5l7-5v19Z M27 30V5h3v25",
    apartment: "M8 30V6h20v24Z",
    office: "M11 30V3h14v27Z",
    tower: "M12 30V10h12v20Z M14 10V5h8v5 M17 5V1h2v4",
  };
  const d = shapes[kind] ?? "M6 30V14h24v16Z";
  return `<svg class="sil" viewBox="0 0 36 32" width="36" height="32" aria-hidden="true"><path d="${d}"/></svg>`;
}

function siteBoard(s: SiteInfo, extraSecs: number, actions: string): string {
  const done = Math.min(s.build_secs, s.done_secs + extraSecs);
  const pct = (done / Math.max(1, s.build_secs)) * 100;
  return `<div class="site">
      <div class="site-head"><strong>${escapeHtml(s.name)}</strong>${actions}</div>
      <div class="bar"><div style="width:${pct.toFixed(1)}%"></div></div>
      <div class="small muted">${hm(done)} of ${hm(s.build_secs)}</div>
    </div>`;
}

function needRow(w: World, n: NeedInfo, active: SiteInfo | undefined): string {
  if (n.lots_done >= n.lots) return `<div class="need done"><span>✓ ${escapeHtml(n.title)}</span></div>`;
  const building = active?.need === n.id;
  const count = n.lots > 1 ? `${n.lots_done} of ${n.lots} · ` : "";
  let act: string;
  if (building) act = `<span class="tag on">Building</span>`;
  else if (!n.designed || n.fits.length) {
    const pick =
      n.designed && n.fits.length > 1 && !n.site
        ? `<select data-need-design="${escapeHtml(n.id)}" aria-label="Blueprint">${n.fits
            .map((id) => `<option value="${escapeHtml(id)}">${escapeHtml(blueprint(w, id)?.name ?? id)}</option>`)
            .join("")}</select>`
        : "";
    act = `${pick}<button data-action="choose" data-need="${escapeHtml(n.id)}">${n.site ? "Resume" : "Build"}</button>`;
  } else {
    const cheapest = (w.blueprints ?? []).filter((b) => n.fits_locked.includes(b.id) && b.unlocked).sort((a, b) => a.price - b.price)[0];
    act = `<span class="small muted">Needs a blueprint${cheapest ? ` · from ${cheapest.price} coins` : ""}</span><button class="link" data-action="shop">Shop</button>`;
  }
  return `<div class="need${building ? " building" : ""}">
      <div class="need-head"><strong>${escapeHtml(n.title)}</strong><span class="small muted">${count}${hm(n.build_secs)}${n.lots > 1 ? " each" : ""}</span></div>
      <div class="words">“${escapeHtml(n.words)}”</div>
      <div class="need-act">${act}</div>
    </div>`;
}

/** The desk card: the site board during a session, the residents' needs between sessions. */
export function deskHtml(w: World, session: SessionInfo | null): string {
  if (!w.needs) return "";
  const active = w.sites?.find((s) => s.active);
  if (session) {
    const c = w.construction;
    if (!c) return `<p class="eyebrow">Under construction</p><div class="small muted">No site chosen: this session banks crew hours for the next one.</div>`;
    const site: SiteInfo = active ?? { index: c.index, lot: c.lot ?? "", need: "", name: c.name ?? "", kind: c.kind ?? "", design: c.design ?? null, done_secs: 0, build_secs: c.remaining_secs ?? 0, active: true, seed: c.seed };
    const extra = session.state === "active" ? session.elapsed_secs : 0;
    const note = session.state === "surrendering" ? `<div class="small loss">Surrendering: this session's work will be lost.</div>` : `<div class="small muted">Lands when the session completes.</div>`;
    return `<p class="eyebrow">Under construction</p>${siteBoard(site, extra, "")}${note}`;
  }
  const parts: string[] = [];
  parts.push(`<div class="desk-head"><p class="eyebrow">The residents ask</p><span class="coins" title="Coins to spend on blueprints">${w.coins ?? 0} coins</span></div>`);
  const open = w.needs.filter((n) => n.lots_done < n.lots);
  if (!active && open.length) {
    parts.push(`<div class="what-next"><strong>What next?</strong> Pick a need; the plan picks the lot.${w.idle_secs ? ` ${hm(w.idle_secs)} of crew hours are waiting.` : ""}</div>`);
  }
  if (active) parts.push(siteBoard(active, 0, `<button class="link" data-action="pause">Pause</button>`));
  const paused = (w.sites ?? []).filter((s) => !s.active);
  if (paused.length) {
    parts.push(`<div class="small muted paused">Paused: ${paused.map((s) => `${escapeHtml(s.name)} (${hm(s.done_secs)} of ${hm(s.build_secs)})`).join(", ")}</div>`);
  }
  parts.push(`<div class="needs">${w.needs.map((n) => needRow(w, n, active)).join("")}</div>`);
  if (w.auto) parts.push(`<div class="small muted">Until you choose, the plan builds itself in order.</div>`);
  const next = w.next_needs?.length ? `<div class="small muted">Then the ${TIERS[Math.min(3, w.tier + 1)]}: ${w.next_needs.slice(0, 4).map(escapeHtml).join(", ")}${w.next_needs.length > 4 ? ", …" : ""}</div>` : "";
  parts.push(`<div class="desk-foot">${next}<button data-action="shop">Blueprints</button></div>`);
  return parts.join("");
}

function tile(w: World, b: BlueprintInfo, closed: boolean): string {
  const coins = w.coins ?? 0;
  let state: string;
  if (b.owned) state = `<span class="tag pass">Owned${b.built ? ` · ${b.built} built` : ""}</span>`;
  else if (!b.unlocked) state = `<span class="small muted">From the ${TIERS[Math.min(3, b.level)]} · ${b.price} coins</span>`;
  else if (coins < b.price) state = `<span class="small muted">${b.price} coins · ${b.price - coins} more to go</span>`;
  else state = `<button class="primary" data-action="buy" data-blueprint="${escapeHtml(b.id)}" ${closed ? "disabled" : ""}>Buy · ${b.price}</button>`;
  return `<div class="bp${b.unlocked ? "" : " locked"}${b.owned ? " owned" : ""}">
      ${silhouette(b.kind)}
      <div class="bp-text">
        <strong>${b.unlocked ? escapeHtml(b.name) : escapeHtml(b.name)}</strong>
        <div class="small muted">${KIND_NAMES[b.kind] ?? b.kind} · ${b.districts.map((d) => DISTRICTS[d] ?? d).join(", ")}</div>
        <div class="bp-state">${state}</div>
      </div>
    </div>`;
}

/** The shop: this level's blueprints for sale, later ones as locked silhouettes. */
export function shopHtml(w: World, inSession: boolean): string {
  const list = w.blueprints ?? [];
  const closed = inSession ? `<p class="small muted">The shop opens when the session ends.</p>` : "";
  return `${closed}<div class="bp-grid">${list.map((b) => tile(w, b, inSession)).join("")}</div>`;
}

function day(ts: number): string {
  const d = new Date(ts * 1000);
  return `${d.getDate()} ${d.toLocaleString("en", { month: "short" })}`;
}

function span(from: number, to: number): string {
  const days = Math.round((new Date(to * 1000).setHours(0, 0, 0, 0) - new Date(from * 1000).setHours(0, 0, 0, 0)) / 86400_000);
  return days <= 0 ? "in one day" : `over ${plural(days + 1, "day")}`;
}

/** The hover tag: name and one line. */
export function tagHtml(w: World, index: number): string {
  const p = w.plots.find((p) => p.index === index);
  if (p) {
    const m = p.memory;
    const sessions = m ? new Set(m.parts.map((x) => x.session_id)).size : 0;
    const line = m ? `Built ${day(p.built_at)} · ${plural(sessions, "session")} · ${hm(m.focused_secs)}` : `Built ${day(p.built_at)}`;
    const hurt = p.damage >= 3 ? " · in ruins" : p.damage ? " · damaged" : "";
    return `<strong>${escapeHtml(p.name ?? `Plot ${index + 1}`)}${p.shiny ? " ✦" : ""}</strong><div>${line}${hurt}</div>`;
  }
  const s = w.sites?.find((s) => s.index === index);
  if (s) return `<strong>${escapeHtml(s.name)}</strong><div>Under construction · ${hm(s.done_secs)} of ${hm(s.build_secs)}${s.active ? "" : " · paused"}</div>`;
  const c = w.construction;
  if (c && c.index === index) return `<strong>${escapeHtml(c.name ?? "Construction site")}</strong><div>Under construction</div>`;
  return "";
}

const CAUSES: Record<string, string> = {
  surrendered: "after a surrender",
  tamper: "in an earthquake (tampering)",
  escalation_denied: "after a refused root attempt",
  clock_jump: "after a wall clock jump",
  tunnel: "after a proxy around the throttle",
};

/** The deed: everything a building remembers of how it was built. */
export function deedHtml(w: World, p: Plot, now: number): string {
  const m = p.memory;
  const need = w.needs?.find((n) => n.id === p.need);
  const design = blueprint(w, p.design);
  const what = [need?.title, design?.name ?? KIND_NAMES[p.kind ?? ""]].filter(Boolean).map((s) => escapeHtml(s!)).join(" · ");
  const rows: string[] = [];
  if (m) {
    const sessions = new Set(m.parts.map((x) => x.session_id)).size;
    const longest = Math.max(0, ...m.parts.map((x) => x.session_secs));
    rows.push(`<div class="deed-stats">
        <div><span class="label">Built</span>${day(p.built_at)}, ${span(m.started_at, p.built_at)}</div>
        <div><span class="label">Focus</span>${hm(m.focused_secs)}</div>
        <div><span class="label">Sessions</span>${sessions}</div>
        <div><span class="label">Longest</span>${hm(longest)}</div>
      </div>`);
    const most = Math.max(1, ...m.parts.map((x) => x.secs));
    rows.push(`<div class="strip" aria-label="Sessions that built it">${m.parts
      .map((x) => `<div title="${day(x.ts)} · ${hm(x.secs)} of a ${hm(x.session_secs)} session" style="height:${Math.max(8, (x.secs / most) * 100).toFixed(0)}%"></div>`)
      .join("")}</div>`);
    const firsts: string[] = [];
    if (m.first) firsts.push("The first building of the city");
    if (p.shiny) firsts.push("Came out rare ✦");
    if (m.streak_at_finish >= 7) firsts.push(`Finished on a ${m.streak_at_finish}-day streak`);
    if (firsts.length) rows.push(`<ul class="firsts">${firsts.map((f) => `<li>${f}</li>`).join("")}</ul>`);
    if (m.scars.length) {
      rows.push(`<ul class="scars">${m.scars
        .map((s) => (s.repaired ? `<li class="gain">Repaired ${day(s.ts)}${s.damage ? ` (damage ${s.damage} left)` : ""}</li>` : `<li class="loss">${s.damage >= 3 ? "Ruined" : "Damaged"} ${day(s.ts)} ${CAUSES[s.cause] ?? ""}</li>`))
        .join("")}</ul>`);
    }
  }
  const state = p.damage >= 3 ? `<span class="tag loss">In ruins</span>` : p.damage ? `<span class="tag loss">Damaged</span>` : "";
  return `<p class="eyebrow">${escapeHtml(p.address ?? `Plot ${p.index + 1}`)}</p>
    <div class="deed-name">
      <h2 id="deed-title">${escapeHtml(p.name ?? `Plot ${p.index + 1}`)}</h2>${state}
      <button class="link" data-action="rename-open">Rename</button>
    </div>
    <form class="rename" data-lot="${escapeHtml(p.lot ?? "")}" hidden>
      <input name="name" maxlength="40" value="${escapeHtml(p.name ?? "")}" aria-label="Name" />
      <button class="primary" type="submit">Save</button>
    </form>
    <div class="small muted">${what}</div>
    ${rows.join("")}
    <div class="small muted">Finished ${ago(now - p.built_at)} ago.</div>`;
}

/**
 * The near-miss prompt: a countdown about to end a little short of a finish
 * line. Seconds to add and the building's name, or null.
 */
export function nearMiss(w: World | null, s: SessionInfo | null): { secs: number; name: string } | null {
  const c = w?.construction;
  if (!c || !s || s.state !== "active" || s.kind.type !== "countdown" || c.remaining_secs === undefined) return null;
  const left = s.remaining_secs ?? 0;
  if (left > 5 * 60) return null;
  const short = c.remaining_secs - s.kind.secs;
  if (short <= 0 || short > 20 * 60) return null;
  return { secs: Math.ceil(short / 60) * 60, name: c.name ?? "the building" };
}

/**
 * The level-up card: what the settlement became, what its residents ask for
 * now and the blueprints that went on sale. `tier` is the level reached; the
 * needs and blueprints are only named when it is the world's current level
 * (a replay can pass through an earlier one).
 */
export function levelUpHtml(w: World, tier: number): string {
  const from = TIERS[Math.max(0, Math.min(3, tier - 1))];
  const to = TIERS[Math.min(3, tier)];
  const current = tier === w.tier;
  const needs = current ? (w.needs ?? []) : [];
  const fresh = current ? (w.blueprints ?? []).filter((b) => b.level === tier) : [];
  const asks = needs.length
    ? `<p class="small muted">Its residents ask for:</p><ul class="levelup-needs">${needs
        .map((n) => `<li><span>${escapeHtml(n.title)}</span>${n.lots > 1 ? `<span class="num">${n.lots}</span>` : ""}</li>`)
        .join("")}</ul>`
    : "";
  const shop = fresh.length
    ? `<p class="small muted">${plural(fresh.length, "new blueprint")} for sale: ${fresh.map((b) => escapeHtml(b.name)).join(", ")}.</p>`
    : "";
  return `
    <div class="eyebrow">Level up</div>
    <h2>${from} <span class="arrow" aria-hidden="true">→</span> ${to}</h2>
    <p>Every need was met. Your ${from.toLowerCase()} is a ${to.toLowerCase()} now.</p>
    ${asks}${shop}
    <div class="row">
      ${fresh.length ? '<button class="primary" data-action="levelup-shop">See the blueprints</button>' : ""}
      <button data-action="levelup-close">${fresh.length ? "Later" : "Back to the city"}</button>
    </div>`;
}
