---
name: de-migration-wiki
description: Build migration evidence packs by combining MSSQL object fact packs, SSIS package discovery, and Databricks target validation.
compatibility: opencode
metadata:
  source: cli_skills mssql-legacy-discovery, ssis-legacy-discovery, migration-wiki-join
---

# Migration Wiki

Use when converting or assessing legacy MSSQL/SSIS workloads for Databricks or lakehouse migration.

## Workflow

0. Run `de migration plan --objects-file object-map.json --source mssql --target databricks` to create the evidence checklist and unresolved mapping list.
1. Discover MSSQL object metadata with `mssql-legacy-discovery`.
2. Discover SSIS package evidence with `ssis-legacy-discovery`.
3. Join evidence with `migration-wiki-join`.
4. Validate target readiness with `de-quality-gates`.

## Output

Evidence should list source objects, package references, target Databricks objects, unresolved mappings, data-quality checks, and remaining risks. Never include secrets or raw sensitive data samples.

Prefer `de migration plan` as the user-facing planning report, then use lower-level migration wiki skills for detailed fact packs.
