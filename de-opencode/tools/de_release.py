#!/usr/bin/env python3
"""Release manifest helper for de-opencode distribution."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {"__pycache__", ".git", "ledger", ".de-opencode"}
EXCLUDE_FILES = {"release-manifest.json"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root: Path) -> list:
    files = []
    for path in root.rglob("*"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDE_FILES:
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def build_manifest(root: Path) -> dict:
    version_path = root / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "0.0.0"
    files = []
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        files.append({
            "path": rel,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    return {
        "name": "de-opencode",
        "version": version,
        "layout": "opencode-config-dir",
        "file_count": len(files),
        "files": files,
    }


def cmd_manifest(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else ROOT
    manifest = build_manifest(root)
    text = json.dumps(manifest, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else ROOT
    manifest_path = Path(args.manifest).resolve() if args.manifest else root / "release-manifest.json"
    expected = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = build_manifest(root)
    expected_files = {item["path"]: item for item in expected.get("files", [])}
    actual_files = {item["path"]: item for item in actual.get("files", [])}
    issues = []
    for rel, item in expected_files.items():
        if rel not in actual_files:
            issues.append(f"missing: {rel}")
        elif item["sha256"] != actual_files[rel]["sha256"]:
            issues.append(f"sha256 mismatch: {rel}")
    for rel in sorted(set(actual_files) - set(expected_files)):
        issues.append(f"unexpected: {rel}")
    print(json.dumps({"status": "ok" if not issues else "failed", "issues": issues}, indent=2))
    return 0 if not issues else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="de-opencode release manifest helper")
    sub = parser.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("manifest", help="Generate release manifest")
    manifest.add_argument("--root")
    manifest.add_argument("--out")
    manifest.set_defaults(func=cmd_manifest)
    verify = sub.add_parser("verify", help="Verify files against release manifest")
    verify.add_argument("--root")
    verify.add_argument("--manifest")
    verify.set_defaults(func=cmd_verify)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
