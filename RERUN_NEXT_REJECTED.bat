@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_coloring_book.ps1" -NextRejected
if errorlevel 1 (
  echo.
  echo Rejected candidate rerun stopped with an error. See the message above.
  pause
  exit /b 1
)
python scripts\publish_review_previews.py
if errorlevel 1 (
  echo.
  echo Candidate reran, but publishing its review preview failed.
  pause
  exit /b 1
)
echo.
echo One rejected candidate was rerun and its fresh preview was published.
pause
