#!/usr/bin/env python3
"""Security/package assertions for the de-opencode control plane."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    config = json.loads(read("opencode.json"))
    permissions = config["permission"]

    assert permissions["*"] == "ask"
    assert permissions["read"]["*.env"] == "deny"
    assert permissions["read"]["*.env.*"] == "deny"
    assert permissions["read"][".databrickscfg"] == "deny"
    assert permissions["edit"] == "allow"
    assert permissions["todowrite"] == "allow"
    assert permissions["task"]["*"] == "deny"
    assert permissions["task"]["data-architect"] == "ask"
    assert permissions["task"]["data-devops"] == "ask"
    assert permissions["de_databricks_bundle_doctor"] == "allow"
    assert permissions["de_databricks_runtime_advisor"] == "allow"
    assert permissions["de_config_auth"] == "allow"
    assert permissions["de_repo_init"] == "allow"
    assert permissions["de_repo_scope"] == "allow"
    assert permissions["de_repo_reset"] == "allow"
    assert permissions["de_repo_map"] == "allow"
    assert permissions["de_repo_archives"] == "allow"
    assert permissions["de_repo_diff"] == "allow"
    assert permissions["de_repo_doctor"] == "allow"
    assert permissions["de_repo_brief"] == "allow"
    assert permissions["de_repo_contract"] == "allow"
    assert permissions["de_repo_todo"] == "allow"
    assert permissions["de_repo_interview"] == "allow"
    assert permissions["de_workbench_catalog"] == "allow"
    assert permissions["de_workbench_capabilities"] == "allow"
    assert permissions["de_workbench_route"] == "allow"
    assert permissions["de_workbench_ado_refine"] == "allow"
    assert permissions["de_workbench_ado_bulk_preview"] == "allow"
    assert permissions["de_workbench_mssql_assess"] == "allow"
    assert permissions["de_quality_verdict"] == "allow"
    assert permissions["de_quality_reconcile"] == "allow"
    assert permissions["bash"]["databricks bundle deploy*"] == "ask"
    assert permissions["bash"]["sqlcmd *"] == "ask"
    assert permissions["bash"]["mssql-client execute-*"] == "ask"
    assert permissions["bash"]["de doctor*"] == "allow"
    assert permissions["bash"]["de pipeline doctor *"] == "allow"
    assert permissions["bash"]["de demo pipeline-doctor*"] == "allow"
    assert permissions["bash"]["de databricks bundle-doctor *"] == "allow"
    assert permissions["bash"]["de-databricks runtime-advisor *"] == "allow"
    assert permissions["bash"]["de databricks sql execute *"] == "allow"
    assert permissions["bash"]["de ado query *"] == "allow"
    assert permissions["bash"]["de mssql query *"] == "allow"
    assert permissions["bash"]["de ado bulk preview *"] == "allow"
    assert permissions["bash"]["de security checklist*"] == "allow"
    assert permissions["bash"]["de done *"] == "allow"
    assert permissions["bash"]["de quality verdict *"] == "allow"
    assert permissions["bash"]["de auth*"] == "allow"
    assert permissions["bash"]["de repo init*"] == "allow"
    assert permissions["bash"]["de repo reset*"] == "allow"
    assert permissions["bash"]["de repo scope*"] == "allow"
    assert permissions["bash"]["de repo map*"] == "allow"
    assert permissions["bash"]["de repo archives*"] == "allow"
    assert permissions["bash"]["de repo diff*"] == "allow"
    assert permissions["bash"]["de repo restore*"] == "allow"
    assert permissions["bash"]["de repo contract*"] == "allow"
    assert permissions["bash"]["de repo todo*"] == "allow"
    assert permissions["bash"]["de repo interview*"] == "allow"
    assert permissions["bash"]["de repo install-agents-md*"] == "ask"
    assert permissions["bash"]["de repo install-contract*"] == "ask"
    assert permissions["bash"]["de-repo init*"] == "allow"
    assert permissions["bash"]["de-repo reset*"] == "allow"
    assert permissions["bash"]["de-repo scope*"] == "allow"
    assert permissions["bash"]["de-repo map*"] == "allow"
    assert permissions["bash"]["de-repo archives*"] == "allow"
    assert permissions["bash"]["de-repo diff*"] == "allow"
    assert permissions["bash"]["de-repo restore*"] == "allow"
    assert permissions["bash"]["de-repo contract*"] == "allow"
    assert permissions["bash"]["de-repo todo*"] == "allow"
    assert permissions["bash"]["de-repo interview*"] == "allow"
    assert permissions["bash"]["de-repo install-contract*"] == "ask"
    assert permissions["bash"]["de workbench capabilities*"] == "allow"
    assert permissions["bash"]["de workbench route *"] == "allow"
    assert permissions["bash"]["de-quality verdict *"] == "allow"

    agent = config["agent"]["data-engineer"]
    assert agent["steps"] == 80
    assert agent["permission"]["edit"] == "allow"
    assert agent["permission"]["todowrite"] == "allow"
    assert agent["permission"]["task"]["*"] == "deny"
    assert agent["permission"]["task"]["data-architect"] == "allow"
    assert agent["permission"]["task"]["data-devops"] == "allow"
    assert config["agent"]["data-architect"]["permission"]["edit"] == "deny"
    assert config["agent"]["data-architect"]["steps"] == 12
    assert config["agent"]["data-devops"]["permission"]["edit"] == "allow"
    assert config["agent"]["data-devops"]["permission"]["todowrite"] == "allow"
    assert config["agent"]["data-devops"]["steps"] == 48
    assert config["agent"]["data-devops"]["permission"]["bash"]["de databricks bundle-doctor *"] == "allow"

    plugin = read("plugins/de-guardrails.ts")
    for expected in [
        "shell.env",
        "tool.execute.before",
        "de_config_doctor",
        "de_config_auth",
        "de_repo_init",
        "de_repo_scope",
        "de_repo_reset",
        "de_repo_map",
        "de_repo_archives",
        "de_repo_diff",
        "de_repo_doctor",
        "de_repo_brief",
        "de_repo_contract",
        "de_repo_todo",
        "de_repo_interview",
        "de_workbench_catalog",
        "de_workbench_capabilities",
        "de_workbench_triage",
        "de_workbench_route",
        "de_workbench_ado_refine",
        "de_workbench_ado_bulk_preview",
        "de_workbench_mssql_assess",
        "de_workbench_migration_plan",
        "de_workbench_security_checklist",
        "de_workbench_quality_readiness",
        "de_databricks_bundle_doctor",
        "de_databricks_runtime_advisor",
        "de_dbsql_classify",
        "de_dbsql_dry_run",
        "de_mssql_policy_check",
        "de_ado_preflight",
        "de_pipeline_preflight",
        "de_pipeline_diagnose",
        "de_pipeline_evidence",
        "de_quality_evidence_template",
        "de_quality_verdict",
        "de_quality_reconcile",
    ]:
        assert expected in plugin
    for risky in [
        "databricks\\s+bundle\\s+deploy",
        "mssql-client\\s+execute-",
        "\\bsqlcmd\\b",
        "DELETE\\s+FROM",
        "MERGE\\s+INTO",
        "ado-work-items",
    ]:
        assert risky in plugin

    assert (ROOT / "templates" / "azure-pipelines" / "databricks-bundle-ci.yml").exists()
    assert (ROOT / "commands" / "de-onboard.md").exists()
    assert (ROOT / "commands" / "de-reset-context.md").exists()
    assert (ROOT / "commands" / "de-done.md").exists()
    assert (ROOT / "commands" / "de-pipeline-fix.md").exists()
    assert "edit: allow" in read("agents/data-engineer.md")
    assert "todowrite: allow" in read("agents/data-engineer.md")
    assert "de_workbench_route" in read("agents/data-engineer.md")
    assert "Route `data-devops` for Azure Pipeline failures" in read("agents/data-engineer.md")
    assert "edit: allow" in read("agents/data-devops.md")
    assert "todowrite: allow" in read("agents/data-devops.md")
    assert "edit: deny" in read("agents/data-architect.md")
    assert (ROOT / "samples" / "ado-pipeline" / "azure-pipelines.good.yml").exists()
    assert (ROOT / "samples" / "ado-pipeline" / "azure-pipelines.bad.yml").exists()
    assert (ROOT / "samples" / "databricks-bundle" / "databricks.good.yml").exists()
    assert (ROOT / "samples" / "databricks-bundle" / "databricks.bad.yml").exists()
    assert (ROOT / "samples" / "ado-work-items" / "sprint-items.json").exists()
    assert (ROOT / "samples" / "ado-work-items" / "bulk-updates.csv").exists()
    assert (ROOT / "samples" / "mssql" / "inventory.json").exists()
    assert (ROOT / "samples" / "migration" / "object-map.json").exists()
    assert (ROOT / "README.md").exists()
    assert (ROOT / "tools" / "de.py").exists()
    assert (ROOT / "tools" / "de_repo.py").exists()
    assert (ROOT / "tools" / "de_workbench.py").exists()
    assert (ROOT / "tools" / "de_databricks.py").exists()
    assert (ROOT / "docs" / "workbench.md").exists()
    assert (ROOT / "docs" / "databricks.md").exists()
    assert (ROOT / "docs" / "user-manual.md").exists()
    assert (ROOT / "docs" / "repo-onboarding.md").exists()
    assert (ROOT / "docs" / "checkpoint-audit.md").exists()
    assert (ROOT / "docs" / "ux-guide.md").exists()
    assert "de auth" in read("README.md")
    assert "de done" in read("README.md")
    assert "de repo reset" in read("README.md")
    assert "de workbench capabilities" in read("README.md")
    assert "docs/user-manual.md" in read("README.md")
    assert "docs/repo-onboarding.md" in read("README.md")
    assert "docs/checkpoint-audit.md" in read("README.md")
    assert 'databricks sql execute --sql "SELECT 1" --dry-run-only' in read("README.md")
    assert "de-mssql policy-check" in read("README.md")
    assert "What You Use It For" in read("docs/user-manual.md")
    assert "Repo Onboarding" in read("docs/user-manual.md")
    assert "de repo reset" in read("docs/repo-onboarding.md")
    assert "de repo scope" in read("docs/repo-onboarding.md")
    assert "Compact DE.md" in read("docs/repo-onboarding.md")
    assert "Opt-In Agent Files" in read("docs/repo-onboarding.md")
    assert "Short Next Actions" in read("docs/repo-onboarding.md")
    assert "Initialized-Only Interview" in read("docs/repo-onboarding.md")
    assert "Keep It Light Principles" in read("docs/checkpoint-audit.md")
    assert "Azure DevOps Workflows" in read("docs/user-manual.md")
    assert "Databricks SQL Live Execution" in read("docs/user-manual.md")
    assert "MSSQL Live Read Query" in read("docs/user-manual.md")
    assert "ready/needs-evidence/blocked" in read("docs/ux-guide.md")
    assert "de quality verdict" in read("docs/user-manual.md")
    assert "`.env` files are not supported" in read("README.md")
    assert "DE_ALLOW_DOTENV=true" not in read("docs/security-model.md")
    assert "local-dev fallback" not in read("skills/de-security-review/SKILL.md")
    assert '"de" = "de.py"' in read("install.ps1")
    assert '"de-databricks" = "de_databricks.py"' in read("install.ps1")
    assert '"de-workbench" = "de_workbench.py"' in read("install.ps1")
    assert '"de-repo" = "de_repo.py"' in read("install.ps1")
    assert '"README.md"' in read("install.ps1")
    assert '"commands"' in read("install.ps1")
    assert 'databricks sql execute --sql "SELECT 1" --dry-run-only' in read("smoke.ps1")
    assert "ado query --help" in read("smoke.ps1")
    assert "mssql query --help" in read("smoke.ps1")
    assert "repo init --root" in read("smoke.ps1")
    assert "repo reset --root" in read("smoke.ps1")
    assert "repo map --root" in read("smoke.ps1")
    assert "repo contract --root" in read("smoke.ps1")
    assert "repo todo --root" in read("smoke.ps1")
    assert "repo interview --root" in read("smoke.ps1")
    assert 'done --claim "install smoke"' in read("smoke.ps1")
    assert "write_wrapper de de.py" in read("install-wsl.sh")
    assert "write_wrapper de-databricks de_databricks.py" in read("install-wsl.sh")
    assert "write_wrapper de-workbench de_workbench.py" in read("install-wsl.sh")
    assert "write_wrapper de-repo de_repo.py" in read("install-wsl.sh")
    assert "$SOURCE_DIR/README.md" in read("install-wsl.sh")
    assert '$SOURCE_DIR/commands' in read("install-wsl.sh")

    secret_scan = re.compile(
        "|".join([
            r"dapi[A-Za-z0-9]{8,}",
            r"ADO_PAT\s*=\s*[^<\s]+",
            r"Password\s*=\s*[^<\s]+",
            r"client_" + r"secret\s*[=:]\s*[^<\s]+",
            r"BEGIN (RSA|OPENSSH|PRIVATE)",
            "your-personal-" + "access-token",
        ])
    )
    for path in ROOT.rglob("*"):
        if "node_modules" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix == ".swp":
            continue
        if path.relative_to(ROOT).as_posix() == "tests/security_package.py":
            continue
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".ts", ".ps1", ".sh", ".py", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not secret_scan.search(text), f"secret-like pattern in {path.relative_to(ROOT)}"

    print("de-opencode security package checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
