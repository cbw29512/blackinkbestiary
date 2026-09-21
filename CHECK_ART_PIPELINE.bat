@echo off
cd /d "%~dp0"
echo.
echo Black-Ink Bestiary - Local Art Pipeline Check
echo =============================================
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py art_pipeline\worker.py --check
) else (
  python art_pipeline\worker.py --check
)
echo.
pause
