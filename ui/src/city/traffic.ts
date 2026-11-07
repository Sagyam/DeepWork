// City theme: street life. Cars, taxis, vans and buses drive the lane graph
// (roads.ts): straight on or round corners, stopping at red; pedestrians
// walk the pavements. Both grow
// with the tier, so a metropolis is busy and a hamlet sleepy. Every part of
// a model is one InstancedMesh, moved every frame; headlights, tail
// lights and signs follow the night.
import * as THREE from "three";
import { BLOCK_X, BLOCK_Z, blockLoop, rng, type CityPlan, type Loop } from "./plan";
import { Flow, lanes, type Car } from "./roads";
import { CAR_PAINTS, realMat, realPiece } from "./real";

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
  private p = new THREE.Vector3();
  private one = new THREE.Vector3(1, 1, 1);
  private up = new THREE.Vector3(0, 1, 0);

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

  set(i: number, x: number, y: number, z: number, heading: number) {
    this.q.setFromAxisAngle(this.up, heading);
    this.m.compose(this.p.set(x, y, z), this.q, this.one);
    for (const mesh of this.meshes) mesh.setMatrixAt(i, this.m);
  }

  flush() {
    for (const mesh of this.meshes) mesh.instanceMatrix.needsUpdate = true;
  }
}

interface Mover {
  fleet: Fleet;
  slot: number;
  loop: Loop;
  d: number;
  speed: number;
  /** -1 walks the loop backwards. */
  dir: number;
  y: number;
  bob: number;
}

/** The vehicles in traffic (pieces of cars.glb). */
const VEHICLES = ["hatch", "sedan", "estate", "suv", "coupe", "taxi", "pickup", "van", "truck", "bus"];

interface Driver {
  fleet: Fleet;
  slot: number;
  car: Car;
}

/** Vehicles per block and people per block, by tier. */
const CARS = [1, 2, 3, 4];
const PEOPLE = [2, 4, 7, 11];

export class Traffic {
  group = new THREE.Group();
  private movers: Mover[] = [];
  private drivers: Driver[] = [];
  private flow: Flow | null = null;
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
      this.mats.set(role, m);
    }
    return m;
  };

  /** Rebuild for a new city plan (when blocks or the tier change). */
  build(p: CityPlan) {
    for (const f of this.fleets) for (const m of f.meshes) this.group.remove(m);
    this.fleets = [];
    this.movers = [];
    this.drivers = [];
    const r = rng(0xca75 + p.blocks.length * 7 + p.tier);
    const tier = Math.min(3, Math.max(0, p.tier));

    // Decide every vehicle first so each model's fleet is sized once.
    const plans: { model: string; block: number; i: number; n: number }[] = [];
    p.blocks.forEach((_, b) => {
      const n = CARS[tier] + (tier >= 2 && r() < 0.5 ? 1 : 0);
      for (let i = 0; i < n; i++) {
        const k = r();
        const model =
          tier >= 2 && i === 0 && b % 3 === 0 ? "bus"
          : tier >= 2 && k < 0.18 ? "taxi"
          : k < 0.26 ? "van"
          : tier >= 1 && k < 0.3 ? "truck"
          : k < 0.48 ? "hatch"
          : k < 0.64 ? "sedan"
          : k < 0.78 ? "suv"
          : k < 0.88 ? "estate"
          : k < 0.94 ? "pickup"
          : "coupe";
        plans.push({ model, block: b, i, n });
      }
    });
    const count = (m: string) => plans.filter((v) => v.model === m).length;
    const fleets = new Map<string, Fleet>();
    const lengths = new Map<string, number>();
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
      lengths.set(model, blob.boundingBox!.getSize(new THREE.Vector3()).z / 1.1);
      const withBlob = [...parts, { role: "blob", geo: blob }];
      fleets.set(model, new Fleet(withBlob, n, { carpaint: colours }, (role) => (role === "blob" ? this.blob : realMats(role)), r));
    }
    const slots = new Map<string, number>();
    // Signals stand from a town on (scene.ts); a hamlet's crossings are first come, first through.
    const flow = (this.flow = new Flow(lanes(p.blocks), tier >= 1, rng(0x7a1c + p.blocks.length)));
    const turn = p.blocks.map(() => Math.floor(r() * 4));
    for (const v of plans) {
      const slot = slots.get(v.model) ?? 0;
      slots.set(v.model, slot + 1);
      // Each starts on one of its block's four lanes (lanes() keeps them in
      // block order), at most two to a lane and well apart.
      const lane = flow.lanes[v.block * 4 + ((v.i + turn[v.block]) % 4)];
      const car = flow.add(lane, lane.path.length * (0.2 + 0.45 * Math.floor(v.i / 4)), lengths.get(v.model)!, 6 + r() * 4);
      this.drivers.push({ fleet: fleets.get(v.model)!, slot, car });
    }

    const walkers = p.blocks.length * PEOPLE[tier];
    // The figure (civic.py), tinted per person by role. Its materials take
    // vertex colours, so the figure gets plain white ones.
    const figure = realPiece("civic", "person").map(({ role, geo }) => {
      const g = geo.clone();
      g.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(g.getAttribute("position").count * 3).fill(1), 3));
      return { role, geo: g };
    });
    const people = new Fleet(figure, walkers, { shirt: SHIRTS, pants: PANTS, skin: SKIN, hair: HAIR }, this.mat, r);
    const walks = p.blocks.flatMap((b) => [
      blockLoop(b.x, b.z, BLOCK_X / 2 + 0.5, BLOCK_Z / 2 + 0.5, 0.8),
      blockLoop(b.x, b.z, BLOCK_X / 2 + 1.25, BLOCK_Z / 2 + 1.25, 1.2),
    ]);
    for (let i = 0; i < walkers; i++) {
      const loop = walks[Math.floor(i / PEOPLE[tier]) * 2 + (i % 2)];
      this.movers.push({ fleet: people, slot: i, loop, d: r() * loop.length, speed: 1.1 + r() * 0.5, dir: i % 2 ? 1 : -1, y: 0.22, bob: r() * 10 });
    }

    this.fleets = [...fleets.values(), people];
    for (const f of this.fleets) for (const m of f.meshes) this.group.add(m);
    this.update(0);
  }

  /** `t`: the scene clock, which runs the signals. */
  update(dt: number, t = this.t) {
    this.t = t;
    if (this.flow) {
      // Small steps, so a long frame cannot carry a car through the one ahead.
      // A stalled frame (a hidden window) skips ahead rather than catching up.
      const step = Math.min(dt, 0.5);
      const n = Math.ceil(step / 0.05);
      for (let i = 0; i < n; i++) this.flow.step(step / n, t - step + ((i + 1) * step) / n);
    }
    for (const d of this.drivers) {
      const at = this.flow!.where(d.car);
      d.fleet.set(d.slot, at.x, 0.05, at.z, at.heading);
    }
    for (const m of this.movers) {
      m.d += m.speed * dt * m.dir;
      const at = m.loop.at(m.d);
      let y = m.y;
      if (m.bob) {
        m.bob += dt * m.speed * 5.5;
        y += Math.abs(Math.sin(m.bob)) * 0.05;
      }
      m.fleet.set(m.slot, at.x, y, at.z, at.heading + (m.dir < 0 ? Math.PI : 0));
    }
    for (const f of this.fleets) f.flush();
  }

  /** The soft dark ellipse under every vehicle, standing in for its shadow. */
  private blob = blobMat();

  /** Anything moving (the scene keeps drawing frames while there is). */
  get active() {
    return this.movers.length > 0 || this.drivers.length > 0;
  }

  /** 0 by day, 1 at night. */
  setNight(night: number) {
    this.blob.opacity = 0.8 - 0.45 * night;
    for (const m of this.lamps) {
      if (m.userData.night) m.emissiveIntensity = m.userData.night * Math.max(night, m.userData.day ?? 0);
    }
  }
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
