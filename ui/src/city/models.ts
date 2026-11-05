// City theme, step 2: 3D models for the plan's specs. Buildings and trees
// are stacked from the Blender kit (kit.ts) with materials picked per
// building and damage, or from a realistic model (real.ts) for the styles
// one replaces; lots, wreckage, rubble and the construction site are built
// here from boxes. Geometry is merged per material to keep draw calls low.
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { NOMINAL, piece } from "./kit";
import { BLOCK_X, BLOCK_Z, LOT, lot, rng, type ParkSpec, type SiteSpec, type Spec } from "./plan";
import { CAR_PAINTS, DEFS, groundMat, hasReal, realMat, realPiece, type Paint, type RealDef } from "./real";
import { ATLAS, panes, type Pane } from "./textures";

export const WALLS = [0xe8d9c0, 0xd9c2a5, 0xc9d3d8, 0xe6c9b5, 0xb9c4b0, 0xd8d0e0, 0xcfb59b, 0xe9e4da];
export const GLASS = [0x7f9bb3, 0x6d8a99, 0x8fa3b8, 0x5d7488, 0x9ab0a8, 0x7a8aa8, 0x8a98b0, 0x6f8c9c];
export const ACCENTS = [0xb5483a, 0x3a6fb5, 0x3a9a6a, 0xc9902a, 0x7a4ab5, 0x2f3a4a];
/** Cottage roofs, by accent: terracotta, slate, moss, clay, plum, charcoal. */
const ROOFS = [0xa8503c, 0x56606e, 0x5e6e4a, 0xb8764a, 0x6e4a5a, 0x3e4044];
const LEAVES = [0x4f7a3a, 0x5d8a42, 0x3f6a34, 0x6a8f3e, 0x48703f];
const BLOSSOMS = [0xf2a5c0, 0xf7c6d6, 0xe88aa8, 0xf5e0ea];
const BRICKS = [0x8a4e3c, 0x9a5a44, 0x7a4636, 0xa0664a, 0x6e3e30, 0x94604c];

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

const UP = new THREE.Vector3(0, 1, 0);
/** Lots, pavements and park lawns sit at kerb height. */
export const KERB = 0.2;
const CAR_PAINT = [0xa8acb0, 0x2a2e36, 0xa83a32, 0x2f5a8a, 0xbcb8b0, 0x5a6a4a, 0x8a6a3a, 0x3a3e44];

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

  /**
   * `cells` moves window panes to another cell of the kit's atlas; `shift`
   * adds to UV x, which for realistic glass gives its windows new ids (other
   * rooms, curtains and lights).
   */
  add(material: THREE.Material, g: THREE.BufferGeometry, x: number, y: number, z: number, rx = 0, ry = 0, rz = 0, scale?: THREE.Vector3, cells?: [number, number], shift = 0) {
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
    if (cells) {
      const uv = geo.getAttribute("uv") as THREE.BufferAttribute;
      for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) + cells[0] / ATLAS, uv.getY(i) + cells[1] / ATLAS);
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

  into(group: THREE.Group, shadows = true) {
    for (const [material, list] of this.byMat) {
      const mesh = new THREE.Mesh(mergeGeometries(list), material);
      mesh.castShadow = shadows;
      mesh.receiveShadow = true;
      group.add(mesh);
    }
  }
}

function shade(color: number, damage: number): THREE.Color {
  return new THREE.Color(color).multiplyScalar([1, 0.78, 0.5][Math.min(2, damage)]);
}

// ---- kit materials -----------------------------------------------------------

interface RoleLook {
  color: number;
  rough?: number;
  metal?: number;
  emissive?: number;
  night?: number;
  double?: boolean;
}

/** Roles whose look does not depend on the building. */
const ROLES: Record<string, RoleLook> = {
  trim: { color: 0xe6dfd2, rough: 0.75 },
  stone: { color: 0xa9a094, rough: 0.9 },
  frame: { color: 0xf3f0ea, rough: 0.6 },
  deck: { color: 0x505256, rough: 0.95 },
  canvas: { color: 0xf2ede0, rough: 0.9, double: true },
  board: { color: 0x1d2024, rough: 0.6 },
  shopfront: { color: 0x2a323c, rough: 0.2, metal: 0.4, emissive: 0xffd9a0, night: 0.9 },
  lobby: { color: 0x2a323c, rough: 0.2, metal: 0.4, emissive: 0xffe2b8, night: 0.5 },
  crownlight: { color: 0x8a6a3a, rough: 0.3, metal: 0.3, emissive: 0xffc870, night: 1.6 },
  door: { color: 0x4a2f20, rough: 0.6 },
  metal: { color: 0x8c9298, rough: 0.4, metal: 0.6 },
  dark: { color: 0x2e2c2a, rough: 0.9 },
  gold: { color: 0xd9a441, rough: 0.3, metal: 0.85, emissive: 0xffb84a, night: 0.9 },
  brick: { color: 0x8a4e3c, rough: 0.9 },
  wood: { color: 0x6e4a32, rough: 0.85 },
  bark: { color: 0x5a4030, rough: 1 },
  paint: { color: 0xf0e8d0, rough: 0.7 },
  railglass: { color: 0x5a7080, rough: 0.15, metal: 0.4 },
  crane: { color: 0xe8b020, rough: 0.5, metal: 0.3 },
  concrete: { color: 0x9a9890, rough: 0.95 },
  grate: { color: 0x4a4c50, rough: 0.6, metal: 0.5 },
  birch: { color: 0xe8e4dc, rough: 0.9 },
  carglass: { color: 0x1a2028, rough: 0.1, metal: 0.6 },
  steel: { color: 0x3e5a52, rough: 0.5, metal: 0.5 },
  led: { color: 0x9ab0c8, rough: 0.3, metal: 0.2, emissive: 0xd8ecff, night: 2 },
  water: { color: 0x4a86a0, rough: 0.08, metal: 0.3 },
  tyre: { color: 0x1a1a1a, rough: 0.9 },
  chrome: { color: 0xc8ccd0, rough: 0.3, metal: 0.8 },
  headlight: { color: 0xf0ecd8, rough: 0.3 },
  taillight: { color: 0x8a1810, rough: 0.4 },
  taxisign: { color: 0xf2c12e, rough: 0.5 },
};

const kitShared = new Map<string, THREE.MeshStandardMaterial>();

/** A kit material: lit by the baked occlusion in the vertex colours. */
function kitMat(look: RoleLook, damage: number): THREE.MeshStandardMaterial {
  const key = `${JSON.stringify(look)}:${damage}`;
  let m = kitShared.get(key);
  if (!m) {
    m = new THREE.MeshStandardMaterial({
      color: shade(look.color, damage),
      roughness: look.rough ?? 0.8,
      metalness: look.metal ?? 0,
      vertexColors: true,
      side: look.double ? THREE.DoubleSide : THREE.FrontSide,
    });
    // Burnt-out shops and lobbies stay dark.
    if (look.emissive !== undefined && damage < 2) {
      m.emissive.setHex(look.emissive);
      m.emissiveIntensity = 0;
      m.userData.night = look.night;
    }
    kitShared.set(key, m);
  }
  return m;
}

/** Window panes: one atlas cell each, lit at night, smashed when broken. */
function paneMat(kind: Pane, color: number, damage: number): THREE.MeshStandardMaterial {
  const key = `pane:${kind}:${color}:${damage}`;
  let m = kitShared.get(key);
  if (!m) {
    const set = panes(kind);
    const broken = damage >= 2;
    const glass = kind === "glass";
    m = new THREE.MeshStandardMaterial({
      map: broken ? set.brokenMap : set.map,
      emissiveMap: broken ? set.brokenEmissive : set.emissive,
      emissive: 0xffffff,
      emissiveIntensity: 0,
      color: shade(color, damage),
      roughness: glass ? 0.12 : 0.25,
      metalness: glass ? 0.6 : 0.2,
      envMapIntensity: glass ? 1.4 : 1,
      vertexColors: true,
    });
    m.userData.night = damage === 1 ? 0.35 : 0.6;
    kitShared.set(key, m);
  }
  return m;
}

type Look = (role: string) => THREE.MeshStandardMaterial;

/** The plain material for a kit role (bridges, street furniture). */
export const kitLook: Look = (role) => kitMat(ROLES[role] ?? ROLES.metal, 0);

/** Materials for a building's roles; night-lit ones are collected in info. */
function looks(s: Spec, info: ModelInfo): Look {
  const office = s.kind === "office";
  const wall = office ? new THREE.Color(GLASS[s.wall]).lerp(new THREE.Color(0xe0e0dc), 0.7).getHex() : WALLS[s.wall];
  const byRole: Record<string, RoleLook> = {
    wall: { color: wall, rough: 0.85 },
    roof: { color: ROOFS[s.accent], rough: 0.8 },
    accent: { color: ACCENTS[s.accent], rough: 0.7, double: true },
    sign: { color: ACCENTS[s.accent], emissive: new THREE.Color(ACCENTS[s.accent]).lerp(new THREE.Color(0xffffff), 0.35).getHex(), night: 1.8 },
    spandrel: { color: new THREE.Color(office ? GLASS[s.wall] : 0x4a4e58).multiplyScalar(0.45).getHex(), rough: 0.3, metal: 0.5 },
    leaf: { color: LEAVES[s.seed % LEAVES.length], rough: 0.9 },
    brick: { color: BRICKS[s.wall % BRICKS.length], rough: 0.9 },
  };
  const glass = office ? GLASS[s.wall] : s.kind === "landmark" ? 0xb4c0cc : 0xa8bccc;
  const seen = new Set<THREE.MeshStandardMaterial>();
  return (role) => {
    const m =
      role === "window" ? paneMat("window", 0xffffff, s.damage)
      : role === "glass" ? paneMat("glass", glass, s.damage)
      : kitMat(byRole[role] ?? ROLES[role] ?? { color: 0xff00ff }, s.damage);
    if (m.userData.night && !seen.has(m)) {
      seen.add(m);
      info.night.push(m);
    }
    return m;
  };
}

/** Puts a kit piece on the stack at height y, scaled to the footprint and turned by ry. */
function put(p: Parts, name: string, y: number, sx: number, sz: number, look: Look, r: () => number, ry = 0) {
  const cells: [number, number] = [Math.floor(r() * ATLAS), Math.floor(r() * ATLAS)];
  const scale = new THREE.Vector3(sx, 1, sz);
  for (const { role, geo } of piece(name).parts) {
    p.add(look(role), geo, 0, y, 0, 0, ry, 0, scale, role === "window" || role === "glass" ? cells : undefined);
  }
  return piece(name).anchors;
}

/**
 * Stacks the first `floors` storeys of a building from the kit, and its roof
 * if `roof`. Returns the height reached, the footprint there, and anchors
 * (piece-local, already moved onto the stack).
 */
function stack(p: Parts, s: Spec, look: Look, floors: number, roof: boolean) {
  const r = rng(s.seed * 13 + 7);
  const variant = (n: number) => "abcd"[Math.floor(r() * n)];
  const [W0, D0] = NOMINAL[s.kind];
  const sx = s.w / W0;
  const sz = s.d / D0;
  const fh = s.floorH;
  const anchors: Record<string, THREE.Vector3> = {};
  let k = 1;
  const place = (name: string, y: number, ry = 0) => {
    for (const [key, a] of Object.entries(put(p, name, y, sx * k, sz * k, look, r, ry))) {
      anchors[key] = new THREE.Vector3(a.x * sx * k, a.y + y, a.z * sz * k).applyAxisAngle(UP, ry);
    }
  };
  switch (s.style) {
    case "modern":
    case "aframe": {
      const v = s.style === "modern" ? "e" : "f";
      if (floors > 0) place(`cottage_body_${v}`, 0);
      if (roof) place(`cottage_roof_${v}`, fh);
      return { top: floors * fh, w: s.w, d: s.d, anchors };
    }
    case "diner":
    case "factory": {
      const [g, rf] = s.style === "diner" ? ["shop_ground_d", "shop_roof_d"] : ["factory_ground", "factory_roof"];
      if (floors > 0) place(g, 0);
      if (roof) place(rf, fh);
      return { top: floors * fh, w: s.w, d: s.d, anchors };
    }
    case "townhouse": {
      for (let f = 0; f < floors; f++) place(f === 0 ? "town_ground" : "town_floor", f * fh);
      if (roof) place("town_roof", floors * fh);
      return { top: floors * fh, w: s.w, d: s.d, anchors };
    }
    case "round": {
      const lower = Math.max(1, Math.round(s.floors * 0.68));
      for (let f = 0; f < floors; f++) {
        if (f === lower) {
          place("round_setback", f * fh);
          k = 0.78;
        }
        place(f === 0 ? "round_ground" : "round_floor", f * fh);
      }
      if (roof) place("round_roof", floors * fh);
      return { top: floors * fh, w: s.w * k, d: s.d * k, anchors };
    }
    case "twist": {
      // Each storey turns a little and the tower tapers: a quarter turn in all.
      const step = Math.PI / 2 / s.floors;
      const at = (f: number) => 1 - 0.14 * (f / s.floors);
      for (let f = 0; f < floors; f++) {
        k = f === 0 ? 1 : at(f);
        place(f === 0 ? "lm3_ground" : "lm3_floor", f * fh, f === 0 ? 0 : f * step);
      }
      k = at(floors);
      if (roof) place("lm3_crown", floors * fh, floors * step);
      return { top: floors * fh, w: s.w * k * 0.9, d: s.d * k * 0.9, anchors };
    }
    case "tvtower": {
      // A concrete shaft with the observation pod three quarters up.
      const pod = Math.round(s.floors * 0.74);
      for (let f = 0; f < floors; f++) {
        if (f === 0) place("tvt_base", 0);
        else if (f === pod) place("tvt_pod", f * fh);
        else if (f !== pod + 1) place("tvt_shaft", f * fh);
      }
      if (roof) place("tvt_spire", floors * fh);
      k = 0.32;
      return { top: floors * fh, w: s.w * k, d: s.d * k, anchors };
    }
  }
  switch (s.kind) {
    case "cottage": {
      const v = variant(4);
      if (floors > 0) place(`cottage_body_${v}`, 0);
      if (roof) place(`cottage_roof_${v}`, fh);
      break;
    }
    case "shop":
    case "apartment": {
      const shop = s.kind === "shop";
      const pre = shop ? "shop" : "apt";
      const fv = variant(3);
      const rv = variant(2);
      // Brick walk-ups (apartment c) have their own ground storey and roof.
      const ground = shop ? `shop_ground_${fv}` : fv === "c" ? "apt_ground_c" : "apt_ground";
      for (let f = 0; f < floors; f++) place(f === 0 ? ground : `${pre}_floor_${fv}`, f * fh);
      if (roof) place(!shop && fv === "c" ? "apt_roof_c" : `${pre}_roof_${rv}`, floors * fh);
      break;
    }
    case "office": {
      const fv = variant(3);
      const rv = variant(2);
      const lower = Math.max(1, Math.round(s.floors * 0.68));
      for (let f = 0; f < floors; f++) {
        if (f === lower) {
          place("office_setback", f * fh);
          k = 0.78;
        }
        place(f === 0 ? "office_ground" : `office_floor_${fv}`, f * fh);
      }
      if (roof) place(`office_roof_${rv}`, floors * fh);
      break;
    }
    case "landmark": {
      // Art deco stone and gold, or a modern glass tower with sky gardens.
      const pre = s.style === "glass" ? "lm2" : "lm";
      const e1 = Math.round(s.floors * 0.5);
      const e2 = Math.round(s.floors * 0.8);
      let tier = 1;
      for (let f = 0; f < floors; f++) {
        const t = f < e1 ? 1 : f < e2 ? 2 : 3;
        if (t !== tier) place(`${pre}_ledge_${tier}`, f * fh);
        tier = t;
        place(f === 0 ? `${pre}_ground` : `${pre}_floor_${t}`, f * fh);
      }
      if (roof) place(`${pre}_crown`, floors * fh);
      // Landmark tiers are modelled at their own sizes; k is only the top's.
      k = [1, 0.78, 0.56][tier - 1];
      break;
    }
  }
  return { top: floors * fh, w: s.w * k, d: s.d * k, anchors };
}

// ---- realistic models -----------------------------------------------------------

/**
 * The realistic model that draws a spec, if it is loaded. A model takes over
 * the kit style it replaces (docs/models.md) as a whole, until its siblings
 * exist to take their own variants of it; siblings (C1 and C2 for the
 * classic cottage) share the style, picked per building from its seed.
 */
export function realDef(s: Spec): RealDef | null {
  if (s.model) return DEFS[s.model] && hasReal(s.model) ? DEFS[s.model] : null;
  const defs = Object.values(DEFS).filter((d) => d.kind === s.kind && d.style === s.style && hasReal(d.id));
  return defs.length ? defs[Math.floor(rng(s.seed * 29 + 3)() * defs.length)] : null;
}

/** A spec sized and placed for its realistic model (real-world sizes, not the kit's); others unchanged. */
export function fitReal<T extends Spec>(s: T): T {
  const def = realDef(s);
  if (!def) return s;
  const l = lot(s.index);
  const yard = LOT / 2 - def.d / 2 - def.front;
  const floors = def.floors(s.floors);
  return { ...s, w: def.w, d: def.d, floors, floorH: def.top(floors) / floors, height: def.height(floors), yard, x: l.x + Math.sin(l.rot) * yard, z: l.z + Math.cos(l.rot) * yard };
}

const paintOf = (s: Spec): Paint => ({ wall: s.wall, accent: s.accent, roof: Math.floor(s.seed / 7) % 97, signs: Math.floor(s.seed / 3) % 8 });

/** Adds a piece of a realistic model; glass gets window ids of its own from `shift`. */
function putReal(p: Parts, def: RealDef, piece: string, paint: Paint, damage: number, info: ModelInfo | null, x: number, y: number, z: number, ry = 0, scale?: THREE.Vector3, shift = 0) {
  for (const { role, geo } of realPiece(def.id, piece)) {
    const m = realMat(def.id, role, paint, damage);
    if (info && m.userData.night && !info.night.includes(m as THREE.MeshStandardMaterial)) info.night.push(m as THREE.MeshStandardMaterial);
    p.add(m, geo, x, y, z, 0, ry, 0, scale, undefined, role.endsWith("glass") ? shift : 0);
  }
}

/** Stacks a realistic model's pieces on the lot (at kerb height), like stack() for the kit. */
function stackReal(p: Parts, s: Spec, def: RealDef, floors: number, roof: boolean, info: ModelInfo) {
  const r = rng(s.seed * 13 + 11);
  const paint = paintOf(s);
  // Window ids restart in every piece: offset them per storey and building.
  const base = (s.seed % 8) * 8 * 256;
  def.stack(floors, roof, r).forEach(({ piece, y }, i) => putReal(p, def, piece, paint, s.damage, info, 0, y + KERB, 0, 0, undefined, base + i * 256));
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

/** The lot round a realistic model; like yard() for the kit. */
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
      if (hasReal("street")) fenceRun(p, "wall_brick", half, back + 0.12, -half, back + 0.12, 1.5);
      else p.box(mat(0x7a4636, { roughness: 0.95 }), LOT - 0.4, 1.6, 0.25, 0, KERB, back + 0.12);
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
      if (hasReal("street")) for (const x of [-half + 0.1, half - 0.1]) fenceRun(p, "fence_panel", x, yb, x, back + 0.6);
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
      if (hasReal("street")) {
        fenceRun(p, "fence_rail", -half + 0.2, fz, -0.6, fz);
        fenceRun(p, "fence_rail", 0.6, fz, dx - 1.6, fz);
      }
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
    case "s3": {
      // An asphalt forecourt to the pavement with a car drawn up beside the
      // steps and shrubs either side of them; behind, a concrete service yard
      // round the kitchen with bins, a grease drum and gas bottles, fenced.
      const asphalt = hasReal("street") ? groundMat("asphalt", 6, { roughness: 0.93, color: 0xb4b4b4 }) : mat(0x3a3c40, { roughness: 0.95 });
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
      if (hasReal("street")) fenceRun(p, "fence_panel", half, back + 0.1, -half, back + 0.1);
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
      if (hasReal("street")) {
        fenceRun(p, "wall_brick", half - 0.12, back + 0.12, -half + 0.12, back + 0.12, 1.8);
        fenceRun(p, "wall_brick", -half + 0.12, back + 0.12, -half + 0.12, yardZ, 1.8);
        fenceRun(p, "wall_brick", half - 0.12, yardZ, half - 0.12, back + 0.12, 1.8);
      } else {
        const wall = mat(0x7a4636, { roughness: 0.95 });
        p.box(wall, LOT - 0.4, 1.8, 0.25, 0, KERB, back + 0.12);
      }
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
      if (hasReal("street")) {
        fenceRun(p, "wall_brick", half - 0.12, back + 0.12, -half + 0.12, back + 0.12, 1.45);
        fenceRun(p, "wall_brick", -half + 0.12, back + 0.12, -half + 0.12, yardZ, 1.45);
        fenceRun(p, "wall_brick", half - 0.12, yardZ, half - 0.12, back + 0.12, 1.45);
      } else {
        const wall = mat(0x7a4636, { roughness: 0.95 });
        p.box(wall, LOT - 0.4, 1.5, 0.25, 0, KERB, back + 0.12);
        for (const sx of [-1, 1]) p.box(wall, 0.25, 1.5, yardZ - back, sx * (half - 0.12), KERB, (yardZ + back) / 2);
      }
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

const TREES = ["tree_a", "tree_a", "tree_b", "tree_b", "tree_c", "tree_d", "tree_d", "tree_e", "tree_f"];
/** Realistic species, by how common they are in town. */
const SPECIES = ["maple", "linden", "oak", "maple", "linden", "birch", "cherry", "young", "spruce", "oak", "birch", "maple", "pine", "poplar", "linden", "cherry"];
const SHRUBS = ["bush", "bush", "bush_wide", "shrub", "flowers"];

/** Paint for a realistic prop: `wall` picks its tint (foliage, car paint). */
const tintOf = (i: number): Paint => ({ wall: i, accent: 0, roof: 0, signs: 0 });

/** A lawn: mown grass from the realistic library when loaded, else flat green. */
export function lawn(): THREE.Material {
  return hasReal("trees") ? groundMat("grass", 2.2, { roughness: 0.95, normal: 0.8 }) : mat(0x6f9a4f, { roughness: 1 });
}

/**
 * A clipped hedge where a box would be (w along x, d along z, from y up to
 * y + h): realistic segments stretched to fit when loaded, else the box.
 */
export function hedge(p: Parts, w: number, h: number, d: number, x: number, y: number, z: number, seed: number) {
  if (!hasReal("trees")) {
    p.box(mat(0x3f6a34, { flatShading: true }), w, h, d, x, y, z);
    return;
  }
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

/** A piece of the realistic street furniture; `phase` ("a" / "b") picks a crossing's signal cycle. */
export function furniture(p: Parts, name: string, x: number, y: number, z: number, ry = 0, scale?: THREE.Vector3, phase = "") {
  for (const { role, geo } of realPiece("street", name)) p.add(realMat("street", role, tintOf(0), 0, phase), geo, x, y, z, 0, ry, 0, scale);
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

/** A garden shrub (nothing without the realistic trees: the kit has none). */
export function shrub(p: Parts, x: number, z: number, seed: number, y = KERB, s = 1) {
  if (!hasReal("trees")) return;
  const r = rng(Math.floor(seed));
  const name = SHRUBS[Math.floor(r() * SHRUBS.length)];
  const k = s * (0.8 + r() * 0.4);
  const scale = new THREE.Vector3(k, k * (0.85 + r() * 0.3), k);
  const ry = r() * Math.PI * 2;
  const tint = tintOf(Math.floor(r() * 6));
  for (const { role, geo } of realPiece("trees", name)) p.add(realMat("trees", role, tint, 0), geo, x, y, z, 0, ry, 0, scale);
}

/** A tree; `s` was the kit's scale (0.35-1.2), which picks the realistic tree's size too; `species` the realistic ones to pick from. */
export function tree(p: Parts, x: number, z: number, s: number, seed: number, y = 0, species = SPECIES) {
  const r = rng(seed);
  if (hasReal("trees")) {
    const name = species[Math.floor(r() * species.length)];
    const k = 0.5 + 0.55 * s;
    const scale = new THREE.Vector3(k, k * (0.88 + r() * 0.24), k);
    const ry = r() * Math.PI * 2;
    const tint = tintOf(Math.floor(r() * 6));
    for (const { role, geo } of realPiece("trees", name)) p.add(realMat("trees", role, tint, 0), geo, x, y, z, 0, ry, 0, scale);
    return;
  }
  const name = TREES[Math.floor(r() * TREES.length)];
  const leaf = kitMat({ color: LEAVES[Math.floor(r() * LEAVES.length)], rough: 0.9 }, 0);
  const roles: Record<string, THREE.MeshStandardMaterial> = {
    leaf,
    blossom: kitMat({ color: BLOSSOMS[Math.floor(r() * BLOSSOMS.length)], rough: 0.9 }, 0),
    birch: kitMat(ROLES.birch, 0),
    bark: kitMat(ROLES.bark, 0),
  };
  const scale = new THREE.Vector3(s, s * (0.85 + r() * 0.3), s);
  const ry = r() * Math.PI * 2;
  for (const { role, geo } of piece(name).parts) p.add(roles[role] ?? roles.bark, geo, x, y, z, 0, ry, 0, scale);
}

/** Realistic cars that park on drives and in bays, by how common they are. */
const PARKED = ["hatch", "sedan", "estate", "suv", "hatch", "sedan", "suv", "coupe", "pickup", "van", "estate", "hatch"];

/** A parked car, nose toward +z before ry: a realistic one if they are loaded, else from the traffic kit. */
export function parked(p: Parts, x: number, z: number, ry: number, seed: number, y = KERB) {
  const r = rng(seed);
  if (hasReal("cars")) {
    const name = PARKED[Math.floor(r() * PARKED.length)];
    const paint: Paint = { wall: Math.floor(r() * CAR_PAINTS.length), accent: 0, roof: 0, signs: 0 };
    for (const { role, geo } of realPiece("cars", name)) p.add(realMat("cars", role, paint, 0), geo, x, y, z, 0, ry, 0);
    return;
  }
  const model = ["car_sedan", "car_hatch", "car_sedan", "car_van"][Math.floor(r() * 4)];
  const body = kitMat({ color: CAR_PAINT[Math.floor(r() * CAR_PAINT.length)], rough: 0.5, metal: 0.15 }, 0);
  for (const { role, geo } of piece(model).parts) p.add(role === "body" ? body : kitMat(ROLES[role] ?? ROLES.dark, 0), geo, x, y, z, 0, ry, 0);
}

/** Parking bays: a strip of asphalt with lines and some cars, centred on (x, z), bays along x. */
function parking(p: Parts, x: number, z: number, w: number, d: number, fill: number, seed: number) {
  const r = rng(seed);
  p.box(mat(0x45474b, { roughness: 0.95 }), w, 0.04, d, x, KERB, z);
  const bays = Math.floor(w / 2.8);
  const line = mat(0xe8e6de, { roughness: 0.7 });
  for (let i = 0; i <= bays; i++) p.box(line, 0.12, 0.05, Math.min(5, d - 0.4), x - (bays * 2.8) / 2 + i * 2.8, KERB, z - d / 2 + Math.min(5, d - 0.4) / 2 + 0.2);
  for (let i = 0; i < bays; i++) {
    if (r() > fill) continue;
    parked(p, x - (bays * 2.8) / 2 + (i + 0.5) * 2.8, z - d / 2 + 2.6, 0, seed * 31 + i);
  }
}

const planter = (p: Parts, x: number, z: number, seed: number, s = 0.55) => {
  p.box(mat(0x9a948a, { roughness: 0.9 }), 1.6, 0.6, 1.6, x, KERB, z);
  tree(p, x, z, s, seed, KERB + 0.5);
};

/**
 * The lot around a building: lawn or paving, a way in from the street, and
 * what the type needs out back (a garden, parking, a loading yard). The
 * building's centre is the origin and its front faces +z.
 */
function yard(p: Parts, s: Spec, r: () => number) {
  const cz = -s.yard;
  const front = LOT / 2 - s.yard;
  const back = -LOT / 2 - s.yard;
  const grass = lawn();
  const paving = mat(0xbab4a8, { roughness: 0.9 });
  const concrete = mat(0xa29e96, { roughness: 0.95 });
  const half = LOT / 2 - 0.2;
  const ground = (m: THREE.Material) => p.box(m, LOT - 0.4, KERB, LOT - 0.4, 0, 0, cz);
  const path = (x: number, w = 1.4) => p.box(paving, w, KERB + 0.03, front - s.d / 2, x, 0, (front + s.d / 2) / 2);
  switch (s.kind) {
    case "cottage": {
      ground(grass);
      const side = r() < 0.5 ? -1 : 1;
      // A drive up to the garage (modern) or along the side of the house, a
      // car on it, and a path to the door.
      const modern = s.style === "modern";
      const dx = modern ? s.w * 0.3 : side * (s.w / 2 + 2.2);
      const dw = modern ? 2.6 : 2.4;
      const dEnd = modern ? s.d / 2 : -s.d / 4;
      p.box(concrete, dw, KERB + 0.03, front - dEnd, dx, 0, (front + dEnd) / 2);
      parked(p, dx, modern ? s.d / 2 + 2.6 : 0.4, 0, s.seed + 3);
      const px = modern ? s.w * 0.05 : 0;
      path(px, 1.2);
      // Hedge along the front, broken for the path and the drive.
      const gaps = [[dx - dw / 2 - 0.1, dx + dw / 2 + 0.1], [px - 0.7, px + 0.7]].sort((a, b) => a[0] - b[0]);
      let x0 = -half;
      for (const [g0, g1] of [...gaps, [half, half]]) {
        if (g0 > x0 + 0.4) hedge(p, g0 - x0, KERB + 0.75, 0.6, (x0 + g0) / 2, 0, front - 0.5, s.seed);
        x0 = Math.max(x0, g1);
      }
      // Garden: trees, maybe a shed, and a fence round the back.
      tree(p, -side * (s.w / 2 + 2.0), s.d / 2 + 1.8, 0.7, s.seed + 1, KERB);
      tree(p, (r() - 0.5) * s.w, back + 2.2, 0.85, s.seed + 2, KERB);
      if (r() < 0.6) p.box(mat(0x7a5a3e), 1.6, 2.0, 1.4, -side * (half - 1.2), KERB, back + 1.2);
      const run = LOT / 2 + s.yard;
      if (hasReal("street")) {
        // Close-board or post-and-rail round the back garden.
        const kind = r() < 0.6 ? "fence_panel" : "fence_rail";
        const h = kind === "fence_panel" ? 0.85 : 1;
        fenceRun(p, kind, half, back + 0.25, -half, back + 0.25, h);
        fenceRun(p, kind, -half, back + 0.25, -half, back + 0.25 + run, h);
        fenceRun(p, kind, half, back + 0.25 + run, half, back + 0.25, h);
      } else {
        const fence = mat(0xe8e0d0, { roughness: 0.8 });
        p.box(fence, LOT - 0.4, 1.1, 0.08, 0, KERB, back + 0.25);
        for (const sx of [-1, 1]) p.box(fence, 0.08, 1.1, run, sx * half, KERB, back + run / 2 + 0.25);
      }
      break;
    }
    case "shop": {
      ground(s.style === "factory" ? concrete : paving);
      if (s.style === "factory") {
        // Loading yard out back: pallets, a skip and a van at the dock.
        parked(p, -s.w * 0.25, s.d / 2 + 2.8, 0, s.seed + 7);
        const wood = mat(0x8a6a40, { roughness: 0.9 });
        for (let i = 0; i < 6; i++) p.box(wood, 1.2, 0.9 + r() * 0.9, 1.0, -half + 1 + (i % 3) * 1.4, KERB, back + 1 + Math.floor(i / 3) * 1.3);
        p.box(mat(0x3a6a3a, { roughness: 0.7, metalness: 0.3 }), 3.2, 1.4, 1.8, half - 2, KERB, back + 1.3);
        p.box(mat(0x2a2c2e, { metalness: 0.5 }), LOT - 0.4, 2.0, 0.06, 0, KERB, back + 0.1);
      } else {
        // Shoppers' parking behind, benches and planters at the front.
        parking(p, 0, back + 3.2, LOT - 1, 5.8, 0.7, s.seed + 5);
        planter(p, -s.w / 2 + 0.4, front - 0.9, s.seed + 11, 0.45);
        planter(p, s.w / 2 - 0.4, front - 0.9, s.seed + 12, 0.45);
      }
      break;
    }
    case "apartment": {
      ground(grass);
      path(0, s.style === "townhouse" ? s.w : 2);
      if (s.style !== "townhouse") {
        tree(p, -s.w / 2 + 0.8, front - 1.2, 0.6, s.seed + 1, KERB);
        tree(p, s.w / 2 - 0.8, front - 1.2, 0.6, s.seed + 2, KERB);
      } else {
        if (hasReal("street")) fenceRun(p, "fence_iron", -half, front - 0.3, half, front - 0.3, 0.75);
        else p.box(mat(0x2a2c2e, { metalness: 0.5 }), LOT - 0.4, 0.9, 0.06, 0, KERB, front - 0.3);
      }
      parking(p, 0, back + 3.2, LOT - 1, 5.8, 0.8, s.seed + 5);
      break;
    }
    case "office": {
      ground(paving);
      // A plaza out front with trees in planters, a smoking-area bench at the back.
      for (const sx of [-1, 1]) {
        planter(p, sx * (s.w / 2 + 1.6), front - 1.3, s.seed + (sx > 0 ? 1 : 2));
        planter(p, sx * (s.w / 2 + 1.6), cz, s.seed + (sx > 0 ? 3 : 4));
      }
      p.box(mat(0x8f8a80, { roughness: 0.9 }), s.w * 0.7, 0.05, front - s.d / 2 - 0.6, 0, KERB, (front + s.d / 2) / 2);
      parking(p, 0, back + 3.0, LOT - 1, 5.6, 0.85, s.seed + 5);
      break;
    }
    case "landmark": {
      ground(mat(0xc8c0b0, { roughness: 0.85 }));
      for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) planter(p, sx * (half - 1.1), sz * (half - 1.1) + cz, s.seed + sx * 3 + sz, 0.5);
      p.box(mat(0xd9a441, { roughness: 0.3, metalness: 0.85 }), LOT - 3, 0.05, 0.25, 0, KERB, front - 0.6);
      break;
    }
  }
}

export function building(s: Spec): { group: THREE.Group; info: ModelInfo } {
  const g = new THREE.Group();
  const p = new Parts();
  const r = rng(s.seed * 31 + 5);
  const info: ModelInfo = { height: s.height, emitters: [], beacons: [], night: [], debris: realDef(s)?.debris ?? WALLS[s.wall] };
  const look = looks(s, info);
  const broken = s.damage >= 2;

  const def = realDef(s);
  const yp = new Parts(YARD);
  if (def) realYard(yp, p, s, def, r);
  else yard(yp, s, r);
  yp.into(g);

  // Heavy damage takes the top quarter off, roof and all.
  const floors = broken ? Math.max(1, Math.round(s.floors * (0.72 + r() * 0.1))) : s.floors;
  const top = def ? stackReal(p, s, def, floors, !broken, info) : stack(p, s, look, floors, !broken);
  if (top.anchors.smoke) info.emitters.push({ pos: top.anchors.smoke, kind: "smoke", rate: s.damage ? 0 : s.style === "factory" ? 1.4 : 0.25 });
  if (top.anchors.beacon) info.beacons.push(top.anchors.beacon);
  if (broken) wreckTop(p, top.w, top.d, top.top, def?.debris ?? (s.kind === "office" ? GLASS[s.wall] : WALLS[s.wall]), r, def ? THREE.MathUtils.clamp(top.top / 20, 0.4, 1) : 1);

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

export function rubble(s: Spec): { group: THREE.Group; info: ModelInfo } {
  const g = new THREE.Group();
  const p = new Parts();
  const r = rng(s.seed * 7 + 1);
  const pile = 1.4 + s.grade * 0.9;
  p.box(mat(0x4a4642), LOT - 0.4, KERB + 0.04, LOT - 0.4, 0, 0, -s.yard);
  p.add(mat(0x5d5852, { flatShading: true, roughness: 1 }), new THREE.ConeGeometry(s.w * 0.62, pile, 9, 1), 0, pile / 2, 0, 0, r(), 0);
  const conc = mat(0x7a7570, { roughness: 1, flatShading: true });
  const wall = mat(new THREE.Color(WALLS[s.wall]).multiplyScalar(0.55).getHex(), { flatShading: true });
  const burnt = mat(0x221e1c, { roughness: 1 });
  for (let i = 0; i < 26 + s.grade * 8; i++) {
    const a = r() * Math.PI * 2;
    const dist = r() * s.w * 0.6;
    const sz = 0.4 + r() * (1 + s.grade * 0.4);
    const y = Math.max(0, pile * (1 - dist / (s.w * 0.62)) - sz * 0.6);
    const m = [conc, conc, wall, burnt][Math.floor(r() * 4)];
    p.box(m, sz, sz * (0.3 + r() * 0.6), sz * (0.5 + r() * 0.8), Math.cos(a) * dist, y, Math.sin(a) * dist, r() * 3, r(), r());
  }
  const steel = mat(0x2a2422, { metalness: 0.5, roughness: 0.6 });
  for (let i = 0; i < 4 + s.grade * 2; i++) {
    p.box(steel, 0.15, 2 + r() * 4, 0.15, (r() - 0.5) * s.w, 0, (r() - 0.5) * s.d, r() * 3, (r() - 0.5) * 1.8, (r() - 0.5) * 1.8);
  }
  p.into(g);
  g.position.set(s.x, 0, s.z);
  g.rotation.y = s.rot;
  const info: ModelInfo = { height: pile, emitters: [{ pos: new THREE.Vector3(0, pile * 0.6, 0), kind: "smoke", rate: 0.8 }], beacons: [], night: [], debris: WALLS[s.wall] };
  return { group: g, info };
}

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
  if (clad > 0) {
    if (def) stackReal(p, s, def, clad, false, info);
    else stack(p, s, looks(s, info), clad, false);
  }

  // Scaffolding one floor above the work.
  const scaff = mat(s.surrendering ? 0xc0392b : 0xd08a2a, { metalness: 0.4, roughness: 0.5 });
  const sh = builtH + s.floorH;
  const gap = 0.8;
  const W = s.w + gap * 2;
  const D = s.d + gap * 2;
  for (const [len, axis] of [[W, "x"], [D, "z"]] as const) {
    const n = Math.max(2, Math.round(len / 2.4));
    for (let i = 0; i <= n; i++) {
      const t = -len / 2 + (len * i) / n;
      for (const side of [-1, 1]) {
        const [x, z] = axis === "x" ? [t, (side * D) / 2] : [(side * W) / 2, t];
        p.box(scaff, 0.09, sh, 0.09, x, 0, z);
      }
    }
  }
  for (let y = s.floorH; y <= sh + 0.01; y += s.floorH) {
    for (const side of [-1, 1]) {
      p.box(scaff, W, 0.08, 0.08, 0, y, (side * D) / 2);
      p.box(scaff, 0.08, 0.08, D, (side * W) / 2, y, 0);
      p.box(mat(0x8a6a40), W, 0.06, 0.6, 0, y - 0.05, side * (D / 2 - 0.3));
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

  // Tower crane from the kit: base and mast sections, then a jib that turns
  // with its cab, counter-jib, pendant ties, trolley, hook and a load of steel.
  const crane = (p: Parts, name: string, x: number, y: number, z: number) => {
    for (const { role, geo } of piece(name).parts) p.add(kitMat(ROLES[role] ?? ROLES.metal, 0), geo, x, y, z);
    return piece(name).anchors;
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

const PARK_ROLES: Record<string, RoleLook> = { ...ROLES, roof: { color: 0x56606e, rough: 0.8 }, accent: { color: 0x3a6fb5, rough: 0.7 } };

function prop(p: Parts, name: string, x: number, z: number, ry = 0, s = 1, y = KERB) {
  const scale = new THREE.Vector3(s, s, s);
  if (name === "bench" && hasReal("street")) return furniture(p, "bench", x, y, z, ry);
  for (const { role, geo } of piece(name).parts) p.add(kitMat(PARK_ROLES[role] ?? ROLES.metal, 0), geo, x, y, z, 0, ry, 0, scale);
}

/** A park lamp: a post with a lantern, lit by `bulb` at night. */
export function lampPost(p: Parts, pole: THREE.Material, bulb: THREE.Material, x: number, z: number, h = 3.6) {
  if (hasReal("street")) return furniture(p, "lamp_heritage", x, KERB, z);
  p.cyl(pole, 0.07, 0.1, h, x, KERB, z, 6);
  p.box(bulb, 0.36, 0.5, 0.36, x, KERB + h, z);
  p.box(pole, 0.5, 0.08, 0.5, x, KERB + h + 0.5, z);
}

/**
 * A park block in place of a district, in world coordinates: a plaza with a
 * fountain, a park with a pond and a bandstand, or a football ground.
 */
export function park(p: Parts, k: ParkSpec, pole: THREE.Material, bulb: THREE.Material) {
  const r = rng(k.seed);
  const { x: X, z: Z } = k;
  const W = BLOCK_X;
  const D = BLOCK_Z;
  const lawn_ = hasReal("trees") ? lawn() : mat(0x6a9a48, { roughness: 1 });
  const paving = hasReal("street") ? groundMat("pave", 3.6, { roughness: 0.88, color: 0xf2eee6 }) : mat(0xc4bcae, { roughness: 0.9 });
  const flat = (m: THREE.Material, g: THREE.BufferGeometry, x: number, z: number, y = KERB + 0.02) => p.add(m, g, X + x, y, Z + z, -Math.PI / 2);
  const bench = (x: number, z: number, ry: number) => prop(p, "bench", X + x, Z + z, ry);
  switch (k.kind) {
    case "plaza": {
      p.box(paving, W, KERB, D, X, 0, Z);
      flat(mat(0x9a8e7e, { roughness: 0.9 }), new THREE.CircleGeometry(10, 32), 0, 0);
      flat(mat(0xd8d0c0, { roughness: 0.9 }), new THREE.RingGeometry(10, 10.8, 32), 0, 0, KERB + 0.03);
      prop(p, "fountain", X, Z, 0, 1.45);
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
      for (const [x, z] of [[-14, -6], [14, -6], [-14, 6], [14, 6]]) lampPost(p, pole, bulb, X + x, Z + z);
      break;
    }
    case "park": {
      p.box(lawn_, W, KERB, D, X, 0, Z);
      // A loop path round the lawn, with a cut through the middle.
      const path = mat(0xc9b896, { roughness: 1 });
      const ax = W / 2 - 6;
      const az = D / 2 - 4.5;
      const n = 36;
      const ring: [number, number][] = Array.from({ length: n }, (_, i) => [Math.cos((i / n) * Math.PI * 2) * ax, Math.sin((i / n) * Math.PI * 2) * az]);
      ring.forEach(([x0, z0], i) => {
        const [x1, z1] = ring[(i + 1) % n];
        p.box(path, Math.hypot(x1 - x0, z1 - z0) + 0.6, KERB + 0.03, 2.2, X + (x0 + x1) / 2, 0, Z + (z0 + z1) / 2, -Math.atan2(z1 - z0, x1 - x0));
        if (i % 6 === 3) lampPost(p, pole, bulb, X + x0 * 1.09, Z + z0 * 1.14);
        if (i % 6 === 0) bench(x0 * 0.9, z0 * 0.86, Math.atan2(x0, z0));
      });
      p.box(path, 2.2, KERB + 0.03, D, X + 4, 0, Z);
      // A pond with a sandy edge, and the bandstand across the lawn.
      const pond = { x: -12, z: 1, rx: 10, rz: 5.5 };
      const sand = new THREE.CircleGeometry(1, 28).scale(pond.rx + 0.9, pond.rz + 0.9, 1);
      flat(mat(0xb8a87c, { roughness: 1 }), sand, pond.x, pond.z, KERB + 0.025);
      flat(mat(0x4a86a0, { roughness: 0.08, metalness: 0.3 }), new THREE.CircleGeometry(1, 28).scale(pond.rx, pond.rz, 1), pond.x, pond.z, KERB + 0.04);
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
      p.box(mat(0xa85a40, { roughness: 1 }), pw + 6, KERB + 0.02, pd + 5, X, 0, Z + pz);
      for (let i = 0; i < 10; i++) {
        p.box(mat(i % 2 ? 0x5e9a3e : 0x6aa646, { roughness: 1 }), pw / 10, KERB + 0.04, pd, X - pw / 2 + (i + 0.5) * (pw / 10), 0, Z + pz);
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
      p.add(white, new THREE.RingGeometry(4.2, 4.35, 32), X, ly + 0.02, Z + pz, -Math.PI / 2);
      for (const x of [-9, 9]) prop(p, "bleachers", X + x, Z + 10.2, Math.PI);
      // Floodlights at the corners.
      for (const sx of [-1, 1]) {
        for (const sz of [-1, 1]) {
          const x = X + sx * (pw / 2 + 4);
          const z = Z + pz + sz * (pd / 2 + 2.2);
          p.cyl(pole, 0.15, 0.25, 13, x, KERB, z, 6);
          p.box(pole, 2.2, 0.2, 0.3, x, KERB + 13, z);
          p.box(bulb, 2.0, 0.8, 0.25, x - sx * 0.1, KERB + 13.2, z - sz * 0.2, 0, -sz * 0.5);
        }
      }
      for (let i = 0; i < 8; i++) tree(p, X + (r() < 0.5 ? -1 : 1) * (28 + r() * 3), Z + (r() - 0.5) * (D - 4), 0.7 + r() * 0.3, k.seed + i, KERB);
      break;
    }
  }
}
