$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "Black-Ink Bestiary — Preparing local AI tools" -ForegroundColor Cyan
Write-Host "================================================"

$Py = Get-Command py -ErrorAction SilentlyContinue
if (-not $Py) { $Py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $Py) {
    Write-Host "Python was not found. Install Python 3.10+ first." -ForegroundColor Red
    exit 2
}

$Venv = Join-Path $Root ".blackink-tools"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$Comfy = Join-Path $Venv "Scripts\comfy.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating project-local tool environment..."
    if ($Py.Name -eq "py.exe") {
        & py -3.12 -m venv $Venv
        if ($LASTEXITCODE -ne 0) { & py -3 -m venv $Venv }
    } else {
        & $Py.Source -m venv $Venv
    }
}

Write-Host "Installing pinned comfy-cli 1.20.0 into the project tool environment..."
& $VenvPython -m pip install --disable-pip-version-check --quiet "comfy-cli==1.20.0"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not install comfy-cli." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
& $Comfy --version
Write-Host ""
& $VenvPython scripts\blackink_doctor.py
$DoctorCode = $LASTEXITCODE

Write-Host ""
if ($DoctorCode -eq 0) {
    Write-Host "Core local stack is present. Next step is template validation / smoke test." -ForegroundColor Green
} else {
    Write-Host "The doctor report above shows the next missing machine-specific item." -ForegroundColor Yellow
}
exit 0
