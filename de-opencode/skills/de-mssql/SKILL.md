---
name: de-mssql
description: SQL Server and MSSQL migration skill for safe metadata discovery, SQL classification, stored procedure inspection, dependency mapping, and guarded execution.
compatibility: opencode
metadata:
  source: cli_skills mssql-client and mssql-legacy-discovery
---

# MSSQL

Use for SQL Server metadata discovery, stored procedure inspection, dependencies, row counts, SQL Agent inventory, and migration fact packs.

## Preferred Commands

- Human front door: `de mssql assess --metadata-file inventory.json`.
- Prefer OpenCode custom tools when available: `de_workbench_mssql_assess`, `de_mssql_classify`, and `de_mssql_policy_check`.
- `de mssql assess --metadata-file inventory.json` to turn discovery output into migration risk findings.
- `de-mssql policy-check` to inspect configured security posture.
- `de-mssql classify --sql "<sql>"` before query execution.
- Existing detailed commands can be used after checks: `mssql-client`, `mssql-legacy-discovery`.

## Guardrails

- Metadata/discovery is the default.
- Query and procedure execution must fail closed unless explicitly enabled.
- Prefer ODBC Driver 18 with encryption and certificate validation.
- Treat `TrustServerCertificate=True`, SQL password auth, and production DML as risks requiring explicit acceptance.

## Assessment UX

Use assessment reports to summarize dynamic SQL, linked servers, SQL Agent dependencies, and migration blockers before asking the agent to rewrite or migrate code.
