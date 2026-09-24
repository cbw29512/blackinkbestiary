@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo Black-Ink Bestiary - Unattended Canary Autopilot
echo ================================================

:LOOP
echo.
echo [1/7] Synchronizing engine rules and AI decisions...
python scripts\sync_engine_for_run.py
if errorlevel 1 (
  echo Engine sync blocked. Autopilot will retry in 5 minutes.
  timeout /t 300 /nobreak >nul
  goto LOOP
)

echo.
echo [2/7] Running local engine preflight before GPU work...
python scripts\engine_preflight.py
if errorlevel 1 (
  echo Engine preflight failed. Publishing diagnostic before retry...
  python scripts\publish_review_previews.py
  timeout /t 300 /nobreak >nul
  goto LOOP
)

echo.
echo [3/7] Ensuring local AI artist and semantic reviewer are ready...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\ensure_local_ai.ps1"
if errorlevel 1 (
  echo Local AI runtime is not ready. Publishing runtime diagnostic before retry...
  python scripts\publish_review_previews.py
  if errorlevel 1 (
    echo Runtime diagnostic publishing also failed; keeping the local status file for the next retry.
  )
  timeout /t 300 /nobreak >nul
  goto LOOP
)

echo.
echo [4/7] Applying exact-image AI review decisions...
python scripts\apply_review_decisions.py
if errorlevel 1 (
  echo Decision import failed. Autopilot will retry in 5 minutes.
  timeout /t 300 /nobreak >nul
  goto LOOP
)

echo.
echo [5/7] Checking canary state...
python scripts\canary_autopilot_status.py
set "STATE_EXIT=!ERRORLEVEL!"
if "!STATE_EXIT!"=="0" (
  echo.
  echo CANARY COMPLETE: all nine pages have exact-image approval.
  echo Full-batch generation may now be considered.
  pause
  exit /b 0
)

echo.
if "!STATE_EXIT!"=="10" (
  echo [6/7] Reconciling canary state and generating only pages that truly need new pixels...
) else (
  echo [6/7] Reconciling review authority on existing images; current pixels will be skipped unless stale or failed...
)
python scripts\generate_test_gallery.py --canary-failed --copies 1
set "GEN_EXIT=!ERRORLEVEL!"

echo.
echo [7/7] Publishing the latest review/diagnostic snapshot...
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
