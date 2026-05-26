#!/usr/bin/env python3
"""Azure DevOps facade for operation classification, preflight, and guarded live reads."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

try:
    from de_pipeline import preflight_yaml
except ImportError:
    preflight_yaml = None


READ_ONLY = {"list", "get", "show", "inspect", "status", "logs", "changes", "search", "preflight"}
WRITE = {"create", "update", "delete", "queue", "trigger", "run", "download", "upload", "comment", "approve"}


def classify_operation(operation: str) -> dict:
    lowered = operation.lower()
    words = set(re.findall(r"[a-z]+", lowered))
    if words & WRITE:
        category = "write"
    elif words & READ_ONLY:
        category = "readonly"
    else:
        category = "unknown"
    return {
        "operation": operation,
        "category": category,
        "requires_approval": category != "readonly",
        "requires_least_privilege_review": category in {"write", "unknown"},
    }


def cmd_classify(args: argparse.Namespace) -> int:
    result = classify_operation(args.operation)
    print(json.dumps(result, indent=2))
    return 0 if result["category"] != "unknown" else 2


def cmd_preflight(args: argparse.Namespace) -> int:
    if preflight_yaml is None:
        print(json.dumps({"status": "blocked", "issues": ["de_pipeline preflight module is unavailable"], "warnings": []}, indent=2))
        return 1
    result = preflight_yaml(Path(args.pipeline_yaml))
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "blocked" else 0


def cmd_query(args: argparse.Namespace) -> int:
    command = with_context([az_path(), "boards", "query", "--wiql", args.wiql, "--output", args.output], args)
    return run_live(command)


def cmd_work_item(args: argparse.Namespace) -> int:
    command = with_context([az_path(), "boards", "work-item", "show", "--id", str(args.id), "--output", args.output], args)
    return run_live(command)


def cmd_pipeline_runs(args: argparse.Namespace) -> int:
    command = [az_path(), "pipelines", "runs", "list", "--top", str(args.top), "--output", args.output]
    if args.pipeline_id:
        command += ["--pipeline-ids", str(args.pipeline_id)]
    command = with_context(command, args)
    return run_live(command)


def az_path() -> str:
    az = shutil.which("az")
    if not az:
        raise SystemExit("Azure CLI `az` is required for live ADO commands.")
    return az


def with_context(command: List[str], args: argparse.Namespace) -> List[str]:
    if args.org:
        command += ["--org", args.org]
    if args.project:
        command += ["--project", args.project]
    return command


def run_live(command: List[str]) -> int:
    result = subprocess.run(command, text=True, capture_output=True, stdin=subprocess.DEVNULL)
    if result.stdout:
        print(redact(result.stdout), end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(redact(result.stderr), end="" if result.stderr.endswith("\n") else "\n")
    return result.returncode


def redact(text: str) -> str:
    return re.sub(r"(?i)(pat|token|authorization|password|secret)([=: ]+)[^\s,;}]+", r"\1\2<redacted>", text or "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Azure DevOps safe operation facade")
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify", help="Classify an ADO operation")
    classify.add_argument("--operation", required=True)
    classify.set_defaults(func=cmd_classify)
    preflight = sub.add_parser("preflight", help="Preflight an Azure Pipeline YAML file")
    preflight.add_argument("--pipeline-yaml", required=True)
    preflight.set_defaults(func=cmd_preflight)
    query = sub.add_parser("query", help="Run a live read-only ADO WIQL query through Azure CLI")
    query.add_argument("--wiql", required=True)
    query.add_argument("--org")
    query.add_argument("--project")
    query.add_argument("--output", choices=["json", "table", "yaml"], default="json")
    query.set_defaults(func=cmd_query)
    item = sub.add_parser("work-item", help="Show a live ADO work item through Azure CLI")
    item.add_argument("--id", required=True, type=int)
    item.add_argument("--org")
    item.add_argument("--project")
    item.add_argument("--output", choices=["json", "table", "yaml"], default="json")
    item.set_defaults(func=cmd_work_item)
    runs = sub.add_parser("pipeline-runs", help="List live ADO pipeline runs through Azure CLI")
    runs.add_argument("--pipeline-id", type=int)
    runs.add_argument("--top", type=int, default=5)
    runs.add_argument("--org")
    runs.add_argument("--project")
    runs.add_argument("--output", choices=["json", "table", "yaml"], default="json")
    runs.set_defaults(func=cmd_pipeline_runs)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
