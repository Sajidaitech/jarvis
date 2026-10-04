// Windows hologram overlay page. State comes from the local server (/state), which reads JARVIS's state file.
import { Avatar } from './avatar.js';
import { Animator } from './animations.js';

const $ = (id) => document.getElementById(id);
const log = (m) => fetch('/log?m=' + encodeURIComponent(String(m).slice(0, 300))).catch(() => {});
const LABEL = { speaking: 'RESPONDING', thinking: 'PROCESSING', listening: 'LISTENING', idle: 'ONLINE', activating: 'ACTIVATING', offline: 'OFFLINE' };

const avatar = new Avatar($('stage'));
let animator = null, state = 'activating', closing = false, level = 0, tAct = 0;

async function poll() {
  try {
    const j = await (await fetch('/state', { cache: 'no-store' })).json();
    if (j.close && !closing) { closing = true; document.body.classList.add('hidden'); state = 'offline'; }
    else if (!closing && performance.now() / 1000 - tAct > 1.8) state = { SPEAKING: 'speaking', THINKING: 'thinking', LISTENING: 'listening' }[j.state] || 'idle';
  } catch { /* server gone: window is closing */ }
  setTimeout(poll, 250);
}

function frame(ts) {
  requestAnimationFrame(frame);
  const t = ts / 1000, dt = Math.min(0.05, t - (frame.p || t)); frame.p = t;
  const target = state === 'speaking' ? Math.max(0.2, 0.5 + 0.3 * Math.sin(t * 9) * Math.sin(t * 5.3)) : 0;
  level += (target - level) * (1 - Math.exp(-dt * 14));
  if (animator) { animator.setState(state, t); animator.update(dt, t, level); avatar.render(dt, t); }
  $('label').textContent = `[ ${LABEL[state] || 'ONLINE'} ]`;
  $('voice').textContent = state === 'speaking' ? 'VOICE ACTIVE' : 'VOICE IDLE';
  $('core').textContent = `CORE  ${Math.round(97 + 2 * Math.sin(t))}%`;
  if ((t | 0) !== frame.s) { frame.s = t | 0; $('clock').textContent = new Date().toLocaleTimeString([], { hour12: false }); }
}

(async () => {
  const ok = await avatar.init({ modelUrl: '/models/jarvis.glb', photoUrl: '/models/jarvis_portrait.jpg' });
  if (!ok) { $('err').textContent = '3D engine not available. Run update_packages.bat (downloads it) or check internet.'; log(avatar.error); }
  else {
    avatar.camera.position.set(0, 1.0, 4.7); avatar.camera.lookAt(0, 0.95, 0); avatar.resize();
    if (avatar.usingPhoto) document.body.classList.add('photo');
    animator = new Animator(avatar.rig); animator.setState('offline', 0);
    import('./photo-avatar.js').then((m) => log('photo-avatar version ' + m.PHOTO_VERSION)).catch(() => {});
    log('avatar ready, glb=' + !!avatar.usingGLB + ', portrait=' + !!avatar.usingPhoto);
  }
  tAct = performance.now() / 1000; state = 'activating';
  document.body.classList.remove('hidden');
  requestAnimationFrame(frame); poll();
  window.jarvisClose = () => { closing = true; document.body.classList.add('hidden'); };
})();
addEventListener('error', (e) => log('js error: ' + e.message));
addEventListener('unhandledrejection', (e) => log('promise: ' + e.reason));
