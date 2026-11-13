#!/usr/bin/env python3
"""List roster 1:1 meetings that still need a draft.

    python3 detect.py            # list
    python3 detect.py --init [--since YYYY-MM-DD]   # create the ledger once (go-live date, default today)

A meeting qualifies when its raw file (raw/meetings/**/mtg-*.txt or .md, not a .summary.md) has a
name matching a roster pattern, its date is on or after the ledger's `since` (no back-fill), and it is
neither drafted nor queued. Two copies of one meeting (same person, same day) count once.
Prints {"count", "items", "warnings"}.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--since")
    args = ap.parse_args()
    if args.init:
        c.init_ledger(args.since or date.today().isoformat())
        c.emit({"status": "success", "ledger": c.rel(c.ledger_path())})
        return 0
    ledger, people = c.load_ledger(), c.roster()
    queued = {p.stem for p in c.queue_dir().glob("*/*.json")}
    items, warnings = [], []
    raw = c.path("core", "raw") / "meetings"
    files = sorted(list(raw.glob("*/*/mtg-*.txt")) + list(raw.glob("*/*/mtg-*.md")))
    for f in files:
        if f.name.endswith(".summary.md"):
            continue
        name, tid = f.name.lower(), f.stem
        m = c.MTG_DATE_RE.match(name)
        if not m or m.group(1) < ledger["since"]:
            continue
        match = [p for p in people if any(pat.lower() in name for pat in p.get("patterns", []))]
        if not match:
            continue
        if len(match) > 1:
            warnings.append(f"{f.name} matches several roster entries; skipped")
            continue
        if tid in ledger["drafted"] or tid in queued:
            continue
        person = match[0]
        summary = f.with_name(tid + ".summary.md")
        items.append({"id": tid, "person_id": person["person_id"], "person": person.get("person"),
                      "relation": person.get("relation"), "showCareer": bool(person.get("showCareer")),
                      "date": m.group(1), "transcript": c.rel(f), "summary": c.rel(summary) if summary.is_file() else None})
    seen, unique = {}, []
    for done_id in list(ledger["drafted"]) + sorted(queued):
        dm = c.MTG_DATE_RE.match(done_id.lower())
        owner = [p for p in people if any(pat.lower() in done_id.lower() for pat in p.get("patterns", []))]
        if dm and len(owner) == 1:
            seen.setdefault((owner[0]["person_id"], dm.group(1)), done_id)
    for it in items:
        key = (it["person_id"], it["date"])
        if key in seen:
            warnings.append(f"{it['id']} looks like a second copy of {seen[key]}; skipped")
            continue
        seen[key] = it["id"]
        unique.append(it)
    c.emit({"count": len(unique), "items": unique, "warnings": warnings})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
