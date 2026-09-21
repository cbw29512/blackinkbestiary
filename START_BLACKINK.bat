@echo off
setlocal
cd /d "%~dp0"

echo.
echo ======================================================
echo   BLACK-INK BESTIARY - START PRODUCTION
echo ======================================================
echo.
echo This first run may download about 12.5 GB of model files.
echo Later runs reuse the verified local files.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install_blackink_ai.ps1"
if errorlevel 1 (
  echo.
  echo Setup did not complete. The messages above identify the blocker.
  pause
  exit /b 1
)

set "PY=.blackink-tools\Scripts\python.exe"
if not exist "%PY%" (
  echo Project Python environment is missing.
  pause
  exit /b 2
)

echo.
echo Running I-01 calibration page...
echo.
set "PYTHONPATH=%CD%\art_pipeline"
"%PY%" "scripts\smoke_test_i01.py"
if errorlevel 1 (
  echo.
  echo I-01 calibration did not complete. Nothing advanced to I-02.
  pause
  exit /b 3
)

echo.
echo Opening the Black-Ink Bestiary Studio...
start "" "http://127.0.0.1:8765"

echo.
echo Review I-01 in the Studio.
echo APPROVE ^& LOCK, MODIFY, or REGENERATE.
echo The system will not move to I-02 without your approval.
echo.
pause
