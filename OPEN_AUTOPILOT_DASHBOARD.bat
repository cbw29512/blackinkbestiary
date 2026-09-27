@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0START_STATUS_DASHBOARD_IF_NEEDED.bat"
start "" "http://127.0.0.1:8765/autopilot-status.html"
exit /b 0
