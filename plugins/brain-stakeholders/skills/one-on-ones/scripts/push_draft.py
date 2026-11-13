#!/usr/bin/env python3
"""Push one approved 1:1 draft onto the person's page. Local write only.

    python3 push_draft.py --id <draft-id> --approved

`--approved` is required and means the owner said yes to THIS draft in chat; never pass it otherwise.
Appends the entry, newest first, inside the confidential wrapper of the page's '1:1 log' section
(created if missing), sets last_contact to the meeting date when it is newer, marks the ledger
`pushed` and deletes the queue file. Aborts without writing if the page is missing, the draft is
unknown, or a human-fenced section would change.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402
from queue_status import render_entry  # noqa: E402

pl = c.pl


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--id", required=True)
    ap.add_argument("--approved", action="store_true")
    args = ap.parse_args()
    if not args.approved:
        c.emit({"status": "refused", "reason": "pass --approved only after the owner said yes to this draft"})
        return 1
    hit = [f for f in c.queue_dir().glob("*/*.json") if f.stem == args.id]
    if not hit:
        c.emit({"status": "not_found", "id": args.id})
        return 1
    d = json.loads(hit[0].read_text(encoding="utf-8"))
    page = pl.page_path(d["person_id"])
    if not page.is_file():
        c.emit({"status": "failed", "reason": f"{c.rel(page)} missing; run `brain new person {d['person_id']}` and retry"})
        return 1
    old = page.read_text(encoding="utf-8")
    if f"### {d['date']} · {d['title']}" in old:
        c.emit({"status": "failed", "reason": "an entry with this date and title is already on the page"})
        return 1
    _, body = pl.frontmatter.split(old)
    secs = pl.split_sections(body)
    i = pl.ensure_section(secs, "1:1 log")
    secs[i] = (secs[i][0], pl.insert_in_confidential(secs[i][1], render_entry(d)))
    new = old[: len(old) - len(body)] + pl.join_sections(secs)
    fm = pl.frontmatter.parse(old)
    if not fm.get("last_contact") or str(fm["last_contact"]) < d["date"]:
        new = pl.frontmatter.set_fields(new, {"last_contact": d["date"]})
    if pl.human_fences(old) != pl.human_fences(new):
        c.emit({"status": "failed", "reason": "a human-fenced section would change; nothing written"})
        return 1
    pl.write_atomic(page, new)
    ledger = c.load_ledger()
    ledger["pushed"][d["id"]] = date.today().isoformat()
    c.save_ledger(ledger)
    hit[0].unlink()
    c.emit({"status": "pushed", "id": d["id"], "page": c.rel(page)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
