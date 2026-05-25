---
name: de-task-triage
description: Route data engineering requests into safe paths for explore, diagnose, change, validate, deploy, and document workflows across ADO, Databricks, MSSQL, and migration work.
compatibility: opencode
metadata:
  audience: consulting-data-engineers
---

# Data Engineering Task Triage

Use this first when the request touches more than one system or the safe path is unclear.

## Routing

- Start with `de workbench triage --request "<request>"` when the lane is unclear.
- Use `de workbench catalog` to show the available package workflows.
- ADO repo, PR, work item, build, release, or wiki: use `de-ado-devops`.
- Databricks SQL, Unity Catalog, lineage, jobs, bundles, or table profiling: use `de-databricks`.
- SQL Server metadata, stored procedures, dependencies, or legacy database discovery: use `de-mssql`.
- MSSQL/SSIS migration evidence: use `de-migration-wiki`.
- Secrets, permissions, auth, client review, or data mutation risk: use `de-security-review`.
- Completion proof, migration validation, or release evidence: use `de-quality-gates`.

## Default Safety

Start read-only. Classify SQL and pipeline actions before running them. Keep secrets out of prompts, logs, stdout, and evidence reports.

## Front Door

Prefer `de workbench triage`, then the domain front door (`de ado`, `de databricks`, `de mssql`, `de migration`, `de security`, `de quality`) before dropping to lower-level CLI skills.
