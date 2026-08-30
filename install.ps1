# pc-remote: dependencies + autostart. No administrator rights required.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# Set PC_REMOTE_PYTHON to pick a specific interpreter; otherwise the Windows
# launcher decides. The Task Scheduler entry is registered by app/autostart.py
# so its definition lives in exactly one place and matches the settings toggle.

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Resolve-Python {
  if ($env:PC_REMOTE_PYTHON) { return $env:PC_REMOTE_PYTHON }
  if (Get-Command py -ErrorAction SilentlyContinue) {
    $found = & py -3 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $found) { return $found.Trim() }
  }
  $onPath = (Get-Command python -ErrorAction SilentlyContinue).Source
  if ($onPath) { return $onPath }
  throw "Python 3.10+ not found. Install it, or set PC_REMOTE_PYTHON to the interpreter to use."
}

Write-Host '== pc-remote: install ==' -ForegroundColor Cyan
Write-Host "project: $Root"

$Python = Resolve-Python
$ver = & $Python -c "import sys; print('%d.%d' % sys.version_info[:2])"
Write-Host "python:  $Python  ($ver)"
if ([version]$ver -lt [version]'3.10') {
  throw "Python $ver is too old, 3.10+ required. Set PC_REMOTE_PYTHON to a newer one."
}

Write-Host "`n-- dependencies --" -ForegroundColor Cyan
& $Python -m pip install --quiet --disable-pip-version-check -r (Join-Path $Root 'requirements.txt')
& $Python -c "import flask, waitress; print('flask and waitress are in place')"

Write-Host "`n-- autostart --" -ForegroundColor Cyan
Push-Location $Root
try {
  & $Python -m app.autostart install
  if ($LASTEXITCODE -ne 0) { throw 'could not register the task' }
} finally {
  Pop-Location
}

schtasks /end /tn 'pc-remote' *> $null
schtasks /run /tn 'pc-remote' | Out-Null
Start-Sleep -Seconds 4

$port = 5000
$cfg = Join-Path $Root 'data\config.json'
if (Test-Path $cfg) { $port = (Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json).port }

try {
  $r = Invoke-WebRequest "http://127.0.0.1:$port/healthz" -UseBasicParsing -TimeoutSec 5
  Write-Host "`nDone. The remote answers: HTTP $($r.StatusCode)" -ForegroundColor Green
  $ip = (Get-NetIPAddress -AddressFamily IPv4 |
         Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
         Select-Object -First 1).IPAddress
  Write-Host "  remote:   http://${ip}:$port"
  Write-Host "  settings: http://${ip}:$port/admin"
  Write-Host "`nChange the password first thing: the default is 'changeme'." -ForegroundColor Yellow
} catch {
  Write-Host "`nThe remote did not answer. See $Root\data\server.log" -ForegroundColor Red
  exit 1
}
