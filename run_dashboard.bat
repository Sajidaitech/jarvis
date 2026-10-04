@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run install.bat first.
  pause
  exit /b 1
)
echo Starting the JARVIS dashboard. Keep this window open; close it to stop.
.venv\Scripts\python.exe dashboard.py
pause
