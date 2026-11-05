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
const S3_TOP = 3.36;
const S4_TOP = 5.3;

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
};

/**
 * Models that are not buildings: the props the city is dressed with
 * (vehicles, ...), each one glb of named pieces. Missing ones fall back to
 * the kit's props.
 */
export const PROPS = ["cars", "trees", "street", "bridge"];

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
  const t = new THREE.CanvasTexture(dinerCanvas);
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
  const t = new THREE.CanvasTexture(worksCanvas);
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
/** Render: white, warm white, pale grey, sand, anthracite, chalk. */
const RENDERS = [0xf6f4ee, 0xeee8da, 0xd8d6d0, 0xe8dcc6, 0x55585a, 0xf2f0ea];
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
    sh.fragmentShader = sh.fragmentShader.replace("#include <normal_fragment_begin>", THREE.ShaderChunk.normal_fragment_begin.replace("normal *= faceDirection;", ""));
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
  const tinted = ["brick", "bluebrick", "rubbed", "steelframe", "doors", "corrugated", "works", "siding", "shutter", "shopframe", "door", "shingle", "sign", "cornice", "ghost", "render", "cladding", "alu", "shake", "boards", "timber", "chair", "enamel", "neon", "neon2", "dinername", "carpaint", "slate", "ridge", "brownstone", "door2", "door3", ...LEAVES, "hedge"].includes(role) || (id === "a2" && role === "frame");
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
    case "shutter": m = w(pbr("louvre", [1, 1], { roughness: 0.55, color: accent })); break;
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
    case "render": m = w(pbr("render", [3, 3], { roughness: 0.9, normal: 0.6, color: pick(RENDERS, paint.wall) }), 0.4); break;
    case "cladding": m = w(pbr("battens", [1.3, 1.3], { roughness: 0.8, color: pick(TIMBER, paint.accent) }), 0.4); break;
    case "alu": m = w(plain(frame, 0.4, 0.5)); break;
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
    case "glass": m = room("home"); break;
    case "shopglass": m = room("shop"); break;
    case "doorglass": m = room("lobby"); break;
    case "dinerglass": m = room("diner"); break;
    case "worksglass": m = room("works"); break;
    default: m = plain(0xff00ff);
  }
  if (damage && !role.endsWith("glass")) (m as THREE.MeshStandardMaterial).color.multiplyScalar(shade);
  m.userData.real = true;
  cache.set(key, m);
  return m;
}
