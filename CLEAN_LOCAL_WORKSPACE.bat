@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\clean_local_workspace.ps1"
if errorlevel 1 (
  echo.
  echo Cleanup stopped before protected project state could be removed.
  pause
  exit /b 1
)
echo.
echo Cleanup complete. Current canary images, review decisions, models, and approved art were preserved.
pause
