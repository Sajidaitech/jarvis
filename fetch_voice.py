"""Downloads the free offline voices: the Piper voice (text-to-speech) and the Whisper model (speech-to-text).
Needs internet once. Safe to re-run. Nothing here is paid.
Upgrades: downloads go to a .part file and are renamed only when complete (a crash can no longer leave a truncated
model that looks valid), the size is checked against Content-Length, retries on network errors, HTTPS only."""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(HERE, "jarvis_config.json"), encoding="utf-8") as f:
        CFG = json.load(f)
except Exception:
    CFG = {}

VOICE = CFG.get("piper_voice", "en_GB-alan-medium")      # e.g. en_GB-alan-medium, en_US-ryan-high
WHISPER = CFG.get("whisper_model", "small")              # tiny, base, small, medium
MIN_ONNX = 1_000_000                                     # a real Piper model is many MB


def get(url, out, retries=3):
    if not url.startswith("https://"):
        raise ValueError("refusing non-HTTPS download: " + url)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    part = out + ".part"
    last = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(part, "wb") as f:
                expected = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
            if expected and got != expected:
                raise IOError(f"incomplete download ({got} of {expected} bytes)")
            os.replace(part, out)                        # atomic: the final name only ever holds a complete file
            return
        except Exception as e:
            last = e
            if os.path.exists(part):
                os.remove(part)
            if attempt < retries:
                print(f"  retry {attempt}/{retries - 1} after error: {e}")
                time.sleep(2 * attempt)
    raise last


def valid(path):
    if path.endswith(".onnx.json"):
        try:
            with open(path, encoding="utf-8") as f:
                json.load(f)
            return True
        except Exception:
            return False
    return os.path.getsize(path) > MIN_ONNX


print(f"1/2  Piper voice: {VOICE}")
try:
    locale, name, quality = VOICE.split("-")
    base = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{locale.split('_')[0]}/{locale}/{name}/{quality}/{VOICE}"
    for ext in (".onnx", ".onnx.json"):
        dst = os.path.join(HERE, "voices", VOICE + ext)
        if os.path.exists(dst) and valid(dst):
            print("  already have", os.path.basename(dst))
            continue
        get(base + ext, dst)
        if not valid(dst):
            os.remove(dst)
            raise IOError(os.path.basename(dst) + " failed validation after download")
        print("  ok  ", os.path.basename(dst))
except Exception as e:
    print("  FAILED:", e, "\n  JARVIS will use the Windows voice until this works.")

print(f"2/2  Whisper speech model: {WHISPER}")
try:
    from faster_whisper import WhisperModel
    WhisperModel(WHISPER, device="cpu", compute_type="int8")
    print("  ok")
except Exception as e:
    print("  FAILED:", e, "\n  JARVIS will use Google speech recognition until this works.")
