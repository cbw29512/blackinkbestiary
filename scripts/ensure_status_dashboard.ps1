param(
  [int]$Port = 8765,
  [int]$StartupTimeoutSeconds = 12
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DataDir = Join-Path $Root "data"
$StatusPath = Join-Path $DataDir "dashboard-runtime-status.json"
$StdoutPath = Join-Path $DataDir "dashboard-runtime.stdout.log"
$StderrPath = Join-Path $DataDir "dashboard-runtime.stderr.log"
$HealthUrl = "http://127.0.0.1:$Port/api/health"

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

function Write-DashboardStatus([string]$Status, [string]$Message, [string]$Python = "", [int]$ProcessId = 0) {
  $payload = [ordered]@{
    schema_version = 1
    status = $Status
    message = $Message
    python = $Python
    pid = if ($ProcessId -gt 0) { $ProcessId } else { $null }
    health_url = $HealthUrl
    stdout_log = "data/dashboard-runtime.stdout.log"
    stderr_log = "data/dashboard-runtime.stderr.log"
    updated_at = [DateTimeOffset]::UtcNow.ToString("o")
  }
  $payload | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $StatusPath
}

function Test-DashboardHealth {
  try {
    $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
    return [bool]$response.ok
  } catch {
    return $false
  }
}

function Tail-Text([string]$Path, [int]$Lines = 30) {
  if (-not (Test-Path $Path -PathType Leaf)) { return "" }
  return ((Get-Content $Path -Tail $Lines -ErrorAction SilentlyContinue) -join [Environment]::NewLine).Trim()
}

if (Test-DashboardHealth) {
  Write-DashboardStatus "ready" "Dashboard already reachable."
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
  Write-DashboardStatus "failed" "No usable Python interpreter was found."
  Write-Host "Dashboard could not start: no usable Python interpreter was found." -ForegroundColor Red
  exit 2
}

foreach ($python in $candidates) {
  Remove-Item $StdoutPath,$StderrPath -Force -ErrorAction SilentlyContinue
  Write-DashboardStatus "starting" "Starting dashboard and waiting for /api/health." $python
  try {
    $arguments = @((Join-Path $Root "server.py"), "--host", "127.0.0.1", "--port", [string]$Port, "--no-browser")
    $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath -PassThru
  } catch {
    Write-DashboardStatus "retrying" ("Failed to launch with {0}: {1}" -f $python, $_.Exception.Message) $python
    continue
  }

  $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
  while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-DashboardHealth) {
      Write-DashboardStatus "ready" "Dashboard is reachable." $python $process.Id
      Write-Host "Black-Ink dashboard ready at http://127.0.0.1:$Port" -ForegroundColor Green
      exit 0
    }
    $process.Refresh()
    if ($process.HasExited) { break }
    Start-Sleep -Milliseconds 500
  }

  if (-not $process.HasExited) {
    try { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue } catch {}
  }
  $stderrTail = Tail-Text $StderrPath
  $stdoutTail = Tail-Text $StdoutPath
  $detail = if ($stderrTail) { $stderrTail } elseif ($stdoutTail) { $stdoutTail } else { "server.py exited or timed out before /api/health became reachable." }
  Write-DashboardStatus "retrying" $detail $python
}

$finalError = Tail-Text $StderrPath
if (-not $finalError) { $finalError = Tail-Text $StdoutPath }
if (-not $finalError) { $finalError = "No Python candidate brought the dashboard health endpoint online." }
Write-DashboardStatus "failed" $finalError
Write-Host "Dashboard failed to start. See data\dashboard-runtime.stderr.log and data\dashboard-runtime-status.json." -ForegroundColor Red
exit 1
