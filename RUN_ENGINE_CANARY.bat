@echo off
setlocal
cd /d "%~dp0"
echo.
echo Black-Ink Bestiary - Engine Canary + Publish
echo ==============================================
echo Regenerating one candidate for the 9-page anatomy/environment canary set...
python scripts\generate_test_gallery.py --canary --copies 1
if errorlevel 1 (
  echo.
  echo Canary generation stopped with an error.
  pause
  exit /b 1
)
echo.
echo Publishing refreshed review previews...
python scripts\publish_review_previews.py
if errorlevel 1 (
  echo.
  echo Preview publishing stopped with an error.
  pause
  exit /b 1
)
echo.
echo Canary previews are published and ready for ChatGPT inspection.
pause
