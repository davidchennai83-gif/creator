@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\pythonw.exe" goto setup
if not exist "frontend\dist\index.html" goto setup
start "Creator Platform" /b "backend\.venv\Scripts\pythonw.exe" "backend\supervise.py"
echo Creator Platform runs in the background at http://127.0.0.1:8000
echo Startup may take a few seconds. You can close this window.
start "" "http://127.0.0.1:8000"
exit /b 0
:setup
echo Setup is incomplete. Run setup-local.cmd first.
pause
exit /b 1
