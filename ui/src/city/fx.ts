// Particles (smoke, fire, dust, sparks) and falling debris.
import * as THREE from "three";
import { puff } from "./textures";

interface P {
  x: number; y: number; z: number;
  vx: number; vy: number; vz: number;
  life: number; max: number;
  size: number; grow: number;
  r: number; g: number; b: number; a: number;
  drag: number; lift: number;
}

const VERT = `
uniform float scale;
attribute float size;
attribute vec4 tint;
varying vec4 vTint;
void main() {
  vTint = tint;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = size * (scale / -mv.z);
  gl_Position = projectionMatrix * mv;
}`;
const FRAG = `
uniform sampler2D map;
varying vec4 vTint;
void main() {
  vec4 t = texture2D(map, gl_PointCoord);
  gl_FragColor = vec4(vTint.rgb, vTint.a * t.a);
  if (gl_FragColor.a < 0.01) discard;
}`;

export class Particles {
  readonly points: THREE.Points;
  private list: P[] = [];
  private pos: Float32Array;
  private size: Float32Array;
  private tint: Float32Array;

  /** Pixels per world unit at distance 1: viewport height / (2 tan(fov / 2)). */
  setScale(px: number) {
    (this.points.material as THREE.ShaderMaterial).uniforms.scale.value = px;
  }

  constructor(private max: number, additive: boolean) {
    const geo = new THREE.BufferGeometry();
    this.pos = new Float32Array(max * 3);
    this.size = new Float32Array(max);
    this.tint = new Float32Array(max * 4);
    geo.setAttribute("position", new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    geo.setAttribute("size", new THREE.BufferAttribute(this.size, 1).setUsage(THREE.DynamicDrawUsage));
    geo.setAttribute("tint", new THREE.BufferAttribute(this.tint, 4).setUsage(THREE.DynamicDrawUsage));
    const material = new THREE.ShaderMaterial({
      uniforms: { map: { value: puff() }, scale: { value: 900 } },
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
      depthWrite: false,
      blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
    this.points = new THREE.Points(geo, material);
    this.points.frustumCulled = false;
  }

  /** Particles alive. */
  get count() {
    return this.list.length;
  }

  emit(p: Partial<P> & { x: number; y: number; z: number }) {
    if (this.list.length >= this.max) this.list.shift();
    this.list.push({ vx: 0, vy: 0, vz: 0, life: 0, max: 2, size: 1, grow: 0, r: 1, g: 1, b: 1, a: 1, drag: 0, lift: 0, ...p });
  }

  update(dt: number, wind: number) {
    this.list = this.list.filter((p) => (p.life += dt) < p.max);
    const n = this.list.length;
    for (let i = 0; i < n; i++) {
      const p = this.list[i];
      p.vy += p.lift * dt;
      p.vx += wind * dt * 0.4;
      const k = Math.max(0, 1 - p.drag * dt);
      p.vx *= k; p.vy *= k; p.vz *= k;
      p.x += p.vx * dt; p.y += p.vy * dt; p.z += p.vz * dt;
      const t = p.life / p.max;
      this.pos.set([p.x, p.y, p.z], i * 3);
      this.size[i] = p.size * (1 + p.grow * t);
      // Fade in quickly, out slowly.
      this.tint.set([p.r, p.g, p.b, p.a * Math.min(1, t * 8) * (1 - t)], i * 4);
    }
    const geo = this.points.geometry;
    geo.setDrawRange(0, n);
    for (const a of ["position", "size", "tint"]) (geo.attributes[a] as THREE.BufferAttribute).needsUpdate = true;
  }
}

export class Fx {
  readonly group = new THREE.Group();
  /** 0 by day to 1 at night; dust and smoke darken with it. */
  night = 0;
  readonly smoke = new Particles(2500, false);
  readonly glow = new Particles(2000, true);
  private debris: { mesh: THREE.Mesh; v: THREE.Vector3; spin: THREE.Vector3; life: number }[] = [];
  private debrisGeo = new THREE.BoxGeometry(1, 1, 1);

  /** Anything still flying (the scene keeps drawing frames while it is). */
  get active() {
    return this.smoke.count + this.glow.count + this.debris.length > 0;
  }

  /** Debris tumbling: the (otherwise static) shadow map is redrawn while it is. */
  get falling() {
    return this.debris.length > 0;
  }

  constructor() {
    this.group.add(this.smoke.points, this.glow.points);
  }

  smokeAt(v: THREE.Vector3, heavy: boolean, night: number) {
    const c = heavy ? 0.16 : 0.55 - night * 0.3;
    this.smoke.emit({
      x: v.x + (Math.random() - 0.5), y: v.y, z: v.z + (Math.random() - 0.5),
      vx: (Math.random() - 0.5) * 0.6, vy: 2 + Math.random() * 1.5, vz: (Math.random() - 0.5) * 0.6,
      max: 5 + Math.random() * 4, size: heavy ? 2.6 : 0.9, grow: heavy ? 3.5 : 2.5,
      r: c, g: c, b: c * 1.05, a: heavy ? 0.75 : 0.3, drag: 0.15,
    });
  }

  fireAt(v: THREE.Vector3) {
    this.glow.emit({
      x: v.x + (Math.random() - 0.5) * 2, y: v.y, z: v.z + (Math.random() - 0.5) * 2,
      vy: 2 + Math.random() * 3, max: 0.6 + Math.random() * 0.6, size: 1.4 + Math.random(), grow: -0.6,
      r: 1, g: 0.35 + Math.random() * 0.3, b: 0.08, a: 0.9, lift: 1,
    });
  }

  /** A ground-level dust cloud, e.g. under a collapse or a new building. */
  dust(v: THREE.Vector3, radius: number, amount: number, color = 0.62) {
    color *= 1 - this.night * 0.7;
    for (let i = 0; i < amount; i++) {
      const a = Math.random() * Math.PI * 2;
      const s = 2 + Math.random() * 6;
      this.smoke.emit({
        x: v.x + Math.cos(a) * radius * 0.4, y: v.y + Math.random() * 2, z: v.z + Math.sin(a) * radius * 0.4,
        vx: Math.cos(a) * s, vy: Math.random() * 2, vz: Math.sin(a) * s,
        max: 3 + Math.random() * 4, size: 4 + Math.random() * 5, grow: 3,
        r: color, g: color * 0.95, b: color * 0.88, a: 0.75, drag: 1.1, lift: 0.6,
      });
    }
  }

  /** Golden sparks and a rising glow, for a completed building. */
  celebrate(v: THREE.Vector3, height: number) {
    for (let i = 0; i < 160; i++) {
      const a = Math.random() * Math.PI * 2;
      const s = 3 + Math.random() * 7;
      this.glow.emit({
        x: v.x, y: v.y + height + 1, z: v.z,
        vx: Math.cos(a) * s, vy: 6 + Math.random() * 10, vz: Math.sin(a) * s,
        max: 1.6 + Math.random() * 1.4, size: 0.7 + Math.random() * 0.6,
        r: 1, g: 0.8 + Math.random() * 0.2, b: 0.4, a: 1, lift: -9, drag: 0.6,
      });
    }
    for (let i = 0; i < 40; i++) {
      this.glow.emit({
        x: v.x + (Math.random() - 0.5) * 8, y: v.y + Math.random() * height, z: v.z + (Math.random() - 0.5) * 8,
        vy: 2 + Math.random() * 2, max: 2 + Math.random(), size: 1.2, r: 1, g: 0.9, b: 0.6, a: 0.8,
      });
    }
  }

  /** Building chunks that fall, tumble and settle. */
  collapse(v: THREE.Vector3, w: number, h: number, color: number, burning: boolean) {
    const mats = [
      new THREE.MeshStandardMaterial({ color, roughness: 0.9 }),
      new THREE.MeshStandardMaterial({ color: 0x77726c, roughness: 1 }),
      new THREE.MeshStandardMaterial({ color: 0x2a2624, roughness: 1 }),
    ];
    const n = Math.min(140, 30 + Math.round(h * 1.5));
    for (let i = 0; i < n; i++) {
      const mesh = new THREE.Mesh(this.debrisGeo, mats[i % 3]);
      const s = 0.6 + Math.random() * Math.min(3, w * 0.25);
      mesh.scale.set(s, s * (0.4 + Math.random() * 0.6), s * (0.5 + Math.random()));
      mesh.position.set(v.x + (Math.random() - 0.5) * w, v.y + h * (0.3 + Math.random() * 0.7), v.z + (Math.random() - 0.5) * w);
      mesh.castShadow = true;
      const out = new THREE.Vector3(mesh.position.x - v.x, 0, mesh.position.z - v.z).normalize().multiplyScalar(2 + Math.random() * 5);
      this.debris.push({ mesh, v: new THREE.Vector3(out.x, Math.random() * 3, out.z), spin: new THREE.Vector3(Math.random() * 4, Math.random() * 4, Math.random() * 4), life: 0 });
      this.group.add(mesh);
    }
    this.dust(v, w * 1.5, 140);
    if (burning) for (let i = 0; i < 80; i++) this.fireAt(new THREE.Vector3(v.x, v.y + Math.random() * h * 0.5, v.z));
  }

  update(dt: number, wind: number) {
    this.smoke.update(dt, wind);
    this.glow.update(dt, wind);
    this.debris = this.debris.filter((d) => {
      d.life += dt;
      d.v.y -= 22 * dt;
      d.mesh.position.addScaledVector(d.v, dt);
      const floor = d.mesh.scale.y / 2;
      if (d.mesh.position.y < floor) {
        d.mesh.position.y = floor;
        d.v.multiplyScalar(0.3);
        d.v.y = Math.abs(d.v.y) * 0.2;
        d.spin.multiplyScalar(0.5);
      }
      d.mesh.rotation.x += d.spin.x * dt;
      d.mesh.rotation.z += d.spin.z * dt;
      // Sink into the ground once the rubble pile is there.
      if (d.life > 3.5) d.mesh.position.y -= dt * 1.5;
      if (d.life > 5) {
        this.group.remove(d.mesh);
        return false;
      }
      return true;
    });
  }
}
