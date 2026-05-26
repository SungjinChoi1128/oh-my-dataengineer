# de-opencode

Lightweight OpenCode data-engineering package for consulting teams that work with Azure DevOps, Databricks, and MSSQL.

The product front door is `de`. The package also includes OpenCode agents, a guardrails plugin, skills, policy tools, sample Azure Pipeline files, installers, and release verification.

Start with `docs/user-manual.md` if you are using the package for the first time or distributing it to another consultant.

## What It Is

- An OpenCode configuration package, not a heavyweight agent framework.
- A data-engineering control plane for pipeline diagnosis, SQL safety checks, evidence capture, and client-safe operating defaults.
- A distribution unit for consultants: copy/install it, set `OPENCODE_CONFIG_DIR`, run `de doctor`, then use OpenCode with the included agents and guardrails.

## Main Workflow

```bash
de doctor
de auth
de workbench catalog
de workbench capabilities
de workbench triage --request "refine sprint backlog for Databricks migration"
de ado refine --items-file sprint-items.json
de ado bulk preview --file bulk-updates.csv
de ado query --wiql "SELECT [System.Id], [System.Title] FROM WorkItems"
de demo pipeline-doctor
de databricks bundle-doctor --bundle-yaml databricks.yml --pipeline-yaml azure-pipelines.yml
de databricks sql execute --sql "SELECT 1"
de databricks runtime-advisor --current-runtime 15.4 --target-runtime 16.4 --environment prod
de mssql assess --metadata-file inventory.json
de mssql query --sql "SELECT TOP 10 * FROM dbo.Customers" --server localhost --database EDW
de migration plan --objects-file object-map.json --source mssql --target databricks
de security checklist --scope client-review
de pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log --write-evidence
de quality readiness --claim "release is ready" --environment prod
de quality reconcile --source-count 100 --target-count 100
de release verify
```

`de workbench` is the unified entry point for the package skill catalog and task triage.

`de pipeline doctor` is the primary CI/CD workflow. It preflights Azure Pipeline YAML, diagnoses build logs, explains blockers in plain language, suggests fixes, and writes evidence artifacts.

`de databricks bundle-doctor` and `de databricks runtime-advisor` add Databricks-specific readiness checks for Asset Bundles, ADO deploys, runtime upgrades, Unity Catalog naming discipline, and modern AI/serving/telemetry workloads.

`de databricks sql execute`, `de ado query`, and `de mssql query` are guarded live paths. They use your installed Databricks CLI/profile, Azure CLI, or `sqlcmd` instead of replacing them.

## Output Modes

Human-readable text is the default. JSON and Markdown are available for automation and client-facing evidence:

```bash
de pipeline doctor --pipeline-yaml azure-pipelines.yml --format json
de demo pipeline-doctor --format markdown --out out/de-evidence
```

## Security Posture

- `.env` files are not supported by this package. Use enterprise-managed environment injection, Microsoft Entra/managed identity/profile auth, or a client-approved secret provider.
- Secret files such as `.env`, `.databrickscfg`, PEM/key files, and ODBC config are denied by OpenCode read policy.
- Dangerous deploy and SQL execution commands require approval.
- PAT/token/password environment variables remain legacy-compatible fallbacks, not the preferred enterprise path.
- Tools classify and dry-run before execution-oriented work; live reads are allowed through guarded wrappers.
- Evidence artifacts are designed to avoid printing secrets.

## Install

Windows 11:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

WSL/macOS/Linux-style shell:

```bash
sh ./install-wsl.sh
```

See `docs/user-manual.md`, `docs/windows-11-install.md`, `docs/security-model.md`, `docs/workbench.md`, `docs/databricks.md`, `docs/pipeline-doctor.md`, and `docs/ux-guide.md`.
