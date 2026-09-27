@echo off
setlocal EnableExtensions
cd /d "%~dp0"

call "%~dp0START_STATUS_DASHBOARD_IF_NEEDED.bat"

echo Checking Black-Ink Bestiary autopilot health...
call "%~dp0WATCHDOG_AUTOPILOT.bat"
if errorlevel 1 (
  echo Autopilot watchdog check failed.
  exit /b 1
)

powershell -NoProfile -Command "$running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'RUN_AUTOPILOT_WATCHDOG_LOOP\.bat' }; if ($running) { exit 0 } else { exit 1 }"
if not errorlevel 1 (
  echo Black-Ink Bestiary watchdog is already running.
  exit /b 0
)

echo Starting Black-Ink Bestiary watchdog loop...
start "Black Ink Bestiary Watchdog" /min cmd /c call "%~dp0RUN_AUTOPILOT_WATCHDOG_LOOP.bat"
exit /b 0
