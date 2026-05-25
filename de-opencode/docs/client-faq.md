# Client FAQ

## Does this send database credentials to the model?

No by design. The wrappers redact secrets, avoid printing full connection strings, and discourage reading local secret files.

## Can it change production data?

Not by default. SQL and pipeline write paths are classified and approval-gated. The smoke tests do not execute live writes.

## Is `.env` required?

No. `.env` is not supported by this package. Enterprise usage should rely on Microsoft Entra/managed identity/profile auth, managed process environment injection for non-secrets, or a client-approved secret provider. Secret-file reads are denied by policy.

## Are PATs required?

No. PATs remain a legacy-compatible fallback for tools or environments that cannot use modern auth, but the preferred model is Microsoft Entra/service principals/managed identity for ADO, Databricks OAuth/profile/workload identity federation, and managed/integrated/Entra auth for MSSQL.

## Why only three agents?

To avoid unnecessary role bloat. Most behavior lives in skills and safe tools. QA is a `de-quality-gates` skill in v1, not a separate agent.

## How does the package control the agent?

It uses layered controls: OpenCode permissions, ask-gated subagents, guardrail hooks, custom tools, and safe Python facades. The agent can inspect and classify freely, but raw production-affecting actions are routed through approval and QA gates.

## What is the killer feature?

Pipeline Doctor. It reads Azure Pipeline YAML and build logs, finds common Databricks/ADO failures, blocks unsafe deploy patterns, suggests fixes, and creates evidence for rerun or release decisions.
