"""The pending queue: raw files still waiting for a downstream skill, and flag flipping.

A file is pending when its frontmatter flag (default `wiki_processed`) is `false`.
A missing flag means "not a queue item".
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from brainos import frontmatter
from brainos.workspace import parse_date, path, rel, root

FLAGS = {"wiki_processed", "todo_processed"}
_DATE_KEYS = ("date", "clipped", "last_modified", "fetched_at")
_SKIP_TYPES = ("index", "owed-replies")


def _item_date(fm: dict) -> str | None:
    for key in _DATE_KEYS:
        if fm.get(key):
            return str(fm[key])[:10]
    return None


def scan(flag: str = "wiki_processed", source_types: set[str] | None = None,
         max_age_days: int | None = None, today: date | None = None) -> dict:
    if flag not in FLAGS:
        raise ValueError(f"flag must be one of {sorted(FLAGS)}")
    today = today or date.today()
    base = path("core", "raw")
    items, stale = [], []
    for p in sorted(base.rglob("*.md")):
        if any(part.startswith((".", "_")) for part in p.relative_to(base).parts):
            continue
        fm = frontmatter.read(p)
        if fm.get(flag) is not False or str(fm.get("type", "")).startswith(_SKIP_TYPES):
            continue
        stype = str(fm.get("source_type") or p.relative_to(base).parts[0])
        if source_types and stype not in source_types:
            continue
        d = _item_date(fm)
        entry = {
            "path": rel(p),
            "source_type": stype,
            "date": d,
            "title": fm.get("title") or fm.get("channel") or p.stem,
            "tags": fm.get("tags") or [],
            "sensitivity": fm.get("sensitivity") or "internal",
        }
        if max_age_days is not None and d and (today - parse_date(d)).days > max_age_days:
            stale.append(entry)
        else:
            items.append(entry)
    return {"flag": flag, "count": len(items), "items": items, "stale": stale}


def set_flag(files: list[str], flag: str, value: bool) -> tuple[list[str], list[str]]:
    if flag not in FLAGS:
        raise ValueError(f"flag must be one of {sorted(FLAGS)}")
    updated, errors = [], []
    for f in files:
        p = Path(f) if Path(f).is_absolute() else root() / f
        try:
            frontmatter.update_file(p, {flag: value})
            updated.append(f)
        except (OSError, ValueError) as exc:
            errors.append(f"{f}: {exc}")
    return updated, errors
