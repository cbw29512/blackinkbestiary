@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Black-Ink Bestiary worker is not set up yet.
  echo Run SETUP_WORKER.bat first.
  pause
  exit /b 1
)

echo Starting Black-Ink Bestiary Studio...
start "Black-Ink Bestiary Studio" ".venv\Scripts\python.exe" server.py
timeout /t 3 /nobreak >nul

echo Checking local AI...
".venv\Scripts\python.exe" art_worker.py --check
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo The Studio is ready, but ComfyUI/model setup still needs attention.
  echo Keep this window open or run CHECK_LOCAL_AI.bat after ComfyUI is ready.
  pause
  exit /b 1
)

echo.
echo Generating the CURRENT page only...
".venv\Scripts\python.exe" art_worker.py
echo.
echo The best passing candidate is now in the Studio for review.
pause
