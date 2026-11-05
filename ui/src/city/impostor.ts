// Tree impostors, shared by the app's scene and the showcase town (where they
// were tried first, docs/models.md "Tried in the showcase town"): past a
// hundred and fifty metres a tree is three crossed cards (front, side and
// top) carrying a picture of its species and tint rendered once at load, 12
// triangles instead of a crown of alpha-tested leaf cards that the GPU
// shades several layers deep. The real trees still draw the shadow map.
import * as THREE from "three";
import type { Parts } from "./models";
import { realMat, realPiece, type Paint } from "./real";
import { rng } from "./plan";

/** Past this many metres from the camera a tree is drawn as its impostor. */
export const IMPOSTOR_NEAR = 150;

// All impostors share one 2048 x 2048 atlas (one material, so a tile's far
// trees are one draw): 256 x 128 slots, each a 64 x 128 front view, a
// 64 x 128 side view and a 128 x 128 top view.
const ATLAS = 2048;

type Card = { geo: THREE.BufferGeometry; mat: THREE.MeshStandardMaterial };

/** A texture whose image has arrived and been uploaded (or no texture). */
export const loaded = (t: THREE.Texture | null | undefined) => !t || (t.image && ((t.image as HTMLImageElement).complete ?? true) && t.version > 0);

export class Impostors {
  private cards = new Map<string, Card>();
  private jobs: { mats: THREE.MeshStandardMaterial[]; draw: () => void }[] = [];
  private atlas: THREE.WebGLRenderTarget | null = null;
  private cleared = false;
  /** The atlas material for merged (Parts) impostors. */
  private mat_: THREE.MeshStandardMaterial | null = null;
  /** The atlas material for instanced impostors that hide within IMPOSTOR_NEAR of the camera (the woods). */
  private far_: THREE.MeshStandardMaterial | null = null;

  constructor(private renderer: THREE.WebGLRenderer) {}

  /** Impostors still waiting for their textures. */
  get pending() {
    return this.jobs.length;
  }

  private material(): THREE.MeshStandardMaterial {
    if (this.mat_) return this.mat_;
    this.atlas = new THREE.WebGLRenderTarget(ATLAS, ATLAS, { colorSpace: THREE.SRGBColorSpace, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter, magFilter: THREE.LinearFilter });
    this.mat_ = new THREE.MeshStandardMaterial({ map: this.atlas.texture, alphaTest: 0.5, roughness: 0.85, vertexColors: true });
    this.mat_.onBeforeCompile = (sh) => sharpen(sh);
    // The real trees draw the shadow map; the cards cast none.
    this.mat_.userData.noShadow = true;
    return this.mat_;
  }

  /** The atlas material for InstancedMesh impostors that leave the near trees to the real ones (see nearOnly). */
  farMaterial(): THREE.MeshStandardMaterial {
    if (this.far_) return this.far_;
    const m = (this.far_ = this.material().clone());
    m.onBeforeCompile = (sh) => {
      sharpen(sh);
      sh.vertexShader = sh.vertexShader.replace("#include <project_vertex>", `#include <project_vertex>\nif (distance(cameraPosition, (modelMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz) < ${IMPOSTOR_NEAR.toFixed(1)}) gl_Position = vec4(0.0, 0.0, 2.0, 1.0);`);
    };
    m.customProgramCacheKey = () => "impostor-far";
    return m;
  }

  /**
   * The cards of one tree model (`pieces` of the realistic trees) in one
   * look; `key` names that pair, `conifer` puts the top card low, where a
   * conifer is widest.
   */
  card(key: string, name: string, paint: Paint, variant = ""): Card {
    const hit = this.cards.get(key);
    if (hit) return hit;
    const atlasMat = this.material();
    const rt = this.atlas!;
    const pieces = realPiece("trees", name);
    const box = new THREE.Box3();
    const sc = new THREE.Scene();
    const mats: THREE.MeshStandardMaterial[] = [];
    // Albedo only: ambient light of pi gives back the base colour (times the baked AO).
    sc.add(new THREE.AmbientLight(0xffffff, Math.PI));
    for (const { role, geo } of pieces) {
      geo.computeBoundingBox();
      box.union(geo.boundingBox!);
      const m = realMat("trees", role, paint, 0, variant) as THREE.MeshStandardMaterial;
      mats.push(m);
      sc.add(new THREE.Mesh(geo, m));
    }
    const { min, max } = box;
    const sy = max.y - min.y;
    const slot = this.cards.size;
    const ox = (slot % (ATLAS / 256)) * 256;
    const oy = Math.floor(slot / (ATLAS / 256)) * 128;
    // Atlas UV of a point (u, v) in this slot's 256 x 128 unit square.
    const A = (u: number, v: number) => [(ox + u * 256) / ATLAS, (oy + v * 128) / ATLAS];
    const cam = (x0: number, x1: number, y0: number, y1: number, pos: THREE.Vector3, up: THREE.Vector3) => {
      const c = new THREE.OrthographicCamera(x0, x1, y1, y0, 0.1, 100);
      c.position.copy(pos);
      c.up.copy(up);
      c.lookAt(pos.x === 0 && pos.z === 0 ? new THREE.Vector3(0, 0, 0) : new THREE.Vector3(0, pos.y, 0));
      return c;
    };
    const views: [THREE.Camera, number, number, number][] = [
      [cam(min.x, max.x, min.y, max.y, new THREE.Vector3(0, 0, max.z + 10), new THREE.Vector3(0, 1, 0)), 0, 64, 128],
      [cam(-max.z, -min.z, min.y, max.y, new THREE.Vector3(max.x + 10, 0, 0), new THREE.Vector3(0, 1, 0)), 64, 64, 128],
      [cam(min.x, max.x, -max.z, -min.z, new THREE.Vector3(0, max.y + 10, 0), new THREE.Vector3(0, 0, -1)), 128, 128, 128],
    ];
    // Drawn into the atlas once the leaf and bark textures have arrived (see draw).
    const r = this.renderer;
    this.jobs.push({
      mats,
      draw: () => {
        const prevTarget = r.getRenderTarget();
        const prevClear = r.getClearAlpha();
        const prevShadows = r.shadowMap.enabled;
        r.shadowMap.enabled = false;
        const prevColor = r.getClearColor(new THREE.Color());
        r.setClearColor(0x000000, 0);
        rt.scissorTest = true;
        for (const [c, x, w, h] of views) {
          rt.viewport.set(ox + x, oy, w, h);
          rt.scissor.set(ox + x, oy, w, h);
          r.setRenderTarget(rt);
          r.render(sc, c);
        }
        rt.scissorTest = false;
        r.setRenderTarget(prevTarget);
        r.setClearColor(prevColor, prevClear);
        r.shadowMap.enabled = prevShadows;
      },
    });

    // The cards: a front (xy) and a side (zy) card, both faces each, and a top card at crown height.
    const crown = new THREE.Vector3((min.x + max.x) / 2, min.y + sy * 0.62, (min.z + max.z) / 2);
    // The top card shows the crown's widest outline: a conifer is widest near its foot.
    const conifer = /spruce|pine|firs|forest_b/.test(name);
    const topY = min.y + sy * (conifer ? 0.3 : 0.62);
    const pos: number[] = [];
    const nrm: number[] = [];
    const uv: number[] = [];
    const vert = (p: THREE.Vector3, u: number, v: number) => {
      pos.push(p.x, p.y, p.z);
      // Normals bent out from the crown's middle, so the cards shade like one rounded mass.
      const n = p.clone().sub(crown).normalize().add(new THREE.Vector3(0, 0.35, 0)).normalize();
      nrm.push(n.x, n.y, n.z);
      const [au, av] = A(u, v);
      uv.push(au, av);
    };
    const quad = (a: THREE.Vector3, b: THREE.Vector3, c: THREE.Vector3, d: THREE.Vector3, ua: number[], ub: number[], uc: number[], ud: number[], both = true) => {
      // a b c d counter-clockwise seen from the front.
      for (const [p, t] of [[a, ua], [b, ub], [c, uc], [a, ua], [c, uc], [d, ud]] as const) vert(p, t[0], t[1]);
      if (both) for (const [p, t] of [[a, ua], [c, uc], [b, ub], [a, ua], [d, ud], [c, uc]] as const) vert(p, t[0], t[1]);
    };
    const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
    const cx = crown.x;
    const cz = crown.z;
    quad(V(min.x, min.y, cz), V(max.x, min.y, cz), V(max.x, max.y, cz), V(min.x, max.y, cz), [0, 0], [0.25, 0], [0.25, 1], [0, 1]);
    quad(V(cx, min.y, max.z), V(cx, min.y, min.z), V(cx, max.y, min.z), V(cx, max.y, max.z), [0.25, 0], [0.5, 0], [0.5, 1], [0.25, 1]);
    quad(V(min.x, topY, max.z), V(max.x, topY, max.z), V(max.x, topY, min.z), V(min.x, topY, min.z), [0.5, 0], [1, 0], [1, 1], [0.5, 1], false);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute("normal", new THREE.Float32BufferAttribute(nrm, 3));
    geo.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    // White: the atlas material takes vertex colours, so merged cards can be tinted.
    geo.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(pos.length).fill(1), 3));
    const out = { geo, mat: atlasMat };
    this.cards.set(key, out);
    return out;
  }

  /** The impostor of the tree that models.ts tree() places with the same arguments (same seed, species, size, turn and tint). */
  tree(p: Parts, x: number, z: number, s: number, seed: number, y: number, species: string[]) {
    const r = rng(seed);
    const name = species[Math.floor(r() * species.length)];
    const k = 0.5 + 0.55 * s;
    const scale = new THREE.Vector3(k, k * (0.88 + r() * 0.24), k);
    const ry = r() * Math.PI * 2;
    const tint = Math.floor(r() * 6);
    const { geo, mat } = this.card(`${name}:${tint}`, name, { wall: tint, accent: 0, roof: 0, signs: 0 });
    p.add(mat, geo, x, y, z, 0, ry, 0, scale);
  }

  /** Draws the impostors whose textures have loaded; true once none are left. */
  draw(): boolean {
    const r = this.renderer;
    if (!this.cleared && this.atlas) {
      // A new render target holds garbage until cleared: clear it once, before the first slot.
      const prev = r.getRenderTarget();
      const alpha = r.getClearAlpha();
      const color = r.getClearColor(new THREE.Color());
      r.setRenderTarget(this.atlas);
      r.setClearColor(0x000000, 0);
      r.clear();
      r.setRenderTarget(prev);
      r.setClearColor(color, alpha);
      this.cleared = true;
    }
    for (let i = this.jobs.length - 1; i >= 0; i--) {
      const j = this.jobs[i];
      if (j.mats.every((m) => loaded(m.map) && loaded(m.aoMap) && loaded(m.normalMap))) {
        j.draw();
        this.jobs.splice(i, 1);
      }
    }
    return this.jobs.length === 0;
  }
}

/**
 * Leaf alpha averages away in the small mip levels far trees use, and a
 * plain 0.5 cut-off then drops them entirely: cut lower, and sharpen the
 * edge to one pixel by alpha's screen-space slope (Ben Golus's trick).
 */
function sharpen(sh: THREE.WebGLProgramParametersWithUniforms) {
  sh.fragmentShader = sh.fragmentShader.replace("#include <alphatest_fragment>", "diffuseColor.a = (diffuseColor.a - 0.22) / max(fwidth(diffuseColor.a), 0.0001) + 0.5;\nif (diffuseColor.a < 0.5) discard;");
}

/**
 * Makes an instanced material draw only the instances within IMPOSTOR_NEAR
 * of the camera (the rest are impostors, farMaterial). The shadow pass uses
 * three's own depth material, so every instance still casts its shadow.
 */
export function nearOnly(m: THREE.Material): THREE.Material {
  const c = m.clone();
  const prev = m.onBeforeCompile.bind(m);
  const key = m.customProgramCacheKey();
  c.onBeforeCompile = (sh, r) => {
    prev(sh, r);
    sh.vertexShader = sh.vertexShader.replace("#include <project_vertex>", `#include <project_vertex>\nif (distance(cameraPosition, (modelMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz) >= ${IMPOSTOR_NEAR.toFixed(1)}) gl_Position = vec4(0.0, 0.0, 2.0, 1.0);`);
  };
  c.customProgramCacheKey = () => `${key}:near-only`;
  c.userData = { ...m.userData };
  return c;
}
