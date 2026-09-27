@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0START_STATUS_DASHBOARD_IF_NEEDED.bat"
if errorlevel 1 (
  echo Canary gallery could not start. Check data\dashboard-runtime-status.json
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8765/autopilot-status.html#canaries"
exit /b 0
