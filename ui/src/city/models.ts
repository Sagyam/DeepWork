// City theme, step 2: 3D models for the plan's specs. Buildings, trees,
// cars and props are pieces of the realistic models (real.ts), stacked and
// placed per building and damage; lots, wreckage and the construction site
// are laid out here. Geometry is merged per material to keep draw calls low.
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { BLOCK_X, BLOCK_Z, LOT, lot, rng, type ParkSpec, type SiteSpec, type Spec } from "./plan";
import { CAR_PAINTS, DEFS, fountainSpray, groundMat, realMat, realPiece, type Paint, type RealDef, waterMat } from "./real";

export const WALLS = [0xe8d9c0, 0xd9c2a5, 0xc9d3d8, 0xe6c9b5, 0xb9c4b0, 0xd8d0e0, 0xcfb59b, 0xe9e4da];
export const GLASS = [0x7f9bb3, 0x6d8a99, 0x8fa3b8, 0x5d7488, 0x9ab0a8, 0x7a8aa8, 0x8a98b0, 0x6f8c9c];
export const ACCENTS = [0xb5483a, 0x3a6fb5, 0x3a9a6a, 0xc9902a, 0x7a4ab5, 0x2f3a4a];

/** Things the scene animates on a model. Positions are model-local. */
export interface ModelInfo {
  height: number;
  /** Smoke and fire sources. */
  emitters: { pos: THREE.Vector3; kind: "smoke" | "fire"; rate: number }[];
  beacons: THREE.Vector3[];
  /** Materials whose emissive follows the night. */
  night: THREE.MeshStandardMaterial[];
  /** The concrete colour for debris when it collapses. */
  debris: number;
  /** Beacons on the crane's jib, which turns (jib-local). */
  jibBeacons?: THREE.Vector3[];
}

/** Lots, pavements and park lawns sit at kerb height. */
export const KERB = 0.2;

const shared = new Map<string, THREE.MeshStandardMaterial>();
/** The one material of every yard (see Parts' tint). */
const YARD = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85 });

/** Shared plain materials. Night-lit ones carry `userData.night`. */
export function mat(color: number, opts: THREE.MeshStandardMaterialParameters & { night?: number } = {}): THREE.MeshStandardMaterial {
  const key = `${color}:${JSON.stringify(opts)}`;
  let m = shared.get(key);
  if (!m) {
    const { night, ...rest } = opts;
    m = new THREE.MeshStandardMaterial({ color, roughness: 0.8, metalness: 0, ...rest });
    if (night) m.userData.night = night;
    shared.set(key, m);
  }
  return m;
}

/** Collects geometry per material and merges it into one mesh each. */
export class Parts {
  private byMat = new Map<THREE.Material, THREE.BufferGeometry[]>();
  /** Objects that cannot be merged (a fountain's spray, Points), added as they are. */
  private extras: THREE.Object3D[] = [];
  private m = new THREE.Matrix4();
  private q = new THREE.Quaternion();
  private e = new THREE.Euler();

  /**
   * With `tint`, every material's colour is baked into the vertex colours
   * (times any baked occlusion) and all geometry shares `tint`: one draw
   * for a whole yard of props, at the cost of their gloss. Realistic
   * models' materials (`userData.real`) keep their own.
   */
  constructor(private tint?: THREE.Material) {}

  /** `shift` adds to UV x, which for glass gives its windows new ids (other rooms, curtains and lights). */
  add(material: THREE.Material, g: THREE.BufferGeometry, x: number, y: number, z: number, rx = 0, ry = 0, rz = 0, scale?: THREE.Vector3, shift = 0) {
    this.q.setFromEuler(this.e.set(rx, ry, rz));
    this.m.compose(new THREE.Vector3(x, y, z), this.q, scale ?? new THREE.Vector3(1, 1, 1));
    const geo = g.index ? g.toNonIndexed() : g.clone();
    geo.applyMatrix4(this.m);
    for (const k of Object.keys(geo.attributes)) if (!["position", "normal", "uv", "uv1", "color"].includes(k)) geo.deleteAttribute(k);
    if (this.tint && !material.userData.real) {
      const c = (material as THREE.MeshStandardMaterial).color ?? new THREE.Color(1, 1, 1);
      const n = geo.getAttribute("position").count;
      const ao = geo.getAttribute("color");
      const col = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        const a = ao ? ao.getX(i) : 1;
        col.set([c.r * a, c.g * a, c.b * a], i * 3);
      }
      geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
      geo.deleteAttribute("uv");
      material = this.tint;
    }
    if (shift) {
      const uv = geo.getAttribute("uv") as THREE.BufferAttribute;
      for (let i = 0; i < uv.count; i++) uv.setX(i, uv.getX(i) + shift);
    }
    const list = this.byMat.get(material) ?? [];
    list.push(geo);
    this.byMat.set(material, list);
  }

  /** A box resting on `y` (its bottom), centred on x / z. */
  box(material: THREE.Material, w: number, h: number, d: number, x: number, y: number, z: number, ry = 0, rx = 0, rz = 0) {
    this.add(material, new THREE.BoxGeometry(w, h, d), x, y + h / 2, z, rx, ry, rz);
  }

  cyl(material: THREE.Material, r0: number, r1: number, h: number, x: number, y: number, z: number, seg = 8) {
    this.add(material, new THREE.CylinderGeometry(r0, r1, h, seg), x, y + h / 2, z);
  }

  /** Adds an object that is not merged (Points, say) to the group into() fills. */
  extra(o: THREE.Object3D) {
    this.extras.push(o);
  }

  into(group: THREE.Group, shadows = true) {
    for (const o of this.extras) group.add(o);
    for (const [material, list] of this.byMat) {
      const mesh = new THREE.Mesh(mergeGeometries(list), material);
      // Clear glass (balcony rails) would cast a solid shadow: it casts none.
      mesh.castShadow = shadows && !material.userData.noShadow;
      mesh.receiveShadow = true;
      group.add(mesh);
    }
  }
}

// ---- buildings -------------------------------------------------------------------

/**
 * The model that draws a spec: its blueprint's, else one of its style's,
 * picked per building from its seed (siblings such as C1 and C2 share the
 * classic cottage). Null only for the town's lots built in code (water
 * tower, square, park: utility()).
 */
export function realDef(s: Spec): RealDef | null {
  if (s.model) return DEFS[s.model] ?? null;
  const defs = Object.values(DEFS).filter((d) => d.kind === s.kind && d.style === s.style);
  return defs.length ? defs[Math.floor(rng(s.seed * 29 + 3)() * defs.length)] : null;
}

/** A spec sized and placed for its model (real-world sizes); the town's own lots unchanged. */
export function fitReal<T extends Spec>(s: T): T {
  const def = realDef(s);
  if (!def) return s;
  const l = lot(s.index);
  const yard = LOT / 2 - def.d / 2 - def.front;
  const floors = def.floors(s.floors);
  return { ...s, w: def.w, d: def.d, floors, floorH: def.top(floors) / floors, height: def.height(floors), yard, x: l.x + Math.sin(l.rot) * yard, z: l.z + Math.cos(l.rot) * yard };
}

const paintOf = (s: Spec): Paint => ({ wall: s.wall, accent: s.accent, roof: Math.floor(s.seed / 7) % 97, signs: Math.floor(s.seed / 3) % 8, ...(s.name ? { name: s.name } : {}) });

/** Adds a piece of a realistic model; glass gets window ids of its own from `shift`. */
function putReal(p: Parts, def: RealDef, piece: string, paint: Paint, damage: number, info: ModelInfo | null, x: number, y: number, z: number, ry = 0, scale?: THREE.Vector3, shift = 0) {
  for (const { role, geo } of realPiece(def.id, piece)) {
    const m = realMat(def.id, role, paint, damage);
    if (info && m.userData.night && !info.night.includes(m as THREE.MeshStandardMaterial)) info.night.push(m as THREE.MeshStandardMaterial);
    p.add(m, geo, x, y, z, 0, ry, 0, scale, role.endsWith("glass") ? shift : 0);
  }
}

/** Stacks a model's pieces on the lot (at kerb height). */
function stackReal(p: Parts, s: Spec, def: RealDef, floors: number, roof: boolean, info: ModelInfo) {
  const r = rng(s.seed * 13 + 11);
  const paint = paintOf(s);
  // Window ids restart in every piece: offset them per storey and building.
  const base = (s.seed % 8) * 8 * 256;
  def.stack(floors, roof, r, s.floors).forEach(({ piece, y }, i) => putReal(p, def, piece, paint, s.damage, info, 0, y + KERB, 0, 0, undefined, base + i * 256));
  const anchors: Record<string, THREE.Vector3> = {};
  if (roof && def.smoke) anchors.smoke = def.smoke(floors).add(new THREE.Vector3(0, KERB, 0));
  return { top: def.top(floors) + KERB, w: s.w, d: s.d, anchors };
}

/** A picket fence along x from x0 to x1 at z, from the model's fence pieces, panels stretched to fit. */
function picket(p: Parts, def: RealDef, s: Spec, x0: number, x1: number, z: number) {
  const L = x1 - x0;
  const n = Math.max(1, Math.round(L / 2.4));
  const paint = paintOf(s);
  for (let i = 0; i < n; i++) putReal(p, def, "fence", paint, 0, null, x0 + ((i + 0.5) * L) / n, KERB, z, 0, new THREE.Vector3(L / n / 2.4, 1, 1));
  putReal(p, def, "fence_post", paint, 0, null, x1, KERB, z);
}

/** The lot round a model: what its kind of building has in front and out back. */
function realYard(p: Parts, rp: Parts, s: Spec, def: RealDef, r: () => number) {
  const cz = -s.yard;
  const front = LOT / 2 - s.yard;
  const back = -LOT / 2 - s.yard;
  const half = LOT / 2 - 0.2;
  const paving = mat(0xbab4a8, { roughness: 0.9 });
  switch (def.id) {
    case "a1": {
      // Paved to the pavement, as in town; bins and a wall out back.
      p.box(paving, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const bin = mat(0x2a4a34, { roughness: 0.6 });
      for (let i = 0; i < 3; i++) p.box(bin, 0.7, 1.1, 0.7, half - 0.6 - i * 0.85, KERB, back + 0.7);
      fenceRun(p, "wall_brick", half, back + 0.12, -half, back + 0.12, 1.5);
      break;
    }
    case "a2": {
      // Flagstone areaways in front behind iron railings, open at the
      // stoops; bins and a shrub or two by the bays, a young tree in one;
      // behind, three narrow lawns between board fences.
      p.box(paving, LOT - 0.4, KERB, front - 3.3, 0, 0, (front + 3.3) / 2);
      p.box(lawn(), LOT - 0.4, KERB, -6.8 - back, 0, 0, (-6.8 + back) / 2);
      const fz = front - 0.35;
      const stoops = [-3.475, -1.725, 6.925]; // the doors' x (a2_brownstone.py)
      const gaps = stoops.map((x) => [x - 0.85, x + 0.85]);
      const runs: [number, number][] = [];
      let x0 = -half;
      for (const [a, b] of gaps) {
        if (a - x0 > 0.3) runs.push([x0, a]);
        x0 = Math.max(x0, b);
      }
      if (half - x0 > 0.3) runs.push([x0, half]);
      for (const [a, b] of runs) fenceRun(p, "fence_iron", a, fz, b, fz, 0.85);
      const bin = mat(0x3a3e40, { roughness: 0.55, metalness: 0.3 });
      for (const [x, z] of [[-5.1, 4.0], [-4.6, 4.0], [0.0, 4.0], [2.6, 4.0]]) p.box(bin, 0.55, 0.95, 0.55, x, KERB, z);
      for (const x of [-6.8, -5.5, 1.4, 4.2, 5.4]) if (r() < 0.75) shrub(p, x, fz - 0.6, s.seed * 5 + x * 3, KERB, 0.55);
      tree(p, 4.4, fz - 1.4, 0.45, s.seed + 1, KERB, ["young", "linden", "cherry"]);
      for (const x of [-2.6, 2.6]) fenceRun(p, "fence_panel", x, -6.8, x, back + 0.1);
      fenceRun(p, "fence_panel", half, back + 0.1, -half, back + 0.1);
      break;
    }
    case "c1": {
      // Lawn, a picket fence along the street, a path to the porch steps,
      // a drive down the side with the car, trees, a hedge at the back.
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const fz = front - 0.45;
      const steps = s.d / 2;
      p.box(paving, 1.2, KERB + 0.03, fz - steps + 0.2, 0, 0, (fz + steps) / 2);
      const dx = half - 1.4;
      p.box(mat(0xa29e96, { roughness: 0.95 }), 2.6, KERB + 0.03, front - cz + 1, dx, 0, (front + cz - 1) / 2);
      parked(p, dx, 0.6, 0, s.seed + 3);
      picket(rp, def, s, -half + 0.2, -0.75, fz);
      picket(rp, def, s, 0.75, dx - 1.5, fz);
      tree(p, -half + 1.4, front - 3.2, 0.75, s.seed + 1, KERB);
      tree(p, -half + 1.6, back + 1.6, 0.85, s.seed + 2, KERB);
      if (r() < 0.6) tree(p, (r() - 0.5) * 3, back + 1.2, 0.6, s.seed + 4, KERB);
      hedge(p, LOT - 0.4, KERB + 1.2, 0.7, 0, 0, back + 0.55, s.seed);
      // Shrubs along the porch, either side of the steps.
      for (const x of [-3.9, -2.4, 2.4, 3.9]) if (r() < 0.8) shrub(p, x, steps + 0.7, s.seed * 5 + x * 3);
      break;
    }
    case "c2": {
      // A front garden behind a clipped hedge, brick gate piers in the gap and
      // a chequered tile path to the door steps; flowers under the bay, a
      // tree on the bay side. Behind, a lawn closed by board fences and a hedge.
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const fz = front - 0.5;
      const gx = 0.25; // the front door
      const steps = s.d / 2 + 0.05;
      const tiles = [mat(0x9a4a36, { roughness: 0.7 }), mat(0xd8ccb4, { roughness: 0.6 })];
      const edging = mat(0x5a3a30, { roughness: 0.8 });
      const n = Math.max(1, Math.round((fz - steps) / 0.3));
      const step = (fz - steps) / n;
      for (let i = 0; i < n; i++) for (let j = 0; j < 4; j++) p.box(tiles[(i + j) % 2], 0.3, KERB + 0.03, step, gx - 0.45 + j * 0.3, 0, steps + (i + 0.5) * step);
      for (const x of [gx - 0.65, gx + 0.65]) p.box(edging, 0.06, KERB + 0.1, fz - steps, x, 0, (fz + steps) / 2);
      putReal(rp, def, "gate", paintOf(s), 0, null, gx, KERB, fz);
      hedge(p, gx - 1.05 + half, KERB + 0.9, 0.6, (-half + gx - 1.05) / 2, 0, fz, s.seed);
      hedge(p, half - gx - 1.05, KERB + 0.9, 0.6, (half + gx + 1.05) / 2, 0, fz, s.seed);
      for (const x of [-5.0, -4.1, -3.2, -2.3]) if (r() < 0.85) shrub(p, x, 5.15, s.seed * 5 + x * 3, KERB, 0.6);
      for (const x of [2.2, 3.2]) if (r() < 0.8) shrub(p, x, 4.55, s.seed * 7 + x * 3, KERB, 0.7);
      tree(p, -half + 1.4, fz - 1.4, 0.6, s.seed + 1, KERB, ["cherry", "birch", "maple", "cherry"]);
      const yb = -s.d / 2 + 0.6; // the back wall
      for (const x of [-half + 0.1, half - 0.1]) fenceRun(p, "fence_panel", x, yb, x, back + 0.6);
      hedge(p, LOT - 0.4, KERB + 1.5, 0.7, 0, 0, back + 0.55, s.seed);
      tree(p, -half + 2.2, back + 1.6, 0.7, s.seed + 2, KERB, ["young", "cherry", "linden"]);
      break;
    }
    case "c3": {
      // Lawn; a drive to the garage with the car on it, stepping slabs to
      // the recessed door, a hedge along the street and across the back.
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const gz = 3.95; // the garage door
      p.box(mat(0xa29e96, { roughness: 0.95 }), 3.6, KERB + 0.03, front - gz, 4.2, 0, (front + gz) / 2);
      parked(p, 4.2, gz + 2.5, Math.PI, s.seed + 3);
      for (let z = 4.65; z < front - 0.5; z += 0.9) p.box(paving, 1.3, KERB + 0.04, 0.6, 0.6, 0, z);
      hedge(p, half - 0.3, KERB + 0.7, 0.6, (-half - 0.3) / 2, 0, front - 0.5, s.seed);
      hedge(p, half - 6.2, KERB + 0.7, 0.6, (half + 6.2) / 2, 0, front - 0.5, s.seed);
      hedge(p, LOT - 0.4, KERB + 1.4, 0.7, 0, 0, back + 0.55, s.seed);
      // A border of shrubs under the living-room glass.
      for (const x of [-5.2, -3.9, -2.6]) if (r() < 0.85) shrub(p, x, 4.45, s.seed * 7 + x * 3);
      tree(p, -half + 2.0, front - 2.2, 0.7, s.seed + 1, KERB);
      if (r() < 0.7) tree(p, 3.5 + r() * 3, back + 1.2, 0.8, s.seed + 2, KERB);
      break;
    }
    case "c4": {
      // A cabin in the pines: a lawn, stepping stones to the deck steps, a
      // gravel drive down the side with the car, a post-and-rail fence along
      // the street and conifers round about.
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const fz = front - 0.45;
      for (let z = s.d / 2 + 0.45; z < fz - 0.3; z += 0.8) p.box(paving, 0.7, KERB + 0.04, 0.5, (r() - 0.5) * 0.25, 0, z, (r() - 0.5) * 0.4);
      const dx = half - 1.7;
      p.box(mat(0x9e978c, { roughness: 1 }), 2.8, KERB + 0.03, front - cz - 0.6, dx, 0, (front + cz + 0.6) / 2);
      parked(p, dx, 0.2, 0, s.seed + 3);
      fenceRun(p, "fence_rail", -half + 0.2, fz, -0.6, fz);
      fenceRun(p, "fence_rail", 0.6, fz, dx - 1.6, fz);
      const pines = ["spruce", "pine", "spruce", "birch", "pine"];
      tree(p, -half + 1.3, front - 2.4, 0.95, s.seed + 1, KERB, pines);
      tree(p, -half + 1.6, back + 2.0, 1.1, s.seed + 2, KERB, pines);
      tree(p, 2.8 + r() * 1.5, back + 1.3, 0.9, s.seed + 4, KERB, pines);
      if (r() < 0.6) tree(p, -half + 1.2, 1.0, 0.7, s.seed + 5, KERB, pines);
      // Low shrubs at the deck's corners, under the eaves.
      for (const x of [-3.9, 3.9]) if (r() < 0.8) shrub(p, x, 4.5, s.seed * 5 + x * 3, KERB, 0.7);
      break;
    }
    case "s2": {
      // Paved to the pavement: the café's terrace of umbrella tables before
      // its windows and round the cut-off corner, closed to the street by
      // planters, a menu board by the corner door; the bins down the side.
      p.box(paving, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const tz = s.d / 2 + 1.55;
      const tables: [number, number][] = [[-2.2, tz], [0.75, tz], [4.4, tz - 0.9]];
      tables.forEach(([x, z], i) => putReal(rp, def, "table", paintOf(s), 0, null, x, KERB, z, (s.seed + i * 2.3) % (Math.PI * 2)));
      const box = mat(0x3a3a36, { roughness: 0.8, metalness: 0.2 });
      for (const x of [-4.6, -0.75, 2.4]) {
        p.box(box, 1.3, 0.5, 0.45, x, KERB, front - 0.45);
        shrub(p, x - 0.3, front - 0.45, s.seed * 3 + x, KERB + 0.5, 0.55);
        shrub(p, x + 0.3, front - 0.45, s.seed * 5 + x, KERB + 0.5, 0.5);
      }
      const board = mat(0x1e1e1e, { roughness: 0.7 });
      for (const k of [-1, 1]) p.box(board, 0.55, 0.95, 0.05, 4.9, KERB, s.d / 2 - 0.4 + k * 0.08, 0, Math.PI / 4 - k * 0.17);
      const bin = mat(0x2a4a34, { roughness: 0.6 });
      for (let i = 0; i < 2; i++) p.box(bin, 0.7, 1.1, 0.7, half - 0.6, KERB, back + 0.7 + i * 0.85);
      break;
    }
    case "p1": {
      // Rough grass round the compound, a concrete drive from the gate
      // (x 0.6 to 4.6, p1_substation.py) to the street, a hedge either side.
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const drive = mat(0xa29e96, { roughness: 0.95 });
      p.box(drive, 4.4, KERB + 0.01, front - s.d / 2, 2.6, 0, (front + s.d / 2) / 2);
      for (const x of [-5.5, -2.5]) shrub(p, x, front - 0.6, s.seed * 5 + x * 3, KERB, 0.7);
      break;
    }
    case "h1": {
      // Paved to the pavement in front (the ramp and steps run onto it),
      // lawns down the left and behind with shrubs, a car at the
      // ambulance bay on the right.
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      p.box(paving, LOT - 0.4, KERB + 0.01, front - 4.5, 0, 0, (front + 4.5) / 2);
      const asphalt = groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 });
      p.box(asphalt, half - 6.5, KERB + 0.012, 8, (half + 6.5) / 2, 0, 0.4);
      const line = mat(0xd8b83a, { roughness: 0.7 });
      for (const z of [-3.2, 4.0]) p.box(line, half - 6.6, KERB + 0.02, 0.1, (half + 6.6) / 2, 0, z);
      parked(p, 7.2, 0.4, 0, s.seed + 3);
      for (const [x, z] of [[-7.3, -2], [-7.3, 1.5], [-3, -5.6], [1.5, -5.6]]) shrub(p, x, z, s.seed * 5 + x * 3 + z, KERB, 0.8);
      break;
    }
    case "e1": {
      // Lawns either side of a paved path to the steps, an iron railing
      // along the street open at the path, the flagpole on the lawn; the
      // asphalt playground round the sides and back, hopscotch on it.
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      p.box(paving, 2.6, KERB + 0.01, front - 5.0, 0, 0, (front + 5.0) / 2);
      const asphalt = groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 });
      p.box(asphalt, LOT - 0.4, KERB + 0.005, 5.5 - back, 0, 0, (5.5 + back) / 2);
      const chalk = mat(0xe8e4d8, { roughness: 0.8 });
      for (let i = 0; i < 6; i++) {
        const z = 2.0 - i * 0.62;
        if (i % 3 === 1) for (const dx of [-0.31, 0.31]) p.box(chalk, 0.5, KERB + 0.012, 0.5, -7.25 + dx, 0, z);
        else p.box(chalk, 0.5, KERB + 0.012, 0.5, -7.25, 0, z);
      }
      fenceRun(p, "fence_iron", -half, front - 0.3, -1.4, front - 0.3, 1.1);
      fenceRun(p, "fence_iron", 1.4, front - 0.3, half, front - 0.3, 1.1);
      const pole = mat(0xe8e6e0, { roughness: 0.4, metalness: 0.4 });
      p.add(pole, new THREE.CylinderGeometry(0.04, 0.07, 9, 10), 4.6, KERB + 4.5, front - 1.2);
      p.add(mat(0xc9a24e, { roughness: 0.3, metalness: 1 }), new THREE.SphereGeometry(0.1, 10, 8), 4.6, KERB + 9.05, front - 1.2);
      for (const x of [-3.0, 3.0]) shrub(p, x, 5.9, s.seed * 5 + x * 3, KERB, 0.7);
      break;
    }
    case "f1": {
      // A concrete apron from the bays to the kerb, KEEP CLEAR hatched in
      // yellow before each door; a paved yard behind, walled.
      const concrete = mat(0xa29e96, { roughness: 0.95 });
      p.box(concrete, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const yellow = mat(0xd8b83a, { roughness: 0.7 });
      for (const x of [-2.95, 2.95]) {
        for (const dx of [-1.7, 1.7]) p.box(yellow, 0.12, KERB + 0.01, front - s.d / 2 - 0.3, x + dx, 0, (front + s.d / 2) / 2);
        for (let i = 0; i < 4; i++) p.box(yellow, 3.3, KERB + 0.01, 0.14, x, 0, s.d / 2 + 0.5 + i * 0.75);
      }
      fenceRun(p, "wall_brick", half - 0.12, back + 0.12, -half + 0.12, back + 0.12, 1.8);
      fenceRun(p, "wall_brick", -half + 0.12, back + 0.12, -half + 0.12, -s.d / 2, 1.8);
      break;
    }
    case "s3": {
      // An asphalt forecourt to the pavement with a car drawn up beside the
      // steps and shrubs either side of them; behind, a concrete service yard
      // round the kitchen with bins, a grease drum and gas bottles, fenced.
      const asphalt = groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 });
      p.box(asphalt, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const line = mat(0xe8e4d8, { roughness: 0.7 });
      for (const x of [-6.9, -1.7]) p.box(line, 0.12, KERB + 0.01, 2.2, x, 0, front - 2.0);
      parked(p, -4.3, front - 2.0, Math.PI / 2, s.seed + 3);
      for (const x of [-1.9, 1.9]) shrub(p, x, 3.75, s.seed * 5 + x * 3, KERB, 0.75);
      const yardZ = -1.8; // the diner's back wall
      p.box(mat(0xa29e96, { roughness: 0.95 }), LOT - 0.4, KERB + 0.02, yardZ - back, 0, 0, (yardZ + back) / 2);
      const bin = mat(0x2a4a34, { roughness: 0.6 });
      for (let i = 0; i < 2; i++) p.box(bin, 0.7, 1.1, 0.7, half - 0.7 - i * 0.85, KERB, back + 0.7);
      p.add(mat(0x3a5a8a, { roughness: 0.5, metalness: 0.3 }), new THREE.CylinderGeometry(0.29, 0.29, 0.88, 14), -half + 0.8, KERB + 0.44, back + 0.7);
      const gas = mat(0xe8e6e0, { roughness: 0.4, metalness: 0.2 });
      for (const x of [-5.2, -4.6]) p.add(gas, new THREE.CapsuleGeometry(0.19, 0.95, 4, 12), x, KERB + 0.67, -3.0);
      fenceRun(p, "fence_panel", half, back + 0.1, -half, back + 0.1);
      break;
    }
    case "s4": {
      // Concrete to the pavement: an apron before the dock with a vehicle
      // drawn up and pallets by the dock steps, oil drums by the boiler
      // house; behind, a walled yard with a skip and scrap.
      const concrete = mat(0xa29e96, { roughness: 0.95 });
      p.box(concrete, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const line = mat(0xd8b83a, { roughness: 0.7 });
      p.box(line, 3.9, KERB + 0.01, 0.12, -1.25, 0, front - 0.5);
      // Nosed in beside the stack, clear of the dock and the office door.
      parked(p, 5.55, front - 2.9, 0, s.seed + 3);
      const wood = mat(0x8a6a40, { roughness: 0.9 });
      for (let i = 0; i < 5; i++) p.box(wood, 1.2, 0.15, 1.0, -5.3 + (i % 2) * 0.06, KERB + i * 0.15, 6.4, 0, (r() - 0.5) * 0.1);
      for (let i = 0; i < 3; i++) p.box(wood, 1.2, 0.15, 1.0, -5.0, KERB + i * 0.15, front - 0.95, 0, 0.3 + (r() - 0.5) * 0.1);
      const drum = [mat(0x2a4a7a, { roughness: 0.5, metalness: 0.3 }), mat(0x7a2a22, { roughness: 0.5, metalness: 0.3 })];
      for (let i = 0; i < 3; i++) p.add(drum[i % 2], new THREE.CylinderGeometry(0.29, 0.29, 0.88, 14), 6.3 - (i % 2) * 0.62, KERB + 0.44, -0.35 - Math.floor(i / 2) * 0.62);
      const yardZ = -5.2; // the back wall
      p.box(mat(0x4a5a3e, { roughness: 0.6, metalness: 0.4 }), 3.4, 1.3, 1.7, -3.2, KERB, (yardZ + back) / 2, 0.04);
      p.box(mat(0x5a4a3e, { roughness: 0.8, metalness: 0.5 }), 1.6, 0.4, 0.9, 2.6, KERB, (yardZ + back) / 2, 0.3);
      fenceRun(p, "wall_brick", half - 0.12, back + 0.12, -half + 0.12, back + 0.12, 1.8);
      fenceRun(p, "wall_brick", -half + 0.12, back + 0.12, -half + 0.12, yardZ, 1.8);
      fenceRun(p, "wall_brick", half - 0.12, yardZ, half - 0.12, back + 0.12, 1.8);
      break;
    }
    case "a3": {
      // Lawn to the pavement, a paved path to the entrance and a gravel
      // strip along the front under the balconies, planted with shrubs, a
      // tree either side; Behind, a lawn closed by a hedge,
      // a bench, the bins, a path to the back door.
      const wall = 4.8; // the front wall's z (a3_balcony.py)
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      p.box(paving, 2.6, KERB + 0.02, front - wall, 0, 0, (front + wall) / 2);
      p.box(mat(0xb4aea2, { roughness: 1 }), 15, KERB + 0.015, 1.0, 0, 0, wall + 0.5);
      for (const x of [-6.6, -5.0, -3.4, 3.4, 5.0, 6.6]) if (r() < 0.8) shrub(p, x, wall + 0.55, s.seed * 7 + x * 5, KERB, 0.6);
      tree(p, -5.6, front - 1.3, 0.55, s.seed + 2, KERB, ["young", "linden", "cherry"]);
      if (r() < 0.6) tree(p, 5.8, front - 1.1, 0.5, s.seed + 5, KERB, ["young", "linden", "cherry"]);
      const bin = mat(0x3a5a46, { roughness: 0.6 });
      for (let i = 0; i < 3; i++) p.box(bin, 0.75, 1.15, 0.75, half - 0.6 - i * 0.85, KERB, back + 1.5);
      const backWall = -s.d / 2 + 0.3;
      p.box(paving, 1.6, KERB + 0.02, backWall - back, 0, 0, (backWall + back) / 2);
      hedge(p, LOT - 0.4, KERB + 1.2, 0.7, 0, 0, back + 0.5, s.seed + 3);
      furniture(p, "bench", -3.5, KERB, back + 1.6, Math.PI);
      break;
    }
    case "o1": {
      // A plaza paved to the pavement: trees in planters either side of the
      // colonnade, benches under them, bollards before the entrance; behind,
      // a service strip with the bins by the loading bay.
      p.box(paving, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const fz = s.d / 2;
      for (const sx of [-1, 1]) {
        planter(p, sx * 5.6, front - 1.3, s.seed + (sx > 0 ? 1 : 2));
        furniture(p, "bench", sx * 3.3, KERB, front - 1.3, 0);
      }
      for (let i = 0; i < 5; i++) furniture(p, "bollard", -2.4 + i * 1.2, KERB, front - 0.45);
      p.box(mat(0x6a6a6c, { roughness: 0.6 }), 4.4, 0.02, 1.6, 0, KERB, fz + 0.9);
      const bin = mat(0x2a3a4a, { roughness: 0.6 });
      for (let i = 0; i < 3; i++) p.box(bin, 1.2, 1.3, 1.0, -half + 1.0 + i * 1.3, KERB, back + 0.9);
      break;
    }
    case "l1": {
      // Granite paving to the pavement, heritage lamps either side of the
      // portal; behind, the bins by the service door.
      p.box(mat(0x9c9890, { roughness: 0.6 }), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      for (const sx of [-1, 1]) furniture(p, "lamp_heritage", sx * 4.5, KERB, front - 0.4, 0);
      const bin = mat(0x2a3a4a, { roughness: 0.6 });
      for (let i = 0; i < 3; i++) p.box(bin, 1.0, 1.2, 0.5, -half + 1.0 + i * 1.1, KERB, back + 0.3);
      break;
    }
    case "e2": {
      // Paved to the pavement, the steps and the blue lamp on it; down the
      // sides narrow paved passages to the yard behind, where the patrol
      // cars stand (white and dark blue) by a brick wall.
      p.box(paving, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const yardZ = -s.d / 2;
      const asphalt = groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 });
      p.box(asphalt, LOT - 0.4, KERB + 0.01, yardZ - back, 0, 0, (yardZ + back) / 2);
      const line = mat(0xe8e4d8, { roughness: 0.7 });
      for (const x of [-4.6, -1.6, 1.4, 4.4]) p.box(line, 0.1, KERB + 0.02, 2.2, x, 0, (yardZ + back) / 2);
      parked(p, -3.1, (yardZ + back) / 2, Math.PI / 2, s.seed + 3, KERB, { name: "estate", paint: 0 });
      parked(p, 2.9, (yardZ + back) / 2, Math.PI / 2, s.seed + 4, KERB, { name: "sedan", paint: 5 });
      fenceRun(p, "wall_brick", half - 0.12, back + 0.12, -half + 0.12, back + 0.12, 1.8);
      for (const sx of [-1, 1]) furniture(p, "bollard", sx * 1.8, KERB, front - 0.45);
      break;
    }
    case "e3": {
      // A paved forecourt before the steps with lamps and benches facing
      // it; lawns down the sides and behind, a tree at each back corner.
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      p.box(mat(0x9c9890, { roughness: 0.7 }), LOT - 0.4, KERB + 0.01, front - 4.0, 0, 0, (front + 4.0) / 2);
      for (const sx of [-1, 1]) {
        furniture(p, "lamp_heritage", sx * 6.4, KERB, front - 0.5, 0);
        furniture(p, "bench", sx * 5.6, KERB, 4.6, 0);
      }
      for (const sx of [-1, 1]) tree(p, sx * 6.6, back + 1.6, 0.8, s.seed + (sx > 0 ? 1 : 2), KERB, ["linden", "oak"]);
      break;
    }
    case "h2": {
      // Paved to the pavement before the main entrance; the asphalt drive
      // under the emergency canopy (h2_hospital.py, x 2.3 to 7.8) with an
      // ambulance drawn up, a drop-off line; a service road behind.
      p.box(paving, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const asphalt = groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 });
      const dz = 1.5; // the podium's front, building-local (CAN / 2)
      p.box(asphalt, half - 2.2, KERB + 0.012, front - dz, (half + 2.2) / 2, 0, (front + dz) / 2);
      p.box(mat(0xd8382a, { roughness: 0.7 }), half - 2.4, KERB + 0.02, 0.12, (half + 2.4) / 2, 0, dz + 0.3);
      parked(p, 5.2, (front + dz) / 2 + 0.2, 0, s.seed + 3, KERB, { name: "van", paint: 0 });
      p.box(asphalt, LOT - 0.4, KERB + 0.01, Math.max(0.5, -s.d / 2 - back), 0, 0, (-s.d / 2 + back) / 2);
      for (const x of [-6.6, -4.6]) furniture(p, "bench", x, KERB, front - 1.2, 0);
      break;
    }
    case "p2": {
      // Concrete to the pavement; behind, the coal yard: a black heap by
      // the conveyor's hopper, a palisade along the back.
      p.box(mat(0xa29e96, { roughness: 0.95 }), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const coal = mat(0x1c1c1e, { roughness: 0.95 });
      p.add(coal, new THREE.ConeGeometry(2.2, 1.6, 9), -4.5, KERB + 0.8, -s.d / 2 + 0.2);
      p.add(coal, new THREE.ConeGeometry(1.6, 1.1, 8), -1.8, KERB + 0.55, -s.d / 2 + 0.6);
      fenceRun(p, "fence_panel", half, back + 0.1, -half, back + 0.1);
      break;
    }
    case "w2": {
      // The railed yard (w2_pumping.py) paved in setts, lawns round the
      // engine house with shrubs, a tree behind.
      p.box(lawn(), LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      p.box(mat(0x8e8a84, { roughness: 0.9 }), LOT - 0.4, KERB + 0.01, 3.2, 0, 0, front - 1.6);
      p.box(mat(0x8e8a84, { roughness: 0.9 }), 3.2, KERB + 0.01, 2.0, 0, 0, front - 4.2);
      for (const [x, z] of [[-6.8, 0], [-6.8, -3], [7.0, 3.0]]) shrub(p, x, z, s.seed * 5 + x * 3 + z, KERB, 0.8);
      tree(p, -5.2, back + 1.4, 0.9, s.seed + 1, KERB);
      break;
    }
    case "s1": {
      // Paved to the pavement, a sandwich board by the door; behind, a
      // concrete service yard with the bins and the delivery van, walled.
      p.box(paving, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
      const yardZ = -s.d / 2;
      p.box(mat(0xa29e96, { roughness: 0.95 }), LOT - 0.4, KERB + 0.02, yardZ - back, 0, 0, (yardZ + back) / 2);
      const board = mat(0x2a2a2a, { roughness: 0.7 });
      for (const k of [-1, 1]) p.box(board, 0.6, 0.95, 0.05, 1.6, KERB, front - 0.4 + k * 0.08, 0, -k * 0.17);
      const bin = mat(0x2a4a34, { roughness: 0.6 });
      for (let i = 0; i < 2; i++) p.box(bin, 0.7, 1.1, 0.7, -half + 0.6 + i * 0.85, KERB, yardZ - 0.6);
      p.box(mat(0x3a4048, { roughness: 0.6, metalness: 0.3 }), 1.6, 1.3, 1.1, -half + 3.0, KERB, yardZ - 0.75);
      parked(p, 2.2 + r() * 1.5, (yardZ + back) / 2 + 0.2, Math.PI / 2, s.seed + 3);
      fenceRun(p, "wall_brick", half - 0.12, back + 0.12, -half + 0.12, back + 0.12, 1.45);
      fenceRun(p, "wall_brick", -half + 0.12, back + 0.12, -half + 0.12, yardZ, 1.45);
      fenceRun(p, "wall_brick", half - 0.12, yardZ, half - 0.12, back + 0.12, 1.45);
      break;
    }
  }
}

/** Broken-off top: jagged chunks and bent rebar on a cut body; `k` scales them down for small buildings. */
function wreckTop(p: Parts, w: number, d: number, y: number, color: number, r: () => number, k = 1) {
  const conc = mat(0x5a5652, { roughness: 1 });
  const wall = mat(new THREE.Color(color).multiplyScalar(0.45).getHex());
  for (let i = 0; i < 9; i++) {
    const cw = w * (0.15 + r() * 0.3) * k;
    const ch = (0.6 + r() * 2.4) * k;
    p.box(r() < 0.5 ? conc : wall, cw, ch, d * (0.15 + r() * 0.35) * k, (r() - 0.5) * (w - cw), y - 0.3, (r() - 0.5) * d * 0.7, r(), (r() - 0.5) * 0.5, (r() - 0.5) * 0.5);
  }
  const steel = mat(0x2a2422, { roughness: 0.6, metalness: 0.5 });
  for (let i = 0; i < 6; i++) {
    p.box(steel, 0.12, (1.5 + r() * 2.5) * k, 0.12, (r() - 0.5) * w * 0.9, y, (r() - 0.5) * d * 0.9, 0, (r() - 0.5) * 0.9, (r() - 0.5) * 0.9);
  }
}

/** Tree species, by how common they are in town. */
export const SPECIES = ["maple", "linden", "oak", "maple", "linden", "birch", "cherry", "young", "spruce", "oak", "birch", "maple", "pine", "poplar", "linden", "cherry"];
const SHRUBS = ["bush", "bush", "bush_wide", "shrub", "flowers"];

/** Paint for a realistic prop: `wall` picks its tint (foliage, car paint). */
const tintOf = (i: number): Paint => ({ wall: i, accent: 0, roof: 0, signs: 0 });

/**
 * The grass texture alone is a lime green; this takes it to a mown lawn's
 * olive, beside the meadow round the town (land.ts tones that the same way).
 */
const LAWN_TINT = 0xbcae88;

/** Loose gravel or sand (paths, a pond's edge, a running track), tinted, from the shared texture library. */
function gravelMat(color: number, tile = 2.4): THREE.Material {
  return groundMat("gravel", tile, { roughness: 1, normal: 0.7, color });
}

/** A lawn: mown grass. */
export function lawn(): THREE.Material {
  return groundMat("grass", 2.2, { roughness: 0.95, normal: 0.8, color: LAWN_TINT });
}

/** A clipped hedge filling a box (w along x, d along z, from y up to y + h): segments stretched to fit. */
export function hedge(p: Parts, w: number, h: number, d: number, x: number, y: number, z: number, seed: number) {
  const alongX = w >= d;
  const L = alongX ? w : d;
  const D = alongX ? d : w;
  const base = Math.max(y, KERB);
  const n = Math.max(1, Math.round(L / 2));
  const scale = new THREE.Vector3(L / n / 2, (y + h - base) / 1.25, D / 0.7);
  for (let i = 0; i < n; i++) {
    const t = -L / 2 + (i + 0.5) * (L / n);
    for (const { role, geo } of realPiece("trees", "hedge")) p.add(realMat("trees", role, tintOf(seed), 0), geo, alongX ? x + t : x, base, alongX ? z : z + t, 0, alongX ? 0 : Math.PI / 2, 0, scale);
  }
}

/** A piece of street furniture; `phase` ("a" / "b") picks a crossing's signal cycle. */
export function furniture(p: Parts, name: string, x: number, y: number, z: number, ry = 0, scale?: THREE.Vector3, phase = "") {
  for (const { role, geo } of realPiece("street", name)) p.add(realMat("street", role, tintOf(0), 0, phase), geo, x, y, z, 0, ry, 0, scale);
}

/** A piece of the civic props model (civic.py): water tower, crane, scaffold, rubble, park pieces. */
export function civic(p: Parts, name: string, x: number, y: number, z: number, opts: { rx?: number; ry?: number; rz?: number; scale?: THREE.Vector3; paint?: Paint; damage?: number; swap?: (role: string) => THREE.Material | undefined } = {}) {
  const { rx = 0, ry = 0, rz = 0, scale, paint = tintOf(0), damage = 0, swap } = opts;
  for (const { role, geo } of realPiece("civic", name)) p.add(swap?.(role) ?? realMat("civic", role, paint, damage), geo, x, y, z, rx, ry, rz, scale);
}

/**
 * A fence or wall (a street piece: fence_panel, fence_rail, fence_iron,
 * wall_brick) from (x0, z0) to (x1, z1), its 2.4 m panels stretched to fit;
 * `h` scales its height. Its face (the piece's front) is to the right of the run.
 */
export function fenceRun(p: Parts, name: string, x0: number, z0: number, x1: number, z1: number, h = 1, y = KERB) {
  const dx = x1 - x0;
  const dz = z1 - z0;
  const L = Math.hypot(dx, dz);
  const n = Math.max(1, Math.round(L / 2.4));
  const ry = Math.atan2(-dz, dx);
  const scale = new THREE.Vector3(L / n / 2.4, h, 1);
  for (let i = 0; i < n; i++) {
    const t = (i + 0.5) / n;
    furniture(p, name, x0 + dx * t, y, z0 + dz * t, ry, scale);
  }
}

/** A garden shrub. */
export function shrub(p: Parts, x: number, z: number, seed: number, y = KERB, s = 1) {
  const r = rng(Math.floor(seed));
  const name = SHRUBS[Math.floor(r() * SHRUBS.length)];
  const k = s * (0.8 + r() * 0.4);
  const scale = new THREE.Vector3(k, k * (0.85 + r() * 0.3), k);
  const ry = r() * Math.PI * 2;
  const tint = tintOf(Math.floor(r() * 6));
  for (const { role, geo } of realPiece("trees", name)) p.add(realMat("trees", role, tint, 0), geo, x, y, z, 0, ry, 0, scale);
}

/** A tree; `s` (0.35-1.2) picks its size, `species` what it may be. */
export function tree(p: Parts, x: number, z: number, s: number, seed: number, y = 0, species = SPECIES) {
  const r = rng(seed);
  const name = species[Math.floor(r() * species.length)];
  const k = 0.5 + 0.55 * s;
  const scale = new THREE.Vector3(k, k * (0.88 + r() * 0.24), k);
  const ry = r() * Math.PI * 2;
  const tint = tintOf(Math.floor(r() * 6));
  for (const { role, geo } of realPiece("trees", name)) p.add(realMat("trees", role, tint, 0), geo, x, y, z, 0, ry, 0, scale);
}

/** Cars that park on drives and in bays, by how common they are. */
const PARKED = ["hatch", "sedan", "estate", "suv", "hatch", "sedan", "suv", "coupe", "pickup", "van", "estate", "hatch"];

/** A parked car, nose toward +z before ry. */
export function parked(p: Parts, x: number, z: number, ry: number, seed: number, y = KERB, pick?: { name?: string; paint?: number }) {
  const r = rng(seed);
  const name = pick?.name ?? PARKED[Math.floor(r() * PARKED.length)];
  const paint: Paint = { wall: pick?.paint ?? Math.floor(r() * CAR_PAINTS.length), accent: 0, roof: 0, signs: 0 };
  for (const { role, geo } of realPiece("cars", name)) p.add(realMat("cars", role, paint, 0), geo, x, y, z, 0, ry, 0);
}

const planter = (p: Parts, x: number, z: number, seed: number, s = 0.55) => {
  p.box(mat(0x9a948a, { roughness: 0.9 }), 1.6, 0.6, 1.6, x, KERB, z);
  tree(p, x, z, s, seed, KERB + 0.5);
};

/**
 * The town's lots built here rather than modelled: a water tower, and a
 * square or a park on one lot. Local frame: the lot's centre is
 * `yard` behind the origin, the street in front (+z).
 */
function utility(s: Spec): { group: THREE.Group; info: ModelInfo } {
  const g = new THREE.Group();
  const p = new Parts();
  const r = rng(s.seed * 13 + 7);
  const info: ModelInfo = { height: 4, emitters: [], beacons: [], night: [], debris: 0x7a7570 };
  const cz = -s.yard;
  const half = LOT / 2 - 0.4;
  if (s.style === "water") {
    // An elevated steel tank (civic.py), 22 m to its vent; broken, it leans.
    p.box(lawn(), LOT - 0.4, KERB + 0.04, LOT - 0.4, 0, 0, cz);
    const lean = s.damage >= 2 ? 0.07 : 0;
    civic(p, "water_tower", 0, KERB, cz, { rx: lean, rz: lean * 0.6, damage: s.damage });
    fenceRun(p, "fence_rail", -half, cz + half, half, cz + half, 0.9);
    info.height = KERB + 21.9;
    info.beacons.push(new THREE.Vector3(0, KERB + 22.0, cz));
  } else {
    const park = s.style === "park";
    p.box(park ? lawn() : groundMat("pave", 3.6, { roughness: 0.88, color: 0xe6e0d4 }), LOT - 0.4, KERB + 0.04, LOT - 0.4, 0, 0, cz);
    if (park) p.box(gravelMat(0xd8ccb0), 2.2, KERB + 0.06, LOT - 0.4, 0, 0, cz);
    const water = (role: string) => (role === "water" ? waterMat({ amp: 0.5, scale: 2.5, ring: [s.x + cz * Math.sin(s.rot), s.z + cz * Math.cos(s.rot)] }) : undefined);
    civic(p, "fountain", 0, KERB, cz, { scale: new THREE.Vector3(0.85, 0.85, 0.85), swap: water });
    if (s.damage === 0) p.extra(fountainSpray(0, KERB, cz, 0.85));
    const n = park ? 6 : 4;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + 0.4;
      tree(p, Math.cos(a) * 5.6, cz + Math.sin(a) * 5.6, 0.8 + r() * 0.3, Math.floor(r() * 1e6), KERB);
    }
    if (!park) for (const x of [-4.5, 4.5]) furniture(p, "bench", x, KERB, cz + 3.6);
    info.height = 6;
  }
  if (s.damage >= 1) info.emitters.push({ pos: new THREE.Vector3(0, info.height * 0.6, cz), kind: "smoke", rate: s.damage >= 2 ? 6 : 2 });
  p.into(g);
  g.position.set(s.x, 0, s.z);
  g.rotation.y = s.rot;
  return { group: g, info };
}

/** A gilded finial for a shiny building: rare, and meant to be noticed. */
function finial(p: Parts, y: number) {
  const gold = mat(0xd4a640, { metalness: 1, roughness: 0.25, emissive: 0x3a2400 });
  p.cyl(gold, 0.12, 0.3, 1.2, 0, y, 0, 8);
  p.add(gold, new THREE.SphereGeometry(0.45, 14, 10), 0, y + 1.6, 0);
  p.add(gold, new THREE.ConeGeometry(0.12, 1.4, 8), 0, y + 2.6, 0);
}

export function building(s: Spec): { group: THREE.Group; info: ModelInfo } {
  if (s.style === "water" || s.style === "square" || s.style === "park") return utility(s);
  const g = new THREE.Group();
  const p = new Parts();
  const r = rng(s.seed * 31 + 5);
  const def = realDef(s);
  if (!def) throw new Error(`no model for a ${s.kind} (${s.style})`);
  const info: ModelInfo = { height: s.height, emitters: [], beacons: [], night: [], debris: def.debris };
  const broken = s.damage >= 2;

  const yp = new Parts(YARD);
  realYard(yp, p, s, def, r);
  yp.into(g);

  // Heavy damage takes the top quarter off, roof and all.
  const floors = broken ? Math.max(1, Math.round(s.floors * (0.72 + r() * 0.1))) : s.floors;
  const top = stackReal(p, s, def, floors, !broken, info);
  if (top.anchors.smoke) info.emitters.push({ pos: top.anchors.smoke, kind: "smoke", rate: s.damage ? 0 : s.style === "factory" || s.style === "powerstation" ? 1.4 : 0.25 });
  if (top.anchors.beacon) info.beacons.push(top.anchors.beacon);
  if (broken) wreckTop(p, top.w, top.d, top.top, def.debris, r, THREE.MathUtils.clamp(top.top / 20, 0.4, 1));
  if (s.shiny && !broken) finial(p, top.top);

  if (s.damage >= 1) {
    const h = top.top;
    info.emitters.push({ pos: new THREE.Vector3((r() - 0.5) * top.w * 0.5, h + 0.5, (r() - 0.5) * top.d * 0.5), kind: "smoke", rate: broken ? 7 : 2.2 });
    if (broken) {
      info.emitters.push({ pos: new THREE.Vector3((r() - 0.5) * top.w * 0.4, h, (r() - 0.5) * top.d * 0.4), kind: "fire", rate: 14 });
      info.emitters.push({ pos: new THREE.Vector3(s.w * 0.51, h * (0.3 + r() * 0.4), 0), kind: "fire", rate: 5 });
    }
    // Scorch on the lawn.
    p.add(mat(0x1e1a18, { transparent: true, opacity: 0.6, depthWrite: false }), new THREE.CircleGeometry(s.w * 0.7, 12), 0, 0.1, 0, -Math.PI / 2);
  }

  p.into(g);
  g.position.set(s.x, 0, s.z);
  g.rotation.y = s.rot;
  return { group: g, info };
}

/** Models whose walls are brick or stone: their ruins keep ragged stumps of wall. */
const MASONRY = new Set(["a1", "a2", "s1", "s2", "s4", "c2", "l1", "f1", "e1", "p1", "l5", "e2", "e3", "p2", "w2"]);

/**
 * A ruin (damage 3) of a realistic building: the burnt shell left standing,
 * about half its storeys with a broken top and no roof, scorched and
 * blackened, broken masonry heaped against its walls; thin smoke, no fire.
 * It stands until repairs bring it back (docs/GAME.md).
 */
function shell(s: Spec, def: RealDef): { group: THREE.Group; info: ModelInfo } {
  const g = new THREE.Group();
  const p = new Parts();
  const r = rng(s.seed * 7 + 1);
  // Damage 3: the burnt materials, and black, empty window openings (realMat).
  const burnt: Spec = { ...s, damage: 3 };
  const info: ModelInfo = { height: s.height, emitters: [], beacons: [], night: [], debris: def.debris };
  const yp = new Parts(YARD);
  realYard(yp, p, burnt, def, r);
  yp.into(g);
  const floors = s.floors > 1 ? Math.max(1, Math.round(s.floors * (0.5 + r() * 0.12))) : 1;
  const top = stackReal(p, burnt, def, floors, false, info);
  info.height = top.top;
  {
    // The broken top: ragged stumps of wall along each edge (masonry) or
    // charred joists and rafters standing out of it (timber and glass).
    const paint: Paint = { wall: s.wall, accent: s.accent, roof: 0, signs: 0 };
    const y = top.top - 0.15;
    const [ww, wd, wx, wz] = def.walls ?? [def.w, def.d, 0, 0];
    if (MASONRY.has(def.id)) {
      const edges: [number, number, number, number][] = [
        [wx, wz + wd / 2 - 0.2, ww, 0],
        [wx, wz - wd / 2 + 0.2, ww, Math.PI],
        [wx + ww / 2 - 0.2, wz, wd, Math.PI / 2],
        [wx - ww / 2 + 0.2, wz, wd, -Math.PI / 2],
      ];
      for (const [x, z, len, a] of edges) {
        const n = Math.max(1, Math.round(len / 3.6));
        for (let i = 0; i < n; i++) {
          if (r() < 0.2) continue;
          const t = (i + 0.5) / n - 0.5;
          const along = t * (len - 0.6);
          civic(p, "rubble_wall", x + (a % Math.PI ? 0 : along), y, z + (a % Math.PI ? along : 0), { ry: a + (r() < 0.5 ? Math.PI : 0), scale: new THREE.Vector3(((len - 0.6) / n / 3.2) * 1.02, 0.45 + r() * 0.5, 1), paint, damage: 2 });
        }
      }
    }
    // Smaller beams on low buildings, where a girder would dwarf the walls.
    const k = THREE.MathUtils.clamp(top.top / 10, 0.4, 1);
    for (let i = 0; i < 2 + s.grade; i++) {
      civic(p, "rubble_beam", wx + (r() - 0.5) * ww * 0.7, y + 0.2 * k, wz + (r() - 0.5) * wd * 0.7, { ry: r() * Math.PI * 2, rx: (r() - 0.5) * 1.2, rz: (r() - 0.5) * 1.2, scale: new THREE.Vector3(k, k, k), damage: 2 });
    }
    for (let i = 0; i < 2; i++) civic(p, "rubble_slab", wx + (r() - 0.5) * ww * 0.5, y + 0.1, wz + (r() - 0.5) * wd * 0.5, { ry: r() * Math.PI * 2, rx: (r() - 0.5) * 0.8, damage: 1 });
  }
  // Scorch round the walls, and what fell from above heaped against them.
  p.add(mat(0x1a1714, { transparent: true, opacity: 0.7, depthWrite: false }), new THREE.CircleGeometry(Math.max(s.w, s.d) * 0.75, 16), 0, KERB + 0.02, 0, -Math.PI / 2);
  {
    const paint: Paint = { wall: s.wall, accent: s.accent, roof: 0, signs: 0 };
    const pile = 0.9 + s.grade * 0.4;
    const sides: [number, number, number][] = [
      [0, s.d / 2 + 0.6, 0],
      [s.w / 2 + 0.6, 0, Math.PI / 2],
      [-s.w / 2 - 0.6, 0, -Math.PI / 2],
    ];
    for (const [x, z, a] of sides) {
      if (r() < 0.25) continue;
      const along = (r() - 0.5) * (a ? s.d : s.w) * 0.5;
      const px = x + (a ? 0 : along);
      const pz = z + (a ? along : 0);
      const R = 1.6 + r() * 1.2;
      civic(p, "rubble_heap", px, KERB, pz, { ry: r() * Math.PI * 2, scale: new THREE.Vector3(R / 5, pile / 2.5, R / 5), damage: 1 });
      civic(p, "rubble_slab", px + (r() - 0.5) * 1.5, KERB + pile * 0.5, pz + (r() - 0.5) * 1.5, { ry: r() * Math.PI * 2, rx: (r() - 0.5) * 1.1, rz: (r() - 0.5) * 0.9, damage: 1 });
      if (r() < 0.6) civic(p, "rubble_wall", px, KERB + 0.1, pz, { ry: a + (r() - 0.5) * 0.6, rx: (r() - 0.5) * 0.4, scale: new THREE.Vector3(0.6 + r() * 0.4, 0.5 + r() * 0.4, 1), paint, damage: 2 });
    }
  }
  info.emitters.push({ pos: new THREE.Vector3((r() - 0.5) * s.w * 0.4, top.top, (r() - 0.5) * s.d * 0.4), kind: "smoke", rate: 0.9 });
  p.into(g);
  g.position.set(s.x, 0, s.z);
  g.rotation.y = s.rot;
  return { group: g, info };
}

export function rubble(s: Spec): { group: THREE.Group; info: ModelInfo } {
  const def = realDef(s);
  if (def) return shell(s, def);
  const g = new THREE.Group();
  const p = new Parts();
  const r = rng(s.seed * 7 + 1);
  const pile = 1.4 + s.grade * 0.9;
  p.box(mat(0x4a4642), LOT - 0.4, KERB + 0.04, LOT - 0.4, 0, 0, -s.yard);
  {
    // A heap of broken masonry (civic.py) with what is left standing or
    // thrown about on it: wall stumps in the building's brick, broken
    // slabs with their rebar out, bent beams; more of each for bigger buildings.
    const paint: Paint = { wall: s.wall, accent: s.accent, roof: 0, signs: 0 };
    const R = s.w * 0.62;
    civic(p, "rubble_heap", 0, 0, 0, { ry: r() * Math.PI * 2, scale: new THREE.Vector3(R / 5, pile / 2.5, R / 5), damage: 1 });
    const on = (d: number) => Math.max(0, pile * (1 - d * d) ** 1.4 - 0.3);
    for (let i = 0; i < 2 + s.grade; i++) {
      const a = r() * Math.PI * 2;
      const d = 0.55 + r() * 0.4;
      civic(p, "rubble_wall", Math.cos(a) * R * d, on(d) * 0.6, Math.sin(a) * R * d, { ry: -a + Math.PI / 2 + (r() - 0.5) * 0.6, rx: (r() - 0.5) * 0.25, scale: new THREE.Vector3(0.8 + r() * 0.5, 0.7 + r() * 0.6 + s.grade * 0.15, 1), paint, damage: 2 });
    }
    for (let i = 0; i < 3 + s.grade * 2; i++) {
      const a = r() * Math.PI * 2;
      const d = r() * 0.85;
      civic(p, "rubble_slab", Math.cos(a) * R * d, on(d), Math.sin(a) * R * d, { ry: r() * Math.PI * 2, rx: (r() - 0.5) * 1.1, rz: (r() - 0.5) * 0.9, damage: 1 });
    }
    for (let i = 0; i < 1 + s.grade; i++) {
      const a = r() * Math.PI * 2;
      const d = r() * 0.7;
      civic(p, "rubble_beam", Math.cos(a) * R * d, on(d) + 0.2, Math.sin(a) * R * d, { ry: r() * Math.PI * 2, rx: (r() - 0.5) * 0.5, damage: 2 });
    }
  }
  p.into(g);
  g.position.set(s.x, 0, s.z);
  g.rotation.y = s.rot;
  const info: ModelInfo = { height: pile, emitters: [{ pos: new THREE.Vector3(0, pile * 0.6, 0), kind: "smoke", rate: 0.8 }], beacons: [], night: [], debris: WALLS[s.wall] };
  return { group: g, info };
}

/** Points on the crane's pieces (civic.py), piece-local: the tie apex, beacons, the counter-jib's end. */
const CRANE: Record<string, Record<string, THREE.Vector3>> = {
  crane_slew: { apex: new THREE.Vector3(0, 5.2, 0), beacon: new THREE.Vector3(0, 5.75, 0) },
  crane_jib_tip: { beacon: new THREE.Vector3(-1.2, 0.75, 0) },
  crane_counter: { end: new THREE.Vector3(9.3, 0.05, 0) },
};

/** Construction site: built floors, scaffolding, a blueprint of the goal and a tower crane. */
export function site(s: SiteSpec): { group: THREE.Group; info: ModelInfo; jib: THREE.Group; ghost: THREE.Mesh } {
  const g = new THREE.Group();
  const p = new Parts();
  const info: ModelInfo = { height: s.height, emitters: [], beacons: [], night: [], debris: 0x8c8d8f };
  const built = Math.max(1, Math.floor(s.floors * s.progress));
  const builtH = built * s.floorH;
  const conc = mat(0xa9a6a0, { roughness: 0.95 });
  const col = mat(0x8f8c86, { roughness: 0.95 });
  p.box(mat(0x8a7a62, { roughness: 1 }), LOT - 0.4, KERB + 0.04, LOT - 0.4, 0, 0, -s.yard);
  p.box(conc, s.w + 0.6, 0.4, s.d + 0.6, 0, 0, 0);
  // Site fence along the street.
  const fence = mat(0x2f5a8a, { roughness: 0.8 });
  p.box(fence, LOT - 0.8, 1.9, 0.08, 0, KERB, LOT / 2 - s.yard - 0.4);
  for (let f = 1; f <= built; f++) p.box(conc, s.w, 0.3, s.d, 0, f * s.floorH - 0.3, 0);
  for (const [cx, cz] of [[-1, -1], [1, -1], [-1, 1], [1, 1], [0, -1], [0, 1], [-1, 0], [1, 0]]) {
    p.box(col, 0.45, builtH, 0.45, (cx * (s.w - 0.5)) / 2, 0, (cz * (s.d - 0.5)) / 2);
  }
  // Lower floors already finished: the real building, rising floor by floor.
  const clad = Math.max(0, built - 2);
  const def = realDef(s);
  if (clad > 0 && def) stackReal(p, s, def, clad, false, info);

  // Scaffolding one floor above the work.
  const sh = builtH + s.floorH;
  const gap = 0.8;
  const W = s.w + gap * 2;
  const D = s.d + gap * 2;
  {
    // Tube-and-fitting bays (civic.py), 2.4 m stretched to fit each face,
    // one lift a storey; red tubes while the site is being surrendered.
    const red = s.surrendering ? mat(0xc0392b, { metalness: 0.4, roughness: 0.5 }) : undefined;
    const swap = (role: string) => (role === "galv" ? red : undefined);
    const lift = new THREE.Vector3(1, s.floorH / 2, 1);
    for (const [len, ox, oz, ry] of [[W, 0, D / 2, 0], [W, 0, -D / 2, Math.PI], [D, W / 2, 0, Math.PI / 2], [D, -W / 2, 0, -Math.PI / 2]] as const) {
      const n = Math.max(1, Math.round(len / 2.4));
      const scale = lift.clone().setX(len / n / 2.4);
      const [dx, dz] = [Math.cos(ry), -Math.sin(ry)];
      for (let i = 0; i < n; i++) {
        const t = -len / 2 + (len * (i + 0.5)) / n;
        for (let y = 0; y < sh - 0.01; y += s.floorH) civic(p, "scaffold", ox + dx * t, y, oz + dz * t, { ry, scale, swap });
      }
    }
  }
  p.into(g);

  // The goal as a translucent blueprint: what completing will put here.
  const ghost = new THREE.Mesh(
    new THREE.BoxGeometry(s.w, s.height, s.d),
    new THREE.MeshBasicMaterial({ color: s.surrendering ? 0xff4030 : 0x7fd0ff, transparent: true, opacity: 0.12, depthWrite: false }),
  );
  ghost.position.y = s.height / 2;
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(ghost.geometry), new THREE.LineBasicMaterial({ color: s.surrendering ? 0xff6050 : 0xa8e0ff, transparent: true, opacity: 0.55 }));
  ghost.add(edges);
  g.add(ghost);

  // Tower crane (civic.py): base and mast sections, then a jib that turns
  // with its cab, counter-jib, pendant ties, trolley, hook and a load of steel.
  const crane = (p: Parts, name: string, x: number, y: number, z: number) => {
    civic(p, name, x, y, z);
    return CRANE[name] ?? {};
  };
  const cp = new Parts();
  const mx = s.w / 2 + 2.8;
  const mz = -s.d / 2 - 1.8;
  const sections = Math.ceil((Math.max(s.height + 8, 18) - 0.6) / 3);
  const mastH = 0.6 + sections * 3;
  crane(cp, "crane_base", mx, 0, mz);
  for (let i = 0; i < sections; i++) crane(cp, "crane_mast", mx, 0.6 + i * 3, mz);
  cp.into(g);
  const jib = new THREE.Group();
  jib.position.set(mx, mastH, mz);
  const jp = new Parts();
  const slew = crane(jp, "crane_slew", 0, 0, 0);
  const n = Math.max(4, Math.round((Math.max(16, s.w * 2.2) - 2) / 3));
  for (let i = 0; i < n; i++) crane(jp, "crane_jib", -1 - i * 3, 0, 0);
  const tipX = -1 - n * 3;
  const tip = crane(jp, "crane_jib_tip", tipX, 0, 0);
  const end = crane(jp, "crane_counter", 0, 0, 0).end;
  const reach = -tipX;
  const steel = mat(0x3a3c40, { metalness: 0.6, roughness: 0.4 });
  const tie = (a: THREE.Vector3, b: THREE.Vector3, t = 0.06) => {
    const d = b.clone().sub(a);
    const mid = a.clone().add(b).multiplyScalar(0.5);
    jp.box(steel, d.length(), t, t, mid.x, mid.y - t / 2, mid.z, 0, 0, Math.atan2(d.y, d.x));
  };
  tie(slew.apex, new THREE.Vector3(-reach * 0.62, 1.25, 0));
  tie(slew.apex, new THREE.Vector3(-reach * 0.3, 1.25, 0));
  tie(slew.apex, end);
  const hookX = -reach * 0.55;
  const drop = Math.max(4, mastH - builtH - 6);
  crane(jp, "crane_trolley", hookX, 0, 0);
  const rope = mat(0x222222);
  for (const dx of [-0.12, 0.12]) jp.box(rope, 0.04, drop - 0.45, 0.04, hookX + dx, -drop, 0);
  crane(jp, "crane_hook", hookX, -drop, 0);
  crane(jp, "crane_load", hookX, -drop, 0);
  jp.into(jib);
  g.add(jib);
  info.jibBeacons = [slew.beacon.clone(), tip.beacon.clone().add(new THREE.Vector3(tipX, 0, 0))];
  if (s.surrendering) info.emitters.push({ pos: new THREE.Vector3(0, builtH, 0), kind: "smoke", rate: 4 });
  else info.emitters.push({ pos: new THREE.Vector3(s.w * 0.3, builtH + 0.4, 0), kind: "smoke", rate: 0.6 });

  g.position.set(s.x, 0, s.z);
  g.rotation.y = s.rot;
  return { group: g, info, jib, ghost };
}

// ---- parks --------------------------------------------------------------------

function prop(p: Parts, name: string, x: number, z: number, ry = 0, s = 1, y = KERB) {
  const scale = new THREE.Vector3(s, s, s);
  if (name === "bench") return furniture(p, "bench", x, y, z, ry);
  // A fountain's water moves: calm small ripples, rings from where it lands, streaks down the jet and streams.
  const water = (role: string) => (role === "water" ? waterMat({ amp: 0.5, scale: 2.5, ring: [x, z] }) : undefined);
  civic(p, name, x, y, z, { ry, scale, swap: water });
}

/** A park lamp, lit at night. */
const lampPost = (p: Parts, x: number, z: number) => furniture(p, "lamp_heritage", x, KERB, z);

/** The master plan's park spots in block-local coordinates: the centre, then the quarters. Matches `PARK_SPOTS` in economy.rs. */
export const SPOTS: [number, number][] = [[0, 0], [-17, -8], [17, -8], [-17, 8], [17, 8]];

/** A decoration the mayor bought, on its spot (world coordinates). */
function decoration(p: Parts, id: string, x: number, z: number, seed: number, onLawn: boolean) {
  const flat = (m: THREE.Material, g: THREE.BufferGeometry, y = KERB + 0.025) => p.add(m, g, x, y, z, -Math.PI / 2);
  if (onLawn && id !== "trees") flat(gravelMat(0xdccfae), new THREE.CircleGeometry(5.6, 32));
  switch (id) {
    case "trees":
      for (let i = 0; i < 6; i++) {
        const a = (i / 6) * Math.PI * 2 + 0.3;
        tree(p, x + Math.cos(a) * 4.4, z + Math.sin(a) * 4.4, 0.75, seed + i, KERB);
      }
      break;
    case "benches":
      for (let i = 0; i < 4; i++) {
        const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
        prop(p, "bench", x + Math.cos(a) * 3.6, z + Math.sin(a) * 3.6, Math.atan2(-Math.cos(a), -Math.sin(a)));
      }
      for (const sx of [-1, 1]) lampPost(p, x + sx * 4.8, z);
      break;
    case "fountain":
      flat(groundMat("ashlar", 2.4, { roughness: 0.85, color: 0xd4c8b4 }), new THREE.CircleGeometry(5, 40), KERB + 0.03);
      prop(p, "fountain", x, z, 0, 1.1);
      p.extra(fountainSpray(x, KERB, z, 1.1));
      break;
    case "statue": {
      // The founder in bronze on a stepped granite plinth.
      const stone = mat(0x8e8a84, { roughness: 0.6 });
      p.box(stone, 2.6, 0.4, 2.6, x, KERB, z);
      p.box(stone, 1.6, 2.2, 1.6, x, KERB + 0.4, z);
      const bronze = mat(0x6a5236, { metalness: 0.85, roughness: 0.38 });
      for (const { geo } of realPiece("civic", "person")) p.add(bronze, geo, x, KERB + 2.6, z, 0, Math.PI, 0, new THREE.Vector3(1.35, 1.35, 1.35));
      break;
    }
    case "bandstand":
      prop(p, "bandstand", x, z, 0, 0.9);
      break;
  }
}

/**
 * A park block in place of a district, in world coordinates: a green or a
 * park (lawn and paths), a plaza or a football ground. The master plan's
 * decorations stand on its spots; without a plan, the old dressing stands.
 */
export function park(p: Parts, k: ParkSpec, pole: THREE.Material, bulb: THREE.Material) {
  const r = rng(k.seed);
  const { x: X, z: Z } = k;
  const W = BLOCK_X;
  const D = BLOCK_Z;
  const lawn_ = lawn();
  const paving = groundMat("pave", 3.6, { roughness: 0.88, color: 0xf2eee6 });
  const flat = (m: THREE.Material, g: THREE.BufferGeometry, x: number, z: number, y = KERB + 0.02) => p.add(m, g, X + x, y, Z + z, -Math.PI / 2);
  const bench = (x: number, z: number, ry: number) => prop(p, "bench", X + x, Z + z, ry);
  const planned = k.decorations !== undefined;
  if (planned && k.kind !== "sports") {
    const onLawn = k.kind !== "plaza";
    if (onLawn) {
      // A green: lawn, paths crossing it, trees round the edge.
      p.box(lawn_, W, KERB, D, X, 0, Z);
      const path = gravelMat(0xe0d0a8);
      p.box(path, W, KERB + 0.03, 2.2, X, 0, Z);
      p.box(path, 2.2, KERB + 0.03, D, X, 0, Z);
      for (let i = 0; i < 14; i++) {
        const t = (i + 0.5) / 14;
        tree(p, X - W / 2 + 2 + t * (W - 4), Z + (i % 2 ? 1 : -1) * (D / 2 - 1.6), 0.55 + r() * 0.3, k.seed + i, KERB);
      }
      for (const [x, z] of [[-4, -4], [4, 4]]) lampPost(p, X + x, Z + z);
    } else {
      // A plaza: paving with a stone ring at its heart, planters at the ends.
      p.box(paving, W, KERB, D, X, 0, Z);
      flat(groundMat("ashlar", 2.4, { roughness: 0.8, color: 0xf0ebe0 }), new THREE.RingGeometry(7.2, 8, 48), 0, 0, KERB + 0.03);
      for (const x of [-29, 29]) for (const z of [-12, 0, 12]) planter(p, X + x, Z + z, k.seed + x * 3 + z, 0.75);
      for (const [x, z] of [[-8, -12], [8, -12], [-8, 12], [8, 12]]) lampPost(p, X + x, Z + z);
    }
    k.decorations!.forEach((d, i) => {
      const [sx, sz] = SPOTS[i] ?? [0, 0];
      if (d) decoration(p, d, X + sx, Z + sz, k.seed + i * 101, onLawn);
    });
    return;
  }
  switch (k.kind) {
    case "plaza": {
      p.box(paving, W, KERB, D, X, 0, Z);
      flat(groundMat("ashlar", 2.4, { roughness: 0.85, color: 0xd4c8b4 }), new THREE.CircleGeometry(10, 48), 0, 0);
      flat(groundMat("ashlar", 2.4, { roughness: 0.8, color: 0xf0ebe0 }), new THREE.RingGeometry(10, 10.8, 48), 0, 0, KERB + 0.03);
      prop(p, "fountain", X, Z, 0, 1.45);
      p.extra(fountainSpray(X, KERB, Z, 1.45));
      for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2 + Math.PI / 8;
        // Benches face the fountain (a bench's front is +z before turning).
        bench(Math.cos(a) * 7.4, Math.sin(a) * 7.4, Math.atan2(-Math.cos(a), -Math.sin(a)));
      }
      for (const z of [-11.5, 11.5]) for (let x = -27; x <= 27; x += 9) planter(p, X + x, Z + z, k.seed + x * 3 + z, 0.75);
      for (const [x, z] of [[-24, 0], [24, 0]]) {
        p.box(lawn_, 12, KERB + 0.12, 9, X + x, 0, Z + z);
        for (let i = 0; i < 5; i++) tree(p, X + x + (r() - 0.5) * 9, Z + z + (r() - 0.5) * 6, 0.35 + r() * 0.2, k.seed + 40 + i + x, KERB + 0.1);
      }
      for (const [x, z] of [[-14, -6], [14, -6], [-14, 6], [14, 6]]) lampPost(p, X + x, Z + z);
      break;
    }
    case "park": {
      p.box(lawn_, W, KERB, D, X, 0, Z);
      // A loop path round the lawn, with a cut through the middle.
      const path = gravelMat(0xe0d0a8);
      const ax = W / 2 - 6;
      const az = D / 2 - 4.5;
      const n = 36;
      const ring: [number, number][] = Array.from({ length: n }, (_, i) => [Math.cos((i / n) * Math.PI * 2) * ax, Math.sin((i / n) * Math.PI * 2) * az]);
      ring.forEach(([x0, z0], i) => {
        const [x1, z1] = ring[(i + 1) % n];
        p.box(path, Math.hypot(x1 - x0, z1 - z0) + 0.6, KERB + 0.03, 2.2, X + (x0 + x1) / 2, 0, Z + (z0 + z1) / 2, -Math.atan2(z1 - z0, x1 - x0));
        if (i % 6 === 3) lampPost(p, X + x0 * 1.09, Z + z0 * 1.14);
        if (i % 6 === 0) bench(x0 * 0.9, z0 * 0.86, Math.atan2(x0, z0));
      });
      p.box(path, 2.2, KERB + 0.03, D, X + 4, 0, Z);
      // A pond with a sandy edge, and the bandstand across the lawn.
      const pond = { x: -12, z: 1, rx: 10, rz: 5.5 };
      const sand = new THREE.CircleGeometry(1, 28).scale(pond.rx + 0.9, pond.rz + 0.9, 1);
      flat(gravelMat(0xd8c490), sand, pond.x, pond.z, KERB + 0.025);
      flat(waterMat({ amp: 0.9, scale: 1.7, color: 0x1d3c3a }), new THREE.CircleGeometry(1, 28).scale(pond.rx, pond.rz, 1), pond.x, pond.z, KERB + 0.04);
      prop(p, "bandstand", X + 16, Z - 1);
      // Trees wherever the paths, the pond and the bandstand leave room.
      for (let i = 0, placed = 0; i < 400 && placed < 34; i++) {
        const x = (r() - 0.5) * (W - 3);
        const z = (r() - 0.5) * (D - 3);
        const e = Math.hypot(x / ax, z / az);
        if (Math.abs(e - 1) < 0.16 || Math.abs(x - 4) < 2.5) continue;
        if (Math.hypot((x - pond.x) / (pond.rx + 3), (z - pond.z) / (pond.rz + 3)) < 1) continue;
        if (Math.hypot(x - 16, z + 1) < 6) continue;
        tree(p, X + x, Z + z, 0.6 + r() * 0.45, k.seed + i, KERB);
        placed++;
      }
      break;
    }
    case "sports": {
      p.box(lawn_, W, KERB, D, X, 0, Z);
      const pz = -3;
      const [pw, pd] = [46, 22];
      // A rubber-crumb surround and a mown pitch: light and dark bands of one turf.
      p.box(gravelMat(0xff8a68, 1.6), pw + 6, KERB + 0.02, pd + 5, X, 0, Z + pz);
      for (let i = 0; i < 10; i++) {
        const turf = groundMat("grass", 1.8, { roughness: 0.95, normal: 0.6, color: i % 2 ? 0xa8c888 : 0xc4dca0 });
        p.box(turf, pw / 10, KERB + 0.04, pd, X - pw / 2 + (i + 0.5) * (pw / 10), 0, Z + pz);
      }
      const white = mat(0xf2f2ea, { roughness: 0.7 });
      const ly = KERB + 0.045;
      const line = (w: number, d: number, x: number, z: number) => p.box(white, w, 0.02, d, X + x, ly, Z + pz + z);
      line(pw, 0.15, 0, -pd / 2);
      line(pw, 0.15, 0, pd / 2);
      for (const sx of [-1, 1]) {
        line(0.15, pd, (sx * pw) / 2, 0);
        line(0.15, 11, sx * (pw / 2 - 6), 0);
        line(6, 0.15, sx * (pw / 2 - 3), -5.5);
        line(6, 0.15, sx * (pw / 2 - 3), 5.5);
        prop(p, "goal", X + (sx * pw) / 2, Z + pz, -sx * Math.PI / 2);
      }
      line(0.15, pd, 0, 0);
      p.add(white, new THREE.RingGeometry(4.2, 4.35, 64), X, ly + 0.02, Z + pz, -Math.PI / 2);
      for (const x of [-9, 9]) prop(p, "bleachers", X + x, Z + 10.2, Math.PI);
      // Floodlights at the corners.
      for (const sx of [-1, 1]) {
        for (const sz of [-1, 1]) {
          const x = X + sx * (pw / 2 + 4);
          const z = Z + pz + sz * (pd / 2 + 2.2);
          // A tapered mast with a footing, and a frame of six lamps tipped at the pitch.
          p.cyl(pole, 0.45, 0.5, 0.4, x, KERB, z, 16);
          p.cyl(pole, 0.13, 0.24, 13, x, KERB + 0.4, z, 16);
          p.box(pole, 2.4, 0.12, 0.12, x, KERB + 13.1, z);
          p.box(pole, 2.4, 0.12, 0.12, x, KERB + 14.1, z);
          for (const lx of [-0.8, 0, 0.8]) for (const ly of [13.35, 14.35]) {
            p.box(pole, 0.62, 0.62, 0.3, x + lx, KERB + ly - 0.31, z + sz * 0.05, 0, -0.5 * sz);
            p.box(bulb, 0.5, 0.5, 0.06, x + lx, KERB + ly - 0.25, z - sz * 0.13, 0, -0.5 * sz);
          }
        }
      }
      for (let i = 0; i < 8; i++) tree(p, X + (r() < 0.5 ? -1 : 1) * (28 + r() * 3), Z + (r() - 0.5) * (D - 4), 0.7 + r() * 0.3, k.seed + i, KERB);
      break;
    }
  }
}
