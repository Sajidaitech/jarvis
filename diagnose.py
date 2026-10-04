"""Shows your microphone level and the live 'Hey Jarvis' score for 15 seconds."""
import json, os, queue, sys, time
import numpy as np
import sounddevice as sd

try:  # use the same microphone JARVIS uses ("input_device" in jarvis_config.json)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json"), encoding="utf-8") as _f:
        _cfg = json.load(_f)
except Exception:
    _cfg = {}
DEV = _cfg.get("input_device")
if DEV == "":
    DEV = None
THRESH = float(_cfg.get("wake_threshold", 0.5))

try:
    print("Microphone:", sd.query_devices(DEV, "input")["name"], "(from jarvis_config.json)" if DEV is not None else "(Windows default)")
except Exception as e:
    sys.exit(f"Cannot open microphone {DEV!r}: {e}\nRun check_env.bat to list working devices.")
try:
    from openwakeword.model import Model
    model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
except Exception as e:
    sys.exit(f"Wake-word model failed to load: {e}\nRe-run install.bat to download it.")

q = queue.Queue(maxsize=100)
def cb(d, f, t, s):
    try:
        q.put_nowait(d[:, 0].copy())
    except queue.Full:
        pass

with sd.InputStream(device=DEV, samplerate=16000, channels=1, dtype="int16", blocksize=1280, callback=cb):
    print("\nSay 'Hey Jarvis' clearly a few times now (15 seconds)...\n")
    end, last, best, loudest, frames = time.time() + 15, 0, 0.0, 0.0, 0
    while time.time() < end:
        try:
            f = q.get(timeout=1.0)
        except queue.Empty:
            continue
        frames += 1
        score = max(model.predict(f).values())
        rms = float(np.sqrt(np.mean(f.astype(np.float32) ** 2)))
        best, loudest = max(best, score), max(loudest, rms)
        if time.time() - last > 0.4:
            print(f"mic {'#' * min(40, int(rms / 100)):<40} {int(rms):5d}   wake score {score:.2f}   best {best:.2f}")
            last = time.time()

print("\n--- RESULT ---")
if frames == 0:
    print("No audio frames arrived at all. Wrong device or the microphone is blocked. Run check_env.bat.")
elif loudest < 150:
    print("The microphone is almost silent. Wrong microphone selected or access blocked.")
    print("Check Settings > System > Sound > Input, and Privacy & security > Microphone.")
elif best >= THRESH:
    print(f"Wake word works (best {best:.2f}, threshold {THRESH}). The problem is that JARVIS isn't running, or a command step failed.")
elif best >= 0.15:
    print(f"It hears you but the score is low (best {best:.2f}). Set \"wake_threshold\" to 0.3 in jarvis_config.json.")
else:
    print(f"The mic works but the phrase isn't recognized (best {best:.2f}). Speak closer and clearer, or try another microphone.")
