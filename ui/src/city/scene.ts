// City theme, step 3: the three.js scene. Builds models from the plan,
// lights them for the local time, and animates what changes: a finished
// building rises with sparks, a lost one collapses into dust and rubble,
// damage hits with a jolt. Changes since the window was last open are
// replayed one by one, so a loss is seen, not just counted.
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import type { World, WorldEvent } from "../proto";
import { Fx } from "./fx";
import { loadKit } from "./kit";
import { groundMat, hasReal, interiorUniforms, loadReal, setRealEnv, setSignals } from "./real";
import { Traffic } from "./traffic";
import { Land } from "./land";
import { piece } from "./kit";
import { RADIUS, ROAD_Z, WATER } from "./terrain";
import { building, fitReal, furniture, KERB, kitLook, mat, park, Parts, rubble, site, tree, type ModelInfo } from "./models";
import { BLOCK_X, BLOCK_Z, LOT, PAVEMENT, PITCH_X, PITCH_Z, ROAD, plan, rng, type CityPlan, type SiteSpec, type Spec } from "./plan";

const SEEN_KEY = "deepwork.seen";

interface Entry {
  key: string;
  group: THREE.Group;
  info: ModelInfo;
  spec: Spec;
  jib?: THREE.Group;
  ghost?: THREE.Mesh;
  surrendering?: boolean;
  /** Seconds of accumulated emitter time, per emitter. */
  acc: number[];
  rise?: { t: number; dur: number };
  hit?: number;
}

/** Sun direction, light colours and sky look for a local hour. */
function daylight(hour: number) {
  const t = ((hour - 6) / 12) * Math.PI;
  const elev = Math.sin(t); // >0 by day
  const az = (hour / 24) * Math.PI * 2 + 0.6;
  const sun = new THREE.Vector3(Math.cos(az) * Math.cos(Math.asin(Math.max(-1, Math.min(1, elev)))), elev, Math.sin(az));
  const day = THREE.MathUtils.smoothstep(elev, -0.12, 0.25);
  const golden = THREE.MathUtils.smoothstep(elev, -0.1, 0.05) * (1 - THREE.MathUtils.smoothstep(elev, 0.05, 0.4));
  return { sun: sun.normalize(), day, golden, night: 1 - THREE.MathUtils.smoothstep(elev, -0.15, 0.08) };
}

export class City {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private controls: OrbitControls;
  private composer: EffectComposer;
  private bloom: UnrealBloomPass;
  private sky = new Sky();
  private stars: THREE.Points;
  private sunLight = new THREE.DirectionalLight(0xffffff, 3);
  private hemi = new THREE.HemisphereLight(0xbcd4ff, 0x4a5a3a, 1);
  private land = new Land();
  private fx = new Fx();
  private traffic = new Traffic();

  private world: World | null = null;
  private plan: CityPlan | null = null;
  private hour = 12;
  private night = 0;
  private entries = new Map<number, Entry>();
  private base = new THREE.Group();
  private baseKey = "";
  private beaconMat = new THREE.MeshStandardMaterial({ color: 0x400000, emissive: 0xff2020, emissiveIntensity: 0 });
  private beaconGeo = new THREE.SphereGeometry(0.45, 8, 6);
  private lampMats: THREE.MeshStandardMaterial[] = [];

  private timer = new THREE.Timer();
  private shake = 0;
  private idle = 0;
  private story: (text: string) => void;
  private queue: { at: number; run: () => void }[] = [];
  private t = 0;
  /** Frames per second over the last second, for the dev readout. */
  fps = 0;
  private fpsCount = 0;
  private fpsT = 0;
  private focus: { to: THREE.Vector3; t: number } | null = null;
  /** Buildings sinking into their own dust. */
  private dying: { group: THREE.Group; t: number; h: number; w: number; x: number; z: number; tilt: number }[] = [];

  private constructor(private el: HTMLElement, story: (text: string) => void) {
    this.story = story;
    const r = (this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" }));
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFShadowMap;
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.outputColorSpace = THREE.SRGBColorSpace;
    el.appendChild(r.domElement);

    this.camera = new THREE.PerspectiveCamera(40, 1, 1, 6000);
    this.camera.position.set(90, 70, 110);
    this.controls = new OrbitControls(this.camera, r.domElement);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = 1.38;
    this.controls.minDistance = 20;
    this.controls.maxDistance = 1200;
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = 0.25;
    this.controls.addEventListener("start", () => {
      this.controls.autoRotate = false;
      this.idle = 0;
      this.focus = null;
    });

    const pmrem = new THREE.PMREMGenerator(r);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environmentIntensity = 0.6;

    this.sky.scale.setScalar(5000);
    const u = this.sky.material.uniforms;
    u.turbidity.value = 6;
    u.rayleigh.value = 1.6;
    u.mieCoefficient.value = 0.004;
    u.mieDirectionalG.value = 0.85;
    this.scene.add(this.sky);

    const starGeo = new THREE.BufferGeometry();
    const sr = rng(99);
    const sp: number[] = [];
    for (let i = 0; i < 2500; i++) {
      const a = sr() * Math.PI * 2;
      const y = 0.05 + sr() * 0.95;
      const k = Math.sqrt(1 - y * y);
      sp.push(Math.cos(a) * k * 4000, y * 4000, Math.sin(a) * k * 4000);
    }
    starGeo.setAttribute("position", new THREE.Float32BufferAttribute(sp, 3));
    this.stars = new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0, fog: false, depthWrite: false }));
    this.scene.add(this.stars);

    this.sunLight.castShadow = true;
    this.sunLight.shadow.mapSize.set(2048, 2048);
    this.sunLight.shadow.bias = -0.0004;
    this.sunLight.shadow.normalBias = 0.6;
    this.scene.add(this.sunLight, this.sunLight.target, this.hemi);

    this.scene.add(this.land.group, this.base, this.fx.group, this.traffic.group);
    this.scene.fog = new THREE.Fog(0xb8c8d8, 350, 3600);

    this.composer = new EffectComposer(r);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.4, 0.5, 0.82);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
    r.setAnimationLoop(() => this.frame());
  }

  static async create(el: HTMLElement, story: (text: string) => void): Promise<City> {
    await Promise.all([loadKit(), loadReal()]);
    return new City(el, story);
  }

  private resize() {
    const w = this.el.clientWidth || 1;
    const h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h);
    this.composer.setSize(w, h);
    this.bloom.resolution.set(w / 2, h / 2);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    const px = (h * this.renderer.getPixelRatio()) / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)));
    this.fx.smoke.setScale(px);
    this.fx.glow.setScale(px);
  }

  /** New world or time; cheap to call on every poll. */
  update(world: World, hour: number, elapsedSecs: number) {
    const first = this.world === null;
    this.world = world;
    if (Math.abs(hour - this.hour) > 1 / 60 || first) this.light(hour);
    const p = plan(world, elapsedSecs);
    this.plan = p;
    this.buildBase(p);
    if (first) {
      this.frameCamera(p, true);
      this.firstSync(world, p);
    } else {
      this.sync(p, true);
    }
  }

  /** A screen shake, e.g. for a quake. */
  quake(strength = 1) {
    this.shake = Math.max(this.shake, strength);
  }

  /** Dev only (mock mode): play a transition on a plot. The next poll puts it back. */
  demo(kind: "collapse" | "build" | "damage", index = -1): string {
    if (index < 0) {
      const standing = [...this.entries.entries()].filter(([, e]) => !("progress" in e.spec) && !e.spec.rubble);
      index = standing.sort((a, b) => b[1].info.height - a[1].info.height)[0]?.[0] ?? -1;
    }
    const old = this.entries.get(index);
    if (!old || "progress" in old.spec) return "nothing there";
    const s = old.spec;
    this.focusOn(s, old.info.height);
    if (kind === "collapse") this.transition(index, old, this.make({ ...s, rubble: true }));
    if (kind === "damage") this.transition(index, old, this.make({ ...s, damage: Math.min(2, s.damage + 1) }));
    if (kind === "build") this.transition(index, { ...old, key: "site:demo" }, this.make({ ...s, rubble: false, damage: 0 }));
    return `${kind} on plot ${index} (${s.kind}, ${old.info.height.toFixed(0)} high, ${s.rubble ? "rubble" : `damage ${s.damage}`})`;
  }

  // ---- world -> scene ----------------------------------------------------

  private keyOf(s: Spec | SiteSpec): string {
    if ("progress" in s) return `site:${s.grade}:${s.seed}:${Math.floor(s.floors * s.progress)}:${s.surrendering}`;
    return `${s.rubble ? "rubble" : "b"}:${s.grade}:${s.seed}:${s.rubble ? 0 : s.damage}`;
  }

  private make(s: Spec | SiteSpec): Entry {
    s = fitReal(s);
    let e: Entry;
    if ("progress" in s) {
      const m = site(s);
      e = { key: this.keyOf(s), group: m.group, info: m.info, spec: s, jib: m.jib, ghost: m.ghost, surrendering: s.surrendering, acc: [] };
    } else {
      const m = s.rubble ? rubble(s) : building(s);
      e = { key: this.keyOf(s), group: m.group, info: m.info, spec: s, acc: [] };
    }
    for (const b of e.info.beacons) {
      const mesh = new THREE.Mesh(this.beaconGeo, this.beaconMat);
      mesh.position.copy(b);
      e.group.add(mesh);
    }
    for (const b of e.info.jibBeacons ?? []) {
      const mesh = new THREE.Mesh(this.beaconGeo, this.beaconMat);
      mesh.position.copy(b);
      e.jib?.add(mesh);
    }
    e.acc = e.info.emitters.map(() => Math.random());
    this.applyNight(e.info);
    return e;
  }

  private put(index: number, e: Entry) {
    const old = this.entries.get(index);
    if (old) this.scene.remove(old.group);
    this.entries.set(index, e);
    this.scene.add(e.group);
  }

  private remove(index: number) {
    const old = this.entries.get(index);
    if (old) this.scene.remove(old.group);
    this.entries.delete(index);
  }

  private specs(p: CityPlan): Map<number, Spec | SiteSpec> {
    const m = new Map<number, Spec | SiteSpec>();
    for (const b of p.buildings) m.set(b.index, b);
    if (p.site) m.set(p.site.index, p.site);
    return m;
  }

  /** Brings the scene to the plan, animating what changed. */
  private sync(p: CityPlan, animate: boolean) {
    const want = this.specs(p);
    for (const index of this.entries.keys()) if (!want.has(index)) this.remove(index);
    for (const [index, s] of want) {
      const old = this.entries.get(index);
      const key = this.keyOf(s);
      if (old?.key === key) continue;
      const e = this.make(s);
      if (!animate || !old) {
        this.put(index, e);
        continue;
      }
      this.transition(index, old, e);
    }
  }

  private worldPos(s: Spec, y = 0) {
    return new THREE.Vector3(s.x, y, s.z);
  }

  private transition(index: number, old: Entry, e: Entry) {
    const s = e.spec;
    const wasSite = old.key.startsWith("site");
    const isSite = e.key.startsWith("site");
    const wasRubble = old.key.startsWith("rubble");
    const isRubble = e.key.startsWith("rubble");
    if (isSite) return this.put(index, e);
    if (isRubble && !wasRubble) {
      // Collapse: the old building shakes, tilts and sinks into its dust,
      // debris rains down, and the rubble is there when the dust clears.
      this.entries.delete(index);
      this.dying.push({ group: old.group, t: 0, h: old.info.height, w: s.w, x: s.x, z: s.z, tilt: (Math.random() < 0.5 ? -1 : 1) * (0.06 + Math.random() * 0.1) });
      this.focusOn(s, old.info.height);
      this.fx.collapse(this.worldPos(s), s.w, old.info.height, old.info.debris, wasSite || old.spec.damage >= 2);
      this.quake(0.7);
      this.later(1.6, () => {
        if (this.entries.has(index)) return;
        this.put(index, e);
      });
      return;
    }
    if (!isRubble && (wasSite || wasRubble)) {
      // A finished building rises out of the site with sparks.
      this.put(index, e);
      this.focusOn(s, e.info.height);
      e.rise = { t: 0, dur: 2.2 };
      this.fx.dust(this.worldPos(s), s.w, 30, 0.75);
      this.later(1.6, () => this.fx.celebrate(this.worldPos(s), e.info.height));
      return;
    }
    const before = Number(old.key.split(":")[3]);
    const after = Number(e.key.split(":")[3]);
    this.put(index, e);
    if (after > before) {
      e.hit = 0;
      this.fx.dust(this.worldPos(s, e.info.height * 0.6), s.w * 0.6, 25, 0.35);
      this.quake(0.25);
    } else if (after < before) {
      this.fx.celebrate(this.worldPos(s), e.info.height * 0.5);
    }
  }

  /** First frame: show the city as it was, then replay unseen events. */
  private firstSync(w: World, p: CityPlan) {
    const seen = Number(localStorage.getItem(SEEN_KEY) ?? NaN);
    const latest = w.history.at(-1)?.ts ?? 0;
    localStorage.setItem(SEEN_KEY, String(latest));
    const unseen = Number.isFinite(seen) ? w.history.filter((e) => e.ts > seen) : [];
    if (!unseen.length) return this.sync(p, false);

    // Start from a guess of the earlier state: unseen ruins standing, unseen
    // builds as sites, unseen damage removed. Then play the events in order.
    const before = this.specs(p);
    const restore = new Set<number>();
    for (const ev of unseen) {
      for (const i of [...ev.ruined, ...(ev.kind === "collapsed" ? ev.plots.slice(0, 1) : [])]) restore.add(i);
    }
    for (const [i, s] of before) {
      if ("progress" in s) continue;
      if (restore.has(i)) before.set(i, { ...s, rubble: false, damage: 1 });
      else if (unseen.some((ev) => ev.kind === "built" && ev.plots[0] === i)) before.delete(i);
      else if (unseen.some((ev) => (ev.kind === "quake" || ev.kind === "damaged") && ev.plots.includes(i))) before.set(i, { ...s, damage: 0 });
    }
    for (const [i, s] of before) this.put(i, this.make(s));

    let at = 1.5;
    for (const ev of unseen) {
      const evAt = at;
      this.later(evAt, () => this.replay(ev, w));
      at += ev.kind === "built" || ev.kind === "repaired" ? 3 : 4.5;
    }
    this.later(at, () => this.sync(this.plan!, true));
  }

  private replay(ev: WorldEvent, w: World) {
    const p = this.plan!;
    const spec = (i: number) => p.buildings.find((b) => b.index === i);
    const target = spec(ev.plots[0]);
    if (target) this.focus = { to: this.worldPos(target, target.height * 0.3), t: 0 };
    this.story(describeLive(ev, w));
    switch (ev.kind) {
      case "quake":
        this.quake(1.4);
        for (const i of ev.plots) {
          const s = spec(i);
          if (s) this.fx.dust(this.worldPos(s), s.w, 20);
        }
        break;
      case "collapsed":
        this.quake(0.6);
        break;
    }
    // Bring the touched plots to their final state with animation.
    for (const i of new Set([...ev.plots, ...ev.ruined])) {
      const s = p.buildings.find((b) => b.index === i);
      const old = this.entries.get(i);
      if (!s) continue;
      const e = this.make(s);
      if (old && old.key !== e.key) this.transition(i, old, e);
      else if (!old) {
        this.put(i, e);
        if (!s.rubble) {
          e.rise = { t: 0, dur: 2.2 };
          this.later(1.6, () => this.fx.celebrate(this.worldPos(s), e.info.height));
        }
      }
    }
  }

  private focusOn(s: Spec, height: number) {
    this.focus = { to: this.worldPos(s, Math.min(height * 0.4, 40)), t: 0 };
  }

  private later(secs: number, run: () => void) {
    this.queue.push({ at: this.t + secs, run });
  }

  // ---- static ground ------------------------------------------------------

  private buildBase(p: CityPlan) {
    const key = `${p.blocks.length}:${p.tier}:${p.emptyLots.length}`;
    if (key === this.baseKey) return;
    this.baseKey = key;
    this.scene.remove(this.base);
    this.base = new THREE.Group();
    this.lampMats = [];
    const parts = new Parts();
    // With the realistic street furniture come textured streets: asphalt,
    // paving slabs, granite kerbs, drains and manhole covers.
    const real = hasReal("street");
    const asphalt = real ? groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 }) : mat(0x3a3c40, { roughness: 0.95 });
    const walk = real ? groundMat("pave", 3.6, { roughness: 0.88 }) : mat(0xa8a49c, { roughness: 0.9 });
    const kerbStone = mat(0xb6b2aa, { roughness: 0.8 });
    const iron = mat(0x2a2b2d, { roughness: 0.55, metalness: 0.5 });
    const line = mat(0xe8e0c0, { roughness: 0.6 });
    const pole = mat(0x3c4046, { metalness: 0.6, roughness: 0.4 });
    const bulb = mat(0xfff0d0, { emissive: 0xffd9a0, emissiveIntensity: 0, night: 2.2 });
    this.lampMats.push(bulb);
    const pw = PAVEMENT;
    for (const b of p.blocks) {
      parts.box(asphalt, PITCH_X + 0.02, 0.06, PITCH_Z + 0.02, b.x, 0, b.z);
      // Pavement: a raised ring round the block, kerb on the road side.
      for (const sz of [-1, 1]) parts.box(walk, BLOCK_X + 2 * pw, KERB, pw, b.x, 0, b.z + sz * (BLOCK_Z / 2 + pw / 2));
      for (const sx of [-1, 1]) parts.box(walk, pw, KERB, BLOCK_Z, b.x + sx * (BLOCK_X / 2 + pw / 2), 0, b.z);
      if (real) {
        // Granite kerbs on the road side, a drain grate by each kerb, and
        // manhole covers in the carriageway.
        const kx = BLOCK_X / 2 + pw - 0.09;
        const kz = BLOCK_Z / 2 + pw - 0.09;
        for (const sz of [-1, 1]) parts.box(kerbStone, BLOCK_X + 2 * pw, KERB + 0.004, 0.18, b.x, 0, b.z + sz * kz);
        for (const sx of [-1, 1]) parts.box(kerbStone, 0.18, KERB + 0.004, BLOCK_Z + 2 * pw - 0.36, b.x + sx * kx, 0, b.z);
        for (const sz of [-1, 1]) for (const t of [-0.6, 0.6]) parts.box(iron, 0.6, 0.065, 0.36, b.x + t * BLOCK_X / 2, 0, b.z + sz * (kz + 0.3));
        for (const sx of [-1, 1]) parts.box(iron, 0.36, 0.065, 0.6, b.x + sx * (kx + 0.3), 0, b.z + 4);
        for (const t of [-0.35, 0.35]) parts.add(iron, new THREE.CircleGeometry(0.33, 14), b.x + t * BLOCK_X, 0.066, b.z - PITCH_Z / 2 + 1.6, -Math.PI / 2);
      }
      // Dashed centre lines on the roads around the block.
      for (let x = -PITCH_X / 2; x < PITCH_X / 2; x += 5) {
        parts.box(line, 2.4, 0.07, 0.25, b.x + x + 1.2, 0, b.z - PITCH_Z / 2);
      }
      for (let z = -PITCH_Z / 2; z < PITCH_Z / 2; z += 5) {
        parts.box(line, 0.25, 0.07, 2.4, b.x - PITCH_X / 2, 0, b.z + z + 1.2);
      }
      // Zebra crossings at the corners.
      const kerb = ROAD - 2 * pw;
      for (const sx of [-1, 1]) {
        const x = b.x + sx * (BLOCK_X / 2 - 2.2);
        for (let i = 0; i < 6; i++) parts.box(line, 2.6, 0.07, 0.5, x, 0, b.z - BLOCK_Z / 2 - pw - 0.8 - i * ((kerb - 1) / 5));
        const z = b.z + (sx < 0 ? -1 : 1) * (BLOCK_Z / 2 - 2.2);
        for (let i = 0; i < 6; i++) parts.box(line, 0.5, 0.07, 2.6, b.x - BLOCK_X / 2 - pw - 0.8 - i * ((kerb - 1) / 5), 0, z);
      }
      // Street lamps along the kerb, and trees between them.
      const ex = BLOCK_X / 2 + pw - 0.45;
      const ez = BLOCK_Z / 2 + pw - 0.45;
      for (const lz of [-1, 1]) {
        for (const t of [-1, -1 / 3, 1 / 3, 1]) {
          const x = b.x + t * (BLOCK_X / 2 - 1);
          const z = b.z + lz * ez;
          if (real) {
            // The arm reaches out over the road.
            furniture(parts, "lamp_led", x, KERB, z, lz > 0 ? 0 : Math.PI);
            continue;
          }
          parts.cyl(pole, 0.08, 0.12, 5, x, KERB, z, 6);
          parts.box(pole, 0.2, 0.15, 1.4, x, KERB + 4.9, z + lz * 0.6);
          parts.box(bulb, 0.5, 0.18, 0.5, x, KERB + 4.75, z + lz * 1.1);
        }
        for (const t of [-5 / 6, -1 / 2, -1 / 6, 1 / 6, 1 / 2, 5 / 6]) {
          tree(parts, b.x + t * (BLOCK_X / 2 - 1), b.z + lz * ez, 0.5, Math.floor(b.x * 31 + b.z * 17 + t * 12 + lz * 5), KERB);
        }
      }
      for (const sx of [-1, 1]) tree(parts, b.x + sx * ex, b.z, 0.5, Math.floor(b.x * 13 + b.z * 7 + sx), KERB);
      if (real) this.streetFurniture(parts, b, p.tier);
    }
    for (const k of p.parks) park(parts, k, pole, bulb);
    // Empty lots: rough grass with survey stakes, waiting to be built on.
    const stake = mat(0xc9a36a);
    const tape = mat(0xff8a2a, { emissive: 0x401800 });
    const e = LOT / 2 - 1.4;
    for (const l of p.emptyLots) {
      parts.box(real && hasReal("trees") ? groundMat("grass", 2.2, { roughness: 1, color: 0xd8d0a8 }) : mat(0x7a8f55, { roughness: 1 }), LOT - 0.4, KERB + 0.06, LOT - 0.4, l.x, 0, l.z);
      for (const [cx, cz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) parts.box(stake, 0.15, 0.9, 0.15, l.x + cx * e, KERB, l.z + cz * e);
      for (const cz of [-1, 1]) parts.box(tape, 2 * e, 0.04, 0.04, l.x, KERB + 0.75, l.z + cz * e);
      for (const cx of [-1, 1]) parts.box(tape, 0.04, 0.04, 2 * e, l.x + cx * e, KERB + 0.75, l.z);
      const r = rng(l.seed);
      if (r() < 0.35) tree(parts, l.x + (r() - 0.5) * 8, l.z + (r() - 0.5) * 8, 0.8 + r() * 0.4, l.seed, KERB);
    }
    this.land.build(p);
    const ground = this.land.shape;
    for (const t of p.trees) {
      const y = ground.height(t.x, t.z);
      if (y > WATER + 1.2 && Math.abs(t.z - ROAD_Z) > 7) tree(parts, t.x, t.z, t.s * 1.3, t.seed, y - 0.1);
    }
    // Roads out of town, along the street north of the first block row.
    // ... all the way to the mountains, over the river on a truss bridge.
    // The bed follows the land, so the road climbs the hills instead of
    // slicing a flat corridor through them.
    const { x: bx, z: bz } = ground.bridge;
    const ribbon = (x0: number, x1: number) => {
      const n = Math.max(2, Math.ceil((x1 - x0) / 8));
      const pos: number[] = [];
      const idx: number[] = [];
      for (let i = 0; i <= n; i++) {
        const x = x0 + ((x1 - x0) * i) / n;
        const y = ground.height(x, ROAD_Z) + 0.045;
        pos.push(x, y, ROAD_Z - 4.5, x, y, ROAD_Z + 4.5);
      }
      for (let i = 0; i < n; i++) {
        const a = i * 2;
        idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
      g.setIndex(idx);
      g.computeVertexNormals();
      const mesh = new THREE.Mesh(g, asphalt);
      mesh.receiveShadow = true;
      this.base.add(mesh);
      if (real) {
        // Lane markings over the hills: a dashed centre line, solid edge lines.
        const mp: number[] = [];
        const quad = (xa: number, xb: number, z0: number, z1: number) => {
          const ya = ground.height(xa, ROAD_Z) + 0.07;
          const yb = ground.height(xb, ROAD_Z) + 0.07;
          mp.push(xa, ya, z0, xb, yb, z0, xb, yb, z1, xa, ya, z0, xb, yb, z1, xa, ya, z1);
        };
        for (let x = x0; x + 3 < x1; x += 9) quad(x, x + 3, ROAD_Z - 0.07, ROAD_Z + 0.07);
        for (let x = x0; x < x1; x += 4) {
          const xb = Math.min(x1, x + 4);
          for (const e of [-1, 1]) quad(x, xb, ROAD_Z + e * 4.05 - 0.07, ROAD_Z + e * 4.05 + 0.07);
        }
        const lg = new THREE.BufferGeometry();
        lg.setAttribute("position", new THREE.Float32BufferAttribute(mp, 3));
        // Wound to face up whatever the order above: draw both sides.
        const marks = new THREE.Mesh(lg, mat(0xe8e4d8, { roughness: 0.7, side: THREE.DoubleSide }));
        lg.computeVertexNormals();
        marks.receiveShadow = true;
        this.base.add(marks);
      }
    };
    ribbon(bx + 15, RADIUS - 1);
    ribbon(-RADIUS + 1, bx - 15);
    for (const { role, geo } of piece("bridge").parts) {
      const m = kitLook(role);
      if (m.userData.night && !this.lampMats.includes(m)) this.lampMats.push(m);
      parts.add(m, geo, bx, 0, bz);
    }
    parts.into(this.base);
    this.base.traverse((o) => {
      if (o instanceof THREE.Mesh) {
        o.castShadow = o.material !== asphalt && o.material !== walk;
        // Realistic lamps (street lights, park lanterns) light up at night too.
        const m = o.material as THREE.MeshStandardMaterial;
        if (m.userData.night && !this.lampMats.includes(m)) this.lampMats.push(m);
      }
    });
    this.scene.add(this.base);
    this.applyNight({ height: 0, emitters: [], beacons: [], night: this.lampMats, debris: 0 });
    this.traffic.build(p);
    this.fitShadows(p);
  }

  /**
   * The realistic pavement furniture round a block: from a town on, traffic
   * signals at its corners (mast arms over the roads running along z, posts
   * for those along x, on opposite phases); a hydrant, litter bins and a
   * bench; a bus stop from a city on.
   */
  private streetFurniture(parts: Parts, b: { x: number; z: number }, tier: number) {
    const pw = PAVEMENT;
    const cx = BLOCK_X / 2 + pw - 0.55;
    const cz = BLOCK_Z / 2 + pw - 0.55;
    const kerb = BLOCK_Z / 2 + pw - 0.4;
    if (tier >= 1) {
      furniture(parts, "signal_mast", b.x + cx, KERB, b.z + cz, Math.PI / 2, undefined, "a");
      furniture(parts, "signal_mast", b.x - cx, KERB, b.z - cz, -Math.PI / 2, undefined, "a");
      furniture(parts, "signal_post", b.x - cx, KERB, b.z + cz, 0, undefined, "b");
      furniture(parts, "signal_post", b.x + cx, KERB, b.z - cz, Math.PI, undefined, "b");
    }
    furniture(parts, "hydrant", b.x, KERB, b.z + kerb, 0);
    for (const sx of [-1, 1]) furniture(parts, "bin", b.x + sx * (BLOCK_X / 2 - 3.2), KERB, b.z - sx * kerb, sx > 0 ? 0 : Math.PI);
    furniture(parts, "bench", b.x - 20.7, KERB, b.z + BLOCK_Z / 2 + pw - 1.3, 0);
    if (tier >= 2) furniture(parts, "busstop", b.x + 20.7, KERB, b.z - (BLOCK_Z / 2 + pw - 1.0), Math.PI);
  }

  private fitShadows(p: CityPlan) {
    const { minX, maxX, minZ, maxZ } = p.bounds;
    const r = Math.max(maxX - minX, maxZ - minZ) / 2 + 60;
    const cam = this.sunLight.shadow.camera;
    cam.left = cam.bottom = -r;
    cam.right = cam.top = r;
    cam.near = 1;
    cam.far = r * 4 + 400;
    cam.updateProjectionMatrix();
    this.sunLight.target.position.set((minX + maxX) / 2, 0, (minZ + maxZ) / 2);
    this.light(this.hour);
  }

  private frameCamera(p: CityPlan, jump: boolean) {
    const { minX, maxX, minZ, maxZ } = p.bounds;
    const c = new THREE.Vector3((minX + maxX) / 2, 0, (minZ + maxZ) / 2);
    const tallest = Math.max(10, ...p.buildings.map((b) => (b.rubble ? 0 : b.height)), p.site?.height ?? 0);
    const footprint = Math.max(maxX - minX, maxZ - minZ);
    const dist = Math.max(95, footprint * 1.4, tallest * 2.5);
    c.y = tallest * 0.45;
    this.controls.target.copy(c);
    // About 14 degrees above the horizon, from the south-east, so the hills
    // and the peaks behind them show above the city.
    if (jump) {
      const cam = this.camera.position.set(c.x + dist * 0.675, c.y + dist * 0.24, c.z + dist * 0.69);
      // Climb until no swell of the land outside town blocks the view.
      const ground = this.land.shape;
      for (let i = 0; i < 40; i++) {
        let clear = true;
        for (let t = 0; t < 0.8 && clear; t += 0.04) {
          const x = cam.x + (c.x - cam.x) * t;
          const z = cam.z + (c.z - cam.z) * t;
          clear = cam.y + (c.y - cam.y) * t > ground.height(x, z) + 3;
        }
        if (clear) break;
        cam.y += 4;
      }
    }
    // Haze that softens the hills and fades the mountains, without hiding them.
    const fog = this.scene.fog as THREE.Fog;
    fog.near = Math.max(650, dist * 3.2);
    fog.far = Math.max(5200, dist * 14);
  }

  // ---- light ----------------------------------------------------------------

  private light(hour: number) {
    this.hour = hour;
    const d = daylight(hour);
    this.night = d.night;
    this.traffic.setNight(d.night);
    this.fx.night = d.night;
    const u = this.sky.material.uniforms;
    u.sunPosition.value.copy(d.sun);
    const centre = this.sunLight.target.position;
    const dir = d.day > 0.02 ? d.sun : new THREE.Vector3(-d.sun.x, Math.max(0.5, -d.sun.y), -d.sun.z).normalize();
    this.sunLight.position.copy(centre).addScaledVector(dir, 500);
    this.sunLight.intensity = THREE.MathUtils.lerp(0.35, 3.2, d.day);
    this.sunLight.color.setHex(d.day > 0.02 ? 0xffffff : 0x9fb4ff).lerp(new THREE.Color(0xffa860), d.golden * 0.7);
    this.hemi.intensity = THREE.MathUtils.lerp(0.25, 1.1, d.day);
    this.hemi.color.setHex(0xbcd4ff).lerp(new THREE.Color(0x2a3560), d.night);
    this.scene.environmentIntensity = THREE.MathUtils.lerp(0.15, 0.6, d.day);
    this.renderer.toneMappingExposure = THREE.MathUtils.lerp(0.75, 0.6, d.day);
    (this.stars.material as THREE.PointsMaterial).opacity = d.night;
    const fog = new THREE.Color(0xc4d4e4).lerp(new THREE.Color(0xe0a070), d.golden * 0.6).lerp(new THREE.Color(0x0c1020), d.night);
    (this.scene.fog as THREE.Fog).color.copy(fog);
    this.land.setNight(d.night);
    this.bloom.strength = 0.15 + d.night * 0.4;
    this.bloom.threshold = 0.9 - d.night * 0.1;
    for (const e of this.entries.values()) this.applyNight(e.info);
    for (const m of this.lampMats) m.emissiveIntensity = d.night * (m.userData.night ?? 1);
    interiorUniforms.uDay.value = d.day;
    interiorUniforms.uNight.value = d.night;
    this.skyEnv(d.sun, d.night);
  }

  private envAt: THREE.Vector3 | null = null;
  private envTarget: THREE.WebGLRenderTarget | null = null;

  /** What the realistic glass reflects: this sky without its sun disc, redrawn when the sun has moved. */
  private skyEnv(sun: THREE.Vector3, night: number) {
    if (this.envAt && this.envAt.angleTo(sun) < 0.05) return;
    this.envAt = sun.clone();
    const scene = new THREE.Scene();
    const sky = new Sky();
    sky.scale.setScalar(1000);
    const u = sky.material.uniforms;
    for (const k of ["turbidity", "rayleigh", "mieCoefficient"] as const) u[k].value = this.sky.material.uniforms[k].value;
    u.mieDirectionalG.value = 0.6;
    u.sunPosition.value.copy(sun);
    u.showSunDisc.value = 0;
    scene.add(sky);
    // A dull ground below the horizon, so glass does not show the sky's underside.
    const ground = new THREE.Mesh(new THREE.CircleGeometry(900, 32).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: new THREE.Color(0x3a3c3e).lerp(new THREE.Color(0x050608), night) }));
    ground.position.y = -2;
    scene.add(ground);
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    const target = pmrem.fromScene(scene, 0.02);
    pmrem.dispose();
    sky.material.dispose();
    sky.geometry.dispose();
    setRealEnv(target.texture);
    this.envTarget?.dispose();
    this.envTarget = target;
  }

  private applyNight(info: ModelInfo) {
    for (const m of info.night) m.emissiveIntensity = this.night * (m.userData.night ?? 1) + (m.userData.night ? 0.04 : 0);
  }

  // ---- per frame --------------------------------------------------------------

  private frame() {
    this.timer.update();
    const raw = this.timer.getDelta();
    const dt = Math.min(0.05, raw);
    this.t += dt;
    this.fpsCount++;
    if ((this.fpsT += raw) >= 1) {
      this.fps = this.fpsCount / this.fpsT;
      this.fpsCount = this.fpsT = 0;
    }
    for (const q of this.queue.filter((q) => q.at <= this.t)) q.run();
    this.queue = this.queue.filter((q) => q.at > this.t);

    this.idle += dt;
    if (!this.controls.autoRotate && this.idle > 30 && !this.focus) this.controls.autoRotate = true;
    if (this.focus) {
      this.focus.t += dt;
      this.controls.target.lerp(this.focus.to, Math.min(1, dt * 1.5));
      if (this.focus.t > 3.5) {
        this.focus = null;
        if (this.plan) this.frameCamera(this.plan, false);
      }
    }
    this.controls.update(dt);

    const blink = Math.sin(this.t * 2.6) > 0.55;
    this.beaconMat.emissiveIntensity = blink ? 3 + this.night * 3 : 0;

    const wind = 0.8;
    const tmp = new THREE.Vector3();
    for (const e of this.entries.values()) {
      e.info.emitters.forEach((em, i) => {
        if (em.rate <= 0) return;
        e.acc[i] += em.rate * dt;
        while (e.acc[i] >= 1) {
          e.acc[i] -= 1;
          tmp.copy(em.pos);
          e.group.localToWorld(tmp);
          if (em.kind === "fire") this.fx.fireAt(tmp);
          else this.fx.smokeAt(tmp, em.rate > 3, this.night);
        }
      });
      if (e.jib) e.jib.rotation.y = Math.sin(this.t * 0.15 + e.spec.index) * 0.9;
      if (e.ghost) {
        const m = e.ghost.material as THREE.MeshBasicMaterial;
        m.opacity = e.surrendering ? 0.1 + 0.12 * (Math.sin(this.t * 6) * 0.5 + 0.5) : 0.1 + 0.04 * Math.sin(this.t * 1.5);
        if (e.surrendering) e.group.rotation.z = Math.sin(this.t * 23) * 0.004;
      }
      if (e.rise) {
        e.rise.t += dt;
        const k = Math.min(1, e.rise.t / e.rise.dur);
        const ease = 1 - Math.pow(1 - k, 3);
        e.group.scale.y = Math.max(0.001, ease);
        if (k >= 1) e.rise = undefined;
      }
      if (e.hit !== undefined) {
        e.hit += dt;
        e.group.position.x = e.spec.x + Math.sin(e.hit * 50) * 0.3 * Math.max(0, 1 - e.hit);
        if (e.hit > 1) {
          e.group.position.x = e.spec.x;
          e.hit = undefined;
        }
      }
    }
    this.dying = this.dying.filter((d) => {
      d.t += dt;
      const dur = 1.2 + Math.min(1.8, d.h / 40);
      const k = Math.min(1, d.t / dur);
      const ease = k * k;
      d.group.position.set(d.x + Math.sin(d.t * 60) * 0.25 * (1 - k), -d.h * ease * 1.02, d.z);
      d.group.rotation.z = d.tilt * ease;
      // Dust boils out at the base as it goes down.
      for (let i = 0; i < 3; i++) this.fx.dust(new THREE.Vector3(d.x, 0, d.z), d.w, 1);
      if (k >= 1) {
        this.scene.remove(d.group);
        return false;
      }
      return true;
    });
    this.fx.update(dt, wind);
    this.land.update(dt);
    this.traffic.update(dt);
    setSignals(this.t, this.night);

    if (this.shake > 0) {
      this.shake = Math.max(0, this.shake - dt * 0.8);
      const a = this.shake * 1.2;
      this.camera.position.x += (Math.random() - 0.5) * a;
      this.camera.position.y += (Math.random() - 0.5) * a;
    }
    this.composer.render(dt);
  }
}

function describeLive(ev: WorldEvent, w: World): string {
  const plots = (l: number[]) => (l.length === 1 ? `plot ${l[0] + 1}` : `plots ${l.map((i) => i + 1).join(", ")}`);
  switch (ev.kind) {
    case "built": {
      const p = w.plots[ev.plots[0]];
      return `A session built ${["a house", "a shop", "a tower block", "a high-rise", "a landmark tower"][Math.min(4, p?.grade ?? 0)]} on ${plots(ev.plots)}.`;
    }
    case "repaired":
      return `Focus repaired ${plots(ev.plots)}.`;
    case "collapsed":
      return `You surrendered. Plot ${ev.plots[0] + 1} collapsed${ev.plots.length > 1 ? ` and fire spread to ${plots(ev.plots.slice(1))}` : ""}.`;
    case "quake":
      return ev.plots.length ? `Tampering set off an earthquake: ${plots(ev.plots)} damaged.` : "Tampering set off an earthquake.";
    case "damaged": {
      const why = { clock_jump: "A wall clock jump", tunnel: "A proxy around the throttle" }[ev.cause as string] ?? "A refused root attempt";
      return `${why} damaged ${plots(ev.plots)}.`;
    }
  }
}
