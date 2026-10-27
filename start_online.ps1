# Brings Creator Platform online free (ngrok-free Cloudflare tunnel).
# Usage: powershell -ExecutionPolicy Bypass -File .\start_online.ps1
$ErrorActionPreference = 'Stop'
$cf = Join-Path $env:TEMP 'opencode\tunnels\cloudflared.exe'
if (-not (Test-Path -LiteralPath $cf)) {
    Write-Host 'cloudflared not found - downloading...' -ForegroundColor Yellow
    New-Item -ItemType Directory -Path (Split-Path $cf) -Force | Out-Null
    Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile $cf -UseBasicParsing
}

$backend = 'http://127.0.0.1:8000'
try { $null = Invoke-WebRequest -Uri "$backend/api/docs" -TimeoutSec 8 -UseBasicParsing }
catch { Write-Host 'Backend is not running on 127.0.0.1:8000 - start it first.' -ForegroundColor Red; exit 1 }

Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 2
$log = Join-Path $env:TEMP 'opencode\tunnels\cf.log'
Remove-Item $log -ErrorAction SilentlyContinue
Start-Process -FilePath $cf -ArgumentList @('tunnel','--url',$backend,'--no-autoupdate','--logfile',$log) -WindowStyle Hidden | Out-Null
Start-Sleep 22
$url = (Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1).Matches.Value
if ($url) {
    Write-Host "ONLINE: $url" -ForegroundColor Green
    Write-Host "Free, unlimited, no account. Keep this window/PC on; the URL changes each restart."
    Write-Host 'SECURITY - this URL is reachable by anyone who has it:' -ForegroundColor Yellow
    Write-Host '  1. Set ALLOW_REGISTRATION=false in backend/.env (open sign-ups create VIEWER accounts only).' -ForegroundColor Yellow
    Write-Host '  2. Set RECORDER_AGENT_TOKEN in backend/.env before sharing (locks the recorder agent channel).' -ForegroundColor Yellow
    Write-Host '  3. Set JWT secrets + COOKIE_SECURE=true for a stable deployment (see ACCESS.md).' -ForegroundColor Yellow
} else { Write-Host 'Tunnel did not report a URL - check the log.' -ForegroundColor Red }
