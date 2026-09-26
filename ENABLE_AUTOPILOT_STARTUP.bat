@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=%STARTUP%\BlackInkBestiaryAutopilot.cmd"

if not exist "%STARTUP%" (
  echo Windows Startup folder was not found:
  echo   %STARTUP%
  exit /b 1
)

> "%LAUNCHER%" echo @echo off
>> "%LAUNCHER%" echo call "%~dp0START_AUTOPILOT_IF_NEEDED.bat"

if errorlevel 1 (
  echo Could not register Black-Ink Bestiary autopilot for sign-in startup.
  exit /b 1
)

echo Registered autopilot startup:
echo   %LAUNCHER%
call "%~dp0START_AUTOPILOT_IF_NEEDED.bat"
exit /b %ERRORLEVEL%
