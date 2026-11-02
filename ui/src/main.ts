import { DaemonRefusal, Unreachable, call, status as getStatus, history, pendingConfig, routines, world as getWorld } from "./daemon";
import { BUILDINGS, TIERS, ago, clock, describe, escapeHtml, hhmm, hm, isLoss } from "./format";
import { dayTip, notice, routinesPanel, skippable, statsPanel } from "./panels";
import { SURRENDER_PHRASE, type Finished, type RoutineInfo, type SessionInfo, type Status, type World } from "./proto";
import { midnight, summarize, type Stats } from "./stats";
import { City } from "./city/scene";

const $ = <T extends HTMLElement>(sel: string) => document.querySelector(sel) as T;
const hourOverride = new URLSearchParams(location.search).get("hour");

let status: Status | null = null;
let world: World | null = null;
let sessionKey = "";
let controlsKey = "";
let lastWorldFetch = 0;

function localHour(): number {
  if (hourOverride !== null) return Number(hourOverride);
  const d = new Date();
  return d.getHours() + d.getMinutes() / 60;
}

let storyTimer = 0;
/** One line narrating what the city is showing, e.g. a replayed loss. */
function story(text: string) {
  const el = $("#story");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(storyTimer);
  storyTimer = window.setTimeout(() => el.classList.remove("show"), 4200);
}

function banner(text: string | null) {
  const el = $("#banner");
  el.hidden = text === null;
  el.textContent = text ?? "";
}

function renderCity(w: World) {
  const span = (w.next_tier_secs ?? w.focused_secs) - w.tier_floor_secs;
  const pct = w.next_tier_secs === null ? 100 : Math.min(100, ((w.focused_secs - w.tier_floor_secs) / Math.max(1, span)) * 100);
  const next =
    w.next_tier_secs === null
      ? "Top tier reached"
      : `${hm(w.next_tier_secs - w.focused_secs)} to ${TIERS[Math.min(3, w.tier + 1)]}`;
  const intact = w.plots.filter((p) => !p.rubble).length;
  const damaged = w.plots.filter((p) => !p.rubble && p.damage > 0).length;
  const rubble = w.plots.length - intact;
  const condition = [
    `${intact} building${intact === 1 ? "" : "s"}`,
    damaged ? `<span class="loss">${damaged} damaged</span>` : "",
    rubble ? `<span class="loss">${rubble} in rubble</span>` : "",
  ].filter(Boolean);
  const streak = w.streak_days ? ` · streak ${w.streak_days} day${w.streak_days === 1 ? "" : "s"}` : "";
  $("#city").innerHTML = `
    <h1>${TIERS[Math.min(3, w.tier)]}${status?.dry_run ? '<span class="badge">dry run</span>' : ""}</h1>
    <div class="muted">${hm(w.focused_secs)} focused${streak}</div>
    <div class="bar"><div style="width:${pct.toFixed(1)}%"></div></div>
    <div class="small muted">${next}</div>
    <div class="small muted">${condition.join(" · ")}</div>`;
}

function renderHistory(w: World) {
  const now = Math.floor(Date.now() / 1000);
  const items = w.history
    .slice(-5)
    .reverse()
    .map((e) => `<li class="${isLoss(e) ? "loss" : ""}"><time>${ago(now - e.ts)}</time>${escapeHtml(describe(w, e))}</li>`);
  $("#history").innerHTML = items.length
    ? `<strong>Recent</strong><ul>${items.join("")}</ul>`
    : `<span>Empty land. Complete a session to put up the first building.</span>`;
}

function building(w: World | null): string {
  const c = w?.construction;
  if (!c) return "";
  const what = BUILDINGS[Math.min(4, c.grade)];
  if (c.surrendering) return `<div class="loss">The ${what} is about to collapse.</div>`;
  if (c.progress_permille === null) return `<div class="muted">Building a ${what}; it grows while the stopwatch runs.</div>`;
  return `<div class="muted">Building a ${what} · ${Math.floor(c.progress_permille / 10)}%</div>`;
}

function liveSession(s: SessionInfo): string {
  const label = s.routine ? `${escapeHtml(s.routine)} · ${escapeHtml(s.profile)}` : escapeHtml(s.profile);
  let main: string;
  if (s.state === "surrendering") {
    main = `<div class="muted">Surrendering</div><div class="timer warn">${clock(s.surrender_remaining_secs ?? 0)}</div>`;
  } else if (s.kind.type === "countdown") {
    main = `<div class="muted">Focus · ${label}</div><div class="timer">${clock(s.remaining_secs ?? 0)}</div>`;
  } else {
    main = `<div class="muted">Stopwatch · ${label}</div><div class="timer">${clock(s.elapsed_secs)}</div>`;
  }
  const distracted = s.distracted_secs >= 60 ? `<div class="small loss">${hm(s.distracted_secs)} on throttled sites${s.escalation_stage ? ` · throttle stage ${s.escalation_stage}` : ""}</div>` : "";
  const stop =
    s.kind.type === "stopwatch" && s.state === "active" && s.stop_locked_secs > 0
      ? `<div class="small muted">Can stop in ${clock(s.stop_locked_secs)}</div>`
      : "";
  return main + building(world) + distracted + stop;
}

function liveIdle(st: Status): string {
  const parts: string[] = [];
  if (st.nudge) {
    const level = Math.min(3, st.nudge.level);
    parts.push(`<div class="nudge level-${level}">No focus for ${hm(st.nudge.idle_secs)}. Start a session.</div>`);
  } else {
    parts.push(`<div class="muted">No session running.</div>`);
  }
  const next = st.upcoming.find((u) => !u.skipped);
  if (next) {
    const when = next.starts_in_secs > 0 ? `in ${hm(next.starts_in_secs)}` : "now";
    parts.push(`<div class="small muted">Next routine: ${escapeHtml(next.routine)} ${when} (${hm(next.ends_at - next.starts_at)})</div>`);
  }
  return parts.join("");
}

function controls(st: Status): string {
  const s = st.session;
  if (!s) {
    const profiles = st.profiles.map((p) => `<option>${escapeHtml(p)}</option>`).join("");
    const next = st.upcoming.find((u) => !u.skipped && u.starts_in_secs > 0);
    const skip = next && st.skip_tokens_left > 0
      ? `<button class="link" data-action="skip" data-routine="${escapeHtml(next.routine)}">Skip ${escapeHtml(next.routine)} (${st.skip_tokens_left} left this week)</button>`
      : "";
    return `
      <div class="row">
        <button class="primary" data-action="start" data-mins="25">25m</button>
        <button class="primary" data-action="start" data-mins="50">50m</button>
        <button class="primary" data-action="start" data-mins="90">90m</button>
        <button data-action="stopwatch">Stopwatch</button>
      </div>
      <div class="row">
        <input class="minutes" id="mins" type="number" min="1" max="360" placeholder="min" />
        <button data-action="start-custom">Start</button>
        <select id="profile">${profiles}</select>
      </div>
      ${skip}`;
  }
  if (s.state !== "active") return "";
  const stop = s.kind.type === "stopwatch" ? `<button data-action="stop" ${s.stop_locked_secs > 0 ? "disabled" : ""}>Stop</button>` : "";
  return `<div class="row">${stop}<button class="link" data-action="surrender">Surrender…</button></div>`;
}

function renderSession(st: Status) {
  const card = $("#session");
  if (!card.firstElementChild) card.innerHTML = `<div class="live"></div><div class="controls"></div><p class="error" id="action-error"></p>`;
  card.querySelector(".live")!.innerHTML = st.session ? liveSession(st.session) : liveIdle(st);
  // Rebuilt only when its shape changes, so typing in it survives polls.
  const s = st.session;
  const key = s ? `${s.id}:${s.state}:${s.kind.type}:${s.stop_locked_secs > 0}` : `idle:${st.profiles}:${st.upcoming.map((u) => u.routine + u.skipped)}:${st.skip_tokens_left}`;
  if (key !== controlsKey) {
    controlsKey = key;
    card.querySelector(".controls")!.innerHTML = controls(st);
  }
}

function actionError(text: string) {
  const el = document.getElementById("action-error");
  if (el) el.textContent = text;
}

async function act(fn: () => Promise<unknown>) {
  actionError("");
  try {
    await fn();
  } catch (e) {
    actionError(e instanceof Error ? e.message : String(e));
  }
  lastWorldFetch = 0;
  await poll();
}

function start(kind: { type: "countdown"; secs: number } | { type: "stopwatch" }) {
  const profile = (document.getElementById("profile") as HTMLSelectElement | null)?.value ?? null;
  return act(() => call({ type: "start", kind, profile }));
}

$("#session").addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest("button");
  if (!btn) return;
  switch (btn.dataset.action) {
    case "start":
      return start({ type: "countdown", secs: Number(btn.dataset.mins) * 60 });
    case "start-custom": {
      const mins = Number(($("#mins") as HTMLInputElement).value);
      if (!(mins >= 1)) return actionError("Enter the length in minutes.");
      return start({ type: "countdown", secs: Math.round(mins * 60) });
    }
    case "stopwatch":
      return start({ type: "stopwatch" });
    case "stop":
      return act(() => call({ type: "stop" }));
    case "skip":
      return confirmSkip(btn.dataset.routine!);
    case "surrender":
      return openSurrender();
  }
});

// Surrender: the phrase has to be typed, so paste and drop are refused.
const dialog = $("#surrender") as HTMLDialogElement;
const input = $("#phrase-input") as HTMLInputElement;
const confirmBtn = $("#surrender-confirm") as HTMLButtonElement;
$("#phrase").textContent = SURRENDER_PHRASE;
for (const ev of ["paste", "drop"]) input.addEventListener(ev, (e) => e.preventDefault());
input.addEventListener("input", () => (confirmBtn.disabled = input.value !== SURRENDER_PHRASE));
function openSurrender() {
  input.value = "";
  confirmBtn.disabled = true;
  $("#surrender-error").textContent = "";
  dialog.showModal();
}
dialog.addEventListener("close", () => {
  if (dialog.returnValue === "confirm" && input.value === SURRENDER_PHRASE) {
    void act(() => call({ type: "surrender", phrase: input.value }));
  }
});

// Skipping costs a token and can't be undone, so it is confirmed (the CLI
// asks at a terminal for the same reason).
const skipDialog = $("#skip") as HTMLDialogElement;
let skipRoutine = "";
function confirmSkip(routine: string) {
  const u = status && skippable(status, routine);
  if (!status || !u) return;
  skipRoutine = routine;
  const left = status.skip_tokens_left;
  $("#skip-title").textContent = `Skip ${routine}?`;
  $("#skip-text").textContent =
    `The run at ${hhmm(u.starts_at)} (${hm(u.ends_at - u.starts_at)}) won't start. ` +
    `This uses one of your ${left} skip token${left === 1 ? "" : "s"} left this week, and can't be undone.`;
  skipDialog.returnValue = "";
  skipDialog.showModal();
}
skipDialog.addEventListener("close", () => {
  if (skipDialog.returnValue === "confirm") void act(() => call({ type: "skip", routine: skipRoutine }));
});

// Routines and Stats panels. Their data is fetched when opened and refreshed
// with the world; the panel is redrawn from it on every poll.
type View = "routines" | "stats" | null;
let view: View = null;
let routineList: { routines: RoutineInfo[]; skip_tokens_per_week: number } | null = null;
let past: Finished[] = [];
let stats: Stats | null = null;
let panelKey = "";
const STATS_DAYS = 28;

async function loadPanel() {
  const now = Math.floor(Date.now() / 1000);
  if (view === "routines") routineList = await routines();
  if (view === "stats") {
    past = await history(midnight(now, STATS_DAYS - 1));
    stats = summarize(past, now, STATS_DAYS);
  }
}

function renderPanel() {
  const panel = $("#panel");
  for (const b of document.querySelectorAll<HTMLButtonElement>("#tabs button")) b.classList.toggle("on", b.dataset.view === view);
  const now = Math.floor(Date.now() / 1000);
  let html = "";
  if (view === "routines" && routineList && status) html = routinesPanel(routineList.routines, routineList.skip_tokens_per_week, status, now);
  if (view === "stats" && stats) html = statsPanel(stats, past, world, now);
  panel.hidden = !html;
  // Only touched when the text changes, so hover and scroll survive polls.
  if (html !== panelKey) {
    panelKey = html;
    panel.innerHTML = html;
  }
}

async function open(next: View) {
  view = view === next ? null : next;
  try {
    await loadPanel();
  } catch (e) {
    banner(e instanceof Error ? e.message : String(e));
  }
  renderPanel();
}

$("#tabs").addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest("button");
  if (btn) void open(btn.dataset.view as View);
});
$("#panel").addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest("button");
  if (btn?.dataset.action === "close") void open(view);
  if (btn?.dataset.action === "skip") confirmSkip(btn.dataset.routine!);
});
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && view && !document.querySelector("dialog[open]")) void open(view);
});

// Chart tooltip.
const tip = $("#tip");
$("#panel").addEventListener("mousemove", (ev) => {
  const col = (ev.target as HTMLElement).closest<HTMLElement>(".col");
  const day = col && stats?.days.slice(-14)[Number(col.dataset.day)];
  tip.hidden = !day;
  if (!day) return;
  tip.innerHTML = dayTip(day);
  tip.style.left = `${Math.min(ev.clientX + 12, innerWidth - tip.offsetWidth - 8)}px`;
  tip.style.top = `${ev.clientY + 14}px`;
});
$("#panel").addEventListener("mouseleave", () => (tip.hidden = true));

let skyline: City | null = null;
let rendererError: string | null = null;
let busy = false;

async function poll() {
  if (busy) return;
  busy = true;
  try {
    status = await getStatus();
    const s = status.session;
    const key = s ? `${s.id}:${s.state}` : "none";
    const now = Date.now();
    if (key !== sessionKey || now - lastWorldFetch > 5000) {
      sessionKey = key;
      lastWorldFetch = now;
      world = await getWorld();
      renderCity(world);
      renderHistory(world);
      $("#notice").innerHTML = notice(await pendingConfig());
      if (view) await loadPanel();
    }
    renderSession(status);
    renderPanel();
    banner(rendererError);
    if (world) skyline?.update(world, localHour(), s?.elapsed_secs ?? 0);
  } catch (e) {
    if (e instanceof Unreachable) banner(`Can't reach deepworkd. ${e.message}`);
    else if (e instanceof DaemonRefusal) banner(e.message);
    else banner(String(e));
  } finally {
    busy = false;
  }
}

window.addEventListener("error", (e) => banner(`UI error: ${e.message}`));
window.addEventListener("unhandledrejection", (e) => banner(`UI error: ${e.reason}`));
// The HUD works without the skyline, so a renderer failure only costs the picture.
try {
  skyline = await City.create($("#stage"), story);
  if (!("__TAURI_INTERNALS__" in window)) Object.assign(window, { city: skyline });
} catch (e) {
  console.error(e);
  rendererError = `Skyline unavailable: ${e}`;
}
await poll();
setInterval(poll, 1000);
// `VITE_FPS=1 bun run build` adds a frame-rate readout, for tuning.
if (import.meta.env.VITE_FPS && skyline) {
  const el = document.createElement("div");
  el.style.cssText = "position:fixed;left:8px;bottom:8px;font:12px monospace;color:#9f9;z-index:9";
  document.body.append(el);
  setInterval(() => (el.textContent = `${skyline!.fps.toFixed(0)} fps`), 500);
}
