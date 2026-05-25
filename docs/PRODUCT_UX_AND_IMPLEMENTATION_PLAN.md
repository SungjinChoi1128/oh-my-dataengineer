# Oh My DataEngineer: Product UX And Implementation Plan

## Product Thesis

Oh My DataEngineer is an OpenCode-first plugin for end-to-end data engineering work. It should behave like a small senior data delivery team inside the coding agent: it can clarify a business ask, discover source systems, design Databricks targets, generate implementation artifacts, validate data quality, manage delivery board traceability, and produce operational handoff evidence.

The product should not be framed as only a Databricks helper or only an ADO helper. Databricks is the first execution platform. ADO is the delivery-management bridge. The real product is the lifecycle layer that connects business requirements, engineering work, data quality, deployment, governance, and operations.

In a consulting company, this becomes more than a developer productivity plugin. It becomes a delivery assurance system: a way to standardize discovery, architecture, QA evidence, release readiness, and board traceability across different clients and project teams.

## Core UX Principle

The user should be able to stay at the intent level:

```text
Migrate customer orders from MSSQL to Databricks and make it ready for reporting.
```

The plugin should turn that into a guided lifecycle:

```text
Intake -> Discovery -> Contract -> Architecture -> Build -> QA -> Deploy -> Operate -> Board Sync
```

Every phase should produce durable evidence, not just chat. Evidence should live in project files and be linkable to pull requests, ADO items, Databricks resources, and runbooks.

## Is This The Best Product Shape?

This is the best shape for the first product because it solves the real failure mode in data engineering: work gets lost between business intent, platform implementation, validation, and delivery tracking.

The weaker alternative is a pack of isolated skills:

```text
databricks query skill
mssql skill
ado skill
lineage skill
```

That is useful but not defensible. Users still need to know what to run, in what order, what evidence matters, and when a task is actually complete.

The stronger product is an orchestration layer:

```text
business ask
  -> structured brief
  -> source evidence
  -> target design
  -> generated Databricks bundle
  -> QA/reconciliation evidence
  -> deployment readiness
  -> ADO/PR/runbook traceability
```

This makes the plugin feel like a data engineering operating system rather than a command catalog.

The design should stay flexible in two areas:

1. Databricks is the first execution target, but the lifecycle model should support Snowflake, Fabric, BigQuery, Airflow, dbt, and plain Spark later.
2. ADO is the first board-management target, but the delivery interface should be abstract enough for Jira, GitHub Issues, Linear, and ServiceNow later.

For consulting delivery, the strongest moat is not the agent prompts themselves. It is the combination of repeatable methodology, templates, artifacts, safety gates, and evidence files that can be reused across client accounts.

## Consulting Delivery Advantages

### Accelerated Onboarding

Consultants often join a client project after months or years of undocumented platform drift. The plugin should make first-week onboarding concrete:

```text
/de-status
/de-discover-source
/de-lineage-impact
```

These commands should produce a standardized view of the client environment: key data products, source systems, target catalogs, quality gaps, active delivery items, blockers, and known risks.

### Consulting IP As Templates

The template layer should encode the firm's delivery methodology:

```text
templates/data-contract/
templates/source-discovery-report/
templates/migration-assessment/
templates/architecture-decision-record/
templates/quality-evidence-pack/
templates/release-readiness/
templates/runbook/
```

This turns methodology into executable delivery assets. A new consultant should not need to remember the firm's preferred migration assessment structure; the plugin should generate it.

### Auditable Delivery Assurance

Clients frequently ask for proof:

- What was tested?
- What changed?
- Which tables are affected?
- Who approved the requirement?
- Which acceptance criteria passed?
- What was deployed?
- What is the rollback plan?

The `.dataengineer/evidence/` folder should be suitable for sprint-end or project-end handover. It should contain concise proof rather than verbose chat transcripts.

### Cross-Account Standardization

The same lifecycle should work across clients even when the tools vary. Client A may use ADO and Databricks. Client B may use Jira and Snowflake. The artifact model should remain stable while platform adapters vary.

## Target Users

### Data Engineer

Primary need: build and modify production data pipelines safely.

UX cases:

- Create a Databricks bundle for a new data product.
- Generate bronze, silver, and gold transformation scaffolds.
- Query Unity Catalog safely with 3-part names.
- Add jobs, schedules, alerts, and environment parameters.
- Run bundle validation before deployment.
- Generate PR notes with changed tables, jobs, tests, and rollback notes.

### Data Architect

Primary need: make structural decisions and keep platforms coherent.

UX cases:

- Turn vague requirements into target architecture.
- Choose bronze/silver/gold placement.
- Design Unity Catalog catalogs, schemas, ownership, and permissions.
- Review lineage impact before schema or table changes.
- Compare batch, streaming, CDC, and federation options.
- Produce architecture decision records.

### Migration Engineer

Primary need: move legacy workloads into Databricks with evidence.

UX cases:

- Inventory MSSQL tables, views, procedures, functions, and SQL Agent jobs.
- Parse SSIS packages and generate fact packs.
- Build migration candidate rankings.
- Generate source-to-target mappings.
- Identify business logic hidden in stored procedures.
- Create reconciliation tests and migration wiki pages.

### Data QA / Tester

Primary need: prove that the data is correct enough to trust.

UX cases:

- Generate data quality rules from schema and business requirements.
- Compare source and target row counts.
- Validate nullability, uniqueness, referential integrity, freshness, and duplicate rules.
- Produce exception/quarantine-table design.
- Create QA evidence reports for ADO and release approval.
- Detect missing tests before a task is marked complete.

### Analytics Engineer / BI Developer

Primary need: turn curated data into consumable business models.

UX cases:

- Design gold-layer facts, dimensions, materialized views, and aggregates.
- Document semantic definitions and measures.
- Trace dashboard dependencies before changing fields.
- Generate SQL checks for report-facing tables.
- Create downstream impact notes for dashboard owners.

### Scrum Master / Delivery Lead

Primary need: keep the work visible and accountable.

UX cases:

- Convert a data request into Epic, Feature, Story, and Task structure.
- Generate sprint-sized work breakdowns.
- Create acceptance criteria from data quality and business rules.
- Produce standup summaries from actual engineering evidence.
- Track blockers such as missing source access, unclear business logic, or failed reconciliation.
- Link ADO items to PRs, Databricks bundle paths, evidence files, and runbooks.

### Product Owner / Business Analyst

Primary need: ensure the data product answers the business question.

UX cases:

- Capture business definitions and acceptance criteria.
- Ask "what does this field mean?" and trace it to source, transformation, and downstream use.
- Review proposed target model in business terms.
- Approve or challenge quality thresholds.
- Receive a non-technical summary of delivery progress and release readiness.

### Data Governance / Platform Admin

Primary need: control access, ownership, compliance, and discoverability.

UX cases:

- Review Unity Catalog ownership and permissions.
- Enforce table/column comments for production objects.
- Check lineage before approving schema changes.
- Identify PII or sensitive fields that need masking, access rules, or retention policies.
- Produce audit evidence linking requirement, code, data objects, validation, and release.

### Operations / Support Engineer

Primary need: keep pipelines running after release.

UX cases:

- Generate runbooks with failure modes and recovery steps.
- Summarize failed job runs and likely root causes.
- Inspect freshness, latency, retry, and cost signals.
- Create incident summaries and follow-up tasks.
- Add alerts and ownership routing.

## Full UX Journeys

### Journey 1: New Databricks Data Product

User prompt:

```text
Build a new finance revenue data product in Databricks for Power BI reporting.
```

Expected plugin behavior:

1. Create an intake brief with owner, consumers, SLA, reporting needs, and source systems.
2. Ask only for missing information that materially changes the design.
3. Discover existing Unity Catalog assets and relevant source tables.
4. Propose bronze/silver/gold target layout.
5. Generate a Databricks bundle skeleton.
6. Add jobs or pipelines, environment variables, and permissions.
7. Generate QA rules and reconciliation checks.
8. Create ADO work items or update existing ones.
9. Produce release notes and runbook.

Primary artifacts:

```text
.dataengineer/briefs/revenue-data-product.md
.dataengineer/architecture/revenue-data-product.md
.dataengineer/contracts/revenue-data-contract.yml
.dataengineer/quality/revenue-quality-plan.md
.dataengineer/evidence/revenue-readiness.md
databricks.yml
resources/jobs.yml
resources/pipelines.yml
```

### Journey 2: MSSQL To Databricks Migration

User prompt:

```text
Migrate dbo.Customer and dbo.OrderHeader from MSSQL to Databricks.
```

Expected plugin behavior:

1. Run source discovery using MSSQL skills.
2. Generate fact packs for tables, procedures, dependencies, and jobs.
3. Detect likely business rules, keys, effective dates, deletes, and SCD patterns.
4. Create source-to-target mapping.
5. Propose bronze raw ingestion, silver validated model, and gold reporting model.
6. Generate Databricks bundle resources.
7. Generate reconciliation checks.
8. Create ADO migration work items.
9. Produce migration runbook and cutover checklist.

Important UX behavior:

- Do not jump directly to code generation.
- Show confidence levels for inferred business logic.
- Keep unknowns visible as open questions.
- Mark destructive or production-changing actions as gated.

### Journey 3: Data Quality Incident

User prompt:

```text
The sales dashboard looks wrong today. Investigate.
```

Expected plugin behavior:

1. Identify dashboard-facing gold tables if known.
2. Use lineage to find upstream silver, bronze, and source dependencies.
3. Check freshness, row counts, nulls, duplicates, schema changes, and failed jobs.
4. Inspect recent Delta table mutations with `DESCRIBE HISTORY` or equivalent table-history APIs.
5. Inspect recent job, pipeline, cluster, and compute events when available.
6. Compare current values against recent baselines where possible.
7. Summarize likely root cause with confidence and evidence.
8. Create ADO bug/incident item with links to queries and evidence.
9. Suggest fix path and regression test.

Primary output:

```text
Impact:
Likely root cause:
Evidence:
Affected tables/jobs/dashboards:
Immediate mitigation:
Permanent fix:
ADO link:
```

Incident investigation should explicitly distinguish:

```text
Data changed
Code changed
Schema changed
Schedule/freshness changed
Compute/runtime changed
Permission/access changed
Dashboard/semantic-layer changed
Unknown
```

### Journey 4: Schema Change With Downstream Impact

User prompt:

```text
Rename customer_id to account_customer_id in silver.customer.
```

Expected plugin behavior:

1. Describe the target table first.
2. Query lineage for downstream tables, jobs, dashboards, and columns.
3. Identify breaking consumers.
4. Recommend compatibility options: alias view, parallel column, versioned table, or coordinated breaking change.
5. Generate implementation plan and ADO tasks.
6. Require QA and downstream sign-off evidence before marking ready.

### Journey 5: Sprint Planning From Technical Scope

User prompt:

```text
Create sprint-ready tasks for the customer migration.
```

Expected plugin behavior:

1. Read migration brief, source discovery, architecture, and QA plan.
2. Create or update ADO Epic/Feature/Stories/Tasks.
3. Add acceptance criteria and verification commands.
4. Identify dependencies and blockers.
5. Generate sprint summary for human review.

ADO should be a bridge, not the only UX. The plugin should sync delivery state from actual evidence whenever possible.

### Journey 6: Release Readiness

User prompt:

```text
Is this Databricks bundle ready to deploy to prod?
```

Expected plugin behavior:

1. Run bundle validation.
2. Check target variables, permissions, service principals, and resource paths.
3. Check quality evidence and missing tests.
4. Check lineage impact and open blockers.
5. Confirm ADO acceptance criteria are satisfied.
6. Produce a deploy/no-deploy verdict.

Verdict format:

```text
Decision: ready | not ready | ready with risk
Blocking issues:
Evidence:
Residual risks:
Rollback plan:
ADO/release notes:
```

### Journey 7: Operational Handoff

User prompt:

```text
Create the handoff for support.
```

Expected plugin behavior:

1. Summarize pipeline purpose, owners, schedules, SLAs, dependencies, and alerts.
2. Document common failures and recovery steps.
3. Include Databricks job/pipeline links or identifiers.
4. Include ADO links, PR links, and release evidence.
5. Save a runbook under `.dataengineer/runbooks/`.

### Journey 8: FinOps And Compute Optimization

User prompt:

```text
Review this Databricks job for cost risks.
```

Expected plugin behavior:

1. Read bundle job and pipeline resource definitions.
2. Identify compute mode, node type, autoscaling, Photon/serverless usage, retry policy, timeout, and schedule frequency.
3. Flag obvious waste patterns such as oversized always-on clusters, missing autotermination, broad schedules, or duplicated jobs.
4. Recommend safer defaults based on workload shape: batch, streaming, SQL warehouse, serverless, job cluster, or shared compute.
5. Save recommendations under `.dataengineer/evidence/finops-review.md`.

Slash command:

```text
/de-optimize-cost
```

### Journey 9: Synthetic Test Data Generation

User prompt:

```text
Generate mock test data for this migration because we do not have prod access yet.
```

Expected plugin behavior:

1. Read source schema from MSSQL, Unity Catalog, or provided DDL.
2. Detect sensitive fields, identifiers, dates, enums, and likely relationships.
3. Generate synthetic data fixtures with representative edge cases.
4. Preserve constraints useful for testing: nullability, uniqueness, referential relationships, date ranges, status distributions, and malformed records.
5. Save fixture metadata and usage instructions.

This capability should avoid copying production data into local artifacts. For early MVP, prefer schema-shaped synthetic fixtures over distribution-matching claims unless real profiling evidence is available and safe to use.

### Journey 10: Legacy Business Logic Decomposition

User prompt:

```text
Explain this stored procedure before we migrate it.
```

Expected plugin behavior:

1. Parse or segment the procedure into functional blocks.
2. Identify inputs, outputs, temp tables, joins, filters, updates, deletes, MERGE logic, dynamic SQL, cursors, and transaction boundaries.
3. Create a human-readable business logic walkthrough.
4. Produce an implementation mapping to PySpark, SQL, dbt, or Lakeflow pipeline steps.
5. Flag low-confidence translations and require client sign-off before implementation.

This should happen before conversion. The product should document legacy intent first, then generate target code.

## UX Surfaces

### Natural Language

The primary UX is natural language. Users describe the business or engineering intent, and the orchestrator chooses the next lifecycle step.

### Slash Commands

OpenCode commands should provide fast entry points:

```text
/de-intake
/de-status
/de-discover-source
/de-design-target
/de-generate-bundle
/de-qa-plan
/de-lineage-impact
/de-ado-sync
/de-release-check
/de-runbook
/de-optimize-cost
/de-generate-fixtures
/de-legacy-logic
```

### Agent Mentions

Specialists should be directly invokable for expert workflows:

```text
@data-orchestrator
@databricks-architect
@source-discovery
@pipeline-engineer
@data-qa
@governance-lineage
@delivery-manager
@ops-engineer
@finops-reviewer
@legacy-translator
```

### Status View

The most important UX command is `/de-status`.

It should summarize:

```text
Task:
Current phase:
Databricks state:
Source discovery:
Quality evidence:
ADO/board state:
Open blockers:
Next best action:
```

### Evidence Files

The plugin should persist important work under:

```text
.dataengineer/
  briefs/
  source-inventory/
  mappings/
  contracts/
  architecture/
  quality/
  deployment/
  runbooks/
  evidence/
```

Artifact files should use strict JSON/YAML schemas where possible, with markdown used as the human-readable rendering. This keeps the local UX simple while preserving a path to centralized consulting dashboards later.

Recommended expanded structure:

```text
.dataengineer/
  schemas/
  briefs/
  source-inventory/
  mappings/
  contracts/
  architecture/
  quality/
  deployment/
  runbooks/
  evidence/
  exports/
```

Recommended rule:

```text
Every important markdown deliverable should either have a matching structured source file or embed enough frontmatter for later indexing.
```

## Standards And Ecosystem Strategy

The plugin should generate and consume established data engineering standards wherever practical. It should avoid inventing a private testing or metadata format when a common ecosystem format exists.

### Data Contracts

The `.dataengineer/contracts/` folder should support an internal normalized contract schema and import/export adapters for common data contract formats.

Initial contract fields:

```text
owner
business purpose
source systems
target tables
columns and types
nullable rules
freshness SLA
uniqueness rules
accepted value sets
PII/sensitivity flags
schema evolution policy
breaking change policy
quality checks
consumer sign-off
```

Future adapters can target open data contract specifications and third-party catalog tooling.

### Data Quality Execution

The `data-qa` agent should be a translator and orchestrator rather than a proprietary quality framework.

Priority order:

1. Generate simple Databricks SQL checks for MVP.
2. Generate native Delta or Databricks constraints where appropriate for hard invariants.
3. Generate Soda Core or Great Expectations configurations for richer quality suites.
4. Generate dbt tests when the project uses dbt.

### Metadata And Lineage

Unity Catalog lineage is the Databricks-first source of truth, but consulting clients may use Purview, Collibra, Atlan, OpenMetadata, or other catalogs.

The `governance-lineage` agent should use an internal lineage model that can be populated from:

```text
Unity Catalog lineage
Databricks system tables
OpenLineage-compatible events
dbt manifests
SQL parsing
MSSQL/SSIS discovery fact packs
manual external dependency declarations
```

For MVP, prioritize Unity Catalog and Databricks system tables. Keep the model exportable so OpenLineage support can be added without redesigning the product.

## Proposed OpenCode Architecture

### Plugin Layer

File target:

```text
.opencode/plugins/oh-my-dataengineer.ts
```

Responsibilities:

- Register custom data-engineering tools where useful.
- Add safety hooks for shell/tool execution.
- Redact secrets from logs and summaries.
- Inject lifecycle context during compaction.
- Add warnings for destructive SQL or production deployment commands.
- Optionally route certain prompts to the orchestrator.

### Agent Layer

Files:

```text
.opencode/agents/data-orchestrator.md
.opencode/agents/databricks-architect.md
.opencode/agents/source-discovery.md
.opencode/agents/pipeline-engineer.md
.opencode/agents/data-qa.md
.opencode/agents/governance-lineage.md
.opencode/agents/delivery-manager.md
.opencode/agents/ops-engineer.md
.opencode/agents/finops-reviewer.md
.opencode/agents/legacy-translator.md
```

### Skill Layer

Start by adapting existing skills from `/Users/sungjinchoi/Developer/cli_skills`:

```text
.opencode/skills/databricks-sql-execute/
.opencode/skills/databricks-unity-catalog/
.opencode/skills/databricks-data-lineage/
.opencode/skills/databricks-bundles/
.opencode/skills/databricks-jobs/
.opencode/skills/mssql-client/
.opencode/skills/mssql-legacy-discovery/
.opencode/skills/ssis-legacy-discovery/
.opencode/skills/migration-wiki-join/
.opencode/skills/ado-work-items/
.opencode/skills/ado-repos/
.opencode/skills/ado-pipelines/
.opencode/skills/ado-standup-reporter/
```

### Template Layer

Templates should make the plugin feel immediately useful:

```text
templates/databricks-bundle/basic-data-product/
templates/databricks-bundle/mssql-migration/
templates/data-contract/
templates/quality-plan/
templates/runbook/
templates/ado-work-breakdown/
templates/finops-review/
templates/legacy-logic-walkthrough/
templates/synthetic-fixtures/
```

## Safety And Trust UX

The plugin should make safety visible without making the user feel slowed down.

Hard gates:

- No destructive SQL without target table, row-count preflight, and explicit WHERE or equivalent safety proof.
- No production deployment without bundle validation evidence.
- No source-to-target migration marked complete without reconciliation evidence.
- No schema-breaking change without downstream lineage check.
- No secrets printed in command output, summaries, ADO comments, or artifacts.
- No unqualified Databricks table references in generated SQL.
- No synthetic fixture generation from production samples unless the user explicitly authorizes safe profiling inputs and the artifact is verified to contain no copied sensitive values.
- No automatic live board or platform writes during the initial scaffold/read-only phase.

Trust markers:

```text
Evidence found
Evidence missing
Inference
Assumption
Blocked
Ready
Risk accepted
```

Security hardening should be a product feature, not an internal implementation detail. The plugin should include local scanners and output filters for common secret patterns:

```text
tokens
PATs
passwords
connection strings
bearer headers
Databricks host/token pairs
SQL Server credential-bearing connection strings
private keys
```

Redaction must apply to generated markdown, JSON/YAML artifacts, ADO descriptions/comments, logs, and final summaries.

## MVP Recommendation

MVP should be:

```text
Databricks execution + migration discovery + QA evidence + ADO traceability
```

MVP should support one excellent golden path:

```text
MSSQL or existing source -> Databricks medallion target -> bundle scaffold -> QA plan -> ADO work items -> release/runbook evidence
```

Databricks target strategy:

- Use Databricks Declarative Automation Bundles as the main deployable unit.
- Generate clean modular `databricks.yml` plus `resources/*.yml`.
- Support Jobs and Lakeflow Spark Declarative Pipelines based on workload shape.
- Keep templates conservative for enterprise consulting: readable YAML, explicit variables, environment targets, permissions, and validation steps.
- Avoid making bleeding-edge platform features mandatory for MVP.

MVP components:

1. `data-orchestrator` agent.
2. `databricks-architect` agent.
3. `source-discovery` agent.
4. `data-qa` agent.
5. `delivery-manager` agent.
6. Ported Databricks, MSSQL, SSIS, migration wiki, and ADO skills.
7. `.dataengineer/` artifact schema.
8. Basic OpenCode plugin with secret redaction and safety warnings.
9. Bundle templates for a data product and a migration.
10. `/de-status`, `/de-intake`, `/de-discover-source`, `/de-design-target`, `/de-qa-plan`, `/de-ado-sync`, `/de-release-check`.

## Rollout Strategy

The safest consulting rollout is deliberately staged:

```text
Phase 1: Local scaffold
  -> markdown/templates/artifacts only
  -> no live writes
  -> no production data changes

Phase 2: Security gate
  -> redaction
  -> dangerous command detection
  -> read-only SQL and metadata operations
  -> deploy readiness checks without deploy

Phase 3: Connected sync
  -> live Databricks, MSSQL, and ADO interactions
  -> explicit write operations
  -> evidence-backed board updates
```

This lets the product create value before it has permission to touch client systems. It also gives consulting teams a low-risk way to pilot the methodology across accounts.

## Implementation Phases

### Phase 1: Product Skeleton

Deliverables:

- Repo README.
- `.opencode/agents` with orchestrator and first specialist prompts.
- `.opencode/skills` copied or adapted from existing CLI skills.
- `.dataengineer/` artifact conventions.
- First slash command templates.

Acceptance criteria:

- OpenCode can discover agents and skills.
- User can run a guided lifecycle in text without implementation automation.
- `/de-status` can summarize existing artifact files.
- No live Databricks, MSSQL, or ADO writes are required.

### Phase 2: Security Hardening

Deliverables:

- Secret redaction hooks.
- Dangerous SQL and production deployment warnings.
- Artifact scanner for generated markdown/JSON/YAML.
- Read-only command policy for early pilots.

Acceptance criteria:

- Generated artifacts do not contain common secret patterns.
- Destructive operations are flagged before execution.
- The plugin can operate in a read-only consulting assessment mode.

### Phase 3: Databricks Golden Path

Deliverables:

- Databricks bundle template.
- Databricks architecture/design artifact template.
- Databricks QA plan template.
- Bundle validation workflow.

Acceptance criteria:

- User can generate a bundle skeleton from a brief.
- Generated resources follow dev/stage/prod variable patterns.
- Release readiness can produce a deploy/no-deploy verdict.

### Phase 4: Migration Golden Path

Deliverables:

- MSSQL/SSIS discovery integration.
- Fact-pack to mapping workflow.
- Source-to-target contract template.
- Reconciliation plan generator.

Acceptance criteria:

- User can run discovery for a legacy source.
- Plugin creates source inventory and mapping artifacts.
- Plugin creates migration work breakdown.

### Phase 5: ADO Traceability

Deliverables:

- ADO work item generation templates.
- ADO status sync.
- Standup summary generation.
- PR/release notes generation from evidence.

Acceptance criteria:

- Plugin can create or update Epic/Feature/Story/Task structures.
- Evidence files are linked or referenced in ADO items.
- Standup summaries reflect real artifact state.

### Phase 6: Advanced Consulting Accelerators

Deliverables:

- FinOps review workflow.
- Synthetic fixture generation.
- Legacy business logic decomposition.
- OpenLineage/exportable lineage model.
- Contract import/export adapters.

Acceptance criteria:

- Cost risks can be reported from bundle resource files.
- Synthetic fixtures can be generated from schema without copied production values.
- Legacy SQL logic can be documented before conversion.
- Lineage and contracts are exportable to external standards.

### Phase 7: Platform Expansion

Potential extensions:

- Snowflake target.
- Microsoft Fabric target.
- BigQuery target.
- dbt-first transformation target.
- Jira or GitHub Issues delivery target.
- ServiceNow incident/change integration.

## Success Metrics

Product-level metrics:

- Time from vague request to sprint-ready plan.
- Time from source discovery to target design.
- Percentage of tasks with linked QA evidence.
- Percentage of production changes with lineage impact checks.
- Reduction in missing acceptance criteria.
- Reduction in undocumented pipeline handoffs.

Developer UX metrics:

- Fewer manual prompt steps per data task.
- Fewer times user must remember command names.
- Higher reuse of generated templates.
- Clearer deploy/no-deploy decisions.

## Open Questions

- Should `.dataengineer/` remain the canonical artifact folder with strict schemas, while optionally exporting summaries into `.omx/` for oh-my-codex lineage?
- Should the first installation mode copy existing skills or reference them globally?
- Should ADO sync be automatic during lifecycle phases or only explicit through `/de-ado-sync`?
- Should Databricks bundle generation target Lakeflow Spark Declarative Pipelines first, Jobs first, or support both based on task shape?
- Which quality adapters should be first after SQL checks: Soda Core, Great Expectations, dbt tests, or client-specific standards?
- Which contract schema should become the first import/export target?
- How much live Databricks system-table access should be required for incident workflows in MVP?
- Should FinOps and synthetic fixture generation be MVP-adjacent or explicitly post-MVP?

## Strong Recommendation

Build the first release as a lifecycle-first OpenCode plugin, not a pile of data platform skills.

The best first promise is:

```text
Turn a data engineering request into Databricks artifacts, QA evidence, and delivery-board traceability.
```

That promise is clear, valuable, and broad enough to grow beyond Databricks and ADO later.

For consulting rollout, the sharper promise is:

```text
Standardize data consulting delivery from intake to evidence-backed handoff.
```

The plugin should win by making excellent delivery behavior the default: structured discovery, explicit assumptions, reusable architecture, quality proof, board traceability, and safe operational handoff.
