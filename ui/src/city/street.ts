// Where the pavement furniture round a block stands: the scene draws it
// there, pedestrians walk round it (walks.ts) and buses stop at the
// shelters (roads.ts). Pure.
import { BLOCK_X, BLOCK_Z, PAVEMENT } from "./plan";

/** Lamps and kerbside trees stand this far in from the pavement's outer edge. */
export const KERB_SET = 0.45;
/** Lamp posts along the north and south kerbs, as fractions of the half block. */
export const LAMP_T = [-1, -1 / 3, 1 / 3, 1];
/** Trees between them, from a boulevard up. */
export const TREE_T = [-5 / 6, -1 / 2, -1 / 6, 1 / 6, 1 / 2, 5 / 6];

/** A piece of street.glb on the pavement, and its footprint as placed, for walking round it. */
export interface Prop {
  piece: string;
  x: number;
  z: number;
  rot: number;
  phase?: string;
  boxes: Box[];
}

/** An area on the ground, world x and z. */
export interface Box {
  x0: number;
  x1: number;
  z0: number;
  z1: number;
}

/** `boxes`: [x0, x1, z0, z1] about the origin, as placed. */
const prop = (piece: string, x: number, z: number, rot: number, boxes: number[][], phase?: string): Prop => ({
  piece,
  x,
  z,
  rot,
  phase,
  boxes: boxes.map(([x0, x1, z0, z1]) => ({ x0: x + x0, x1: x + x1, z0: z + z0, z1: z + z1 })),
});

/**
 * The furniture round a block: from a town on, traffic signals at its
 * corners (mast arms over the roads running along z, posts for those along
 * x, on opposite phases); a hydrant, litter bins and a bench; a bus shelter
 * from a city on.
 */
export function streetProps(b: { x: number; z: number }, tier: number): Prop[] {
  const pw = PAVEMENT;
  const cx = BLOCK_X / 2 + pw - 0.55;
  const cz = BLOCK_Z / 2 + pw - 0.55;
  const kerb = BLOCK_Z / 2 + pw - 0.4;
  const out: Prop[] = [];
  if (tier >= 1) {
    const pole = [[-0.3, 0.3, -0.3, 0.3]];
    out.push(prop("signal_mast", b.x + cx, b.z + cz, Math.PI / 2, pole, "a"));
    out.push(prop("signal_mast", b.x - cx, b.z - cz, -Math.PI / 2, pole, "a"));
    out.push(prop("signal_post", b.x - cx, b.z + cz, 0, pole, "b"));
    out.push(prop("signal_post", b.x + cx, b.z - cz, Math.PI, pole, "b"));
  }
  out.push(prop("hydrant", b.x, b.z + kerb, 0, [[-0.23, 0.23, -0.23, 0.23]]));
  for (const sx of [-1, 1]) out.push(prop("bin", b.x + sx * (BLOCK_X / 2 - 3.2), b.z - sx * kerb, sx > 0 ? 0 : Math.PI, [[-0.3, 0.3, -0.3, 0.3]]));
  out.push(prop("bench", b.x - 20.7, b.z + BLOCK_Z / 2 + pw - 1.3, 0, [[-1, 1, -0.25, 0.25]]));
  // Turned to face the road, its glazed back toward the block (the flag's thin pole by the kerb is left out).
  if (tier >= 2) out.push(prop("busstop", b.x + 20.7, b.z - (BLOCK_Z / 2 + pw - 1.0), Math.PI, [[-1.7, 1.7, -0.65, 0.6]]));
  return out;
}

/** The shelter's spot on the kerb, where a bus stops (null below a city). */
export function busStop(b: { x: number; z: number }, tier: number): { x: number; z: number } | null {
  return tier >= 2 ? { x: b.x + 20.7, z: b.z - BLOCK_Z / 2 - PAVEMENT } : null;
}
