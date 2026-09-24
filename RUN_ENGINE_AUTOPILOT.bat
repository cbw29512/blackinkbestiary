@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo Black-Ink Bestiary - Unattended Canary Autopilot
echo ================================================

:LOOP
echo.
echo [1/5] Synchronizing engine rules and AI decisions...
python scripts\sync_engine_for_run.py
if errorlevel 1 (
  echo Engine sync blocked. Autopilot will retry in 5 minutes.
  timeout /t 300 /nobreak >nul
  goto LOOP
)

echo.
echo [2/5] Applying exact-image AI review decisions...
python scripts\apply_review_decisions.py
if errorlevel 1 (
  echo Decision import failed. Autopilot will retry in 5 minutes.
  timeout /t 300 /nobreak >nul
  goto LOOP
)

echo.
echo [3/5] Checking canary state...
python scripts\canary_autopilot_status.py
set "STATE_EXIT=!ERRORLEVEL!"
if "!STATE_EXIT!"=="0" (
  echo.
  echo CANARY COMPLETE: all nine pages have exact-image approval.
  echo Full-batch generation may now be considered.
  pause
  exit /b 0
)

if "!STATE_EXIT!"=="10" (
  echo.
  echo [4/5] Generating only missing, failed, or AI-rejected pages...
  python scripts\generate_test_gallery.py --canary-failed --copies 1
  set "GEN_EXIT=!ERRORLEVEL!"
) else (
  echo.
  echo [4/5] All current images are waiting for AI review; no GPU regeneration needed.
  set "GEN_EXIT=0"
)

echo.
echo [5/5] Publishing the latest review/diagnostic snapshot...
python scripts\publish_review_previews.py
set "PUB_EXIT=!ERRORLEVEL!"
if not "!PUB_EXIT!"=="0" (
  echo Publish failed. Autopilot will retry in 5 minutes.
  timeout /t 300 /nobreak >nul
  goto LOOP
)

if not "!GEN_EXIT!"=="0" (
  echo Generation reported an error, but diagnostics were published for AI review.
)

echo.
echo Waiting 5 minutes for new AI review decisions or engine updates...
timeout /t 300 /nobreak >nul
goto LOOP
