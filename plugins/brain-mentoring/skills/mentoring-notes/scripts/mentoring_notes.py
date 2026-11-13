#!/usr/bin/env python3
"""Capture a mentoring session: write the dated note and update the actions log.

    python3 mentoring_notes.py --person casey-nguyen --payload growth/mentoring/_run/notes-casey.json

Payload (written by the skill with the Write tool):
  {"date": "2026-11-19", "discussed": ["..."], "insights": ["..."],
   "actions": [{"owner": "casey-nguyen", "what": "...", "due": "2026-12-03"}],
   "closed": ["A-003"]}

Validates everything first; any error leaves the folder untouched and the payload in place.
Writes sessions/<date>-session.md (a -2, -3 suffix if the day already has one), appends the new
actions with ids, ticks the closed ones, deletes the payload. Prints only counts and paths.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mentoring-setup" / "scripts"))
import mentorlib as ml  # noqa: E402


def validate(pl: dict, known_ids: set[str], valid_owners: set[str]) -> list[str]:
    errs = []
    if not ml.DATE_RE.match(str(pl.get("date", ""))):
        errs.append("date must be YYYY-MM-DD")
    for key in ("discussed", "insights"):
        v = pl.get(key, [])
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            errs.append(f"'{key}' must be a list of non-empty strings")
    if not pl.get("discussed"):
        errs.append("'discussed' is empty; a session note needs at least one topic")
    for i, a in enumerate(pl.get("actions", [])):
        if not isinstance(a, dict) or not a.get("what") or not a.get("owner"):
            errs.append(f"action {i}: needs 'owner' and 'what'")
            continue
        if a["owner"] not in valid_owners:
            errs.append(f"action {i}: owner '{a['owner']}' must be one of {sorted(valid_owners)}")
        if a.get("due") and not ml.DATE_RE.match(a["due"]):
            errs.append(f"action {i}: due must be YYYY-MM-DD")
    for cid in pl.get("closed", []):
        if cid not in known_ids:
            errs.append(f"cannot close unknown action '{cid}'")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--person", required=True)
    ap.add_argument("--payload", required=True)
    args = ap.parse_args()
    d = ml.person_dir(args.person)
    pp = Path(args.payload)
    if not pp.is_absolute():
        pp = ml.root() / pp
    try:
        pl = json.loads(pp.read_text(encoding="utf-8"))
        assert isinstance(pl, dict)
    except (OSError, json.JSONDecodeError, AssertionError) as exc:
        ml.emit({"status": "invalid", "errors": [f"cannot read payload: {exc}"]})
        return 1
    meta, _ = ml.read_readme(d)
    actions = ml.parse_actions(d)
    me = ml.owner().get("person_id") or "owner"
    errs = validate(pl, {a["id"] for a in actions}, {args.person, me, "both"})
    if errs:
        ml.emit({"status": "invalid", "errors": errs})
        return 1

    new_actions = []
    for a in pl.get("actions", []):
        new = {"id": ml.next_action_id(actions + new_actions), "opened": pl["date"], "owner": a["owner"],
               "due": a.get("due") or "", "what": a["what"].strip(), "done": False, "closed": ""}
        new_actions.append(new)
    for a in actions:
        if a["id"] in pl.get("closed", []) and not a["done"]:
            a["done"], a["closed"] = True, pl["date"]
    allacts = actions + new_actions

    base = d / "sessions" / f"{pl['date']}-session.md"
    target, n = base, 1
    while target.exists():
        n += 1
        target = base.with_name(f"{pl['date']}-session-{n}.md")
    lines = ["## Discussed"] + [f"- {x}" for x in pl["discussed"]]
    if pl.get("insights"):
        lines += ["", "## Insights"] + [f"- {x}" for x in pl["insights"]]
    if new_actions:
        lines += ["", "## Actions"] + [f"- {a['id']} {a['owner']}: {a['what']}" for a in new_actions]
    note = (ml.frontmatter.render({"date": pl["date"], "person": args.person, "mode": meta.get("mode", "mentor"),
                                   "sensitivity": "confidential"})
            + f"\n# Session {pl['date']}\n\n" + ml.wrap("\n".join(lines)))
    acts_text = (ml.frontmatter.render({"person": args.person, "sensitivity": "confidential"})
                 + "\n# Actions log\n\n" + ml.wrap("\n".join(ml.action_line(a) for a in allacts) or "*(no actions yet)*"))
    ml.write_atomic(target, note)
    ml.write_atomic(d / "actions.md", acts_text)
    pp.unlink(missing_ok=True)
    ml.emit({"status": "success", "note": ml.rel(target), "actions_added": len(new_actions),
             "actions_closed": sum(1 for a in actions if a["closed"] == pl["date"]),
             "open_actions": sum(1 for a in allacts if not a["done"])})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
