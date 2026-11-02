// City theme: street life. Cars, taxis, vans and buses loop around each
// block in the right-hand lane; pedestrians walk the pavements. Both grow
// with the tier, so a metropolis is busy and a hamlet sleepy. Every part of
// a kit model is one InstancedMesh, moved every frame; headlights, tail
// lights and signs follow the night.
import * as THREE from "three";
import { piece } from "./kit";
import { BLOCK_X, BLOCK_Z, PAVEMENT, ROAD, blockLoop, rng, type CityPlan, type Loop } from "./plan";

const CAR_PAINT = [0xb8252a, 0x1f4e8c, 0xe8e6e0, 0x2a2c30, 0x8a8f96, 0x2f6b4a, 0xd9a03a, 0x6a2a4a, 0x3a7fb8, 0xc8c2b4];
const BUS_PAINT = [0xc0392b, 0x2e6fb5, 0x2a9a5a];
const SHIRTS = [0xc0392b, 0x2e6fb5, 0x2a9a5a, 0xe8b020, 0xf0ece4, 0x6a4a8a, 0xe07a30, 0x30343a, 0x8ab0d0, 0xd06a8a];
const PANTS = [0x2a3040, 0x3a3a3e, 0x4a3a2a, 0x1e2a4a, 0x6a6458, 0x202020];
const SKIN = [0xf1c8a8, 0xd9a47e, 0xb07850, 0x8a5634, 0x5e3a22];
const HAIR = [0x1a1410, 0x3a2414, 0x6a4424, 0xb08a50, 0x8a8a88];

interface Look {
  color: number;
  rough?: number;
  metal?: number;
  emissive?: number;
  night?: number;
  /** Emissive by day too (tail lights, signs), as a share of the night level. */
  day?: number;
}

const LOOKS: Record<string, Look> = {
  body: { color: 0xffffff, rough: 0.35, metal: 0.35 },
  carglass: { color: 0x1a2028, rough: 0.1, metal: 0.6 },
  dark: { color: 0x222326, rough: 0.8 },
  tyre: { color: 0x151515, rough: 0.9 },
  chrome: { color: 0xc8ccd0, rough: 0.25, metal: 0.9 },
  headlight: { color: 0xfff6e0, emissive: 0xfff2d0, night: 3 },
  taillight: { color: 0x801010, emissive: 0xff2010, night: 2.2, day: 0.15 },
  taxisign: { color: 0xffd040, emissive: 0xffd040, night: 1.6, day: 0.2 },
  led: { color: 0x402000, emissive: 0xffa020, night: 1.8, day: 0.5 },
  skin: { color: 0xffffff, rough: 0.8 },
  shirt: { color: 0xffffff, rough: 0.9 },
  pants: { color: 0xffffff, rough: 0.9 },
  hair: { color: 0xffffff, rough: 0.9 },
};

/** Roles whose colour varies per instance, and the palette to pick from. */
type Paint = Partial<Record<string, number[]>>;

/** One kit model drawn many times: an InstancedMesh per material role. */
class Fleet {
  meshes: THREE.InstancedMesh[] = [];
  private m = new THREE.Matrix4();
  private q = new THREE.Quaternion();
  private p = new THREE.Vector3();
  private one = new THREE.Vector3(1, 1, 1);
  private up = new THREE.Vector3(0, 1, 0);

  constructor(name: string, count: number, paint: Paint, mats: (role: string) => THREE.MeshStandardMaterial, r: () => number) {
    for (const { role, geo } of piece(name).parts) {
      const mesh = new THREE.InstancedMesh(geo, mats(role), Math.max(1, count));
      mesh.count = count;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
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

/** Vehicles per block and people per block, by tier. */
const CARS = [1, 2, 3, 4];
const PEOPLE = [2, 4, 7, 11];

export class Traffic {
  group = new THREE.Group();
  private movers: Mover[] = [];
  private fleets: Fleet[] = [];
  private mats = new Map<string, THREE.MeshStandardMaterial>();

  private mat = (role: string) => {
    let m = this.mats.get(role);
    if (!m) {
      const l = LOOKS[role] ?? { color: 0xff00ff };
      m = new THREE.MeshStandardMaterial({ color: l.color, roughness: l.rough ?? 0.6, metalness: l.metal ?? 0, vertexColors: true });
      if (l.emissive !== undefined) {
        m.emissive.setHex(l.emissive);
        m.userData.night = l.night;
        m.userData.day = l.day ?? 0;
      }
      this.mats.set(role, m);
    }
    return m;
  };

  /** Rebuild for a new city plan (when blocks or the tier change). */
  build(p: CityPlan) {
    for (const f of this.fleets) for (const m of f.meshes) this.group.remove(m);
    this.fleets = [];
    this.movers = [];
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
          : tier >= 2 && k < 0.22 ? "car_taxi"
          : k < 0.38 ? "car_van"
          : k < 0.65 ? "car_hatch"
          : "car_sedan";
        plans.push({ model, block: b, i, n });
      }
    });
    const count = (m: string) => plans.filter((v) => v.model === m).length;
    const fleets = new Map<string, Fleet>();
    for (const model of ["car_sedan", "car_hatch", "car_van", "car_taxi", "bus"]) {
      const n = count(model);
      if (!n) continue;
      const paint: Paint = { body: model === "car_taxi" ? [0xf2c12e] : model === "bus" ? BUS_PAINT : CAR_PAINT };
      fleets.set(model, new Fleet(model, n, paint, this.mat, r));
    }
    const slots = new Map<string, number>();
    // The lane next to the block: a quarter of the way across the carriageway.
    const lane = PAVEMENT + (ROAD - 2 * PAVEMENT) / 4;
    const loops = p.blocks.map((b) => blockLoop(b.x, b.z, BLOCK_X / 2 + lane, BLOCK_Z / 2 + lane, 3.5));
    const speeds = p.blocks.map(() => 6 + r() * 4);
    const phase = p.blocks.map(() => r());
    for (const v of plans) {
      const slot = slots.get(v.model) ?? 0;
      slots.set(v.model, slot + 1);
      const loop = loops[v.block];
      // Evenly spaced on their loop, all at the loop's speed, so none collide.
      this.movers.push({ fleet: fleets.get(v.model)!, slot, loop, d: ((v.i + phase[v.block]) / v.n) * loop.length, speed: speeds[v.block], dir: 1, y: 0.05, bob: 0 });
    }

    const walkers = p.blocks.length * PEOPLE[tier];
    const people = new Fleet("person", walkers, { shirt: SHIRTS, pants: PANTS, skin: SKIN, hair: HAIR }, this.mat, r);
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

  update(dt: number) {
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

  /** 0 by day, 1 at night. */
  setNight(night: number) {
    for (const m of this.mats.values()) {
      if (m.userData.night) m.emissiveIntensity = m.userData.night * Math.max(night, m.userData.day ?? 0);
    }
  }
}
