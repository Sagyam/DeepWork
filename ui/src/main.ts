import { DaemonRefusal, Unreachable, call, status as getStatus, pendingConfig, world as getWorld } from "./daemon";
import { TIERS, clock, escapeHtml, hm } from "./format";
import { deedHtml, deskHtml, levelUpHtml, nearMiss, shopHtml, tagHtml, townHtml } from "./desk";
import { notice } from "./panels";
import { SURRENDER_PHRASE, type SessionInfo, type Status, type World } from "./proto";
import { openProgress, progressUpdate } from "./progress";
import { confirmSkip, hudUpdate, openSettings, type SettingsSection } from "./settings";
import { City } from "./city/scene";
import { modelsStatus, type ModelsStatus } from "./models";

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

let levelTimer = 0;
/** The level-up card over the scene; it goes by itself after a while. */
function levelUp(tier: number) {
  if (!world) return;
  const el = $("#levelup");
  el.innerHTML = levelUpHtml(world, tier);
  el.hidden = false;
  // Restart the entrance on a second level in a row.
  el.classList.remove("show");
  void el.offsetWidth;
  el.classList.add("show");
  clearTimeout(levelTimer);
  levelTimer = window.setTimeout(closeLevelUp, 20000);
}

function closeLevelUp() {
  clearTimeout(levelTimer);
  $("#levelup").hidden = true;
}

$("#levelup").addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-action]");
  if (!btn) return;
  closeLevelUp();
  if (btn.dataset.action === "levelup-shop") openShop();
});

function banner(text: string | null) {
  const el = $("#banner");
  el.hidden = text === null;
  el.textContent = text ?? "";
}

/** The city's models (models.ts) until they are all there and the city is drawn. */
let models: ModelsStatus | null = null;

function modelsLine(): string {
  const mb = (n: number) => (n / 1e6).toFixed(0);
  switch (models?.state) {
    case "downloading":
      return `<div class="small muted">Downloading the city: ${mb(models.done)} of ${mb(models.total)} MB</div>`;
    case "retrying":
      return `<div class="small muted" title="${escapeHtml(models.error)}">City download stalled, retrying in ${models.retry_secs < 60 ? `${models.retry_secs} s` : hm(models.retry_secs)}</div>`;
    case "none":
      return `<div class="small muted">This build has no city models.</div>`;
    default:
      return "";
  }
}

function renderCity(w: World) {
  // Levels graduate by build time (needs met); an older daemon counted focus.
  const built = w.built_secs ?? w.focused_secs;
  const span = (w.next_tier_secs ?? built) - w.tier_floor_secs;
  const pct = w.next_tier_secs === null ? 100 : Math.min(100, ((built - w.tier_floor_secs) / Math.max(1, span)) * 100);
  const next =
    w.next_tier_secs === null
      ? "The plan is finished"
      : `${hm(Math.max(0, w.next_tier_secs - built))} of building to the ${TIERS[Math.min(3, w.tier + 1)]}`;
  const intact = w.plots.filter((p) => !p.rubble).length;
  const damaged = w.plots.filter((p) => !p.rubble && p.damage > 0).length;
  const rubble = w.plots.length - intact;
  const condition = [
    `${intact} building${intact === 1 ? "" : "s"}`,
    damaged ? `<span class="loss">${damaged} damaged</span>` : "",
    rubble ? `<span class="loss">${rubble} in ruins</span>` : "",
  ].filter(Boolean);
  const freezes = w.freezes ? ` (${w.freezes} freeze${w.freezes === 1 ? "" : "s"})` : "";
  const streak = w.streak_days ? ` · streak ${w.streak_days} day${w.streak_days === 1 ? "" : "s"}${freezes}` : "";
  $("#city").innerHTML = `
    <h1>${TIERS[Math.min(3, w.tier)]}${status?.dry_run ? '<span class="badge">dry run</span>' : ""}</h1>
    <div class="muted">${hm(w.focused_secs)} focused${streak}</div>
    <div class="bar"><div style="width:${pct.toFixed(1)}%"></div></div>
    <div class="small muted">${next}</div>
    <div class="small muted">${condition.join(" · ")}</div>
    ${modelsLine()}`;
}

function building(w: World | null, s: SessionInfo): string {
  const c = w?.construction;
  if (!c) return w?.needs ? `<div class="muted">No site chosen: banking crew hours.</div>` : "";
  const what = escapeHtml(c.name ?? "the building");
  if (c.surrendering) return `<div class="loss">The work on ${what} is about to be lost.</div>`;
  if (c.progress_permille === null) return `<div class="muted">Building ${what}.</div>`;
  const pct = Math.min(100, Math.floor(c.progress_permille / 10));
  return `<div class="muted">Building ${what} · ${pct}%${s.state === "active" && pct >= 100 ? ", done when the session completes" : ""}</div>`;
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
  return main + building(world, s) + distracted + stop;
}

function liveIdle(st: Status): string {
  const parts: string[] = [];
  if (st.nudge) {
    const level = Math.min(3, st.nudge.level);
    parts.push(`<div class="nudge level-${level}">No focus for ${hm(st.nudge.idle_secs)}. Start a session.</div>`);
  } else {
    parts.push(`<div class="muted">No session running.</div>`);
  }
  if (world?.needs && !world.auto && !world.sites?.some((s) => s.active) && world.needs.some((n) => n.lots_done < n.lots)) {
    parts.push(`<div class="small muted">Nothing is under construction: pick a need on the desk first, or this session banks crew hours.</div>`);
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

// ---------------------------------------------------------------------------
// Starting a session: a mode, a ring dial in 5-minute steps, a profile, go.

type StartMode = "timer" | "stopwatch";
/** One full turn of the ring is 3 hours, zero at 12 o'clock. The daemon caps
 * sessions at 6 h; the dial stays well inside that. */
const STEP_MINS = 5;
const MIN_MINS = 5;
const MAX_MINS = 180;
let startMode: StartMode = "timer";
let startMins = 30;
let startProfile: string | null = null;

function snapMins(mins: number): number {
  return Math.min(MAX_MINS, Math.max(MIN_MINS, Math.round(mins / STEP_MINS) * STEP_MINS));
}

/** The readout in the middle: minutes, with hours only once there are any. */
function dialReadout(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  const num = (v: number | string, cls = "") => `<tspan class="num${cls}">${v}</tspan>`;
  const unit = (u: string) => `<tspan class="unit">${u}</tspan>`;
  if (h === 0) return `${num(m, " min")}${unit(" min")}`;
  return `${num(h)}${unit("h ")}${num(String(m).padStart(2, "0"), " min")}${unit("m")}`;
}

/** The timer dial as inline SVG: a pale ring that fills in deeper as it is
 * dragged round. Stopwatch mode keeps the same box, so nothing shifts. */
function clockDial(): string {
  const dim = startMode === "stopwatch";
  const c = 95;
  const r = 84;
  const len = 2 * Math.PI * r;
  const filled = dim ? 0 : (startMins / MAX_MINS) * len;
  // Rotated so the stroke starts at 12 o'clock and runs clockwise.
  const fill = filled > 0
    ? `<circle cx="${c}" cy="${c}" r="${r}" class="fill" transform="rotate(-90 ${c} ${c})"
        stroke-dasharray="${filled.toFixed(2)} ${len.toFixed(2)}"/>`
    : "";
  const readout = dim ? `<tspan class="num">0</tspan><tspan class="unit"> min</tspan>` : dialReadout(startMins);
  return `<svg class="clockdial${dim ? " dim" : ""}" viewBox="0 0 190 190" width="190" height="190" role="slider"
      aria-label="Focus length" aria-valuemin="${MIN_MINS}" aria-valuemax="${MAX_MINS}"
      aria-valuenow="${dim ? 0 : startMins}" aria-valuetext="${dim ? "0 minutes, stopwatch" : hm(startMins * 60)}"
      aria-disabled="${dim}" tabindex="${dim ? -1 : 0}">
      <circle cx="${c}" cy="${c}" r="${r}" class="track"/>
      ${fill}
      <text x="${c}" y="${c}" class="readout">${readout}</text>
    </svg>`;
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
    return `<div class="start-block">
        <div class="seg start-mode">
          <button class="${startMode === "timer" ? "on" : ""}" data-action="mode" data-mode="timer">Focus timer</button>
          <button class="${startMode === "stopwatch" ? "on" : ""}" data-action="mode" data-mode="stopwatch">Stopwatch</button>
        </div>
        ${clockDial()}
        <div class="start-row">
          <select id="profile" aria-label="Profile" title="Profile">${profiles}</select>
          <button class="start-button primary" data-action="start-selected">${startMode === "stopwatch" ? "Start stopwatch" : "Start focus"}</button>
        </div>
        ${stakeRow()}
      </div>
      ${skip}${freeControls(st)}`;
  }
  if (s.state !== "active") return "";
  const stop = s.kind.type === "stopwatch" ? `<button data-action="stop" ${s.stop_locked_secs > 0 ? "disabled" : ""}>Stop</button>` : "";
  const nm = nearMiss(world, s);
  const prompt = nm
    ? `<div class="near-miss">${Math.round(nm.secs / 60)} more minutes finishes ${escapeHtml(nm.name)}.
        <button class="primary" data-action="extend" data-secs="${nm.secs}">Extend</button></div>`
    : "";
  const stake = world?.stake ? `<div class="stake-on">${world.stake} coins at stake: finish to win them twice.</div>` : "";
  return `${prompt}${stake}<div class="row">${stop}<button class="link" data-action="surrender">Surrender…</button></div>`;
}

/** Coins to bet on finishing, for a countdown at least as long as the usual session. */
function stakeRow(): string {
  const max = world?.stake_max ?? 0;
  const target = world?.stake_target_secs ?? 0;
  if (startMode !== "timer" || max <= 0 || !target) return "";
  const long = startMins * 60 >= target;
  return `<label class="stake-row" title="Finish and the stake comes back twice; surrender and it is gone.">
      Stake <input id="stake" type="number" min="0" max="${max}" step="10" placeholder="0" ${long ? "" : "disabled"} /> coins
      <span class="small muted">${long ? `up to ${max}` : `from ${Math.ceil(target / 60)} min`}</span>
    </label>`;
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
  const key = s ? `${s.id}:${s.state}:${s.kind.type}:${s.stop_locked_secs > 0}:${nearMiss(world, s)?.secs ?? 0}:${world?.stake ?? 0}` : `idle:${st.profiles}:${st.upcoming.map((u) => u.routine + u.skipped)}:${st.skip_tokens_left}:${st.free?.spending}:${Math.floor((st.free?.balance_secs ?? 0) / 60)}:${world?.stake_max ?? 0}:${world?.stake_target_secs ?? 0}`;
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
  const stake = Number((document.getElementById("stake") as HTMLInputElement | null)?.value || 0);
  return act(() => call({ type: "start", kind, profile, ...(stake > 0 && kind.type === "countdown" ? { stake } : {}) }));
}

function redrawControls() {
  if (!status) return;
  actionError("");
  controlsKey = "";
  renderSession(status);
}

function setMins(next: number) {
  const snapped = snapMins(next);
  if (snapped === startMins) return;
  startMins = snapped;
  redrawControls();
}

const sessionCard = $("#session");

sessionCard.addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest("button");
  if (!btn) return;
  switch (btn.dataset.action) {
    case "mode":
      startMode = btn.dataset.mode as StartMode;
      return redrawControls();
    case "start-selected":
      if (startMode === "stopwatch") return start({ type: "stopwatch" });
      if (!(startMins >= MIN_MINS)) return actionError("Pick a length on the clock.");
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
    case "extend":
      return act(() => call({ type: "extend", secs: Number(btn.dataset.secs) }));
  }
});

// ---------------------------------------------------------------------------
// The mayor's desk, the shop and the deed.

let deskKey = "";
function renderDesk(force = false) {
  if (!world) return;
  const s = status?.session ?? null;
  // Rebuilt when what it shows changes, so an open blueprint pick survives polls.
  const key = JSON.stringify([world.needs, world.sites, world.coins, world.idle_secs, world.construction?.index, world.goals, world.inventory, s?.state, s ? Math.floor(s.elapsed_secs / 30) : 0]);
  if (!force && key === deskKey) return;
  deskKey = key;
  $("#desk").innerHTML = deskHtml(world, s);
}

const shopDialog = $("#shop") as HTMLDialogElement;
const townDialog = $("#town") as HTMLDialogElement;

function renderTown() {
  if (!world) return;
  $("#town-coins").textContent = `You have ${world.coins ?? 0} coins.`;
  $("#town-main").innerHTML = townHtml(world, status?.session != null);
}

function openTown() {
  $("#town-error").textContent = "";
  renderTown();
  if (!townDialog.open) townDialog.showModal();
}
const deedDialog = $("#deed") as HTMLDialogElement;
let deedIndex: number | null = null;

function renderShop() {
  if (!world) return;
  $("#shop-coins").textContent = `You have ${world.coins ?? 0} coins.`;
  $("#shop-main").innerHTML = shopHtml(world, status?.session != null, skyline ? (id) => skyline!.blueprintPic(id) : undefined);
}

function openShop() {
  $("#shop-error").textContent = "";
  renderShop();
  if (!shopDialog.open) shopDialog.showModal();
}

function renderDeed() {
  const p = world?.plots.find((p) => p.index === deedIndex);
  if (!p) {
    deedDialog.close();
    return;
  }
  $("#deed-main").innerHTML = deedHtml(world!, p, Math.floor(Date.now() / 1000));
}

function openDeed(index: number) {
  if (!world?.plots.some((p) => p.index === index)) return;
  deedIndex = index;
  $("#deed-error").textContent = "";
  renderDeed();
  if (!deedDialog.open) deedDialog.showModal();
}

/** A decision for the daemon; errors show where it was asked. */
async function decide(req: Parameters<typeof call>[0], errorEl: string, after?: () => void) {
  $(errorEl).textContent = "";
  try {
    const r = await call(req);
    if (r.type === "world") {
      world = r;
      renderCity(world);
      renderDesk(true);
      skyline?.update(world, localHour(), status?.session?.elapsed_secs ?? 0);
    }
    after?.();
  } catch (e) {
    $(errorEl).textContent = e instanceof Error ? e.message : String(e);
  }
}

$("#desk").addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest("button");
  if (!btn) return;
  switch (btn.dataset.action) {
    case "choose": {
      const need = btn.dataset.need!;
      const pick = $("#desk").querySelector<HTMLSelectElement>(`select[data-need-design="${CSS.escape(need)}"]`);
      return decide({ type: "choose", need, blueprint: pick?.value ?? null }, "#action-error");
    }
    case "pause":
      return decide({ type: "pause" }, "#action-error");
    case "shop":
      return openShop();
    case "town":
      return openTown();
    case "buy-land":
      return decide({ type: "buy_land", lot: btn.dataset.lot! }, "#action-error");
    case "use-item":
      return decide({ type: "use_item", item: btn.dataset.item!, lot: null }, "#action-error");
  }
});

townDialog.addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-action]");
  if (btn?.dataset.action === "upgrade") void decide({ type: "upgrade_street", street: btn.dataset.street! }, "#town-error", renderTown);
  if (btn?.dataset.action === "decorate") {
    const spot = btn.dataset.spot!;
    const pick = townDialog.querySelector<HTMLSelectElement>(`select[data-spot-pick="${CSS.escape(spot)}"]`);
    if (pick?.value) void decide({ type: "decorate", spot, decoration: pick.value }, "#town-error", renderTown);
  }
});

for (const d of [shopDialog, deedDialog, townDialog]) {
  d.addEventListener("click", (ev) => {
    if (ev.target === d || (ev.target as HTMLElement).closest("[data-action=close]")) d.close();
  });
}
shopDialog.addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-action=buy]");
  if (btn) void decide({ type: "buy", blueprint: btn.dataset.blueprint! }, "#shop-error", renderShop);
});
deedDialog.addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-action]");
  if (btn?.dataset.action === "repair") void decide({ type: "repair", lot: btn.dataset.lot! }, "#deed-error", renderDeed);
  if (btn?.dataset.action === "repair-kit") void decide({ type: "use_item", item: "repair_kit", lot: btn.dataset.lot! }, "#deed-error", renderDeed);
  if ((ev.target as HTMLElement).closest("[data-action=rename-open]")) {
    const form = deedDialog.querySelector<HTMLFormElement>("form.rename")!;
    form.hidden = false;
    form.querySelector("input")!.select();
  }
});
deedDialog.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const form = ev.target as HTMLFormElement;
  const name = (form.elements.namedItem("name") as HTMLInputElement).value;
  void decide({ type: "rename", lot: form.dataset.lot!, name }, "#deed-error", renderDeed);
});

const tag = $("#tag");
function hover(index: number | null, x: number, y: number) {
  const html = index === null || !world ? "" : tagHtml(world, index);
  tag.hidden = !html;
  if (!html) return;
  tag.innerHTML = html;
  tag.style.left = `${Math.min(x + 14, innerWidth - 260)}px`;
  tag.style.top = `${y + 14}px`;
}

sessionCard.addEventListener("change", (ev) => {
  const el = ev.target as HTMLSelectElement;
  if (el.id === "profile") startProfile = el.value;
});

// The ring dial: click or drag round it, scroll or use the arrow keys. All of
// them land on the nearest 5-minute step.
function dialFromEvent(ev: MouseEvent, dragging: boolean) {
  if (startMode !== "timer") return;
  const dial = sessionCard.querySelector(".clockdial");
  if (!dial) return;
  const rect = dial.getBoundingClientRect();
  const dx = ev.clientX - (rect.left + rect.width / 2);
  const dy = ev.clientY - (rect.top + rect.height / 2);
  let deg = (Math.atan2(dx, -dy) * 180) / Math.PI; // 0 at 12 o'clock, clockwise
  if (deg < 0) deg += 360;
  let mins = (deg / 360) * MAX_MINS;
  // A drag that crosses 12 o'clock sticks to the end it came from instead of
  // jumping between 3 h and nothing.
  if (dragging && Math.abs(mins - startMins) > MAX_MINS / 2) {
    mins = startMins > MAX_MINS / 2 ? MAX_MINS : MIN_MINS;
  }
  setMins(mins);
}

let dialDrag = false;
sessionCard.addEventListener("pointerdown", (ev) => {
  const dial = (ev.target as Element).closest<SVGElement>(".clockdial");
  if (!dial || startMode !== "timer") return;
  dialDrag = true;
  // Capture on the card, not the dial: the dial is rebuilt on every change.
  sessionCard.setPointerCapture(ev.pointerId);
  ev.preventDefault();
  dial.focus();
  dialFromEvent(ev, false);
});
sessionCard.addEventListener("pointermove", (ev) => {
  if (dialDrag) dialFromEvent(ev, true);
});
const endDialDrag = (ev: PointerEvent) => {
  if (!dialDrag) return;
  dialDrag = false;
  try {
    sessionCard.releasePointerCapture(ev.pointerId);
  } catch {
    // The pointer was already released.
  }
};
sessionCard.addEventListener("pointerup", endDialDrag);
sessionCard.addEventListener("pointercancel", endDialDrag);

sessionCard.addEventListener(
  "wheel",
  (ev) => {
    const dial = (ev.target as Element).closest(".clockdial");
    if (!dial || startMode !== "timer") return;
    ev.preventDefault();
    setMins(startMins + (ev.deltaY < 0 ? STEP_MINS : -STEP_MINS));
  },
  { passive: false },
);

sessionCard.addEventListener("keydown", (ev) => {
  const dial = (ev.target as Element).closest(".clockdial");
  if (!dial || startMode !== "timer") return;
  const step = ev.key === "ArrowUp" || ev.key === "ArrowRight" ? STEP_MINS : ev.key === "ArrowDown" || ev.key === "ArrowLeft" ? -STEP_MINS : 0;
  if (!step) return;
  ev.preventDefault();
  setMins(startMins + step);
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

// Two buttons under the city card: the chart opens Stats and Session logs,
// the cog opens everything that can be configured.
$("#menu").addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest("button");
  if (btn?.dataset.open === "progress") openProgress();
  else if (btn?.dataset.open === "settings") void openSettings("session");
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

let skyline: City | null = null;
let rendererError: string | null = null;
let busy = false;

async function poll() {
  if (busy) return;
  busy = true;
  try {
    if (!skyline && models && models.state !== "ready") {
      models = await modelsStatus();
      if (models.state === "ready") void startCity();
    }
    status = await getStatus();
    const s = status.session;
    const key = s ? `${s.id}:${s.state}` : "none";
    const now = Date.now();
    if (key !== sessionKey || now - lastWorldFetch > 5000) {
      sessionKey = key;
      lastWorldFetch = now;
      const was = world?.tier;
      world = await getWorld();
      // The scene starts the card with its fireworks; without one, at once.
      if (!skyline && was !== undefined && world.tier > was) levelUp(world.tier);
      renderCity(world);
      if (deedDialog.open) renderDeed();
      if (shopDialog.open) renderShop();
      $("#notice").innerHTML = notice(await pendingConfig());
    }
    renderSession(status);
    renderDesk();
    hudUpdate(status);
    progressUpdate(world);
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
// The HUD works without the skyline: until the models are downloaded there is
// none, and a renderer failure only costs the picture.
let starting = false;
async function startCity() {
  if (skyline || starting) return;
  starting = true;
  try {
    const city = await City.create($("#stage"), story);
    city.onHover = hover;
    city.onGraduate = levelUp;
    city.onPick = (i) => {
      skyline?.look(i);
      openDeed(i);
    };
    skyline = city;
    models = null;
    rendererError = null;
    if (!("__TAURI_INTERNALS__" in window)) Object.assign(window, { city: skyline });
    if (world) {
      renderCity(world);
      skyline.update(world, localHour(), status?.session?.elapsed_secs ?? 0);
    }
  } catch (e) {
    console.error(e);
    rendererError = `Skyline unavailable: ${e}`;
  } finally {
    starting = false;
  }
}
models = await modelsStatus();
if (models.state === "ready") await startCity();
await poll();
setInterval(poll, 1000);
// `VITE_FPS=1` (dev server or build) adds a frame-rate readout with the 1% low, for tuning.
if (import.meta.env.VITE_FPS && skyline) {
  const el = document.createElement("div");
  el.style.cssText = "position:fixed;left:8px;bottom:8px;font:12px monospace;color:#9f9;z-index:9";
  document.body.append(el);
  setInterval(() => (el.textContent = `${skyline!.fps.toFixed(0)} fps · 1% low ${skyline!.low.toFixed(0)}`), 500);
}
