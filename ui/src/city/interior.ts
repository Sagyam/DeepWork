// Window glass that shows a room behind it (interior mapping): a ray from the
// camera is traced through a box room, a piece of furniture and a curtain
// layer, all in the shader, so every pane gets depth and parallax for the
// cost of one quad. The glass on top reflects the sky (MeshPhysicalMaterial
// with a high ior), so windows read as glass by day and lit rooms by night.
//
// UV0 on panes is (window id + u, v) across the whole opening; the window's
// size in metres comes from screen derivatives, so no extra attributes.
import * as THREE from "three";

export type RoomKind = "home" | "shop" | "lobby" | "diner" | "works";

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

void hitBox(vec3 ro, vec3 rd, vec3 lo, vec3 hi, vec3 c, inout float t, inout vec3 col, inout vec3 nn) {
  vec3 n;
  float tb = boxHit(ro, rd, lo, hi, n);
  if (tb > 0.0 && tb < t) { t = tb; col = c; nn = n; }
}

// A diner seen through one of its windows: a booth at the window (red vinyl
// seats either side of a table, sometimes with customers), the aisle, the
// counter with its stools, and the back bar against the far wall; the room
// runs on to either side, so neighbouring windows show one long room.
vec3 diner(vec3 ro, vec3 rd, float id, float W) {
  float fl = -0.96, ce = fl + 2.8, depth = 4.6;
  float x0 = -9.0, x1 = W + 9.0;
  float tx = rd.x > 0.0 ? (x1 - ro.x) / rd.x : (x0 - ro.x) / rd.x;
  float ty = rd.y > 0.0 ? (ce - ro.y) / rd.y : (fl - ro.y) / rd.y;
  float tz = depth / rd.z;
  float t = min(tx, min(ty, tz));
  vec3 p = ro + rd * t;
  vec3 col, nn;
  float glow = 0.0;
  if (t == ty && rd.y < 0.0) {
    float ch = mod(floor(p.x / 0.3) + floor(p.z / 0.3), 2.0);
    col = mix(vec3(0.86, 0.84, 0.8), vec3(0.07), ch);
    nn = vec3(0.0, 1.0, 0.0);
  } else if (t == ty) {
    col = vec3(0.93, 0.91, 0.84);
    // Round lights over the booths and along the counter.
    float a = length(vec2(p.x - W * 0.5, p.z - 0.9));
    float b = length(vec2(fract(p.x / 1.4) * 1.4 - 0.7, p.z - 3.0));
    glow = smoothstep(0.24, 0.1, min(a, b));
    nn = vec3(0.0, -1.0, 0.0);
  } else if (t == tz) {
    float y = p.y - fl;
    if (y < 1.0) col = vec3(0.62, 0.64, 0.66) * (0.85 + 0.15 * step(0.04, fract(p.x / 0.6)));
    else if (y < 1.65) col = mix(vec3(0.32, 0.62, 0.6), vec3(0.94), step(0.1, min(fract(p.x / 0.15), fract(y / 0.15))) * 0.5);
    else if (y < 2.25) {
      // Menu boards and a pie case.
      col = vec3(0.1, 0.09, 0.08);
      if (fract(y / 0.09) < 0.35 && fract(p.x / 1.6) < 0.8 && fract(p.x / 1.6) > 0.08) col = vec3(0.8, 0.76, 0.62);
    } else col = vec3(0.68, 0.7, 0.72);
    nn = vec3(0.0, 0.0, -1.0);
  } else {
    col = vec3(0.9, 0.86, 0.76);
    nn = vec3(1.0, 0.0, 0.0);
  }
  vec3 vinyl = vec3(0.6, 0.07, 0.08);
  vec3 chrome = vec3(0.75, 0.77, 0.8);
  // The booth: backs on the mullions, seats, the table and its pedestal.
  hitBox(ro, rd, vec3(-0.07, fl, 0.02), vec3(0.07, fl + 1.15, 1.3), vinyl, t, col, nn);
  hitBox(ro, rd, vec3(W - 0.07, fl, 0.02), vec3(W + 0.07, fl + 1.15, 1.3), vinyl, t, col, nn);
  hitBox(ro, rd, vec3(0.07, fl, 0.02), vec3(0.5, fl + 0.45, 1.3), vinyl * 1.15, t, col, nn);
  hitBox(ro, rd, vec3(W - 0.5, fl, 0.02), vec3(W - 0.07, fl + 0.45, 1.3), vinyl * 1.15, t, col, nn);
  hitBox(ro, rd, vec3(0.55, fl + 0.7, 0.02), vec3(W - 0.55, fl + 0.75, 0.75), vec3(0.88, 0.86, 0.8), t, col, nn);
  hitBox(ro, rd, vec3(W * 0.5 - 0.05, fl, 0.35), vec3(W * 0.5 + 0.05, fl + 0.7, 0.45), chrome, t, col, nn);
  // Customers, some booths.
  vec3 skin = mix(vec3(0.85, 0.66, 0.52), vec3(0.42, 0.28, 0.2), hash(id + 51.0));
  if (hash(id + 47.0) < 0.6) {
    hitBox(ro, rd, vec3(0.14, fl + 0.45, 0.35), vec3(0.42, fl + 1.02, 0.78), fabric(hash(id + 53.0)), t, col, nn);
    hitBox(ro, rd, vec3(0.2, fl + 1.05, 0.46), vec3(0.38, fl + 1.3, 0.66), skin, t, col, nn);
  }
  if (hash(id + 59.0) < 0.45) {
    vec3 skin2 = mix(vec3(0.85, 0.66, 0.52), vec3(0.42, 0.28, 0.2), hash(id + 61.0));
    hitBox(ro, rd, vec3(W - 0.42, fl + 0.45, 0.35), vec3(W - 0.14, fl + 1.02, 0.78), fabric(hash(id + 67.0)), t, col, nn);
    hitBox(ro, rd, vec3(W - 0.38, fl + 1.05, 0.46), vec3(W - 0.2, fl + 1.3, 0.66), skin2, t, col, nn);
  }
  // The counter, its formica top, and stools in front.
  hitBox(ro, rd, vec3(x0, fl, 2.8), vec3(x1, fl + 0.98, 3.35), chrome * 0.9, t, col, nn);
  hitBox(ro, rd, vec3(x0, fl + 0.98, 2.72), vec3(x1, fl + 1.03, 3.38), vec3(0.85, 0.2, 0.2), t, col, nn);
  float ts = (2.45 - ro.z) / rd.z;
  float sx = (floor((ro.x + rd.x * ts) / 0.7) + 0.5) * 0.7;
  for (int i = -1; i <= 1; i++) {
    float cx = sx + float(i) * 0.7;
    hitBox(ro, rd, vec3(cx - 0.18, fl + 0.68, 2.28), vec3(cx + 0.18, fl + 0.76, 2.62), vinyl, t, col, nn);
    hitBox(ro, rd, vec3(cx - 0.03, fl, 2.42), vec3(cx + 0.03, fl + 0.68, 2.48), chrome, t, col, nn);
  }
  p = ro + rd * t;
  float shade = abs(nn.y) > 0.5 ? (nn.y > 0.0 ? 1.0 : 0.8) : abs(nn.x) > 0.5 ? 0.72 : 0.88;
  // Bright by day and lit all night, unless it burnt.
  float fall = mix(1.0, 0.55, clamp(p.z / depth, 0.0, 1.0));
  bool lit = hash(id + 7.0) >= uBurn;
  vec3 light = vec3(0.62, 0.61, 0.58) * uDay * fall + (lit ? vec3(1.0, 0.9, 0.76) * 0.75 * uNight : vec3(0.0));
  vec3 room = col * shade * light + (lit ? vec3(1.6, 1.45, 1.2) * glow * (0.4 + 0.6 * uNight) : vec3(0.0));
  return room * mix(1.0, 0.1, uBurn);
}

// A works floor seen through one of its windows: a tall shed of whitewashed
// brick over a green dado, a concrete floor with painted gangways, the roof
// trusses' ties, steel stanchions, machine tools in a row along the window
// side and bigger ones beyond, a bench under the sill, lamps hanging in
// enamel shades; it runs on to either side. Some shops work a night shift.
vec3 works(vec3 ro, vec3 rd, float id, float W) {
  float fl = -1.1, ce = fl + 4.9, depth = 9.0;
  float x0 = -14.0, x1 = W + 14.0;
  float tx = rd.x > 0.0 ? (x1 - ro.x) / rd.x : (x0 - ro.x) / rd.x;
  float ty = rd.y > 0.0 ? (ce - ro.y) / rd.y : (fl - ro.y) / rd.y;
  float tz = depth / rd.z;
  float t = min(tx, min(ty, tz));
  vec3 p = ro + rd * t;
  vec3 col, nn;
  float sky = 0.0;
  if (t == ty && rd.y < 0.0) {
    col = vec3(0.5, 0.49, 0.46) * (0.85 + 0.15 * hash(floor(p.x * 0.7) + floor(p.z * 0.7) * 13.0));
    if (abs(p.z - 1.55) < 0.05 || abs(p.z - 4.6) < 0.05) col = vec3(0.78, 0.66, 0.2);
    nn = vec3(0.0, 1.0, 0.0);
  } else if (t == ty) {
    // The underside of the sawtooth: dark sheeting, bright bands of north light.
    float f = fract((p.x + id * 1.3) / 3.6);
    sky = step(0.78, f);
    col = mix(vec3(0.3, 0.3, 0.3), vec3(0.95, 0.97, 1.0), sky);
    nn = vec3(0.0, -1.0, 0.0);
  } else {
    float y = p.y - fl;
    col = y < 1.4 ? vec3(0.26, 0.4, 0.32) : vec3(0.86, 0.84, 0.78);
    if (abs(y - 1.4) < 0.03) col = vec3(0.12);
    // Pilasters, and tall windows in the far wall.
    float u = t == tz ? p.x : p.z;
    if (fract(u / 3.6) < 0.12) col *= 0.82;
    if (t == tz && y > 2.3 && y < 4.4 && abs(fract(p.x / 3.6) - 0.56) < 0.25) col = vec3(0.62, 0.68, 0.72) * (0.8 + 0.2 * step(0.08, fract(y / 0.45)));
    nn = t == tz ? vec3(0.0, 0.0, -1.0) : vec3(1.0, 0.0, 0.0);
  }
  vec3 steel = vec3(0.16, 0.17, 0.18);
  // The trusses' ties across the shed, and a stanchion at each.
  for (int i = 0; i < 3; i++) {
    float z = 1.8 + float(i) * 3.0;
    hitBox(ro, rd, vec3(x0, ce - 0.25, z), vec3(x1, ce - 0.12, z + 0.12), steel, t, col, nn);
  }
  float tc = (4.2 - ro.z) / rd.z;
  float cx = (floor((ro.x + rd.x * tc) / 3.6) + 0.5) * 3.6;
  for (int i = -1; i <= 1; i++) hitBox(ro, rd, vec3(cx + float(i) * 3.6 - 0.1, fl, 4.1), vec3(cx + float(i) * 3.6 + 0.1, ce, 4.3), steel, t, col, nn);
  // The bench under the window.
  hitBox(ro, rd, vec3(-0.2, fl + 0.82, 0.05), vec3(W + 0.2, fl + 0.9, 0.75), vec3(0.42, 0.32, 0.22), t, col, nn);
  hitBox(ro, rd, vec3(-0.15, fl, 0.6), vec3(W + 0.15, fl + 0.82, 0.7), vec3(0.3, 0.24, 0.18), t, col, nn);
  if (hash(id + 23.0) < 0.6) hitBox(ro, rd, vec3(W * 0.3, fl + 0.9, 0.2), vec3(W * 0.3 + 0.35, fl + 1.15, 0.45), vec3(0.24, 0.36, 0.42), t, col, nn);
  // Lathes in a row, and presses and mills beyond the gangway.
  vec3 paint = vec3(0.34, 0.42, 0.38);
  float tl = (2.6 - ro.z) / rd.z;
  float lx = floor((ro.x + rd.x * tl) / 2.4);
  for (int i = -1; i <= 1; i++) {
    float k = lx + float(i);
    if (hash(k + id * 0.1) < 0.2) continue;
    float c0 = k * 2.4 + 0.3, len = 1.4 + 0.6 * hash(k + 3.0);
    hitBox(ro, rd, vec3(c0, fl + 0.55, 2.2), vec3(c0 + len, fl + 1.0, 2.9), paint, t, col, nn);
    hitBox(ro, rd, vec3(c0 + 0.1, fl, 2.35), vec3(c0 + 0.35, fl + 0.55, 2.75), paint * 0.8, t, col, nn);
    hitBox(ro, rd, vec3(c0 + len - 0.35, fl, 2.35), vec3(c0 + len - 0.1, fl + 0.55, 2.75), paint * 0.8, t, col, nn);
    hitBox(ro, rd, vec3(c0, fl + 1.0, 2.3), vec3(c0 + 0.45, fl + 1.4, 2.8), paint * 0.9, t, col, nn);
  }
  float tp = (5.6 - ro.z) / rd.z;
  float px = floor((ro.x + rd.x * tp) / 3.0);
  for (int i = -1; i <= 1; i++) {
    float k = px + float(i);
    if (hash(k * 1.7 + 9.0) < 0.3) continue;
    float c0 = k * 3.0 + 0.5, h = 1.6 + 0.9 * hash(k + 5.0);
    vec3 pc = hash(k + 11.0) < 0.5 ? paint : vec3(0.42, 0.44, 0.46);
    hitBox(ro, rd, vec3(c0, fl, 5.2), vec3(c0 + 1.3, fl + h, 6.4), pc, t, col, nn);
  }
  // Lamps in enamel shades over the gangway.
  float tm = (3.6 - ro.z) / rd.z;
  float mx = (floor((ro.x + rd.x * tm) / 3.6) + 0.5) * 3.6;
  float glow = 0.0;
  for (int i = -1; i <= 1; i++) {
    vec3 c = vec3(mx + float(i) * 3.6, ce - 1.6, 3.6);
    hitBox(ro, rd, c - vec3(0.25, 0.0, 0.25), c + vec3(0.25, 0.14, 0.25), vec3(0.18, 0.3, 0.24), t, col, nn);
    hitBox(ro, rd, c + vec3(-0.01, 0.14, -0.01), vec3(c.x + 0.01, ce, c.z + 0.01), steel, t, col, nn);
    vec3 w = ro + rd * max(dot(c - ro, rd), 0.0) - c;
    glow += smoothstep(0.34, 0.0, length(w)) * step(-0.05, -w.y);
  }
  p = ro + rd * t;
  float shade = abs(nn.y) > 0.5 ? (nn.y > 0.0 ? 1.0 : 0.75) : abs(nn.x) > 0.5 ? 0.72 : 0.88;
  float fall = mix(1.0, 0.6, clamp(p.z / depth, 0.0, 1.0));
  bool lit = hash(id + 5.0) < 0.5 && hash(id + 7.0) >= uBurn;
  vec3 lamp = vec3(1.0, 0.9, 0.72);
  vec3 light = vec3(0.5, 0.51, 0.52) * uDay * fall + (lit ? lamp * 0.6 * uNight : vec3(0.0));
  vec3 room = col * shade * light + sky * vec3(0.8, 0.85, 0.9) * uDay * 0.6;
  if (lit) room += lamp * 1.8 * glow * uNight;
  // Factory glass is never clean.
  room = mix(room, vec3(0.32, 0.33, 0.3) * (0.3 * uDay + 0.1), 0.18);
  return room * mix(1.0, 0.1, uBurn);
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
  if (uKind == 3) return diner(ro, rd, id, W);
  if (uKind == 4) return works(ro, rd, id, W);

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
    sh.uniforms.uKind = { value: ["home", "shop", "lobby", "diner", "works"].indexOf(kind) };
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
