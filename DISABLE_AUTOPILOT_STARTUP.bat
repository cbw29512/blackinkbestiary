@echo off
setlocal EnableExtensions
cd /d "%~dp0"

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

powershell -NoProfile -Command "$running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'RUN_AUTOPILOT_WATCHDOG_LOOP\.bat' }; foreach ($proc in $running) { Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue }"
echo Stopped the persistent autopilot watchdog loop if it was running.
exit /b 0
