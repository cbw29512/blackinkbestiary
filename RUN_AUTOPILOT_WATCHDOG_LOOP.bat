@echo off
setlocal EnableExtensions
cd /d "%~dp0"

:WATCH
call "%~dp0WATCHDOG_AUTOPILOT.bat"
timeout /t 300 /nobreak >nul
goto WATCH
