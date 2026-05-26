# Checkpoint Audit

Date: 2026-05-26

This is the brutally honest product checkpoint for `de-opencode` after the repo-onboarding and compact `DE.md` work.

## What Is Strong

- The package is still lightweight: one OpenCode config directory, three agents, local Python tools, no server, no database, no extra package manager runtime.
- The main `de` command is a good human front door. Low-level wrappers remain available for automation.
- Repo onboarding is useful without hidden memory: `.de-opencode/*` artifacts are generated, reviewable, and ignored by default.
- The compact `DE.md` contract is the right direction. It gives the agent durable data-engineering behavior without loading a full handbook.
- Security posture is much better than early versions: `.env` is unsupported, secret-like files are skipped, agent file export is opt-in, and live SQL/pipeline actions are guarded.
- Tests now cover smoke behavior, package security assertions, release manifest verification, and installed wrapper behavior.

## Main Weak Spots

- Some examples still risk teaching users to jump into live commands too early. Default docs and generated commands should keep emphasizing dry-run, classify, policy-check, and preflight first.
- Repo detection is useful but shallow. It identifies obvious Databricks, ADO, SQL, dbt, Python, tests, and risk files, but it does not deeply parse bundle targets, pipeline stages, SQL objects, or test commands yet.
- `de repo brief` can grow if large README/config snippets are captured. It is lazy-read, which is acceptable, but the package should keep guarding the always-loaded `DE.md` size.
- ADO live operations are mostly read-oriented. Bulk apply remains intentionally outside the light package, but users may expect more end-to-end ADO sprint operations after seeing bulk preview.
- Native Windows PowerShell execution is documented and structurally covered, but verification still happens on macOS unless a Windows 11 machine runs `smoke.ps1`.

## Keep It Light Principles

- Do not add new agents unless a role has a distinct permission boundary.
- Do not add a background service, database, or daemon.
- Keep `DE.md` under 60 lines and make tests enforce it.
- Prefer safer generated recommendations over new runtime layers.
- Add deep parsing only where it unlocks a clear workflow: bundle target detection, pipeline stage/environment detection, SQL object inventory, or test command discovery.

## Recommended Next Improvements

1. Safer UX defaults: all docs and generated commands should show dry-run/classify/policy-check before live query examples.
2. Better repo context with no extra runtime: parse `databricks.yml` target names and Azure Pipeline stage/environment names using lightweight text/YAML heuristics.
3. Add `de repo todo`: a short generated next-action list based on missing auth, missing tests, missing safe environment, or detected prod risk.
4. Add Windows evidence loop: ask one Windows 11 user to run `smoke.ps1` and paste output into `docs/verification-evidence.md`.
5. Improve ADO sprint UX later by adding an approved apply path only after bulk preview has evidence and explicit approval.
