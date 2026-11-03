// Viewer for the realistic building prototype (blender/proto_apartment.py):
// the apartment block on a street corner, lit like the city. Open
// /proto.html?view=hero|city|detail|roof|back|street&hour=15 in the dev
// server after `bun run proto`. &count=N is the stress test below.
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Sky } from "three/examples/jsm/objects/Sky.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { glass, interiorUniforms } from "./interior";

const q = new URLSearchParams(location.search);
const hour = Number(q.get("hour") ?? 15);
const view = q.get("view") ?? "hero";
// Stress test: ?count=N buildings on a grid, drawn instanced (or one mesh
// each with &draw=separate), with the app's render settings.
const count = Number(q.get("count") ?? 1);
const stress = count > 1;
const SPACING = 24;
const across = Math.ceil(Math.sqrt(count));
const extent = across * SPACING;
const BASE = `${import.meta.env.BASE_URL}proto/`;

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
const VIEWS: Record<string, [number[], number[], number?]> = {
  hero: [[25, 4, 30], [0, 13.5, 0], 50],
  city: [[52, 44, 62], [0, 9, 0], 38],
  detail: [[10.5, 17.5, 13.5], [1.5, 14.5, 5.5], 40],
  roof: [[17, 33, 19], [0, 24, 0], 42],
  back: [[-22, 6, -21], [0, 12, 0], 46],
  street: [[-6, 1.7, 12], [2, 3.5, 6], 55],
};
if (stress) VIEWS.city = [[extent * 0.75 + 40, extent * 0.6 + 35, extent * 0.9 + 50], [0, 6, 0], 40];
const [pos, target, fov] = VIEWS[view] ?? VIEWS.hero;
camera.position.fromArray(pos);
camera.fov = fov ?? 42;
camera.updateProjectionMatrix();
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.fromArray(target);
controls.update();

// ---- sky, sun and the environment the glass reflects ----

const night = hour < 6 || hour >= 19.5;
const el_ = night ? 0.5 : Math.max(4, 50 * Math.sin(((hour - 6) / 13.5) * Math.PI));
const az = THREE.MathUtils.degToRad(Number(q.get("az") ?? (night ? 210 : -95 + (hour - 9) * 12)));
const sunDir = new THREE.Vector3().setFromSphericalCoords(1, THREE.MathUtils.degToRad(90 - (night ? -12 : el_)), az);

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
// No sun disc in what the glass and ambient light see: the sun is the shadowed light.
envSky.material.uniforms.showSunDisc.value = 0;
envScene.add(envSky);
// A dull ground below the horizon so reflections do not show the sky's underside.
const envGround = new THREE.Mesh(new THREE.CircleGeometry(900, 32).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: night ? 0x050608 : 0x3a3c3e }));
envGround.position.y = -2;
envScene.add(envGround);
scene.environment = pmrem.fromScene(envScene, 0.02).texture;
scene.environmentIntensity = Number(q.get("env") ?? (night ? 0.08 : 0.12));

const sun = new THREE.DirectionalLight(night ? 0x8fa8d8 : 0xfff1dc, night ? 0.25 : Number(q.get("sun") ?? 5));
sun.position.copy(night ? new THREE.Vector3(-0.4, 0.8, 0.5) : sunDir).multiplyScalar(Math.max(80, extent));
sun.castShadow = true;
sun.shadow.mapSize.setScalar(stress ? 2048 : 4096);
const sc = sun.shadow.camera;
sc.left = sc.bottom = -Math.max(32, extent * 0.75);
sc.right = sc.top = Math.max(32, extent * 0.75);
sc.far = Math.max(200, extent * 2);
sc.near = 1;
sun.shadow.bias = -0.0002;
sun.shadow.normalBias = 0.03;
scene.add(sun);
scene.add(new THREE.HemisphereLight(night ? 0x223044 : 0xc8dcff, night ? 0x101010 : 0x5a5248, night ? 0.15 : 0.35));
scene.fog = new THREE.Fog(night ? 0x0a0e18 : 0xc4d2e0, 300, 2500);
renderer.toneMappingExposure = night ? 0.9 : 0.75;
interiorUniforms.uDay.value = night ? 0 : 1;
interiorUniforms.uNight.value = night ? 1 : 0;

// ---- textures and materials ----

const loader = new THREE.TextureLoader();
function tex(name: string, tile: [number, number] = [1, 1], color = true): THREE.Texture {
  const t = loader.load(`${BASE}${name}.png`);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.flipY = false;
  t.repeat.set(1 / tile[0], 1 / tile[1]);
  t.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return t;
}

const ao = tex("ao", [1, 1], false);
ao.channel = 1;

const grime = tex("grime", [1, 1], false);
const GRIME = /* glsl */ `
  vec3 gn = abs(normalize(vGN));
  vec2 gp = gn.y > 0.7 ? vGW.xz : gn.x > gn.z ? vGW.zy : vGW.xy;
  float macro = texture2D(grimeMap, gp / 11.0).r;
  float streak = texture2D(grimeMap, vec2(gp.x / 0.9, gp.y / 16.0)).r;
  float splash = smoothstep(1.4, 0.0, vGW.y);
  float occ = texture2D(aoMap, vAoMapUv).r;
  float dirt = uGrime * (0.22 * smoothstep(0.45, 0.85, streak) + 0.2 * (macro - 0.5) + 0.22 * splash + 0.3 * (1.0 - occ));
  diffuseColor.rgb *= clamp(1.0 - dirt, 0.55, 1.15);
`;

/**
 * Baked occlusion darkens direct light a little too, for contact shadows
 * under ledges; `weather` adds world-space grime: blotches, rain streaks,
 * splash at the foot and dirt in the corners.
 */
function withAo<T extends THREE.MeshStandardMaterial>(m: T, weather = 0): T {
  m.aoMap = ao;
  m.aoMapIntensity = 1;
  m.onBeforeCompile = (sh) => {
    sh.uniforms.grimeMap = { value: grime };
    sh.uniforms.uGrime = { value: weather };
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vGW;\nvarying vec3 vGN;")
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\nvGW = (modelMatrix * vec4(transformed, 1.0)).xyz;\nvGN = mat3(modelMatrix) * objectNormal;");
    sh.fragmentShader = sh.fragmentShader
      .replace("#include <common>", "#include <common>\nuniform sampler2D grimeMap;\nuniform float uGrime;\nvarying vec3 vGW;\nvarying vec3 vGN;")
      .replace("#include <map_fragment>", `#include <map_fragment>\n${GRIME}`)
      .replace(
        "#include <aomap_fragment>",
        "#include <aomap_fragment>\nreflectedLight.directDiffuse *= mix(1.0, occ, 0.55);\nreflectedLight.directSpecular *= mix(1.0, occ, 0.55);",
      );
  };
  m.customProgramCacheKey = () => "weathered";
  return m;
}

function pbr(name: string, tile: [number, number], opts: THREE.MeshStandardMaterialParameters & { rough?: boolean; normal?: number } = {}) {
  const { rough, normal = 1, ...rest } = opts;
  const m = new THREE.MeshStandardMaterial({ map: tex(`${name}_col`, tile), normalMap: tex(`${name}_nrm`, tile, false), roughness: 0.85, ...rest });
  m.normalScale.set(normal, -normal);
  if (rough) {
    m.roughnessMap = tex(`${name}_rgh`, tile, false);
    m.roughness = 1;
  }
  return m;
}

function signs(): THREE.Texture {
  const c = document.createElement("canvas");
  c.width = 2048;
  c.height = 256;
  const g = c.getContext("2d")!;
  const draw = (x: number, bg: string, fg: string, text: string, sub: string) => {
    g.fillStyle = bg;
    g.fillRect(x, 0, 1024, 256);
    g.strokeStyle = fg;
    g.lineWidth = 5;
    g.strokeRect(x + 14, 14, 996, 228);
    g.fillStyle = fg;
    g.textAlign = "center";
    g.font = "600 112px Georgia, 'Times New Roman', serif";
    g.fillText(text, x + 512, 150);
    g.font = "italic 40px Georgia, serif";
    g.fillText(sub, x + 512, 212);
  };
  draw(0, "#1d3a2c", "#e3c27a", "ROSSI & SONS", "bakery · est. 1931");
  draw(1024, "#22303f", "#f0e6cf", "HARBOUR BOOKS", "new & secondhand");
  const t = new THREE.CanvasTexture(c);
  t.flipY = false;
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = THREE.RepeatWrapping;
  t.repeat.x = 0.5;
  t.anisotropy = 8;
  return t;
}

const signTex = signs();
const plain = (color: number, roughness = 0.6, metalness = 0, extra: THREE.MeshStandardMaterialParameters = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });

const MATS: Record<string, THREE.Material> = {
  brick: withAo(pbr("brick", [1.72, 1.8], { rough: true }), 1.6),
  stone: withAo(pbr("stone", [2, 2], { roughness: 0.82 }), 1.6),
  ashlar: withAo(pbr("ashlar", [2.4, 1.8], { roughness: 0.85 }), 1.4),
  granite: withAo(new THREE.MeshStandardMaterial({ map: tex("granite_col"), roughness: 0.5 }), 0.5),
  roof: withAo(pbr("roof", [4, 4], { roughness: 0.92 }), 1),
  wood: withAo(pbr("wood", [1.2, 1.2], { roughness: 0.9 }), 0.8),
  concrete: withAo(pbr("stone", [2, 2], { color: 0xb8b8b4, roughness: 0.95 }), 1),
  frame: withAo(plain(0xe9e4d8, 0.42)),
  shopframe: withAo(plain(0x1f3a2e, 0.35)),
  door: withAo(plain(0x3a2216, 0.38)),
  brass: withAo(plain(0xc9a24e, 0.3, 1)),
  dark: withAo(plain(0x161616, 0.7)),
  iron: withAo(plain(0x1b1c1e, 0.5, 0.35)),
  ac: withAo(plain(0xc4c4be, 0.45, 0.4)),
  steel: withAo(plain(0x4b423b, 0.75, 0.5)),
  terracotta: withAo(plain(0x9a5436, 0.8)),
  canopy: plain(0xa8bcc4, 0.08, 0, { transparent: true, opacity: 0.35 }),
  lamp: plain(0xfff2d8, 0.3, 0, { emissive: 0xffd9a0, emissiveIntensity: night ? 6 : 0.2 }),
  sign: withAo(plain(0xffffff, 0.35, 0, { map: signTex, emissiveMap: signTex, emissive: 0xffffff, emissiveIntensity: night ? 0.35 : 0 })),
  awning: withAo(new THREE.MeshStandardMaterial({ map: tex("awning_col"), roughness: 0.92 })),
  bars: new THREE.MeshStandardMaterial({ map: tex("bars"), alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.5, metalness: 0.35 }),
  grate: new THREE.MeshStandardMaterial({ map: tex("grate"), alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.5, metalness: 0.35 }),
  glass: glass("home"),
  shopglass: glass("shop"),
  doorglass: glass("lobby"),
};

// ---- the street corner ----

/** Plan UVs in metres, for tiling textures. */
function metres(g: THREE.BufferGeometry) {
  const uv = g.getAttribute("uv") as THREE.BufferAttribute;
  const p = g.getAttribute("position") as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, p.getX(i), p.getZ(i));
  return g;
}

function street() {
  const g = new THREE.Group();
  const ground = new THREE.PlaneGeometry(400, 400).rotateX(-Math.PI / 2);
  metres(ground);
  const asphalt = new THREE.Mesh(ground, pbr("asphalt", [6, 6], { roughness: 0.9, normal: 0.6 }));
  asphalt.position.y = -0.15;
  asphalt.receiveShadow = true;
  g.add(asphalt);
  // Pavement round the block, with a granite kerb.
  const pw = 14 + 8, pd = 12 + 8;
  const slab = metres(new THREE.BoxGeometry(pw, 0.15, pd));
  const pave = new THREE.Mesh(slab, pbr("pave", [3.6, 3.6], { roughness: 0.88 }));
  pave.position.y = -0.075;
  pave.receiveShadow = true;
  g.add(pave);
  const kerbMat = new THREE.MeshStandardMaterial({ color: 0x9a9894, roughness: 0.7 });
  for (const [w, d, x, z] of [[pw + 0.3, 0.3, 0, pd / 2], [pw + 0.3, 0.3, 0, -pd / 2], [0.3, pd, pw / 2, 0], [0.3, pd, -pw / 2, 0]]) {
    const k = new THREE.Mesh(new THREE.BoxGeometry(w, 0.17, d), kerbMat);
    k.position.set(x, -0.07, z);
    k.receiveShadow = true;
    g.add(k);
  }
  // Soft contact shadow where the walls meet the pavement.
  const c = document.createElement("canvas");
  c.width = 4;
  c.height = 64;
  const cg = c.getContext("2d")!;
  const grad = cg.createLinearGradient(0, 0, 0, 64);
  grad.addColorStop(0, "rgba(0,0,0,0.55)");
  grad.addColorStop(0.35, "rgba(0,0,0,0.18)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  cg.fillStyle = grad;
  cg.fillRect(0, 0, 4, 64);
  const fade = new THREE.CanvasTexture(c);
  const contact = new THREE.MeshBasicMaterial({ map: fade, transparent: true, depthWrite: false });
  for (const [len, x, z, ry] of [[14.2, 0, 6.06, 0], [14.2, 0, -6.06, Math.PI], [12.2, 7.06, 0, Math.PI / 2], [12.2, -7.06, 0, -Math.PI / 2]]) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(len, 1.4).translate(0, -0.7, 0).rotateX(-Math.PI / 2), contact);
    m.rotation.y = ry;
    m.position.set(x, 0.004, z);
    g.add(m);
  }
  // Lane lines.
  const paint = new THREE.MeshStandardMaterial({ color: 0xe8e6de, roughness: 0.7 });
  for (let i = -20; i <= 20; i++) {
    for (const [x, z, rot] of [[i * 6, pd / 2 + 5, 0], [i * 6, -pd / 2 - 5, 0], [pw / 2 + 5, i * 6, 1], [-pw / 2 - 5, i * 6, 1]]) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(rot ? 0.15 : 3, rot ? 3 : 0.15).rotateX(-Math.PI / 2), paint);
      m.position.set(x, -0.145, z);
      m.receiveShadow = true;
      g.add(m);
    }
  }
  // Street lamps at the corners.
  const pole = new THREE.MeshStandardMaterial({ color: 0x232527, roughness: 0.5, metalness: 0.5 });
  for (const [x, z] of [[pw / 2 - 0.6, pd / 2 - 0.6], [-pw / 2 + 0.6, pd / 2 - 0.6], [pw / 2 - 0.6, -pd / 2 + 0.6]]) {
    const s = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.11, 5.5, 12), pole);
    s.position.set(x, 2.75, z);
    s.castShadow = true;
    g.add(s);
    const head = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.32, 0.45, 12), MATS.lamp);
    head.position.set(x, 5.6, z);
    g.add(head);
    if (night) {
      const l = new THREE.PointLight(0xffc98a, 18, 16, 1.6);
      l.position.set(x, 5.2, z);
      g.add(l);
    }
  }
  return g;
}
if (!stress) scene.add(street());

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
  const ground = new THREE.Mesh(metres(new THREE.PlaneGeometry(extent + 400, extent + 400).rotateX(-Math.PI / 2)), pbr("asphalt", [6, 6], { roughness: 0.9 }));
  ground.receiveShadow = true;
  scene.add(ground);
}

new GLTFLoader().load(`${BASE}apartment.glb`, (gltf) => {
  gltf.scene.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    const name = (mesh.material as THREE.Material).name;
    mesh.material = MATS[name] ?? plain(0xff00ff);
    mesh.castShadow = name !== "canopy";
    mesh.receiveShadow = true;
  });
  if (stress) grid(gltf.scene);
  else scene.add(gltf.scene);
  if (night) {
    // Light pooling round the entrance and under the shop signs.
    for (const [x, y, z, c, i] of [[0, 3.2, 7.2, 0xffc98a, 6], [-4.2, 3.2, 6.8, 0xffe0b0, 5], [4.2, 3.2, 6.8, 0xffe0b0, 5]] as const) {
      const l = new THREE.PointLight(c, i, 8, 1.8);
      l.position.set(x, y, z);
      scene.add(l);
    }
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
