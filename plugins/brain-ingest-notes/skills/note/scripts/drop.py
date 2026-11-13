#!/usr/bin/env python3
"""Turn a pasted note (written by the model to a payload file) into an inbox drop file.

    python3 ${CLAUDE_SKILL_DIR}/scripts/drop.py --payload system/run/payloads/note.md [--title T] [--project P] [--people "A, B"] [--tags "x, y"] [--date YYYY-MM-DD]

Writes inbox/notes/YYYY-MM-DD <title-slug>.md with the optional header lines first and the note text
unchanged after them, then deletes the payload. Never overwrites: a name collision gets a -2 suffix.
Run ingest-notes afterwards (or let the orchestrator) to normalise it into raw/notes.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from brainos import payload  # noqa: E402
from brainos.workspace import emit, path, rel  # noqa: E402


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60].strip("-") or "note"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--payload", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--project", default="")
    ap.add_argument("--people", default="")
    ap.add_argument("--tags", default="")
    ap.add_argument("--date", default=date.today().isoformat())
    a = ap.parse_args()
    try:
        p = Path(a.payload)
        if not p.is_file():
            raise FileNotFoundError(f"payload not found: {p}")
        text = p.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("payload is empty: nothing to save")
        header = [f"{k}: {v}" for k, v in (("title", a.title), ("project", a.project), ("people", a.people), ("tags", a.tags)) if v]
        inbox = path("notes", "inbox")
        inbox.mkdir(parents=True, exist_ok=True)
        stem = f"{a.date} {slug(a.title or text.strip().splitlines()[0].lstrip('# '))}"
        dest, n = inbox / f"{stem}.md", 2
        while dest.exists():
            dest = inbox / f"{stem}-{n}.md"
            n += 1
        dest.write_text(("\n".join(header) + "\n\n" if header else "") + text.rstrip("\n") + "\n", encoding="utf-8")
        payload.consume(p)
    except (OSError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 1
    emit({"ok": True, "file": rel(dest)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
