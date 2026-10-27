@echo off
REM ── Creator Platform — Recorder Agent installer/launcher ──────────────────
REM Installs the packages the agent needs, then starts it.
REM The web recorder attaches to the Chrome you already have open, so no
REM Playwright browser download is required.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH. Install Python 3.10+ and tick "Add to PATH".
  pause
  exit /b 1
)

echo Installing/updating dependencies...
python -m pip install --quiet --upgrade "python-socketio[client]" pynput pyautogui playwright
if errorlevel 1 (
  echo [ERROR] pip install failed.
  pause
  exit /b 1
)

set HUB=%1
if "%HUB%"=="" set HUB=http://127.0.0.1:8000
REM %2 = agent token; when omitted it is read from the project .env files so the
REM agent matches RECORDER_AGENT_TOKEN on the server without extra typing.
set TOKEN=%2
if "%TOKEN%"=="" for /f "tokens=1,* delims==" %%A in ('findstr /b /c:"RECORDER_AGENT_TOKEN=" "%~dp0..\..\..\.env" 2^>nul') do set TOKEN=%%B
if "%TOKEN%"=="" for /f "tokens=1,* delims==" %%A in ('findstr /b /c:"RECORDER_AGENT_TOKEN=" "%~dp0..\..\.env" 2^>nul') do set TOKEN=%%B

echo Starting Recorder Agent against %HUB%
if "%TOKEN%"=="" (
  python recorder_agent.py --hub %HUB%
) else (
  python recorder_agent.py --hub %HUB% --token %TOKEN%
)
endlocal
