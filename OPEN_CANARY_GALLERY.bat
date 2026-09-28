@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "%~dp0LOCAL_CANARY_GALLERY.html" (
  echo LOCAL_CANARY_GALLERY.html is missing.
  pause
  exit /b 1
)
start "" "%~dp0LOCAL_CANARY_GALLERY.html"
exit /b 0
