# Auto-start for creator-platform services (Tailscale funnel + backend)
# Registered as scheduled task "CreatorPlatformAutoStart" (AtLogOn)

# 0. Refresh PATH from registry (logon env can be stale) + make Node available
#    for render_frames.cjs and npx; Node lives at C:\Users\sys\nodejs (user install).
$machinePath = [Environment]::GetEnvironmentVariable('PATH', 'Machine')
$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
$env:PATH = "$machinePath;$userPath"
if (Test-Path 'C:\Users\sys\nodejs') {
    $env:PATH = 'C:\Users\sys\nodejs;' + $env:PATH
}

# 0b. Ensure Ollama server is running (history jobs need it). Idempotent.
if ((Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe") -and
    -not (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" `
        -ArgumentList 'serve' -WindowStyle Hidden
}

# 0c. Ensure the CreatorRecorder Chrome with DevTools port 9222 is up
#     (YouTube upload automation attaches over CDP). Only after the profile
#     has been created by the first manual login.
$recorderProfile = "$env:LOCALAPPDATA\CreatorRecorder\chrome-profile"
$chromeCandidates = @('C:\Program Files\Google\Chrome\Application\chrome.exe',
                      'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                      "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe")
if ((Test-Path $recorderProfile) -and
    -not (Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue)) {
    $chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($chrome) {
        Start-Process -FilePath $chrome `
            -ArgumentList '--remote-debugging-port=9222', "--user-data-dir=$recorderProfile",
                          '--no-first-run', '--no-default-browser-check', '--start-minimized',
                          'https://studio.youtube.com' `
            -WindowStyle Minimized
    }
}

# 1. Ensure Tailscale funnel is on (idempotent - safe to run repeatedly)
try {
    & 'C:\Program Files\Tailscale\tailscale.exe' funnel --bg 8000 *> $null
} catch {}

# 2. Start backend only if port 8000 is not already listening
if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath 'C:\Users\sys\AppData\Local\Temp\opencode\pyembed\python.exe' `
        -ArgumentList 'start.py' `
        -WorkingDirectory 'E:\my_tool\creator-platform\backend' `
        -WindowStyle Hidden
}
