@echo off
setlocal EnableExtensions

set "LAUNCHER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BlackInkBestiaryAutopilot.cmd"

if exist "%LAUNCHER%" (
  del /q "%LAUNCHER%"
  if errorlevel 1 (
    echo Could not remove startup launcher:
    echo   %LAUNCHER%
    exit /b 1
  )
  echo Removed Black-Ink Bestiary autopilot from Windows sign-in startup.
) else (
  echo Black-Ink Bestiary autopilot is not registered in Windows sign-in startup.
)

exit /b 0
