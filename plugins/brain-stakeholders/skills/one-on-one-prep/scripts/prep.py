#!/usr/bin/env python3
"""Facts for prepping a 1:1. Read-only.

    python3 prep.py --person casey-nguyen [--today YYYY-MM-DD] [--window-days 14]

Prints: the person's profile fields (role, relationship, health, last contact, days since), the last
three entries of their '1:1 log', the open (unticked) actions from that log, queued drafts waiting to
be pushed, and recent non-confidential meeting or digest files that mention them. The skill turns it
into a short agenda. Output is for the owner's eyes only: it can contain 1:1 notes.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "person" / "scripts"))
import peoplelib as pl  # noqa: E402

ENTRY_RE = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s*·\s*(.+)$")
ACTION_RE = re.compile(r"^\s*-\s+\[ \]\s+(.+)$")


def log_entries(text: str) -> list[dict]:
    secs = dict((h, ls) for h, ls in pl.split_sections(pl.frontmatter.split(text)[1]) if h)
    lines = secs.get("1:1 log", [])
    out, cur = [], None
    for ln in lines:
        if (m := ENTRY_RE.match(ln)):
            cur = {"date": m.group(1), "title": m.group(2).strip(), "lines": []}
            out.append(cur)
        elif cur is not None and ln.strip() not in (pl.OPEN, pl.CLOSE):
            cur["lines"].append(ln)
    for e in out:
        e["text"] = "\n".join(e.pop("lines")).strip()
        e["open_actions"] = [m.group(1) for ln in e["text"].splitlines() if (m := ACTION_RE.match(ln))]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--person", required=True)
    ap.add_argument("--today")
    ap.add_argument("--window-days", type=int, default=14)
    args = ap.parse_args()
    today = pl.parse_date(args.today) if args.today else date.today()
    page = pl.page_path(args.person)
    if not page.is_file():
        pl.emit({"status": "failed", "reason": f"{pl.rel(page)} missing; run `brain new person {args.person}`"})
        return 1
    text = page.read_text(encoding="utf-8")
    fm = pl.frontmatter.parse(text)
    entries = log_entries(text)
    lc = str(fm.get("last_contact") or "")
    days = (today - pl.parse_date(lc)).days if pl.DATE_RE.match(lc) else None
    name = str(fm.get("name") or args.person)
    since = today - timedelta(days=args.window_days)
    pat = re.compile(r"\b(" + "|".join(re.escape(x) for x in (args.person, name)) + r")\b", re.I)
    mentions = []
    for g in ("raw/meetings/**/*.md", "digests/weekly/*.md"):
        for p in sorted(pl.root().glob(g)):
            m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
            if m and pl.parse_date(m.group(1)) < since:
                continue
            f = pl.frontmatter.read(p)
            if str(f.get("sensitivity", "")).lower() == "confidential" or f.get("redact_content") is True:
                continue
            if pat.search(p.read_text(encoding="utf-8", errors="replace")):
                mentions.append(pl.rel(p))
    queue = pl.path("stakeholders", "queue") / args.person
    queued = sorted(p.name for p in queue.glob("*.json")) if queue.is_dir() else []
    pl.emit({"status": "success", "person": args.person, "name": name, "role": fm.get("role"),
             "relationship": fm.get("relationship"), "health": fm.get("health"), "last_contact": lc or None,
             "days_since_contact": days, "recent_entries": entries[:3],
             "open_actions": [{"from": e["date"], "action": a} for e in entries for a in e["open_actions"]],
             "queued_drafts": queued, "recent_mentions": mentions[-10:]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
