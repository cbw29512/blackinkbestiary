@echo off
setlocal EnableExtensions
cd /d "%~dp0"

:WATCH
call "%~dp0START_STATUS_DASHBOARD_IF_NEEDED.bat" >nul 2>&1
call "%~dp0WATCHDOG_AUTOPILOT.bat"
timeout /t 300 /nobreak >nul
goto WATCH
