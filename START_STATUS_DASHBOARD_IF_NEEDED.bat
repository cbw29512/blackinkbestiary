@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ensure_status_dashboard.ps1"
exit /b %ERRORLEVEL%
