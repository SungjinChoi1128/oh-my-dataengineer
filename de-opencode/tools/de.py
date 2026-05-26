#!/usr/bin/env python3
"""Human-first umbrella CLI for de-opencode."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
DEFAULT_EVIDENCE_DIR = Path("out") / "de-evidence"


def run_tool(script: str, args: List[str], expect_failure: bool = False) -> Tuple[int, Dict, str]:
    cmd = [sys.executable, str(TOOLS / script), *args]
    result = subprocess.run(cmd, text=True, capture_output=True)
    text = result.stdout.strip() or "{}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"status": "error", "raw_stdout": result.stdout, "raw_stderr": result.stderr}
    if result.returncode != 0 and not expect_failure:
        data.setdefault("status", "failed")
    return result.returncode, data, result.stderr


def artifact_paths(name: str, out_dir: Optional[str]) -> Dict[str, str]:
    if not out_dir:
        return {}
    target = Path(out_dir)
    json_path = target / f"{name}.json"
    md_path = target / f"{name}.md"
    return {"json": str(json_path), "markdown": str(md_path)}


def write_artifacts(name: str, data: Dict, out_dir: Optional[str], markdown: str) -> Dict[str, str]:
    artifacts = artifact_paths(name, out_dir)
    if not artifacts:
        return {}
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    Path(artifacts["json"]).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    Path(artifacts["markdown"]).write_text(markdown + "\n", encoding="utf-8")
    return artifacts


def print_output(data: Dict, fmt: str, text: str, markdown: str) -> None:
    if fmt == "json":
        print(json.dumps(data, indent=2))
    elif fmt == "markdown":
        print(markdown)
    else:
        print(text)


def severity_label(severity: str) -> str:
    return severity.upper()


def render_pipeline_text(data: Dict, artifacts: Optional[Dict[str, str]] = None) -> str:
    status = str(data.get("status", "unknown")).upper()
    lines = [f"Pipeline Doctor: {status}"]
    preflight = data.get("preflight", {})
    issues = preflight.get("issues", [])
    warnings = preflight.get("warnings", [])
    matches = data.get("diagnosis", {}).get("matches", [])
    actions = data.get("fix_plan", {}).get("actions", [])

    if issues:
        lines += ["", "Blocking issues:"]
        for item in issues:
            lines.append(f"- {severity_label(item.get('severity', ''))}: {item.get('message', '')}")
    if warnings:
        lines += ["", "Warnings:"]
        for item in warnings:
            lines.append(f"- {severity_label(item.get('severity', ''))}: {item.get('message', '')}")
    if matches:
        lines += ["", "Log diagnosis:"]
        for item in matches:
            lines.append(f"- {severity_label(item.get('severity', ''))}: {item.get('summary', '')}")
            for evidence in item.get("evidence", [])[:2]:
                lines.append(f"  Evidence: {evidence}")
    if actions:
        lines += ["", "Fix plan:"]
        for idx, action in enumerate(actions, 1):
            lines.append(f"{idx}. {action.get('action', '')}")
    next_commands = data.get("fix_plan", {}).get("ado_next_commands", [])
    if next_commands:
        lines += ["", "Next ADO commands:"]
        lines += [f"- {cmd}" for cmd in next_commands]
    if artifacts:
        lines += ["", "Evidence written:"]
        for kind, path in artifacts.items():
            lines.append(f"- {kind}: {path}")
    return "\n".join(lines)


def render_pipeline_markdown(data: Dict, artifacts: Optional[Dict[str, str]] = None) -> str:
    status = str(data.get("status", "unknown")).upper()
    lines = ["# Pipeline Doctor Evidence", "", f"**Status:** {status}", ""]
    preflight = data.get("preflight", {})
    sections = [
        ("Blocking Issues", preflight.get("issues", []), "message"),
        ("Warnings", preflight.get("warnings", []), "message"),
        ("Log Diagnosis", data.get("diagnosis", {}).get("matches", []), "summary"),
        ("Fix Plan", data.get("fix_plan", {}).get("actions", []), "action"),
    ]
    for title, items, field in sections:
        if not items:
            continue
        lines += [f"## {title}", ""]
        for item in items:
            severity = severity_label(item.get("severity", "info"))
            lines.append(f"- **{severity}:** {item.get(field, '')}")
            for evidence in item.get("evidence", [])[:2]:
                lines.append(f"  - Evidence: `{evidence}`")
        lines.append("")
    next_commands = data.get("fix_plan", {}).get("ado_next_commands", [])
    if next_commands:
        lines += ["## Next ADO Commands", ""]
        lines += [f"- `{cmd}`" for cmd in next_commands]
        lines.append("")
    if artifacts:
        lines += ["## Artifacts", ""]
        lines += [f"- **{kind}:** `{path}`" for kind, path in artifacts.items()]
        lines.append("")
    return "\n".join(lines).rstrip()


def render_doctor_text(data: Dict) -> str:
    checks = data.get("checks", {})
    config = data.get("config", [])
    lines = ["de-opencode Doctor"]
    lines.append("")
    lines.append("Runtime:")
    for key in ("platform", "python", "opencode", "git", "databricks", "az", "dotenv_supported"):
        value = checks.get(key, "")
        state = "OK" if value not in ("", False, None) else "Missing"
        if key == "dotenv_supported":
            state = "OK" if value is False else "Warn"
        lines.append(f"- {key}: {state} {value}")
    missing = [item for item in config if item.get("source") == "missing"]
    if missing:
        lines.append("")
        lines.append("Config not set yet:")
        for item in missing:
            secret = "secret" if item.get("secret") else "non-secret"
            lines.append(f"- {item.get('key')} ({secret})")
    lines.append("")
    posture = data.get("auth_posture", {})
    if posture:
        lines.append("Auth posture:")
        for key in ("ado", "databricks", "mssql"):
            lines.append(f"- {key}: {posture.get(key, 'unknown')}")
        if posture.get("legacy_secrets_present"):
            lines.append(f"- legacy secrets present: {', '.join(posture.get('legacy_secrets_present', []))}")
        lines.append(f"- safe default: {posture.get('safe_default')}")
        lines.append(f"- enterprise ready: {posture.get('enterprise_ready')}")
        lines.append("")
    lines.append("Next:")
    lines.append("- Configure non-secret defaults through DE_CONFIG_PATH or environment.")
    lines.append("- Use Microsoft Entra, managed identity, Databricks OAuth/profile, or a client-approved secret provider for secrets.")
    lines.append("- Run `de demo pipeline-doctor` to see the workflow.")
    return "\n".join(lines)


def cmd_doctor(args: argparse.Namespace) -> int:
    code, data, _ = run_tool("de_config.py", ["doctor", "--all"])
    text = render_doctor_text(data)
    markdown = "# de-opencode Doctor\n\n```text\n" + text + "\n```\n"
    print_output(data, args.format, text, markdown)
    return code


def cmd_auth(args: argparse.Namespace) -> int:
    code, data, _ = run_tool("de_config.py", ["auth"])
    posture = data.get("posture", {})
    text = "Enterprise Auth: " + ("READY" if posture.get("enterprise_ready") else "NEEDS-ACTION")
    text += "\n- ADO: " + str(posture.get("ado", "unknown"))
    text += "\n- Databricks: " + str(posture.get("databricks", "unknown"))
    text += "\n- MSSQL: " + str(posture.get("mssql", "unknown"))
    text += "\n- .env supported: " + str(posture.get("dotenv_supported", False))
    text += "\n- Safe default: " + str(posture.get("safe_default", False))
    text += "\n- Preferred: ADO Entra/managed identity, Databricks WIF/OAuth/profile, MSSQL managed/integrated/Entra"
    if posture.get("legacy_secrets_present"):
        text += "\n- Legacy env secrets present: " + ", ".join(posture["legacy_secrets_present"])
    markdown = "# Enterprise Auth\n\n```text\n" + text + "\n```\n"
    print_output(data, args.format, text, markdown)
    return code


def cmd_pipeline_doctor(args: argparse.Namespace) -> int:
    out_dir = args.out or (str(DEFAULT_EVIDENCE_DIR) if args.write_evidence else None)
    ledger = str(Path(out_dir) / "ledger.jsonl") if out_dir else ""
    tool_args = ["diagnose"]
    if args.pipeline_yaml:
        tool_args += ["--pipeline-yaml", args.pipeline_yaml]
    if args.log_file:
        tool_args += ["--log-file", args.log_file]
    if args.log_text:
        tool_args += ["--log-text", args.log_text]
    if ledger:
        tool_args += ["--ledger", ledger]
    tool_args += ["--environment", args.environment]
    code, data, _ = run_tool("de_pipeline.py", tool_args, expect_failure=True)
    artifacts = artifact_paths("pipeline-diagnosis", out_dir)
    text = render_pipeline_text(data, artifacts)
    markdown = render_pipeline_markdown(data, artifacts)
    if artifacts:
        write_artifacts("pipeline-diagnosis", data, out_dir, markdown)
    print_output(data, args.format, text, markdown)
    if getattr(args, "success_on_blocked", False) and data.get("status") in {"ok", "warning", "blocked"}:
        return 0
    return code


def cmd_pipeline_preflight(args: argparse.Namespace) -> int:
    code, data, _ = run_tool("de_pipeline.py", ["preflight", "--pipeline-yaml", args.pipeline_yaml], expect_failure=True)
    wrapper = {
        "status": data.get("status"),
        "preflight": data,
        "diagnosis": {"matches": []},
        "fix_plan": {"actions": [], "ado_next_commands": []},
    }
    text = render_pipeline_text(wrapper)
    markdown = render_pipeline_markdown(wrapper)
    print_output(data, args.format, text, markdown)
    return code


def cmd_pipeline_evidence(args: argparse.Namespace) -> int:
    tool_args = ["evidence", "--claim", args.claim, "--environment", args.environment]
    if args.build_id:
        tool_args += ["--build-id", args.build_id]
    if args.pipeline_id:
        tool_args += ["--pipeline-id", args.pipeline_id]
    code, data, _ = run_tool("de_pipeline.py", tool_args)
    markdown = "# Pipeline Release Evidence\n\n```json\n" + json.dumps(data, indent=2) + "\n```\n"
    text = "Pipeline evidence template created for: " + args.claim
    artifacts = write_artifacts("pipeline-evidence", data, args.out, markdown)
    if artifacts:
        text += "\nEvidence written:\n" + "\n".join(f"- {k}: {v}" for k, v in artifacts.items())
    print_output(data, args.format, text, markdown)
    return code


def cmd_demo_pipeline_doctor(args: argparse.Namespace) -> int:
    sample_dir = ROOT / "samples" / "ado-pipeline"
    demo_args = argparse.Namespace(
        pipeline_yaml=str(sample_dir / "azure-pipelines.bad.yml"),
        log_file=str(sample_dir / "build-failure.log"),
        log_text=None,
        environment="prod",
        out=args.out or str(DEFAULT_EVIDENCE_DIR / "demo-pipeline-doctor"),
        write_evidence=True,
        format=args.format,
        success_on_blocked=True,
    )
    return cmd_pipeline_doctor(demo_args)


def cmd_quality_reconcile(args: argparse.Namespace) -> int:
    code, data, _ = run_tool("de_quality.py", [
        "reconcile",
        "--source-count",
        str(args.source_count),
        "--target-count",
        str(args.target_count),
        "--tolerance",
        str(args.tolerance),
    ], expect_failure=True)
    status = data.get("status", "unknown").upper()
    text = (
        f"Row Count Reconciliation: {status}\n"
        f"- source: {data.get('source_count')}\n"
        f"- target: {data.get('target_count')}\n"
        f"- difference: {data.get('difference')} ({data.get('difference_percent')}%)\n"
        f"- tolerance: {data.get('tolerance')}"
    )
    markdown = "# Row Count Reconciliation\n\n```text\n" + text + "\n```\n"
    print_output(data, args.format, text, markdown)
    return code


def render_databricks_bundle_text(data: Dict) -> str:
    status = data.get("status", "unknown").upper()
    lines = [f"Databricks Bundle Doctor: {status}"]
    for label, key in [("Blocking issues", "issues"), ("Warnings", "warnings")]:
        items = data.get(key, [])
        if items:
            lines += ["", f"{label}:"]
            for item in items:
                lines.append(f"- {severity_label(item.get('severity', ''))}: {item.get('message', '')}")
    actions = data.get("fix_plan", [])
    if actions:
        lines += ["", "Fix plan:"]
        for idx, action in enumerate(actions, 1):
            lines.append(f"{idx}. {action}")
    commands = data.get("evidence_commands", [])
    if commands:
        lines += ["", "Evidence commands:"]
        lines += [f"- {cmd}" for cmd in commands]
    return "\n".join(lines)


def render_databricks_runtime_text(data: Dict) -> str:
    status = data.get("status", "unknown").upper()
    lines = [f"Databricks Runtime Advisor: {status}"]
    risks = data.get("risks", [])
    if risks:
        lines += ["", "Risks:"]
        for risk in risks:
            lines.append(f"- {severity_label(risk.get('severity', ''))}: {risk.get('message', '')}")
    checks = data.get("required_checks", [])
    if checks:
        lines += ["", "Required checks:"]
        for idx, check in enumerate(checks, 1):
            lines.append(f"{idx}. {check}")
    if data.get("approval_required"):
        lines += ["", "Approval required before production rollout or high-risk upgrade."]
    return "\n".join(lines)


def cmd_databricks_bundle_doctor(args: argparse.Namespace) -> int:
    tool_args = ["bundle-doctor", "--bundle-yaml", args.bundle_yaml, "--environment", args.environment]
    if args.pipeline_yaml:
        tool_args += ["--pipeline-yaml", args.pipeline_yaml]
    code, data, _ = run_tool("de_databricks.py", tool_args, expect_failure=True)
    text = render_databricks_bundle_text(data)
    markdown = "# Databricks Bundle Doctor\n\n```text\n" + text + "\n```\n"
    print_output(data, args.format, text, markdown)
    return code


def cmd_databricks_runtime_advisor(args: argparse.Namespace) -> int:
    tool_args = [
        "runtime-advisor",
        "--current-runtime",
        args.current_runtime,
        "--target-runtime",
        args.target_runtime,
        "--environment",
        args.environment,
    ]
    for flag, enabled in [
        ("--uses-udfs", args.uses_udfs),
        ("--uses-jars", args.uses_jars),
        ("--uses-streaming", args.uses_streaming),
        ("--uses-delta-writes", args.uses_delta_writes),
        ("--uses-ml-serving", args.uses_ml_serving),
    ]:
        if enabled:
            tool_args.append(flag)
    code, data, _ = run_tool("de_databricks.py", tool_args)
    text = render_databricks_runtime_text(data)
    markdown = "# Databricks Runtime Advisor\n\n```text\n" + text + "\n```\n"
    print_output(data, args.format, text, markdown)
    return code


def cmd_databricks_sql_execute(args: argparse.Namespace) -> int:
    tool_args = ["execute", "--sql", args.sql, "--environment", args.environment, "--format", args.result_format]
    for flag, value in [
        ("--warehouse-id", args.warehouse_id),
        ("--host", args.host),
        ("--profile", args.profile),
        ("--timeout", str(args.timeout)),
        ("--limit", str(args.limit)),
    ]:
        if value:
            tool_args += [flag, value]
    for flag, enabled in [
        ("--dry-run-only", args.dry_run_only),
        ("--allow-write", args.allow_write),
        ("--confirm-write", args.confirm_write),
        ("--row-count-checked", args.row_count_checked),
        ("--allow-unqualified-names", args.allow_unqualified_names),
    ]:
        if enabled:
            tool_args.append(flag)
    return subprocess.run([sys.executable, str(TOOLS / "de_dbsql.py"), *tool_args]).returncode


def cmd_databricks_warehouses(args: argparse.Namespace) -> int:
    tool_args = ["warehouses", "--format", args.result_format]
    for flag, value in [("--host", args.host), ("--profile", args.profile)]:
        if value:
            tool_args += [flag, value]
    return subprocess.run([sys.executable, str(TOOLS / "de_dbsql.py"), *tool_args]).returncode


def cmd_ado_live(args: argparse.Namespace) -> int:
    if args.ado_live_command == "query":
        tool_args = ["query", "--wiql", args.wiql, "--output", args.output]
    elif args.ado_live_command == "work-item":
        tool_args = ["work-item", "--id", str(args.id), "--output", args.output]
    else:
        tool_args = ["pipeline-runs", "--top", str(args.top), "--output", args.output]
        if args.pipeline_id:
            tool_args += ["--pipeline-id", str(args.pipeline_id)]
    for flag, value in [("--org", args.org), ("--project", args.project)]:
        if value:
            tool_args += [flag, value]
    return subprocess.run([sys.executable, str(TOOLS / "de_ado.py"), *tool_args]).returncode


def cmd_mssql_query(args: argparse.Namespace) -> int:
    tool_args = ["query", "--sql", args.sql, "--auth-mode", args.auth_mode, "--format", args.result_format, "--timeout", str(args.timeout)]
    for flag, value in [
        ("--server", args.server),
        ("--database", args.database),
        ("--user", args.user),
        ("--password-env", args.password_env),
    ]:
        if value:
            tool_args += [flag, value]
    for flag, enabled in [("--allow-dangerous", args.allow_dangerous), ("--allow-sql-password", args.allow_sql_password)]:
        if enabled:
            tool_args.append(flag)
    return subprocess.run([sys.executable, str(TOOLS / "de_mssql.py"), *tool_args]).returncode


def render_workbench_text(title: str, data: Dict) -> str:
    status = str(data.get("status", "ok")).upper()
    lines = [f"{title}: {status}"]
    if "primary" in data:
        primary = data["primary"]
        lines += ["", f"Primary skill: {primary.get('skill')}"]
        lines.append(f"- lane: {primary.get('lane')}")
        lines.append(f"- when: {primary.get('when')}")
        lines += ["", "Suggested commands:"]
        lines += [f"- {cmd}" for cmd in primary.get("commands", [])]
    if "skills" in data:
        lines += ["", "Skills:"]
        for skill in data["skills"]:
            lines.append(f"- {skill.get('skill')}: {skill.get('when')}")
    if "capabilities" in data:
        lines += ["", "Capabilities:"]
        for item in data["capabilities"]:
            lines.append(f"- {item.get('domain')}/{item.get('surface')}: {item.get('front_door')}")
    if "stats" in data:
        lines += ["", "Stats:"]
        for key, value in data["stats"].items():
            lines.append(f"- {key}: {value}")
    if "findings" in data and data["findings"]:
        lines += ["", "Findings:"]
        for item in data["findings"]:
            lines.append(f"- {severity_label(item.get('severity', ''))}: {item.get('title', item.get('item', ''))} - {item.get('recommendation', '')}")
    if "issues" in data and data["issues"]:
        lines += ["", "Issues:"]
        for item in data["issues"]:
            lines.append(f"- {severity_label(item.get('severity', ''))}: {item.get('message', '')}")
    if "operations" in data:
        lines += ["", f"Operations: {data.get('count', len(data['operations']))}"]
        for item in data["operations"][:10]:
            lines.append(f"- #{item.get('id')} {item.get('field')}: {item.get('current')} -> {item.get('value')} ({item.get('risk')})")
    if "required_evidence" in data:
        lines += ["", "Required evidence:"]
        lines += [f"- {item}" for item in data["required_evidence"]]
    if "required_checks" in data:
        lines += ["", "Required checks:"]
        lines += [f"- {item}" for item in data["required_checks"]]
    if "checklist" in data:
        lines += ["", "Checklist:"]
        lines += [f"- {item}" for item in data["checklist"]]
    if "recommended_commands" in data:
        lines += ["", "Recommended commands:"]
        lines += [f"- {cmd}" for cmd in data["recommended_commands"]]
    if "recommended_next_commands" in data:
        lines += ["", "Next commands:"]
        lines += [f"- {cmd}" for cmd in data["recommended_next_commands"]]
    if data.get("approval_required"):
        lines += ["", "Approval required before apply/write/release."]
    return "\n".join(lines)


def cmd_workbench_proxy(args: argparse.Namespace) -> int:
    tool_args = [args.workbench_command]
    mapping = {
        "triage": [("--request", getattr(args, "request", None))],
        "capabilities": [("--domain", getattr(args, "domain", None))],
        "ado-refine": [("--items-file", getattr(args, "items_file", None))],
        "ado-bulk-preview": [("--file", getattr(args, "file", None)), ("--out", getattr(args, "out", None))],
        "mssql-assess": [("--metadata-file", getattr(args, "metadata_file", None))],
        "migration-plan": [
            ("--objects-file", getattr(args, "objects_file", None)),
            ("--source", getattr(args, "source", None)),
            ("--target", getattr(args, "target", None)),
        ],
        "security-checklist": [("--scope", getattr(args, "scope", None))],
        "quality-readiness": [("--claim", getattr(args, "claim", None)), ("--environment", getattr(args, "environment", None))],
    }
    for flag, value in mapping.get(args.workbench_command, []):
        if value:
            tool_args += [flag, value]
    code, data, _ = run_tool("de_workbench.py", tool_args, expect_failure=True)
    title = {
        "catalog": "Workbench Catalog",
        "capabilities": "Capability Catalog",
        "triage": "Task Triage",
        "ado-refine": "ADO Backlog Refinement",
        "ado-bulk-preview": "ADO Bulk Preview",
        "mssql-assess": "MSSQL Assessment",
        "migration-plan": "Migration Plan",
        "security-checklist": "Security Checklist",
        "quality-readiness": "Quality Readiness",
    }.get(args.workbench_command, "Workbench")
    text = render_workbench_text(title, data)
    markdown = f"# {title}\n\n```text\n{text}\n```\n"
    print_output(data, args.format, text, markdown)
    return code


def cmd_release_verify(args: argparse.Namespace) -> int:
    code, data, _ = run_tool("de_release.py", ["verify", "--root", args.root], expect_failure=True)
    status = data.get("status", "unknown").upper()
    text = f"Release Verify: {status}"
    issues = data.get("issues", [])
    if issues:
        text += "\nIssues:\n" + "\n".join(f"- {issue}" for issue in issues)
    markdown = "# Release Verify\n\n```text\n" + text + "\n```\n"
    print_output(data, args.format, text, markdown)
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="de",
        description="Data Engineering OpenCode package: diagnose pipelines, validate quality, and produce evidence.",
    )
    def add_format_arg(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--format",
            choices=["text", "json", "markdown"],
            default=argparse.SUPPRESS,
            help="Output format",
        )

    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Run Windows/team onboarding checks")
    add_format_arg(doctor)
    doctor.set_defaults(func=cmd_doctor)
    auth = sub.add_parser("auth", help="Show enterprise auth posture")
    add_format_arg(auth)
    auth.set_defaults(func=cmd_auth)

    workbench = sub.add_parser("workbench", help="Unified data-engineering skill workbench")
    workbench_sub = workbench.add_subparsers(dest="workbench_command", required=True)
    wb_catalog = workbench_sub.add_parser("catalog", help="List skills and workflow front doors")
    add_format_arg(wb_catalog)
    wb_catalog.set_defaults(func=cmd_workbench_proxy)
    wb_capabilities = workbench_sub.add_parser("capabilities", help="Show package capability coverage")
    wb_capabilities.add_argument("--domain", choices=["ado", "databricks", "mssql", "migration"])
    add_format_arg(wb_capabilities)
    wb_capabilities.set_defaults(func=cmd_workbench_proxy)
    wb_triage = workbench_sub.add_parser("triage", help="Route a request to the right skill workflow")
    wb_triage.add_argument("--request", required=True)
    add_format_arg(wb_triage)
    wb_triage.set_defaults(func=cmd_workbench_proxy)

    ado = sub.add_parser("ado", help="ADO sprint, backlog, and work-item workflows")
    ado_sub = ado.add_subparsers(dest="ado_command", required=True)
    ado_refine = ado_sub.add_parser("refine", help="Generate backlog refinement findings")
    ado_refine.add_argument("--items-file", required=True)
    add_format_arg(ado_refine)
    ado_refine.set_defaults(func=lambda args: setattr(args, "workbench_command", "ado-refine") or cmd_workbench_proxy(args))
    ado_bulk = ado_sub.add_parser("bulk", help="Bulk work item workflows")
    ado_bulk_sub = ado_bulk.add_subparsers(dest="ado_bulk_command", required=True)
    ado_bulk_preview = ado_bulk_sub.add_parser("preview", help="Preview bulk work-item updates")
    ado_bulk_preview.add_argument("--file", required=True)
    ado_bulk_preview.add_argument("--out")
    add_format_arg(ado_bulk_preview)
    ado_bulk_preview.set_defaults(func=lambda args: setattr(args, "workbench_command", "ado-bulk-preview") or cmd_workbench_proxy(args))
    ado_query = ado_sub.add_parser("query", help="Run live read-only ADO WIQL query through Azure CLI")
    ado_query.add_argument("--wiql", required=True)
    ado_query.add_argument("--org")
    ado_query.add_argument("--project")
    ado_query.add_argument("--output", choices=["json", "table", "yaml"], default="json")
    ado_query.set_defaults(func=lambda args: setattr(args, "ado_live_command", "query") or cmd_ado_live(args))
    ado_item = ado_sub.add_parser("work-item", help="Show live ADO work item through Azure CLI")
    ado_item.add_argument("--id", required=True, type=int)
    ado_item.add_argument("--org")
    ado_item.add_argument("--project")
    ado_item.add_argument("--output", choices=["json", "table", "yaml"], default="json")
    ado_item.set_defaults(func=lambda args: setattr(args, "ado_live_command", "work-item") or cmd_ado_live(args))
    ado_runs = ado_sub.add_parser("pipeline-runs", help="List live ADO pipeline runs through Azure CLI")
    ado_runs.add_argument("--pipeline-id", type=int)
    ado_runs.add_argument("--top", type=int, default=5)
    ado_runs.add_argument("--org")
    ado_runs.add_argument("--project")
    ado_runs.add_argument("--output", choices=["json", "table", "yaml"], default="json")
    ado_runs.set_defaults(func=lambda args: setattr(args, "ado_live_command", "pipeline-runs") or cmd_ado_live(args))

    pipeline = sub.add_parser("pipeline", help="Pipeline Doctor workflows")
    pipeline_sub = pipeline.add_subparsers(dest="pipeline_command", required=True)
    p_doc = pipeline_sub.add_parser("doctor", help="Diagnose pipeline YAML and build logs")
    p_doc.add_argument("--pipeline-yaml")
    p_doc.add_argument("--log-file")
    p_doc.add_argument("--log-text")
    p_doc.add_argument("--environment", default="dev")
    p_doc.add_argument("--out")
    p_doc.add_argument("--write-evidence", action="store_true")
    add_format_arg(p_doc)
    p_doc.set_defaults(func=cmd_pipeline_doctor)
    p_pre = pipeline_sub.add_parser("preflight", help="Preflight pipeline YAML")
    p_pre.add_argument("--pipeline-yaml", required=True)
    add_format_arg(p_pre)
    p_pre.set_defaults(func=cmd_pipeline_preflight)
    p_ev = pipeline_sub.add_parser("evidence", help="Create release evidence template")
    p_ev.add_argument("--claim", required=True)
    p_ev.add_argument("--environment", default="dev")
    p_ev.add_argument("--build-id")
    p_ev.add_argument("--pipeline-id")
    p_ev.add_argument("--out")
    add_format_arg(p_ev)
    p_ev.set_defaults(func=cmd_pipeline_evidence)

    databricks = sub.add_parser("databricks", help="Databricks SQL, bundle, and runtime workflows")
    databricks_sub = databricks.add_subparsers(dest="databricks_command", required=True)
    db_bundle = databricks_sub.add_parser("bundle-doctor", help="Preflight databricks.yml and optional ADO YAML")
    db_bundle.add_argument("--bundle-yaml", required=True)
    db_bundle.add_argument("--pipeline-yaml")
    db_bundle.add_argument("--environment", default="dev")
    add_format_arg(db_bundle)
    db_bundle.set_defaults(func=cmd_databricks_bundle_doctor)
    db_runtime = databricks_sub.add_parser("runtime-advisor", help="Create runtime upgrade risk checks")
    db_runtime.add_argument("--current-runtime", required=True)
    db_runtime.add_argument("--target-runtime", required=True)
    db_runtime.add_argument("--environment", default="dev")
    db_runtime.add_argument("--uses-udfs", action="store_true")
    db_runtime.add_argument("--uses-jars", action="store_true")
    db_runtime.add_argument("--uses-streaming", action="store_true")
    db_runtime.add_argument("--uses-delta-writes", action="store_true")
    db_runtime.add_argument("--uses-ml-serving", action="store_true")
    add_format_arg(db_runtime)
    db_runtime.set_defaults(func=cmd_databricks_runtime_advisor)
    db_sql = databricks_sub.add_parser("sql", help="Execute guarded live Databricks SQL")
    db_sql_sub = db_sql.add_subparsers(dest="databricks_sql_command", required=True)
    db_sql_exec = db_sql_sub.add_parser("execute", help="Execute guarded SQL through Databricks SQL Statement API")
    db_sql_exec.add_argument("--sql", required=True)
    db_sql_exec.add_argument("--environment", default="dev")
    db_sql_exec.add_argument("--warehouse-id")
    db_sql_exec.add_argument("--host")
    db_sql_exec.add_argument("--profile")
    db_sql_exec.add_argument("--timeout", type=int, default=120)
    db_sql_exec.add_argument("--limit", type=int, default=100)
    db_sql_exec.add_argument("--result-format", choices=["table", "json", "csv"], default="table")
    db_sql_exec.add_argument("--dry-run-only", action="store_true")
    db_sql_exec.add_argument("--allow-write", action="store_true")
    db_sql_exec.add_argument("--confirm-write", action="store_true")
    db_sql_exec.add_argument("--row-count-checked", action="store_true")
    db_sql_exec.add_argument("--allow-unqualified-names", action="store_true")
    db_sql_exec.set_defaults(func=cmd_databricks_sql_execute)
    db_wh = db_sql_sub.add_parser("warehouses", help="List live Databricks SQL warehouses")
    db_wh.add_argument("--host")
    db_wh.add_argument("--profile")
    db_wh.add_argument("--result-format", choices=["table", "json"], default="table")
    db_wh.set_defaults(func=cmd_databricks_warehouses)

    quality = sub.add_parser("quality", help="Quality evidence workflows")
    quality_sub = quality.add_subparsers(dest="quality_command", required=True)
    q_rec = quality_sub.add_parser("reconcile", help="Compare source and target row counts")
    q_rec.add_argument("--source-count", required=True)
    q_rec.add_argument("--target-count", required=True)
    q_rec.add_argument("--tolerance", default="0")
    add_format_arg(q_rec)
    q_rec.set_defaults(func=cmd_quality_reconcile)
    q_ready = quality_sub.add_parser("readiness", help="Create release/readiness checklist")
    q_ready.add_argument("--claim", required=True)
    q_ready.add_argument("--environment", default="dev")
    add_format_arg(q_ready)
    q_ready.set_defaults(func=lambda args: setattr(args, "workbench_command", "quality-readiness") or cmd_workbench_proxy(args))

    mssql = sub.add_parser("mssql", help="MSSQL assessment workflows")
    mssql_sub = mssql.add_subparsers(dest="mssql_command", required=True)
    mssql_assess = mssql_sub.add_parser("assess", help="Assess MSSQL inventory metadata")
    mssql_assess.add_argument("--metadata-file", required=True)
    add_format_arg(mssql_assess)
    mssql_assess.set_defaults(func=lambda args: setattr(args, "workbench_command", "mssql-assess") or cmd_workbench_proxy(args))
    mssql_query = mssql_sub.add_parser("query", help="Execute guarded live MSSQL read-only query through sqlcmd")
    mssql_query.add_argument("--sql", required=True)
    mssql_query.add_argument("--server")
    mssql_query.add_argument("--database")
    mssql_query.add_argument("--auth-mode", choices=["integrated", "entra", "sql-password"], default="integrated")
    mssql_query.add_argument("--user")
    mssql_query.add_argument("--password-env", default="MSSQL_PASSWORD")
    mssql_query.add_argument("--result-format", choices=["table", "csv"], default="table")
    mssql_query.add_argument("--timeout", type=int, default=60)
    mssql_query.add_argument("--allow-dangerous", action="store_true")
    mssql_query.add_argument("--allow-sql-password", action="store_true")
    mssql_query.set_defaults(func=cmd_mssql_query)

    migration = sub.add_parser("migration", help="Migration evidence workflows")
    migration_sub = migration.add_subparsers(dest="migration_command", required=True)
    migration_plan = migration_sub.add_parser("plan", help="Create migration evidence plan")
    migration_plan.add_argument("--objects-file", required=True)
    migration_plan.add_argument("--source", required=True)
    migration_plan.add_argument("--target", required=True)
    add_format_arg(migration_plan)
    migration_plan.set_defaults(func=lambda args: setattr(args, "workbench_command", "migration-plan") or cmd_workbench_proxy(args))

    security = sub.add_parser("security", help="Client security review workflows")
    security_sub = security.add_subparsers(dest="security_command", required=True)
    security_checklist = security_sub.add_parser("checklist", help="Create security review checklist")
    security_checklist.add_argument("--scope", default="client-review")
    add_format_arg(security_checklist)
    security_checklist.set_defaults(func=lambda args: setattr(args, "workbench_command", "security-checklist") or cmd_workbench_proxy(args))

    release = sub.add_parser("release", help="Release/package workflows")
    release_sub = release.add_subparsers(dest="release_command", required=True)
    r_verify = release_sub.add_parser("verify", help="Verify release manifest")
    r_verify.add_argument("--root", default=str(ROOT))
    add_format_arg(r_verify)
    r_verify.set_defaults(func=cmd_release_verify)

    demo = sub.add_parser("demo", help="Run built-in demos")
    demo_sub = demo.add_subparsers(dest="demo_command", required=True)
    d_pipeline = demo_sub.add_parser("pipeline-doctor", help="Run Pipeline Doctor on bundled bad sample")
    d_pipeline.add_argument("--out")
    add_format_arg(d_pipeline)
    d_pipeline.set_defaults(func=cmd_demo_pipeline_doctor)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
