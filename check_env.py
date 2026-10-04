"""Environment check for JARVIS: Python version, every package, and a real microphone frame test."""
import importlib
import importlib.metadata as md
import queue
import sys
import time

print("Python", sys.version.split()[0], "|", sys.executable, "\n")
MODS = [("numpy", "numpy"), ("onnxruntime", "onnxruntime"), ("openwakeword", "openwakeword"), ("sounddevice", "sounddevice"),
        ("speech_recognition", "SpeechRecognition"), ("pyttsx3", "pyttsx3"), ("psutil", "psutil"), ("requests", "requests"),
        ("screen_brightness_control", "screen-brightness-control"), ("pycaw.pycaw", "pycaw"), ("comtypes", "comtypes"),
        ("win32api", "pywin32"), ("PIL", "pillow"), ("clr", "pythonnet"), ("webview", "pywebview"),
        ("faster_whisper", "faster-whisper"), ("piper", "piper-tts")]
bad = []
for mod, pkg in MODS:
    try:
        importlib.import_module(mod)
        try:
            v = md.version(pkg)
        except Exception:
            v = "?"
        print(f"  OK    {pkg:28s} {v}")
    except Exception as e:
        bad.append(pkg)
        print(f"  FAIL  {pkg:28s} {type(e).__name__}: {str(e)[:90]}")
print("\nMissing/broken:", ", ".join(bad) if bad else "none")
if "pywebview" in bad or "pythonnet" in bad:
    print("  -> The 3D hologram needs pywebview + pythonnet 3.1+. Without them JARVIS uses the classic wireframe overlay.")

# Microphone test: do audio frames actually arrive? (This is what failed in jarvis.log: queue.Empty in calibrate_noise.)
print("\n--- Microphone ---")
try:
    import numpy as np
    import sounddevice as sd

    def test(dev, secs=1.5):
        q = queue.Queue()
        try:
            with sd.InputStream(device=dev, samplerate=16000, channels=1, dtype="int16", blocksize=1280,
                                callback=lambda d, f, t, s: q.put(d[:, 0].copy())):
                end, n, peak = time.time() + secs, 0, 0.0
                while time.time() < end:
                    try:
                        fr = q.get(timeout=0.5)
                        n += 1
                        peak = max(peak, float(np.sqrt(np.mean(fr.astype(np.float32) ** 2))))
                    except queue.Empty:
                        pass
                return n, peak, None
        except Exception as e:
            return 0, 0.0, f"{type(e).__name__}: {e}"

    default = sd.default.device[0]
    devs = [(i, d) for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]
    print("Default input device index:", default)
    working = []
    for i, d in devs[:12]:
        n, peak, err = test(i)
        tag = "DEFAULT" if i == default else ""
        status = f"{n} frames, peak level {peak:.0f}" if not err else f"ERROR {err[:80]}"
        print(f"  [{i}] {d['name'][:44]:44s} {d['hostapi']!s:2} {tag:8s} {status}")
        if n > 0:
            working.append(i)
    if default in working:
        print("\nThe default microphone delivers audio. If JARVIS still fails, tell me and send jarvis.log.")
    elif working:
        print(f"\nDefault mic gives NO frames, but device(s) {working} work. Set one as the Windows default input"
              " (Settings > System > Sound > Input), or tell me the number and I will add an input_device option.")
    else:
        print("\nNo microphone delivers audio. Check Settings > Privacy & security > Microphone (allow desktop apps),"
              " the default input device, and that no app holds the mic in exclusive mode.")
except Exception as e:
    print("Microphone test could not run:", type(e).__name__, e)


# ---- Security check of jarvis_config.json
print("\n--- Security ---")
try:
    import json, os
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = json.load(open(os.path.join(here, "jarvis_config.json"), encoding="utf-8"))
    warn = 0
    for k in ("gemini_api_key", "anthropic_api_key", "openai_api_key", "local_api_key"):
        if cfg.get(k):
            warn += 1
            print(f"  WARN  {k} is stored in plain text in jarvis_config.json. Use an environment variable instead (setx).")
    if cfg.get("agent_mode", "smart") not in ("smart", "always", "off"):
        warn += 1
        print("  WARN  agent_mode must be smart, always or off.")
    for k in ("odysseus_url", "local_base_url"):
        u = str(cfg.get(k) or "")
        if u and not any(h in u for h in ("localhost", "127.0.0.1")):
            warn += 1
            print(f"  WARN  {k} points away from this PC: {u}")
    for fn in ("jarvis_config.json", "jarvis_memory.json"):
        pth = os.path.join(here, fn)
        if os.path.exists(pth):
            print(f"  note  {fn} is readable by anyone who can open your user folder; keep the folder private and out of cloud sync/Git.")
    print("  Security settings look fine." if not warn else f"  {warn} warning(s) above.")
except Exception as e:
    print("Security check could not run:", type(e).__name__, e)
