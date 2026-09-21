@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Worker environment is not installed.
  echo Run SETUP_WORKER.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe art_worker.py --check
pause
