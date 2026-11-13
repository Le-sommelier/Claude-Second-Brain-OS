"""Shared helpers for the brain-mentoring scripts: folder shape, goals, actions log, validation.

Folder: growth/mentoring/<person-id>/{README.md, sessions/YYYY-MM-DD-session.md, actions.md}.
Everything lives under growth/ so it is confidential by default and wrapped in redact-on-share markers.
Sibling skills add this folder to sys.path and import it.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
from brainos.workspace import root, path, rel, emit, owner, parse_date  # noqa: E402,F401
from brainos import frontmatter  # noqa: E402,F401
from brainos.confidential import OPEN, CLOSE  # noqa: E402,F401

ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ACTION_RE = re.compile(
    r"^- \[(?P<box>[ xX])\] (?P<id>A-\d{3}) · (?P<opened>\d{4}-\d{2}-\d{2}) · owner: (?P<owner>[a-z0-9-]+)"
    r"(?: · due: (?P<due>\d{4}-\d{2}-\d{2}))? · (?P<what>.+?)(?: · closed: (?P<closed>\d{4}-\d{2}-\d{2}))?\s*$")
GOAL_RE = re.compile(r"^-\s+(G\d+):\s+(.+?)\s*$")
CADENCE_DAYS = {"weekly": 7, "fortnightly": 14, "monthly": 30, "quarterly": 91}


def mentoring_root() -> Path:
    return path("mentoring", "root")


def person_dir(person: str, must_exist: bool = True) -> Path:
    if not ID_RE.match(person):
        raise SystemExit(f"person id must look like first-last, got '{person}'")
    d = mentoring_root() / person
    if must_exist and not d.is_dir():
        raise SystemExit(f"no mentorship folder for {person}: run mentoring-setup first")
    return d


def wrap(block: str) -> str:
    return f"{OPEN}\n{block.strip()}\n{CLOSE}\n"


def read_readme(d: Path) -> tuple[dict, list[dict]]:
    text = (d / "README.md").read_text(encoding="utf-8")
    goals = [{"id": m.group(1), "text": m.group(2)} for ln in text.splitlines() if (m := GOAL_RE.match(ln.strip()))]
    return frontmatter.parse(text), goals


def parse_actions(d: Path) -> list[dict]:
    p = d / "actions.md"
    out = []
    if p.is_file():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if (m := ACTION_RE.match(ln)):
                a = m.groupdict()
                a["done"] = a.pop("box").lower() == "x"
                out.append(a)
    return out


def action_line(a: dict) -> str:
    due = f" · due: {a['due']}" if a.get("due") else ""
    closed = f" · closed: {a['closed']}" if a.get("closed") else ""
    box = "x" if a.get("done") else " "
    return f"- [{box}] {a['id']} · {a['opened']} · owner: {a['owner']}{due} · {a['what']}{closed}"


def next_action_id(actions: list[dict]) -> str:
    n = max((int(a["id"][2:]) for a in actions), default=0) + 1
    return f"A-{n:03d}"


def session_files(d: Path) -> list[Path]:
    s = d / "sessions"
    return sorted(s.glob("*.md")) if s.is_dir() else []


def session_date(p: Path) -> str:
    return p.name[:10]


def write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)
