#!/usr/bin/env python3
"""Start a mentorship: create growth/mentoring/<person-id>/ with README, sessions/ and actions.md.

    python3 mentoring_setup.py --person casey-nguyen --mode mentor --cadence fortnightly \
        --goal "Present a roadmap unaided" --goal "..." [--name "Casey Nguyen"] [--started YYYY-MM-DD]

Refuses to touch an existing folder. The agreement text is a default the owner edits afterwards.
Warns when people/<person-id>.md does not exist yet (create it with `brain new person`).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mentorlib as ml  # noqa: E402

MODES = {"mentor": "you mentor them", "mentee": "they mentor you"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--person", required=True)
    ap.add_argument("--mode", required=True, choices=sorted(MODES))
    ap.add_argument("--cadence", default="fortnightly", choices=sorted(ml.CADENCE_DAYS))
    ap.add_argument("--goal", action="append", default=[])
    ap.add_argument("--name")
    ap.add_argument("--started")
    args = ap.parse_args()

    d = ml.person_dir(args.person, must_exist=False)
    if d.exists():
        ml.emit({"status": "failed", "reason": f"{ml.rel(d)} already exists; edit it instead"})
        return 1
    if not args.goal:
        ml.emit({"status": "failed", "reason": "give at least one --goal; a mentorship without goals drifts"})
        return 1
    started = args.started or date.today().isoformat()
    if not ml.DATE_RE.match(started):
        ml.emit({"status": "failed", "reason": "--started must be YYYY-MM-DD"})
        return 1
    name = args.name or args.person.replace("-", " ").title()
    me = ml.owner().get("first_name") or "I"
    goals = "\n".join(f"- G{i}: {g}" for i, g in enumerate(args.goal, 1))
    fm = ml.frontmatter.render({"person": args.person, "mode": args.mode, "started": started,
                                "cadence": args.cadence, "sensitivity": "confidential", "status": "active"})
    body = (f"\n# Mentoring: {name} ({MODES[args.mode]})\n\n" + ml.wrap(
        f"## Goals\n\n{goals}\n\n## Agreement\n\n"
        f"- {args.cadence.capitalize()}, 45 minutes. Either side can cancel with a day's notice.\n"
        f"- What is said stays between {me if me != 'I' else 'us'} and {name.split()[0]} unless they agree to share it.\n"
        "- Each session: one topic from the mentee, one stretch from the mentor.\n\n"
        f"## Cadence\n\nPrep takes 10 minutes from the last session note and the open actions."))
    ml.write_atomic(d / "README.md", fm + body)
    (d / "sessions").mkdir(exist_ok=True)
    ml.write_atomic(d / "actions.md", ml.frontmatter.render({"person": args.person, "sensitivity": "confidential"})
                    + "\n# Actions log\n\n" + ml.wrap("*(no actions yet)*"))
    out = {"status": "success", "folder": ml.rel(d), "goals": len(args.goal), "warnings": []}
    if not (ml.path("core", "people") / f"{args.person}.md").is_file():
        out["warnings"].append(f"people/{args.person}.md does not exist; run `brain new person {args.person}`")
    ml.emit(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
