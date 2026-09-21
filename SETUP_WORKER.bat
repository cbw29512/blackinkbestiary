@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  echo Creating local Python environment...
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
    py -m venv .venv
  ) else (
    python -m venv .venv
  )
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Black-Ink Bestiary worker dependencies are ready.
echo Next: make sure ComfyUI is installed and running.
pause
