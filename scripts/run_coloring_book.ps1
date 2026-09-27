param([switch]$NextRejected)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "Black-Ink Bestiary - Automated Test Gallery" -ForegroundColor Cyan
Write-Host "================================================"

$runner = Get-Command python -ErrorAction SilentlyContinue
if (-not $runner) { $runner = Get-Command py -ErrorAction SilentlyContinue }
if (-not $runner) { throw "Python was not found." }

$studioConfig = Get-Content (Join-Path $root "config\studio.json") -Raw | ConvertFrom-Json
$manifestPath = Join-Path $root ([string]$studioConfig.active_book.manifest)
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$qualityScorecard = Get-Content (Join-Path $root "config\quality_scorecard.json") -Raw | ConvertFrom-Json
$pageCount = @($manifest.pages).Count
$canaryCount = @($qualityScorecard.canary_page_ids).Count
$copiesPerPage = 4
$maxImages = $pageCount * $copiesPerPage
$bookLabel = [string]$manifest.title
if ([string]::IsNullOrWhiteSpace($bookLabel)) { $bookLabel = [string]$manifest.tome_id }
if ($pageCount -lt 1) { throw "Active book manifest has no pages: $manifestPath" }
if ($canaryCount -lt 1) { throw "Quality scorecard has no canary pages." }

Write-Host "Synchronizing latest engine rules and AI decisions..." -ForegroundColor Yellow
& $runner.Source (Join-Path $root "scripts\sync_engine_for_run.py")
if ($LASTEXITCODE -ne 0) {
  throw "Engine sync refused or failed with code $LASTEXITCODE."
}

Write-Host "Running local engine preflight before full gallery generation..." -ForegroundColor Yellow
& $runner.Source (Join-Path $root "scripts\engine_preflight.py")
if ($LASTEXITCODE -ne 0) {
  & $runner.Source (Join-Path $root "scripts\publish_review_previews.py")
  throw "Engine preflight failed; diagnostic snapshot was published."
}

Write-Host "Ensuring local AI artist is ready; local reviewer is advisory..." -ForegroundColor Yellow
& (Join-Path $root "scripts\ensure_local_ai.ps1")
if ($LASTEXITCODE -ne 0) {
  & $runner.Source (Join-Path $root "scripts\publish_review_previews.py")
  throw "Local AI runtime preflight failed; diagnostic snapshot was published."
}

& $runner.Source (Join-Path $root "scripts\apply_review_decisions.py")
if ($LASTEXITCODE -ne 0) {
  throw "Review decision applier exited with code $LASTEXITCODE."
}

Write-Host "Checking exact-image canary approvals before full gallery..." -ForegroundColor Yellow
& $runner.Source (Join-Path $root "scripts\canary_autopilot_status.py")
$canaryExit = $LASTEXITCODE
if ($canaryExit -ne 0) {
  throw "Full $pageCount-page gallery is blocked until all $canaryCount configured canary pages have exact-image AI approval. Run RUN_ENGINE_AUTOPILOT.bat (or RUN_ENGINE_CANARY.bat) first."
}
Write-Host "Canary approval gate passed: $canaryCount/$canaryCount exact-image approved." -ForegroundColor Green

$galleryArgs = @("--copies", [string]$copiesPerPage, "--rerun-failed")
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
  Write-Host "Starting/resuming $bookLabel test gallery: $pageCount pages x $copiesPerPage candidates (up to $maxImages images)..." -ForegroundColor Green
}

& $runner.Source (Join-Path $root "scripts\generate_test_gallery.py") @galleryArgs
if ($LASTEXITCODE -ne 0) {
  throw "Gallery runner exited with code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Gallery run complete." -ForegroundColor Green
