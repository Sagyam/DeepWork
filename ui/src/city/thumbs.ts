// Pictures of the blueprints for the shop (docs/APP.md):
// each design's realistic model on its lot, drawn once by the city's own
// renderer into a target off screen and kept as a data URL. A design whose
// model is not loaded (the pack is still downloading) gets none, and the
// shop falls back to its outline.
import * as THREE from "three";
import { building, fitReal } from "./models";
import type { Spec } from "./plan";
import { DEFS, hasReal } from "./real";

const W = 240;
const H = 180;
const SS = 2; // supersampling: drawn at twice the size, averaged down

const cache = new Map<string, string>();

/** ACES filmic (Narkowicz's fit) and the sRGB curve, for linear pixels read back from the target. */
function tone(x: number): number {
  x *= 1.1;
  const y = (x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14);
  const c = Math.min(1, Math.max(0, y));
  return c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055;
}

function scene(): THREE.Scene {
  const s = new THREE.Scene();
  s.add(new THREE.HemisphereLight(0xdfe8f2, 0x6a6458, 1.6));
  const sun = new THREE.DirectionalLight(0xfff1dc, 2.6);
  sun.position.set(-40, 60, 50);
  s.add(sun);
  return s;
}

/**
 * The picture of design `id` (a blueprint's model id) as a PNG data URL, or
 * null while its model is not loaded. `seed` picks its paint, as in the city.
 */
export function thumbnail(renderer: THREE.WebGLRenderer, id: string, seed = 3): string | null {
  const hit = cache.get(id);
  if (hit) return hit;
  const def = DEFS[id];
  if (!def || !hasReal(id)) return null;
  const { kind, style } = def;
  const floors = def.floors(kind === "landmark" ? 18 : kind === "office" ? 10 : kind === "apartment" ? 5 : 2);
  const raw: Spec = { index: 0, kind, style, grade: 0, x: 0, z: 0, rot: 0, yard: 0, w: 10, d: 10, floors, floorH: 3, height: 20, wall: seed, accent: seed + 2, seed, damage: 0, rubble: false, model: id };
  const spec = { ...fitReal(raw), x: 0, z: 0, rot: 0 };
  const { group } = building(spec);
  const sc = scene();
  sc.add(group);

  // Frame the whole lot from the front right corner, a little above: the
  // camera backs off until the bounding sphere fits the narrower field.
  const sphere = new THREE.Box3().setFromObject(group).getBoundingSphere(new THREE.Sphere());
  const cam = new THREE.PerspectiveCamera(30, W / H, 0.5, 2000);
  const fov = THREE.MathUtils.degToRad(Math.min(cam.fov, cam.fov * cam.aspect)) / 2;
  const dist = (sphere.radius / Math.sin(fov)) * 0.82;
  const dir = new THREE.Vector3(1.45, 0.95, 1.9).normalize();
  cam.position.copy(sphere.center).addScaledVector(dir, dist);
  cam.lookAt(sphere.center);

  const target = new THREE.WebGLRenderTarget(W * SS, H * SS, { type: THREE.FloatType });
  const prev = renderer.getRenderTarget();
  const clear = renderer.getClearAlpha();
  renderer.setClearAlpha(0);
  renderer.setRenderTarget(target);
  renderer.clear();
  renderer.render(sc, cam);
  renderer.setRenderTarget(prev);
  renderer.setClearAlpha(clear);
  const px = new Float32Array(W * SS * H * SS * 4);
  renderer.readRenderTargetPixels(target, 0, 0, W * SS, H * SS, px);
  target.dispose();
  group.traverse((o) => (o as THREE.Mesh).isMesh && (o as THREE.Mesh).geometry.dispose());

  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;
  const img = ctx.createImageData(W, H);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      let r_ = 0, g = 0, b = 0, a = 0;
      for (let j = 0; j < SS; j++) {
        for (let i = 0; i < SS; i++) {
          // The target's rows run bottom up.
          const k = (((H - 1 - y) * SS + j) * W * SS + x * SS + i) * 4;
          r_ += px[k];
          g += px[k + 1];
          b += px[k + 2];
          a += px[k + 3];
        }
      }
      const n = SS * SS;
      const o = (y * W + x) * 4;
      const al = a / n;
      // Colours come premultiplied by coverage at the edges: undo before toning.
      const un = al > 1e-4 ? 1 / al : 0;
      img.data[o] = tone((r_ / n) * un) * 255;
      img.data[o + 1] = tone((g / n) * un) * 255;
      img.data[o + 2] = tone((b / n) * un) * 255;
      img.data[o + 3] = Math.min(1, al) * 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const url = canvas.toDataURL("image/png");
  cache.set(id, url);
  return url;
}
