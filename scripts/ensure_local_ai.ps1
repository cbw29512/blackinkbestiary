param(
  [int]$ComfyTimeoutSeconds = 90,
  [int]$OllamaTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

. (Join-Path $PSScriptRoot "local_runtime_helpers.ps1")

$runtimeStatusPath = Join-Path $root "data\local-runtime-status.json"
$script:CurrentStage = "startup"
$script:CurrentDetail = "Initializing local AI runtime checks."

function Write-RuntimeStatus(
  [string]$Status,
  [string]$Stage,
  [string]$Message,
  [string]$Detail = ""
) {
  Write-BlackInkRuntimeStatus $runtimeStatusPath $Status $Stage $Message $Detail
}

function Set-RuntimeStage(
  [string]$Stage,
  [string]$Message,
  [string]$Detail = ""
) {
  $script:CurrentStage = $Stage
  $script:CurrentDetail = $Detail
  Write-RuntimeStatus "starting" $Stage $Message $Detail
  Write-Host "$Stage - $Message"
}

trap {
  $message = [string]$_.Exception.Message
  try {
    Write-RuntimeStatus "failed" $script:CurrentStage $message $script:CurrentDetail
  } catch {}
  Write-Host "Local AI runtime failed at '$($script:CurrentStage)': $message" -ForegroundColor Red
  if ($script:CurrentDetail) {
    Write-Host "Context: $($script:CurrentDetail)" -ForegroundColor DarkYellow
  }
  exit 1
}

Set-RuntimeStage "config-load" "Reading local AI configuration."
$configPath = Join-Path $root "config\local_ai_stack.json"
if (-not (Test-Path $configPath -PathType Leaf)) {
  throw "Missing local AI config: $configPath"
}
$config = Get-Content $configPath -Raw | ConvertFrom-Json

$comfyHealth = "$($config.comfy_url.TrimEnd('/'))/system_stats"
Set-RuntimeStage "comfy-health" "Checking ComfyUI API." $comfyHealth
if (-not (Test-BlackInkJsonEndpoint $comfyHealth 2)) {
  Set-RuntimeStage "comfy-discovery" "Locating ComfyUI Desktop."
  $desktopExe = Find-BlackInkComfyDesktopExe
  if (-not $desktopExe) {
    throw "ComfyUI is not reachable and the installed ComfyUI Desktop executable could not be found."
  }

  Set-RuntimeStage "comfy-launch" "Starting ComfyUI Desktop." $desktopExe
  $script:CurrentDetail = "Executable: $desktopExe"
  $launchMethod = Start-BlackInkDetachedLocalProcess $desktopExe

  Set-RuntimeStage "comfy-wait" "Waiting for ComfyUI API after $launchMethod." $comfyHealth
  Wait-BlackInkEndpoint $comfyHealth $ComfyTimeoutSeconds "ComfyUI"
}
Write-Host "ComfyUI ready." -ForegroundColor Green

$vision = $config.vision_reviewer
if (-not $vision -or -not $vision.required) {
  throw "Required semantic vision reviewer is not configured."
}
$ollamaBase = [string]$vision.base_url
$ollamaTagsUrl = "$($ollamaBase.TrimEnd('/'))/api/tags"

Set-RuntimeStage "ollama-health" "Checking Ollama API." $ollamaTagsUrl
if (-not (Test-BlackInkJsonEndpoint $ollamaTagsUrl 2)) {
  Set-RuntimeStage "ollama-discovery" "Locating Ollama CLI."
  $ollama = Get-Command ollama -ErrorAction SilentlyContinue
  if (-not $ollama) {
    throw "Ollama is not reachable and the ollama CLI is not installed or on PATH."
  }

  Set-RuntimeStage "ollama-launch" "Starting Ollama service." $ollama.Source
  $script:CurrentDetail = "Executable: $($ollama.Source); arguments: serve"
  $launchMethod = Start-BlackInkDetachedLocalProcess $ollama.Source @("serve")

  Set-RuntimeStage "ollama-wait" "Waiting for Ollama API after $launchMethod." $ollamaTagsUrl
  Wait-BlackInkEndpoint $ollamaTagsUrl $OllamaTimeoutSeconds "Ollama"
}
Write-Host "Ollama ready." -ForegroundColor Green

$visionModel = [string]$vision.model
Set-RuntimeStage "ollama-model-check" "Checking required semantic vision model." $visionModel
$tags = Invoke-RestMethod -Uri $ollamaTagsUrl -TimeoutSec 5
$installed = @($tags.models | ForEach-Object { [string]$_.name })
if (-not ($installed | Where-Object { $_ -eq $visionModel -or $_ -like "$visionModel*" })) {
  $ollama = Get-Command ollama -ErrorAction SilentlyContinue
  if (-not $ollama) {
    throw "Required vision model $visionModel is missing and ollama CLI is unavailable."
  }

  Set-RuntimeStage "ollama-model-pull" "Installing required semantic vision model." $visionModel
  & $ollama.Source pull $visionModel
  if ($LASTEXITCODE -ne 0) {
    throw "Ollama failed to install required vision model $visionModel (exit $LASTEXITCODE)."
  }
}

Set-RuntimeStage "reviewer-smoke-test" "Testing semantic reviewer response." "$ollamaBase / $visionModel"
$smokeBody = @{
  model = $visionModel
  stream = $false
  prompt = 'Reply with exactly this JSON and nothing else: {"pass":true,"score":100,"defects":[],"preserve":[]}'
  options = @{ temperature = 0; num_predict = 256 }
} | ConvertTo-Json -Depth 8

$smoke = Invoke-RestMethod -Method Post -Uri "$($ollamaBase.TrimEnd('/'))/api/generate" -ContentType "application/json" -Body $smokeBody -TimeoutSec 120
$payload = [string]$smoke.response
if ([string]::IsNullOrWhiteSpace($payload)) {
  throw "Semantic vision smoke test returned an empty response."
}
$verdict = $payload | ConvertFrom-Json
if ($verdict.pass -ne $true -or $null -eq $verdict.defects) {
  throw "Semantic vision smoke test returned unexpected structured output: $payload"
}

$script:CurrentStage = "complete"
$script:CurrentDetail = ""
Write-RuntimeStatus "ready" "complete" "Local artist and semantic reviewer are ready."
Write-Host "Local artist + semantic reviewer ready." -ForegroundColor Green
exit 0
