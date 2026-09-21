$ErrorActionPreference = "SilentlyContinue"
Write-Host ""
Write-Host "Black-Ink Bestiary - Local Setup Check" -ForegroundColor Cyan
Write-Host "======================================="

$ok = $true

Write-Host ""
Write-Host "[1/3] Python"
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if ($python) {
    Write-Host "  OK - Python launcher found" -ForegroundColor Green
} else {
    Write-Host "  MISSING - Python was not found" -ForegroundColor Red
    $ok = $false
}

Write-Host ""
Write-Host "[2/3] ComfyUI local server"
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
    Write-Host "  This is normal until ComfyUI Desktop is installed and open."
    $ok = $false
}

Write-Host ""
Write-Host "[3/3] Black-Ink worker files"
$root = Split-Path -Parent $PSScriptRoot
$required = @(
    "art_pipeline\worker.py",
    "art_pipeline\comfy_client.py",
    "art_pipeline\prompt_builder.py",
    "art_pipeline\workflow_adapter.py",
    "data\tome-I.json",
    "data\production-state.json"
)
$missing = @()
foreach ($rel in $required) {
    $full = Join-Path $root $rel
    if (-not (Test-Path $full)) { $missing += $rel }
}
if ($missing.Count -eq 0) {
    Write-Host "  OK - Production worker files present" -ForegroundColor Green
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
