// State-driven animation. Works on the placeholder rig and on a GLB rig (bones, morph targets, optional clips).
const BONES = ['hips', 'spine', 'chest', 'neck', 'head', 'armL', 'armR', 'elbowL', 'elbowR'];

// Targets per state. Numbers are smoothed toward these values, so state changes blend instead of snapping.
const PROFILE = {
  offline:    { eye: 0.10, core: 0.10, pulse: 0.4, head: 0.0, droop: 0.28, look: 0,    tilt: 0,    breath: 0.5, sway: 0 },
  activating: { eye: 1.50, core: 1.70, pulse: 3.0, head: 0.5, droop: 0,    look: 0,    tilt: 0,    breath: 1.0, sway: 0.4 },
  idle:       { eye: 0.65, core: 0.55, pulse: 0.9, head: 0.6, droop: 0.03, look: 0,    tilt: 0,    breath: 1.0, sway: 0.5 },
  listening:  { eye: 1.00, core: 0.85, pulse: 1.4, head: 0.7, droop: 0,    look: 0,    tilt: 0.10, breath: 1.0, sway: 0.5 },
  thinking:   { eye: 0.85, core: 1.10, pulse: 3.2, head: 0.4, droop: 0,    look: 0.12, tilt: -0.05, breath: 1.2, sway: 0.3 },
  speaking:   { eye: 1.10, core: 1.00, pulse: 2.0, head: 0.9, droop: 0,    look: 0,    tilt: 0,    breath: 1.0, sway: 0.7 },
};

export class Animator {
  constructor(rig) {
    this.rig = rig; this.state = 'offline'; this.tState = 0;
    this.cur = { ...PROFILE.offline };
    this.base = {}; for (const k of BONES) if (rig[k]) this.base[k] = rig[k].rotation.clone();
    this.blink = { next: 2, t: -1 }; this.mouth = 0; this.activeAction = null; this.procBody = true;
  }

  setState(s, t) {
    if (s === this.state) return;
    this.state = s; this.tState = t;
    const r = this.rig;
    if (r.mixer && r.clips) {                       // optional skeletal clips from the GLB
      const clip = r.clips[s] || r.clips.idle;
      const next = clip ? (r.actions[clip.name] ||= r.mixer.clipAction(clip)) : null;
      if (this.activeAction && this.activeAction !== next) this.activeAction.fadeOut(0.4);
      if (next) next.reset().fadeIn(0.4).play();
      this.activeAction = next; this.procBody = !next;
    }
  }

  update(dt, t, level) {
    const rig = this.rig, P = PROFILE[this.state], c = this.cur, el = t - this.tState;
    if (rig.mixer) rig.mixer.update(dt);
    const k = 1 - Math.exp(-dt * 5);
    for (const key in P) c[key] += (P[key] - c[key]) * k;

    const speaking = this.state === 'speaking';
    const br = Math.sin(t * 1.5) * c.breath;

    // Head and neck
    let yaw = Math.sin(t * 0.42) * 0.13 * c.head + Math.sin(t * 1.1) * 0.02 * c.head;
    let pitch = Math.sin(t * 0.31 + 1) * 0.04 * c.head + c.droop - c.look;
    if (this.state === 'activating') yaw += Math.max(0, 1 - el / 1.6) * -0.6;      // turns toward the user
    if (speaking) { pitch += level * 0.06 * Math.sin(t * 7); yaw += Math.sin(t * 2.3) * 0.05 * level; }

    if (this.procBody) {
      const set = (name, x, y, z) => { const b = rig[name]; if (!b) return; const o = this.base[name]; b.rotation.set(o.x + x, o.y + y, o.z + z); };
      set('head', pitch, yaw, c.tilt);
      set('neck', pitch * 0.4, yaw * 0.4, c.tilt * 0.3);
      set('chest', br * 0.015, yaw * 0.15, 0);
      set('spine', br * 0.01, yaw * 0.1, 0);
      if (rig.canMoveArms) {
        const s = Math.sin(t * 0.9) * 0.012 * c.sway, g = speaking ? level * 0.22 : 0;
        set('armL', br * 0.01, 0, s); set('armR', br * 0.01, 0, -s);
        set('elbowL', -g, 0, 0); set('elbowR', -g * 0.7, 0, 0);
      }
    }

    // Face: blink and mouth (always procedural so lip movement works with any model)
    let b = 0;
    if (t > this.blink.next && this.blink.t < 0) this.blink.t = t;
    if (this.blink.t >= 0) {
      const p = (t - this.blink.t) / 0.16;
      if (p >= 1) { this.blink.t = -1; this.blink.next = t + 2 + Math.random() * 3.5; } else b = p < 0.5 ? p * 2 : 2 - p * 2;
    }
    rig.setBlink(this.state === 'offline' ? Math.max(b, 0.55) : b);
    const mTarget = speaking ? level * (0.55 + 0.45 * Math.abs(Math.sin(t * 14))) : 0;
    this.mouth += (mTarget - this.mouth) * (1 - Math.exp(-dt * 25));
    rig.setMouth(this.mouth);

    // Light: eyes, reactor, travelling scan on activation
    const eye = c.eye * (1 + 0.08 * Math.sin(t * 2));
    let core = c.core * (1 + 0.22 * Math.sin(t * c.pulse * 2));
    if (speaking) core += level * 0.7;
    if (this.state === 'thinking') core += 0.25 * Math.abs(Math.sin(t * 6));
    rig.setGlow(eye, core);
    rig.setScan?.(this.state === 'activating' && el < 1.9 ? el / 1.6 : -1);
  }
}
