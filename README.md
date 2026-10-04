# JARVIS for Windows 11

Say **"Hey Jarvis"** -> JARVIS answers -> speak commands back to back -> say **"exit"** (or stay silent ~8 s) to return to standby.
JARVIS runs in the background and listens for its own wake word, with no Siri or Cortana involved.

## Install (once)
1. Install Python 3.11 or 3.12 from python.org (tick "Add python.exe to PATH").
2. Double-click `install.bat` (creates a virtual environment, installs packages, downloads the wake-word model).
3. Windows Settings -> Privacy & security -> Microphone -> allow microphone access, including "Let desktop apps access your microphone".
4. Edit `jarvis_config.json`: add your contacts, emergency contact and number, and optionally your latitude/longitude/city.
5. Double-click `run_jarvis.bat`, then say "Hey Jarvis". Try `run_jarvis.bat --text` first to test without a microphone.

## Start automatically with Windows
Double-click `install_autostart.bat`. JARVIS then starts silently when you sign in (after a 20 s delay so audio/network are ready).
`remove_autostart.bat` undoes it, and `stop_jarvis.bat` stops the background copy. Errors go to `jarvis.log`.

## Connect Claude
1. Create an API key at console.anthropic.com (API usage is billed separately from a claude.ai subscription).
2. Paste it into `anthropic_api_key` in `jarvis_config.json` (or set the ANTHROPIC_API_KEY environment variable).
3. Say "Claude, <question>" or just ask anything JARVIS has no built-in command for. Keep the key private.

## Commands (say them naturally)
status, battery, play/pause/resume/next/previous music, driving mode, work mode, morning briefing, night mode,
navigate to <place>, weather, calendar, call <contact>, message, WhatsApp, camera, YouTube, open <app>, emergency, exit, quit.

## Honest limits
- Speech-to-text uses Google's free web recognizer, so it needs internet. The wake word itself runs offline.
- Pause and Resume both send Windows' play/pause key. Windows can't tell JARVIS whether music is playing.
- Calendar needs classic Outlook (not "new Outlook"). Otherwise JARVIS says calendar access is unavailable.
- Weather location comes from your IP address (approximate) unless you set coordinates in the config.
- Calls go through the `tel:` handler (Phone Link, if paired). Messages open a prefilled WhatsApp chat; you press Enter to send.
- Night mode lowers brightness only. Windows has no reliable switch for Do Not Disturb or Night Light.
- Brightness control works on laptop screens and many monitors, not all desktop monitors.
- Open Apple Music, Teams, etc. are found through Start-menu app names. If one isn't installed, JARVIS says so and moves on.

## Hologram
When you say "Hey Jarvis", a realistic holographic humanoid (an original design) appears at the bottom-right of your screen:
glowing scan-layer contours, see-through blue glow, flicker, a projector base and floating particles. It is click-through
and never steals focus. It changes while JARVIS listens, thinks and speaks, and fades out when the session ends.
- First run `update_packages.bat` once (installs Pillow). Without it JARVIS falls back to a simple wireframe figure.
- Preview any time with `preview_hologram.bat` (12 seconds, no microphone needed).
- Turn it off with `"show_overlay": false` in `jarvis_config.json`.
- `overlay.log` records which display mode started ("per-pixel alpha" is the good one) and any errors.
