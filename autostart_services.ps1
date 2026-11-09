# Auto-start for creator-platform services (Tailscale funnel + backend).
#
# Optional: the Startup-folder watchdog (watchdog_at_logon.cmd) already
# self-heals every 10 minutes. This script is a single-shot variant for a
# Scheduled Task, and it is now self-locating: it works from any drive letter
# and never assumes the old G:/E:/C:\Users\sys paths.

$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path $PSScriptRoot -Parent
$backendDir = Join-Path $root 'backend'
$pythonw = Join-Path $backendDir '.venv\Scripts\pythonw.exe'

# 0. Fresh PATH from the registry (logon environments can be stale).
$machinePath = [Environment]::GetEnvironmentVariable('PATH', 'Machine')
$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
$env:PATH = "$machinePath;$userPath"

# 1. Ollama (history jobs use it).
$ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if ((Test-Path $ollama) -and
    -not (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden
}

# 2. CreatorRecorder Chrome with the DevTools port the upload scripts attach to.
$recorderProfile = Join-Path $env:LOCALAPPDATA 'CreatorRecorder\chrome-profile'
$chromeCandidates = @(
    'C:\Program Files\Google\Chrome\Application\chrome.exe',
    'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
)
if ((Test-Path $recorderProfile) -and
    -not (Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue)) {
    $chrome = $chromeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($chrome) {
        Start-Process -FilePath $chrome -ArgumentList `
            '--remote-debugging-port=9222', "--user-data-dir=$recorderProfile",
            '--no-first-run', '--no-default-browser-check', '--start-minimized',
            'https://studio.youtube.com' `
            -WindowStyle Minimized
    }
}

# 3. Tailscale funnel (idempotent).
$tailscale = 'C:\Program Files\Tailscale\tailscale.exe'
if (Test-Path $tailscale) {
    & $tailscale funnel --bg 8000 *> $null
}

# 4. Backend, only when port 8000 is not already listening.
if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    if (Test-Path $pythonw) {
        Start-Process -FilePath $pythonw -ArgumentList 'start.py' -WorkingDirectory $backendDir -WindowStyle Hidden
    }
}
