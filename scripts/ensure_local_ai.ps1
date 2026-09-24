param(
  [int]$ComfyTimeoutSeconds = 90,
  [int]$OllamaTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$configPath = Join-Path $root "config\local_ai_stack.json"
if (-not (Test-Path $configPath)) { throw "Missing local AI config: $configPath" }
$config = Get-Content $configPath -Raw | ConvertFrom-Json

function Test-JsonEndpoint([string]$Uri, [int]$TimeoutSec = 2) {
  try {
    Invoke-RestMethod -Uri $Uri -TimeoutSec $TimeoutSec | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Find-ComfyDesktopExe {
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI\ComfyUI.exe"),
    (Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI Desktop\ComfyUI.exe")
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) { return $candidate }
  }

  if ($env:LOCALAPPDATA -and (Test-Path $env:LOCALAPPDATA)) {
    $hit = Get-ChildItem -Path $env:LOCALAPPDATA -Include "ComfyUI.exe","ComfyUI Desktop.exe" -File -Recurse -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($hit) { return $hit.FullName }
  }
  return $null
}

function Wait-Endpoint([string]$Uri, [int]$TimeoutSeconds, [string]$Label) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-JsonEndpoint $Uri 2) { return $true }
    Start-Sleep -Seconds 2
  }
  Write-Host "$Label did not become ready within $TimeoutSeconds seconds." -ForegroundColor Red
  return $false
}

$comfyHealth = "$($config.comfy_url.TrimEnd('/'))/system_stats"
if (-not (Test-JsonEndpoint $comfyHealth 2)) {
  $desktopExe = Find-ComfyDesktopExe
  if (-not $desktopExe) {
    throw "ComfyUI is not reachable and the installed ComfyUI Desktop executable could not be found."
  }
  Write-Host "Starting ComfyUI Desktop..." -ForegroundColor Yellow
  Start-Process -FilePath $desktopExe | Out-Null
  if (-not (Wait-Endpoint $comfyHealth $ComfyTimeoutSeconds "ComfyUI")) {
    throw "ComfyUI API is still unavailable at $($config.comfy_url)."
  }
}
Write-Host "ComfyUI ready." -ForegroundColor Green

$vision = $config.vision_reviewer
if (-not $vision -or -not $vision.required) {
  throw "Required semantic vision reviewer is not configured."
}
$ollamaBase = [string]$vision.base_url
$ollamaTagsUrl = "$($ollamaBase.TrimEnd('/'))/api/tags"

if (-not (Test-JsonEndpoint $ollamaTagsUrl 2)) {
  $ollama = Get-Command ollama -ErrorAction SilentlyContinue
  if (-not $ollama) {
    throw "Ollama is not reachable and the ollama CLI is not installed or on PATH."
  }
  Write-Host "Starting Ollama service..." -ForegroundColor Yellow
  try {
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden | Out-Null
  } catch {
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" | Out-Null
  }
  if (-not (Wait-Endpoint $ollamaTagsUrl $OllamaTimeoutSeconds "Ollama")) {
    throw "Ollama API is still unavailable at $ollamaBase."
  }
}
Write-Host "Ollama ready." -ForegroundColor Green

$visionModel = [string]$vision.model
$tags = Invoke-RestMethod -Uri $ollamaTagsUrl -TimeoutSec 5
$installed = @($tags.models | ForEach-Object { [string]$_.name })
if (-not ($installed | Where-Object { $_ -eq $visionModel -or $_ -like "$visionModel*" })) {
  $ollama = Get-Command ollama -ErrorAction SilentlyContinue
  if (-not $ollama) {
    throw "Required vision model $visionModel is missing and ollama CLI is unavailable."
  }
  Write-Host "Installing required vision model $visionModel..." -ForegroundColor Yellow
  & $ollama.Source pull $visionModel
  if ($LASTEXITCODE -ne 0) {
    throw "Ollama failed to install required vision model $visionModel."
  }
}

$smokeBody = @{
  model = $visionModel
  stream = $false
  prompt = 'Reply with exactly this JSON and nothing else: {"pass":true,"score":100,"defects":[],"preserve":[]}'
  options = @{ temperature = 0; num_predict = 256 }
} | ConvertTo-Json -Depth 8

try {
  $smoke = Invoke-RestMethod -Method Post -Uri "$($ollamaBase.TrimEnd('/'))/api/generate" -ContentType "application/json" -Body $smokeBody -TimeoutSec 120
  $payload = [string]$smoke.response
  if ([string]::IsNullOrWhiteSpace($payload)) { throw "empty response" }
  $verdict = $payload | ConvertFrom-Json
  if ($verdict.pass -ne $true -or $null -eq $verdict.defects) {
    throw "unexpected structured response: $payload"
  }
} catch {
  throw "Semantic vision smoke test failed: $($_.Exception.Message)"
}

Write-Host "Local artist + semantic reviewer ready." -ForegroundColor Green
exit 0
