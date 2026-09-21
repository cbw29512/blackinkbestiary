@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install_blackink_ai.ps1"
echo.
pause
