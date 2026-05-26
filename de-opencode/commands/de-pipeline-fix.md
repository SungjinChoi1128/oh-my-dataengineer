---
description: Diagnose an Azure Pipeline or Databricks bundle failure
agent: data-engineer
---

Run the safest available pipeline diagnosis path: `de pipeline preflight` when only YAML is available, or `de pipeline doctor --pipeline-yaml <file> --log-file <log> --write-evidence` when logs exist. For Databricks bundles, also run `de databricks bundle-doctor`. Summarize blockers, suggested fixes, approval needs, and evidence files.
