param(
    [string]$ComfyRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $RepoRoot "art_pipeline\model_manifest.json"
$LogPath = Join-Path $RepoRoot "install_verified_models.log"

function Write-Log {
    param([string]$Message, [string]$Color = "Gray")
    Write-Host $Message -ForegroundColor $Color
    Add-Content -Path $LogPath -Value $Message
}

function Resolve-ComfyInstallRoot {
    param([string]$Explicit)

    if ($Explicit -and (Test-Path $Explicit)) {
        return (Resolve-Path $Explicit).Path
    }

    $installationsFile = Join-Path $env:APPDATA "Comfy Desktop\installations.json"
    if (Test-Path $installationsFile) {
        try {
            $installations = Get-Content $installationsFile -Raw | ConvertFrom-Json
            $target = $installations | Where-Object {
                $_.name -eq "Black-Ink Bestiary" -and $_.installPath -and (Test-Path $_.installPath)
            } | Select-Object -First 1

            if (-not $target) {
                $target = $installations | Where-Object {
                    $_.sourceId -ne "cloud" -and $_.installPath -and (Test-Path $_.installPath)
                } | Select-Object -First 1
            }

            if ($target) {
                return (Resolve-Path $target.installPath).Path
            }
        } catch {
            Write-Log "Could not parse Comfy Desktop installations.json: $($_.Exception.Message)" "Yellow"
        }
    }

    $legacyCandidates = @(
        (Join-Path $env:USERPROFILE "ComfyUI"),
        (Join-Path $env:USERPROFILE "Documents\ComfyUI"),
        (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI\resources\ComfyUI"),
        (Join-Path $env:APPDATA "ComfyUI")
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($candidate in $legacyCandidates) {
        if ((Test-Path (Join-Path $candidate "ComfyUI\models")) -or (Test-Path (Join-Path $candidate "models"))) {
            return (Resolve-Path $candidate).Path
        }
    }

    return $null
}

function Resolve-ModelsRoot {
    param([string]$InstallRoot)

    $nested = Join-Path $InstallRoot "ComfyUI\models"
    if (Test-Path (Split-Path -Parent $nested)) {
        return $nested
    }

    $direct = Join-Path $InstallRoot "models"
    if (Test-Path $direct) {
        return $direct
    }

    # Current standalone/multi-instance installs normally use <installPath>\ComfyUI\models.
    return $nested
}

Set-Content -Path $LogPath -Value ("Black-Ink Bestiary model installer - " + (Get-Date))

Write-Host ""
Write-Host "Black-Ink Bestiary - Verified Model Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

try {
    if (-not (Test-Path $ManifestPath)) {
        throw "Model manifest not found at $ManifestPath"
    }

    $root = Resolve-ComfyInstallRoot -Explicit $ComfyRoot
    if (-not $root) {
        throw "Could not locate the Black-Ink Bestiary Comfy Desktop instance. Expected installation metadata at %APPDATA%\Comfy Desktop\installations.json."
    }

    $modelsRoot = Resolve-ModelsRoot -InstallRoot $root

    Write-Log "Comfy install root: $root" "Green"
    Write-Log "Models root:       $modelsRoot" "Green"

    $manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

    foreach ($model in $manifest.required_models) {
        $relative = $model.relative_path -replace '^models[\\/]', ''
        $destination = Join-Path $modelsRoot $relative
        $directory = Split-Path -Parent $destination

        if (-not (Test-Path $directory)) {
            New-Item -ItemType Directory -Force -Path $directory | Out-Null
        }

        if (Test-Path $destination) {
            $size = (Get-Item $destination).Length
            if ($size -gt 100MB) {
                Write-Log ("OK      " + $model.filename) "Green"
                continue
            }
            Write-Log ("REPLACE " + $model.filename + " exists but is suspiciously small") "Yellow"
            Remove-Item $destination -Force
        } else {
            Write-Log ("MISSING " + $model.filename) "Yellow"
        }

        Write-Log ("Downloading official " + $model.role + ": " + $model.filename) "Cyan"
        try {
            Start-BitsTransfer -Source $model.url -Destination $destination -DisplayName ("Black-Ink " + $model.filename) -ErrorAction Stop
        } catch {
            Write-Log "BITS download unavailable; falling back to Invoke-WebRequest." "Yellow"
            Invoke-WebRequest -Uri $model.url -OutFile $destination -UseBasicParsing
        }

        if (-not (Test-Path $destination)) {
            throw "Download did not create $destination"
        }

        $finalSize = (Get-Item $destination).Length
        if ($finalSize -lt 100MB) {
            throw "Downloaded file is unexpectedly small: $destination ($finalSize bytes)"
        }

        Write-Log ("DONE    " + $model.filename) "Green"
    }

    Write-Host ""
    Write-Log "VERIFIED MODEL SET INSTALLED" "Green"
    Write-Log "Restart the Black-Ink Bestiary ComfyUI instance after this installer finishes." "Green"
    exit 0
}
catch {
    Write-Host ""
    Write-Log ("ERROR: " + $_.Exception.Message) "Red"
    Write-Log ("See log: " + $LogPath) "Yellow"
    exit 1
}
