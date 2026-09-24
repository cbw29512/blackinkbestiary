param([switch]$NextRejected)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "Black-Ink Bestiary - Automated Test Gallery" -ForegroundColor Cyan
Write-Host "================================================"

Write-Host "Ensuring local AI artist and semantic reviewer are ready..." -ForegroundColor Yellow
& (Join-Path $root "scripts\ensure_local_ai.ps1")
if ($LASTEXITCODE -ne 0) {
  throw "Local AI runtime preflight failed with code $LASTEXITCODE."
}

$runner = Get-Command python -ErrorAction SilentlyContinue
if (-not $runner) { $runner = Get-Command py -ErrorAction SilentlyContinue }
if (-not $runner) { throw "Python was not found." }

Write-Host "Synchronizing latest engine rules and AI decisions..." -ForegroundColor Yellow
& $runner.Source (Join-Path $root "scripts\sync_engine_for_run.py")
if ($LASTEXITCODE -ne 0) {
  throw "Engine sync refused or failed with code $LASTEXITCODE."
}

& $runner.Source (Join-Path $root "scripts\apply_review_decisions.py")
if ($LASTEXITCODE -ne 0) {
  throw "Review decision applier exited with code $LASTEXITCODE."
}

Write-Host "Checking exact-image canary approvals before full gallery..." -ForegroundColor Yellow
& $runner.Source (Join-Path $root "scripts\canary_autopilot_status.py")
$canaryExit = $LASTEXITCODE
if ($canaryExit -ne 0) {
  throw "Full 50-page gallery is blocked until all nine canary pages have exact-image AI approval. Run RUN_ENGINE_AUTOPILOT.bat (or RUN_ENGINE_CANARY.bat) first."
}
Write-Host "Canary approval gate passed: 9/9 exact-image approved." -ForegroundColor Green

$galleryArgs = @("--copies", "4", "--rerun-failed")
if ($NextRejected) {
  $statePath = Join-Path $root "data\test-gallery-state.json"
  if (-not (Test-Path $statePath)) {
    Write-Host "No gallery state exists yet; nothing rejected to rerun." -ForegroundColor Yellow
    exit 0
  }

  $galleryState = Get-Content $statePath -Raw | ConvertFrom-Json
  $rejected = @(
    $galleryState.results |
      Where-Object { $_.status -eq "assistant_rejected" } |
      Select-Object -First 1
  )
  if (-not $rejected -or $rejected.Count -eq 0) {
    Write-Host "No assistant-rejected candidate is waiting to rerun." -ForegroundColor Green
    exit 0
  }

  $target = $rejected[0]
  Write-Host "Rerunning one rejected candidate: $($target.page_id) C$($target.candidate)" -ForegroundColor Yellow
  $galleryArgs += @("--only", [string]$target.page_id, "--candidate", [string]$target.candidate)
} else {
  Write-Host "Starting/resuming Tome I test gallery: 50 pages x 4 candidates (up to 200 images)..." -ForegroundColor Green
}

& $runner.Source (Join-Path $root "scripts\generate_test_gallery.py") @galleryArgs
if ($LASTEXITCODE -ne 0) {
  throw "Gallery runner exited with code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Gallery run complete." -ForegroundColor Green
