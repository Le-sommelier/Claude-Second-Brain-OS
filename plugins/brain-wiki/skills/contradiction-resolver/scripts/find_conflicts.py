#!/usr/bin/env python3
"""Surface candidate contradictions and duplicates in project logs. Read-only; never edits a log.

    python3 ${CLAUDE_SKILL_DIR}/scripts/find_conflicts.py [--project SLUG] [--window-days 7] [--similarity 0.6]

Deterministic candidates only; the skill's model step decides whether each one is a real conflict.
Kinds:
  rag-split       status entries within --window-days of each other with different RAG
  near-duplicate  two live entries of one facet with very similar text and different IDs
  decision-clash  two accepted decisions in one project with similar titles and no `supersedes`
  resolved-open   an entry still open although a later entry in the same project cites it in `refs`
                  with state closed/done/mitigated
Prints {"count", "candidates": [{kind, project, ids, paths, detail}]}.
"""
from __future__ import annotations

import argparse
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import kbparse  # noqa: E402
from brainos import frontmatter  # noqa: E402
from brainos.workspace import emit, parse_date, path, rel  # noqa: E402

LIVE = {"open", "at-risk", "off-track", "proposed", "slipped"}
DONE = {"closed", "done", "mitigated", "superseded"}


def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project")
    ap.add_argument("--window-days", type=int, default=7)
    ap.add_argument("--similarity", type=float, default=0.6)
    args = ap.parse_args()

    base = path("core", "projects")
    dirs = [base / args.project] if args.project else sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))
    out: list[dict] = []
    for d in dirs:
        entries = kbparse.project_entries(d)
        current = kbparse.latest_by_id(entries)
        status = sorted((e for e in entries if e["facet"] == "status" and e["meta"].get("rag")), key=lambda e: e["date"])
        for i, a in enumerate(status):
            for b in status[i + 1:]:
                if (parse_date(b["date"]) - parse_date(a["date"])).days > args.window_days:
                    break
                if a["meta"]["rag"] != b["meta"]["rag"] and a["id"] != b["id"]:
                    out.append({"kind": "rag-split", "project": d.name, "ids": [a["id"], b["id"]],
                                "paths": [rel(Path(a["path"]))],
                                "detail": f"{a['date']} {a['meta']['rag']} vs {b['date']} {b['meta']['rag']}"})
        live = [e for e in current if e["state"] in LIVE]
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                if a["facet"] == b["facet"] and sim(a["body"], b["body"]) >= args.similarity:
                    out.append({"kind": "near-duplicate", "project": d.name, "ids": [a["id"], b["id"]],
                                "paths": [rel(Path(a["path"]))], "detail": f"text similarity >= {args.similarity}"})
        by_id = {e["id"]: e for e in current}
        for e in sorted(entries, key=lambda x: x["date"]):
            if e["state"] not in DONE:
                continue
            for ref in [r.strip() for r in e["meta"].get("refs", "").split(",") if r.strip()]:
                t = by_id.get(ref)
                if t and t["state"] in LIVE and t["date"] <= e["date"]:
                    out.append({"kind": "resolved-open", "project": d.name, "ids": [ref, e["id"]],
                                "paths": [rel(Path(t["path"]))], "detail": f"{e['id']} ({e['state']}, {e['date']}) cites {ref}, still {t['state']}"})
        decs = []
        for f in sorted((d / "decisions").glob("*.md")) if (d / "decisions").is_dir() else []:
            fm = frontmatter.read(f)
            if fm.get("status") == "accepted" and not fm.get("supersedes"):
                decs.append((fm, f))
        superseded = {str(fm.get("supersedes")) for fm in (frontmatter.read(f) for f in (d / "decisions").glob("*.md"))} if (d / "decisions").is_dir() else set()
        for i, (a, fa) in enumerate(decs):
            for b, fb in decs[i + 1:]:
                if a.get("id") in superseded or b.get("id") in superseded:
                    continue
                if sim(str(a.get("title", "")), str(b.get("title", ""))) >= args.similarity:
                    out.append({"kind": "decision-clash", "project": d.name, "ids": [a.get("id"), b.get("id")],
                                "paths": [rel(fa), rel(fb)], "detail": "similar accepted decisions, none supersedes the other"})
    emit({"count": len(out), "candidates": out})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
