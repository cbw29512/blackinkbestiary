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
  try { Write-RuntimeStatus "failed" $script:CurrentStage $message $script:CurrentDetail } catch {}
  Write-Host "Local AI runtime failed at '$($script:CurrentStage)': $message" -ForegroundColor Red
  if ($script:CurrentDetail) { Write-Host "Context: $($script:CurrentDetail)" -ForegroundColor DarkYellow }
  exit 1
}

Set-RuntimeStage "config-load" "Reading local AI configuration."
$configPath = Join-Path $root "config\local_ai_stack.json"
if (-not (Test-Path $configPath -PathType Leaf)) { throw "Missing local AI config: $configPath" }
$config = Get-Content $configPath -Raw | ConvertFrom-Json

$comfyHealth = "$($config.comfy_url.TrimEnd('/'))/system_stats"
$launchArgs = @(
  @($config.production_policy.comfy_launch_args) |
    Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
    ForEach-Object { [string]$_ }
)
$launchMode = [string]$config.production_policy.comfy_launch_mode
if ([string]::IsNullOrWhiteSpace($launchMode)) { $launchMode = "managed_direct_python" }

$comfyStdout = Join-Path $root "data\comfy-runtime.stdout.log"
$comfyStderr = Join-Path $root "data\comfy-runtime.stderr.log"

Set-RuntimeStage "comfy-health" "Checking ComfyUI API." $comfyHealth
if (-not (Test-BlackInkJsonEndpoint $comfyHealth 2)) {
  Set-RuntimeStage "comfy-discovery" "Locating Black-Ink ComfyUI workspace."
  $comfyWorkspace = Find-BlackInkComfyWorkspace $root ([string]$config.workspace)
  if (-not $comfyWorkspace) { throw "Black-Ink ComfyUI workspace root could not be found." }

  $comfyRoot = Join-Path $comfyWorkspace "ComfyUI"
  $mainPy = Join-Path $comfyRoot "main.py"
  $comfyPython = Find-BlackInkComfyPython $comfyWorkspace
  if (-not $comfyPython) {
    throw "No valid ComfyUI workspace Python was found for persistent logged launch."
  }

  # Stop a stale comfy-cli-managed process when possible, but do not require
  # comfy-cli for recovery. The direct workspace Python is the stable authority.
  $comfyCli = Join-Path $root ".blackink-tools\Scripts\comfy.exe"
  if (Test-Path $comfyCli -PathType Leaf) {
    Set-RuntimeStage "comfy-stop" "Clearing any stale comfy-cli background record." $comfyWorkspace
    $null = Invoke-BlackInkCommand $comfyCli @("--workspace=$comfyWorkspace", "stop")
  }

  if ($launchMode -ne "managed_direct_python") {
    throw "Unsupported production_policy.comfy_launch_mode: $launchMode"
  }

  $runtimeArgs = @(
    $mainPy,
    "--listen", "127.0.0.1",
    "--port", "8188"
  ) + $launchArgs

  $argSummary = ($runtimeArgs | ForEach-Object { [string]$_ }) -join " "
  Set-RuntimeStage "comfy-launch" "Starting logged ComfyUI runtime." "Python: $comfyPython; args: $argSummary; stdout: $comfyStdout; stderr: $comfyStderr"
  $launchMethod = Start-BlackInkDetachedLocalProcess $comfyPython $runtimeArgs $comfyRoot $comfyStdout $comfyStderr

  Set-RuntimeStage "comfy-wait" "Waiting for logged ComfyUI API after $launchMethod." $comfyHealth
  try {
    Wait-BlackInkEndpoint $comfyHealth $ComfyTimeoutSeconds "ComfyUI"
  } catch {
    $stdoutTail = Get-BlackInkLogTail $comfyStdout
    $stderrTail = Get-BlackInkLogTail $comfyStderr
    $script:CurrentDetail = "workspace=$comfyWorkspace; launch_args=$argSummary; stdout=$stdoutTail; stderr=$stderrTail"
    throw
  }
}
Write-Host "ComfyUI ready. Runtime logs: data/comfy-runtime.stdout.log + data/comfy-runtime.stderr.log" -ForegroundColor Green

$vision = $config.vision_reviewer
$reviewerRequired = $false
$reviewerAuthority = "advisory"
if ($vision) {
  $reviewerRequired = [bool]$vision.required
  if ($vision.authority) { $reviewerAuthority = [string]$vision.authority }
}

function Complete-WithoutLocalReviewer([string]$Reason) {
  if ($reviewerRequired) { throw $Reason }
  $script:CurrentStage = "complete"
  $script:CurrentDetail = $Reason
  Write-RuntimeStatus "ready" "complete" "Local artist ready; advisory vision reviewer unavailable." $Reason
  Write-Host "Local artist ready. Advisory vision reviewer unavailable: $Reason" -ForegroundColor Yellow
  exit 0
}

if (-not $vision) {
  Complete-WithoutLocalReviewer "No local vision reviewer is configured."
}

$ollamaBase = [string]$vision.base_url
$ollamaTagsUrl = "$($ollamaBase.TrimEnd('/'))/api/tags"

Set-RuntimeStage "ollama-health" "Checking advisory Ollama reviewer API." $ollamaTagsUrl
if (-not (Test-BlackInkJsonEndpoint $ollamaTagsUrl 2)) {
  Set-RuntimeStage "ollama-discovery" "Locating Ollama CLI for advisory reviewer."
  $ollama = Get-Command ollama -ErrorAction SilentlyContinue
  if (-not $ollama) {
    Complete-WithoutLocalReviewer "Ollama is not reachable and the ollama CLI is unavailable."
  }

  Set-RuntimeStage "ollama-launch" "Starting advisory Ollama reviewer service." $ollama.Source
  $launchMethod = Start-BlackInkDetachedLocalProcess $ollama.Source @("serve")
  Set-RuntimeStage "ollama-wait" "Waiting for advisory Ollama API after $launchMethod." $ollamaTagsUrl
  try {
    Wait-BlackInkEndpoint $ollamaTagsUrl $OllamaTimeoutSeconds "Ollama"
  } catch {
    Complete-WithoutLocalReviewer ([string]$_.Exception.Message)
  }
}
Write-Host "Ollama advisory reviewer reachable." -ForegroundColor Green

$visionModel = [string]$vision.model
Set-RuntimeStage "ollama-model-check" "Checking advisory vision model." $visionModel
$tags = Invoke-RestMethod -Uri $ollamaTagsUrl -TimeoutSec 5
$installed = @($tags.models | ForEach-Object { [string]$_.name })
if (-not ($installed | Where-Object { $_ -eq $visionModel -or $_ -like "$visionModel*" })) {
  $ollama = Get-Command ollama -ErrorAction SilentlyContinue
  if (-not $ollama) {
    Complete-WithoutLocalReviewer "Advisory vision model $visionModel is missing and ollama CLI is unavailable."
  }
  Set-RuntimeStage "ollama-model-pull" "Installing advisory vision model." $visionModel
  & $ollama.Source pull $visionModel
  if ($LASTEXITCODE -ne 0) {
    Complete-WithoutLocalReviewer "Ollama failed to install advisory vision model $visionModel (exit $LASTEXITCODE)."
  }
}

Set-RuntimeStage "reviewer-smoke-test" "Testing advisory vision reviewer response." "$ollamaBase / $visionModel"
$smokeBody = @{
  model = $visionModel
  stream = $false
  prompt = 'Reply with exactly this JSON and nothing else: {"pass":true,"score":100,"defects":[],"preserve":[]}'
  options = @{ temperature = 0; num_predict = 256 }
} | ConvertTo-Json -Depth 8

try {
  $smoke = Invoke-RestMethod -Method Post -Uri "$($ollamaBase.TrimEnd('/'))/api/generate" -ContentType "application/json" -Body $smokeBody -TimeoutSec 120
  $payload = [string]$smoke.response
  if ([string]::IsNullOrWhiteSpace($payload)) { throw "Vision smoke test returned an empty response." }
  $verdict = $payload | ConvertFrom-Json
  if ($verdict.pass -ne $true -or $null -eq $verdict.defects) {
    throw "Vision smoke test returned unexpected structured output: $payload"
  }
} catch {
  Complete-WithoutLocalReviewer ([string]$_.Exception.Message)
}

$script:CurrentStage = "complete"
$script:CurrentDetail = ""
Write-RuntimeStatus "ready" "complete" "Local artist ready; local vision reviewer is advisory." "authority=$reviewerAuthority"
Write-Host "Local artist ready. Local vision reviewer is advisory only." -ForegroundColor Green
exit 0
