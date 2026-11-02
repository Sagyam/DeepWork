// The small pure parts of the settings sheet, kept out of the DOM module so
// they can be unit tested (`bun test`).
import type { Config } from "./proto";

/** Turns what a person pasted into a rule domain. */
export function cleanDomain(raw: string): string {
  let d = raw.trim().toLowerCase();
  d = d.replace(/^[a-z][a-z0-9+.-]*:\/\//, "");
  d = d.split(/[/?#]/)[0].replace(/:\d+$/, "");
  return d.replace(/^\*\./, "").replace(/\.$/, "");
}

/** Sets a dotted path (`profiles.deep.rules.0.action`) in a plain object. */
export function putPath(root: unknown, path: string, next: unknown): void {
  const parts = path.split(".");
  let at = root as Record<string, unknown>;
  for (const key of parts.slice(0, -1)) at = at[key] as Record<string, unknown>;
  at[parts[parts.length - 1]] = next;
}

/** The configured default profile when it exists, else the first one. */
export function defaultProfileName(c: Config): string {
  return c.profiles[c.session.default_profile]
    ? c.session.default_profile
    : (Object.keys(c.profiles)[0] ?? "");
}
