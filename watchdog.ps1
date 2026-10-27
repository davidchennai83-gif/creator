# Creator Platform watchdog - checks every few minutes and self-heals the platform
# after restarts or crashes. Paths are resolved from this script, so the project
# can live on any drive.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $root 'watchdog.log'
$backendDir = Join-Path $root 'backend'
$py = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

function Log([string]$m) {
    try { Add-Content -Path $log -Value ("$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') " + $m) } catch {}
}

function Start-Backend {
    Start-Process -FilePath $py `
        -ArgumentList 'start.py' `
        -WorkingDirectory $backendDir `
        -WindowStyle Hidden
}

# Kill + immediately bring the backend back, so a self-heal never leaves the
# platform offline until the next 10-minute tick.
function Restart-Backend([string]$why) {
    $p = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty OwningProcess
    if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
    for ($i = 0; $i -lt 40; $i++) {
        if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 500
    }
    Start-Backend
    Log "backend restarted ($why)"
}

# Fresh PATH from the registry + Node (render_frames.cjs uses node/npx)
$machinePath = [Environment]::GetEnvironmentVariable('PATH', 'Machine')
$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
$env:PATH = "$machinePath;$userPath"
$node = Get-Command node.exe -ErrorAction SilentlyContinue
if ($node) { Log "node: $($node.Source)" }

$backendUp = [bool](Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
$ollamaUp  = [bool](Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)
$recUp     = [bool](Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue)

# Ollama
if (-not $ollamaUp) {
    $ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path $ollama) {
        Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden
        Log 'ollama was down - started'
    }
}

# Recorder Chrome (CDP 9222) - YouTube upload automation
if (-not $recUp) {
    $profile = Join-Path $env:LOCALAPPDATA 'CreatorRecorder\chrome-profile'
    $chrome = @(
        (Join-Path $env:PROGRAMFILES 'Google\Chrome\Application\chrome.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($chrome -and (Test-Path $profile)) {
        Start-Process -FilePath $chrome -ArgumentList '--remote-debugging-port=9222',
            "--user-data-dir=$profile", '--no-first-run', '--no-default-browser-check',
            '--start-minimized', 'https://studio.youtube.com',
            'https://www.instagram.com/accounts/login/',
            'https://www.facebook.com/login/' -WindowStyle Minimized
        Log 'recorder chrome was down - launched'
    }
}

# Funnel (idempotent)
try {
    $ts = Join-Path $env:PROGRAMFILES 'Tailscale\tailscale.exe'
    if (Test-Path $ts) { & $ts funnel --bg 8000 *> $null }
} catch {}

# Backend
if ($backendUp) {
    Log 'health ok (backend up)'
} else {
    Start-Backend
    Log 'backend was down - started'
    # After a downtime, bring the user's normal Chrome back with the app (only if none is open)
    try {
        if (-not (Get-Process chrome -ErrorAction SilentlyContinue)) {
            $chrome = Join-Path $env:PROGRAMFILES 'Google\Chrome\Application\chrome.exe'
            if (Test-Path $chrome) {
                Start-Process -FilePath $chrome `
                    -ArgumentList 'https://desktop-57mkr8o.tail979641.ts.net/video-creator'
                Log 'user chrome reopened with the app'
            }
        }
    } catch {}
}

# Voice surveillance agent heartbeat (runs inside the backend process). If the
# heartbeat goes stale and no render is active, restart the backend so the agent
# comes back - never interrupt an in-progress render.
try {
    $stateFile = Join-Path $backendDir 'storage\voice\state.json'
    if ((Test-Path $stateFile) -and $backendUp) {
        $age = (New-TimeSpan -Start (Get-Item $stateFile).LastWriteTime -End (Get-Date)).TotalMinutes
        if ($age -gt 20) {
            $verdict = & $py (Join-Path $root 'voice_health.py') 2>$null
            if ($verdict -eq 'RESTART') {
                Restart-Backend "voice agent stale ($([math]::Round($age,1))m)"
            } else {
                Log "voice agent stale ($([math]::Round($age,1))m) but a render is running - left alone"
            }
        }
    }
} catch {}

# Autonomous self-upgrade: the daily AI session drops restart.requested after it has
# shipped a verified backend change. Apply it only when no render is active.
try {
    $flag = Join-Path $backendDir 'storage\ops\restart.requested'
    if ((Test-Path $flag) -and $backendUp) {
        $ready = & $py (Join-Path $root 'ops_restart.py') 2>$null
        if ($ready -eq 'OK') {
            Remove-Item $flag -Force -ErrorAction SilentlyContinue
            Restart-Backend 'self-upgrade applied'
        } else {
            Log 'self-upgrade pending but a render is running - deferred'
        }
    }
} catch {}

# OpenCode desktop app (the 24x7 surveillance/agent UI) - reopen after restarts
try {
    $ocMain = Get-CimInstance Win32_Process -Filter "Name='OpenCode.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -notmatch '--type=' }
    if (-not $ocMain) {
        $ocExe = Join-Path $env:LOCALAPPDATA 'Programs\@opencodedesktop\OpenCode.exe'
        if (Test-Path $ocExe) {
            Start-Process -FilePath $ocExe
            Start-Sleep -Seconds 3
            Log 'opencode desktop app reopened'
        }
    }
} catch {}
