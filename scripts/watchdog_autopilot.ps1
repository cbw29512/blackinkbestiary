param(
    [int]$StaleMinutes = 45,
    [int]$StartupGraceMinutes = 10
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$DataDir = Join-Path $RepoRoot "data"
$LogPath = Join-Path $DataDir "autopilot-watchdog.log"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

function Write-WatchdogLog([string]$Message) {
    $stamp = (Get-Date).ToUniversalTime().ToString("o")
    Add-Content -Path $LogPath -Value "$stamp $Message"
    Write-Host $Message
}

function Get-AutopilotProcesses {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq "cmd.exe" -and
            $_.CommandLine -match "RUN_ENGINE_AUTOPILOT\\.bat"
        })
}

function Start-Autopilot {
    $bat = Join-Path $RepoRoot "RUN_ENGINE_AUTOPILOT.bat"
    Write-WatchdogLog "Starting Black Ink Bestiary autopilot."
    $arguments = @("/c", "call `"$bat`"")
    Start-Process -FilePath $env:ComSpec -ArgumentList $arguments -WorkingDirectory $RepoRoot -WindowStyle Minimized | Out-Null
}

$running = Get-AutopilotProcesses
if ($running.Count -eq 0) {
    Write-WatchdogLog "Autopilot process missing; restarting."
    Start-Autopilot
    exit 0
}

$now = Get-Date
$youngestAgeMinutes = $null
foreach ($proc in $running) {
    if ($proc.CreationDate) {
        if ($proc.CreationDate -is [datetime]) {
            $created = [datetime]$proc.CreationDate
        } else {
            $created = [Management.ManagementDateTimeConverter]::ToDateTime([string]$proc.CreationDate)
        }
        $age = ($now - $created).TotalMinutes
        if ($youngestAgeMinutes -eq $null -or $age -lt $youngestAgeMinutes) {
            $youngestAgeMinutes = $age
        }
    }
}
if ($youngestAgeMinutes -ne $null -and $youngestAgeMinutes -lt $StartupGraceMinutes) {
    exit 0
}

$Python = Join-Path $RepoRoot ".blackink-tools\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python (Join-Path $RepoRoot "scripts\autopilot_watchdog.py") --max-age-minutes $StaleMinutes
$healthExit = $LASTEXITCODE

if ($healthExit -eq 0) {
    exit 0
}
if ($healthExit -ne 10) {
    Write-WatchdogLog "Autopilot health check failed with exit code $healthExit; leaving current process intact."
    exit 1
}

Write-WatchdogLog "Autopilot activity is stale; terminating the stuck process tree."
foreach ($proc in $running) {
    & taskkill.exe /PID $proc.ProcessId /T /F | Out-Null
}
Start-Sleep -Seconds 2
Start-Autopilot
exit 0
