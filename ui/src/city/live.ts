// Live weather, opt-in: the viewer names a place in Settings, and the city
// shows the weather there now, from Open-Meteo (free, no key, no account).
// A view preference like the theme: kept in this window's localStorage,
// never sent to deepworkd. Off, or with no answer for three hours, the city
// falls back to the day's weather by date (weather.ts). The only thing sent
// is the place's coordinates, rounded to about a kilometre.
import { forcedWeather, fromReport, weatherByDate, type Report, type Weather } from "./weather";

export interface Place {
  name: string;
  /** Region and country, for telling one Springfield from another. */
  detail: string;
  lat: number;
  lon: number;
}

export interface WeatherPref {
  live: boolean;
  place: Place | null;
}

interface Cached {
  at: number;
  lat: number;
  lon: number;
  report: Report;
}

const KEY = "weather";
const CACHE = "weather.live";
/** How often to ask again while the window is open. */
const EVERY = 15 * 60_000;
/** How long an answer stands in when the next ask fails (offline, the API down). */
const STALE = 3 * 3600_000;
const FORECAST = "https://api.open-meteo.com/v1/forecast";
const GEOCODE = "https://geocoding-api.open-meteo.com/v1/search";
const FIELDS = "weather_code,cloud_cover,wind_speed_10m,visibility,snow_depth,precipitation";

const listeners = new Set<(w: Weather) => void>();
let timer: ReturnType<typeof setInterval> | null = null;

function read<T>(key: string): T | null {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Still applies to this window.
  }
}

export function weatherPref(): WeatherPref {
  const p = read<WeatherPref>(KEY);
  return { live: !!p?.live && !!p.place, place: p?.place ?? null };
}

export function setWeatherPref(p: WeatherPref) {
  write(KEY, p.place ? p : null);
  if (!p.live) write(CACHE, null);
  schedule();
  notify();
  if (p.live) void refresh();
}

/** The live answer for the chosen place, if one is fresh enough. */
function cached(): Cached | null {
  const { live, place } = weatherPref();
  const c = read<Cached>(CACHE);
  if (!live || !place || !c) return null;
  if (Math.abs(c.lat - round(place.lat)) > 1e-6 || Math.abs(c.lon - round(place.lon)) > 1e-6) return null;
  return Date.now() - c.at < STALE ? c : null;
}

/** The weather to draw now: forced by the URL, live, or the day's. */
export function currentWeather(): Weather {
  const forced = forcedWeather();
  if (forced) return forced;
  const c = cached();
  if (c) return fromReport(c.report);
  const place = weatherPref().place;
  return weatherByDate(new Date(), !!place && place.lat < 0);
}

/** One line for Settings: what the city shows and why. */
export function weatherLine(): string {
  const { live, place } = weatherPref();
  const w = currentWeather();
  const c = cached();
  if (live && place && c) {
    const at = new Date(c.at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    return `${cap(w.kind)} in ${place.name} now (checked ${at}).`;
  }
  if (live && place) return `Asking for the weather in ${place.name}… Until it answers, the city shows the day's weather (${w.kind}).`;
  return `The day's weather, picked by the date and season: ${w.kind} today.`;
}

const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

/** About a kilometre: enough for the weather, less of a fingerprint. */
const round = (x: number) => Math.round(x * 100) / 100;

async function getJson<T>(url: string): Promise<T> {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 10_000);
  try {
    const res = await fetch(url, { signal: ctl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

/** Places matching what the viewer typed, best first. */
export async function findPlaces(query: string): Promise<Place[]> {
  const q = query.trim();
  if (q.length < 2) return [];
  const data = await getJson<{ results?: { name: string; latitude: number; longitude: number; admin1?: string; country?: string }[] }>(
    `${GEOCODE}?name=${encodeURIComponent(q)}&count=5&language=en&format=json`,
  );
  return (data.results ?? []).map((r) => ({
    name: r.name,
    detail: [r.admin1, r.country].filter(Boolean).join(", "),
    lat: r.latitude,
    lon: r.longitude,
  }));
}

/** Asks for the weather at the chosen place now; tells the listeners when it changes. */
export async function refresh(): Promise<void> {
  const { live, place } = weatherPref();
  if (!live || !place) return;
  const lat = round(place.lat);
  const lon = round(place.lon);
  try {
    const data = await getJson<{ current?: Report }>(`${FORECAST}?latitude=${lat}&longitude=${lon}&current=${FIELDS}`);
    if (!data.current || typeof data.current.weather_code !== "number") return;
    const before = JSON.stringify(currentWeather());
    write(CACHE, { at: Date.now(), lat, lon, report: data.current } satisfies Cached);
    if (JSON.stringify(currentWeather()) !== before) notify();
  } catch {
    // Offline or the API is down: the last answer stands for a while, then the day's weather.
  }
}

function notify() {
  const w = currentWeather();
  for (const f of listeners) f(w);
}

function schedule() {
  const { live } = weatherPref();
  if (live && !timer) timer = setInterval(() => void refresh(), EVERY);
  if (!live && timer) {
    clearInterval(timer);
    timer = null;
  }
}

/** Calls `f` whenever the weather to draw changes; starts asking if live weather is on. */
export function onWeather(f: (w: Weather) => void) {
  listeners.add(f);
  if (listeners.size === 1) {
    schedule();
    if (!cached() || Date.now() - (read<Cached>(CACHE)?.at ?? 0) > EVERY) void refresh();
  }
}
