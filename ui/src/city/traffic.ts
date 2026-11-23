// City theme: street life. Cars, taxis, vans, lorries and buses make trips
// on the lane graph (roads.ts): in from the open road over the hills and
// the bridge, into the lots and out again, bus stop to bus stop, stopping
// at red. Pedestrians walk the pavements and cross on the walk phase
// (walks.ts), swinging their arms and legs. Both grow with the tier, so a
// metropolis is busy and a hamlet sleepy. Every part of a model is one
// InstancedMesh, moved every frame; headlights, tail lights and signs
// follow the night.
import * as THREE from "three";
import { lot, onStreets, rng, type CityPlan } from "./plan";
import { Flow, lanes, populate, spotAt, type Car, type Spot, type Vehicle } from "./roads";
import { KERB } from "./models";
import { CAR_PAINTS, realMat, realPiece } from "./real";
import { busStop } from "./street";
import { ROAD_Z, type Land } from "./terrain";
import { Crowd, type CarShape } from "./walks";

const BUS_PAINT = [0xc0392b, 0x2e6fb5, 0x2a9a5a];
const SHIRTS = [0xc0392b, 0x2e6fb5, 0x2a9a5a, 0xe8b020, 0xf0ece4, 0x6a4a8a, 0xe07a30, 0x30343a, 0x8ab0d0, 0xd06a8a];
const PANTS = [0x2a3040, 0x3a3a3e, 0x4a3a2a, 0x1e2a4a, 0x6a6458, 0x202020];
const SKIN = [0xf1c8a8, 0xd9a47e, 0xb07850, 0x8a5634, 0x5e3a22];
const HAIR = [0x1a1410, 0x3a2414, 0x6a4424, 0xb08a50, 0x8a8a88];

interface Look {
  color: number;
  rough?: number;
}

/** The figure's roles; colours come per person from the palettes above. */
const LOOKS: Record<string, Look> = {
  skin: { color: 0xffffff, rough: 0.8 },
  shirt: { color: 0xffffff, rough: 0.9 },
  pants: { color: 0xffffff, rough: 0.9 },
  hair: { color: 0xffffff, rough: 0.9 },
};

/** Roles whose colour varies per instance, and the palette to pick from. */
type Paint = Partial<Record<string, number[]>>;

/** One model drawn many times: an InstancedMesh per material role. */
class Fleet {
  meshes: THREE.InstancedMesh[] = [];
  private m = new THREE.Matrix4();
  private q = new THREE.Quaternion();
  private e = new THREE.Euler(0, 0, 0, "YXZ");
  private p = new THREE.Vector3();
  private s = new THREE.Vector3();

  constructor(parts: { role: string; geo: THREE.BufferGeometry }[], count: number, paint: Paint, mats: (role: string) => THREE.Material, r: () => number) {
    for (const { role, geo } of parts) {
      const mesh = new THREE.InstancedMesh(geo, mats(role), Math.max(1, count));
      mesh.count = count;
      // The shadow map is drawn once, not every frame (scene.ts): moving
      // vehicles cast a blob on the road instead (see blob()).
      mesh.castShadow = false;
      mesh.receiveShadow = role !== "blob";
      mesh.frustumCulled = false;
      const palette = paint[role];
      if (palette) {
        const c = new THREE.Color();
        for (let i = 0; i < count; i++) mesh.setColorAt(i, c.setHex(palette[Math.floor(r() * palette.length)]));
      }
      this.meshes.push(mesh);
    }
  }

  /** `pitch`: nose up, radians; `scale` 0 hides it. */
  set(i: number, x: number, y: number, z: number, heading: number, pitch = 0, scale = 1) {
    this.q.setFromEuler(this.e.set(-pitch, heading, 0));
    this.m.compose(this.p.set(x, y, z), this.q, this.s.setScalar(scale));
    for (const mesh of this.meshes) mesh.setMatrixAt(i, this.m);
  }

  flush() {
    for (const mesh of this.meshes) mesh.instanceMatrix.needsUpdate = true;
  }
}

/** The vehicles in traffic (pieces of cars.glb). */
const VEHICLES = ["hatch", "sedan", "estate", "suv", "coupe", "taxi", "pickup", "van", "truck", "bus"];

interface Driver {
  fleet: Fleet;
  slot: number;
  car: Car;
  wid: number;
}

/** Vehicles living in town per block, and coming by on the open road, by tier. */
const CARS = [1, 2, 3, 4];
const THROUGH = [4, 7, 10, 14];
/** People per block, by tier. */
const PEOPLE = [2, 4, 7, 11];
/** How far past the town the open road's traffic is driven, m (the bridge is some 250 m out). */
const REACH = 750;
/** The road's height over the land, and the bridge deck's. */
const TYRES = 0.05;
const DECK = 0.07;
/** `?people=0` leaves the pedestrians out. */
const NO_PEOPLE = new URLSearchParams(globalThis.location?.search ?? "").get("people") === "0";

export class Traffic {
  group = new THREE.Group();
  private drivers: Driver[] = [];
  private flow: Flow | null = null;
  private crowd: Crowd | null = null;
  private people: Fleet | null = null;
  private walk: THREE.InstancedBufferAttribute | null = null;
  private ground: Land | null = null;
  private plan: CityPlan | null = null;
  private t = 0;
  private fleets: Fleet[] = [];
  private mats = new Map<string, THREE.MeshStandardMaterial>();
  /** Realistic vehicles' lamps, which follow the night too. */
  private lamps = new Set<THREE.MeshStandardMaterial>();

  private mat = (role: string) => {
    let m = this.mats.get(role);
    if (!m) {
      const l = LOOKS[role] ?? { color: 0xff00ff };
      m = new THREE.MeshStandardMaterial({ color: l.color, roughness: l.rough ?? 0.6, vertexColors: true });
      striding(m);
      this.mats.set(role, m);
    }
    return m;
  };

  /** Rebuild for a new city plan (when blocks or the tier change); `ground` puts the open road's traffic on the hills. */
  build(p: CityPlan, ground?: Land) {
    for (const f of this.fleets) for (const m of f.meshes) this.group.remove(m);
    this.fleets = [];
    this.drivers = [];
    this.plan = p;
    this.ground = ground ?? null;
    const r = rng(0xca75 + p.blocks.length * 7 + p.tier);
    const tier = Math.min(3, Math.max(0, p.tier));

    const all = lanes(p.blocks, { z: ROAD_Z, reach: REACH });
    // Trips end in front of a building's lot, or at a bus shelter.
    const spots: Spot[] = [];
    for (const b of p.buildings) {
      const l = lot(b.index);
      // The drive is to one side of the lot, on the block's edge.
      const s = spotAt(all, l.x + 5, l.z + Math.cos(l.rot) * 8, "lot");
      if (s) spots.push(s);
    }
    for (const b of p.blocks) {
      const at = busStop(b, tier);
      const s = at && spotAt(all, at.x, at.z, "stop", 12);
      if (s) spots.push(s);
    }

    // Decide every vehicle first so each model's fleet is sized once.
    const pickModel = (k: number) =>
      tier >= 2 && k < 0.18 ? "taxi"
      : k < 0.26 ? "van"
      : tier >= 1 && k < 0.3 ? "truck"
      : k < 0.48 ? "hatch"
      : k < 0.64 ? "sedan"
      : k < 0.78 ? "suv"
      : k < 0.88 ? "estate"
      : k < 0.94 ? "pickup"
      : "coupe";
    const local: string[] = [];
    p.blocks.forEach((_, b) => {
      const n = CARS[tier] + (tier >= 2 && r() < 0.5 ? 1 : 0);
      for (let i = 0; i < n; i++) local.push(tier >= 2 && i === 0 && b % 3 === 0 ? "bus" : pickModel(r()));
    });
    const through = Array.from({ length: THROUGH[tier] }, () => (r() < 0.12 ? "truck" : pickModel(r())));
    const count = (m: string) => local.filter((v) => v === m).length + through.filter((v) => v === m).length;
    const fleets = new Map<string, Fleet>();
    const sizes = new Map<string, { len: number; wid: number }>();
    this.lamps.clear();
    const realMats = (role: string) => {
      const m = realMat("cars", role, { wall: -1, accent: 0, roof: 0, signs: 0 }, 0, "traffic") as THREE.MeshStandardMaterial;
      if (m.userData.night) this.lamps.add(m);
      return m;
    };
    for (const model of VEHICLES) {
      const n = count(model);
      if (!n) continue;
      const colours = model === "taxi" ? [0xf2c12e] : model === "bus" ? BUS_PAINT : CAR_PAINTS;
      const parts = realPiece("cars", model);
      const blob = blobGeo(parts);
      blob.computeBoundingBox();
      const size = blob.boundingBox!.getSize(new THREE.Vector3());
      sizes.set(model, { len: size.z / 1.1, wid: size.x / 1.15 });
      const withBlob = [...parts, { role: "blob", geo: blob }];
      fleets.set(model, new Fleet(withBlob, n, { carpaint: colours }, (role) => (role === "blob" ? this.blob : realMats(role)), r));
    }
    // Signals stand from a town on (scene.ts); a hamlet's crossings are first come, first through.
    const flow = (this.flow = new Flow(all, tier >= 1, rng(0x7a1c + p.blocks.length), spots));
    const vehicle = (m: string): Vehicle => ({ len: sizes.get(m)!.len, bus: m === "bus" });
    const cars = populate(flow, local.map(vehicle), through.map(vehicle), r);
    const slots = new Map<string, number>();
    [...local, ...through].forEach((model, i) => {
      const slot = slots.get(model) ?? 0;
      slots.set(model, slot + 1);
      this.drivers.push({ fleet: fleets.get(model)!, slot, car: cars[i], wid: sizes.get(model)!.wid });
    });

    // People: the figure (civic.py), tinted per person by role, its limbs
    // swung by the vertex shader (striding()). Its materials take vertex
    // colours, so the figure gets plain white ones.
    const walkers = NO_PEOPLE ? 0 : p.blocks.length * PEOPLE[tier];
    const signs = new Set(p.signs.map((s) => `${s.x},${s.z}`));
    this.crowd = walkers ? new Crowd(p.blocks, tier, PEOPLE[tier], rng(0x9e0 + p.blocks.length), signs) : null;
    const crowd = this.crowd;
    if (crowd) {
      flow.people = (x, z, rad) => crowd.near(x, z, rad);
      flow.crossers = (x, z, rad) => crowd.crossing(x, z, rad);
    }
    this.walk = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(1, walkers) * 2), 2);
    this.walk.setUsage(THREE.DynamicDrawUsage);
    const figure = rig(realPiece("civic", "person")).map(({ role, geo }) => {
      geo.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(geo.getAttribute("position").count * 3).fill(1), 3));
      geo.setAttribute("aWalk", this.walk!);
      return { role, geo };
    });
    this.people = new Fleet(figure, walkers, { shirt: SHIRTS, pants: PANTS, skin: SKIN, hair: HAIR }, this.mat, r);

    this.fleets = [...fleets.values(), this.people];
    for (const f of this.fleets) for (const m of f.meshes) this.group.add(m);
    this.update(0);
  }

  /** Height of the road under a point: the town's streets, the bridge deck, or the open road over the land. */
  private roadY(x: number, z: number): number {
    const g = this.ground;
    if (!g || (this.plan && onStreets(this.plan.blocks, x, z))) return TYRES;
    if (Math.abs(x - g.bridge.x) < 22 && Math.abs(z - g.bridge.z) < 6) return DECK;
    return g.height(x, z) + TYRES;
  }

  /** `t`: the scene clock, which runs the signals. */
  update(dt: number, t = this.t) {
    this.t = t;
    const flow = this.flow;
    if (!flow) return;
    // Small steps, so a long frame cannot carry a car through the one ahead.
    // A stalled frame (a hidden window) skips ahead rather than catching up.
    const step = Math.min(dt, 0.5);
    const n = Math.ceil(step / 0.05);
    for (let i = 0; i < n; i++) flow.step(step / n, t - step + ((i + 1) * step) / n);
    const shapes: CarShape[] = [];
    for (const d of this.drivers) {
      const at = flow.where(d.car);
      if (!at.scale) {
        d.fleet.set(d.slot, 0, -50, 0, 0, 0, 0);
        continue;
      }
      // On the hills, the car tilts with the road.
      const half = d.car.len / 2;
      const [sx, sz] = [Math.sin(at.heading) * half, Math.cos(at.heading) * half];
      const front = this.roadY(at.x + sx, at.z + sz);
      const back = this.roadY(at.x - sx, at.z - sz);
      d.fleet.set(d.slot, at.x, (front + back) / 2, at.z, at.heading, Math.atan2(front - back, d.car.len), at.scale);
      shapes.push({ x: at.x, z: at.z, heading: at.heading, len: d.car.len, wid: d.wid, v: d.car.v, drive: d.car.mode === "in" || d.car.mode === "out" ? flow.driveway(d.car.spot!) : null, committed: !!(d.car.turn || d.car.granted || d.car.held) });
    }
    if (this.crowd && this.people && this.walk) {
      this.crowd.step(Math.min(dt, 0.25), t, shapes);
      const arr = this.walk.array as Float32Array;
      this.crowd.walkers.forEach((w, i) => {
        const pose = this.crowd!.pose(w, KERB, TYRES);
        this.people!.set(i, pose.x, pose.y, pose.z, pose.heading);
        arr[i * 2] = pose.phase;
        arr[i * 2 + 1] = pose.amp;
      });
      this.walk.needsUpdate = true;
    }
    for (const f of this.fleets) f.flush();
  }

  /** The soft dark ellipse under every vehicle, standing in for its shadow. */
  private blob = blobMat();

  /** Anything moving (the scene keeps drawing frames while there is). */
  get active() {
    return this.drivers.length > 0 || (this.crowd?.walkers.length ?? 0) > 0;
  }

  /** 0 by day, 1 at night. */
  setNight(night: number) {
    this.blob.opacity = 0.8 - 0.45 * night;
    for (const m of this.lamps) {
      if (m.userData.night) m.emissiveIntensity = m.userData.night * Math.max(night, m.userData.day ?? 0);
    }
  }
}

/** Hips and shoulders of the figure (civic.py), m up from its feet. */
const HIP = 0.92;
const SHOULDER = 1.4;
/** How far legs and arms swing either way at a walk, radians. */
const LEG_SWING = 0.42;
const ARM_SWING = 0.32;

/**
 * The figure's parts with an `aLimb` attribute for striding(): per vertex,
 * how far its limb swings (signed, so legs and arms alternate), the height
 * of its pivot, and the angle it was modelled at (mid-stride), which the
 * shader takes off so a figure standing still stands straight.
 */
function rig(parts: { role: string; geo: THREE.BufferGeometry }[]): { role: string; geo: THREE.BufferGeometry }[] {
  const out = parts.map(({ role, geo }) => ({ role, geo: geo.clone() }));
  // Which limb each vertex is on: 0 body, then legs and arms by side.
  const limbOf = out.map(({ role, geo }) => {
    const pos = geo.getAttribute("position");
    const parent = Array.from({ length: pos.count }, (_, i) => i);
    const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i])));
    const idx = geo.getIndex();
    const tri = idx ? idx.count : pos.count;
    for (let t = 0; t < tri; t += 3) {
      const [a, b, c] = [0, 1, 2].map((k) => (idx ? idx.getX(t + k) : t + k));
      parent[find(b)] = find(a);
      parent[find(c)] = find(a);
    }
    // Each connected piece by where its middle is.
    const sum = new Map<number, [number, number, number]>();
    for (let i = 0; i < pos.count; i++) {
      const s = sum.get(find(i)) ?? [0, 0, 0];
      s[0] += pos.getX(i);
      s[1] += pos.getY(i);
      s[2]++;
      sum.set(find(i), s);
    }
    return Array.from({ length: pos.count }, (_, i) => {
      const [x, y, n] = sum.get(find(i))!;
      const [cx, cy] = [x / n, y / n];
      if (role === "pants") return cx < 0 ? 1 : 2;
      if ((role === "shirt" || role === "skin") && Math.abs(cx) > 0.12 && cy < SHOULDER) return cx < 0 ? 3 : 4;
      return 0;
    });
  });
  // The angle each limb was modelled at, from where its lower part hangs.
  const pivot = [0, HIP, HIP, SHOULDER, SHOULDER];
  const lean = [0, 0, 0, 0, 0];
  for (let limb = 1; limb <= 4; limb++) {
    let [dy, dz] = [0, 0];
    out.forEach(({ geo }, j) => {
      const pos = geo.getAttribute("position");
      for (let i = 0; i < pos.count; i++) {
        if (limbOf[j][i] !== limb || pos.getY(i) > pivot[limb] - 0.3) continue;
        dy += pos.getY(i) - pivot[limb];
        dz += pos.getZ(i);
      }
    });
    // Rotating straight down by θ about x puts the limb at z = -L sin θ.
    lean[limb] = dy ? Math.atan2(-dz, -dy) : 0;
  }
  const swing = [0, -LEG_SWING, LEG_SWING, ARM_SWING, -ARM_SWING];
  for (const [j, { geo }] of out.entries()) {
    const a = new Float32Array(geo.getAttribute("position").count * 3);
    limbOf[j].forEach((limb, i) => a.set([swing[limb], pivot[limb], lean[limb]], i * 3));
    geo.setAttribute("aLimb", new THREE.BufferAttribute(a, 3));
  }
  return out;
}

/**
 * Swings each limb about its hip or shoulder by the person's stride: per
 * instance `aWalk` is the stride phase and how much to swing (0 standing).
 */
function striding(m: THREE.MeshStandardMaterial) {
  m.onBeforeCompile = (sh) => {
    sh.vertexShader = sh.vertexShader
      .replace("#include <common>", "#include <common>\nattribute vec3 aLimb;\nattribute vec2 aWalk;")
      .replace(
        "#include <beginnormal_vertex>",
        `#include <beginnormal_vertex>
        float limbA = aLimb.x * sin(aWalk.x) * aWalk.y - aLimb.z;
        float limbC = cos(limbA);
        float limbS = sin(limbA);
        objectNormal = vec3(objectNormal.x, limbC * objectNormal.y - limbS * objectNormal.z, limbS * objectNormal.y + limbC * objectNormal.z);`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
        transformed.y -= aLimb.y;
        transformed = vec3(transformed.x, limbC * transformed.y - limbS * transformed.z, limbS * transformed.y + limbC * transformed.z);
        transformed.y += aLimb.y;`,
      );
  };
  m.customProgramCacheKey = () => "striding";
}

/** A ground plane a little larger than the vehicle's footprint, just above the road. */
function blobGeo(parts: { geo: THREE.BufferGeometry }[]): THREE.BufferGeometry {
  const box = new THREE.Box3();
  for (const { geo } of parts) {
    geo.computeBoundingBox();
    box.union(geo.boundingBox!);
  }
  const s = box.getSize(new THREE.Vector3());
  const c = box.getCenter(new THREE.Vector3());
  return new THREE.PlaneGeometry(s.x * 1.15, s.z * 1.1).rotateX(-Math.PI / 2).translate(c.x, 0.02, c.z);
}

function blobMat(): THREE.MeshBasicMaterial {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const x = c.getContext("2d")!;
  const g = x.createRadialGradient(32, 32, 4, 32, 32, 32);
  g.addColorStop(0, "rgba(0,0,0,0.75)");
  g.addColorStop(0.6, "rgba(0,0,0,0.45)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  x.fillStyle = g;
  x.fillRect(0, 0, 64, 64);
  const m = new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false, opacity: 0.8, polygonOffset: true, polygonOffsetFactor: -2 });
  m.userData.noShadow = true;
  return m;
}
