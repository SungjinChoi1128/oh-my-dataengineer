#!/usr/bin/env python3
"""Append-only local action ledger for de-opencode evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import List, Optional


SECRET_WORDS = ("token", "password", "secret", "pat", "pwd", "connectionstring")


def default_ledger_path() -> Path:
    root = os.environ.get("DE_LEDGER_PATH", "").strip()
    if root:
        return Path(root).expanduser()
    return Path.cwd() / ".de-opencode" / "ledger.jsonl"


def redact_value(value):
    if isinstance(value, dict):
        return {key: ("<redacted>" if any(word in key.lower() for word in SECRET_WORDS) else redact_value(val)) for key, val in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        text = value
        for marker in ("Bearer ", "dapi"):
            if marker in text:
                text = text.replace(marker, marker + "<redacted>")
        return text
    return value


def append_event(event: dict, path: Optional[Path] = None) -> dict:
    ledger = path or default_ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    record = redact_value(event)
    record.setdefault("timestamp", dt.datetime.now(dt.timezone.utc).isoformat())
    record.setdefault("tool", "de-opencode")
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return {"status": "ok", "ledger": str(ledger), "record": record}


def cmd_append(args: argparse.Namespace) -> int:
    event = {
        "type": args.type,
        "claim": args.claim,
        "target": args.target or "",
        "environment": args.environment,
        "status": args.status,
        "approval": args.approval or "",
        "evidence": json.loads(args.evidence_json) if args.evidence_json else {},
    }
    result = append_event(event, Path(args.ledger) if args.ledger else None)
    print(json.dumps(result, indent=2))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger) if args.ledger else default_ledger_path()
    records = []
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    by_status = {}
    by_type = {}
    for record in records:
        by_status[record.get("status", "unknown")] = by_status.get(record.get("status", "unknown"), 0) + 1
        by_type[record.get("type", "unknown")] = by_type.get(record.get("type", "unknown"), 0) + 1
    print(json.dumps({"ledger": str(ledger), "count": len(records), "by_status": by_status, "by_type": by_type}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="de-opencode append-only action ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    append = sub.add_parser("append", help="Append a sanitized action/evidence event")
    append.add_argument("--type", required=True)
    append.add_argument("--claim", required=True)
    append.add_argument("--target")
    append.add_argument("--environment", default="dev")
    append.add_argument("--status", default="recorded")
    append.add_argument("--approval")
    append.add_argument("--evidence-json")
    append.add_argument("--ledger")
    append.set_defaults(func=cmd_append)
    summary = sub.add_parser("summary", help="Summarize ledger entries")
    summary.add_argument("--ledger")
    summary.set_defaults(func=cmd_summary)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
