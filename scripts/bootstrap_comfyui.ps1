$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$config = Get-Content (Join-Path $root "config\local_ai_stack.json") -Raw | ConvertFrom-Json
$workspace = Join-Path $root $config.workspace
$comfyRoot = Join-Path $workspace "ComfyUI"
$mainPy = Join-Path $comfyRoot "main.py"

if (Test-Path $mainPy) {
  Write-Host "ComfyUI workspace already installed." -ForegroundColor Green
  exit 0
}

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) { throw "Git is required to install the project-local ComfyUI workspace." }
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python is required to install ComfyUI." }

New-Item -ItemType Directory -Force -Path $workspace | Out-Null
Write-Host "Cloning ComfyUI into $comfyRoot ..." -ForegroundColor Yellow
& $git.Source clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git $comfyRoot
if ($LASTEXITCODE -ne 0) { throw "ComfyUI clone failed." }

Write-Host "Installing ComfyUI Python requirements..." -ForegroundColor Yellow
& $python.Source -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $python.Source -m pip install -r (Join-Path $comfyRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "ComfyUI requirements installation failed." }

Write-Host "ComfyUI workspace installed." -ForegroundColor Green
Write-Host "Model files are not downloaded by this bootstrap. Existing configured models must already be present or be installed separately." -ForegroundColor Yellow
