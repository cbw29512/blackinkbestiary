@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_COMFY_MODELS.ps1"
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo Model installation did not complete.
  pause
  exit /b 1
)
echo.
echo Restart ComfyUI, then run CHECK_LOCAL_AI.bat.
pause
