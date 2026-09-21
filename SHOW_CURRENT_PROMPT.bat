@echo off
cd /d "%~dp0"
echo.
echo Black-Ink Bestiary - Current Page Prompt
echo ========================================
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py art_pipeline\worker.py --prompt
) else (
  python art_pipeline\worker.py --prompt
)
echo.
pause
