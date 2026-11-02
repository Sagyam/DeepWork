// City theme, step 2: 3D models for the plan's specs. Buildings and trees
// are stacked from the Blender kit (kit.ts) with materials picked per
// building and damage; lots, wreckage, rubble and the construction site are
// built here from boxes. Geometry is merged per material to keep draw calls low.
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { NOMINAL, piece } from "./kit";
import { LOT, rng, type SiteSpec, type Spec } from "./plan";
import { ATLAS, panes, type Pane } from "./textures";

export const WALLS = [0xe8d9c0, 0xd9c2a5, 0xc9d3d8, 0xe6c9b5, 0xb9c4b0, 0xd8d0e0, 0xcfb59b, 0xe9e4da];
export const GLASS = [0x7f9bb3, 0x6d8a99, 0x8fa3b8, 0x5d7488, 0x9ab0a8, 0x7a8aa8, 0x8a98b0, 0x6f8c9c];
export const ACCENTS = [0xb5483a, 0x3a6fb5, 0x3a9a6a, 0xc9902a, 0x7a4ab5, 0x2f3a4a];
/** Cottage roofs, by accent: terracotta, slate, moss, clay, plum, charcoal. */
const ROOFS = [0xa8503c, 0x56606e, 0x5e6e4a, 0xb8764a, 0x6e4a5a, 0x3e4044];
const LEAVES = [0x4f7a3a, 0x5d8a42, 0x3f6a34, 0x6a8f3e, 0x48703f];

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
}

const shared = new Map<string, THREE.MeshStandardMaterial>();

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

  add(material: THREE.Material, g: THREE.BufferGeometry, x: number, y: number, z: number, rx = 0, ry = 0, rz = 0, scale?: THREE.Vector3, cells?: [number, number]) {
    this.q.setFromEuler(this.e.set(rx, ry, rz));
    this.m.compose(new THREE.Vector3(x, y, z), this.q, scale ?? new THREE.Vector3(1, 1, 1));
    const geo = g.index ? g.toNonIndexed() : g.clone();
    geo.applyMatrix4(this.m);
    for (const k of Object.keys(geo.attributes)) if (!["position", "normal", "uv", "color"].includes(k)) geo.deleteAttribute(k);
    if (cells) {
      const uv = geo.getAttribute("uv") as THREE.BufferAttribute;
      for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) + cells[0] / ATLAS, uv.getY(i) + cells[1] / ATLAS);
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
  lobby: { color: 0x2a323c, rough: 0.2, metal: 0.4, emissive: 0xfff0d8, night: 1 },
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

/** Puts a kit piece on the stack at height y, scaled to the footprint. */
function put(p: Parts, name: string, y: number, sx: number, sz: number, look: Look, r: () => number) {
  const cells: [number, number] = [Math.floor(r() * ATLAS), Math.floor(r() * ATLAS)];
  const scale = new THREE.Vector3(sx, 1, sz);
  for (const { role, geo } of piece(name).parts) {
    p.add(look(role), geo, 0, y, 0, 0, 0, 0, scale, role === "window" || role === "glass" ? cells : undefined);
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
  const variant = (n: number) => "abc"[Math.floor(r() * n)];
  const [W0, D0] = NOMINAL[s.kind];
  const sx = s.w / W0;
  const sz = s.d / D0;
  const fh = s.floorH;
  const anchors: Record<string, THREE.Vector3> = {};
  let k = 1;
  const place = (name: string, y: number) => {
    for (const [key, a] of Object.entries(put(p, name, y, sx * k, sz * k, look, r))) {
      anchors[key] = new THREE.Vector3(a.x * sx * k, a.y + y, a.z * sz * k);
    }
  };
  switch (s.kind) {
    case "cottage": {
      const v = variant(3);
      if (floors > 0) place(`cottage_body_${v}`, 0);
      if (roof) place(`cottage_roof_${v}`, fh);
      break;
    }
    case "shop":
    case "apartment": {
      const pre = s.kind === "shop" ? "shop" : "apt";
      const fv = variant(2);
      const rv = variant(2);
      for (let f = 0; f < floors; f++) place(f === 0 ? `${pre}_ground${s.kind === "shop" ? `_${fv}` : ""}` : `${pre}_floor_${fv}`, f * fh);
      if (roof) place(`${pre}_roof_${rv}`, floors * fh);
      break;
    }
    case "office": {
      const fv = variant(2);
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
      const e1 = Math.round(s.floors * 0.5);
      const e2 = Math.round(s.floors * 0.8);
      let tier = 1;
      for (let f = 0; f < floors; f++) {
        const t = f < e1 ? 1 : f < e2 ? 2 : 3;
        if (t !== tier) place(`lm_ledge_${tier}`, f * fh);
        tier = t;
        place(f === 0 ? "lm_ground" : `lm_floor_${t}`, f * fh);
      }
      if (roof) place("lm_crown", floors * fh);
      // Landmark tiers are modelled at their own sizes; k is only the top's.
      k = [1, 0.78, 0.56][tier - 1];
      break;
    }
  }
  return { top: floors * fh, w: s.w * k, d: s.d * k, anchors };
}

/** Broken-off top: jagged chunks and bent rebar on a cut body. */
function wreckTop(p: Parts, w: number, d: number, y: number, color: number, r: () => number) {
  const conc = mat(0x5a5652, { roughness: 1 });
  const wall = mat(new THREE.Color(color).multiplyScalar(0.45).getHex());
  for (let i = 0; i < 9; i++) {
    const cw = w * (0.15 + r() * 0.3);
    const ch = 0.6 + r() * 2.4;
    p.box(r() < 0.5 ? conc : wall, cw, ch, d * (0.15 + r() * 0.35), (r() - 0.5) * (w - cw), y - 0.3, (r() - 0.5) * d * 0.7, r(), (r() - 0.5) * 0.5, (r() - 0.5) * 0.5);
  }
  const steel = mat(0x2a2422, { roughness: 0.6, metalness: 0.5 });
  for (let i = 0; i < 6; i++) {
    p.box(steel, 0.12, 1.5 + r() * 2.5, 0.12, (r() - 0.5) * w * 0.9, y, (r() - 0.5) * d * 0.9, 0, (r() - 0.5) * 0.9, (r() - 0.5) * 0.9);
  }
}

const TREES = ["tree_a", "tree_a", "tree_b", "tree_c", "tree_d", "tree_d", "tree_b"];

export function tree(p: Parts, x: number, z: number, s: number, seed: number) {
  const r = rng(seed);
  const name = TREES[Math.floor(r() * TREES.length)];
  const leaf = kitMat({ color: LEAVES[Math.floor(r() * LEAVES.length)], rough: 0.9 }, 0);
  const bark = kitMat(ROLES.bark, 0);
  const scale = new THREE.Vector3(s, s * (0.85 + r() * 0.3), s);
  const ry = r() * Math.PI * 2;
  for (const { role, geo } of piece(name).parts) p.add(role === "leaf" ? leaf : bark, geo, x, 0, z, 0, ry, 0, scale);
}

export function building(s: Spec): { group: THREE.Group; info: ModelInfo } {
  const g = new THREE.Group();
  const p = new Parts();
  const r = rng(s.seed * 31 + 5);
  const info: ModelInfo = { height: s.height, emitters: [], beacons: [], night: [], debris: WALLS[s.wall] };
  const look = looks(s, info);
  const broken = s.damage >= 2;

  // Lot: lawn and a path to the front door.
  p.box(mat(0x6f9a4f), LOT - 1.2, 0.08, LOT - 1.2, 0, 0, 0);
  p.box(mat(0xbab4a8), 1.4, 0.1, LOT / 2 - s.d / 2, 0, 0, s.d / 2 + (LOT / 2 - s.d / 2) / 2);
  if (s.kind === "cottage") {
    p.box(mat(0x3f6a34, { flatShading: true }), LOT - 2, 0.7, 0.6, 0, 0, LOT / 2 - 1.2);
    tree(p, (r() < 0.5 ? -1 : 1) * (s.w / 2 + 1.6), s.d / 2 + 1.6, 0.7, s.seed + 1);
  }
  if (s.kind === "landmark") p.box(mat(0xc8c0b0), LOT - 1.4, 0.15, 1.2, 0, 0, s.d / 2 + 0.6);

  // Heavy damage takes the top quarter off, roof and all.
  const floors = broken ? Math.max(1, Math.round(s.floors * (0.72 + r() * 0.1))) : s.floors;
  const top = stack(p, s, look, floors, !broken);
  if (top.anchors.smoke) info.emitters.push({ pos: top.anchors.smoke, kind: "smoke", rate: s.damage ? 0 : 0.25 });
  if (top.anchors.beacon) info.beacons.push(top.anchors.beacon);
  if (broken) wreckTop(p, top.w, top.d, top.top, s.kind === "office" ? GLASS[s.wall] : WALLS[s.wall], r);

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
  p.box(mat(0x4a4642), LOT - 1.2, 0.08, LOT - 1.2, 0, 0, 0);
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
  p.box(mat(0x8a7a62, { roughness: 1 }), LOT - 1.2, 0.08, LOT - 1.2, 0, 0, 0);
  p.box(conc, s.w + 0.6, 0.4, s.d + 0.6, 0, 0, 0);
  for (let f = 1; f <= built; f++) p.box(conc, s.w, 0.3, s.d, 0, f * s.floorH - 0.3, 0);
  for (const [cx, cz] of [[-1, -1], [1, -1], [-1, 1], [1, 1], [0, -1], [0, 1], [-1, 0], [1, 0]]) {
    p.box(col, 0.45, builtH, 0.45, (cx * (s.w - 0.5)) / 2, 0, (cz * (s.d - 0.5)) / 2);
  }
  // Lower floors already finished: the real building, rising floor by floor.
  const clad = Math.max(0, built - 2);
  if (clad > 0) stack(p, s, looks(s, info), clad, false);

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

  // Tower crane.
  const yellow = mat(0xe8b020, { metalness: 0.3, roughness: 0.5 });
  const cp = new Parts();
  const mastH = Math.max(s.height + 8, 18);
  const mx = s.w / 2 + 2.6;
  const mz = -s.d / 2 - 1.5;
  for (const [cx, cz] of [[-0.6, -0.6], [0.6, -0.6], [-0.6, 0.6], [0.6, 0.6]]) cp.box(yellow, 0.16, mastH, 0.16, mx + cx, 0, mz + cz);
  for (let y = 0; y < mastH; y += 2.4) {
    cp.box(yellow, 1.3, 0.1, 0.1, mx, y, mz - 0.6, 0, 0, 0.9);
    cp.box(yellow, 1.3, 0.1, 0.1, mx, y, mz + 0.6, 0, 0, -0.9);
    cp.box(yellow, 0.1, 0.1, 1.3, mx - 0.6, y, mz, 0, 0.9);
    cp.box(yellow, 0.1, 0.1, 1.3, mx + 0.6, y, mz, 0, -0.9);
  }
  cp.box(mat(0x4d4f55), 1.6, 0.6, 1.6, mx, 0, mz);
  cp.into(g);
  const jib = new THREE.Group();
  jib.position.set(mx, mastH, mz);
  const jp = new Parts();
  const reach = Math.max(16, s.w * 2.2);
  jp.box(yellow, reach, 0.7, 0.8, -reach / 2 + 3, 0, 0);
  jp.box(yellow, 7, 0.6, 0.8, 5.5, 0, 0);
  jp.box(mat(0x55585e, { roughness: 0.9 }), 2.2, 1.6, 1.4, 8, -0.8, 0);
  jp.box(mat(0xf0f0f0), 1.4, 1.3, 1.3, 0.2, -1.4, 0.9);
  jp.box(yellow, 0.3, 4, 0.3, 0, 0.7, 0);
  // Hook and a load of steel hanging over the site.
  const hookX = -reach * 0.55;
  const drop = Math.max(4, mastH - builtH - 4);
  jp.box(mat(0x222222), 0.05, drop, 0.05, hookX, -drop, 0);
  jp.box(mat(0x6a6e75, { metalness: 0.6 }), 3.2, 0.4, 0.8, hookX, -drop - 0.5, 0);
  jp.into(jib);
  g.add(jib);
  info.beacons.push(new THREE.Vector3(mx, mastH + 4.8, mz), new THREE.Vector3(mx - reach + 3, mastH + 0.4, mz));
  if (s.surrendering) info.emitters.push({ pos: new THREE.Vector3(0, builtH, 0), kind: "smoke", rate: 4 });
  else info.emitters.push({ pos: new THREE.Vector3(s.w * 0.3, builtH + 0.4, 0), kind: "smoke", rate: 0.6 });

  g.position.set(s.x, 0, s.z);
  g.rotation.y = s.rot;
  return { group: g, info, jib, ghost };
}
