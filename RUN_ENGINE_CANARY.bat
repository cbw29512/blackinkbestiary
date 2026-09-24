@echo off
setlocal
cd /d "%~dp0"
echo.
echo Black-Ink Bestiary - Engine Canary + Publish
echo ==============================================
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
if errorlevel 1 (
  echo.
  echo Canary generation stopped with an error.
  pause
  exit /b 1
)
echo.
echo Publishing refreshed previews to the dedicated review-previews-live branch...
python scripts\publish_review_previews.py
if errorlevel 1 (
  echo.
  echo Preview publishing stopped with an error.
  pause
  exit /b 1
)
echo.
echo Review snapshot published. ChatGPT can inspect it directly from GitHub.
pause
