"""
JARVIS hologram overlay: an original holographic armored humanoid (3D wireframe,
software-rendered with tkinter, no extra packages). JARVIS starts this when you
say "Hey Jarvis" and closes it when the session ends.

Run `python overlay.py` on its own for a 12-second preview.
"""
import math
import os
import sys
import time
import traceback

W, H = 460, 760
KEY = "#010203"                      # colour made transparent on screen
D = 620.0
F = D * 3.15
CX, CY = W / 2, H / 2 + 6
GLOW, MAIN, MAIN_SPEAK, HI = "#073a5e", "#2ab6ff", "#5fe0ff", "#c8f4ff"


# ------------------------------------------------------------------ 3D model
def box(c, s):
    cx, cy, cz = c
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    return [(cx + a * hx, cy + b * hy, cz + d * hz) for a in (-1, 1) for b in (-1, 1) for d in (-1, 1)]


EDGES = [(i, j) for i in range(8) for j in range(i + 1, 8) if bin(i ^ j).count("1") == 1]
PARTS = []


def add(c, s):
    PARTS.append(box(c, s))


# Front of the figure faces the camera (-z). Units are roughly centimetres, y is up.
add((0, 76, 0), (18, 22, 20))          # head
add((0, 78, -10.8), (12, 3.5, 1.5))    # visor
add((0, 62, 0), (7, 8, 7))             # neck
add((0, 54, 0), (46, 9, 16))           # shoulders
add((0, 39, 0), (34, 22, 19))          # chest
add((0, 40, -10.5), (20, 14, 2))       # chest plate
add((0, 21, 0), (22, 14, 13))          # waist
add((0, 8, 0), (28, 12, 16))           # hips
for s in (-1, 1):
    add((s * 27, 56, 0), (14, 12, 18))   # shoulder armour
    add((s * 29, 40, 0), (9, 26, 9))     # upper arm
    add((s * 29, 14, 0), (8, 26, 8))     # forearm
    add((s * 29, -3, 0), (7, 10, 6))     # hand
    add((s * 8, -12, 0), (12, 34, 12))   # thigh
    add((s * 8, -29, -6), (11, 8, 4))    # knee plate
    add((s * 8, -52, 0), (10, 46, 10))   # shin
    add((s * 8, -81, -4), (11, 10, 24))  # foot

CORE_Y, CORE_Z = 40, -12.5


# ----------------------------------------------------------------- rendering
def mix(a, b, f):
    f = max(0.0, min(1.0, f))
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * f) for x, y in zip(pa, pb))


def render(c, t, state):
    """Draw one frame on a tkinter-style canvas."""
    c.delete("all")
    speaking = state == "SPEAKING"
    main = MAIN_SPEAK if speaking else MAIN
    yaw, pitch = 0.9 * math.sin(t * 0.7), -0.17
    cy_, sy_, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)

    def proj(p):
        x, y, z = p
        x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
        y, z = y * cp - z * sp, y * sp + z * cp
        k = F / (D + z)
        return CX + x * k, CY - y * k

    # HUD corner brackets
    for bx, by, dx, dy in ((14, 14, 1, 1), (W - 14, 14, -1, 1), (14, H - 14, 1, -1), (W - 14, H - 14, -1, -1)):
        c.create_line([bx + dx * 30, by, bx, by, bx, by + dy * 30], fill=main, width=2)

    # rotating floor rings
    for r, spd in ((36, 0.7), (54, -0.45), (70, 0.3)):
        pts = []
        for i in range(61):
            a = i / 60 * 2 * math.pi + t * spd
            pts += proj((r * math.cos(a), -88, r * math.sin(a)))
        c.create_line(pts, fill=GLOW, width=5, dash=(14, 10))
        c.create_line(pts, fill=main, width=1, dash=(14, 10))

    # body wireframe with a scanning highlight sweeping upward
    scan = -90 + (t * 75) % 185
    segs = []
    for verts in PARTS:
        pv = [proj(v) for v in verts]
        for i, j in EDGES:
            hot = abs((verts[i][1] + verts[j][1]) / 2 - scan) < 7
            segs.append(([pv[i][0], pv[i][1], pv[j][0], pv[j][1]], hot))
    for coords, _ in segs:
        c.create_line(coords, fill=GLOW, width=3)
    for coords, hot in segs:
        c.create_line(coords, fill=HI if hot else main, width=1)
    sy = proj((0, scan, 0))[1]
    c.create_line([CX - 135, sy, CX + 135, sy], fill=mix(main, KEY, 0.45), width=1)

    # chest core
    pulse = 1 + (0.35 * abs(math.sin(t * 11)) if speaking else 0.12 * math.sin(t * 3))
    ccx, ccy = proj((0, CORE_Y, CORE_Z))
    for rad, col, w in ((7 * pulse, HI, 2), (3.8 * pulse, HI, 2)):
        pts = []
        for i in range(25):
            a = i / 24 * 2 * math.pi
            pts += proj((rad * math.cos(a), CORE_Y + rad * math.sin(a), CORE_Z))
        c.create_line(pts, fill=col, width=w)
    c.create_oval(ccx - 24 * pulse, ccy - 24 * pulse, ccx + 24 * pulse, ccy + 24 * pulse,
                  outline=mix(main, KEY, 0.5), width=1)
    if speaking:  # expanding voice rings
        for k in range(3):
            r = (t * 70 + k * 30) % 90 + 20
            c.create_oval(ccx - r, ccy - r, ccx + r, ccy + r, outline=mix(main, KEY, 0.3 + r / 130), width=1)

    # text
    label = {"SPEAKING": "RESPONDING", "THINKING": "PROCESSING", "LISTENING": "LISTENING"}.get(state, "ONLINE")
    c.create_text(W / 2, 32, text="J . A . R . V . I . S", font=("Consolas", 17, "bold"), fill=HI)
    c.create_text(W / 2, 58, text=f"[ {label} ]", font=("Consolas", 11), fill=main)
    left = (f"CORE  {int(97 + 2 * math.sin(t))}%", "POWER STABLE", "LINK SECURE")
    right = ("VOICE ACTIVE" if speaking else "VOICE IDLE", time.strftime("%H:%M:%S"), "SYS NOMINAL")
    for n in range(3):
        c.create_text(22, 130 + n * 22, text=left[n], font=("Consolas", 9), fill=main, anchor="w")
        c.create_text(W - 22, 130 + n * 22, text=right[n], font=("Consolas", 9), fill=main, anchor="e")


# ------------------------------------------------------------------- window
def run(state_file):
    import ctypes
    import tkinter as tk

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)
    root.configure(bg=KEY)
    root.attributes("-transparentcolor", KEY)
    x = root.winfo_screenwidth() - W - 30
    y = max(0, root.winfo_screenheight() - H - 60)
    root.geometry(f"{W}x{H}+{x}+{y}")
    canvas = tk.Canvas(root, width=W, height=H, bg=KEY, highlightthickness=0)
    canvas.pack()
    root.update()
    try:  # click-through, no taskbar button, never steals focus
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20 | 0x80 | 0x08000000)
    except Exception:
        pass

    t0 = time.time()
    st = {"state": "LISTENING", "closing": None, "last": 0.0}

    def frame():
        t = time.time() - t0
        if t - st["last"] > 0.25:
            st["last"] = t
            if state_file:
                try:
                    st["state"] = open(state_file).read().strip() or "ONLINE"
                    stale = time.time() - os.path.getmtime(state_file) > 90
                except OSError:
                    st["state"], stale = "CLOSE", False
                if st["state"] == "CLOSE" or stale or t > 900:
                    st["closing"] = st["closing"] or t
            else:  # preview mode
                st["state"] = "SPEAKING" if int(t) % 6 >= 3 else "LISTENING"
                if t > 12:
                    st["closing"] = st["closing"] or t
        alpha = min(1.0, t / 0.5) * 0.93
        if st["closing"] is not None:
            left = 1 - (t - st["closing"]) / 0.4
            if left <= 0:
                root.destroy()
                return
            alpha *= left
        root.attributes("-alpha", alpha)
        render(canvas, t, "ONLINE" if st["state"] == "CLOSE" else st["state"])
        root.after(40, frame)

    frame()
    root.mainloop()


if __name__ == "__main__":
    try:
        run(sys.argv[1] if len(sys.argv) > 1 else "")
    except Exception:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "overlay.log"), "a") as f:
            traceback.print_exc(file=f)
