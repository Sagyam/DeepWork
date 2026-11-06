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
import { ShaderPass } from "three/examples/jsm/postprocessing/ShaderPass.js";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import type { World, WorldEvent } from "../proto";
import { namesOf } from "../format";
import { Bench } from "./bench";
import { shadowTaps, type ShadowTaps } from "./shadow";
import { onQuality, QUALITY, qualityPref, type QualitySpec } from "./quality";
import { Fx } from "./fx";
import { IMPOSTOR_NEAR, Impostors, loaded } from "./impostor";
import { loadKit } from "./kit";
import { thumbnail } from "./thumbs";
import { groundMat, hasReal, interiorUniforms, loadReal, realMat, realPiece, setRealEnv, setSignals, setSprayScale, setWaterTime, useModels } from "./real";
import { modelsStatus, type ModelsStatus } from "../models";
import { Traffic } from "./traffic";
import { Land } from "./land";
import { piece } from "./kit";
import { RADIUS, ROAD_Z, WATER } from "./terrain";
import { building, fitReal, furniture, KERB, kitLook, mat, park, Parts, rubble, site, SPECIES, tree, type ModelInfo } from "./models";
import { BLOCK_X, BLOCK_Z, LOT, lot, PAVEMENT, PITCH_X, PITCH_Z, ROAD, plan, rng, type CityPlan, type SiteSpec, type Spec } from "./plan";

const SEEN_KEY = "deepwork.seen";

// The rendering optimisations tried first in the showcase town (proto/town.ts,
// measured in docs/APP.md "Performance"), each commented
// where it is made: res, shadow, idle, cull, trees, sky, ibl, prewarm, clamp.

/** cull: tiny props (signals, hydrants, bins, benches) drop out past this many metres, */
const TINY = 140;
/** and lamps past this. */
const SMALL = 320;
/** Side of the tiles the trees round town are grouped in, for impostors. */
const TREE_TILE = 64;
/** pause: frames a second for ambient motion while the window is unfocused. */
const DIM_FPS = 5;
/** shadow: redraw the shadow map once the sun has moved this far (radians, ~3 minutes). */
const SUN_STEP = 0.0125;
/**
 * ibl: the neutral ambient light that stands in for the environment light
 * rough materials lost, per unit of environment intensity. Unlike the town's
 * faint sky, the room environment is most of the city's fill light (night
 * included); 6.5 matched the old frames' mean brightness by day and by night
 * (scripts/bench-app.ts with LUMA=1).
 */
const FILL = 6.5;

/** clamp: caps brightness before the bloom (see the constructor). */
const CLAMP = {
  uniforms: { tDiffuse: { value: null }, uMax: { value: 8 } },
  vertexShader: "varying vec2 vUv;\nvoid main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
  fragmentShader: "uniform sampler2D tDiffuse;\nuniform float uMax;\nvarying vec2 vUv;\nvoid main() { vec4 c = texture2D(tDiffuse, vUv); gl_FragColor = vec4(min(c.rgb, vec3(uMax)), c.a); }",
};

interface Entry {
  key: string;
  group: THREE.Group;
  info: ModelInfo;
  spec: Spec;
  jib?: THREE.Group;
  /** The jib's turn when the shadow map was last drawn. */
  jibShadow?: number;
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
  private skyScene = new THREE.Scene();
  private skyCube = new THREE.WebGLCubeRenderTarget(512, { type: THREE.HalfFloatType });
  private cubeCam = new THREE.CubeCamera(1, 6000, this.skyCube);
  private clamp: ShaderPass;
  private roomEnv: THREE.Texture;
  /** Materials that took the environment light in prepare(); their intensity follows the day. */
  private glossy = new Set<THREE.MeshStandardMaterial>();
  private prepared = new WeakSet<THREE.Material>();
  /** Cut-out textures the shadow map waits for. */
  private shadowWait = new Set<THREE.Texture>();
  private shadowDir: THREE.Vector3 | null = null;
  private impostors: Impostors;
  /** Street props that drop out with distance (cull). */
  private chunks: { group: THREE.Group; centre: THREE.Vector3; far: number }[] = [];
  /** Trees round town, real near the camera and impostors further out. */
  private treeTiles: { real: THREE.Group; imp: THREE.Group | null; centre: THREE.Vector3 }[] = [];
  /** Something changed that a frame should show (idle). */
  private dirty = true;
  /** Compile shaders and upload textures before the next frame (prewarm). */
  private warm = false;
  private bench: Bench | null = null;
  private stars: THREE.Points;
  private sunLight = new THREE.DirectionalLight(0xffffff, 3);
  private hemi = new THREE.HemisphereLight(0xbcd4ff, 0x4a5a3a, 1);
  private fill = new THREE.AmbientLight(0xffffff, 0);
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
  /** The shadow filter's taps in use (0 before the first applyQuality). */
  private taps: ShadowTaps | 0 = 0;
  /**
   * pause: the window is unfocused, so only ambient motion (smoke, cranes,
   * the ghost's pulse) draws, at DIM_FPS, with traffic and auto-rotate
   * stopped; moments still play at full rate. Hidden draws nothing.
   */
  private dim = false;
  private dimAt = 0;
  private shake = 0;
  private idle = 0;
  private story: (text: string) => void;
  private queue: { at: number; run: () => void }[] = [];
  private t = 0;
  /** Frames per second over the last second, for the dev readout. */
  fps = 0;
  /** The realistic models as they were when the city was made (models.ts). */
  models: ModelsStatus = { state: "none" };
  private fpsCount = 0;
  private fpsT = 0;
  private focus: { to: THREE.Vector3; t: number } | null = null;
  /** The camera backing off to a distance and height above the target, e.g. to see a whole city. */
  private pull: { dist: number; rise: number } | null = null;
  /** Buildings sinking into their own dust. */
  private dying: { group: THREE.Group; t: number; h: number; w: number; x: number; z: number; tilt: number }[] = [];

  /** A building or site under the pointer (`null`: none), with the pointer's place. */
  onHover: ((index: number | null, x: number, y: number) => void) | null = null;
  /** The settlement reached a new level (live or replayed), as its fireworks end. */
  onGraduate: ((tier: number) => void) | null = null;
  /** A building or site clicked (not dragged). */
  onPick: ((index: number) => void) | null = null;
  private ray = new THREE.Raycaster();

  /**
   * The building or site under a screen point. Lots are known rectangles, so
   * the ray is met with the ground, not with the buildings' meshes: cheap,
   * and a tall tower is picked at its foot. Good enough looking down.
   */
  pickAt(clientX: number, clientY: number): number | null {
    const p = this.plan;
    if (!p) return null;
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    this.ray.setFromCamera(ndc, this.camera);
    const hit = new THREE.Vector3();
    if (!this.ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -KERB), hit)) return null;
    const all = [...p.buildings, ...p.paused, ...(p.site ? [p.site] : [])];
    for (const s of all) {
      const l = lot(s.index);
      if (Math.abs(hit.x - l.x) <= LOT / 2 && Math.abs(hit.z - l.z) <= LOT / 2) return s.index;
    }
    return null;
  }

  /** Eases the camera to a lot. */
  look(index: number) {
    const p = this.plan;
    const s = p && [...p.buildings, ...p.paused, ...(p.site ? [p.site] : [])].find((b) => b.index === index);
    if (!s) return;
    this.controls.autoRotate = false;
    this.focusOn(s, this.entries.get(index)?.info.height ?? s.height);
  }

  private constructor(private el: HTMLElement, story: (text: string) => void) {
    this.story = story;
    // res: one pixel per CSS pixel (1.5x cost double), antialiased by MSAA 4x
    // in the composer's target, with alpha to coverage on cut-out leaves,
    // railings and grilles (prepare()). SMAA at 1x stair-stepped edges once
    // stretched to a 1.5x screen and broke thin railings up. The canvas
    // itself needs no MSAA: only the output pass draws to it.
    const r = (this.renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" }));
    r.setPixelRatio(1);
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFShadowMap;
    // shadow: the city stands still nearly all the time and the sun moves
    // slowly, so the shadow map is drawn only when the sun has moved on, a
    // building changes or cut-out textures arrive (shadowsDirty()), not every
    // frame. Moving vehicles cast a blob instead (traffic.ts).
    r.shadowMap.autoUpdate = false;
    // movers (shadows()): the main pass's shadow map is drawn here, inside
    // the render call, where three's render state is set up.
    const draw = r.shadowMap.render.bind(r.shadowMap);
    r.shadowMap.render = (lights, scene, camera) => (scene === this.scene ? this.shadows(draw, lights, camera) : draw(lights, scene, camera));
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
    this.controls.addEventListener("change", () => (this.dirty = true));
    this.controls.addEventListener("start", () => {
      this.controls.autoRotate = false;
      this.idle = 0;
      this.focus = null;
    });

    // ibl: image-based light costs every pixel several texture reads, yet on
    // rough brick, render and roofs it is a faint fill: only glossy and metal
    // materials take it (prepare()), and a brighter hemisphere light fills the
    // rest for nearly nothing. So the scene has no environment of its own.
    const pmrem = new THREE.PMREMGenerator(r);
    this.roomEnv = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environmentIntensity = 0.6;
    this.impostors = new Impostors(r);
    if (new URLSearchParams(location.search).has("bench")) this.bench = new Bench(r);

    // sky: the scattering sky is a full-screen shader; it is drawn into a
    // cube map when the light changes (light()), which the background samples.
    this.sky.scale.setScalar(5000);
    const u = this.sky.material.uniforms;
    u.turbidity.value = 6;
    u.rayleigh.value = 1.6;
    u.mieCoefficient.value = 0.004;
    u.mieDirectionalG.value = 0.85;
    this.skyScene.add(this.sky);
    this.scene.background = this.skyCube.texture;

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
    this.scene.add(this.sunLight, this.sunLight.target, this.hemi, this.fill);

    this.scene.add(this.land.group, this.base, this.fx.group, this.traffic.group);
    this.scene.fog = new THREE.Fog(0xb8c8d8, 350, 3600);

    this.composer = new EffectComposer(r, new THREE.WebGLRenderTarget(1, 1, { samples: 4, type: THREE.HalfFloatType }));
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    // clamp: near-mirror glass catching the moon (or a lamp) exactly makes one
    // pixel hundreds of times brighter than anything else, which bloom smears
    // into a disc. Capping brightness before the bloom keeps glints small. By
    // night only: by day the sun disc is meant to bloom.
    this.clamp = new ShaderPass(CLAMP);
    this.composer.addPass(this.clamp);
    this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.4, 0.5, 0.82);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    // Picking: a click that did not drag the camera, and hover for a tag.
    let down: { x: number; y: number } | null = null;
    let hoverAt = 0;
    r.domElement.addEventListener("pointerdown", (e) => (down = { x: e.clientX, y: e.clientY }));
    r.domElement.addEventListener("pointerup", (e) => {
      const moved = down ? Math.hypot(e.clientX - down.x, e.clientY - down.y) : 99;
      down = null;
      if (moved > 5) return;
      const i = this.pickAt(e.clientX, e.clientY);
      if (i !== null) this.onPick?.(i);
    });
    r.domElement.addEventListener("pointermove", (e) => {
      if (down || !this.onHover) return;
      const now = performance.now();
      if (now - hoverAt < 60) return;
      hoverAt = now;
      this.onHover(this.pickAt(e.clientX, e.clientY), e.clientX, e.clientY);
    });
    r.domElement.addEventListener("pointerleave", () => this.onHover?.(null, 0, 0));

    new ResizeObserver(() => this.resize()).observe(el);
    this.applyQuality(QUALITY[qualityPref()]);
    onQuality((q) => this.applyQuality(QUALITY[q]));
    const activity = () => this.activity();
    document.addEventListener("visibilitychange", activity);
    window.addEventListener("focus", activity);
    window.addEventListener("blur", activity);
    this.activity();
  }

  /** Follows the window: no frames while hidden, few while unfocused (pause). */
  private activity() {
    const hidden = !this.bench && document.hidden;
    this.dim = !this.bench && !document.hasFocus();
    if (this.dim && !this.focus) this.controls.autoRotate = false;
    this.renderer.setAnimationLoop(hidden ? null : () => this.frame());
    // A paused clock would hand the first frame back the whole gap.
    this.timer.reset();
    this.dirty = true;
  }

  /** A moment (camera move, collapse, rise, queued replay) plays at full rate even unfocused. */
  private moment(): boolean {
    if (this.dirty || this.focus || this.queue.length || this.dying.length || this.shake > 0 || this.fx.falling) return true;
    for (const e of this.entries.values()) if (e.rise || e.hit !== undefined) return true;
    return false;
  }

  /** The shop's picture of a blueprint (thumbs.ts), or null while its model is not loaded. */
  blueprintPic(id: string): string | null {
    return thumbnail(this.renderer, id);
  }

  static async create(el: HTMLElement, story: (text: string) => void): Promise<City> {
    // The renderer first: it picks the format compressed textures transcode to (real.ts).
    const city = new City(el, story);
    const models = (city.models = await modelsStatus());
    if (models.state === "ready") useModels(models.base, models.png ?? false);
    await Promise.all([loadKit(), models.state === "ready" ? loadReal(undefined, city.renderer) : null]);
    return city;
  }

  /**
   * quality (quality.ts): render scale, MSAA, shadow map and filter, bloom,
   * all changeable while the city is on screen. A new shadow filter
   * recompiles every material (one hitch, on a settings change).
   */
  private applyQuality(q: QualitySpec) {
    // shadow filter (shadow.ts): a fixed 2x2 grid looks as soft as three's
    // noisy 5-tap disc and costs less; &taps=1|4|5 compares them.
    const url = Number(new URLSearchParams(location.search).get("taps"));
    const taps = ([1, 4, 5].includes(url) ? url : q.taps) as ShadowTaps;
    if (taps !== this.taps) {
      const first = this.taps === 0;
      this.taps = taps;
      shadowTaps(taps);
      if (!first) {
        this.scene.traverse((o) => {
          const m = (o as THREE.Mesh).material;
          if (m) for (const x of Array.isArray(m) ? m : [m]) x.needsUpdate = true;
        });
        this.warm = true;
      }
    }
    this.renderer.setPixelRatio(q.scale);
    this.composer.setPixelRatio(q.scale);
    for (const rt of [this.composer.renderTarget1, this.composer.renderTarget2]) {
      if (rt.samples === q.msaa) continue;
      rt.samples = q.msaa;
      rt.dispose();
    }
    const shadow = this.sunLight.shadow;
    if (shadow.mapSize.x !== q.shadow) {
      shadow.mapSize.set(q.shadow, q.shadow);
      shadow.map?.dispose();
      shadow.map = null;
      this.shadowsDirty();
    }
    this.bloom.enabled = q.bloom;
    this.resize();
  }

  private resize() {
    this.dirty = true;
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
    setSprayScale(this.renderer.getPixelRatio());
  }

  /** New world or time; cheap to call on every poll. */
  update(world: World, hour: number, elapsedSecs: number) {
    const first = this.world === null;
    const was = this.world?.tier ?? world.tier;
    this.world = world;
    if (Math.abs(hour - this.hour) > 1 / 60 || first) this.light(hour);
    const p = plan(world, elapsedSecs);
    this.plan = p;
    this.buildBase(p);
    if (first) {
      this.frameCamera(p, true);
      this.benchCamera();
      this.firstSync(world, p);
      this.warm = true;
    } else {
      this.sync(p, true);
      // After the finished building has risen and sparkled.
      if (world.tier > was) this.later(2.8, () => this.graduate(world.tier));
    }
  }

  /**
   * The level-up moment: the camera turns to the whole city and slowly
   * circles it while fireworks go up over the rooftops. About 6 seconds;
   * nothing in it needs waiting for.
   */
  graduate(tier: number) {
    const p = this.plan;
    if (!p) return;
    this.story("Every need was met. The settlement grew.");
    const { minX, maxX, minZ, maxZ } = p.bounds;
    const cx = (minX + maxX) / 2;
    const cz = (minZ + maxZ) / 2;
    const span = Math.max(40, maxX - minX, maxZ - minZ);
    const tallest = Math.max(10, ...p.buildings.map((b) => (b.rubble ? 0 : b.height)));
    // Back off to the opening view's distance (frameCamera), a bit higher.
    const dist = Math.max(110, span * 1.4, tallest * 2.5);
    const ty = tallest * 0.45;
    this.focus = { to: new THREE.Vector3(cx, ty, cz), t: 0 };
    this.pull = { dist, rise: dist * 0.3 };
    this.controls.autoRotate = true;
    this.idle = 0;
    // Bursts in the upper part of that view, never over the top of the screen.
    const half = dist * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2));
    const size = Math.min(2.2, 0.8 + span / 250);
    // Brand amber and gold first, then the rest of a festival.
    const colors: [number, number, number][] = [[1, 0.7, 0.2], [1, 0.85, 0.35], [1, 0.4, 0.45], [0.45, 0.75, 1], [0.6, 1, 0.55], [1, 0.55, 0.15]];
    const shots = 10 + Math.min(8, tier * 3);
    for (let i = 0; i < shots; i++) {
      const at = 0.3 + i * 0.38 + Math.random() * 0.25;
      this.later(at, () => {
        const a = Math.random() * Math.PI * 2;
        const d = Math.random() * span * 0.45;
        const y = Math.max(tallest + 12, ty + half * (0.3 + Math.random() * 0.35));
        this.fx.firework(new THREE.Vector3(cx + Math.cos(a) * d, y, cz + Math.sin(a) * d), colors[i % colors.length], size);
      });
    }
    // The finale: three together.
    const end = 0.5 + shots * 0.38;
    for (let k = 0; k < 3; k++) {
      this.later(end + k * 0.08, () => {
        const a = (k / 3) * Math.PI * 2;
        this.fx.firework(new THREE.Vector3(cx + Math.cos(a) * span * 0.2, Math.max(tallest + 15, ty + half * 0.55), cz + Math.sin(a) * span * 0.2), colors[k], size * 1.3);
      });
    }
    this.later(end + 1.6, () => this.onGraduate?.(tier));
  }

  /** A screen shake, e.g. for a quake. */
  quake(strength = 1) {
    this.shake = Math.max(this.shake, strength);
  }

  /** Dev only (mock mode): play a transition on a plot. The next poll puts it back. */
  demo(kind: "collapse" | "build" | "damage" | "graduate", index = -1): string {
    if (kind === "graduate") {
      this.graduate(Math.max(1, this.world?.tier ?? 1));
      return "graduation";
    }
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
    return `${s.rubble ? "rubble" : "b"}:${s.grade}:${s.seed}:${s.rubble ? 0 : s.damage}:${s.shiny ? 1 : 0}`;
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
    this.prepare(e.group);
  }

  private remove(index: number) {
    const old = this.entries.get(index);
    if (old) this.scene.remove(old.group);
    this.entries.delete(index);
    this.shadowsDirty();
  }

  private specs(p: CityPlan): Map<number, Spec | SiteSpec> {
    const m = new Map<number, Spec | SiteSpec>();
    for (const b of p.buildings) m.set(b.index, b);
    for (const s of p.paused) m.set(s.index, s);
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
    let levels = unseen.filter((ev) => ev.kind === "graduated").length;
    for (const ev of unseen) {
      const evAt = at;
      if (ev.kind === "graduated") {
        const tier = w.tier - --levels;
        this.later(evAt, () => this.graduate(tier));
        at += 8;
        continue;
      }
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
    const key = `${p.blocks.length}:${p.tier}:${p.emptyLots.map((l) => l.seed).join(",")}`;
    if (key === this.baseKey) return;
    this.baseKey = key;
    this.scene.remove(this.base);
    this.base = new THREE.Group();
    this.lampMats = [];
    // cull: the streets are merged per block (and per kind of prop) instead
    // of once for the whole city, so blocks out of view are skipped, and
    // small props drop out with distance (TINY, SMALL; frame()).
    const chunks = new Map<string, { parts: Parts; centre: THREE.Vector3; far: number }>();
    const chunk = (key: string, x: number, z: number, far = Infinity) => {
      let c = chunks.get(key);
      if (!c) chunks.set(key, (c = { parts: new Parts(), centre: new THREE.Vector3(x, 0, z), far }));
      return c.parts;
    };
    // trees: past IMPOSTOR_NEAR a tile's trees are drawn as impostors
    // (impostor.ts); the real ones still draw the shadow map, and come back up close.
    const impostors = hasReal("trees") ? this.impostors : null;
    type Tile = { real: Parts; imp: Parts | null; centre: THREE.Vector3 };
    const tiles = new Map<string, Tile>();
    const tile = (key: string, x: number, z: number) => {
      let t = tiles.get(key);
      if (!t) tiles.set(key, (t = { real: new Parts(), imp: impostors && new Parts(), centre: new THREE.Vector3(x, 0, z) }));
      return t;
    };
    const gridTile = (x: number, z: number) => {
      const gx = Math.floor(x / TREE_TILE);
      const gz = Math.floor(z / TREE_TILE);
      return tile(`${gx},${gz}`, (gx + 0.5) * TREE_TILE, (gz + 0.5) * TREE_TILE);
    };
    /** A tree as tree() places it, plus its impostor. */
    const treeAt = (t: Tile, x: number, z: number, s: number, seed: number, y: number) => {
      tree(t.real, x, z, s, seed, y);
      if (t.imp) impostors!.tree(t.imp, x, z, s, seed, y, SPECIES);
    };
    // Parks, empty lots and the bridge: always drawn.
    const parts = chunk("all", 0, 0);
    // With the realistic street furniture come textured streets: asphalt,
    // paving slabs, granite kerbs, drains and manhole covers.
    const real = hasReal("street");
    const asphalt = real ? groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 }) : mat(0x3a3c40, { roughness: 0.95 });
    const walk = real ? groundMat("pave", 3.6, { roughness: 0.88 }) : mat(0xa8a49c, { roughness: 0.9 });
    const kerbStone = mat(0xb6b2aa, { roughness: 0.8 });
    const pool = real ? lightPool() : null;
    const iron = mat(0x2a2b2d, { roughness: 0.55, metalness: 0.5 });
    const line = mat(0xe8e0c0, { roughness: 0.6 });
    const pole = mat(0x3c4046, { metalness: 0.6, roughness: 0.4 });
    const bulb = mat(0xfff0d0, { emissive: 0xffd9a0, emissiveIntensity: 0, night: 2.2 });
    this.lampMats.push(bulb);
    const pw = PAVEMENT;
    for (const b of p.blocks) {
      const key = `${b.x},${b.z}`;
      const surf = chunk(key, b.x, b.z);
      const props = chunk(`${key}:props`, b.x, b.z, SMALL);
      const tiny = chunk(`${key}:tiny`, b.x, b.z, TINY);
      const trees = tile(`block:${key}`, b.x, b.z);
      surf.box(asphalt, PITCH_X + 0.02, 0.06, PITCH_Z + 0.02, b.x, 0, b.z);
      // Pavement: a raised ring round the block, kerb on the road side.
      for (const sz of [-1, 1]) surf.box(walk, BLOCK_X + 2 * pw, KERB, pw, b.x, 0, b.z + sz * (BLOCK_Z / 2 + pw / 2));
      for (const sx of [-1, 1]) surf.box(walk, pw, KERB, BLOCK_Z, b.x + sx * (BLOCK_X / 2 + pw / 2), 0, b.z);
      if (real) {
        // Granite kerbs on the road side, a drain grate by each kerb, and
        // manhole covers in the carriageway.
        const kx = BLOCK_X / 2 + pw - 0.09;
        const kz = BLOCK_Z / 2 + pw - 0.09;
        for (const sz of [-1, 1]) surf.box(kerbStone, BLOCK_X + 2 * pw, KERB + 0.004, 0.18, b.x, 0, b.z + sz * kz);
        for (const sx of [-1, 1]) surf.box(kerbStone, 0.18, KERB + 0.004, BLOCK_Z + 2 * pw - 0.36, b.x + sx * kx, 0, b.z);
        for (const sz of [-1, 1]) for (const t of [-0.6, 0.6]) surf.box(iron, 0.6, 0.065, 0.36, b.x + t * BLOCK_X / 2, 0, b.z + sz * (kz + 0.3));
        for (const sx of [-1, 1]) surf.box(iron, 0.36, 0.065, 0.6, b.x + sx * (kx + 0.3), 0, b.z + 4);
        for (const t of [-0.35, 0.35]) surf.add(iron, new THREE.CircleGeometry(0.33, 14), b.x + t * BLOCK_X, 0.066, b.z - PITCH_Z / 2 + 1.6, -Math.PI / 2);
      }
      // Dashed centre lines on the roads around the block.
      for (let x = -PITCH_X / 2; x < PITCH_X / 2; x += 5) {
        surf.box(line, 2.4, 0.07, 0.25, b.x + x + 1.2, 0, b.z - PITCH_Z / 2);
      }
      for (let z = -PITCH_Z / 2; z < PITCH_Z / 2; z += 5) {
        surf.box(line, 0.25, 0.07, 2.4, b.x - PITCH_X / 2, 0, b.z + z + 1.2);
      }
      // Zebra crossings at the corners.
      const kerb = ROAD - 2 * pw;
      for (const sx of [-1, 1]) {
        const x = b.x + sx * (BLOCK_X / 2 - 2.2);
        for (let i = 0; i < 6; i++) surf.box(line, 2.6, 0.07, 0.5, x, 0, b.z - BLOCK_Z / 2 - pw - 0.8 - i * ((kerb - 1) / 5));
        const z = b.z + (sx < 0 ? -1 : 1) * (BLOCK_Z / 2 - 2.2);
        for (let i = 0; i < 6; i++) surf.box(line, 0.5, 0.07, 2.6, b.x - BLOCK_X / 2 - pw - 0.8 - i * ((kerb - 1) / 5), 0, z);
      }
      // Street lamps along the kerb, and trees between them.
      const ex = BLOCK_X / 2 + pw - 0.45;
      const ez = BLOCK_Z / 2 + pw - 0.45;
      for (const lz of [-1, 1]) {
        for (const t of [-1, -1 / 3, 1 / 3, 1]) {
          const x = b.x + t * (BLOCK_X / 2 - 1);
          const z = b.z + lz * ez;
          if (real) {
            // The arm reaches out over the road; at night its light pools
            // on the road and pavement below (lit faces point down, so from
            // the usual overhead view the pool is what shows). The pool
            // stays when the lamp drops out with distance.
            furniture(props, "lamp_led", x, KERB, z, lz > 0 ? 0 : Math.PI);
            surf.add(pool!, new THREE.PlaneGeometry(11, 11), x, 0.08, z + lz * 1.8, -Math.PI / 2);
            continue;
          }
          props.cyl(pole, 0.08, 0.12, 5, x, KERB, z, 6);
          props.box(pole, 0.2, 0.15, 1.4, x, KERB + 4.9, z + lz * 0.6);
          props.box(bulb, 0.5, 0.18, 0.5, x, KERB + 4.75, z + lz * 1.1);
        }
        for (const t of [-5 / 6, -1 / 2, -1 / 6, 1 / 6, 1 / 2, 5 / 6]) {
          treeAt(trees, b.x + t * (BLOCK_X / 2 - 1), b.z + lz * ez, 0.5, Math.floor(b.x * 31 + b.z * 17 + t * 12 + lz * 5), KERB);
        }
      }
      for (const sx of [-1, 1]) treeAt(trees, b.x + sx * ex, b.z, 0.5, Math.floor(b.x * 13 + b.z * 7 + sx), KERB);
      if (real) this.streetFurniture(tiny, b, p.tier);
    }
    for (const k of p.parks) park(parts, k, pole, bulb);
    // Empty lots: rough grass with survey stakes, waiting to be built on.
    const stake = mat(0xc9a36a);
    const tape = mat(0xff8a2a, { emissive: 0x401800 });
    const e = LOT / 2 - 1.4;
    for (const l of p.emptyLots) {
      parts.box(real && hasReal("trees") ? groundMat("grass", 2.2, { roughness: 1, color: 0xc4b080 }) : mat(0x7a8f55, { roughness: 1 }), LOT - 0.4, KERB + 0.06, LOT - 0.4, l.x, 0, l.z);
      for (const [cx, cz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) parts.box(stake, 0.15, 0.9, 0.15, l.x + cx * e, KERB, l.z + cz * e);
      for (const cz of [-1, 1]) parts.box(tape, 2 * e, 0.04, 0.04, l.x, KERB + 0.75, l.z + cz * e);
      for (const cx of [-1, 1]) parts.box(tape, 0.04, 0.04, 2 * e, l.x + cx * e, KERB + 0.75, l.z);
      const r = rng(l.seed);
      if (r() < 0.35) {
        const [tx, tz] = [l.x + (r() - 0.5) * 8, l.z + (r() - 0.5) * 8];
        treeAt(gridTile(tx, tz), tx, tz, 0.8 + r() * 0.4, l.seed, KERB);
      }
    }
    this.land.build(p, impostors);
    const ground = this.land.shape;
    for (const t of p.trees) {
      const y = ground.height(t.x, t.z);
      if (y > WATER + 1.2 && Math.abs(t.z - ROAD_Z) > 7) treeAt(gridTile(t.x, t.z), t.x, t.z, t.s * 1.3, t.seed, y - 0.1);
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
    if (hasReal("bridge")) {
      for (const { role, geo } of realPiece("bridge", "bridge")) parts.add(realMat("bridge", role, { wall: 0, accent: 0, roof: 0, signs: 0 }, 0), geo, bx, 0, bz);
    } else {
      for (const { role, geo } of piece("bridge").parts) {
        const m = kitLook(role);
        if (m.userData.night && !this.lampMats.includes(m)) this.lampMats.push(m);
        parts.add(m, geo, bx, 0, bz);
      }
    }
    this.chunks = [];
    for (const c of chunks.values()) {
      const g = new THREE.Group();
      c.parts.into(g);
      this.base.add(g);
      if (c.far < Infinity) this.chunks.push({ group: g, centre: c.centre, far: c.far });
    }
    this.treeTiles = [];
    for (const t of tiles.values()) {
      const real = new THREE.Group();
      t.real.into(real);
      this.base.add(real);
      let imp: THREE.Group | null = null;
      if (t.imp) {
        imp = new THREE.Group();
        t.imp.into(imp, false);
        this.base.add(imp);
      }
      this.treeTiles.push({ real, imp, centre: t.centre });
    }
    this.base.traverse((o) => {
      if (o instanceof THREE.Mesh) {
        o.castShadow = o.material !== asphalt && o.material !== walk && o.material !== pool && !(o.material as THREE.Material).userData.noShadow;
        // Realistic lamps (street lights, park lanterns) light up at night too.
        const m = o.material as THREE.MeshStandardMaterial;
        if (m.userData.night && !this.lampMats.includes(m)) this.lampMats.push(m);
      }
    });
    this.scene.add(this.base);
    this.applyNight({ height: 0, emitters: [], beacons: [], night: this.lampMats, debris: 0 });
    this.traffic.build(p);
    this.prepare(this.base);
    this.prepare(this.land.group);
    this.prepare(this.traffic.group);
    this.warm = true;
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
    if (!this.shadowDir || this.shadowDir.angleTo(dir) > SUN_STEP) {
      this.shadowDir = dir.clone();
      this.shadowsDirty();
    }
    this.sunLight.intensity = THREE.MathUtils.lerp(0.35, 3.2, d.day);
    this.sunLight.color.setHex(d.day > 0.02 ? 0xffffff : 0x9fb4ff).lerp(new THREE.Color(0xffa860), d.golden * 0.7);
    this.hemi.intensity = THREE.MathUtils.lerp(0.25, 1.1, d.day);
    this.hemi.color.setHex(0xbcd4ff).lerp(new THREE.Color(0x2a3560), d.night);
    this.scene.environmentIntensity = THREE.MathUtils.lerp(0.15, 0.6, d.day);
    this.fill.intensity = this.scene.environment ? 0 : FILL * this.scene.environmentIntensity;
    for (const m of this.glossy) if (m.envMap === this.roomEnv) m.envMapIntensity = this.scene.environmentIntensity;
    this.renderer.toneMappingExposure = THREE.MathUtils.lerp(0.75, 0.6, d.day);
    (this.stars.material as THREE.PointsMaterial).opacity = d.night;
    const fog = new THREE.Color(0xc4d4e4).lerp(new THREE.Color(0xe0a070), d.golden * 0.6).lerp(new THREE.Color(0x0c1020), d.night);
    (this.scene.fog as THREE.Fog).color.copy(fog);
    this.land.setNight(d.night);
    this.bloom.strength = 0.15 + d.night * 0.4;
    this.clamp.enabled = d.night > 0.05;
    // threshold: a white wall in full sun reaches about 1.3 before tone
    // mapping, so a threshold under that made every white car, sign and
    // painted wall glow. By day only the sun disc (thousands) and real lights
    // clear it; by night the moonlit city sits far below 1 and lit windows,
    // lamps and neon (2 and up) still bloom.
    this.bloom.threshold = THREE.MathUtils.lerp(1.5, 6, d.day);
    for (const e of this.entries.values()) this.applyNight(e.info);
    for (const m of this.lampMats) m.emissiveIntensity = d.night * (m.userData.night ?? 1);
    interiorUniforms.uDay.value = d.day;
    interiorUniforms.uNight.value = d.night;
    this.skyEnv(d.sun, d.night);
    this.cubeCam.update(this.renderer, this.skyScene);
    this.dirty = true;
  }

  // ---- rendering optimisations ------------------------------------------------

  /** shadow: the shadow map is drawn again on the next frame. */
  private shadowsDirty() {
    this.renderer.shadowMap.needsUpdate = true;
    this.dirty = true;
  }

  /** The static shadow map, without what moves (shadows()). */
  private staticShadow: THREE.WebGLRenderTarget | null = null;
  private movers: THREE.Object3D[] = [];
  /** This frame's shadow work, from shadowPlan(). */
  private shadowWork = { full: false, move: false };

  /**
   * shadow, movers: buildings rising, shaking or falling, debris and crane
   * jibs move through the shadow map, but redrawing all of it each frame
   * they do (every tree and prop) doubled the frame for the seconds a
   * building rises. So the static map is drawn without them and kept; while
   * something moves, each frame copies it back and draws only the movers.
   */
  private shadowPlan(): boolean {
    const sm = this.renderer.shadowMap;
    let full = sm.needsUpdate || this.staticShadow?.width !== this.sunLight.shadow.mapSize.x;
    const movers: THREE.Object3D[] = [];
    let move = false;
    for (const e of this.entries.values()) {
      if (e.rise || e.hit !== undefined) {
        movers.push(e.group);
        move = true;
      }
      if (e.jib) {
        movers.push(e.jib);
        if (Math.abs(e.jib.rotation.y - (e.jibShadow ?? 1e9)) > 0.03) {
          e.jibShadow = e.jib.rotation.y;
          move = true;
        }
      }
    }
    for (const d of this.dying) movers.push(d.group);
    if (this.fx.falling) movers.push(this.fx.group);
    if (this.dying.length || this.fx.falling) move = true;
    // What stopped moving and still stands joins the static map.
    if (this.movers.some((o) => !movers.includes(o))) full = true;
    this.movers = movers;
    this.shadowWork = { full, move };
    return full;
  }

  /** Draws what shadowPlan() found (see there) with three's `draw`. */
  private shadows(draw: THREE.WebGLShadowMap["render"], lights: THREE.Light[], camera: THREE.Camera) {
    const { full, move } = this.shadowWork;
    this.shadowWork = { full: false, move: false };
    const sm = this.renderer.shadowMap;
    const sun = this.sunLight.shadow;
    const movers = this.movers;
    sm.needsUpdate = false;
    if (!full && !move) return;

    if (full) {
      const shown = [...movers, this.fx.group].filter((o) => o.visible);
      for (const o of shown) o.visible = false;
      sm.needsUpdate = true;
      draw(lights, this.scene, camera);
      for (const o of shown) o.visible = true;
      const size = sun.mapSize.x;
      if (this.staticShadow?.width !== size) {
        this.staticShadow?.dispose();
        this.staticShadow = new THREE.WebGLRenderTarget(size, size, { depthTexture: new THREE.DepthTexture(size, size, THREE.UnsignedIntType) });
        this.renderer.initRenderTarget(this.staticShadow);
      }
      this.renderer.copyTextureToTexture(sun.map!.depthTexture!, this.staticShadow.depthTexture!);
    } else {
      this.renderer.copyTextureToTexture(this.staticShadow!.depthTexture!, sun.map!.depthTexture!);
    }
    if (!movers.length) return;
    // The movers on top of the static map: three clears the map before it
    // draws, so clear() is held off for this one call.
    const root = new THREE.Group();
    root.children = movers;
    const clear = this.renderer.clear;
    this.renderer.clear = () => {};
    try {
      sm.needsUpdate = true;
      draw(lights, root as unknown as THREE.Scene, camera);
    } finally {
      this.renderer.clear = clear;
      sm.needsUpdate = false;
    }
  }

  /**
   * Readies new objects for the renderer: alpha to coverage on cut-out
   * materials (res), the environment light on glossy ones only (ibl), and
   * the shadow map redrawn now and again once their cut-out textures arrive
   * (drawn before the leaf textures loaded, every leaf card would be cut away
   * and trees would cast the shadows of bare branches).
   */
  private prepare(root: THREE.Object3D) {
    root.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        const s = m as THREE.MeshStandardMaterial;
        if (mesh.castShadow && m.alphaTest > 0 && s.map && !loaded(s.map)) this.shadowWait.add(s.map);
        if (this.prepared.has(m)) continue;
        this.prepared.add(m);
        if (m.alphaTest > 0 && !m.alphaToCoverage) {
          m.alphaToCoverage = true;
          m.needsUpdate = true;
        }
        if (s.isMeshStandardMaterial && !s.envMap && (s.metalness >= 0.3 || s.roughness <= 0.45)) {
          s.envMap = this.roomEnv;
          s.envMapIntensity = this.scene.environmentIntensity;
          s.needsUpdate = true;
          this.glossy.add(s);
        }
      }
    });
    this.shadowsDirty();
  }

  /**
   * prewarm: compiles every shader and uploads every texture now, with
   * everything shown, instead of the first time it comes into view: a shader
   * compiled mid-pan is a hitch of tens to hundreds of milliseconds (the 1% lows).
   */
  private prewarm() {
    const hidden: THREE.Object3D[] = [];
    this.scene.traverse((o) => {
      if (!o.visible) {
        hidden.push(o);
        o.visible = true;
      }
    });
    const seen = new Set<THREE.Texture>();
    this.scene.traverse((o) => {
      const m = (o as THREE.Mesh).material as unknown as Record<string, unknown> | undefined;
      if (!m) return;
      for (const v of Object.values(m)) if (v instanceof THREE.Texture && v.image && !seen.has(v)) seen.add(v);
    });
    for (const t of seen) this.renderer.initTexture(t);
    // compileAsync() picks its programs before it returns, so the hidden can hide again at once.
    const done = this.renderer.compileAsync(this.scene, this.camera);
    for (const o of hidden) o.visible = false;
    void done.then(() => (this.dirty = true));
  }

  /**
   * The orbit's polar limit keeps the camera above the target's level, not
   * above the land: on the hills round town, or looking along the ground,
   * it could sink into the terrain. So the eye is held a little above the
   * ground (or the water) under it, and the target never below it. The
   * margin grows away from town, where the terrain's triangles are larger
   * than its height function's bumps.
   */
  private keepAboveGround() {
    const g = this.land.shape;
    const t = this.controls.target;
    t.y = Math.max(t.y, g.height(t.x, t.z), WATER);
    const p = this.camera.position;
    const floor = Math.max(g.height(p.x, p.z), WATER) + 2.5 + Math.hypot(p.x, p.z) * 0.004;
    if (p.y < floor) {
      p.y = floor;
      this.camera.lookAt(t);
    }
  }

  /** Bench (`?bench&cam=x,y,z,tx,ty,tz`): a fixed camera, no auto-rotate. */
  private benchCamera() {
    const cam = new URLSearchParams(location.search).get("cam");
    if (!this.bench || !cam) return;
    const [x, y, z, tx, ty, tz] = cam.split(",").map(Number);
    this.camera.position.set(x, y, z);
    this.controls.target.set(tx, ty, tz);
    this.controls.autoRotate = false;
    this.idle = -1e9;
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
    // Nothing to draw before the first world (the models are still loading).
    if (!this.world) return;
    if (this.dim && !this.moment()) {
      const now = performance.now();
      if (now - this.dimAt < 1000 / DIM_FPS) return;
      this.dimAt = now;
    }
    this.timer.update();
    const raw = this.timer.getDelta();
    // dim frames are far apart: a larger step keeps ambient motion at its speed.
    const dt = Math.min(this.dim ? 0.25 : 0.05, raw);
    this.t += dt;
    if ((this.fpsT += raw) >= 1) {
      this.fps = this.fpsCount / this.fpsT;
      this.fpsCount = this.fpsT = 0;
    }
    for (const q of this.queue.filter((q) => q.at <= this.t)) q.run();
    this.queue = this.queue.filter((q) => q.at > this.t);

    this.idle += dt;
    if (!this.controls.autoRotate && this.idle > 30 && !this.focus && !this.dim) this.controls.autoRotate = true;
    if (this.focus) {
      this.focus.t += dt;
      this.controls.target.lerp(this.focus.to, Math.min(1, dt * 1.5));
      if (this.pull) {
        const off = this.camera.position.clone().sub(this.controls.target);
        const k = Math.min(1, dt * 1.2);
        const flat = Math.hypot(off.x, off.z) || 1;
        const want = Math.sqrt(Math.max(1, this.pull.dist ** 2 - this.pull.rise ** 2));
        const f = (flat + (want - flat) * k) / flat;
        off.x *= f;
        off.z *= f;
        off.y += (this.pull.rise - off.y) * k;
        this.camera.position.copy(this.controls.target).add(off);
      }
      if (this.focus.t > 3.5) {
        this.focus = null;
        this.pull = null;
        if (this.dim) this.controls.autoRotate = false;
        if (this.plan) this.frameCamera(this.plan, false);
      }
    }
    this.controls.update(dt);
    this.keepAboveGround();

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
    if (!this.dim) this.traffic.update(dt);
    setSignals(this.t, this.night);
    setWaterTime(this.t);

    let animating = this.dying.length > 0 || this.fx.falling;
    let busy = false;
    for (const e of this.entries.values()) {
      if (e.rise || e.hit !== undefined) animating = true;
      if (e.ghost || e.jib || e.info.emitters.length) busy = true;
    }
    if (this.shadowWait.size && [...this.shadowWait].every(loaded)) {
      this.shadowWait.clear();
      this.shadowsDirty();
      this.warm = true;
    }
    if (this.impostors.pending) this.impostors.draw();

    if (this.shake > 0) {
      this.shake = Math.max(0, this.shake - dt * 0.8);
      const a = this.shake * 1.2;
      this.camera.position.x += (Math.random() - 0.5) * a;
      this.camera.position.y += (Math.random() - 0.5) * a;
    }
    // idle: no frames while nothing moves (camera at rest, no auto-rotate, no
    // traffic, effects or transitions): a focus timer's city can sit on screen
    // for hours, and a still frame costs as much as a busy one.
    const moving = this.controls.autoRotate || !!this.focus || this.shake > 0 || this.queue.length > 0 || animating || busy || this.fx.active || (this.traffic.active && !this.dim) || this.impostors.pending > 0;
    if (!moving && !this.dirty && !this.bench) return;
    this.dirty = false;
    if (this.warm) {
      this.warm = false;
      this.prewarm();
    }
    // cull and trees: small props out with distance, trees real near the
    // camera and impostors further out (everything in while the shadow map is
    // drawn, so what drops out keeps its shadow).
    const shadowing = this.shadowPlan();
    const eye = this.camera.position;
    for (const c of this.chunks) c.group.visible = shadowing || eye.distanceTo(c.centre) < c.far;
    for (const t of this.treeTiles) {
      if (!t.imp) continue;
      const near = shadowing || eye.distanceTo(t.centre) < IMPOSTOR_NEAR;
      t.real.visible = near;
      t.imp.visible = !near;
    }
    this.land.cull(eye);
    this.fpsCount++;
    this.bench?.begin();
    this.composer.render(dt);
    this.bench?.end();
  }
}

function describeLive(ev: WorldEvent, w: World): string {
  const names = (l: number[]) => namesOf(w, l);
  switch (ev.kind) {
    case "built":
      return `${names(ev.plots)} was finished.`;
    case "repaired":
      return `Focus repaired ${names(ev.plots)}.`;
    case "graduated":
      return "Every need was met. The settlement grew.";
    case "collapsed":
      return `You surrendered. The session built nothing${ev.plots.length > 1 ? `, and fire spread to ${names(ev.plots.slice(1))}` : ""}.`;
    case "quake":
      return ev.plots.length ? `Tampering set off an earthquake: ${names(ev.plots)} damaged.` : "Tampering set off an earthquake.";
    case "damaged": {
      const why = { clock_jump: "A wall clock jump", tunnel: "A proxy around the throttle" }[ev.cause as string] ?? "A refused root attempt";
      return `${why} damaged ${names(ev.plots)}.`;
    }
  }
}

let poolMat: THREE.MeshStandardMaterial | null = null;

/**
 * The glow a street light throws on the ground: a warm radial gradient,
 * added on top of what is below, its strength following the night (it is
 * one of the scene's lamp materials).
 */
function lightPool(): THREE.MeshStandardMaterial {
  if (poolMat) return poolMat;
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  // Grey on black: alphaMap and emissiveMap both read the colour channels.
  g.fillStyle = "#000";
  g.fillRect(0, 0, 128, 128);
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, "#fff");
  grad.addColorStop(0.3, "#9a9a9a");
  grad.addColorStop(0.7, "#262626");
  grad.addColorStop(1, "#000");
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  poolMat = new THREE.MeshStandardMaterial({
    color: 0x000000, roughness: 1, emissive: 0xffc27a, emissiveMap: t, emissiveIntensity: 0, alphaMap: t,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
  });
  poolMat.userData.night = 0.65;
  return poolMat;
}
