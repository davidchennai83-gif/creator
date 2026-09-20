@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" python -m venv "backend\.venv"
if errorlevel 1 goto failed
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto failed
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements-video.txt"
if errorlevel 1 goto failed
"backend\.venv\Scripts\python.exe" "scripts\setup_local.py"
if errorlevel 1 goto failed
pushd frontend
call npm.cmd ci
if errorlevel 1 (popd & goto failed)
call npx.cmd playwright install chromium
if errorlevel 1 (popd & goto failed)
call npm.cmd run build
if errorlevel 1 (popd & goto failed)
popd
call start-local.cmd
exit /b %errorlevel%
:failed
echo Setup failed. Read the error above. The application was not started.
pause
exit /b 1
