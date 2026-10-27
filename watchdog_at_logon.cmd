@echo off
rem Creator Platform self-heal at logon (no admin needed)
start "" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0watchdog_loop.ps1"
