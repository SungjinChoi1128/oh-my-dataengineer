# Windows 11 Install

Recommended path for consultants:

1. Use WSL2 Ubuntu for the best OpenCode experience.
2. Keep repositories inside the WSL filesystem when possible.
3. Install this package in WSL with `./install-wsl.sh`.

Native Windows path:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

For user-level environment setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -SetUserEnvironment
```

Then open a new terminal and run:

```powershell
de-config doctor
de doctor
de auth
de repo init
de repo brief
de workbench catalog
de workbench capabilities
de workbench triage --request "sprint backlog refinement"
de ado refine --items-file .\sprint-items.json
de ado bulk preview --file .\bulk-updates.csv
de databricks bundle-doctor --bundle-yaml .\databricks.yml --pipeline-yaml .\azure-pipelines.yml
de databricks runtime-advisor --current-runtime 15.4 --target-runtime 16.4 --environment dev
de mssql assess --metadata-file .\inventory.json
de migration plan --objects-file .\object-map.json --source mssql --target databricks
de security checklist --scope client-review
de-dbsql classify --sql "SELECT 1"
de-mssql policy-check
de pipeline doctor --pipeline-yaml .\azure-pipelines.yml --log-file .\build.log --write-evidence
de-quality evidence-template --claim "install smoke"
de-release verify
```

The installer does not install Python, OpenCode, Git, Databricks CLI, Azure CLI, or ODBC Driver 18. It detects and uses what the client machine already provides. `.env` files are not a supported configuration path; use client-approved managed identity/profile/auth providers or managed environment injection.

For CI or packaging smoke without running the smoke script during install:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -SkipSmoke
powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\de-opencode\smoke.ps1"
```
