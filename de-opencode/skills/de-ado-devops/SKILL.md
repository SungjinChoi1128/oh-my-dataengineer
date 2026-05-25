---
name: de-ado-devops
description: Azure DevOps and Azure Pipelines workflow skill for repos, PRs, work items, builds, release inspection, Databricks bundle CI/CD, and safe pipeline preflight.
compatibility: opencode
metadata:
  source: cli_skills ado-* and databricks-bundles
---

# ADO DevOps

Use for Azure DevOps repos, PRs, work items, sprint boards, backlog refinement, bulk work-item updates, pipelines, wiki, tests, and CI/CD.

## Preferred Commands

- Human front door: `de ado refine`, `de ado bulk preview`, `de pipeline doctor`, and `de workbench triage`.
- Prefer OpenCode custom tools when available: `de_workbench_ado_refine`, `de_workbench_ado_bulk_preview`, `de_ado_classify`, `de_ado_preflight`, `de_pipeline_preflight`, `de_pipeline_diagnose`, and `de_pipeline_evidence`.
- `de ado refine --items-file sprint-items.json` before backlog refinement or sprint planning.
- `de ado bulk preview --file updates.csv` before any bulk work-item update.
- `de-ado classify --operation <name>` before write or trigger actions.
- `de-ado preflight --pipeline-yaml azure-pipelines.yml` before pipeline changes.
- `de-pipeline diagnose --pipeline-yaml azure-pipelines.yml --log-file build.log` to understand and fix a failed build.
- Existing detailed commands can be used after preflight: `ado-repos`, `ado-work-items`, `ado-pipelines`, `ado-wiki`, `ado-test-plans`, `ado-search`.

## Guardrails

- Pipeline trigger, release mutation, artifact download, work-item bulk create, and wiki write are not casual read-only actions.
- Bulk work-item update must be previewed before apply.
- Bare stories are discouraged; use story templates or child tasks for trackable sprint work.
- Use service connections and variable groups for secrets.
- Production deploys need explicit approval and release evidence from `de-quality-gates`.

## Sprint UX

For daily consulting work:

1. Run `de ado refine --items-file <export.json>` to find missing acceptance criteria, child tasks, estimates, assignees, stale active items, and missing iteration.
2. Prepare changes in CSV/JSON and run `de ado bulk preview --file <updates.csv>`.
3. Apply through `ado-work-items` only after preview is reviewed and approved.
