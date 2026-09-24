$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$config = Get-Content (Join-Path $root "config\local_ai_stack.json") -Raw | ConvertFrom-Json
$health = "$($config.comfy_url.TrimEnd('/'))/system_stats"

function Test-Comfy {
  try { Invoke-RestMethod -Uri $health -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

function Find-ComfyMain {
  $candidates = @(
    (Join-Path $root ".blackink-comfy\ComfyUI\main.py"),
    (Join-Path $env:USERPROFILE "Desktop\ComfyUI\main.py"),
    (Join-Path $env:USERPROFILE "Documents\ComfyUI\main.py"),
    (Join-Path $env:USERPROFILE "ComfyUI\main.py"),
    (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI\resources\ComfyUI\main.py"),
    (Join-Path $env:LOCALAPPDATA "ComfyUI\resources\ComfyUI\main.py")
  )
  foreach ($p in $candidates) { if ($p -and (Test-Path $p)) { return $p } }

  $roots = @(
    (Join-Path $env:USERPROFILE "Desktop"),
    (Join-Path $env:USERPROFILE "Documents"),
    $env:LOCALAPPDATA
  )
  foreach ($searchRoot in $roots) {
    if (-not $searchRoot -or -not (Test-Path $searchRoot)) { continue }
    $hit = Get-ChildItem -Path $searchRoot -Filter main.py -File -Recurse -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -match "[\\/]ComfyUI[\\/]main\.py$" } |
      Select-Object -First 1
    if ($hit) { return $hit.FullName }
  }
  return $null
}

Write-Host ""
Write-Host "Black-Ink Bestiary - Automated Test Gallery" -ForegroundColor Cyan
Write-Host "================================================"

if (-not (Test-Comfy)) {
  $mainPy = Find-ComfyMain
  if (-not $mainPy) {
    throw "Existing ComfyUI installation was not found. Start your existing ComfyUI Desktop once, then rerun this launcher."
  }

  $comfyRoot = Split-Path -Parent $mainPy
  $python = Get-Command python -ErrorAction SilentlyContinue
  if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
  if (-not $python) { throw "Python was not found." }

  Write-Host "Found existing ComfyUI: $comfyRoot" -ForegroundColor Green
  Write-Host "Starting existing ComfyUI..." -ForegroundColor Yellow
  $args = @($mainPy, "--listen", "127.0.0.1", "--port", "8188")
  Start-Process -FilePath $python.Source -ArgumentList $args -WorkingDirectory $comfyRoot -WindowStyle Minimized | Out-Null

  Write-Host "Waiting for ComfyUI API..." -ForegroundColor Yellow
  $ready = $false
  for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 2
    if (Test-Comfy) { $ready = $true; break }
    if (($i + 1) % 10 -eq 0) { Write-Host "  still starting... $((($i + 1) * 2)) seconds" }
  }
  if (-not $ready) { throw "Existing ComfyUI did not become ready at $($config.comfy_url) within 4 minutes." }
}

Write-Host "ComfyUI API ready." -ForegroundColor Green
Write-Host "Starting/resuming Tome I: 50 pages x 4 candidates (up to 200 images)..." -ForegroundColor Green

$runner = Get-Command python -ErrorAction SilentlyContinue
if (-not $runner) { $runner = Get-Command py -ErrorAction SilentlyContinue }
if (-not $runner) { throw "Python was not found." }
& $runner.Source (Join-Path $root "scripts\generate_test_gallery.py") --copies 4
if ($LASTEXITCODE -ne 0) { throw "Gallery runner exited with code $LASTEXITCODE." }

Write-Host ""
Write-Host "Gallery run complete." -ForegroundColor Green
