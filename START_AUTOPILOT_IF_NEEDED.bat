@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -Command "$running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'RUN_ENGINE_AUTOPILOT\\.bat' }; if ($running) { exit 0 } else { exit 1 }"
if not errorlevel 1 (
  echo Black-Ink Bestiary autopilot is already running.
  exit /b 0
)

echo Starting Black-Ink Bestiary autopilot...
start "Black Ink Bestiary Autopilot" /min cmd /c call "%~dp0RUN_ENGINE_AUTOPILOT.bat"
exit /b 0
