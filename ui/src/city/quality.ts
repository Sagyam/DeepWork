// Quality presets for the city, for weak iGPUs on large windows. A view
// preference like the theme: kept in this window's localStorage, never sent
// to deepworkd. `?quality=low|medium|high` overrides it (benches).
import type { ShadowTaps } from "./shadow";

export type Quality = "low" | "medium" | "high";

export interface QualitySpec {
  /** Render pixels per CSS pixel. */
  scale: number;
  /** MSAA samples; never 0: cut-out leaves use alpha to coverage. */
  msaa: 2 | 4;
  /** Side of the sun's shadow map. */
  shadow: number;
  taps: ShadowTaps;
  bloom: boolean;
}

export const QUALITY: Record<Quality, QualitySpec> = {
  low: { scale: 0.67, msaa: 2, shadow: 1024, taps: 1, bloom: false },
  medium: { scale: 0.85, msaa: 4, shadow: 2048, taps: 4, bloom: false },
  high: { scale: 1, msaa: 4, shadow: 2048, taps: 4, bloom: true },
};

export const QUALITIES: { key: Quality; label: string }[] = [
  { key: "low", label: "Low" },
  { key: "medium", label: "Medium" },
  { key: "high", label: "High" },
];

const KEY = "quality";
const listeners = new Set<(q: Quality) => void>();

function valid(v: string | null): v is Quality {
  return v === "low" || v === "medium" || v === "high";
}

export function qualityPref(): Quality {
  const url = new URLSearchParams(location.search).get("quality");
  if (valid(url)) return url;
  try {
    const v = localStorage.getItem(KEY);
    return valid(v) ? v : "high";
  } catch {
    return "high";
  }
}

export function setQualityPref(q: Quality) {
  try {
    if (q === "high") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, q);
  } catch {
    // Still applies to this window.
  }
  for (const f of listeners) f(q);
}

/** Calls `f` whenever the preference changes. */
export function onQuality(f: (q: Quality) => void) {
  listeners.add(f);
}
