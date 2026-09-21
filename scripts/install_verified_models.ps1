param(
    [string]$ComfyRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $RepoRoot "art_pipeline\model_manifest.json"

function Find-ComfyRoot {
    param([string]$Explicit)

    if ($Explicit -and (Test-Path $Explicit)) {
        return (Resolve-Path $Explicit).Path
    }

    $candidates = @(
        (Join-Path $env:USERPROFILE "ComfyUI"),
        (Join-Path $env:USERPROFILE "Documents\ComfyUI"),
        (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI\resources\ComfyUI"),
        (Join-Path $env:APPDATA "ComfyUI")
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($candidate in $candidates) {
        if (Test-Path (Join-Path $candidate "models")) {
            return (Resolve-Path $candidate).Path
        }
    }

    return $null
}

$root = Find-ComfyRoot -Explicit $ComfyRoot

Write-Host ""
Write-Host "Black-Ink Bestiary - Verified Model Setup" -ForegroundColor Cyan
Write-Host "=========================================="

if (-not $root) {
    Write-Host ""
    Write-Host "ComfyUI model root was not found automatically." -ForegroundColor Yellow
    Write-Host "After ComfyUI is installed, run:"
    Write-Host 'powershell -ExecutionPolicy Bypass -File scripts\install_verified_models.ps1 -ComfyRoot "C:\path\to\ComfyUI"'
    exit 2
}

Write-Host "ComfyUI root: $root" -ForegroundColor Green
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

foreach ($model in $manifest.required_models) {
    $destination = Join-Path $root $model.relative_path
    $directory = Split-Path -Parent $destination

    if (-not (Test-Path $directory)) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }

    if (Test-Path $destination) {
        $size = (Get-Item $destination).Length
        if ($size -gt 100MB) {
            Write-Host "OK      $($model.filename)" -ForegroundColor Green
            continue
        }
        Write-Host "REPLACE $($model.filename) exists but is suspiciously small" -ForegroundColor Yellow
    } else {
        Write-Host "MISSING $($model.filename)" -ForegroundColor Yellow
    }

    Write-Host "Downloading official $($model.role): $($model.filename)"
    try {
        Start-BitsTransfer -Source $model.url -Destination $destination -DisplayName "Black-Ink $($model.filename)"
    } catch {
        Write-Host "BITS unavailable; using Invoke-WebRequest..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $model.url -OutFile $destination -UseBasicParsing
    }

    if (-not (Test-Path $destination) -or (Get-Item $destination).Length -lt 100MB) {
        throw "Download failed or file is unexpectedly small: $destination"
    }
    Write-Host "DONE    $($model.filename)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Verified Black-Ink v1 model set is installed." -ForegroundColor Green
Write-Host "Restart ComfyUI if it was already running."
Write-Host ""
