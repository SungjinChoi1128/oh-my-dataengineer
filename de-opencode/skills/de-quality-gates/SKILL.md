---
name: de-quality-gates
description: QA workflow for data-engineering changes: tests, SQL validation, row counts, schema drift, nulls, duplicates, outliers, Databricks smoke tests, Azure Pipeline preflight, migration evidence, and release readiness.
compatibility: opencode
metadata:
  role: qa-skill-not-agent
---

# Quality Gates

Use before marking implementation, migration, SQL, pipeline, or deployment work complete.

## Required Thinking

Define the claim first. Then run the smallest checks that prove it.

## Common Gates

- Code: unit tests, lint/type checks where available, compile checks.
- SQL: classify query, bounded result check, row count, key uniqueness, null thresholds, duplicate checks.
- Migration: source row count, target row count, schema diff, unresolved mapping list, fact-pack evidence.
- Databricks: bundle validate, sandbox job smoke run, Unity Catalog object existence, lineage/profile evidence.
- Azure Pipelines: YAML preflight, secret scan, service connection/variable group check, deployment approval check.
- Security: config doctor/auth posture, secret scan, and no `.env` dependency.

## Preferred Tool

Use `de quality readiness --claim "<claim>" --environment <env>` to plan evidence.
Use `de done --claim "<claim>" --environment <env>` or `de quality verdict` before claiming completion.
Use `de_quality_evidence_template`, `de_workbench_quality_readiness`, or `de_quality_verdict` when OpenCode custom tools are available. Otherwise run `de-quality evidence-template --claim "<claim>"`.

## Evidence Report

Report command, target, environment, result, and remaining risks. Do not include secrets, tokens, full connection strings, or raw sensitive data samples.

Before production release, readiness should mention tests, SQL classification, row/schema evidence, pipeline/bundle preflight, security review, and rollback notes.
