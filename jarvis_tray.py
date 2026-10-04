"""JARVIS Tray: runs JARVIS invisibly from the Windows system tray, so you never open a .bat file again.

  * The tray icon is a small arc reactor that changes colour with JARVIS's state
    (green = listening, amber = thinking/starting, blue = speaking, grey = stopped).
  * Right-click: start/stop JARVIS, open the dashboard, open the log, start with Windows.
  * Double-click the icon: open the dashboard.
  * Watchdog: if JARVIS crashes it is restarted (max 3 times in 10 minutes), with a notification.
Start it from the desktop/Start-menu "JARVIS" shortcut (made by install_tray.bat)."""
import json, os, socket, subprocess, sys, tempfile, threading, time, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
_exe_dir = os.path.dirname(sys.executable)
PYW = os.path.join(_exe_dir, "pythonw.exe") if os.path.exists(os.path.join(_exe_dir, "pythonw.exe")) else sys.executable
STATE = os.path.join(tempfile.gettempdir(), "jarvis_state.txt")
TOKEN_FILE = os.path.join(HERE, "dashboard_token.txt")
ICON_FILE = os.path.join(HERE, "jarvis.ico")
DASH_PORT = 8765
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "JARVIS Tray"
NO_WINDOW, NEW_GROUP = 0x08000000, 0x00000200

COLORS = {"LISTENING": (52, 211, 153), "THINKING": (251, 191, 36), "STARTING": (251, 191, 36),
          "SPEAKING": (56, 189, 248), "ONLINE": (56, 189, 248), "OFFLINE": (110, 125, 140)}


def make_icon(rgb, size=64):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d, c, k = ImageDraw.Draw(img), size / 2, size / 64
    for r, a in ((30, 45), (26, 95)):
        d.ellipse([c - r * k, c - r * k, c + r * k, c + r * k], fill=rgb + (a,))
    d.ellipse([c - 22 * k, c - 22 * k, c + 22 * k, c + 22 * k], fill=(11, 17, 24, 255), outline=rgb + (255,), width=max(2, int(3 * k)))
    d.ellipse([c - 12 * k, c - 12 * k, c + 12 * k, c + 12 * k], outline=rgb + (255,), width=max(2, int(3 * k)))
    d.ellipse([c - 5 * k, c - 5 * k, c + 5 * k, c + 5 * k], fill=rgb + (255,))
    return img


def procs_for(script):
    """Running python processes executing <script> from this folder."""
    import psutil
    found, here = [], os.path.normcase(HERE)
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if p.pid == os.getpid() or "python" not in (p.info["name"] or "").lower():
                continue
            cl = p.info["cmdline"] or []
            for a in cl[1:]:
                if os.path.basename(a).lower() == script:
                    full = os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.join(HERE, script))
                    if full or os.path.normcase(p.cwd()) == here:
                        found.append(p)
                        break
        except Exception:
            continue
    return found


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def read_state():
    try:
        return open(STATE, encoding="utf-8").read().strip() or "ONLINE"
    except OSError:
        return "OFFLINE"


def autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except Exception:
        return False


def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, f'"{PYW}" "{os.path.abspath(__file__)}" --autostart')
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


def make_shortcuts():
    q = lambda s: str(s).replace("'", "''")
    tray = os.path.abspath(__file__)
    ps = ("$s=New-Object -ComObject WScript.Shell;"
          "foreach($d in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))){"
          "$l=$s.CreateShortcut((Join-Path $d 'JARVIS.lnk'));"
          f"$l.TargetPath='{q(PYW)}';$l.Arguments='\"{q(tray)}\"';$l.WorkingDirectory='{q(HERE)}';"
          f"$l.IconLocation='{q(ICON_FILE)}';$l.Description='JARVIS assistant';$l.Save()}}")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, creationflags=NO_WINDOW)


class Tray:
    def __init__(self, autostart_launch=False):
        self.autostart_launch = autostart_launch
        self.want_running = True
        self.running = False
        self.restarts = []
        self.icon = None
        self.last_color = None
        self.last_title = None

    # ---- JARVIS control
    def start_jarvis(self, *_):
        self.want_running = True
        if procs_for("jarvis.py"):
            return
        args = [PYW, os.path.join(HERE, "jarvis.py")] + (["--startup"] if self.autostart_launch else [])
        subprocess.Popen(args, cwd=HERE, creationflags=NO_WINDOW | NEW_GROUP, close_fds=True)

    def stop_jarvis(self, *_):
        self.want_running = False
        ps = procs_for("jarvis.py") + procs_for("overlay.py") + procs_for("overlay_classic.py")
        for p in ps:
            try:
                p.terminate()
            except Exception:
                pass
        try:
            import psutil
            _, alive = psutil.wait_procs(ps, timeout=3)
            for p in alive:
                p.kill()
        except Exception:
            pass
        try:
            open(STATE, "w", encoding="utf-8").write("CLOSE")
        except OSError:
            pass

    # ---- menu actions
    def open_dashboard(self, *_):
        if not port_open(DASH_PORT):
            subprocess.Popen([PYW, os.path.join(HERE, "dashboard.py"), "--no-browser", "--port", str(DASH_PORT)],
                             cwd=HERE, creationflags=NO_WINDOW | NEW_GROUP, close_fds=True)
            for _ in range(30):
                if port_open(DASH_PORT) and os.path.exists(TOKEN_FILE):
                    break
                time.sleep(0.2)
        try:
            tok = open(TOKEN_FILE, encoding="utf-8").read().strip()
        except OSError:
            tok = ""
        webbrowser.open(f"http://127.0.0.1:{DASH_PORT}/?k={tok}")

    def open_log(self, *_):
        p = os.path.join(HERE, "jarvis.log")
        os.startfile(p if os.path.exists(p) else HERE)

    def open_folder(self, *_):
        os.startfile(HERE)

    def toggle_autostart(self, *_):
        try:
            set_autostart(not autostart_enabled())
        except Exception as e:
            self.notify(f"Could not change auto-start: {e}")

    def quit_tray(self, icon, *_):
        icon.stop()

    def quit_and_stop(self, icon, *_):
        self.stop_jarvis()
        icon.stop()

    def notify(self, msg):
        try:
            self.icon.notify(msg, "JARVIS")
        except Exception:
            pass

    # ---- watchdog + icon updates
    def loop(self, icon):
        icon.visible = True
        self.icon = icon
        if self.want_running:
            self.start_jarvis()
        was_running = False
        while getattr(icon, "_running", True) and not getattr(self, "_stop", False):
            self.running = bool(procs_for("jarvis.py"))
            st = read_state() if self.running else "OFFLINE"
            if self.running and st == "CLOSE":
                st = "STARTING"
            if was_running and not self.running and self.want_running:
                if read_state() == "CLOSE":
                    self.want_running = False                      # you said "quit" / goodbye: respect it
                else:
                    now = time.time()
                    self.restarts = [t for t in self.restarts if now - t < 600] + [now]
                    if len(self.restarts) > 3:
                        self.want_running = False
                        self.notify("JARVIS keeps stopping. Open the log from the tray menu to see why.")
                    else:
                        self.notify("JARVIS stopped unexpectedly. Restarting...")
                        self.start_jarvis()
            was_running = self.running
            color = COLORS.get(st, COLORS["ONLINE"])
            title = "JARVIS - " + (st.title() if self.running else "stopped")
            if color != self.last_color:
                icon.icon, self.last_color = make_icon(color), color
            if title != self.last_title:
                icon.title, self.last_title = title, title
            time.sleep(2)

    def run(self):
        import pystray
        from pystray import Menu, MenuItem as Item
        menu = Menu(
            Item(lambda i: self.last_title or "JARVIS", None, enabled=False),
            Menu.SEPARATOR,
            Item("Open dashboard", self.open_dashboard, default=True),
            Item("Start JARVIS", self.start_jarvis, visible=lambda i: not self.running),
            Item("Stop JARVIS", self.stop_jarvis, visible=lambda i: self.running),
            Item("Open log", self.open_log),
            Item("Open JARVIS folder", self.open_folder),
            Menu.SEPARATOR,
            Item("Start with Windows", self.toggle_autostart, checked=lambda i: autostart_enabled()),
            Menu.SEPARATOR,
            Item("Exit tray (JARVIS keeps running)", self.quit_tray),
            Item("Exit and stop JARVIS", self.quit_and_stop),
        )
        icon = pystray.Icon("jarvis", make_icon(COLORS["STARTING"]), "JARVIS", menu)
        icon.run(self.loop)


def main():
    if "--make-icon" in sys.argv:
        make_icon(COLORS["SPEAKING"], 256).save(ICON_FILE, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print("created", ICON_FILE)
        return
    if "--make-shortcuts" in sys.argv:
        make_shortcuts()
        print("Desktop and Start-menu shortcuts created.")
        return
    guard = socket.socket()                                           # only one tray at a time
    try:
        guard.bind(("127.0.0.1", 47654))
    except OSError:
        return
    Tray(autostart_launch="--autostart" in sys.argv).run()


if __name__ == "__main__":
    main()
