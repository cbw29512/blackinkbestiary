@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ======================================================
echo   BLACK-INK BESTIARY - START / RESUME PRODUCTION
echo ======================================================
echo.

set "PY=.blackink-tools\Scripts\python.exe"
set "STACK_READY=0"

if exist "%PY%" (
  "%PY%" "scripts\local_stack_marker.py" --check >nul 2>&1
  if not errorlevel 1 set "STACK_READY=1"
)

if "%STACK_READY%"=="0" (
  echo Verified local AI stack is missing, incomplete, or outdated.
  echo Running the pinned installer/repair path...
  echo First-time setup may download about 12.5 GB of model files.
  echo.
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install_blackink_ai.ps1"
  if errorlevel 1 (
    echo.
    echo Setup/repair did not complete. Nothing will generate until this is fixed.
    pause
    exit /b 1
  )
) else (
  echo Verified local AI stack found. Heavy installation checks are skipped.
)

echo.
echo Starting the self-healing Canary Nine production loop...
call "%~dp0ENABLE_AUTOPILOT_STARTUP.bat"
if errorlevel 1 (
  echo.
  echo Could not start/register the production watchdog.
  pause
  exit /b 2
)

echo.
echo Black-Ink Bestiary is running in self-healing mode.
echo - engine/review authority syncs automatically
echo - non-GPU preflight runs before generation
echo - failed/stale canary pages regenerate without advancing the book
echo - full production remains blocked until the Canary Nine are exact-image approved
echo.
exit /b 0
