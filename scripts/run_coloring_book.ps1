$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$config = Get-Content (Join-Path $root "config\local_ai_stack.json") -Raw | ConvertFrom-Json
$health = "$($config.comfy_url.TrimEnd('/'))/system_stats"

function Test-Comfy {
  try { Invoke-RestMethod -Uri $health -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

Write-Host ""
Write-Host "Black-Ink Bestiary - Automated Test Gallery" -ForegroundColor Cyan
Write-Host "================================================"

if (-not (Test-Comfy)) {
  $workspace = Join-Path $root $config.workspace
  $comfyRoot = Join-Path $workspace "ComfyUI"
  $mainPy = Join-Path $comfyRoot "main.py"
  if (-not (Test-Path $mainPy)) {
    Write-Host "Project-local ComfyUI is missing. Bootstrapping it now..." -ForegroundColor Yellow
    $setup = Join-Path $root "scripts\bootstrap_comfyui.ps1"
    if (-not (Test-Path $setup)) { throw "Missing bootstrap script: $setup" }
    powershell -NoProfile -ExecutionPolicy Bypass -File $setup
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $mainPy)) {
      throw "Automatic ComfyUI bootstrap did not complete successfully."
    }
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
  if (-not $python) { throw "Python was not found." }

  Write-Host "Starting project-local ComfyUI..." -ForegroundColor Yellow
  $args = @($mainPy, "--listen", "127.0.0.1", "--port", "8188")
  Start-Process -FilePath $python.Source -ArgumentList $args -WorkingDirectory $comfyRoot -WindowStyle Minimized | Out-Null

  Write-Host "Waiting for ComfyUI API..." -ForegroundColor Yellow
  $ready = $false
  for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 2
    if (Test-Comfy) { $ready = $true; break }
    if (($i + 1) % 10 -eq 0) { Write-Host "  still starting... $((($i + 1) * 2)) seconds" }
  }
  if (-not $ready) { throw "ComfyUI did not become ready at $($config.comfy_url) within 4 minutes." }
}

Write-Host "ComfyUI API ready." -ForegroundColor Green
Write-Host "Starting/resuming 4-candidate gallery..." -ForegroundColor Green

$runner = Get-Command python -ErrorAction SilentlyContinue
if (-not $runner) { $runner = Get-Command py -ErrorAction SilentlyContinue }
& $runner.Source (Join-Path $root "scripts\generate_test_gallery.py") --copies 4
if ($LASTEXITCODE -ne 0) { throw "Gallery runner exited with code $LASTEXITCODE." }

Write-Host ""
Write-Host "Gallery run complete." -ForegroundColor Green
