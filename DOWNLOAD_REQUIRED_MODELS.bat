@echo off
cd /d "%~dp0"
set "PY=.blackink-tools\Scripts\python.exe"
if not exist "%PY%" (
  echo Run PREPARE_LOCAL_AI.bat first.
  pause
  exit /b 2
)
"%PY%" scripts\download_required_models.py
echo.
pause
