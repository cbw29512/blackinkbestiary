$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "Black-Ink Bestiary - Continue After Models" -ForegroundColor Cyan
Write-Host "=========================================="
Write-Host ""
Write-Host "This uses the existing ComfyUI Desktop instance on 127.0.0.1:8188."
Write-Host "It will NOT install a second ComfyUI copy or redownload the models."
Write-Host ""

function Fail-Step {
    param([string]$Message, [int]$Code = 1)
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    exit $Code
}

# 1. Confirm ComfyUI Desktop is running.
try {
    $stats = Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 3
    Write-Host "[OK] ComfyUI Desktop is running." -ForegroundColor Green
    if ($stats.devices -and $stats.devices.Count -gt 0) {
        Write-Host ("     GPU: " + $stats.devices[0].name)
    }
} catch {
    Fail-Step "ComfyUI Desktop is not reachable. Open the Black-Ink Bestiary ComfyUI instance, then run this again." 2
}

# 2. Prepare only the small project-local control tools.
Write-Host ""
Write-Host "[1/4] Preparing Black-Ink control tools..." -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\prepare_local_ai.ps1")
if ($LASTEXITCODE -ne 0) {
    Fail-Step "Could not prepare the project-local Comfy control tools." $LASTEXITCODE
}

$Python = Join-Path $Root ".blackink-tools\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Fail-Step "Project Python environment was not created." 3
}
$env:PYTHONPATH = (Join-Path $Root "art_pipeline")

# 3. Verify the running Desktop instance sees all three required models.
Write-Host ""
Write-Host "[2/4] Verifying GPU, ComfyUI, and required models..." -ForegroundColor Cyan
& $Python scripts\blackink_doctor.py
if ($LASTEXITCODE -ne 0) {
    Fail-Step "The local AI doctor found a blocker. Do not generate yet." $LASTEXITCODE
}

# 4. Pull and validate the current official FLUX.2 Klein workflows.
Write-Host ""
Write-Host "[3/4] Validating official FLUX.2 Klein workflow templates..." -ForegroundColor Cyan
& $Python art_pipeline\validate_local_templates.py
if ($LASTEXITCODE -ne 0) {
    Fail-Step "Official workflow validation failed. Nothing was generated." $LASTEXITCODE
}

# 5. Generate exactly one I-01 calibration candidate and register it in the Studio.
Write-Host ""
Write-Host "[4/4] Generating I-01 Kobold Warrior calibration candidate..." -ForegroundColor Cyan
& $Python scripts\smoke_test_i01.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "I-01 did not complete. The production queue has NOT advanced." -ForegroundColor Yellow
    Write-Host "Read the message above and send it to ChatGPT before changing anything."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "SUCCESS - I-01 is ready for your review." -ForegroundColor Green
Write-Host "Opening the Black-Ink Bestiary Studio..."
Start-Process "http://127.0.0.1:8765"
Write-Host ""
Write-Host "Choose APPROVE & LOCK, MODIFY, or REGENERATE in the Studio."
Write-Host "The system will not move to I-02 without your approval."
exit 0
