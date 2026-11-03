// The progress sheet: the read-only Stats and Session logs views, opened from
// their own button next to the cog. Nothing here edits config; the HUD poll
// pushes fresh data in and the open section re-renders only when it changed.
import { history } from "./daemon";
import { escapeHtml } from "./format";
import { dayTip, logsPanel, statsPanel } from "./panels";
import { midnight, summarize, type Stats } from "./stats";
import type { Finished, World } from "./proto";

export type ProgressSection = "stats" | "logs";

const SECTIONS: { key: ProgressSection; label: string; blurb: string }[] = [
  { key: "stats", label: "Stats", blurb: "Focused time and outcomes" },
  { key: "logs", label: "Session logs", blurb: "Every build, collapse and quake" },
];

const STATS_DAYS = 28;

let section: ProgressSection = "stats";
let world: World | null = null;
let past: Finished[] = [];
let stats: Stats | null = null;
let statsError = "";
let statsFetchedAt = 0;
let statsBusy = false;
/** Last HTML written to the body, so polls only touch changed text. */
let viewKey = "";

const dialog = () => document.querySelector<HTMLDialogElement>("#progress")!;
const main = () => document.querySelector<HTMLElement>("#progress-main")!;
const nav = () => document.querySelector<HTMLElement>("#progress-nav")!;

function statsSection(): string {
  const title = `<div class="sheet-title"><p class="eyebrow">Progress</p><h2>Stats</h2>
    <p class="muted">Focused time per day, completed and surrendered sessions, streak.</p></div>`;
  if (statsError) return `${title}<p class="error">Stats unavailable: ${escapeHtml(statsError)}</p>`;
  if (!stats) return `${title}<p class="muted">Loading stats…</p>`;
  return title + statsPanel(stats, past, world, Math.floor(Date.now() / 1000));
}

function logsSection(): string {
  const title = `<div class="sheet-title"><p class="eyebrow">Progress</p><h2>Session logs</h2>
    <p class="muted">The city's event log, newest first: what every session — or bypass — did.</p></div>`;
  return title + logsPanel(world, Math.floor(Date.now() / 1000));
}

function body(): string {
  return section === "stats" ? statsSection() : logsSection();
}

function render() {
  nav().innerHTML = SECTIONS.map(
    (s) =>
      `<button class="nav-item${s.key === section ? " on" : ""}" data-action="section" data-section="${s.key}">
        <span class="nav-label">${s.label}</span><span class="nav-blurb">${s.blurb}</span>
      </button>`,
  ).join("");
  viewKey = body();
  main().innerHTML = viewKey;
}

/** Rewrites the open section only when its HTML changed, so polls never
 * reset scroll or hover. */
function updateView() {
  if (!dialog().open) return;
  const html = body();
  if (html === viewKey) return;
  viewKey = html;
  main().innerHTML = html;
}

/** Refetches history and re-renders the Stats section if it is showing. */
async function refreshStats() {
  if (statsBusy) return;
  statsBusy = true;
  try {
    const now = Math.floor(Date.now() / 1000);
    past = await history(midnight(now, STATS_DAYS - 1));
    stats = summarize(past, now, STATS_DAYS);
    statsError = "";
  } catch (e) {
    statsError = e instanceof Error ? e.message : String(e);
  } finally {
    statsFetchedAt = Date.now();
    statsBusy = false;
  }
  updateView();
}

/** Called by the HUD poll: keeps the open section's live data fresh. */
export function progressUpdate(w: World | null): void {
  if (w) world = w;
  if (!dialog().open) return;
  if (section === "stats" && Date.now() - statsFetchedAt > 4000) void refreshStats();
  else updateView();
}

export function openProgress(at: ProgressSection = "stats") {
  section = at;
  render();
  if (section === "stats") void refreshStats();
  if (!dialog().open) dialog().showModal();
}

function start() {
  const d = dialog();
  d.addEventListener("click", (ev) => {
    const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-action]");
    if (!btn) return;
    if (btn.dataset.action === "close-progress") return d.close();
    if (btn.dataset.action === "section") {
      section = btn.dataset.section as ProgressSection;
      render();
      if (section === "stats") void refreshStats();
    }
  });

  // Chart tooltip for the Stats section.
  const tip = document.querySelector<HTMLElement>("#tip")!;
  const mainEl = main();
  mainEl.addEventListener("mousemove", (ev) => {
    const col = (ev.target as Element).closest<HTMLElement>(".col");
    const day = col && stats?.days.slice(-14)[Number(col.dataset.day)];
    tip.hidden = !day;
    if (!day) return;
    tip.innerHTML = dayTip(day);
    tip.style.left = `${Math.min(ev.clientX + 12, innerWidth - tip.offsetWidth - 8)}px`;
    tip.style.top = `${ev.clientY + 14}px`;
  });
  mainEl.addEventListener("mouseleave", () => (tip.hidden = true));
  d.addEventListener("close", () => (tip.hidden = true));
}

start();
