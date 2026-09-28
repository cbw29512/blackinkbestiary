@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0START_STATUS_DASHBOARD_IF_NEEDED.bat"
if errorlevel 1 (
  echo.
  echo Black Ink Bestiary Review Studio could not start.
  echo Check data\dashboard-runtime-status.json and data\dashboard-runtime.stderr.log
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8765/human-review.html"
exit /b 0
