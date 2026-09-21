@echo off
setlocal
cd /d "%~dp0"
title Black-Ink Bestiary - Verified Model Installer
cls
echo Black-Ink Bestiary - Verified Model Installer
echo =============================================
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_verified_models.ps1"
set "RC=%ERRORLEVEL%"
echo.
echo =============================================
if "%RC%"=="0" (
  echo Installer completed successfully.
) else (
  echo Installer stopped with exit code %RC%.
  echo.
  echo The full log is here:
  echo %~dp0install_verified_models.log
)
echo.
echo This window will stay open until you press a key.
pause >nul
exit /b %RC%
