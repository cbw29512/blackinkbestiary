@echo off
setlocal
cd /d "%~dp0"

echo.
echo Black-Ink Bestiary - Full Gallery
echo ================================
echo Synchronizing latest engine before runtime startup...
python scripts\sync_engine_for_run.py
if errorlevel 1 (
  echo.
  echo Engine sync stopped because the workstation has protected tracked edits or is on the wrong branch.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_coloring_book.ps1"
set "RUN_EXIT=%ERRORLEVEL%"

echo.
if not "%RUN_EXIT%"=="0" (
  echo Full-gallery generation reported an error. Publishing all completed/diagnostic results anyway...
) else (
  echo Full-gallery generation completed. Publishing review snapshot...
)

python scripts\publish_review_previews.py
set "PUB_EXIT=%ERRORLEVEL%"
if not "%PUB_EXIT%"=="0" (
  echo.
  echo Review snapshot publishing stopped with an error.
  pause
  exit /b %PUB_EXIT%
)

echo.
if not "%RUN_EXIT%"=="0" (
  echo Partial/diagnostic full-gallery snapshot published to GitHub.
  pause
  exit /b %RUN_EXIT%
)

echo Full-gallery review snapshot published to GitHub.
pause
