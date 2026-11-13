#!/usr/bin/env python3
"""Facts for a quarterly mentoring review. Read-only.

    python3 mentoring_review.py --person casey-nguyen [--quarter 2026-Q4 | --since D --until D] [--today D]

Prints, for the window: sessions held versus expected from the cadence, the longest gap, actions
opened, closed and still open (with overdue), the goals from the README, and the session note paths
so the model can read them against each goal. The model writes the review; this script counts.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mentoring-setup" / "scripts"))
import mentorlib as ml  # noqa: E402


def quarter_window(q: str) -> tuple[date, date]:
    m = re.match(r"^(\d{4})-Q([1-4])$", q)
    if not m:
        raise SystemExit("--quarter must look like 2026-Q4")
    y, n = int(m.group(1)), int(m.group(2))
    start = date(y, 3 * n - 2, 1)
    end = (date(y + (n == 4), 1 if n == 4 else 3 * n + 1, 1)) - timedelta(days=1)
    return start, end


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--person", required=True)
    ap.add_argument("--quarter")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--today")
    args = ap.parse_args()
    today = ml.parse_date(args.today) if args.today else date.today()
    if args.quarter:
        since, until = quarter_window(args.quarter)
    else:
        until = ml.parse_date(args.until) if args.until else today
        since = ml.parse_date(args.since) if args.since else until - timedelta(days=90)
    d = ml.person_dir(args.person)
    meta, goals = ml.read_readme(d)
    sess = [p for p in ml.session_files(d) if since.isoformat() <= ml.session_date(p) <= until.isoformat()]
    dates = [ml.parse_date(ml.session_date(p)) for p in sess]
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    cadence = ml.CADENCE_DAYS.get(str(meta.get("cadence")), 14)
    expected = max(1, ((min(until, today) - since).days) // cadence)
    acts = ml.parse_actions(d)
    inwin = lambda s: bool(s) and since.isoformat() <= s <= until.isoformat()  # noqa: E731
    open_now = [a for a in acts if not a["done"]]
    ml.emit({"status": "success", "person": args.person, "mode": meta.get("mode"), "window": [since.isoformat(), until.isoformat()],
             "goals": goals, "sessions_held": len(sess), "sessions_expected": expected,
             "longest_gap_days": max(gaps) if gaps else None, "session_notes": [ml.rel(p) for p in sess],
             "actions_opened": sum(1 for a in acts if inwin(a["opened"])),
             "actions_closed": sum(1 for a in acts if inwin(a.get("closed"))),
             "actions_open": len(open_now),
             "actions_overdue": [a["id"] for a in open_now if a.get("due") and a["due"] < today.isoformat()]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
