// City theme: the kit of building pieces and trees made in Blender
// (ui/blender/city_kit.py writes public/city-kit.glb). Each piece is split
// by material role ("wall", "window", ...); models.ts stacks pieces into
// buildings and picks the real materials. Geometry carries baked ambient
// occlusion as vertex colours and window panes as cells of the window atlas.
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { Kind } from "./plan";

export interface Piece {
  parts: { role: string; geo: THREE.BufferGeometry }[];
  /** Points marked in the kit (smoke, beacon), piece-local. */
  anchors: Record<string, THREE.Vector3>;
}

/** Footprint (x, z) each kind's pieces are modelled at; must match city_kit.py. */
export const NOMINAL: Record<Kind, [number, number]> = {
  cottage: [6.75, 6.25],
  shop: [8.75, 8],
  apartment: [9.15, 9.15],
  office: [9.6, 9.6],
  landmark: [10.4, 10.4],
};

let pieces: Map<string, Piece> | null = null;

export async function loadKit(url = `${import.meta.env.BASE_URL}city-kit.glb`): Promise<void> {
  if (pieces) return;
  const gltf = await new GLTFLoader().loadAsync(url);
  const out = new Map<string, Piece>();
  for (const node of gltf.scene.children) {
    node.updateMatrixWorld(true);
    const parts: Piece["parts"] = [];
    node.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      parts.push({ role: (mesh.material as THREE.Material).name, geo: mesh.geometry.clone().applyMatrix4(mesh.matrixWorld) });
    });
    const anchors: Piece["anchors"] = {};
    for (const [k, v] of Object.entries(node.userData)) {
      if (Array.isArray(v) && v.length === 3) anchors[k] = new THREE.Vector3(v[0], v[1], v[2]);
    }
    out.set(node.name, { parts, anchors });
  }
  pieces = out;
}

export function piece(name: string): Piece {
  const p = pieces?.get(name);
  if (!p) throw new Error(`city kit: no piece "${name}"`);
  return p;
}
