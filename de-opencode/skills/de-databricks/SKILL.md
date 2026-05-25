---
name: de-databricks
description: Databricks data engineering skill for SQL warehouses, Unity Catalog, Asset Bundles, jobs/workflows, runtime upgrades, AI/serving telemetry awareness, SQL safety, profiling, and safe CI/CD-aware operations.
compatibility: opencode
metadata:
  source: cli_skills databricks-* and databricks-bundles
---

# Databricks

Use for Databricks SQL, Unity Catalog, data lineage, Jobs/Workflows, Asset Bundles, DBR/runtime upgrades, model serving/AI workloads, telemetry governance, and Databricks CI/CD.

## First Move

Classify the task before acting:

- SQL or warehouse: classify/dry-run first.
- Bundle/ADO deploy: run Bundle Doctor and Pipeline Doctor.
- Runtime upgrade: run Runtime Advisor and require smoke evidence.
- Unity Catalog/governance: check 3-part names, grants, masking/filtering, lineage, and external locations.
- AI/serving/telemetry: verify official docs first, then check data residency, PII, retention, access grants, and cost/performance evidence.

## Preferred Tools

- Human front door: `de databricks bundle-doctor`, `de databricks runtime-advisor`, `de pipeline doctor`, `de quality readiness`, and `de workbench triage`.
- OpenCode custom tools when available: `de_dbsql_classify`, `de_dbsql_dry_run`, `de_databricks_bundle_doctor`, `de_databricks_runtime_advisor`.
- Low-level wrappers for automation: `de-dbsql`, `de-databricks`, `de-pipeline`, `de-quality`.

## Guardrails

- Prefer OAuth/profile/service principal/managed identity over PATs.
- Use 3-part Unity Catalog names: `catalog.schema.object`; justify any unqualified object names.
- For DML/DDL/admin SQL, require target object, environment, row-count or target-object precheck, and approval.
- For bundle deploys, run `databricks bundle validate` before deploy and attach `de-quality-gates` evidence.
- Do not rerun production deploys until critical/high Pipeline Doctor or Bundle Doctor findings are cleared.
- Treat new Databricks features as product intelligence: verify official docs, classify impact, then turn them into client-safe checks. Do not auto-upgrade clients based on news.

## Consulting Workflows

### Asset Bundle / ADO Deploy

1. Run `de databricks bundle-doctor --bundle-yaml databricks.yml --pipeline-yaml azure-pipelines.yml --environment <env>`.
2. Run `de pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log --write-evidence` when a build failed.
3. Confirm service connection/auth, variable groups, target workspace, validate-before-deploy, approval gate, and release evidence.

### Runtime Upgrade

1. Run `de databricks runtime-advisor --current-runtime <current> --target-runtime <target> --environment <env>`.
2. Add flags for risky workload shape: `--uses-udfs`, `--uses-jars`, `--uses-streaming`, `--uses-delta-writes`, `--uses-ml-serving`.
3. Require representative job smoke, library compatibility, Spark SQL behavior checks, rollback plan, and production approval.

### SQL / Unity Catalog

1. Run `de-dbsql classify --sql "<sql>"`.
2. Run `de-dbsql dry-run --sql "<sql>" --environment <env>` before writes.
3. For writes, attach row-count/schema evidence from `de-quality-gates`.

### AI, Serving, Telemetry

When Databricks features involve Foundation Model APIs, prompt caching, model serving, OpenTelemetry, Genie, Agent workflows, or UC telemetry tables:

- Verify current official docs before implementation.
- Identify whether prompts, retrieved context, traces, labels, or logs can contain PII/secrets.
- Plan Unity Catalog permissions, masking/row filters, retention, and cost/performance evidence.
