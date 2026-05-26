import { type Plugin, tool } from "@opencode-ai/plugin"
import { fileURLToPath } from "url"

const pythonExecutable = process.env.DE_OPENCODE_PYTHON || process.env.PYTHON || "python3"
const packageToolsDir = new URL("../tools/", import.meta.url)

const secretFilePatterns = [
  ".env",
  ".env.local",
  ".databrickscfg",
  "odbc.ini",
  "tnsnames.ora",
]

const riskyCommandPatterns = [
  /databricks\s+bundle\s+deploy\b/i,
  /databricks\s+bundle\s+run\b/i,
  /mssql-client\s+execute-/i,
  /\bsqlcmd\b/i,
  /ado-pipelines\s+run-trigger/i,
  /ado-work-items\s+(create|update|batch-update|from-json|from-template|create-story|create-tasks|add-comment|link-)/i,
  /\baz\s+pipelines\s+run\b/i,
  /\bDROP\s+TABLE\b/i,
  /\bTRUNCATE\s+TABLE\b/i,
  /\bDELETE\s+FROM\b/i,
  /\bUPDATE\s+\S+\s+SET\b/i,
  /\bMERGE\s+INTO\b/i,
]

export const DataEngineeringGuardrails: Plugin = async ({ client, $ }) => {
  return {
    "shell.env": async (input, output) => {
      output.env.DE_OPENCODE_ACTIVE = "true"
      output.env.DE_ALLOW_DOTENV = "false"
      output.env.DE_ENV_FILE_SUPPORT = "false"
      output.env.DE_OPENCODE_WORKDIR = input.cwd
    },
    "tool.execute.before": async (input, output) => {
      if (input.tool === "read") {
        const filePath = String(output.args?.filePath || "")
        const lowered = filePath.toLowerCase()
        if (secretFilePatterns.some((item) => lowered.endsWith(item))) {
          throw new Error("Blocked reading secret/config file. Use de-config doctor or an approved secret-provider path instead.")
        }
      }

      if (input.tool === "bash") {
        const command = String(output.args?.command || "")
        if (riskyCommandPatterns.some((pattern) => pattern.test(command))) {
          await client.app.log({
            body: {
              service: "de-guardrails",
              level: "warn",
              message: "Risky data-engineering command requires explicit approval",
              extra: { command_class: classifyCommand(command) },
            },
          })
          throw new Error("Risky data-engineering command blocked by de-guardrails. Run classify/preflight first and request explicit approval.")
        }
      }
    },
    tool: {
      de_config_doctor: tool({
        description: "Show redacted readiness and config state for the data-engineering OpenCode package.",
        args: {
          all: tool.schema.boolean().optional().describe("Include all known config keys."),
        },
        async execute(args) {
          return runPython($, "de_config.py", ["doctor", ...(args.all ? ["--all"] : [])])
        },
      }),
      de_config_audit: tool({
        description: "Audit local config posture for insecure data-engineering settings without printing secrets.",
        args: {},
        async execute() {
          return runPython($, "de_config.py", ["audit"])
        },
      }),
      de_config_auth: tool({
        description: "Show enterprise auth posture and supported secure modes without printing secrets.",
        args: {},
        async execute() {
          return runPython($, "de_config.py", ["auth"])
        },
      }),
      de_repo_init: tool({
        description: "Create safe repo-local de-opencode context artifacts for data-engineering onboarding.",
        args: {
          root: tool.schema.string().optional().describe("Optional repo root. Defaults to current working repo."),
          maxFiles: tool.schema.number().optional().describe("Maximum files to scan."),
        },
        async execute(args) {
          return runPython($, "de_repo.py", [
            "init",
            ...(args.root ? ["--root", args.root] : []),
            ...(args.maxFiles ? ["--max-files", String(args.maxFiles)] : []),
          ])
        },
      }),
      de_repo_doctor: tool({
        description: "Check whether repo-local de-opencode context is initialized and healthy.",
        args: {
          root: tool.schema.string().optional().describe("Optional repo root. Defaults to current working repo."),
        },
        async execute(args) {
          return runPython($, "de_repo.py", ["doctor", ...(args.root ? ["--root", args.root] : [])])
        },
      }),
      de_repo_brief: tool({
        description: "Read the generated repo brief for data-engineering context.",
        args: {
          root: tool.schema.string().optional().describe("Optional repo root. Defaults to current working repo."),
        },
        async execute(args) {
          return runPython($, "de_repo.py", ["brief", ...(args.root ? ["--root", args.root] : [])])
        },
      }),
      de_repo_interview: tool({
        description: "Generate targeted repo-specific interview questions after repo context is initialized.",
        args: {
          root: tool.schema.string().optional().describe("Optional repo root. Defaults to current working repo."),
          maxQuestions: tool.schema.number().optional().describe("Maximum questions to return."),
        },
        async execute(args) {
          return runPython($, "de_repo.py", [
            "interview",
            "--format",
            "json",
            ...(args.root ? ["--root", args.root] : []),
            ...(args.maxQuestions ? ["--max-questions", String(args.maxQuestions)] : []),
          ])
        },
      }),
      de_workbench_catalog: tool({
        description: "List de-opencode skills and their human front-door workflows.",
        args: {},
        async execute() {
          return runPython($, "de_workbench.py", ["catalog"])
        },
      }),
      de_workbench_capabilities: tool({
        description: "Show de-opencode capability coverage and secure auth posture by domain.",
        args: {
          domain: tool.schema.string().optional().describe("Optional domain: ado, databricks, mssql, or migration."),
        },
        async execute(args) {
          return runPython($, "de_workbench.py", [
            "capabilities",
            ...(args.domain ? ["--domain", args.domain] : []),
          ])
        },
      }),
      de_workbench_triage: tool({
        description: "Route a data-engineering request to the right package skill and safe first commands.",
        args: {
          request: tool.schema.string().describe("User request or task summary."),
        },
        async execute(args) {
          return runPython($, "de_workbench.py", ["triage", "--request", args.request])
        },
      }),
      de_workbench_ado_refine: tool({
        description: "Generate backlog refinement findings from exported ADO work item JSON/CSV.",
        args: {
          itemsFile: tool.schema.string().describe("Path to work item JSON/CSV export."),
        },
        async execute(args) {
          return runPython($, "de_workbench.py", ["ado-refine", "--items-file", args.itemsFile])
        },
      }),
      de_workbench_ado_bulk_preview: tool({
        description: "Preview bulk ADO work-item updates from CSV/JSON before any apply step.",
        args: {
          file: tool.schema.string().describe("Path to bulk update CSV/JSON."),
          out: tool.schema.string().optional().describe("Optional output path for the preview plan."),
        },
        async execute(args) {
          return runPython($, "de_workbench.py", [
            "ado-bulk-preview",
            "--file",
            args.file,
            ...(args.out ? ["--out", args.out] : []),
          ])
        },
      }),
      de_workbench_mssql_assess: tool({
        description: "Assess MSSQL inventory metadata for migration risks.",
        args: {
          metadataFile: tool.schema.string().describe("Path to MSSQL inventory JSON."),
        },
        async execute(args) {
          return runPython($, "de_workbench.py", ["mssql-assess", "--metadata-file", args.metadataFile])
        },
      }),
      de_workbench_migration_plan: tool({
        description: "Create a migration evidence plan from source/target object mappings.",
        args: {
          objectsFile: tool.schema.string().describe("Path to object mapping JSON/CSV."),
          source: tool.schema.string().describe("Source platform."),
          target: tool.schema.string().describe("Target platform."),
        },
        async execute(args) {
          return runPython($, "de_workbench.py", [
            "migration-plan",
            "--objects-file",
            args.objectsFile,
            "--source",
            args.source,
            "--target",
            args.target,
          ])
        },
      }),
      de_workbench_security_checklist: tool({
        description: "Create a client-facing package security checklist.",
        args: {
          scope: tool.schema.string().optional().describe("Review scope."),
        },
        async execute(args) {
          return runPython($, "de_workbench.py", ["security-checklist", "--scope", args.scope || "client-review"])
        },
      }),
      de_workbench_quality_readiness: tool({
        description: "Create release/readiness checklist for a data-engineering claim.",
        args: {
          claim: tool.schema.string().describe("Claim being verified."),
          environment: tool.schema.string().optional().describe("Target environment."),
        },
        async execute(args) {
          return runPython($, "de_workbench.py", [
            "quality-readiness",
            "--claim",
            args.claim,
            "--environment",
            args.environment || "dev",
          ])
        },
      }),
      de_databricks_bundle_doctor: tool({
        description: "Preflight databricks.yml and optional Azure Pipeline YAML for bundle CI/CD readiness.",
        args: {
          bundleYaml: tool.schema.string().describe("Path to databricks.yml."),
          pipelineYaml: tool.schema.string().optional().describe("Optional Azure Pipelines YAML path."),
          environment: tool.schema.string().optional().describe("Target environment, for example dev, test, prod."),
        },
        async execute(args) {
          return runPython($, "de_databricks.py", [
            "bundle-doctor",
            "--bundle-yaml",
            args.bundleYaml,
            "--environment",
            args.environment || "dev",
            ...(args.pipelineYaml ? ["--pipeline-yaml", args.pipelineYaml] : []),
          ])
        },
      }),
      de_databricks_runtime_advisor: tool({
        description: "Create Databricks runtime upgrade risk checks for jobs, bundles, streaming, Delta writes, and serving workloads.",
        args: {
          currentRuntime: tool.schema.string().describe("Current Databricks Runtime version."),
          targetRuntime: tool.schema.string().describe("Target Databricks Runtime version."),
          environment: tool.schema.string().optional().describe("Target environment."),
          usesUdfs: tool.schema.boolean().optional().describe("Whether workload uses UDFs."),
          usesJars: tool.schema.boolean().optional().describe("Whether workload uses JAR/Java/Scala dependencies."),
          usesStreaming: tool.schema.boolean().optional().describe("Whether workload uses Structured Streaming."),
          usesDeltaWrites: tool.schema.boolean().optional().describe("Whether workload writes Delta tables."),
          usesMlServing: tool.schema.boolean().optional().describe("Whether workload includes ML/AI serving."),
        },
        async execute(args) {
          return runPython($, "de_databricks.py", [
            "runtime-advisor",
            "--current-runtime",
            args.currentRuntime,
            "--target-runtime",
            args.targetRuntime,
            "--environment",
            args.environment || "dev",
            ...(args.usesUdfs ? ["--uses-udfs"] : []),
            ...(args.usesJars ? ["--uses-jars"] : []),
            ...(args.usesStreaming ? ["--uses-streaming"] : []),
            ...(args.usesDeltaWrites ? ["--uses-delta-writes"] : []),
            ...(args.usesMlServing ? ["--uses-ml-serving"] : []),
          ])
        },
      }),
      de_dbsql_classify: tool({
        description: "Classify Databricks SQL as readonly, dml, ddl, admin, mixed, or unknown without executing it.",
        args: {
          sql: tool.schema.string().describe("SQL text to classify."),
        },
        async execute(args) {
          return runPython($, "de_dbsql.py", ["classify", "--sql", args.sql])
        },
      }),
      de_dbsql_dry_run: tool({
        description: "Policy-check Databricks SQL before execution, including production and row-count gates.",
        args: {
          sql: tool.schema.string().describe("SQL text to dry-run."),
          environment: tool.schema.string().optional().describe("Target environment, for example dev, test, prod."),
          confirmWrite: tool.schema.boolean().optional().describe("Whether a write approval exists."),
          rowCountChecked: tool.schema.boolean().optional().describe("Whether row-count/target precheck evidence exists."),
        },
        async execute(args) {
          return runPython($, "de_dbsql.py", [
            "dry-run",
            "--sql",
            args.sql,
            "--environment",
            args.environment || "dev",
            ...(args.confirmWrite ? ["--confirm-write"] : []),
            ...(args.rowCountChecked ? ["--row-count-checked"] : []),
          ])
        },
      }),
      de_mssql_classify: tool({
        description: "Classify SQL Server SQL without executing it.",
        args: {
          sql: tool.schema.string().describe("SQL text to classify."),
        },
        async execute(args) {
          return runPython($, "de_mssql.py", ["classify", "--sql", args.sql])
        },
      }),
      de_mssql_policy_check: tool({
        description: "Check MSSQL local security posture for encryption, auth mode, and execution flags.",
        args: {
          strict: tool.schema.boolean().optional().describe("Return failure when warnings exist."),
        },
        async execute(args) {
          return runPython($, "de_mssql.py", ["policy-check", ...(args.strict ? ["--strict"] : [])])
        },
      }),
      de_ado_classify: tool({
        description: "Classify an Azure DevOps operation as readonly, write, or unknown.",
        args: {
          operation: tool.schema.string().describe("Operation name or short phrase."),
        },
        async execute(args) {
          return runPython($, "de_ado.py", ["classify", "--operation", args.operation])
        },
      }),
      de_ado_preflight: tool({
        description: "Preflight an Azure Pipeline YAML file for inline secrets and missing Databricks validation.",
        args: {
          pipelineYaml: tool.schema.string().describe("Path to Azure Pipelines YAML."),
        },
        async execute(args) {
          return runPython($, "de_ado.py", ["preflight", "--pipeline-yaml", args.pipelineYaml])
        },
      }),
      de_pipeline_preflight: tool({
        description: "Deep preflight of Azure Pipeline YAML for Databricks, production gates, secrets, and dangerous inline SQL.",
        args: {
          pipelineYaml: tool.schema.string().describe("Path to Azure Pipelines YAML."),
        },
        async execute(args) {
          return runPython($, "de_pipeline.py", ["preflight", "--pipeline-yaml", args.pipelineYaml])
        },
      }),
      de_pipeline_diagnose: tool({
        description: "Diagnose ADO pipeline YAML and build log text/file, then produce a fix plan and ADO next commands.",
        args: {
          pipelineYaml: tool.schema.string().optional().describe("Path to Azure Pipelines YAML."),
          logText: tool.schema.string().optional().describe("Build log text."),
          logFile: tool.schema.string().optional().describe("Path to build log file."),
          ledger: tool.schema.string().optional().describe("Optional ledger JSONL path."),
          environment: tool.schema.string().optional().describe("Target environment, for example dev, test, prod."),
        },
        async execute(args) {
          return runPython($, "de_pipeline.py", [
            "diagnose",
            ...(args.pipelineYaml ? ["--pipeline-yaml", args.pipelineYaml] : []),
            ...(args.logText ? ["--log-text", args.logText] : []),
            ...(args.logFile ? ["--log-file", args.logFile] : []),
            ...(args.ledger ? ["--ledger", args.ledger] : []),
            "--environment",
            args.environment || "dev",
          ])
        },
      }),
      de_pipeline_evidence: tool({
        description: "Create an ADO pipeline release evidence template with required commands and approval evidence.",
        args: {
          claim: tool.schema.string().describe("Claim being verified."),
          environment: tool.schema.string().optional().describe("Environment name."),
          buildId: tool.schema.string().optional().describe("ADO build ID."),
          pipelineId: tool.schema.string().optional().describe("ADO pipeline ID."),
        },
        async execute(args) {
          return runPython($, "de_pipeline.py", [
            "evidence",
            "--claim",
            args.claim,
            "--environment",
            args.environment || "dev",
            ...(args.buildId ? ["--build-id", args.buildId] : []),
            ...(args.pipelineId ? ["--pipeline-id", args.pipelineId] : []),
          ])
        },
      }),
      de_quality_evidence_template: tool({
        description: "Create a sanitized QA evidence template for data-engineering completion proof.",
        args: {
          claim: tool.schema.string().describe("Claim being verified."),
          environment: tool.schema.string().optional().describe("Environment name."),
        },
        async execute(args) {
          return runPython($, "de_quality.py", ["evidence-template", "--claim", args.claim, "--environment", args.environment || "dev"])
        },
      }),
      de_quality_reconcile: tool({
        description: "Compare source and target row counts before migration or release signoff.",
        args: {
          sourceCount: tool.schema.string().describe("Source row count."),
          targetCount: tool.schema.string().describe("Target row count."),
          tolerance: tool.schema.string().optional().describe("Allowed absolute difference."),
        },
        async execute(args) {
          return runPython($, "de_quality.py", [
            "reconcile",
            "--source-count",
            args.sourceCount,
            "--target-count",
            args.targetCount,
            "--tolerance",
            args.tolerance || "0",
          ])
        },
      }),
    },
  }
}

function classifyCommand(command: string): string {
  if (/databricks/i.test(command)) return "databricks"
  if (/mssql|sqlcmd/i.test(command)) return "mssql"
  if (/ado-pipelines|az pipelines/i.test(command)) return "azure-devops"
  if (/ado-work-items/i.test(command)) return "azure-devops-work-items"
  if (/drop|truncate/i.test(command)) return "sql-dangerous"
  return "unknown"
}

async function runPython($: any, scriptName: string, args: string[]): Promise<string> {
  const scriptPath = fileURLToPath(new URL(scriptName, packageToolsDir))
  try {
    const result = await $`${pythonExecutable} ${scriptPath} ${args}`.quiet().text()
    return redact(result.trim())
  } catch (error: any) {
    const stdout = error?.stdout ? String(error.stdout) : ""
    const stderr = error?.stderr ? String(error.stderr) : ""
    const message = [stdout, stderr, error?.message || ""].filter(Boolean).join("\n")
    return redact(message.trim() || "Command failed")
  }
}

function redact(value: string): string {
  return value
    .replace(/(dapi)[A-Za-z0-9]+/g, "$1<redacted>")
    .replace(/(Bearer\s+)[A-Za-z0-9._-]+/gi, "$1<redacted>")
    .replace(/(Password|Pwd|Token|Secret|PAT|client_secret)(\s*[=:]\s*)[^;\s"']+/gi, "$1$2<redacted>")
}
