@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run install.bat first.
  pause & exit /b 1
)
echo Starting the 3D hologram preview (12 seconds)...
.venv\Scripts\python.exe overlay.py --verbose
echo.
echo ---- overlay.log (last lines) ----
powershell -NoProfile -Command "if (Test-Path overlay.log) { Get-Content overlay.log -Tail 25 }"
pause
