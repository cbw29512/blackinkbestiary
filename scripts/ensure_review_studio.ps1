param(
  [int]$Port = 8766,
  [int]$StartupTimeoutSeconds = 12
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DataDir = Join-Path $Root "data"
$StatusPath = Join-Path $DataDir "review-studio-runtime-status.json"
$StdoutPath = Join-Path $DataDir "review-studio-runtime.stdout.log"
$StderrPath = Join-Path $DataDir "review-studio-runtime.stderr.log"
$HealthUrl = "http://127.0.0.1:$Port/api/health"

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

function Write-Status([string]$Status, [string]$Message, [string]$Python = "", [int]$ProcessId = 0) {
  [ordered]@{
    schema_version = 1
    service = "human-review"
    status = $Status
    message = $Message
    python = $Python
    pid = if ($ProcessId -gt 0) { $ProcessId } else { $null }
    url = "http://127.0.0.1:$Port/human-review.html"
    health_url = $HealthUrl
    stdout_log = "data/review-studio-runtime.stdout.log"
    stderr_log = "data/review-studio-runtime.stderr.log"
    updated_at = [DateTimeOffset]::UtcNow.ToString("o")
  } | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $StatusPath
}

function Test-Health {
  try {
    $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
    return [bool]($response.ok -and $response.service -eq "human-review")
  } catch {
    return $false
  }
}

function Tail-Text([string]$Path, [int]$Lines = 30) {
  if (-not (Test-Path $Path -PathType Leaf)) { return "" }
  return ((Get-Content $Path -Tail $Lines -ErrorAction SilentlyContinue) -join [Environment]::NewLine).Trim()
}

if (Test-Health) {
  Write-Status "ready" "Human Review Studio already reachable."
  Write-Host "Black Ink Review Studio ready at http://127.0.0.1:$Port/human-review.html" -ForegroundColor Green
  exit 0
}

$candidates = New-Object System.Collections.Generic.List[string]
$preflightPath = Join-Path $DataDir "engine-preflight-status.json"
if (Test-Path $preflightPath -PathType Leaf) {
  try {
    $preflight = Get-Content $preflightPath -Raw | ConvertFrom-Json
    $recorded = [string]$preflight.python
    if ($recorded -and (Test-Path $recorded -PathType Leaf)) {
      $candidates.Add([IO.Path]::GetFullPath($recorded))
    }
  } catch {}
}

$projectPython = Join-Path $Root ".blackink-tools\Scripts\python.exe"
if (Test-Path $projectPython -PathType Leaf) {
  $candidates.Add([IO.Path]::GetFullPath($projectPython))
}

$systemPython = Get-Command python -ErrorAction SilentlyContinue
if ($systemPython -and $systemPython.Source -and (Test-Path $systemPython.Source -PathType Leaf)) {
  $candidates.Add([IO.Path]::GetFullPath($systemPython.Source))
}

$candidates = @($candidates | Select-Object -Unique)
if (-not $candidates.Count) {
  Write-Status "failed" "No usable Python interpreter was found."
  Write-Host "Human Review Studio could not start: no usable Python interpreter was found." -ForegroundColor Red
  exit 2
}

foreach ($python in $candidates) {
  Remove-Item $StdoutPath,$StderrPath -Force -ErrorAction SilentlyContinue
  Write-Status "starting" "Starting dedicated Human Review Studio." $python
  try {
    $arguments = @(
      (Join-Path $Root "scripts\human_review_web_server.py"),
      "--host", "127.0.0.1",
      "--port", [string]$Port
    )
    $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath -PassThru
  } catch {
    Write-Status "retrying" ("Launch failed with {0}: {1}" -f $python, $_.Exception.Message) $python
    continue
  }

  $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
  while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-Health) {
      Write-Status "ready" "Dedicated Human Review Studio is reachable." $python $process.Id
      Write-Host "Black Ink Review Studio ready at http://127.0.0.1:$Port/human-review.html" -ForegroundColor Green
      exit 0
    }
    $process.Refresh()
    if ($process.HasExited) { break }
    Start-Sleep -Milliseconds 500
  }

  if (-not $process.HasExited) {
    try { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue } catch {}
  }
  $detail = Tail-Text $StderrPath
  if (-not $detail) { $detail = Tail-Text $StdoutPath }
  if (-not $detail) { $detail = "Review server exited or timed out before health check." }
  Write-Status "retrying" $detail $python
}

$final = Tail-Text $StderrPath
if (-not $final) { $final = Tail-Text $StdoutPath }
if (-not $final) { $final = "No Python candidate brought the Human Review Studio online." }
Write-Status "failed" $final
Write-Host "Human Review Studio failed to start." -ForegroundColor Red
Write-Host "See data\review-studio-runtime-status.json and data\review-studio-runtime.stderr.log." -ForegroundColor Yellow
exit 1
