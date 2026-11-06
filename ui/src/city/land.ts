// City theme: the countryside meshes, from terrain.ts. Smooth terrain
// coloured by height and slope (meadow, forest floor, river sand, rock,
// snow) with grass and stone detail near the eye, one water plane that
// fills the river and the lake, forests instanced from the trees model (or
// the kit) and boulders of their own (rocks()): lush broadleaf and
// rainforest giants in the lowlands, conifers higher up, bare rock above the
// tree line.
import * as THREE from "three";
import { mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { piece } from "./kit";
import { hasReal, realMat, realPiece, tex } from "./real";
import { IMPOSTOR_NEAR, Impostors, nearOnly } from "./impostor";
import { PITCH_X, PITCH_Z, rng, type CityPlan } from "./plan";
import { LAKE, RADIUS, ROAD_Z, WATER, fbm, noise, smoothstep, terrain, type Land as Shape } from "./terrain";

const RINGS = 300;
const SEGMENTS = 520;
const SECTORS = 12;
/** Side of the tiles the real woods are cut into, in metres. */
const TILE = 96;

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
  private ground = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1 });
  private groundDetail = false;
  private rockMat: THREE.MeshStandardMaterial | null = null;
  private rockGeos: [THREE.BufferGeometry, THREE.BufferGeometry][] = [];
  private waterMat: THREE.MeshStandardMaterial;
  private forestMats = new Map<string, THREE.MeshStandardMaterial>();
  /** The real woods near the camera, in tiles (see cull()). */
  private tiles: { group: THREE.Group; box: THREE.Box3 }[] = [];
  private nearMats = new Map<THREE.Material, THREE.Material>();

  constructor() {
    this.waterMat = new THREE.MeshStandardMaterial({ color: 0x3d6e86, roughness: 0.06, metalness: 0.3, envMapIntensity: 1.2, normalMap: ripples(), normalScale: new THREE.Vector2(0.3, 0.3) });
  }

  /** Rebuild for a city of a new size. */
  build(p: CityPlan, imps: Impostors | null = null) {
    this.group.clear();
    this.tiles = [];
    const land = (this.shape = terrain(p.bounds));
    if (!this.groundDetail && hasReal("trees")) {
      this.groundDetail = true;
      detail(this.ground);
    }
    this.group.add(this.terrainMesh(land), this.waterMesh());
    this.forest(land, p, imps);
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
    // Rings of vertices round the middle, denser near it, each shared by the
    // triangles round it: smooth normals and colours blended across the
    // ground, so hills and mountains read as land, not as facets.
    const pos: number[] = [];
    const col: number[] = [];
    const idx: number[] = [];
    const c = new THREE.Color();
    for (let i = 0; i < RINGS; i++) {
      const r = RADIUS * Math.pow(i / (RINGS - 1), 1.7);
      const dr = Math.max(1.5, RADIUS * 1.7 * Math.pow(Math.max(i, 1) / (RINGS - 1), 0.7) / RINGS);
      const step = (Math.PI * 2) / SEGMENTS;
      const off = (i % 2) * (step / 2);
      for (let j = 0; j < SEGMENTS; j++) {
        const a = j * step + off;
        const x = Math.cos(a) * r;
        const z = Math.sin(a) * r;
        const h = land.height(x, z);
        this.paint(c, land, x, z, h, dr);
        pos.push(x, h, z);
        col.push(c.r, c.g, c.b);
      }
    }
    for (let i = 0; i < RINGS - 1; i++) {
      for (let j = 0; j < SEGMENTS; j++) {
        const j1 = (j + 1) % SEGMENTS;
        const A = i * SEGMENTS + j, B = i * SEGMENTS + j1, C = (i + 1) * SEGMENTS + j, D = (i + 1) * SEGMENTS + j1;
        idx.push(A, B, C, B, D, C);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    g.setIndex(idx);
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
  private forest(land: Shape, p: CityPlan, imps: Impostors | null) {
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
    // The realistic woods (trees model) draw the kit's forest pieces when loaded.
    const real = hasReal("trees");
    const white = new THREE.Color(0xffffff);
    const place = (mesh: THREE.InstancedMesh, list: Inst[], color: (t: Inst) => THREE.Color) => {
      list.forEach((t, i) => {
        q.setFromAxisAngle(up, t.ry);
        m.compose(v.set(t.x, t.y, t.z), q, sc.set(t.s, t.sy, t.s));
        mesh.setMatrixAt(i, m);
        mesh.setColorAt(i, color(t));
      });
      mesh.computeBoundingSphere();
      mesh.receiveShadow = true;
      return mesh;
    };
    // Realistic leaves are textured: the kit's greens only tint them, lightened.
    const tint = (t: Inst) => col.setHex(t.color).lerp(white, 0.45);
    for (const [key, list] of buckets) {
      const model = key.split(":")[0];
      const realistic = real && model.startsWith("forest_");
      if (realistic && imps) {
        // trees: far trees are impostors (impostor.ts), one InstancedMesh a
        // model a sector that hides the trees within IMPOSTOR_NEAR of the
        // camera; those are drawn real, from tiles small enough that only
        // the few round the camera are drawn at all (cull()).
        const card = imps.card(`${model}:forest`, model, { wall: -1, accent: 0, roof: 0, signs: 0 }, "forest");
        this.group.add(place(new THREE.InstancedMesh(card.geo, imps.farMaterial(), list.length), list, tint));
        const tiles = new Map<string, Inst[]>();
        for (const t of list) {
          // Small tiles in the near woods, where trees stand thick; large ones in the far clumps.
          const size = Math.hypot(t.x, t.z) < 500 ? TILE : TILE * 4;
          const k = `${size}:${Math.floor(t.x / size)},${Math.floor(t.z / size)}`;
          const l = tiles.get(k) ?? [];
          l.push(t);
          tiles.set(k, l);
        }
        for (const tl of tiles.values()) {
          const group = new THREE.Group();
          const box = new THREE.Box3();
          for (const t of tl) box.expandByPoint(v.set(t.x, t.y, t.z));
          for (const { role, geo } of realPiece("trees", model)) {
            const leafy = role === "woods" || role === "firs";
            const base = realMat("trees", role, { wall: -1, accent: 0, roof: 0, signs: 0 }, 0, "forest");
            let near = this.nearMats.get(base);
            if (!near) this.nearMats.set(base, (near = nearOnly(base)));
            group.add(place(new THREE.InstancedMesh(geo, near, tl.length), tl, leafy ? tint : () => white));
          }
          group.visible = false;
          this.tiles.push({ group, box });
          this.group.add(group);
        }
        continue;
      }
      if (model.startsWith("rock_")) {
        // Boulders of their own (rocks()), not the kit's low-poly ones.
        // Full detail round the town, a light one (about 500 triangles) beyond.
        const [hi, lo] = this.rocks()[model === "rock_a" ? 0 : 1];
        const tint = (t: Inst) => col.setHex(ROCK_TINTS[Math.floor(Math.abs(t.ry * 1000)) % ROCK_TINTS.length]);
        const near = list.filter((t) => Math.hypot(t.x, t.z) < ROCK_NEAR);
        const far = list.filter((t) => Math.hypot(t.x, t.z) >= ROCK_NEAR);
        if (near.length) this.group.add(place(new THREE.InstancedMesh(hi, this.rockMat!, near.length), near, tint));
        if (far.length) this.group.add(place(new THREE.InstancedMesh(lo, this.rockMat!, far.length), far, tint));
        continue;
      }
      const parts = realistic ? realPiece("trees", model) : piece(model).parts;
      for (const { role, geo } of parts) {
        const leafy = role === "woods" || role === "firs";
        const material = realistic ? (realMat("trees", role, { wall: -1, accent: 0, roof: 0, signs: 0 }, 0, "forest") as THREE.MeshStandardMaterial) : this.mat(role === "leaf" ? "leaf" : role);
        this.group.add(
          place(new THREE.InstancedMesh(geo, material, list.length), list, (t) =>
            realistic ? (leafy ? tint(t) : white) : col.setHex(role === "leaf" ? t.color : role === "bark" ? 0x5a4030 : 0x8a8478),
          ),
        );
      }
    }
  }

  /**
   * Two boulders (rock_a, rock_b at the kit's sizes, about 1 m): a dense
   * sphere pushed about by noise and cut by a few cleavage planes, smooth
   * shaded, darker in its hollows, with stone on it when the library has
   * loaded (triplanar, as boulders have no UVs).
   */
  private rocks(): [THREE.BufferGeometry, THREE.BufferGeometry][] {
    if (this.rockGeos.length) return this.rockGeos;
    this.rockGeos = [
      [rock(7, [1.2, 0.8, 1.0], 8), rock(7, [1.2, 0.8, 1.0], 4)],
      [rock(19, [0.9, 1.1, 1.3], 8), rock(19, [0.9, 1.1, 1.3], 4)],
    ];
    const m = (this.rockMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.92 }));
    if (hasReal("trees")) {
      const stone = tex("stone_col");
      m.onBeforeCompile = (sh) => {
        sh.uniforms.tStone = { value: stone };
        sh.vertexShader = sh.vertexShader
          .replace("#include <common>", "#include <common>\nvarying vec3 vRockP;\nvarying vec3 vRockN;")
          .replace("#include <begin_vertex>", "#include <begin_vertex>\nvRockP = position * 0.9;\nvRockN = normal;");
        sh.fragmentShader = sh.fragmentShader
          .replace("#include <common>", "#include <common>\nuniform sampler2D tStone;\nvarying vec3 vRockP;\nvarying vec3 vRockN;")
          .replace(
            "#include <color_fragment>",
            `#include <color_fragment>
            vec3 rw = pow(abs(normalize(vRockN)), vec3(4.0));
            rw /= rw.x + rw.y + rw.z;
            vec3 st = texture2D(tStone, vRockP.zy).rgb * rw.x + texture2D(tStone, vRockP.xz).rgb * rw.y + texture2D(tStone, vRockP.xy).rgb * rw.z;
            vec3 sm = textureLod(tStone, vec2(0.5), 12.0).rgb;
            diffuseColor.rgb *= sm.g > 0.01 ? clamp(st / sm, 0.0, 2.0) : vec3(1.0);`,
          );
      };
      m.customProgramCacheKey = () => "rock";
    }
    return this.rockGeos;
  }

  /** Shows the real woods' tiles that hold trees within IMPOSTOR_NEAR of the eye; the rest are impostors. */
  cull(eye: THREE.Vector3) {
    for (const t of this.tiles) t.group.visible = t.box.distanceToPoint(eye) < IMPOSTOR_NEAR;
  }
}

/** Boulders closer than this to the town are drawn in full detail. */
const ROCK_NEAR = 350;
const ROCK_TINTS = [0x9a948a, 0x8a8478, 0xa49c90, 0x7c786e, 0x948c80];

/** 3D value noise from three 2D slices: enough to rough up a boulder. */
const noise3 = (x: number, y: number, z: number) => (noise(x, y) + noise(y + 31.7, z - 7.3) + noise(z + 57.1, x + 13.9)) / 3;

/**
 * A boulder with radii `size` (x, height, z) like the kit's, base at y = 0: an icosphere
 * (`detail` 8 is about 1,600 triangles) pushed out by noise, flattened by a few cleavage planes and
 * sunk at the bottom; vertex colours darken its hollows and cracks.
 */
function rock(seed: number, size: [number, number, number], detail: number): THREE.BufferGeometry {
  let g: THREE.BufferGeometry = new THREE.IcosahedronGeometry(1, detail);
  g.deleteAttribute("normal");
  g.deleteAttribute("uv");
  g = mergeVertices(g);
  const r = rng(seed);
  const planes = Array.from({ length: 6 }, () => {
    const n = new THREE.Vector3(r() - 0.5, (r() - 0.5) * 0.6 + 0.25, r() - 0.5).normalize();
    return { n, d: 0.62 + r() * 0.22 };
  });
  const pos = g.getAttribute("position") as THREE.BufferAttribute;
  const col: number[] = [];
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).normalize();
    const big = noise3(v.x * 1.6 + seed, v.y * 1.6, v.z * 1.6) - 0.5;
    const fine = noise3(v.x * 7 + seed, v.y * 7, v.z * 7) - 0.5;
    let k = 1 + big * 0.5 + fine * 0.1;
    // Cleavage: a face of the rock where a plane cuts it, softened.
    for (const p of planes) {
      const along = v.dot(p.n) * k;
      if (along > p.d) k -= (along - p.d) * 0.85;
    }
    v.multiplyScalar(k);
    // Sunk in the ground: the bottom flattened.
    if (v.y < -0.35) v.y = -0.35 + (v.y + 0.35) * 0.25;
    pos.setXYZ(i, v.x * size[0], (v.y + 0.35) * size[1], v.z * size[2]);
    // Hollows and cracks darker, lichen-pale on the crown.
    const shade = THREE.MathUtils.clamp(0.78 + big * 0.5 + fine * 0.6 + Math.max(0, v.y) * 0.12, 0.45, 1.1);
    col.push(shade, shade, shade * 0.97);
  }
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.computeVertexNormals();
  return g;
}

/**
 * Grass and stone on the terrain near the eye: library textures mapped by
 * world position (stone triplanar, on steep or grey ground), divided by
 * their own mean colour so the terrain's painted colours stay in charge,
 * and faded out with distance before their tiling shows.
 */
function detail(m: THREE.MeshStandardMaterial) {
  const grass = tex("grass_col");
  const stone = tex("stone_col");
  m.onBeforeCompile = (sh) => {
    sh.uniforms.tGrass = { value: grass };
    sh.uniforms.tStone = { value: stone };
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vGroundP;\nvarying vec3 vGroundN;")
      .replace("#include <project_vertex>", "#include <project_vertex>\nvGroundP = (modelMatrix * vec4(transformed, 1.0)).xyz;\nvGroundN = normalize(mat3(modelMatrix) * objectNormal);");
    sh.fragmentShader = sh.fragmentShader
      .replace("#include <common>", "#include <common>\nuniform sampler2D tGrass;\nuniform sampler2D tStone;\nvarying vec3 vGroundP;\nvarying vec3 vGroundN;")
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        float gNear = 1.0 - smoothstep(120.0, 900.0, length(vGroundP - cameraPosition));
        if (gNear > 0.0) {
          vec3 gn = normalize(vGroundN);
          vec3 gm = textureLod(tGrass, vec2(0.5), 12.0).rgb;
          vec2 guv = vGroundP.xz / 2.6;
          // A second, larger scale breaks up the tiling.
          vec3 gr = texture2D(tGrass, guv).rgb * mix(0.8, 1.2, texture2D(tGrass, vGroundP.xz / 37.0 + 0.3).g / max(gm.g, 0.01) * 0.5);
          vec3 gd = gm.g > 0.01 ? gr / gm : vec3(1.0);
          vec3 gw = pow(abs(gn), vec3(4.0));
          gw /= gw.x + gw.y + gw.z;
          vec3 sp = vGroundP / 7.0;
          vec3 st = texture2D(tStone, sp.zy).rgb * gw.x + texture2D(tStone, sp.xz).rgb * gw.y + texture2D(tStone, sp.xy).rgb * gw.z;
          vec3 sm = textureLod(tStone, vec2(0.5), 12.0).rgb;
          vec3 sd = sm.g > 0.01 ? st / sm : vec3(1.0);
          vec3 vc = diffuseColor.rgb;
          float hi = max(vc.r, max(vc.g, vc.b));
          float sat = (hi - min(vc.r, min(vc.g, vc.b))) / max(hi, 0.01);
          float rocky = max(1.0 - smoothstep(0.72, 0.9, gn.y), 1.0 - smoothstep(0.12, 0.3, sat));
          diffuseColor.rgb *= mix(vec3(1.0), clamp(mix(gd, sd, rocky), 0.0, 2.5), gNear);
        }`,
      );
  };
  m.customProgramCacheKey = () => "ground-detail";
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
