# Security Model

This package is safe-by-default scaffolding for enterprise data-engineering work.

## Defaults

- `.env` files are not a supported configuration path.
- Secret values are redacted in diagnostics.
- Live ADO, Databricks, and MSSQL calls are not performed by smoke tests.
- SQL and pipeline operations are classified before execution.
- Production deploys and data mutations require explicit approval.
- Secret-provider commands are never invoked by `doctor`; explicit resolve commands can invoke them without printing secret values.
- OpenCode permissions deny secret-file reads, allow normal code edits for the primary implementation flow, and ask-gate raw deployment, SQL, and pipeline mutation commands.
- Subagent task delegation is limited to the architecture and DevOps lanes and is ask-gated.

## Preferred Auth

- Azure DevOps: Microsoft Entra service principal or managed identity where possible; PAT remains a legacy-compatible fallback only.
- Databricks: workload identity federation for CI/CD and OAuth/profile/service principal before PAT.
- MSSQL: ODBC Driver 18, encrypted connections, certificate validation, managed/integrated auth where possible.
- Secret-provider command: optional client-approved adapter for resolving secrets without storing them in the package.

## Client Review Answer

The agent package should not store client secrets and should not read `.env` files. Client-specific secret resolution belongs in Microsoft Entra/managed identity/profile auth, a client-approved provider adapter, or managed process environment injection.

## Control Layers

1. OpenCode permissions allow code edits while blocking or ask-gating risky tools.
2. `de-guardrails.ts` blocks secret-file reads and risky raw bash commands.
3. Plugin custom tools expose safer structured entry points.
4. Python facades classify and dry-run sensitive actions before live execution.
5. QA evidence is generated through `de-quality-gates`.
6. Pipeline Doctor writes diagnosis/evidence into an optional append-only local ledger.
