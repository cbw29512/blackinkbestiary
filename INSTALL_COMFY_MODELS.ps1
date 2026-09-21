param(
    [string]$ComfyRoot = $env:COMFYUI_ROOT
)

$ErrorActionPreference = "Stop"

function Test-ComfyRoot([string]$Path) {
    if (-not $Path) { return $false }
    return (Test-Path (Join-Path $Path "models"))
}

if (-not (Test-ComfyRoot $ComfyRoot)) {
    $candidates = @(
        (Join-Path $env:USERPROFILE "ComfyUI"),
        (Join-Path $env:USERPROFILE "Documents\ComfyUI"),
        (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI\resources\ComfyUI"),
        (Join-Path $env:APPDATA "ComfyUI")
    )

    foreach ($candidate in $candidates) {
        if (Test-ComfyRoot $candidate) {
            $ComfyRoot = $candidate
            break
        }
    }
}

if (-not (Test-ComfyRoot $ComfyRoot)) {
    Write-Host ""
    Write-Host "I could not auto-detect your ComfyUI model folder."
    $ComfyRoot = Read-Host "Paste the ComfyUI folder that contains the 'models' folder"
}

if (-not (Test-ComfyRoot $ComfyRoot)) {
    throw "That folder does not contain a models directory: $ComfyRoot"
}

Write-Host "Using ComfyUI: $ComfyRoot"

$downloads = @(
    @{
        Url = "https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors?download=true"
        Dir = "diffusion_models"
        Name = "flux-2-klein-4b-fp8.safetensors"
    },
    @{
        Url = "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors?download=true"
        Dir = "text_encoders"
        Name = "qwen_3_4b.safetensors"
    },
    @{
        Url = "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors?download=true"
        Dir = "vae"
        Name = "flux2-vae.safetensors"
    }
)

foreach ($item in $downloads) {
    $dir = Join-Path (Join-Path $ComfyRoot "models") $item.Dir
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $destination = Join-Path $dir $item.Name

    if ((Test-Path $destination) -and ((Get-Item $destination).Length -gt 100MB)) {
        Write-Host "Already present: $($item.Name)"
        continue
    }

    Write-Host ""
    Write-Host "Downloading $($item.Name)..."
    if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) {
        Start-BitsTransfer -Source $item.Url -Destination $destination
    } else {
        Invoke-WebRequest -Uri $item.Url -OutFile $destination -UseBasicParsing
    }
    Write-Host "Saved: $destination"
}

Write-Host ""
Write-Host "Required Black-Ink Bestiary models are installed."
Write-Host "Restart ComfyUI so it discovers the new model files."
