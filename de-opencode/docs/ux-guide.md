# UX Guide

The product front door is `de`.

Use focused low-level commands such as `de-pipeline`, `de-quality`, and `de-config` for automation. Use `de` for humans.

## Core Commands

```bash
de doctor
de auth
de repo init
de repo brief
de repo interview
de workbench catalog
de workbench capabilities
de workbench triage --request "refine sprint backlog for Databricks migration"
de ado refine --items-file sprint-items.json
de ado bulk preview --file bulk-updates.csv
de databricks bundle-doctor --bundle-yaml databricks.yml --pipeline-yaml azure-pipelines.yml
de databricks runtime-advisor --current-runtime 15.4 --target-runtime 16.4 --environment prod
de mssql assess --metadata-file inventory.json
de migration plan --objects-file object-map.json --source mssql --target databricks
de security checklist --scope client-review
de quality readiness --claim "release is ready" --environment prod
de pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log --write-evidence
de pipeline preflight --pipeline-yaml azure-pipelines.yml
de pipeline evidence --claim "Bundle deploy is safe" --environment dev --out out/de-evidence
de quality reconcile --source-count 100 --target-count 100
de release verify
de demo pipeline-doctor
```

## Output Formats

Default output is human-readable text. Use JSON or Markdown when needed:

```bash
de --format json pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log
de --format markdown demo pipeline-doctor
```

## UX Principles

- Lead with status: OK, WARN, BLOCKED, FAILED.
- Explain the reason in plain language.
- Show the safest next action.
- Write evidence artifacts when the action matters.
- Keep raw JSON available for automation.
- Never print secrets.
