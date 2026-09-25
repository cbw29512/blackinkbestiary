$ErrorActionPreference = "Stop"

function Write-BlackInkRuntimeStatus(
  [string]$Path,
  [string]$Status,
  [string]$Stage,
  [string]$Message,
  [string]$Detail = ""
) {
  $payload = [ordered]@{
    schema_version = 2
    status = $Status
    stage = $Stage
    message = $Message
    detail = $Detail
    updated_at = (Get-Date).ToUniversalTime().ToString("o")
  }
  $parent = Split-Path -Parent $Path
  if (-not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
  $payload | ConvertTo-Json -Depth 4 | Set-Content -Path $Path -Encoding UTF8
}

function Test-BlackInkJsonEndpoint(
  [string]$Uri,
  [int]$TimeoutSec = 2
) {
  try {
    Invoke-RestMethod -Uri $Uri -TimeoutSec $TimeoutSec | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Wait-BlackInkEndpoint(
  [string]$Uri,
  [int]$TimeoutSeconds,
  [string]$Label
) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-BlackInkJsonEndpoint $Uri 2) {
      return
    }
    Start-Sleep -Seconds 2
  }
  throw "$Label did not become ready within $TimeoutSeconds seconds at $Uri."
}

function Find-BlackInkComfyDesktopExe {
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI\ComfyUI.exe"),
    (Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\ComfyUI Desktop\ComfyUI.exe")
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
      return $candidate
    }
  }

  if ($env:LOCALAPPDATA -and (Test-Path $env:LOCALAPPDATA)) {
    $hit = Get-ChildItem -Path $env:LOCALAPPDATA -Include "ComfyUI.exe","ComfyUI Desktop.exe" -File -Recurse -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($hit) {
      return $hit.FullName
    }
  }
  return $null
}

function Start-BlackInkDetachedLocalProcess(
  [string]$FilePath,
  [string[]]$Arguments = @()
) {
  try {
    Start-Process -FilePath $FilePath -ArgumentList $Arguments -WindowStyle Hidden -ErrorAction Stop | Out-Null
    return "Start-Process"
  } catch {
    $firstError = [string]$_.Exception.Message
    try {
      $shell = New-Object -ComObject Shell.Application
      $shell.ShellExecute($FilePath, ($Arguments -join " "), "", "open", 0)
      return "ShellExecute"
    } catch {
      throw "Could not launch '$FilePath'. Start-Process failed: $firstError; ShellExecute failed: $($_.Exception.Message)"
    }
  }
}
