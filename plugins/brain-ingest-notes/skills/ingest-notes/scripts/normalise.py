#!/usr/bin/env python3
"""Normalise hand-dropped notes into raw/notes/YYYY/YYYY-Www/. Script-only brick, no model.

    python3 ${CLAUDE_SKILL_DIR}/scripts/normalise.py [--dry-run]

Inbox: paths.json notes.inbox (inbox/notes): *.md and *.txt. Files starting with _ or . are ignored.
Target: raw/notes/YYYY/YYYY-Www/note-YYYY-MM-DD-<slug>.md with frontmatter:
  id, source_type: note, title, date, tags, people, project, sensitivity, source_file,
  content_sha, wiki_processed: false, todo_processed: false
The body is the note text exactly as written (minus the optional header). Existing targets are never
overwritten (-2 suffix). Originals move to notes.processed; nothing is deleted. A note whose body is
identical to one already in raw/notes is a duplicate: its original is archived and nothing is written.

Optional header: the first lines of a file, up to the first blank line or non-header line, or a YAML
frontmatter block. Keys (case-insensitive):
  title:   people:   tags:   project:   date: YYYY-MM-DD   sensitivity: confidential
`people:` takes names ("First Last") or person IDs; `tags:` and `people:` are comma- or semicolon-separated.
`project:` is kept only when the owner wrote it; otherwise it stays null for the wiki step to decide.
Prints a brick-contract return object.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from brainos import confidential, frontmatter  # noqa: E402
from brainos.workspace import emit, path, rel, week_dir  # noqa: E402

HEADER_KEYS = ("title", "people", "tags", "project", "date", "sensitivity")
HEADER_LINE = re.compile(rf"^({'|'.join(HEADER_KEYS)})\s*:\s*(.*)$", re.IGNORECASE)
DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})[ _-]+(.+)$")
DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def slug(s: str, n: int = 60) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n].strip("-") or "note"


def split_list(value: str) -> list[str]:
    return [v.strip() for v in re.split(r"[;,]", value.strip().strip("[]")) if v.strip()]


def parse_header(text: str) -> tuple[dict, str]:
    """({header fields}, body). Handles a YAML frontmatter block or leading `key: value` lines."""
    text = text.lstrip("﻿")
    fm_text, rest = frontmatter.split(text)
    header: dict = {}
    if fm_text is not None:
        for k, v in frontmatter.parse(text).items():
            if k.lower() in HEADER_KEYS:
                header[k.lower()] = ", ".join(v) if isinstance(v, list) else ("" if v is None else str(v))
        return header, rest.lstrip("\n")
    lines = text.split("\n")
    i = 0
    while i < len(lines) and (m := HEADER_LINE.match(lines[i])):
        header[m[1].lower()] = m[2].strip()
        i += 1
    if not header:
        return {}, text
    if i < len(lines) and lines[i].strip() == "":
        i += 1  # the blank line that ends the header belongs to the header
    return header, "\n".join(lines[i:])


def person_slug(display: str) -> str:
    name = re.sub(r"\(.*?\)", "", display).strip().lstrip("@")
    return slug(name)


def note_date(header: dict, stem: str, src: Path) -> tuple[date, str]:
    """(date, filename-title). Header date wins, then a YYYY-MM-DD filename prefix, then the file time."""
    m = DATE_PREFIX.match(stem)
    name = m[2] if m else stem
    candidate = header.get("date", "")
    if candidate and DATE_ONLY.match(candidate[:10]):
        return date.fromisoformat(candidate[:10]), name
    if m:
        return date.fromisoformat(m[1]), m[2]
    if DATE_ONLY.match(stem):
        return date.fromisoformat(stem), "note"
    st = src.stat()
    return datetime.fromtimestamp(getattr(st, "st_birthtime", None) or st.st_mtime).date(), name


def title_of(header: dict, body: str, filename_title: str) -> str:
    if header.get("title"):
        return header["title"]
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
        if line.strip():
            break
    t = re.sub(r"[-_]+", " ", filename_title).strip()
    return t.capitalize() if t else "Note"


def target_for(d: date, title: str, base_dir: Path) -> Path:
    base = f"note-{d:%Y-%m-%d}-{slug(title)}"
    week = week_dir(base_dir, d)
    dest, n = week / f"{base}.md", 2
    while dest.exists():
        dest = week / f"{base}-{n}.md"
        n += 1
    return dest


def archive(folder: Path, src: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    dest, n = folder / src.name, 2
    while dest.exists():
        dest = folder / f"{src.stem} ({n}){src.suffix}"
        n += 1
    shutil.move(str(src), str(dest))
    return dest


def known_hashes(raw_root: Path) -> set[str]:
    out = set()
    for f in raw_root.rglob("note-*.md") if raw_root.exists() else []:
        sha = frontmatter.read(f).get("content_sha")
        if sha:
            out.add(str(sha))
    return out


def normalise(dry: bool) -> dict:
    inbox, processed, raw_root = path("notes", "inbox"), path("notes", "processed"), path("notes", "root")
    files = sorted(f for pat in ("*.md", "*.txt") for f in (inbox.glob(pat) if inbox.exists() else [])
                   if not f.name.startswith(("_", ".")))
    seen = known_hashes(raw_root)
    outputs: list[str] = []
    warnings: list[str] = []
    counts = {"written": 0, "duplicates": 0, "skipped": 0}
    for src in files:
        try:
            header, body = parse_header(src.read_text(encoding="utf-8"))
            if not body.strip():
                warnings.append(f"{src.name}: empty note, left in inbox")
                counts["skipped"] += 1
                continue
            sha = hashlib.sha256(body.strip().encode("utf-8")).hexdigest()[:16]
            if sha in seen:
                warnings.append(f"{src.name}: identical to a note already in raw/notes, archived without writing")
                counts["duplicates"] += 1
                if not dry:
                    archive(processed, src)
                continue
            d, fname_title = note_date(header, src.stem, src)
            title = title_of(header, body, fname_title)
            secret = header.get("sensitivity", "").lower() == "confidential"
            fields = {
                "id": None,
                "source_type": "note",
                "title": title,
                "date": d.isoformat(),
                "tags": [slug(t) for t in split_list(header.get("tags", ""))],
                "people": [p for p in (person_slug(x) for x in split_list(header.get("people", ""))) if p],
                "project": slug(header["project"]) if header.get("project") else None,
                "sensitivity": "confidential" if secret else "internal",
                "source_file": src.name,
                "content_sha": sha,
                "wiki_processed": False,
                "todo_processed": False,
            }
            dest = target_for(d, title, raw_root)
            fields["id"] = dest.stem
            text = body.rstrip("\n")
            content = confidential.wrap(text) if secret else text
            if not dry:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open("x", encoding="utf-8") as fh:  # exclusive create: never overwrite
                    fh.write(frontmatter.render(fields) + f"\n{content}\n")
                archive(processed, src)
            seen.add(sha)
            outputs.append(rel(dest) if not dry else str(dest))
            counts["written"] += 1
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            warnings.append(f"{src.name}: {exc}")
    errors = [w for w in warnings if not w.endswith(("left in inbox", "without writing"))]
    return {
        "brick": "brain-ingest-notes:ingest-notes",
        "status": "partial" if errors else ("success" if outputs or counts["duplicates"] else "skipped"),
        "counts": counts,
        "outputs": outputs,
        "warnings": warnings,
        "observations": [],
        "reason": None if outputs or errors or counts["duplicates"] else "inbox empty",
        "dry_run": dry,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    emit(normalise(ap.parse_args().dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
