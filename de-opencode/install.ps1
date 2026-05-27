param(
  [string]$InstallRoot = "$env:LOCALAPPDATA\de-opencode",
  [string]$Python = "python",
  [switch]$SetUserEnvironment,
  [switch]$NoSetUserEnvironment,
  [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
  Write-Host "[de-opencode] $Message"
}

$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$BinDir = Join-Path $InstallRoot "bin"
$ToolDir = Join-Path $InstallRoot "tools"

Write-Step "Installing from $SourceRoot"
Write-Step "Target: $InstallRoot"

& $Python --version | Out-Null

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

foreach ($name in @("README.md", "opencode.json", "VERSION", "release-manifest.json", "install.ps1", "install-wsl.sh", "smoke.ps1", "agents", "skills", "plugins", "commands", "tools", "docs", "tests", "samples", "templates")) {
  $src = Join-Path $SourceRoot $name
  $dst = Join-Path $InstallRoot $name
  if (Test-Path $src) {
    if (Test-Path $dst) {
      Remove-Item -Recurse -Force $dst
    }
    Copy-Item -Recurse -Force $src $dst
  }
}

$commands = @{
  "de" = "de.py"
  "de-config" = "de_config.py"
  "de-databricks" = "de_databricks.py"
  "de-dbsql" = "de_dbsql.py"
  "de-mssql" = "de_mssql.py"
  "de-ado" = "de_ado.py"
  "de-pipeline" = "de_pipeline.py"
  "de-ledger" = "de_ledger.py"
  "de-quality" = "de_quality.py"
  "de-repo" = "de_repo.py"
  "de-release" = "de_release.py"
  "de-workbench" = "de_workbench.py"
}

foreach ($entry in $commands.GetEnumerator()) {
  $cmdName = $entry.Key
  $scriptName = $entry.Value
  $scriptPath = Join-Path $ToolDir $scriptName
  $cmdPath = Join-Path $BinDir "$cmdName.cmd"
  $psPath = Join-Path $BinDir "$cmdName.ps1"

  "@echo off`r`n`"$Python`" `"$scriptPath`" %*`r`n" | Set-Content -Encoding ASCII $cmdPath
  @"
& "$Python" "$scriptPath" @args
exit `$LASTEXITCODE
"@ | Set-Content -Encoding ASCII $psPath
}

Write-Step "Generated wrappers in $BinDir"

$env:OPENCODE_CONFIG_DIR = $InstallRoot
$env:PATH = "$BinDir;$env:PATH"

$ShouldSetUserEnvironment = -not $NoSetUserEnvironment
if ($SetUserEnvironment) {
  $ShouldSetUserEnvironment = $true
}

if ($ShouldSetUserEnvironment) {
  [Environment]::SetEnvironmentVariable("OPENCODE_CONFIG_DIR", $InstallRoot, "User")
  $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if (($currentPath -split ";") -notcontains $BinDir) {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$BinDir", "User")
  }
  Write-Step "Set user OPENCODE_CONFIG_DIR and appended wrapper bin to user PATH"
  Write-Step "Restart PowerShell/OpenCode so the new user environment is visible everywhere"
} else {
  Write-Step "User environment update skipped. To use in this shell:"
  Write-Host "  `$env:OPENCODE_CONFIG_DIR = '$InstallRoot'"
  Write-Host "  `$env:PATH = '$BinDir;' + `$env:PATH"
}

Write-Step "Smoke test:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$InstallRoot\smoke.ps1`""

$installRecord = @{
  installed_at = (Get-Date).ToString("o")
  source = $SourceRoot
  target = $InstallRoot
  python = $Python
  commands = @($commands.Keys | Sort-Object)
}
$installRecord | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $InstallRoot "INSTALLATION.json")

if (-not $SkipSmoke) {
  Write-Step "Running smoke test"
  & powershell -ExecutionPolicy Bypass -File (Join-Path $InstallRoot "smoke.ps1") -InstallRoot $InstallRoot -Python $Python
}

Write-Step "Done"
