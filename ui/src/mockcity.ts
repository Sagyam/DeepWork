// The mock daemon's city: a small mirror of the daemon's fold
// (crates/daemon/src/world.rs, plan.rs) so the mayor's desk, the shop and
// the renderer can be developed in a browser. Simplified on purpose (no
// streak bonuses, freezes, session repairs or wealth in prices; the
// scenarios get their land free); the daemon is the truth. The layout is
// the daemon's own (`layout.json`, kept current by a Rust test).
import FIXTURE from "./layout.json";
import type { Award, BlueprintInfo, Construction, GoalInfo, Layout, NeedInfo, Plot, SetInfo, SiteInfo, World, WorldEvent } from "./proto";

const LAYOUT = FIXTURE as Layout;
const LAND: Record<string, number> = { village: 60, works: 80, civic: 100, main_street: 120, downtown: 250 };
const ROADS: [number, number][] = [[0, 0], [150, 0], [400, 1], [900, 2]];
const DECORATIONS = [
  { id: "trees", name: "A ring of trees", price: 80, level: 0 },
  { id: "benches", name: "Benches and lamps", price: 120, level: 0 },
  { id: "fountain", name: "Fountain", price: 350, level: 1 },
  { id: "statue", name: "Statue of the founder", price: 450, level: 1 },
  { id: "bandstand", name: "Bandstand", price: 600, level: 2 },
];
const GOALS = [
  { id: "daily_focus", title: "Two hours of focus today", target: 7200 },
  { id: "long_stretch", title: "One 90-minute session", target: 5400 },
  { id: "sessions", title: "Three sessions today", target: 3 },
];
const ITEMS: Record<string, string> = { repair_kit: "Repair kit", hired_help: "Hired help", master_crew: "Master crew" };

interface Need { id: string; level: number; title: string; words: string; kind: string; district: string; lots: number }

const MIN = 60;
const BUILD: Record<string, number> = {
  water: 30, power: 30, cottage: 60, shop: 90, workshop: 120, square: 180, apartment: 240, park: 240,
  school: 300, clinic: 300, fire_station: 300, police: 360, library: 360, office: 480, hospital: 720, city_hall: 720, tower: 1500,
};
const DESIGNED = new Set(["cottage", "shop", "workshop", "apartment", "office", "tower"]);
const GRADE: Record<string, number> = {
  water: 0, power: 0, cottage: 0, shop: 1, workshop: 1, square: 1, park: 1, apartment: 2, school: 2, clinic: 2,
  fire_station: 2, police: 2, library: 2, office: 3, hospital: 3, city_hall: 3, tower: 4,
};

const NEEDS: Need[] = [
  { id: "hamlet-homes", level: 0, title: "Housing shortage", words: "Four families share the old farmhouse.", kind: "cottage", district: "village", lots: 4 },
  { id: "hamlet-shops", level: 0, title: "Small business", words: "We walk an hour to buy a loaf of bread.", kind: "shop", district: "main_street", lots: 2 },
  { id: "hamlet-jobs", level: 0, title: "Jobs", words: "The young ones leave to find work.", kind: "workshop", district: "works", lots: 1 },
  { id: "hamlet-water", level: 0, title: "Water", words: "We still carry water up from the river.", kind: "water", district: "civic", lots: 1 },
  { id: "hamlet-power", level: 0, title: "Electricity", words: "Candles at night, and the pump is worked by hand.", kind: "power", district: "civic", lots: 1 },
  { id: "town-homes", level: 1, title: "More homes", words: "Newcomers are sleeping above the shops.", kind: "cottage", district: "village", lots: 4 },
  { id: "town-flats", level: 1, title: "Apartments", words: "Young couples cannot find a place to rent.", kind: "apartment", district: "main_street", lots: 2 },
  { id: "town-shops", level: 1, title: "Shops and a café", words: "There is nowhere to sit and talk.", kind: "shop", district: "main_street", lots: 3 },
  { id: "town-jobs", level: 1, title: "Work", words: "The works turns people away every Monday.", kind: "workshop", district: "works", lots: 2 },
  { id: "town-school", level: 1, title: "A school", words: "Our children ride the bus two towns over.", kind: "school", district: "civic", lots: 1 },
  { id: "town-clinic", level: 1, title: "A clinic", words: "The nearest doctor is forty minutes away.", kind: "clinic", district: "civic", lots: 1 },
  { id: "town-fire", level: 1, title: "A fire station", words: "The barn fire last spring burned for an hour before help came.", kind: "fire_station", district: "civic", lots: 1 },
  { id: "town-square", level: 1, title: "A square", words: "A town needs somewhere to gather.", kind: "square", district: "civic", lots: 1 },
  { id: "town-water", level: 1, title: "More water", words: "The taps run dry on wash day.", kind: "water", district: "civic", lots: 1 },
  { id: "town-power", level: 1, title: "More power", words: "The lights dim when the works runs late.", kind: "power", district: "civic", lots: 1 },
  { id: "city-offices", level: 2, title: "Offices", words: "Firms want to move here, but there are no desks.", kind: "office", district: "downtown", lots: 6 },
  { id: "city-flats", level: 2, title: "Apartments", words: "Rents doubled when the offices came.", kind: "apartment", district: "downtown", lots: 6 },
  { id: "city-shops", level: 2, title: "Shops", words: "Downtown closes at five.", kind: "shop", district: "downtown", lots: 6 },
  { id: "city-hospital", level: 2, title: "A hospital", words: "The clinic sends the serious cases away.", kind: "hospital", district: "civic", lots: 1 },
  { id: "city-police", level: 2, title: "A police station", words: "Bikes go missing from the station racks.", kind: "police", district: "civic", lots: 1 },
  { id: "city-library", level: 2, title: "A library", words: "The students study in the café until it closes.", kind: "library", district: "civic", lots: 1 },
  { id: "city-park", level: 2, title: "A park", words: "There is not a tree downtown.", kind: "park", district: "civic", lots: 1 },
  { id: "city-hall", level: 2, title: "City hall", words: "The council still meets above the bakery.", kind: "city_hall", district: "civic", lots: 1 },
  { id: "city-landmark", level: 2, title: "A landmark", words: "Nobody would know our skyline.", kind: "tower", district: "downtown", lots: 1 },
  { id: "city-water", level: 2, title: "Water mains", words: "The old mains burst every winter.", kind: "water", district: "civic", lots: 1 },
  { id: "city-power", level: 2, title: "A power station", words: "Every new tower trips the grid.", kind: "power", district: "civic", lots: 1 },
  { id: "metro-towers", level: 3, title: "Towers", words: "Head offices want an address on the skyline.", kind: "tower", district: "downtown", lots: 3 },
  { id: "metro-offices", level: 3, title: "More offices", words: "Start-ups share desks in the library.", kind: "office", district: "downtown", lots: 6 },
  { id: "metro-flats", level: 3, title: "More apartments", words: "People commute in from three towns away.", kind: "apartment", district: "downtown", lots: 6 },
  { id: "metro-shops", level: 3, title: "Late shops", words: "A city this size should never sleep.", kind: "shop", district: "downtown", lots: 4 },
];

const BLUEPRINTS: Omit<BlueprintInfo, "owned" | "unlocked" | "built">[] = [
  { id: "c1", name: "Clapboard farmhouse", kind: "cottage", districts: ["village"], level: 0, price: 0 },
  { id: "c2", name: "Brick cottage", kind: "cottage", districts: ["village"], level: 0, price: 250 },
  { id: "c4", name: "A-frame cabin", kind: "cottage", districts: ["village"], level: 0, price: 250 },
  { id: "s1", name: "Main-street shop", kind: "shop", districts: ["main_street", "downtown"], level: 0, price: 300 },
  { id: "s3", name: "Diner", kind: "shop", districts: ["main_street"], level: 0, price: 400 },
  { id: "s4", name: "Brick factory", kind: "workshop", districts: ["works"], level: 0, price: 400 },
  { id: "c3", name: "Modern house", kind: "cottage", districts: ["village"], level: 1, price: 400 },
  { id: "s2", name: "Corner café", kind: "shop", districts: ["main_street", "downtown"], level: 1, price: 500 },
  { id: "a1", name: "Brick apartment block", kind: "apartment", districts: ["main_street", "downtown"], level: 1, price: 800 },
  { id: "a2", name: "Brownstone row", kind: "apartment", districts: ["main_street", "downtown"], level: 1, price: 900 },
  { id: "a3", name: "Balcony block", kind: "apartment", districts: ["main_street", "downtown"], level: 1, price: 900 },
  { id: "o1", name: "Curtain-wall office tower", kind: "office", districts: ["downtown"], level: 2, price: 1500 },
  { id: "l1", name: "Art deco skyscraper", kind: "tower", districts: ["downtown"], level: 2, price: 3000 },
];

const SURNAMES = ["Hart", "Fletcher", "Moreau", "Okafor", "Lindqvist", "Brennan", "Castillo", "Novak", "Whitlock", "Sato", "Abernathy", "Rossi"];
const TRADES = ["Bakery", "Grocery", "Hardware", "Books", "Tailors", "Pharmacy"];

interface Lot { index: number; id: string; need: number; name: string; address: string }
const LOTS: Lot[] = [];
for (const [ni, n] of NEEDS.entries()) {
  for (let k = 1; k <= n.lots; k++) {
    const i = LOTS.length;
    const sur = SURNAMES[(i * 7 + 3) % SURNAMES.length];
    const name = ({ cottage: `The ${sur} house`, shop: `${sur}'s ${TRADES[(i * 5) % TRADES.length]}`, workshop: `${sur} & Sons Works`, apartment: `${sur} Court`, office: `${sur} Building`, tower: `${sur} Tower`, water: "Water tower", power: "Substation" } as Record<string, string>)[n.kind] ?? n.title.replace(/^An? /, "The ");
    LOTS.push({ index: i, id: `${n.id}-${k}`, need: ni, name, address: LAYOUT.lots[i]?.address ?? "" });
  }
}

/** A few names from the daemon's piles (`crates/daemon/names/`), by design; the first free one is dealt. */
const PILES: Record<string, string[]> = {
  c1: ["Hart Farm", "Old Orchard Farm", "Brook Farm", "Fletcher's Farm"],
  c2: ["The Hart house", "Willowbank", "The Okafor house", "Rosemount"],
  c3: ["The Hart house", "Willowbank", "The Okafor house", "Rosemount"],
  c4: ["Pine Hollow", "Larch Cabin", "The Bothy", "Fir Lodge"],
  s1: ["Rossi & Sons", "Harbour Books", "Marlowe's", "Green & Co.", "Kovac Hardware", "Pier Pharmacy", "Fletcher's Bakery", "Moreau Fine Foods"],
  s2: ["Café des Arts", "Caffè Bellavista", "Kaffeehaus Rose", "Café du Coin", "Café Amadeus", "Café Lumière"],
  s3: ["Starlite Diner", "Moonbeam Diner", "Silver Spoon"],
  s4: ["Hollis & Ward · Engineers", "Brandt Machine Works", "Northgate Foundry Co."],
  a1: ["Ardmore Court", "Belgrave Mansions", "Carlisle Court", "Danbury House", "Edgewood Court", "Fairview Mansions"],
  a2: ["Linden Row", "Chestnut Row", "Ardmore Court", "Belgrave Mansions", "Carlisle Court", "Danbury House"],
  a3: ["Ardmore Court", "Belgrave Mansions", "Carlisle Court", "Danbury House", "Edgewood Court", "Fairview Mansions"],
  o1: ["Meridian House", "One Harbour Place", "Carlton Tower", "Northbridge Centre", "The Exchange", "Atlas Building", "200 Park Row", "Sovereign House", "Pinnacle House", "Riverside Plaza", "The Foundry Building", "Quayside Centre"],
  l1: ["The Orion Building", "Halcyon Tower", "Continental Life", "The Zenith Building"],
};

const fits = (b: { kind: string; districts: string[] }, n: Need) => b.kind === n.kind && b.districts.includes(n.district);
const buildSecs = (i: number) => BUILD[NEEDS[LOTS[i].need].kind] * MIN;

interface Built { design: string | null; damage: number; shiny: boolean; name: string | null; at: number; parts: { session_id: number; ts: number; secs: number; session_secs: number }[] }

export class MockCity {
  built = new Map<number, Built>();
  sites = new Map<number, { design: string | null; done: number }>();
  active: number | null = null;
  owned = new Set(["c1"]);
  earned = 0;
  spent = 0;
  idle = 0;
  level = 0;
  manual = false;
  focused = 0;
  streak = 0;
  history: WorldEvent[] = [];
  /** Names dealt when a lot got its design, as the daemon deals them. */
  dealt = new Map<number, string>();
  /** Land bought: the first plot is free. Scenarios set `freeLand` while they grow. */
  land = new Set([0]);
  freeLand = false;
  roads: number[] = LAYOUT.streets.map(() => 0);
  streetNames = new Map<number, string>();
  spots = new Map<string, string>();
  inventory = new Map<string, number>();
  setsWon = new Set<string>();
  today = { day: -1, focus: 0, sessions: 0, longest: 0, paid: new Set<string>() };
  stakes = new Map<number, number>();
  recent: number[] = [];

  /** The lot's name: the mayor's, else the one dealt for its design, else the plan's. */
  nameOf(i: number, design: string | null): string {
    const own = this.built.get(i)?.name;
    if (own) return own;
    if (!design || !PILES[design]) return LOTS[i].name;
    let name = this.dealt.get(i);
    if (!name) {
      const taken = new Set([...this.dealt.entries()].filter(([j]) => j !== i).map(([, n]) => n.toUpperCase()));
      for (const b of this.built.values()) if (b.name) taken.add(b.name.toUpperCase());
      const pile = PILES[design];
      // The mock's piles are short: past them, the plan's name.
      name = pile.find((n) => !taken.has(n.toUpperCase())) ?? LOTS[i].name;
      this.dealt.set(i, name);
    }
    return name;
  }
  award: Award | null = null;
  private sessionId = 1000;

  coins() {
    return this.earned - this.spent;
  }

  private nextLot(ni: number): number | null {
    return LOTS.find((l) => l.need === ni && !this.built.has(l.index))?.index ?? null;
  }

  private open(ni: number) {
    return NEEDS[ni].level === this.level && this.nextLot(ni) !== null;
  }

  private owns(i: number): boolean {
    if (this.freeLand) this.land.add(i);
    return this.land.has(i);
  }

  private autoPick(): number | null {
    for (const [ni, n] of NEEDS.entries()) {
      if (!this.open(ni) || !this.owns(this.nextLot(ni)!)) continue;
      let design: string | null = null;
      if (DESIGNED.has(n.kind)) {
        const own = BLUEPRINTS.find((b) => fits(b, n) && this.owned.has(b.id));
        if (own) design = own.id;
        else {
          const cheap = BLUEPRINTS.filter((b) => fits(b, n) && b.level <= this.level).sort((a, b) => a.price - b.price)[0];
          if (!cheap || this.coins() < cheap.price) continue;
          this.owned.add(cheap.id);
          this.spent += cheap.price;
          design = cheap.id;
        }
      }
      const lot = this.nextLot(ni)!;
      this.sites.set(lot, { design, done: 0 });
      return lot;
    }
    return null;
  }

  /** Puts focused time into the sites, as a completed session does. */
  pour(secs: number, ts: number, sessionId: number, sessionSecs: number) {
    let left = secs;
    while (left > 0) {
      const a = this.active ?? (this.manual ? null : this.autoPick());
      if (a === null) break;
      this.active = a;
      const site = this.sites.get(a)!;
      const take = Math.min(left, buildSecs(a) - site.done);
      site.done += take;
      left -= take;
      if (site.done >= buildSecs(a)) this.finish(a, ts, sessionId, sessionSecs, site.design);
    }
    this.idle += left;
  }

  private finish(i: number, ts: number, sessionId: number, sessionSecs: number, design: string | null) {
    this.sites.delete(i);
    this.built.set(i, { design, damage: 0, shiny: (i * 37 + sessionId) % 11 === 0, name: null, at: ts, parts: [{ session_id: sessionId, ts, secs: buildSecs(i), session_secs: sessionSecs }] });
    this.active = null;
    this.history.push({ ts, kind: "built", cause: "completed", session_id: sessionId, plots: [i], ruined: [] });
    this.award?.finished.push(i);
    // A set its last lot finishes pays a box (the mock's roll is plain).
    for (const set of this.sets()) {
      if (!set.done || this.setsWon.has(set.id)) continue;
      this.setsWon.add(set.id);
      const item = ["repair_kit", "hired_help", "master_crew"][(sessionId + set.id.length) % 3];
      this.inventory.set(item, (this.inventory.get(item) ?? 0) + 1);
      this.award?.boxes?.push({ goal: "set", item, set: set.name });
    }
    while (this.level < 4 && NEEDS.every((n, ni) => n.level !== this.level || this.nextLot(ni) === null)) {
      this.level++;
      this.history.push({ ts, kind: "graduated", cause: "completed", session_id: sessionId, plots: [], ruined: [] });
    }
    const ni = LOTS[i].need;
    const next = this.nextLot(ni);
    if (this.manual && this.open(ni) && next !== null && this.owns(next)) {
      if (!this.sites.has(next)) this.sites.set(next, { design, done: 0 });
      this.active = next;
    }
  }

  /** A completed session. */
  complete(secs: number, ts: number) {
    const id = ++this.sessionId;
    const mins = Math.floor(secs / 60);
    const units = [[0, 50, 10], [50, 90, 15], [90, 180, 20], [180, 1e9, 10]].reduce((a, [f, t, r]) => a + Math.max(0, Math.min(mins, t) - f) * r, 0);
    const coins = Math.floor(units / 6);
    this.focused += secs;
    this.earned += coins;
    this.award = { session_id: id, ts, coins, length_bonus: coins - Math.floor((mins * 10) / 6), streak_bonus: 0, rested_bonus: 0, build_secs: secs, finished: [], freeze_earned: false, freezes_used: 0, boxes: [] };
    const stake = this.stakes.get(id) ?? 0;
    if (stake) {
      this.stakes.delete(id);
      this.spent -= stake;
      this.earned += stake;
      this.award.stake_won = stake;
    }
    this.recent = [...this.recent, secs].slice(-10);
    const day = Math.floor(ts / 86400);
    if (this.today.day !== day) this.today = { day, focus: 0, sessions: 0, longest: 0, paid: new Set() };
    const t = this.today;
    t.focus += secs;
    t.longest = Math.max(t.longest, secs);
    if (secs >= 1500) t.sessions++;
    for (const g of GOALS) {
      if (t.paid.has(g.id) || this.progress(g.id) < g.target) continue;
      t.paid.add(g.id);
      const item = ["repair_kit", "hired_help", "master_crew"][(id + g.id.length) % 3];
      this.inventory.set(item, (this.inventory.get(item) ?? 0) + 1);
      this.award.boxes!.push({ goal: g.id, item });
    }
    this.pour(secs, ts, id, secs);
  }

  private progress(goal: string): number {
    const t = this.today;
    return goal === "daily_focus" ? t.focus : goal === "long_stretch" ? t.longest : t.sessions;
  }

  /** The id the next session gets, for a stake placed at its start. */
  nextSessionId(): number {
    return this.sessionId + 1;
  }

  stakeTarget(): number {
    if (this.recent.length < 3) return 1500;
    return [...this.recent].sort((a, b) => a - b)[Math.floor(this.recent.length / 2)];
  }

  stake(coins: number, secs: number | null): string | null {
    const target = this.stakeTarget();
    if (secs === null || secs < target) return `a stake needs a countdown of at least ${Math.ceil(target / 60)} minutes, your usual length`;
    if (coins <= 0) return "stake at least one coin";
    if (coins > Math.min(1000, this.coins())) return `the most you can stake now is ${Math.min(1000, this.coins())} coins`;
    this.spent += coins;
    this.stakes.set(this.nextSessionId(), coins);
    return null;
  }

  /** A surrendered session: its stake is lost. */
  surrendered(id: number) {
    this.stakes.delete(id);
  }

  private landPrice(i: number): number {
    const n = NEEDS[LOTS[i].need];
    return LAND[n.district] * (1 + Math.floor(n.level / 2));
  }

  buyLand(lot: string): string | null {
    const l = LOTS.find((l) => l.id === lot);
    if (!l) return `no lot ${lot}`;
    if (this.land.has(l.index)) return `the plot at ${l.address} is already yours`;
    if (NEEDS[l.need].level > this.level) return `the plot at ${l.address} is for sale from a later level`;
    const price = this.landPrice(l.index);
    if (this.coins() < price) return `the plot at ${l.address} costs ${price} coins; you have ${this.coins()}`;
    this.spent += price;
    this.land.add(l.index);
    return null;
  }

  repair(lot: string, kit: boolean): string | null {
    const l = LOTS.find((l) => l.id === lot);
    const b = l && this.built.get(l.index);
    if (!b) return `${lot} is not built yet`;
    if (!b.damage) return "it needs no repair";
    const price = 40 * b.damage;
    if (!kit && this.coins() < price) return `repairing it costs ${price} coins; you have ${this.coins()}`;
    if (!kit) this.spent += price;
    b.damage = 0;
    this.history.push({ ts: Math.floor(Date.now() / 1000), kind: "repaired", cause: "mayor", session_id: null, plots: [l.index], ruined: [] });
    return null;
  }

  upgrade(street: string): string | null {
    const si = LAYOUT.streets.findIndex((s) => s.id === street);
    if (si < 0) return `no street ${street}`;
    const next = ROADS[this.roads[si] + 1];
    if (!next) return "it is already an avenue";
    if (next[1] > this.level) return "not before a later level";
    if (this.coins() < next[0]) return `that costs ${next[0]} coins; you have ${this.coins()}`;
    this.spent += next[0];
    this.roads[si]++;
    return null;
  }

  private streetComplete(si: number): boolean {
    const on = LAYOUT.lots.flatMap((l, i) => (l.street === si ? [i] : []));
    return on.length > 0 && on.every((i) => this.built.has(i));
  }

  /** Collection sets, as the daemon's `Set`: streets, then neighbourhoods, with lots. */
  private sets(): SetInfo[] {
    const of = (test: (l: Layout["lots"][number]) => boolean) => LAYOUT.lots.flatMap((l, i) => (test(l) ? [i] : []));
    const all = [
      ...LAYOUT.streets.map((s, si) => ({ id: `street:${s.id}`, kind: "street" as const, name: this.streetNames.get(si) ?? s.name, lots: of((l) => l.street === si) })),
      ...(LAYOUT.neighbourhoods ?? []).map((h) => ({ id: `hood:${h.id}`, kind: "neighbourhood" as const, name: h.name, lots: of((l) => h.blocks.includes(l.block)) })),
    ];
    return all
      .filter((s) => s.lots.length > 0)
      .map(({ lots, ...s }) => {
        const built = lots.filter((i) => this.built.has(i)).length;
        return { ...s, built, total: lots.length, done: built === lots.length };
      });
  }

  renameStreet(street: string, name: string): string | null {
    const si = LAYOUT.streets.findIndex((s) => s.id === street);
    if (si < 0) return `no street ${street}`;
    if (!this.streetComplete(si)) return "a street can be renamed once every lot on it is built";
    if (name.trim()) this.streetNames.set(si, name.trim());
    else this.streetNames.delete(si);
    return null;
  }

  decorate(spot: string, id: string): string | null {
    const d = DECORATIONS.find((d) => d.id === id);
    if (!d) return `no decoration ${id}`;
    if (d.level > this.level) return `a ${d.name.toLowerCase()} is for sale from a later level`;
    if (this.coins() < d.price) return `a ${d.name.toLowerCase()} costs ${d.price} coins; you have ${this.coins()}`;
    this.spent += d.price;
    this.spots.set(spot, id);
    return null;
  }

  useItem(item: string, lot: string | null): string | null {
    const n = this.inventory.get(item) ?? 0;
    if (!n) return `you have no ${(ITEMS[item] ?? item).toLowerCase()}`;
    if (item === "repair_kit") {
      const err = this.repair(lot ?? "", true);
      if (err) return err;
    } else {
      if (this.active === null) return "there is no construction site to help on";
      const site = this.sites.get(this.active)!;
      const total = buildSecs(this.active);
      site.done = Math.min(total, site.done + Math.floor((total * (item === "master_crew" ? 50 : 25)) / 100));
      if (site.done >= total) this.finish(this.active, Math.floor(Date.now() / 1000), 0, 0, site.design);
    }
    this.inventory.set(item, n - 1);
    return null;
  }

  buy(id: string): string | null {
    const b = BLUEPRINTS.find((b) => b.id === id);
    if (!b) return `no blueprint ${id}`;
    if (this.owned.has(id)) return `the ${b.name} blueprint is already yours`;
    if (b.level > this.level) return `the ${b.name} blueprint is for sale from a later level`;
    if (this.coins() < b.price) return `the ${b.name} blueprint costs ${b.price} coins; you have ${this.coins()}`;
    this.manual = true;
    this.owned.add(id);
    this.spent += b.price;
    return null;
  }

  choose(need: string, blueprint: string | null, ts: number): string | null {
    const ni = NEEDS.findIndex((n) => n.id === need);
    if (ni < 0) return `no need ${need}`;
    const n = NEEDS[ni];
    if (!this.open(ni)) return `"${n.title}" is not open`;
    const lot = this.nextLot(ni)!;
    if (!this.owns(lot)) return `buy the plot at ${LOTS[lot].address} first`;
    let design: string | null = null;
    if (DESIGNED.has(n.kind)) {
      design = blueprint ?? BLUEPRINTS.find((b) => fits(b, n) && this.owned.has(b.id))?.id ?? null;
      if (!design) return `buy a blueprint for "${n.title.toLowerCase()}" first`;
      if (!this.owned.has(design)) return "buy that blueprint first";
    }
    const paused = [...this.sites.keys()].filter((i) => i !== this.active).length;
    if (this.active !== null && this.active !== lot && !this.sites.has(lot) && paused >= 3) return "3 sites already stand half built; finish or resume one first";
    this.manual = true;
    const site = this.sites.get(lot);
    if (!site) this.sites.set(lot, { design, done: 0 });
    else if (site.done === 0) site.design = design;
    this.active = lot;
    const idle = this.idle;
    this.idle = 0;
    if (idle) this.pour(idle, ts, this.sessionId, idle);
    return null;
  }

  pause(): string | null {
    if (this.active === null) return "nothing is under construction";
    this.manual = true;
    this.active = null;
    return null;
  }

  rename(lot: string, name: string): string | null {
    const l = LOTS.find((l) => l.id === lot);
    const b = l && this.built.get(l.index);
    if (!b) return `${lot} is not built yet`;
    const n = name.trim();
    if ([...n].length > 40) return "a name can be at most 40 characters";
    b.name = n || null;
    return null;
  }

  /** For the scenarios: streets paved and parks dressed as a town of its level would be. */
  dress() {
    this.roads = this.roads.map((_, i) => Math.min(3, this.level + (i % 3 === 0 ? 1 : 0)));
    const looks = ["fountain", "trees", "benches", "statue", "trees"];
    LAYOUT.blocks.forEach((b, bi) => {
      if (b.park && b.level <= this.level) b.spots.forEach((s, n) => (n === 0 || this.level >= 2) && this.spots.set(s.id, looks[(n + bi) % looks.length]));
    });
  }

  /** Damage for the scenarios: a building, how much. */
  hurt(i: number, damage: number, ts: number, cause: WorldEvent["cause"] = "surrendered") {
    const b = this.built.get(i);
    if (!b) return;
    b.damage = Math.min(3, b.damage + damage);
    const kind = cause === "tamper" ? "quake" : cause === "surrendered" ? "collapsed" : "damaged";
    this.history.push({ ts, kind, cause, session_id: null, plots: kind === "collapsed" ? [i, i] : [i], ruined: b.damage === 3 ? [i] : [] });
  }

  construction(sessionId: number, elapsed: number, surrendering: boolean): Construction | null {
    let site = this.active;
    let design = site !== null ? this.sites.get(site)!.design : null;
    let done = site !== null ? this.sites.get(site)!.done : 0;
    if (site === null && !this.manual) {
      const ni = NEEDS.findIndex((_, ni) => this.open(ni) && this.land.has(this.nextLot(ni)!));
      if (ni >= 0) {
        site = this.nextLot(ni);
        design = DESIGNED.has(NEEDS[ni].kind) ? (BLUEPRINTS.find((b) => fits(b, NEEDS[ni]) && this.owned.has(b.id))?.id ?? null) : null;
        done = 0;
      }
    }
    if (site === null) return null;
    const total = buildSecs(site);
    const n = NEEDS[LOTS[site].need];
    return {
      session_id: sessionId, index: site, grade: GRADE[n.kind], seed: site * 7919 + 13, surrendering,
      progress_permille: Math.floor((Math.min(total, done + elapsed) * 1000) / total),
      lot: LOTS[site].id, kind: n.kind, design, name: this.nameOf(site, design), need: n.id, remaining_secs: total - done,
    };
  }

  world(now: number, construction: Construction | null): World {
    const level = Math.min(this.level, 4);
    const levelSecs = (l: number) => NEEDS.filter((n) => n.level === l).reduce((a, n) => a + BUILD[n.kind] * MIN * n.lots, 0);
    let floor = 0;
    for (let l = 0; l < level; l++) floor += levelSecs(l);
    const plots: Plot[] = [...this.built.entries()].sort((a, b) => a[0] - b[0]).map(([i, b]) => {
      const n = NEEDS[LOTS[i].need];
      return {
        index: i, district: LAYOUT.lots[i]?.block ?? 0, grade: GRADE[n.kind], damage: b.damage, rubble: b.damage >= 3, seed: i * 7919 + 13,
        session_id: b.parts[0]?.session_id ?? 0, built_at: b.at, lot: LOTS[i].id, kind: n.kind, design: b.design,
        name: this.nameOf(i, b.design), address: LOTS[i].address, need: n.id, shiny: b.shiny, repair_price: b.damage ? 40 * b.damage : null,
        memory: { started_at: b.at - buildSecs(i), parts: b.parts, focused_secs: buildSecs(i), streak_at_finish: this.streak, scars: b.damage ? [{ ts: now - 7200, cause: "surrendered", damage: b.damage, repaired: false }] : [], first: i === 0 },
      };
    });
    const sites: SiteInfo[] = [...this.sites.entries()].map(([i, s]) => ({
      index: i, lot: LOTS[i].id, need: NEEDS[LOTS[i].need].id, name: this.nameOf(i, s.design), kind: NEEDS[LOTS[i].need].kind,
      design: s.design, done_secs: s.done, build_secs: buildSecs(i), active: this.active === i, seed: i * 7919 + 13,
    })).sort((a, b) => Number(b.active) - Number(a.active));
    const needs: NeedInfo[] = NEEDS.map((n, ni) => ({ n, ni })).filter(({ n }) => n.level === level).map(({ n, ni }) => {
      const next = this.nextLot(ni);
      return {
        id: n.id, title: n.title, words: n.words, kind: n.kind, district: n.district, build_secs: BUILD[n.kind] * MIN,
        lots: n.lots, lots_done: LOTS.filter((l) => l.need === ni && this.built.has(l.index)).length,
        next_lot: next === null ? null : LOTS[next].id, site: next !== null && this.sites.has(next), designed: DESIGNED.has(n.kind),
        fits: BLUEPRINTS.filter((b) => fits(b, n) && this.owned.has(b.id)).map((b) => b.id),
        fits_locked: BLUEPRINTS.filter((b) => fits(b, n) && !this.owned.has(b.id)).map((b) => b.id),
        land_price: next !== null && !this.land.has(next) ? this.landPrice(next) : null,
      };
    });
    return {
      tier: Math.min(3, level),
      focused_secs: this.focused,
      tier_floor_secs: floor,
      next_tier_secs: level < 4 ? floor + levelSecs(level) : null,
      built_secs: [...this.built.keys()].reduce((a, i) => a + buildSecs(i), 0) + [...this.sites.values()].reduce((a, s) => a + s.done, 0),
      streak_days: this.streak,
      plots,
      construction,
      history: this.history.slice(-30),
      coins: this.coins(),
      coins_earned: this.earned,
      needs,
      next_needs: NEEDS.filter((n) => n.level === level + 1).map((n) => n.title),
      blueprints: BLUEPRINTS.map((b) => ({ ...b, owned: this.owned.has(b.id), unlocked: b.level <= level, built: plots.filter((p) => p.design === b.id).length })),
      sites,
      idle_secs: this.idle,
      freezes: this.streak >= 7 ? 1 : 0,
      auto: !this.manual,
      last_award: this.award,
      layout: this.layout(level),
      wealth: 0,
      decorations: DECORATIONS.map((d) => ({ ...d, unlocked: d.level <= level })),
      stake: this.stakes.get(this.nextSessionId()) ?? null,
      stake_target_secs: this.stakeTarget(),
      stake_max: Math.min(1000, this.coins()),
      inventory: [...this.inventory.entries()].filter(([, n]) => n > 0).map(([id, count]) => ({ id, name: ITEMS[id] ?? id, count, rare: id === "master_crew" })),
      goals: this.goals(now),
      boxes_to_rare: 5,
      sets: this.sets(),
    };
  }

  private goals(now: number): GoalInfo[] {
    const on = this.today.day === Math.floor(now / 86400);
    return GOALS.map((g) => ({ ...g, progress: on ? this.progress(g.id) : 0, done: on && this.today.paid.has(g.id) }));
  }

  private layout(level: number): Layout {
    const taken = new Set([...this.built.keys(), ...this.sites.keys()]);
    const lots = LAYOUT.lots.map((l, i) => ({ ...l, owned: this.land.has(i) || taken.has(i), price: this.landPrice(i), for_sale: NEEDS[LOTS[i].need].level <= level }));
    const blocks = LAYOUT.blocks.map((b, bi) => ({
      ...b,
      open: b.park ? b.level <= level : lots.some((l) => l.block === bi && l.owned),
      spots: b.spots.map((s) => ({ id: s.id, decoration: this.spots.get(s.id) ?? null })),
    }));
    const streets = LAYOUT.streets.map((s, si) => {
      const next = ROADS[this.roads[si] + 1];
      return { ...s, name: this.streetNames.get(si) ?? s.name, class: this.roads[si], upgrade_price: next && next[1] <= level ? next[0] : null, complete: this.streetComplete(si) };
    });
    return { blocks, streets, lots, neighbourhoods: LAYOUT.neighbourhoods };
  }
}
