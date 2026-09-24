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
  $knownInstall = Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI-Installs\Black-Ink Bestiary\ComfyUI"
  $knownMain = Join-Path $knownInstall "main.py"

  if (Test-Path $knownMain) {
    Write-Host "Found existing ComfyUI Desktop install: $knownInstall" -ForegroundColor Green
    $desktopExe = @(
      (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI\ComfyUI.exe"),
      (Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI.exe"),
      (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI Desktop\ComfyUI.exe")
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $desktopExe) {
      $desktopExe = Get-ChildItem -Path $env:LOCALAPPDATA -Include "ComfyUI.exe","ComfyUI Desktop.exe" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if ($desktopExe) {
      $desktopPath = if ($desktopExe -is [System.IO.FileInfo]) { $desktopExe.FullName } else { [string]$desktopExe }
      Write-Host "Launching ComfyUI Desktop: $desktopPath" -ForegroundColor Yellow
      Start-Process -FilePath $desktopPath | Out-Null
    } else {
      Write-Host "ComfyUI Desktop executable was not found automatically." -ForegroundColor Red
      Write-Host "The model install exists at: $knownInstall"
      Write-Host "Do not reinstall anything. Open your existing ComfyUI Desktop app manually, wait until it is fully loaded, then rerun RUN_COLORING_BOOK.bat."
      throw "ComfyUI Desktop app is required; refusing to start its managed install with a guessed Python runtime."
    }
  } else {
    $mainPy = Find-ComfyMain
    if (-not $mainPy) {
      throw "Existing ComfyUI installation was not found. Open ComfyUI Desktop once, then rerun RUN_COLORING_BOOK.bat."
    }
    throw "A ComfyUI core folder was found at $mainPy, but this launcher will not start it with the wrong Python environment. Open ComfyUI Desktop once, then rerun."
  }

  Write-Host "Waiting for ComfyUI API..." -ForegroundColor Yellow
  $ready = $false
  for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    if (Test-Comfy) { $ready = $true; break }
    if (($i + 1) % 10 -eq 0) { Write-Host "  still starting... $((($i + 1) * 2)) seconds" }
  }
  if (-not $ready) { throw "ComfyUI Desktop did not expose the API at $($config.comfy_url) within 90 seconds. Do not reinstall; open the existing ComfyUI Desktop app and rerun." }
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
