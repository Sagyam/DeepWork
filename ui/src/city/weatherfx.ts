// Drawing the weather (weather.ts says what it is):
//  - surfaces: snow lying on whatever faces up, darker wet surfaces and
//    puddles that mirror the sky and ring with rain (weatherize(), patched
//    into every lit material by scene.ts's prepare());
//  - precipitation: rain streaks and snowflakes in a box ahead of the
//    camera, moved and sized in the vertex shader (one draw each, no CPU
//    work per drop);
//  - clouds: a dome in the sky scene, drawn into the background cube map
//    with the sky;
//  - lightning: flashes and the odd bolt on the horizon in a storm.
import * as THREE from "three";
import { rng } from "./plan";

/** Shared by every weatherized material; scene.ts sets them. */
export const weatherUniforms = {
  /** Snow lying, 0-1. */
  uWxSnow: { value: 0 },
  /** Wetness, 0-1. */
  uWxWet: { value: 0 },
  /** Rain falling on the puddles, 0-1. */
  uWxRain: { value: 0 },
  uWxTime: { value: 0 },
  /** The sky cube, for puddles to mirror. */
  uWxSky: { value: null as THREE.Texture | null },
  /** How bright the mirrored sky is (dim at night). */
  uWxSkyI: { value: 1 },
};

const NOISE = /* glsl */ `
float wxHash(vec2 p) { vec3 q = fract(vec3(p.xyx) * 0.1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
float wxNoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(wxHash(i), wxHash(i + vec2(1.0, 0.0)), f.x), mix(wxHash(i + vec2(0.0, 1.0)), wxHash(i + vec2(1.0)), f.x), f.y);
}`;

const SURFACE = /* glsl */ `
{
  vec3 wxN = normalize(vWxN);
  float wxUp = wxN.y;
  vec3 wxUpV = normalize((viewMatrix * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
  float wxBig = wxNoise(vWxP.xz * 0.21);
  float wxFine = wxNoise(vWxP.xz * 2.7 + vWxP.y * 0.7);
  // Snow: settles on what faces up; thin first in the low spots of the
  // noise, then everywhere. Flattens the texture's relief under it.
  float wxS = uWxSnow * uWxSnowK;
  wxSnowAmt = wxS * smoothstep(0.45, 0.75, wxUp + (wxBig - 0.5) * 0.35 + (wxFine - 0.5) * 0.2 + (wxS - 1.0) * 0.45);
  diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.86, 0.89, 0.93) * (0.92 + 0.08 * wxFine), wxSnowAmt);
  roughnessFactor = mix(roughnessFactor, 0.7, wxSnowAmt);
  metalnessFactor = mix(metalnessFactor, 0.0, wxSnowAmt);
  normal = normalize(mix(normal, nonPerturbedNormal, wxSnowAmt * 0.8));
  // Wet: porous things darken, everything gets glossier, and flat ground
  // collects puddles in the low spots.
  float wxW = uWxWet * uWxWetK * (1.0 - wxSnowAmt);
  diffuseColor.rgb *= mix(1.0, 0.55 + 0.45 * metalnessFactor, wxW * (0.55 + 0.45 * max(wxUp, 0.0)));
  roughnessFactor = mix(roughnessFactor, roughnessFactor * 0.35, wxW * max(wxUp, 0.3));
  wxPuddle = wxW * smoothstep(0.9, 0.98, wxUp) * smoothstep(0.52, 0.68, wxBig + (wxFine - 0.5) * 0.12);
  roughnessFactor = mix(roughnessFactor, 0.03, wxPuddle);
  diffuseColor.rgb *= 1.0 - 0.65 * wxPuddle;
  // Rings where drops land in the puddles.
  vec2 wxRp = vWxP.xz * 1.3;
  vec2 wxCell = floor(wxRp);
  vec2 wxRing = vec2(0.0);
  for (int k = 0; k < 2; k++) {
    vec2 c = wxCell + vec2(float(k) * 0.5);
    float ph = fract(uWxTime * 0.8 + wxHash(c * 1.7 + float(k)));
    vec2 o = fract(wxRp - float(k) * 0.5) - 0.5 - (vec2(wxHash(c), wxHash(c + 3.1)) - 0.5) * 0.5;
    float d = length(o);
    float r = ph * 0.45;
    float w = sin((d - r) * 60.0) * smoothstep(0.08, 0.0, abs(d - r)) * (1.0 - ph);
    wxRing += (d > 0.001 ? o / d : vec2(0.0)) * w;
  }
  vec3 wxFlat = normalize(wxUpV + (viewMatrix * vec4(wxRing.x, 0.0, wxRing.y, 0.0)).xyz * 0.25 * uWxRain);
  normal = normalize(mix(normal, wxFlat, wxPuddle));
}
`;

const MIRROR = /* glsl */ `
if (wxPuddle > 0.001) {
  vec3 wxV = normalize(vWxP - cameraPosition);
  vec3 wxR = reflect(wxV, vec3(0.0, 1.0, 0.0));
  wxR.y = max(wxR.y, 0.02);
  float wxF = 0.04 + 0.96 * pow(1.0 - max(-wxV.y, 0.0), 5.0);
  reflectedLight.indirectSpecular += textureCube(uWxSky, wxR).rgb * uWxSkyI * wxF * wxPuddle;
}
`;

/**
 * Snow, wet and puddles on a lit material: chained after its own patch, so
 * it works with the grime, ground and foliage shaders. `userData.snow`
 * scales the snow it holds (roads are cleared, leaves shed some);
 * `userData.noWeather` leaves it alone (water, people).
 */
export function weatherize(m: THREE.Material) {
  const s = m as THREE.MeshStandardMaterial;
  if (!s.isMeshStandardMaterial || m.userData.noWeather || m.userData.water || m.userData.weather || m.transparent) return;
  m.userData.weather = true;
  const prev = m.onBeforeCompile;
  const key = m.customProgramCacheKey();
  const snowK = { value: m.userData.snow ?? 1 };
  // Cut-out leaves and tree cards glitter when glossy: they stay dry.
  const wetK = { value: m.alphaTest > 0 ? 0 : 1 };
  m.onBeforeCompile = (sh, r) => {
    prev.call(m, sh, r);
    if (!sh.fragmentShader.includes("#include <normal_fragment_maps>")) return;
    Object.assign(sh.uniforms, weatherUniforms, { uWxSnowK: snowK, uWxWetK: wetK });
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vWxP;\nvarying vec3 vWxN;")
      .replace(
        "#include <worldpos_vertex>",
        "#include <worldpos_vertex>\n{ mat4 wxM = modelMatrix;\n#ifdef USE_INSTANCING\nwxM = modelMatrix * instanceMatrix;\n#endif\nvWxP = (wxM * vec4(transformed, 1.0)).xyz;\nvWxN = mat3(wxM) * objectNormal; }",
      );
    sh.fragmentShader = sh.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>\nuniform float uWxSnow;\nuniform float uWxSnowK;\nuniform float uWxWetK;\nuniform float uWxWet;\nuniform float uWxRain;\nuniform float uWxTime;\nuniform samplerCube uWxSky;\nuniform float uWxSkyI;\nvarying vec3 vWxP;\nvarying vec3 vWxN;\n${NOISE}`,
      )
      .replace("#include <normal_fragment_maps>", `#include <normal_fragment_maps>\nfloat wxSnowAmt = 0.0;\nfloat wxPuddle = 0.0;\nif (uWxSnow + uWxWet > 0.0) ${SURFACE}`)
      .replace("#include <lights_fragment_end>", `#include <lights_fragment_end>\n${MIRROR}`);
  };
  m.customProgramCacheKey = () => `${key}:wx`;
  m.needsUpdate = true;
}

// ---- precipitation ------------------------------------------------------------

const PRECIP_VERT = /* glsl */ `
attribute vec2 corner;
attribute vec4 aSeed;
uniform float uTime;
uniform vec3 uCenter;
uniform vec3 uBox;
uniform vec3 uVel;
uniform float uLen;
uniform vec2 uRes;
uniform float uFocal;
uniform float uSize;
uniform float uSnowy;
uniform float uAlpha;
varying float vA;
varying vec2 vC;
void main() {
  float speed = 0.8 + 0.4 * aSeed.w;
  vec3 v = uVel * speed;
  vec3 p = aSeed.xyz * uBox + v * uTime;
  // Snow drifts and tumbles on its own little eddy.
  float ph = aSeed.w * 40.0;
  p.xz += uSnowy * vec2(sin(uTime * 0.9 + ph), cos(uTime * 0.7 + ph * 1.3)) * 0.8;
  vec3 lo = uCenter - uBox * 0.5;
  p = lo + mod(p - lo, uBox);
  vec4 a = projectionMatrix * viewMatrix * vec4(p, 1.0);
  vC = vec2(corner.x, corner.y * 2.0 - 1.0);
  if (a.w < 1.0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); vA = 0.0; return; }
  float px = uSize * uFocal / a.w;
  float fade = smoothstep(1.0, 4.0, a.w) * (1.0 - smoothstep(uBox.x * 0.35, uBox.x * 0.6, distance(p, uCenter)));
  if (uSnowy > 0.5) {
    // Flakes right by the lens would be blobs: capped, and faded out close in.
    float s = clamp(px, 1.8, 4.5);
    gl_Position = a + vec4(vC * s / uRes * a.w, 0.0, 0.0);
    vA = uAlpha * fade * smoothstep(3.0, 12.0, a.w) * min(1.0, 0.45 + px / 2.0);
  } else {
    vec4 b = projectionMatrix * viewMatrix * vec4(p - v * uLen, 1.0);
    vec2 d = (a.xy / a.w - b.xy / max(b.w, 1.0)) * uRes;
    float l = length(d);
    vec2 dir = l > 1e-3 ? d / l : vec2(0.0, 1.0);
    float wpx = max(px, 0.9);
    vec4 q = mix(b, a, corner.y);
    q.xy += vec2(-dir.y, dir.x) * corner.x * wpx / uRes * q.w;
    gl_Position = q;
    // Drops are thinner than a pixel past a few metres: they read by their sheen.
    vA = uAlpha * fade * min(1.0, 0.4 + px);
  }
}`;

const PRECIP_FRAG = /* glsl */ `
uniform vec3 uColor;
uniform float uSnowy;
varying float vA;
varying vec2 vC;
void main() {
  float a;
  if (uSnowy > 0.5) a = smoothstep(1.0, 0.2, length(vC));
  else a = (1.0 - vC.x * vC.x) * (0.25 + 0.75 * (vC.y * 0.5 + 0.5));
  gl_FragColor = vec4(uColor, a * vA);
  if (gl_FragColor.a < 0.004) discard;
}`;

interface Fall {
  mesh: THREE.Mesh;
  mat: THREE.ShaderMaterial;
  max: number;
}

function fall(max: number, snowy: boolean): Fall {
  const base = new THREE.InstancedBufferGeometry();
  base.setAttribute("corner", new THREE.Float32BufferAttribute([-1, 0, 1, 0, -1, 1, 1, 1], 2));
  // three needs a position attribute to count vertices.
  base.setAttribute("position", new THREE.Float32BufferAttribute(new Array(12).fill(0), 3));
  base.setIndex([0, 1, 2, 2, 1, 3]);
  const r = rng(snowy ? 23 : 17);
  const seed = new Float32Array(max * 4);
  for (let i = 0; i < seed.length; i++) seed[i] = r();
  base.setAttribute("aSeed", new THREE.InstancedBufferAttribute(seed, 4));
  base.instanceCount = 0;
  const mat = new THREE.ShaderMaterial({
    vertexShader: PRECIP_VERT,
    fragmentShader: PRECIP_FRAG,
    // A streak's winding follows its direction on screen.
    side: THREE.DoubleSide,
    transparent: true,
    depthWrite: false,
    uniforms: {
      uTime: { value: 0 },
      uCenter: { value: new THREE.Vector3() },
      uBox: { value: new THREE.Vector3() },
      uVel: { value: new THREE.Vector3() },
      uLen: { value: 0.1 },
      uRes: { value: new THREE.Vector2(1, 1) },
      uFocal: { value: 1000 },
      uSize: { value: snowy ? 0.12 : 0.006 },
      uSnowy: { value: snowy ? 1 : 0 },
      uAlpha: { value: snowy ? 0.95 : 0.45 },
      uColor: { value: new THREE.Color() },
    },
  });
  const mesh = new THREE.Mesh(base, mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = 5;
  mesh.visible = false;
  mesh.userData.noShadow = true;
  return { mesh, mat, max };
}

/** Rain and snow in a box ahead of the camera. */
export class Precip {
  group = new THREE.Group();
  private rain = fall(30000, false);
  private snow = fall(24000, true);
  private rainAmt = 0;
  private snowAmt = 0;
  private wind = new THREE.Vector2();

  constructor() {
    this.group.add(this.rain.mesh, this.snow.mesh);
  }

  get active() {
    return this.rainAmt > 0 || this.snowAmt > 0;
  }

  /** Sets how much falls and how the wind takes it; `light` colours the drops. */
  set(rain: number, snow: number, wind: number, light: THREE.Color) {
    this.rainAmt = rain;
    this.snowAmt = snow;
    // The wind blows from the west-south-west, more or less.
    this.wind.set(0.9, 0.45).multiplyScalar(wind);
    const r = this.rain;
    r.mesh.visible = rain > 0;
    (r.mesh.geometry as THREE.InstancedBufferGeometry).instanceCount = Math.round(r.max * Math.min(1, 0.15 + rain));
    r.mat.uniforms.uVel.value.set(this.wind.x * 6, -11, this.wind.y * 6);
    r.mat.uniforms.uColor.value.copy(light).multiplyScalar(2.4);
    r.mat.uniforms.uAlpha.value = 0.35 + 0.3 * rain;
    const s = this.snow;
    s.mesh.visible = snow > 0;
    (s.mesh.geometry as THREE.InstancedBufferGeometry).instanceCount = Math.round(s.max * Math.min(1, 0.2 + snow));
    s.mat.uniforms.uVel.value.set(this.wind.x * 3, -1.3, this.wind.y * 3);
    s.mat.uniforms.uColor.value.copy(light).multiplyScalar(2.6);
  }

  /** Follows the camera: the box sits between the eye and what it looks at. */
  update(t: number, camera: THREE.PerspectiveCamera, target: THREE.Vector3, res: THREE.Vector2) {
    if (!this.active) return;
    const dist = camera.position.distanceTo(target);
    const fwd = target.clone().sub(camera.position).normalize();
    const focal = res.y / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    for (const [f, reach] of [
      [this.rain, Math.min(dist * 0.4, 100)],
      [this.snow, Math.min(dist * 0.3, 70)],
    ] as const) {
      if (!f.mesh.visible) continue;
      const u = f.mat.uniforms;
      u.uTime.value = t;
      u.uCenter.value.copy(camera.position).addScaledVector(fwd, reach);
      const side = reach * 2.2;
      u.uBox.value.set(side, Math.max(60, side * 0.8), side);
      u.uRes.value.set(res.x / 2, res.y / 2);
      u.uFocal.value = focal;
    }
  }
}

// ---- clouds -------------------------------------------------------------------

const CLOUD_VERT = /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const CLOUD_FRAG = /* glsl */ `
uniform float uCover;
uniform float uDark;
uniform float uFog;
uniform float uFlash;
uniform vec2 uDrift;
uniform vec3 uSun;
uniform vec3 uLit;
uniform vec3 uShade;
uniform vec3 uHaze;
varying vec3 vDir;
${NOISE}
float fbm(vec2 p) {
  float s = 0.0, a = 0.5;
  mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 6; i++) { s += a * wxNoise(p); p = m * p; a *= 0.5; }
  return s;
}
void main() {
  vec3 d = normalize(vDir);
  float h = max(d.y, 0.0);
  // A cloud deck: the view ray meets a plane overhead, so the clouds crowd
  // and flatten towards the horizon.
  vec2 p = d.xz / (h + 0.07) * 0.55 + uDrift;
  float n = fbm(p);
  float t = mix(0.72, 0.18, uCover);
  float dens = smoothstep(t, t + 0.22, n);
  dens = max(dens, smoothstep(0.75, 1.0, uCover) * 0.9 + 0.1 * dens);
  // Lit on the sun's side: less cloud a step towards the sun means light gets in.
  vec2 toSun = normalize(uSun.xz + 1e-4) * 0.12;
  float n2 = fbm(p + toSun);
  float lit = clamp(0.55 + (n - n2) * 4.0, 0.0, 1.0);
  float thick = smoothstep(t, t + 0.6, n);
  float shade = clamp(mix(0.25 + thick * 0.6 - lit * 0.4, 0.5 + 0.5 * thick - 0.25 * lit, uDark), 0.0, 1.0);
  vec3 col = mix(uLit, uShade, shade);
  // Silver edges round the sun.
  float sunGlow = pow(max(dot(d, normalize(uSun)), 0.0), 10.0);
  col += uLit * sunGlow * (1.0 - thick) * 0.9 * (1.0 - uDark);
  col += vec3(0.9, 0.92, 1.1) * uFlash * (0.4 + 0.6 * thick);
  // Far cloud melts into the haze at the horizon.
  float far = 1.0 - smoothstep(0.0, 0.28, h);
  // In fog the sky is the fog.
  col = mix(col, uHaze, clamp(far * 0.7 + uFog, 0.0, 1.0));
  float a = dens * mix(smoothstep(0.0, 0.1, d.y), 1.0, smoothstep(0.8, 1.0, uCover));
  gl_FragColor = vec4(col, a);
}`;

export const cloudUniforms = {
  uCover: { value: 0 },
  uDark: { value: 0 },
  uFog: { value: 0 },
  uFlash: { value: 0 },
  uDrift: { value: new THREE.Vector2() },
  uSun: { value: new THREE.Vector3(0, 1, 0) },
  uLit: { value: new THREE.Color() },
  uShade: { value: new THREE.Color() },
  uHaze: { value: new THREE.Color() },
};

const cloudMat = new THREE.ShaderMaterial({
  vertexShader: CLOUD_VERT,
  fragmentShader: CLOUD_FRAG,
  uniforms: cloudUniforms,
  side: THREE.BackSide,
  transparent: true,
  depthWrite: false,
  depthTest: false,
});

/** The cloud dome, for a sky scene (drawn after its Sky). */
export function cloudDome(radius: number): THREE.Mesh {
  const m = new THREE.Mesh(new THREE.SphereGeometry(radius, 48, 24), cloudMat);
  m.renderOrder = 1;
  m.frustumCulled = false;
  return m;
}

// ---- lightning ----------------------------------------------------------------

/** Flashes in a storm, now and then a bolt on the horizon. */
export class Lightning {
  group = new THREE.Group();
  /** The flash's brightness now, 0-1. */
  flash = 0;
  private next = 4;
  private pulses: { at: number; k: number }[] = [];
  private bolt: THREE.Mesh | null = null;
  private boltT = 0;
  private r = rng(71);
  private mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(0.85, 0.88, 1).multiplyScalar(12), fog: false, side: THREE.DoubleSide, transparent: true, depthWrite: false });

  /** Steps the storm; returns whether a flash is lighting the sky. */
  update(dt: number, on: boolean, camera: THREE.Camera, target: THREE.Vector3): boolean {
    if (!on) {
      this.flash = 0;
      this.pulses = [];
      this.clearBolt();
      return false;
    }
    this.next -= dt;
    if (this.next <= 0) {
      this.next = 5 + this.r() * 12;
      const n = 1 + Math.floor(this.r() * 3);
      for (let i = 0; i < n; i++) this.pulses.push({ at: i * (0.08 + this.r() * 0.12), k: 0.6 + this.r() * 0.4 });
      if (this.r() < 0.6) this.strike(camera, target);
    }
    let f = 0;
    for (const p of this.pulses) {
      p.at -= dt;
      if (p.at <= 0) f = Math.max(f, p.k * Math.exp(p.at * 18));
    }
    this.pulses = this.pulses.filter((p) => p.at > -0.4);
    this.flash = f;
    if (this.bolt) {
      this.boltT -= dt;
      this.mat.opacity = Math.max(0, Math.min(1, f * 1.5));
      if (this.boltT <= 0) this.clearBolt();
    }
    return f > 0.01;
  }

  private clearBolt() {
    if (!this.bolt) return;
    this.group.remove(this.bolt);
    this.bolt.geometry.dispose();
    this.bolt = null;
  }

  /** A jagged ribbon from the cloud base to the ground, out beyond the town. */
  private strike(camera: THREE.Camera, target: THREE.Vector3) {
    this.clearBolt();
    const r = this.r;
    const fwd = target.clone().sub(camera.position).setY(0).normalize();
    const side = new THREE.Vector3(-fwd.z, 0, fwd.x);
    const base = target.clone().addScaledVector(fwd, 700 + r() * 900).addScaledVector(side, (r() - 0.5) * 1400);
    const top = 420 + r() * 120;
    const pts: THREE.Vector3[] = [];
    const walk = (from: THREE.Vector3, h: number, steps: number, out: THREE.Vector3[]) => {
      let p = from.clone();
      out.push(p.clone());
      for (let i = 0; i < steps; i++) {
        p = p.clone().add(new THREE.Vector3((r() - 0.5) * 40, -h / steps, (r() - 0.5) * 40));
        out.push(p);
      }
    };
    walk(new THREE.Vector3(base.x, top, base.z), top, 18, pts);
    const branches: THREE.Vector3[][] = [];
    for (let b = 0; b < 3; b++) {
      const from = pts[2 + Math.floor(r() * 8)];
      const br: THREE.Vector3[] = [];
      walk(from, 60 + r() * 100, 6, br);
      branches.push(br);
    }
    const pos: number[] = [];
    const ribbon = (line: THREE.Vector3[], w: number) => {
      for (let i = 0; i < line.length - 1; i++) {
        const a = line[i];
        const b = line[i + 1];
        const s = side.clone().multiplyScalar(w);
        pos.push(a.x - s.x, a.y, a.z - s.z, a.x + s.x, a.y, a.z + s.z, b.x - s.x, b.y, b.z - s.z);
        pos.push(b.x - s.x, b.y, b.z - s.z, a.x + s.x, a.y, a.z + s.z, b.x + s.x, b.y, b.z + s.z);
      }
    };
    ribbon(pts, 1.6);
    for (const br of branches) ribbon(br, 0.8);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    this.bolt = new THREE.Mesh(g, this.mat);
    this.bolt.frustumCulled = false;
    this.bolt.userData.noShadow = true;
    this.boltT = 0.5;
    this.group.add(this.bolt);
  }
}
