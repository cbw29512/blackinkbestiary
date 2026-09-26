@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',8765); $c.Close(); exit 0 } catch { exit 1 }"
if not errorlevel 1 exit /b 0

set "PY=.blackink-tools\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
start "Black Ink Bestiary Monitor" /min "%PY%" "%~dp0server.py" --no-browser
exit /b 0
