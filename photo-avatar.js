// "Living portrait" avatar: animates your JARVIS image (assets/avatar/jarvis_portrait.jpg) in real time.
// It is a 2.5D effect on a single picture, NOT a 3D model: head sway/tilt/nod, breathing, blinking, a mouth that opens while
// JARVIS speaks, glowing eyes and chest reactor, and a light scan. Same rig interface as the GLB and placeholder avatars.
// Feature positions (0..1, y down) are measured from the supplied image. If you swap the picture, edit the constants below.

const VERT = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

const FRAG = `
uniform sampler2D uTex; uniform vec3 uHead; uniform float uMouth, uBlink, uBreath, uEye, uCore, uScan;
varying vec2 vUv;
const vec2 FACE = vec2(.46,.15), PIV = vec2(.46,.315), EYEL = vec2(.418,.160), EYER = vec2(.512,.167),
           MOUTH = vec2(.461,.229), REACT = vec2(.525,.501), S = vec2(1.0,1.5);
float blob(vec2 p, vec2 c, vec2 r){ vec2 d = (p - c) / r; return exp(-dot(d, d)); }
void main(){
  vec2 p = vec2(vUv.x, 1.0 - vUv.y), q = p;
  vec2 cc = vec2(.5,.62); q = cc + (q - cc) / (1.0 + uBreath * .004);                 // breathing

  float w = (1.0 - smoothstep(.285,.345,p.y)) * (1.0 - smoothstep(.20,.30,abs(p.x - .46)));   // head-only weight
  float depth = blob(p, FACE, vec2(.17,.17));                                         // fake depth: nose/face moves most
  vec2 r = (q - PIV) * S; float a = -uHead.z * w, ca = cos(a), sa = sin(a);
  r = vec2(ca*r.x - sa*r.y, sa*r.x + ca*r.y); q = PIV + r / S;                         // head roll about the neck
  q.x -= uHead.y * .12 * depth * w;                                                    // yaw
  q.y -= uHead.x * .05 * depth * w;                                                    // pitch

  float mx = 1.0 - smoothstep(.07,.12,abs(p.x - MOUTH.x));
  q.y -= uMouth * .007 * smoothstep(.227,.240,p.y) * (1.0 - smoothstep(.275,.320,p.y)) * mx;   // jaw drop

  float eL = blob(p, EYEL, vec2(.04,.0095)), eR = blob(p, EYER, vec2(.04,.0095));        // blink = squash eye band
  vec2 ec = eL > eR ? EYEL : EYER;
  q.y = mix(q.y, ec.y + (q.y - ec.y) / max(.3, 1.0 - uBlink * .7), max(eL, eR));

  vec4 c = texture2D(uTex, vec2(q.x, 1.0 - q.y));   // q is y-down; GL textures are y-up
  vec2 md = (p - vec2(MOUTH.x, MOUTH.y + uMouth * .003)) / vec2(.017, .0012 + uMouth * .0038);
  c.rgb = mix(c.rgb, vec3(.01,.004,.004), exp(-dot(md, md) * 1.5) * smoothstep(.1,.35,uMouth) * .7);   // mouth opening

  c.rgb *= mix(.55, 1.0, clamp(uEye / .65, 0.0, 1.0));                                 // dim when offline
  vec3 add = vec3(.25,.65,1.0) * (blob(q, EYEL, vec2(.022,.010)) + blob(q, EYER, vec2(.022,.010))) * max(0.0, uEye - .5) * .8 * (1.0 - uBlink);
  float rg = blob(q, REACT, vec2(.03,.02)) * .9 + blob(q, REACT, vec2(.075,.05)) * .35;
  add += vec3(.3,.75,1.0) * rg * max(0.0, uCore - .35) * .6;
  if (uScan >= 0.0) add += vec3(.25,.65,1.0) * exp(-pow((p.y - (1.0 - uScan)) / .012, 2.0)) * .7;

  float edge = smoothstep(0.,.04,p.x) * smoothstep(0.,.04,1.-p.x) * smoothstep(0.,.03,p.y) * smoothstep(0.,.05,1.-p.y);
  gl_FragColor = vec4(c.rgb + add, c.a * edge);
  #include <colorspace_fragment>
}`;

export async function buildPhotoRig(T, url, holder) {
  const tex = await new T.TextureLoader().loadAsync(url);
  tex.colorSpace = T.SRGBColorSpace; tex.anisotropy = 4;
  const aspect = tex.image.width / tex.image.height;
  const U = { uTex: { value: tex }, uHead: { value: new T.Vector3() }, uMouth: { value: 0 }, uBlink: { value: 0 },
    uBreath: { value: 0 }, uEye: { value: 0.6 }, uCore: { value: 0.5 }, uScan: { value: -1 } };
  const mat = new T.ShaderMaterial({ uniforms: U, vertexShader: VERT, fragmentShader: FRAG, transparent: true, toneMapped: false, depthWrite: false });
  const mesh = new T.Mesh(new T.PlaneGeometry(1, 1), mat); mesh.position.y = 0.95; holder.add(mesh);
  const mk = () => new T.Object3D(), hips = mk(), spine = mk(), chest = mk(), neck = mk(), head = mk();
  return {
    hips, spine, chest, neck, head, canMoveArms: false, isPhoto: true,
    fit(visH, visW) { if (visW / visH < aspect) mesh.scale.set(visW, visW / aspect, 1); else mesh.scale.set(visH * aspect, visH, 1); },
    update() {
      U.uHead.value.set(head.rotation.x + neck.rotation.x, head.rotation.y + neck.rotation.y, head.rotation.z + neck.rotation.z);
      U.uBreath.value = chest.rotation.x * 66;
    },
    setMouth: (v) => { U.uMouth.value = v; },
    setBlink: (v) => { U.uBlink.value = v; },
    setGlow: (eye, core) => { U.uEye.value = eye; U.uCore.value = core; },
    setScan: (v) => { U.uScan.value = v; },
    dispose() { holder.remove(mesh); mesh.geometry.dispose(); mat.dispose(); tex.dispose(); },   // frees GPU memory
  };
}
