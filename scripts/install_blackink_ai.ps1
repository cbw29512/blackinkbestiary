$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "Black-Ink Bestiary — One-Click Local AI Install" -ForegroundColor Cyan
Write-Host "=================================================="

# Step 1: project-local comfy-cli
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\prepare_local_ai.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tool preparation failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

$Config = Get-Content (Join-Path $Root "config\local_ai_stack.json") -Raw | ConvertFrom-Json
$Comfy = Join-Path $Root ".blackink-tools\Scripts\comfy.exe"
$Python = Join-Path $Root ".blackink-tools\Scripts\python.exe"
$Workspace = Join-Path $Root $Config.workspace
$ComfyRoot = Join-Path $Workspace "ComfyUI"
$ModelsRoot = Join-Path $ComfyRoot "models"

if (-not (Test-Path $Comfy)) {
    Write-Host "Pinned comfy-cli executable was not created." -ForegroundColor Red
    exit 2
}

# Step 2: install one pinned core-only ComfyUI workspace
if (-not (Test-Path (Join-Path $ComfyRoot "main.py"))) {
    Write-Host ""
    Write-Host "Installing pinned ComfyUI $($Config.comfyui_version)..." -ForegroundColor Cyan
    & $Comfy "--workspace=$Workspace" install --skip-manager --fast-deps --version $Config.comfyui_version
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ComfyUI installation failed." -ForegroundColor Red
        exit $LASTEXITCODE
    }
} else {
    Write-Host ""
    Write-Host "Existing Black-Ink ComfyUI workspace found. It will not be auto-updated." -ForegroundColor Green
}

# Step 3: exact hash-verified model payload
Write-Host ""
Write-Host "Installing/verifying the three required model files..." -ForegroundColor Cyan
& $Python scripts\download_required_models.py --models-root $ModelsRoot
if ($LASTEXITCODE -ne 0) {
    Write-Host "Model installation failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

# Step 4: launch locally, core-only
Write-Host ""
Write-Host "Launching Black-Ink ComfyUI on 127.0.0.1:8188..." -ForegroundColor Cyan
& $Comfy "--workspace=$Workspace" launch --background -- --listen 127.0.0.1 --port 8188
if ($LASTEXITCODE -ne 0) {
    Write-Host "ComfyUI launch command failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

# Step 5: bounded wait for server
$Ready = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 2
        $Ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $Ready) {
    Write-Host "ComfyUI did not become ready within 90 seconds." -ForegroundColor Red
    Write-Host "Run the doctor or inspect the ComfyUI background log before changing anything."
    exit 3
}

# Step 6: validate exact official templates against this live install
Write-Host ""
Write-Host "Fetching and validating official FLUX.2 Klein templates..." -ForegroundColor Cyan
$env:PYTHONPATH = (Join-Path $Root "art_pipeline")
& $Python art_pipeline\validate_local_templates.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Template validation failed. Do not generate yet." -ForegroundColor Red
    exit $LASTEXITCODE
}

# Step 7: final machine report
Write-Host ""
& $Python scripts\blackink_doctor.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Local AI doctor did not report full readiness." -ForegroundColor Yellow
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "BLACK-INK LOCAL AI STACK IS READY." -ForegroundColor Green
Write-Host "Next: run the I-01 smoke test from the production worker."
