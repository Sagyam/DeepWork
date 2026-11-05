// The showcase town: every realistic model (blender/real) together in one
// hand-laid town, built with the app's own code (models.ts, real.ts), so
// new models can be seen in context without earning them through focus.
// A dev tool, not part of the app. Open /town.html in the dev server with
//   ?view=overview|downtown|main|homes|works|bridge|plaza|skyline|fountain|pond &hour=15
//   &still (parks the traffic) &gputimer=0 (no GPU timer queries)
//   &opt=0-8 (the optimisations below, cumulative; default all)
//   &aa=msaa|smaa|fxaa|none &scale=1 &shadowmap=8192 (trade-offs) &fps=30 (cap) &bench (see scripts/bench-town.ts)
// The bottom-left panel ("stats for nerds") shows frame, CPU and GPU times,
// draw calls, triangles and memory, for judging the cost of new models.
// A new model shows up once it is added to BLOCKS below.
//
// It is also where the realistic city's rendering optimisations are tried
// out before the app gets them (docs/models.md, "Performance"); each is
// commented where it is made. Measured on a Radeon 610M iGPU, GPU ms per
// frame at 1600 x 900 (1.5x), overview / street level: as first built
// 88 / 95; 1 res 61 / 64; 2 shadow 36 / 39; 3 idle (energy, not frame time);
// 4 cull 33 / 36; 5 trees 24 / 32; 6 sky 23 / 29; 7 merge 23 / 29 (CPU);
// 8 ibl 20 / 24 (table in docs/models.md).
import * as THREE from "three";
import { MapControls } from "three/examples/jsm/controls/MapControls.js";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { ShaderPass } from "three/examples/jsm/postprocessing/ShaderPass.js";
import { SMAAPass } from "three/examples/jsm/postprocessing/SMAAPass.js";
import { FXAAPass } from "three/examples/jsm/postprocessing/FXAAPass.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { loadKit } from "../city/kit";
import { building, furniture, KERB, mat, park, parked, Parts, SPECIES, tree } from "../city/models";
import { BLOCK_X, BLOCK_Z, LOT, PAVEMENT, PITCH_X, PITCH_Z, rng, type Spec } from "../city/plan";
import { IMPOSTOR_NEAR, Impostors, loaded } from "../city/impostor";
import { CAR_PAINTS, DEFS, fountainSpray, groundMat, hasReal, interiorUniforms, loadReal, PROPS, realMat, realPiece, realPieces, setRealEnv, setSignals, setWaterTime, waterMat } from "../city/real";

const q = new URLSearchParams(location.search);
const hour = Number(q.get("hour") ?? 15);
const night = hour < 6 || hour >= 19.5;

// Optimisations, easiest first; ?opt=N turns on the first N (default all),
// ?opt=0 is the scene as first built.
const OPTS = ["res", "shadow", "idle", "cull", "trees", "sky", "merge", "ibl"] as const;
type Opt = (typeof OPTS)[number];
const level = Math.min(OPTS.length, Number(q.get("opt") ?? OPTS.length));
const on = (o: Opt) => OPTS.indexOf(o) < level;

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
// res: one pixel per CSS pixel, and MSAA 4x with alpha to coverage, so cut-out
// leaves and railings antialias too (SMAA at 1x broke thin railings up and
// stair-stepped edges once stretched to a 1.5x screen).
// &aa=msaa (default) | smaa | fxaa | none; &scale= overrides the render scale.
const aa = on("res") ? (q.get("aa") ?? "msaa") : "msaa";
renderer.setPixelRatio(q.has("scale") ? Number(q.get("scale")) : on("res") ? 1 : Math.min(devicePixelRatio, 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
// shadow: the sun and the town stand still, so the shadow map is drawn once
// (and again only when asked) instead of every frame; moving cars cast a
// soft blob on the road instead.
renderer.shadowMap.autoUpdate = !on("shadow");
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
  fountain: [[-PITCH_X + 8, 2.6, PITCH_Z + 8.5], [-PITCH_X, 2.6, PITCH_Z], 50],
  pond: [[PITCH_X - 4, 5, -PITCH_Z + 15], [PITCH_X - 12, 0.2, -PITCH_Z + 1], 50],
};
const view = q.get("view") ?? "overview";
const [pos, at, fov] = VIEWS[view] ?? VIEWS.overview;
camera.position.fromArray(pos);
camera.fov = fov;
camera.updateProjectionMatrix();
// Map controls, as in a city builder: left drag pans along the ground,
// right drag (or ctrl / shift + left) turns, the wheel zooms, WASD pans. The
// camera stays above ground, out of buildings and inside the map, and moves
// no faster than SPEED times its distance to the target a second (see limit()).
const controls = new MapControls(camera, renderer.domElement);
controls.target.fromArray(at);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = false;
controls.maxPolarAngle = Math.PI * 0.62; // street views look up at the towers; limit() keeps the camera above ground
controls.minDistance = 4;
controls.maxDistance = 900;
controls.rotateSpeed = 0.5;
controls.zoomSpeed = 0.8;
controls.keys = { LEFT: "KeyA", UP: "KeyW", RIGHT: "KeyD", BOTTOM: "KeyS" };
controls.keyPanSpeed = 25;
controls.listenToKeyEvents(window);
controls.update();
const SPEED = 1.6;
const EYE = 1.6; // lowest eye height
const BOUND = 450; // how far from the middle the target may go
const solids: THREE.Box3[] = []; // building bodies, filled by place()
const prevCam = camera.position.clone();
const prevTarget = controls.target.clone();
const push = new THREE.Vector3();
/** Holds the camera to the rules after controls.update(); dt in seconds. */
function limit(dt: number) {
  const t = controls.target;
  t.x = THREE.MathUtils.clamp(t.x, -BOUND, BOUND);
  t.z = THREE.MathUtils.clamp(t.z, -BOUND, BOUND);
  t.y = Math.max(0, t.y);
  // Speed: target and eye each move at most SPEED x distance per second (and 30 m/s close up).
  const max = Math.max(30, SPEED * camera.position.distanceTo(t)) * dt;
  for (const [now, prev] of [[t, prevTarget], [camera.position, prevCam]] as const) {
    push.subVectors(now, prev);
    if (push.length() > max) now.copy(prev).addScaledVector(push.normalize(), max);
  }
  // Out of buildings: push the eye out through the nearest face.
  const c = camera.position;
  for (const b of solids) {
    const m = 1.2;
    if (c.x < b.min.x - m || c.x > b.max.x + m || c.z < b.min.z - m || c.z > b.max.z + m || c.y > b.max.y + m) continue;
    const opts = [c.x - (b.min.x - m), b.max.x + m - c.x, c.z - (b.min.z - m), b.max.z + m - c.z, b.max.y + m - c.y];
    const k = opts.indexOf(Math.min(...opts));
    if (k === 0) c.x = b.min.x - m;
    else if (k === 1) c.x = b.max.x + m;
    else if (k === 2) c.z = b.min.z - m;
    else if (k === 3) c.z = b.max.z + m;
    else c.y = b.max.y + m;
  }
  c.y = Math.max(EYE, c.y);
  prevCam.copy(c);
  prevTarget.copy(t);
}

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
// Night: a full moon behind the default views (so the facades they face are moonlit; turn round to see it), moonlight that casts shadows,
// a dark blue sky with stars and a glow round the moon.
const moonDir = new THREE.Vector3(-0.45, 0.5, 0.6).normalize();
function nightSky(size: number, stars = true, disc = true) {
  const m = new THREE.ShaderMaterial({
    uniforms: { uMoon: { value: moonDir } },
    side: THREE.BackSide,
    depthWrite: false,
    // Pinned to the far plane (as Sky does), so any camera sees it, the environment map's (far 100 m) included.
    vertexShader: "varying vec3 vDir;\nvoid main() { vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position.z = gl_Position.w; }",
    fragmentShader: `
      uniform vec3 uMoon;
      varying vec3 vDir;
      float hash(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
      void main() {
        vec3 d = normalize(vDir);
        float h = clamp(d.y, -0.2, 1.0);
        vec3 col = mix(vec3(0.05, 0.075, 0.13), vec3(0.008, 0.014, 0.035), smoothstep(-0.02, 0.55, h));
        float m = max(dot(d, uMoon), 0.0);
        col += vec3(0.16, 0.2, 0.3) * pow(m, 40.0) + vec3(0.03, 0.04, 0.07) * pow(m, 5.0);
        ${disc ? "col += vec3(5.0, 4.8, 4.3) * smoothstep(0.99993, 0.99996, m);" : ""}
        ${stars ? "float s = hash(floor(d * 700.0)); col += vec3(1.0, 0.97, 0.9) * step(0.9986, s) * (0.6 + 0.8 * fract(s * 91.0)) * smoothstep(0.02, 0.25, h) * (1.0 - smoothstep(0.995, 0.9999, m));" : ""}
        gl_FragColor = vec4(col, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 24), m);
  mesh.scale.setScalar(size);
  return mesh;
}
const sky = new Sky();
sky.scale.setScalar(5000);
const skyMesh: THREE.Mesh = night ? nightSky(5000) : sky;
const su = sky.material.uniforms;
su.turbidity.value = 4;
su.rayleigh.value = night ? 0.3 : 1.4;
su.mieCoefficient.value = 0.004;
su.mieDirectionalG.value = 0.82;
su.sunPosition.value.copy(sunDir);
// sky: the scattering sky is a full-screen shader; while the sun stands
// still it is drawn once into a cube map that the background samples (to be
// redrawn when the sun moves on).
if (on("sky")) {
  const skyScene = new THREE.Scene();
  skyScene.add(skyMesh);
  const cubeRT = new THREE.WebGLCubeRenderTarget(night ? 1024 : 512, { type: THREE.HalfFloatType });
  new THREE.CubeCamera(1, 6000, cubeRT).update(renderer, skyScene);
  scene.background = cubeRT.texture;
} else scene.add(skyMesh);

const pmrem = new THREE.PMREMGenerator(renderer);
const envScene = new THREE.Scene();
const envSky = new Sky();
envSky.scale.setScalar(1000);
Object.assign(envSky.material.uniforms, THREE.UniformsUtils.clone(sky.material.uniforms));
envSky.material.uniforms.sunPosition.value.copy(sunDir);
envSky.material.uniforms.mieDirectionalG.value = 0.6;
envSky.material.uniforms.showSunDisc.value = 0;
// (Without the disc: glass would mirror it into a bloom blob.)
envScene.add(night ? nightSky(1000, false, false) : envSky);
const envGround = new THREE.Mesh(new THREE.CircleGeometry(900, 32).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: night ? 0x050608 : 0x3a3c3e }));
envGround.position.y = -2;
envScene.add(envGround);
const env = pmrem.fromScene(envScene, 0.02).texture;
scene.environment = env;
scene.environmentIntensity = night ? 0.08 : 0.12;
setRealEnv(env);

const sun = new THREE.DirectionalLight(night ? 0xa4bbe8 : 0xfff1dc, night ? 0.7 : 5);
const reach = 200;
sun.position.copy(night ? moonDir : sunDir).multiplyScalar(500);
sun.target.position.set(20, 0, 0);
sun.position.add(sun.target.position);
scene.add(sun.target);
sun.castShadow = true;
sun.shadow.mapSize.setScalar(Number(q.get("shadowmap") ?? 8192));
const sc = sun.shadow.camera;
sc.left = sc.bottom = -reach;
sc.right = sc.top = reach;
sc.near = 1;
sc.far = 1200;
sun.shadow.bias = -0.0002;
sun.shadow.normalBias = 0.05;
scene.add(sun);
const hemi = new THREE.HemisphereLight(night ? 0x3a4c70 : 0xc8dcff, night ? 0x15171c : 0x5a5248, night ? 0.3 : 0.35);
scene.add(hemi);
scene.fog = new THREE.Fog(night ? 0x0c1424 : 0xc4d2e0, 400, 3000);
renderer.toneMappingExposure = night ? 1.05 : 0.75;
interiorUniforms.uDay.value = night ? 0 : 1;
interiorUniforms.uNight.value = night ? 1 : 0;

// Everything by category, for the bench (cost per category) and culling.
const cats = { buildings: new THREE.Group(), streets: new THREE.Group(), woods: new THREE.Group(), ground: new THREE.Group(), traffic: new THREE.Group() };
for (const g of Object.values(cats)) scene.add(g);

// cull: scenery is merged per tile (a block's street, a 64 m patch of
// woods) instead of once for the whole town, so tiles out of view are
// skipped, and small props drop out with distance: tiny ones (hydrants,
// bins, benches, signals) past 140 m, lamps and parked cars past 320 m.
type Chunk = { parts: Parts; centre: THREE.Vector3; far: number; group?: THREE.Group; cat: keyof typeof cats };
const chunks = new Map<string, Chunk>();
function chunk(cat: keyof typeof cats, key: string, x: number, z: number, far = Infinity): Parts {
  const k = on("cull") ? `${cat}:${key}` : cat;
  let c = chunks.get(k);
  if (!c) chunks.set(k, (c = { parts: new Parts(), centre: new THREE.Vector3(x, 0, z), far: on("cull") ? far : Infinity, cat }));
  return c.parts;
}
const TINY = 140;
const SMALL = 320;
type StreetParts = { surf: Parts; trees: Trees; props: Parts; tiny: Parts; pools: Parts };

/** The warm pool of light a street lamp throws on the road at night: an additive decal, not a real light (which would cost every pixel). */
let poolMatC: THREE.MeshBasicMaterial | null = null;
const poolGeo = new THREE.PlaneGeometry(13, 13);
function poolMat() {
  if (poolMatC) return poolMatC;
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const x = c.getContext("2d")!;
  const g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.35, "rgba(255,255,255,0.55)");
  g.addColorStop(0.7, "rgba(255,255,255,0.15)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = g;
  x.fillRect(0, 0, 128, 128);
  poolMatC = new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), color: 0xffb870, transparent: true, opacity: 0.32, blending: THREE.AdditiveBlending, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4 });
  poolMatC.userData.noShadow = true;
  return poolMatC;
}

// trees: past IMPOSTOR_NEAR a tile's trees are drawn as impostors, three
// crossed cards (front, side and top) carrying a picture of that species
// and tint rendered once at load (city/impostor.ts, which the app shares).
// The real trees still draw the (static) shadow map, and come back up close.
type Trees = { real: Parts; imp: Parts | null; key: string };
const treeTiles = new Map<string, Trees & { centre: THREE.Vector3; realGroup?: THREE.Group; impGroup?: THREE.Group; cat: keyof typeof cats }>();
function trees(cat: keyof typeof cats, key: string, x: number, z: number): Trees {
  const k = `${cat}:${key}:trees`;
  let t = treeTiles.get(k);
  if (!t) treeTiles.set(k, (t = { real: on("cull") ? new Parts() : chunk(cat, `${key}:trees`, x, z), imp: on("trees") ? new Parts() : null, key: k, centre: new THREE.Vector3(x, 0, z), cat }));
  return t;
}
const imps = new Impostors(renderer);
/** Cut-out textures the shadow map waits for. */
const shadowTextures = new Set<THREE.Texture>();

/** A tree as tree() places it, plus its impostor. */
function treeAt(t: Trees, x: number, z: number, s: number, seed: number, y = 0) {
  tree(t.real, x, z, s, seed, y);
  if (t.imp) imps.tree(t.imp, x, z, s, seed, y, SPECIES);
}

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
  const g = building(s).group;
  cats.buildings.add(g);
  solids.push(new THREE.Box3(new THREE.Vector3(s.x - def.w / 2, 0, s.z - def.d / 2), new THREE.Vector3(s.x + def.w / 2, s.height + KERB, s.z + def.d / 2)));
  return g;
}

// merge: a building is a mesh per material (30-45 of them), so 56
// buildings were ~2,100 draws, each with its state change. Buildings of the
// same model share materials, so a block's buildings merge into one mesh per
// material: a draw per material per block.
function mergeBlock(groups: THREE.Group[]) {
  const byMat = new Map<THREE.Material, THREE.BufferGeometry[]>();
  for (const g of groups) {
    g.updateMatrixWorld(true);
    g.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const list = byMat.get(m.material as THREE.Material) ?? [];
      list.push(m.geometry.clone().applyMatrix4(m.matrixWorld));
      byMat.set(m.material as THREE.Material, list);
    });
    g.removeFromParent();
  }
  const out = new THREE.Group();
  for (const [material, list] of byMat) {
    const merged = mergeGeometries(list);
    for (const geo of merged ? [merged] : list) {
      const mesh = new THREE.Mesh(geo, material);
      mesh.castShadow = !material.userData.noShadow;
      mesh.receiveShadow = true;
      out.add(mesh);
    }
    if (merged) for (const geo of list) geo.dispose();
  }
  cats.buildings.add(out);
}

function streets(P: StreetParts, b: { x: number; z: number }, r: () => number) {
  const parts = P.surf;
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
    for (const t of [-1, -1 / 3, 1 / 3, 1]) {
      furniture(P.props, "lamp_led", b.x + t * (BLOCK_X / 2 - 1), KERB, b.z + lz * ez, lz > 0 ? 0 : Math.PI);
      if (night) P.pools.add(poolMat(), poolGeo, b.x + t * (BLOCK_X / 2 - 1), KERB + 0.02, b.z + lz * (ez + 1.6), -Math.PI / 2);
    }
    for (const t of [-5 / 6, -1 / 2, -1 / 6, 1 / 6, 1 / 2, 5 / 6]) treeAt(P.trees, b.x + t * (BLOCK_X / 2 - 1), b.z + lz * ez, 0.5, Math.floor(b.x * 31 + b.z * 17 + t * 12 + lz * 5), KERB);
    // Parked cars along the kerb, between the trees.
    for (const t of [-2 / 3, 0, 2 / 3]) {
      if (r() < 0.3) continue;
      const x = b.x + t * (BLOCK_X / 2 - 1) + (r() - 0.5) * 3;
      parked(P.props, x, b.z + lz * (BLOCK_Z / 2 + pw + 1.1), lz > 0 ? -Math.PI / 2 : Math.PI / 2, Math.floor(r() * 1e6), 0.06);
    }
  }
  for (const sx of [-1, 1]) treeAt(P.trees, b.x + sx * ex, b.z, 0.5, Math.floor(b.x * 13 + b.z * 7 + sx), KERB);
  // Street furniture: signals, hydrant, bins, bench, bus stop.
  const cx = BLOCK_X / 2 + pw - 0.55;
  const cz = BLOCK_Z / 2 + pw - 0.55;
  furniture(P.tiny, "signal_mast", b.x + cx, KERB, b.z + cz, Math.PI / 2, undefined, "a");
  furniture(P.tiny, "signal_mast", b.x - cx, KERB, b.z - cz, -Math.PI / 2, undefined, "a");
  furniture(P.tiny, "signal_post", b.x - cx, KERB, b.z + cz, 0, undefined, "b");
  furniture(P.tiny, "signal_post", b.x + cx, KERB, b.z - cz, Math.PI, undefined, "b");
  const kb = BLOCK_Z / 2 + pw - 0.4;
  furniture(P.tiny, "hydrant", b.x, KERB, b.z + kb, 0);
  for (const sx of [-1, 1]) furniture(P.tiny, "bin", b.x + sx * (BLOCK_X / 2 - 3.2), KERB, b.z - sx * kb, sx > 0 ? 0 : Math.PI);
  furniture(P.tiny, "bench", b.x - 20.7, KERB, b.z + BLOCK_Z / 2 + pw - 1.3, 0);
  furniture(P.tiny, "busstop", b.x + 20.7, KERB, b.z - (BLOCK_Z / 2 + pw - 1.0), Math.PI);
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
    const cx = Math.floor(x / 64) * 64 + 32;
    const cz = Math.floor(z / 64) * 64 + 32;
    treeAt(trees("woods", `${cx},${cz}`, cx, cz), x, z, 0.8 + r() * 0.5, Math.floor(r() * 1e6), 0);
  }
}

// The river: the shared moving water (real.ts waterMat), at its waviest.
const waterMat_ = waterMat({ amp: 2.4 });
const water = new THREE.Mesh(new THREE.PlaneGeometry(RIVER * 2, 2800).rotateX(-Math.PI / 2), waterMat_);
water.position.set(RX, -1.6, 0);
water.receiveShadow = true;
cats.ground.add(water);

// ---- traffic: cars driving round the grid (through the junctions, it's a showcase) ----

/** A soft dark ellipse under a moving car, standing in for its shadow. */
const blobGeo = new THREE.PlaneGeometry(2.3, 5.2).rotateX(-Math.PI / 2).translate(0, 0.02, 0);
let blob: THREE.MeshBasicMaterial | null = null;
function blobMat() {
  if (blob) return blob;
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const x = c.getContext("2d")!;
  const g = x.createRadialGradient(32, 32, 4, 32, 32, 32);
  g.addColorStop(0, "rgba(0,0,0,0.75)");
  g.addColorStop(0.6, "rgba(0,0,0,0.45)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  x.fillStyle = g;
  x.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c);
  blob = new THREE.MeshBasicMaterial({ map: t, transparent: true, depthWrite: false, opacity: night ? 0.35 : 0.8 });
  return blob;
}

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
          m.castShadow = !on("shadow");
          m.receiveShadow = true;
          g.add(m);
        }
        if (on("shadow")) g.add(new THREE.Mesh(blobGeo, blobMat()));
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
        cats.traffic.add(g);
        movers.push({ obj: g, axis: l.axis, dir, speed: 8 + r() * 4, min: l.min, max: l.max });
      }
    }
  }
}

// ---- go ----

Promise.all([loadKit(), loadReal([...Object.keys(DEFS), ...PROPS])]).then(async () => {
  const missing = [...Object.keys(DEFS), ...PROPS].filter((id) => !hasReal(id));
  if (missing.length) console.warn("not built:", missing);
  const ground = new Parts();
  land(ground);
  const r = rng(3);
  const pole = mat(0x3c4046, { metalness: 0.6, roughness: 0.4 });
  const bulb = mat(0xfff0d0, { emissive: 0xffd9a0, emissiveIntensity: 0, night: 2.2 });
  for (const b of BLOCKS) {
    const x = b.bx * PITCH_X;
    const z = b.bz * PITCH_Z;
    const key = `${x},${z}`;
    const P = { surf: chunk("streets", key, x, z), trees: trees("streets", key, x, z), props: chunk("streets", `${key}:props`, x, z, SMALL), tiny: chunk("streets", `${key}:tiny`, x, z, TINY), pools: chunk("streets", `${key}:pools`, x, z) };
    streets(P, { x, z }, r);
    if (b.park) {
      park(P.props, { x, z, kind: b.park, seed: 5 + b.bx * 3 + b.bz }, pole, bulb);
      // The plaza's fountain plays (park() draws it at 1.45x on the kerb).
      if (b.park === "plaza") {
        const spray = fountainSpray(x, KERB, z, 1.45);
        if (night) (spray.material as THREE.ShaderMaterial).uniforms.uBright.value = 0.22;
        cats.streets.add(spray);
      }
      continue;
    }
    const groups: THREE.Group[] = [];
    for (const [row, list] of [[1, b.south], [-1, b.north]] as const) {
      list!.forEach((code, i) => {
        const g = place(code, x + (i - 1.5) * LOT, z + row * (LOT / 2), row > 0 ? 0 : Math.PI, 7 + Math.floor(r() * 400));
        if (g) groups.push(g);
      });
    }
    if (on("merge")) mergeBlock(groups);
  }
  for (const c of chunks.values()) {
    c.group = new THREE.Group();
    c.parts.into(c.group);
    cats[c.cat].add(c.group);
  }
  ground.into(cats.ground);
  for (const t of treeTiles.values()) {
    if (!on("cull")) continue; // merged with the rest of their category (chunk())
    t.realGroup = new THREE.Group();
    t.real.into(t.realGroup);
    cats[t.cat].add(t.realGroup);
    if (t.imp) {
      t.impGroup = new THREE.Group();
      t.imp.into(t.impGroup, false);
      cats[t.cat].add(t.impGroup);
    }
  }
  traffic();
  renderer.shadowMap.needsUpdate = true;
  // The leaf cards cut their shapes out of their textures, which are still
  // loading now: drawn once from this first frame, a tree's shadow would be
  // its bare branches. Draw it again when every cut-out texture has arrived.
  scene.traverse((o) => {
    const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
    if ((o as THREE.Mesh).castShadow && m?.alphaTest && m.map) shadowTextures.add(m.map);
  });
  // With MSAA, cut-out leaves, railings and grilles antialias their edges too (alpha to coverage).
  if (on("res") && aa === "msaa")
    scene.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.Material | undefined;
      if (m && m.alphaTest > 0 && !m.alphaToCoverage) {
        m.alphaToCoverage = true;
        m.needsUpdate = true;
      }
    });
  // ibl: image-based light (the sky's prefiltered environment) costs every
  // pixel several texture reads, yet on rough brick, render and roofs at an
  // intensity of 0.12 it is a faint fill. Only glossy and metal surfaces
  // (glass, steel and car paint already carry it) keep it; the hemisphere
  // light, a little brighter, fills the rest for nearly nothing.
  if (on("ibl")) {
    scene.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
      if (!m?.isMeshStandardMaterial || m.envMap) return;
      if (m.metalness >= 0.3 || m.roughness <= 0.45) {
        m.envMap = env;
        m.envMapIntensity = scene.environmentIntensity;
        m.needsUpdate = true;
      }
    });
    scene.environment = null;
    hemi.intensity *= night ? 3 : 5;
  }
  // Water by night: darker, the (dim) night sky stronger in it.
  if (night)
    scene.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
      if (m?.userData?.water && !m.userData.nightDone) {
        m.color.multiplyScalar(0.55);
        m.envMapIntensity = 1;
        m.userData.nightDone = true;
      }
    });
  // Everything that lights at night (windows, lamps, signals, neon, headlights).
  scene.traverse((o) => {
    const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
    if (m?.userData?.night) m.emissiveIntensity = night ? m.userData.night : 0;
  });
  await prewarm();
  frames = 0;
});

/**
 * Compiles every shader and uploads every texture now, with everything
 * shown, instead of the first time it comes into view: a shader compiled
 * mid-pan is a hitch of tens to hundreds of milliseconds, the 1% lows.
 */
async function prewarm() {
  const hidden: THREE.Object3D[] = [];
  scene.traverse((o) => {
    if (!o.visible) {
      hidden.push(o);
      o.visible = true;
    }
  });
  const seen = new Set<THREE.Texture>();
  scene.traverse((o) => {
    const m = (o as THREE.Mesh).material as unknown as Record<string, unknown> | undefined;
    if (!m) return;
    for (const v of Object.values(m)) if (v instanceof THREE.Texture && !seen.has(v) && v.image) seen.add(v);
  });
  for (const t of seen) renderer.initTexture(t);
  await renderer.compileAsync(scene, camera);
  for (const o of hidden) o.visible = false;
}

// ---- render ----

const target_ = new THREE.WebGLRenderTarget(innerWidth * renderer.getPixelRatio(), innerHeight * renderer.getPixelRatio(), { samples: aa === "msaa" ? 4 : 0, type: THREE.HalfFloatType });
const composer = new EffectComposer(renderer, target_);
composer.addPass(new RenderPass(scene, camera));
// Firefly clamp: near-mirror glass catching the moon (or sun) exactly makes
// one pixel hundreds of times brighter than anything else, which bloom
// smears into a disc. Capping brightness before the bloom keeps glints small.
const clamp = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, uMax: { value: 8 } },
  vertexShader: "varying vec2 vUv;\nvoid main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
  fragmentShader: "uniform sampler2D tDiffuse;\nuniform float uMax;\nvarying vec2 vUv;\nvoid main() { vec4 c = texture2D(tDiffuse, vUv); gl_FragColor = vec4(min(c.rgb, vec3(uMax)), c.a); }",
});
clamp.enabled = night;
composer.addPass(clamp);
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth / 2, innerHeight / 2), 0.55, 0.5, 0.95);
bloom.enabled = night;
composer.addPass(bloom);
composer.addPass(new OutputPass());
const smaa = aa === "smaa" ? new SMAAPass() : aa === "fxaa" ? new FXAAPass() : null;
if (smaa) composer.addPass(smaa);
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
});

let frames = -1;
let last = performance.now();
const still = q.has("still") || q.has("bench");
const bench = q.has("bench");
(window as unknown as { town: object }).town = { scene, renderer, cats, camera, imps, treeTiles: () => treeTiles, solids: () => solids };

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
    ["gpu busy", timerExt ? `${(busy * 100).toFixed(0)}%  (${fpsCap ? `${fpsCap} fps cap` : "uncapped"}${idle ? ", idle when still" : ""})` : "n/a"],
    ["opt", `${level}/${OPTS.length}  ${OPTS.slice(0, level).join(" ") || "none"}`],
    ["draws", fmt(i.render.calls)],
    ["tris", fmt(i.render.triangles)],
    ["geoms", fmt(i.memory.geometries)],
    ["textures", fmt(i.memory.textures)],
    ["programs", fmt(i.programs?.length ?? 0)],
    ["scene", `${fmt(objects)} objects, ${movers.length} cars`],
    ["canvas", `${renderer.domElement.width}×${renderer.domElement.height} @${pr}x, ${aa === "msaa" ? "MSAA 4x" : aa.toUpperCase()}`],
    ["shadow", `${sun.shadow.mapSize.x}² PCF, ${renderer.shadowMap.autoUpdate ? "every frame" : "drawn once"}`],
    ["heap", mem ? `${(mem.usedJSHeapSize / 2 ** 20).toFixed(0)} / ${(mem.jsHeapSizeLimit / 2 ** 20).toFixed(0)} MB` : "n/a"],
    ["gpu dev", gpuName.replace(/^ANGLE \(/, "").replace(/ \(.*$/, "").replace(/^[^,]*, /, "").slice(0, 34)],
  ];
  statsText.innerHTML = rows.map(([k, v]) => `<span class="k">${k}</span>${v}`).join("\n");
}
let objects = 0;
let lastText = 0;

// cap: draw at most 30 frames a second, and none at all while nothing moves
// (traffic parked with &still, camera at rest): a focus timer's city sits
// on screen for hours, and an idle frame costs as much as a busy one.
let dirty = true;
controls.addEventListener("change", () => (dirty = true));
addEventListener("resize", () => (dirty = true));
// idle: no frames while nothing moves (&still, camera at rest). &fps=30 caps the rate (off by default).
const idle = on("idle") && !bench;
const fpsCap = Number(q.get("fps") ?? 0);
let lastTick = performance.now();
let rendered = 0;
let busyMs = 0;
let busy = 0;
let lastBusy = performance.now();

renderer.setAnimationLoop(() => {
  const now = performance.now();
  const moving = !still && movers.length > 0;
  controls.update();
  limit(Math.min(0.1, (now - lastTick) / 1000));
  lastTick = now;
  if (fpsCap && now - last < 1000 / fpsCap - 2) return;
  if (idle && !(dirty || moving || frames < 10)) return;
  dirty = false;
  // (Everything stays in while the shadow map is drawn, so props that pop in keep their shadows.)
  if (imps.pending) imps.draw();
  if (shadowTextures.size && [...shadowTextures].every(loaded)) {
    shadowTextures.clear();
    renderer.shadowMap.needsUpdate = true;
  }
  const shadowing = renderer.shadowMap.needsUpdate;
  if (on("cull")) for (const c of chunks.values()) if (c.group && c.far < Infinity) c.group.visible = shadowing || camera.position.distanceTo(c.centre) < c.far;
  if (on("trees"))
    for (const t of treeTiles.values()) {
      const near = shadowing || camera.position.distanceTo(t.centre) < IMPOSTOR_NEAR;
      if (t.realGroup) t.realGroup.visible = near;
      if (t.impGroup) t.impGroup.visible = !near;
    }
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
  setSignals(now / 1000, night ? 1 : 0);
  setWaterTime(bench ? 0 : now / 1000);
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
  rendered++;
  busyMs += lastGpu;
  if (!statsEl.classList.contains("min")) {
    drawGraph();
    if (now - lastText > 250) {
      lastText = now;
      busy = busyMs / (now - lastBusy);
      busyMs = 0;
      lastBusy = now;
      if (frames >= 0 && !objects) scene.traverse(() => objects++);
      updateText();
    }
  }
  if (frames >= 0 && ++frames === 5) {
    document.title = "ready";
    // Forget the loading and shader-compile frames.
    for (const a of [frameMs, cpuMs, gpuMs]) a.fill(0);
  }
  // Bench: once the history has filled with settled frames, publish its stats.
  if (bench && frames === 5 + N + 20) {
    const i = renderer.info;
    (window as unknown as { bench: object }).bench = { frame: stat(frameMs), cpu: stat(cpuMs), gpu: stat(gpuMs), draws: i.render.calls, tris: i.render.triangles, geoms: i.memory.geometries, textures: i.memory.textures, canvas: [renderer.domElement.width, renderer.domElement.height], spikes: [...cpuMs].map((v, k) => [(k - head + N) % N, +v.toFixed(1)]).filter(([, v]) => v > 2 * stat(cpuMs).avg).sort((x, y) => x[0] - y[0]) };
  }
});
