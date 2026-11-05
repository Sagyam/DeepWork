// The showcase town: every realistic model (blender/real) together in one
// hand-laid town, built with the app's own code (models.ts, real.ts), so
// new models can be seen in context without earning them through focus.
// A dev tool, not part of the app. Open /town.html in the dev server with
//   ?view=overview|downtown|main|homes|works|bridge|plaza|skyline &hour=15
//   &still (parks the traffic) &gputimer=0 (no GPU timer queries)
// The bottom-left panel ("stats for nerds") shows frame, CPU and GPU times,
// draw calls, triangles and memory, for judging the cost of new models.
// A new model shows up once it is added to BLOCKS below.
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { loadKit } from "../city/kit";
import { building, furniture, KERB, mat, park, parked, Parts, tree } from "../city/models";
import { BLOCK_X, BLOCK_Z, LOT, PAVEMENT, PITCH_X, PITCH_Z, rng, type Spec } from "../city/plan";
import { CAR_PAINTS, DEFS, groundMat, hasReal, interiorUniforms, loadReal, PROPS, realMat, realPiece, realPieces, setRealEnv, setSignals } from "../city/real";

const q = new URLSearchParams(location.search);
const hour = Number(q.get("hour") ?? 15);
const night = hour < 6 || hour >= 19.5;

// ---- the plan: 3 x 3 blocks of 4 x 2 lots, a river and bridge east ----

type Block = { bx: number; bz: number; north?: string[]; south?: string[]; park?: "park" | "plaza" | "sports" };
// "id:floors"; north row faces -z, south row faces +z.
const BLOCKS: Block[] = [
  { bx: 0, bz: 0, south: ["s2", "o1:12", "l1:16", "a1:7"], north: ["a3:6", "o1:18", "o1:9", "s2"] },
  { bx: 1, bz: 0, south: ["s1", "s2", "s1", "s3"], north: ["a2", "a1:5", "s1", "a2"] },
  { bx: -1, bz: 0, south: ["a3:5", "a2", "a2", "a1:6"], north: ["a2", "a3:8", "s1", "a3:4"] },
  { bx: 0, bz: -1, south: ["c1", "c2", "c3", "c4"], north: ["c2", "c1", "c4", "c3"] },
  { bx: -1, bz: -1, south: ["c3", "c4", "c1", "c2"], north: ["c4", "c3", "c2", "c1"] },
  { bx: 1, bz: -1, park: "park" },
  { bx: 0, bz: 1, south: ["o1:7", "s1", "a1:4", "s3"], north: ["s3", "a2", "s2", "a3:5"] },
  { bx: 1, bz: 1, south: ["s4", "s4", "s3", "s4"], north: ["s4", "s4", "s4", "s1"] },
  { bx: -1, bz: 1, park: "plaza" },
];
const ROAD_Z = PITCH_Z / 2; // the through road, between the middle and south block rows
const RX = 168; // river centre
const RIVER = 18; // half width, bank to bank (the bridge spans 44 m)
const EDGE_X = 1.5 * PITCH_X;
const EDGE_Z = 1.5 * PITCH_Z;

// ---- renderer, camera ----

const el = document.getElementById("view")!;
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
el.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.5, 6000);
const VIEWS: Record<string, [number[], number[], number]> = {
  overview: [[135, 85, 150], [10, 12, 0], 42],
  downtown: [[34, 1.8, ROAD_Z + 2.5], [-6, 16, -6], 62],
  main: [[PITCH_X + 40, 1.8, ROAD_Z - 1], [PITCH_X - 10, 6, 6], 58],
  homes: [[-20, 26, -PITCH_Z - 50], [-20, 2, -PITCH_Z], 46],
  works: [[PITCH_X + 60, 30, PITCH_Z + 70], [PITCH_X, 4, PITCH_Z], 44],
  bridge: [[RX + 40, 6, ROAD_Z + 34], [RX - 10, 3, ROAD_Z], 50],
  plaza: [[-PITCH_X + 10, 14, PITCH_Z + 48], [-PITCH_X, 2, PITCH_Z], 50],
  skyline: [[-260, 40, 120], [0, 30, 0], 32],
};
const view = q.get("view") ?? "overview";
const [pos, at, fov] = VIEWS[view] ?? VIEWS.overview;
camera.position.fromArray(pos);
camera.fov = fov;
camera.updateProjectionMatrix();
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.fromArray(at);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.62;
controls.update();

const hud = document.getElementById("hud")!;
const link = (label: string, params: Record<string, string>) => {
  const a = document.createElement("a");
  const u = new URLSearchParams(q);
  for (const [k, v] of Object.entries(params)) u.set(k, v);
  a.href = `?${u}`;
  a.textContent = label;
  hud.appendChild(a);
};
for (const v of Object.keys(VIEWS)) link(v, { view: v });
link("☀ day", { hour: "14" });
link("◐ golden", { hour: "18.4" });
link("☾ night", { hour: "21" });

// ---- sky, sun and the environment the glass reflects (as in the viewer) ----

const elev = night ? 0.5 : Math.max(4, 50 * Math.sin(((hour - 6) / 13.5) * Math.PI));
const az = THREE.MathUtils.degToRad(night ? 210 : -95 + (hour - 9) * 12);
const sunDir = new THREE.Vector3().setFromSphericalCoords(1, THREE.MathUtils.degToRad(90 - (night ? -12 : elev)), az);
const sky = new Sky();
sky.scale.setScalar(5000);
const su = sky.material.uniforms;
su.turbidity.value = 4;
su.rayleigh.value = night ? 0.3 : 1.4;
su.mieCoefficient.value = 0.004;
su.mieDirectionalG.value = 0.82;
su.sunPosition.value.copy(sunDir);
scene.add(sky);

const pmrem = new THREE.PMREMGenerator(renderer);
const envScene = new THREE.Scene();
const envSky = new Sky();
envSky.scale.setScalar(1000);
Object.assign(envSky.material.uniforms, THREE.UniformsUtils.clone(sky.material.uniforms));
envSky.material.uniforms.sunPosition.value.copy(sunDir);
envSky.material.uniforms.mieDirectionalG.value = 0.6;
envSky.material.uniforms.showSunDisc.value = 0;
envScene.add(envSky);
const envGround = new THREE.Mesh(new THREE.CircleGeometry(900, 32).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: night ? 0x050608 : 0x3a3c3e }));
envGround.position.y = -2;
envScene.add(envGround);
const env = pmrem.fromScene(envScene, 0.02).texture;
scene.environment = env;
scene.environmentIntensity = night ? 0.08 : 0.12;
setRealEnv(env);

const sun = new THREE.DirectionalLight(night ? 0x8fa8d8 : 0xfff1dc, night ? 0.25 : 5);
const reach = 200;
sun.position.copy(night ? new THREE.Vector3(-0.4, 0.8, 0.5) : sunDir).multiplyScalar(500);
sun.target.position.set(20, 0, 0);
sun.position.add(sun.target.position);
scene.add(sun.target);
sun.castShadow = true;
sun.shadow.mapSize.setScalar(8192);
const sc = sun.shadow.camera;
sc.left = sc.bottom = -reach;
sc.right = sc.top = reach;
sc.near = 1;
sc.far = 1200;
sun.shadow.bias = -0.0002;
sun.shadow.normalBias = 0.05;
scene.add(sun);
scene.add(new THREE.HemisphereLight(night ? 0x223044 : 0xc8dcff, night ? 0x101010 : 0x5a5248, night ? 0.15 : 0.35));
scene.fog = new THREE.Fog(night ? 0x0a0e18 : 0xc4d2e0, 400, 3000);
renderer.toneMappingExposure = night ? 0.9 : 0.75;
interiorUniforms.uDay.value = night ? 0 : 1;
interiorUniforms.uNight.value = night ? 1 : 0;

// ---- building ----

const KIND_GRADE: Record<string, number> = { landmark: 4, office: 3, apartment: 2, shop: 1, cottage: 0 };

function place(code: string, lx: number, lz: number, rot: number, seed: number) {
  const [id, fl] = code.split(":");
  const def = DEFS[id];
  if (!def || !hasReal(id)) return console.warn("missing model", id);
  const floors = def.floors(Number(fl ?? 3));
  const yard = LOT / 2 - def.d / 2 - def.front;
  const s: Spec = {
    index: 0, kind: def.kind, style: def.style, grade: KIND_GRADE[def.kind], x: lx + Math.sin(rot) * yard, z: lz + Math.cos(rot) * yard, rot, yard,
    w: def.w, d: def.d, floors, floorH: def.top(floors) / floors, height: def.height(floors), wall: seed % 8, accent: (seed * 3) % 6, seed, damage: 0, rubble: false, model: id,
  };
  scene.add(building(s).group);
}

function streets(parts: Parts, b: { x: number; z: number }, r: () => number) {
  const asphalt = groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 });
  const walk = groundMat("pave", 3.6, { roughness: 0.88 });
  const kerbStone = mat(0xb6b2aa, { roughness: 0.8 });
  const iron = mat(0x2a2b2d, { roughness: 0.55, metalness: 0.5 });
  const line = mat(0xe8e0c0, { roughness: 0.6 });
  const pw = PAVEMENT;
  parts.box(asphalt, PITCH_X + 0.02, 0.06, PITCH_Z + 0.02, b.x, 0, b.z);
  for (const sz of [-1, 1]) parts.box(walk, BLOCK_X + 2 * pw, KERB, pw, b.x, 0, b.z + sz * (BLOCK_Z / 2 + pw / 2));
  for (const sx of [-1, 1]) parts.box(walk, pw, KERB, BLOCK_Z, b.x + sx * (BLOCK_X / 2 + pw / 2), 0, b.z);
  const kx = BLOCK_X / 2 + pw - 0.09;
  const kz = BLOCK_Z / 2 + pw - 0.09;
  for (const sz of [-1, 1]) parts.box(kerbStone, BLOCK_X + 2 * pw, KERB + 0.004, 0.18, b.x, 0, b.z + sz * kz);
  for (const sx of [-1, 1]) parts.box(kerbStone, 0.18, KERB + 0.004, BLOCK_Z + 2 * pw - 0.36, b.x + sx * kx, 0, b.z);
  for (const sz of [-1, 1]) for (const t of [-0.6, 0.6]) parts.box(iron, 0.6, 0.065, 0.36, b.x + (t * BLOCK_X) / 2, 0, b.z + sz * (kz + 0.3));
  for (const t of [-0.35, 0.35]) parts.add(iron, new THREE.CircleGeometry(0.33, 14), b.x + t * BLOCK_X, 0.066, b.z - PITCH_Z / 2 + 1.6, -Math.PI / 2);
  for (let x = -PITCH_X / 2; x < PITCH_X / 2; x += 5) parts.box(line, 2.4, 0.07, 0.25, b.x + x + 1.2, 0, b.z - PITCH_Z / 2);
  for (let z = -PITCH_Z / 2; z < PITCH_Z / 2; z += 5) parts.box(line, 0.25, 0.07, 2.4, b.x - PITCH_X / 2, 0, b.z + z + 1.2);
  const kerb = 12 - 2 * pw;
  for (const sx of [-1, 1]) {
    const x = b.x + sx * (BLOCK_X / 2 - 2.2);
    for (let i = 0; i < 6; i++) parts.box(line, 2.6, 0.07, 0.5, x, 0, b.z - BLOCK_Z / 2 - pw - 0.8 - i * ((kerb - 1) / 5));
    const z = b.z + (sx < 0 ? -1 : 1) * (BLOCK_Z / 2 - 2.2);
    for (let i = 0; i < 6; i++) parts.box(line, 0.5, 0.07, 2.6, b.x - BLOCK_X / 2 - pw - 0.8 - i * ((kerb - 1) / 5), 0, z);
  }
  const ex = BLOCK_X / 2 + pw - 0.45;
  const ez = BLOCK_Z / 2 + pw - 0.45;
  for (const lz of [-1, 1]) {
    for (const t of [-1, -1 / 3, 1 / 3, 1]) furniture(parts, "lamp_led", b.x + t * (BLOCK_X / 2 - 1), KERB, b.z + lz * ez, lz > 0 ? 0 : Math.PI);
    for (const t of [-5 / 6, -1 / 2, -1 / 6, 1 / 6, 1 / 2, 5 / 6]) tree(parts, b.x + t * (BLOCK_X / 2 - 1), b.z + lz * ez, 0.5, Math.floor(b.x * 31 + b.z * 17 + t * 12 + lz * 5), KERB);
    // Parked cars along the kerb, between the trees.
    for (const t of [-2 / 3, 0, 2 / 3]) {
      if (r() < 0.3) continue;
      const x = b.x + t * (BLOCK_X / 2 - 1) + (r() - 0.5) * 3;
      parked(parts, x, b.z + lz * (BLOCK_Z / 2 + pw + 1.1), lz > 0 ? -Math.PI / 2 : Math.PI / 2, Math.floor(r() * 1e6), 0.06);
    }
  }
  for (const sx of [-1, 1]) tree(parts, b.x + sx * ex, b.z, 0.5, Math.floor(b.x * 13 + b.z * 7 + sx), KERB);
  // Street furniture: signals, hydrant, bins, bench, bus stop.
  const cx = BLOCK_X / 2 + pw - 0.55;
  const cz = BLOCK_Z / 2 + pw - 0.55;
  furniture(parts, "signal_mast", b.x + cx, KERB, b.z + cz, Math.PI / 2, undefined, "a");
  furniture(parts, "signal_mast", b.x - cx, KERB, b.z - cz, -Math.PI / 2, undefined, "a");
  furniture(parts, "signal_post", b.x - cx, KERB, b.z + cz, 0, undefined, "b");
  furniture(parts, "signal_post", b.x + cx, KERB, b.z - cz, Math.PI, undefined, "b");
  const kb = BLOCK_Z / 2 + pw - 0.4;
  furniture(parts, "hydrant", b.x, KERB, b.z + kb, 0);
  for (const sx of [-1, 1]) furniture(parts, "bin", b.x + sx * (BLOCK_X / 2 - 3.2), KERB, b.z - sx * kb, sx > 0 ? 0 : Math.PI);
  furniture(parts, "bench", b.x - 20.7, KERB, b.z + BLOCK_Z / 2 + pw - 1.3, 0);
  furniture(parts, "busstop", b.x + 20.7, KERB, b.z - (BLOCK_Z / 2 + pw - 1.0), Math.PI);
}

function land(parts: Parts) {
  const grass = groundMat("grass", 2.2, { roughness: 0.98, normal: 0.8 });
  const asphalt = groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 });
  const stone = groundMat("ashlar", 2, { roughness: 0.9 });
  const line = mat(0xe8e4d8, { roughness: 0.7 });
  const W = 1400;
  // The ground either side of the river, its banks faced in stone, the bed and the water.
  parts.box(grass, RX - RIVER + W, 4, W * 2, (RX - RIVER - W) / 2, -4, 0);
  parts.box(grass, W, 4, W * 2, RX + RIVER + W / 2, -4, 0);
  for (const sx of [-1, 1]) parts.box(stone, 0.6, 4.02, W * 2, RX + sx * (RIVER - 0.3), -4, 0);
  parts.box(mat(0x4a4436, { roughness: 1 }), RIVER * 2, 0.2, W * 2, RX, -4.2, 0);
  // Roads out of town along ROAD_Z, west and east over the bridge.
  const roadOut = (x0: number, x1: number) => {
    parts.box(asphalt, x1 - x0, 0.06, 9, (x0 + x1) / 2, 0, ROAD_Z);
    for (let x = x0; x + 3 < x1; x += 9) parts.box(line, 3, 0.07, 0.14, x + 1.5, 0, ROAD_Z);
    for (const e of [-1, 1]) parts.box(line, x1 - x0, 0.07, 0.14, (x0 + x1) / 2, 0, ROAD_Z + e * 4.05);
  };
  roadOut(EDGE_X, RX - 22);
  roadOut(RX + 22, 700);
  roadOut(-700, -EDGE_X);
  for (const { role, geo } of realPiece("bridge", "bridge")) parts.add(realMat("bridge", role, { wall: 0, accent: 0, roof: 0, signs: 0 }, 0), geo, RX, 0, ROAD_Z);
  // Woods round the town, thicker further out, none on the roads or in the river.
  const r = rng(7);
  for (let i = 0; i < 1400; i++) {
    const x = (r() - 0.5) * 900;
    const z = (r() - 0.5) * 900;
    const out = Math.max(Math.abs(x) - EDGE_X, Math.abs(z) - EDGE_Z);
    if (out < 6) continue;
    if (Math.abs(z - ROAD_Z) < 9 || Math.abs(x - RX) < RIVER + 4) continue;
    if (r() > Math.min(1, 0.15 + out / 120)) continue;
    tree(parts, x, z, 0.8 + r() * 0.5, Math.floor(r() * 1e6), 0);
  }
}

const water = new THREE.Mesh(
  new THREE.PlaneGeometry(RIVER * 2, 2800).rotateX(-Math.PI / 2),
  new THREE.MeshStandardMaterial({ color: night ? 0x0a1420 : 0x2c4a58, roughness: 0.05, metalness: 0.2, envMapIntensity: 6 }),
);
water.position.set(RX, -1.6, 0);
water.receiveShadow = true;
scene.add(water);

// ---- traffic: cars driving round the grid (through the junctions, it's a showcase) ----

type Mover = { obj: THREE.Object3D; axis: "x" | "z"; dir: number; speed: number; min: number; max: number };
const movers: Mover[] = [];
function traffic() {
  const names = realPieces("cars");
  const r = rng(11);
  const lanes: { axis: "x" | "z"; c: number; min: number; max: number }[] = [
    { axis: "x", c: -PITCH_Z / 2, min: -EDGE_X, max: EDGE_X },
    { axis: "x", c: ROAD_Z, min: -500, max: 500 },
    { axis: "z", c: -PITCH_X / 2, min: -EDGE_Z, max: EDGE_Z },
    { axis: "z", c: PITCH_X / 2, min: -EDGE_Z, max: EDGE_Z },
  ];
  for (const l of lanes) {
    for (const dir of [-1, 1]) {
      const n = l.max - l.min > 400 ? 14 : 4;
      for (let i = 0; i < n; i++) {
        const name = names[Math.floor(r() * names.length)];
        const g = new THREE.Group();
        const paint = { wall: Math.floor(r() * CAR_PAINTS.length), accent: 0, roof: 0, signs: 0 };
        for (const { role, geo } of realPiece("cars", name)) {
          const m = new THREE.Mesh(geo, realMat("cars", role, paint, 0, "traffic"));
          m.castShadow = true;
          m.receiveShadow = true;
          g.add(m);
        }
        // Right-hand traffic: moving +x keeps to +z, moving +z keeps to -x.
        const off = 2 * dir;
        if (l.axis === "x") {
          g.position.set(0, 0.06, l.c + off);
          g.rotation.y = dir > 0 ? Math.PI / 2 : -Math.PI / 2;
        } else {
          g.position.set(l.c - off, 0.06, 0);
          g.rotation.y = dir > 0 ? 0 : Math.PI;
        }
        const t = l.min + ((i + r() * 0.5) / n) * (l.max - l.min);
        g.position[l.axis] = t;
        scene.add(g);
        movers.push({ obj: g, axis: l.axis, dir, speed: 8 + r() * 4, min: l.min, max: l.max });
      }
    }
  }
}

// ---- go ----

Promise.all([loadKit(), loadReal([...Object.keys(DEFS), ...PROPS])]).then(() => {
  const missing = [...Object.keys(DEFS), ...PROPS].filter((id) => !hasReal(id));
  if (missing.length) console.warn("not built:", missing);
  const parts = new Parts();
  land(parts);
  const r = rng(3);
  const pole = mat(0x3c4046, { metalness: 0.6, roughness: 0.4 });
  const bulb = mat(0xfff0d0, { emissive: 0xffd9a0, emissiveIntensity: 0, night: 2.2 });
  for (const b of BLOCKS) {
    const x = b.bx * PITCH_X;
    const z = b.bz * PITCH_Z;
    streets(parts, { x, z }, r);
    if (b.park) {
      park(parts, { x, z, kind: b.park, seed: 5 + b.bx * 3 + b.bz }, pole, bulb);
      continue;
    }
    for (const [row, list] of [[1, b.south], [-1, b.north]] as const) {
      list!.forEach((code, i) => place(code, x + (i - 1.5) * LOT, z + row * (LOT / 2), row > 0 ? 0 : Math.PI, 7 + Math.floor(r() * 400)));
    }
  }
  const g = new THREE.Group();
  parts.into(g);
  scene.add(g);
  traffic();
  // Everything that lights at night (windows, lamps, signals, neon, headlights).
  scene.traverse((o) => {
    const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
    if (m?.userData?.night) m.emissiveIntensity = night ? m.userData.night : 0;
  });
  frames = 0;
});

// ---- render ----

const target_ = new THREE.WebGLRenderTarget(innerWidth * renderer.getPixelRatio(), innerHeight * renderer.getPixelRatio(), { samples: 4, type: THREE.HalfFloatType });
const composer = new EffectComposer(renderer, target_);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth / 2, innerHeight / 2), 0.55, 0.5, 0.75);
bloom.enabled = night;
composer.addPass(bloom);
composer.addPass(new OutputPass());
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
});

let frames = -1;
let last = performance.now();
const still = q.has("still");

// ---- stats for nerds (bottom left) ----

const statsEl = document.getElementById("stats")!;
const statsText = document.getElementById("stats-text")!;
const graph = document.getElementById("stats-graph") as HTMLCanvasElement;
const gctx = graph.getContext("2d")!;
const N = 240;
const frameMs = new Float32Array(N); // wall time between frames
const cpuMs = new Float32Array(N); // JS time spent in the frame
const gpuMs = new Float32Array(N); // GPU time, if the timer query extension is there
let head = 0;
let lastGpu = 0;
renderer.info.autoReset = false;
const gl = renderer.getContext() as WebGL2RenderingContext;
const timerExt = q.get("gputimer") === "0" ? null : gl.getExtension("EXT_disjoint_timer_query_webgl2");
const pending: WebGLQuery[] = [];
const dbg = gl.getExtension("WEBGL_debug_renderer_info");
const gpuName = dbg ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)) : String(gl.getParameter(gl.RENDERER));
statsEl.addEventListener("click", () => statsEl.classList.toggle("min"));

function pollGpu() {
  while (pending.length) {
    const qy = pending[0];
    if (!gl.getQueryParameter(qy, gl.QUERY_RESULT_AVAILABLE)) break;
    const disjoint = gl.getParameter(timerExt!.GPU_DISJOINT_EXT);
    if (!disjoint) lastGpu = gl.getQueryParameter(qy, gl.QUERY_RESULT) / 1e6;
    gl.deleteQuery(qy);
    pending.shift();
  }
}

function stat(a: Float32Array) {
  const v = [...a].filter((x) => x > 0).sort((x, y) => x - y);
  if (!v.length) return { avg: 0, min: 0, max: 0, p99: 0 };
  return { avg: v.reduce((s, x) => s + x, 0) / v.length, min: v[0], max: v[v.length - 1], p99: v[Math.min(v.length - 1, Math.floor(v.length * 0.99))] };
}

function drawGraph() {
  const w = graph.width;
  const h = graph.height;
  gctx.clearRect(0, 0, w, h);
  const top = Math.min(250, Math.max(40, Math.ceil((stat(frameMs).p99 * 1.15) / 10) * 10));
  const y = (ms: number) => h - (ms / top) * h;
  gctx.font = "10px ui-monospace, monospace";
  for (const [ms, label] of [[1000 / 60, "60"], [1000 / 30, "30"]] as const) {
    gctx.strokeStyle = "#ffffff30";
    gctx.setLineDash([3, 3]);
    gctx.beginPath();
    gctx.moveTo(0, y(ms));
    gctx.lineTo(w, y(ms));
    gctx.stroke();
    gctx.fillStyle = "#ffffff70";
    gctx.fillText(label, w - 16, y(ms) - 2);
  }
  gctx.setLineDash([]);
  const line = (a: Float32Array, color: string, fill = false) => {
    gctx.beginPath();
    for (let i = 0; i < N; i++) {
      const x = (i / (N - 1)) * w;
      const v = Math.min(a[(head + i) % N], top);
      if (i === 0) gctx.moveTo(x, y(v));
      else gctx.lineTo(x, y(v));
    }
    if (fill) {
      gctx.lineTo(w, h);
      gctx.lineTo(0, h);
      gctx.fillStyle = color + "40";
      gctx.fill();
    } else {
      gctx.strokeStyle = color;
      gctx.lineWidth = 1.25;
      gctx.stroke();
    }
  };
  line(frameMs, "#5ab0ff", true);
  line(frameMs, "#5ab0ff");
  line(cpuMs, "#7ee08a");
  if (timerExt) line(gpuMs, "#ffad4a");
  gctx.fillStyle = "#ffffffa0";
  gctx.fillText(`${top} ms`, 2, 10);
}

const fmt = (n: number) => n.toLocaleString("en-US");
function updateText() {
  const f = stat(frameMs);
  const c = stat(cpuMs);
  const g = stat(gpuMs);
  const i = renderer.info;
  const mem = (performance as unknown as { memory?: { usedJSHeapSize: number; jsHeapSizeLimit: number } }).memory;
  const pr = renderer.getPixelRatio();
  const rows: [string, string][] = [
    ["fps", `${(1000 / (f.avg || 1)).toFixed(1)}   1% low ${(1000 / (f.p99 || 1)).toFixed(1)}`],
    ["frame", `${f.avg.toFixed(2)} ms  (min ${f.min.toFixed(1)}, max ${f.max.toFixed(1)})`],
    ["cpu", `${c.avg.toFixed(2)} ms  (max ${c.max.toFixed(1)})`],
    ["gpu", timerExt ? `${g.avg.toFixed(2)} ms  (max ${g.max.toFixed(1)})` : "n/a (no timer query)"],
    ["draws", fmt(i.render.calls)],
    ["tris", fmt(i.render.triangles)],
    ["geoms", fmt(i.memory.geometries)],
    ["textures", fmt(i.memory.textures)],
    ["programs", fmt(i.programs?.length ?? 0)],
    ["scene", `${fmt(objects)} objects, ${movers.length} cars`],
    ["canvas", `${renderer.domElement.width}×${renderer.domElement.height} @${pr}x, MSAA 4x`],
    ["shadow", `${sun.shadow.mapSize.x}² PCF${night ? " (night: bloom)" : ""}`],
    ["heap", mem ? `${(mem.usedJSHeapSize / 2 ** 20).toFixed(0)} / ${(mem.jsHeapSizeLimit / 2 ** 20).toFixed(0)} MB` : "n/a"],
    ["gpu dev", gpuName.replace(/^ANGLE \(/, "").replace(/ \(.*$/, "").replace(/^[^,]*, /, "").slice(0, 34)],
  ];
  statsText.innerHTML = rows.map(([k, v]) => `<span class="k">${k}</span>${v}`).join("\n");
}
let objects = 0;
let lastText = 0;

renderer.setAnimationLoop(() => {
  const now = performance.now();
  const dt = Math.min(0.1, (now - last) / 1000);
  frameMs[head] = now - last;
  last = now;
  if (!still) {
    for (const m of movers) {
      let v = m.obj.position[m.axis] + m.dir * m.speed * dt;
      if (v > m.max) v = m.min;
      if (v < m.min) v = m.max;
      m.obj.position[m.axis] = v;
    }
  }
  controls.update();
  setSignals(now / 1000, night ? 1 : 0);
  renderer.info.reset();
  let qy: WebGLQuery | null = null;
  if (timerExt && pending.length < 4) {
    qy = gl.createQuery()!;
    gl.beginQuery(timerExt.TIME_ELAPSED_EXT, qy);
  }
  composer.render();
  if (qy) {
    gl.endQuery(timerExt!.TIME_ELAPSED_EXT);
    pending.push(qy);
  }
  if (timerExt) pollGpu();
  cpuMs[head] = performance.now() - now;
  gpuMs[head] = lastGpu;
  head = (head + 1) % N;
  if (!statsEl.classList.contains("min")) {
    drawGraph();
    if (now - lastText > 250) {
      lastText = now;
      if (frames >= 0 && !objects) scene.traverse(() => objects++);
      updateText();
    }
  }
  if (frames >= 0 && ++frames === 5) {
    document.title = "ready";
    // Forget the loading and shader-compile frames.
    for (const a of [frameMs, cpuMs, gpuMs]) a.fill(0);
  }
});
