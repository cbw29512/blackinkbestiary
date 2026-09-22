$ErrorActionPreference = "SilentlyContinue"
Write-Host ""
Write-Host "Black-Ink Bestiary - Local Setup Check" -ForegroundColor Cyan
Write-Host "======================================="

$ok = $true

Write-Host ""
Write-Host "[1/4] Python"
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if ($python) {
    Write-Host "  OK - Python launcher found" -ForegroundColor Green
} else {
    Write-Host "  MISSING - Python was not found" -ForegroundColor Red
    $ok = $false
}

Write-Host ""
Write-Host "[2/4] ComfyUI local server"
try {
    $stats = Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 2
    Write-Host "  OK - ComfyUI is running on port 8188" -ForegroundColor Green
    if ($stats.devices -and $stats.devices.Count -gt 0) {
        foreach ($device in $stats.devices) {
            $vramGB = if ($device.vram_total) { [math]::Round($device.vram_total / 1GB, 1) } else { "?" }
            Write-Host "  GPU - $($device.name) - $vramGB GB VRAM"
        }
    }
} catch {
    Write-Host "  WAITING - ComfyUI is not reachable yet" -ForegroundColor Yellow
    $ok = $false
}

Write-Host ""
Write-Host "[3/4] Black-Ink ComfyUI workspace"
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root "config\local_ai_stack.json"
try {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    $workspace = Join-Path $root $config.workspace
    $comfyRoot = Join-Path $workspace "ComfyUI"
    $mainPy = Join-Path $comfyRoot "main.py"
    if (Test-Path $mainPy) {
        Write-Host "  OK - project-local ComfyUI workspace found" -ForegroundColor Green
        Write-Host "  Path - $comfyRoot"
    } else {
        Write-Host "  MISSING - project-local ComfyUI workspace not installed" -ForegroundColor Red
        Write-Host "  Expected - $mainPy"
        $ok = $false
    }
} catch {
    Write-Host "  ERROR - could not read config\local_ai_stack.json" -ForegroundColor Red
    $ok = $false
}

Write-Host ""
Write-Host "[4/4] Black-Ink generation files"
$root = Split-Path -Parent $PSScriptRoot
$required = @(
    "art_pipeline\generation_runtime.py",
    "art_pipeline\candidate_runner.py",
    "art_pipeline\comfy_client.py",
    "art_pipeline\prompt_builder.py",
    "art_pipeline\calibration_service.py",
    "scripts\generate_current_page.py",
    "scripts\generate_golden_page.py",
    "data\tome-I.json",
    "data\production-state.json",
    "data\golden-five-state.json"
)
$missing = @()
foreach ($rel in $required) {
    $full = Join-Path $root $rel
    if (-not (Test-Path $full)) { $missing += $rel }
}
if ($missing.Count -eq 0) {
    Write-Host "  OK - Production and Golden Five generation files present" -ForegroundColor Green
} else {
    Write-Host "  MISSING FILES:" -ForegroundColor Red
    foreach ($item in $missing) { Write-Host "    - $item" }
    $ok = $false
}

Write-Host ""
if ($ok) {
    Write-Host "READY FOR MODEL/WORKFLOW VALIDATION" -ForegroundColor Green
} else {
    Write-Host "NOT READY YET - see the items above" -ForegroundColor Yellow
}
Write-Host ""
