#!/usr/bin/env python3
"""The org chart, people/_org.yaml: check it, add to it, print the tree.

    python3 org.py check
    python3 org.py add --id sam-patel --name "Sam Patel" --role "Engineering Manager" [--manager riley-chen] [--team Eng] [--tier ic|lead|exec] [--email e] [--slack-id U1]
    python3 org.py tree

check: duplicate ids, bad id format, manager that is not in the chart, manager cycles, people with
no page (warning), page frontmatter that disagrees with the chart (warning). Exit 1 on errors.
add: refuses a duplicate id or an unknown manager; never edits an existing record.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import peoplelib as pl  # noqa: E402


def check(people: list[dict]) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    ids = [p.get("id") for p in people]
    for i in sorted({x for x in ids if ids.count(x) > 1}):
        errs.append(f"duplicate id '{i}'")
    idset = set(ids)
    for p in people:
        pid = p.get("id")
        if not pid or not pl.ID_RE.match(str(pid)):
            errs.append(f"bad id '{pid}': use first-last in lowercase")
            continue
        if not p.get("name"):
            errs.append(f"{pid}: missing name")
        mgr = p.get("manager")
        if mgr and mgr not in idset:
            errs.append(f"{pid}: manager '{mgr}' is not in the chart")
        seen, cur = {pid}, mgr
        while cur and cur in idset:
            if cur in seen:
                errs.append(f"{pid}: manager cycle through '{cur}'")
                break
            seen.add(cur)
            cur = next((q.get("manager") for q in people if q.get("id") == cur), None)
        page = pl.page_path(pid)
        if not page.is_file():
            warns.append(f"{pid}: no page at {pl.rel(page)}; run `brain new person {pid}`")
            continue
        fm = pl.frontmatter.read(page)
        for key in ("manager", "role"):
            if p.get(key) and fm.get(key) and str(fm[key]) != str(p[key]):
                warns.append(f"{pid}: page {key} '{fm[key]}' differs from chart '{p[key]}'")
    return errs, warns


def tree(people: list[dict]) -> list[str]:
    kids: dict = {}
    for p in people:
        kids.setdefault(p.get("manager"), []).append(p)
    ids = {p["id"] for p in people}
    lines: list[str] = []

    def walk(p, depth):
        lines.append("  " * depth + f"{p['name']} ({p['id']}), {p.get('role') or '-'}")
        for c in sorted(kids.get(p["id"], []), key=lambda x: x["name"]):
            walk(c, depth + 1)

    for p in sorted(people, key=lambda x: x["name"]):
        if not p.get("manager") or p["manager"] not in ids:
            walk(p, 0)
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("tree")
    a = sub.add_parser("add")
    for f in ("id", "name"):
        a.add_argument(f"--{f}", required=True)
    for f in ("role", "manager", "team", "tier", "email", "slack-id"):
        a.add_argument(f"--{f}")
    args = ap.parse_args()
    comments, people = pl.read_org()

    if args.cmd == "check":
        errs, warns = check(people)
        pl.emit({"status": "invalid" if errs else "success", "people": len(people), "errors": errs, "warnings": warns})
        return 1 if errs else 0
    if args.cmd == "tree":
        pl.emit({"status": "success", "tree": tree(people)})
        return 0
    if not pl.ID_RE.match(args.id):
        pl.emit({"status": "failed", "reason": "id must look like first-last"})
        return 1
    if any(p.get("id") == args.id for p in people):
        pl.emit({"status": "failed", "reason": f"'{args.id}' is already in the chart; edit the file by hand"})
        return 1
    if args.manager and args.manager not in {p.get("id") for p in people}:
        pl.emit({"status": "failed", "reason": f"manager '{args.manager}' is not in the chart; add them first"})
        return 1
    rec = {"id": args.id, "name": args.name, "role": args.role, "tier": args.tier, "manager": args.manager,
           "team": args.team, "email": args.email, "slack_id": args.slack_id, "status": "active"}
    people.append({k: v for k, v in rec.items() if v})
    if not comments:
        comments = ["# Org chart. Manager is a person id. Edit freely: scripts only add records, never rewrite yours."]
    pl.write_org(comments, people)
    pl.emit({"status": "success", "added": args.id, "people": len(people)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
