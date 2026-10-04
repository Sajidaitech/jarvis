"""Compatibility wrapper: JARVIS (or an old shortcut) may still start overlay_classic.py. It now opens the 3D overlay.
The old wireframe robot lives in overlay_wireframe_old.py (enable with "overlay_style": "wireframe")."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlay

run = overlay.run

if __name__ == "__main__":
    overlay.main()
