// City theme, step 2: procedural 3D models for the plan's specs. Every
// building is built from boxes, prisms and cylinders; small details are
// merged per material to keep draw calls low.
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { LOT, rng, type SiteSpec, type Spec } from "./plan";
import { CELLS, facades, type Facade } from "./textures";

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

  add(material: THREE.Material, g: THREE.BufferGeometry, x: number, y: number, z: number, rx = 0, ry = 0, rz = 0) {
    this.q.setFromEuler(this.e.set(rx, ry, rz));
    this.m.compose(new THREE.Vector3(x, y, z), this.q, new THREE.Vector3(1, 1, 1));
    const geo = g.index ? g.toNonIndexed() : g.clone();
    geo.applyMatrix4(this.m);
    for (const k of Object.keys(geo.attributes)) if (!["position", "normal", "uv"].includes(k)) geo.deleteAttribute(k);
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

/** A box body whose four sides carry a window facade. */
function body(
  g: THREE.Group,
  info: ModelInfo,
  kind: Facade,
  s: { w: number; d: number; h: number; y: number; floors: number; color: number; seed: number; damage: number },
  glass = false,
) {
  const r = rng(s.seed);
  const set = facades(kind)[Math.floor(r() * 3)];
  const broken = s.damage >= 2;
  const cols = Math.max(1, Math.round(s.w / (kind === "house" ? 2.6 : kind === "glass" ? 1.6 : 2.4)));
  const colsD = Math.max(1, Math.round(s.d / (kind === "house" ? 2.6 : kind === "glass" ? 1.6 : 2.4)));
  const ox = Math.floor(r() * CELLS) / CELLS;
  const oy = Math.floor(r() * CELLS) / CELLS;
  const side = (c: number) => {
    const map = (broken ? set.brokenMap : set.map).clone();
    const em = (broken ? set.brokenEmissive : set.emissive).clone();
    for (const t of [map, em]) {
      t.repeat.set(c / CELLS, s.floors / CELLS);
      t.offset.set(ox, oy);
    }
    const m = new THREE.MeshStandardMaterial({
      map,
      emissiveMap: em,
      emissive: 0xffffff,
      emissiveIntensity: 0,
      color: shade(s.color, s.damage),
      roughness: glass ? 0.18 : 0.85,
      metalness: glass ? 0.55 : 0,
      envMapIntensity: glass ? 1.4 : 0.5,
    });
    m.userData.night = s.damage === 1 ? 0.35 : 0.55;
    info.night.push(m);
    return m;
  };
  const roof = mat(0x6b6d70, { roughness: 0.9 });
  const sw = side(cols);
  const sd = side(colsD);
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(s.w, s.h, s.d), [sd, sd, roof, roof, sw, sw]);
  mesh.position.y = s.y + s.h / 2;
  mesh.castShadow = mesh.receiveShadow = true;
  g.add(mesh);
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

export function tree(p: Parts, x: number, z: number, s: number, seed: number) {
  const r = rng(seed);
  p.cyl(mat(0x5a4030), 0.12 * s, 0.18 * s, 1.4 * s, x, 0, z, 5);
  const leaf = mat([0x4f7a3a, 0x5d8a42, 0x3f6a34, 0x6a8f3e][Math.floor(r() * 4)], { flatShading: true });
  const blobs = 2 + Math.floor(r() * 2);
  for (let i = 0; i < blobs; i++) {
    p.add(leaf, new THREE.IcosahedronGeometry((0.9 + r() * 0.5) * s, 0), x + (r() - 0.5) * s, (1.8 + i * 0.7) * s, z + (r() - 0.5) * s, r(), r(), r());
  }
}

export function building(s: Spec): { group: THREE.Group; info: ModelInfo } {
  const g = new THREE.Group();
  const p = new Parts();
  const r = rng(s.seed * 31 + 5);
  const info: ModelInfo = { height: s.height, emitters: [], beacons: [], night: [], debris: WALLS[s.wall] };
  const wall = s.kind === "office" ? GLASS[s.wall] : WALLS[s.wall];
  const accent = ACCENTS[s.accent];
  const broken = s.damage >= 2;
  // Heavy damage takes the top quarter off.
  const cut = broken ? 0.72 + r() * 0.1 : 1;
  const trim = mat(0xd8d2c8, { roughness: 0.7 });
  const dark = mat(0x3a3430, { roughness: 0.9 });

  // Lot: lawn and a path to the front door.
  p.box(mat(0x6f9a4f), LOT - 1.2, 0.08, LOT - 1.2, 0, 0, 0);
  p.box(mat(0xbab4a8), 1.4, 0.1, LOT / 2 - s.d / 2, 0, 0, s.d / 2 + (LOT / 2 - s.d / 2) / 2);

  switch (s.kind) {
    case "cottage": {
      const h = s.height;
      body(g, info, "house", { w: s.w, d: s.d, h, y: 0, floors: 1, color: wall, seed: s.seed, damage: s.damage });
      const roofH = 2.6;
      if (!broken) {
        const tri = new THREE.Shape([new THREE.Vector2(-s.d / 2 - 0.4, 0), new THREE.Vector2(s.d / 2 + 0.4, 0), new THREE.Vector2(0, roofH)]);
        const prism = new THREE.ExtrudeGeometry(tri, { depth: s.w + 0.6, bevelEnabled: false });
        prism.translate(0, 0, -(s.w + 0.6) / 2);
        p.add(mat(shade(accent, s.damage).getHex(), { roughness: 0.75, flatShading: true }), prism, 0, h, 0, 0, Math.PI / 2, 0);
        p.box(mat(0x8a5a4a), 0.7, 1.8, 0.7, s.w * 0.25, h + 0.8, -s.d * 0.15);
        info.emitters.push({ pos: new THREE.Vector3(s.w * 0.25, h + 2.7, -s.d * 0.15), kind: "smoke", rate: s.damage ? 0 : 0.25 });
      } else {
        wreckTop(p, s.w, s.d, h, wall, r);
      }
      p.box(mat(0x5a3a28), 1.1, 2.1, 0.12, 0, 0, s.d / 2);
      p.box(trim, 1.5, 0.12, 0.6, 0, 2.15, s.d / 2 + 0.25);
      // Hedge and a garden tree.
      p.box(mat(0x3f6a34, { flatShading: true }), LOT - 2, 0.7, 0.6, 0, 0, LOT / 2 - 1.2);
      tree(p, (r() < 0.5 ? -1 : 1) * (s.w / 2 + 1.6), s.d / 2 + 1.6, 0.9, s.seed + 1);
      break;
    }
    case "shop": {
      const h = s.height * cut;
      body(g, info, "residential", { w: s.w, d: s.d, h: h - 3.4, y: 3.4, floors: s.floors - 1, color: wall, seed: s.seed, damage: s.damage });
      // Ground floor: shop window, glowing at night.
      p.box(mat(shade(wall, s.damage).getHex()), s.w, 3.4, s.d, 0, 0, 0);
      const front = new THREE.MeshStandardMaterial({ color: 0x223040, emissive: broken ? 0x000000 : 0xffd9a0, emissiveIntensity: 0, roughness: 0.2, metalness: 0.4 });
      front.userData.night = 0.9;
      info.night.push(front);
      p.box(front, s.w * 0.8, 2.4, 0.1, 0, 0.3, s.d / 2 + 0.01);
      // Awning and a lit sign.
      p.box(mat(shade(accent, s.damage).getHex(), { roughness: 0.6 }), s.w * 0.9, 0.15, 1.6, 0, 2.9, s.d / 2 + 0.75, 0, 0.25);
      if (!broken) {
        const sign = mat(accent, { emissive: accent, emissiveIntensity: 0, night: 1.6 });
        info.night.push(sign);
        p.box(sign, s.w * 0.5, 0.7, 0.2, 0, 3.5, s.d / 2 + 0.1);
        for (const [dx, dz] of [[0, s.d / 2], [0, -s.d / 2], [s.w / 2, 0], [-s.w / 2, 0]]) {
          p.box(trim, dx ? 0.3 : s.w + 0.3, 0.6, dz ? 0.3 : s.d, dx, h, dz);
        }
        p.box(mat(0x9aa0a6, { metalness: 0.4 }), 1.4, 0.9, 1.1, -s.w * 0.2, h, -s.d * 0.2);
      } else wreckTop(p, s.w, s.d, h, wall, r);
      break;
    }
    case "apartment": {
      const h = s.height * cut;
      const floors = Math.max(1, Math.round(s.floors * cut));
      body(g, info, "residential", { w: s.w, d: s.d, h, y: 0, floors, color: wall, seed: s.seed, damage: s.damage });
      // Balconies on the front.
      const slab = mat(0xcfc9be);
      const rail = mat(0x30343a, { metalness: 0.5, roughness: 0.5 });
      for (let f = 1; f < floors; f++) {
        for (const bx of [-s.w * 0.28, s.w * 0.28]) {
          const y = f * s.floorH;
          p.box(slab, 2.2, 0.18, 1.1, bx, y, s.d / 2 + 0.55);
          p.box(rail, 2.2, 0.9, 0.06, bx, y + 0.18, s.d / 2 + 1.07);
        }
      }
      p.box(trim, s.w + 0.4, 0.5, s.d + 0.4, 0, h - 0.25, 0);
      if (!broken) {
        // Water tank on legs.
        const tank = mat(0x7a5a44, { roughness: 0.9 });
        p.cyl(tank, 1.1, 1.1, 1.8, s.w * 0.2, h + 1.2, -s.d * 0.15, 10);
        p.add(tank, new THREE.ConeGeometry(1.2, 0.7, 10), s.w * 0.2, h + 3.35, -s.d * 0.15);
        for (const [lx, lz] of [[-0.7, -0.7], [0.7, -0.7], [-0.7, 0.7], [0.7, 0.7]]) {
          p.box(dark, 0.12, 1.2, 0.12, s.w * 0.2 + lx, h, -s.d * 0.15 + lz);
        }
        p.box(mat(0x8a8e94), 1.6, 2.2, 1.6, -s.w * 0.25, h, s.d * 0.15);
      } else wreckTop(p, s.w, s.d, h, wall, r);
      break;
    }
    case "office": {
      const h = s.height * cut;
      const lower = Math.min(h, s.height * 0.68);
      const fl = (y: number) => Math.max(1, Math.round(y / s.floorH));
      body(g, info, "glass", { w: s.w, d: s.d, h: lower, y: 0, floors: fl(lower), color: wall, seed: s.seed, damage: s.damage }, true);
      p.box(mat(0xb8bcc2, { metalness: 0.6, roughness: 0.35 }), s.w + 0.3, 0.5, s.d + 0.3, 0, lower - 0.25, 0);
      if (h > lower) {
        const w2 = s.w * 0.78;
        const d2 = s.d * 0.78;
        body(g, info, "glass", { w: w2, d: d2, h: h - lower, y: lower, floors: fl(h - lower), color: wall, seed: s.seed + 3, damage: s.damage }, true);
        if (!broken) {
          p.box(mat(0x8a8e94), w2 * 0.6, 2.4, d2 * 0.6, 0, h, 0);
          p.cyl(mat(0xc0c4ca, { metalness: 0.7, roughness: 0.3 }), 0.08, 0.15, 9, w2 * 0.2, h + 2.4, 0, 6);
          info.beacons.push(new THREE.Vector3(w2 * 0.2, h + 11.5, 0));
        } else wreckTop(p, w2, d2, h, wall, r);
      } else if (broken) wreckTop(p, s.w, s.d, h, wall, r);
      // Entrance canopy.
      p.box(mat(0x30343a, { metalness: 0.6 }), 4, 0.25, 2, 0, 3.2, s.d / 2 + 1);
      break;
    }
    case "landmark": {
      const h = s.height * cut;
      const gold = mat(0xd9a441, { metalness: 0.85, roughness: 0.3, emissive: 0xffb84a, emissiveIntensity: 0, night: 0.9 });
      info.night.push(gold);
      const tiers: [number, number, number][] = [
        [0, 0.5, 1],
        [0.5, 0.8, 0.78],
        [0.8, 1, 0.56],
      ];
      let top = 0;
      for (const [a, b, k] of tiers) {
        const y0 = s.height * a;
        const y1 = Math.min(h, s.height * b);
        if (y1 <= y0) break;
        const fl = Math.max(1, Math.round((y1 - y0) / s.floorH));
        body(g, info, "office", { w: s.w * k, d: s.d * k, h: y1 - y0, y: y0, floors: fl, color: wall, seed: s.seed + y0, damage: s.damage });
        p.box(gold, s.w * k + 0.5, 0.45, s.d * k + 0.5, 0, y1 - 0.2, 0);
        // Corner piers make the tiers read as stone.
        for (const [cx, cz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
          p.box(trim, 0.7, y1 - y0, 0.7, (cx * s.w * k) / 2, y0, (cz * s.d * k) / 2);
        }
        top = y1;
      }
      if (!broken) {
        const cw = s.w * 0.56;
        p.add(gold, new THREE.ConeGeometry(cw * 0.72, 9, 4), 0, top + 4.5, 0, 0, Math.PI / 4, 0);
        p.cyl(mat(0xd0d4da, { metalness: 0.8, roughness: 0.25 }), 0.1, 0.35, 14, 0, top + 8, 0, 8);
        info.beacons.push(new THREE.Vector3(0, top + 22.2, 0));
      } else wreckTop(p, s.w * 0.56, s.d * 0.56, top, wall, r);
      // Plaza with a fountain-ish disc.
      p.box(mat(0xc8c0b0), LOT - 1.4, 0.15, 1.2, 0, 0, s.d / 2 + 0.6);
      break;
    }
  }

  if (s.damage >= 1) {
    const top = s.height * cut;
    info.emitters.push({ pos: new THREE.Vector3((r() - 0.5) * s.w * 0.5, top + 0.5, (r() - 0.5) * s.d * 0.5), kind: "smoke", rate: broken ? 7 : 2.2 });
    if (broken) {
      info.emitters.push({ pos: new THREE.Vector3((r() - 0.5) * s.w * 0.4, top, (r() - 0.5) * s.d * 0.4), kind: "fire", rate: 14 });
      info.emitters.push({ pos: new THREE.Vector3(s.w * 0.51, top * (0.3 + r() * 0.4), 0), kind: "fire", rate: 5 });
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
  // Lower floors already clad.
  const clad = Math.max(0, built - 2);
  if (clad > 0) p.box(mat(0x9fa4aa, { roughness: 0.6 }), s.w - 0.1, clad * s.floorH, s.d - 0.1, 0, 0, 0);

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
