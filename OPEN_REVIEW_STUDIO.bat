@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ensure_review_studio.ps1"
if errorlevel 1 (
  echo.
  echo Black Ink Bestiary Review Studio could not start.
  echo Check data\review-studio-runtime-status.json
  echo Check data\review-studio-runtime.stderr.log
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8766/human-review.html"
exit /b 0
