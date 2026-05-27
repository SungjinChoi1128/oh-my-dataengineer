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
import time
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parents[1]


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


def run_opencode_debug(args: List[str]) -> dict:
    opencode = shutil.which("opencode")
    if not opencode:
        return {"available": False, "error": "opencode not found on PATH"}
    env = os.environ.copy()
    last_error = ""
    for attempt in range(3):
        try:
            result = subprocess.run(
                [opencode, "debug", *args],
                text=True,
                capture_output=True,
                timeout=30,
                env=env,
                stdin=subprocess.DEVNULL,
            )
        except Exception as exc:
            return {"available": True, "ok": False, "error": safe_message(str(exc))}
        last_error = safe_message(result.stderr)
        if result.returncode == 0 or "wal_checkpoint" not in last_error:
            break
        time.sleep(0.5 * (attempt + 1))
    data = None
    if result.stdout.strip():
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            data = None
    return {
        "available": True,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout_json": data,
        "stdout_excerpt": result.stdout.strip()[:1000],
        "stderr_excerpt": safe_message(result.stderr)[:1000],
    }


def plugin_loaded_from_config(config: dict) -> bool:
    expected = "de-guardrails.ts"
    plugins = config.get("plugin", [])
    origins = config.get("plugin_origins", [])
    plugin_text = json.dumps(plugins) + json.dumps(origins)
    return expected in plugin_text


def custom_tools_visible(agent_config: dict) -> bool:
    tools = agent_config.get("tools", {})
    return bool(
        tools.get("de_config_doctor")
        and tools.get("de_repo_init")
        and tools.get("de_workbench_route")
        and tools.get("de_quality_verdict")
    )


def cmd_hooks(args: argparse.Namespace) -> int:
    plugin_path = ROOT / "plugins" / "de-guardrails.ts"
    env_config_dir = os.environ.get("OPENCODE_CONFIG_DIR", "")
    env_points_to_package = bool(env_config_dir) and Path(env_config_dir).expanduser().resolve() == ROOT.resolve()
    if env_points_to_package:
        current_debug = run_opencode_debug(["config"])
        current_agent = run_opencode_debug(["agent", "data-engineer"])
    else:
        current_debug = {"ok": False, "stdout_json": {}, "stderr_excerpt": "OPENCODE_CONFIG_DIR is not set to this package; skipping OpenCode debug checks."}
        current_agent = {"ok": False, "stdout_json": {}, "stderr_excerpt": "OPENCODE_CONFIG_DIR is not set to this package; skipping OpenCode debug checks."}

    current_config = current_debug.get("stdout_json") or {}
    current_agent_config = current_agent.get("stdout_json") or {}

    checks = {
        "package_root": str(ROOT),
        "env_OPENCODE_CONFIG_DIR": env_config_dir,
        "env_points_to_package": env_points_to_package,
        "plugin_file_exists": plugin_path.exists(),
        "opencode_on_path": bool(shutil.which("opencode")),
        "current_config_plugin_loaded": plugin_loaded_from_config(current_config),
        "current_agent_custom_tools_visible": custom_tools_visible(current_agent_config),
    }
    ok = (
        checks["plugin_file_exists"]
        and checks["opencode_on_path"]
        and checks["current_config_plugin_loaded"]
        and checks["current_agent_custom_tools_visible"]
    )
    recommendations = []
    if not checks["opencode_on_path"]:
        recommendations.append("Install OpenCode or open a shell where opencode is on PATH.")
    if not checks["env_OPENCODE_CONFIG_DIR"]:
        recommendations.append("Set OPENCODE_CONFIG_DIR to the installed de-opencode directory before launching OpenCode.")
    elif not checks["env_points_to_package"]:
        recommendations.append("OPENCODE_CONFIG_DIR points somewhere else; set it to this installed package directory.")
    if not checks["plugin_file_exists"]:
        recommendations.append("The guardrails plugin file is missing; reinstall the package.")
    if checks["current_config_plugin_loaded"] and not checks["current_agent_custom_tools_visible"]:
        recommendations.append("Plugin origin is visible but custom tools are not; restart OpenCode and check plugin load errors in OpenCode logs.")

    result = {
        "status": "ok" if ok else "error",
        "checks": checks,
        "current_debug": {
            "config_ok": current_debug.get("ok"),
            "agent_ok": current_agent.get("ok"),
            "plugin_origins": current_config.get("plugin_origins", []),
            "plugin": current_config.get("plugin", []),
            "data_engineer_tools_sample": {
                key: (current_agent_config.get("tools") or {}).get(key)
                for key in ["de_config_doctor", "de_repo_init", "de_workbench_route", "de_quality_verdict"]
            },
            "config_error": current_debug.get("error") or current_debug.get("stderr_excerpt", ""),
            "agent_error": current_agent.get("error") or current_agent.get("stderr_excerpt", ""),
        },
        "recommendations": recommendations,
    }
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


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
    hooks = sub.add_parser("hooks", help="Verify OpenCode plugin/hook loading and custom tool visibility")
    hooks.set_defaults(func=cmd_hooks)
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
