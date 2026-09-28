$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Run-Python([string[]]$Arguments) {
  & python @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed ($LASTEXITCODE): python $($Arguments -join ' ')"
  }
}

Write-Host ""
Write-Host "Black Ink Bestiary - One-at-a-Time Human Calibration" -ForegroundColor Cyan
Write-Host "====================================================="

Write-Host "[1/5] Synchronizing current engine and human review decisions..." -ForegroundColor Yellow
Run-Python @("scripts\sync_engine_for_run.py")

Write-Host "[2/5] Applying current human decisions to the local gallery..." -ForegroundColor Yellow
Run-Python @("scripts\apply_review_decisions.py")

$targetJson = & python "scripts\next_canary_target.py" --json
if ($LASTEXITCODE -ne 0) { throw "Could not determine next Canary target." }
$target = $targetJson | ConvertFrom-Json

if ($target.complete) {
  Write-Host "All configured Canary pages are human approved." -ForegroundColor Green
  exit 0
}

$pageId = [string]$target.target.page_id
$state = [string]$target.target.state
$monster = [string]$target.target.monster_name
Write-Host ("Current calibration target: {0} - {1} [{2}]" -f $pageId, $monster, $state) -ForegroundColor Cyan

if ($state -eq "awaiting_review") {
  Write-Host "[3/5] Current local pixels are ready for your review. No GPU generation needed." -ForegroundColor Green
  & (Join-Path $Root "OPEN_REVIEW_STUDIO.bat")
  exit $LASTEXITCODE
}

if ($state -ne "needs_generation") {
  throw "Unexpected Canary target state: $state"
}

Write-Host "[3/5] Running non-GPU engine preflight..." -ForegroundColor Yellow
Run-Python @("scripts\engine_preflight.py")

Write-Host "[4/5] Ensuring local AI runtime is ready..." -ForegroundColor Yellow
& (Join-Path $Root "scripts\ensure_local_ai.ps1")
if ($LASTEXITCODE -ne 0) {
  throw "Local AI runtime is not ready."
}

Write-Host ("[5/5] Generating ONLY {0}. Other Canary pages will not run." -f $pageId) -ForegroundColor Yellow
Run-Python @(
  "scripts\generate_test_gallery.py",
  "--only", $pageId,
  "--candidate", "1",
  "--copies", "1",
  "--rerun-failed"
)

Run-Python @("scripts\publish_review_previews.py")

Write-Host ""
Write-Host ("{0} is ready for human review. Stopping here." -f $pageId) -ForegroundColor Green
& (Join-Path $Root "OPEN_REVIEW_STUDIO.bat")
