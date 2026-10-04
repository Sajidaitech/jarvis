"""Downloads three.js into web/vendor so the hologram works without internet. Safe to re-run."""
import os, sys, urllib.request
V = "0.160.0"
BASE = f"https://cdn.jsdelivr.net/npm/three@{V}/"
FILES = {
    "build/three.module.js": "three.module.js",
    "examples/jsm/environments/RoomEnvironment.js": "addons/environments/RoomEnvironment.js",
    "examples/jsm/loaders/GLTFLoader.js": "addons/loaders/GLTFLoader.js",
    "examples/jsm/utils/BufferGeometryUtils.js": "addons/utils/BufferGeometryUtils.js",
}
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "vendor")
ok = True
for src, dst in FILES.items():
    out = os.path.join(root, dst)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        with urllib.request.urlopen(BASE + src, timeout=30) as r, open(out, "wb") as f:
            f.write(r.read())
        print("ok  ", dst)
    except Exception as e:
        ok = False; print("FAIL", dst, e)
if not ok:
    print("Some files failed. The overlay will load three.js from the internet instead.")
    for dst in FILES.values():
        p = os.path.join(root, dst)
        if dst == "three.module.js" and os.path.exists(p) and os.path.getsize(p) < 1000: os.remove(p)
