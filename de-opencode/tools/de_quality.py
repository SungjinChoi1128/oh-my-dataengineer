#!/usr/bin/env python3
"""Local QA evidence helpers for data-engineering workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional


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
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
