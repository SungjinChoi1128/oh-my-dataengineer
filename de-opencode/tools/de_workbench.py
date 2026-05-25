#!/usr/bin/env python3
"""Unified data-engineering workbench reports for de-opencode."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional


SKILLS = [
    {
        "skill": "de-task-triage",
        "lane": "intake",
        "when": "Ambiguous or cross-system data-engineering requests.",
        "commands": ["de workbench triage --request \"...\"", "de workbench catalog"],
        "approval": "none",
    },
    {
        "skill": "de-ado-devops",
        "lane": "ado",
        "when": "Sprint work, backlog refinement, work items, repos, PRs, pipelines, wiki, tests.",
        "commands": ["de ado refine --items-file sprint-items.json", "de ado bulk preview --file bulk.csv", "de pipeline doctor ..."],
        "approval": "required for create/update/bulk apply/pipeline trigger",
    },
    {
        "skill": "de-databricks",
        "lane": "databricks",
        "when": "Databricks SQL, Unity Catalog, bundles, jobs, runtimes, serving, telemetry.",
        "commands": ["de databricks bundle-doctor ...", "de databricks runtime-advisor ...", "de-dbsql dry-run ..."],
        "approval": "required for deploys, writes, production runtime changes",
    },
    {
        "skill": "de-mssql",
        "lane": "mssql",
        "when": "SQL Server discovery, stored procedures, dependencies, execution posture.",
        "commands": ["de mssql assess --metadata-file mssql-inventory.json", "de-mssql policy-check"],
        "approval": "required for query/procedure execution or production DML",
    },
    {
        "skill": "de-migration-wiki",
        "lane": "migration",
        "when": "Legacy MSSQL/SSIS to Databricks/lakehouse migration evidence packs.",
        "commands": ["de migration plan --objects-file migration-objects.json --source mssql --target databricks"],
        "approval": "required for production cutover or destructive migration steps",
    },
    {
        "skill": "de-quality-gates",
        "lane": "quality",
        "when": "Completion proof, row counts, schema drift, tests, release readiness.",
        "commands": ["de quality readiness --claim \"...\"", "de quality reconcile --source-count N --target-count N"],
        "approval": "none for evidence generation; required for release signoff",
    },
    {
        "skill": "de-security-review",
        "lane": "security",
        "when": "Client security answers, secret handling, permission review, CI/CD risk.",
        "commands": ["de security checklist --scope client-review", "de doctor"],
        "approval": "required for relaxing guardrails or accessing secrets",
    },
]

CAPABILITIES = [
    {
        "domain": "ado",
        "surface": "work-items",
        "covered": True,
        "front_door": "de ado refine / de ado bulk preview",
        "upstream_skills": ["ado-work-items", "ado-standup-reporter", "ado-search"],
        "capabilities": ["sprint hygiene", "backlog refinement", "bulk preview", "standup input", "work item search planning"],
        "live_apply": "Use ado-work-items after preview/approval.",
    },
    {
        "domain": "ado",
        "surface": "pipelines",
        "covered": True,
        "front_door": "de pipeline doctor",
        "upstream_skills": ["ado-pipelines"],
        "capabilities": ["YAML preflight", "build log diagnosis", "release evidence", "Databricks bundle CI/CD checks"],
        "live_apply": "Pipeline trigger/release mutation remains approval-gated.",
    },
    {
        "domain": "ado",
        "surface": "repos-pr-wiki-tests-search",
        "covered": "guided",
        "front_door": "de workbench triage",
        "upstream_skills": ["ado-repos", "ado-wiki", "ado-test-plans", "ado-search"],
        "capabilities": ["route to existing detailed skills", "security-gated write classification", "client-safe guidance"],
        "live_apply": "Detailed live commands stay in underlying skills until promoted to first-class de wrappers.",
    },
    {
        "domain": "databricks",
        "surface": "sql-bundles-runtime",
        "covered": True,
        "front_door": "de databricks bundle-doctor / runtime-advisor / de-dbsql",
        "upstream_skills": ["databricks-sql-execute", "databricks-unity-catalog", "databricks-data-lineage"],
        "capabilities": ["SQL classify/dry-run", "UC 3-part name checks", "bundle CI/CD readiness", "runtime upgrade evidence"],
        "live_apply": "Live SQL/profile/catalog operations remain approval and auth gated.",
    },
    {
        "domain": "mssql",
        "surface": "discovery-migration",
        "covered": True,
        "front_door": "de mssql assess / de-mssql policy-check",
        "upstream_skills": ["mssql-client", "mssql-legacy-discovery"],
        "capabilities": ["policy posture", "SQL classify", "inventory risk assessment", "migration blocker summary"],
        "live_apply": "Query/procedure execution remains disabled unless explicitly enabled by client policy.",
    },
    {
        "domain": "migration",
        "surface": "evidence-pack",
        "covered": True,
        "front_door": "de migration plan / de quality readiness",
        "upstream_skills": ["mssql-legacy-discovery", "ssis-legacy-discovery", "migration-wiki-join"],
        "capabilities": ["object mapping plan", "unresolved mapping list", "required evidence", "quality gates"],
        "live_apply": "Cutover/destructive migration steps remain approval-gated.",
    },
]


def read_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_table(path: str) -> List[Dict[str, str]]:
    source = Path(path)
    if source.suffix.lower() == ".json":
        data = read_json(path)
        if not isinstance(data, list):
            raise ValueError("JSON input must be a list of objects")
        return [dict(item) for item in data]
    with source.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def cmd_catalog(args: argparse.Namespace) -> int:
    result = {"status": "ok", "skills": SKILLS}
    print(json.dumps(result, indent=2))
    return 0


def cmd_capabilities(args: argparse.Namespace) -> int:
    items = [item for item in CAPABILITIES if not args.domain or item["domain"] == args.domain]
    result = {
        "status": "ok",
        "domain": args.domain or "all",
        "capabilities": items,
        "security_model": {
            "env_file_support": False,
            "preferred_ado_auth": "Microsoft Entra service principal or managed identity; PAT is legacy-compatible fallback.",
            "preferred_databricks_auth": "Workload identity federation for CI/CD; OAuth/profile/service principal before PAT.",
            "preferred_mssql_auth": "Managed/integrated/Entra auth with encrypted ODBC Driver 18 connections.",
        },
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_triage(args: argparse.Namespace) -> int:
    text = args.request.lower()
    matches = []
    keyword_map = {
        "ado": ["ado", "sprint", "backlog", "work item", "story", "task", "pipeline", "pr", "wiki"],
        "databricks": ["databricks", "unity catalog", "bundle", "runtime", "warehouse", "genie", "serving"],
        "mssql": ["mssql", "sql server", "stored procedure", "ssis", "database"],
        "migration": ["migration", "migrate", "mapping", "cutover", "legacy"],
        "quality": ["quality", "qa", "reconcile", "row count", "schema", "evidence", "test"],
        "security": ["security", "secret", "permission", "client review", "pat", "token", "credential"],
    }
    for skill in SKILLS:
        lane = skill["lane"]
        score = sum(1 for word in keyword_map.get(lane, []) if word in text)
        if score:
            item = dict(skill)
            item["score"] = score
            matches.append(item)
    if not matches:
        matches = [dict(SKILLS[0], score=1)]
    matches = sorted(matches, key=lambda item: item["score"], reverse=True)
    result = {
        "status": "ok",
        "primary": matches[0],
        "related": matches[1:4],
        "safe_first": [
            "Run read-only discovery first.",
            "Use preview/dry-run/classify before write operations.",
            "Attach quality/security evidence before production changes.",
        ],
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_ado_refine(args: argparse.Namespace) -> int:
    items = read_table(args.items_file)
    findings = []
    stats = {"items": len(items), "stories": 0, "tasks": 0, "bugs": 0}
    for item in items:
        item_type = normalized(item.get("type") or item.get("work_item_type"))
        state = normalized(item.get("state"))
        identifier = str(item.get("id", "")).strip()
        title = str(item.get("title", "")).strip()
        if item_type == "user story":
            stats["stories"] += 1
        elif item_type == "task":
            stats["tasks"] += 1
        elif item_type == "bug":
            stats["bugs"] += 1
        if item_type in {"user story", "bug"} and not truthy(item.get("acceptance_criteria")):
            findings.append(finding(identifier, "missing_acceptance_criteria", "high", title, "Add testable acceptance criteria before sprint commitment."))
        if item_type == "user story" and intish(item.get("child_task_count")) == 0:
            findings.append(finding(identifier, "story_without_tasks", "high", title, "Split the story into child tasks for tracking and estimation."))
        if not truthy(item.get("assigned_to")):
            findings.append(finding(identifier, "missing_assignee", "medium", title, "Assign an owner or leave it out of sprint commitment."))
        if not truthy(item.get("iteration")):
            findings.append(finding(identifier, "missing_iteration", "medium", title, "Set the sprint/iteration path before planning."))
        if item_type in {"user story", "bug", "task"} and not truthy(item.get("estimate")):
            findings.append(finding(identifier, "missing_estimate", "medium", title, "Add story points or task hours for capacity planning."))
        if state in {"active", "in progress", "committed"} and intish(item.get("last_updated_days")) >= 7:
            findings.append(finding(identifier, "stale_active_item", "medium", title, "Review stale active item and add a status/comment/update."))
    result = {
        "status": "needs-refinement" if findings else "ok",
        "stats": stats,
        "findings": findings,
        "recommended_next_commands": [
            "ado-work-items sprint-board --team <TEAM>",
            "ado-work-items batch-get --ids <IDS>",
            "de ado bulk preview --file refinement-updates.csv",
        ],
    }
    print(json.dumps(result, indent=2))
    return 0 if not any(item["severity"] == "high" for item in findings) else 1


def cmd_ado_bulk_preview(args: argparse.Namespace) -> int:
    rows = read_table(args.file)
    operations = []
    issues = []
    allowed_fields = {"state", "assigned_to", "iteration", "tags", "title", "estimate", "priority"}
    for index, row in enumerate(rows, 1):
        item_id = str(row.get("id", "")).strip()
        field_name = normalized(row.get("field"))
        new_value = str(row.get("value", "")).strip()
        old_value = str(row.get("current", "")).strip()
        operation = {
            "row": index,
            "id": item_id,
            "field": field_name,
            "current": old_value,
            "value": new_value,
            "risk": "normal",
        }
        if not item_id:
            issues.append({"row": index, "severity": "high", "message": "Missing work item id."})
        if field_name not in allowed_fields:
            issues.append({"row": index, "severity": "medium", "message": f"Unsupported or unusual field: {field_name}"})
        if field_name == "state" and normalized(new_value) in {"done", "closed", "resolved"}:
            operation["risk"] = "completion"
            issues.append({"row": index, "severity": "medium", "message": "Completion state update should have PR/test/evidence attached."})
        operations.append(operation)
    result = {
        "status": "blocked" if any(item["severity"] == "high" for item in issues) else "preview",
        "operation": "ado-work-item-bulk-update",
        "count": len(operations),
        "operations": operations,
        "issues": issues,
        "apply_command": "ado-work-items batch-update ...",
        "approval_required": True,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "blocked" else 0


def cmd_mssql_assess(args: argparse.Namespace) -> int:
    data = read_json(args.metadata_file)
    objects = data.get("objects", []) if isinstance(data, dict) else data
    findings = []
    counts: Dict[str, int] = {}
    for obj in objects:
        obj_type = normalized(obj.get("type", "unknown"))
        counts[obj_type] = counts.get(obj_type, 0) + 1
        name = obj.get("name") or obj.get("full_name") or "<unknown>"
        if obj_type in {"procedure", "stored procedure"} and truthy(obj.get("uses_dynamic_sql")):
            findings.append(finding(str(name), "dynamic_sql", "high", str(name), "Review dynamic SQL and parameter handling before migration."))
        if truthy(obj.get("uses_linked_server")):
            findings.append(finding(str(name), "linked_server", "high", str(name), "Map linked server dependency and replacement access pattern."))
        if truthy(obj.get("uses_sql_agent")):
            findings.append(finding(str(name), "sql_agent_dependency", "medium", str(name), "Inventory scheduling, retries, and ownership before migration."))
    result = {
        "status": "needs-review" if findings else "ok",
        "object_counts": counts,
        "findings": findings,
        "recommended_next_commands": ["de-mssql policy-check", "mssql-legacy-discovery inventory --database <DB>"],
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_migration_plan(args: argparse.Namespace) -> int:
    objects = read_table(args.objects_file)
    unresolved = [item for item in objects if not truthy(item.get("target")) or truthy(item.get("risk"))]
    result = {
        "status": "needs-mapping" if unresolved else "ready-for-validation",
        "source": args.source,
        "target": args.target,
        "object_count": len(objects),
        "unresolved_count": len(unresolved),
        "required_evidence": [
            "source object inventory",
            "target object mapping",
            "row-count reconciliation",
            "schema diff",
            "failed/unresolved mapping list",
            "cutover and rollback notes",
        ],
        "unresolved": unresolved[:50],
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_security_checklist(args: argparse.Namespace) -> int:
    result = {
        "status": "ok",
        "scope": args.scope,
        "checklist": [
            "Run `de doctor` or `de auth` and confirm `.env` support is false.",
            "Confirm OpenCode denies secret/config files and asks for external directory access.",
            "Confirm ADO uses Microsoft Entra/service principal/managed identity where possible; PAT fallback must be least-privilege and client-approved.",
            "Confirm Databricks uses service principal/profile/OAuth where possible, not hardcoded PATs.",
            "Confirm MSSQL uses encryption and certificate validation.",
            "Confirm SQL writes, pipeline triggers, deploys, and bulk ADO updates are previewed/classified and approval-gated.",
            "Confirm evidence reports redact secrets and avoid raw production samples.",
        ],
        "client_answer": "This package is a local OpenCode configuration and tool bundle. It defaults to read-only discovery, blocks secret-file reads, classifies risky data-engineering actions, and requires explicit approval for writes, deploys, SQL execution, and bulk work-item changes.",
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_quality_readiness(args: argparse.Namespace) -> int:
    checks = [
        "claim defined",
        "code/test evidence attached",
        "SQL classified or dry-run complete",
        "row-count/schema evidence attached when data changed",
        "pipeline/bundle preflight complete when CI/CD changed",
        "security review complete when secrets/permissions/production are involved",
        "rollback or recovery note attached for production changes",
    ]
    result = {
        "status": "template",
        "claim": args.claim,
        "environment": args.environment,
        "required_checks": checks,
        "recommended_commands": [
            f"de-quality evidence-template --claim \"{args.claim}\" --environment {args.environment}",
            "de quality reconcile --source-count <SOURCE> --target-count <TARGET>",
            "de security checklist --scope release",
        ],
    }
    print(json.dumps(result, indent=2))
    return 0


def normalized(value: object) -> str:
    return str(value or "").strip().lower()


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() not in {"", "0", "false", "none", "null", "no"}


def intish(value: object) -> int:
    try:
        return int(float(str(value or "0").strip()))
    except ValueError:
        return 0


def finding(identifier: str, finding_id: str, severity: str, title: str, recommendation: str) -> Dict[str, str]:
    return {
        "item": identifier,
        "id": finding_id,
        "severity": severity,
        "title": title,
        "recommendation": recommendation,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="de-opencode workbench reports")
    sub = parser.add_subparsers(dest="command", required=True)
    catalog = sub.add_parser("catalog", help="List package skills and front-door workflows")
    catalog.set_defaults(func=cmd_catalog)
    capabilities = sub.add_parser("capabilities", help="Show package capability coverage by domain")
    capabilities.add_argument("--domain", choices=["ado", "databricks", "mssql", "migration"])
    capabilities.set_defaults(func=cmd_capabilities)
    triage = sub.add_parser("triage", help="Route a request to the right data-engineering workflow")
    triage.add_argument("--request", required=True)
    triage.set_defaults(func=cmd_triage)
    ado_refine = sub.add_parser("ado-refine", help="Generate backlog refinement findings from work item JSON/CSV")
    ado_refine.add_argument("--items-file", required=True)
    ado_refine.set_defaults(func=cmd_ado_refine)
    ado_bulk = sub.add_parser("ado-bulk-preview", help="Preview bulk ADO work-item changes from CSV/JSON")
    ado_bulk.add_argument("--file", required=True)
    ado_bulk.add_argument("--out")
    ado_bulk.set_defaults(func=cmd_ado_bulk_preview)
    mssql = sub.add_parser("mssql-assess", help="Assess MSSQL inventory metadata for migration risk")
    mssql.add_argument("--metadata-file", required=True)
    mssql.set_defaults(func=cmd_mssql_assess)
    migration = sub.add_parser("migration-plan", help="Create migration evidence plan from object mapping JSON/CSV")
    migration.add_argument("--objects-file", required=True)
    migration.add_argument("--source", required=True)
    migration.add_argument("--target", required=True)
    migration.set_defaults(func=cmd_migration_plan)
    security = sub.add_parser("security-checklist", help="Create client-facing security checklist")
    security.add_argument("--scope", default="client-review")
    security.set_defaults(func=cmd_security_checklist)
    quality = sub.add_parser("quality-readiness", help="Create release/readiness checklist for a claim")
    quality.add_argument("--claim", required=True)
    quality.add_argument("--environment", default="dev")
    quality.set_defaults(func=cmd_quality_readiness)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
