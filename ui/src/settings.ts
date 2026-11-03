// The settings sheet: every key in /etc/deepwork/config.toml, editable here.
// Stats and Session logs live in their own sheet (progress.ts). The daemon is
// still the authority: it validates, writes the file, and holds back loosening changes
// for 24 hours. This module only holds the draft.
import { exportBackup, getConfig, importBackup, saveConfig, skip as skipRun } from "./daemon";
import { confirmAction, openText, saveText } from "./files";
import { escapeHtml, hhmm, hm } from "./format";
import { runsPanel, skippable } from "./panels";
import { cleanDomain, defaultProfileName, putPath } from "./settings-model";
import { setThemePref, themePref, type ThemePref } from "./theme";
import type { Config, ListMode, PendingConfig, Profile, RuleAction, Status, Throttle } from "./proto";

export type SettingsSection = "session" | "lists" | "routines" | "inverted" | "dns" | "backup" | "appearance";

const SECTIONS: { key: SettingsSection; label: string; blurb: string }[] = [
  { key: "session", label: "Session", blurb: "Timer defaults and nudges" },
  { key: "lists", label: "Site lists", blurb: "Allow, slow and block" },
  { key: "routines", label: "Routines", blurb: "Sessions that start on their own" },
  { key: "inverted", label: "Inverted mode", blurb: "Throttle between sessions" },
  { key: "dns", label: "DNS", blurb: "Resolver and upstreams" },
  { key: "backup", label: "Backup", blurb: "Export and import everything" },
  { key: "appearance", label: "Appearance", blurb: "System, light or dark" },
];

const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_LABELS: Record<string, string> = {
  mon: "Mon",
  tue: "Tue",
  wed: "Wed",
  thu: "Thu",
  fri: "Fri",
  sat: "Sat",
  sun: "Sun",
};

const ACTIONS: { key: RuleAction; label: string }[] = [
  { key: "allow", label: "Allow (full speed)" },
  { key: "throttle", label: "Slow down" },
  { key: "block", label: "Block" },
];

let draft: Config | null = null;
let section: SettingsSection = "session";
let profileName = "";
let message = "";
let messageIsError = false;
let dirty = false;
let busy = false;
let pending: PendingConfig | null = null;

/** Latest daemon status, pushed in from the HUD poll for the runs list and skips. */
let liveStatus: Status | null = null;

const dialog = () => document.querySelector<HTMLDialogElement>("#settings")!;
const main = () => document.querySelector<HTMLElement>("#settings-main")!;
const nav = () => document.querySelector<HTMLElement>("#settings-nav")!;
const footMessage = () => document.querySelector<HTMLElement>("#settings-message")!;
const skipDialog = () => document.querySelector<HTMLDialogElement>("#skip")!;

/** The first profile if the remembered one disappeared. */
/** The daemon omits optional keys (null in Rust), so fill them in once. */
function normalize(c: Config): Config {
  c.inverted.profile ??= null;
  c.dns.container_dns ??= null;
  for (const r of c.routines) r.profile ??= null;
  return c;
}

function currentProfile(): Profile {
  const c = draft!;
  if (!c.profiles[profileName]) profileName = Object.keys(c.profiles)[0] ?? "";
  return c.profiles[profileName];
}

function setMessage(text: string, error = false) {
  message = text;
  messageIsError = error;
  const el = footMessage();
  if (el) {
    el.textContent = text;
    el.className = `settings-message${error ? " error" : ""}`;
  }
}

function updateFoot() {
  const el = footMessage();
  if (el) {
    el.textContent = message;
    el.className = `settings-message${messageIsError ? " error" : ""}`;
  }
  const save = document.querySelector<HTMLButtonElement>("#settings-save");
  if (save) {
    save.disabled = busy || !draft || !dirty;
    save.textContent = busy ? "Saving…" : dirty ? "Save changes" : "Saved";
  }
  const revert = document.querySelector<HTMLButtonElement>("#settings-revert");
  if (revert) revert.disabled = busy || !dirty;
  const dot = document.querySelector<HTMLElement>("#settings-dirty");
  if (dot) dot.hidden = !dirty;
}

// ---------------------------------------------------------------------------
// Field helpers

function field(label: string, control: string, hint = ""): string {
  return `<div class="field"><span class="field-label">${label}</span>${control}${
    hint ? `<span class="hint">${hint}</span>` : ""
  }</div>`;
}

interface NumberOptions {
  min?: number;
  max?: number;
  step?: number;
  /** Config stores this unit; the field shows value / scale. */
  scale?: number;
  suffix?: string;
}

function num(path: string, value: number, opts: NumberOptions = {}): string {
  const scale = opts.scale ?? 1;
  const shown = scale === 1 ? value : Math.round((value / scale) * 10) / 10;
  return `<span class="number"><input type="number" data-path="${path}" data-scale="${scale}" value="${shown}"${
    opts.min !== undefined ? ` min="${opts.min}"` : ""
  }${opts.max !== undefined ? ` max="${opts.max}"` : ""}${
    opts.step !== undefined ? ` step="${opts.step}"` : ""
  }>${opts.suffix ? `<span class="unit">${opts.suffix}</span>` : ""}</span>`;
}

function toggle(path: string, on: boolean, label: string, hint = ""): string {
  return `<label class="toggle"><input type="checkbox" data-path="${path}"${on ? " checked" : ""}>
    <span><strong>${label}</strong>${hint ? `<span class="hint">${hint}</span>` : ""}</span></label>`;
}

function days(value: string[], kind: "routine" | "nudge", index = 0): string {
  return `<div class="day-row">${DAY_KEYS.map(
    (d) =>
      `<button class="day${value.includes(d) ? " on" : ""}" data-action="day" data-kind="${kind}"${
        kind === "routine" ? ` data-index="${index}"` : ""
      } data-day="${d}">${DAY_LABELS[d]}</button>`,
  ).join("")}</div>`;
}

function profileOptions(selected: string | null): string {
  return draft!.profiles
    ? Object.keys(draft!.profiles)
        .map((p) => `<option value="${escapeHtml(p)}"${p === selected ? " selected" : ""}>${escapeHtml(p)}</option>`)
        .join("")
    : "";
}

function segmented(current: ListMode, name: string): string {
  const options: { key: ListMode; label: string }[] = [
    { key: "block_list", label: "Block list" },
    { key: "allow_only", label: "Allow only" },
  ];
  return `<div class="seg">${options
    .map(
      (o) =>
        `<button class="${current === o.key ? "on" : ""}" data-action="mode" data-mode="${o.key}">${o.label}</button>`,
    )
    .join("")}</div>
    <p class="hint">${
      current === "block_list"
        ? `Sites you list are slowed or blocked; everything else runs at full speed. An allow rule punches a hole through a slowed parent domain (for example <code>music.youtube.com</code>).`
        : `Only allowed sites run at full speed; every other website is slowed, and blocked sites stay blocked.`
    } <span class="muted">Profile ${escapeHtml(name)}.</span></p>`;
}

// ---------------------------------------------------------------------------
// Sections

function sessionSection(c: Config): string {
  return `${sheetTitle("Session", `What every new focus session uses. Changes that loosen enforcement wait 24 hours.`)}
    <div class="grid2">
      ${field("Default profile", `<select data-path="session.default_profile">${profileOptions(c.session.default_profile)}</select>`)}
      ${field("Stopwatch minimum", num("session.stopwatch_min_secs", c.session.stopwatch_min_secs, { min: 1, scale: 60, suffix: "min" }), "A stopwatch cannot be stopped before this.")}
      ${field("Surrender wait", num("session.surrender_wait_secs", c.session.surrender_wait_secs, { min: 1, scale: 60, suffix: "min" }), "Enforcement stays on for this long after you surrender.")}
      ${field("Routine heads-up", num("schedule.heads_up_secs", c.schedule.heads_up_secs, { min: 0, scale: 60, suffix: "min" }), "How early the app and bar warn you.")}
      ${field("Skip tokens per week", num("schedule.skip_tokens_per_week", c.schedule.skip_tokens_per_week, { min: 0, max: 20 }), "One token skips one routine run, Monday to Sunday.")}
    </div>

    <h3>Nudges</h3>
    ${toggle("nudge.enabled", c.nudge.enabled, "Remind me when I have not started a session", "Inside the active hours below.")}
    <div class="grid2">
      ${field("Active days", days(c.nudge.days, "nudge"), "No day selected means every day.")}
      ${field("Between", `<span class="row tight"><input type="time" data-path="nudge.from" value="${c.nudge.from}"><span class="muted">and</span><input type="time" data-path="nudge.until" value="${c.nudge.until}"></span>`)}
      ${field("First nudge after", num("nudge.after_mins", c.nudge.after_mins, { min: 1, suffix: "min" }), "Without a session.")}
      ${field("Then every", num("nudge.repeat_mins", c.nudge.repeat_mins, { min: 1, suffix: "min" }), "Each repeat is a notch more urgent.")}
    </div>
    <p class="hint">Nudges only notify; they never start a session. Routines do.</p>`;
}

function ruleRow(c: Config, name: string, index: number): string {
  const rule = c.profiles[name].rules[index];
  return `<li>
    <input class="rule-domain" data-path="profiles.${name}.rules.${index}.domain" value="${escapeHtml(rule.domain)}" spellcheck="false" autocomplete="off">
    <select data-path="profiles.${name}.rules.${index}.action" data-rerender="1">
      ${ACTIONS.map((a) => `<option value="${a.key}"${rule.action === a.key ? " selected" : ""}>${a.label}</option>`).join("")}
    </select>
    <button class="icon" data-action="rule-remove" data-index="${index}" title="Remove">×</button>
  </li>`;
}

function listGroup(c: Config, name: string, action: RuleAction, title: string, hint: string): string {
  const items = c.profiles[name].rules
    .map((r, i) => (r.action === action ? ruleRow(c, name, i) : ""))
    .join("");
  return `<div class="rule-group ${action}">
    <div class="rule-head"><span class="rule-dot"></span><strong>${title}</strong>
      <span class="tag">${c.profiles[name].rules.filter((r) => r.action === action).length}</span></div>
    <p class="hint">${hint}</p>
    ${items ? `<ul class="rule-list">${items}</ul>` : `<p class="empty small">Nothing here yet.</p>`}
  </div>`;
}

function listsSection(c: Config): string {
  const p = currentProfile();
  const names = Object.keys(c.profiles);
  return `${sheetTitle("Site lists", `Slow or block distractions, and let the sites you need through. Every domain also covers its subdomains.`)}
    <div class="pill-row">${names
      .map(
        (n) =>
          `<button class="pill${n === profileName ? " on" : ""}" data-action="profile" data-profile="${escapeHtml(n)}">${escapeHtml(n)}</button>`,
      )
      .join("")}</div>
    <div class="profile-bar">
      ${field("Profile name", `<input data-action="profile-rename" value="${escapeHtml(profileName)}" spellcheck="false">`)}
      ${field("New profile", `<span class="row tight"><input id="new-profile" placeholder="e.g. study" spellcheck="false"><button data-action="profile-add">Add</button></span>`)}
      <button class="danger-quiet" data-action="profile-remove"${names.length < 2 ? " disabled" : ""}>Delete this profile</button>
    </div>

    <h3>How this profile treats sites</h3>
    ${segmented(p.mode, profileName)}

    <h3>Add a site</h3>
    <div class="add-rule">
      <input id="rule-domain" placeholder="example.com" spellcheck="false" autocomplete="off">
      <select id="rule-action">${ACTIONS.map(
        (a) =>
          `<option value="${a.key}"${a.key === (p.mode === "allow_only" ? "allow" : "throttle") ? " selected" : ""}>${a.label}</option>`,
      ).join("")}</select>
      <button class="primary" data-action="rule-add">Add site</button>
    </div>

    <div class="rule-groups">
      ${listGroup(c, profileName, "allow", "Allow", p.mode === "allow_only" ? "The allow list: these sites run at full speed." : "Exceptions: these sites stay fast even inside a slowed or blocked parent.")}
      ${listGroup(c, profileName, "throttle", "Slow down", "Painfully slow, but they still work: the default for distractions.")}
      ${listGroup(c, profileName, "block", "Block", "Connections are reset. Prefer slowing down: it is harder to work around.")}
    </div>

    <h3>Throttle</h3>
    <div class="grid4">
      ${field("Bandwidth", num(`profiles.${profileName}.throttle.rate_kbit`, p.throttle.rate_kbit, { min: 8, suffix: "kbit/s" }))}
      ${field("Added delay", num(`profiles.${profileName}.throttle.rtt_ms`, p.throttle.rtt_ms, { min: 0, suffix: "ms" }))}
      ${field("Jitter", num(`profiles.${profileName}.throttle.jitter_ms`, p.throttle.jitter_ms, { min: 0, suffix: "ms" }))}
      ${field("Packet loss", num(`profiles.${profileName}.throttle.loss_pct`, p.throttle.loss_pct, { min: 0, max: 50, step: 0.1, suffix: "%" }))}
    </div>
    <p class="hint">256 kbit/s, +400 ms and no loss is the tuned default: 240p video buffers, everything else still works.</p>

    <h3>Escalation</h3>
    <p class="hint">Harsher throttles the longer slowed sites are actually used in a session.</p>
    ${p.escalation
      .map(
        (s, i) => `<div class="stage-row">
          <span class="stage-when">after ${num(`profiles.${profileName}.escalation.${i}.after_mins`, s.after_mins, { min: 1, suffix: "min" })}</span>
          <span class="stage-throttle">
            ${num(`profiles.${profileName}.escalation.${i}.throttle.rate_kbit`, s.throttle.rate_kbit, { min: 8, suffix: "kbit/s" })}
            ${num(`profiles.${profileName}.escalation.${i}.throttle.rtt_ms`, s.throttle.rtt_ms, { min: 0, suffix: "ms" })}
            ${num(`profiles.${profileName}.escalation.${i}.throttle.jitter_ms`, s.throttle.jitter_ms, { min: 0, suffix: "ms" })}
            ${num(`profiles.${profileName}.escalation.${i}.throttle.loss_pct`, s.throttle.loss_pct, { min: 0, max: 50, step: 0.1, suffix: "%" })}
          </span>
          <button class="icon" data-action="stage-remove" data-index="${i}" title="Remove">×</button>
        </div>`,
      )
      .join("") || `<p class="empty small">No stages: the throttle never tightens.</p>`}
    <button data-action="stage-add">Add a stage</button>

    <h3>Enforcement</h3>
    <div class="toggles">
      ${toggle(`profiles.${profileName}.block_quic`, p.block_quic, "Block QUIC", "Browsers fall back from UDP 443 to TCP, where throttling works.")}
      ${toggle(`profiles.${profileName}.inspect_sni`, p.inspect_sni, "Inspect TLS server names", "Judges new connections by name, so shared CDN addresses are not collateral.")}
      ${toggle(`profiles.${profileName}.lock_docker`, p.lock_docker, "Lock the Docker socket", "The docker group is root in all but name; this closes the socket during sessions.")}
    </div>`;
}

function routinesSection(c: Config): string {
  const runs = liveStatus
    ? `<div id="runs">${runsPanel(liveStatus, c.schedule.skip_tokens_per_week, Math.floor(Date.now() / 1000))}</div>`
    : "";
  const rows = c.routines
    .map(
      (r, i) => `<div class="routine-card">
        <div class="routine-top">
          ${field("Name", `<input data-path="routines.${i}.name" value="${escapeHtml(r.name)}" spellcheck="false">`)}
          ${field("Start", `<input type="time" data-path="routines.${i}.start" value="${r.start}">`)}
          ${field("Length", num(`routines.${i}.duration_mins`, r.duration_mins, { min: 1, max: 360, suffix: "min" }))}
          ${field("Profile", `<select data-path="routines.${i}.profile" data-nullable="1"><option value=""${r.profile === null ? " selected" : ""}>default</option>${profileOptions(r.profile)}</select>`)}
          <button class="icon" data-action="routine-remove" data-index="${i}" title="Remove">×</button>
        </div>
        ${field("Days", days(r.days, "routine", i), "No day selected means every day.")}
      </div>`,
    )
    .join("");
  return `${sheetTitle("Routines", `A routine starts a countdown on its own. If the machine was asleep, it starts late with what is left of its window. Each run happens once.`)}
    ${runs}
    ${rows || `<p class="empty">No routines. Focus only starts when you do.</p>`}
    <button class="primary" data-action="routine-add">Add a routine</button>`;
}

function invertedSection(c: Config): string {
  const inv = c.inverted;
  return `${sheetTitle("Inverted mode", `Distractions are slowed whenever no session is running. Completing focus earns free minutes that lift the throttle for a while.`)}
    ${toggle("inverted.enabled", inv.enabled, "Keep distractions slow between sessions", "Outside sessions nothing is locked: sudo, systemctl and Docker work as usual.")}
    <div class="grid2">
      ${field("Profile to enforce", `<select data-path="inverted.profile" data-nullable="1"><option value=""${inv.profile === null ? " selected" : ""}>default profile</option>${profileOptions(inv.profile)}</select>`)}
      ${field("Free minutes per focused hour", num("inverted.free_mins_per_hour", inv.free_mins_per_hour, { min: 0, max: 60, suffix: "min" }))}
      ${field("Bank cap", num("inverted.max_bank_mins", inv.max_bank_mins, { min: 0, max: 1440, suffix: "min" }))}
    </div>
    <p class="hint">Spend banked time with the button in the session card, or <code>deepwork free 15m</code>. Starting a session stops free time and banks the rest.</p>`;
}

function upstreamRow(c: Config, i: number): string {
  const u = c.dns.upstreams[i];
  const tls = typeof u !== "string";
  return `<li class="upstream-row">
    <select data-action="upstream-type" data-index="${i}">
      <option value="plain"${tls ? "" : " selected"}>Plain DNS</option>
      <option value="tls"${tls ? " selected" : ""}>DNS-over-TLS</option>
    </select>
    <input data-path="dns.upstreams.${i}${tls ? ".addr" : ""}" value="${escapeHtml(tls ? u.addr : u)}" placeholder="9.9.9.9:53" spellcheck="false">
    ${tls ? `<input data-path="dns.upstreams.${i}.tls_name" value="${escapeHtml(u.tls_name)}" placeholder="dns.quad9.net" spellcheck="false">` : ""}
    <button class="icon" data-action="upstream-remove" data-index="${i}" title="Remove">×</button>
  </li>`;
}

function dnsSection(c: Config): string {
  return `${sheetTitle("DNS", `The forwarder runs during sessions so names can be matched before the address is known.`)}
    <p class="notice-small">DNS changes take effect when <code>deepworkd</code> restarts, not when you save.</p>
    <div class="grid2">
      ${field("Port", num("dns.port", c.dns.port, { min: 1, max: 65535 }))}
      ${field("Container DNS", `<input data-path="dns.container_dns" data-nullable="1" value="${escapeHtml(c.dns.container_dns ?? "")}" placeholder="172.17.0.1:53" spellcheck="false">`, "Forwarded container DNS is sent here during sessions. Empty: refused.")}
    </div>
    ${toggle("dns.manage_resolved", c.dns.manage_resolved, "Point systemd-resolved at the forwarder during sessions", "Needed when resolved uses DNS-over-TLS itself.")}

    <h3>Upstreams</h3>
    <ul class="plain-list">${c.dns.upstreams.map((_, i) => upstreamRow(c, i)).join("")}</ul>
    <div class="row">
      <button data-action="upstream-add" data-kind="plain">Add plain DNS</button>
      <button data-action="upstream-add" data-kind="tls">Add DNS-over-TLS</button>
    </div>

    <h3>Forward zones</h3>
    <p class="hint">Names under a suffix go to a specific server, for example a Tailscale MagicDNS name.</p>
    <ul class="plain-list">${c.dns.forward
      .map(
        (z, i) => `<li class="upstream-row">
          <input data-path="dns.forward.${i}.suffix" value="${escapeHtml(z.suffix)}" placeholder="ts.net" spellcheck="false">
          <input data-path="dns.forward.${i}.server" value="${escapeHtml(z.server)}" placeholder="100.100.100.100:53" spellcheck="false">
          <button class="icon" data-action="forward-remove" data-index="${i}" title="Remove">×</button>
        </li>`,
      )
      .join("")}</ul>
    <button data-action="forward-add">Add a forward zone</button>`;
}

function backupSection(): string {
  return `${sheetTitle("Backup", `Settings and progress travel together: your city is rebuilt from the sessions in the file.`)}
    <div class="backup-card">
      <h3>Export everything</h3>
      <p>One JSON file with the settings, ended sessions, penalties, routine runs and the free-minute bank.</p>
      <p class="hint">A loosening change still waiting behind the 24h delay is not included: backups carry the settings in effect.</p>
      <button class="primary" data-action="export">Export a backup…</button>
    </div>
    <div class="backup-card">
      <h3>Import a backup</h3>
      <p>Merges into this machine. A session already here (same profile and start) is skipped, so importing the same file twice is safe. End a running session first.</p>
      <button data-action="import">Choose a backup…</button>
    </div>
    <div class="note">
      <strong>Why a file and not only the app?</strong>
      <p>The daemon still writes every change to <code>/etc/deepwork/config.toml</code>, so the settings survive reinstalls, a headless machine and a broken window. You never need to edit it by hand, but it stays readable.</p>
    </div>`;
}

const THEMES: { key: ThemePref; label: string; icon: string }[] = [
  { key: "system", label: "System", icon: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>' },
  { key: "light", label: "Light", icon: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>' },
  { key: "dark", label: "Dark", icon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>' },
];

/** A view preference, so it applies at once and never goes to deepworkd. */
function appearanceSection(): string {
  const pref = themePref();
  return `${sheetTitle("Appearance", `How this window looks. Kept in the app, not in <code>config.toml</code>, and applied at once.`)}
    ${field(
      "Theme",
      `<div class="seg" role="group" aria-label="Colour theme">${THEMES.map(
        (t) =>
          `<button class="${pref === t.key ? "on" : ""}" data-action="theme" data-theme="${t.key}" aria-pressed="${pref === t.key}">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${t.icon}</svg>${t.label}</button>`,
      ).join("")}</div>`,
      "System follows the desktop's light or dark preference, and switches with it.",
    )}`;
}

/** Eyebrow, heading and blurb, then the pending banner on config sections. */
function sheetTitle(title: string, blurb: string): string {
  return `<div class="sheet-title"><p class="eyebrow">Settings</p><h2>${title}</h2>
      <p class="muted">${blurb}</p></div>${section === "appearance" ? "" : pendingBanner()}`;
}

function pendingBanner(): string {
  if (!pending) return "";
  const reasons = pending.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("");
  return `<div class="pending-banner"><strong>A loosening change applies in ${hm(Math.max(0, pending.applies_in_secs))}.</strong>
    <ul>${reasons}</ul>
    <button class="link" data-action="cancel-pending">Cancel this change</button>
    <span class="hint">The form shows the settings that will apply. Cancel goes back to the ones in effect now.</span></div>`;
}

function body(): string {
  if (section === "appearance") return appearanceSection();
  if (!draft) return `<p class="muted">Loading settings…</p>`;
  return sectionBody(draft);
}

function sectionBody(c: Config): string {
  switch (section) {
    case "session":
      return sessionSection(c);
    case "lists":
      return listsSection(c);
    case "routines":
      return routinesSection(c);
    case "inverted":
      return invertedSection(c);
    case "dns":
      return dnsSection(c);
    case "backup":
      return backupSection();
    case "appearance":
      return appearanceSection();
  }
}

function render() {
  if (!draft && section !== "appearance") return;
  nav().innerHTML = SECTIONS.map(
    (s) =>
      `<button class="nav-item${s.key === section ? " on" : ""}" data-action="section" data-section="${s.key}">
        <span class="nav-label">${s.label}</span><span class="nav-blurb">${s.blurb}</span>
      </button>`,
  ).join("");
  main().innerHTML = body();
  updateFoot();
}

// ---------------------------------------------------------------------------
// Live data: the HUD poll pushes status in; the runs list refreshes from it
// without rebuilding the routine editor underneath.

/** The runs list inside the Routines section, without rebuilding the editor. */
function updateRuns() {
  if (!liveStatus || !draft) return;
  const div = main().querySelector("#runs");
  if (!div) return;
  const html = runsPanel(liveStatus, draft.schedule.skip_tokens_per_week, Math.floor(Date.now() / 1000));
  if (html !== div.innerHTML) div.innerHTML = html;
}

/** Called by the HUD poll: keeps the Routines runs list fresh. */
export function hudUpdate(status: Status): void {
  liveStatus = status;
  if (dialog().open && section === "routines") updateRuns();
}

// ---------------------------------------------------------------------------
// Actions

function addRule() {
  if (!draft) return;
  const domain = cleanDomain(document.querySelector<HTMLInputElement>("#rule-domain")?.value ?? "");
  const action = (document.querySelector<HTMLSelectElement>("#rule-action")?.value ?? "throttle") as RuleAction;
  if (!domain) return setMessage("Type a domain, for example example.com.", true);
  if (!/^[a-z0-9.-]+$/.test(domain) || domain.startsWith(".") || domain.includes("..")) {
    return setMessage(`${domain} does not look like a domain.`, true);
  }
  const profile = currentProfile();
  if (profile.rules.some((r) => r.domain === domain)) {
    return setMessage(`${domain} is already listed for ${profileName}.`, true);
  }
  profile.rules.push({ domain, action });
  dirty = true;
  setMessage(`${domain} added to ${profileName}. Save to apply.`);
  render();
  document.querySelector<HTMLInputElement>("#rule-domain")?.focus();
}

function addProfile() {
  if (!draft) return;
  const input = document.querySelector<HTMLInputElement>("#new-profile");
  const name = (input?.value ?? "").trim().toLowerCase();
  if (!/^[a-z0-9_-]{1,64}$/.test(name)) {
    return setMessage("Profile names may only use letters, digits, - and _.", true);
  }
  if (draft.profiles[name]) return setMessage(`There is already a profile called ${name}.`, true);
  draft.profiles[name] = {
    mode: "block_list",
    throttle: { rtt_ms: 400, jitter_ms: 50, rate_kbit: 256, loss_pct: 0 },
    block_quic: true,
    inspect_sni: true,
    lock_docker: false,
    rules: [],
    escalation: [],
  };
  profileName = name;
  dirty = true;
  setMessage(`Profile ${name} added.`);
  render();
}

async function removeProfile() {
  if (!draft) return;
  const names = Object.keys(draft.profiles);
  if (names.length < 2) return setMessage("At least one profile is required.", true);
  if (!(await confirmAction(`Delete profile ${profileName}? Its site lists go with it.`))) return;
  delete draft.profiles[profileName];
  const fallback = Object.keys(draft.profiles)[0];
  if (draft.session.default_profile === profileName) draft.session.default_profile = fallback;
  if (draft.inverted.profile === profileName) draft.inverted.profile = fallback;
  for (const r of draft.routines) if (r.profile === profileName) r.profile = null;
  profileName = fallback;
  dirty = true;
  render();
}

function renameProfile(input: HTMLInputElement) {
  if (!draft) return;
  const next = input.value.trim().toLowerCase();
  if (next === profileName) return;
  if (!/^[a-z0-9_-]{1,64}$/.test(next)) {
    setMessage("Profile names may only use letters, digits, - and _.", true);
    input.value = profileName;
    return;
  }
  if (draft.profiles[next]) {
    setMessage(`There is already a profile called ${next}.`, true);
    input.value = profileName;
    return;
  }
  const old = profileName;
  // Keep the key order: rebuild the map rather than renaming in place.
  const profiles: Record<string, Profile> = {};
  for (const [name, p] of Object.entries(draft.profiles)) profiles[name === old ? next : name] = p;
  draft.profiles = profiles;
  if (draft.session.default_profile === old) draft.session.default_profile = next;
  if (draft.inverted.profile === old) draft.inverted.profile = next;
  for (const r of draft.routines) if (r.profile === old) r.profile = next;
  profileName = next;
  dirty = true;
  render();
}

function addThrottle(): Throttle {
  return { rtt_ms: 600, jitter_ms: 50, rate_kbit: 128, loss_pct: 0 };
}

function toggleDay(kind: "routine" | "nudge", day: string, index: number) {
  if (!draft) return;
  const list = kind === "nudge" ? draft.nudge.days : draft.routines[index].days;
  const at = list.indexOf(day);
  if (at >= 0) list.splice(at, 1);
  else list.push(day);
  dirty = true;
  render();
}

async function save() {
  if (!draft || busy) return;
  busy = true;
  updateFoot();
  try {
    const saved = await saveConfig(draft);
    // Show what will apply: a queued loosening change must not look like the
    // edit vanished from the form.
    draft = normalize(saved.pendingConfig ?? saved.config);
    pending = saved.pending;
    dirty = false;
    setMessage(saved.message, false);
    window.dispatchEvent(new CustomEvent("deepwork:changed"));
  } catch (e) {
    setMessage(e instanceof Error ? e.message : String(e), true);
  } finally {
    busy = false;
    render();
  }
}

async function revert() {
  if (!draft) return;
  try {
    const loaded = await getConfig();
    // Back to what the daemon has: the waiting change if there is one.
    draft = normalize(loaded.pendingConfig ?? loaded.config);
    pending = loaded.pending;
    profileName = defaultProfileName(draft);
    dirty = false;
    setMessage("Reverted to the saved settings.");
    render();
  } catch (e) {
    setMessage(e instanceof Error ? e.message : String(e), true);
  }
}

/** Drops a waiting loosening change by saving the config in effect again. */
async function cancelPending() {
  if (!pending) return;
  if (!(await confirmAction("Cancel the waiting change and go back to the settings in effect now?"))) return;
  try {
    const loaded = await getConfig();
    const saved = await saveConfig(loaded.config);
    draft = normalize(saved.pendingConfig ?? saved.config);
    pending = saved.pending;
    dirty = false;
    setMessage(saved.message);
    window.dispatchEvent(new CustomEvent("deepwork:changed"));
    render();
  } catch (e) {
    setMessage(e instanceof Error ? e.message : String(e), true);
  }
}

interface BackupShape {
  format?: string;
  version?: number;
  exported_at?: number;
  sessions?: unknown[];
}

async function exportAll() {
  try {
    setMessage("Preparing the backup…");
    const data = await exportBackup();
    const name = `deepwork-backup-${new Date().toISOString().slice(0, 10)}.json`;
    const where = await saveText(name, `${JSON.stringify(data, null, 2)}\n`);
    setMessage(where ? `Backup written to ${where}.` : "Export cancelled.");
  } catch (e) {
    setMessage(e instanceof Error ? e.message : String(e), true);
  }
}

async function importAll() {
  try {
    const file = await openText();
    if (!file) return;
    let parsed: BackupShape;
    try {
      parsed = JSON.parse(file.text) as BackupShape;
    } catch {
      return setMessage(`${file.path} is not JSON.`, true);
    }
    if (parsed.format !== "deepwork-backup") {
      return setMessage(`${file.path} is not a DeepWork backup.`, true);
    }
    const sessions = Array.isArray(parsed.sessions) ? parsed.sessions.length : 0;
    const when = parsed.exported_at ? new Date(parsed.exported_at * 1000).toLocaleDateString() : "an unknown date";
    if (!(await confirmAction(`Import ${sessions} session${sessions === 1 ? "" : "s"} from ${when}? The settings in the file replace the ones in effect (loosening changes still wait 24 hours). Progress is merged, not erased.`))) {
      return;
    }
    setMessage("Importing…");
    const result = await importBackup(parsed);
    dirty = false;
    const loaded = await getConfig();
    draft = normalize(loaded.pendingConfig ?? loaded.config);
    pending = loaded.pending;
    profileName = defaultProfileName(draft);
    setMessage(`${result.message} Imported ${result.sessions} new session${result.sessions === 1 ? "" : "s"}.`, false);
    window.dispatchEvent(new CustomEvent("deepwork:changed"));
    render();
  } catch (e) {
    setMessage(e instanceof Error ? e.message : String(e), true);
  }
}

// ---------------------------------------------------------------------------
// Skipping a routine run. It costs a token and can't be undone, so it is
// confirmed in a dialog (the CLI asks at a terminal for the same reason).

let skipRoutine = "";

/** Offer the skip dialog for a routine's next unskipped run. Exported for the
 * skip link in the session card. */
export function confirmSkip(routine: string) {
  const st = liveStatus;
  const u = st && skippable(st, routine);
  if (!st || !u) return;
  skipRoutine = routine;
  skipDialog().querySelector("#skip-title")!.textContent = `Skip ${routine}?`;
  skipDialog().querySelector("#skip-text")!.textContent =
    `The run at ${hhmm(u.starts_at)} (${hm(u.ends_at - u.starts_at)}) won't start. ` +
    `This uses one of your ${st.skip_tokens_left} skip token${st.skip_tokens_left === 1 ? "" : "s"} left this week, and can't be undone.`;
  skipDialog().returnValue = "";
  skipDialog().showModal();
}

// ---------------------------------------------------------------------------
// Wiring

function commitInput(el: HTMLInputElement | HTMLSelectElement) {
  if (!draft || !el.dataset.path) return;
  const scale = Number(el.dataset.scale ?? 1);
  let next: unknown;
  if (el instanceof HTMLInputElement && el.type === "checkbox") next = el.checked;
  else if (el instanceof HTMLInputElement && el.type === "number") {
    next = el.value === "" ? 0 : Number(el.value) * scale;
    if (scale === 60) next = Math.round(next as number);
  } else if (el.dataset.nullable === "1") next = el.value.trim() === "" ? null : el.value.trim();
  else next = el.value;
  putPath(draft, el.dataset.path, next);
  dirty = true;
  updateFoot();
}

export async function openSettings(at: SettingsSection = "session") {
  section = at;
  const d = dialog();
  message = "";
  messageIsError = false;
  if (!draft || !dirty) {
    try {
      const loaded = await getConfig();
      draft = normalize(loaded.pendingConfig ?? loaded.config);
      pending = loaded.pending;
      profileName = defaultProfileName(draft);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e), true);
    }
  }
  render();
  if (!draft && section !== "appearance") main().innerHTML = `<p class="empty">Could not load settings. Close this and try again.</p>`;
  if (!d.open) d.showModal();
}

async function closeSettings() {
  if (dirty && !(await confirmAction("Discard unsaved changes?"))) return;
  dirty = false;
  message = "";
  dialog().close();
}

function start() {
  const d = dialog();
  d.addEventListener("click", (ev) => {
    const target = ev.target as HTMLElement;
    const btn = target.closest<HTMLButtonElement>("button[data-action]");
    if (!btn) return;
    // These work without a loaded config; the rest edit the draft.
    switch (btn.dataset.action) {
      case "close-settings":
        return void closeSettings();
      case "section":
        section = btn.dataset.section as SettingsSection;
        return render();
      case "skip":
        return confirmSkip(btn.dataset.routine!);
      case "theme":
        setThemePref(btn.dataset.theme as ThemePref);
        return render();
    }
    if (!draft) return;
    switch (btn.dataset.action) {
      case "save":
        return void save();
      case "revert":
        return void revert();
      case "cancel-pending":
        return void cancelPending();
      case "export":
        return void exportAll();
      case "import":
        return void importAll();
      case "profile":
        profileName = btn.dataset.profile ?? profileName;
        return render();
      case "profile-add":
        return addProfile();
      case "profile-remove":
        return void removeProfile();
      case "mode":
        currentProfile().mode = btn.dataset.mode as ListMode;
        dirty = true;
        return render();
      case "rule-add":
        return addRule();
      case "rule-remove": {
        currentProfile().rules.splice(Number(btn.dataset.index), 1);
        dirty = true;
        return render();
      }
      case "stage-add":
        currentProfile().escalation.push({ after_mins: 30, throttle: addThrottle() });
        dirty = true;
        return render();
      case "stage-remove":
        currentProfile().escalation.splice(Number(btn.dataset.index), 1);
        dirty = true;
        return render();
      case "routine-add":
        draft.routines.push({ name: `routine-${draft.routines.length + 1}`, days: [], start: "09:00", duration_mins: 50, profile: null });
        dirty = true;
        return render();
      case "routine-remove":
        draft.routines.splice(Number(btn.dataset.index), 1);
        dirty = true;
        return render();
      case "day":
        return toggleDay(btn.dataset.kind as "routine" | "nudge", btn.dataset.day ?? "", Number(btn.dataset.index));
      case "upstream-add":
        draft.dns.upstreams.push(btn.dataset.kind === "tls" ? { addr: "1.1.1.1:853", tls_name: "cloudflare-dns.com" } : "1.1.1.1:53");
        dirty = true;
        return render();
      case "upstream-remove":
        draft.dns.upstreams.splice(Number(btn.dataset.index), 1);
        dirty = true;
        return render();
      case "forward-add":
        draft.dns.forward.push({ suffix: "", server: "" });
        dirty = true;
        return render();
      case "forward-remove":
        draft.dns.forward.splice(Number(btn.dataset.index), 1);
        dirty = true;
        return render();
    }
  });

  d.addEventListener("input", (ev) => {
    const el = ev.target as HTMLInputElement;
    if (el.dataset.action === "profile-rename") return; // committed on change
    commitInput(el);
  });

  d.addEventListener("change", (ev) => {
    const el = ev.target as HTMLInputElement | HTMLSelectElement;
    if (el.dataset.action === "profile-rename") return renameProfile(el as HTMLInputElement);
    if (el.dataset.action === "upstream-type") {
      const i = Number(btnIndex(el));
      const u = draft?.dns.upstreams[i];
      if (!draft || u === undefined) return;
      if (el.value === "tls") draft.dns.upstreams[i] = typeof u === "string" ? { addr: u, tls_name: "" } : u;
      else draft.dns.upstreams[i] = typeof u === "string" ? u : u.addr;
      dirty = true;
      return render();
    }
    commitInput(el);
    if (el.dataset.rerender === "1") render();
  });

  d.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter") return;
    const el = ev.target as HTMLElement;
    if (el.id === "rule-domain") {
      ev.preventDefault();
      addRule();
    } else if (el.id === "new-profile") {
      ev.preventDefault();
      addProfile();
    }
  });

  // A confirmed skip goes through the daemon, then the HUD refetches.
  skipDialog().addEventListener("close", () => {
    if (skipDialog().returnValue !== "confirm") return;
    void (async () => {
      try {
        await skipRun(skipRoutine);
        setMessage(`${skipRoutine} skipped.`);
        window.dispatchEvent(new CustomEvent("deepwork:changed"));
      } catch (e) {
        setMessage(e instanceof Error ? e.message : String(e), true);
      }
    })();
  });

  d.addEventListener("cancel", (ev) => {
    if (!dirty) return;
    // Prevent first: whether to close is answered asynchronously.
    ev.preventDefault();
    void confirmAction("Discard unsaved changes?").then((discard) => {
      if (!discard) return;
      dirty = false;
      message = "";
      d.close();
    });
  });
}

function btnIndex(el: HTMLElement): string {
  return el.dataset.index ?? "0";
}

start();
