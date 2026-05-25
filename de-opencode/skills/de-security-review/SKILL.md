---
name: de-security-review
description: Client-facing security review workflow for ADO, Databricks, MSSQL, OpenCode permissions, secret handling, SQL execution, CI/CD, audit logging, and Windows 11 distribution.
compatibility: opencode
metadata:
  audience: client-security-review
---

# Security Review

Use when answering client security questions or reviewing production readiness.

## Checklist

- Start with `de security checklist --scope client-review` for a client-facing answer.
- Auth uses least privilege and short-lived/profile-based credentials where possible.
- `.env` files are not supported by this package.
- Secret files are not read by default.
- SQL and pipeline writes are classified and approval-gated.
- MSSQL uses encrypted connections and certificate validation by default.
- Databricks production writes use service principals and Unity Catalog privileges.
- Azure Pipelines secrets use service connections, variable groups, or vault-backed variables.
- Logs and evidence redact secrets and avoid raw production data samples.

## UX Rule

Security review should produce plain-language client answers plus concrete evidence commands. Do not ask the user to expose credentials; use doctor, policy checks, manifests, and package permissions as evidence.
