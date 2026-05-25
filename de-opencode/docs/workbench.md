# Data Engineering Workbench

`de` is the human front door. Skills remain lightweight, but daily work should feel like one product.

## Skill Catalog

```bash
de workbench catalog
de workbench capabilities
de workbench triage --request "refine sprint backlog for Databricks migration"
```

## ADO Sprint / Backlog

```bash
de ado refine --items-file sprint-items.json
de ado bulk preview --file bulk-updates.csv --out out/ado-bulk-plan.json
```

Use this for backlog refinement, sprint planning, missing acceptance criteria, story/task hygiene, estimates, assignees, stale active work, and safe bulk update previews.

## Platform Workflows

```bash
de databricks bundle-doctor --bundle-yaml databricks.yml --pipeline-yaml azure-pipelines.yml
de mssql assess --metadata-file inventory.json
de migration plan --objects-file object-map.json --source mssql --target databricks
```

## Evidence / Security

```bash
de auth
de quality readiness --claim "migration release is ready" --environment prod
de security checklist --scope client-review
```

`de auth` and `de workbench capabilities` make the package contract visible: supported domains, preferred auth modes, and the fact that `.env` files are not supported.

## Apply Rule

Workbench commands generate reports and previews. They do not mutate ADO, Databricks, MSSQL, or production systems. Apply steps remain explicit and approval-gated through the underlying client-approved skills/tools.
