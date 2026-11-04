// Window glass that shows a room behind it (interior mapping): a ray from the
// camera is traced through a box room, a piece of furniture and a curtain
// layer, all in the shader, so every pane gets depth and parallax for the
// cost of one quad. The glass on top reflects the sky (MeshPhysicalMaterial
// with a high ior), so windows read as glass by day and lit rooms by night.
//
// UV0 on panes is (window id + u, v) across the whole opening; the window's
// size in metres comes from screen derivatives, so no extra attributes.
import * as THREE from "three";

export type RoomKind = "home" | "shop" | "lobby";

export const interiorUniforms = {
  uDay: { value: 1 },
  uNight: { value: 0 },
};

const PARS = /* glsl */ `
uniform float uDay;
uniform float uNight;
uniform int uKind;
uniform float uBurn;
varying vec3 vWP;
varying vec3 vWN;
varying vec2 vPane;

float hash(float n) { return fract(sin(n * 127.1 + 0.37) * 43758.5453); }

// Ray / box slab test; returns entry t or -1, and the hit normal axis.
float boxHit(vec3 ro, vec3 rd, vec3 lo, vec3 hi, out vec3 n) {
  vec3 inv = 1.0 / rd;
  vec3 t0 = (lo - ro) * inv;
  vec3 t1 = (hi - ro) * inv;
  vec3 tn = min(t0, t1);
  vec3 tf = max(t0, t1);
  float a = max(max(tn.x, tn.y), tn.z);
  float b = min(min(tf.x, tf.y), tf.z);
  if (a > b || b < 0.0) return -1.0;
  n = a == tn.x ? vec3(1.0, 0.0, 0.0) : a == tn.y ? vec3(0.0, 1.0, 0.0) : vec3(0.0, 0.0, 1.0);
  return a;
}

vec3 palette(float h) {
  vec3 c[6];
  c[0] = vec3(0.86, 0.82, 0.74); c[1] = vec3(0.72, 0.78, 0.80); c[2] = vec3(0.78, 0.80, 0.68);
  c[3] = vec3(0.92, 0.90, 0.86); c[4] = vec3(0.82, 0.70, 0.62); c[5] = vec3(0.66, 0.68, 0.72);
  return c[int(h * 5.999)];
}

vec3 fabric(float h) {
  vec3 c[6];
  c[0] = vec3(0.85, 0.80, 0.68); c[1] = vec3(0.55, 0.16, 0.12); c[2] = vec3(0.22, 0.32, 0.45);
  c[3] = vec3(0.92, 0.90, 0.84); c[4] = vec3(0.62, 0.55, 0.32); c[5] = vec3(0.35, 0.42, 0.30);
  return c[int(h * 5.999)];
}

vec3 interior() {
  float id = floor(vPane.x + 1e-4);
  float lu = vPane.x - id;
  float lv = 1.0 - vPane.y;
  vec3 N = normalize(vWN);
  vec3 T = normalize(cross(vec3(0.0, 1.0, 0.0), N));
  vec3 V = normalize(vWP - cameraPosition);
  float s = dot(vWP, T);
  float W = length(vec2(dFdx(s), dFdy(s))) / max(length(vec2(dFdx(lu), dFdy(lu))), 1e-5);
  float H = length(vec2(dFdx(vWP.y), dFdy(vWP.y))) / max(length(vec2(dFdx(lv), dFdy(lv))), 1e-5);
  W = clamp(W, 0.5, 6.0);
  H = clamp(H, 0.5, 4.0);
  vec3 ro = vec3(lu * W, lv * H, 0.0);
  vec3 rd = vec3(dot(V, T), V.y, -dot(V, N));
  rd.z = max(rd.z, 0.05);

  bool shop = uKind == 1;
  float r1 = hash(id), r2 = hash(id + 17.0), r3 = hash(id + 41.0), r4 = hash(id + 73.0);
  // Rooms are at least as wide as their window (glass walls), and shift
  // sideways behind narrower ones.
  float RW = shop ? W + 0.2 : max(3.6, W + 0.2);
  float x0 = W * 0.5 - RW * 0.5 + (shop ? 0.0 : (r2 - 0.5) * min(0.8, RW - W - 0.2));
  float x1 = x0 + RW;
  float fl = shop || uKind == 2 ? 0.0 : (H > 2.1 ? -0.05 : -0.9);
  float ce = fl + (shop ? 3.4 : 2.8);
  float depth = shop ? 6.5 : 4.2;

  float tx = rd.x > 0.0 ? (x1 - ro.x) / rd.x : (x0 - ro.x) / rd.x;
  float ty = rd.y > 0.0 ? (ce - ro.y) / rd.y : (fl - ro.y) / rd.y;
  float tz = depth / rd.z;
  float t = min(tx, min(ty, tz));
  vec3 p = ro + rd * t;

  // Surfaces of the room.
  vec3 wall = shop ? vec3(0.9, 0.88, 0.84) : palette(r1);
  vec3 col;
  float shade = 1.0;
  if (t == ty && rd.y < 0.0) {
    col = shop ? mix(vec3(0.75), vec3(0.32), step(0.5, fract(floor(p.x * 2.0) * 0.5 + floor(p.z * 2.0) * 0.5)))
               : vec3(0.42, 0.28, 0.17) * (0.85 + 0.15 * sin(p.x * 40.0 + r3 * 9.0));
    shade = 0.8;
  } else if (t == ty) {
    col = vec3(0.95);
    float lamp = length(vec2(p.x - (x0 + x1) * 0.5, p.z - depth * 0.45));
    col += vec3(3.0, 2.4, 1.6) * smoothstep(0.25, 0.0, lamp) * (shop ? 1.0 : uNight);
    shade = 0.75;
  } else if (t == tx) {
    col = wall * 0.85;
    shade = 0.8;
  } else {
    col = wall;
    // A doorway or a picture on the back wall.
    float dx = x0 + RW * (0.2 + 0.6 * r3);
    if (!shop && abs(p.x - dx) < 0.45 && p.y - fl < 2.05) col = wall * 0.35;
    else if (!shop && abs(p.x - (x0 + x1 - dx)) < 0.4 && abs(p.y - fl - 1.6) < 0.3) col = fabric(r4) * 0.8;
  }
  float yy = p.y - fl;
  if (t != ty && yy < 0.09) col *= 0.6;
  if (shop && t != ty) {
    // Shelves full of stock along the walls.
    float row = fract(yy / 0.45);
    if (yy > 0.2 && yy < 2.3) {
      float item = floor((p.x + p.z) * 9.0) + floor(yy / 0.45) * 31.0;
      vec3 stock = fabric(hash(item)) * (0.55 + 0.45 * hash(item + 3.0));
      float gap = step(0.82, fract((p.x + p.z) * 9.0)) + step(0.8, row);
      col = row < 0.1 ? vec3(0.3, 0.22, 0.15) : mix(stock, vec3(0.12, 0.1, 0.08), clamp(gap, 0.0, 1.0));
    }
  }

  // A piece of furniture against the back wall: sofa, sideboard or bed; a counter in shops.
  vec3 fn;
  float fw = shop ? 2.4 : 1.4 + r4;
  float fh = shop ? 1.0 : 0.5 + 0.4 * r2;
  float fd = shop ? 0.7 : 0.8;
  float fx = shop ? x0 + RW * 0.6 : x0 + RW * (0.3 + 0.4 * r1);
  float fz = shop ? depth * 0.45 : depth - fd;
  vec3 lo = vec3(fx - fw * 0.5, fl, fz);
  vec3 hi = vec3(fx + fw * 0.5, fl + fh, fz + fd);
  float tb = boxHit(ro, rd, lo, hi, fn);
  if (tb > 0.0 && tb < t) {
    t = tb;
    p = ro + rd * t;
    col = shop ? vec3(0.45, 0.3, 0.2) : fabric(fract(r4 * 7.0)) * 0.8;
    shade = fn.y > 0.5 ? 1.0 : fn.x > 0.5 ? 0.7 : 0.85;
  }

  // Light: daylight falls off into the room; at night some rooms are lit.
  float fall = mix(1.0, 0.35, clamp(p.z / depth, 0.0, 1.0));
  vec3 day = vec3(0.32, 0.33, 0.35) * uDay * fall;
  bool lit = (shop || hash(id + 5.0) < 0.55) && hash(id + 7.0) >= uBurn;
  vec3 warm = mix(vec3(1.0, 0.72, 0.45), vec3(1.0, 0.86, 0.7), hash(id + 9.0));
  vec3 night = lit ? warm * (shop ? 1.4 : 0.9) * mix(1.0, 0.55, clamp(p.z / depth, 0.0, 1.0)) : vec3(0.0);
  if (!lit && hash(id + 3.0) < 0.15) night = vec3(0.12, 0.18, 0.35) * (0.8 + 0.2 * sin(id * 3.0));
  if (shop) day += vec3(0.3, 0.29, 0.27) * fall;
  vec3 room = col * shade * (day + night * uNight);

  // Curtains and blinds in the glass plane.
  if (uKind == 0) {
    float kind = hash(id + 29.0);
    vec3 cc = fabric(hash(id + 31.0));
    float a = 0.0;
    float fold = 1.0;
    if (kind < 0.4) {
      float c = 0.1 + 0.22 * hash(id + 37.0);
      if (lu < c || lu > 1.0 - c) { a = 1.0; fold = 0.75 + 0.25 * sin(lu * 70.0); }
    } else if (kind < 0.7) {
      float b = 0.15 + 0.6 * hash(id + 43.0);
      if (lv > 1.0 - b) { a = 1.0; fold = 0.85 + 0.15 * step(0.45, fract(lv * 30.0)); cc = vec3(0.88, 0.86, 0.8); }
    } else if (kind < 0.85) {
      a = 0.6; cc = vec3(0.95, 0.94, 0.9);
    }
    vec3 cur = cc * fold * (vec3(0.5) * uDay + (lit ? warm * 0.75 : vec3(0.0)) * uNight);
    room = mix(room, cur, a);
  }
  // Damage: soot, and burnt-out rooms that no longer light up.
  return room * mix(1.0, 0.1, uBurn);
}
`;

/** `burn` 0 to 1 darkens the rooms and puts their lights out, for damage. */
export function glass(kind: RoomKind, burn = 0): THREE.MeshPhysicalMaterial {
  const m = new THREE.MeshPhysicalMaterial({ color: 0x000000, roughness: 0.03, metalness: 0, ior: 1.65, envMapIntensity: 1 });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uDay = interiorUniforms.uDay;
    sh.uniforms.uNight = interiorUniforms.uNight;
    sh.uniforms.uKind = { value: kind === "home" ? 0 : kind === "shop" ? 1 : 2 };
    sh.uniforms.uBurn = { value: burn };
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vWP;\nvarying vec3 vWN;\nvarying vec2 vPane;")
      .replace("#include <worldpos_vertex>", "#include <worldpos_vertex>\nmat4 wm = modelMatrix;\n#ifdef USE_INSTANCING\nwm = modelMatrix * instanceMatrix;\n#endif\nvWP = (wm * vec4(transformed, 1.0)).xyz;\nvWN = normalize(mat3(wm) * objectNormal);\nvPane = uv;");
    sh.fragmentShader = sh.fragmentShader
      .replace("#include <common>", `#include <common>\n${PARS}`)
      .replace("#include <emissivemap_fragment>", "#include <emissivemap_fragment>\ntotalEmissiveRadiance += interior();");
  };
  m.customProgramCacheKey = () => `interior-${kind}`;
  m.userData.interior = true;
  return m;
}
