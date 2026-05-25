#!/usr/bin/env python3
"""Safe MSSQL facade for policy checks and SQL classification."""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import List, Optional


DANGEROUS = {
    "insert", "update", "delete", "merge", "drop", "truncate", "alter", "create",
    "exec", "execute", "grant", "revoke", "backup", "restore", "use",
}


def classify(sql: str) -> dict:
    cleaned = re.sub(r"/\*.*?\*/", " ", sql or "", flags=re.S)
    cleaned = re.sub(r"--.*?(?:$|\n)", " ", cleaned, flags=re.M).strip().lower()
    words = re.findall(r"[a-z_]+", cleaned)
    if not words:
        category = "unknown"
    elif words[0] in {"select", "with", "declare"} and not (set(words) & DANGEROUS):
        category = "readonly"
    elif words[0] in DANGEROUS or (set(words) & {"exec", "execute"}):
        category = "dangerous"
    else:
        category = "unknown"
    return {
        "category": category,
        "requires_execute_flag": True,
        "requires_dangerous_flag": category != "readonly",
        "allowed_by_default": False,
    }


def env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def cmd_classify(args: argparse.Namespace) -> int:
    result = classify(args.sql)
    print(json.dumps(result, indent=2))
    return 0 if result["category"] != "unknown" else 2


def cmd_policy_check(args: argparse.Namespace) -> int:
    warnings = []
    driver = os.environ.get("MSSQL_DRIVER", "")
    encrypt = os.environ.get("MSSQL_ENCRYPT", "")
    trust = os.environ.get("MSSQL_TRUST_SERVER_CERTIFICATE", "")
    auth_mode = os.environ.get("MSSQL_AUTH_MODE", "")
    connection_string = os.environ.get("MSSQL_CONNECTIONSTRING", "")
    if connection_string:
        warnings.append("MSSQL_CONNECTIONSTRING is set; prefer component config and managed auth for enterprise use.")
        if "trustservercertificate=true" in connection_string.lower():
            warnings.append("Connection string enables TrustServerCertificate=True.")
    if driver and "18" not in driver:
        warnings.append("Prefer ODBC Driver 18 for SQL Server.")
    if encrypt and encrypt.lower() not in {"yes", "mandatory", "strict", "true"}:
        warnings.append("MSSQL encryption is not mandatory.")
    if trust.lower() in {"1", "true", "yes"}:
        warnings.append("TrustServerCertificate is enabled; this weakens certificate validation.")
    if auth_mode.lower() in {"sqlpassword", "sql", "password"}:
        warnings.append("SQL password auth is configured; prefer integrated, managed identity, or service principal where possible.")
    if env_bool("DatabaseConfiguration__EnableExecuteQuery"):
        warnings.append("Query execution flag is enabled.")
    if env_bool("MSSQL_ENABLE_DANGEROUS_SQL"):
        warnings.append("Dangerous SQL flag is enabled.")
    print(json.dumps({"status": "warn" if warnings else "ok", "warnings": warnings}, indent=2))
    return 1 if warnings and args.strict else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe MSSQL policy facade")
    sub = parser.add_subparsers(dest="command", required=True)
    classify_parser = sub.add_parser("classify", help="Classify SQL without executing it")
    classify_parser.add_argument("--sql", required=True)
    classify_parser.set_defaults(func=cmd_classify)
    policy = sub.add_parser("policy-check", help="Check local MSSQL security posture")
    policy.add_argument("--strict", action="store_true")
    policy.set_defaults(func=cmd_policy_check)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
