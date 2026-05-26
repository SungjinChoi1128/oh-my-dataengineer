#!/usr/bin/env python3
"""Local QA evidence helpers for data-engineering workflows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


PASS_STATUSES = {"ok", "pass", "passed", "ready", "success", "succeeded"}
BLOCK_STATUSES = {"blocked", "block", "fail", "failed", "error", "dangerous"}
NEUTRAL_STATUSES = {"template", "pending", "preview", "needs-evidence", "needs-review", "warning", "warn"}

GATE_KEYWORDS = {
    "tests": ("test", "pytest", "unit", "compile", "lint", "typecheck", "smoke"),
    "sql_safety": ("sql", "dbsql", "mssql", "classify", "dry-run", "dry_run", "policy-check"),
    "row_schema": ("row", "schema", "reconcile", "count", "migration"),
    "pipeline": ("pipeline", "bundle", "preflight", "doctor", "deploy", "release"),
    "security": ("security", "secret", "auth", "permission", "policy"),
    "rollback": ("rollback", "recovery", "restore", "backout"),
    "approval": ("approval", "approved", "signoff", "sign-off", "change-ticket"),
}


def cmd_evidence_template(args: argparse.Namespace) -> int:
    template = {
        "claim": args.claim,
        "environment": args.environment,
        "checks": [
            {"name": "unit_or_compile_tests", "status": "pending", "evidence": ""},
            {"name": "sql_classification", "status": "pending", "evidence": ""},
            {"name": "row_count_reconciliation", "status": "pending", "evidence": ""},
            {"name": "schema_diff", "status": "pending", "evidence": ""},
            {"name": "secret_config_scan", "status": "pending", "evidence": ""},
        ],
        "risks": [],
    }
    if args.out:
        Path(args.out).write_text(json.dumps(template, indent=2), encoding="utf-8")
    print(json.dumps(template, indent=2))
    return 0


def cmd_reconcile(args: argparse.Namespace) -> int:
    source = int(args.source_count)
    target = int(args.target_count)
    diff = target - source
    pct = 0.0 if source == 0 else round((diff / source) * 100, 6)
    passed = abs(diff) <= int(args.tolerance)
    result = {
        "status": "pass" if passed else "fail",
        "source_count": source,
        "target_count": target,
        "difference": diff,
        "difference_percent": pct,
        "tolerance": int(args.tolerance),
    }
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


def cmd_schema_diff(args: argparse.Namespace) -> int:
    source = json.loads(Path(args.source_schema).read_text(encoding="utf-8"))
    target = json.loads(Path(args.target_schema).read_text(encoding="utf-8"))
    source_cols = normalize_schema(source)
    target_cols = normalize_schema(target)
    missing = sorted(set(source_cols) - set(target_cols))
    extra = sorted(set(target_cols) - set(source_cols))
    changed = sorted(name for name in set(source_cols) & set(target_cols) if source_cols[name] != target_cols[name])
    result = {
        "status": "pass" if not missing and not changed else "fail",
        "missing_in_target": missing,
        "extra_in_target": extra,
        "type_changes": [{"column": name, "source": source_cols[name], "target": target_cols[name]} for name in changed],
    }
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


def cmd_verdict(args: argparse.Namespace) -> int:
    result = build_verdict(args)
    text = render_verdict_text(result)
    markdown = render_verdict_markdown(result)
    if args.out:
        artifacts = write_verdict_artifacts(result, args.out)
        result["artifacts"] = artifacts
        text = render_verdict_text(result)
        markdown = render_verdict_markdown(result)
    if args.format == "json":
        print(json.dumps(result, indent=2))
    elif args.format == "markdown":
        print(markdown)
    else:
        print(text)
    if args.strict and result["verdict"] != "ready":
        return 1
    return 0


def build_verdict(args: argparse.Namespace) -> dict:
    repo_root = Path(args.repo_root).resolve()
    context = load_json_safe(repo_root / ".de-opencode" / "repo-context.json")
    todo = load_json_safe(repo_root / ".de-opencode" / "next-actions.json")
    signals = context.get("signals", {}) if isinstance(context, dict) else {}
    active_signals = {key: value for key, value in signals.items() if value}
    repo_initialized = bool(context)

    evidence = collect_evidence(args.evidence_file, args.evidence_dir)
    supplied = {
        "tests": bool(args.tests_evidence),
        "sql_safety": bool(args.sql_evidence),
        "row_schema": bool(args.row_schema_evidence),
        "pipeline": bool(args.pipeline_evidence),
        "security": bool(args.security_evidence),
        "rollback": bool(args.rollback_note),
        "approval": bool(args.approval_note),
    }
    gate_hits = infer_gate_hits(evidence, supplied)
    blockers = evidence_blockers(evidence)
    missing = missing_gates(
        claim=args.claim,
        environment=args.environment,
        repo_initialized=repo_initialized,
        signals=signals,
        gate_hits=gate_hits,
        force_data_changed=args.data_changed,
        force_pipeline_changed=args.pipeline_changed,
        force_security=args.security_sensitive,
    )
    todo_actions = unresolved_todo_actions(todo)
    next_actions = next_steps(missing, blockers, todo_actions)
    verdict = "blocked" if blockers else "needs-evidence" if missing else "ready"
    return {
        "status": verdict,
        "verdict": verdict,
        "claim": args.claim,
        "environment": args.environment,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_context": {
            "root": str(repo_root),
            "initialized": repo_initialized,
            "repo_types": context.get("repo_types", []) if isinstance(context, dict) else [],
            "signals": active_signals,
        },
        "todo": {
            "count": len(todo_actions),
            "high_priority": [item for item in todo_actions if item.get("priority") == "high"],
        },
        "evidence_found": evidence,
        "gates": gate_hits,
        "missing": missing,
        "blockers": blockers,
        "next_actions": next_actions,
    }


def load_json_safe(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def collect_evidence(files: Optional[List[str]], evidence_dir: Optional[str]) -> list[dict]:
    paths: list[Path] = []
    for item in files or []:
        paths.append(Path(item))
    if evidence_dir:
        root = Path(evidence_dir)
        if root.exists():
            paths.extend(sorted(root.glob("*.json")))
    evidence = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        data = load_json_safe(path)
        if not data:
            evidence.append({
                "path": str(path),
                "label": path.name,
                "status": "missing-or-unreadable",
                "gates": [],
            })
            continue
        label = evidence_label(path, data)
        status = normalize_status(data)
        evidence.append({
            "path": str(path),
            "label": label,
            "status": status,
            "gates": sorted(infer_gates_from_text(" ".join([path.name, label, json.dumps(data, sort_keys=True)]))),
        })
    return evidence


def evidence_label(path: Path, data: dict) -> str:
    for key in ("claim", "check", "name", "operation", "action", "summary"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return path.stem


def normalize_status(data: dict) -> str:
    for key in ("verdict", "status", "category"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return "unknown"


def infer_gate_hits(evidence: list[dict], supplied: Dict[str, bool]) -> dict:
    gates = {key: {"satisfied": bool(value), "sources": ["flag"] if value else []} for key, value in supplied.items()}
    for item in evidence:
        status = str(item.get("status", "")).lower()
        if status in BLOCK_STATUSES:
            continue
        if status and status not in PASS_STATUSES | NEUTRAL_STATUSES | {"unknown"}:
            continue
        for gate in item.get("gates", []):
            if gate not in gates:
                continue
            if status in PASS_STATUSES or status in {"unknown", "preview"}:
                gates[gate]["satisfied"] = True
                gates[gate]["sources"].append(item.get("path", "evidence"))
    return gates


def infer_gates_from_text(text: str) -> set[str]:
    lowered = text.lower()
    hits = set()
    for gate, words in GATE_KEYWORDS.items():
        if any(word in lowered for word in words):
            hits.add(gate)
    return hits


def evidence_blockers(evidence: list[dict]) -> list[str]:
    blockers = []
    for item in evidence:
        status = str(item.get("status", "")).lower()
        if status in BLOCK_STATUSES or status == "missing-or-unreadable":
            blockers.append(f"{item.get('label', 'evidence')} is {status} ({item.get('path')})")
    return blockers


def missing_gates(
    claim: str,
    environment: str,
    repo_initialized: bool,
    signals: dict,
    gate_hits: dict,
    force_data_changed: bool,
    force_pipeline_changed: bool,
    force_security: bool,
) -> list[str]:
    missing = []
    env = environment.lower()
    production = env in {"prod", "production"}
    if not claim.strip():
        missing.append("claim is required")
    if not repo_initialized:
        missing.append("repo context missing; run de repo init first")
    if signals.get("tests") and not gate_hits["tests"]["satisfied"]:
        missing.append("test or compile evidence")
    if (signals.get("sql") or signals.get("mssql_or_tsql")) and not gate_hits["sql_safety"]["satisfied"]:
        missing.append("SQL classify/dry-run or MSSQL policy evidence")
    needs_row_schema = force_data_changed or production and (signals.get("sql") or signals.get("mssql_or_tsql"))
    if needs_row_schema and not gate_hits["row_schema"]["satisfied"]:
        missing.append("row-count or schema evidence for changed data")
    needs_pipeline = force_pipeline_changed or signals.get("azure_pipelines") or signals.get("databricks_bundle")
    if needs_pipeline and not gate_hits["pipeline"]["satisfied"]:
        missing.append("pipeline or Databricks bundle preflight evidence")
    needs_security = force_security or production
    if needs_security and not gate_hits["security"]["satisfied"]:
        missing.append("security/auth evidence")
    if production and not gate_hits["rollback"]["satisfied"]:
        missing.append("rollback or recovery note")
    if production and not gate_hits["approval"]["satisfied"]:
        missing.append("production approval or change-ticket note")
    return missing


def unresolved_todo_actions(todo: dict) -> list[dict]:
    actions = todo.get("actions", []) if isinstance(todo, dict) else []
    result = []
    for item in actions:
        if not isinstance(item, dict):
            continue
        result.append({
            "id": item.get("id", ""),
            "priority": item.get("priority", ""),
            "action": item.get("action", ""),
            "command": item.get("command", ""),
        })
    return result


def next_steps(missing: list[str], blockers: list[str], todo_actions: list[dict]) -> list[str]:
    if blockers:
        return ["Fix or replace blocked/failed evidence, then rerun de done."]
    if missing:
        steps = [f"Attach evidence for: {item}." for item in missing[:6]]
        for item in todo_actions[:3]:
            command = item.get("command") or item.get("action")
            if command:
                steps.append(command)
        return steps
    return ["Evidence looks ready for final handoff. Include the verdict output in the PR/client note."]


def write_verdict_artifacts(result: dict, out: str) -> dict:
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "done-verdict.json"
    md_path = target / "done-verdict.md"
    artifacts = {"json": str(json_path), "markdown": str(md_path)}
    payload = dict(result)
    payload["artifacts"] = artifacts
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_verdict_markdown(payload) + "\n", encoding="utf-8")
    return artifacts


def render_verdict_text(result: dict) -> str:
    verdict = str(result.get("verdict", "unknown")).upper()
    lines = [
        f"Done Verdict: {verdict}",
        f"- claim: {result.get('claim')}",
        f"- environment: {result.get('environment')}",
        f"- repo context: {result.get('repo_context', {}).get('initialized')}",
    ]
    evidence = result.get("evidence_found", [])
    if evidence:
        lines += ["", "Evidence found:"]
        for item in evidence:
            gates = ", ".join(item.get("gates", [])) or "general"
            lines.append(f"- {item.get('label')} [{item.get('status')}] ({gates})")
    if result.get("missing"):
        lines += ["", "Missing evidence:"]
        lines += [f"- {item}" for item in result["missing"]]
    if result.get("blockers"):
        lines += ["", "Blockers:"]
        lines += [f"- {item}" for item in result["blockers"]]
    if result.get("next_actions"):
        lines += ["", "Next:"]
        lines += [f"- {item}" for item in result["next_actions"][:8]]
    if result.get("artifacts"):
        lines += ["", "Artifacts:"]
        lines += [f"- {kind}: {path}" for kind, path in result["artifacts"].items()]
    return "\n".join(lines)


def render_verdict_markdown(result: dict) -> str:
    lines = [
        "# Data Engineering Done Verdict",
        "",
        f"**Verdict:** {str(result.get('verdict', 'unknown')).upper()}",
        f"**Claim:** {result.get('claim')}",
        f"**Environment:** {result.get('environment')}",
        "",
        "## Repo Context",
        "",
        f"- Initialized: `{result.get('repo_context', {}).get('initialized')}`",
        "- Types: " + ", ".join(result.get("repo_context", {}).get("repo_types", []) or ["unknown"]),
        "- Signals: " + ", ".join(sorted(result.get("repo_context", {}).get("signals", {}))) if result.get("repo_context", {}).get("signals") else "- Signals: none",
        "",
    ]
    for title, key in [("Evidence Found", "evidence_found"), ("Missing Evidence", "missing"), ("Blockers", "blockers"), ("Next Actions", "next_actions")]:
        items = result.get(key, [])
        if not items:
            continue
        lines += [f"## {title}", ""]
        for item in items:
            if isinstance(item, dict):
                lines.append(f"- `{item.get('status')}` {item.get('label')} ({item.get('path')})")
            else:
                lines.append(f"- {item}")
        lines.append("")
    if result.get("artifacts"):
        lines += ["## Artifacts", ""]
        lines += [f"- **{kind}:** `{path}`" for kind, path in result["artifacts"].items()]
        lines.append("")
    return "\n".join(lines).rstrip()


def normalize_schema(value: object) -> dict:
    if isinstance(value, dict):
        raw_items = value.get("columns", value)
    else:
        raw_items = value
    result = {}
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("column") or "").lower()
                dtype = str(item.get("type") or item.get("data_type") or item.get("dtype") or "").lower()
                if name:
                    result[name] = dtype
            elif isinstance(item, (list, tuple)) and item:
                result[str(item[0]).lower()] = str(item[1] if len(item) > 1 else "").lower()
    elif isinstance(raw_items, dict):
        result = {str(k).lower(): str(v).lower() for k, v in raw_items.items()}
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Data-engineering QA evidence helper")
    sub = parser.add_subparsers(dest="command", required=True)
    evidence = sub.add_parser("evidence-template", help="Create a sanitized QA evidence template")
    evidence.add_argument("--claim", required=True)
    evidence.add_argument("--environment", default="dev")
    evidence.add_argument("--out")
    evidence.set_defaults(func=cmd_evidence_template)
    reconcile = sub.add_parser("reconcile", help="Compare source and target row counts")
    reconcile.add_argument("--source-count", required=True)
    reconcile.add_argument("--target-count", required=True)
    reconcile.add_argument("--tolerance", default="0")
    reconcile.set_defaults(func=cmd_reconcile)
    schema = sub.add_parser("schema-diff", help="Compare source and target schema JSON files")
    schema.add_argument("--source-schema", required=True)
    schema.add_argument("--target-schema", required=True)
    schema.set_defaults(func=cmd_schema_diff)
    verdict = sub.add_parser("verdict", help="Aggregate repo and evidence files into a done verdict")
    verdict.add_argument("--claim", required=True)
    verdict.add_argument("--environment", default="dev")
    verdict.add_argument("--repo-root", default=".")
    verdict.add_argument("--evidence-file", action="append")
    verdict.add_argument("--evidence-dir")
    verdict.add_argument("--tests-evidence", action="store_true")
    verdict.add_argument("--sql-evidence", action="store_true")
    verdict.add_argument("--row-schema-evidence", action="store_true")
    verdict.add_argument("--pipeline-evidence", action="store_true")
    verdict.add_argument("--security-evidence", action="store_true")
    verdict.add_argument("--rollback-note", action="store_true")
    verdict.add_argument("--approval-note", action="store_true")
    verdict.add_argument("--data-changed", action="store_true")
    verdict.add_argument("--pipeline-changed", action="store_true")
    verdict.add_argument("--security-sensitive", action="store_true")
    verdict.add_argument("--out")
    verdict.add_argument("--strict", action="store_true")
    verdict.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    verdict.set_defaults(func=cmd_verdict)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
