param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root 'backend\.venv\Scripts\pythonw.exe'
$launcher = Join-Path $root 'backend\supervise.py'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$name = 'CreatorPlatformWeb'
if ($Remove) {
    Remove-ItemProperty -Path $runKey -Name $name -ErrorAction SilentlyContinue
    'Creator Platform automatic startup removed. The current server is still running.'
    exit
}
if (!(Test-Path -LiteralPath $python) -or !(Test-Path -LiteralPath (Join-Path $root 'frontend\dist\index.html'))) {
    throw 'Run setup-local.cmd before installing automatic startup.'
}
if (!(Test-Path -LiteralPath $runKey)) { New-Item -Path $runKey -Force | Out-Null }
New-ItemProperty -Path $runKey -Name $name -PropertyType String -Value ('"{0}" "{1}"' -f $python, $launcher) -Force | Out-Null
Start-Process -FilePath $python -ArgumentList ('"{0}"' -f $launcher) -WorkingDirectory (Join-Path $root 'backend')
'Installed current-user logon startup. Open http://127.0.0.1:8000 - no CMD window required.'
