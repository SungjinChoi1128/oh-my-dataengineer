# Databricks Workflows

This package treats Databricks as a data-engineering system: SQL, Unity Catalog, Asset Bundles, jobs, runtime upgrades, CI/CD, AI/serving, telemetry, and release evidence.

## Core Commands

```bash
de databricks bundle-doctor --bundle-yaml databricks.yml --pipeline-yaml azure-pipelines.yml --environment dev
de databricks runtime-advisor --current-runtime 15.4 --target-runtime 16.4 --environment prod --uses-delta-writes
de-dbsql classify --sql "SELECT * FROM main.sales.orders"
de-dbsql dry-run --sql "MERGE INTO main.sales.orders ..." --environment prod --row-count-checked --confirm-write
```

## Bundle Doctor

Use before Databricks Asset Bundle deploys and before rerunning failed ADO deployments.

It checks:

- `bundle:` and `targets:` structure
- obvious inline secrets
- production target signals
- hardcoded workspace host risk
- runtime values that need upgrade evidence
- optional ADO YAML validate-before-deploy behavior

## Runtime Advisor

Use when a client considers DBR/Spark/runtime changes.

It turns workload shape into required evidence:

- representative job smoke test
- bundle validate
- row-count/schema evidence for Delta writes
- UDF/JAR/streaming compatibility checks
- ML/AI serving latency, cost, PII, and data-residency checks
- rollback plan and production approval

## Modern Databricks Feature Awareness

New Databricks features should be treated as product intelligence, not automatic implementation instructions.

For features around Foundation Model APIs, prompt caching, OpenTelemetry, Unity Catalog telemetry, Genie, Agent workflows, serverless, or runtime changes:

- verify official docs before changing client systems
- classify impact: security, CI/CD, runtime, cost/performance, governance, or data quality
- turn the update into evidence-backed checks
- avoid production rollout without client approval and rollback evidence
