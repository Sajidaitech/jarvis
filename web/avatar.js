// 3D avatar: renderer, lighting, adaptive quality, GLB loading with a procedural placeholder fallback.
// Both paths return the same "rig" interface used by animations.js:
//   rig.{hips,spine,chest,neck,head,armL,armR,elbowL,elbowR}  bones/groups (any may be missing)
//   rig.setMouth(0..1) rig.setBlink(0..1) rig.setGlow(eye, core) rig.setScan(v)  rig.mixer/clips/actions (optional)
let T = null;

export class Avatar {
  constructor(canvas) {
    this.canvas = canvas; this.ready = false; this.error = '';
    this.quality = 2; this.avg = 16; this.slowFor = 0; this.fastFor = 0; this.cool = 0; this.lowPower = false;
  }

  async init({ modelUrl, photoUrl = '', lowPower = false }) {
    try { T = await import('three'); } catch { this.error = '3D engine could not load. Connect to the internet once so it can be cached.'; return false; }
    this.lowPower = lowPower; if (lowPower) this.quality = 0;
    const r = this.renderer = new T.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
    r.outputColorSpace = T.SRGBColorSpace; r.toneMapping = T.ACESFilmicToneMapping; r.toneMappingExposure = 1.05;
    r.setClearColor(0x000000, 0);
    this.scene = new T.Scene();
    this.camera = new T.PerspectiveCamera(30, 1, 0.1, 50);
    this.camera.position.set(0, 1.05, 5.3); this.camera.lookAt(0, 0.95, 0);

    try {
      const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
      const pm = new T.PMREMGenerator(r);
      this.scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    } catch { /* reflections are optional */ }

    this.scene.add(new T.HemisphereLight(0x9fc4ff, 0x05070c, 0.8));
    const key = new T.DirectionalLight(0xffffff, 1.5); key.position.set(2, 3, 4); this.scene.add(key);
    this.rim = new T.DirectionalLight(0x2aa8ff, 2.2); this.rim.position.set(-3, 2, -3); this.scene.add(this.rim);
    this.scan = new T.PointLight(0x37b7ff, 0, 3.2); this.scene.add(this.scan);

    // Floor ring
    this.floor = new T.Group();
    for (const [rad, op] of [[0.62, 0.55], [0.85, 0.28]]) {
      const m = new T.Mesh(new T.RingGeometry(rad, rad + 0.012, 64), new T.MeshBasicMaterial({ color: 0x2aa8ff, transparent: true, opacity: op, side: T.DoubleSide }));
      m.rotation.x = -Math.PI / 2; m.position.y = 0.005; this.floor.add(m);
    }
    this.scene.add(this.floor);

    // Particles (disabled on low quality)
    const n = 90, pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { pos[i * 3] = (Math.random() - 0.5) * 2.4; pos[i * 3 + 1] = Math.random() * 2.2; pos[i * 3 + 2] = (Math.random() - 0.5) * 1.6; }
    const pg = new T.BufferGeometry(); pg.setAttribute('position', new T.BufferAttribute(pos, 3));
    this.particles = new T.Points(pg, new T.PointsMaterial({ color: 0x5fe0ff, size: 0.012, transparent: true, opacity: 0.5, depthWrite: false }));
    this.scene.add(this.particles);

    this.holder = new T.Group(); this.scene.add(this.holder);
    let rig = null;
    const exists = await fetch(modelUrl, { method: 'HEAD' }).then((x) => x.ok).catch(() => false);
    if (exists) { try { rig = await this.loadGLB(modelUrl); this.usingGLB = true; } catch (e) { console.warn('GLB failed, using placeholder', e); } }
    if (!rig && photoUrl) {                                   // living portrait of your supplied image
      const ok = await fetch(photoUrl, { method: 'HEAD' }).then((x) => x.ok).catch(() => false);
      if (ok) { try { const { buildPhotoRig } = await import('./photo-avatar.js'); rig = await buildPhotoRig(T, photoUrl, this.holder); this.usingPhoto = true; this.floor.visible = false; } catch (e) { console.warn('photo avatar failed', e); } }
    }
    if (!rig) rig = buildPlaceholder(T, this.holder);
    this.rig = rig;
    const photoScan = rig.setScan;
    rig.setScan = (v) => { this.scan.intensity = v < 0 ? 0 : Math.sin(Math.min(1, v) * Math.PI) * 6; this.scan.position.set(0, Math.max(0, v) * 1.9, 0.6); photoScan?.(v); };

    this.applyQuality(); this.resize(); addEventListener('resize', () => this.resize());
    this.ready = true; return true;
  }

  async loadGLB(url) {
    const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
    const gltf = await new GLTFLoader().loadAsync(url);
    return rigFromGLTF(T, gltf, this.holder);
  }

  resize() {
    const w = this.canvas.clientWidth || innerWidth, h = this.canvas.clientHeight || innerHeight;
    this.renderer.setSize(w, h, false); this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    const visH = 2 * Math.tan(this.camera.fov * Math.PI / 360) * this.camera.position.z;
    this.rig?.fit?.(visH, visH * this.camera.aspect);
  }

  applyQuality() {
    const dpr = devicePixelRatio || 1;
    this.renderer.setPixelRatio([1, Math.min(dpr, 1.5), Math.min(dpr, 2)][this.quality]);
    this.particles.visible = this.quality >= 1; this.rim.visible = this.quality >= 1;
    document.body.classList.toggle('low-power', this.quality === 0);
    this.resize();
  }

  /** Lower resolution/effects when frames get slow (heat, battery saver); recover slowly when the device is comfortable. */
  adapt(ms) {
    this.avg += (ms - this.avg) * 0.05; if (this.cool > 0) { this.cool -= ms; return; }
    if (this.avg > 24 && this.quality > 0) { if ((this.slowFor += ms) > 2000) { this.quality--; this.slowFor = 0; this.cool = 4000; this.applyQuality(); } }
    else this.slowFor = 0;
    if (!this.lowPower && this.avg < 12 && this.quality < 2) { if ((this.fastFor += ms) > 15000) { this.quality++; this.fastFor = 0; this.cool = 4000; this.applyQuality(); } }
    else this.fastFor = 0;
  }

  render(dt, t) {
    if (!this.ready) return;
    this.floor.rotation.y = t * 0.3;
    this.rig?.update?.(t);
    if (this.particles.visible) this.particles.rotation.y = t * 0.04;
    this.renderer.render(this.scene, this.camera);
    this.adapt(dt * 1000);
  }
}

/* ---------------------------------------------------------------- GLB rig */
function rigFromGLTF(T, gltf, holder) {
  const root = gltf.scene, bones = {}, morphMeshes = [], emissives = [];
  const box = new T.Box3().setFromObject(root), size = box.getSize(new T.Vector3());
  const s = 1.8 / (size.y || 1.8); root.scale.setScalar(s);
  box.setFromObject(root); root.position.y -= box.min.y; root.position.x -= (box.min.x + box.max.x) / 2;
  holder.add(root);
  root.traverse((o) => {
    if (o.isBone) bones[o.name.replace(/^mixamorig:?/i, '').replace(/[_.\s:]/g, '').toLowerCase()] = o;
    if (o.isMesh) {
      o.frustumCulled = false;
      if (o.morphTargetDictionary) morphMeshes.push(o);
      for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
        if (m && m.emissive && /eye|core|reactor|led|glow/i.test(m.name)) emissives.push({ m, core: /core|reactor/i.test(m.name), base: m.emissiveIntensity || 1 });
      }
    }
  });
  const pick = (...n) => n.map((x) => bones[x]).find(Boolean);
  const morph = (names, v) => { for (const me of morphMeshes) for (const n of names) { const i = me.morphTargetDictionary[n]; if (i !== undefined) me.morphTargetInfluences[i] = v; } };
  const rig = {
    hips: pick('hips'), spine: pick('spine'), chest: pick('spine2', 'spine1', 'chest', 'upperchest'),
    neck: pick('neck'), head: pick('head'), canMoveArms: false,   // T-pose arm axes differ per model; use clips for arms
    setMouth: (v) => morph(['jawOpen', 'mouthOpen', 'viseme_aa'], v),
    setBlink: (v) => morph(['eyeBlinkLeft', 'eyeBlinkRight', 'eyesClosed', 'blink'], v),
    setGlow: (eye, core) => { for (const e of emissives) e.m.emissiveIntensity = e.base * (e.core ? core : eye); },
    clips: {}, actions: {},
  };
  if (gltf.animations?.length) {
    rig.mixer = new T.AnimationMixer(root);
    for (const a of gltf.animations) {
      for (const k of ['activating', 'idle', 'listening', 'thinking', 'speaking']) {
        const alias = { activating: /activat|wake|start/i, idle: /idle|stand|breath/i, listening: /listen/i, thinking: /think|process/i, speaking: /speak|talk/i }[k];
        if (alias.test(a.name) && !rig.clips[k]) rig.clips[k] = a;
      }
    }
  }
  return rig;
}

/* ------------------------------------------------- procedural placeholder */
function buildPlaceholder(T, holder) {
  const M = (c, r, m, extra = {}) => new T.MeshStandardMaterial({ color: c, roughness: r, metalness: m, envMapIntensity: 0.7, ...extra });
  const white = M(0xe6ebf2, 0.28, 0.5), silver = M(0xaab4c2, 0.35, 0.7), dark = M(0x0a0d13, 0.45, 0.75);
  const skin = M(0xd2bfb0, 0.5, 0.02, { envMapIntensity: 0.25 }), hair = M(0x15110f, 0.8, 0);
  const led = new T.MeshBasicMaterial({ color: 0x2aa8ff }), eyeMat = new T.MeshBasicMaterial({ color: 0x6fd6ff }), coreMat = new T.MeshBasicMaterial({ color: 0x66d4ff });
  const mesh = (g, m, p, parent, sc) => { const o = new T.Mesh(g, m); o.position.set(...p); if (sc) o.scale.set(...sc); parent.add(o); return o; };
  const grp = (p, parent) => { const g = new T.Group(); g.position.set(...p); parent.add(g); return g; };
  const cap = (r, l) => new T.CapsuleGeometry(r, l, 4, 14);

  const hips = grp([0, 0.98, 0], holder);
  mesh(cap(0.16, 0.08), white, [0, 0, 0], hips, [1.35, 0.8, 0.85]);
  for (const s of [-1, 1]) {                                       // legs (static)
    mesh(cap(0.07, 0.3), white, [s * 0.09, -0.27, 0], hips);
    mesh(new T.SphereGeometry(0.055, 12, 10), dark, [s * 0.09, -0.52, 0], hips);
    mesh(cap(0.055, 0.34), silver, [s * 0.09, -0.74, 0], hips);
    mesh(new T.BoxGeometry(0.09, 0.06, 0.22), dark, [s * 0.09, -0.96, 0.04], hips);
    mesh(new T.BoxGeometry(0.012, 0.3, 0.01), led, [s * 0.09, -0.27, 0.07], hips);
  }
  const spine = grp([0, 0.06, 0], hips);
  mesh(cap(0.15, 0.14), dark, [0, 0.14, 0], spine, [1.15, 1, 0.75]);
  const chest = grp([0, 0.3, 0], spine);
  mesh(cap(0.21, 0.2), white, [0, 0.14, 0], chest, [1.3, 1, 0.8]);

  const cv = document.createElement('canvas'); cv.width = 256; cv.height = 64;
  const cx = cv.getContext('2d'); cx.fillStyle = '#18408f'; cx.font = '600 38px -apple-system,Helvetica,Arial'; cx.textAlign = 'center'; cx.textBaseline = 'middle';
  cx.fillText('JARVIS', 128, 34);
  const tex = new T.CanvasTexture(cv); tex.colorSpace = T.SRGBColorSpace;
  mesh(new T.PlaneGeometry(0.2, 0.05), new T.MeshBasicMaterial({ map: tex, transparent: true }), [0, 0.215, 0.172], chest);

  mesh(new T.CircleGeometry(0.062, 32), dark, [0, 0.09, 0.171], chest);
  mesh(new T.TorusGeometry(0.05, 0.008, 12, 40), coreMat, [0, 0.09, 0.175], chest);
  mesh(new T.CircleGeometry(0.036, 32), coreMat, [0, 0.09, 0.176], chest);
  const gc = document.createElement('canvas'); gc.width = gc.height = 64;
  const gx = gc.getContext('2d'), gr = gx.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, 'rgba(120,220,255,1)'); gr.addColorStop(0.35, 'rgba(42,168,255,.45)'); gr.addColorStop(1, 'rgba(42,168,255,0)');
  gx.fillStyle = gr; gx.fillRect(0, 0, 64, 64);
  const coreGlow = new T.Sprite(new T.SpriteMaterial({ map: new T.CanvasTexture(gc), transparent: true, blending: T.AdditiveBlending, depthWrite: false }));
  coreGlow.position.set(0, 0.09, 0.2); chest.add(coreGlow);
  for (const s of [-1, 1]) mesh(new T.BoxGeometry(0.012, 0.2, 0.01), led, [s * 0.19, 0.12, 0.12], chest);

  const arms = {};
  for (const [s, side] of [[-1, 'L'], [1, 'R']]) {                 // arms
    const sh = grp([s * 0.3, 0.27, 0], chest); sh.rotation.z = s * 0.07; arms['arm' + side] = sh;
    mesh(new T.SphereGeometry(0.085, 16, 12), white, [0, 0, 0], sh, [1, 0.9, 1]);
    mesh(cap(0.055, 0.2), white, [0, -0.17, 0], sh);
    mesh(new T.BoxGeometry(0.012, 0.18, 0.01), led, [0, -0.16, 0.058], sh);
    const el = grp([0, -0.32, 0], sh); el.rotation.x = -0.3; arms['elbow' + side] = el;
    mesh(new T.SphereGeometry(0.05, 12, 10), dark, [0, 0, 0], el);
    mesh(cap(0.05, 0.2), silver, [0, -0.17, 0], el);
    mesh(new T.BoxGeometry(0.07, 0.1, 0.04), dark, [0, -0.36, 0], el);
  }

  const neck = grp([0, 0.46, 0], chest);
  mesh(new T.CylinderGeometry(0.04, 0.05, 0.1, 14), dark, [0, 0.02, 0], neck);
  const head = grp([0, 0.06, 0], neck);
  mesh(new T.SphereGeometry(0.1, 28, 20), skin, [0, 0.1, 0], head, [0.9, 1.12, 1]);
  const cap2 = mesh(new T.SphereGeometry(0.104, 28, 14, 0, Math.PI * 2, 0, Math.PI * 0.5), hair, [0, 0.11, -0.006], head, [0.93, 1.15, 1.04]); cap2.rotation.x = -0.18;
  mesh(new T.SphereGeometry(0.018, 10, 8), skin, [0, 0.085, 0.1], head, [0.6, 1, 0.8]);
  const eyes = [-1, 1].map((s) => mesh(new T.SphereGeometry(0.016, 12, 10), eyeMat, [s * 0.038, 0.12, 0.088], head, [1.2, 1, 0.6]));
  const mouth = mesh(new T.BoxGeometry(0.04, 0.006, 0.01), dark, [0, 0.045, 0.094], head);
  const jaw = grp([0, 0.07, 0.02], head);
  mesh(new T.SphereGeometry(0.05, 16, 12), skin, [0, -0.045, 0.045], jaw, [1, 0.8, 0.9]);
  for (const s of [-1, 1]) {                                       // ear modules
    const ear = grp([s * 0.095, 0.105, 0], head);
    const body = mesh(new T.CylinderGeometry(0.036, 0.036, 0.03, 20), white, [s * 0.006, 0, 0], ear); body.rotation.z = Math.PI / 2;
    const ring = mesh(new T.TorusGeometry(0.026, 0.005, 8, 24), led, [s * 0.023, 0, 0], ear); ring.rotation.y = Math.PI / 2;
  }

  return {
    root: holder, hips, spine, chest, neck, head, jaw, ...arms, canMoveArms: true,
    setMouth(v) { jaw.rotation.x = v * 0.22; mouth.scale.y = 0.4 + v * 5; },
    setBlink(v) { const y = Math.max(0.08, 1 - v); for (const e of eyes) e.scale.y = y; },
    setGlow(eye, core) {
      eyeMat.color.setRGB(0.25 * eye, 0.8 * eye, 1.0 * eye);
      led.color.setRGB(0.12 + 0.1 * eye, 0.45 + 0.25 * eye, 1.0);
      coreMat.color.setRGB(0.3 * core, 0.78 * core, 1.0 * core);
      coreGlow.material.opacity = Math.min(1, 0.3 + 0.35 * core); coreGlow.scale.setScalar(0.18 + 0.1 * core);
    },
  };
}
