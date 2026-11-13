#!/usr/bin/env python3
"""Normalise every transcript inbox into raw/meetings/YYYY/YYYY-Www/. Script-only brick, no model.

    python3 ${CLAUDE_SKILL_DIR}/scripts/prepare.py [--dry-run]

Inboxes (paths.json meetings.*):
  teams_inbox  *.vtt written by ingest-teams (route "m365"; optional <name>.meta.json with invited names)
  inbox        *.vtt, *.txt, *.docx dropped by hand (route "drop")
Target: raw/meetings/YYYY/YYYY-Www/mtg-YYYY-MM-DD-<slug>.md, frontmatter + the transcript as
"Speaker: text" lines, wiki_processed/todo_processed false. Existing targets are never
overwritten (a -2 suffix is added). Originals move to meetings.processed; nothing is deleted.

Dedupe: the same meeting arriving by both routes (same day, and same title or start within
same_meeting_minutes, or identical transcript text) counts once. The m365 copy wins; the other
goes to the week's duplicates/ folder. A per-week _origin.json remembers where each file came from.
Prints a brick-contract return object.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from brainos import frontmatter  # noqa: E402
from brainos.workspace import emit, owner, path, rel, week_dir  # noqa: E402

FULL_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2})\.(\d{2})\.(\d{2}) (.+)$")
DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})[ _]+(.+)$")
UNDERSCORE_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})_(.+)$")
VTT_TIMING = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}")
VTT_VOICE = re.compile(r"^<v\s+([^>]+)>(.*?)(?:</v>)?$")
CUE_ID = re.compile(r"^(?:[\w-]+/\d+-\d+|\d+)$")
SPEAKER_LINE = re.compile(r"^([A-Z][^:\n]{1,40}):\s+\S")
DOCX_HEADER = re.compile(r"^(.+?)\s+\d{1,2}:\d{2}(?::\d{2})?$")
ORIGIN_INDEX = "_origin.json"
SAME_MEETING_MINUTES = 10
SKIP_REASONS = ("left in inbox",)


# ---------- names, dates, slugs ----------

def slug(s: str, n: int = 60) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n].strip("-") or "meeting"


def parse_name(stem: str, fallback: datetime) -> tuple[datetime, str]:
    """(meeting datetime, clean title) from a filename stem; else the file's timestamp."""
    if m := FULL_PREFIX.match(stem):
        return datetime.strptime(f"{m[1]} {m[2]}:{m[3]}:{m[4]}", "%Y-%m-%d %H:%M:%S"), m[5]
    if m := UNDERSCORE_NAME.match(stem):
        return datetime.strptime(f"{m[1]} {m[2]}:{m[3]}", "%Y-%m-%d %H:%M"), m[4]
    if m := DATE_PREFIX.match(stem):
        return datetime.strptime(m[1], "%Y-%m-%d"), m[2]
    return fallback, stem


def file_time(p: Path) -> datetime:
    st = p.stat()
    return datetime.fromtimestamp(getattr(st, "st_birthtime", None) or st.st_mtime)


def person_slug(display: str) -> str:
    """'Morgan, Alex (Fernhill)' and 'Alex Morgan' both give 'alex-morgan'."""
    name = re.sub(r"\(.*?\)", "", display).strip()
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    return slug(name)


def is_owner(display: str) -> bool:
    o = owner()
    s = person_slug(display)
    return bool(s) and s in {o.get("person_id"), person_slug(o.get("name") or "")} - {None, "", "meeting"}


def attendance(speakers: list[str], invited: list[str]) -> str:
    """attended | invited-absent | not-invited, computed against owner().person_id."""
    if any(is_owner(s) for s in speakers):
        return "attended"
    if any(is_owner(i) for i in invited):
        return "invited-absent"
    return "not-invited"


# ---------- transcript readers ----------

def vtt_to_text(raw: str) -> str:
    """WebVTT -> one 'Speaker: text' line per speaker turn."""
    out, speaker, block = [], None, []
    for line in raw.splitlines():
        line = line.rstrip()
        if not line or line.startswith(("WEBVTT", "NOTE", "STYLE")) or VTT_TIMING.match(line) or CUE_ID.match(line):
            continue
        m = VTT_VOICE.match(line)
        if m:
            who, text = m[1].strip(), m[2].strip()
            if who != speaker:
                if block:
                    out.append(f"{speaker}: {' '.join(block)}")
                speaker, block = who, []
            if text:
                block.append(text)
        elif speaker:
            block.append(re.sub(r"</?v[^>]*>", "", line).strip())
    if block:
        out.append(f"{speaker}: {' '.join(block)}")
    return "\n".join(out)


def docx_to_text(p: Path) -> str:
    """Paragraph text of a .docx (stdlib only). 'Name  0:03' header paragraphs become 'Name: text' turns."""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(p) as z:
        tree = ElementTree.fromstring(z.read("word/document.xml"))
    paras = ["".join(t.text or "" for t in para.iter(f"{ns}t")).strip() for para in tree.iter(f"{ns}p")]
    paras = [x for x in paras if x]
    if paras and all(DOCX_HEADER.match(x) for x in paras[::2][:3]) and len(paras) > 1:
        out, i = [], 0
        while i < len(paras):
            m = DOCX_HEADER.match(paras[i])
            if m and i + 1 < len(paras):
                out.append(f"{m[1].strip()}: {paras[i + 1]}")
                i += 2
            else:
                out.append(paras[i])
                i += 1
        return "\n".join(out)
    return "\n".join(paras)


def read_transcript(p: Path) -> str:
    if p.suffix.lower() == ".vtt":
        return vtt_to_text(p.read_text(encoding="utf-8"))
    if p.suffix.lower() == ".docx":
        return docx_to_text(p)
    return p.read_text(encoding="utf-8").strip()


def speakers_of(text: str) -> list[str]:
    seen: list[str] = []
    for line in text.splitlines():
        m = SPEAKER_LINE.match(line)
        if m and m[1].strip() not in seen:
            seen.append(m[1].strip())
    return seen


# ---------- origin index, dedupe, placement ----------

def load_origin(week: Path) -> dict:
    p = week / ORIGIN_INDEX
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}  # bad JSON raises: nothing overwritten


def save_origin(week: Path, index: dict) -> None:
    week.mkdir(parents=True, exist_ok=True)
    (week / ORIGIN_INDEX).write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def same_meeting(m: dict, dt: datetime, name: str, sha: str) -> bool:
    if m.get("sha") == sha:
        return True
    if m["date"] != f"{dt:%Y-%m-%d}":
        return False
    if m["slug"] == slug(name):
        return True
    return abs(m["minute"] - (dt.hour * 60 + dt.minute)) <= SAME_MEETING_MINUTES


def unique(dest: Path) -> Path:
    n, base = 2, dest
    while dest.exists():
        dest = base.with_name(f"{base.stem} ({n}){base.suffix}")
        n += 1
    return dest


def move_to(folder: Path, p: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    dest = unique(folder / p.name)
    shutil.move(str(p), str(dest))
    return dest


def target_for(dt: datetime, name: str, base_dir: Path) -> Path:
    base = f"mtg-{dt:%Y-%m-%d}-{slug(name)}"
    week = week_dir(base_dir, dt.date())
    dest, n = week / f"{base}.md", 2
    while dest.exists() or (week / f"{dest.stem}.txt").exists() or (week / f"{dest.stem}.summary.md").exists():
        dest = week / f"{base}-{n}.md"
        n += 1
    return dest


def sidecar(src: Path) -> Path:
    return src.with_suffix(".meta.json")


def prepare(dry: bool) -> dict:
    meetings, processed = path("meetings", "root"), path("meetings", "processed")
    routes = [("m365", path("meetings", "teams_inbox"), ("*.vtt",)),
              ("drop", path("meetings", "inbox"), ("*.vtt", "*.txt", "*.docx"))]  # m365 first: it wins duplicates
    counts = {"m365": 0, "drop": 0, "skipped": 0, "duplicates": 0}
    outputs: list[str] = []
    warnings: list[str] = []
    observations: list[str] = []

    for route, inbox, patterns in routes:
        files = sorted({f for pat in patterns for f in (inbox.glob(pat) if inbox.exists() else [])
                        if not f.name.startswith(("_", "."))})
        for src in files:
            try:
                text = read_transcript(src)
                if not text.strip():
                    warnings.append(f"{route}: {src.name} has no speech after conversion, left in inbox")
                    counts["skipped"] += 1
                    continue
                dt, name = parse_name(src.stem, file_time(src))
                week = week_dir(meetings, dt.date())
                index = load_origin(week)
                sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
                same = {s: m for s, m in index.items() if same_meeting(m, dt, name, sha)}
                if route == "drop" and same:
                    observations.append(f"duplicate: {src.name} matches {sorted(same)[0]} already in raw, moved to duplicates/")
                    if not dry:
                        move_to(week / "duplicates", src)
                        if sidecar(src).exists():
                            move_to(week / "duplicates", sidecar(src))
                    counts["duplicates"] += 1
                    continue
                if route == "m365":
                    for stem, m in same.items():
                        if m["origin"] != "drop":
                            continue
                        observations.append(f"duplicate: {stem} is a hand-dropped copy of an m365 meeting, moved to duplicates/")
                        if not dry:
                            for f in (week / f"{stem}.md", week / f"{stem}.txt", week / f"{stem}.summary.md"):
                                if f.exists():
                                    move_to(week / "duplicates", f)
                            index.pop(stem, None)
                        counts["duplicates"] += 1
                    mdup = [s for s, m in same.items() if m["origin"] == "m365"]
                    if mdup:
                        observations.append(f"duplicate: {src.name} is already ingested as {mdup[0]}, moved to duplicates/")
                        if not dry:
                            move_to(week / "duplicates", src)
                        counts["duplicates"] += 1
                        continue

                meta = {}
                if sidecar(src).exists():
                    meta = json.loads(sidecar(src).read_text(encoding="utf-8"))
                speakers = speakers_of(text)
                fields = {
                    "id": None,
                    "source_type": "meeting",
                    "title": name,
                    "date": f"{dt:%Y-%m-%d}",
                    "time": f"{dt:%H:%M}",
                    "origin": route,
                    "source_file": src.name,
                    "participants": speakers,
                    "attendance": attendance(speakers, meta.get("invited", [])),
                    "tags": [],
                    "sensitivity": "internal",
                    "wiki_processed": False,
                    "todo_processed": False,
                }
                dest = target_for(dt, name, meetings)
                fields["id"] = dest.stem
                if not dry:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(frontmatter.render(fields) + f"\n# {name}\n\n{text}\n", encoding="utf-8")
                    index[dest.stem] = {"origin": route, "date": f"{dt:%Y-%m-%d}", "minute": dt.hour * 60 + dt.minute,
                                        "slug": slug(name), "sha": sha}
                    save_origin(week, index)
                    move_to(processed, src)
                    if sidecar(src).exists():
                        move_to(processed, sidecar(src))
                outputs.append(rel(dest) if not dry else str(dest))
                counts[route] += 1
            except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
                warnings.append(f"{route}: {src.name}: {exc}")

    errors = [w for w in warnings if not w.endswith(SKIP_REASONS)]
    return {
        "brick": "brain-ingest-teams:ingest-meeting-files",
        "status": "partial" if errors else ("success" if outputs or counts["duplicates"] else "skipped"),
        "counts": {**counts, "written": len(outputs)},
        "outputs": outputs,
        "warnings": warnings,
        "observations": observations,
        "reason": None if outputs or errors or counts["duplicates"] else "inboxes empty",
        "dry_run": dry,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    emit(prepare(ap.parse_args().dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
