"""Tiny reader for KB v3 facet logs (entry grammar in system/schema/entry-grammar.md).

Shared by the brain-wiki scripts. Not a validator: `brain kb build` owns validation.
Entries inside <!-- human -->...<!-- /human --> fences are skipped, as the grammar requires.
"""
from __future__ import annotations

import re
from pathlib import Path

HEADER = re.compile(r"^## (\d{4}-\d{2}-\d{2}) · ((?:DEC-[a-z0-9-]+|RSK|DEP|MS|STA|RES|HYP)-\d{3}) · (\S+)\s*$")
FENCE = re.compile(r"<!-- human -->.*?<!-- /human -->", re.S)
FACET_FILES = ("status", "risks", "milestones", "resources", "hypotheses")


def parse_log(path: Path) -> list[dict]:
    text = FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), path.read_text(encoding="utf-8"))
    lines = text.splitlines()
    out: list[dict] = []
    i = 0
    while i < len(lines):
        m = HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        entry = {"date": m.group(1), "id": m.group(2), "state": m.group(3), "line": i + 1,
                 "facet": path.stem, "path": str(path), "meta": {}, "body": ""}
        j = i + 1
        if j < len(lines) and lines[j].startswith("by: "):
            for part in lines[j].split(" · "):
                k, _, v = part.partition(": ")
                entry["meta"][k.strip()] = v.strip()
            j += 1
        body = []
        while j < len(lines) and not lines[j].startswith("## "):
            body.append(lines[j])
            j += 1
        entry["body"] = " ".join(" ".join(body).split())
        out.append(entry)
        i = j
    return out


def project_entries(project_dir: Path) -> list[dict]:
    entries: list[dict] = []
    for facet in FACET_FILES:
        f = project_dir / f"{facet}.md"
        if f.is_file():
            for e in parse_log(f):
                e["project"] = project_dir.name
                entries.append(e)
    return entries


def latest_by_id(entries: list[dict]) -> list[dict]:
    """Current state: the last entry per ID (latest date, then file order)."""
    best: dict[str, dict] = {}
    for e in sorted(entries, key=lambda x: (x["date"], x["line"])):
        best[e["id"]] = e
    return list(best.values())
