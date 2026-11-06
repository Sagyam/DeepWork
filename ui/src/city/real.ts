// City theme: the realistic models (ui/blender/real, docs/models.md), which
// replace the low-poly kit's styles one model at a time. `bun run models`
// writes public/models/: <id>.glb (pieces as nodes, materials named by
// role), <id>_ao.png (AO baked on the lightmap UVs) and tex/, the shared
// texture library. Any model that is missing falls back to the kit. Release
// builds download them instead (models.ts), so the base is set at startup.
//
// This module loads the models and owns their materials: PBR from the
// library with baked AO and world-space weathering, and window glass that
// shows a room behind it (interior.ts). models.ts stacks the pieces.
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { KTXLoader } from "three/examples/jsm/loaders/KTXLoader.js";
import { glass, interiorUniforms, type RoomKind } from "./interior";
import type { Kind } from "./plan";

export { interiorUniforms };

let BASE = `${import.meta.env.BASE_URL}models/`;
/** Whether PNGs sit beside the BC7 files; the downloaded pack has none. */
let hasPng = true;

/** Where the models load from (models.ts); call before loadReal. */
export function useModels(base: string, png: boolean) {
  BASE = base;
  hasPng = png;
}

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
  /**
   * Pieces bottom to top for `floors` storeys, without the roof if not `roof`;
   * `total` is the finished building's storeys, for models whose stack
   * depends on it (a setback) while it is being built or is damaged.
   */
  stack(floors: number, roof: boolean, r: () => number, total: number): { piece: string; y: number }[];
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
const A2_G = 5.6;
const A2_FL = 3.3;
const A2_TF = 3.1;
const C1_PLATE = 6.1;
const C2_PLATE = 4.0;
const C3_G = 3.3;
const C3_TOP = 6.3;
const C4_TOP = 3.35;
const C4_RIDGE = 7.8;
const S1_G = 4.45;
const S1_FL = 3.3;
const S2_G = 4.5;
const S2_F1 = 3.3;
const S2_F2 = 3.2;
/** S2's frieze, cornice and roof above its top storey: the slates start 1.04 m up, the stacks top out 4.8 m up. */
const S2_EAVES = 1.04;
const S3_TOP = 3.36;
const S4_TOP = 5.3;
const A3_G = 3.2;
const A3_FL = 2.9;
const O1_G = 5.4;
const O1_FL = 3.6;
/** Where O1 steps back: after about two thirds of its storeys, never at the top. */
const o1Lower = (total: number) => Math.min(total - 1, Math.max(2, Math.round(total * 0.68)));
const L1_G = 6.0;
const L1_FL = 3.5;
/** L1's crown above its top storey: the lit stages to 12.8 m, the spire to 29.6 m. */
const L1_CROWN = 12.8;

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
  a2: {
    id: "a2",
    kind: "apartment",
    style: "townhouse",
    // Three houses wall to wall, the stoops in front.
    w: 15.6,
    d: 13.63,
    front: 0.8,
    // Storeys over the garden storey: the parlour, typical storeys, the top storey.
    floors: (plan) => Math.min(4, Math.max(3, plan)),
    stack(floors, roof) {
      const out = floors > 0 ? [{ piece: "ground", y: 0 }] : [];
      let y = A2_G;
      for (let f = 2; f < floors; f++, y += A2_FL) out.push({ piece: "floor", y });
      if (floors > 1) out.push({ piece: "top", y });
      if (floors > 1 && roof) out.push({ piece: "roof", y: y + A2_TF });
      return out;
    },
    top: (floors) => (floors > 1 ? A2_G + (floors - 2) * A2_FL + A2_TF : A2_G),
    height: (floors) => A2_G + (floors - 2) * A2_FL + A2_TF + 1.45,
    // The front stack on the first party wall.
    smoke: (floors) => new THREE.Vector3(-2.6, A2_G + (floors - 2) * A2_FL + A2_TF + 3.5, 1.08),
    debris: 0x6e4a3a,
  },
  a3: {
    id: "a3",
    kind: "apartment",
    // A1's sibling: the classic apartment with balconies.
    style: "classic",
    // The roof slab oversails the walls and the balconies in front.
    w: 15.6,
    d: 13.0,
    // A strip of lawn and the path to the entrance.
    front: 2.4,
    floors: (plan) => Math.min(8, Math.max(3, plan)),
    stack(floors, roof, r) {
      // The ground storey, typical storeys (two kinds, alternating from a random start), the roof.
      const out = floors > 0 ? [{ piece: "ground", y: 0 }] : [];
      const flip = r() < 0.5 ? 1 : 0;
      for (let f = 1; f < floors; f++) out.push({ piece: (f + flip) % 2 ? "floor_a" : "floor_b", y: A3_G + (f - 1) * A3_FL });
      if (roof) out.push({ piece: "roof", y: A3_G + (floors - 1) * A3_FL });
      return out;
    },
    top: (floors) => A3_G + (floors - 1) * A3_FL,
    // The roof slab; the bulkhead and the aerials stand higher.
    height: (floors) => A3_G + (floors - 1) * A3_FL + 0.47,
    debris: 0xd8d4c8,
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
  c2: {
    id: "c2",
    kind: "cottage",
    style: "classic",
    w: 12.4,
    d: 9.7,
    front: 3.0,
    floors: () => 2,
    // One storey and the loft under the hip: the body to the wall plate, then the roof.
    stack: (floors, roof) => [...(floors > 0 ? [{ piece: "body", y: 0 }] : []), ...(roof ? [{ piece: "roof", y: C2_PLATE }] : [])],
    top: () => C2_PLATE,
    height: () => 7.9,
    smoke: () => new THREE.Vector3(0.45, 9.4, -0.125),
    debris: 0x8a4e3c,
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
  c4: {
    id: "c4",
    kind: "cottage",
    style: "aframe",
    w: 8.6,
    d: 12,
    front: 1.5,
    floors: () => 2,
    // The body stops at the loft floor; the roof is the rest of the A.
    stack: (floors, roof) => [...(floors > 0 ? [{ piece: "body", y: 0 }] : []), ...(roof ? [{ piece: "roof", y: C4_TOP }] : [])],
    top: () => C4_TOP,
    height: () => C4_RIDGE + 0.2,
    smoke: () => new THREE.Vector3(-1.0, C4_RIDGE + 0.8, -3.38),
    debris: 0x8a6a4c,
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
  s2: {
    id: "s2",
    kind: "shop",
    style: "classic",
    // The block with its cornice all round; the oriel and balconettes stay inside it.
    w: 11.1,
    d: 12.6,
    // A terrace of umbrella tables between the café and the pavement.
    front: 3.2,
    floors: (plan) => Math.min(3, Math.max(2, plan)),
    stack(floors, roof) {
      // The café, the piano nobile, the top storey if there is one, the roof.
      const out = floors > 0 ? [{ piece: "ground", y: 0 }] : [];
      if (floors > 1) out.push({ piece: "first", y: S2_G });
      if (floors > 2) out.push({ piece: "second", y: S2_G + S2_F1 });
      if (roof) out.push({ piece: "roof", y: DEFS.s2.top(floors) });
      return out;
    },
    top: (floors) => S2_G + (floors > 1 ? S2_F1 : 0) + (floors > 2 ? S2_F2 : 0),
    height: (floors) => DEFS.s2.top(floors) + 4.8,
    // The front stack on the party wall.
    smoke: (floors) => new THREE.Vector3(-4.55, DEFS.s2.top(floors) + S2_EAVES + 3.75, 2.4),
    debris: 0xd8c8a8,
  },
  s3: {
    id: "s3",
    kind: "shop",
    style: "diner",
    // The body and the kitchen behind, eaves to eaves; the pylon stands in front, on the forecourt.
    w: 14.2,
    d: 10.4,
    front: 3.4,
    floors: () => 1,
    stack: (floors, roof) => [...(floors > 0 ? [{ piece: "body", y: 0 }] : []), ...(roof ? [{ piece: "roof", y: S3_TOP }] : [])],
    top: () => S3_TOP,
    height: () => 5.45,
    // The kitchen's exhaust fan.
    smoke: () => new THREE.Vector3(-1.2, 4.05, -3.4),
    debris: 0xb4b8bc,
  },
  s4: {
    id: "s4",
    kind: "shop",
    style: "factory",
    // The shed and its loading dock, the boiler house and the stack beside it.
    w: 13.5,
    d: 10.4,
    // A concrete apron in front of the dock.
    front: 3.0,
    floors: () => 1,
    stack: (floors, roof) => [...(floors > 0 ? [{ piece: "body", y: 0 }] : []), ...(roof ? [{ piece: "roof", y: S4_TOP }] : [])],
    top: () => S4_TOP,
    // The sawtooth's gables; the stack rises to 17.3 m.
    height: () => 7.85,
    smoke: () => new THREE.Vector3(5.4, 17.6, 1.2),
    debris: 0x8a4e3c,
  },
  o1: {
    id: "o1",
    kind: "office",
    style: "classic",
    // The lower block; the colonnade is inside it, the plaza in front.
    w: 14.4,
    d: 11.2,
    front: 3.0,
    floors: (plan) => Math.max(6, plan),
    stack(floors, roof, _r, total) {
      // The lobby, the lower block's storeys, the terrace where it steps
      // back, the upper block's storeys, the roof.
      const lower = o1Lower(Math.max(total, floors));
      const out = floors > 0 ? [{ piece: "ground", y: 0 }] : [];
      for (let f = 1; f < floors; f++) {
        const y = O1_G + (f - 1) * O1_FL;
        if (f === lower) out.push({ piece: "setback", y });
        out.push({ piece: f < lower ? "floor" : "upper", y });
      }
      if (roof) out.push({ piece: "roof", y: O1_G + (floors - 1) * O1_FL });
      return out;
    },
    top: (floors) => O1_G + (floors - 1) * O1_FL,
    // The parapet, the lift overrun and plant; the mast goes 8 m higher.
    height: (floors) => O1_G + (floors - 1) * O1_FL + 4.4,
    debris: 0x5a6a70,
  },
  l1: {
    id: "l1",
    kind: "landmark",
    style: "deco",
    // 14.4 m square on a 1.8 m bay; the portal's step is inside the footprint.
    w: 14.4,
    d: 14.4,
    front: 0.8,
    floors: (plan) => Math.max(12, plan),
    stack(floors, roof, _r, total) {
      // Three tiers, stepping back at about half and four fifths of the
      // finished height (as the kit's deco tower does), a ledge piece where
      // each tier ends; the crown on top.
      const n = Math.max(total, floors);
      const e1 = Math.round(n * 0.5);
      const e2 = Math.round(n * 0.8);
      const out = floors > 0 ? [{ piece: "ground", y: 0 }] : [];
      let tier = 1;
      for (let f = 1; f < floors; f++) {
        const y = L1_G + (f - 1) * L1_FL;
        const t = f < e1 ? 1 : f < e2 ? 2 : 3;
        if (t !== tier) out.push({ piece: `ledge${tier}`, y });
        tier = t;
        out.push({ piece: `floor${t}`, y });
      }
      if (roof) out.push({ piece: "crown", y: L1_G + (floors - 1) * L1_FL });
      return out;
    },
    top: (floors) => L1_G + (floors - 1) * L1_FL,
    height: (floors) => L1_G + (floors - 1) * L1_FL + L1_CROWN,
    debris: 0xc8bca4,
  },
};

/**
 * Models that are not buildings: the props the city is dressed with
 * (vehicles, ...), each one glb of named pieces. Missing ones fall back to
 * the kit's props.
 */
export const PROPS = ["cars", "trees", "street", "bridge", "civic"];

// ---- compressed textures ------------------------------------------------------------
//
// Textures listed in models/bc7.json (scripts/textures.ts) load as BC7, which
// the GPU keeps compressed: a quarter of the memory of a decoded PNG. They are
// transcoded at build time, so loading one is a fetch, a gunzip (the
// browser's own DecompressionStream) and an upload: no worker, no WebAssembly.
// GPUs without BC7, and anything not listed, load PNG.

const packed = new Set<string>();
let bc7Ready: Promise<void> | null = null;

/** Reads the BC7 list once, if this GPU has BC7 (`renderer` tells). Any failure leaves everything PNG. */
function initBc7(renderer?: THREE.WebGLRenderer): Promise<void> {
  // ?png (dev): the PNGs, for comparing.
  if (!renderer || new URLSearchParams(location.search).has("png")) return Promise.resolve();
  if (!renderer.extensions.has("EXT_texture_compression_bptc") || typeof DecompressionStream === "undefined") return Promise.resolve();
  return (bc7Ready ??= (async () => {
    try {
      const r = await fetch(`${BASE}bc7.json`);
      if (r.ok) for (const n of (await r.json()) as string[]) packed.add(n);
    } catch {
      packed.clear();
    }
  })());
}

const ktx = new KTXLoader();

/**
 * Fills `t` (a CompressedTexture not yet uploaded: version 0) from a gzipped
 * BC7 KTX file. Its GPU storage is made once, at the right size, when it is.
 */
async function fillBc7(t: THREE.CompressedTexture, url: string) {
  const r = await fetch(url);
  if (!r.ok || !r.body) throw new Error(`${url}: ${r.status}`);
  const k = ktx.parse(await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer(), true);
  t.mipmaps = k.mipmaps;
  t.image = { width: k.width, height: k.height } as unknown as typeof t.image;
  // The files hold BC7 UNORM; the texture's colour space picks the sRGB variant.
  t.format = THREE.RGBA_BPTC_Format;
  t.minFilter = k.mipmaps.length > 1 && t.minFilter !== THREE.LinearFilter ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
  t.needsUpdate = true;
}

/** A texture to load: BC7 if it is listed (and this GPU has it), else the PNG. */
const isBc7 = (url: string) => packed.has(url.slice(BASE.length, -4));

/** Loads every model there is; missing ones are left to the kit. Never throws. `renderer` lets textures load compressed. */
export async function loadReal(ids = [...Object.keys(DEFS), ...PROPS], renderer?: THREE.WebGLRenderer): Promise<void> {
  await initBc7(renderer);
  // Without BC7 the pack has nothing to draw with: the kit it is.
  if (!hasPng && packed.size === 0) return;
  const png = new THREE.TextureLoader();
  const tex = {
    loadAsync: async (url: string): Promise<THREE.Texture> => {
      if (!isBc7(url)) return png.loadAsync(url);
      const t = new THREE.CompressedTexture([], 1, 1);
      try {
        await fillBc7(t, url.replace(/\.png$/, ".bc7"));
        return t;
      } catch (e) {
        console.warn("texture", url, e);
        return png.loadAsync(url);
      }
    },
  };
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
        if (id === "trees") for (const parts of pieces.values()) bendLeaves(parts);
        loaded.set(id, { pieces, ao });
      } catch {
        // Not built (bun run models) or not downloaded yet: the kit draws this style.
      }
    }),
  );
}

export const hasReal = (id: string) => loaded.has(id);

/** Leaf-card roles: alpha-tested, two-sided, normals bent out from the crown. */
const LEAVES = ["leaf", "smallleaf", "needles", "blossom", "bloom", "woods", "firs"];

/**
 * Points each leaf card's normals away from the middle of its crown (the
 * cards' bounding box), mostly: a crown then shades as one soft mass, lit
 * on the sun's side and dark underneath, instead of a heap of flat cards.
 */
function bendLeaves(parts: RealPart[]) {
  const leaves = parts.filter((p) => LEAVES.includes(p.role));
  if (!leaves.length) return;
  const box = new THREE.Box3();
  for (const { geo } of leaves) {
    geo.computeBoundingBox();
    box.union(geo.boundingBox!);
  }
  const c = box.getCenter(new THREE.Vector3());
  const half = box.getSize(new THREE.Vector3()).multiplyScalar(0.5).max(new THREE.Vector3(0.3, 0.3, 0.3));
  // Bend toward a point a little below the middle, so tops face the sky.
  c.y -= half.y * 0.25;
  const v = new THREE.Vector3();
  const n = new THREE.Vector3();
  for (const { geo } of leaves) {
    const pos = geo.getAttribute("position") as THREE.BufferAttribute;
    const nrm = geo.getAttribute("normal") as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).sub(c).divide(half).normalize();
      n.fromBufferAttribute(nrm, i);
      if (n.dot(v) < 0) n.negate();
      n.lerp(v, 0.8).normalize();
      nrm.setXYZ(i, n.x, n.y, n.z);
    }
    nrm.needsUpdate = true;
  }
}

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
export function tex(name: string, tile: [number, number] = [1, 1], color = true): THREE.Texture {
  const key = `${name}:${tile}`;
  let t = library.get(key);
  if (!t) {
    t = isBc7(`${BASE}tex/${name}.png`) ? compressed(`${BASE}tex/${name}`) : texLoader.load(`${BASE}tex/${name}.png`);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.flipY = false;
    t.repeat.set(1 / tile[0], 1 / tile[1]);
    t.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.anisotropy = 8;
    library.set(key, t);
  }
  return t;
}

/**
 * A BC7 texture as tex() hands out textures: at once, filled in when it has
 * loaded (materials share it before then; it is not drawn until then). If
 * the BC7 file fails, the PNG is decoded into it instead.
 */
function compressed(base: string): THREE.Texture {
  const t = new THREE.CompressedTexture([], 1, 1);
  fillBc7(t, `${base}.bc7`).catch(async (e) => {
    console.warn("texture", base, e);
    const img = await texLoader.loadAsync(`${base}.png`);
    const c = new OffscreenCanvas(img.image.width, img.image.height);
    const g = c.getContext("2d")!;
    g.drawImage(img.image, 0, 0);
    t.mipmaps = [{ data: new Uint8Array(g.getImageData(0, 0, c.width, c.height).data.buffer), width: c.width, height: c.height }] as unknown as typeof t.mipmaps;
    t.image = { width: c.width, height: c.height } as unknown as typeof t.image;
    t.format = THREE.RGBAFormat as unknown as THREE.CompressedPixelFormat;
    t.minFilter = THREE.LinearFilter;
    t.needsUpdate = true;
  });
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

const sheets = new Map<HTMLCanvasElement, THREE.Texture>();

/**
 * A texture of a shared sheet of signs. Each building gets its own (for its
 * offset and repeat), but they are clones of one, so they share one upload:
 * a new CanvasTexture each would upload the sheet again per building (60
 * copies of the shop signs, 640 MB, in the metropolis mock).
 */
function sheet(c: HTMLCanvasElement): THREE.Texture {
  let base = sheets.get(c);
  if (!base) sheets.set(c, (base = new THREE.CanvasTexture(c)));
  return base.clone();
}

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
  const t = sheet(signCanvas);
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
  const t = sheet(ghostCanvas);
  t.flipY = false;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(1, 0.25);
  t.offset.set(0, row * 0.25);
  t.anisotropy = 8;
  return t;
}

const TOWERS = ["MERIDIAN HOUSE", "ONE HARBOUR PLACE", "CARLTON TOWER", "NORTHBRIDGE CENTRE", "THE EXCHANGE", "ATLAS BUILDING", "200 PARK ROW", "SOVEREIGN HOUSE"];

let towerCanvas: HTMLCanvasElement | null = null;

/** Office buildings' names for the fascia, eight rows of 2048 x 128: spaced brushed-steel capitals on clear. */
function towerNames(row: number): THREE.Texture {
  if (!towerCanvas) {
    const c = (towerCanvas = document.createElement("canvas"));
    c.width = 2048;
    c.height = 1024;
    const g = c.getContext("2d")!;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.font = "500 64px 'Helvetica Neue', Helvetica, Arial, sans-serif";
    TOWERS.forEach((name, i) => {
      const y = i * 128 + 66;
      const text = name.split("").join(String.fromCharCode(8202, 8202, 8202));
      g.fillStyle = "rgba(10,10,12,0.9)";
      g.fillText(text, 1026, y + 3, 1400);
      const grad = g.createLinearGradient(0, y - 30, 0, y + 30);
      grad.addColorStop(0, "#f4f6f8");
      grad.addColorStop(0.5, "#b8bec4");
      grad.addColorStop(1, "#e2e6ea");
      g.fillStyle = grad;
      g.fillText(text, 1024, y, 1400);
    });
  }
  const t = sheet(towerCanvas);
  t.flipY = false;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(1, 0.125);
  t.offset.set(0, row * 0.125);
  t.anisotropy = 8;
  return t;
}

const DINERS = ["STARLITE DINER", "MOONBEAM DINER", "SILVER SPOON", "PARKWAY DINER", "NIGHT OWL DINER", "LUCKY 7 DINER", "COMET DINER", "SUNRISE DINER"];

let dinerCanvas: HTMLCanvasElement | null = null;

/** Diners' names for the frieze, eight rows of 2048 x 128: polished letters on clear, a diner shows one row. */
function dinerNames(row: number): THREE.Texture {
  if (!dinerCanvas) {
    const c = (dinerCanvas = document.createElement("canvas"));
    c.width = 2048;
    c.height = 1024;
    const g = c.getContext("2d")!;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.font = "italic 900 100px 'Arial Black', Impact, 'Helvetica Neue', sans-serif";
    DINERS.forEach((name, i) => {
      const y = i * 128 + 66;
      const text = name.split("").join(String.fromCharCode(8202));
      // A dark edge under the letters, then the polished face, lit from above.
      g.fillStyle = "rgba(20,20,22,1)";
      g.fillText(text, 1028, y + 5, 1900);
      const grad = g.createLinearGradient(0, y - 46, 0, y + 46);
      grad.addColorStop(0, "#ffffff");
      grad.addColorStop(0.48, "#d8dce0");
      grad.addColorStop(0.52, "#9aa0a8");
      grad.addColorStop(1, "#e8ecf0");
      g.fillStyle = grad;
      g.fillText(text, 1024, y, 1900);
    });
  }
  const t = sheet(dinerCanvas);
  t.flipY = false;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(1, 0.125);
  t.offset.set(0, row * 0.125);
  t.anisotropy = 8;
  return t;
}

const WORKS = [
  "HOLLIS & WARD · ENGINEERS",
  "BRANDT MACHINE WORKS",
  "NORTHGATE FOUNDRY CO.",
  "EAGLE SPRING & AXLE CO.",
  "MERCER BROS. · BOILERMAKERS",
  "UNION BOX & PAPER CO.",
  "CALDER WORSTED MILLS",
  "PARAGON CASTINGS LTD.",
];

let worksCanvas: HTMLCanvasElement | null = null;

/** Firms' names painted on a factory's frieze, eight rows of 2048 x 128: cream letters, weathered, on clear. */
function worksNames(row: number): THREE.Texture {
  if (!worksCanvas) {
    const c = (worksCanvas = document.createElement("canvas"));
    c.width = 2048;
    c.height = 1024;
    const g = c.getContext("2d")!;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.font = "800 96px Impact, 'Arial Black', 'Helvetica Neue', sans-serif";
    WORKS.forEach((name, i) => {
      g.fillStyle = "rgba(236,228,206,0.92)";
      g.fillText(name.split("").join(String.fromCharCode(8202)), 1024, i * 128 + 66, 1960);
    });
    // Weathered: the paint has flaked and washed out of the brick.
    g.globalCompositeOperation = "destination-out";
    let seed = 11;
    const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 14000; i++) {
      g.globalAlpha = 0.25 + rand() * 0.75;
      g.fillRect(rand() * 2048, rand() * 1024, 2 + rand() * 7, 2 + rand() * 4);
    }
    for (let i = 0; i < 120; i++) {
      g.globalAlpha = 0.1 + rand() * 0.3;
      g.fillRect(rand() * 2048, rand() * 1024, 4 + rand() * 12, 30 + rand() * 90);
    }
    g.globalCompositeOperation = "source-over";
  }
  const t = sheet(worksCanvas);
  t.flipY = false;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(1, 0.125);
  t.offset.set(0, row * 0.125);
  t.anisotropy = 8;
  return t;
}

const CAFES = ["CAFÉ DES ARTS", "CAFFÈ BELLAVISTA", "KAFFEEHAUS ROSE", "CAFÉ DU COIN", "CAFÉ AMADEUS", "CAFÉ LUMIÈRE", "CAFFÈ DEL CORSO", "CAFÉ NOVA"];

let cafeCanvas: HTMLCanvasElement | null = null;

/** Cafés' names in gilt serif capitals for a frieze, eight rows of 2048 x 128: gold with a dark edge, on clear. */
function cafeNames(row: number): THREE.Texture {
  if (!cafeCanvas) {
    const c = (cafeCanvas = document.createElement("canvas"));
    c.width = 2048;
    c.height = 1024;
    const g = c.getContext("2d")!;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.font = "700 98px Didot, 'Bodoni 72', Georgia, 'DejaVu Serif', 'Times New Roman', serif";
    CAFES.forEach((name, i) => {
      const y = i * 128 + 68;
      const text = name.split("").join(String.fromCharCode(8202, 8202));
      g.fillStyle = "rgba(40,28,10,0.9)";
      g.fillText(text, 1027, y + 4, 1960);
      const grad = g.createLinearGradient(0, y - 44, 0, y + 44);
      grad.addColorStop(0, "#fff2b0");
      grad.addColorStop(0.45, "#d8a83c");
      grad.addColorStop(0.55, "#a8761e");
      grad.addColorStop(1, "#e8c060");
      g.fillStyle = grad;
      g.fillText(text, 1024, y, 1960);
    });
  }
  const t = sheet(cafeCanvas);
  t.flipY = false;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(1, 0.125);
  t.offset.set(0, row * 0.125);
  t.anisotropy = 8;
  return t;
}

const DECOS = ["THE ORION BUILDING", "HALCYON TOWER", "CONTINENTAL LIFE", "THE ZENITH BUILDING", "STERLING TRUST", "AURORA TOWER", "MONARCH BUILDING", "THE BEACON BUILDING"];

let decoCanvas: HTMLCanvasElement | null = null;

/**
 * Art deco towers' names in gilt geometric capitals over the portal, eight
 * rows of 2048 x 128 for a 3.9 x 0.62 m panel: the letters are drawn
 * stretched 2.5 times across, so they come out in proportion on it.
 */
function decoNames(row: number): THREE.Texture {
  if (!decoCanvas) {
    const c = (decoCanvas = document.createElement("canvas"));
    c.width = 2048;
    c.height = 1024;
    const g = c.getContext("2d")!;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.font = "600 80px Futura, 'Century Gothic', 'Avenir Next', 'DejaVu Sans', sans-serif";
    const sx = 2.5;
    DECOS.forEach((name, i) => {
      const y = i * 128 + 66;
      const text = name.split("").join(String.fromCharCode(8202, 8202));
      g.save();
      g.scale(sx, 1);
      g.fillStyle = "rgba(30,20,8,0.9)";
      g.fillText(text, 1026 / sx, y + 3, 1940 / sx);
      const grad = g.createLinearGradient(0, y - 40, 0, y + 40);
      grad.addColorStop(0, "#fff0b8");
      grad.addColorStop(0.5, "#c8963a");
      grad.addColorStop(1, "#ecc66a");
      g.fillStyle = grad;
      g.fillText(text, 1024 / sx, y, 1940 / sx);
      g.restore();
    });
  }
  const t = sheet(decoCanvas);
  t.flipY = false;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(1, 0.125);
  t.offset.set(0, row * 0.125);
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
/** Slates: Welsh blue-grey, purple, Westmorland green, dark, silver-grey. */
const SLATES = [0xd8dce4, 0xd4c8d4, 0xc8d4c8, 0x9c9ea4, 0xeceae6];
/** Ridge rolls: red clay, blue-black, buff. */
const RIDGES = [0x9a4a32, 0x2e3034, 0x9a4a32, 0xb08a60];
/** Brownstone: chocolate, pinkish, dark, warm, umber. */
const BROWNSTONES = [0xffffff, 0xf4dcd0, 0xd4c8c0, 0xf0dcc4, 0xc0b4ac];
/** A2's cornices: brown, black, brownstone, dark green, cream. */
const ROW_CORNICES = [0x3a2c24, 0x1e2022, 0x6a5040, 0x26342a, 0xd8ccb4];
/** A2's sashes: cream, dark brown, black-green, white. */
const SASHES = [0xe9e4d8, 0x2e2520, 0x1e2a24, 0xf0eee8];
/** Front doors in heritage paint: black, Brunswick green, oxblood, navy, plum, ochre, teal. */
const HERITAGE = [0x1c1d1f, 0x1f3a2c, 0x5a1e1c, 0x1e2a44, 0x3e2638, 0xb07a2a, 0x2a5458];
/** S2's stucco: Schönbrunn yellow, ochre, salmon, sage, cream, terracotta, pale blue-grey, white. */
const STUCCO = [0xf6dc96, 0xeccb94, 0xf0c0a6, 0xd2dcc0, 0xf4e8d0, 0xdca07e, 0xd4dce2, 0xf6f2ea];
/** S2's shutters: green, grey-green, grey-blue, oxblood, dove grey, brown. */
const S2_SHUTTERS = [0x2e4a36, 0x6a7a68, 0x5a6a7a, 0x6a2a24, 0xa8aaa4, 0x5a4232];
/** Café parasols: cream, bordeaux, bottle green, navy, terracotta, white. */
const PARASOLS = [0xeee4cc, 0x7a1e26, 0x234a34, 0x23304e, 0xb8583a, 0xf4f2ec];
/** Render: white, warm white, pale grey, sand, anthracite, chalk. */
const RENDERS = [0xf6f4ee, 0xeee8da, 0xd8d6d0, 0xe8dcc6, 0x55585a, 0xf2f0ea];
/** A3's render: white, cream, pale primrose, pale sage, light ochre, pale pink-beige. */
const MID_RENDERS = [0xf4f2ec, 0xeee4cc, 0xf0e6b4, 0xd8dcc8, 0xe4cc9e, 0xeed6c8];
/** A3's panels, the 1960s' colours: tomato red, ochre, teal, sky blue, olive, charcoal. */
const INFILLS = [0xb4402e, 0xd2a03a, 0x2e7a78, 0x6a9cc4, 0x7a8a46, 0x3a3e42];
/** Timber cladding: larch, silver-weathered, charred, cedar, honey. */
const TIMBER = [0xe6b488, 0xc4c2bc, 0x4a4644, 0xd2905e, 0xf0cc96];
/** Window frames, copings and doors: anthracite (most), black, bronze. */
const FRAMES = [0x33373b, 0x1e1f21, 0x33373b, 0x6e5e4a, 0x40454a];
/** C4's boards: natural cedar, honey pine, walnut, barn red, weathered grey, forest green, whitewash. */
const STAINS = [0xd8a070, 0xeec890, 0x8a5c40, 0xb04c3a, 0xc0bab0, 0x7a9670, 0xf2ece0];
/** Cedar shakes: natural, silvered, dark-stained, red cedar, charcoal. */
const SHAKES = [0xd8b090, 0xc4c0b8, 0x8a7060, 0xc89078, 0x84807a];
/** C4's trim: dark brown, white, black, cream, barn red, forest green. */
const TRIMS = [0x3a2a20, 0xeeeae2, 0x1e1e1e, 0xe4d8bc, 0x7a2a22, 0x2e4234];
/** Front doors and deck chairs: red, mustard, teal, navy, orange, oiled wood. */
const BRIGHTS = [0xa02a22, 0xd09a2a, 0x2a6a6a, 0x24344e, 0xc8642a, 0x8a5a36];
/** S3's porcelain enamel: red, turquoise, royal blue, maroon, green, black. */
const ENAMELS = [0xa3202a, 0x1d8a88, 0x234f9c, 0x6a1c2a, 0x2a6e48, 0x1e1e20];
/** Neon: red, pink, blue, green, amber, white. */
const NEONS = [0xff2a1e, 0xff3c9a, 0x2a8cff, 0x30ff7a, 0xffa21e, 0xfff0e0];
/** S4's steelwork (windows, beams, canopy): black, works green, grey, oxide red, cream, blue-grey. */
const STEELS = [0x1e2022, 0x2c4436, 0x5a5e62, 0x6a2a20, 0xd8d2c0, 0x34465a];
/** S4's timber doors: green, oxblood, brown, blue, grey. */
const WORKS_DOORS = [0x3a5a40, 0x6a2620, 0x5a3e2a, 0x2e4a66, 0x7a7c78];
/** Corrugated sheet: weathered galvanising (most), grey paint, oxide red, green, dark grey. */
const SHEETS = [0xe4e4e0, 0xd4d4d0, 0xc4c6c4, 0xc87860, 0x9ab49a, 0x8a8e92];
/** O1's glass: blue-green, blue, bronze, neutral grey, green, silver-blue. */
const OFFICE_GLASS = [0x7fb2aa, 0x7f9cc4, 0xb89a74, 0x949aa0, 0x86b48e, 0xb4c4d0];
/** O1's metalwork: silver, dark bronze, black, champagne, white, mid grey. */
const MULLIONS = [0xb8bcc0, 0x4a3e34, 0x1e2022, 0xc8b894, 0xe8e8e4, 0x7a8086];
/** L1's limestone: Indiana buff, pale grey, cream, warm pink, silver-grey, ivory. */
const LIMESTONES = [0xf4ead8, 0xdcdcd8, 0xfff4dc, 0xf0d4c4, 0xc8ccd0, 0xfffaf0];
/** L1's metalwork, frames to spandrels: statuary bronze, aluminium, verdigris, nickel, black, light bronze. */
const DECO_METALS = [0x8a6440, 0xc4c8cc, 0x6a8a76, 0xdcd8cc, 0x2e2e30, 0xb08a5a];
/** Foliage tints over the leaf textures: mid greens, a dark one, a yellow-green, a blue-green. */
const FOLIAGE = [0xd6e2c4, 0xbcd0a8, 0xe8ecc0, 0xa8bc98, 0xc8dcc8, 0xdce8b0];
/** Car paint, as on real roads: white, black, silvers and greys most; then blue, red, green, beige, burgundy. */
export const CAR_PAINTS = [0xeceae6, 0x16181b, 0xa9adb1, 0x5c6066, 0xeceae6, 0x1f3550, 0x9c1f22, 0x2e4a3c, 0xb8ab90, 0x5a1c26, 0x7e8a94, 0x16181b];

const cache = new Map<string, THREE.Material>();
/** Glass and lamps, which follow the time of day (see City.light). */
const glassMats = new Set<THREE.MeshStandardMaterial>();
let skyEnv: THREE.Texture | null = null;

/** The sky the realistic glass reflects; set by the scene when the light changes. */
export function setRealEnv(env: THREE.Texture) {
  skyEnv = env;
  for (const m of glassMats) {
    m.envMap = env;
    m.needsUpdate = true;
  }
}

// ---- water ------------------------------------------------------------------------

/** The clock every water surface and fountain spray runs on; see setWaterTime. */
export const waterUniforms = { uTime: { value: 0 } };
/** Moves the water on: call every frame with the time in seconds. */
export function setWaterTime(t: number) {
  waterUniforms.uTime.value = t;
}

const WATER_NOISE = /* glsl */ `
  float wHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float wNoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(wHash(i), wHash(i + vec2(1, 0)), f.x), mix(wHash(i + vec2(0, 1)), wHash(i + vec2(1, 1)), f.x), f.y);
  }
  // Slope (d/dx, d/dz) of a wave of direction d, wavenumber k, amplitude a, speed w.
  vec2 wWave(vec2 p, vec2 d, float k, float a, float w) { return d * (a * k * cos(dot(d, p) * k + uTime * w)); }
`;

const waterCache = new Map<string, THREE.MeshStandardMaterial>();
/**
 * Moving water, all in the shader: level surfaces ripple (waves summed in
 * world space, flowing toward +z, small ones fading with distance so they do
 * not shimmer; `ring` adds rings spreading from a point, where a fountain's
 * water lands), steep ones (a fountain's jet and falling streams) run with
 * white streaks. The sky is in it at grazing angles (fresnel, from the
 * environment map). `amp` scales the waves, `scale` their size (2 is half
 * as big). `userData.water` marks it for day and night tints.
 */
export function waterMat(o: { amp?: number; scale?: number; ring?: [number, number]; color?: number } = {}): THREE.MeshStandardMaterial {
  const { amp = 1, scale = 1, ring, color = 0x173238 } = o;
  const key = `${amp}:${scale}:${ring}:${color}`;
  let m = waterCache.get(key);
  if (m) return m;
  m = new THREE.MeshStandardMaterial({ color, roughness: 0.2, metalness: 0, envMapIntensity: 0.3 });
  if (skyEnv) m.envMap = skyEnv;
  glassMats.add(m);
  m.userData.water = true;
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = waterUniforms.uTime;
    sh.uniforms.uAmp = { value: amp };
    sh.uniforms.uScale = { value: scale };
    sh.uniforms.uRing = { value: new THREE.Vector3(ring?.[0] ?? 0, ring?.[1] ?? 0, ring ? 1 : 0) };
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vWW;\nvarying vec3 vWN;")
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\nvWW = (modelMatrix * vec4(transformed, 1.0)).xyz;\nvWN = normalize(mat3(modelMatrix) * objectNormal);");
    sh.fragmentShader = sh.fragmentShader
      .replace("#include <common>", `#include <common>\nuniform float uTime;\nuniform float uAmp;\nuniform float uScale;\nuniform vec3 uRing;\nvarying vec3 vWW;\nvarying vec3 vWN;\n${WATER_NOISE}`)
      .replace(
        "#include <map_fragment>",
        `#include <map_fragment>
        float wSteep = 1.0 - smoothstep(0.55, 0.8, abs(vWN.y));
        if (wSteep > 0.0) {
          // Falling water: white streaks running down, broken up round the stream.
          vec2 sp = vec2(dot(vWW.xz, vec2(7.0, 5.0)), vWW.y * 3.0 + uTime * 5.0);
          float streak = wNoise(sp) * 0.65 + wNoise(sp * 2.7) * 0.35;
          // Broken into falling sheets, not a solid rod.
          if (wSteep > 0.5 && streak < 0.47) discard;
          diffuseColor.rgb = mix(diffuseColor.rgb, mix(vec3(0.55, 0.68, 0.72), vec3(0.95), smoothstep(0.35, 0.8, streak)), wSteep);
        }`,
      )
      .replace(
        "#include <normal_fragment_maps>",
        `#include <normal_fragment_maps>
        if (wSteep < 1.0) {
          vec2 p = vWW.xz * uScale;
          float far = smoothstep(260.0 / uScale, 30.0 / uScale, distance(cameraPosition, vWW));
          vec2 g = wWave(p, normalize(vec2(0.15, 1.0)), 0.31, 0.06, 0.8)
                 + wWave(p, normalize(vec2(0.15, 1.0)), 0.47, 0.05, 1.1)
                 + wWave(p, normalize(vec2(-0.45, 1.0)), 0.83, 0.03, 1.7)
                 + wWave(p, normalize(vec2(0.75, 0.66)), 1.37, 0.018, 2.3) * (0.4 + 0.6 * far)
                 + wWave(p, normalize(vec2(-0.9, 0.43)), 2.29, 0.011, 3.1) * far
                 + wWave(p, normalize(vec2(0.31, -0.95)), 3.71, 0.007, 3.9) * far
                 + wWave(p, normalize(vec2(0.98, 0.2)), 5.93, 0.004, 4.8) * far
                 + wWave(p, normalize(vec2(-0.2, -0.98)), 8.77, 0.003, 6.1) * far;
          g *= uAmp;
          if (uRing.z > 0.0) {
            // Rings spreading from where the water lands, fading outward.
            vec2 d = vWW.xz - uRing.xy;
            float r = max(length(d), 0.001);
            vec2 dir = d / r;
            g += dir * (0.09 * 7.0 * cos(r * 7.0 - uTime * 6.0) + 0.05 * 11.0 * cos(r * 11.0 - uTime * 8.5 + 1.3)) * exp(-r * 0.35);
          }
          vec3 wn = normalize(vec3(-g.x, 1.0, -g.y));
          normal = normalize(mix(normal, (viewMatrix * vec4(wn, 0.0)).xyz, 1.0 - wSteep));
        }`,
      );
  };
  m.customProgramCacheKey = () => "water";
  waterCache.set(key, m);
  return m;
}

/**
 * A fountain's spray, drawn by the GPU alone (no per-frame work): the jet
 * from the top falls back into the upper basin, and eight streams arc from
 * the upper basin's rim into the lower one, as the kit fountain shows them.
 * `x, y, z` is the fountain's foot, `s` its scale.
 */
export function fountainSpray(x: number, y: number, z: number, s: number): THREE.Points {
  const N = 1400;
  const p0 = new Float32Array(N * 3);
  const v = new Float32Array(N * 3);
  const life = new Float32Array(N * 2);
  const r = (k: number) => {
    const t = Math.sin(k * 12.9898) * 43758.5453;
    return t - Math.floor(t);
  };
  const g = 9.8;
  for (let i = 0; i < N; i++) {
    let px: number, py: number, pz: number, vx: number, vy: number, vz: number, T: number;
    if (i < N * 0.45) {
      // The jet: up from the top, falling back on the upper basin.
      const a = r(i + 1) * Math.PI * 2;
      const spread = 0.25 + r(i + 2) * 0.5;
      [px, py, pz] = [0, 4.35 * s, 0];
      [vx, vy, vz] = [Math.cos(a) * spread, 3.6 + r(i + 3) * 1.2, Math.sin(a) * spread];
      const h = py - 2.25 * s;
      T = (vy + Math.sqrt(vy * vy + 2 * g * h)) / g;
    } else {
      // The streams: from the upper basin's rim, out and down into the lower basin.
      const k = Math.floor(r(i + 4) * 8);
      const a = (k / 8) * Math.PI * 2 + (r(i + 5) - 0.5) * 0.12;
      const [ra, rb] = [1.12 * s, (1.45 + r(i + 6) * 0.3) * s];
      [px, py, pz] = [Math.cos(a) * ra, 2.24 * s, Math.sin(a) * ra];
      T = 0.42 + r(i + 7) * 0.12;
      const drop = 2.24 * s - 0.62 * s;
      [vx, vy, vz] = [(Math.cos(a) * (rb - ra)) / T, (-drop + 0.5 * g * T * T) / T, (Math.sin(a) * (rb - ra)) / T];
    }
    p0.set([px, py, pz], i * 3);
    v.set([vx, vy, vz], i * 3);
    life.set([T, r(i + 8)], i * 2);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(p0, 3));
  geo.setAttribute("aVel", new THREE.BufferAttribute(v, 3));
  geo.setAttribute("aLife", new THREE.BufferAttribute(life, 2));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: waterUniforms.uTime, uSize: { value: 0.09 }, uBright: { value: 1 } },
    transparent: true,
    depthWrite: false,
    vertexShader: /* glsl */ `
      uniform float uTime;
      uniform float uSize;
      attribute vec3 aVel;
      attribute vec2 aLife;
      varying float vFade;
      void main() {
        float t = mod(uTime + aLife.y * aLife.x * 7.0, aLife.x);
        vec3 p = position + aVel * t + vec3(0.0, -4.9 * t * t, 0.0);
        vFade = smoothstep(0.0, 0.08, t) * (1.0 - smoothstep(0.8, 1.0, t / aLife.x));
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = uSize * 900.0 / -mv.z;
      }`,
    fragmentShader: /* glsl */ `
      uniform float uBright;
      varying float vFade;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        gl_FragColor = vec4(vec3(0.9, 0.95, 1.0) * uBright, (1.0 - d * 2.0) * 0.55 * vFade);
        #include <colorspace_fragment>
      }`,
  });
  const pts = new THREE.Points(geo, mat);
  pts.position.set(x, y, z);
  pts.frustumCulled = false;
  pts.userData.spray = true;
  return pts;
}

/** Signal lenses, by role and phase ("a" or "b": the two roads at a crossing); see setSignals. */
const signals: { m: THREE.MeshStandardMaterial; role: string; phase: string }[] = [];
const LENS: Record<string, number> = { sig_red: 0xff2a1a, sig_amber: 0xffa21a, sig_green: 0x3aff8a, ped_red: 0xff3a1a, ped_white: 0xf4f0e6 };

/**
 * Runs the traffic signals: a 30 s cycle in which road "a" gets green,
 * amber, then red while road "b" waits, and the other way round; the
 * walk signal shows white across the road that has red. `night` (0-1)
 * brightens the lit lenses.
 */
export function setSignals(t: number, night = 0) {
  const T = 30;
  const c = ((t % T) + T) % T;
  const lit = (phase: string) => {
    const k = phase === "a" ? c : (c + T / 2) % T;
    return k < 12 ? "green" : k < 15 ? "amber" : "red";
  };
  for (const { m, role, phase } of signals) {
    const state = lit(phase);
    const on = role === "ped_white" ? state === "red" : role === "ped_red" ? state !== "red" : role === `sig_${state}`;
    m.emissiveIntensity = on ? 2.2 + 3 * night : 0;
  }
}

/**
 * Leaf cards: the cluster texture alpha-tested, both sides lit as the front
 * (the normals are bent out from the crown, see bendLeaves), baked AO.
 */
function foliage(name: string, color: number, ao: THREE.Texture): THREE.MeshStandardMaterial {
  const m = new THREE.MeshStandardMaterial({ map: tex(`${name}_col`), color, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.78, aoMap: ao, aoMapIntensity: 0.55 });
  m.onBeforeCompile = (sh) => {
    sh.fragmentShader = sh.fragmentShader
      .replace("#include <normal_fragment_begin>", THREE.ShaderChunk.normal_fragment_begin.replace("normal *= faceDirection;", ""))
      // A card seen edge-on smears its leaves into streaks and gives the
      // crown away as flat sheets: thin it out as it turns edge-on (its true
      // face, from the screen-space derivatives; the normals are bent).
      .replace(
        "#include <alphatest_fragment>",
        "vec3 cardN = normalize(cross(dFdx(vViewPosition), dFdy(vViewPosition)));\ndiffuseColor.a *= smoothstep(0.05, 0.25, abs(dot(cardN, normalize(vViewPosition))));\n#include <alphatest_fragment>",
      );
  };
  m.customProgramCacheKey = () => "foliage";
  return m;
}

/**
 * A tiling ground material (grass, paving, asphalt) mapped by world x / z,
 * so boxes of any size share it without UVs of their own; `tile` in metres.
 */
export function groundMat(name: string, tile: number, opts: Std & { normal?: number } = {}): THREE.MeshStandardMaterial {
  const key = `ground:${name}:${tile}:${JSON.stringify(opts)}`;
  let m = cache.get(key) as THREE.MeshStandardMaterial | undefined;
  if (m) return m;
  const { normal = 1, ...rest } = opts;
  m = new THREE.MeshStandardMaterial({ map: tex(`${name}_col`), normalMap: tex(`${name}_nrm`, [1, 1], false), roughness: 0.9, ...rest });
  m.normalScale.set(normal, -normal);
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uTile = { value: 1 / tile };
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nuniform float uTile;")
      .replace("#include <uv_vertex>", "#include <uv_vertex>\nvec2 gUv = (modelMatrix * vec4(position, 1.0)).xz * uTile;\nvMapUv = gUv;\nvNormalMapUv = gUv;");
  };
  m.customProgramCacheKey = () => "ground";
  m.userData.real = true;
  cache.set(key, m);
  return m;
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
  const tinted = ["brick", "bluebrick", "rubbed", "steelframe", "doors", "corrugated", "works", "siding", "shutter", "shopframe", "door", "shingle", "sign", "cornice", "ghost", "render", "cladding", "alu", "shake", "boards", "timber", "chair", "enamel", "neon", "neon2", "dinername", "carpaint", "slate", "ridge", "rustic", "cafename", "parasol", "officeglass", "spandrel", "mullion", "blades", "towername", "cladstone", "floodstone", "deco", "bronze", "deconame", "brownstone", "door2", "door3", "infill", ...LEAVES, "hedge"].includes(role) || (id === "a2" && role === "frame");
  const key = `${id}:${role}:${damage}:${variant}:${tinted ? `${paint.wall}:${paint.accent}:${paint.roof}:${paint.signs}` : ""}`;
  let m = cache.get(key);
  if (m) return m;
  const ao = loaded.get(id)!.ao;
  const shade = [1, 0.72, 0.42][Math.min(2, damage)];
  const w = (mat: THREE.MeshStandardMaterial, weather = 0) => weathered(mat, ao, weather + damage * 0.8);
  const room = (kind: RoomKind, tint?: number) => {
    const g = glass(kind, damage / 2, tint);
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
    // The factory.
    case "bluebrick": m = w(pbr("brick", [1.72, 1.8], { rough: true, color: 0x50566e }), 1.2); break;
    case "rubbed": m = w(plain(new THREE.Color(0xa04a32).multiply(new THREE.Color(pick(BRICK_TINTS, paint.wall))).getHex(), 0.85), 1.6); break;
    case "steelframe": m = w(plain(pick(STEELS, paint.accent), 0.5, 0.3), 1); break;
    case "doors": m = w(pbr("boards", [1.4, 1.4], { roughness: 0.75, color: pick(WORKS_DOORS, paint.accent + 1) }), 1.2); break;
    case "copper": m = w(plain(0x5a8a74, 0.6, 0.4)); break;
    // Weathered sheet is dull: no sky in it, or it reads as glass from above.
    case "corrugated": m = w(pbr("corrugated", [1.52, 2.4], { rough: true, metalness: 0.15, color: pick(SHEETS, paint.roof) }), 1.4); break;
    case "northlight":
      // Wired glass up in the roof: the sky by day, the shop floor's lamps by night.
      m = sheen({ color: 0x2a3236, roughness: 0.18, emissive: 0xe8d8b4, emissiveIntensity: 0 });
      if (damage < 2) m.userData.night = 0.22;
      break;
    case "works":
      m = new THREE.MeshStandardMaterial({ map: worksNames(paint.signs), transparent: true, opacity: 0.85, roughness: 0.9, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      break;
    case "ashlar": m = w(pbr("ashlar", [2.4, 1.8], { roughness: 0.85 }), 1.4); break;
    case "granite": m = w(new THREE.MeshStandardMaterial({ map: tex("granite_col"), roughness: 0.5 }), 0.5); break;
    case "roof": m = w(pbr("roof", [4, 4], { roughness: 0.92 }), 1); break;
    case "wood": m = w(pbr("wood", [1.2, 1.2], { roughness: 0.9 }), 0.8); break;
    case "deck": m = w(pbr("wood", [1.2, 1.2], { roughness: 0.8, color: 0xb8c0c4 }), 0.6); break;
    case "concrete": m = w(pbr("stone", [2, 2], { color: 0xb8b8b4, roughness: 0.95 }), 1); break;
    case "siding": m = w(pbr("siding", [2.4, 1.2], { rough: true, color: pick(SIDING, paint.wall) }), 0.7); break;
    case "shingle": m = w(pbr("shingle", [2, 1.12], { roughness: 0.95, color: pick(SHINGLES, paint.roof) }), 0.8); break;
    case "shutter": m = w(pbr("louvre", [1, 1], { roughness: 0.55, color: id === "s2" ? pick(S2_SHUTTERS, paint.wall + paint.roof) : accent })); break;
    case "trim": m = w(plain(0xeeebe2, 0.55), 0.5); break;
    case "cornice": m = w(plain(pick(id === "a2" ? ROW_CORNICES : CORNICES, paint.roof), 0.5, 0.2), 1.2); break;
    case "brownstone": m = w(pbr("brownstone", [2.4, 1.8], { rough: true, color: pick(BROWNSTONES, paint.wall) }), 1.5); break;
    case "paint": m = w(plain(0xf0ede4, 0.6), 0.6); break;
    case "ceiling": m = w(plain(0xb4d4d2, 0.6)); break;
    case "gutter": m = w(plain(0xe4e2dc, 0.4, 0.3)); break;
    case "frame": m = w(plain(id === "c1" ? 0xf2efe8 : id === "a2" ? pick(SASHES, paint.roof) : 0xe9e4d8, 0.42)); break;
    case "shopframe": m = w(plain(accent, 0.35)); break;
    case "door": m = w(plain(id === "c1" ? accent : id === "c3" ? frame : id === "c4" ? pick(BRIGHTS, paint.accent + paint.wall) : id === "c2" || id === "a2" ? pick(HERITAGE, paint.accent) : 0x3a2216, 0.38)); break;
    // A2's other two houses.
    case "door2": m = w(plain(pick(HERITAGE, paint.accent + 2), 0.38)); break;
    case "door3": m = w(plain(pick(HERITAGE, paint.accent + 5), 0.38)); break;
    case "render": m = w(pbr("render", [3, 3], { roughness: 0.9, normal: 0.6, color: id === "s2" ? pick(STUCCO, paint.wall) : id === "a3" ? pick(MID_RENDERS, paint.wall) : pick(RENDERS, paint.wall) }), id === "s2" ? 1.2 : id === "a3" ? 0.45 : 0.4);
      // A3's walls sit deep between balconies: the bake over-darkens them against the bounce they would get.
      if (id === "a3") (m as THREE.MeshStandardMaterial).aoMapIntensity = 0.55;
      break;
    // A3's coloured panels under the windows and up the stair band.
    case "infill": m = w(plain(pick(INFILLS, paint.accent), 0.45), 0.5); break;
    // Roller shutters let down in the windows: grey blades.
    case "roller": m = w(pbr("blades", [1, 1], { roughness: 0.6, metalness: 0.1, color: 0xd4d2cc }), 0.6); break;
    // Frosted glass in the balcony rails: sky in it, a little see-through.
    case "railglass": {
      const g = new THREE.MeshPhysicalMaterial({ color: 0xa8c4be, roughness: 0.2, ior: 1.5, transparent: true, opacity: 0.32, side: THREE.DoubleSide, depthWrite: false });
      if (skyEnv) g.envMap = skyEnv;
      g.userData.noShadow = true;
      glassMats.add(g);
      m = g;
      break;
    }
    // S2's banded rustication: the stucco a shade deeper.
    case "rustic": m = w(pbr("rustic", [3, 1.2], { roughness: 0.88, normal: 0.9, color: new THREE.Color(pick(STUCCO, paint.wall)).multiplyScalar(0.92).getHex() }), 1.4); break;
    case "parasol": m = w(plain(pick(PARASOLS, paint.accent + paint.signs), 0.9)); break;
    case "cane": m = w(plain(0xc8a46a, 0.85)); break;
    case "cafename": {
      const t = cafeNames(paint.signs);
      m = new THREE.MeshStandardMaterial({ map: t, alphaTest: 0.5, roughness: 0.3, metalness: 0.7, emissive: 0xffe0a0, emissiveMap: t, emissiveIntensity: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      if (damage < 2) m.userData.night = 0.3;
      break;
    }
    case "cladding": m = w(pbr("battens", [1.3, 1.3], { roughness: 0.8, color: pick(TIMBER, paint.accent) }), 0.4); break;
    case "alu": m = w(plain(id === "a3" ? pick(MULLIONS, paint.roof) : frame, 0.4, 0.5)); break;
    case "shake": m = w(pbr("shake", [1.5, 1.5], { roughness: 0.92, color: pick(SHAKES, paint.roof) }), 0.9); break;
    case "boards": m = w(pbr("boards", [1.4, 1.4], { roughness: 0.82, color: pick(STAINS, paint.wall) }), 0.6); break;
    case "timber": m = w(plain(pick(TRIMS, paint.accent), 0.6)); break;
    case "slate": m = w(pbr("slate", [2, 1.2], { rough: true, color: pick(SLATES, paint.roof) }), 0.7); break;
    case "ridge": m = w(plain(pick(RIDGES, paint.roof + 1), 0.7), 0.6); break;
    case "lead": m = w(plain(0x6e7276, 0.55, 0.3), 0.8); break;
    case "chair": m = w(plain(pick(BRIGHTS, paint.accent + paint.wall + 2), 0.55)); break;
    case "logend": m = w(plain(0xc8a478, 0.9)); break;
    case "stainless":
    case "fluted": {
      // Polished metal shows what it reflects: the sky, like the glass.
      const steel = role === "fluted" ? pbr("fluted", [1, 0.4], { rough: true, metalness: 1 }) : plain(0xd8dce0, 0.22, 1);
      if (skyEnv) steel.envMap = skyEnv;
      glassMats.add(steel);
      m = w(steel, 0.3);
      break;
    }
    case "enamel": m = w(plain(pick(ENAMELS, paint.accent), 0.25), 0.3); break;
    case "cream": m = w(plain(0xf0e9d8, 0.3), 0.3); break;
    case "glassblock": {
      const gb = pbr("glassblock", [0.8, 0.8], { roughness: 0.1 });
      gb.emissive.setHex(0xffe2b8);
      gb.emissiveMap = tex("glassblock_col", [0.8, 0.8]);
      gb.emissiveIntensity = 0;
      if (damage < 2) gb.userData.night = 0.7;
      m = w(gb);
      break;
    }
    case "neon":
    case "neon2": {
      // Glass tubes in their colour by day; lit at night (bloom does the glow).
      const c = pick(NEONS, paint.signs + (role === "neon2" ? 2 : 0));
      m = plain(new THREE.Color(c).multiplyScalar(0.55).getHex(), 0.2, 0, { emissive: c, emissiveIntensity: 0 });
      if (damage < 2) m.userData.night = 3.5;
      break;
    }
    case "bulb":
      m = plain(0xfff2d8, 0.2, 0, { emissive: 0xffd890, emissiveIntensity: 0 });
      if (damage < 2) m.userData.night = 3;
      break;
    case "dinername": {
      const t = dinerNames(paint.signs);
      m = new THREE.MeshStandardMaterial({ map: t, alphaTest: 0.5, roughness: 0.25, metalness: 0.6, emissive: 0xffffff, emissiveMap: t, emissiveIntensity: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      if (damage < 2) m.userData.night = 0.45;
      break;
    }
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
    case "rim": m = w(plain(0xd4d8dc, 0.3, 0.5)); break;
    case "tyre": m = w(plain(0x262628, 0.9)); break;
    case "plate": m = w(plain(0xe8e6dc, 0.4)); break;
    case "seam": m = plain(0x0a0a0b, 0.9); break;
    case "brake": m = w(plain(0x6a6c6e, 0.45, 0.8)); break;
    case "caliper": m = w(plain(0x2c2e30, 0.5, 0.3)); break;
    case "indicator":
      m = plain(0xd08a20, 0.25, 0, { emissive: 0xffa020, emissiveIntensity: 0 });
      break;
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
    // The bridge.
    case "girder": m = w(plain(0x4a625c, 0.55, 0.45), 1.4); break;
    case "road": m = w(pbr("asphalt", [6, 6], { roughness: 0.93, color: 0xb4b4b4 }), 0.4); break;
    case "pave": m = w(pbr("pave", [3.6, 3.6], { roughness: 0.88 }), 0.6); break;
    case "marking": m = w(plain(0xe8e4d8, 0.7)); break;
    // Street furniture.
    case "galv": m = w(plain(0x9a9ea2, 0.42, 0.7), 0.4); break;
    case "hydrant": m = w(plain(0xb02a1e, 0.45, 0.15), 0.4); break;
    case "panel": m = w(plain(0xf0f0ec, 0.5)); break;
    case "busflag": m = w(plain(0x1d6a3c, 0.4)); break;
    case "sig_red":
    case "sig_amber":
    case "sig_green":
    case "ped_red":
    case "ped_white": {
      const lens = new THREE.MeshStandardMaterial({ color: new THREE.Color(LENS[role]).multiplyScalar(0.18), roughness: 0.2, emissive: LENS[role], emissiveIntensity: 0 });
      signals.push({ m: lens, role, phase: variant || "a" });
      m = lens;
      break;
    }
    // Trees and shrubs.
    case "bark": m = w(pbr("bark", [1, 2], { roughness: 0.95, normal: 1.2 })); break;
    case "birch": m = w(new THREE.MeshStandardMaterial({ map: tex("birch_col", [1, 1]), roughness: 0.8 })); break;
    case "hedge": m = w(pbr("hedge", [1.5, 1.5], { roughness: 0.85, color: paint.wall < 0 ? 0xffffff : pick(FOLIAGE, paint.wall) })); break;
    case "leaf":
    case "smallleaf":
    case "needles":
    case "blossom":
    case "bloom":
    case "woods":
    case "firs":
      // paint.wall < 0: white, for instance colours to tint (the woods).
      m = foliage(role, role === "blossom" || role === "bloom" || paint.wall < 0 ? 0xffffff : pick(FOLIAGE, paint.wall), ao);
      break;
    // The office tower: tinted, coated glass with the floor behind it.
    case "officeglass": {
      const tint = pick(OFFICE_GLASS, paint.wall);
      // Tinted glass lets through about half the light, in its colour.
      const g = room("office", new THREE.Color(tint).lerp(new THREE.Color(0xffffff), 0.35).getHex());
      // A reflective coating: more of the sky, in the glass's colour.
      g.ior = 2.1;
      g.specularColor.setHex(tint).lerp(new THREE.Color(0xffffff), 0.35);
      m = g;
      break;
    }
    case "spandrel": {
      const tint = new THREE.Color(pick(OFFICE_GLASS, paint.wall));
      m = sheen({ color: tint.clone().multiplyScalar(0.07).getHex(), roughness: 0.05, ior: 2.1, specularColor: tint.lerp(new THREE.Color(0xffffff), 0.35) });
      break;
    }
    case "mullion": m = w(plain(pick(MULLIONS, paint.accent), 0.35, 0.6), 0.3); break;
    case "blades": m = w(pbr("blades", [1, 1], { roughness: 0.45, metalness: 0.5, color: new THREE.Color(pick(MULLIONS, paint.accent)).lerp(new THREE.Color(0xffffff), 0.3).getHex() }), 0.8); break;
    case "towername": {
      const t = towerNames(paint.signs);
      m = new THREE.MeshStandardMaterial({ map: t, alphaTest: 0.5, roughness: 0.3, metalness: 0.7, emissive: 0xffffff, emissiveMap: t, emissiveIntensity: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      if (damage < 2) m.userData.night = 0.35;
      break;
    }
    // The art deco tower.
    case "cladstone":
    case "floodstone": {
      const stone = pbr("cladstone", [2.4, 1.2], { roughness: 0.82, normal: 0.8, color: pick(LIMESTONES, paint.wall) });
      if (role === "floodstone") {
        // The crown, floodlit from the terraces at night.
        stone.emissive.setHex(0xffd8a8);
        stone.emissiveMap = tex("cladstone_col", [2.4, 1.2]);
        stone.emissiveIntensity = 0;
        if (damage < 2) stone.userData.night = 0.55;
      }
      m = w(stone, 1.8);
      break;
    }
    case "deco": m = w(pbr("chevron", [1, 1], { roughness: 0.5, metalness: 0.35, normal: 1.2, color: pick(DECO_METALS, paint.accent) }), 1.2); break;
    case "bronze": m = w(plain(pick(DECO_METALS, paint.accent), 0.4, 0.55), 0.8); break;
    case "jet": {
      // Polished black granite: it shows the sky.
      const jet = new THREE.MeshStandardMaterial({ map: tex("granite_col", [1, 1]), color: 0x3a3a3c, roughness: 0.14 });
      if (skyEnv) jet.envMap = skyEnv;
      glassMats.add(jet);
      m = w(jet, 0.6);
      break;
    }
    case "deconame": {
      const t = decoNames(paint.signs);
      m = new THREE.MeshStandardMaterial({ map: t, alphaTest: 0.5, roughness: 0.3, metalness: 0.8, emissive: 0xffe0a0, emissiveMap: t, emissiveIntensity: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      if (damage < 2) m.userData.night = 0.3;
      break;
    }
    case "crownglass":
      // The crown's tall windows: dark glass by day, lit lanterns at night.
      m = sheen({ color: 0x1a2026, roughness: 0.1, emissive: 0xffd49a, emissiveIntensity: 0 });
      if (damage < 2) m.userData.night = 1.6;
      break;
    case "beacon":
      m = plain(0x8a1010, 0.3, 0, { emissive: 0xff1a10, emissiveIntensity: 0 });
      if (damage < 2) m.userData.night = 4;
      break;
    case "glass": m = room("home"); break;
    case "shopglass": m = room("shop"); break;
    case "doorglass": m = room(id === "o1" ? "atrium" : "lobby"); break;
    case "decoglass": m = room("office"); break;
    case "dinerglass": m = room("diner"); break;
    case "worksglass": m = room("works"); break;
    case "cafeglass": m = room("cafe"); break;
    // Civic props (civic.py): water tower, crane, scaffold, rubble, parks.
    // Years of sun and rain: a dulled silver-grey tank, its band faded and
    // streaked, and crane yellow gone ochre (clean paint read as a toy).
    case "tankpaint": m = w(plain(0xaeb0aa, 0.62, 0.25), 2.4); break;
    case "tankband": m = w(plain(0x4a5c6c, 0.7, 0.15), 2.4); break;
    case "crane": m = w(plain(0xd0a030, 0.6, 0.25), 1.8); break;
    case "rubble": m = w(pbr("rubble", [3, 3], { roughness: 0.97 }), 0.6); break;
    case "char": m = w(plain(0x1d1a18, 0.95), 0.4); break;
    case "scaffboard": m = w(plain(0xa08458, 0.85), 1.2); break;
    case "net": m = new THREE.MeshStandardMaterial({ map: tex("net_col", [1, 1]), alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.8 }); break;
    case "water": m = sheen({ color: 0x4f7d93, roughness: 0.1, metalness: 0.2 }); break;
    case "skin": case "shirt": case "pants": case "hair": m = w(plain(0xffffff, 0.8)); break;
    default: m = plain(0xff00ff);
  }
  if (damage && !role.endsWith("glass")) (m as THREE.MeshStandardMaterial).color.multiplyScalar(shade);
  m.userData.real = true;
  cache.set(key, m);
  return m;
}
