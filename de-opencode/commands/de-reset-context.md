---
description: Archive stale repo context and reinitialize it
agent: data-engineer
---

Use `de repo scope current` and `de repo doctor` to understand the active context. Run `de repo reset` for safe archive-and-reinitialize behavior. If the user named a feature area, create or use a scope with `de repo scope add --name <name> --path <path> --use` before resetting. Do not use `--force` unless the user explicitly asked to delete old generated context.
