#!/usr/bin/env python3
"""Safe Databricks SQL facade for classification and dry-run checks."""

from __future__ import annotations

import argparse
import json
import re
from typing import List, Optional


DML = {"insert", "update", "delete", "merge", "copy"}
DDL = {"create", "alter", "drop", "truncate", "replace"}
ADMIN = {"grant", "revoke", "optimize", "vacuum", "refresh"}


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql or "", flags=re.S)
    sql = re.sub(r"--.*?(?:$|\n)", " ", sql, flags=re.M)
    return sql.strip()


def tokens(sql: str) -> list[str]:
    return re.findall(r"[a-z_]+", strip_comments(sql).lower())


def classify_sql(sql: str) -> dict:
    words = tokens(sql)
    if not words:
        category = "unknown"
    elif words[0] in {"select", "with", "describe", "show", "explain"}:
        category = "readonly" if not (set(words) & (DML | DDL | ADMIN)) else "mixed"
    elif words[0] in DML:
        category = "dml"
    elif words[0] in DDL:
        category = "ddl"
    elif words[0] in ADMIN:
        category = "admin"
    else:
        category = "unknown"
    return {
        "category": category,
        "requires_approval": category not in {"readonly"},
        "requires_row_count_precheck": category in {"dml", "ddl", "mixed"},
        "requires_three_part_names": category in {"readonly", "dml", "ddl", "mixed"},
        "object_references": object_references(sql),
        "unqualified_references": unqualified_references(sql),
    }


def cmd_classify(args: argparse.Namespace) -> int:
    result = classify_sql(args.sql)
    result["sql_redacted"] = redact_sql(args.sql)
    print(json.dumps(result, indent=2))
    return 0 if result["category"] != "unknown" else 2


def cmd_dry_run(args: argparse.Namespace) -> int:
    result = classify_sql(args.sql)
    issues = []
    warnings = []
    if result["requires_approval"] and not args.confirm_write:
        issues.append("Write/admin/unknown SQL requires --confirm-write and an approval record.")
    if result["requires_row_count_precheck"] and not args.row_count_checked:
        issues.append("DML/DDL requires row-count or target-object precheck evidence.")
    if args.environment.lower() in {"prod", "production"} and result["requires_approval"]:
        issues.append("Production write/admin SQL must be approved outside the tool before execution.")
    if result["requires_three_part_names"] and result["unqualified_references"] and not args.allow_unqualified_names:
        issue = "Unity Catalog operations should use 3-part names: catalog.schema.object."
        if result["requires_approval"]:
            issues.append(issue)
        else:
            warnings.append(issue)
    print(json.dumps({
        "status": "blocked" if issues else "ok",
        "classification": result,
        "environment": args.environment,
        "issues": issues,
        "warnings": warnings,
    }, indent=2))
    return 1 if issues else 0


def redact_sql(sql: str) -> str:
    redacted = re.sub(r"(?i)(password|token|secret|key)\s*=\s*'[^']*'", r"\1='<redacted>'", sql or "")
    redacted = re.sub(r"(?i)(password|token|secret|key)\s*=\s*\"[^\"]*\"", r"\1=\"<redacted>\"", redacted)
    return redacted


def object_references(sql: str) -> List[str]:
    clean = strip_comments(sql)
    patterns = [
        r"(?i)\bfrom\s+([`\"\[]?[A-Za-z_][\w.`\"\]\[]*)",
        r"(?i)\bjoin\s+([`\"\[]?[A-Za-z_][\w.`\"\]\[]*)",
        r"(?i)\busing\s+([`\"\[]?[A-Za-z_][\w.`\"\]\[]*)",
        r"(?i)\binto\s+([`\"\[]?[A-Za-z_][\w.`\"\]\[]*)",
        r"(?i)\bupdate\s+([`\"\[]?[A-Za-z_][\w.`\"\]\[]*)",
        r"(?i)\bmerge\s+into\s+([`\"\[]?[A-Za-z_][\w.`\"\]\[]*)",
        r"(?i)\btruncate\s+table\s+([`\"\[]?[A-Za-z_][\w.`\"\]\[]*)",
        r"(?i)\btable\s+([`\"\[]?[A-Za-z_][\w.`\"\]\[]*)",
    ]
    refs = []
    for pattern in patterns:
        for match in re.finditer(pattern, clean):
            ref = normalize_identifier(match.group(1))
            if ref and ref.lower() not in {"select", "values", "set", "on", "when", "matched", "not"}:
                refs.append(ref)
    return sorted(set(refs))


def unqualified_references(sql: str) -> List[str]:
    refs = []
    for ref in object_references(sql):
        if ref.startswith("system."):
            continue
        if len([part for part in ref.split(".") if part]) < 3:
            refs.append(ref)
    return refs


def normalize_identifier(value: str) -> str:
    return (value or "").strip().strip("`\"[]").replace("`", "").replace('"', "").replace("[", "").replace("]", "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe Databricks SQL classification facade")
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify", help="Classify SQL without executing it")
    classify.add_argument("--sql", required=True)
    classify.set_defaults(func=cmd_classify)
    dry = sub.add_parser("dry-run", help="Check whether SQL would be allowed by policy")
    dry.add_argument("--sql", required=True)
    dry.add_argument("--environment", default="dev")
    dry.add_argument("--confirm-write", action="store_true")
    dry.add_argument("--row-count-checked", action="store_true")
    dry.add_argument("--allow-unqualified-names", action="store_true")
    dry.set_defaults(func=cmd_dry_run)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
