// Tiny synth sound effects (Web Audio, no audio files). Off until the user turns sound on.
let ctx: AudioContext | null = null;
let enabled = localStorage.getItem("ecn-sound") === "on";

export const sound = {
  get enabled() { return enabled; },
  set(on: boolean) {
    enabled = on;
    localStorage.setItem("ecn-sound", on ? "on" : "off");
    if (on) ensure();
  },
};

function ensure(): AudioContext | null {
  if (!ctx) {
    try { ctx = new AudioContext(); } catch { return null; }
  }
  if (ctx.state === "suspended") void ctx.resume();
  return ctx;
}

function tone(freq: number, start: number, dur: number, type: OscillatorType = "square", vol = 0.06) {
  const c = ensure();
  if (!c) return;
  const o = c.createOscillator();
  const g = c.createGain();
  const f = c.createBiquadFilter();
  f.type = "lowpass";
  f.frequency.value = 2400;
  o.type = type;
  o.frequency.setValueAtTime(freq, c.currentTime + start);
  g.gain.setValueAtTime(0, c.currentTime + start);
  g.gain.linearRampToValueAtTime(vol, c.currentTime + start + 0.015);
  g.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + start + dur);
  o.connect(f).connect(g).connect(c.destination);
  o.start(c.currentTime + start);
  o.stop(c.currentTime + start + dur + 0.05);
}

export function playRadio() {
  if (!enabled) return;
  tone(1320, 0, 0.05, "sine", 0.025);
  tone(990, 0.06, 0.05, "sine", 0.02);
}

export function playStart() {
  if (!enabled) return;
  [220, 220, 220, 440].forEach((f, i) => tone(f, i * 0.5, i === 3 ? 0.6 : 0.25, "square", 0.05));
}

export function playCash() {
  if (!enabled) return;
  tone(1568, 0, 0.08, "triangle", 0.07);
  tone(2093, 0.09, 0.25, "triangle", 0.07);
}

export function playFanfare() {
  if (!enabled) return;
  const notes = [523, 659, 784, 1047, 784, 1047, 1319];
  notes.forEach((f, i) => tone(f, i * 0.12, i === notes.length - 1 ? 0.9 : 0.16, "sawtooth", 0.05));
  [262, 330, 392].forEach((f) => tone(f, 0.84, 0.9, "triangle", 0.04));
}
