@echo off
setlocal
cd /d "%~dp0"
title Black-Ink Bestiary - Reset Tome I For Rebuild
cls
echo Black-Ink Bestiary - Reset Tome I For Rebuild
echo ===============================================
echo.
echo This preserves discarded artwork and backs up the current production state.
echo It resets Tome I to page I-01 for a clean perfection pass.
echo.
set "PY=.blackink-tools\Scripts\python.exe"
if exist "%PY%" (
  "%PY%" "scripts\reset_tome_i_for_rebuild.py"
) else (
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
    py "scripts\reset_tome_i_for_rebuild.py"
  ) else (
    python "scripts\reset_tome_i_for_rebuild.py"
  )
)
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Rebuild state is ready. Start the Studio and review I-01.
) else (
  echo Reset failed with exit code %RC%.
)
echo.
pause
exit /b %RC%
