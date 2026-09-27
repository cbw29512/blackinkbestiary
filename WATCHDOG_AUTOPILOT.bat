@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\watchdog_autopilot.ps1"
exit /b %ERRORLEVEL%
