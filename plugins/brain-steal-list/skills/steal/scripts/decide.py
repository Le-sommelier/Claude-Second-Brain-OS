"""Record a decision on a reviewed item. Enforces the build gate: plan_approved only after plan_drafted.

Statuses: proposed -> adopted -> plan_drafted -> plan_approved -> done; or rejected / deferred.
Only run `--status plan_approved` on the owner's explicit approval of the drafted plan.
Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/decide.py --id 12 --status adopted --note "why"
       python3 ${CLAUDE_SKILL_DIR}/scripts/decide.py --id 12 --status plan_drafted --plan plans/12-slug.md
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--status", required=True, choices=[s for s in _steal.STATUSES if s not in ("proposed", "skipped")])
    ap.add_argument("--note", default="")
    ap.add_argument("--plan", help="plan file, relative to the steal home folder (plan_drafted)")
    ap.add_argument("--link", help="what was built, workspace-relative path or URL (done)")
    args = ap.parse_args()

    con = _steal.connect()
    row = con.execute("SELECT status, plan_path FROM decisions WHERE item_id=?", (args.id,)).fetchone()
    if not row:
        _steal.emit({"status": "failed", "reason": f"no item {args.id}"})
        raise SystemExit(1)
    cur = row["status"]
    if args.status not in _steal.TRANSITIONS.get(cur, ()):
        _steal.emit({"status": "failed", "reason": f"{cur} -> {args.status} not allowed",
                     "allowed": list(_steal.TRANSITIONS.get(cur, ()))})
        raise SystemExit(1)

    plan = row["plan_path"]
    if args.status == "plan_drafted":
        if not args.plan or not (_steal.home_dir() / args.plan).is_file():
            _steal.emit({"status": "failed", "reason": "plan_drafted needs --plan pointing to an existing file"})
            raise SystemExit(1)
        plan = args.plan
    if args.status == "done" and not args.link:
        _steal.emit({"status": "failed", "reason": "done needs --link to what was built"})
        raise SystemExit(1)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with con:
        con.execute("UPDATE decisions SET status=?, decided_at=COALESCE(decided_at, ?), note=COALESCE(NULLIF(?, ''), note),"
                    " plan_path=?, link=COALESCE(?, link), updated_at=? WHERE item_id=?",
                    (args.status, now, args.note, plan, args.link, now, args.id))
        con.execute("INSERT INTO decision_log (item_id, status, at, note) VALUES (?,?,?,?)",
                    (args.id, args.status, now, args.note))
    _steal.emit({"status": "success", "item_id": args.id, "from": cur, "to": args.status, "plan": plan})


if __name__ == "__main__":
    main()
