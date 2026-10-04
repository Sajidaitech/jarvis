@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run install.bat first.
  pause
  exit /b 1
)
set "PY=%~dp0.venv\Scripts\python.exe"
set "PYW=%~dp0.venv\Scripts\pythonw.exe"
echo Installing the tray packages...
"%PY%" -m pip install pystray psutil pillow || goto :fail
"%PY%" jarvis_tray.py --make-icon || goto :fail
"%PY%" jarvis_tray.py --make-shortcuts || goto :fail
echo.
echo Done. A "JARVIS" shortcut is now on your Desktop and in the Start menu.
echo Starting JARVIS in the system tray (look near the clock, click ^^ if hidden)...
start "" "%PYW%" "%~dp0jarvis_tray.py"
echo.
echo Right-click the tray icon and tick "Start with Windows" so it starts by itself after every restart.
pause
exit /b 0
:fail
echo.
echo ERROR: something failed above. Send me the messages.
pause
exit /b 1
