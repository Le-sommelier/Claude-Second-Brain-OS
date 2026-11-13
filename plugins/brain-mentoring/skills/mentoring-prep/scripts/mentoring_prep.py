#!/usr/bin/env python3
"""Facts for prepping a mentoring session. Read-only.

    python3 mentoring_prep.py --person casey-nguyen [--today YYYY-MM-DD] [--window-days 30]

Prints: goals, cadence and whether a session is due, the last session note, open actions (with
overdue and who owns them), recent meeting or digest files that mention the person, and objectives
that mention them. The skill turns this into a one-page prep. Confidential output.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mentoring-setup" / "scripts"))
import mentorlib as ml  # noqa: E402


def mentions(person: str, name: str, since: date) -> list[str]:
    pat = re.compile(r"\b(" + "|".join(re.escape(x) for x in (person, name) if x) + r")\b", re.I)
    hits = []
    for g in ("raw/meetings/**/*.md", "digests/weekly/*.md", "projects/*/decisions/*.md"):
        for p in sorted(ml.root().glob(g)):
            m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
            if m and ml.parse_date(m.group(1)) < since:
                continue
            fm = ml.frontmatter.read(p)
            if str(fm.get("sensitivity", "")).lower() == "confidential" or fm.get("redact_content") is True:
                continue
            if pat.search(p.read_text(encoding="utf-8", errors="replace")):
                hits.append(ml.rel(p))
    return hits[-10:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--person", required=True)
    ap.add_argument("--today")
    ap.add_argument("--window-days", type=int, default=30)
    args = ap.parse_args()
    today = ml.parse_date(args.today) if args.today else date.today()
    d = ml.person_dir(args.person)
    meta, goals = ml.read_readme(d)
    sessions = ml.session_files(d)
    last = sessions[-1] if sessions else None
    cadence_days = ml.CADENCE_DAYS.get(str(meta.get("cadence")), 14)
    days_since = (today - ml.parse_date(ml.session_date(last))).days if last else None
    acts = [a for a in ml.parse_actions(d) if not a["done"]]
    for a in acts:
        a["overdue"] = bool(a.get("due")) and a["due"] < today.isoformat()
    first = args.person.split("-")[0]
    objs = []
    for p in sorted(ml.path("growth", "objectives").glob("*.md")) if ml.path("growth", "objectives").is_dir() else []:
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.startswith("## Objective") and first.lower() in ln.lower():
                objs.append({"file": ml.rel(p), "heading": ln.lstrip("# ").strip()})
    name = args.person.replace("-", " ")
    ml.emit({"status": "success", "person": args.person, "mode": meta.get("mode"), "cadence": meta.get("cadence"),
             "goals": goals, "sessions_total": len(sessions),
             "last_session": {"file": ml.rel(last), "date": ml.session_date(last), "text": last.read_text(encoding="utf-8")} if last else None,
             "days_since_last": days_since, "session_due": days_since is None or days_since >= cadence_days - 2,
             "open_actions": acts, "overdue_actions": [a["id"] for a in acts if a["overdue"]],
             "recent_mentions": mentions(args.person, name, today - timedelta(days=args.window_days)),
             "related_objectives": objs})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
