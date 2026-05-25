#!/usr/bin/env python3
"""Shared config diagnostics for the lightweight data-engineering OpenCode package."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


SECRET_KEYS = {
    "ADO_PAT",
    "ADO_ENTRA_TOKEN",
    "DATABRICKS_TOKEN",
    "DATABRICKS_CLIENT_SECRET",
    "MSSQL_CONNECTIONSTRING",
    "MSSQL_PASSWORD",
    "SQL_PASSWORD",
}

NON_SECRET_KEYS = {
    "ADO_ORG",
    "ADO_PROJECT",
    "ADO_AUTH_MODE",
    "ADO_TENANT_ID",
    "ADO_CLIENT_ID",
    "DATABRICKS_HOST",
    "DATABRICKS_AUTH_TYPE",
    "DATABRICKS_CLIENT_ID",
    "DATABRICKS_PROFILE",
    "DATABRICKS_WAREHOUSE_ID",
    "MSSQL_SERVER",
    "MSSQL_DATABASE",
    "MSSQL_AUTH_MODE",
    "MSSQL_DRIVER",
}

LEGACY_SECRET_KEYS = {"ADO_PAT", "DATABRICKS_TOKEN", "MSSQL_PASSWORD", "SQL_PASSWORD"}
AUTH_MODES = {
    "ado": [
        {
            "mode": "entra",
            "status": "recommended",
            "description": "Microsoft Entra token, service principal, or managed identity for Azure DevOps Services.",
        },
        {
            "mode": "pat",
            "status": "legacy-compatible",
            "description": "Personal access token for compatibility/testing or Azure DevOps Server constraints.",
        },
    ],
    "databricks": [
        {
            "mode": "workload_identity_federation",
            "status": "recommended-ci",
            "description": "OIDC/workload identity federation for CI/CD without stored Databricks secrets.",
        },
        {
            "mode": "oauth_m2m_or_profile",
            "status": "recommended",
            "description": "OAuth machine-to-machine, user-to-machine profile, or service principal auth.",
        },
        {
            "mode": "pat",
            "status": "legacy-compatible",
            "description": "Databricks PAT for compatibility/testing only.",
        },
    ],
    "mssql": [
        {
            "mode": "managed_or_integrated_identity",
            "status": "recommended",
            "description": "Managed identity, Microsoft Entra, or integrated auth with encrypted ODBC Driver 18 connections.",
        },
        {
            "mode": "sql_password",
            "status": "legacy-compatible",
            "description": "SQL password auth only when client policy explicitly accepts it.",
        },
    ],
}


def is_secret(key: str) -> bool:
    upper = key.upper()
    return upper in SECRET_KEYS or any(token in upper for token in ("TOKEN", "PAT", "PASSWORD", "SECRET", "PWD", "CONNECTIONSTRING"))


def redact(key: str, value: str) -> str:
    if not value:
        return ""
    if is_secret(key):
        return "<redacted>"
    return value


def dotenv_allowed() -> bool:
    return False


def resolve_key(key: str, invoke_provider: bool = False) -> dict:
    if key in os.environ:
        return {"key": key, "source": "env", "secret": is_secret(key), "value": redact(key, os.environ.get(key, ""))}
    provider = os.environ.get("DE_SECRET_PROVIDER_COMMAND", "").strip()
    if provider and is_secret(key):
        if invoke_provider:
            return resolve_from_provider(key, provider)
        return {"key": key, "source": "secret-provider-configured", "secret": True, "value": "<not-invoked-by-doctor>"}
    config_path = os.environ.get("DE_CONFIG_PATH", "").strip()
    if config_path and not is_secret(key):
        path = Path(config_path).expanduser()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
            if key in data:
                return {"key": key, "source": str(path), "secret": False, "value": str(data[key])}
    return {"key": key, "source": "missing", "secret": is_secret(key), "value": ""}


def auth_posture() -> dict:
    ado_mode = "entra" if os.environ.get("ADO_ENTRA_TOKEN") or os.environ.get("ADO_AUTH_MODE", "").lower() in {"entra", "managed_identity", "service_principal"} else "pat" if os.environ.get("ADO_PAT") else "unconfigured"
    databricks_mode = "workload_identity_federation" if os.environ.get("DATABRICKS_AUTH_TYPE", "").lower() in {"env-oidc", "github-oidc", "azure-devops-oidc", "workload_identity"} else "oauth_or_profile" if os.environ.get("DATABRICKS_PROFILE") or os.environ.get("DATABRICKS_CLIENT_ID") else "pat" if os.environ.get("DATABRICKS_TOKEN") else "unconfigured"
    mssql_mode = "managed_or_integrated" if os.environ.get("MSSQL_AUTH_MODE", "").lower() in {"managed_identity", "entra", "active_directory_integrated", "integrated"} else "sql_password" if os.environ.get("MSSQL_PASSWORD") or os.environ.get("SQL_PASSWORD") else "unconfigured"
    legacy = [key for key in sorted(LEGACY_SECRET_KEYS) if os.environ.get(key)]
    insecure_or_missing = {"pat", "sql_password", "unconfigured"}
    return {
        "ado": ado_mode,
        "databricks": databricks_mode,
        "mssql": mssql_mode,
        "legacy_secrets_present": legacy,
        "dotenv_supported": False,
        "safe_default": not legacy,
        "enterprise_ready": not legacy and not ({ado_mode, databricks_mode, mssql_mode} & insecure_or_missing),
    }


def resolve_from_provider(key: str, provider: str) -> dict:
    import shlex

    try:
        command = shlex.split(provider) + [key]
        env = os.environ.copy()
        env["DE_CONFIG_KEY"] = key
        result = subprocess.run(command, text=True, capture_output=True, timeout=15, env=env, stdin=subprocess.DEVNULL)
    except Exception as exc:
        return {"key": key, "source": "secret-provider-error", "secret": True, "value": "", "error": safe_message(str(exc))}
    if result.returncode != 0:
        return {"key": key, "source": "secret-provider-error", "secret": True, "value": "", "error": safe_message(result.stderr)}
    value = result.stdout.strip()
    return {"key": key, "source": "secret-provider", "secret": True, "value": "<resolved>" if value else ""}


def safe_message(message: str) -> str:
    cleaned = message or ""
    for key, value in os.environ.items():
        if is_secret(key) and value:
            cleaned = cleaned.replace(value, "<redacted>")
    return cleaned.strip()


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "opencode": shutil.which("opencode") or "",
        "git": shutil.which("git") or "",
        "databricks": shutil.which("databricks") or "",
        "az": shutil.which("az") or "",
        "dotenv_allowed": dotenv_allowed(),
        "dotenv_supported": False,
    }
    keys = sorted((NON_SECRET_KEYS | SECRET_KEYS) if args.all else {"ADO_ORG", "ADO_PROJECT", "DATABRICKS_HOST", "DATABRICKS_PROFILE", "MSSQL_SERVER", "MSSQL_DATABASE"})
    result = {
        "status": "ok",
        "checks": checks,
        "config": [resolve_key(key) for key in keys],
        "auth_posture": auth_posture(),
        "notes": [
            ".env is not supported by de-opencode. Use process env, managed identity/profile auth, or a client-approved secret provider.",
            "Secret-provider execution is intentionally not performed by doctor.",
        ],
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    print(json.dumps(resolve_key(args.key, invoke_provider=args.invoke_provider), indent=2))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    warnings = []
    if os.environ.get("DE_ALLOW_DOTENV"):
        warnings.append("DE_ALLOW_DOTENV is ignored; .env files are not supported by de-opencode.")
    if os.environ.get("MSSQL_CONNECTIONSTRING"):
        warnings.append("MSSQL_CONNECTIONSTRING is set; prefer component config plus managed auth for enterprise rollout.")
    if os.environ.get("DATABRICKS_TOKEN"):
        warnings.append("DATABRICKS_TOKEN is set; prefer workload identity federation, OAuth profile, or service principal auth.")
    if os.environ.get("ADO_PAT"):
        warnings.append("ADO_PAT is set; prefer Microsoft Entra service principal or managed identity where possible.")
    print(json.dumps({"status": "warn" if warnings else "ok", "warnings": warnings, "auth_posture": auth_posture()}, indent=2))
    return 0


def cmd_auth(args: argparse.Namespace) -> int:
    print(json.dumps({
        "status": "ok",
        "posture": auth_posture(),
        "supported_modes": AUTH_MODES,
        "guidance": [
            "Use Microsoft Entra/service principals/managed identity for Azure DevOps Services automation.",
            "Use Databricks workload identity federation for Azure DevOps Pipelines where possible.",
            "Use Databricks OAuth/profile/service principal auth before PATs.",
            "Use MSSQL managed/integrated/Entra auth with ODBC Driver 18 encryption where possible.",
            "Keep PAT/token/password env variables as legacy-compatible fallback only.",
        ],
    }, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Data-engineering OpenCode config diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Show redacted local readiness and config state")
    doctor.add_argument("--all", action="store_true", help="Include all known keys")
    doctor.set_defaults(func=cmd_doctor)
    explain = sub.add_parser("explain", help="Explain how a config key would resolve")
    explain.add_argument("key")
    explain.add_argument("--invoke-provider", action="store_true", help="Invoke configured secret provider but never print secret values")
    explain.set_defaults(func=cmd_explain)
    resolve = sub.add_parser("resolve", help="Resolve a config key for wrappers; prints non-secrets only")
    resolve.add_argument("key")
    resolve.add_argument("--invoke-provider", action="store_true")
    resolve.set_defaults(func=cmd_resolve)
    audit = sub.add_parser("audit", help="Warn about insecure local config posture")
    audit.set_defaults(func=cmd_audit)
    auth = sub.add_parser("auth", help="Show enterprise auth posture and supported secure modes")
    auth.set_defaults(func=cmd_auth)
    return parser


def cmd_resolve(args: argparse.Namespace) -> int:
    result = resolve_key(args.key, invoke_provider=args.invoke_provider)
    if result["secret"]:
        print(json.dumps({k: v for k, v in result.items() if k != "value"}, indent=2))
        return 0 if result["source"] != "missing" else 1
    print(json.dumps(result, indent=2))
    return 0 if result["source"] != "missing" else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
