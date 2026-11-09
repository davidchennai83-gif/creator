# Wait for Tailscale to come up after a reboot, then enable the public funnel.
# Runs at logon in parallel with the watchdog; keeps retrying for ~4 minutes so
# a slow network start does not leave the phone URL offline until the next tick.

$ErrorActionPreference = 'SilentlyContinue'
$ts = 'C:\Program Files\Tailscale\tailscale.exe'
if (-not (Test-Path $ts)) { exit 0 }

for ($i = 0; $i -lt 24; $i++) {
    & $ts funnel --bg 8000 *> $null
    $status = & $ts funnel status 2>$null
    if (($status -match 'Funnel on') -and ($status -match '127\.0\.0\.1:8000')) { exit 0 }
    Start-Sleep -Seconds 10
}
exit 0
