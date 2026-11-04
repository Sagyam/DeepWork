// City theme: the realistic models (ui/blender/real, docs/models.md), which
// replace the low-poly kit's styles one model at a time. `bun run models`
// writes public/models/: <id>.glb (pieces as nodes, materials named by
// role), <id>_ao.png (AO baked on the lightmap UVs) and tex/, the shared
// texture library. Any model that is missing falls back to the kit.
//
// This module loads the models and owns their materials: PBR from the
// library with baked AO and world-space weathering, and window glass that
// shows a room behind it (interior.ts). models.ts stacks the pieces.
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { glass, interiorUniforms, type RoomKind } from "./interior";
import type { Kind } from "./plan";

export { interiorUniforms };

const BASE = `${import.meta.env.BASE_URL}models/`;

export interface RealPart {
  role: string;
  geo: THREE.BufferGeometry;
}

interface Loaded {
  pieces: Map<string, RealPart[]>;
  ao: THREE.Texture;
}

const loaded = new Map<string, Loaded>();

/** How a model sits in the city: its size, how it stacks, where its chimney smokes. */
export interface RealDef {
  id: string;
  /** The kit kind and style it takes over (docs/models.md). */
  kind: Kind;
  style: string;
  /** Footprint (x, z) in metres, eaves, porch and steps included; front faces +z. */
  w: number;
  d: number;
  /** Stand-back from the street to the front of the footprint. */
  front: number;
  /** Storeys for the plan's floor count. */
  floors(plan: number): number;
  /** Pieces bottom to top for `floors` storeys, without the roof if not `roof`. */
  stack(floors: number, roof: boolean, r: () => number): { piece: string; y: number }[];
  /** Height of the body (top of the last storey, or the eaves). */
  top(floors: number): number;
  /** Height with the roof. */
  height(floors: number): number;
  /** Chimney smoke, building-local. */
  smoke?: (floors: number) => THREE.Vector3;
  /** The colour debris takes when it collapses. */
  debris: number;
}

const A1_G = 4.5;
const A1_FL = 3.1;
const C1_PLATE = 6.1;
const C3_G = 3.3;
const C3_TOP = 6.3;
const S1_G = 4.45;
const S1_FL = 3.3;

export const DEFS: Record<string, RealDef> = {
  a1: {
    id: "a1",
    kind: "apartment",
    style: "classic",
    w: 14,
    d: 12,
    front: 1.0,
    floors: (plan) => Math.max(3, plan),
    stack(floors, roof, r) {
      // Ground storey, then the first, typical storeys (balconies; two kinds,
      // alternating from a random start) and the top storey, then the roof.
      const upper = Math.max(2, floors - 1);
      const out = [{ piece: "ground", y: 0 }];
      const flip = r() < 0.5 ? 1 : 0;
      for (let f = 0; f < upper; f++) {
        const last = f === upper - 1 && roof;
        const piece = f === 0 ? "first" : last ? "last" : (f + flip) % 2 ? "floor_a" : "floor_b";
        out.push({ piece, y: A1_G + f * A1_FL });
      }
      if (roof) out.push({ piece: "roof", y: A1_G + upper * A1_FL });
      return out;
    },
    top: (floors) => A1_G + Math.max(2, floors - 1) * A1_FL,
    height: (floors) => A1_G + Math.max(2, floors - 1) * A1_FL + 2.3,
    debris: 0x8a4e3c,
  },
  c1: {
    id: "c1",
    kind: "cottage",
    style: "classic",
    w: 10,
    d: 11.8,
    front: 2.0,
    floors: () => 2,
    stack: (floors, roof) => [...(floors > 0 ? [{ piece: "body", y: 0 }] : []), ...(roof ? [{ piece: "roof", y: C1_PLATE }] : [])],
    top: () => C1_PLATE,
    height: () => 8.8,
    smoke: () => new THREE.Vector3(-4.6, 9.9, 0.2),
    debris: 0xd8d2c4,
  },
  c3: {
    id: "c3",
    kind: "cottage",
    style: "modern",
    w: 12.2,
    d: 10.3,
    // Room for the car in front of the garage.
    front: 4.0,
    floors: () => 2,
    stack: (floors, roof) => [
      ...(floors > 0 ? [{ piece: "ground", y: 0 }] : []),
      ...(floors > 1 ? [{ piece: "upper", y: C3_G }] : []),
      ...(floors > 1 && roof ? [{ piece: "roof", y: C3_TOP }] : []),
    ],
    top: (floors) => (floors > 1 ? C3_TOP : C3_G),
    height: () => C3_TOP + 0.45,
    smoke: () => new THREE.Vector3(-4.6, C3_TOP + 1.6, -2.2),
    debris: 0xe4e0d6,
  },
  s1: {
    id: "s1",
    kind: "shop",
    style: "classic",
    w: 9.3,
    d: 11,
    front: 1.0,
    floors: (plan) => Math.min(3, Math.max(2, plan)),
    stack(floors, roof, r) {
      // The shop, one or two storeys of flats, the roof; most shops have an awning.
      const out = floors > 0 ? [{ piece: "ground", y: 0 }] : [];
      if (floors > 0 && r() < 0.75) out.push({ piece: "awning", y: 0 });
      for (let f = 1; f < floors; f++) out.push({ piece: "floor", y: S1_G + (f - 1) * S1_FL });
      if (roof) out.push({ piece: "roof", y: S1_G + (floors - 1) * S1_FL });
      return out;
    },
    top: (floors) => S1_G + (floors - 1) * S1_FL,
    height: (floors) => S1_G + (floors - 1) * S1_FL + 2.2,
    smoke: (floors) => new THREE.Vector3(-4.1, S1_G + (floors - 1) * S1_FL + 2.9, -1.6),
    debris: 0x8a4e3c,
  },
};

/**
 * Models that are not buildings: the props the city is dressed with
 * (vehicles, ...), each one glb of named pieces. Missing ones fall back to
 * the kit's props.
 */
export const PROPS = ["cars"];

/** Loads every model there is; missing ones are left to the kit. Never throws. */
export async function loadReal(ids = [...Object.keys(DEFS), ...PROPS]): Promise<void> {
  const tex = new THREE.TextureLoader();
  await Promise.all(
    ids.map(async (id) => {
      if (loaded.has(id)) return;
      try {
        const [gltf, ao] = await Promise.all([new GLTFLoader().loadAsync(`${BASE}${id}.glb`), tex.loadAsync(`${BASE}${id}_ao.png`)]);
        ao.flipY = false;
        ao.channel = 1;
        // Props are small on screen: mipmaps would blend each island of the
        // atlas with its neighbours (tyres, underbodies) into blotches.
        if (PROPS.includes(id)) {
          ao.generateMipmaps = false;
          ao.minFilter = THREE.LinearFilter;
        }
        ao.colorSpace = THREE.NoColorSpace;
        const pieces = new Map<string, RealPart[]>();
        for (const node of gltf.scene.children) {
          node.updateMatrixWorld(true);
          const name = node.name.replace(new RegExp(`^${id}_`), "").replace(/_(cut|decal)$/, "");
          const parts = pieces.get(name) ?? [];
          node.traverse((o) => {
            const mesh = o as THREE.Mesh;
            if (mesh.isMesh) parts.push({ role: (mesh.material as THREE.Material).name, geo: mesh.geometry.clone().applyMatrix4(mesh.matrixWorld) });
          });
          pieces.set(name, parts);
        }
        loaded.set(id, { pieces, ao });
      } catch {
        // Not built (bun run models) or not downloaded yet: the kit draws this style.
      }
    }),
  );
}

export const hasReal = (id: string) => loaded.has(id);

/** A loaded model's baked AO (for the viewer's debug view). */
export const realAo = (id: string) => loaded.get(id)?.ao;

/** The pieces a loaded model has, in file order. */
export const realPieces = (id: string): string[] => [...(loaded.get(id)?.pieces.keys() ?? [])];

export function realPiece(id: string, name: string): RealPart[] {
  const p = loaded.get(id)?.pieces.get(name);
  if (!p) throw new Error(`realistic model ${id}: no piece "${name}"`);
  return p;
}

// ---- materials ------------------------------------------------------------------

const texLoader = new THREE.TextureLoader();
const library = new Map<string, THREE.Texture>();

/** A library texture; `tile` is its size in metres (UV0 is in metres). */
function tex(name: string, tile: [number, number] = [1, 1], color = true): THREE.Texture {
  const key = `${name}:${tile}`;
  let t = library.get(key);
  if (!t) {
    t = texLoader.load(`${BASE}tex/${name}.png`);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.flipY = false;
    t.repeat.set(1 / tile[0], 1 / tile[1]);
    t.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.anisotropy = 8;
    library.set(key, t);
  }
  return t;
}

const GRIME = /* glsl */ `
  vec3 gn = abs(normalize(vGN));
  vec2 gp = gn.y > 0.7 ? vGW.xz : gn.x > gn.z ? vGW.zy : vGW.xy;
  float macro = texture2D(grimeMap, gp / 11.0).r;
  float streak = texture2D(grimeMap, vec2(gp.x / 0.9, gp.y / 16.0)).r;
  float splash = smoothstep(1.4, 0.0, vGW.y - uFloor);
  float occ = texture2D(aoMap, vAoMapUv).r;
  float dirt = uGrime * (0.22 * smoothstep(0.45, 0.85, streak) + 0.2 * (macro - 0.5) + 0.22 * splash + 0.3 * (1.0 - occ));
  diffuseColor.rgb *= clamp(1.0 - dirt, 0.55, 1.15);
`;

/**
 * Baked occlusion darkens direct light a little too, for contact shadows
 * under ledges; `weather` adds world-space grime: blotches, rain streaks,
 * splash at the foot and dirt in the corners.
 */
function weathered<T extends THREE.MeshStandardMaterial>(m: T, ao: THREE.Texture, weather = 0): T {
  m.aoMap = ao;
  m.aoMapIntensity = 1;
  const grime = tex("grime", [1, 1], false);
  m.onBeforeCompile = (sh) => {
    sh.uniforms.grimeMap = { value: grime };
    sh.uniforms.uGrime = { value: weather };
    sh.uniforms.uFloor = { value: 0.2 };
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vGW;\nvarying vec3 vGN;")
      .replace(
        "#include <worldpos_vertex>",
        "#include <worldpos_vertex>\nmat4 gm = modelMatrix;\n#ifdef USE_INSTANCING\ngm = modelMatrix * instanceMatrix;\n#endif\nvGW = (gm * vec4(transformed, 1.0)).xyz;\nvGN = mat3(gm) * objectNormal;",
      );
    sh.fragmentShader = sh.fragmentShader
      .replace("#include <common>", "#include <common>\nuniform sampler2D grimeMap;\nuniform float uGrime;\nuniform float uFloor;\nvarying vec3 vGW;\nvarying vec3 vGN;")
      .replace("#include <map_fragment>", `#include <map_fragment>\n${GRIME}`)
      .replace(
        "#include <aomap_fragment>",
        "#include <aomap_fragment>\nreflectedLight.directDiffuse *= mix(1.0, occ, 0.55);\nreflectedLight.directSpecular *= mix(1.0, occ, 0.55);",
      );
  };
  m.customProgramCacheKey = () => "weathered";
  return m;
}

type Std = THREE.MeshStandardMaterialParameters;

function pbr(name: string, tile: [number, number], opts: Std & { rough?: boolean; normal?: number } = {}): THREE.MeshStandardMaterial {
  const { rough, normal = 1, ...rest } = opts;
  const m = new THREE.MeshStandardMaterial({ map: tex(`${name}_col`, tile), normalMap: tex(`${name}_nrm`, tile, false), roughness: 0.85, ...rest });
  m.normalScale.set(normal, -normal);
  if (rough) {
    m.roughnessMap = tex(`${name}_rgh`, tile, false);
    m.roughness = 1;
  }
  return m;
}

const plain = (color: number, roughness = 0.6, metalness = 0, extra: Std = {}) => new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });

const SHOPS: [string, string, string, string][] = [
  ["#1d3a2c", "#e3c27a", "ROSSI & SONS", "bakery · est. 1931"],
  ["#22303f", "#f0e6cf", "HARBOUR BOOKS", "new & secondhand"],
  ["#4a1c1c", "#f2dfb4", "MARLOWE'S", "delicatessen"],
  ["#1f2a24", "#d9e4d0", "GREEN & CO.", "florist"],
  ["#2b2b2b", "#e8c66a", "KOVAC HARDWARE", "tools · paint · keys"],
  ["#30264a", "#efe2c8", "LUNA CAFÉ", "espresso bar"],
  ["#14324a", "#f4ecd8", "PIER PHARMACY", "dispensing chemist"],
  ["#5a3a1a", "#f6e6c2", "OLD MILL TAILORS", "bespoke since 1924"],
];

let signCanvas: HTMLCanvasElement | null = null;

/** Shop signs, two columns by four rows of 1024 x 256; a building shows one row, from column `col` on. */
function signs(row: number, col = 0): THREE.Texture {
  if (!signCanvas) {
    const c = (signCanvas = document.createElement("canvas"));
    c.width = 2048;
    c.height = 1024;
    const g = c.getContext("2d")!;
    SHOPS.forEach(([bg, fg, text, sub], i) => {
      const x = (i % 2) * 1024;
      const y = Math.floor(i / 2) * 256;
      g.fillStyle = bg;
      g.fillRect(x, y, 1024, 256);
      g.strokeStyle = fg;
      g.lineWidth = 5;
      g.strokeRect(x + 14, y + 14, 996, 228);
      g.fillStyle = fg;
      g.textAlign = "center";
      g.font = "600 104px Georgia, 'Times New Roman', serif";
      g.fillText(text, x + 512, y + 148, 960);
      g.font = "italic 40px Georgia, serif";
      g.fillText(sub, x + 512, y + 212);
    });
  }
  const t = new THREE.CanvasTexture(signCanvas);
  t.flipY = false;
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = THREE.RepeatWrapping;
  t.repeat.set(0.5, 0.25);
  t.offset.set(col * 0.5, row * 0.25);
  t.anisotropy = 8;
  return t;
}

const ADS: [string, string, string, string][] = [
  ["#3a1f1a", "#efe4cc", "HARRISON'S FLOUR", "the best bread begins here"],
  ["#1c2433", "#ece6d6", "STAR LAUNDRY", "collars & cuffs · shirts 10¢"],
  ["#20261e", "#e9dfc2", "OLD MILL TOBACCO", "mild and mellow"],
  ["#2a1d2c", "#f0e2c8", "BAKER BROS.", "furniture · stoves · carpets"],
];

let ghostCanvas: HTMLCanvasElement | null = null;

/** Faded advertisements painted on party walls, four rows of 1024 x 320; a wall shows one. */
function ghosts(row: number): THREE.Texture {
  if (!ghostCanvas) {
    const c = (ghostCanvas = document.createElement("canvas"));
    c.width = 1024;
    c.height = 1280;
    const g = c.getContext("2d")!;
    ADS.forEach(([bg, fg, text, sub], i) => {
      const y = i * 320;
      g.globalAlpha = 0.7;
      g.fillStyle = bg;
      g.fillRect(16, y + 16, 992, 288);
      g.globalAlpha = 0.85;
      g.strokeStyle = fg;
      g.lineWidth = 8;
      g.strokeRect(34, y + 34, 956, 252);
      g.fillStyle = fg;
      g.textAlign = "center";
      g.font = "800 112px Impact, 'Arial Black', sans-serif";
      g.fillText(text, 512, y + 170, 900);
      g.font = "italic 600 52px Georgia, serif";
      g.fillText(sub, 512, y + 248, 860);
    });
    // Weathered away: flakes and streaks where the paint has gone.
    g.globalAlpha = 1;
    g.globalCompositeOperation = "destination-out";
    let seed = 7;
    const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 9000; i++) {
      g.globalAlpha = 0.3 + rand() * 0.7;
      g.fillRect(rand() * 1024, rand() * 1280, 2 + rand() * 9, 2 + rand() * 6);
    }
    for (let i = 0; i < 140; i++) {
      g.globalAlpha = 0.15 + rand() * 0.3;
      g.fillRect(rand() * 1024, rand() * 1280, 3 + rand() * 10, 40 + rand() * 200);
    }
    g.globalCompositeOperation = "source-over";
  }
  const t = new THREE.CanvasTexture(ghostCanvas);
  t.flipY = false;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(1, 0.25);
  t.offset.set(0, row * 0.25);
  t.anisotropy = 8;
  return t;
}

/** Per-building choices: paint colours and the like. Indexes wrap. */
export interface Paint {
  /** Main walls: brick tint or siding paint. */
  wall: number;
  /** Shopfronts, doors and shutters. */
  accent: number;
  roof: number;
  /** Which shop signs: 0-7, the row and (for one-shop models) the column. */
  signs: number;
}

const BRICK_TINTS = [0xffffff, 0xe8d8cc, 0xc8b8b0, 0xf4e0c0];
const SHOPFRONTS = [0x1f3a2e, 0x4a1c1c, 0x1c2a44, 0x222222, 0x3a2a4a, 0x2e4a52];
const SIDING = [0xf2efe6, 0xf0e2b8, 0xc9d3bf, 0xb8c6cf, 0xe8ddd0, 0x9a3c30, 0xd9cdb4, 0xf4f1ea];
const SHUTTERS = [0x1d2a22, 0x1f2d44, 0x222222, 0x6a2a24, 0x3e5a48, 0x4a5a6a];
const SHINGLES = [0x5a5a5c, 0x6e5a48, 0x4e5660, 0x5c6252, 0x7a6e64, 0x3e3e40];
/** Pressed-metal cornices: cream, stone, bottle green, oxblood, slate. */
const CORNICES = [0xe6dcc4, 0xc8beac, 0x2e4434, 0x5a2420, 0x4a5058];
/** Render: white, warm white, pale grey, sand, anthracite, chalk. */
const RENDERS = [0xf6f4ee, 0xeee8da, 0xd8d6d0, 0xe8dcc6, 0x55585a, 0xf2f0ea];
/** Timber cladding: larch, silver-weathered, charred, cedar, honey. */
const TIMBER = [0xe6b488, 0xc4c2bc, 0x4a4644, 0xd2905e, 0xf0cc96];
/** Window frames, copings and doors: anthracite (most), black, bronze. */
const FRAMES = [0x33373b, 0x1e1f21, 0x33373b, 0x6e5e4a, 0x40454a];
/** Car paint, as on real roads: white, black, silvers and greys most; then blue, red, green, beige, burgundy. */
export const CAR_PAINTS = [0xeceae6, 0x16181b, 0xa9adb1, 0x5c6066, 0xeceae6, 0x1f3550, 0x9c1f22, 0x2e4a3c, 0xb8ab90, 0x5a1c26, 0x7e8a94, 0x16181b];

const cache = new Map<string, THREE.Material>();
/** Glass and lamps, which follow the time of day (see City.light). */
const glassMats = new Set<THREE.MeshPhysicalMaterial>();
let skyEnv: THREE.Texture | null = null;

/** The sky the realistic glass reflects; set by the scene when the light changes. */
export function setRealEnv(env: THREE.Texture) {
  skyEnv = env;
  for (const m of glassMats) {
    m.envMap = env;
    m.needsUpdate = true;
  }
}

/**
 * The material for a role of model `id`, for one building's paint and
 * damage (0-2). Shared between buildings with the same choices; `variant`
 * keeps a set apart (traffic's lamps light at night, parked cars' do not).
 * Car paint takes CAR_PAINTS[paint.wall], or white for paint.wall < 0 so
 * instance colours tint it.
 */
export function realMat(id: string, role: string, paint: Paint, damage: number, variant = ""): THREE.Material {
  const pick = (list: number[], i: number) => list[((i % list.length) + list.length) % list.length];
  const tinted = ["brick", "siding", "shutter", "shopframe", "door", "shingle", "sign", "cornice", "ghost", "render", "cladding", "alu", "carpaint"].includes(role);
  const key = `${id}:${role}:${damage}:${variant}:${tinted ? `${paint.wall}:${paint.accent}:${paint.roof}:${paint.signs}` : ""}`;
  let m = cache.get(key);
  if (m) return m;
  const ao = loaded.get(id)!.ao;
  const shade = [1, 0.72, 0.42][Math.min(2, damage)];
  const w = (mat: THREE.MeshStandardMaterial, weather = 0) => weathered(mat, ao, weather + damage * 0.8);
  const room = (kind: RoomKind) => {
    const g = glass(kind, damage / 2);
    if (skyEnv) g.envMap = skyEnv;
    glassMats.add(g);
    return g;
  };
  const accent = id === "c1" ? pick(SHUTTERS, paint.accent) : pick(SHOPFRONTS, paint.accent);
  const frame = pick(FRAMES, paint.roof);
  /** Glossy glass without a room behind: sky reflections only. */
  const sheen = (params: THREE.MeshPhysicalMaterialParameters) => {
    const g = new THREE.MeshPhysicalMaterial({ roughness: 0.08, ior: 1.5, ...params });
    if (skyEnv) g.envMap = skyEnv;
    glassMats.add(g);
    return g;
  };
  switch (role) {
    case "brick": m = w(pbr("brick", [1.72, 1.8], { rough: true, color: id === "c1" ? 0xffffff : pick(BRICK_TINTS, paint.wall) }), 1.6); break;
    case "stone": m = w(pbr("stone", [2, 2], { roughness: 0.82 }), 1.6); break;
    case "ashlar": m = w(pbr("ashlar", [2.4, 1.8], { roughness: 0.85 }), 1.4); break;
    case "granite": m = w(new THREE.MeshStandardMaterial({ map: tex("granite_col"), roughness: 0.5 }), 0.5); break;
    case "roof": m = w(pbr("roof", [4, 4], { roughness: 0.92 }), 1); break;
    case "wood": m = w(pbr("wood", [1.2, 1.2], { roughness: 0.9 }), 0.8); break;
    case "deck": m = w(pbr("wood", [1.2, 1.2], { roughness: 0.8, color: 0xb8c0c4 }), 0.6); break;
    case "concrete": m = w(pbr("stone", [2, 2], { color: 0xb8b8b4, roughness: 0.95 }), 1); break;
    case "siding": m = w(pbr("siding", [2.4, 1.2], { rough: true, color: pick(SIDING, paint.wall) }), 0.7); break;
    case "shingle": m = w(pbr("shingle", [2, 1.12], { roughness: 0.95, color: pick(SHINGLES, paint.roof) }), 0.8); break;
    case "shutter": m = w(pbr("louvre", [1, 1], { roughness: 0.55, color: accent })); break;
    case "trim": m = w(plain(0xeeebe2, 0.55), 0.5); break;
    case "cornice": m = w(plain(pick(CORNICES, paint.roof), 0.5, 0.2), 1.2); break;
    case "paint": m = w(plain(0xf0ede4, 0.6), 0.6); break;
    case "ceiling": m = w(plain(0xb4d4d2, 0.6)); break;
    case "gutter": m = w(plain(0xe4e2dc, 0.4, 0.3)); break;
    case "frame": m = w(plain(id === "c1" ? 0xf2efe8 : 0xe9e4d8, 0.42)); break;
    case "shopframe": m = w(plain(accent, 0.35)); break;
    case "door": m = w(plain(id === "c1" ? accent : id === "c3" ? frame : 0x3a2216, 0.38)); break;
    case "render": m = w(pbr("render", [3, 3], { roughness: 0.9, normal: 0.6, color: pick(RENDERS, paint.wall) }), 0.4); break;
    case "cladding": m = w(pbr("battens", [1.3, 1.3], { roughness: 0.8, color: pick(TIMBER, paint.accent) }), 0.4); break;
    case "alu": m = w(plain(frame, 0.4, 0.5)); break;
    case "gravel": m = w(pbr("gravel", [1.5, 1.5], { roughness: 0.95 }), 0.6); break;
    case "sedum": m = w(pbr("sedum", [1.2, 1.2], { roughness: 0.9 })); break;
    case "solar": m = sheen({ map: tex("solar_col"), roughness: 0.15, metalness: 0.1 }); break;
    case "skyglass": m = sheen({ color: 0x141a20 }); break;
    case "brass": m = w(plain(0xc9a24e, 0.3, 1)); break;
    case "dark": m = w(plain(0x161616, 0.7)); break;
    case "iron": m = w(plain(0x1b1c1e, 0.5, 0.35)); break;
    case "ac": m = w(plain(0xc4c4be, 0.45, 0.4)); break;
    case "steel": m = w(plain(0x4b423b, 0.75, 0.5)); break;
    case "terracotta": m = w(plain(0x9a5436, 0.8)); break;
    case "canopy": m = plain(0xa8bcc4, 0.08, 0, { transparent: true, opacity: 0.35 }); break;
    case "lamp":
      m = plain(0xfff2d8, 0.3, 0, { emissive: 0xffd9a0, emissiveIntensity: 0 });
      if (damage < 2) m.userData.night = 6;
      break;
    case "sign": {
      const t = signs(paint.signs % 4, id === "s1" ? Math.floor(paint.signs / 4) % 2 : 0);
      m = w(plain(0xffffff, 0.35, 0, { map: t, emissiveMap: t, emissive: 0xffffff, emissiveIntensity: 0 }));
      if (damage < 2) m.userData.night = 0.35;
      break;
    }
    case "ghost":
      m = new THREE.MeshStandardMaterial({ map: ghosts(paint.wall % 4), transparent: true, opacity: 0.6, roughness: 0.95, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      break;
    case "awning": m = w(new THREE.MeshStandardMaterial({ map: tex("awning_col"), roughness: 0.92 })); break;
    case "bars": m = new THREE.MeshStandardMaterial({ map: tex("bars", [1, 1]), alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.5, metalness: 0.35 }); break;
    case "grate": m = new THREE.MeshStandardMaterial({ map: tex("grate", [1, 1]), alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.5, metalness: 0.35 }); break;
    // Vehicles.
    case "carpaint": {
      const car = new THREE.MeshPhysicalMaterial({ color: paint.wall < 0 ? 0xffffff : pick(CAR_PAINTS, paint.wall), roughness: 0.45, metalness: 0.2, clearcoat: 1, clearcoatRoughness: 0.05 });
      if (skyEnv) car.envMap = skyEnv;
      glassMats.add(car);
      m = w(car);
      break;
    }
    case "carglass": m = sheen({ color: 0x0b0e12, roughness: 0.04, metalness: 0.1 }); break;
    case "rubber": m = w(plain(0x1a1b1d, 0.65)); break;
    case "chrome": m = w(plain(0xd8dce0, 0.12, 1)); break;
    case "rim": m = w(plain(0xc8ccd0, 0.32, 0.6)); break;
    case "tyre": m = w(plain(0x262628, 0.9)); break;
    case "plate": m = w(plain(0xe8e6dc, 0.4)); break;
    case "cargo": m = w(plain(0xe6e6e2, 0.5, 0.2)); break;
    case "headlight":
      m = plain(0xf4f2ea, 0.1, 0.3, { emissive: 0xfff2d0, emissiveIntensity: 0 });
      if (variant === "traffic") m.userData.night = 3;
      break;
    case "taillight":
      m = plain(0x7a0e0c, 0.25, 0, { emissive: 0xff2010, emissiveIntensity: 0 });
      if (variant === "traffic") Object.assign(m.userData, { night: 2.2, day: 0.15 });
      break;
    case "taxisign":
      m = plain(0xffd040, 0.4, 0, { emissive: 0xffd040, emissiveIntensity: 0 });
      if (variant === "traffic") Object.assign(m.userData, { night: 1.6, day: 0.2 });
      break;
    case "led":
      m = plain(0x2a1400, 0.4, 0, { emissive: 0xffa020, emissiveIntensity: 0 });
      if (variant === "traffic") Object.assign(m.userData, { night: 1.8, day: 0.5 });
      break;
    case "glass": m = room("home"); break;
    case "shopglass": m = room("shop"); break;
    case "doorglass": m = room("lobby"); break;
    default: m = plain(0xff00ff);
  }
  if (damage && !role.endsWith("glass")) (m as THREE.MeshStandardMaterial).color.multiplyScalar(shade);
  m.userData.real = true;
  cache.set(key, m);
  return m;
}
