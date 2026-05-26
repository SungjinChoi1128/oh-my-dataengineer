# Verification Evidence

Date: 2026-05-25

Environment used for local verification:

- macOS host
- Python 3.9.6
- No live ADO, Databricks, or MSSQL credentials
- No PowerShell Core available on this host, so `install.ps1` is provided for Windows 11 execution but not executed here

Checks run for version `0.9.0`:

```text
python3 de-opencode/tests/smoke.py
python3 de-opencode/tests/security_package.py
env PYTHONPYCACHEPREFIX=/private/tmp/de-opencode-pycache python3 -m compileall de-opencode/tools de-opencode/tests
python3 -m json.tool de-opencode/opencode.json
python3 de-opencode/tools/de.py doctor --format json
python3 de-opencode/tools/de.py auth
python3 de-opencode/tools/de.py repo init --root /private/tmp/de-opencode-repo-context-smoke
python3 de-opencode/tools/de.py repo doctor --root /private/tmp/de-opencode-repo-context-smoke
python3 de-opencode/tools/de.py repo brief --root /private/tmp/de-opencode-repo-context-smoke
python3 de-opencode/tools/de.py repo interview --root /private/tmp/de-opencode-repo-context-smoke --format json --max-questions 8
python3 de-opencode/tools/de.py workbench catalog
python3 de-opencode/tools/de.py workbench capabilities --domain ado
python3 de-opencode/tools/de.py workbench triage --request "refine sprint backlog for Databricks migration"
python3 de-opencode/tools/de.py ado refine --items-file de-opencode/samples/ado-work-items/sprint-items.json
python3 de-opencode/tools/de.py ado bulk preview --file de-opencode/samples/ado-work-items/bulk-updates.csv
python3 de-opencode/tools/de.py databricks bundle-doctor --bundle-yaml de-opencode/samples/databricks-bundle/databricks.good.yml
python3 de-opencode/tools/de.py databricks bundle-doctor --bundle-yaml de-opencode/samples/databricks-bundle/databricks.bad.yml --environment prod
python3 de-opencode/tools/de.py databricks runtime-advisor --current-runtime 15.4 --target-runtime 18.0 --environment prod --uses-delta-writes --uses-ml-serving
python3 de-opencode/tools/de.py mssql assess --metadata-file de-opencode/samples/mssql/inventory.json
python3 de-opencode/tools/de.py migration plan --objects-file de-opencode/samples/migration/object-map.json --source mssql --target databricks
python3 de-opencode/tools/de.py security checklist --scope client-review
python3 de-opencode/tools/de.py quality readiness --claim "migration release is ready" --environment prod
python3 de-opencode/tools/de_dbsql.py dry-run --sql "MERGE INTO sales.orders USING staging.orders ON sales.orders.id = staging.orders.id WHEN MATCHED THEN UPDATE SET amount = staging.orders.amount" --environment prod
python3 de-opencode/tools/de.py demo pipeline-doctor --out /private/tmp/de-evidence-ux --format markdown
python3 de-opencode/tools/de.py pipeline doctor --pipeline-yaml de-opencode/samples/ado-pipeline/azure-pipelines.bad.yml --log-file de-opencode/samples/ado-pipeline/build-failure.log --write-evidence --out /private/tmp/de-evidence-direct
python3 de-opencode/tools/de_release.py manifest --root de-opencode --out de-opencode/release-manifest.json
python3 de-opencode/tools/de_release.py verify --root de-opencode
env HOME=/private/tmp/de-opencode-home-workbench sh de-opencode/install-wsl.sh /private/tmp/de-opencode-install-workbench
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de doctor
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de auth
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de repo init --root /private/tmp/de-opencode-repo-context-smoke
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de-repo doctor --root /private/tmp/de-opencode-repo-context-smoke
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de repo interview --root /private/tmp/de-opencode-repo-context-smoke
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de-workbench catalog
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de workbench capabilities --domain ado
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de ado bulk preview --file /private/tmp/de-opencode-install-workbench/samples/ado-work-items/bulk-updates.csv
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de security checklist
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de-databricks bundle-doctor --bundle-yaml /private/tmp/de-opencode-install-workbench/samples/databricks-bundle/databricks.good.yml
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de databricks runtime-advisor --current-runtime 15.4 --target-runtime 16.4 --environment dev
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de demo pipeline-doctor --out /private/tmp/de-evidence-installed-final --format markdown
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de quality reconcile --source-count 10 --target-count 10
env PATH=/private/tmp/de-opencode-home-workbench/.local/bin:$PATH de release verify --root /private/tmp/de-opencode-install-workbench
python3 de-opencode/tools/de_pipeline.py preflight --pipeline-yaml de-opencode/samples/ado-pipeline/azure-pipelines.good.yml
python3 de-opencode/tools/de_pipeline.py diagnose --pipeline-yaml de-opencode/samples/ado-pipeline/azure-pipelines.bad.yml --log-file de-opencode/samples/ado-pipeline/build-failure.log --ledger /private/tmp/de-opencode-pipeline-ledger.jsonl
sh -n de-opencode/install-wsl.sh
secret-pattern scan over markdown, JSON, TypeScript, PowerShell, shell, and Python files
```

Results:

- Cross-platform Python smoke test passed.
- Security/package control assertions passed.
- Python tools compiled successfully when pycache was redirected to `/private/tmp`.
- `opencode.json` parsed as valid JSON.
- `de doctor` produced a human-readable readiness report and JSON output mode worked.
- `de auth` reported `.env supported: False`, safe-default posture, and enterprise-ready status based on configured modern auth rather than mere absence of legacy secrets.
- `de repo init`, `de repo doctor`, `de repo brief`, and `de repo interview` generated and read repo-local `.de-opencode` context artifacts without requiring secret files.
- `de workbench catalog`, `de workbench capabilities`, and `de workbench triage` exposed all existing package skills and domain coverage through one front door.
- `de ado refine` produced sprint/backlog refinement findings for missing acceptance criteria, child tasks, estimates, assignees, stale active work, and iteration gaps.
- `de ado bulk preview` generated a non-mutating bulk update preview with approval required.
- `de mssql assess` identified dynamic SQL, SQL Agent, and linked-server migration risks from inventory metadata.
- `de migration plan` produced required migration evidence and unresolved mapping counts.
- `de security checklist` and `de quality readiness` produced client/release checklists.
- `de demo pipeline-doctor` returned success for the bundled unsafe demo while still showing `BLOCKED` in the report.
- `de pipeline doctor` returned nonzero for the unsafe sample, wrote JSON/Markdown evidence, and included fix steps plus ADO next commands.
- Databricks Bundle Doctor passed the safe sample and blocked the unsafe sample with secret, production-mode, hardcoded-host, and runtime-evidence findings.
- Databricks Runtime Advisor produced required evidence for a production major-version runtime upgrade with Delta writes and ML/AI serving.
- Databricks SQL dry-run blocked unsafe production MERGE without approval, row-count evidence, and Unity Catalog 3-part names.
- Release manifest generation and verification passed for version `0.9.0`.
- Pipeline Doctor passed the safe sample, blocked the unsafe sample, diagnosed a missing Databricks CLI failure, and wrote ledger evidence.
- WSL-style installer copied package files into `/private/tmp/de-opencode-install-workbench`.
- Generated WSL wrappers ran successfully from a temporary PATH.
- Installed package verified against its release manifest.
- Installed `de quality reconcile` produced a passing row-count evidence summary.
- OpenCode plugin exposes safe data-engineering tools for config, Workbench catalog/triage/refinement/bulk preview/MSSQL assessment/migration plan/security checklist/quality readiness, Databricks Bundle Doctor, Runtime Advisor, Databricks SQL classification/dry-run, MSSQL policy/classification, ADO preflight, Pipeline Doctor, evidence templates, and row-count reconciliation.
- Shell syntax check passed for `install-wsl.sh`.
- Secret-pattern scan returned no matches.

Windows 11 validation to run on a Windows machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\de-opencode\smoke.ps1"
```

Expected result:

```text
[de-opencode] Windows smoke test passed
```
