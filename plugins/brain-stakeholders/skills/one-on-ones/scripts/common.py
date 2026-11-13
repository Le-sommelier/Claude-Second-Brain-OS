"""Shared helpers for the 1:1 drafts brick: roster, ledger, queue, style rules."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "person" / "scripts"))
import peoplelib as pl  # noqa: E402
from brainos.workspace import root, path, rel, emit  # noqa: E402,F401

SECTION_KEYS = ["discussed", "decisions", "feedback", "career", "carryover"]
MAX_BULLETS, MAX_BULLET_WORDS, MAX_TOTAL_WORDS, MAX_ACTIONS = 4, 25, 170, 6
MTG_DATE_RE = re.compile(r"mtg-(\d{4}-\d{2}-\d{2})-")
FORBIDDEN_TEXT = re.compile(r"\[\[|source_transcript|wiki_processed|^---", re.M)


def roster_doc() -> dict:
    p = path("stakeholders", "roster")
    if not p.is_file():
        raise SystemExit(f"{rel(p)} missing: copy the roster template during setup and list the people whose 1:1s you want drafted")
    return json.loads(p.read_text(encoding="utf-8"))


def roster() -> list[dict]:
    return [r for r in roster_doc().get("people", []) if r.get("person_id")]


def ledger_path() -> Path:
    return path("stakeholders", "ledger")


def init_ledger(since: str) -> None:
    p = ledger_path()
    if p.exists():
        raise SystemExit(f"{rel(p)} already exists; it holds the go-live date and is never recreated")
    save_ledger({"since": since, "drafted": {}, "pushed": {}})


def load_ledger() -> dict:
    p = ledger_path()
    if not p.is_file():
        raise SystemExit(f"{rel(p)} missing: run detect.py --init once (it records today as the go-live date, so nothing is back-filled)")
    data = json.loads(p.read_text(encoding="utf-8"))
    for key in ("since", "drafted", "pushed"):
        if key not in data:
            raise SystemExit(f"ledger malformed: missing '{key}'")
    return data


def save_ledger(data: dict) -> None:
    pl.write_atomic(ledger_path(), json.dumps(data, indent=2, sort_keys=True) + "\n")


def queue_dir() -> Path:
    q = path("stakeholders", "queue")
    q.mkdir(parents=True, exist_ok=True)
    return q


def banned_words() -> list[str]:
    """Phrases from BRAND.md under a 'Words I Never Use' (or 'Banned words') heading."""
    p = path("core", "brand")
    if not p.is_file():
        return []
    m = re.search(r"^##\s+(?:Words I Never Use|Banned words)\s*\n(.*?)(?=\n## |\Z)", p.read_text(encoding="utf-8"), re.S | re.M)
    out = []
    for line in (m.group(1).splitlines() if m else []):
        line = line.strip()
        if line.startswith("- "):
            item = re.sub(r"\(.*?\)", "", line[2:]).strip().lower()
            out.extend(w.strip() for w in item.split("/") if w.strip())
    return out
