"""
JARVIS 3D hologram overlay for Windows 11 (realistic humanoid, rendered with three.js in a WebView2 window).

Same contract as the old overlay: `python overlay.py <state_file>` is started by JARVIS on "Hey Jarvis" and closes when the
state file says CLOSE (or goes stale). `python overlay.py` alone = 12-second preview.
Engines, tried in order (override with "overlay_engine" in jarvis_config.json: "auto" | "webview" | "browser"):
  1. pywebview (frameless, always-on-top, click-through)
  2. Microsoft Edge / Chrome in app mode (no extra Python packages; works on Python 3.14)
The old wireframe robot is only used if you set "overlay_style": "wireframe".
Run with --verbose (preview_hologram.bat does) to see exactly why an engine failed.
"""
import functools
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
LOG = os.path.join(HERE, "overlay.log")
TITLE = "JARVIS Hologram"
W, H = 460, 760
THREE_VER = "0.160.0"


VERBOSE = "--verbose" in sys.argv


def log(msg):
    if VERBOSE:
        print(msg, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + str(msg) + "\n")
    except OSError:
        pass


def load_config():
    try:
        with open(os.path.join(HERE, "jarvis_config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class Session:
    """Decides what state the page should show and when to close."""

    def __init__(self, state_file):
        self.state_file, self.t0 = state_file, time.time()

    def read(self):
        t = time.time() - self.t0
        if not self.state_file:                                   # preview
            return {"state": "SPEAKING" if int(t) % 6 >= 3 else "LISTENING", "close": t > 12}
        try:
            st = open(self.state_file, encoding="utf-8").read().strip() or "ONLINE"
            stale = time.time() - os.path.getmtime(self.state_file) > 90
        except OSError:
            return {"state": "CLOSE", "close": True}
        return {"state": st, "close": st == "CLOSE" or stale or t > 900}


def importmap():
    vend = os.path.join(WEB, "vendor", "three.module.js")
    if os.path.exists(vend):
        m = {"three": "/vendor/three.module.js", "three/addons/": "/vendor/addons/"}
    else:
        base = f"https://cdn.jsdelivr.net/npm/three@{THREE_VER}"
        m = {"three": f"{base}/build/three.module.js", "three/addons/": f"{base}/examples/jsm/"}
    return '<script type="importmap">' + json.dumps({"imports": m}) + "</script>"


def make_handler(session, style, flip=False):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _send(self, body, ctype, code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if (self.headers.get("Host") or "").split(":")[0] not in ("127.0.0.1", "localhost"):
                return self._send(b"forbidden", "text/plain", 403)     # only our own window may talk to this server
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
                html = html.replace("<!--IMPORTMAP-->", importmap()).replace("<!--STYLE-->", style)
                html = html.replace("<!--FLAGS-->", "<script>window.PHOTO_FLIP=%s</script>" % ("true" if flip else "false"))
                return self._send(html.encode("utf-8"), "text/html; charset=utf-8")
            if u.path == "/state":
                return self._send(json.dumps(session.read()).encode(), "application/json")
            if u.path == "/log":
                log("page: " + parse_qs(u.query).get("m", [""])[0])
                return self._send(b"ok", "text/plain")
            return super().do_GET()

        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                          ".js": "text/javascript", ".mjs": "text/javascript", ".glb": "model/gltf-binary"}

    return functools.partial(Handler, directory=WEB)


class Quiet(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def start_server(session, style, flip=False):
    srv = Quiet(("127.0.0.1", 0), make_handler(session, style, flip))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def sweep_old_profiles(max_age=3600):
    """Remove leftover browser profiles from crashed runs (they can be tens of MB each)."""
    try:
        root = tempfile.gettempdir()
        for n in os.listdir(root):
            p = os.path.join(root, n)
            if n.startswith("jarvis_overlay_") and os.path.isdir(p) and time.time() - os.path.getmtime(p) > max_age:
                shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass


def click_through(title):
    """Make the window click-through, hidden from the taskbar and never focus-stealing."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    hwnd = u.FindWindowW(None, title)
    if not hwnd:
        return False
    top = 0x80000 | 0x20 | 0x80 | 0x08000000      # LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
    child = 0x20 | 0x08000000

    def apply(h, flags):
        u.SetWindowLongW(h, -20, u.GetWindowLongW(h, -20) | flags)

    apply(hwnd, top)
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    cb = proc(lambda h, _l: (apply(h, child) or True))
    u.EnumChildWindows(hwnd, cb, 0)
    return True


def pick_style(cfg):
    style = "card" if str(cfg.get("overlay_style", "transparent")).lower() == "card" else "transparent"
    has_glb = os.path.exists(os.path.join(WEB, "models", "jarvis.glb"))
    if not has_glb and os.path.exists(os.path.join(WEB, "models", "jarvis_portrait.jpg")):
        style = "card"                               # the portrait image has its own background, so it cannot be see-through
    return style


def run_webview(state_file, cfg):
    import webview                                  # pywebview (needs pythonnet 3.1+ on Python 3.14)
    style = pick_style(cfg)
    session = Session(state_file)
    srv = start_server(session, style, bool(cfg.get("photo_flip", False)))
    url = f"http://127.0.0.1:{srv.server_address[1]}/"

    import ctypes
    sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    scale = 1.0
    try:
        scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100.0
    except Exception:
        pass
    x, y = int(sw / scale) - W - 30, max(0, int(sh / scale) - H - 60)

    kw = dict(url=url, width=W, height=H, x=x, y=y, frameless=True, on_top=True, easy_drag=False,
              resizable=False, transparent=(style == "transparent"), shadow=False)
    while True:                                      # drop options this pywebview version does not know
        try:
            window = webview.create_window(TITLE, **kw)
            break
        except TypeError as e:
            bad = next((k for k in list(kw) if f"'{k}'" in str(e)), None)
            if not bad or bad in ("url", "width", "height"):
                raise
            kw.pop(bad)

    closed = threading.Event()
    try:
        window.events.closed += closed.set           # window closed by hand -> let the worker exit
    except Exception:
        pass

    def worker():
        for delay in (0.8, 1.5, 3.0):                # WebView2 child windows appear late
            time.sleep(delay)
            try:
                click_through(TITLE)
            except Exception:
                log("click-through failed:\n" + traceback.format_exc())
        while not closed.is_set():
            time.sleep(0.3)
            if session.read()["close"]:
                try:
                    window.evaluate_js("window.jarvisClose && window.jarvisClose()")
                except Exception:
                    pass
                time.sleep(0.6)
                window.destroy()
                return

    log(f"[pywebview] starting ({style}) {url}")
    try:
        webview.start(worker)
    finally:
        srv.shutdown()
    log("[pywebview] window closed")


def find_browser():
    pf = [os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""), os.environ.get("LocalAppData", "")]
    rels = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"]
    for rel in rels:
        for base in pf:
            p = os.path.join(base, rel) if base else ""
            if p and os.path.exists(p):
                return p
    return shutil.which("msedge") or shutil.which("chrome")


def find_window(prefix):
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    found = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _l):
        n = u.GetWindowTextLengthW(h)
        if n and u.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, buf, n + 1)
            if buf.value.startswith(prefix):
                found.append(h)
        return True

    u.EnumWindows(proc(cb), 0)
    return found[0] if found else 0


def run_browser(state_file, cfg):
    """Edge/Chrome app window, then placed bottom-right, always on top, click-through, hidden from the taskbar."""
    import ctypes
    exe = find_browser()
    if not exe:
        raise RuntimeError("Microsoft Edge / Chrome not found")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    sweep_old_profiles()
    session = Session(state_file)
    srv = start_server(session, "card", bool(cfg.get("photo_flip", False)))
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    profile = tempfile.mkdtemp(prefix="jarvis_overlay_")
    args = [exe, f"--app={url}", f"--window-size={W},{H}", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", "--disable-sync", "--disable-features=Translate",
            "--autoplay-policy=no-user-gesture-required"]
    log(f"[browser] starting {exe}")
    proc = subprocess.Popen(args)
    u = ctypes.windll.user32
    try:
        hwnd = 0
        for _ in range(60):                          # up to ~12 s for the window to appear
            time.sleep(0.2)
            hwnd = find_window(TITLE)
            if hwnd or proc.poll() is not None:
                break
        if not hwnd:
            raise RuntimeError("overlay window did not appear")
        try:
            scale = u.GetDpiForWindow(hwnd) / 96.0
        except Exception:
            scale = 1.0
        w, h = int(W * scale), int(H * scale)
        x, y = u.GetSystemMetrics(0) - w - int(30 * scale), max(0, u.GetSystemMetrics(1) - h - int(60 * scale))
        u.SetWindowPos(hwnd, -1, x, y, w, h, 0x10 | 0x40)         # TOPMOST, NOACTIVATE, SHOWWINDOW
        for delay in (0.3, 1.0, 2.5):
            time.sleep(delay)
            try:
                click_through(TITLE)
            except Exception:
                log("click-through failed:\n" + traceback.format_exc())
        while proc.poll() is None and not session.read()["close"]:
            time.sleep(0.3)
        log("[browser] closing")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, creationflags=0x08000000)
        srv.shutdown()
        shutil.rmtree(profile, ignore_errors=True)


def run_wireframe(state_file):
    sys.path.insert(0, HERE)
    import overlay_wireframe_old
    overlay_wireframe_old.run(state_file)


def run(state_file):
    cfg = load_config()
    engine = str(cfg.get("overlay_engine", "auto")).lower()
    if str(cfg.get("overlay_style", "")).lower() == "wireframe":
        return run_wireframe(state_file)
    engines = {"webview": [run_webview], "browser": [run_browser]}.get(engine, [run_webview, run_browser])
    for fn in engines:
        try:
            fn(state_file, cfg)
            return
        except ImportError as e:
            log(f"{fn.__name__} skipped (package missing: {e}). Trying the next engine.")
        except Exception:
            log(f"3D overlay engine {fn.__name__} failed:\n" + traceback.format_exc())
    log("No 3D overlay engine worked. See the errors above. Set \"overlay_style\": \"wireframe\" to use the old robot.")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(args[0] if args else "")


if __name__ == "__main__":
    main()
