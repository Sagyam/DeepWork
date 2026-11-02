// Facade textures drawn on canvases at startup: an 8 x 8 grid of window
// cells per texture. The colour map is greyscale (tinted by the material);
// the emissive map holds the lit windows, scaled by the time of day.
import * as THREE from "three";
import { rng } from "./plan";

export const CELLS = 8;
const PX = 32;
const SIZE = CELLS * PX;

export type Facade = "house" | "residential" | "office" | "glass";

export interface FacadeSet {
  map: THREE.Texture;
  emissive: THREE.Texture;
  /** The same facade with smashed and burnt-out windows. */
  brokenMap: THREE.Texture;
  brokenEmissive: THREE.Texture;
}

function canvas(): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = c.height = SIZE;
  return [c, c.getContext("2d")!];
}

function texture(c: HTMLCanvasElement, color: boolean): THREE.Texture {
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = 4;
  return t;
}

const WARM = ["#ffd38a", "#ffc46b", "#ffe2b0", "#fff0d0", "#ffb35c", "#cfe4ff"];

function draw(kind: Facade, seed: number, broken: boolean): [HTMLCanvasElement, HTMLCanvasElement] {
  const r = rng(seed);
  const [mc, m] = canvas();
  const [ec, e] = canvas();
  m.fillStyle = "#fff";
  m.fillRect(0, 0, SIZE, SIZE);
  e.fillStyle = "#000";
  e.fillRect(0, 0, SIZE, SIZE);
  // Slight grime so walls are not flat.
  for (let i = 0; i < 900; i++) {
    m.fillStyle = `rgba(0,0,0,${r() * 0.05})`;
    m.fillRect(r() * SIZE, r() * SIZE, 2 + r() * 6, 2 + r() * 6);
  }
  for (let row = 0; row < CELLS; row++) {
    for (let col = 0; col < CELLS; col++) {
      const x = col * PX;
      const y = row * PX;
      let wx: number, wy: number, ww: number, wh: number;
      switch (kind) {
        case "house":
          [wx, wy, ww, wh] = [x + 9, y + 8, 14, 15];
          break;
        case "residential":
          [wx, wy, ww, wh] = [x + 7, y + 7, 18, 17];
          break;
        case "office":
          [wx, wy, ww, wh] = [x + 2, y + 6, 28, 20];
          break;
        case "glass":
          [wx, wy, ww, wh] = [x + 1, y + 2, 30, 28];
          break;
      }
      const smashed = broken && r() < 0.55;
      // Frame / sill.
      if (kind !== "glass") {
        m.fillStyle = "#c9c4bc";
        m.fillRect(wx - 2, wy - 2, ww + 4, wh + 4);
        m.fillStyle = "#9a958e";
        m.fillRect(wx - 3, wy + wh + 1, ww + 6, 3);
      }
      const glass = 40 + r() * 30;
      m.fillStyle = smashed ? "#0a0808" : `rgb(${glass * 0.7},${glass * 0.85},${glass + 25})`;
      m.fillRect(wx, wy, ww, wh);
      if (!smashed) {
        // Sky reflection in the upper half.
        const g = m.createLinearGradient(wx, wy, wx + ww, wy + wh);
        g.addColorStop(0, "rgba(255,255,255,0.28)");
        g.addColorStop(0.5, "rgba(255,255,255,0.04)");
        g.addColorStop(1, "rgba(255,255,255,0.12)");
        m.fillStyle = g;
        m.fillRect(wx, wy, ww, wh);
      }
      // Mullions.
      m.fillStyle = kind === "glass" ? "#5a6470" : "#d8d3cb";
      if (kind === "house" || kind === "residential") {
        m.fillRect(wx + ww / 2 - 1, wy, 2, wh);
        m.fillRect(wx, wy + wh / 2 - 1, ww, 2);
      } else {
        m.fillRect(wx + ww / 2 - 0.5, wy, 1, wh);
      }
      if (smashed) {
        // Scorch above the opening.
        const s = m.createRadialGradient(wx + ww / 2, wy, 1, wx + ww / 2, wy - 4, PX * 0.7);
        s.addColorStop(0, "rgba(10,8,8,0.85)");
        s.addColorStop(1, "rgba(10,8,8,0)");
        m.fillStyle = s;
        m.fillRect(x, y - PX / 2, PX, PX);
        // A few still burn.
        if (r() < 0.25) {
          e.fillStyle = "#ff6a1a";
          e.fillRect(wx, wy + wh * 0.3, ww, wh * 0.7);
        }
        continue;
      }
      const lit = r() < (broken ? 0.12 : 0.62);
      if (lit) {
        const warm = WARM[Math.floor(r() * WARM.length)];
        e.fillStyle = warm;
        e.fillRect(wx, wy, ww, wh);
        // Curtains / blinds.
        if (r() < 0.4) {
          e.fillStyle = "rgba(0,0,0,0.55)";
          e.fillRect(wx, wy, ww * (0.2 + r() * 0.3), wh);
        }
      }
    }
  }
  return [mc, ec];
}

const cache = new Map<string, FacadeSet[]>();

/** A few variants per facade kind, so neighbours differ. */
export function facades(kind: Facade): FacadeSet[] {
  let sets = cache.get(kind);
  if (!sets) {
    sets = [0, 1, 2].map((v) => {
      const seed = kind.length * 977 + v * 7919;
      const [m, e] = draw(kind, seed, false);
      const [bm, be] = draw(kind, seed + 1, true);
      return { map: texture(m, true), emissive: texture(e, true), brokenMap: texture(bm, true), brokenEmissive: texture(be, true) };
    });
    cache.set(kind, sets);
  }
  return sets;
}

/** A soft round sprite for particles. */
export function puff(): THREE.Texture {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.25, "rgba(255,255,255,0.55)");
  grad.addColorStop(0.6, "rgba(255,255,255,0.15)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
