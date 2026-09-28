param(
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

$Protected = @(
  ".blackink-tools",
  ".blackink-comfy",
  "web\test-gallery",
  "web\approved",
  "review-previews",
  "data\test-gallery-state.json",
  "data\review_failure_memory.json",
  "data\production-state.json"
)

$Files = @(
  "data\generation-worker.log",
  "data\generation-progress.json",
  "data\local-runtime-status.json",
  "data\engine-preflight-status.json",
  "data\comfy-runtime.stdout.log",
  "data\comfy-runtime.stderr.log",
  "data\dashboard-runtime-status.json",
  "data\dashboard-runtime.stdout.log",
  "data\dashboard-runtime.stderr.log",
  "data\review-studio-runtime-status.json",
  "data\review-studio-runtime.stdout.log",
  "data\review-studio-runtime.stderr.log",
  "data\autopilot-watchdog-status.json",
  "data\autopilot-watchdog.log",
  "data\test-gallery-state.json.tmp"
)

$Dirs = @(
  ".pytest_cache",
  ".mypy_cache",
  ".ruff_cache"
)

function Remove-SafePath([string]$RelativePath) {
  $target = Join-Path $Root $RelativePath
  if (-not (Test-Path $target)) { return }

  foreach ($protectedPath in $Protected) {
    $protected = [IO.Path]::GetFullPath((Join-Path $Root $protectedPath))
    $full = [IO.Path]::GetFullPath($target)
    if ($full -eq $protected -or $full.StartsWith($protected + [IO.Path]::DirectorySeparatorChar)) {
      throw "Refusing to remove protected path: $RelativePath"
    }
  }

  if ($DryRun) {
    Write-Host "[dry-run] remove $RelativePath"
  } else {
    Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "removed $RelativePath"
  }
}

Write-Host "Black Ink Bestiary safe workspace cleanup" -ForegroundColor Cyan
Write-Host "Preserving models, ComfyUI, current gallery images/state, human decisions, and approved art." -ForegroundColor DarkGray

foreach ($file in $Files) { Remove-SafePath $file }
foreach ($dir in $Dirs) { Remove-SafePath $dir }

Get-ChildItem -Path $Root -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Where-Object {
    $_.FullName -notlike (Join-Path $Root ".blackink-tools*") -and
    $_.FullName -notlike (Join-Path $Root ".blackink-comfy*")
  } |
  ForEach-Object {
    $relative = $_.FullName.Substring($Root.Length).TrimStart("\")
    Remove-SafePath $relative
  }

Get-ChildItem -Path (Join-Path $Root "art_pipeline\workflows\official") -File -Filter "*.json" -ErrorAction SilentlyContinue |
  ForEach-Object {
    $relative = $_.FullName.Substring($Root.Length).TrimStart("\")
    Remove-SafePath $relative
  }

if ($DryRun) {
  Write-Host "Dry run complete. Nothing was deleted." -ForegroundColor Yellow
} else {
  Write-Host "Safe cleanup complete." -ForegroundColor Green
}
