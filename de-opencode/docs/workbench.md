# Data Engineering Workbench

`de` is the human front door. Skills remain lightweight, but daily work should feel like one product.

## Skill Catalog

```bash
de repo init
de repo contract
de repo brief
de repo todo
de workbench catalog
de workbench capabilities
de workbench route --request "fix failed Azure Pipeline deploying Databricks bundle"
de workbench triage --request "refine sprint backlog for Databricks migration"
```

Use `de repo init` when first entering a client repo. It creates reviewable `.de-opencode/*` context artifacts so the agent can understand repo shape, a compact DE contract, short next actions, important files, risk zones, and safe commands.

## Agent Routing

`de workbench route` is the lightweight routing gate for OpenCode agents:

- `data-devops`: Azure Pipeline failures, build logs, release evidence, Databricks bundle validate/deploy/run issues, service connections, variable groups, and CI/CD YAML fixes.
- `data-architect`: architecture review, migration design, Unity Catalog layout, governance, ownership, data contracts, cutover, rollback, and operational-risk review.
- `data-engineer`: scoped implementation, SQL safety, ADO sprint hygiene, Databricks SQL/MSSQL checks, QA evidence, and normal repo-local code edits.

The primary `data-engineer` agent is allowed to invoke only `data-devops` and `data-architect` automatically, so routing is stronger without adding a large agent hierarchy. `data-engineer`, `data-devops`, and `data-architect` each have a 250-step runaway ceiling for long real-world implementation, pipeline diagnosis, and architecture-review loops; `data-architect` remains read-only.

## ADO Sprint / Backlog

```bash
de ado refine --items-file sprint-items.json
de ado bulk preview --file bulk-updates.csv --out out/ado-bulk-plan.json
de ado query --wiql "SELECT [System.Id], [System.Title] FROM WorkItems"
```

Use this for backlog refinement, sprint planning, missing acceptance criteria, story/task hygiene, estimates, assignees, stale active work, and safe bulk update previews.

## Platform Workflows

```bash
de databricks bundle-doctor --bundle-yaml databricks.yml --pipeline-yaml azure-pipelines.yml
de databricks sql execute --sql "SELECT 1" --dry-run-only
de mssql assess --metadata-file inventory.json
de-mssql policy-check
de mssql query --sql "SELECT TOP 10 * FROM dbo.Customers" --server sql01 --database EDW
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

Workbench commands generate reports, previews, and guarded live reads. They do not silently mutate ADO, Databricks, MSSQL, or production systems. Apply/write steps remain explicit and approval-gated through the underlying client-approved skills/tools.
