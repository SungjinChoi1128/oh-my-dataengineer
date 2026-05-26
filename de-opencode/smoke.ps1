param(
  [string]$InstallRoot = "$PSScriptRoot",
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$ToolDir = Join-Path $InstallRoot "tools"

function Assert-Exists($Path) {
  if (-not (Test-Path $Path)) {
    throw "Missing expected path: $Path"
  }
}

Assert-Exists (Join-Path $InstallRoot "opencode.json")
Assert-Exists (Join-Path $InstallRoot "agents\data-engineer.md")
Assert-Exists (Join-Path $InstallRoot "skills\de-quality-gates\SKILL.md")
Assert-Exists (Join-Path $InstallRoot "plugins\de-guardrails.ts")
Assert-Exists (Join-Path $ToolDir "de_config.py")

& $Python (Join-Path $ToolDir "de.py") doctor | Out-Null
& $Python (Join-Path $ToolDir "de_config.py") doctor | Out-Null
& $Python (Join-Path $ToolDir "de.py") databricks runtime-advisor --current-runtime "15.4" --target-runtime "16.4" | Out-Null
& $Python (Join-Path $ToolDir "de_databricks.py") bundle-doctor --bundle-yaml (Join-Path $InstallRoot "samples\databricks-bundle\databricks.good.yml") | Out-Null
& $Python (Join-Path $ToolDir "de_dbsql.py") classify --sql "SELECT 1" | Out-Null
& $Python (Join-Path $ToolDir "de_dbsql.py") execute --sql "SELECT 1" --dry-run-only --format json | Out-Null
& $Python (Join-Path $ToolDir "de.py") databricks sql execute --sql "SELECT 1" --dry-run-only --result-format json | Out-Null
& $Python (Join-Path $ToolDir "de.py") databricks sql warehouses --help | Out-Null
& $Python (Join-Path $ToolDir "de_mssql.py") classify --sql "SELECT 1" | Out-Null
& $Python (Join-Path $ToolDir "de.py") mssql query --help | Out-Null
& $Python (Join-Path $ToolDir "de_ado.py") classify --operation "pipeline-list" | Out-Null
& $Python (Join-Path $ToolDir "de.py") ado query --help | Out-Null
& $Python (Join-Path $ToolDir "de.py") ado work-item --help | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $env:TEMP "de-opencode-repo-smoke\sql") | Out-Null
Set-Content -Encoding ASCII -Path (Join-Path $env:TEMP "de-opencode-repo-smoke\databricks.yml") -Value "bundle:`n  name: smoke"
Set-Content -Encoding ASCII -Path (Join-Path $env:TEMP "de-opencode-repo-smoke\azure-pipelines.yml") -Value "trigger: none"
Set-Content -Encoding ASCII -Path (Join-Path $env:TEMP "de-opencode-repo-smoke\sql\smoke.sql") -Value "SELECT 1;"
& $Python (Join-Path $ToolDir "de.py") repo init --root (Join-Path $env:TEMP "de-opencode-repo-smoke") | Out-Null
& $Python (Join-Path $ToolDir "de.py") repo doctor --root (Join-Path $env:TEMP "de-opencode-repo-smoke") | Out-Null
& $Python (Join-Path $ToolDir "de.py") repo contract --root (Join-Path $env:TEMP "de-opencode-repo-smoke") | Out-Null
& $Python (Join-Path $ToolDir "de.py") repo brief --root (Join-Path $env:TEMP "de-opencode-repo-smoke") | Out-Null
& $Python (Join-Path $ToolDir "de.py") repo todo --root (Join-Path $env:TEMP "de-opencode-repo-smoke") | Out-Null
& $Python (Join-Path $ToolDir "de.py") repo interview --root (Join-Path $env:TEMP "de-opencode-repo-smoke") | Out-Null
& $Python (Join-Path $ToolDir "de.py") done --claim "install smoke" --environment dev --repo-root (Join-Path $env:TEMP "de-opencode-repo-smoke") --tests-evidence --sql-evidence --pipeline-evidence | Out-Null
& $Python (Join-Path $ToolDir "de.py") workbench catalog | Out-Null
& $Python (Join-Path $ToolDir "de.py") ado bulk preview --file (Join-Path $InstallRoot "samples\ado-work-items\bulk-updates.csv") | Out-Null
& $Python (Join-Path $ToolDir "de.py") security checklist | Out-Null
& $Python (Join-Path $ToolDir "de_pipeline.py") evidence --claim "smoke test" | Out-Null
& $Python (Join-Path $ToolDir "de.py") demo pipeline-doctor | Out-Null
& $Python (Join-Path $ToolDir "de_quality.py") evidence-template --claim "smoke test" | Out-Null
& $Python (Join-Path $ToolDir "de_release.py") manifest --root $InstallRoot | Out-Null

Write-Host "[de-opencode] Windows smoke test passed"
