#!/usr/bin/env python3
"""List log entries whose current state looks abandoned. Read-only; never edits a log.

    python3 ${CLAUDE_SKILL_DIR}/scripts/find_stale.py [--project SLUG] [--days 21] [--today YYYY-MM-DD]

Current state per ID = the latest entry. Candidates are IDs whose current state is still live
(open, at-risk, off-track, proposed, slipped) and whose latest entry is older than --days, plus
decisions still `proposed` after --days. A candidate is `possibly_stale`, not "dead": the skill
turns each into a proposal for the owner. Entries in human-fenced blocks are never read.
Prints {"as_of", "days", "count", "candidates": [{project, id, facet, state, date, age_days, owner, source, body, path, line}]}.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import kbparse  # noqa: E402
from brainos import frontmatter  # noqa: E402
from brainos.workspace import emit, parse_date, path, rel  # noqa: E402

LIVE = {"open", "at-risk", "off-track", "proposed", "slipped"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project")
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--today", default=date.today().isoformat())
    args = ap.parse_args()
    today = parse_date(args.today)

    base = path("core", "projects")
    dirs = [base / args.project] if args.project else sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))
    out = []
    for d in dirs:
        for e in kbparse.latest_by_id(kbparse.project_entries(d)):
            age = (today - parse_date(e["date"])).days
            if e["state"] in LIVE and age > args.days:
                out.append({"project": d.name, "id": e["id"], "facet": e["facet"], "state": e["state"], "date": e["date"],
                            "age_days": age, "owner": e["meta"].get("owner"), "source": e["meta"].get("source"),
                            "body": e["body"][:200], "path": rel(Path(e["path"])), "line": e["line"]})
        for f in sorted((d / "decisions").glob("*.md")) if (d / "decisions").is_dir() else []:
            fm = frontmatter.read(f)
            if fm.get("status") == "proposed" and fm.get("date"):
                age = (today - parse_date(str(fm["date"]))).days
                if age > args.days:
                    out.append({"project": d.name, "id": fm.get("id", f.stem), "facet": "decisions", "state": "proposed",
                                "date": str(fm["date"]), "age_days": age, "owner": fm.get("owner"), "source": fm.get("source"),
                                "body": str(fm.get("title", ""))[:200], "path": rel(f), "line": 1})
    out.sort(key=lambda c: -c["age_days"])
    emit({"as_of": today.isoformat(), "days": args.days, "count": len(out), "candidates": out})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
