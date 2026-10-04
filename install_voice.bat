@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run install.bat first.
  pause & exit /b 1
)
set "PY=%~dp0.venv\Scripts\python.exe"
if exist requirements_voice.lock (
  echo Installing free offline voice packages from the hash-pinned lock file...
  "%PY%" -m pip install --require-hashes -r requirements_voice.lock || goto :fail
) else (
  echo Installing free offline voice packages...
  echo ^(Tip: for supply-chain safety, create requirements_voice.lock with:
  echo    python -m pip install pip-tools ^& python -m piptools compile --generate-hashes requirements_voice.txt -o requirements_voice.lock^)
  "%PY%" -m pip install --upgrade -r requirements_voice.txt || goto :fail
)
echo.
echo Downloading the voice and speech models (one time, needs internet)...
"%PY%" fetch_voice.py || goto :fail
echo.
echo Done. Run run_jarvis.bat and read the first log lines: you should see
echo   [tts] Piper voice: ...    and    [stt] Whisper ready
pause
exit /b 0
:fail
echo.
echo ERROR: something failed above. Fix it and run this again.
pause
exit /b 1
