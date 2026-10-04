@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run install.bat first.
  pause & exit /b 1
)
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.lnk"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%'); $s.TargetPath='%~dp0.venv\Scripts\pythonw.exe'; $s.Arguments='\"%~dp0jarvis.py\" --startup'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
echo.
echo JARVIS will now start silently in the background every time you sign in to Windows.
echo Start it right now without restarting? (Close any open JARVIS window first.)
pause
start "" ".venv\Scripts\pythonw.exe" "%~dp0jarvis.py"
