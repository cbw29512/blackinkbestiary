@echo off
setlocal
cd /d "%~dp0"
echo.
echo Black-Ink Bestiary - Engine Canary + Publish
echo ==============================================
echo Ensuring local AI artist and semantic reviewer are ready...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\ensure_local_ai.ps1"
if errorlevel 1 (
  echo.
  echo Local AI runtime could not be started or verified.
  echo Publishing runtime diagnostic to the review snapshot...
  python scripts\publish_review_previews.py
  pause
  exit /b 1
)
echo.
echo Synchronizing the latest engine rules and AI decisions...
python scripts\sync_engine_for_run.py
if errorlevel 1 (
  echo.
  echo Engine sync stopped because the workstation has protected tracked edits or is on the wrong branch.
  pause
  exit /b 1
)
echo.
echo Applying exact-image AI review decisions from the engine branch...
python scripts\apply_review_decisions.py
if errorlevel 1 (
  echo.
  echo Review decision import stopped with an error.
  pause
  exit /b 1
)
echo.
echo Retrying only missing, failed, or exact-image-rejected canary pages...
python scripts\generate_test_gallery.py --canary-failed --copies 1
set "GEN_EXIT=%ERRORLEVEL%"

echo.
if not "%GEN_EXIT%"=="0" (
  echo Canary generation reported an error. Publishing all completed/diagnostic results anyway...
) else (
  echo Canary generation completed. Publishing refreshed previews...
)
echo Publishing snapshot to the dedicated review-previews-live branch...
python scripts\publish_review_previews.py
set "PUB_EXIT=%ERRORLEVEL%"
if not "%PUB_EXIT%"=="0" (
  echo.
  echo Preview publishing stopped with an error.
  pause
  exit /b %PUB_EXIT%
)

echo.
if not "%GEN_EXIT%"=="0" (
  echo Partial/diagnostic review snapshot published. ChatGPT can inspect the completed work directly from GitHub.
  pause
  exit /b %GEN_EXIT%
)

echo Review snapshot published. ChatGPT can inspect it directly from GitHub.
pause
