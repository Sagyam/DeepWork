// The residents' letters (`Letter` in proto.ts): the mailbox's unread count
// and the letters sheet. Which letters were read is a per-window note, like
// the theme: reading earns nothing, so the daemon never needs to know.
import { dayName, escapeHtml } from "./format";
import type { Letter, World } from "./proto";

const KEY = "deepwork.lettersRead";

/** The newest letter's time the mailbox was last opened at, or null on a first run. */
export function readUpTo(): number | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === null ? null : Number(v) || 0;
  } catch {
    return null;
  }
}

export function markRead(ts: number) {
  try {
    localStorage.setItem(KEY, String(ts));
  } catch {
    // Private windows: unread again next time.
  }
}

/** Letters after `readTs`. A first run (null) starts with none unread, not a backlog. */
export function unread(letters: Letter[], readTs: number | null): number {
  if (readTs === null) return 0;
  return letters.filter((l) => l.ts > readTs).length;
}

export function newest(letters: Letter[]): number {
  return letters.reduce((m, l) => Math.max(m, l.ts), 0);
}

/** Newest first, each with its writers' signature and, when about a building, a link to its deed. */
export function lettersHtml(w: World, readTs: number | null, now: number): string {
  const letters = [...(w.letters ?? [])].reverse();
  if (!letters.length) return `<p class="small muted">No letters yet. Families write when something you built or paid for reaches them: a paved street, a mended home, a new school.</p>`;
  const built = new Set(w.plots.map((p) => p.index));
  return `<ul class="letters">${letters
    .map((l) => {
      const fresh = readTs !== null && l.ts > readTs;
      const see = l.lot != null && built.has(l.lot) ? `<button class="link" data-action="letter-deed" data-lot="${l.lot}">See it</button>` : "";
      return `<li class="letter${fresh ? " fresh" : ""}">
          <div class="letter-head"><span class="small muted">${dayName(l.ts, now)}</span>${see}</div>
          <p>${escapeHtml(l.text)}</p>
          <p class="sign">${escapeHtml(l.from)}<span class="small muted">, ${escapeHtml(l.address)}</span></p>
        </li>`;
    })
    .join("")}</ul>`;
}
