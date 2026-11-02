// Skyline theme, step 2: draws a Scene with PixiJS. Static shapes are drawn
// once per layout; the ticker only animates smoke, beacons, stars, the crane
// and the shake of a site that is being surrendered.
// The app's CSP has no unsafe-eval; this swaps in Pixi's eval-free shader setup.
import "pixi.js/unsafe-eval";
import { Application, Container, Graphics } from "pixi.js";
import { layout, mix, rng, type Building, type Scene } from "./layout";
import type { World } from "./proto";

const NIGHT = 0x0b0d18;
const LIT = 0xffcf7a;
const SOOT = 0x1c1a1a;

interface Smoke {
  x: number;
  y: number;
  r: number;
  vx: number;
  vy: number;
  life: number;
  max: number;
  dark: boolean;
}

export class Skyline {
  private world: World | null = null;
  private hour = 12;
  private elapsed = 0;
  private scene: Scene | null = null;

  private sky = new Graphics();
  private stars = new Graphics();
  private far = new Graphics();
  private city = new Graphics();
  private siteLayer = new Container();
  private site = new Graphics();
  private crane = new Graphics();
  private fx = new Graphics();
  private ground = new Graphics();

  private smoke: Smoke[] = [];
  private beacons: { x: number; y: number; r: number }[] = [];
  private starList: { x: number; y: number; r: number; phase: number }[] = [];
  private t = 0;
  private shake = 0;

  private constructor(private app: Application) {
    this.siteLayer.addChild(this.site, this.crane);
    app.stage.addChild(this.sky, this.stars, this.far, this.city, this.siteLayer, this.ground, this.fx);
    app.renderer.on("resize", () => this.relayout());
    app.ticker.add((tk) => this.tick(tk.deltaMS / 1000));
  }

  static async create(el: HTMLElement): Promise<Skyline> {
    const app = new Application();
    await app.init({
      resizeTo: el,
      antialias: true,
      autoDensity: true,
      resolution: window.devicePixelRatio || 1,
      background: NIGHT,
    });
    el.appendChild(app.canvas);
    return new Skyline(app);
  }

  /** New world or time; cheap enough to call on every poll. */
  update(world: World, hour: number, elapsedSecs: number) {
    const sameWorld = JSON.stringify(world) === JSON.stringify(this.world);
    const sameTime = Math.abs(hour - this.hour) < 1 / 30;
    const site = world.construction;
    // Only countdown progress or a stopwatch's slow pulse move the site.
    const siteMoved = site !== null && Math.floor(elapsedSecs / 10) !== Math.floor(this.elapsed / 10);
    this.world = world;
    this.hour = hour;
    this.elapsed = elapsedSecs;
    if (!sameWorld || !sameTime || siteMoved) this.relayout();
  }

  /** A short screen shake, for losses that happen while the window is open. */
  quake(strength = 1) {
    this.shake = Math.max(this.shake, strength);
  }

  private relayout() {
    if (!this.world) return;
    const { width, height } = this.app.screen;
    this.scene = layout(this.world, width, height, this.hour, this.elapsed);
    this.draw(this.scene);
  }

  private draw(s: Scene) {
    const haze = s.sky[2];
    // Sky: banded vertical gradient through the three stops.
    this.sky.clear();
    const bands = 48;
    for (let i = 0; i < bands; i++) {
      const t = i / (bands - 1);
      const c = t < 0.6 ? mix(s.sky[0], s.sky[1], t / 0.6) : mix(s.sky[1], s.sky[2], (t - 0.6) / 0.4);
      this.sky.rect(0, (s.ground * i) / bands, s.width, s.ground / bands + 1).fill(c);
    }
    this.drawSunMoon(s);

    const r = rng(77);
    this.starList = Array.from({ length: Math.round((s.width * s.ground) / 9000) }, () => ({
      x: r() * s.width,
      y: r() * s.ground * 0.7,
      r: 0.5 + r() * 1.1,
      phase: r() * Math.PI * 2,
    }));

    this.far.clear();
    for (const layer of s.far) {
      this.far.poly(layer.points).fill(mix(mix(layer.color, haze, 0.35), NIGHT, s.glow * 0.5));
    }

    this.city.clear();
    this.beacons = [];
    for (const rb of s.rubble) {
      const fog = (1 - rb.depth) * 0.6;
      this.city.poly(rb.points).fill(mix(mix(0x5d5650, NIGHT, s.glow * 0.5), haze, fog));
      for (const b of rb.beams) {
        const dx = (Math.cos(b.angle) * b.len) / 2;
        const dy = (Math.sin(b.angle) * b.len) / 2;
        this.city
          .moveTo(b.x - dx, b.y - dy)
          .lineTo(b.x + dx, b.y + dy)
          .stroke({ width: 2 * rb.depth, color: mix(0x3a3330, haze, fog) });
      }
    }
    for (const b of s.buildings) this.drawBuilding(b, s, haze);

    this.drawSite(s, haze);

    // Ground: pavement, road, lamps.
    const g = this.ground.clear();
    const dusk = s.glow * 0.6;
    g.rect(0, s.ground, s.width, s.height - s.ground).fill(mix(0x3b3f44, NIGHT, dusk));
    g.rect(0, s.ground, s.width, 4).fill(mix(0x7b7f86, NIGHT, dusk));
    const road = s.ground + (s.height - s.ground) * 0.42;
    g.rect(0, road, s.width, (s.height - s.ground) * 0.4).fill(mix(0x2a2c30, NIGHT, dusk));
    for (let x = 10; x < s.width; x += 46) {
      g.rect(x, road + (s.height - s.ground) * 0.19, 22, 2).fill(mix(0xd8d0a0, NIGHT, dusk));
    }
    for (const x of s.lamps) {
      g.rect(x - 1, s.ground - 30, 2, 32).fill(mix(0x55585e, NIGHT, dusk));
      g.rect(x - 5, s.ground - 32, 10, 3).fill(mix(0x55585e, NIGHT, dusk));
      if (s.glow > 0.3) {
        g.circle(x, s.ground - 28, 12).fill({ color: LIT, alpha: 0.05 * s.glow });
        g.circle(x, s.ground - 29, 3).fill({ color: LIT, alpha: s.glow });
      }
    }
  }

  private drawSunMoon(s: Scene) {
    // Sun by day, moon by night, each on an arc across the sky.
    const day = this.hour >= 6 && this.hour < 19;
    const t = day ? (this.hour - 6) / 13 : ((this.hour + 24 - 19) % 24) / 11;
    const x = s.width * (0.1 + 0.8 * t);
    const y = s.ground * (0.75 - 0.6 * Math.sin(Math.PI * t));
    if (day) {
      this.sky.circle(x, y, 44).fill({ color: 0xfff2c0, alpha: 0.12 });
      this.sky.circle(x, y, 26).fill(0xfff4d0);
    } else {
      this.sky.circle(x, y, 28).fill({ color: 0xc8d0ff, alpha: 0.03 });
      this.sky.circle(x, y, 16).fill(0xe6e9f5);
      this.sky.circle(x + 6, y - 4, 14).fill(mix(s.sky[0], s.sky[1], 0.4));
    }
  }

  private drawBuilding(b: Building, s: Scene, haze: number) {
    const g = this.city;
    const fog = (1 - b.depth) * 0.6;
    const shade = (c: number) => mix(mix(c, NIGHT, s.glow * 0.55), haze, fog);
    const facade = shade(mix(b.facade, SOOT, b.damage * 0.22));
    const top = b.base - b.h;
    const roofH = b.roof === "pitched" ? Math.min(b.w * 0.45, b.h * 0.5) : 0;
    const bodyTop = top + roofH;
    const notchX = b.x + b.w * (1 - b.notch);
    const notchY = bodyTop + b.h * b.notch * 0.5;

    if (b.notch > 0) {
      // A broken corner with a jagged edge.
      const r = rng(b.index * 31 + 7);
      const pts = [b.x, b.base, b.x, bodyTop, notchX, bodyTop];
      const steps = 4;
      for (let i = 1; i < steps; i++) {
        pts.push(notchX + ((b.x + b.w - notchX) * i) / steps, bodyTop + (notchY - bodyTop) * (i / steps) + (r() - 0.5) * 6);
      }
      pts.push(b.x + b.w, notchY, b.x + b.w, b.base);
      g.poly(pts).fill(facade);
    } else {
      g.rect(b.x, bodyTop, b.w, b.base - bodyTop).fill(facade);
    }
    // A lighter edge on the left reads as volume.
    g.rect(b.x, bodyTop, Math.max(1, b.w * 0.06), b.base - bodyTop).fill({ color: 0xffffff, alpha: 0.06 * b.depth });

    switch (b.roof) {
      case "pitched":
        g.poly([b.x - b.w * 0.06, bodyTop, b.x + b.w / 2, top, b.x + b.w * 1.06, bodyTop]).fill(shade(0x7a4a3c));
        break;
      case "awning": {
        const y = b.base - Math.min(b.h * 0.3, 16 * b.depth);
        const stripes = 6;
        for (let i = 0; i < stripes; i++) {
          g.rect(b.x - 2 + (i * (b.w + 4)) / stripes, y, (b.w + 4) / stripes, 5 * b.depth).fill(shade(i % 2 ? 0xe8e0d0 : 0xb0473a));
        }
        g.rect(b.x - 1, bodyTop - 3, b.w + 2, 3).fill(shade(0x444852));
        break;
      }
      case "tank": {
        g.rect(b.x - 1, bodyTop - 3, b.w + 2, 3).fill(shade(0x444852));
        if (b.notch === 0) {
          const tw = Math.min(14, b.w * 0.3) * b.depth;
          const tx = b.x + b.w * 0.6;
          g.rect(tx, bodyTop - tw * 1.4, tw, tw).fill(shade(0x6b5040));
          g.rect(tx + 1, bodyTop - tw * 0.4, 1.5, tw * 0.4).fill(shade(0x333333));
          g.rect(tx + tw - 2.5, bodyTop - tw * 0.4, 1.5, tw * 0.4).fill(shade(0x333333));
        }
        break;
      }
      case "antenna":
        g.rect(b.x - 1, bodyTop - 3, b.w + 2, 3).fill(shade(0x444852));
        if (b.notch === 0) {
          const ax = b.x + b.w * 0.35;
          const ah = Math.min(40, b.h * 0.15);
          g.rect(ax, bodyTop - ah, 2 * b.depth, ah).fill(shade(0x8a8f99));
          this.beacons.push({ x: ax + b.depth, y: bodyTop - ah, r: 2.4 * b.depth });
        }
        break;
      case "spire":
        if (b.notch === 0) {
          const sh = Math.min(b.h * 0.22, b.w * 1.2);
          g.poly([b.x + b.w * 0.15, bodyTop, b.x + b.w / 2, bodyTop - sh, b.x + b.w * 0.85, bodyTop]).fill(shade(mix(b.facade, 0xb8c4d4, 0.4)));
          g.rect(b.x + b.w / 2 - 1, bodyTop - sh - 14 * b.depth, 2, 14 * b.depth).fill(shade(0xa0a8b4));
          this.beacons.push({ x: b.x + b.w / 2, y: bodyTop - sh - 14 * b.depth, r: 3 * b.depth });
        }
        break;
    }

    for (const w of b.windows) {
      if (b.notch > 0 && w.x + w.w > notchX && w.y < notchY + 4) continue;
      let color: number;
      let alpha = 1;
      if (w.broken) color = shade(0x0c0c10);
      else if (s.glow > w.on) color = mix(LIT, haze, fog * 0.6);
      else {
        // Unlit glass reflects the sky by day.
        color = shade(mix(b.facade, s.sky[1], 0.45));
        alpha = 0.9;
      }
      g.rect(w.x, w.y, w.w, w.h).fill({ color, alpha });
    }
    for (const c of b.cracks) {
      g.moveTo(c[0], c[1]);
      for (let i = 2; i < c.length; i += 2) g.lineTo(c[i], c[i + 1]);
      g.stroke({ width: 1.2 * b.depth, color: 0x0e0d0d, alpha: 0.85 });
    }
  }

  private drawSite(s: Scene, haze: number) {
    const g = this.site.clear();
    this.crane.clear();
    const site = s.site;
    if (!site) return;
    const fog = (1 - site.depth) * 0.6;
    const shade = (c: number) => mix(mix(c, NIGHT, s.glow * 0.45), haze, fog);
    const top = site.base - site.target;
    const builtTop = site.base - site.built;

    // Concrete floors built so far.
    g.rect(site.x, builtTop, site.w, site.built).fill(shade(0x8c8d8f));
    const floor = Math.max(8, 12 * site.depth);
    for (let y = site.base - floor; y > builtTop; y -= floor) {
      g.rect(site.x, y, site.w, 2).fill(shade(0x6a6b6e));
    }
    // Scaffolding up to the full height.
    const pole = { width: 1.2, color: shade(site.surrendering ? 0xd0503a : 0xe0a040) };
    const cols = Math.max(2, Math.round(site.w / 10));
    for (let i = 0; i <= cols; i++) {
      const x = site.x - 3 + ((site.w + 6) * i) / cols;
      g.moveTo(x, site.base).lineTo(x, top).stroke(pole);
    }
    for (let y = site.base; y >= top; y -= floor * 1.5) {
      g.moveTo(site.x - 3, y).lineTo(site.x + site.w + 3, y).stroke(pole);
    }
    for (let y = site.base; y - floor * 1.5 >= top; y -= floor * 3) {
      g.moveTo(site.x - 3, y).lineTo(site.x + site.w + 3, y - floor * 1.5).stroke({ ...pole, alpha: 0.6 });
    }

    // Tower crane beside it; its jib and hook animate in the ticker.
    const mastX = site.x + site.w + Math.max(10, site.w * 0.25);
    const mastTop = top - Math.max(24, site.target * 0.15);
    g.rect(mastX - 2, mastTop, 4, site.base - mastTop).fill(shade(0xd8a530));
    for (let y = site.base; y > mastTop; y -= 8) {
      g.moveTo(mastX - 2, y).lineTo(mastX + 2, y - 8).stroke({ width: 1, color: shade(0x8a6a20) });
    }
    this.crane.position.set(mastX, mastTop);
    const jib = this.crane;
    const reach = site.w * 1.6 + 30;
    jib.rect(-reach, -3, reach + reach * 0.35, 4).fill(shade(0xd8a530));
    jib.rect(reach * 0.2, -1, reach * 0.12, 8).fill(shade(0x555a60));
    this.beacons.push({ x: mastX, y: mastTop - 3, r: 2.5 });
  }

  private tick(dt: number) {
    if (!this.scene) return;
    const s = this.scene;
    this.t += dt;
    const fx = this.fx.clear();

    // Twinkling stars at night, under the far layers.
    this.stars.clear();
    if (s.glow > 0.05) {
      for (const st of this.starList) {
        const a = s.glow * (0.5 + 0.5 * Math.sin(this.t * 1.3 + st.phase));
        this.stars.circle(st.x, st.y, st.r).fill({ color: 0xffffff, alpha: a * 0.9 });
      }
    }

    // Blinking aircraft beacons.
    const on = Math.sin(this.t * 3) > 0.2;
    for (const b of this.beacons) {
      if (on) {
        fx.circle(b.x, b.y, b.r * 3).fill({ color: 0xff3030, alpha: 0.18 });
        fx.circle(b.x, b.y, b.r).fill(0xff4040);
      }
    }

    // Smoke from damaged buildings, more and darker with damage.
    for (const b of s.buildings) {
      if (b.damage === 0) continue;
      const rate = b.damage === 1 ? 0.6 : 2.2;
      if (Math.random() < rate * dt) {
        const top = b.base - b.h * (b.notch > 0 ? 1 - b.notch * 0.5 : 1);
        this.smoke.push({
          x: b.x + b.w * (0.3 + Math.random() * 0.5),
          y: top,
          r: (3 + Math.random() * 3) * b.depth,
          vx: 4 + Math.random() * 6,
          vy: -(10 + Math.random() * 10),
          life: 0,
          max: 4 + Math.random() * 3,
          dark: b.damage >= 2,
        });
      }
    }
    this.smoke = this.smoke.filter((p) => (p.life += dt) < p.max);
    for (const p of this.smoke) {
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      const k = p.life / p.max;
      fx.circle(p.x, p.y, p.r * (1 + k * 2.5)).fill({ color: p.dark ? 0x2a2626 : 0x8a8a8a, alpha: 0.45 * (1 - k) });
    }

    // Crane swing and the site's distress while surrendering.
    const site = s.site;
    if (site) {
      this.crane.rotation = Math.sin(this.t * 0.25) * 0.08;
      if (site.surrendering) {
        this.siteLayer.position.set(Math.sin(this.t * 40) * 1.5, 0);
        if (Math.sin(this.t * 5) > 0) {
          fx.rect(site.x - 6, site.base - site.target - 6, site.w + 12, site.target + 6).fill({ color: 0xff2a1a, alpha: 0.12 });
        }
      } else {
        this.siteLayer.position.set(0, 0);
      }
    }

    // Screen shake for live losses.
    if (this.shake > 0) {
      this.shake = Math.max(0, this.shake - dt * 1.2);
      const a = this.shake * 8;
      this.app.stage.position.set((Math.random() - 0.5) * a, (Math.random() - 0.5) * a);
    } else if (this.app.stage.x !== 0 || this.app.stage.y !== 0) {
      this.app.stage.position.set(0, 0);
    }
  }
}
