# Looping watchdog: runs the self-heal check every 10 minutes while logged in.
# Launched once at logon from the Startup folder (no admin required).
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$watchdog = Join-Path $root 'watchdog.ps1'
while ($true) {
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $watchdog
    } catch {}
    Start-Sleep -Seconds 600
}
