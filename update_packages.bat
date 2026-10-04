@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run install.bat first.
  pause & exit /b 1
)
set "PY=%~dp0.venv\Scripts\python.exe"
"%PY%" -m pip install --upgrade pip || goto :fail
"%PY%" -m pip install --upgrade pillow "numpy>=2.3" "pythonnet>=3.1.0" "pywebview>=5.0" || goto :fail
"%PY%" fetch_vendor.py || goto :fail
"%PY%" -m pip check
echo.
echo Done. Run check_env.bat, then preview_hologram.bat.
pause
exit /b 0
:fail
echo.
echo ERROR: an update step failed. Nothing else was changed. Send me the messages above.
pause
exit /b 1
