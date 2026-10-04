@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem ---- SECURITY: put a commit SHA you have reviewed here. Empty = you will be asked to accept the latest, unreviewed code.
set "ODYSSEUS_COMMIT="
set "REPO_URL=https://github.com/odysseus-dev/odysseus.git"

where git >nul 2>nul || (echo Install Git for Windows first: https://git-scm.com & pause & exit /b 1)
where docker >nul 2>nul || (echo Install Docker Desktop first: https://www.docker.com & pause & exit /b 1)

if "%ODYSSEUS_COMMIT%"=="" (
  echo WARNING: no pinned commit. This would run the newest code from the repository without review.
  set /p OK=Type YES to continue anyway, anything else to stop: 
  if /I not "%OK%"=="YES" exit /b 1
)

if not exist odysseus\.git git clone "%REPO_URL%" odysseus || (echo Clone failed. & pause & exit /b 1)
cd odysseus

if not "%ODYSSEUS_COMMIT%"=="" (
  git fetch --force origin "%ODYSSEUS_COMMIT%" || (echo Could not fetch that commit. & pause & exit /b 1)
  git checkout --detach "%ODYSSEUS_COMMIT%" || exit /b 1
  for /f "delims=" %%A in ('git rev-parse HEAD') do set "ACTUAL=%%A"
  if /I not "%ACTUAL%"=="%ODYSSEUS_COMMIT%" (echo Commit mismatch: %ACTUAL% & pause & exit /b 1)
  echo Pinned to %ACTUAL%
)

if not exist .env (
  copy .env.example .env >nul
  echo Created .env from .env.example. Open it and review every value before continuing.
)

rem ---- SECURITY: refuse to start unless port 7000 is published on 127.0.0.1 only (Compose prints it as host_ip).
docker compose config 2>nul | findstr /C:"host_ip: 127.0.0.1" >nul
if errorlevel 1 (
  echo.
  echo STOPPED: the Compose file does not bind Odysseus to 127.0.0.1, so it could be reachable from your network.
  echo Edit its "ports:" entry to  "127.0.0.1:7000:7000"  and run this script again.
  pause & exit /b 1
)

docker compose up -d --build || (echo Odysseus failed to start. & pause & exit /b 1)
echo.
echo Odysseus: http://127.0.0.1:7000   (user: admin)
echo The first admin password is NOT printed here on purpose. Read it yourself with:
echo    cd odysseus ^&^& docker compose logs odysseus ^| findstr /i "temporary password"
echo then log in and change it immediately.
echo.
echo In Odysseus Settings add Ollama: http://host.docker.internal:11434/v1
pause
endlocal
