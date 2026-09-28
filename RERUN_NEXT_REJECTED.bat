@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo RERUN_NEXT_REJECTED now uses the human-first one-at-a-time Canary workflow.
call "%~dp0RUN_NEXT_CANARY.bat"
exit /b %ERRORLEVEL%
