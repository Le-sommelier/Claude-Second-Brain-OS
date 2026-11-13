"""Scaffold an implementation plan for an adopted item: plans/<id>-<slug>.md, prefilled from the DB.

Claude then fills the empty sections (reading the real target files) and runs decide.py --status plan_drafted.
Nothing is built from this file until the owner approves it.
Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/new_plan.py --id 12
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    args = ap.parse_args()

    con = _steal.connect()
    r = con.execute("SELECT i.*, v.*, d.status FROM items i JOIN verdicts v ON v.item_id=i.id"
                    " JOIN decisions d ON d.item_id=i.id WHERE i.id=?", (args.id,)).fetchone()
    if not r:
        _steal.emit({"status": "failed", "reason": f"no item {args.id}"})
        raise SystemExit(1)
    if r["status"] != "adopted":
        _steal.emit({"status": "failed", "reason": f"item is '{r['status']}', plan scaffolding needs 'adopted'"})
        raise SystemExit(1)

    slug = re.sub(r"[^a-z0-9]+", "-", r["title"].lower()).strip("-")[:48] or "item"
    rel = f"plans/{args.id}-{slug}.md"
    out = _steal.home_dir() / rel
    if out.exists():
        _steal.emit({"status": "failed", "reason": f"{rel} already exists; edit it instead"})
        raise SystemExit(1)
    targets = ", ".join(json.loads(r["targets"] or "[]")) or "?"
    out.write_text(f"""---
item_id: {args.id}
status: draft
effort: {r['effort'] or '?'}
targets: {targets}
---

# Plan: {r['title']}

> Source: {r['author_handle'] or 'unknown'}, {r['platform'] or 'unknown'}, reviewed {r['reviewed_at'][:10]}. Item {args.id} in steal.db.
> **Not approved. Nothing gets built until the owner approves this plan.**

## What we're stealing
{r['summary']}

## Why (from the review)
{r['why']}

## Reviewer's first idea of how
{r['how'] or '(none)'}

## Goal and "done looks like"
TODO

## What already exists in the workspace (checked, with paths)
TODO

## Steps
TODO

## Files touched / created
TODO

## Risks and what we're not doing
TODO

## How to verify
TODO
""", encoding="utf-8")
    _steal.emit({"status": "success", "plan": rel, "path": _steal.rel(out)})


if __name__ == "__main__":
    main()
