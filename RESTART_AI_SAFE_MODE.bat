@echo off
cd /d "%~dp0"
set "COMFY=.blackink-tools\Scripts\comfy.exe"
if not exist "%COMFY%" (
  echo Run INSTALL_BLACKINK_AI.bat first.
  pause
  exit /b 2
)
"%COMFY%" --workspace=".blackink-comfy" stop >nul 2>nul
"%COMFY%" --workspace=".blackink-comfy" launch --background -- --listen 127.0.0.1 --port 8188 --disable-dynamic-vram
echo.
echo Black-Ink ComfyUI restarted with --disable-dynamic-vram.
echo Use this only if the normal RTX 5060 Ti run shows a DynamicVRAM/VBAR/OOM failure.
pause
