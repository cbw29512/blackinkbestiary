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
if errorlevel 1 (
  echo.
  echo Black-Ink Bestiary stopped with an error. See the message above.
  pause
  exit /b 1
)
