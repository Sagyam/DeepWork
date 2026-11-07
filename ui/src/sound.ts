// The city's sounds, made in WebAudio at play time: no audio files to ship
// or license. A per-window preference like the theme (localStorage); off
// until the first click, since browsers keep audio shut until then.

const KEY = "deepwork.sound";

let ctx: AudioContext | null = null;
let master: GainNode | null = null;

export function soundOn(): boolean {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

export function setSound(on: boolean) {
  try {
    if (on) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, "off");
  } catch {
    // Private windows: it lasts this session only.
  }
  if (master) master.gain.value = on ? 0.5 : 0;
}

/** Opens the audio context on a user gesture, as browsers require. */
export function unlockSound() {
  if (ctx) {
    void ctx.resume();
    return;
  }
  const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AC) return;
  ctx = new AC();
  master = ctx.createGain();
  master.gain.value = soundOn() ? 0.5 : 0;
  // A little room, so the bells ring out instead of stopping dead.
  const delay = ctx.createDelay(1);
  delay.delayTime.value = 0.19;
  const feedback = ctx.createGain();
  feedback.gain.value = 0.28;
  const wet = ctx.createGain();
  wet.gain.value = 0.25;
  master.connect(ctx.destination);
  master.connect(delay);
  delay.connect(feedback).connect(delay);
  delay.connect(wet).connect(ctx.destination);
}

/** A bell: a sine with an inharmonic partial, struck and decaying. */
function bell(freq: number, at: number, dur = 1.6, level = 0.3) {
  if (!ctx || !master) return;
  const t = ctx.currentTime + at;
  for (const [mult, gain] of [[1, 1], [2.76, 0.35], [5.4, 0.12]]) {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.frequency.value = freq * mult;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(level * gain, t + 0.006);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur / mult);
    o.connect(g).connect(master);
    o.start(t);
    o.stop(t + dur);
  }
}

/** Filtered noise: rubble, a rumble. */
function noise(at: number, dur: number, from: number, to: number, level: number) {
  if (!ctx || !master) return;
  const t = ctx.currentTime + at;
  const buf = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * dur), ctx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  const src = ctx.createBufferSource();
  src.buffer = buf;
  const f = ctx.createBiquadFilter();
  f.type = "lowpass";
  f.frequency.setValueAtTime(from, t);
  f.frequency.exponentialRampToValueAtTime(to, t + dur);
  const g = ctx.createGain();
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(level, t + 0.03);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  src.connect(f).connect(g).connect(master);
  src.start(t);
}

/** A soft brass-like note: a saw through a closing filter. */
function horn(freq: number, at: number, dur: number, level = 0.12) {
  if (!ctx || !master) return;
  const t = ctx.currentTime + at;
  const o = ctx.createOscillator();
  o.type = "sawtooth";
  o.frequency.value = freq;
  const f = ctx.createBiquadFilter();
  f.type = "lowpass";
  f.frequency.setValueAtTime(freq * 6, t);
  f.frequency.exponentialRampToValueAtTime(freq * 2, t + dur);
  const g = ctx.createGain();
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(level, t + 0.08);
  g.gain.setValueAtTime(level, t + dur * 0.7);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(f).connect(g).connect(master);
  o.start(t);
  o.stop(t + dur);
}

export type Cue = "built" | "repaired" | "collapsed" | "quake" | "damaged" | "graduated" | "coins";

/** Plays one of the city's moments. */
export function play(cue: Cue) {
  if (!ctx || !master || !soundOn()) return;
  switch (cue) {
    case "built":
      // A rising major arpeggio on bells.
      [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => bell(f, i * 0.11, 1.8, 0.22));
      break;
    case "repaired":
      bell(659.25, 0, 1.2, 0.16);
      bell(987.77, 0.12, 1.4, 0.14);
      break;
    case "collapsed":
      noise(0, 2.6, 1800, 90, 0.5);
      noise(0.35, 1.8, 600, 60, 0.35);
      bell(155.56, 0.05, 2.4, 0.18);
      break;
    case "quake":
      noise(0, 3.2, 220, 40, 0.7);
      break;
    case "damaged":
      noise(0, 0.9, 900, 120, 0.35);
      break;
    case "graduated":
      // A short fanfare: fifth, octave, then the chord held.
      horn(261.63, 0, 0.35);
      horn(392, 0.3, 0.35);
      horn(523.25, 0.6, 1.4);
      horn(659.25, 0.6, 1.4, 0.08);
      horn(783.99, 0.6, 1.4, 0.08);
      [1046.5, 1318.5, 1568].forEach((f, i) => bell(f, 0.65 + i * 0.09, 2.2, 0.12));
      break;
    case "coins":
      bell(1318.5, 0, 0.5, 0.12);
      bell(1760, 0.06, 0.6, 0.1);
      break;
  }
}
