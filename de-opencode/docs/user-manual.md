# de-opencode User Manual

This manual is for consultants and data engineers using `de-opencode` on real Azure DevOps, Databricks, MSSQL, and migration work.

The package is an OpenCode configuration package plus safe command-line wrappers. It is not a heavyweight agent framework. Use it when you want a data-engineering assistant with guardrails, repeatable checks, and client-safe evidence.

## What You Use It For

Use `de-opencode` for:

- Azure DevOps sprint hygiene, backlog refinement, bulk update previews, and pipeline troubleshooting.
- Databricks Asset Bundle preflight, runtime upgrade evidence, Databricks SQL classification, and Unity Catalog naming checks.
- MSSQL SQL classification, connection/security posture checks, and legacy inventory risk review.
- MSSQL/SSIS to Databricks migration planning and evidence packs.
- QA gates: row-count reconciliation, schema/evidence templates, release readiness, done verdicts, and rollback notes.
- Client security answers: secret handling, auth posture, OpenCode permissions, and production-change controls.

Do not use it as a silent production executor. It is designed to inspect, classify, preview, run guarded live reads, and produce evidence first. Actual writes, deploys, reruns, mutating SQL, and bulk updates remain explicit and approval-gated.

## Install

### Windows 11

Run from the package directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Optional user-level environment setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -SetUserEnvironment
```

Then open a new terminal and run:

```powershell
de doctor
de auth
de workbench capabilities
de release verify
```

### WSL, macOS, or Linux-Style Shell

```bash
sh ./install-wsl.sh
```

Then make sure the printed wrapper directory is on `PATH` and run:

```bash
de doctor
de auth
de workbench capabilities
de release verify
```

## First Five Commands

Run these before trusting the package in a client context:

```bash
de doctor
de auth
de repo init
de repo reset
de repo brief
de workbench catalog
de workbench capabilities
de security checklist --scope client-review
```

What they tell you:

- `de doctor`: local runtime, installed CLIs, redacted config state, and missing keys.
- `de auth`: whether `.env` is unsupported, whether legacy secrets are present, and whether modern auth is configured.
- `de repo init`: create repo-local context artifacts for the current project.
- `de repo reset`: archive stale repo-local context and reinitialize it after branch or integration-repo context changes.
- `de repo brief`: show the detected repo shape, important files, risk zones, and safe commands.
- `de workbench catalog`: what skills and workflows the package exposes.
- `de workbench capabilities`: what ADO, Databricks, MSSQL, and migration capability is covered.
- `de security checklist`: client-facing security answer and review checklist.

## Security Model

Security defaults are intentionally conservative:

- `.env` files are not supported by this package.
- OpenCode read policy denies secret files such as `.env`, `.databrickscfg`, PEM/key files, and ODBC config.
- PATs, Databricks tokens, SQL passwords, and connection strings are legacy-compatible fallbacks only.
- Preferred auth is Microsoft Entra/service principal/managed identity for ADO, Databricks workload identity federation/OAuth/profile, and MSSQL managed/integrated/Entra auth.
- Dangerous SQL, deploys, pipeline triggers, and bulk ADO updates are approval-gated.
- Guarded live reads are supported for ADO, Databricks SQL, and MSSQL when the client-approved CLI/auth path is already configured.
- Evidence reports should not include secrets, full connection strings, client hostnames, or raw sensitive production samples.

`de auth` uses two separate ideas:

- `safe_default`: no legacy secret fallback is currently detected.
- `enterprise_ready`: modern auth appears configured for ADO, Databricks, and MSSQL.

An unconfigured laptop can be safe by default but not enterprise ready yet.

## Human Front Door

Use `de` first. It gives human-readable output by default and supports JSON/Markdown when you need automation or evidence:

```bash
de --format json pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log
de --format markdown demo pipeline-doctor --out out/de-evidence
```

Use lower-level wrappers only when you need automation:

- `de-config`
- `de-workbench`
- `de-databricks`
- `de-dbsql`
- `de-mssql`
- `de-ado`
- `de-pipeline`
- `de-quality`
- `de-release`
- `de-repo`

## Repo Onboarding

When you first use the package in a client repository, use conversation-first onboarding:

```text
Onboard this repo for data engineering.
```

The `data-engineer` agent should run:

```bash
de repo doctor
de repo init
de repo reset
de repo contract
de repo brief
de repo todo
de repo interview
```

The generated context lives in:

```text
.de-opencode/repo-context.json
.de-opencode/DE.md
.de-opencode/repo-brief.md
.de-opencode/next-actions.md
.de-opencode/repo-interview.md
.de-opencode/commands.json
.de-opencode/safety-policy.json
```

Use:

```bash
de repo contract
de repo todo
de repo interview
de repo commands
de repo policy
de repo refresh
de repo reset
```

`de repo contract` prints compact `.de-opencode/DE.md`: the small data-engineering operating contract for the repo. Keep it short; put detailed facts in `repo-brief.md`.

`de repo todo` prints the short next-action list, such as auth posture, safe environment, Pipeline Doctor, Bundle Doctor, SQL policy check, missing verification, or risk-zone review.

`de repo reset` is for integration repos and branch switches. It archives old `.de-opencode` context into `.de-opencode-archive/` by default and then creates fresh context. Use `de repo reset --force` only when you intentionally want to delete old generated context instead of archiving it.

`de repo interview` only works after initialization. It turns detected repo facts into targeted questions, such as safe default environment, ADO project/sprint defaults, Databricks bundle targets, SQL execution boundaries, and required handoff evidence.

`AGENTS.md` and `CLAUDE.md` export is opt-in because agent tools auto-load those files:

```bash
de repo install-contract --target agents
de repo install-contract --target claude
```

The scanner skips `.env`, `.databrickscfg`, ODBC config, PEM/key files, obvious secret JSON/YAML files, and very large files.

## Azure DevOps Workflows

### Sprint and Backlog Refinement

Use this when you have exported work items and want missing acceptance criteria, stale active work, missing estimates, missing assignees, and task/story hygiene surfaced.

```bash
de ado refine --items-file sprint-items.json
```

Typical input is JSON or CSV with fields such as `id`, `title`, `type`, `state`, `acceptance_criteria`, `estimate`, `assigned_to`, and `iteration`.

### Bulk Work Item Preview

Use this before any batch update:

```bash
de ado bulk preview --file bulk-updates.csv --out out/ado-bulk-plan.json
```

The preview shows row-level operations, unusual fields, completion-state risk, and whether approval is required. It does not apply the update.

### Live ADO Read Queries

Use this when Azure CLI and the Azure DevOps extension are already authenticated:

```bash
de ado query --wiql "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems"
de ado work-item --id 12345
de ado pipeline-runs --pipeline-id 42 --top 5
```

These commands call `az boards` / `az pipelines` and only expose read paths in the `de` front door.

### Pipeline Doctor

Use this when an Azure Pipeline fails, especially for Databricks bundle deployment or CI/CD failures.

```bash
de pipeline preflight --pipeline-yaml azure-pipelines.yml
de pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log --write-evidence
```

Pipeline Doctor checks YAML and logs for known failure classes such as missing Databricks CLI, auth failure, service connection issues, inline secrets, missing approval gates, and unsafe deploy patterns.

For live ADO facts, collect logs/status through the existing ADO skills or client-approved CLI, then feed the log into Pipeline Doctor.

## Databricks Workflows

### Bundle Doctor

Run before Databricks Asset Bundle deploys or before rerunning a failed deployment:

```bash
de databricks bundle-doctor --bundle-yaml databricks.yml --pipeline-yaml azure-pipelines.yml --environment prod
```

It checks bundle structure, inline secrets, production target signals, hardcoded workspace hosts, runtime evidence needs, and ADO validate-before-deploy behavior.

### Runtime Advisor

Run when changing DBR/Spark/runtime versions:

```bash
de databricks runtime-advisor --current-runtime 15.4 --target-runtime 16.4 --environment prod --uses-delta-writes
```

It produces evidence requirements such as job smoke tests, bundle validate, row-count/schema checks, UDF/JAR/streaming compatibility, ML/serving checks, rollback notes, and production approval.

### Databricks SQL Classification

Use this before SQL execution:

```bash
de-dbsql classify --sql "SELECT * FROM main.sales.orders"
de-dbsql dry-run --sql "MERGE INTO main.sales.orders ..." --environment prod --row-count-checked --confirm-write
```

Production writes require explicit confirmation and evidence. Unity Catalog three-part naming is encouraged for production reads and writes.

### Databricks SQL Live Execution

Use this when `DATABRICKS_HOST` and either `DATABRICKS_PROFILE` or `DATABRICKS_TOKEN` are configured:

```bash
de databricks sql warehouses
de databricks sql execute --sql "SELECT 1"
de databricks sql execute --sql "SELECT * FROM main.sales.orders LIMIT 10" --result-format json
```

Readonly SQL executes by default. Write/admin SQL requires explicit flags and evidence:

```bash
de databricks sql execute --sql "MERGE INTO main.sales.target ..." --allow-write --confirm-write --row-count-checked --environment prod
```

## MSSQL Workflows

### SQL Classification

```bash
de-mssql classify --sql "DROP TABLE dbo.Customers"
```

Use classification before any execution path. Dangerous or mutating SQL should go through approval and QA gates.

### MSSQL Live Read Query

Use this when `sqlcmd` is installed and client-approved auth is available:

```bash
de mssql query --sql "SELECT TOP 10 * FROM dbo.Customers" --server sql01 --database EDW --auth-mode integrated
de mssql query --sql "SELECT TOP 10 * FROM dbo.Customers" --server sql01 --database EDW --auth-mode entra
```

SQL password auth is possible only with an explicit flag and a password environment variable:

```bash
de mssql query --sql "SELECT TOP 10 * FROM dbo.Customers" --server sql01 --database EDW --auth-mode sql-password --user svc_user --password-env MSSQL_PASSWORD --allow-sql-password
```

### Security Policy Check

```bash
de-mssql policy-check
```

This checks local MSSQL posture signals such as driver, encryption, certificate trust, connection-string usage, and auth mode.

### Inventory Assessment

```bash
de mssql assess --metadata-file inventory.json
```

Use this for migration readiness. It highlights dynamic SQL, linked servers, SQL Agent dependencies, stored procedure risks, and blockers that need mapping.

## Migration Workflows

Use migration planning when moving from MSSQL/SSIS/legacy systems to Databricks or lakehouse targets:

```bash
de migration plan --objects-file object-map.json --source mssql --target databricks
```

The plan reports object counts, unresolved mappings, required evidence, and migration blockers. Pair it with:

```bash
de quality readiness --claim "migration release is ready" --environment prod
de quality reconcile --source-count 100 --target-count 100
```

## Quality and Release Gates

Before claiming work is complete, define the claim and run the smallest checks that prove it:

```bash
de quality readiness --claim "Databricks bundle release is ready" --environment prod
de quality reconcile --source-count 100000 --target-count 100000
de pipeline evidence --claim "Bundle deploy is safe" --environment dev --out out/de-evidence
de done --claim "Databricks bundle release is ready" --environment prod --evidence-dir out/de-evidence
```

For production releases, evidence should mention tests, SQL classification, row/schema evidence, pipeline or bundle preflight, security review, rollback notes, and approval status.

`de done` is the final verdict command. It does not run live Databricks, ADO, or MSSQL actions. It reads `.de-opencode` repo context, repo next actions, optional JSON evidence files, and evidence flags, then returns:

- `ready`: enough evidence is present for the detected repo shape and environment.
- `needs-evidence`: nothing failed, but the claim is missing proof such as SQL dry-run, tests, row/schema evidence, pipeline preflight, security/auth, rollback, or approval.
- `blocked`: an attached evidence file failed, is blocked, or cannot be read.

Useful examples:

```bash
de done --claim "migration wave 1 is ready" --environment prod --evidence-dir out/de-evidence
de quality verdict --claim "sprint update is safe" --environment dev --tests-evidence --security-evidence
de done --claim "SQL update is safe" --environment prod --data-changed --sql-evidence --row-schema-evidence --security-evidence --rollback-note --approval-note
```

## OpenCode Usage

Set `OPENCODE_CONFIG_DIR` to the installed package directory when using OpenCode with this package. The included configuration provides:

- `data-engineer`: primary agent for ADO, Databricks, MSSQL, migration, CI/CD, and QA-gated work.
- `data-architect`: ask-gated architecture reviewer for migration, governance, and operational risk.
- `data-devops`: ask-gated CI/CD specialist for Azure Pipelines and Databricks bundle release troubleshooting.
- `de-guardrails.ts`: plugin hooks and custom tools for safer structured workflows.

Prefer the custom tools or `de` wrappers over raw shell commands whenever possible.

## Common Scenarios

### I Need To Refine A Sprint

```bash
de ado refine --items-file sprint-items.json
de ado bulk preview --file proposed-updates.csv
de quality readiness --claim "sprint update is safe" --environment dev
de done --claim "sprint update is safe" --environment dev --tests-evidence --security-evidence
```

### A Databricks Deployment Failed In ADO

```bash
de pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log --write-evidence
de databricks bundle-doctor --bundle-yaml databricks.yml --pipeline-yaml azure-pipelines.yml --environment prod
de security checklist --scope release
```

### A Client Asks About Security

```bash
de auth
de doctor
de security checklist --scope client-review
de release verify
```

Answer in plain language: the package does not store secrets, does not support `.env`, denies secret-file reads, redacts diagnostics, classifies risky actions first, and approval-gates production-affecting commands.

### I Need A Migration Evidence Pack

```bash
de mssql assess --metadata-file inventory.json
de migration plan --objects-file object-map.json --source mssql --target databricks
de quality readiness --claim "migration wave 1 is ready" --environment prod
de done --claim "migration wave 1 is ready" --environment prod --evidence-dir out/de-evidence
```

## Troubleshooting

### `de doctor` Says A CLI Is Missing

Install the missing client-approved dependency if the workflow needs it. The package itself does not install Python, OpenCode, Git, Databricks CLI, Azure CLI, or ODBC Driver 18.

### `de auth` Says `NEEDS-ACTION`

That is normal on a fresh machine. Configure modern auth for the systems you need. Avoid adding `.env`; it is not supported. PAT/token/password variables are fallback paths only.

### A Command Is Blocked

Run the classify, preflight, dry-run, or doctor command first. If the action is still needed, capture evidence and get explicit approval through the client-approved path.

### Output Is Too Verbose

Use JSON for automation and Markdown for evidence:

```bash
de --format json doctor
de --format markdown pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log
```

## Distribution Checklist

Before sharing with another consultant:

```bash
python3 tests/smoke.py
python3 tests/security_package.py
python3 tools/de_release.py verify --root .
de release verify
```

On Windows, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\smoke.ps1
```

## Feedback Loop

During beta use, capture:

- task attempted
- command used
- what was confusing
- missing option or missing skill capability
- whether the result helped with ADO, Databricks, MSSQL, migration, QA, or security
- whether the evidence was good enough for a client or reviewer

Repeated friction should become a wrapper, test, doc update, or guardrail change.
