#!/usr/bin/env python3
"""Databricks consulting helpers for bundles and runtime upgrades."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional


SECRET_RE = re.compile(r"(?i)(password|token|secret|pat|client_secret)\s*[:=]\s*['\"]?([^'\"\s]+)")
RUNTIME_RE = re.compile(r"(?im)\bspark_version\s*:\s*['\"]?([A-Za-z0-9_.-]+)")


def read_text(path: Optional[str]) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def issue(identifier: str, severity: str, message: str) -> Dict[str, str]:
    return {"id": identifier, "severity": severity, "message": message}


def has_section(text: str, name: str) -> bool:
    return bool(re.search(rf"(?im)^\s*{re.escape(name)}\s*:", text or ""))


def has_target(text: str, target: str) -> bool:
    return bool(re.search(rf"(?im)^\s{{2,}}{re.escape(target)}\s*:", text or ""))


def target_block(text: str, target: str) -> str:
    match = re.search(rf"(?ims)^(\s*){re.escape(target)}\s*:\s*\n(.*?)(?=^\1\S|\Z)", text or "")
    return match.group(2) if match else ""


def runtime_values(text: str) -> List[str]:
    return sorted(set(match.group(1) for match in RUNTIME_RE.finditer(text or "")))


def bundle_doctor(bundle_yaml: str, pipeline_yaml: str, environment: str) -> Dict:
    issues: List[Dict] = []
    warnings: List[Dict] = []
    facts: Dict[str, object] = {}
    bundle_path = Path(bundle_yaml)
    facts["bundle_yaml"] = str(bundle_path)
    facts["bundle_exists"] = bundle_path.exists()
    if not bundle_path.exists():
        return {
            "status": "blocked",
            "facts": facts,
            "issues": [issue("missing_bundle_yaml", "high", f"Databricks bundle file not found: {bundle_path}")],
            "warnings": warnings,
            "fix_plan": ["Locate databricks.yml or run this check from the bundle root."],
        }

    text = read_text(str(bundle_path))
    lowered = text.lower()
    prod_block = target_block(text, "prod") or target_block(text, "production")
    runtimes = runtime_values(text)
    facts.update({
        "has_bundle_section": has_section(text, "bundle"),
        "has_targets_section": has_section(text, "targets"),
        "has_resources_section": has_section(text, "resources"),
        "has_jobs_section": has_section(text, "jobs"),
        "has_prod_target": has_target(text, "prod") or has_target(text, "production"),
        "prod_target_uses_production_mode": "mode: production" in prod_block.lower(),
        "has_workspace_host": bool(re.search(r"(?im)^\s*host\s*:\s*https?://", text)),
        "has_workspace_root_path": "root_path:" in lowered,
        "runtime_values": runtimes,
    })

    if SECRET_RE.search(text):
        issues.append(issue("inline_secret", "critical", "Possible inline secret found in databricks.yml."))
    if not facts["has_bundle_section"]:
        issues.append(issue("missing_bundle_section", "high", "Bundle YAML is missing a top-level `bundle:` section."))
    if not facts["has_targets_section"]:
        issues.append(issue("missing_targets", "high", "Bundle YAML is missing deployment `targets:`."))
    if not facts["has_resources_section"]:
        warnings.append(issue("missing_resources", "medium", "Bundle YAML has no top-level `resources:` section."))
    if facts["has_prod_target"] and not facts["prod_target_uses_production_mode"]:
        warnings.append(issue("prod_without_production_mode", "medium", "Production target does not clearly use `mode: production`."))
    if facts["has_workspace_host"]:
        warnings.append(issue("hardcoded_workspace_host", "medium", "Workspace host is hardcoded; confirm this is expected for client distribution."))
    if any(value.startswith("18") for value in runtimes) and environment.lower() in {"prod", "production"}:
        warnings.append(issue("new_major_runtime_prod", "medium", "New major runtime detected for production; attach runtime upgrade evidence before deploy."))

    if pipeline_yaml:
        pipeline_path = Path(pipeline_yaml)
        facts["pipeline_yaml"] = str(pipeline_path)
        facts["pipeline_exists"] = pipeline_path.exists()
        pipeline_text = read_text(str(pipeline_path)) if pipeline_path.exists() else ""
        pipeline_lowered = pipeline_text.lower()
        facts["pipeline_has_bundle_validate"] = "databricks bundle validate" in pipeline_lowered
        facts["pipeline_has_bundle_deploy"] = "databricks bundle deploy" in pipeline_lowered
        if not pipeline_path.exists():
            warnings.append(issue("missing_pipeline_yaml", "medium", f"Azure Pipeline YAML not found: {pipeline_path}"))
        elif facts["pipeline_has_bundle_deploy"] and not facts["pipeline_has_bundle_validate"]:
            issues.append(issue("deploy_without_validate", "high", "Azure Pipeline deploys a Databricks bundle without `databricks bundle validate`."))

    return {
        "status": "blocked" if issues else "warn" if warnings else "ok",
        "facts": facts,
        "issues": issues,
        "warnings": warnings,
        "fix_plan": fix_plan(issues, warnings),
        "evidence_commands": [
            "databricks bundle validate -t <target>",
            "databricks bundle deploy -t <target> --dry-run",
            "de pipeline doctor --pipeline-yaml azure-pipelines.yml --log-file build.log --write-evidence",
            "de quality reconcile --source-count <SOURCE> --target-count <TARGET>",
        ],
    }


def fix_plan(issues: List[Dict], warnings: List[Dict]) -> List[str]:
    suggestions = {
        "inline_secret": "Move secrets to an approved secret provider, variable group, or Databricks secret scope; rotate exposed values.",
        "missing_bundle_section": "Add a top-level `bundle:` section with a stable bundle name.",
        "missing_targets": "Add explicit dev/test/prod targets and avoid ambiguous default deploys.",
        "missing_resources": "Declare jobs, pipelines, or other resources under `resources:` so deployment is reviewable.",
        "prod_without_production_mode": "Set production target controls and document approval evidence before deploy.",
        "hardcoded_workspace_host": "Confirm host values are environment-specific and not copied across clients accidentally.",
        "new_major_runtime_prod": "Run Runtime Advisor and attach representative job smoke evidence before production deploy.",
        "deploy_without_validate": "Add `databricks bundle validate` before `databricks bundle deploy` in CI/CD.",
        "missing_pipeline_yaml": "Attach the ADO YAML so bundle validation can be checked with pipeline context.",
    }
    return [suggestions.get(item["id"], "Review before deploy.") for item in [*issues, *warnings]]


def runtime_advisor(args: argparse.Namespace) -> Dict:
    risks: List[Dict] = []
    checks: List[str] = [
        "Run `databricks bundle validate` for each target.",
        "Run a representative sandbox job smoke test on the target runtime.",
        "Capture row-count/schema evidence for Delta writes or migrations.",
        "Document rollback target runtime and deployment rollback steps.",
    ]
    current_major = major_version(args.current_runtime)
    target_major = major_version(args.target_runtime)
    if target_major and current_major and target_major > current_major:
        risks.append(issue("major_runtime_upgrade", "high", "Target runtime is a major-version upgrade."))
    if args.environment.lower() in {"prod", "production"}:
        risks.append(issue("production_upgrade", "high", "Production runtime upgrades require approval and rollback evidence."))
    if args.uses_udfs:
        risks.append(issue("udf_compatibility", "medium", "UDF behavior and dependencies need compatibility smoke tests."))
        checks.append("Run focused tests for Python/Scala SQL UDFs and permissions.")
    if args.uses_jars:
        risks.append(issue("jar_compatibility", "medium", "JAR/Java dependencies may be runtime or JDK sensitive."))
        checks.append("Verify JAR compatibility, init scripts, Maven coordinates, and cluster policies.")
    if args.uses_streaming:
        risks.append(issue("streaming_state", "high", "Structured Streaming state and checkpoint compatibility must be validated."))
        checks.append("Run streaming resume/rollback test using representative checkpoint state.")
    if args.uses_delta_writes:
        risks.append(issue("delta_write_path", "medium", "Delta write behavior must be validated with schema and row-count evidence."))
    if args.uses_ml_serving:
        risks.append(issue("serving_ai_workload", "medium", "AI/model-serving workloads need latency, cost, data-residency, and PII checks."))
        checks.append("Capture serving latency/cost baseline and confirm prompt/trace data handling.")

    return {
        "status": "needs-evidence" if risks else "ok",
        "current_runtime": args.current_runtime,
        "target_runtime": args.target_runtime,
        "environment": args.environment,
        "risks": risks,
        "required_checks": sorted(set(checks)),
        "approval_required": args.environment.lower() in {"prod", "production"} or any(item["severity"] == "high" for item in risks),
        "official_docs_required": True,
    }


def major_version(value: str) -> Optional[int]:
    match = re.search(r"(\d+)", value or "")
    return int(match.group(1)) if match else None


def cmd_bundle_doctor(args: argparse.Namespace) -> int:
    result = bundle_doctor(args.bundle_yaml, args.pipeline_yaml or "", args.environment)
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "blocked" else 0


def cmd_runtime_advisor(args: argparse.Namespace) -> int:
    result = runtime_advisor(args)
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Databricks data-engineering package helpers")
    sub = parser.add_subparsers(dest="command", required=True)
    bundle = sub.add_parser("bundle-doctor", help="Preflight databricks.yml and optional ADO YAML")
    bundle.add_argument("--bundle-yaml", required=True)
    bundle.add_argument("--pipeline-yaml")
    bundle.add_argument("--environment", default="dev")
    bundle.set_defaults(func=cmd_bundle_doctor)

    runtime = sub.add_parser("runtime-advisor", help="Create runtime upgrade risk checks")
    runtime.add_argument("--current-runtime", required=True)
    runtime.add_argument("--target-runtime", required=True)
    runtime.add_argument("--environment", default="dev")
    runtime.add_argument("--uses-udfs", action="store_true")
    runtime.add_argument("--uses-jars", action="store_true")
    runtime.add_argument("--uses-streaming", action="store_true")
    runtime.add_argument("--uses-delta-writes", action="store_true")
    runtime.add_argument("--uses-ml-serving", action="store_true")
    runtime.set_defaults(func=cmd_runtime_advisor)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
