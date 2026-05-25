#!/usr/bin/env python3
"""Pipeline intelligence for ADO/Databricks data engineering CI/CD."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

try:
    from de_ledger import append_event
except ImportError:
    append_event = None


SECRET_RE = re.compile(r"(?i)(password|token|secret|pat|client_secret)\s*[:=]\s*['\"]?([^'\"\s]+)")

FAILURE_PATTERNS = [
    {
        "id": "missing_variable",
        "severity": "high",
        "patterns": [
            re.compile(r"(?i)variable ['\"]?([A-Za-z0-9_.-]+)['\"]? .*not found"),
            re.compile(r"(?i)could not find a variable named ['\"]?([A-Za-z0-9_.-]+)['\"]?"),
        ],
        "summary": "Pipeline references a missing variable.",
        "fix": "Define the variable in YAML, a variable group, or the pipeline library. If it is secret, use a variable group or vault-backed secret.",
    },
    {
        "id": "missing_service_connection",
        "severity": "high",
        "patterns": [
            re.compile(r"(?i)service connection .* not found"),
            re.compile(r"(?i)endpoint .* does not exist"),
            re.compile(r"(?i)could not find.* service connection"),
        ],
        "summary": "A service connection is missing or not authorized.",
        "fix": "Verify the service connection name, project permission, and pipeline authorization. Do not replace it with inline credentials.",
    },
    {
        "id": "databricks_cli_missing",
        "severity": "medium",
        "patterns": [
            re.compile(r"(?i)databricks: command not found"),
            re.compile(r"(?i)'databricks' is not recognized"),
            re.compile(r"(?i)No such file or directory.*databricks"),
        ],
        "summary": "Databricks CLI is unavailable on the build agent.",
        "fix": "Install Databricks CLI in the job, use a pinned tool cache step, or switch to a build image that includes it.",
    },
    {
        "id": "databricks_auth",
        "severity": "high",
        "patterns": [
            re.compile(r"(?i)databricks.*unauthorized"),
            re.compile(r"(?i)invalid.*databricks.*token"),
            re.compile(r"(?i)cannot configure default credentials"),
        ],
        "summary": "Databricks authentication failed.",
        "fix": "Prefer workload identity federation, service principal, Azure CLI/profile auth, or a scoped secret variable. Avoid hardcoded PATs.",
    },
    {
        "id": "bundle_validate_missing",
        "severity": "medium",
        "patterns": [
            re.compile(r"(?i)bundle deploy"),
        ],
        "summary": "Databricks bundle deployment was detected.",
        "fix": "Ensure `databricks bundle validate` runs before deploy and that production deploy requires approval.",
    },
    {
        "id": "yaml_syntax",
        "severity": "high",
        "patterns": [
            re.compile(r"(?i)yaml.*(scanner|parser|syntax|mapping)"),
            re.compile(r"(?i)bad indentation"),
            re.compile(r"(?i)mapping values are not allowed"),
        ],
        "summary": "Pipeline YAML syntax appears invalid.",
        "fix": "Validate indentation, quoting, multiline scripts, and template parameter syntax.",
    },
    {
        "id": "tests_failed",
        "severity": "high",
        "patterns": [
            re.compile(r"(?i)test[s]? failed"),
            re.compile(r"(?i)pytest.*failed"),
            re.compile(r"(?i)##\[error\].*failed"),
        ],
        "summary": "A test step failed.",
        "fix": "Inspect the failing test output, reproduce locally, and attach the fixed test evidence before rerunning.",
    },
]


def read_text(path: Optional[str]) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def redact(text: str) -> str:
    return SECRET_RE.sub(lambda m: f"{m.group(1)}=<redacted>", text or "")


def preflight_yaml(path: Path) -> Dict:
    issues: List[Dict] = []
    warnings: List[Dict] = []
    facts: Dict[str, object] = {"exists": path.exists(), "path": str(path)}
    if not path.exists():
        issues.append({"id": "missing_yaml", "severity": "high", "message": f"Pipeline YAML not found: {path}"})
        return {"status": "blocked", "facts": facts, "issues": issues, "warnings": warnings}

    text = path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    facts.update({
        "line_count": len(text.splitlines()),
        "has_databricks_bundle_validate": "databricks bundle validate" in lowered,
        "has_databricks_bundle_deploy": "databricks bundle deploy" in lowered,
        "has_variable_group": bool(re.search(r"(?im)^\s*-\s*group\s*:", text)),
        "has_trigger": "trigger:" in lowered,
        "has_pr": "pr:" in lowered,
        "mentions_prod": bool(re.search(r"(?i)\bprod(uction)?\b", text)),
    })
    if SECRET_RE.search(text):
        issues.append({"id": "inline_secret", "severity": "critical", "message": "Possible inline secret found in pipeline YAML."})
    if facts["has_databricks_bundle_deploy"] and not facts["has_databricks_bundle_validate"]:
        issues.append({"id": "deploy_without_validate", "severity": "high", "message": "Databricks bundle deploy appears without bundle validate."})
    if facts["mentions_prod"] and "approval" not in lowered and "environment:" not in lowered:
        warnings.append({"id": "prod_without_approval_signal", "severity": "medium", "message": "Production-like target appears without an obvious approval/environment gate."})
    if "variables:" in lowered and not facts["has_variable_group"]:
        warnings.append({"id": "variables_without_group", "severity": "low", "message": "Variables are present but no variable group reference was detected."})
    if re.search(r"(?im)^\s*script:\s*.*(delete\s+from|drop\s+table|truncate\s+table)", text):
        issues.append({"id": "dangerous_inline_sql", "severity": "critical", "message": "Dangerous inline SQL detected in a script step."})
    status = "blocked" if issues else "warn" if warnings else "ok"
    return {"status": status, "facts": facts, "issues": issues, "warnings": warnings}


def diagnose_logs(log_text: str) -> Dict:
    clean = redact(log_text)
    matches = []
    for item in FAILURE_PATTERNS:
        evidence = []
        for pattern in item["patterns"]:
            for match in pattern.finditer(clean):
                line = line_for_offset(clean, match.start())
                evidence.append(line)
        if evidence:
            matches.append({
                "id": item["id"],
                "severity": item["severity"],
                "summary": item["summary"],
                "fix": item["fix"],
                "evidence": sorted(set(evidence))[:5],
            })
    if not matches and clean.strip():
        matches.append({
            "id": "unclassified_failure",
            "severity": "medium",
            "summary": "Pipeline log contains no known failure pattern.",
            "fix": "Inspect the first error block, identify the failing task, and add a new failure pattern if this recurs.",
            "evidence": first_error_lines(clean),
        })
    return {"status": "diagnosed" if matches else "no-log-evidence", "matches": matches}


def line_for_offset(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end == -1:
        end = len(text)
    return text[start:end].strip()[:500]


def first_error_lines(text: str) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if re.search(r"(?i)(##\[error\]|error|failed|exception)", line)]
    return lines[:5]


def build_fix_plan(preflight: Dict, diagnosis: Dict) -> Dict:
    actions = []
    for issue in preflight.get("issues", []):
        actions.append({
            "source": "yaml-preflight",
            "id": issue["id"],
            "severity": issue["severity"],
            "action": suggested_action(issue["id"]),
        })
    for warning in preflight.get("warnings", []):
        actions.append({
            "source": "yaml-preflight",
            "id": warning["id"],
            "severity": warning["severity"],
            "action": suggested_action(warning["id"]),
        })
    for match in diagnosis.get("matches", []):
        actions.append({
            "source": "log-diagnosis",
            "id": match["id"],
            "severity": match["severity"],
            "action": match["fix"],
        })
    return {
        "status": "needs-fix" if actions else "no-action",
        "actions": actions,
        "requires_approval_before_rerun": any(action["severity"] in {"critical", "high"} for action in actions),
        "ado_next_commands": [
            "ado-pipelines build-logs --id <BUILD_ID> --task-id <LOG_ID>",
            "ado-pipelines build-changes --id <BUILD_ID>",
            "ado-pipelines build-status --id <BUILD_ID>",
        ],
    }


def suggested_action(issue_id: str) -> str:
    suggestions = {
        "inline_secret": "Move the value to a variable group or vault-backed secret and rotate the exposed credential.",
        "deploy_without_validate": "Add `databricks bundle validate` before any `databricks bundle deploy` step.",
        "prod_without_approval_signal": "Add an environment approval/check or manual validation gate before production deploy.",
        "variables_without_group": "Use a variable group for shared non-secret defaults and secret references.",
        "dangerous_inline_sql": "Remove inline destructive SQL; route writes through approved migration scripts and quality gates.",
        "missing_yaml": "Locate the pipeline YAML through `ado-pipelines pipeline-get` or repository search.",
    }
    return suggestions.get(issue_id, "Review and address before rerun.")


def cmd_preflight(args: argparse.Namespace) -> int:
    result = preflight_yaml(Path(args.pipeline_yaml))
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "blocked" else 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    log_text = read_text(args.log_file) or args.log_text or ""
    preflight = preflight_yaml(Path(args.pipeline_yaml)) if args.pipeline_yaml else {"status": "not-run", "issues": [], "warnings": []}
    diagnosis = diagnose_logs(log_text)
    fix_plan = build_fix_plan(preflight, diagnosis)
    result = {
        "status": "blocked" if preflight.get("status") == "blocked" or fix_plan["actions"] else "ok",
        "pipeline_yaml": str(args.pipeline_yaml or ""),
        "preflight": preflight,
        "diagnosis": diagnosis,
        "fix_plan": fix_plan,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.ledger and append_event is not None:
        append_event({
            "type": "pipeline_diagnosis",
            "claim": "pipeline diagnosis generated",
            "target": str(args.pipeline_yaml or args.log_file or "log-text"),
            "environment": args.environment,
            "status": result["status"],
            "evidence": result,
        }, Path(args.ledger))
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "blocked" else 0


def cmd_evidence(args: argparse.Namespace) -> int:
    result = {
        "claim": args.claim,
        "build_id": args.build_id or "",
        "pipeline_id": args.pipeline_id or "",
        "environment": args.environment,
        "required_evidence": [
            "pipeline preflight result",
            "build status",
            "build log diagnosis",
            "quality gate report",
            "security/config audit",
            "release approval for production-like target",
        ],
        "ado_commands": [
            "ado-pipelines build-status --id <BUILD_ID>",
            "ado-pipelines build-logs --id <BUILD_ID>",
            "ado-pipelines build-changes --id <BUILD_ID>",
        ],
        "risks": [],
    }
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Data-engineering ADO pipeline intelligence")
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight", help="Preflight pipeline YAML")
    preflight.add_argument("--pipeline-yaml", required=True)
    preflight.set_defaults(func=cmd_preflight)
    diagnose = sub.add_parser("diagnose", help="Diagnose pipeline YAML and/or build logs")
    diagnose.add_argument("--pipeline-yaml")
    diagnose.add_argument("--log-file")
    diagnose.add_argument("--log-text")
    diagnose.add_argument("--out")
    diagnose.add_argument("--ledger")
    diagnose.add_argument("--environment", default="dev")
    diagnose.set_defaults(func=cmd_diagnose)
    evidence = sub.add_parser("evidence", help="Create pipeline release evidence template")
    evidence.add_argument("--claim", required=True)
    evidence.add_argument("--build-id")
    evidence.add_argument("--pipeline-id")
    evidence.add_argument("--environment", default="dev")
    evidence.add_argument("--out")
    evidence.set_defaults(func=cmd_evidence)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
