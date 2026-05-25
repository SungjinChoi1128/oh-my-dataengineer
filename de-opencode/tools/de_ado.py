#!/usr/bin/env python3
"""Azure DevOps facade for operation classification and pipeline preflight."""

from __future__ import annotations

import argparse
import json
import re
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Azure DevOps safe operation facade")
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify", help="Classify an ADO operation")
    classify.add_argument("--operation", required=True)
    classify.set_defaults(func=cmd_classify)
    preflight = sub.add_parser("preflight", help="Preflight an Azure Pipeline YAML file")
    preflight.add_argument("--pipeline-yaml", required=True)
    preflight.set_defaults(func=cmd_preflight)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
