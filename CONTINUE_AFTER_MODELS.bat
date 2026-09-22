@echo off
setlocal
cd /d "%~dp0"
title Black-Ink Bestiary - Continue After Models
cls
echo Black-Ink Bestiary - Continue After Models
echo ==========================================
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\continue_after_models.ps1"
set "RC=%ERRORLEVEL%"
echo.
echo ==========================================
if "%RC%"=="0" (
  echo I-01 workflow completed successfully.
) else (
  echo Workflow stopped with exit code %RC%.
  echo Nothing has advanced past I-01.
)
echo.
echo This window will stay open until you press a key.
pause >nul
exit /b %RC%
