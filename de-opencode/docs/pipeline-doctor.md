# Pipeline Doctor

Pipeline Doctor is the ADO/CI/CD killer feature lane.

It combines:

- pipeline YAML preflight
- build-log diagnosis
- known failure classification
- suggested fixes
- next ADO commands
- release evidence templates

## Offline Use

```bash
de pipeline preflight --pipeline-yaml azure-pipelines.yml
de pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log --write-evidence
de pipeline evidence --claim "Databricks bundle deploy is safe" --environment dev
de-ledger append --type pipeline_diagnosis --claim "Pipeline diagnosis reviewed" --target azure-pipelines.yml
```

## Live ADO Workflow

Use the existing ADO skills to collect facts:

```bash
ado-pipelines pipeline-list
ado-pipelines run-list --pipeline-id <PIPELINE_ID> --top 5
ado-pipelines build-status --id <BUILD_ID>
ado-pipelines build-logs --id <BUILD_ID>
ado-pipelines build-changes --id <BUILD_ID>
```

Then feed the build log into Pipeline Doctor:

```bash
de pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log --out out/de-evidence
```

## Production Rule

Do not rerun a failed production deployment until Pipeline Doctor has:

- no critical/high preflight issues
- build failure cause classified or explicitly marked unknown
- fix plan written
- `de-quality-gates` evidence attached
- production approval captured outside the tool
