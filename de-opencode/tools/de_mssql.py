#!/usr/bin/env python3
"""Safe MSSQL facade for policy checks, SQL classification, and guarded live reads."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
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


def cmd_query(args: argparse.Namespace) -> int:
    result = classify(args.sql)
    if result["category"] != "readonly" and not args.allow_dangerous:
        print(json.dumps({
            "status": "blocked",
            "classification": result,
            "issues": ["Live MSSQL query only allows readonly SQL by default. Use --allow-dangerous only after explicit approval."],
        }, indent=2))
        return 1
    sqlcmd = shutil.which("sqlcmd")
    if not sqlcmd:
        raise SystemExit("sqlcmd is required for live MSSQL query execution.")
    command = [sqlcmd, "-b", "-S", args.server or os.environ.get("MSSQL_SERVER", "")]
    database = args.database or os.environ.get("MSSQL_DATABASE", "")
    if database:
        command += ["-d", database]
    if args.auth_mode == "integrated":
        command += ["-E"]
    elif args.auth_mode == "entra":
        command += ["-G"]
    elif args.auth_mode == "sql-password":
        if not args.allow_sql_password:
            raise SystemExit("SQL password auth requires --allow-sql-password.")
        user = args.user or os.environ.get("MSSQL_USER", "")
        password = os.environ.get(args.password_env or "MSSQL_PASSWORD", "")
        if not user or not password:
            raise SystemExit("MSSQL_USER/--user and password env are required for sql-password auth.")
        command += ["-U", user, "-P", password]
    if not command[command.index("-S") + 1]:
        raise SystemExit("MSSQL server is required via --server or MSSQL_SERVER.")
    bounded_sql = args.sql
    command += ["-Q", bounded_sql, "-W"]
    if args.format == "csv":
        command += ["-s", ","]
    completed = subprocess.run(command, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=args.timeout)
    if completed.stdout:
        print(redact(completed.stdout), end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(redact(completed.stderr), end="" if completed.stderr.endswith("\n") else "\n")
    return completed.returncode


def redact(text: str) -> str:
    clean = text or ""
    for key, value in os.environ.items():
        if value and any(token in key.upper() for token in ("PASSWORD", "TOKEN", "SECRET", "PAT", "PWD", "CONNECTIONSTRING")):
            clean = clean.replace(value, "<redacted>")
    return clean


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe MSSQL policy facade")
    sub = parser.add_subparsers(dest="command", required=True)
    classify_parser = sub.add_parser("classify", help="Classify SQL without executing it")
    classify_parser.add_argument("--sql", required=True)
    classify_parser.set_defaults(func=cmd_classify)
    policy = sub.add_parser("policy-check", help="Check local MSSQL security posture")
    policy.add_argument("--strict", action="store_true")
    policy.set_defaults(func=cmd_policy_check)
    query = sub.add_parser("query", help="Execute a guarded live MSSQL read-only query through sqlcmd")
    query.add_argument("--sql", required=True)
    query.add_argument("--server")
    query.add_argument("--database")
    query.add_argument("--auth-mode", choices=["integrated", "entra", "sql-password"], default=os.environ.get("MSSQL_AUTH_MODE", "integrated"))
    query.add_argument("--user")
    query.add_argument("--password-env", default="MSSQL_PASSWORD")
    query.add_argument("--format", choices=["table", "csv"], default="table")
    query.add_argument("--timeout", type=int, default=60)
    query.add_argument("--allow-dangerous", action="store_true")
    query.add_argument("--allow-sql-password", action="store_true")
    query.set_defaults(func=cmd_query)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
