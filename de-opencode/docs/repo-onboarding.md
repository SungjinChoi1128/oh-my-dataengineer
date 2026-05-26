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
de repo contract
de repo map
de repo brief
de repo todo
de repo interview
```

If repo context already exists, it should use `de repo contract`, `de repo brief`, `de repo todo`, `de repo interview`, and `de repo commands` instead of rescanning immediately.

## CLI UX

```bash
de repo init
de repo doctor
de repo contract
de repo brief
de repo todo
de repo interview
de repo commands
de repo policy
de repo refresh
de repo reset
de repo scope list
```

`de repo init` writes:

```text
.de-opencode/repo-context.json
.de-opencode/DE.md
.de-opencode/repo-map.md
.de-opencode/repo-map.json
.de-opencode/repo-brief.md
.de-opencode/next-actions.md
.de-opencode/next-actions.json
.de-opencode/repo-interview.md
.de-opencode/repo-interview.json
.de-opencode/commands.json
.de-opencode/safety-policy.json
```

These files are reviewable. They contain detected repo shape, a compact data-engineering contract, short next actions, important files, risk zones, recommended commands, targeted interview questions, and safety policy.

## Integration Repo Scopes

Use scopes when one integration repo contains many feature areas or multiple users are working in unrelated paths:

```bash
de repo scope add --name customer360 --path src/customer360 --path pipelines/customer360 --use
de repo init
de repo map
de repo reset
```

Scoped context lives under `.de-opencode/scopes/<name>/`. The active scope is stored in `.de-opencode/scopes.json`, so later `de repo init`, `de repo reset`, `de repo doctor`, `de repo brief`, `de repo map`, `de repo todo`, and `de repo interview` use that scope by default. Use `--global-context` when you intentionally want whole-repo context.

## Refresh vs Reset

Use `de repo refresh` when the same repo shape changed and you simply want to rescan.

Use `de repo reset` when a shared integration repo, branch switch, or feature area change made the existing `.de-opencode` context stale. Reset archives the old context to `.de-opencode-archive/` by default, then initializes fresh context:

```bash
de repo reset
de repo reset --archive-dir .de-opencode-archive
```

Use `--force` only when you intentionally want to delete the old context instead of archiving it:

```bash
de repo reset --force
```

Use `--no-init` when you only want to clear or archive context and leave the repo uninitialized:

```bash
de repo reset --no-init
```

Use archive inspection and diff when you want to understand what changed:

```bash
de repo archives
de repo diff --archive latest
de repo restore --archive latest
```

`de repo doctor` warns when context is old, the git branch changed, or important files changed after context generation.

## Compact DE.md

`.de-opencode/DE.md` is the small always-safe contract inspired by `CLAUDE.md`, but tailored to data engineering. It should stay short: operating principles, environment discipline, SQL safety, pipeline safety, Databricks safety, and evidence-before-done.

Use:

```bash
de repo contract
de repo map
```

Do not turn `DE.md` into a full handbook. Detailed repo facts belong in `repo-brief.md`, command details in `commands.json`, and approval rules in `safety-policy.json`.

## Short Next Actions

`de repo todo` prints a compact action list based on repo signals. It exists to stop onboarding from becoming a context dump.

Typical actions include auth posture, safe default environment, Pipeline Doctor, Bundle Doctor, SQL policy checks, missing verification evidence, and risk-zone review.

## Initialized-Only Interview

`de repo interview` is intentionally not a generic setup wizard. It requires initialized context and fails with `needs-init` before `.de-opencode/repo-context.json` exists.

The questions are generated from detected signals:

- Azure Pipelines: ADO organization, project, team, sprint, and rerun boundaries.
- Databricks bundles: safe target/profile, workspace, catalog, and deployment boundaries.
- SQL/MSSQL: read-only endpoints, mutation approval, and reconciliation evidence.
- Missing tests: the evidence command or manual proof expected for this repo.
- Risk zones: which detected deploy, SQL, notebook, or production-looking files are truly sensitive.

## Opt-In Agent Files

OpenCode automatically loads `AGENTS.md`, and Claude Code can load `CLAUDE.md`, so the package does not create or overwrite either during normal onboarding.

Use this only when you want repo-level agent instructions:

```bash
de repo install-contract --target agents
de repo install-contract --target claude
```

If the target file already exists, the command blocks unless `--force` is used.

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
