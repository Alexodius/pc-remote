# Build pc-remote.exe
#
#   powershell -ExecutionPolicy Bypass -File build.ps1
#
# Output is dist\pc-remote\ : a folder with the exe and everything it needs.
# Zip it and move it to any Windows machine; no Python required there.
#
# Set PC_REMOTE_PYTHON to build with a specific interpreter.

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

Write-Host '== pc-remote: build ==' -ForegroundColor Cyan
$Python = Resolve-Python
Write-Host "python: $Python"

& $Python -m pip install --quiet --disable-pip-version-check -r (Join-Path $Root 'requirements.txt')
& $Python -m pip install --quiet --disable-pip-version-check pyinstaller

Write-Host "`n-- tests before building --" -ForegroundColor Cyan
Push-Location $Root
try {
  & $Python -m unittest discover -s tests -t . 2>&1 | Select-Object -Last 3
  if ($LASTEXITCODE -ne 0) { throw 'tests failed, build cancelled' }

  Write-Host "`n-- PyInstaller --" -ForegroundColor Cyan
  & $Python -m PyInstaller 'pc-remote.spec' --noconfirm --distpath dist --workpath build |
    Select-Object -Last 2
} finally {
  Pop-Location
}

$out = Join-Path $Root 'dist\pc-remote'
$size = (Get-ChildItem $out -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("`nDone: {0}  ({1:N0} MB)" -f $out, $size) -ForegroundColor Green
Write-Host '  install on the target machine:  pc-remote.exe --install'
