// Text for the HUD. Wording follows the CLI (crates/cli/src/skyline.rs).
import type { World, WorldEvent } from "./proto";

export const TIERS = ["Hamlet", "Town", "City", "Metropolis"];
export const BUILDINGS = ["house", "shop", "tower block", "high-rise", "landmark tower"];

/** `25:00`, or `1:05:09` past an hour. */
export function clock(secs: number): string {
  secs = Math.max(0, Math.floor(secs));
  const h = Math.floor(secs / 3600);
  const m = Math.floor(secs / 60) % 60;
  const s = secs % 60;
  const mm = String(m).padStart(h ? 2 : 1, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function hm(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor(secs / 60) % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

export function ago(secs: number): string {
  if (secs < 60) return "now";
  if (secs < 3600) return `${Math.floor(secs / 60)} min`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h`;
  return `${Math.floor(secs / 86400)} d`;
}

function plots(list: number[]): string {
  const names = list.map((i) => String(i + 1));
  return names.length === 1 ? `plot ${names[0]}` : `plots ${names.join(", ")}`;
}

/** Whether an event cost the player something. */
export const isLoss = (e: WorldEvent) => e.kind === "collapsed" || e.kind === "quake" || e.kind === "damaged";

export function describe(w: World, e: WorldEvent): string {
  const ruined = e.ruined.length ? `; ${plots(e.ruined)} fell into rubble` : "";
  let text: string;
  switch (e.kind) {
    case "built": {
      const p = w.plots[e.plots[0]];
      const what = p && p.session_id === e.session_id ? BUILDINGS[Math.min(4, p.grade)] : "building";
      text = `built a ${what} (${plots(e.plots)})`;
      break;
    }
    case "repaired":
      text = `repaired ${plots(e.plots)}`;
      break;
    case "collapsed": {
      const [site, ...burned] = e.plots;
      const fire = burned.length ? `, fire spread to ${plots(burned)}` : "";
      text = `surrendered: plot ${(site ?? 0) + 1} collapsed${fire}`;
      break;
    }
    case "quake":
      text = e.plots.length ? `earthquake (tampering) hit ${plots(e.plots)}` : "earthquake (tampering) on empty land";
      break;
    case "damaged": {
      const why = e.cause === "clock_jump" ? "wall clock jump" : "refused root access";
      text = e.plots.length ? `${why} damaged ${plots(e.plots)}` : `${why}, nothing to damage yet`;
      break;
    }
  }
  return text + ruined;
}

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
export const DAY_NAMES: Record<string, string> = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };

/** `14:05`, local. */
export function hhmm(ts: number): string {
  const d = new Date(ts * 1000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** `Today`, `Yesterday`, `Sat`, or `12 Oct` further back. */
export function dayName(ts: number, now: number): string {
  const d = new Date(ts * 1000);
  const today = new Date(now * 1000);
  today.setHours(0, 0, 0, 0);
  const back = Math.round((today.getTime() - new Date(d).setHours(0, 0, 0, 0)) / 86400_000);
  if (back <= 0) return back === 0 ? "Today" : "Tomorrow";
  if (back === 1) return "Yesterday";
  if (back < 7) return WEEKDAYS[d.getDay()];
  return `${d.getDate()} ${d.toLocaleString("en", { month: "short" })}`;
}

export const weekday = (ts: number) => WEEKDAYS[new Date(ts * 1000).getDay()];
