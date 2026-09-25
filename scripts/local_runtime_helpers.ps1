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

function Test-BlackInkJsonEndpoint([string]$Uri, [int]$TimeoutSec = 2) {
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
    if (Test-BlackInkJsonEndpoint $Uri 2) { return }
    Start-Sleep -Seconds 2
  }
  throw "$Label did not become ready within $TimeoutSeconds seconds at $Uri."
}

function Find-BlackInkComfyWorkspace(
  [string]$Root,
  [string]$ConfiguredWorkspace
) {
  $candidates = @()
  if ($env:LOCALAPPDATA) {
    $candidates += Join-Path $env:LOCALAPPDATA "Comfy-Desktop\ComfyUI-Installs\Black-Ink Bestiary\ComfyUI"
  }
  if ($ConfiguredWorkspace) {
    $candidate = if ([IO.Path]::IsPathRooted($ConfiguredWorkspace)) {
      $ConfiguredWorkspace
    } else {
      Join-Path $Root $ConfiguredWorkspace
    }
    $candidates += $candidate
  }

  foreach ($candidate in $candidates | Select-Object -Unique) {
    if (Test-Path (Join-Path $candidate "main.py") -PathType Leaf) {
      return $candidate
    }
    $nested = Join-Path $candidate "ComfyUI"
    if (Test-Path (Join-Path $nested "main.py") -PathType Leaf) {
      return $nested
    }
  }
  return $null
}

function Find-BlackInkComfyPython([string]$Workspace) {
  $parent = Split-Path -Parent $Workspace
  $candidates = @(
    (Join-Path $Workspace ".venv\Scripts\python.exe"),
    (Join-Path $Workspace "venv\Scripts\python.exe"),
    (Join-Path $parent ".venv\Scripts\python.exe"),
    (Join-Path $parent "python_embeded\python.exe")
  )
  foreach ($candidate in $candidates) {
    if (Test-Path $candidate -PathType Leaf) { return $candidate }
  }
  return $null
}

function Invoke-BlackInkCommand(
  [string]$FilePath,
  [string[]]$Arguments = @()
) {
  $quoted = @($Arguments | ForEach-Object {
    '"' + ([string]$_).Replace('"', '\\"') + '"'
  })

  $startInfo = New-Object System.Diagnostics.ProcessStartInfo
  $startInfo.FileName = $FilePath
  $startInfo.Arguments = ($quoted -join " ")
  $startInfo.UseShellExecute = $false
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $startInfo.CreateNoWindow = $true

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $startInfo
  try {
    $null = $process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = [string]$stdoutTask.Result
    $stderr = [string]$stderrTask.Result
    $combined = (($stdout.Trim(), $stderr.Trim()) | Where-Object { $_ }) -join [Environment]::NewLine
    return @{
      exit_code = $process.ExitCode
      output = $combined
    }
  } finally {
    $process.Dispose()
  }
}

function Quote-BlackInkArgument([string]$Value) {
  if ($Value -notmatch '[\s"]') { return $Value }
  return '"' + $Value.Replace('"', '\\"') + '"'
}

function Get-BlackInkLogTail(
  [string]$Path,
  [int]$MaxChars = 3000
) {
  if (-not $Path -or -not (Test-Path $Path -PathType Leaf)) { return "" }
  $text = Get-Content $Path -Raw -ErrorAction SilentlyContinue
  if (-not $text) { return "" }
  $text = $text.Trim()
  if ($text.Length -gt $MaxChars) {
    return $text.Substring($text.Length - $MaxChars)
  }
  return $text
}

function Start-BlackInkDetachedLocalProcess(
  [string]$FilePath,
  [string[]]$Arguments = @(),
  [string]$WorkingDirectory = "",
  [string]$StdoutPath = "",
  [string]$StderrPath = ""
) {
  $argumentLine = (@($Arguments | ForEach-Object {
    Quote-BlackInkArgument ([string]$_)
  }) -join " ")

  try {
    $start = @{
      FilePath = $FilePath
      ArgumentList = $argumentLine
      WindowStyle = "Hidden"
      ErrorAction = "Stop"
    }
    if ($WorkingDirectory) { $start.WorkingDirectory = $WorkingDirectory }
    if ($StdoutPath) {
      Remove-Item $StdoutPath -Force -ErrorAction SilentlyContinue
      $start.RedirectStandardOutput = $StdoutPath
    }
    if ($StderrPath) {
      Remove-Item $StderrPath -Force -ErrorAction SilentlyContinue
      $start.RedirectStandardError = $StderrPath
    }
    Start-Process @start | Out-Null
    return "Start-Process"
  } catch {
    $firstError = [string]$_.Exception.Message
    try {
      $shell = New-Object -ComObject Shell.Application
      $shell.ShellExecute($FilePath, $argumentLine, $WorkingDirectory, "open", 0)
      return "ShellExecute"
    } catch {
      throw "Could not launch '$FilePath'. Start-Process failed: $firstError; ShellExecute failed: $($_.Exception.Message)"
    }
  }
}
