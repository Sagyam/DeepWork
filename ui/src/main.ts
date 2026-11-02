import { DaemonRefusal, Unreachable, call, status as getStatus, history, pendingConfig, routines, world as getWorld } from "./daemon";
import { BUILDINGS, TIERS, ago, clock, describe, escapeHtml, hhmm, hm, isLoss } from "./format";
import { dayTip, notice, routinesPanel, skippable, statsPanel } from "./panels";
import { SURRENDER_PHRASE, type Finished, type RoutineInfo, type SessionInfo, type Status, type World } from "./proto";
import { midnight, summarize, type Stats } from "./stats";
import { openSettings, type SettingsSection } from "./settings";
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
  const f = st.free;
  if (f?.spending) {
    parts.push(`<div class="muted">Free time · throttle lifted</div><div class="timer free">${clock(f.stops_in_secs ?? 0)}</div>`);
  } else if (f) {
    const state = f.throttled ? "Distractions are slowed down." : "";
    parts.push(`<div class="small muted">${state} Free time banked: ${hm(f.balance_secs)} (${f.free_mins_per_hour} min per focused hour)</div>`);
  }
  return parts.join("");
}

type StartMode = "timer" | "stopwatch";
const PRESETS = [25, 50, 90];
let startMode: StartMode = "timer";
let startMins = 25;
let startProfile: string | null = null;

function startLabel(): string {
  if (startMode === "stopwatch") return "Start stopwatch";
  if (!(startMins >= 1)) return "Start focus";
  return `Start ${startMins}-minute focus`;
}

function controls(st: Status): string {
  const s = st.session;
  if (!s) {
    if (startProfile && !st.profiles.includes(startProfile)) startProfile = null;
    const profiles = st.profiles
      .map((p) => `<option${p === startProfile ? " selected" : ""}>${escapeHtml(p)}</option>`)
      .join("");
    const next = st.upcoming.find((u) => !u.skipped && u.starts_in_secs > 0);
    const skip = next && st.skip_tokens_left > 0
      ? `<div class="start-extra"><button class="link" data-action="skip" data-routine="${escapeHtml(next.routine)}">Skip ${escapeHtml(next.routine)} (${st.skip_tokens_left} left this week)</button></div>`
      : "";
    const chips = PRESETS.map(
      (m) =>
        `<button class="chip${startMode === "timer" && startMins === m ? " on" : ""}" data-action="mins" data-mins="${m}"><b>${m}</b><span>min</span></button>`,
    ).join("");
    const custom = !PRESETS.includes(startMins);
    return `<div class="start-block">
        <div class="seg start-mode">
          <button class="${startMode === "timer" ? "on" : ""}" data-action="mode" data-mode="timer">Focus timer</button>
          <button class="${startMode === "stopwatch" ? "on" : ""}" data-action="mode" data-mode="stopwatch">Stopwatch</button>
        </div>
        <div class="chips"${startMode === "stopwatch" ? " hidden" : ""}>
          ${chips}
          <label class="chip custom${custom ? " on" : ""}">
            <input id="mins" type="number" min="1" max="360" value="${startMins}" aria-label="Custom minutes" />
            <span>min</span>
          </label>
        </div>
        <label class="start-profile"><span>Profile</span><select id="profile">${profiles}</select></label>
        <button class="start-button primary" data-action="start-selected">${startLabel()}</button>
      </div>
      ${skip}${freeControls(st)}`;
  }
  if (s.state !== "active") return "";
  const stop = s.kind.type === "stopwatch" ? `<button data-action="stop" ${s.stop_locked_secs > 0 ? "disabled" : ""}>Stop</button>` : "";
  return `<div class="row">${stop}<button class="link" data-action="surrender">Surrender…</button></div>`;
}

function freeControls(st: Status): string {
  const f = st.free;
  if (!f) return "";
  if (f.spending) return `<div class="row"><button data-action="free-stop">Back to focus (bank the rest)</button></div>`;
  if (f.balance_secs < 60) return "";
  return `<div class="row"><button data-action="free">Spend free time (${hm(f.balance_secs)})</button></div>`;
}

function renderSession(st: Status) {
  const card = $("#session");
  if (!card.firstElementChild) card.innerHTML = `<div class="live"></div><div class="controls"></div><p class="error" id="action-error"></p>`;
  card.querySelector(".live")!.innerHTML = st.session ? liveSession(st.session) : liveIdle(st);
  // Rebuilt only when its shape changes, so typing in it survives polls.
  const s = st.session;
  const key = s ? `${s.id}:${s.state}:${s.kind.type}:${s.stop_locked_secs > 0}` : `idle:${st.profiles}:${st.upcoming.map((u) => u.routine + u.skipped)}:${st.skip_tokens_left}:${st.free?.spending}:${Math.floor((st.free?.balance_secs ?? 0) / 60)}`;
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
  const profile =
    startProfile ?? (document.getElementById("profile") as HTMLSelectElement | null)?.value ?? null;
  return act(() => call({ type: "start", kind, profile }));
}

function redrawControls() {
  if (!status) return;
  actionError("");
  controlsKey = "";
  renderSession(status);
}

$("#session").addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest("button");
  if (!btn) return;
  switch (btn.dataset.action) {
    case "mode":
      startMode = btn.dataset.mode as StartMode;
      return redrawControls();
    case "mins":
      startMode = "timer";
      startMins = Number(btn.dataset.mins);
      return redrawControls();
    case "start-selected":
      if (startMode === "stopwatch") return start({ type: "stopwatch" });
      if (!(startMins >= 1)) return actionError("Enter the length in minutes.");
      return start({ type: "countdown", secs: Math.round(startMins * 60) });
    case "stop":
      return act(() => call({ type: "stop" }));
    case "skip":
      return confirmSkip(btn.dataset.routine!);
    case "free":
      return act(() => call({ type: "free", secs: null }));
    case "free-stop":
      return act(() => call({ type: "free_stop" }));
    case "surrender":
      return openSurrender();
  }
});

// The custom length updates the button in place, so typing never loses focus.
$("#session").addEventListener("change", (ev) => {
  const el = ev.target as HTMLSelectElement;
  if (el.id === "profile") startProfile = el.value;
});

$("#session").addEventListener("input", (ev) => {
  const el = ev.target as HTMLInputElement;
  if (el.id !== "mins") return;
  startMins = Number(el.value);
  const button = document.querySelector<HTMLButtonElement>(".start-button");
  if (button) button.textContent = startLabel();
  for (const chip of document.querySelectorAll<HTMLElement>(".chip[data-mins]")) {
    chip.classList.toggle("on", Number(chip.dataset.mins) === startMins);
  }
  document.querySelector(".chip.custom")?.classList.toggle("on", !PRESETS.includes(startMins));
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
  if (!btn) return;
  if (btn.dataset.settings) {
    void openSettings(btn.dataset.settings as SettingsSection);
    return;
  }
  void open(btn.dataset.view as View);
});

// Settings and imports can change the world or the pending config.
window.addEventListener("deepwork:changed", () => {
  lastWorldFetch = 0;
  void poll();
});
$("#notice").addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest("button");
  if (btn?.dataset.action === "settings") {
    void openSettings((btn.dataset.section as SettingsSection) ?? "session");
  }
});
$("#panel").addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest("button");
  if (btn?.dataset.action === "close") void open(view);
  if (btn?.dataset.action === "skip") confirmSkip(btn.dataset.routine!);
  if (btn?.dataset.action === "settings") {
    void openSettings((btn.dataset.section as SettingsSection) ?? "session");
  }
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
