@echo off
cd /d "%~dp0"
set "PY=.blackink-tools\Scripts\python.exe"
if not exist "%PY%" (
  echo Run INSTALL_BLACKINK_AI.bat first.
  pause
  exit /b 2
)
set "PYTHONPATH=%CD%\art_pipeline"
"%PY%" scripts\smoke_test_i01.py
echo.
pause
