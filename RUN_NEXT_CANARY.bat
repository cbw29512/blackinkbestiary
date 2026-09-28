@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_next_canary.ps1"
if errorlevel 1 (
  echo.
  echo One-at-a-time Canary calibration stopped with an error.
  pause
  exit /b 1
)
exit /b 0
