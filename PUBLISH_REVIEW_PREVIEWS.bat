@echo off
setlocal
cd /d "%~dp0"
echo.
echo Black-Ink Bestiary - Publish Review Previews
echo =============================================
python scripts\publish_review_previews.py
if errorlevel 1 (
  echo.
  echo Review preview publishing stopped with an error.
  pause
  exit /b 1
)
echo.
echo Review previews are on GitHub and ready for ChatGPT inspection.
pause
