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
    ".de-opencode-archive",
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


def iter_repo_files(root: Path, max_files: int) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
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


def git_root(start: Path) -> Optional[Path]:
    try:
        result = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], text=True, capture_output=True, timeout=5)
    except Exception:
        return None
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return None


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


def write_artifacts(root: Path, context: dict, force: bool = True) -> dict[str, str]:
    target = root / CONTEXT_DIR
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "context": target / "repo-context.json",
        "brief": target / "repo-brief.md",
        "contract": target / "DE.md",
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


def load_context(root: Path) -> Optional[dict]:
    path = root / CONTEXT_DIR / "repo-context.json"
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
    result = initialize_context(root, args.max_files)
    print(json.dumps(result, indent=2))
    return 0


def initialize_context(root: Path, max_files: int) -> dict:
    files = iter_repo_files(root, max_files)
    context = detect_repo(root, files)
    context["interview"] = build_interview(context)
    context["next_actions"] = build_next_actions(context)
    artifacts = write_artifacts(root, context)
    return {"status": "ok", "root": str(root), "artifacts": artifacts, "summary": summary(context)}


def cmd_doctor(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    context = load_context(root)
    issues = []
    if context is None:
        issues.append("Repo context not initialized. Run `de repo init`.")
    else:
        for name in ("repo-brief.md", "DE.md", "next-actions.md", "next-actions.json", "repo-interview.md", "repo-interview.json", "commands.json", "safety-policy.json"):
            if not (root / CONTEXT_DIR / name).exists():
                issues.append(f"Missing {CONTEXT_DIR}/{name}. Run `de repo refresh`.")
    agents_md = root / "AGENTS.md"
    result = {
        "status": "ok" if not issues else "needs-init",
        "root": str(root),
        "issues": issues,
        "context_dir": str(root / CONTEXT_DIR),
        "agents_md_installed": agents_md.exists() and "de-opencode repo context" in agents_md.read_text(encoding="utf-8", errors="ignore"),
    }
    print(json.dumps(result, indent=2))
    return 1 if issues and args.strict else 0


def cmd_reset(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    context_dir = root / CONTEXT_DIR
    reset_result = reset_context_dir(root, context_dir, args.force, args.archive_dir)
    init_result = None if args.no_init else initialize_context(root, args.max_files)
    result = {
        "status": "ok",
        "root": str(root),
        "context_dir": str(context_dir),
        "reset": reset_result,
        "reinitialized": init_result is not None,
    }
    if init_result:
        result["artifacts"] = init_result["artifacts"]
        result["summary"] = init_result["summary"]
    print(json.dumps(result, indent=2))
    return 0


def reset_context_dir(root: Path, context_dir: Path, force: bool, archive_dir: Optional[str]) -> dict:
    if not context_dir.exists():
        return {"mode": "none", "message": ".de-opencode did not exist; nothing to remove"}
    if force:
        shutil.rmtree(context_dir)
        return {"mode": "deleted", "path": str(context_dir)}
    archive_root = Path(archive_dir).resolve() if archive_dir else root / ".de-opencode-archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = archive_root / f"de-opencode-{stamp}"
    suffix = 1
    while target.exists():
        suffix += 1
        target = archive_root / f"de-opencode-{stamp}-{suffix}"
    shutil.move(str(context_dir), str(target))
    return {"mode": "archived", "path": str(target)}


def cmd_brief(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    context = load_context(root)
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
    context = load_context(root)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init`."}, indent=2))
        return 1
    print(json.dumps(context[key], indent=2))
    return 0


def cmd_interview(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    context = load_context(root)
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
    context = load_context(root)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init` before generating repo next actions."}, indent=2))
        return 1
    if "next_actions" not in context:
        context["next_actions"] = build_next_actions(context)
    data = {
        "status": "ok",
        "root": str(root),
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
    context = load_context(root)
    if context is None:
        print(json.dumps({"status": "needs-init", "message": "Run `de repo init` before generating the data-engineering contract."}, indent=2))
        return 1
    text = render_de_contract(context)
    if args.format == "json":
        print(json.dumps({
            "status": "ok",
            "root": str(root),
            "path": f"{CONTEXT_DIR}/DE.md",
            "line_count": len(text.splitlines()),
            "contract": text,
        }, indent=2))
    else:
        print(text)
    return 0


def cmd_install_contract(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    context = load_context(root)
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
    context = load_context(root)
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

    init = sub.add_parser("init", help="Create .de-opencode repo context artifacts")
    add_root(init)
    init.add_argument("--max-files", type=int, default=2000)
    init.set_defaults(func=cmd_init)
    refresh = sub.add_parser("refresh", help="Refresh .de-opencode repo context artifacts")
    add_root(refresh)
    refresh.add_argument("--max-files", type=int, default=2000)
    refresh.set_defaults(func=cmd_init)
    reset = sub.add_parser("reset", help="Archive or delete .de-opencode and reinitialize repo context")
    add_root(reset)
    reset.add_argument("--max-files", type=int, default=2000)
    reset.add_argument("--archive-dir", help="Archive parent directory; defaults to .de-opencode-archive")
    reset.add_argument("--force", action="store_true", help="Delete .de-opencode instead of archiving it")
    reset.add_argument("--no-init", action="store_true", help="Only remove/archive context; do not create fresh context")
    reset.set_defaults(func=cmd_reset)
    doctor = sub.add_parser("doctor", help="Check repo context health")
    add_root(doctor)
    doctor.add_argument("--strict", action="store_true")
    doctor.set_defaults(func=cmd_doctor)
    brief = sub.add_parser("brief", help="Print repo brief")
    add_root(brief)
    brief.add_argument("--format", choices=["markdown", "json"], default="markdown")
    brief.set_defaults(func=cmd_brief)
    contract = sub.add_parser("contract", help="Print compact data-engineering agent contract")
    add_root(contract)
    contract.add_argument("--format", choices=["markdown", "json"], default="markdown")
    contract.set_defaults(func=cmd_contract)
    todo = sub.add_parser("todo", help="Print short repo-specific next actions")
    add_root(todo)
    todo.add_argument("--format", choices=["markdown", "json"], default="markdown")
    todo.set_defaults(func=cmd_todo)
    interview = sub.add_parser("interview", help="Print initialized repo-specific user interview questions")
    add_root(interview)
    interview.add_argument("--format", choices=["markdown", "json"], default="markdown")
    interview.add_argument("--max-questions", type=int, default=0)
    interview.set_defaults(func=cmd_interview)
    commands = sub.add_parser("commands", help="Print detected repo commands")
    add_root(commands)
    commands.set_defaults(func=lambda args: cmd_json_artifact(args, "commands"))
    policy = sub.add_parser("policy", help="Print detected repo safety policy")
    add_root(policy)
    policy.set_defaults(func=lambda args: cmd_json_artifact(args, "safety_policy"))
    agents = sub.add_parser("install-agents-md", help="Opt-in AGENTS.md generation from repo context")
    add_root(agents)
    agents.add_argument("--force", action="store_true")
    agents.set_defaults(func=cmd_install_agents_md)
    install_contract = sub.add_parser("install-contract", help="Opt-in export of the compact DE contract to AGENTS.md or CLAUDE.md")
    add_root(install_contract)
    install_contract.add_argument("--target", choices=["agents", "claude"], default="agents")
    install_contract.add_argument("--force", action="store_true")
    install_contract.set_defaults(func=cmd_install_contract)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
