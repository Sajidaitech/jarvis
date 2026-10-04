@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ============================================================
echo  JARVIS installer (Python 3.14 supported; 3.11-3.13 also work)
echo ============================================================
if not exist .venv\Scripts\python.exe (
  echo Creating virtual environment...
  py -3.14 -m venv .venv 2>nul || py -3.13 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv
)
if not exist .venv\Scripts\python.exe (
  echo Python was not found. Install Python from python.org and tick "Add python.exe to PATH", then run this again.
  pause & exit /b 1
)
set "PY=%~dp0.venv\Scripts\python.exe"
"%PY%" --version
"%PY%" -m pip install --upgrade pip setuptools wheel

echo Installing packages one by one so a single failure does not stop everything...
if exist failed_packages.txt del failed_packages.txt
for /f "usebackq eol=# tokens=*" %%p in ("requirements.txt") do (
  echo.
  echo --- %%p
  "%PY%" -m pip install --upgrade "%%p" || echo %%p>>failed_packages.txt
)

echo.
echo Downloading the "Hey Jarvis" wake-word model...
"%PY%" -c "import openwakeword; openwakeword.utils.download_models()" || echo WARNING: wake-word model download failed. Re-run this installer with internet access.
echo Downloading the 3D engine for the hologram...
"%PY%" fetch_vendor.py || echo WARNING: 3D engine download failed. The overlay will use the CDN or the classic robot.
echo.
echo Checking that installed packages are compatible with each other...
"%PY%" -m pip check
echo.
if exist failed_packages.txt (
  echo THESE PACKAGES FAILED - send me this list:
  type failed_packages.txt
) else (
  echo All packages installed.
)
echo.
echo SECURITY TIP: put API keys in environment variables, not in jarvis_config.json, e.g.
echo   setx GEMINI_API_KEY "your-key"      (then open a new terminal)
echo.
echo Next: run check_env.bat, then preview_hologram.bat, then run_jarvis.bat
pause
endlocal
