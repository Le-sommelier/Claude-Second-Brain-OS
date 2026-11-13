#!/usr/bin/env python3
"""Append owner-only action cards to the todo file's Inbox section.

    python3 ${CLAUDE_SKILL_DIR}/scripts/add_todos.py --file system/run/payloads/todos.json [--dry-run]

Payload: JSON array of {"title", "owner", "source", "due"?, "tag"?, "note"?}.
Validate first, write second: any malformed card aborts with nothing written. Cards whose owner
is not the workspace owner (or `unclear`) are rejected. A card already present (same source and
normalised title) is skipped. This script is the only writer of the Inbox section.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
from brainos import payload  # noqa: E402
from brainos.workspace import emit, owner, path, rel  # noqa: E402

HEADING = "## Inbox (from meetings)"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEADER = "# Todos\n\nHuman-owned board. Cards under the Inbox heading are added by the todo-extract brick.\n\n"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def is_owner(value: str) -> bool:
    me = owner()
    mine = {norm(str(me.get(k, ""))) for k in ("name", "first_name", "person_id")} - {""}
    return norm(value) in mine or norm(value) == "unclear"


def card(c: dict) -> str:
    title = c["title"].strip()
    if norm(c["owner"]) == "unclear" and not norm(title).startswith("confirm owner"):
        title = f"Confirm owner of: {title}"
    parts = [f"- [ ] {title}"]
    if c.get("tag"):
        parts.append(f"#{c['tag']}")
    if c.get("due"):
        parts.append(f"(due {c['due']})")
    parts.append(f"[[{c['source']}]]")
    if c.get("note"):
        parts.append(f"([context]({c['note']}))")
    return " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cards = payload.load(args.file, list)
    errors, rejected, valid = [], [], []
    for i, c in enumerate(cards):
        if not isinstance(c, dict):
            errors.append(f"[{i}] not an object")
            continue
        for k in ("title", "owner", "source"):
            if not str(c.get(k, "")).strip():
                errors.append(f"[{i}] missing {k}")
        if c.get("due") and not DATE_RE.match(str(c["due"])):
            errors.append(f"[{i}] bad due date {c['due']!r}")
        if errors and errors[-1].startswith(f"[{i}]"):
            continue
        if not is_owner(str(c["owner"])):
            rejected.append({"title": c["title"], "owner": c["owner"], "reason": "not the workspace owner"})
            continue
        valid.append(c)
    if errors:
        emit({"status": "failed", "errors": errors, "added": 0})
        return 1

    todo = path("core", "todos")
    text = todo.read_text(encoding="utf-8") if todo.is_file() else HEADER
    existing: set[tuple[str, str]] = set()
    for m in re.finditer(r"^- \[[ xX]\] (.*?) \[\[([^\]]+)\]\]", text, re.M):
        title = re.sub(r"\s*\(due [\d-]+\)|\s+#\S+", "", m.group(1))
        existing.add((m.group(2), norm(re.sub(r"^Confirm owner of:\s*", "", title, flags=re.I))))
    new, skipped = [], 0
    for c in valid:
        key = (c["source"], norm(re.sub(r"^Confirm owner of:\s*", "", c["title"].strip(), flags=re.I)))
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        new.append(card(c))

    if new and not args.dry_run:
        if HEADING not in text:
            text = text.rstrip("\n") + f"\n\n{HEADING}\n"
        head, _, tail = text.partition(HEADING)
        tail_lines = tail.split("\n")
        # insert after the last card of the Inbox section (before the next "## " heading)
        end = next((j for j, ln in enumerate(tail_lines[1:], 1) if ln.startswith("## ")), len(tail_lines))
        while end > 1 and not tail_lines[end - 1].strip():
            end -= 1
        tail_lines[end:end] = new
        todo.parent.mkdir(parents=True, exist_ok=True)
        todo.write_text(head + HEADING + "\n".join(tail_lines).rstrip("\n") + "\n", encoding="utf-8")
    if not args.dry_run:
        payload.consume(args.file)
    emit({"status": "success", "dry_run": args.dry_run, "added": len(new), "skipped_duplicate": skipped,
          "rejected": rejected, "output": rel(todo)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
