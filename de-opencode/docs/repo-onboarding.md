# Repo Onboarding

Repo onboarding tailors `de-opencode` to the current client repository without turning it into hidden memory.

## Primary UX

In OpenCode, select `data-engineer` and say:

```text
Onboard this repo for data engineering.
```

The agent should run:

```bash
de repo doctor
de repo init
de repo brief
de repo interview
```

If repo context already exists, it should use `de repo brief`, `de repo interview`, and `de repo commands` instead of rescanning immediately.

## CLI UX

```bash
de repo init
de repo doctor
de repo brief
de repo interview
de repo commands
de repo policy
de repo refresh
```

`de repo init` writes:

```text
.de-opencode/repo-context.json
.de-opencode/repo-brief.md
.de-opencode/repo-interview.md
.de-opencode/repo-interview.json
.de-opencode/commands.json
.de-opencode/safety-policy.json
```

These files are reviewable. They contain detected repo shape, important files, risk zones, recommended commands, targeted interview questions, and safety policy.

## Initialized-Only Interview

`de repo interview` is intentionally not a generic setup wizard. It requires initialized context and fails with `needs-init` before `.de-opencode/repo-context.json` exists.

The questions are generated from detected signals:

- Azure Pipelines: ADO organization, project, team, sprint, and rerun boundaries.
- Databricks bundles: safe target/profile, workspace, catalog, and deployment boundaries.
- SQL/MSSQL: read-only endpoints, mutation approval, and reconciliation evidence.
- Missing tests: the evidence command or manual proof expected for this repo.
- Risk zones: which detected deploy, SQL, notebook, or production-looking files are truly sensitive.

## Opt-In AGENTS.md

OpenCode automatically loads `AGENTS.md`, so the package does not create or overwrite it during normal onboarding.

Use this only when you want repo-level agent instructions:

```bash
de repo install-agents-md
```

If `AGENTS.md` already exists, the command blocks unless `--force` is used.

## What It Detects

- Databricks bundle files
- Azure Pipeline and GitHub Actions files
- SQL and T-SQL assets
- notebooks
- dbt projects
- Python data-engineering repos
- SSIS or legacy migration assets
- tests and documentation
- deployment and production-risk paths

## What It Does Not Read

- `.env`
- `.databrickscfg`
- ODBC config
- PEM/key/certificate files
- obvious local secret JSON/YAML files
- very large files

## Recommended First Prompt

```text
Onboard this repo. Then tell me the repo type, important files, risk zones, safe commands, and what you need from me before live ADO/Databricks/MSSQL access.
```

## Refresh Rule

Run this after major repo changes:

```bash
de repo refresh
```

The context artifacts should be treated as generated project memory. Review them before committing them to a client repo.
