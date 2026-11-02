// Window atlas drawn on canvases at startup. Every pane of the Blender kit
// maps to one cell of an ATLAS x ATLAS grid, and buildings shift cells per
// floor, so each window gets its own look: the colour map holds glass,
// curtains and blinds by day, the emissive map the lit rooms at night.
import * as THREE from "three";
import { rng } from "./plan";

/** Cells per side; must match CELLS in city_kit.py. */
export const ATLAS = 32;
const PX = 16;
const SIZE = ATLAS * PX;

/** Residential sash windows, or office glazing. */
export type Pane = "window" | "glass";

export interface PaneSet {
  map: THREE.Texture;
  emissive: THREE.Texture;
  /** Smashed, scorched and partly burning. */
  brokenMap: THREE.Texture;
  brokenEmissive: THREE.Texture;
}

function canvas(): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = c.height = SIZE;
  return [c, c.getContext("2d")!];
}

function texture(c: HTMLCanvasElement): THREE.Texture {
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  // glTF UVs run top-down.
  t.flipY = false;
  t.anisotropy = 4;
  return t;
}

const WARM = ["#ffd38a", "#ffc46b", "#ffe2b0", "#fff0d0", "#ffb35c", "#ffcf9a"];
const COOL = ["#fff1d8", "#ffe6c0", "#f2f0ea", "#ffd9a8", "#e8eefc"];
const CURTAINS = ["#e8e0cc", "#d9c7a8", "#b8483a", "#4a6a8a", "#c9b07a", "#f0ece4", "#7a8a5a"];

function draw(kind: Pane, seed: number, broken: boolean): [HTMLCanvasElement, HTMLCanvasElement] {
  const r = rng(seed);
  const [mc, m] = canvas();
  const [ec, e] = canvas();
  e.fillStyle = "#000";
  e.fillRect(0, 0, SIZE, SIZE);
  for (let row = 0; row < ATLAS; row++) {
    for (let col = 0; col < ATLAS; col++) {
      const x = col * PX;
      const y = row * PX;
      const smashed = broken && r() < 0.55;
      // Glass: dark, with a sky reflection that fades down the pane.
      const base = kind === "glass" ? 150 + r() * 60 : 34 + r() * 26;
      m.fillStyle = smashed ? "#0b0908" : kind === "glass" ? `rgb(${base},${base},${base})` : `rgb(${base * 0.75},${base * 0.9},${base + 22})`;
      m.fillRect(x, y, PX, PX);
      if (!smashed) {
        const g = m.createLinearGradient(x, y, x + PX * 0.6, y + PX);
        g.addColorStop(0, `rgba(255,255,255,${kind === "glass" ? 0.35 : 0.22})`);
        g.addColorStop(0.55, "rgba(255,255,255,0)");
        g.addColorStop(1, "rgba(0,0,0,0.12)");
        m.fillStyle = g;
        m.fillRect(x, y, PX, PX);
      }
      if (smashed) {
        // Jagged shards and soot.
        m.fillStyle = "rgba(90,90,96,0.6)";
        for (let i = 0; i < 3; i++) {
          m.beginPath();
          const sx = x + r() * PX;
          m.moveTo(sx, y);
          m.lineTo(sx + (r() - 0.5) * 6, y + 3 + r() * 5);
          m.lineTo(sx + 3, y);
          m.fill();
        }
        if (r() < 0.3) {
          e.fillStyle = r() < 0.5 ? "#ff5a10" : "#ff8a20";
          e.fillRect(x, y + PX * (0.25 + r() * 0.3), PX, PX);
          e.fillStyle = "#ffc040";
          e.fillRect(x + 3, y + PX * 0.7, PX - 6, PX * 0.3);
        }
        continue;
      }
      const lit = r() < (broken ? 0.12 : kind === "glass" ? 0.5 : 0.58);
      if (kind === "window") {
        // Curtains or blinds by day, muntins on top.
        const dressing = r();
        const cur = CURTAINS[Math.floor(r() * CURTAINS.length)];
        if (dressing < 0.45) {
          const w = PX * (0.18 + r() * 0.2);
          m.fillStyle = cur;
          m.fillRect(x, y, w, PX);
          m.fillRect(x + PX - w, y, w, PX);
        } else if (dressing < 0.65) {
          m.fillStyle = "#ddd6c8";
          m.fillRect(x, y, PX, PX * (0.2 + r() * 0.6));
          m.fillStyle = "rgba(0,0,0,0.15)";
          for (let ly = y + 2; ly < y + PX; ly += 2) m.fillRect(x, ly, PX, 0.6);
        }
        if (lit) {
          const warm = r() < 0.08 ? "#9ec4ff" : WARM[Math.floor(r() * WARM.length)];
          const g = e.createRadialGradient(x + PX / 2, y + PX * 0.35, 1, x + PX / 2, y + PX / 2, PX * 0.75);
          g.addColorStop(0, warm);
          g.addColorStop(1, "rgba(120,70,20,0.85)");
          e.fillStyle = g;
          e.fillRect(x, y, PX, PX);
          if (dressing < 0.45) {
            e.fillStyle = "rgba(0,0,0,0.55)";
            const w = PX * (0.2 + r() * 0.15);
            e.fillRect(x, y, w, PX);
            e.fillRect(x + PX - w, y, w, PX);
          }
        }
        m.fillStyle = "#e8e4dc";
        m.fillRect(x + PX / 2 - 0.5, y, 1, PX);
        m.fillRect(x, y + PX * 0.45, PX, 1);
        e.fillStyle = "#000";
        e.fillRect(x + PX / 2 - 0.5, y, 1, PX);
        e.fillRect(x, y + PX * 0.45, PX, 1);
      } else {
        // Offices: a ceiling-light band and desks; some floors half lit.
        m.fillStyle = "rgba(0,0,0,0.18)";
        m.fillRect(x, y + PX * 0.82, PX, PX * 0.18);
        if (lit) {
          const c = COOL[Math.floor(r() * COOL.length)];
          const g = e.createLinearGradient(x, y, x, y + PX);
          g.addColorStop(0, c);
          g.addColorStop(1, "rgba(90,60,30,0.9)");
          e.fillStyle = g;
          e.globalAlpha = 0.45 + r() * 0.45;
          e.fillRect(x, y, PX, PX);
          e.globalAlpha = 1;
          e.fillStyle = c;
          e.fillRect(x, y + 1, PX, 1.5);
          e.fillStyle = "rgba(0,0,0,0.5)";
          for (let i = 0; i < 2; i++) e.fillRect(x + 1 + r() * (PX - 6), y + PX * 0.62, 3 + r() * 3, PX * 0.38);
        } else if (r() < 0.2) {
          e.fillStyle = "#1a2a40";
          e.fillRect(x, y, PX, PX);
        }
      }
    }
  }
  return [mc, ec];
}

const cache = new Map<Pane, PaneSet>();

export function panes(kind: Pane): PaneSet {
  let set = cache.get(kind);
  if (!set) {
    const seed = kind === "glass" ? 7919 : 977;
    const [m, e] = draw(kind, seed, false);
    const [bm, be] = draw(kind, seed + 1, true);
    set = { map: texture(m), emissive: texture(e), brokenMap: texture(bm), brokenEmissive: texture(be) };
    cache.set(kind, set);
  }
  return set;
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
