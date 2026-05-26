#!/usr/bin/env python3
"""Safe Databricks SQL facade for classification, dry-run checks, and guarded execution."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional


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


def cmd_warehouses(args: argparse.Namespace) -> int:
    headers, host = databricks_auth(args)
    data = databricks_request("GET", f"{host}/api/2.0/sql/warehouses", headers)
    warehouses = data.get("warehouses", [])
    if args.format == "json":
        print(json.dumps({"status": "ok", "warehouses": warehouses}, indent=2))
        return 0
    print("Databricks SQL Warehouses")
    for item in warehouses:
        print(f"- {item.get('id', '')}: {item.get('name', '')} [{item.get('state', '')}]")
    return 0


def cmd_execute(args: argparse.Namespace) -> int:
    policy = execution_policy(args)
    if policy["status"] == "blocked":
        print(json.dumps(policy, indent=2))
        return 1
    if args.dry_run_only:
        print(json.dumps(policy, indent=2))
        return 0
    headers, host = databricks_auth(args)
    warehouse_id = args.warehouse_id or os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
    if not warehouse_id:
        warehouse_id = default_warehouse(headers, host)
    result = execute_statement(args.sql, warehouse_id, headers, host, args.timeout)
    output = render_statement_result(result, args.limit)
    if args.format == "json":
        print(json.dumps(output, indent=2))
    elif args.format == "csv":
        print(csv_text(output["columns"], output["rows"]), end="")
    else:
        print(table_text(output["columns"], output["rows"]))
        if output["truncated"]:
            print(f"\n[warning] showing {len(output['rows'])} of {output['total_row_count']} rows; lower risk by adding LIMIT.")
    return 0


def execution_policy(args: argparse.Namespace) -> dict:
    classification = classify_sql(args.sql)
    issues = []
    warnings = []
    if classification["category"] != "readonly":
        if not args.allow_write or not args.confirm_write:
            issues.append("Live Databricks SQL execution only allows readonly SQL by default. Use --allow-write --confirm-write after approval.")
        if not args.row_count_checked:
            issues.append("Write/admin SQL requires --row-count-checked evidence before execution.")
    if args.environment.lower() in {"prod", "production"} and classification["category"] != "readonly":
        issues.append("Production write/admin SQL requires external approval before execution.")
    if classification["unqualified_references"] and not args.allow_unqualified_names:
        warnings.append("Unity Catalog queries should use 3-part names: catalog.schema.object.")
    return {
        "status": "blocked" if issues else "ok",
        "action": "databricks-sql-execute",
        "classification": classification,
        "issues": issues,
        "warnings": warnings,
        "will_execute": not issues and not args.dry_run_only,
    }


def databricks_auth(args: argparse.Namespace) -> tuple[Dict[str, str], str]:
    host = (args.host or os.environ.get("DATABRICKS_HOST", "")).rstrip("/")
    if not host:
        raise SystemExit("DATABRICKS_HOST is required, or pass --host.")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    profile = args.profile or os.environ.get("DATABRICKS_PROFILE", "")
    if profile:
        token = token_from_profile(profile, host)
    if not token:
        raise SystemExit("DATABRICKS_PROFILE or DATABRICKS_TOKEN is required. Prefer profile/OAuth over PAT.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, host


def token_from_profile(profile: str, host: str) -> str:
    cli = shutil.which("databricks") or os.environ.get("DATABRICKS_CLI_PATH", "")
    if not cli:
        raise SystemExit("Databricks CLI is required for DATABRICKS_PROFILE auth.")
    cmd = [cli, "auth", "token", "--profile", profile, "--host", host]
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=20, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise SystemExit(redact_error(result.stderr or result.stdout))
    text = result.stdout + result.stderr
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise SystemExit("Databricks CLI did not return token JSON.")
    data = json.loads(text[start:end + 1])
    token = data.get("access_token", "")
    if not token:
        raise SystemExit("Databricks CLI token response did not include access_token.")
    return token


def databricks_request(method: str, url: str, headers: Dict[str, str], payload: Optional[dict] = None, timeout: int = 30) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Databricks HTTP {exc.code}: {redact_error(body_text)}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Databricks network error: {redact_error(str(exc.reason))}")


def default_warehouse(headers: Dict[str, str], host: str) -> str:
    data = databricks_request("GET", f"{host}/api/2.0/sql/warehouses", headers)
    warehouses = data.get("warehouses", [])
    if not warehouses:
        raise SystemExit("No Databricks SQL warehouses found. Set DATABRICKS_WAREHOUSE_ID or create a warehouse.")
    running = [item for item in warehouses if item.get("state") == "RUNNING"]
    chosen = running[0] if running else warehouses[0]
    print(f"Using warehouse: {chosen.get('name', chosen.get('id'))}", file=sys.stderr)
    return chosen["id"]


def execute_statement(sql: str, warehouse_id: str, headers: Dict[str, str], host: str, timeout: int) -> dict:
    payload = {
        "statement": sql,
        "warehouse_id": warehouse_id,
        "wait_timeout": "30s",
        "on_wait_timeout": "CONTINUE",
        "format": "JSON_ARRAY",
    }
    result = databricks_request("POST", f"{host}/api/2.0/sql/statements", headers, payload, timeout=timeout)
    statement_id = result.get("statement_id")
    state = result.get("status", {}).get("state", "")
    deadline = time.time() + timeout
    while state in {"PENDING", "RUNNING"} and time.time() < deadline:
        time.sleep(2)
        result = databricks_request("GET", f"{host}/api/2.0/sql/statements/{statement_id}", headers, timeout=timeout)
        state = result.get("status", {}).get("state", "")
    if state != "SUCCEEDED":
        error = result.get("status", {}).get("error", {}).get("message", state or "unknown")
        raise SystemExit(f"Databricks SQL failed: {redact_error(error)}")
    return result


def render_statement_result(result: dict, limit: int) -> dict:
    manifest = result.get("manifest", {})
    columns = [item.get("name", f"col{idx}") for idx, item in enumerate(manifest.get("schema", {}).get("columns", []))]
    rows_raw = result.get("result", {}).get("data_array", []) or []
    rows_raw = rows_raw[: max(limit, 0)]
    rows = [{columns[idx]: (row[idx] if idx < len(row) else None) for idx in range(len(columns))} for row in rows_raw]
    total = int(manifest.get("total_row_count", len(rows_raw)) or 0)
    return {"status": "ok", "columns": columns, "rows": rows, "row_count": len(rows), "total_row_count": total, "truncated": total > len(rows)}


def csv_text(columns: List[str], rows: List[dict]) -> str:
    import csv
    import io

    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue()


def table_text(columns: List[str], rows: List[dict]) -> str:
    if not columns:
        return "(no columns returned)"
    if not rows:
        return "(no rows returned)"
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))
    line = "+".join("-" * (widths[col] + 2) for col in columns)
    output = [line, "|".join(f" {col.ljust(widths[col])} " for col in columns), line]
    for row in rows:
        output.append("|".join(f" {str(row.get(col, '')).ljust(widths[col])} " for col in columns))
    output.append(line)
    return "\n".join(output)


def redact_error(text: str) -> str:
    clean = text or ""
    for key, value in os.environ.items():
        if value and is_secretish(key):
            clean = clean.replace(value, "<redacted>")
    clean = re.sub(r"dapi[a-zA-Z0-9]+", "dapi<redacted>", clean)
    return clean


def is_secretish(key: str) -> bool:
    return any(token in key.upper() for token in ("TOKEN", "PASSWORD", "SECRET", "PAT", "PWD"))


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
    execute = sub.add_parser("execute", help="Execute guarded Databricks SQL through the SQL Statement API")
    execute.add_argument("--sql", required=True)
    execute.add_argument("--environment", default="dev")
    execute.add_argument("--warehouse-id")
    execute.add_argument("--host")
    execute.add_argument("--profile")
    execute.add_argument("--timeout", type=int, default=120)
    execute.add_argument("--limit", type=int, default=100)
    execute.add_argument("--format", choices=["table", "json", "csv"], default="table")
    execute.add_argument("--dry-run-only", action="store_true")
    execute.add_argument("--allow-write", action="store_true")
    execute.add_argument("--confirm-write", action="store_true")
    execute.add_argument("--row-count-checked", action="store_true")
    execute.add_argument("--allow-unqualified-names", action="store_true")
    execute.set_defaults(func=cmd_execute)
    warehouses = sub.add_parser("warehouses", help="List Databricks SQL warehouses")
    warehouses.add_argument("--host")
    warehouses.add_argument("--profile")
    warehouses.add_argument("--format", choices=["table", "json"], default="table")
    warehouses.set_defaults(func=cmd_warehouses)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
