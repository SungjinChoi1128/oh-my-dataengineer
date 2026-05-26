#!/usr/bin/env python3
"""Repo-specific context onboarding for de-opencode."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


CONTEXT_DIR = ".de-opencode"
ARCHIVE_DIR = ".de-opencode-archive"
SCOPES_FILE = "scopes.json"
FRESHNESS_DAYS = 14
SECRET_NAMES = {
    ".env",
    ".env.local",
    ".databrickscfg",
    "odbc.ini",
    "tnsnames.ora",
}
SECRET_SUFFIXES = {".pem", ".key", ".pfx", ".p12"}
IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".omx",
    ".de-opencode",
    ARCHIVE_DIR,
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".terraform",
    "dist",
    "build",
    "target",
}


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_secret_path(path: Path) -> bool:
    name = path.name.lower()
    return name in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES or "secret" in name and path.suffix.lower() in {".json", ".yml", ".yaml"}


def iter_repo_files(root: Path, max_files: int, include_paths: Optional[list[str]] = None) -> list[Path]:
    files: list[Path] = []
    starts = scoped_start_paths(root, include_paths)
    for start in starts:
        if start.is_file():
            if not is_secret_path(start):
                files.append(start)
            continue
        if not start.exists():
            continue
        for current, dirs, names in os.walk(start):
            dirs[:] = [item for item in dirs if item not in IGNORE_DIRS and not item.startswith(".cache")]
            current_path = Path(current)
            for name in names:
                path = current_path / name
                if is_secret_path(path):
                    continue
                try:
                    if path.stat().st_size > 2_000_000:
                        continue
                except OSError:
                    continue
                files.append(path)
                if len(files) >= max_files:
                    return files
    return files


def scoped_start_paths(root: Path, include_paths: Optional[list[str]]) -> list[Path]:
    if not include_paths:
        return [root]
    starts = []
    for item in include_paths:
        path = (root / item).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        starts.append(path)
    return starts or [root]


def git_root(start: Path) -> Optional[Path]:
    try:
        result = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], text=True, capture_output=True, timeout=5)
    except Exception:
        return None
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return None


def git_value(root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, timeout=5)
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def git_metadata(root: Path) -> dict:
    return {
        "branch": git_value(root, ["branch", "--show-current"]),
        "commit": git_value(root, ["rev-parse", "--short", "HEAD"]),
    }


def detect_repo(root: Path, files: list[Path]) -> dict:
    rels = [rel(path, root) for path in files]
    lower = [item.lower() for item in rels]
    suffixes: dict[str, int] = {}
    for path in files:
        suffix = path.suffix.lower() or "<none>"
        suffixes[suffix] = suffixes.get(suffix, 0) + 1

    signals = {
        "git_repo": (root / ".git").exists(),
        "databricks_bundle": any(Path(item).name in {"databricks.yml", "databricks.yaml"} for item in lower),
        "azure_pipelines": any(Path(item).name in {"azure-pipelines.yml", "azure-pipelines.yaml"} or item.startswith(".azuredevops/") for item in lower),
        "github_actions": any(item.startswith(".github/workflows/") for item in lower),
        "dbt": any(Path(item).name == "dbt_project.yml" for item in lower),
        "python": any(Path(item).name in {"pyproject.toml", "requirements.txt", "setup.py"} for item in lower) or any(item.endswith(".py") for item in lower),
        "sql": any(item.endswith(".sql") for item in lower),
        "notebooks": any(item.endswith((".ipynb", ".dbc")) for item in lower),
        "mssql_or_tsql": any("mssql" in item or "sqlserver" in item or "stored" in item or "procedure" in item for item in lower),
        "ssis": any(item.endswith(".dtsx") for item in lower),
        "tests": any("/test" in f"/{item}" or item.startswith("tests/") or item.endswith("_test.py") or item.endswith(".test.ts") for item in lower),
    }
    repo_types = []
    if signals["databricks_bundle"]:
        repo_types.append("databricks-bundle")
    if signals["azure_pipelines"] or signals["github_actions"]:
        repo_types.append("ci-cd")
    if signals["dbt"]:
        repo_types.append("dbt")
    if signals["sql"]:
        repo_types.append("sql")
    if signals["mssql_or_tsql"] or signals["ssis"]:
        repo_types.append("legacy-migration")
    if signals["python"]:
        repo_types.append("python-data-engineering")
    if not repo_types:
        repo_types.append("unknown")

    important = important_files(root, rels)
    return {
        "repo_name": root.name,
        "root": ".",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "git": git_metadata(root),
        "file_count_scanned": len(files),
        "file_suffix_counts": dict(sorted(suffixes.items(), key=lambda item: item[0])),
        "repo_types": repo_types,
        "signals": signals,
        "important_files": important,
        "file_summaries": file_summaries(root, files),
        "risk_zones": risk_zones(rels),
        "commands": command_catalog(signals, important),
        "safety_policy": safety_policy(signals),
        "secret_policy": {
            "env_files_supported": False,
            "secret_files_scanned": False,
            "skipped_secret_patterns": sorted(SECRET_NAMES),
            "message": "Repo onboarding skips secret/config files and does not read .env.",
        },
    }


def important_files(root: Path, rels: list[str]) -> dict[str, list[str]]:
    groups = {
        "pipelines": [],
        "databricks": [],
        "sql": [],
        "notebooks": [],
        "tests": [],
        "docs": [],
        "config": [],
    }
    for item in rels:
        low = item.lower()
        name = Path(low).name
        if name in {"azure-pipelines.yml", "azure-pipelines.yaml"} or low.startswith(".github/workflows/") or low.startswith(".azuredevops/"):
            groups["pipelines"].append(item)
        if name in {"databricks.yml", "databricks.yaml"} or "bundle" in low and low.endswith((".yml", ".yaml")):
            groups["databricks"].append(item)
        if low.endswith(".sql"):
            groups["sql"].append(item)
        if low.endswith((".ipynb", ".dbc")):
            groups["notebooks"].append(item)
        if "/test" in f"/{low}" or low.startswith("tests/") or low.endswith("_test.py") or low.endswith(".test.ts"):
            groups["tests"].append(item)
        if name in {"readme.md", "contributing.md"} or low.startswith("docs/"):
            groups["docs"].append(item)
        if name in {"pyproject.toml", "requirements.txt", "package.json", "dbt_project.yml"}:
            groups["config"].append(item)
    return {key: sorted(value)[:50] for key, value in groups.items()}


def file_summaries(root: Path, files: list[Path]) -> list[dict[str, object]]:
    interesting = []
    for path in files:
        low = rel(path, root).lower()
        name = Path(low).name
        if name in {"readme.md", "pyproject.toml", "package.json", "dbt_project.yml", "databricks.yml", "databricks.yaml", "azure-pipelines.yml", "azure-pipelines.yaml"} or low.startswith(".github/workflows/"):
            interesting.append(path)
    summaries = []
    for path in sorted(interesting)[:20]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        excerpt = "\n".join(text.splitlines()[:80])
        summaries.append({
            "path": rel(path, root),
            "line_count": len(text.splitlines()),
            "excerpt": redact_text(excerpt[:8000]),
        })
    return summaries


def redact_text(text: str) -> str:
    redacted = text or ""
    redacted = re.sub(r"(?i)(password|passwd|pwd|token|secret|client_secret|pat|connectionstring)\s*[:=]\s*['\"]?[^'\"\s]+", r"\1=<redacted>", redacted)
    redacted = re.sub(r"dapi[a-zA-Z0-9]+", "dapi<redacted>", redacted)
    return redacted


def risk_zones(rels: list[str]) -> list[dict[str, str]]:
    risks = []
    patterns = [
        ("production-deploy", re.compile(r"(?i)(prod|production).*(deploy|pipeline)|deploy.*(prod|production)"), "high"),
        ("sql-mutation", re.compile(r"(?i)(ddl|dml|migration|merge|delete|truncate|drop).*\.(sql)$"), "high"),
        ("pipeline", re.compile(r"(?i)(azure-pipelines|\.github/workflows|deploy|release).*\.(ya?ml)$"), "medium"),
        ("notebook", re.compile(r"(?i)\.(ipynb|dbc)$"), "medium"),
    ]
    for item in rels:
        for risk_id, pattern, severity in patterns:
            if pattern.search(item):
                risks.append({"id": risk_id, "severity": severity, "path": item})
                break
    return risks[:100]


def command_catalog(signals: dict, important: dict[str, list[str]]) -> dict[str, list[str]]:
    commands: dict[str, list[str]] = {
        "onboarding": ["de repo doctor", "de repo contract", "de repo brief", "de repo todo", "de repo commands", "de repo reset"],
        "security": ["de auth", "de security checklist --scope client-review"],
    }
    if signals.get("azure_pipelines"):
        pipeline = important.get("pipelines", ["azure-pipelines.yml"])[0] if important.get("pipelines") else "azure-pipelines.yml"
        commands["pipeline"] = [
            f"de pipeline preflight --pipeline-yaml {pipeline}",
            f"de pipeline doctor --pipeline-yaml {pipeline} --log-file build.log --write-evidence",
            "de ado pipeline-runs --top 5 --output table",
        ]
    if signals.get("databricks_bundle"):
        bundle = important.get("databricks", ["databricks.yml"])[0] if important.get("databricks") else "databricks.yml"
        commands["databricks"] = [
            f"de databricks bundle-doctor --bundle-yaml {bundle}",
            'de databricks sql execute --sql "SELECT 1" --dry-run-only',
            "de databricks sql warehouses",
        ]
    if signals.get("sql") or signals.get("mssql_or_tsql"):
        commands["mssql"] = [
            'de-mssql classify --sql "SELECT 1"',
            'de-mssql policy-check',
            'de mssql query --sql "SELECT 1" --server <server> --database <db> --auth-mode integrated',
        ]
    if signals.get("tests"):
        commands["quality"] = ["de quality readiness --claim \"repo change is ready\" --environment dev"]
    return commands


def safety_policy(signals: dict) -> dict:
    rules = [
        "Do not read .env, .databrickscfg, ODBC config, PEM/key files, or local secret stores.",
        "Run repo-specific preflight/classify commands before live execution.",
        "Readonly discovery is allowed; writes, deploys, pipeline triggers, and production SQL require explicit approval.",
        "Prefer Microsoft Entra/managed identity/profile auth over PAT/token/password fallback.",
    ]
    if signals.get("databricks_bundle"):
        rules.append("Run Databricks Bundle Doctor before bundle deploys or reruns.")
    if signals.get("azure_pipelines"):
        rules.append("Run Pipeline Doctor before rerunning failed deployments.")
    if signals.get("sql") or signals.get("mssql_or_tsql"):
        rules.append("Classify SQL and require row-count/schema evidence before production mutations.")
    return {"status": "active", "rules": rules}


def build_interview(context: dict) -> dict:
    signals = context.get("signals", {})
    questions: list[dict[str, str]] = []

    def add(question_id: str, priority: str, question: str, reason: str) -> None:
        questions.append({
            "id": question_id,
            "priority": priority,
            "question": question,
            "reason": reason,
        })

    if "unknown" in context.get("repo_types", []):
        add(
            "repo-purpose",
            "high",
            "What is this repo mainly responsible for, and what should the agent never assume about it?",
            "The scanner could not classify the repo from files alone.",
        )

    add(
        "safe-default-environment",
        "high",
        "Which environment is safe for default live checks: local, dev, test, uat, or none without approval?",
        "Live Databricks, MSSQL, and ADO actions need an explicit safe default.",
    )
    add(
        "owner-and-escalation",
        "medium",
        "Who owns this repo and who should approve deploys, SQL mutations, or pipeline reruns?",
        "The package can block risky actions, but approval ownership is client-specific.",
    )

    if signals.get("azure_pipelines"):
        add(
            "ado-project-and-sprint",
            "high",
            "Which Azure DevOps organization/project/team/sprint should backlog and pipeline commands use by default?",
            "Azure Pipelines were detected, but ADO workspace defaults are not safe to infer.",
        )
        add(
            "pipeline-rerun-boundary",
            "high",
            "Which pipeline reruns are safe after Pipeline Doctor, and which require human approval?",
            "Pipeline reruns can affect deployments or shared environments.",
        )

    if signals.get("databricks_bundle"):
        add(
            "databricks-targets",
            "high",
            "Which Databricks bundle target/profile is safe for validate, deploy, and run commands?",
            "A Databricks bundle was detected, but target names do not reveal client approval boundaries.",
        )
        add(
            "unity-catalog-boundary",
            "medium",
            "Which catalogs/schemas/workspaces are dev-only, shared, or production governed?",
            "Unity Catalog and workspace boundaries determine safe SQL and deployment behavior.",
        )

    if signals.get("sql") or signals.get("mssql_or_tsql"):
        add(
            "sql-execution-boundary",
            "high",
            "Which MSSQL or SQL endpoints are read-only, and where are mutations forbidden without approval?",
            "SQL files were detected, so live query execution needs client-specific boundaries.",
        )
        add(
            "data-quality-evidence",
            "medium",
            "What row-count, schema, reconciliation, or sample evidence is expected before calling data work done?",
            "Quality evidence expectations vary by client and dataset.",
        )

    if signals.get("dbt"):
        add(
            "dbt-targets",
            "medium",
            "Which dbt targets, selectors, and schemas should the agent use for safe validation?",
            "dbt project settings do not prove which target is safe.",
        )

    if not signals.get("tests"):
        add(
            "verification-gap",
            "medium",
            "There are no obvious tests. What command or manual evidence proves a change is safe here?",
            "The scanner did not detect a test surface.",
        )

    if context.get("risk_zones"):
        add(
            "risk-zone-review",
            "medium",
            "Which detected risk-zone files are production-affecting, and which are safe development artifacts?",
            "File names suggest possible deploy, SQL mutation, notebook, or pipeline risk.",
        )

    add(
        "definition-of-done",
        "medium",
        "For this repo, what should be included in the final evidence pack before a PR or client handoff?",
        "Consulting delivery needs repeatable completion evidence.",
    )

    return {
        "status": "ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "repo-context",
        "instructions": "Ask these only after repo context has been initialized. Prefer the highest-priority unresolved questions.",
        "questions": questions,
    }


def build_next_actions(context: dict) -> dict:
    signals = context.get("signals", {})
    actions: list[dict[str, str]] = []

    def add(action_id: str, priority: str, action: str, reason: str, command: str = "") -> None:
        actions.append({
            "id": action_id,
            "priority": priority,
            "action": action,
            "reason": reason,
            "command": command,
        })

    add(
        "confirm-auth-posture",
        "high",
        "Confirm enterprise auth posture before live ADO, Databricks, or MSSQL use.",
        "The package can guard execution, but client auth setup is outside repo scanning.",
        "de auth",
    )
    add(
        "confirm-safe-environment",
        "high",
        "Answer the safe default environment question from repo interview.",
        "The agent must not infer dev/test/prod boundaries from file names.",
        "de repo interview --max-questions 3",
    )
    if "unknown" in context.get("repo_types", []):
        add(
            "explain-repo-purpose",
            "high",
            "Tell the agent what this repo is responsible for and what it must never assume.",
            "The scanner could not classify the repo confidently.",
            "de repo interview --max-questions 5",
        )
    if signals.get("azure_pipelines"):
        pipeline_cmds = context.get("commands", {}).get("pipeline", [])
        add(
            "pipeline-preflight",
            "high",
            "Run Pipeline Doctor before changing or rerunning Azure Pipelines.",
            "Pipeline YAML was detected and reruns can affect shared environments.",
            pipeline_cmds[0] if pipeline_cmds else "de pipeline preflight --pipeline-yaml azure-pipelines.yml",
        )
    if signals.get("databricks_bundle"):
        db_cmds = context.get("commands", {}).get("databricks", [])
        add(
            "databricks-bundle-check",
            "high",
            "Run Bundle Doctor before Databricks deploy/run work.",
            "Databricks bundle files were detected.",
            db_cmds[0] if db_cmds else "de databricks bundle-doctor --bundle-yaml databricks.yml",
        )
    if signals.get("sql") or signals.get("mssql_or_tsql"):
        add(
            "sql-safety-first",
            "high",
            "Classify SQL and check MSSQL policy before live query work.",
            "SQL assets were detected, so live execution needs explicit safety posture.",
            "de-mssql policy-check",
        )
    if not signals.get("tests"):
        add(
            "define-verification",
            "medium",
            "Define the test command or manual evidence expected for this repo.",
            "No obvious test surface was detected.",
            "de repo interview --max-questions 8",
        )
    if context.get("risk_zones"):
        add(
            "review-risk-zones",
            "medium",
            "Review detected risk-zone files and label which ones are production-affecting.",
            "File names suggest deploy, notebook, pipeline, production, or SQL mutation risk.",
            "de repo brief",
        )
    add(
        "read-compact-contract",
        "medium",
        "Use compact DE.md for behavior and lazy-read detailed context only when needed.",
        "This keeps the agent controlled without heavy always-loaded context.",
        "de repo contract",
    )
    return {
        "status": "ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "actions": actions[:10],
    }


def render_de_contract(context: dict) -> str:
    repo_types = ", ".join(context.get("repo_types", ["unknown"]))
    signals = [key for key, value in context.get("signals", {}).items() if value]
    signal_text = ", ".join(sorted(signals)) if signals else "none detected"
    commands = []
    for group, items in context.get("commands", {}).items():
        commands.extend(items[:2])
    command_lines = [f"- `{command}`" for command in commands[:8]] or ["- `de repo brief`"]
    return "\n".join([
        "# DE.md",
        "",
        "Compact data-engineering agent contract for this repository.",
        "",
        "## Repo Snapshot",
        "",
        f"- Repo: {context.get('repo_name', 'unknown')}",
        f"- Types: {repo_types}",
        f"- Signals: {signal_text}",
        "- Detailed context lives in `.de-opencode/repo-brief.md`; read it only when needed.",
        "",
        "## Operating Principles",
        "",
        "1. Think before touching data: identify system, environment, target data, auth mode, and blast radius before live action.",
        "2. Simplicity first: make the smallest safe change; do not add speculative abstractions, migrations, retries, or pipeline rewrites.",
        "3. Surgical changes: touch only files tied to the request; do not refactor unrelated SQL, notebooks, bundles, or pipeline code.",
        "4. Environment discipline: never assume dev, test, staging, or prod; ask when unclear and block risky live actions without approval.",
        "5. SQL safety: classify SQL before execution; read-only first; mutations need environment, approval, row-count/schema evidence, and rollback thinking.",
        "6. Pipeline safety: preflight YAML before rerun; diagnose logs before changing pipeline code; deploy/rerun only through approved commands.",
        "7. Databricks safety: validate bundles before deploy/run; prefer profile/OAuth/WIF auth; respect Unity Catalog boundaries.",
        "8. Evidence before done: report commands run, environment, result, evidence files, remaining risk, and what was not tested.",
        "",
        "## Safety Rules",
        "",
        "- Do not read `.env`, `.databrickscfg`, ODBC config, PEM/key files, or local secret stores.",
        "- Do not expose secrets, full connection strings, PATs, bearer tokens, client hostnames, or raw production data samples.",
        "- Use `de repo interview` only after repo context exists and only for high-value unresolved questions.",
        "- Use `de repo refresh` after major repo structure or pipeline changes.",
        "",
        "## Preferred Commands",
        "",
        *command_lines,
        "",
    ]).rstrip()


def write_artifacts(root: Path, context: dict, target: Optional[Path] = None, force: bool = True) -> dict[str, str]:
    target = target or root / CONTEXT_DIR
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "context": target / "repo-context.json",
        "brief": target / "repo-brief.md",
        "contract": target / "DE.md",
        "map": target / "repo-map.md",
        "map_json": target / "repo-map.json",
        "next_actions": target / "next-actions.md",
        "next_actions_json": target / "next-actions.json",
        "interview": target / "repo-interview.md",
        "interview_json": target / "repo-interview.json",
        "commands": target / "commands.json",
        "policy": target / "safety-policy.json",
    }
    paths["context"].write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    paths["brief"].write_text(render_brief(context) + "\n", encoding="utf-8")
    paths["contract"].write_text(render_de_contract(context) + "\n", encoding="utf-8")
    repo_map = build_repo_map(context)
    paths["map"].write_text(render_repo_map(repo_map) + "\n", encoding="utf-8")
    paths["map_json"].write_text(json.dumps(repo_map, indent=2) + "\n", encoding="utf-8")
    paths["next_actions"].write_text(render_next_actions(context) + "\n", encoding="utf-8")
    paths["next_actions_json"].write_text(json.dumps(context["next_actions"], indent=2) + "\n", encoding="utf-8")
    paths["interview"].write_text(render_interview(context) + "\n", encoding="utf-8")
    paths["interview_json"].write_text(json.dumps(context["interview"], indent=2) + "\n", encoding="utf-8")
    paths["commands"].write_text(json.dumps(context["commands"], indent=2) + "\n", encoding="utf-8")
    paths["policy"].write_text(json.dumps(context["safety_policy"], indent=2) + "\n", encoding="utf-8")
    return {key: rel(path, root) for key, path in paths.items()}


def render_brief(context: dict) -> str:
    lines = [
        f"# Repo Brief: {context['repo_name']}",
        "",
        f"Generated: {context['generated_at']}",
        "",
        "## Detected Shape",
        "",
        "- Types: " + ", ".join(context["repo_types"]),
        f"- Files scanned: {context['file_count_scanned']}",
        "- .env support: false",
        "",
        "## Important Files",
        "",
    ]
    for group, items in context["important_files"].items():
        if items:
            lines.append(f"### {group.title()}")
            lines.extend(f"- `{item}`" for item in items[:20])
            lines.append("")
    if context["risk_zones"]:
        lines += ["## Risk Zones", ""]
        for item in context["risk_zones"][:30]:
            lines.append(f"- {item['severity'].upper()}: `{item['path']}` ({item['id']})")
        lines.append("")
    if context.get("file_summaries"):
        lines += ["## Context Snippets", ""]
        for item in context["file_summaries"][:8]:
            lines.append(f"### `{item['path']}`")
            excerpt = str(item.get("excerpt", "")).strip()
            if excerpt:
                lines.append("```text")
                lines.append(excerpt[:1200])
                lines.append("```")
            lines.append("")
    lines += ["## Recommended Commands", ""]
    for group, commands in context["commands"].items():
        lines.append(f"### {group.title()}")
        lines.extend(f"- `{command}`" for command in commands)
        lines.append("")
    lines += ["## Safety Policy", ""]
    lines.extend(f"- {rule}" for rule in context["safety_policy"]["rules"])
    if context.get("interview", {}).get("questions"):
        lines += ["", "", "## Suggested Interview", ""]
        lines.append("- Run `de repo interview` after initialization to ask targeted repo questions.")
    if context.get("next_actions", {}).get("actions"):
        lines += ["", "", "## Next Actions", ""]
        lines.append("- Run `de repo todo` for the short repo-specific action list.")
    return "\n".join(lines).rstrip()


def render_next_actions(context: dict) -> str:
    next_actions = context.get("next_actions") or build_next_actions(context)
    lines = [
        f"# Repo Next Actions: {context['repo_name']}",
        "",
        f"Generated: {next_actions.get('generated_at', context.get('generated_at', 'unknown'))}",
        "",
        "Short, repo-specific actions only. Keep detailed analysis in `repo-brief.md`.",
        "",
    ]
    for item in next_actions.get("actions", []):
        lines.append(f"## {item['id']} ({item['priority']})")
        lines.append("")
        lines.append(item["action"])
        lines.append("")
        lines.append(f"Why: {item['reason']}")
        if item.get("command"):
            lines.append("")
            lines.append(f"Command: `{item['command']}`")
        lines.append("")
    return "\n".join(lines).rstrip()


def build_repo_map(context: dict) -> dict:
    important = context.get("important_files", {})
    return {
        "status": "ok",
        "repo_name": context.get("repo_name"),
        "scope": context.get("scope"),
        "generated_at": context.get("generated_at"),
        "repo_types": context.get("repo_types", []),
        "domains": {
            "pipelines": important.get("pipelines", []),
            "databricks": important.get("databricks", []),
            "sql": important.get("sql", []),
            "notebooks": important.get("notebooks", []),
            "tests": important.get("tests", []),
            "config": important.get("config", []),
        },
        "risk_zones": context.get("risk_zones", [])[:30],
        "recommended_commands": context.get("commands", {}),
    }


def render_repo_map(repo_map: dict) -> str:
    scope = repo_map.get("scope") or {}
    title = f"# DE Repo Map: {repo_map.get('repo_name', 'unknown')}"
    if scope.get("name"):
        title += f" ({scope['name']})"
    lines = [title, "", f"Generated: {repo_map.get('generated_at', 'unknown')}", ""]
    lines += ["## Domains", ""]
    for domain, items in repo_map.get("domains", {}).items():
        if not items:
            continue
        lines.append(f"### {domain.title()}")
        lines.extend(f"- `{item}`" for item in items[:30])
        lines.append("")
    if repo_map.get("risk_zones"):
        lines += ["## Risk Zones", ""]
        for item in repo_map["risk_zones"]:
            lines.append(f"- {item.get('severity', '').upper()}: `{item.get('path')}` ({item.get('id')})")
        lines.append("")
    if repo_map.get("recommended_commands"):
        lines += ["## Commands", ""]
        for group, commands in repo_map["recommended_commands"].items():
            lines.append(f"### {group.title()}")
            lines.extend(f"- `{command}`" for command in commands)
            lines.append("")
    return "\n".join(lines).rstrip()


def render_interview(context: dict, max_questions: Optional[int] = None) -> str:
    interview = context.get("interview") or build_interview(context)
    questions = interview.get("questions", [])
    if max_questions:
        questions = questions[:max_questions]
    lines = [
        f"# Repo Interview: {context['repo_name']}",
        "",
        f"Generated: {interview.get('generated_at', context.get('generated_at', 'unknown'))}",
        "",
        "Use these questions only after `de repo init` has generated repo context. Ask the highest-priority unanswered questions first.",
        "",
    ]
    if not questions:
        lines.append("No interview questions were generated.")
        return "\n".join(lines)
    for item in questions:
        lines.append(f"## {item['id']} ({item['priority']})")
        lines.append("")
        lines.append(item["question"])
        lines.append("")
        lines.append(f"Why: {item['reason']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def sanitize_scope_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip(".-")
    if not cleaned:
        raise ValueError("scope name cannot be empty")
    return cleaned[:80]


def context_dir(root: Path, scope: Optional[str] = None) -> Path:
    if scope:
        return root / CONTEXT_DIR / "scopes" / sanitize_scope_name(scope)
    return root / CONTEXT_DIR


def scopes_path(root: Path) -> Path:
    return root / CONTEXT_DIR / SCOPES_FILE


def load_scopes(root: Path) -> dict:
    path = scopes_path(root)
    if not path.exists():
        return {"status": "ok", "active": "", "scopes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "error", "active": "", "scopes": {}}
    data.setdefault("active", "")
    data.setdefault("scopes", {})
    return data


def save_scopes(root: Path, data: dict) -> None:
    path = scopes_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def resolve_scope(root: Path, explicit: Optional[str], global_context: bool = False) -> Optional[str]:
    if global_context:
        return None
    if explicit:
        return sanitize_scope_name(explicit)
    active = load_scopes(root).get("active", "")
    return sanitize_scope_name(active) if active else None


def scope_info(root: Path, scope: Optional[str]) -> Optional[dict]:
    if not scope:
        return None
    return load_scopes(root).get("scopes", {}).get(scope)


def load_context(root: Path, scope: Optional[str] = None) -> Optional[dict]:
    path = context_dir(root, scope) / "repo-context.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def resolve_root(value: Optional[str]) -> Path:
    if value:
        return Path(value).resolve()
    start = Path(os.getcwd()).resolve()
    return git_root(start) or start


def cmd_init(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    result = initialize_context(root, args.max_files, scope)
    print(json.dumps(result, indent=2))
    return 0


def initialize_context(root: Path, max_files: int, scope: Optional[str] = None) -> dict:
    info = scope_info(root, scope)
    include_paths = info.get("paths", []) if info else None
    files = iter_repo_files(root, max_files, include_paths)
    context = detect_repo(root, files)
    if scope:
        context["scope"] = {"name": scope, "paths": include_paths or []}
    context["interview"] = build_interview(context)
    context["next_actions"] = build_next_actions(context)
    artifacts = write_artifacts(root, context, context_dir(root, scope))
    result = {"status": "ok", "root": str(root), "scope": scope or "", "artifacts": artifacts, "summary": summary(context)}
    if scope and not info:
        result["warnings"] = [f"Scope '{scope}' is not defined; scanned full repo. Use `de repo scope add --name {scope} --path <path>`."]
    return result


def cmd_doctor(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    base = context_dir(root, scope)
    context = load_context(root, scope)
    issues = []
    warnings = []
    if context is None:
        issues.append("Repo context not initialized. Run `de repo init`.")
    else:
        for name in ("repo-brief.md", "DE.md", "repo-map.md", "repo-map.json", "next-actions.md", "next-actions.json", "repo-interview.md", "repo-interview.json", "commands.json", "safety-policy.json"):
            if not (base / name).exists():
                issues.append(f"Missing {rel(base / name, root)}. Run `de repo refresh`.")
        warnings.extend(freshness_warnings(root, context))
    agents_md = root / "AGENTS.md"
    result = {
        "status": "ok" if not issues else "needs-init",
        "root": str(root),
        "scope": scope or "",
        "issues": issues,
        "warnings": warnings,
        "context_dir": str(base),
        "agents_md_installed": agents_md.exists() and "de-opencode repo context" in agents_md.read_text(encoding="utf-8", errors="ignore"),
    }
    print(json.dumps(result, indent=2))
    return 1 if issues and args.strict else 0


def freshness_warnings(root: Path, context: dict) -> list[str]:
    warnings = []
    generated = parse_dt(context.get("generated_at", ""))
    if generated:
        age_days = (datetime.now(timezone.utc) - generated).days
        if age_days > FRESHNESS_DAYS:
            warnings.append(f"Repo context is {age_days} days old; run `de repo refresh` or `de repo reset`.")
    git = context.get("git", {})
    current = git_metadata(root)
    if git.get("branch") and current.get("branch") and git.get("branch") != current.get("branch"):
        warnings.append(f"Git branch changed from {git.get('branch')} to {current.get('branch')}; consider `de repo reset`.")
    if generated:
        for group, paths in context.get("important_files", {}).items():
            for item in paths[:20]:
                path = root / item
                try:
                    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                except OSError:
                    continue
                if modified > generated:
                    warnings.append(f"Important {group} file changed after context init: {item}")
                    return warnings
    return warnings


def parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def cmd_reset(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    base = context_dir(root, scope)
    reset_result = reset_context_dir(root, base, args.force, args.archive_dir, scope)
    init_result = None if args.no_init else initialize_context(root, args.max_files, scope)
    result = {
        "status": "ok",
        "root": str(root),
        "scope": scope or "",
        "context_dir": str(base),
        "reset": reset_result,
        "reinitialized": init_result is not None,
    }
    if init_result:
        result["artifacts"] = init_result["artifacts"]
        result["summary"] = init_result["summary"]
    print(json.dumps(result, indent=2))
    return 0


def reset_context_dir(root: Path, base: Path, force: bool, archive_dir: Optional[str], scope: Optional[str] = None) -> dict:
    label = rel(base, root)
    if not base.exists():
        return {"mode": "none", "message": f"{label} did not exist; nothing to remove"}
    if force:
        shutil.rmtree(base)
        return {"mode": "deleted", "path": str(base), "scope": scope or ""}
    archive_root = Path(archive_dir).resolve() if archive_dir else root / ARCHIVE_DIR / (scope or "global")
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = archive_root / f"de-opencode-{stamp}"
    suffix = 1
    while target.exists():
        suffix += 1
        target = archive_root / f"de-opencode-{stamp}-{suffix}"
    shutil.move(str(base), str(target))
    return {"mode": "archived", "path": str(target), "scope": scope or ""}


def cmd_brief(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    context = load_context(root, scope)
    if context is None:
        print("Repo context not initialized. Run `de repo init`.")
        return 1
    text = render_brief(context)
    if args.format == "json":
        print(json.dumps(context, indent=2))
    else:
        print(text)
    return 0


def cmd_json_artifact(args: argparse.Namespace, key: str) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    context = load_context(root, scope)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init`."}, indent=2))
        return 1
    print(json.dumps(context[key], indent=2))
    return 0


def cmd_interview(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    context = load_context(root, scope)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init` before interviewing the user."}, indent=2))
        return 1
    if "interview" not in context:
        context["interview"] = build_interview(context)
    max_questions = args.max_questions if args.max_questions and args.max_questions > 0 else None
    questions = context["interview"].get("questions", [])
    if max_questions:
        questions = questions[:max_questions]
    data = {
        "status": "ok",
        "root": str(root),
        "scope": scope or "",
        "question_count": len(questions),
        "instructions": context["interview"].get("instructions", ""),
        "questions": questions,
    }
    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        print(render_interview({**context, "interview": {**context["interview"], "questions": questions}}))
    return 0


def cmd_todo(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    context = load_context(root, scope)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init` before generating repo next actions."}, indent=2))
        return 1
    if "next_actions" not in context:
        context["next_actions"] = build_next_actions(context)
    data = {
        "status": "ok",
        "root": str(root),
        "scope": scope or "",
        "action_count": len(context["next_actions"].get("actions", [])),
        "actions": context["next_actions"].get("actions", []),
    }
    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        print(render_next_actions(context))
    return 0


def cmd_contract(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    context = load_context(root, scope)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init` before generating the data-engineering contract."}, indent=2))
        return 1
    text = render_de_contract(context)
    if args.format == "json":
        print(json.dumps({
            "status": "ok",
            "root": str(root),
            "scope": scope or "",
            "path": rel(context_dir(root, scope) / "DE.md", root),
            "line_count": len(text.splitlines()),
            "contract": text,
        }, indent=2))
    else:
        print(text)
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    context = load_context(root, scope)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init` before generating the repo map."}, indent=2))
        return 1
    repo_map = build_repo_map(context)
    if args.format == "json":
        print(json.dumps(repo_map, indent=2))
    else:
        print(render_repo_map(repo_map))
    return 0


def cmd_scope(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    data = load_scopes(root)
    if args.scope_command == "add":
        name = sanitize_scope_name(args.name)
        paths = []
        for item in args.path:
            path = (root / item).resolve()
            try:
                paths.append(rel(path, root))
            except ValueError:
                print(json.dumps({"status": "blocked", "message": f"Scope path must stay inside repo root: {item}"}, indent=2))
                return 1
        data["scopes"][name] = {
            "name": name,
            "paths": paths,
            "created_at": data.get("scopes", {}).get(name, {}).get("created_at") or datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if args.use or not data.get("active"):
            data["active"] = name
        save_scopes(root, data)
        print(json.dumps({"status": "ok", "root": str(root), "active": data.get("active", ""), "scope": data["scopes"][name]}, indent=2))
        return 0
    if args.scope_command == "list":
        print(json.dumps({"status": "ok", "root": str(root), "active": data.get("active", ""), "scopes": list(data.get("scopes", {}).values())}, indent=2))
        return 0
    if args.scope_command == "use":
        name = sanitize_scope_name(args.name)
        if name not in data.get("scopes", {}):
            print(json.dumps({"status": "missing", "message": f"Scope '{name}' is not defined."}, indent=2))
            return 1
        data["active"] = name
        save_scopes(root, data)
        print(json.dumps({"status": "ok", "active": name, "scope": data["scopes"][name]}, indent=2))
        return 0
    if args.scope_command == "current":
        active = data.get("active", "")
        print(json.dumps({"status": "ok", "active": active, "scope": data.get("scopes", {}).get(active, {}) if active else {}}, indent=2))
        return 0
    if args.scope_command == "remove":
        name = sanitize_scope_name(args.name)
        removed = data.get("scopes", {}).pop(name, None)
        if data.get("active") == name:
            data["active"] = ""
        save_scopes(root, data)
        print(json.dumps({"status": "ok" if removed else "missing", "removed": bool(removed), "scope": name}, indent=2))
        return 0 if removed else 1
    raise AssertionError(f"Unhandled scope command: {args.scope_command}")


def cmd_archives(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    archives = list_archives(root, getattr(args, "scope", None))
    print(json.dumps({"status": "ok", "root": str(root), "archives": archives}, indent=2))
    return 0


def list_archives(root: Path, scope: Optional[str] = None) -> list[dict]:
    base = root / ARCHIVE_DIR
    if scope:
        base = base / sanitize_scope_name(scope)
    if not base.exists():
        return []
    archives = []
    for path in sorted(base.rglob("repo-context.json"), reverse=True):
        archive = path.parent
        context = load_json_file(path)
        archives.append({
            "name": archive.name,
            "path": str(archive),
            "scope": context.get("scope", {}).get("name", ""),
            "generated_at": context.get("generated_at", ""),
            "repo_types": context.get("repo_types", []),
        })
    return archives


def cmd_restore(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    archive = resolve_archive(root, args.archive, scope)
    if not archive:
        print(json.dumps({"status": "missing", "message": "Archive not found."}, indent=2))
        return 1
    base = context_dir(root, scope)
    backup = reset_context_dir(root, base, False, None, scope) if base.exists() else {"mode": "none"}
    base.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(archive, base, dirs_exist_ok=True)
    print(json.dumps({"status": "ok", "root": str(root), "scope": scope or "", "restored_from": str(archive), "previous_context": backup}, indent=2))
    return 0


def resolve_archive(root: Path, value: str, scope: Optional[str]) -> Optional[Path]:
    if value == "latest":
        archives = list_archives(root, scope)
        return Path(archives[0]["path"]) if archives else None
    path = Path(value)
    if path.exists():
        return path
    for item in list_archives(root, scope):
        if item["name"] == value:
            return Path(item["path"])
    return None


def cmd_diff(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    current = load_context(root, scope)
    archive_path = resolve_archive(root, args.archive, scope)
    archived = load_json_file(archive_path / "repo-context.json") if archive_path else {}
    if not current or not archived:
        print(json.dumps({"status": "missing", "message": "Current context or archive context is missing."}, indent=2))
        return 1
    diff = context_diff(archived, current)
    if args.format == "json":
        print(json.dumps(diff, indent=2))
    else:
        print(render_context_diff(diff))
    return 0


def load_json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def context_diff(old: dict, new: dict) -> dict:
    return {
        "status": "ok",
        "old_generated_at": old.get("generated_at", ""),
        "new_generated_at": new.get("generated_at", ""),
        "repo_types": diff_lists(old.get("repo_types", []), new.get("repo_types", [])),
        "signals": diff_lists(active_signal_names(old), active_signal_names(new)),
        "risk_zones": diff_lists([item.get("path", "") for item in old.get("risk_zones", [])], [item.get("path", "") for item in new.get("risk_zones", [])]),
        "important_files": {
            key: diff_lists(old.get("important_files", {}).get(key, []), new.get("important_files", {}).get(key, []))
            for key in sorted(set(old.get("important_files", {})) | set(new.get("important_files", {})))
        },
    }


def active_signal_names(context: dict) -> list[str]:
    return sorted(key for key, value in context.get("signals", {}).items() if value)


def diff_lists(old: list[str], new: list[str]) -> dict:
    return {"added": sorted(set(new) - set(old)), "removed": sorted(set(old) - set(new)), "unchanged_count": len(set(old) & set(new))}


def render_context_diff(diff: dict) -> str:
    lines = ["# Repo Context Diff", "", f"Old: {diff.get('old_generated_at')}", f"New: {diff.get('new_generated_at')}", ""]
    for title, key in [("Repo Types", "repo_types"), ("Signals", "signals"), ("Risk Zones", "risk_zones")]:
        item = diff.get(key, {})
        lines += [f"## {title}", ""]
        lines += [f"- added: {', '.join(item.get('added', [])) or 'none'}", f"- removed: {', '.join(item.get('removed', [])) or 'none'}", ""]
    lines += ["## Important Files", ""]
    for group, item in diff.get("important_files", {}).items():
        if item.get("added") or item.get("removed"):
            lines.append(f"### {group}")
            lines.append(f"- added: {', '.join(item.get('added', [])) or 'none'}")
            lines.append(f"- removed: {', '.join(item.get('removed', [])) or 'none'}")
            lines.append("")
    return "\n".join(lines).rstrip()


def cmd_install_contract(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    context = load_context(root, scope)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init` first."}, indent=2))
        return 1
    target_name = "CLAUDE.md" if args.target == "claude" else "AGENTS.md"
    target = root / target_name
    if target.exists() and not args.force:
        print(json.dumps({"status": "blocked", "message": f"{target_name} already exists. Use --force to overwrite or edit manually."}, indent=2))
        return 1
    text = render_de_contract(context)
    if args.target == "agents":
        text = render_agents_md(context, contract=text)
    target.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "path": target_name}, indent=2))
    return 0


def cmd_install_agents_md(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    scope = resolve_scope(root, getattr(args, "scope", None), getattr(args, "global_context", False))
    context = load_context(root, scope)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init` first."}, indent=2))
        return 1
    target = root / "AGENTS.md"
    if target.exists() and not args.force:
        print(json.dumps({"status": "blocked", "message": "AGENTS.md already exists. Use --force to overwrite or edit manually."}, indent=2))
        return 1
    target.write_text(render_agents_md(context), encoding="utf-8")
    print(json.dumps({"status": "ok", "path": "AGENTS.md"}, indent=2))
    return 0


def render_agents_md(context: dict, contract: Optional[str] = None) -> str:
    commands = []
    for group, items in context["commands"].items():
        commands.extend(items[:3])
    contract_text = contract or render_de_contract(context)
    return "\n".join([
        "# AGENTS.md",
        "",
        "This repository uses de-opencode repo context.",
        "",
        "## Data Engineering Contract",
        "",
        contract_text,
        "",
        "Before making data-engineering changes:",
        "",
        "- Follow the data-engineering contract above.",
        "- Read `.de-opencode/repo-brief.md`.",
        "- Use `.de-opencode/safety-policy.json` for approval and secret-handling rules.",
        "- Prefer `de repo doctor`, `de repo brief`, and the recommended commands below.",
        "- Do not read `.env`, `.databrickscfg`, ODBC config, PEM/key files, or local secret stores.",
        "- Classify SQL and preflight pipelines before live actions.",
        "",
        "Recommended commands:",
        "",
        *[f"- `{command}`" for command in commands[:12]],
        "",
    ])


def summary(context: dict) -> dict:
    return {
        "repo_name": context["repo_name"],
        "repo_types": context["repo_types"],
        "signals": {key: value for key, value in context["signals"].items() if value},
        "risk_count": len(context["risk_zones"]),
        "next_commands": ["de repo contract", "de repo brief", "de repo todo", "de repo interview", "de repo doctor", "de repo commands", "de repo reset"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize and inspect repo-local de-opencode context")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_root(target: argparse.ArgumentParser) -> None:
        target.add_argument("--root", help="Repo root; defaults to current git root or cwd")

    def add_scope(target: argparse.ArgumentParser) -> None:
        target.add_argument("--scope", help="Named repo scope; defaults to active scope when set")
        target.add_argument("--global-context", action="store_true", help="Ignore active scope and use global repo context")

    init = sub.add_parser("init", help="Create .de-opencode repo context artifacts")
    add_root(init)
    add_scope(init)
    init.add_argument("--max-files", type=int, default=2000)
    init.set_defaults(func=cmd_init)
    refresh = sub.add_parser("refresh", help="Refresh .de-opencode repo context artifacts")
    add_root(refresh)
    add_scope(refresh)
    refresh.add_argument("--max-files", type=int, default=2000)
    refresh.set_defaults(func=cmd_init)
    reset = sub.add_parser("reset", help="Archive or delete .de-opencode and reinitialize repo context")
    add_root(reset)
    add_scope(reset)
    reset.add_argument("--max-files", type=int, default=2000)
    reset.add_argument("--archive-dir", help="Archive parent directory; defaults to .de-opencode-archive")
    reset.add_argument("--force", action="store_true", help="Delete .de-opencode instead of archiving it")
    reset.add_argument("--no-init", action="store_true", help="Only remove/archive context; do not create fresh context")
    reset.set_defaults(func=cmd_reset)
    doctor = sub.add_parser("doctor", help="Check repo context health")
    add_root(doctor)
    add_scope(doctor)
    doctor.add_argument("--strict", action="store_true")
    doctor.set_defaults(func=cmd_doctor)
    brief = sub.add_parser("brief", help="Print repo brief")
    add_root(brief)
    add_scope(brief)
    brief.add_argument("--format", choices=["markdown", "json"], default="markdown")
    brief.set_defaults(func=cmd_brief)
    contract = sub.add_parser("contract", help="Print compact data-engineering agent contract")
    add_root(contract)
    add_scope(contract)
    contract.add_argument("--format", choices=["markdown", "json"], default="markdown")
    contract.set_defaults(func=cmd_contract)
    repo_map = sub.add_parser("map", help="Print compact data-engineering repo map")
    add_root(repo_map)
    add_scope(repo_map)
    repo_map.add_argument("--format", choices=["markdown", "json"], default="markdown")
    repo_map.set_defaults(func=cmd_map)
    todo = sub.add_parser("todo", help="Print short repo-specific next actions")
    add_root(todo)
    add_scope(todo)
    todo.add_argument("--format", choices=["markdown", "json"], default="markdown")
    todo.set_defaults(func=cmd_todo)
    interview = sub.add_parser("interview", help="Print initialized repo-specific user interview questions")
    add_root(interview)
    add_scope(interview)
    interview.add_argument("--format", choices=["markdown", "json"], default="markdown")
    interview.add_argument("--max-questions", type=int, default=0)
    interview.set_defaults(func=cmd_interview)
    commands = sub.add_parser("commands", help="Print detected repo commands")
    add_root(commands)
    add_scope(commands)
    commands.set_defaults(func=lambda args: cmd_json_artifact(args, "commands"))
    policy = sub.add_parser("policy", help="Print detected repo safety policy")
    add_root(policy)
    add_scope(policy)
    policy.set_defaults(func=lambda args: cmd_json_artifact(args, "safety_policy"))
    scope = sub.add_parser("scope", help="Manage named repo scopes for integration repos")
    scope_sub = scope.add_subparsers(dest="scope_command", required=True)
    scope_add = scope_sub.add_parser("add", help="Add or update a named repo scope")
    add_root(scope_add)
    scope_add.add_argument("--name", required=True)
    scope_add.add_argument("--path", action="append", required=True)
    scope_add.add_argument("--use", action="store_true")
    scope_add.set_defaults(func=cmd_scope)
    scope_list = scope_sub.add_parser("list", help="List repo scopes")
    add_root(scope_list)
    scope_list.set_defaults(func=cmd_scope)
    scope_use = scope_sub.add_parser("use", help="Set active repo scope")
    add_root(scope_use)
    scope_use.add_argument("name")
    scope_use.set_defaults(func=cmd_scope)
    scope_current = scope_sub.add_parser("current", help="Show active repo scope")
    add_root(scope_current)
    scope_current.set_defaults(func=cmd_scope)
    scope_remove = scope_sub.add_parser("remove", help="Remove a repo scope definition")
    add_root(scope_remove)
    scope_remove.add_argument("name")
    scope_remove.set_defaults(func=cmd_scope)
    archives = sub.add_parser("archives", help="List archived repo contexts")
    add_root(archives)
    archives.add_argument("--scope")
    archives.set_defaults(func=cmd_archives)
    restore = sub.add_parser("restore", help="Restore an archived repo context")
    add_root(restore)
    add_scope(restore)
    restore.add_argument("--archive", default="latest")
    restore.set_defaults(func=cmd_restore)
    diff = sub.add_parser("diff", help="Compare current repo context with an archive")
    add_root(diff)
    add_scope(diff)
    diff.add_argument("--archive", default="latest")
    diff.add_argument("--format", choices=["markdown", "json"], default="markdown")
    diff.set_defaults(func=cmd_diff)
    agents = sub.add_parser("install-agents-md", help="Opt-in AGENTS.md generation from repo context")
    add_root(agents)
    add_scope(agents)
    agents.add_argument("--force", action="store_true")
    agents.set_defaults(func=cmd_install_agents_md)
    install_contract = sub.add_parser("install-contract", help="Opt-in export of the compact DE contract to AGENTS.md or CLAUDE.md")
    add_root(install_contract)
    add_scope(install_contract)
    install_contract.add_argument("--target", choices=["agents", "claude"], default="agents")
    install_contract.add_argument("--force", action="store_true")
    install_contract.set_defaults(func=cmd_install_contract)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
