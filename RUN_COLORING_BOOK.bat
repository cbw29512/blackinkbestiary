@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_coloring_book.ps1"
if errorlevel 1 (
  echo.
  echo Black-Ink Bestiary stopped with an error. See the message above.
  pause
)
