// City theme: the countryside meshes, from terrain.ts. Faceted terrain
// coloured by height and slope (meadow, forest floor, river sand, rock,
// snow), one water plane that fills the river and the lake, and forests and
// boulders instanced from the kit: lush broadleaf and rainforest giants in
// the lowlands, conifers higher up, bare rock above the tree line.
import * as THREE from "three";
import { piece } from "./kit";
import { PITCH_X, PITCH_Z, rng, type CityPlan } from "./plan";
import { LAKE, RADIUS, ROAD_Z, WATER, fbm, noise, smoothstep, terrain, type Land as Shape } from "./terrain";

const RINGS = 170;
const SEGMENTS = 288;
const SECTORS = 12;

const LUSH = [0x3f7a34, 0x4d8a3a, 0x356a2c, 0x5a9a40, 0x2f5e2a, 0x467f30, 0x63a044];
const PINES = [0x2f5a32, 0x3a6a3a, 0x284e2c, 0x335f3a];

const C = (hex: number) => new THREE.Color(hex);
const CITY = C(0x57813f);
const MEADOW = C(0x6c9a48);
const MEADOW_LUSH = C(0x4d7c34);
const MEADOW_DRY = C(0x9fa95c);
const FLOOR = C(0x3c632e);
const SAND = C(0xb8a87c);
const MUD = C(0x5e5440);
const ROCK = C(0x7a746a);
const ROCK_DARK = C(0x5c5852);
const SNOW = C(0xeef2f7);

/** Forest cover in [0, 1]: big woods with meadows and clearings between. */
const cover = (x: number, z: number) =>
  smoothstep(fbm(x / 340 + 40, z / 340 - 12, 3), 0.29, 0.41);

export class Land {
  group = new THREE.Group();
  shape: Shape = terrain({ minX: 0, maxX: 0, minZ: 0, maxZ: 0 });
  private ground = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, flatShading: true });
  private waterMat: THREE.MeshStandardMaterial;
  private forestMats = new Map<string, THREE.MeshStandardMaterial>();

  constructor() {
    this.waterMat = new THREE.MeshStandardMaterial({ color: 0x3d6e86, roughness: 0.06, metalness: 0.3, envMapIntensity: 1.2, normalMap: ripples(), normalScale: new THREE.Vector2(0.3, 0.3) });
  }

  /** Rebuild for a city of a new size. */
  build(p: CityPlan) {
    this.group.clear();
    const land = (this.shape = terrain(p.bounds));
    this.group.add(this.terrainMesh(land), this.waterMesh());
    this.forest(land, p);
  }

  update(dt: number) {
    const n = this.waterMat.normalMap!;
    n.offset.x += dt * 0.004;
    n.offset.y += dt * 0.0025;
  }

  setNight(night: number) {
    this.ground.color.setRGB(1 - 0.55 * night, 1 - 0.55 * night, 1 - 0.42 * night);
    this.waterMat.color.setHex(0x3d6e86).lerp(C(0x0a1626), night * 0.85);
    for (const m of this.forestMats.values()) m.color.setRGB(1 - 0.5 * night, 1 - 0.5 * night, 1 - 0.4 * night);
  }

  private terrainMesh(land: Shape): THREE.Mesh {
    // One colour per facet, like the models, so the ground reads as low-poly
    // land rather than a smooth green sheet.
    const pos: number[] = [];
    const col: number[] = [];
    const c = new THREE.Color();
    const ring = (i: number) => {
      const r = RADIUS * Math.pow(i / (RINGS - 1), 1.7);
      const dr = Math.max(1.5, RADIUS * 1.7 * Math.pow(Math.max(i, 1) / (RINGS - 1), 0.7) / RINGS);
      const step = (Math.PI * 2) / SEGMENTS;
      const off = (i % 2) * (step / 2);
      return Array.from({ length: SEGMENTS }, (_, j) => {
        const a = j * step + off;
        const x = Math.cos(a) * r;
        const z = Math.sin(a) * r;
        return { x, z, h: land.height(x, z), dr };
      });
    };
    let prev = ring(0);
    for (let i = 0; i < RINGS - 1; i++) {
      const next = ring(i + 1);
      for (let j = 0; j < SEGMENTS; j++) {
        const j1 = (j + 1) % SEGMENTS;
        const A = prev[j], B = prev[j1], C = next[j], D = next[j1];
        for (const [p, q, s] of [[A, B, C], [B, D, C]] as const) {
          const x = (p.x + q.x + s.x) / 3;
          const z = (p.z + q.z + s.z) / 3;
          const h = (p.h + q.h + s.h) / 3;
          this.paint(c, land, x, z, h, p.dr);
          pos.push(p.x, p.h, p.z, q.x, q.h, q.z, s.x, s.h, s.z);
          col.push(c.r, c.g, c.b, c.r, c.g, c.b, c.r, c.g, c.b);
        }
      }
      prev = next;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    g.computeVertexNormals();
    const mesh = new THREE.Mesh(g, this.ground);
    mesh.receiveShadow = true;
    return mesh;
  }

  /** Ground colour from height, slope, forest cover and the water's edge. */
  private paint(c: THREE.Color, land: Shape, x: number, z: number, h: number, e: number) {
    const slope = Math.hypot(land.height(x + e, z) - h, land.height(x, z + e) - h) / e;
    const wild = land.wild(x, z);
    const patch = fbm(x / 230 + 9, z / 230 - 4, 3);
    const fine = fbm(x / 17, z / 17, 2);
    const thicket = fbm(x / 95 + 30, z / 95 - 11, 2);
    // Meadows drift from lush hollows to dry sunburnt rises, so the fields
    // are never one flat green.
    c.copy(MEADOW_LUSH).lerp(MEADOW, smoothstep(patch, 0.3, 0.55)).lerp(MEADOW_DRY, smoothstep(patch, 0.58, 0.82) * 0.85);
    // Rank grass and scrub in the hollows.
    c.lerp(FLOOR, smoothstep(thicket, 0.55, 0.82) * 0.45);
    // Forest floor under the canopy.
    c.lerp(FLOOR, cover(x, z) * smoothstep(h, WATER + 2, WATER + 4) * (1 - smoothstep(h, 150, 260)));
    // The town's lawns, mown but still mottled.
    c.lerp(CITY.clone().multiplyScalar(0.9 + 0.2 * patch), 0.62 * (1 - smoothstep(wild, 0.05, 0.55)));
    c.multiplyScalar((0.82 + 0.36 * fine) * (0.94 + 0.12 * fbm(x / 55 + 2, z / 55 - 8, 2)) * (0.92 + 0.16 * patch) * (0.95 + 0.1 * noise(x / 3 + 17, z / 3 - 5)));
    // Sand and mud at the water's edge.
    c.lerp(SAND, 1 - smoothstep(h, WATER + 0.4, WATER + 1.6));
    c.lerp(MUD, 1 - smoothstep(h, WATER - 0.6, WATER + 0.2));
    // Rock on steep faces and high ground; snow on the peaks.
    const rock = Math.max(smoothstep(slope, 0.55, 1.0), smoothstep(h, 170 + patch * 80, 240 + patch * 80));
    c.lerp(ROCK.clone().lerp(ROCK_DARK, patch), rock);
    c.lerp(SNOW, smoothstep(h, 300 + patch * 90, 340 + patch * 90) * (1 - smoothstep(slope, 1.3, 2.2)));
  }

  private waterMesh(): THREE.Mesh {
    const mesh = new THREE.Mesh(new THREE.CircleGeometry(RADIUS, 64), this.waterMat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = WATER;
    mesh.receiveShadow = true;
    return mesh;
  }

  private mat(role: string): THREE.MeshStandardMaterial {
    let m = this.forestMats.get(role);
    if (!m) {
      m = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.92, vertexColors: true, flatShading: true });
      this.forestMats.set(role, m);
    }
    return m;
  }

  /** Woods and boulders, instanced per model part and per sector so the camera can cull them. */
  private forest(land: Shape, p: CityPlan) {
    const r = rng(0xf0e57);
    /** s scales x / z, sy height: distant clumps are wide so the canopy closes. */
    type Inst = { x: number; y: number; z: number; s: number; sy: number; ry: number; color: number };
    const buckets = new Map<string, Inst[]>();
    const put = (model: string, inst: Inst) => {
      const sector = Math.floor(((Math.atan2(inst.z, inst.x) + Math.PI) / (Math.PI * 2)) * SECTORS) % SECTORS;
      const key = `${model}:${sector}`;
      const list = buckets.get(key) ?? [];
      list.push(inst);
      buckets.set(key, list);
    };
    const bridge = land.bridge;
    // Where the camera circles (see frameCamera in scene.ts): no rainforest
    // giants there, or one crown fills the view.
    const { minX, maxX, minZ, maxZ } = p.bounds;
    const [cx, cz] = [(minX + maxX) / 2, (minZ + maxZ) / 2];
    const orbit = Math.max(95, Math.max(maxX - minX, maxZ - minZ) * 1.4) + 90;
    // Near woods are real trees packed into a canopy; further out each
    // instance is a clump standing for several, scaled to close the gaps.
    for (const [r0, r1, step] of [[0, 460, 10], [460, 1300, 18], [1300, 2600, 32]] as const) {
      const near = step < 12;
      for (let gx = -r1; gx <= r1; gx += step) {
        for (let gz = -r1; gz <= r1; gz += step) {
          const x = gx + (r() - 0.5) * step;
          const z = gz + (r() - 0.5) * step;
          const d = Math.hypot(x, z);
          if (d < r0 || d >= r1) continue;
          const pick = r();
          const wild = land.wild(x, z);
          if (wild < 0.16 || Math.abs(z - ROAD_Z) < 12 || Math.hypot(x - bridge.x, z - bridge.z) < 40) continue;
          const h = land.height(x, z);
          if (h < WATER + 1.4) continue;
          const slope = Math.hypot(land.height(x + 3, z) - h, land.height(x, z + 3) - h) / 3;
          const line = 230 + fbm(x / 90, z / 90, 2) * 70;
          // Woods close in a few hundred metres out of town; the fields just
          // beyond the last streets stay open meadow with the odd tree.
          const density = cover(x, z) * (0.42 + 0.58 * smoothstep(d, 120, 700)) + 0.01;
          if (pick < density && slope < 0.95 && h < line) {
            const k = r();
            let model =
              h > 150 ? (k < 0.9 ? "forest_b" : "forest_a")
              : h > 55 ? (k < 0.45 ? "forest_b" : k < 0.85 ? "forest_a" : "forest_d")
              : k < 0.36 ? "forest_a" : k < 0.66 ? "forest_d" : k < 0.84 ? "forest_c" : "forest_b";
            if (model === "forest_c" && Math.hypot(x - cx, z - cz) < orbit) model = "forest_a";
            const pine = model === "forest_b";
            const palette = pine ? PINES : LUSH;
            const jitter = 0.8 + r() * 0.45;
            let s: number;
            let sy: number;
            if (near) {
              s = sy = (2.0 + r() * 1.0) * (model === "forest_c" ? 1.25 : 1);
            } else {
              if (!pine) model = "forest_e";
              s = (step / (pine ? 2.8 : 2.4)) * jitter;
              sy = Math.min(s, pine ? 3 + step / 12 : 2.2 + step / 14) * jitter;
            }
            put(model, { x, y: h - Math.max(0.5, s * 0.3), z, s, sy, ry: r() * Math.PI * 2, color: palette[Math.floor(r() * palette.length)] });
          } else if (pick > 0.985 || (slope > 0.5 && pick > 0.94) || (Math.hypot(x - LAKE.x, z - LAKE.z) < LAKE.r * 1.3 && pick > 0.9)) {
            const s = (0.8 + r() * 2.2) * Math.pow(step / 9, 0.8);
            put(r() < 0.5 ? "rock_a" : "rock_b", { x, y: h - 0.3, z, s, sy: s, ry: r() * Math.PI * 2, color: 0xffffff });
          }
        }
      }
    }
    // Scrub and boulders in the fields around town, so the last lots do not
    // sit on a mown lawn.
    for (let gx = -330; gx <= 330; gx += 7) {
      for (let gz = -330; gz <= 330; gz += 7) {
        const x = gx + (r() - 0.5) * 7;
        const z = gz + (r() - 0.5) * 7;
        const open = land.open(x, z);
        if (open < 0.02 || Math.abs(z - ROAD_Z) < 10 || Math.hypot(x - bridge.x, z - bridge.z) < 34) continue;
        const h = land.height(x, z);
        if (h < WATER + 1.2) continue;
        const pick = r();
        const clump = smoothstep(fbm(x / 70 + 12, z / 70 - 3, 2), 0.42, 0.62);
        if (pick < 0.08 + 0.42 * clump) {
          const s2 = (0.45 + r() * 1.05) * (0.7 + open * 0.7);
          put("forest_d", { x, y: h - Math.max(0.4, s2 * 0.3), z, s: s2, sy: s2 * (0.8 + r() * 0.5), ry: r() * Math.PI * 2, color: LUSH[Math.floor(r() * LUSH.length)] });
        } else if (pick > 0.996) {
          const s2 = 0.5 + r() * 1.1;
          put(r() < 0.5 ? "rock_a" : "rock_b", { x, y: h - s2 * 0.4, z, s: s2, sy: s2, ry: r() * Math.PI * 2, color: 0xffffff });
        }
      }
    }
    // Tufts and flower clumps on the town's own grass, so the ground inside
    // the last streets is not a bare lawn.
    const paved = (x: number, z: number) =>
      Math.abs(z - ROAD_Z) < 6 ||
      p.blocks.some((b) => Math.abs(x - b.x) < PITCH_X / 2 - 1 && Math.abs(z - b.z) < PITCH_Z / 2 - 1);
    for (let i = 0; i < 700; i++) {
      const x = minX + r() * (maxX - minX);
      const z = minZ + r() * (maxZ - minZ);
      if (paved(x, z)) continue;
      const s2 = 0.3 + r() * 0.55;
      put(r() < 0.85 ? "forest_d" : "rock_a", { x, y: land.height(x, z) - s2 * 0.3, z, s: s2, sy: s2 * (0.8 + r() * 0.4), ry: r() * Math.PI * 2, color: LUSH[Math.floor(r() * LUSH.length)] });
    }
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const up = new THREE.Vector3(0, 1, 0);
    const v = new THREE.Vector3();
    const sc = new THREE.Vector3();
    const col = new THREE.Color();
    for (const [key, list] of buckets) {
      const model = key.split(":")[0];
      for (const { role, geo } of piece(model).parts) {
        const mesh = new THREE.InstancedMesh(geo, this.mat(role === "leaf" ? "leaf" : role), list.length);
        list.forEach((t, i) => {
          q.setFromAxisAngle(up, t.ry);
          m.compose(v.set(t.x, t.y, t.z), q, sc.set(t.s, t.sy, t.s));
          mesh.setMatrixAt(i, m);
          mesh.setColorAt(i, col.setHex(role === "leaf" ? t.color : role === "bark" ? 0x5a4030 : 0x8a8478));
        });
        mesh.computeBoundingSphere();
        mesh.receiveShadow = true;
        this.group.add(mesh);
      }
    }
  }
}

/** A tiling normal map of soft ripples for the water. */
function ripples(): THREE.Texture {
  const size = 256;
  const data = new Uint8Array(size * size * 4);
  const hgt = (x: number, y: number) => fbm((x / size) * 8, (y / size) * 8, 3);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      // Wrap the noise so the texture tiles: blend opposite edges.
      const sample = (sx: number, sy: number) => {
        const u = sx / size;
        const w = sy / size;
        return hgt(sx, sy) * (1 - u) * (1 - w) + hgt(sx - size, sy) * u * (1 - w) + hgt(sx, sy - size) * (1 - u) * w + hgt(sx - size, sy - size) * u * w;
      };
      const dx = sample(x + 1, y) - sample(x - 1, y);
      const dy = sample(x, y + 1) - sample(x, y - 1);
      const i = (y * size + x) * 4;
      data[i] = Math.max(0, Math.min(255, 128 - dx * 900));
      data[i + 1] = Math.max(0, Math.min(255, 128 - dy * 900));
      data[i + 2] = 255;
      data[i + 3] = 255;
    }
  }
  const t = new THREE.DataTexture(data, size, size);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(220, 220);
  t.needsUpdate = true;
  return t;
}
