#!/usr/bin/env sh
set -eu

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_ROOT="${1:-$HOME/.config/opencode}"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
cp -R "$SOURCE_DIR/README.md" "$SOURCE_DIR/opencode.json" "$SOURCE_DIR/VERSION" "$SOURCE_DIR/install.ps1" "$SOURCE_DIR/install-wsl.sh" "$SOURCE_DIR/smoke.ps1" "$SOURCE_DIR/agents" "$SOURCE_DIR/skills" "$SOURCE_DIR/plugins" "$SOURCE_DIR/tools" "$SOURCE_DIR/docs" "$SOURCE_DIR/tests" "$SOURCE_DIR/samples" "$SOURCE_DIR/templates" "$INSTALL_ROOT/"
if [ -f "$SOURCE_DIR/release-manifest.json" ]; then
  cp "$SOURCE_DIR/release-manifest.json" "$INSTALL_ROOT/"
fi

write_wrapper() {
  name="$1"
  script="$2"
  path="$BIN_DIR/$name"
  {
    printf '%s\n' '#!/usr/bin/env sh'
    printf 'exec python3 "%s/tools/%s" "$@"\n' "$INSTALL_ROOT" "$script"
  } > "$path"
  chmod +x "$path"
}

write_wrapper de de.py
write_wrapper de-config de_config.py
write_wrapper de-databricks de_databricks.py
write_wrapper de-dbsql de_dbsql.py
write_wrapper de-mssql de_mssql.py
write_wrapper de-ado de_ado.py
write_wrapper de-pipeline de_pipeline.py
write_wrapper de-ledger de_ledger.py
write_wrapper de-quality de_quality.py
write_wrapper de-release de_release.py
write_wrapper de-workbench de_workbench.py

printf '[de-opencode] Installed to %s\n' "$INSTALL_ROOT"
printf '[de-opencode] Wrappers written to %s\n' "$BIN_DIR"
printf '[de-opencode] Ensure %s is on PATH.\n' "$BIN_DIR"
printf '[de-opencode] For custom config dir, export OPENCODE_CONFIG_DIR=%s\n' "$INSTALL_ROOT"
