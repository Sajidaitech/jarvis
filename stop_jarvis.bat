@echo off
powershell -NoProfile -Command "Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force"
echo Background JARVIS stopped.
pause
