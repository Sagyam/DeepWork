// The weather: by default the day's, picked from the date and the season,
// the same all day and for everyone; or, when the viewer turns it on in
// Settings, the live weather where they are (live.ts maps Open-Meteo's
// report to a Weather with fromReport()). Pure, so it is tested; scene.ts
// and sky.ts draw it. Ambience only: it rewards nothing (docs/GAME.md, the
// one rule).

export type WeatherKind = "clear" | "fair" | "haze" | "overcast" | "fog" | "drizzle" | "rain" | "storm" | "snow";

export const KINDS: WeatherKind[] = ["clear", "fair", "haze", "overcast", "fog", "drizzle", "rain", "storm", "snow"];

export interface Weather {
  kind: WeatherKind;
  /** 0 clear sky to 1 a full lid of cloud. */
  cloud: number;
  /** How heavy the cloud is: 0 white fair-weather cloud to 1 a storm's slate. */
  dark: number;
  /** Falling rain, 0 dry to 1 a downpour. */
  rain: number;
  /** Falling snow, 0 none to 1 heavy. */
  snow: number;
  /** Snow lying on roofs and ground, 0 none to 1 a full cover. */
  cover: number;
  /** Wet streets and puddles, 0 dry to 1 soaked. */
  wet: number;
  /** Fog, 0 the usual distance haze to 1 a few hundred metres. */
  fog: number;
  /** Wind, 0 still to 1 a gale: slants rain, drives snow, moves clouds. */
  wind: number;
  /** Lightning in the clouds. */
  lightning: boolean;
}

const BASE: Omit<Weather, "kind"> = { cloud: 0, dark: 0, rain: 0, snow: 0, cover: 0, wet: 0, fog: 0, wind: 0.2, lightning: false };

export const LOOKS: Record<WeatherKind, Omit<Weather, "kind">> = {
  clear: { ...BASE },
  fair: { ...BASE, cloud: 0.4, wind: 0.3 },
  haze: { ...BASE, cloud: 0.15, fog: 0.35, wind: 0.1 },
  overcast: { ...BASE, cloud: 0.92, dark: 0.35, wind: 0.35 },
  fog: { ...BASE, cloud: 1, dark: 0.15, fog: 1, wet: 0.25, wind: 0 },
  drizzle: { ...BASE, cloud: 0.95, dark: 0.4, rain: 0.3, wet: 0.6, fog: 0.3, wind: 0.25 },
  rain: { ...BASE, cloud: 1, dark: 0.6, rain: 0.75, wet: 1, fog: 0.35, wind: 0.45 },
  storm: { ...BASE, cloud: 1, dark: 0.95, rain: 1, wet: 1, fog: 0.45, wind: 0.9, lightning: true },
  snow: { ...BASE, cloud: 1, dark: 0.3, snow: 0.7, cover: 1, fog: 0.4, wind: 0.3 },
};

/** Out of a hundred days, by season. */
const ODDS: Record<"winter" | "shoulder" | "summer", [WeatherKind, number][]> = {
  winter: [["clear", 22], ["fair", 18], ["haze", 6], ["overcast", 18], ["fog", 8], ["drizzle", 4], ["rain", 4], ["snow", 20]],
  shoulder: [["clear", 25], ["fair", 25], ["haze", 8], ["overcast", 14], ["fog", 6], ["drizzle", 8], ["rain", 9], ["storm", 2], ["snow", 3]],
  summer: [["clear", 38], ["fair", 28], ["haze", 10], ["overcast", 8], ["fog", 2], ["drizzle", 4], ["rain", 5], ["storm", 5]],
};

/** Month (0-11) to season; `south` flips the year for the southern hemisphere. */
function season(month: number, south = false): keyof typeof ODDS {
  const m = south ? (month + 6) % 12 : month;
  if (m === 11 || m <= 1) return "winter";
  if (m >= 5 && m <= 7) return "summer";
  return "shoulder";
}

export function look(kind: WeatherKind): Weather {
  return { kind, ...LOOKS[kind] };
}

/** The weather of a local calendar day (`days`: days since 1970-01-01). */
export function weatherOn(days: number, south = false): Weather {
  let h = Math.imul(days ^ 0x5bd1e995, 0x27d4eb2d);
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
  let roll = ((h ^ (h >>> 13)) >>> 0) % 100;
  const odds = ODDS[season(new Date(days * 86_400_000).getUTCMonth(), south)];
  for (const [kind, n] of odds) {
    if (roll < n) return look(kind);
    roll -= n;
  }
  return look("clear");
}

/** `?weather=rain` (or any kind) forces one, for the mock and screenshots. */
export function forcedWeather(): Weather | null {
  const forced = new URLSearchParams(globalThis.location?.search ?? "").get("weather");
  return forced && forced in LOOKS ? look(forced as WeatherKind) : null;
}

/** The day's weather by the local date. */
export function weatherByDate(now = new Date(), south = false): Weather {
  const days = Math.floor(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) / 86_400_000);
  return weatherOn(days, south);
}

/** Open-Meteo's `current` block, the fields live.ts asks for. */
export interface Report {
  weather_code: number;
  /** Percent. */
  cloud_cover?: number;
  /** km/h. */
  wind_speed_10m?: number;
  /** Metres. */
  visibility?: number;
  /** Metres of snow lying. */
  snow_depth?: number;
  /** mm in the last hour. */
  precipitation?: number;
}

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

/** A live report as a Weather: the WMO code picks the kind, the measurements tune it. */
export function fromReport(r: Report): Weather {
  const c = r.weather_code;
  let w: Weather;
  if (c === 0) w = look("clear");
  else if (c === 1 || c === 2) w = { ...look("fair"), cloud: c === 1 ? 0.25 : 0.5 };
  else if (c === 3) w = look("overcast");
  else if (c === 45 || c === 48) w = look("fog");
  else if (c >= 51 && c <= 57) w = { ...look("drizzle"), rain: [0.2, 0.3, 0.45][Math.min(2, Math.floor((c - 51) / 2))] };
  else if ((c >= 61 && c <= 67) || (c >= 80 && c <= 82)) w = { ...look("rain"), rain: c === 61 || c === 66 || c === 80 ? 0.5 : c === 63 || c === 81 ? 0.75 : 1 };
  else if ((c >= 71 && c <= 77) || c === 85 || c === 86) w = { ...look("snow"), snow: c === 71 || c === 77 || c === 85 ? 0.4 : c === 73 ? 0.7 : 1 };
  else if (c >= 95) w = look("storm");
  else w = look("clear");
  if (r.cloud_cover !== undefined && w.rain === 0 && w.snow === 0 && w.kind !== "fog") w.cloud = clamp01(r.cloud_cover / 100);
  if (r.wind_speed_10m !== undefined) w.wind = clamp01(r.wind_speed_10m / 50);
  if (r.visibility !== undefined && r.visibility < 5000) w.fog = Math.max(w.fog, clamp01(1 - r.visibility / 5000));
  // Snow on the ground outlasts the snowfall; a few centimetres whiten the town.
  if (r.snow_depth !== undefined) w.cover = Math.max(w.snow > 0 ? 0.6 : 0, clamp01(r.snow_depth / 0.05));
  if (w.cover > 0) w.wet = 0;
  return w;
}
