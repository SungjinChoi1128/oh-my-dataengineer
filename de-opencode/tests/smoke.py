#!/usr/bin/env python3
"""Cross-platform smoke test for de-opencode."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def run_tool(script: str, *args: str, expect: int = 0) -> str:
    cmd = [sys.executable, str(TOOLS / script), *args]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != expect:
        raise AssertionError(f"{cmd} returned {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result.stdout


def assert_json(text: str) -> dict:
    return json.loads(text)


def main() -> int:
    required = [
        ROOT / "opencode.json",
        ROOT / "agents" / "data-engineer.md",
        ROOT / "skills" / "de-quality-gates" / "SKILL.md",
        ROOT / "plugins" / "de-guardrails.ts",
        TOOLS / "de_config.py",
        TOOLS / "de.py",
        TOOLS / "de_databricks.py",
        TOOLS / "de_release.py",
        TOOLS / "de_pipeline.py",
        TOOLS / "de_ledger.py",
        TOOLS / "de_workbench.py",
        TOOLS / "de_repo.py",
    ]
    for path in required:
        if not path.exists():
            raise AssertionError(f"Missing {path}")

    doctor = assert_json(run_tool("de_config.py", "doctor"))
    assert doctor["status"] == "ok"
    assert doctor["checks"]["dotenv_supported"] is False
    assert doctor["auth_posture"]["dotenv_supported"] is False

    auth = assert_json(run_tool("de_config.py", "auth"))
    assert auth["posture"]["dotenv_supported"] is False
    assert auth["supported_modes"]["ado"][0]["mode"] == "entra"

    umbrella_doctor = run_tool("de.py", "doctor")
    assert "de-opencode Doctor" in umbrella_doctor
    assert "dotenv_supported: OK False" in umbrella_doctor

    umbrella_auth = run_tool("de.py", "auth")
    assert "Enterprise Auth" in umbrella_auth
    assert ".env supported: False" in umbrella_auth

    repo_fixture = Path(tempfile.gettempdir()) / "de-opencode-repo-context-smoke"
    if repo_fixture.exists():
        shutil.rmtree(repo_fixture)
    (repo_fixture / "sql").mkdir(parents=True)
    (repo_fixture / "tests").mkdir()
    (repo_fixture / "databricks.yml").write_text("bundle:\n  name: smoke\n", encoding="utf-8")
    (repo_fixture / "azure-pipelines.yml").write_text("trigger: none\n", encoding="utf-8")
    (repo_fixture / "sql" / "load_orders.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (repo_fixture / "tests" / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    repo_init = assert_json(run_tool("de_repo.py", "init", "--root", str(repo_fixture)))
    assert repo_init["status"] == "ok"
    assert "databricks-bundle" in repo_init["summary"]["repo_types"]
    assert (repo_fixture / ".de-opencode" / "repo-context.json").exists()
    repo_doctor = assert_json(run_tool("de.py", "repo", "doctor", "--root", str(repo_fixture), "--format", "json"))
    assert repo_doctor["status"] == "ok"
    repo_brief = run_tool("de.py", "repo", "brief", "--root", str(repo_fixture))
    assert "Repo Brief" in repo_brief
    agents = assert_json(run_tool("de_repo.py", "install-agents-md", "--root", str(repo_fixture)))
    assert agents["status"] == "ok"
    agents_blocked = assert_json(run_tool("de_repo.py", "install-agents-md", "--root", str(repo_fixture), expect=1))
    assert agents_blocked["status"] == "blocked"

    dbsql = assert_json(run_tool("de_dbsql.py", "classify", "--sql", "SELECT 1"))
    assert dbsql["category"] == "readonly"
    dbsql_execute_plan = assert_json(run_tool("de_dbsql.py", "execute", "--sql", "SELECT 1", "--dry-run-only", "--format", "json"))
    assert dbsql_execute_plan["status"] == "ok"
    assert dbsql_execute_plan["will_execute"] is False
    umbrella_sql_plan = assert_json(run_tool("de.py", "databricks", "sql", "execute", "--sql", "SELECT 1", "--dry-run-only", "--result-format", "json"))
    assert umbrella_sql_plan["status"] == "ok"

    uc_dry = assert_json(run_tool("de_dbsql.py", "dry-run", "--sql", "SELECT * FROM sales.orders"))
    assert uc_dry["status"] == "ok"
    assert uc_dry["warnings"]

    bundle_good = ROOT / "samples" / "databricks-bundle" / "databricks.good.yml"
    bundle_bad = ROOT / "samples" / "databricks-bundle" / "databricks.bad.yml"
    bundle_ok = assert_json(run_tool("de_databricks.py", "bundle-doctor", "--bundle-yaml", str(bundle_good)))
    assert bundle_ok["status"] == "ok"
    bundle_blocked = assert_json(run_tool("de_databricks.py", "bundle-doctor", "--bundle-yaml", str(bundle_bad), "--environment", "prod", expect=1))
    assert bundle_blocked["status"] == "blocked"
    assert any(item["id"] == "inline_secret" for item in bundle_blocked["issues"])
    runtime = assert_json(run_tool(
        "de_databricks.py",
        "runtime-advisor",
        "--current-runtime",
        "15.4",
        "--target-runtime",
        "18.0",
        "--environment",
        "prod",
        "--uses-delta-writes",
    ))
    assert runtime["approval_required"] is True
    umbrella_bundle = run_tool("de.py", "databricks", "bundle-doctor", "--bundle-yaml", str(bundle_bad), "--environment", "prod", expect=1)
    assert "Databricks Bundle Doctor: BLOCKED" in umbrella_bundle

    mssql = assert_json(run_tool("de_mssql.py", "classify", "--sql", "DROP TABLE dbo.Customers"))
    assert mssql["category"] == "dangerous"
    blocked_mssql = assert_json(run_tool("de_mssql.py", "query", "--sql", "DROP TABLE dbo.Customers", expect=1))
    assert blocked_mssql["status"] == "blocked"

    ado = assert_json(run_tool("de_ado.py", "classify", "--operation", "run-trigger"))
    assert ado["requires_approval"] is True

    catalog = assert_json(run_tool("de_workbench.py", "catalog"))
    assert len(catalog["skills"]) >= 7
    capabilities = assert_json(run_tool("de_workbench.py", "capabilities", "--domain", "ado"))
    assert capabilities["security_model"]["env_file_support"] is False
    assert any(item["surface"] == "work-items" for item in capabilities["capabilities"])
    umbrella_capabilities = run_tool("de.py", "workbench", "capabilities", "--domain", "databricks")
    assert "Capability Catalog: OK" in umbrella_capabilities
    triage = assert_json(run_tool("de_workbench.py", "triage", "--request", "refine sprint backlog and bulk update ADO tasks"))
    assert triage["primary"]["skill"] == "de-ado-devops"
    sprint_items = ROOT / "samples" / "ado-work-items" / "sprint-items.json"
    refine = assert_json(run_tool("de_workbench.py", "ado-refine", "--items-file", str(sprint_items), expect=1))
    assert refine["status"] == "needs-refinement"
    assert any(item["id"] == "missing_acceptance_criteria" for item in refine["findings"])
    bulk_updates = ROOT / "samples" / "ado-work-items" / "bulk-updates.csv"
    bulk = assert_json(run_tool("de_workbench.py", "ado-bulk-preview", "--file", str(bulk_updates)))
    assert bulk["approval_required"] is True
    umbrella_bulk = run_tool("de.py", "ado", "bulk", "preview", "--file", str(bulk_updates))
    assert "ADO Bulk Preview: PREVIEW" in umbrella_bulk

    mssql_inventory = ROOT / "samples" / "mssql" / "inventory.json"
    mssql_assess = assert_json(run_tool("de_workbench.py", "mssql-assess", "--metadata-file", str(mssql_inventory)))
    assert mssql_assess["status"] == "needs-review"
    object_map = ROOT / "samples" / "migration" / "object-map.json"
    migration = assert_json(run_tool("de_workbench.py", "migration-plan", "--objects-file", str(object_map), "--source", "mssql", "--target", "databricks"))
    assert migration["status"] == "needs-mapping"
    security = assert_json(run_tool("de_workbench.py", "security-checklist"))
    assert "client_answer" in security
    readiness = assert_json(run_tool("de_workbench.py", "quality-readiness", "--claim", "release ready"))
    assert "required_checks" in readiness

    pipeline = assert_json(run_tool("de_pipeline.py", "evidence", "--claim", "pipeline smoke"))
    assert "ado-pipelines build-status --id <BUILD_ID>" in pipeline["ado_commands"]

    good_yaml = ROOT / "samples" / "ado-pipeline" / "azure-pipelines.good.yml"
    good_preflight = assert_json(run_tool("de_pipeline.py", "preflight", "--pipeline-yaml", str(good_yaml)))
    assert good_preflight["status"] == "ok"

    bad_yaml = ROOT / "samples" / "ado-pipeline" / "azure-pipelines.bad.yml"
    bad_preflight = assert_json(run_tool("de_pipeline.py", "preflight", "--pipeline-yaml", str(bad_yaml), expect=1))
    assert bad_preflight["status"] == "blocked"
    assert any(issue["id"] == "inline_secret" for issue in bad_preflight["issues"])

    bad_log = ROOT / "samples" / "ado-pipeline" / "build-failure.log"
    diagnosis = assert_json(run_tool("de_pipeline.py", "diagnose", "--pipeline-yaml", str(bad_yaml), "--log-file", str(bad_log), expect=1))
    assert diagnosis["fix_plan"]["requires_approval_before_rerun"] is True
    assert any(match["id"] == "databricks_cli_missing" for match in diagnosis["diagnosis"]["matches"])

    umbrella_pipeline = run_tool("de.py", "pipeline", "doctor", "--pipeline-yaml", str(bad_yaml), "--log-file", str(bad_log), expect=1)
    assert "Pipeline Doctor: BLOCKED" in umbrella_pipeline
    assert "Fix plan:" in umbrella_pipeline
    umbrella_pipeline_json = assert_json(run_tool(
        "de.py",
        "pipeline",
        "doctor",
        "--pipeline-yaml",
        str(good_yaml),
        "--format",
        "json",
    ))
    assert umbrella_pipeline_json["status"] == "ok"
    evidence_dir = Path(tempfile.gettempdir()) / "de-opencode-smoke-evidence"
    umbrella_demo = run_tool("de.py", "demo", "pipeline-doctor", "--out", str(evidence_dir), "--format", "markdown")
    assert "# Pipeline Doctor Evidence" in umbrella_demo
    assert (evidence_dir / "pipeline-diagnosis.json").exists()
    assert (evidence_dir / "pipeline-diagnosis.md").exists()

    ledger_path = Path(tempfile.gettempdir()) / "de-opencode-smoke-ledger.jsonl"
    if ledger_path.exists():
        ledger_path.unlink()
    ledger = assert_json(run_tool("de_ledger.py", "append", "--type", "smoke", "--claim", "ledger smoke", "--ledger", str(ledger_path)))
    assert ledger["status"] == "ok"
    summary = assert_json(run_tool("de_ledger.py", "summary", "--ledger", str(ledger_path)))
    assert summary["count"] == 1

    reconciliation = assert_json(run_tool("de_quality.py", "reconcile", "--source-count", "10", "--target-count", "10"))
    assert reconciliation["status"] == "pass"

    quality = assert_json(run_tool("de_quality.py", "evidence-template", "--claim", "smoke"))
    assert quality["claim"] == "smoke"

    release = assert_json(run_tool("de_release.py", "manifest", "--root", str(ROOT)))
    assert release["name"] == "de-opencode"
    assert release["file_count"] >= 20

    print("de-opencode smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
