// shadow filter: three's PCF takes 5 hardware-filtered taps on a disc turned
// by per-pixel noise. The scattered reads cost every lit pixel; a single
// tap (the hardware's own 2x2 compare) or a fixed 2x2 grid of them read
// neighbouring texels. shadowTaps() swaps the filter for every material
// compiled after it.
import * as THREE from "three";

export type ShadowTaps = 1 | 4 | 5;

const PCF = /float phi = interleavedGradientNoise[\s\S]*?\) \* 0\.2;/;

const FILTERS: Record<Exclude<ShadowTaps, 5>, string> = {
  1: "shadow = texture( shadowMap, vec3( shadowCoord.xy, shadowCoord.z ) );",
  4: `vec2 o = radius * 0.5;
				shadow = (
					texture( shadowMap, vec3( shadowCoord.xy + vec2( -o.x, -o.y ), shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vec2( o.x, -o.y ), shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vec2( -o.x, o.y ), shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vec2( o.x, o.y ), shadowCoord.z ) )
				) * 0.25;`,
};

const stock = THREE.ShaderChunk.shadowmap_pars_fragment;

/** Sets the PCF filter's taps (5 is three's own); call before materials compile. */
export function shadowTaps(taps: ShadowTaps) {
  if (taps === 5) {
    THREE.ShaderChunk.shadowmap_pars_fragment = stock;
    return;
  }
  if (!PCF.test(stock)) throw new Error("shadow: three's PCF filter changed; update shadow.ts");
  THREE.ShaderChunk.shadowmap_pars_fragment = stock.replace(PCF, FILTERS[taps]);
}
