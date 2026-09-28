@echo off
setlocal EnableExtensions
cd /d "%~dp0"
python scripts\human_canary_review.py
if errorlevel 1 (
  echo.
  echo Human Canary Review failed.
  pause
)
