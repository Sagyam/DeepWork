// Viewer for the realistic models (blender/real, `bun run models`): one
// building on its lot, built by the app's own code (models.ts), on a street
// corner. Open /proto.html in the dev server with
//   ?model=a1|a2|a3|c1|c2|c3|c4|s1|s2|s3|s4|o1|l1|p1|f1|e1|h1|l5|e2|e3|h2|p2|w2 &floors=7 &seed=3 &damage=0|1|2|3 (3: the ruin)
//   &view=hero|city|detail|roof|back|street &hour=15
// &count=N is a stress test: N buildings on a grid, drawn instanced (or one
// mesh each with &draw=separate).
// ?props=cars shows a props model's pieces side by side instead
// (&only=hatch,suv picks and orders them, &gap=3.4 the spacing, &ry the turn).
// &cam=x,y,z&at=x,y,z&fov=45 places the camera anywhere; &signal=s fixes the
// traffic signals' cycle at s seconds.
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { loadKit } from "../city/kit";
import { building, fitReal, furniture, KERB, Parts, rubble } from "../city/models";
import { LOT, PAVEMENT, type Spec } from "../city/plan";
import { DEFS, hasReal, interiorUniforms, loadReal, PROPS, realAo, realMat, realPiece, realPieces, setRealEnv, setSignals } from "../city/real";

const q = new URLSearchParams(location.search);
const hour = Number(q.get("hour") ?? 15);
const view = q.get("view") ?? "hero";
const props = q.get("props");
const id = props ?? q.get("model") ?? "a1";
const count = Number(q.get("count") ?? 1);
const stress = count > 1;
const SPACING = LOT + 8;
const across = Math.ceil(Math.sqrt(count));
const extent = across * SPACING;

const el = document.getElementById("view")!;
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(stress ? 1 : Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
el.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.5, 4000);
const H = DEFS[id] ? DEFS[id].height(DEFS[id].floors(Number(q.get("floors") ?? 7))) : props ? 6 : 27; // to frame the views
const k = H / 27;
const VIEWS: Record<string, [number[], number[], number?]> = {
  hero: [[25 * Math.max(k, 0.55), 4 * k + 1.2, 30 * Math.max(k, 0.55)], [0, H / 2, 0], 50],
  city: [[52, 44, 62], [0, 9 * k, 0], 38],
  detail: [[10.5 * k + 2, 17.5 * k + 0.6, 13.5 * k + 4], [1.5 * k, 14.5 * k, 5.5 * k + 1], 40],
  roof: [[17 * k + 6, 33 * k + 4, 19 * k + 6], [0, H - 3 * k, 0], 42],
  back: [[-22 * Math.max(k, 0.55), 6 * k + 1, -21 * Math.max(k, 0.55)], [0, H / 2, 0], 46],
  street: [[-6, 1.7, 12], [2, 3.5 * k + 1, 6], 55],
};
if (props) {
  VIEWS.hero = [[4, 5.5, 16], [0, 1.0, 0], 50];
  VIEWS.close = [[3.5, 2.2, 7.5], [0, 0.9, 0], 45];
  VIEWS.low = [[-6, 1.4, 9], [0, 1.2, 0], 55];
  VIEWS.far = [[6, 7, 38], [0, 4.5, 0], 50];
}
if (stress) VIEWS.city = [[extent * 0.75 + 40, extent * 0.6 + 35, extent * 0.9 + 50], [0, 6, 0], 40];
if (q.has("cam")) VIEWS.custom = [q.get("cam")!.split(",").map(Number), (q.get("at") ?? "0,1,0").split(",").map(Number), Number(q.get("fov") ?? 45)];
const [pos, target, fov] = VIEWS[q.has("cam") ? "custom" : view] ?? VIEWS.hero;
camera.position.fromArray(pos);
camera.fov = fov ?? 42;
camera.updateProjectionMatrix();
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.fromArray(target);
controls.update();

// ---- sky, sun and the environment the glass reflects ----

const night = hour < 6 || hour >= 19.5;
const elev = night ? 0.5 : Math.max(4, 50 * Math.sin(((hour - 6) / 13.5) * Math.PI));
const az = THREE.MathUtils.degToRad(Number(q.get("az") ?? (night ? 210 : -95 + (hour - 9) * 12)));
const sunDir = new THREE.Vector3().setFromSphericalCoords(1, THREE.MathUtils.degToRad(90 - (night ? -12 : elev)), az);

const sky = new Sky();
sky.scale.setScalar(3000);
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
scene.environmentIntensity = Number(q.get("env") ?? (night ? 0.08 : 0.12));
setRealEnv(env);

const sun = new THREE.DirectionalLight(night ? 0x8fa8d8 : 0xfff1dc, night ? 0.25 : Number(q.get("sun") ?? 5));
// The shadow box reaches the top of a tall tower and the shadow it throws.
const reach = Math.max(32, extent * 0.75, H * 0.8);
sun.position.copy(night ? new THREE.Vector3(-0.4, 0.8, 0.5) : sunDir).multiplyScalar(Math.max(80, extent, H * 1.6));
sun.castShadow = true;
sun.shadow.mapSize.setScalar(stress ? 2048 : 4096);
const sc = sun.shadow.camera;
sc.left = sc.bottom = -reach;
sc.right = sc.top = reach;
sc.far = Math.max(200, extent * 2, H * 3.2);
sc.near = 1;
sun.shadow.bias = -0.0002;
sun.shadow.normalBias = 0.03;
scene.add(sun);
scene.add(new THREE.HemisphereLight(night ? 0x223044 : 0xc8dcff, night ? 0x101010 : 0x5a5248, night ? 0.15 : 0.35));
scene.fog = new THREE.Fog(night ? 0x0a0e18 : 0xc4d2e0, 300, 2500);
renderer.toneMappingExposure = night ? 0.9 : 0.75;
interiorUniforms.uDay.value = night ? 0 : 1;
interiorUniforms.uNight.value = night ? 1 : 0;

// ---- the street corner ----

const texLoader = new THREE.TextureLoader();
function ground(name: string, tile: number, color = true) {
  const t = texLoader.load(`${import.meta.env.BASE_URL}models/tex/${name}.png`);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(1 / tile, 1 / tile);
  t.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  return t;
}

/** Plan UVs in metres, for tiling textures. */
function metres(g: THREE.BufferGeometry) {
  const uv = g.getAttribute("uv") as THREE.BufferAttribute;
  const p = g.getAttribute("position") as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, p.getX(i), p.getZ(i));
  return g;
}

function street(cz: number) {
  const g = new THREE.Group();
  const asphalt = new THREE.Mesh(metres(new THREE.PlaneGeometry(400, 400).rotateX(-Math.PI / 2)), new THREE.MeshStandardMaterial({ map: ground("asphalt_col", 6), normalMap: ground("asphalt_nrm", 6, false), roughness: 0.9 }));
  asphalt.receiveShadow = true;
  g.add(asphalt);
  // Pavement round the lot, at kerb height.
  const pw = LOT + 2 * PAVEMENT;
  const pave = new THREE.Mesh(metres(new THREE.BoxGeometry(pw, KERB - 0.01, pw)), new THREE.MeshStandardMaterial({ map: ground("pave_col", 3.6), normalMap: ground("pave_nrm", 3.6, false), roughness: 0.88 }));
  pave.position.set(0, (KERB - 0.01) / 2, cz);
  pave.receiveShadow = true;
  g.add(pave);
  const paint = new THREE.MeshStandardMaterial({ color: 0xe8e6de, roughness: 0.7 });
  for (let i = -20; i <= 20; i++) {
    for (const [x, z, rot] of [[i * 6, cz + pw / 2 + 5, 0], [i * 6, cz - pw / 2 - 5, 0], [pw / 2 + 5, cz + i * 6, 1], [-pw / 2 - 5, cz + i * 6, 1]]) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(rot ? 0.15 : 3, rot ? 3 : 0.15).rotateX(-Math.PI / 2), paint);
      m.position.set(x, 0.005, z);
      m.receiveShadow = true;
      g.add(m);
    }
  }
  const pole = new THREE.MeshStandardMaterial({ color: 0x232527, roughness: 0.5, metalness: 0.5 });
  const bulb = new THREE.MeshStandardMaterial({ color: 0xfff2d8, emissive: 0xffd9a0, emissiveIntensity: night ? 6 : 0.2 });
  if (hasReal("street")) {
    // The realistic street furniture: lamps reaching over the road, signals
    // at the near corner, a hydrant and a bin.
    const parts = new Parts();
    const e = pw / 2 - 0.55;
    furniture(parts, "lamp_led", -pw / 2 + 0.6, KERB, cz + e, 0);
    furniture(parts, "lamp_led", pw / 2 - 0.6, KERB, cz - e, Math.PI);
    furniture(parts, "signal_mast", e, KERB, cz + e, Math.PI / 2, undefined, "a");
    furniture(parts, "signal_post", -e, KERB, cz - e, Math.PI, undefined, "b");
    furniture(parts, "hydrant", 3, KERB, cz + pw / 2 - 0.4);
    furniture(parts, "bin", pw / 2 - 0.4, KERB, cz + 4);
    parts.into(g);
    g.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
      if (m?.userData?.night) m.emissiveIntensity = night ? m.userData.night : 0;
    });
    return g;
  }
  for (const [x, z] of [[pw / 2 - 0.6, cz + pw / 2 - 0.6], [-pw / 2 + 0.6, cz + pw / 2 - 0.6], [pw / 2 - 0.6, cz - pw / 2 + 0.6]]) {
    const s = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.11, 5.5, 12), pole);
    s.position.set(x, 2.75 + KERB, z);
    s.castShadow = true;
    g.add(s);
    const head = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.32, 0.45, 12), bulb);
    head.position.set(x, 5.6 + KERB, z);
    g.add(head);
    if (night) {
      const l = new THREE.PointLight(0xffc98a, 18, 16, 1.6);
      l.position.set(x, 5.2 + KERB, z);
      g.add(l);
    }
  }
  return g;
}

function grid(model: THREE.Object3D) {
  const meshes: THREE.Mesh[] = [];
  model.traverse((o) => (o as THREE.Mesh).isMesh && meshes.push(o as THREE.Mesh));
  const m = new THREE.Matrix4();
  const at = (i: number) => {
    const x = ((i % across) - (across - 1) / 2) * SPACING;
    const z = (Math.floor(i / across) - (across - 1) / 2) * SPACING;
    return m.makeRotationY((i % 4) * (Math.PI / 2)).setPosition(x, 0, z);
  };
  if (q.get("draw") === "separate") {
    for (let i = 0; i < count; i++) {
      const c = model.clone();
      c.applyMatrix4(at(i));
      scene.add(c);
    }
  } else {
    for (const mesh of meshes) {
      const inst = new THREE.InstancedMesh(mesh.geometry, mesh.material, count);
      for (let i = 0; i < count; i++) inst.setMatrixAt(i, at(i));
      inst.castShadow = mesh.castShadow;
      inst.receiveShadow = true;
      inst.frustumCulled = false;
      scene.add(inst);
    }
  }
}

/** A props model's pieces in a row along x on an open street, each in its own paint. */
function lineup() {
  const only = q.get("only")?.split(",") ?? realPieces(id);
  const gap = Number(q.get("gap") ?? 3.4);
  const ry = Number(q.get("ry") ?? -0.45);
  const g = new THREE.Group();
  const asphalt = new THREE.Mesh(metres(new THREE.PlaneGeometry(400, 400).rotateX(-Math.PI / 2)), new THREE.MeshStandardMaterial({ map: ground("asphalt_col", 6), normalMap: ground("asphalt_nrm", 6, false), roughness: 0.9 }));
  asphalt.receiveShadow = true;
  g.add(asphalt);
  only.forEach((name, i) => {
    const x = (i - (only.length - 1) / 2) * gap;
    const paint = { wall: i * 5 + Number(q.get("seed") ?? 0), accent: i, roof: i, signs: i };
    for (const { role, geo } of realPiece(id, name)) {
      const debugAo = q.get("debug") === "ao";
      const m = new THREE.Mesh(geo, debugAo ? new THREE.MeshBasicMaterial({ aoMap: realAo(id)!, color: 0xffffff }) : realMat(id, role, paint, 0, night ? "traffic" : ""));
      const mm = m.material as THREE.MeshStandardMaterial;
      if (night && mm.userData.night) mm.emissiveIntensity = mm.userData.night;
      m.position.set(x, 0.01, 0);
      m.rotation.y = ry;
      m.castShadow = q.get("shadow") !== "0" && !(m.material as THREE.Material).userData.noShadow;
      m.receiveShadow = true;
      g.add(m);
    }
  });
  scene.add(g);
}

Promise.all([loadKit(), loadReal([id, ...PROPS], renderer)]).then(() => {
  if (props) {
    lineup();
    frames = 0;
    return;
  }
  if (!DEFS[id]) throw new Error(`no model ${id}`);
  const { kind, style } = DEFS[id];
  const floors = Number(q.get("floors") ?? 7);
  const seed = Number(q.get("seed") ?? 3);
  const raw: Spec = { index: 0, kind, style, grade: kind === "landmark" ? 4 : kind === "apartment" ? 2 : kind === "shop" ? 1 : 0, x: 0, z: 0, rot: 0, yard: 0, w: 10, d: 10, floors, floorH: 3, height: 20, wall: seed, accent: seed + 2, seed, damage: Math.min(2, Number(q.get("damage") ?? 0)), rubble: Number(q.get("damage") ?? 0) >= 3, model: id };
  const s = { ...fitReal(raw), x: 0, z: 0, rot: 0 };
  const { group, info } = s.rubble ? rubble(s) : building(s);
  for (const m of info.night) m.emissiveIntensity = night ? (m.userData.night ?? 1) : 0;
  if (stress) grid(group);
  else {
    scene.add(street(-s.yard));
    scene.add(group);
  }
  frames = 0;
});

// ---- render ----

const target_ = new THREE.WebGLRenderTarget(innerWidth * renderer.getPixelRatio(), innerHeight * renderer.getPixelRatio(), { samples: stress ? 0 : 4, type: THREE.HalfFloatType });
const composer = new EffectComposer(renderer, target_);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth / 2, innerHeight / 2), night ? 0.55 : 0.0, 0.5, night ? 0.75 : 10);
bloom.enabled = night;
composer.addPass(bloom);
composer.addPass(new OutputPass());

let frames = -1;
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
});
renderer.info.autoReset = false;
let cpu = 0;
let loops = 0;
// Waits for the GPU each frame, so frame times are real (for benchmarks).
const sync = q.has("sync");
const px = new Uint8Array(4);
renderer.setAnimationLoop(() => {
  const t0 = performance.now();
  renderer.info.reset();
  controls.update();
  setSignals(Number(q.get("signal") ?? t0 / 1000), night ? 1 : 0);
  composer.render();
  if (sync) {
    const gl = renderer.getContext();
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
  }
  cpu = cpu * 0.95 + (performance.now() - t0) * 0.05;
  loops++;
  ((window as unknown as { durs: number[] }).durs ??= []).push(t0, performance.now());
  if (frames >= 0 && ++frames === 5) document.title = "ready";
  const info = renderer.info.render;
  (window as unknown as { stats: object }).stats = { calls: info.calls, triangles: info.triangles, jsMs: +cpu.toFixed(2), loops };
});
