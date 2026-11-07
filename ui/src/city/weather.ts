// The day's weather: clear, hazy, overcast or rain, the same all day and
// the same for everyone on that date. Pure, so it is tested; scene.ts dims
// the sun, thickens the haze and draws the rain from it. Ambience only: it
// rewards nothing (docs/GAME.md, the one rule).

export type WeatherKind = "clear" | "haze" | "overcast" | "rain";

export interface Weather {
  kind: WeatherKind;
  /** 0 clear sky to 1 a full grey lid. */
  cloud: number;
  /** 0 dry to 1 a steady rain. */
  rain: number;
}

/** Out of a hundred days. */
const ODDS: [WeatherKind, number][] = [["clear", 55], ["haze", 20], ["overcast", 15], ["rain", 10]];

const LOOKS: Record<WeatherKind, Omit<Weather, "kind">> = {
  clear: { cloud: 0, rain: 0 },
  haze: { cloud: 0.3, rain: 0 },
  overcast: { cloud: 0.75, rain: 0 },
  rain: { cloud: 0.9, rain: 1 },
};

/** The weather of a local calendar day (`days`: days since 1970-01-01). */
export function weatherOn(days: number): Weather {
  let h = Math.imul(days ^ 0x5bd1e995, 0x27d4eb2d);
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
  let roll = ((h ^ (h >>> 13)) >>> 0) % 100;
  for (const [kind, odds] of ODDS) {
    if (roll < odds) return { kind, ...LOOKS[kind] };
    roll -= odds;
  }
  return { kind: "clear", ...LOOKS.clear };
}

/** Today's, by the local date; `?weather=rain` (and the others) forces one. */
export function weatherNow(now = new Date()): Weather {
  const forced = new URLSearchParams(globalThis.location?.search ?? "").get("weather") as WeatherKind | null;
  if (forced && forced in LOOKS) return { kind: forced, ...LOOKS[forced] };
  const days = Math.floor((Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())) / 86_400_000);
  return weatherOn(days);
}
